import logging
import secrets
from datetime import datetime, timedelta, timezone

from src.database.manager import db_manager
from src.config import settings

logger = logging.getLogger(__name__)

async def generate_and_store_temporary_code(user_id: int) -> str | None:
    try:
        secret_code = secrets.token_hex(3).upper()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=settings.qr_code_ttl_seconds)
        logger.info(f"Generated temporary code {secret_code} for user {user_id} with expiration at {expires_at}")
    except Exception as e:
        logger.error(f"Error generating and storing temporary code for user {user_id}: {e}", exc_info=True)
        return None

    sql_insert_code = """
    INSERT INTO temporary_codes (user_id, secret_code, expires_at)
    VALUES ($1, $2, $3);
    """
    try:
        insert_result = await db_manager.execute(sql_insert_code, user_id, secret_code, expires_at)

        if insert_result and 'INSERT 0 1' in insert_result:
            logger.info(f"Successfully stored temporary code {secret_code} for user {user_id}.")
            return secret_code
        else:
             logger.error(f"Could not store temporary code {secret_code} for user {user_id}.")
             return None
    except Exception as e:
        logger.error(f"Error storing temporary code {secret_code} for user {user_id}: {e}", exc_info=True)
        return None