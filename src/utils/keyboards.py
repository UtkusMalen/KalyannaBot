from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder, InlineKeyboardButton
from src.utils.messages import get_message

def get_phone_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(
            text=get_message('registration.share_phone_button'),
            request_contact=True
        )
    )
    return builder.as_markup(
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder=get_message('registration.phone_input_placeholder')
    )

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(get_generate_qr_button())
    return builder.as_markup()

def get_goto_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_message('main_menu.back_to_menu'),
            callback_data="action_show_main_menu"
        )
    )
    return builder.as_markup()

def get_generate_qr_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=get_message('main_menu.get_qr_button'),
        callback_data="action_generate_user_qr"
    )