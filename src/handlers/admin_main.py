import logging

from aiogram import Router, Bot, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from src.filters.admin_filter import AdminFilter
from src.utils.keyboards import get_admin_panel_keyboard
from src.utils.messages import get_message

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

@router.message(Command("admin"))
async def handle_admin_command(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    logger.info(f"Admin {user_id} accessed the admin panel.")
    await message.answer(
        text=get_message('admin_panel.welcome'),
        reply_markup=get_admin_panel_keyboard(user_id),
        parse_mode='HTML'
    )

@router.callback_query(F.data == "admin:back_to_panel")
async def handle_back_to_admin_panel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    message = callback.message
    if not message:
        await callback.answer("Помилка: не вдалося знайти повідомлення.", show_alert=True)
        return

    user_id = callback.from_user.id
    logger.info(f"Admin {user_id} pressed 'Back to Admin Panel'. Clearing state.")
    await state.clear()

    try:
        current_text = message.text or ""
        target_text = get_message('admin_panel.welcome')
        if current_text != target_text or message.reply_markup != get_admin_panel_keyboard(user_id):
            await bot.edit_message_text(
                text=target_text,
                chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=get_admin_panel_keyboard(user_id),
                parse_mode='HTML'
            )
        await callback.answer()
    except TelegramBadRequest as e:
        if "message is not modified" in e.message:
            logger.warning(f"Message {message.message_id} not modified for back_to_admin_panel.")
            await callback.answer()
        elif "there is no text in the message to edit" in e.message or "message to edit not found" in e.message:
            logger.warning(f"Could not edit message {message.message_id} (no text/not found). Sending new one. Error: {e}")
            try:
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=get_message('admin_panel.welcome'),
                    reply_markup=get_admin_panel_keyboard(user_id),
                    parse_mode='HTML'
                )
                await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
                await callback.answer()
            except Exception as send_err:
                logger.error(f"Error sending new message for back_to_admin_panel (admin {user_id}): {send_err}", exc_info=True)
                await callback.answer("Сталася помилка при поверненні до панелі.", show_alert=True)
        else:
             logger.error(f"Error editing message for back_to_admin_panel (admin {user_id}): {e}", exc_info=True)
             await callback.answer("Сталася помилка.", show_alert=True)
             await message.answer(
                 text=get_message('admin_panel.welcome'),
                 reply_markup=get_admin_panel_keyboard(user_id),
                 parse_mode='HTML'
             )
    except Exception as e:
        logger.error(f"Unexpected error in handle_back_to_admin_panel (admin {user_id}): {e}", exc_info=True)
        await callback.answer("Сталася непередбачена помилка.", show_alert=True)
        await message.answer(
            text=get_message('admin_panel.welcome'),
            reply_markup=get_admin_panel_keyboard(user_id),
            parse_mode='HTML'
        )