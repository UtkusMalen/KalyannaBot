import asyncio
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime

from aiogram import Router, Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.logic import admin_logic
from src.filters.admin_filter import AdminFilter
from src.utils.keyboards import get_admin_panel_keyboard, get_goto_profile, get_goto_admin_panel
from src.utils.messages import get_message

logger = logging.getLogger(__name__)
router = Router()

ERROR_MSG_DELETE_DELAY = 7

class AdminStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_free_hookah_usage = State()
    waiting_for_amount = State()
    waiting_for_hookah_count = State()

@router.message(Command("admin"), AdminFilter())
async def handle_admin_command(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    logger.info(f"Admin {user_id} accessed the admin panel.")
    await message.answer(
        text=get_message('admin_panel.welcome'),
        reply_markup=get_admin_panel_keyboard(),
        parse_mode='HTML'
    )

@router.callback_query(F.data == "admin:back_to_panel", AdminFilter())
async def handle_back_to_admin_panel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    message = callback.message
    if not message:
        await callback.answer("Помилка: не вдалося знайти повідомлення.", show_alert=True)
        return

    user_id = callback.from_user.id
    logger.info(f"Admin {user_id} pressed 'Back to Admin Panel'. Clearing state.")
    await state.clear()

    try:
        await bot.edit_message_text(
            text=get_message('admin_panel.welcome'),
            chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=get_admin_panel_keyboard(),
            parse_mode='HTML'
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Error editing message for back_to_admin_panel (admin {user_id}): {e}", exc_info=True)
        await callback.answer("Сталася помилка.", show_alert=True)
        await message.answer(
            text=get_message('admin_panel.welcome'),
            reply_markup=get_admin_panel_keyboard(),
            parse_mode='HTML'
        )


@router.callback_query(F.data == "admin:enter_token", AdminFilter())
async def handle_enter_token(callback: CallbackQuery, state: FSMContext, bot: Bot):
    message = callback.message
    if not message:
        await callback.answer("Помилка: не вдалося знайти оригінальне повідомлення.", show_alert=True)
        logger.warning(f"Callback 'admin:enter_token' received without message. Callback ID: {callback.id}")
        return

    chat_id = message.chat.id
    message_id = message.message_id
    user_id = callback.from_user.id

    logger.info(f"Admin {user_id} initiated token entry.")

    try:
        await bot.edit_message_text(
            text=get_message('admin_panel.enter_token'),
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None
        )
        await state.set_state(AdminStates.waiting_for_token)
        await state.update_data(message_id=message_id)
        logger.info(f"Admin {user_id} state set to waiting_for_token.")
        await callback.answer()
    except Exception as e:
        logger.error(f"Error editing message for token prompt (admin {user_id}): {e}", exc_info=True)
        await callback.answer("Сталася помилка під час оновлення повідомлення.", show_alert=True)
        await message.answer(
            text=get_message('admin_panel.welcome'),
            reply_markup=get_admin_panel_keyboard(),
            parse_mode='HTML'
        )
        await state.clear()


@router.message(AdminStates.waiting_for_token, F.text, AdminFilter())
async def handle_token_input(message: Message, state: FSMContext, bot: Bot):
    entered_token = message.text.strip().upper()
    admin_id = message.from_user.id
    chat_id = message.chat.id
    context_data = await state.get_data()
    original_prompt_message_id = context_data.get('message_id')

    logger.info(f"Admin {admin_id} entered token: {entered_token}")

    token_info = await admin_logic.validate_token(entered_token)

    if token_info:
        client_user_id = token_info['user_id']
        logger.info(f"Token {entered_token} is valid for user {client_user_id}.")

        user_initial_data = await admin_logic.get_user_initial_data(client_user_id)

        if user_initial_data:
            available_free_hookahs = user_initial_data.get('free_hookahs_available', 0)
            user_name = user_initial_data.get('name', 'Клієнт')
        else:
            logger.error(f"Token {entered_token} valid for user {client_user_id}, but user data not found in 'users' table.")
            await message.answer(get_message('admin_panel.internal_error'), reply_markup=get_goto_admin_panel())
            await state.clear()
            return

        await state.update_data(client_user_id=client_user_id, used_token=entered_token, client_name=user_name)

        try:
            if original_prompt_message_id:
                await bot.delete_message(chat_id=chat_id, message_id=original_prompt_message_id)
            await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except Exception as e:
            logger.warning(f"Could not delete previous messages in token handling: {e}")

        if available_free_hookahs > 0:
            logger.info(f"User {client_user_id} has {available_free_hookahs} free hookahs available. Asking admin.")
            alert_text = get_message('admin_panel.free_hookah_alert', count=available_free_hookahs)
            prompt_text = get_message(
                'admin_panel.enter_free_hookah_usage',
                user_name=user_name,
                alert_text=alert_text,
                max_available=available_free_hookahs
            )
            next_prompt_msg = await message.answer(prompt_text, parse_mode='HTML')
            await state.update_data(
                available_free_hookahs=available_free_hookahs,
                message_id=next_prompt_msg.message_id
            )
            await state.set_state(AdminStates.waiting_for_free_hookah_usage)
        else:
            logger.info(f"User {client_user_id} has no free hookahs available. Proceeding to amount entry.")
            amount_prompt_msg = await message.answer(
                get_message('admin_panel.enter_amount', user_name=user_name),
                parse_mode='HTML'
            )
            await state.update_data(
                available_free_hookahs=0,
                used_free_hookahs=0,
                message_id=amount_prompt_msg.message_id
            )
            await state.set_state(AdminStates.waiting_for_amount)

    else:
        logger.warning(f"Admin {admin_id} entered invalid/expired token or DB error occurred: {entered_token}")
        error_msg = await message.answer(get_message('admin_panel.invalid_token'))
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except Exception as e:
            logger.warning(f"Could not delete admin's invalid token message: {e}")

        await asyncio.sleep(ERROR_MSG_DELETE_DELAY)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=error_msg.message_id)
        except Exception as e:
            logger.warning(f"Could not delete invalid token error message: {e}")

@router.message(AdminStates.waiting_for_free_hookah_usage, F.text, AdminFilter())
async def handle_free_hookah_usage(message: Message, state: FSMContext, bot: Bot):
    entered_free_hookahs_str = message.text.strip()
    admin_id = message.from_user.id
    chat_id = message.chat.id
    context_data = await state.get_data()
    client_user_id = context_data.get('client_user_id')
    available_free_hookahs = context_data.get('available_free_hookahs', 0)
    prompt_message_id = context_data.get('message_id')
    user_name = context_data.get('client_name', 'Клієнт')

    logger.info(f"Admin {admin_id} entered free hookah usage count '{entered_free_hookahs_str}' for client {client_user_id} (Available: {available_free_hookahs})")

    try:
        used_free_hookahs = int(entered_free_hookahs_str)
        if not (0 <= used_free_hookahs <= available_free_hookahs):
            raise ValueError("Value out of allowed range [0, available]")

        logger.info(f"Admin {admin_id} confirmed using {used_free_hookahs} free hookahs for client {client_user_id}. Storing in state.")

        try:
            if prompt_message_id:
                await bot.delete_message(chat_id=chat_id, message_id=prompt_message_id)
            await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except Exception as e:
            logger.warning(f"Could not delete messages in free hookah handling: {e}")

        await state.update_data(used_free_hookahs=used_free_hookahs)

        amount_prompt_msg = await message.answer(
            get_message('admin_panel.enter_amount', user_name=user_name),
            parse_mode='HTML'
        )
        await state.update_data(message_id=amount_prompt_msg.message_id)
        await state.set_state(AdminStates.waiting_for_amount)
        logger.info(f"Admin {admin_id} state set to waiting_for_amount for client {client_user_id}.")

    except (ValueError, TypeError):
        logger.warning(f"Admin {admin_id} entered invalid free hookah usage count '{entered_free_hookahs_str}' for client {client_user_id}")
        error_msg = await message.answer(
            get_message('admin_panel.invalid_hookah_count_range', max_available=available_free_hookahs)
        )
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except Exception as e:
            logger.warning(f"Could not delete admin's invalid free hookah count message: {e}")

        await asyncio.sleep(ERROR_MSG_DELETE_DELAY)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=error_msg.message_id)
        except Exception as e:
            logger.warning(f"Could not delete invalid free hookah count error message: {e}")


