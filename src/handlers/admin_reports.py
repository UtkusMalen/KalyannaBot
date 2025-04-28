import logging
from datetime import datetime

from aiogram import Router, Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, BufferedInputFile

from src.logic import admin_logic
from src.filters.admin_filter import AdminFilter
from src.utils.keyboards import get_goto_admin_panel
from src.utils.messages import get_message
from src.utils.tg_utils import safe_delete_message

logger = logging.getLogger(__name__)
router = Router()
router.callback_query.filter(AdminFilter())

@router.callback_query(F.data == "admin:list_clients")
async def handle_list_clients(callback: CallbackQuery, bot: Bot):
    admin_id = callback.from_user.id
    message = callback.message
    if not message:
        await callback.answer("Помилка: не вдалося знайти повідомлення.", show_alert=True)
        return

    chat_id = message.chat.id
    message_id_to_delete = message.message_id

    logger.info(f"Admin {admin_id} requested clients list.")

    try:
        await callback.answer(get_message('admin_panel.generating_report'))
    except TelegramAPIError as e:
        logger.error(f"Failed to send 'generating report' answer to admin {admin_id}: {e}", exc_info=True)

    await safe_delete_message(bot, chat_id, message_id_to_delete)

    csv_content = await admin_logic.generate_clients_report_csv()

    if csv_content:
        try:
            report_bytes = csv_content.encode('utf-8-sig')
            filename = f"clients_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
            report_file = BufferedInputFile(file=report_bytes, filename=filename)

            await bot.send_document(
                chat_id=admin_id,
                document=report_file,
                caption=get_message('admin_panel.report_caption'),
                reply_markup=get_goto_admin_panel()
            )
            logger.info(f"Report sent to admin {admin_id}.")
        except TelegramAPIError as e:
            logger.error(f"Telegram API error sending report to admin {admin_id}: {e}", exc_info=True)
            await bot.send_message(
                chat_id=admin_id,
                text=f"❌ Помилка Telegram під час надсилання файлу звіту: {e.message}",
                reply_markup=get_goto_admin_panel()
            )
        except Exception as e:
            logger.error(f"Failed to send report to admin {admin_id}: {e}", exc_info=True)
            await bot.send_message(
                chat_id=admin_id,
                text=get_message('admin_panel.internal_error'),
                reply_markup=get_goto_admin_panel()
            )
    else:
        logger.warning(f"Failed to generate clients report for admin {admin_id}.")
        await bot.send_message(
            chat_id=admin_id,
            text=get_message('admin_panel.report_generation_failed'),
             reply_markup=get_goto_admin_panel()
        )