import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import settings
from src.handlers import registration
from src.database.manager import db_manager

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = settings.telegram_token


async def main():
    if not BOT_TOKEN:
         logging.error("Bot token not found")
         return

    storage = MemoryStorage()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    await db_manager.connect()
    dp.include_router(registration.router)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