@router.message(AdminStates.waiting_for_amount, F.text, AdminFilter())
async def handle_amount_input(message: Message, state: FSMContext, bot: Bot):
    entered_amount_str = message.text.strip().replace(',', '.')
    admin_id = message.from_user.id
    chat_id = message.chat.id
    context_data = await state.get_data()
    client_user_id = context_data.get('client_user_id')
    prompt_message_id = context_data.get('message_id')
    user_name = context_data.get('client_name', 'Клієнт')

    if not client_user_id:
        logger.error(f"Admin {admin_id} in waiting_for_amount, but client_user_id missing in state.")
        await message.answer(get_message('admin_panel.internal_error'), reply_markup=get_goto_admin_panel())
        await state.clear()
        return

    logger.info(f"Admin {admin_id} entered amount for client {client_user_id}: {entered_amount_str}")

    try:
        amount = Decimal(entered_amount_str)
        if amount < 0:
            raise ValueError("Amount cannot be negative")

        await state.update_data(entered_amount=str(amount))
        logger.info(f"Stored amount {amount} in state for admin {admin_id}, client {client_user_id}.")

        try:
            if prompt_message_id:
                await bot.delete_message(chat_id=chat_id, message_id=prompt_message_id)
            await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except Exception as e:
            logger.warning(f"Could not delete messages in amount handling: {e}")

        hookah_message = await message.answer(
            get_message('admin_panel.enter_hookah_count', user_name=user_name), parse_mode='HTML'
        )
        await state.set_state(AdminStates.waiting_for_hookah_count)
        await state.update_data(message_id=hookah_message.message_id)
        logger.info(f"Admin {admin_id} state set to waiting_for_hookah_count for client {client_user_id}.")

    except (InvalidOperation, ValueError):
        logger.warning(f"Admin {admin_id} entered invalid amount for client {client_user_id}: {entered_amount_str}")
        error_msg = await message.answer(get_message('admin_panel.invalid_amount'))
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except Exception as e:
            logger.warning(f"Could not delete admin's invalid amount message: {e}")

        await asyncio.sleep(ERROR_MSG_DELETE_DELAY)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=error_msg.message_id)
        except Exception as e:
            logger.warning(f"Could not delete invalid amount error message: {e}")

