import csv
import io
import logging
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional

from aiogram import Bot
from aiogram.types import BufferedInputFile

from src.config import settings
from src.database.manager import db_manager
from src.utils.keyboards import get_goto_admin_panel
from src.utils.messages import get_message

logger = logging.getLogger(__name__)


async def log_admin_action(
        admin_id: int,
        admin_name: Optional[str],
        admin_username: Optional[str],
        action_type: str,
        user_id: Optional[int] = None,
        client_name: Optional[str] = None,
        client_phone_number: Optional[str] = None,
        amount: Optional[Decimal] = None,
        hookah_count: Optional[int] = None
) -> None:
    query = """
    INSERT INTO admin_actions
    (admin_id, admin_name, admin_username, action_type, user_id, client_name, client_phone_number, amount, hookah_count)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
    """
    try:
        await db_manager.execute(
            query,
            admin_id,
            admin_name,
            admin_username,
            action_type,
            user_id,
            client_name,
            client_phone_number,
            float(amount) if amount is not None else None,
            hookah_count
        )
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}", exc_info=True)


async def generate_waiters_report_csv(start_date_filter: Optional[date] = None,
                                      end_date_filter: Optional[date] = None) -> str | None:
    regular_admin_ids = list(set(settings.admin_ids) - set(settings.super_admin_ids))

    if not regular_admin_ids:
        logger.warning(
            "No regular admin IDs found for waiters report. Only super admins exist or no admins are configured.")
        return "Немає даних: звичайні адміністратори не налаштовані."

    base_query = """
    SELECT
        DATE(aa.action_date AT TIME ZONE 'UTC') as report_date,
        aa.admin_id,
        COALESCE(aa.admin_name, aa.admin_username, aa.admin_id::text) as admin_display_name,
        COUNT(DISTINCT CASE WHEN aa.action_type = 'user_registered' THEN aa.user_id END) as new_users_registered_today,
        COALESCE(SUM(CASE WHEN aa.action_type = 'transaction' THEN aa.amount ELSE 0 END), 0) as total_amount_today
    FROM admin_actions aa
    WHERE aa.admin_id = ANY($1::bigint[])
    """
    params: list = [regular_admin_ids]

    date_conditions = []
    param_idx = 2

    if start_date_filter:
        date_conditions.append(f"(aa.action_date AT TIME ZONE 'UTC')::date >= ${param_idx}")
        params.append(start_date_filter)
        param_idx += 1
    if end_date_filter:
        date_conditions.append(f"(aa.action_date AT TIME ZONE 'UTC')::date <= ${param_idx}")
        params.append(end_date_filter)
        param_idx += 1

    if date_conditions:
        base_query += " AND " + " AND ".join(date_conditions)

    query = base_query + """
    GROUP BY report_date, aa.admin_id, admin_display_name
    ORDER BY report_date DESC, admin_display_name ASC;
    """

    try:
        records = await db_manager.fetch_all(query, *params)

        if not records:
            logger.info(
                f"No admin actions found for the period to generate waiters report. Start: {start_date_filter}, End: {end_date_filter}")
            return None

        output = io.StringIO()
        fieldnames = [
            'Дата',
            'ID Офіціанта',
            'Ім\'я Офіціанта',
            'Зареєстровано клієнтів (за день)',
            'Сума продажів (за день, грн)'
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=',', lineterminator='\n')
        writer.writeheader()

        for record in records:
            writer.writerow({
                'Дата': record['report_date'].strftime('%Y-%m-%d') if record['report_date'] else 'N/A',
                'ID Офіціанта': record['admin_id'],
                'Ім\'я Офіціанта': record['admin_display_name'],
                'Зареєстровано клієнтів (за день)': record['new_users_registered_today'],
                'Сума продажів (за день, грн)': f"{float(record['total_amount_today']):.2f}"
            })

        csv_content = output.getvalue()
        output.close()
        logger.info(
            f"Successfully generated waiters report for period. Start: {start_date_filter}, End: {end_date_filter}. {len(records)} entries.")
        return csv_content

    except Exception as e:
        logger.error(
            f"Error generating waiters report for period. Start: {start_date_filter}, End: {end_date_filter}: {e}",
            exc_info=True)
        return None


async def send_waiters_report(bot: Bot, chat_id: int, start_date: Optional[date] = None,
                              end_date: Optional[date] = None) -> bool:
    try:
        csv_content = await generate_waiters_report_csv(start_date, end_date)

        if csv_content is None:
            await bot.send_message(
                chat_id=chat_id,
                text=get_message('admin_panel.no_data_for_report'),
                reply_markup=get_goto_admin_panel()
            )
            logger.info(f"No data for waiters report (Period: {start_date} to {end_date}), informed admin {chat_id}.")
            return False
        elif csv_content == "Немає даних: звичайні адміністратори не налаштовані.":
            await bot.send_message(
                chat_id=chat_id,
                text=csv_content,
                reply_markup=get_goto_admin_panel()
            )
            logger.info(f"No regular admins configured for waiters report, informed admin {chat_id}.")
            return False

        report_bytes = csv_content.encode('utf-8-sig')

        ""
        if start_date and end_date:
            if start_date == end_date:
                filename_date_part = start_date.strftime('%d.%m.%Y')
            else:
                filename_date_part = f"{start_date.strftime('%d.%m.%Y')}-{end_date.strftime('%d.%m.%Y')}"
            filename = f"waiters_report_date({filename_date_part}).csv"
        else:
            current_time_str = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f"waiters_report_all_time_{current_time_str}.csv"

        report_file = BufferedInputFile(file=report_bytes, filename=filename)

        await bot.send_document(
            chat_id=chat_id,
            document=report_file,
            caption=get_message('admin_panel.all_waiters_daily_report_caption'),
            reply_markup=get_goto_admin_panel()
        )
        logger.info(f"Sent waiters report (Period: {start_date} to {end_date}) to chat_id {chat_id} as {filename}.")
        return True

    except Exception as e:
        logger.error(f"Error sending waiters report (Period: {start_date} to {end_date}) to {chat_id}: {e}",
                     exc_info=True)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=get_message('admin_panel.report_generation_error'),
                reply_markup=get_goto_admin_panel()
            )
        except Exception as inner_e:
            logger.error(f"Failed to send error message to admin {chat_id}: {inner_e}")
        return False


