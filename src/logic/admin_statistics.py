import csv
import io
import logging
from datetime import datetime
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
        admin_username: Optional[str],
        action_type: str,
        user_id: Optional[int] = None,
        amount: Optional[Decimal] = None,
        hookah_count: Optional[int] = None
) -> None:
    query = """
    INSERT INTO admin_actions 
    (admin_id, admin_username, action_type, user_id, amount, hookah_count)
    VALUES ($1, $2, $3, $4, $5, $6)
    """
    try:
        await db_manager.execute(
            query,
            admin_id,
            admin_username,
            action_type,
            user_id,
            float(amount) if amount is not None else None,
            hookah_count
        )
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}", exc_info=True)


async def generate_all_time_daily_waiters_report_csv() -> str | None:
    query = """
    SELECT
        DATE(aa.action_date AT TIME ZONE 'UTC') as report_date,
        aa.admin_id,
        COALESCE(aa.admin_username, 'Невідомий') as admin_username,
        COUNT(DISTINCT CASE WHEN aa.action_type = 'user_registered' THEN aa.user_id END) as new_users_registered_today,
        COALESCE(SUM(CASE WHEN aa.action_type = 'transaction' THEN aa.amount ELSE 0 END), 0) as total_amount_today
    FROM admin_actions aa
    WHERE aa.admin_id = ANY($1::bigint[]) -- Filter for regular admins
    GROUP BY report_date, aa.admin_id, aa.admin_username
    ORDER BY report_date DESC, admin_username ASC;
    """

    admin_ids = list(set(settings.admin_ids) - set(settings.super_admin_ids))

    if not admin_ids:
        logger.warning("No regular admin IDs found for waiters report (only super admins exist or no admins).")
        return "Немає даних: звичайні адміністратори не налаштовані."

    try:
        records = await db_manager.fetch_all(query, admin_ids)

        if not records:
            logger.info("No admin actions found to generate waiters report.")
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
                'Ім\'я Офіціанта': record['admin_username'],
                'Зареєстровано клієнтів (за день)': record['new_users_registered_today'],
                'Сума продажів (за день, грн)': f"{float(record['total_amount_today']):.2f}"
            })

        csv_content = output.getvalue()
        output.close()
        logger.info(f"Successfully generated all-time daily waiters report with {len(records)} entries.")
        return csv_content

    except Exception as e:
        logger.error(f"Error generating all-time daily waiters report: {e}", exc_info=True)
        return None


async def send_waiters_report(bot: Bot, chat_id: int) -> bool:
    try:
        csv_content = await generate_all_time_daily_waiters_report_csv()

        if csv_content is None:
            await bot.send_message(
                chat_id=chat_id,
                text=get_message('admin_panel.no_data_for_report'),
                reply_markup=get_goto_admin_panel()
            )
            logger.info("No data for waiters report, informed admin.")
            return False
        elif csv_content == "Немає даних: звичайні адміністратори не налаштовані.":
            await bot.send_message(
                chat_id=chat_id,
                text=csv_content,
                reply_markup=get_goto_admin_panel()
            )
            logger.info("No regular admins configured for waiters report, informed admin.")
            return False

        report_bytes = csv_content.encode('utf-8-sig')
        filename = f"waiters_report{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        report_file = BufferedInputFile(file=report_bytes, filename=filename)

        await bot.send_document(
            chat_id=chat_id,
            document=report_file,
            caption=get_message('admin_panel.all_waiters_daily_report_caption'),
            reply_markup=get_goto_admin_panel()
        )
        logger.info(f"Sent all-time daily waiters report to chat_id {chat_id}.")
        return True

    except Exception as e:
        logger.error(f"Error sending waiters report to {chat_id}: {e}", exc_info=True)
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=get_message('admin_panel.report_generation_error'),
                reply_markup=get_goto_admin_panel()
            )
        except Exception as inner_e:
            logger.error(f"Failed to send error message to admin {chat_id}: {inner_e}")
        return False