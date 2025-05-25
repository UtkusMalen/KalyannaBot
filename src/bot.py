import asyncio
import logging
from datetime import datetime, timezone, time, timedelta

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from src.config import settings
from src.database.backup import create_db_backup
from src.handlers import registration, main_menu, qr_handler, admin_main, admin_reports, admin_broadcasts, \
    admin_token_flow, profile, instruction, booking, waiters_report
from src.database.manager import db_manager
from src.utils.messages import get_message
from src.utils.tg_utils import safe_delete_message

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

BOT_TOKEN = settings.telegram_token

cleanup_task = None
backup_task = None

async def schedule_daily_backup():
    BACKUP_TIME_UTC = time(3, 0, 0)

    logger.info(f"Starting background daily backup task. Scheduled time (UTC): {BACKUP_TIME_UTC.strftime('%H:%M:%S')}.")

    while True:
        now_utc = datetime.now(timezone.utc)
        today_backup_time = datetime.combine(now_utc.date(), BACKUP_TIME_UTC, tzinfo=timezone.utc)

        if now_utc > today_backup_time:
            next_run_time = today_backup_time + timedelta(days=1)
        else:
            next_run_time = today_backup_time

        wait_seconds = (next_run_time - now_utc).total_seconds()

        logger.info(f"Next backup scheduled at: {next_run_time.strftime('%Y-%m-%d %H:%M:%S %Z')}. Waiting for {wait_seconds:.0f} seconds.")

        await asyncio.sleep(wait_seconds)

        logger.info("Starting scheduled daily database backup...")
        try:
            success = await create_db_backup()
            if success:
                logger.info("Scheduled daily backup completed successfully.")
            else:
                logger.error("Scheduled daily backup failed.")
        except Exception as e:
            logger.error(f"Backup Task: Unexpected error in schedule_daily_backup loop during backup execution: {e}", exc_info=True)
            await asyncio.sleep(60)
        await asyncio.sleep(1)

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
    deleted_messages = 0
    failed_message_deletions = 0

    sql_delete_expired_returning = """
    DELETE FROM temporary_codes
    WHERE expires_at < $1
    RETURNING user_id, message_id;
    """

    try:
        deleted_records = await db_manager.fetch_all(sql_delete_expired_returning, now_utc)

        if not deleted_records:
            logger.info("Cleanup: No expired codes found to delete.")
            return

        deleted_count = len(deleted_records)
        logger.info(f"Cleanup: Deleted {deleted_count} expired code records from the database.")

        for record in deleted_records:
            user_id = record.get('user_id')
            message_id = record.get('message_id')

            if not user_id:
                logger.warning(f"Cleanup: Skipping record with missing user_id: {record}")
                continue

            if message_id:
                try:
                    await safe_delete_message(bot, chat_id=user_id, message_id=message_id)
                    deleted_messages += 1
                except Exception:
                    logger.warning(f"Cleanup: Failed attempt to delete message {message_id} for user {user_id}. Error logged by safe_delete_message.")
                    failed_message_deletions += 1

        log_summary = f"Cleanup finished: DB records deleted: {deleted_count}."
        if deleted_messages > 0 or failed_message_deletions > 0:
            log_summary += f" TG messages deleted: {deleted_messages}, Failed TG deletions: {failed_message_deletions}."
        logger.info(log_summary)

    except Exception as e:
        logger.error(f"Cleanup: Database error during expired code deletion: {e}", exc_info=True)


async def schedule_cleanup(bot: Bot):
    interval = settings.cleanup_interval_seconds
    logger.info(f"Starting background cleanup task. Interval: {interval} seconds.")
    while True:
        try:
            await cleanup_expired_codes(bot)
        except Exception as e:
            logger.error(f"Cleanup Task: Unexpected error in schedule_cleanup loop: {e}", exc_info=True)
            await asyncio.sleep(interval * 2)
            continue

        await asyncio.sleep(interval)


async def on_startup(bot: Bot):
    global cleanup_task, backup_task
    try:
        await db_manager.connect()
        logger.info("Database connection established.")
        await set_bot_commands(bot)
        if cleanup_task is None:
            cleanup_task = asyncio.create_task(schedule_cleanup(bot))
            logger.info("Background cleanup task scheduled.")
        if backup_task is None:
            backup_task = asyncio.create_task(schedule_daily_backup())
            logger.info("Background daily backup task scheduled.")

    except Exception as e:
         logger.critical(f"Startup failed: Could not connect to DB or set commands. Error: {e}", exc_info=True)


async def on_shutdown():
    global cleanup_task, backup_task
    logger.info("Shutting down...")
    if backup_task and not backup_task.done():
        backup_task.cancel()
        try:
            await backup_task
        except asyncio.CancelledError:
            logger.info("Backup task successfully cancelled.")
        except Exception as e:
            logger.error(f"Error during backup task cancellation: {e}", exc_info=True)

    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.info("Cleanup task successfully cancelled.")
        except Exception as e:
            logger.error(f"Error during cleanup task cancellation: {e}", exc_info=True)

    await db_manager.close()
    logger.info("Database connection pool closed.")

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
    dp.include_router(admin_main.router)
    dp.include_router(admin_token_flow.router)
    dp.include_router(admin_reports.router)
    dp.include_router(admin_broadcasts.router)
    dp.include_router(profile.router)
    dp.include_router(instruction.router)
    dp.include_router(booking.router)
    dp.include_router(waiters_report.router)

    logging.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Роботу бота зупинено.")