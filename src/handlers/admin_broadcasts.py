import asyncio
import logging

from aiogram import Router, Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.filters.super_admin_filter import SuperAdminFilter
from src.logic.admin_logic import get_all_user_ids
from src.utils.keyboards import get_admin_panel_keyboard, get_goto_admin_panel, get_broadcast_confirmation_keyboard
from src.utils.messages import get_message
from src.utils.tg_utils import safe_delete_message

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(SuperAdminFilter())
router.callback_query.filter(SuperAdminFilter())

class AdminBroadcastStates(StatesGroup):
    waiting_for_broadcast_message = State()
    waiting_for_broadcast_confirmation = State()


@router.callback_query(F.data == "admin:start_broadcast")
async def handle_start_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    message = callback.message
    if not message:
        await callback.answer("Помилка: не вдалося знайти повідомлення.", show_alert=True)
        return

    admin_id = callback.from_user.id
    logger.info(f"Admin {admin_id} initiated broadcast.")

    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=get_message('admin_panel.prompt_broadcast_message'),
            reply_markup=get_goto_admin_panel(),
            parse_mode='HTML'
        )
        await state.set_state(AdminBroadcastStates.waiting_for_broadcast_message)
        await state.update_data(prompt_message_id=message.message_id)
        await callback.answer()
    except Exception as e:
        logger.error(f"Error editing message for broadcast prompt (admin {admin_id}): {e}", exc_info=True)
        await callback.answer("Сталася помилка.", show_alert=True)
        await message.answer(
            text=get_message('admin_panel.welcome'),
            reply_markup=get_admin_panel_keyboard(),
            parse_mode='HTML'
        )
        await state.clear()


@router.message(AdminBroadcastStates.waiting_for_broadcast_message, F.text | F.photo)
async def handle_broadcast_content(message: Message, state: FSMContext, bot: Bot):
    admin_id = message.from_user.id
    chat_id = message.chat.id
    state_data = await state.get_data()
    prompt_message_id = state_data.get('prompt_message_id')

    photo_file_id = None

    if message.text:
        content_type = "text"
        text_content = message.html_text
        logger.info(f"Admin {admin_id} provided text for broadcast: '{message.text[:50]}...'")
    elif message.photo:
        content_type = "photo"
        photo_file_id = message.photo[-1].file_id
        text_content = message.caption
        logger.info(f"Admin {admin_id} provided photo (ID: {photo_file_id}) for broadcast.")
    else:
        await message.answer(get_message('admin_panel.unsupported_broadcast_content'), reply_markup=get_goto_admin_panel())
        await safe_delete_message(bot, chat_id, message.message_id)
        await safe_delete_message(bot, chat_id, prompt_message_id)
        await state.clear()
        return

    await safe_delete_message(bot, chat_id, prompt_message_id)

    await state.update_data(
        broadcast_content_type=content_type,
        broadcast_text=text_content,
        broadcast_photo_id=photo_file_id,
        original_content_message_id=message.message_id
    )

    user_ids = await get_all_user_ids()
    user_count = len(user_ids) if user_ids is not None else 0

    if user_ids is None:
        await message.answer(get_message('admin_panel.broadcast_user_fetch_error'), reply_markup=get_goto_admin_panel())
        await safe_delete_message(bot, chat_id, message.message_id)
        await state.clear()
        return

    confirm_prompt_text = get_message('admin_panel.confirm_broadcast_prompt', user_count=user_count)

    preview_message = None
    confirm_message = None
    try:
        preview_message = await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=chat_id,
            message_id=message.message_id,
            reply_markup=None
        )
        await safe_delete_message(bot, chat_id, message.message_id)

        confirm_message = await bot.send_message(
            chat_id=chat_id,
            text=confirm_prompt_text,
            reply_markup=get_broadcast_confirmation_keyboard(),
            parse_mode='HTML'
        )
        await state.update_data(
            preview_message_id=preview_message.message_id,
            confirm_message_id=confirm_message.message_id
        )
        await state.set_state(AdminBroadcastStates.waiting_for_broadcast_confirmation)
        logger.info(f"Sent broadcast preview and confirmation prompt to admin {admin_id}.")

    except Exception as e:
        logger.error(f"Failed to send broadcast preview/confirmation to admin {admin_id}: {e}", exc_info=True)
        await message.answer(get_message('admin_panel.internal_error'), reply_markup=get_goto_admin_panel())
        await safe_delete_message(bot, chat_id, message.message_id)
        await safe_delete_message(bot, chat_id, preview_message.message_id if preview_message else None)
        await safe_delete_message(bot, chat_id, confirm_message.message_id if confirm_message else None)
        await state.clear()


