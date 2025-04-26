import logging
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery
from decimal import Decimal
from typing import TypedDict, Optional

from src.utils.messages import get_message
from src.utils.keyboards import get_goto_main_menu
from src.database.manager import db_manager

logger = logging.getLogger(__name__)
router = Router()

class UserProfileData(TypedDict):
    name: Optional[str]
    total_spent: Optional[Decimal]
    hookah_count: Optional[int]

async def get_user_profile_data(user_id: int) -> Optional[UserProfileData]:
    try:
        user_record = await db_manager.fetch_one(
            "SELECT name, total_spent, hookah_count FROM users WHERE user_id = $1",
            user_id
        )
        if user_record:
            return UserProfileData(
                name=user_record['name'],
                total_spent=user_record['total_spent'],
                hookah_count=user_record['hookah_count']
            )
        else:
            logger.warning(f"Could not find profile data for user_id {user_id} in database.")
            return None
    except Exception as e:
        logger.error(f"Error fetching profile data for user_id {user_id}: {e}", exc_info=True)
        return None

@router.callback_query(F.data == "action_show_profile")
async def handle_show_profile(callback: CallbackQuery, bot: Bot):
    message = callback.message
    if not message:
        await callback.answer("Не вдалося знайти оригінальне повідомлення.", show_alert=True)
        logger.warning(f"Callback 'action_show_profile' received without message. Callback ID: {callback.id}")
        return

    chat_id = message.chat.id
    message_id = message.message_id
    user_id = callback.from_user.id
    profile_data = await get_user_profile_data(user_id)

    if profile_data and profile_data.get('name') is not None:
        name = profile_data.get('name')
        hookah_count = profile_data.get('hookah_count', 0)
        total_spent = profile_data.get('total_spent', Decimal(0.00))
        discount_percent = int(total_spent // 5000)
        available_free_hookahs = hookah_count // 6
        paid_hookahs_towards_next = hookah_count % 6
        hookahs_needed_for_free = 6 - paid_hookahs_towards_next

        if discount_percent > 0:
            discount_line = get_message('profile.discount_line', discount_percent=discount_percent)
        else:
            discount_line = get_message('profile.no_discount_yet')

        if available_free_hookahs > 0:
            free_hookah_available_line = get_message('profile.free_hookah_available_line', free_hookah_count=available_free_hookahs)
        else:
            free_hookah_available_line = ""

        free_hookah_progress_line = get_message('profile.free_hookah_progress_line',hookahs_needed_for_free=hookahs_needed_for_free)

        user_mention = callback.from_user.mention_html(name)

        profile_text = get_message(
            'profile.display',
            name=user_mention,
            total_spent=f"{total_spent:.2f}",
            discount_line=discount_line,
            hookah_count=hookah_count,
            free_hookah_available_line=free_hookah_available_line,
            free_hookah_progress_line=free_hookah_progress_line,
        )
    else:
        profile_text = "Дані профілю не знайдено."

    try:
        await bot.edit_message_text(
            text=profile_text,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode='HTML',
            reply_markup=get_goto_main_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Unexpected error handling callback 'action_show_profile': {e}", exc_info=True)
        await callback.answer("Сталася помилка відображення профілю.", show_alert=True)