import logging
from datetime import datetime, timedelta, date, timezone
from typing import Optional

from aiogram import Router, Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery

from src.filters.super_admin_filter import SuperAdminFilter
from src.logic import admin_statistics
from src.utils.messages import get_message
from src.utils.tg_utils import safe_delete_message
from src.utils.keyboards import get_serviced_clients_report_period_keyboard

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.filter(SuperAdminFilter())

@router.callback_query(F.data == "admin:serviced_clients_report")
async def handle_select_serviced_clients_report_period(callback: CallbackQuery, bot: Bot):
    admin_id = callback.from_user.id
    message = callback.message
    if not message:
        await callback.answer("Помилка: не вдалося знайти повідомлення.", show_alert=True)
        return

    logger.info(f"SuperAdmin {admin_id} requested serviced clients report, showing period selection.")

    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=get_message('admin_panel.select_serviced_clients_report_period'),
            reply_markup=get_serviced_clients_report_period_keyboard()
        )
        await callback.answer()
    except TelegramAPIError as e:
        if "message is not modified" in str(e).lower():
            await callback.answer()
            logger.warning(f"Message not modified for serviced_clients report period selection: {e}")
        else:
            logger.error(f"Error editing message for serviced_clients period selection: {e}", exc_info=True)
            await callback.answer("Сталася помилка.", show_alert=True)


async def _process_serviced_clients_report_request(callback: CallbackQuery, bot: Bot, start_dt: Optional[date], end_dt: Optional[date], period_name: str):
    admin_id = callback.from_user.id
    message = callback.message
    if not message:
        await callback.answer("Помилка: не вдалося знайти повідомлення.", show_alert=True)
        return

    chat_id_for_deletion = message.chat.id
    message_id_to_delete = message.message_id

    logger.info(f"SuperAdmin {admin_id} requested serviced_clients report for period: {period_name}.")

    try:
        await callback.answer(get_message('admin_panel.generating_report'))
    except TelegramAPIError as e:
        logger.warning(f"Failed to send 'generating report' answer to admin {admin_id}: {e}")

    await safe_delete_message(bot, chat_id_for_deletion, message_id_to_delete)

    await admin_statistics.send_serviced_clients_report(
        bot=bot,
        chat_id=admin_id,
        start_date=start_dt,
        end_date=end_dt
    )


@router.callback_query(F.data == "admin:serviced_clients_report_today")
async def handle_serviced_clients_report_today(callback: CallbackQuery, bot: Bot):
    today_utc = datetime.now(timezone.utc).date()
    await _process_serviced_clients_report_request(callback, bot, start_dt=today_utc, end_dt=today_utc, period_name="today")

@router.callback_query(F.data == "admin:serviced_clients_report_week")
async def handle_serviced_clients_report_week(callback: CallbackQuery, bot: Bot):
    today_utc = datetime.now(timezone.utc).date()
    start_of_week = today_utc - timedelta(days=today_utc.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    await _process_serviced_clients_report_request(callback, bot, start_dt=start_of_week, end_dt=end_of_week, period_name="current_week")

@router.callback_query(F.data == "admin:serviced_clients_report_month")
async def handle_serviced_clients_report_month(callback: CallbackQuery, bot: Bot):
    today_utc = datetime.now(timezone.utc).date()
    start_of_month = today_utc.replace(day=1)
    if start_of_month.month == 12:
        next_month_start = start_of_month.replace(year=start_of_month.year + 1, month=1, day=1)
    else:
        next_month_start = start_of_month.replace(month=start_of_month.month + 1, day=1)
    end_of_month = next_month_start - timedelta(days=1)
    await _process_serviced_clients_report_request(callback, bot, start_dt=start_of_month, end_dt=end_of_month, period_name="current_month")

@router.callback_query(F.data == "admin:serviced_clients_report_all_time_final")
async def handle_serviced_clients_report_all_time(callback: CallbackQuery, bot: Bot):
    await _process_serviced_clients_report_request(callback, bot, start_dt=None, end_dt=None, period_name="all_time")