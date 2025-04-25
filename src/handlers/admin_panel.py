import logging
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from src.filters.admin_filter import AdminFilter
from src.utils.keyboards import get_admin_panel_keyboard
from src.utils.messages import get_message

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("admin"), AdminFilter())
async def handle_admin_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    logger.info(f"Admin {user_id} accessed the admin panel.")
    await message.answer(
        text=get_message('admin_panel.welcome'),
        reply_markup=get_admin_panel_keyboard()
    )
