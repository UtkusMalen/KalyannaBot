import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from src.config import settings
from src.handlers import registration, main_menu, qr_handler, admin_panel, profile, instruction
from src.database.manager import db_manager
from src.utils.messages import get_message

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

BOT_TOKEN = settings.telegram_token

cleanup_task = None

async def set_bot_commands(bot: Bot):
    user_commands = [
        BotCommand(command="start", description=get_message('commands.start')),
        BotCommand(command="profile", description=get_message('commands.profile')),
        BotCommand(command="instruction", description=get_message('commands.instruction')),
    ]
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    logger.info("Set user commands.")

    admin_commands = user_commands + [
        BotCommand(command="admin", description=get_message('commands.admin')),
    ]
    if settings.admin_ids:
        for admin_id in settings.admin_ids:
            try:
                await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
                logger.info(f"Set admin commands for {admin_id}.")
            except Exception as e:
                logger.error(f"Could not set admin commands for {admin_id}: {e}")
    else:
         logger.warning("No admin IDs configured. Admin commands will not be set.")

async def cleanup_expired_codes(bot: Bot):
    now_utc = datetime.now(timezone.utc)
    sql_select_expired = """
    SELECT id, user_id, message_id FROM temporary_codes
    WHERE expires_at < $1;
    """
    try:
        records = await db_manager.fetch_all(sql_select_expired, now_utc)
        if records:
            expired_records = [dict(record) for record in records]
            logger.info(f"Found {len(expired_records)} expired codes to clean up.")
        else:
            logger.info("No expired codes found to clean up.")
            return
    except Exception as e:
        logger.error(f"Database error selecting expired codes: {e}", exc_info=True)
        return

    deleted_count = 0
    for record in expired_records:
        code_db_id = record.get('id')
        user_id = record.get('user_id')
        message_id = record.get('message_id')

        if not code_db_id or not user_id:
            logger.warning(f"Skipping invalid record during cleanup: {record}")
            continue

        if message_id:
            try:
                await bot.delete_message(chat_id=user_id, message_id=message_id)
                logger.info(f"Successfully deleted expired QR message {message_id} for user {user_id}.")
            except Exception as e:
                logger.error(f"Error while deleting expired code message: {e}", exc_info=True)

        sql_delete_by_id = "DELETE FROM temporary_codes WHERE id = $1;"
        try:
            delete_result = await db_manager.execute(sql_delete_by_id, code_db_id)
            if delete_result and 'DELETE' in delete_result:
                deleted_count += 1
            else:
                logger.warning(f"Failed to delete expired code with ID {code_db_id}.")
        except Exception as e:
            logger.error(f"Error while deleting expired code: {e}", exc_info=True)

    if deleted_count > 0:
        logger.info(f"Successfully deleted {deleted_count} expired code records from the database.")


async def schedule_cleanup(bot: Bot):
    interval = settings.cleanup_interval_seconds
    logging.info(f"Launching cleanup task with interval {interval} seconds:")
    while True:
        try:
            await cleanup_expired_codes(bot)
        except Exception as e:
            logging.error(f"Unexpected error in cleanup task: {e}", exc_info=True)

        await asyncio.sleep(interval)

async def on_startup(bot: Bot):
    global cleanup_task
    await db_manager.connect()
    logging.info("Connection to the database established.")
    await set_bot_commands(bot)
    cleanup_task = asyncio.create_task(schedule_cleanup(bot))
    logging.info("Background cleanup task started.")

async def on_shutdown():
    global cleanup_task
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            logging.info("Cleanup task was canceled.")
        except Exception as e:
            logging.error(f"Error while canceling cleanup task: {e}", exc_info=True)

    # Закриваємо з'єднання з БД
    await db_manager.close()
    logging.info("Connection to the database closed.")

async def main():
    if not BOT_TOKEN:
         logging.critical("Bot token is not set.")
         return

    storage = MemoryStorage()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.include_router(registration.router)
    dp.include_router(main_menu.router)
    dp.include_router(qr_handler.router)
    dp.include_router(admin_panel.router)
    dp.include_router(profile.router)
    dp.include_router(instruction.router)

    logging.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Роботу бота зупинено.")