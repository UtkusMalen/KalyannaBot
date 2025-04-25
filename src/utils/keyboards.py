from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder, InlineKeyboardButton
from src.utils.messages import get_message
import logging

logger = logging.getLogger(__name__)

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
    builder.row(
        InlineKeyboardButton(
            text=get_message('main_menu.profile_button'),
            callback_data="action_show_profile"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_message('main_menu.qr_button'),
            callback_data="action_generate_user_qr"
        )
    )
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

def get_profile_keyboard() -> InlineKeyboardMarkup: # Added
    return get_goto_main_menu()

def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_message(''),
            callback_data="admin:"
        )
    )
    return builder.as_markup()