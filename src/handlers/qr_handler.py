import logging
from aiogram import Router, F, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, Message

from src.utils.messages import get_message
from src.utils.qr_generator import generate_qr_code_inputfile
from src.database.manager import db_manager
from src.logic.qr_logic import generate_and_store_temporary_code
from src.config import settings

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "action_generate_user_qr")
async def handle_generate_user_qr(callback: CallbackQuery, bot: Bot):
    message = callback.message
    if not message:
        await callback.answer("Не вдалося знайти оригінальне повідомлення.", show_alert=True)
        logger.warning(f"Callback 'action_generate_user_qr' received without message. Callback ID: {callback.id}")
        return

    chat_id = message.chat.id
    user_id = callback.from_user.id

    try:
        sql_ensure_user = """
        INSERT INTO users (user_id) VALUES ($1)
        ON CONFLICT (user_id) DO NOTHING;
        """
        ensure_result = await db_manager.execute(sql_ensure_user, user_id)
        if ensure_result and 'INSERT 0 1' in ensure_result:
            logger.warning(f"User {user_id} already exists in the database.")
        elif ensure_result is None:
            await callback.answer("Помилка бази даних. Спробуйте пізніше.", show_alert=True)
            return
    except Exception as e:
        logger.error(f"Error ensuring user {user_id} in the database: {e}", exc_info=True)
        await callback.answer("Помилка перевірки користувача. Спробуйте пізніше.", show_alert=True)
        return

    secret_code = await generate_and_store_temporary_code(user_id)

    if not secret_code:
        await callback.answer("Can't generate QR code. Try again later.", show_alert=True)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except TelegramAPIError:
            pass
        return

    qr_data = secret_code
    qr_input_file = await generate_qr_code_inputfile(qr_data)

    if not qr_input_file:
        await callback.answer("Can't generate QR code. Try again later.", show_alert=True)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except TelegramAPIError:
            pass
        return

    try:
        ttl_minutes = settings.qr_code_ttl_seconds // 60
        sent_message = await bot.send_photo(
            chat_id=chat_id,
            photo=qr_input_file,
            caption=get_message('qr_handler.qr_caption', ttl_minutes=ttl_minutes),
            parse_mode='HTML'
        )
        await callback.answer()
        await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
    except Exception as e:
        logger.error(f"Error sending QR Code for user {user_id} in chat {chat_id}: {e}", exc_info=True)
        try:
             await callback.answer("Не вдалося надіслати QR-код.", show_alert=True)
        except:
             pass

    if sent_message:
        try:
            sql_update_message_id = """
            UPDATE temporary_codes SET message_id = $1
            WHERE secret_code = $2 AND user_id = $3;
            """
            update_result = await db_manager.execute(
                sql_update_message_id,
                sent_message.message_id,
                secret_code,
                user_id
            )
            if update_result:
                logger.info(f"Successfully stored message_id {sent_message.message_id} for code {secret_code} user {user_id}.")
            else:
                logger.warning(f"Could not store message_id for code {secret_code} user {user_id}. Update result: {update_result}")
        except Exception as e:
            logger.error(f"Failed to store message_id {sent_message.message_id} for code {secret_code} user {user_id}: {e}",exc_info=True)