@router.message(AdminStates.waiting_for_hookah_count, F.text, AdminFilter())
async def handle_hookah_count_input(message: Message, state: FSMContext, bot: Bot):
    entered_hookah_count_str = message.text.strip()
    admin_id = message.from_user.id
    chat_id = message.chat.id

    context_data = await state.get_data()
    client_user_id = context_data.get('client_user_id')
    used_token = context_data.get('used_token')
    entered_amount_str = context_data.get('entered_amount')
    prompt_message_id = context_data.get('message_id')
    used_free_hookahs = context_data.get('used_free_hookahs', 0)

    # Перевірки наявності даних зі стану
    if not all([client_user_id, used_token, entered_amount_str is not None]):
         logger.error(f"Admin {admin_id} in waiting_for_hookah_count, but critical data missing in state: {context_data}")
         await message.answer(get_message('admin_panel.internal_error'), reply_markup=get_goto_admin_panel())
         await state.clear()
         return

    logger.info(f"Admin {admin_id} entered paid hookah count '{entered_hookah_count_str}' for client {client_user_id}.")

    try:
        hookah_count_added = int(entered_hookah_count_str)
        if hookah_count_added < 0:
            raise ValueError("Hookah count cannot be negative")

        try:
            entered_amount = Decimal(entered_amount_str)
        except InvalidOperation:
            logger.error(f"Could not convert stored amount '{entered_amount_str}' back to Decimal. State data: {context_data}")
            raise ValueError("Invalid amount stored in state")

        try:
            if prompt_message_id:
                await bot.delete_message(chat_id=chat_id, message_id=prompt_message_id)
            await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except Exception as e:
            logger.warning(f"Could not delete messages in hookah count handling: {e}")

        logger.info(f"Calling finalize_user_update for {client_user_id} with: amount={entered_amount}, added_paid={hookah_count_added}, used_free={used_free_hookahs}")
        final_user_data = await admin_logic.finalize_user_update(
            client_user_id=client_user_id,
            used_token=used_token,
            entered_amount=entered_amount,
            hookah_count_added=hookah_count_added,
            used_free_hookahs=used_free_hookahs
        )

        if final_user_data:
            logger.info(f"Final update successful for user {client_user_id}. Final data: {final_user_data}")

            user_name = final_user_data['name']
            total_spent = final_user_data['total_spent']
            final_paid_count = final_user_data['hookah_count']
            final_free_available = final_user_data['free_hookahs_available']

            admin_free_used_line = ""
            user_free_used_line = ""
            if used_free_hookahs > 0:
                admin_free_used_line = get_message('admin_panel.success_free_used_line', count=used_free_hookahs)
                user_free_used_line = get_message('user_notify.free_used_line', count=used_free_hookahs)

            success_message = get_message(
                'admin_panel.update_success',
                user_name=user_name,
                amount=f"{entered_amount:.2f}",
                free_used_line=admin_free_used_line,
                hookah_count_added=hookah_count_added,
                total_spent=f"{total_spent:.2f}",
                final_paid_count=final_paid_count,
                final_free_available=final_free_available
            )
            await message.answer(success_message, parse_mode='HTML', reply_markup=get_goto_admin_panel())

            try:
                user_notification_message = get_message(
                    'admin_panel.user_update_notification',
                    user_name=user_name,
                    free_hookahs_used_line=user_free_used_line,
                    amount_added=f"{entered_amount:.2f}",
                    hookah_count_added=hookah_count_added,
                    total_spent=f"{total_spent:.2f}",
                    final_paid_count=final_paid_count,
                    final_free_available=final_free_available
                )
                await bot.send_message(
                    chat_id=client_user_id,
                    text=user_notification_message,
                    parse_mode='HTML',
                    reply_markup=get_goto_profile()
                )
                logger.info(f"Successfully sent update notification to user {client_user_id}")
            except TelegramAPIError as e:
                logger.error(f"Failed to send notification to user {client_user_id}: {e}", exc_info=True)
                await message.answer(f"⚠️ Не вдалося надіслати сповіщення користувачу {user_name} ({client_user_id}). Помилка: {e.message}", reply_markup=get_goto_admin_panel())

            await state.clear()

        else:
            logger.error(f"Failed to finalize update for client {client_user_id}. finalize_user_update returned None.")
            await message.answer(get_message('admin_panel.internal_error'), reply_markup=get_goto_admin_panel())
            await state.clear()

    except ValueError as e:
        logger.warning(f"Admin {admin_id} entered invalid hookah count for client {client_user_id}: {entered_hookah_count_str} or invalid amount stored. Error: {e}")
        error_message_key = 'admin_panel.invalid_hookah_count' if "hookah count" in str(e).lower() else 'admin_panel.internal_error'
        error_msg = await message.answer(get_message(error_message_key))
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message.message_id)
        except Exception as log_e:
            logger.warning(f"Could not delete admin's invalid hookah count message: {log_e}")

        await asyncio.sleep(ERROR_MSG_DELETE_DELAY)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=error_msg.message_id)
        except Exception as log_e:
            logger.warning(f"Could not delete admin's invalid hookah count error message: {log_e}")

    except Exception as e:
        logger.error(f"Unexpected error processing hookah count input or during finalization for client {client_user_id}: {e}", exc_info=True)
        await message.answer(get_message('admin_panel.internal_error'), reply_markup=get_goto_admin_panel())
        await state.clear()

