import logging
from src.database.manager import db_manager

logger = logging.getLogger(__name__)

async def save_user_name(user_id: int, user_name: str) -> bool:
    sql_upsert_name = """
    INSERT INTO users (user_id, name)
    VALUES ($1, $2)
    ON CONFLICT (user_id) DO UPDATE SET
        name = EXCLUDED.name;
    """
    try:
        result = await db_manager.execute(sql_upsert_name, user_id, user_name)
        if result is not None:
            logger.info(f"User name {user_id} saved in DB.")
            return True
        else:
             logger.error(f"Can't save name for user {user_id} (execute returned None)")
             return False
    except Exception as e:
        logger.error(f"Error saving name for user {user_id}: {e}", exc_info=True)
        return False

async def save_user_phone(user_id: int, phone_number: str) -> bool:
    sql_update_phone = """
    UPDATE users SET phone_number = $1
    WHERE user_id = $2;
    """
    try:
        result = await db_manager.execute(sql_update_phone, phone_number, user_id)
        if result and 'UPDATE 1' in result:
            logger.info(f"Phone number {phone_number} updated for user {user_id}.")
            return True
        elif result and 'UPDATE 0' in result:
             logger.warning(f"Update phone number command executed for user {user_id}, but no rows affected or an issue.")
             return False
        elif result is None:
             logger.error(f"Can't update phone number for user {user_id}: DB execute returned None.")
             return False
        else:
             logger.warning(f"Command to update phone for user {user_id} returned unexpected result: {result}")
             return False

    except Exception as e:
        logger.error(f"Error updating phone number for user {user_id}: {e}", exc_info=True)
        return False