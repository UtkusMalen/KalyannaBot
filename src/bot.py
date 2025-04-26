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

async def cleanup_expired_codes():
    try:
        now_utc = datetime.now(timezone.utc)
        sql_delete = "DELETE FROM temporary_codes WHERE expires_at < $1;"
        result = await db_manager.execute(sql_delete, now_utc)

        if result and 'DELETE' in result:
            try:
                deleted_count_str = result.split()[-1]
                deleted_count = int(deleted_count_str)
                if deleted_count > 0:
                    logging.info(f"Successfully deleted {deleted_count} expired codes from the database.")
            except (IndexError, ValueError):
                logging.warning(f"Cleanup command executed, but no rows deleted: {result}")
        elif result is None:
             logging.error("Error while deleting expired codes: DB execute returned None.")
             pass
    except Exception as e:
        logging.error(f"Error while deleting expired codes: {e}", exc_info=True)

async def schedule_cleanup():
    interval = settings.cleanup_interval_seconds
    logging.info(f"Launching cleanup task with interval {interval} seconds:")
    while True:
        try:
            await cleanup_expired_codes()
        except Exception as e:
            logging.error(f"Unexpected error in cleanup task: {e}", exc_info=True)

        await asyncio.sleep(interval)

async def on_startup(bot: Bot):
    global cleanup_task
    await db_manager.connect() # Встановлюємо з'єднання з БД
    logging.info("Connection to the database established.")
    await set_bot_commands(bot)
    cleanup_task = asyncio.create_task(schedule_cleanup())
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