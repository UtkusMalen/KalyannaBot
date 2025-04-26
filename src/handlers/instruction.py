import logging
from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from src.utils.messages import get_message
from src.config import settings

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("instruction"))
async def handle_instruction(message: Message):
    user_id = message.from_user.id
    logger.info(f"User {user_id} requested instruction.")

    instruction_text = get_message(
        'instruction.text',
        discount_threshold=settings.discount_threshold_per_percent,
        qr_ttl_minutes=settings.qr_code_ttl_seconds // 60
    )

    await message.answer(instruction_text, parse_mode='HTML')