async def generate_serviced_clients_report_csv(start_date_filter: Optional[date] = None,
                                               end_date_filter: Optional[date] = None) -> str | None:
    base_query = """
    SELECT
        (aa.action_date AT TIME ZONE 'UTC')::date as report_date,
        COALESCE(aa.client_name, 'N/A') as client_name,
        COALESCE(aa.client_phone_number, 'N/A') as client_phone_number,
        aa.amount as check_amount,
        aa.hookah_count as ordered_hookahs,
        COALESCE(aa.admin_name, aa.admin_username, aa.admin_id::text) as admin_display_name
    FROM admin_actions aa
    WHERE aa.action_type = 'transaction'
    """
    params: list = []
    param_idx = 1

    date_conditions = []
    if start_date_filter:
        date_conditions.append(f"(aa.action_date AT TIME ZONE 'UTC')::date >= ${param_idx}")
        params.append(start_date_filter)
        param_idx += 1
    if end_date_filter:
        date_conditions.append(f"(aa.action_date AT TIME ZONE 'UTC')::date <= ${param_idx}")
        params.append(end_date_filter)
        param_idx += 1

    if date_conditions:
        base_query += " AND " + " AND ".join(date_conditions)

    query = base_query + " ORDER BY aa.action_date DESC;"

    try:
        records = await db_manager.fetch_all(query, *params)

        if not records:
            logger.info(
                f"No serviced client transactions found for the period. Start: {start_date_filter}, End: {end_date_filter}")
            return None

        output = io.StringIO()
        fieldnames = [
            'Дата',
            'Ім\'я клієнта',
            'Номер телефону клієнта',
            'Сума чеку (грн)',
            'К-сть кальянів',
            'Обслуговував адмін'
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=',', lineterminator='\n')
        writer.writeheader()

        for record in records:
            writer.writerow({
                'Дата': record['report_date'].strftime('%Y-%m-%d') if record['report_date'] else 'N/A',
                'Ім\'я клієнта': record['client_name'],
                'Номер телефону клієнта': f"'{record['client_phone_number']}" if record[
                                                                                     'client_phone_number'] != 'N/A' else 'N/A',
                'Сума чеку (грн)': f"{float(record['check_amount']):.2f}" if record[
                                                                                 'check_amount'] is not None else "0.00",
                'К-сть кальянів': record['ordered_hookahs'] if record['ordered_hookahs'] is not None else 0,
                'Обслуговував адмін': record['admin_display_name']
            })

        csv_content = output.getvalue()
        output.close()
        logger.info(
            f"Successfully generated serviced clients report. Period: {start_date_filter} to {end_date_filter}. {len(records)} entries.")
        return csv_content

    except Exception as e:
        logger.error(
            f"Error generating serviced clients report for period. Start: {start_date_filter}, End: {end_date_filter}: {e}",
            exc_info=True)
        return None


async def send_serviced_clients_report(bot: Bot, chat_id: int, start_date: Optional[date] = None,
                                       end_date: Optional[date] = None) -> bool:
    try:
        csv_content = await generate_serviced_clients_report_csv(start_date, end_date)

        if csv_content is None:
            await bot.send_message(
                chat_id=chat_id,
                text=get_message('admin_panel.no_data_for_report'),
                reply_markup=get_goto_admin_panel()
            )
            logger.info(
                f"No data for serviced clients report (Period: {start_date} to {end_date}), informed admin {chat_id}.")
            return False

        report_bytes = csv_content.encode('utf-8-sig')
        if start_date and end_date:
            if start_date == end_date:
                filename_date_part = start_date.strftime('%d.%m.%Y')
            else:
                filename_date_part = f"{start_date.strftime('%d.%m.%Y')}-{end_date.strftime('%d.%m.%Y')}"
            filename = f"serviced_clients_report_date({filename_date_part}).csv"
        else:
            current_time_str = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f"serviced_clients_report_all_time_{current_time_str}.csv"

        report_file = BufferedInputFile(file=report_bytes, filename=filename)

        await bot.send_document(
            chat_id=chat_id,
            document=report_file,
            caption=get_message('admin_panel.serviced_clients_report_button'),
            reply_markup=get_goto_admin_panel()
        )
        logger.info(
            f"Sent serviced clients report (Period: {start_date} to {end_date}) to chat_id {chat_id} as {filename}.")
        return True

    except Exception as e:
        logger.error(f"Error sending serviced clients report (Period: {start_date} to {end_date}) to {chat_id}: {e}",
                     exc_info=True)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=get_message('admin_panel.report_generation_error'),
                reply_markup=get_goto_admin_panel()
            )
        except Exception as inner_e:
            logger.error(f"Failed to send error message to admin {chat_id}: {inner_e}")
        return False