import logging
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from decimal import Decimal
from typing import TypedDict, Optional

from src.utils.messages import get_message
from src.utils.keyboards import get_goto_main_menu
from src.database.manager import db_manager
from src.logic.profile_logic import calculate_profile_metrics

logger = logging.getLogger(__name__)
router = Router()

class UserProfileData(TypedDict):
    name: Optional[str]
    total_spent: Optional[Decimal]
    hookah_count: Optional[int]
    free_hookahs_available: Optional[int]

async def get_user_profile_data(user_id: int) -> Optional[UserProfileData]:
    try:
        user_record = await db_manager.fetch_one(
            "SELECT name, total_spent, hookah_count, free_hookahs_available FROM users WHERE user_id = $1",
            user_id
        )
        if user_record:
            return UserProfileData(
                name=user_record['name'],
                total_spent=user_record['total_spent'] if user_record['total_spent'] is not None else Decimal('0.00'),
                hookah_count=user_record['hookah_count'] if user_record['hookah_count'] is not None else 0,
                free_hookahs_available=user_record['free_hookahs_available'] if user_record['free_hookahs_available'] is not None else 0
            )
        else:
            logger.warning(f"Could not find profile data for user_id {user_id} in database.")
            return None
    except Exception as e:
        logger.error(f"Error fetching profile data for user_id {user_id}: {e}", exc_info=True)
        return None

async def display_profile(target: Message | CallbackQuery, bot: Bot):
    if isinstance(target, Message):
        user = target.from_user
        chat_id = target.chat.id
        is_edit = False
    elif isinstance(target, CallbackQuery):
        if not target.message:
             await target.answer("Помилка: не вдалося знайти оригінальне повідомлення.", show_alert=True)
             logger.warning(f"Callback query {target.id} received without message.")
             return
        user = target.from_user
        chat_id = target.message.chat.id
        message_id = target.message.message_id
        is_edit = True
    else:
        logger.error(f"Unsupported target type in display_profile: {type(target)}")
        return

    user_id = user.id
    profile_data = await get_user_profile_data(user_id)

    if profile_data:
        name = profile_data.get('name', 'Guest')
        hookah_count = profile_data.get('hookah_count', 0)
        total_spent = profile_data.get('total_spent', Decimal('0.00'))
        available_free_hookahs = profile_data.get('free_hookahs_available', 0)

        metrics = calculate_profile_metrics(total_spent, hookah_count)
        discount_percent = metrics['discount_percent']
        hookahs_needed_for_free = metrics['hookahs_needed_for_free']

        if discount_percent > 0:
            discount_line = get_message('profile.discount_line', discount_percent=discount_percent)
        else:
            discount_line = get_message('profile.no_discount_yet')

        if available_free_hookahs > 0:
            free_hookah_available_line = get_message('profile.free_hookah_available_line', free_hookah_count=available_free_hookahs)
        else:
            free_hookah_available_line = get_message('profile.no_free_hookah_available', default="")

        if hookahs_needed_for_free < 999:
             free_hookah_progress_line = get_message('profile.free_hookah_progress_line', hookahs_needed_for_free=hookahs_needed_for_free)
        else:
             free_hookah_progress_line = ""

        user_mention = user.mention_html(name)

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
        profile_text = get_message('profile.not_found')

    try:
        if is_edit and isinstance(target, CallbackQuery):
            await bot.edit_message_text(
                text=profile_text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode='HTML',
                reply_markup=get_goto_main_menu()
            )
            await target.answer()
        elif not is_edit and isinstance(target, Message):
             await target.answer(
                 text=profile_text,
                 parse_mode='HTML',
                 reply_markup=get_goto_main_menu()
             )
    except Exception as e:
        logger.error(f"Error displaying profile for user {user_id}: {e}", exc_info=True)
        if isinstance(target, CallbackQuery):
             await target.answer("Помилка відображення профілю.", show_alert=True)
        elif isinstance(target, Message):
             await target.answer("Помилка відображення профілю.")


@router.callback_query(F.data == "action_show_profile")
async def handle_show_profile_callback(callback: CallbackQuery, bot: Bot):
    logger.debug(f"User {callback.from_user.id} requested profile via button.")
    await display_profile(callback, bot)


@router.message(Command("profile"))
async def handle_profile_command(message: Message, bot: Bot):
     logger.info(f"User {message.from_user.id} requested profile via /profile command.")
     await display_profile(message, bot)