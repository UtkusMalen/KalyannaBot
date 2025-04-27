from aiogram import F, Router, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove
from src.utils.messages import get_message
from src.database.manager import db_manager
from src.logic.registration_logic import save_user_name, save_user_phone
from src.utils.keyboards import get_phone_keyboard, get_goto_main_menu
from src.handlers.main_menu import show_main_menu
import logging

logger = logging.getLogger(__name__)

router = Router()

class RegistationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()

@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    existing_user = await db_manager.fetch_one("SELECT user_id FROM users WHERE user_id = $1", message.from_user.id)
    if existing_user:
        logger.info(f"User {message.from_user.id} already registered.")
        await state.clear()
        await show_main_menu(message)
        return

    logger.info(f"New user {message.from_user.id} started registration.")
    bot_message = await message.answer(get_message('registration.start_prompt'))
    await state.update_data(greeting_message_id=bot_message.message_id)
    await state.set_state(RegistationStates.waiting_for_name)

@router.message(RegistationStates.waiting_for_name, F.text)
async def handle_name(message: Message, state: FSMContext, bot: Bot):
    user_name = message.text.strip()
    if not user_name:
         await message.answer("Name cannot be empty.")
         return

    chat_id = message.chat.id
    user_id = message.from_user.id
    user_message_id = message.message_id

    if not await save_user_name(user_id, user_name):
        await message.answer(get_message('registration.name_save_error'))
        return

    await state.update_data(name=user_name)
    context_data = await state.get_data()
    bot_message_id = context_data.get('greeting_message_id')

    try:
        await bot.delete_message(chat_id=chat_id, message_id=user_message_id)
    except Exception as e:
        logger.warning(f"Error deleting user message: {e}")

    user_mention = message.from_user.mention_html(user_name)
    greeting_text = get_message('registration.greeting', user_name=user_mention)

    edited = False
    if bot_message_id:
        try:
            greeting_msg = await bot.edit_message_text(
                text=greeting_text,
                chat_id=chat_id,
                message_id=bot_message_id,
                parse_mode='HTML'
            )
            edited = True
        except Exception as e:
            logger.error(f"Error editing greeting message: {e}")

    if not edited:
        greeting_msg = await message.answer(greeting_text, parse_mode='HTML')

    phone_prompt = await message.answer(
        text=get_message('registration.phone_prompt'),
        reply_markup=get_phone_keyboard()
    )
    await state.update_data(greeting_msg=greeting_msg.message_id)
    await state.update_data(phone_prompt=phone_prompt.message_id)
    await state.set_state(RegistationStates.waiting_for_phone)

@router.message(RegistationStates.waiting_for_phone, F.contact)
async def handle_phone(message: Message, state: FSMContext, bot: Bot):
    if not message.contact or message.contact.user_id != message.from_user.id:
        await message.answer(
            get_message('registration.phone_not_yours'),
            reply_markup=get_phone_keyboard(),
            parse_mode = 'HTML'
        )
        return

    user_phone = message.contact.phone_number
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not await save_user_phone(user_id, user_phone):
         await message.answer(get_message('registration.phone_save_error'))
         return

    context_data = await state.get_data()
    greeting_msg_id = context_data.get('greeting_msg')
    phone_prompt_id = context_data.get('phone_prompt')

    try:
        await bot.delete_message(chat_id=chat_id, message_id=greeting_msg_id)
    except Exception as e:
        logger.warning(f"Can't delete greeting message: {e}")

    try:
        await bot.delete_message(chat_id=chat_id, message_id=phone_prompt_id)
    except Exception as e:
        logger.warning(f"Can't delete phone prompt message: {e}")

    remover_msg = await message.answer(
        get_message('registration.removing_keyboard', default='.'),
        reply_markup=ReplyKeyboardRemove()
    )
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=remover_msg.message_id)
    except Exception as e:
        logger.warning(f"Can't delete removing keyboard message: {e}")

    try:
        await message.answer(
            get_message('registration.phone_success'),
            reply_markup=get_goto_main_menu(),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Can't send registration success message: {e}", exc_info=True)

    logger.info(f"Registration for user {user_id} completed.")
    await state.clear()

@router.message(RegistationStates.waiting_for_phone, F.text)
async def handle_phone_text_instead_of_contact(message: Message):
     await message.reply(
          get_message('registration.phone_text_error'),
          reply_markup=get_phone_keyboard()
     )