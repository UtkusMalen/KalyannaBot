import logging
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery

from src.utils.messages import get_message
from src.utils.keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()

async def show_main_menu(message: Message):
    await message.answer(
        text=get_message('main_menu.menu'),
        parse_mode='HTML',
        reply_markup=get_main_menu_keyboard()
    )

@router.callback_query(F.data == "action_show_main_menu")
async def handle_goto_main_menu(callback: CallbackQuery, bot: Bot):
    message = callback.message
    if not message:
        await callback.answer("Не вдалося знайти оригінальне повідомлення.", show_alert=True)
        logger.warning(f"Callback 'action_show_main_menu' received without message. Callback ID: {callback.id}")
        return

    chat_id = message.chat.id
    message_id = message.message_id

    try:
        await bot.edit_message_text(
            text=get_message('main_menu.menu'),
            chat_id=chat_id,
            message_id=message_id,
            parse_mode='HTML',
            reply_markup=get_main_menu_keyboard()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Unexpected error handling callback 'action_show_main_menu': {e}", exc_info=True)
        await callback.answer("Сталася помилка.", show_alert=True)