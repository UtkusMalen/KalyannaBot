import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import settings
from src.handlers import registration, main_menu, qr_handler
from src.database.manager import db_manager

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = settings.telegram_token

cleanup_task = None

async def cleanup_expired_codes():
    try:
        now_utc = datetime.now(timezone.utc)
        sql_delete = "DELETE FROM temporary_codes WHERE expires_at < $1;"
        result = await db_manager.execute(sql_delete, now_utc)

        if result and 'DELETE' in result:
            try:
                deleted_count = int(result.split()[-1])
                if deleted_count > 0:
                    logging.info(f"Successfully cleaned up {deleted_count} expired temporary codes.")
                else:
                    logging.info("No expired temporary codes found during cleanup.")
            except (ImportError, ValueError):
                logging.warning(f"Cleanup executed, but couldn't parse deleted count from result: {result}")
        elif result is None:
            logging.error("Cleanup task failed: DB execute returned None.")
        else:
            logging.info(f"Cleanup task ran, no expired codes found or result format unexpected: {result}")
    except Exception as e:
        logging.error(f"Error during expired codes cleanup: {e}", exc_info=True)

async def schedule_cleanup():
    interval = 600
    logging.info(f"Starting periodic cleanup task with interval: {interval} seconds.")
    while True:
        try:
            await cleanup_expired_codes()
        except Exception as e:
            logging.error(f"Unhandled error in schedule_cleanup loop: {e}", exc_info=True)

        await asyncio.sleep(interval)

async def on_startup():
    global cleanup_task
    await db_manager.connect()
    logging.info("Database connection established.")
    cleanup_task = asyncio.create_task(schedule_cleanup())
    logging.info("Background cleanup task scheduled.")

async def on_shutdown():
    global cleanup_task
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            logging.info("Background cleanup task successfully cancelled.")
        except Exception as e:
            logging.error(f"Error during cleanup task cancellation: {e}", exc_info=True)

    await db_manager.close()
    logging.info("Database connection closed.")

async def main():
    if not BOT_TOKEN:
         logging.error("Bot token not found")
         return

    storage = MemoryStorage()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.include_router(registration.router)
    dp.include_router(main_menu.router)
    dp.include_router(qr_handler.router)

    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
