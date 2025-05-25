import logging
from aiogram import Router, Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery

from src.filters.super_admin_filter import SuperAdminFilter
from src.logic import admin_statistics
from src.utils.messages import get_message
from src.utils.tg_utils import safe_delete_message

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.filter(SuperAdminFilter())

@router.callback_query(F.data == "admin:waiters_report")
async def handle_waiters_report_all_time(callback: CallbackQuery, bot: Bot):
    admin_id = callback.from_user.id
    message = callback.message
    if not message:
        await callback.answer("Помилка: не вдалося знайти повідомлення.", show_alert=True)
        return

    chat_id_for_deletion = message.chat.id
    message_id_to_delete = message.message_id

    logger.info(f"SuperAdmin {admin_id} requested all-time daily waiters report.")

    try:
        await callback.answer(get_message('admin_panel.generating_report'))
    except TelegramAPIError as e:
        logger.warning(f"Failed to send 'generating report' answer to admin {admin_id}: {e}")

    await safe_delete_message(bot, chat_id_for_deletion, message_id_to_delete)

    success = await admin_statistics.send_waiters_report(bot=bot, chat_id=admin_id)

    if not success:
        logger.warning(f"Failed to generate or send all-time daily waiters report for admin {admin_id}.")