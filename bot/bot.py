import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from bot.config import settings

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = settings.telegram_token

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def send_welcome(message: types.Message):
    await message.reply("Hello!")

async def main():
    if not BOT_TOKEN:
         logging.error("Bot token not found")
         return
         
    logging.info("Starting bot...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
