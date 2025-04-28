import logging
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from src.utils.messages import get_message
from src.utils.keyboards import get_goto_main_menu
from src.config import settings

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == 'action_show_booking_info')
async def handle_show_booking_info(callback: CallbackQuery, bot: Bot):
    message = callback.message
    if not message:
        await callback.answer("Помилка: не вдалося знайти оригінальне повідомлення.", show_alert=True)
        logger.warning(f"Callback 'action_show_booking_info' received without message. Callback ID: {callback.id}")
        return

    chat_id = message.chat.id
    message_id = message.message_id

    phone = settings.booking_phone_number
    insta_url = settings.instagram_url
    tiktok_url = settings.tiktok_url

    follow_us_line = ""
    social_links = []
    if tiktok_url:
        social_links.append(get_message('booking.tiktok_link_template', tiktok_url=tiktok_url))
    if insta_url:
        social_links.append(get_message('booking.instagram_link_template', instagram_url=insta_url))

    if social_links:
        social_links_html = "\n".join(social_links)
        follow_us_line = get_message(
            'booking.follow_us_template',
            social_links_html=social_links_html
        )

    if phone:
        booking_text = get_message(
            'booking.contact_info',
            phone_number=phone,
            phone_number_display=phone,
            follow_us_line=follow_us_line,
        )
    else:
        booking_text = get_message('booking.error_missing_info')
        logger.warning(f"Booking info requested by {callback.from_user.id} but phone or Instagram URL is missing in settings.")

    try:
        if message.text != booking_text:
            await bot.edit_message_text(
                text=booking_text,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode='HTML',
                reply_markup=get_goto_main_menu(),
                disable_web_page_preview=True
            )
        await callback.answer()
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            logger.info(f"Booking info message was not modified.")
            await callback.answer()
        else:
            logger.error(f"Error editing message for booking info: {e}", exc_info=True)
            await callback.answer("Сталася помилка відображення інформації.", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error handling booking info: {e}", exc_info=True)
        await callback.answer("Сталася помилка.", show_alert=True)