@router.callback_query(F.data == "admin:confirm_broadcast_no", AdminBroadcastStates.waiting_for_broadcast_confirmation)
async def handle_broadcast_cancel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    admin_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else admin_id
    state_data = await state.get_data()
    preview_message_id = state_data.get('preview_message_id')
    confirm_message_id = state_data.get('confirm_message_id')

    logger.info(f"Admin {admin_id} cancelled the broadcast.")

    await safe_delete_message(bot, chat_id, preview_message_id)
    await safe_delete_message(bot, chat_id, confirm_message_id)

    await bot.send_message(
        chat_id=chat_id,
        text=get_message('admin_panel.broadcast_cancelled'),
        reply_markup=get_goto_admin_panel()
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "admin:confirm_broadcast_yes", AdminBroadcastStates.waiting_for_broadcast_confirmation)
async def handle_broadcast_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    admin_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else admin_id
    state_data = await state.get_data()
    preview_message_id = state_data.get('preview_message_id')
    confirm_message_id = state_data.get('confirm_message_id')

    await safe_delete_message(bot, chat_id, preview_message_id)
    await safe_delete_message(bot, chat_id, confirm_message_id)

    await bot.send_message(chat_id=chat_id, text=get_message('admin_panel.broadcast_started'), reply_markup=get_goto_admin_panel())
    await callback.answer()

    user_ids = await get_all_user_ids()
    if user_ids is None:
        logger.error(f"Failed to get user IDs again before starting broadcast for admin {admin_id}")
        await bot.send_message(chat_id, get_message('admin_panel.broadcast_user_fetch_error'), reply_markup=get_goto_admin_panel())
        await state.clear()
        return
    if not user_ids:
         logger.warning(f"No users found to broadcast to for admin {admin_id}")
         await bot.send_message(chat_id, get_message('admin_panel.broadcast_no_users'), reply_markup=get_goto_admin_panel())
         await state.clear()
         return


    content_type = state_data.get('broadcast_content_type')
    text = state_data.get('broadcast_text')
    photo_id = state_data.get('broadcast_photo_id')

    success_count = 0
    fail_count = 0
    total_users = len(user_ids)

    logger.info(f"Starting broadcast by admin {admin_id} to {total_users} users. Content type: {content_type}")

    for i, user_id in enumerate(user_ids):
        try:
            if content_type == 'text':
                await bot.send_message(user_id, text, parse_mode='HTML', disable_web_page_preview=True)
            elif content_type == 'photo':
                await bot.send_photo(user_id, photo_id, caption=text, parse_mode='HTML')

            success_count += 1
            logger.debug(f"Broadcast message sent successfully to user {user_id}")
        except TelegramAPIError as e:
            fail_count += 1
            if "bot was blocked by the user" in e.message or \
               "user is deactivated" in e.message or \
               "chat not found" in e.message or \
               "user not found" in e.message:
                logger.warning(f"Broadcast failed for user {user_id} (Blocked/Deactivated/Not Found): {e.message}")
            else:
                logger.error(f"TelegramAPIError sending broadcast to {user_id}: {e}", exc_info=True)
        except Exception as e:
            fail_count += 1
            logger.error(f"Unexpected error sending broadcast to user {user_id}: {e}", exc_info=True)

        if i % 20 == 0:
             await asyncio.sleep(1)
        else:
             await asyncio.sleep(0.05)


    result_message = get_message(
        'admin_panel.broadcast_success',
        success_count=success_count,
        fail_count=fail_count,
        total_users=total_users
    )
    await bot.send_message(chat_id=chat_id, text=result_message, reply_markup=get_goto_admin_panel())
    logger.info(f"Broadcast finished. {success_count}/{total_users} sent, {fail_count} failed.")

    await state.clear()