@router.callback_query(F.data == "admin:list_clients", AdminFilter())
async def handle_list_clients(callback: CallbackQuery, bot: Bot):
    admin_id = callback.from_user.id
    logger.info(f"Admin {admin_id} requested clients list.")

    try:
        await callback.answer(get_message('admin_panel.generating_report'))
    except TelegramAPIError as e:
        logger.error(f"Failed to send answer to admin {admin_id}: {e}", exc_info=True)

    csv_content = await admin_logic.generate_clients_report_csv()

    if csv_content:
        try:
            report_bytes = csv_content.encode('utf-8-sig')
            filename = f"clients_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
            report_file = BufferedInputFile(file=report_bytes, filename=filename)

            await bot.send_document(
                chat_id=admin_id,
                document=report_file,
                caption=get_message('admin_panel.report_caption'),
            )
            logger.info(f"Report sent to admin {admin_id}.")
        except TelegramAPIError as e:
            try:
                await callback.message.answer(f"❌ Помилка Telegram під час надсилання файлу: {e.message}")
            except:
                pass
        except Exception as e:
            logger.error(f"Failed to send report to admin {admin_id}: {e}", exc_info=True)
            try:
                await callback.message.answer(get_message('admin_panel.internal_error'))
            except:
                pass
    else:
        logger.warning(f"Failed to generate clients report for admin {admin_id}.")
        try:
            await callback.message.answer(get_message('admin_panel.internal_error'))
        except Exception as e:
            logger.warning(f"Failed to send error message to admin {admin_id}: {e}", exc_info=True)
