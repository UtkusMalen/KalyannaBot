import logging
import secrets
from datetime import datetime, timedelta, timezone
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery

from src.utils.messages import get_message
from src.utils.qr_generator import generate_qr_code_inputfile
from src.database.manager import db_manager

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
        if ensure_result and ensure_result == 'INSERT 0 1':
            logger.warning(
                f"User {user_id} was not found in 'users' table before generating QR code. Inserted ID. Check registration flow.")
        elif ensure_result is None:
            logger.error(f"Failed to execute 'ensure user' query for user {user_id}. Connection issue?")
    except Exception as e:
        logger.error(f"Error ensuring if user {user_id} exists in DB: {e}", exc_info=True)

    try:
        secret_code = secrets.token_hex(3).upper()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=600)
        logger.info(f"Generated secret code {secret_code} for user {user_id}, expires at {expires_at}")
    except Exception as e:
        logger.error(f"Error generating secret code or expiration time: {e}", exc_info=True)
        await callback.answer("Помилка генерації коду. Спробуйте пізніше.", show_alert=True)
        return

    sql_insert_code = """
    INSERT INTO temporary_codes (user_id, secret_code, expires_at)
    VALUES ($1, $2, $3);
    """
    try:
        insert_result = await db_manager.execute(sql_insert_code, user_id, secret_code, expires_at)
        if insert_result is None:
            raise Exception("DB execute returned None")
        elif 'INSERT 0 0' in insert_result:
            raise Exception("DB execute reported 0 rows inserted")

        logger.info(f"Successfully stored temporary code {secret_code} for user {user_id} in DB.")
    except Exception as e:
        logger.error(f"Failed to store temporary code for user {user_id} in DB: {e}", exc_info=True)
        await callback.answer("Помилка збереження коду. Спробуйте пізніше.", show_alert=True)
        return

    qr_data = secret_code
    qr_input_file = await generate_qr_code_inputfile(qr_data)

    if not qr_input_file:
        await callback.answer("Не вдалося згенерувати QR-код. Спробуйте пізніше.", show_alert=True)
        return

    try:
        await bot.send_photo(
            chat_id=chat_id,
            photo=qr_input_file,
            caption=get_message('qr_handler.qr_caption', ttl_minutes=10),
            parse_mode='HTML'
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Failed to send QR for user {user_id} to chat {chat_id}: {e}",exc_info=True)
        await callback.answer("Не вдалося надіслати QR-код.", show_alert=True)

