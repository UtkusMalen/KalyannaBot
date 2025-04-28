import logging
from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from decimal import Decimal
from typing import TypedDict, Optional

from src.utils.messages import get_message
from src.utils.keyboards import get_goto_main_menu
from src.utils.progress_bar import generate_progress_bar
from src.database.manager import db_manager
from src.logic.profile_logic import calculate_profile_metrics
from src.config import settings

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
        name = profile_data.get('name', 'Гість')
        total_spent = profile_data.get('total_spent', Decimal('0.00'))
        hookah_count = profile_data.get('hookah_count', 0)
        available_free_hookahs = profile_data.get('free_hookahs_available', 0)

        metrics = calculate_profile_metrics(total_spent, hookah_count)
        discount_percent = metrics['discount_percent']
        next_discount_percent = metrics['next_discount_percent']
        progress_percent_to_next_discount = metrics['progress_percent_to_next_discount']
        amount_needed = metrics['amount_needed_for_next_discount']
        hookahs_needed_for_free = metrics['hookahs_needed_for_free']
        hookah_progress_percent = metrics['hookah_progress_percent']

        user_mention = user.mention_html(name)

        discount_progress_section = ""
        if next_discount_percent is not None and amount_needed is not None:
            discount_progress_bar = generate_progress_bar(progress_percent_to_next_discount)
            amount_needed_str = f"{amount_needed:.2f} грн"
            discount_progress_section = get_message(
                'profile.discount_progress_section_template',
                next_discount_percent=next_discount_percent,
                discount_progress_bar=discount_progress_bar,
                discount_progress_percent=progress_percent_to_next_discount,
                amount_needed=amount_needed_str
            )
        elif discount_percent > 0:
            discount_progress_section = get_message('profile.discount_max_level_reached')

        hookah_progress_section = ""
        if settings.free_hookah_every > 0 and hookahs_needed_for_free != 999:
            hookah_progress_bar = generate_progress_bar(hookah_progress_percent)
            hookah_progress_section = get_message(
                 'profile.hookah_progress_section_template',
                 hookahs_needed_for_free=hookahs_needed_for_free,
                 hookah_progress_bar=hookah_progress_bar,
                 hookah_progress_percent=hookah_progress_percent
            )

        free_hookah_available_line = ""
        if available_free_hookahs > 0:
            free_hookah_available_line = get_message(
                'profile.free_hookah_available_line_template',
                free_hookah_count=available_free_hookahs
            )

        bonus_section = get_message('profile.bonus_section_template')
        benefits_section = get_message('profile.benefits_section_template')

        profile_text = get_message(
            'profile.display',
            name=user_mention,
            discount_percent=discount_percent,
            discount_progress_section=discount_progress_section,
            hookah_progress_section=hookah_progress_section,
            free_hookah_available_line=free_hookah_available_line,
            bonus_section=bonus_section,
            benefits_section=benefits_section
        )

    else:
        profile_text = get_message('profile.not_found')

    try:
        reply_markup = get_goto_main_menu()
        if is_edit and isinstance(target, CallbackQuery):
            await bot.edit_message_text(
                text=profile_text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode='HTML',
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            await target.answer()
        elif not is_edit and isinstance(target, Message):
             await target.answer(
                 text=profile_text,
                 parse_mode='HTML',
                 reply_markup=reply_markup,
                 disable_web_page_preview=True
             )
    except Exception as e:
        logger.error(f"Error displaying profile for user {user_id}: {e}", exc_info=True)
        error_message = "Помилка відображення профілю."
        if isinstance(target, CallbackQuery):
             try:
                 await target.answer(error_message, show_alert=True)
             except Exception: pass
        elif isinstance(target, Message):
             try:
                 await target.answer(error_message)
             except Exception: pass

@router.callback_query(F.data == "action_show_profile")
async def handle_show_profile_callback(callback: CallbackQuery, bot: Bot):
    logger.debug(f"User {callback.from_user.id} requested profile via button.")
    await display_profile(callback, bot)


@router.message(Command("profile"))
async def handle_profile_command(message: Message, bot: Bot):
     logger.info(f"User {message.from_user.id} requested profile via /profile command.")
     await display_profile(message, bot)