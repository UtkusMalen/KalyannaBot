import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)

ERROR_MSG_DELETE_DELAY = 7

async def safe_delete_message(bot: Bot, chat_id: int, message_id: int | None):
    if message_id is None:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramAPIError as e:
        if "message to delete not found" in e.message or \
           "message can't be deleted" in e.message:
             logger.warning(f"Could not delete message {message_id} in chat {chat_id}: {e.message}")
        else:
             logger.error(f"Error deleting message {message_id} in chat {chat_id}: {e}", exc_info=True)
    except Exception as e:
         logger.error(f"Unexpected error deleting message {message_id} in chat {chat_id}: {e}", exc_info=True)


async def send_temporary_error(bot: Bot, chat_id: int, user_message_id: int | None, error_text: str, delay: int = ERROR_MSG_DELETE_DELAY):
    await safe_delete_message(bot, chat_id, user_message_id)

    error_msg = None
    try:
        error_msg = await bot.send_message(chat_id=chat_id, text=error_text)
        await asyncio.sleep(delay)
    except Exception as e:
        logger.error(f"Failed to send or sleep during temporary error handling in chat {chat_id}: {e}", exc_info=True)
    finally:
        if error_msg:
            await safe_delete_message(bot, chat_id, error_msg.message_id)