from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from src.utils.messages import get_message
from src.database.manager import db_manager
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
        await message.answer("Main menu placeholder")
        await state.clear()
        return

    bot_message = await message.answer(get_message('registration.start_prompt'))
    await state.update_data(greeting_message_id=bot_message.message_id)
    await state.set_state(RegistationStates.waiting_for_name)

@router.message(RegistationStates.waiting_for_name, F.text)
async def handle_name(message: Message, state: FSMContext, bot: Bot):
    user_name = message.text.strip()
    chat_id = message.chat.id
    user_id = message.from_user.id
    user_message_id = message.message_id

    user_mention = message.from_user.mention_markdown(user_name)

    sql_upsert_name = """
    INSERT INTO users (user_id, name)
    VALUES ($1, $2)
    ON CONFLICT (user_id) DO UPDATE SET
        name = EXCLUDED.name;
    """
    try:
        await db_manager.execute(sql_upsert_name, user_id, user_name)
    except Exception as e:
        logger.error(f"Failed to save/update name for user {user_id}: {e}")
        return

    await state.update_data(name=user_name)
    context_data = await state.get_data()
    bot_message_id = context_data.get('greeting_message_id')

    try:
        await bot.delete_message(chat_id=chat_id, message_id=user_message_id)
    except Exception as e:
        logger.error(f"Error deleting user message: {e}")

    if bot_message_id:
        try:
            await bot.edit_message_text(
                text=get_message('registration.greeting', user_name=user_mention),
                chat_id=chat_id,
                message_id=bot_message_id,
                parse_mode='MarkdownV2'
            )
        except Exception as e:
            logger.error(f"Error editing bot message: {e}")
            await message.answer(get_message('registration.greeting', user_name=user_mention))
    else:
        await message.answer(get_message('registration.greeting', user_name=user_mention))

    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text=get_message('registration.share_phone_button'),
                    request_contact=True
                )
            ]
        ],
        resize_keyboard=True,
    )

    await message.answer(
        text=get_message('registration.phone_prompt'),
        reply_markup=phone_keyboard
    )

    await state.set_state(RegistationStates.waiting_for_phone)

@router.message(RegistationStates.waiting_for_phone, F.contact)
async def handle_phone(message: Message, state: FSMContext):
    if message.contact.user_id != message.from_user.id:
        await message.answer(
            get_message('registration.phone_not_yours'),
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[
                    [
                        KeyboardButton(
                            text=get_message('registration.share_phone_button'),
                            request_contact=True
                        )
                    ]
                ],
                resize_keyboard=True,
            )
        )
        return

    user_phone = message.contact.phone_number
    user_id = message.from_user.id
    context_data = await state.get_data()
    user_name = context_data.get('name', message.from_user.full_name)
    user_mention = message.from_user.mention_markdown(user_name)
    logger.info(f"User {user_id} shared phone: {user_phone}")

    sql_update_phone = """
    UPDATE users SET phone_number = $1
    WHERE user_id = $2;
    """
    try:
        result = await db_manager.execute(sql_update_phone, user_phone, user_id)
        if result:
            logger.info(f"User {user_id} ({user_name}) phone number '{user_phone}' saved in DB.")
        else:
            logger.warning(f"Phone number update command executed for user {user_id}, but result indicates no rows affected or an issue.")
    except Exception as e:
        logger.error(f"Failed to save phone number for user {user_id}: {e}")
        return

    await message.answer(
        get_message('registration.phone_success', user_name=user_mention),
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='MarkdownV2'
    )

    await state.clear()
