from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder, InlineKeyboardButton
from src.utils.messages import get_message
from src.config import settings
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
    if settings.menu_url:
        builder.row(
            InlineKeyboardButton(
                text=get_message('main_menu.our_menu_button'),
                url=settings.menu_url
            )
        )
    builder.row(
        InlineKeyboardButton(
            text=get_message('main_menu.book_table_button'),
            callback_data="action_show_booking_info"
        )
    )
    return builder.as_markup()

def get_goto_profile() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_message('main_menu.profile_button'),
            callback_data="action_show_profile"
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

def get_admin_panel_keyboard(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.enter_token_button'),
            callback_data="admin:enter_token"
        )
    )
    if user_id in settings.super_admin_ids:
        builder.row(
            InlineKeyboardButton(
                text=get_message('admin_panel.list_clients_button'),
                callback_data="admin:list_clients"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=get_message('admin_panel.broadcast_button'),
                callback_data="admin:start_broadcast"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=get_message('admin_panel.waiters_report_button'),
                callback_data="admin:waiters_report"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=get_message('admin_panel.serviced_clients_report_button'),
                callback_data="admin:serviced_clients_report"
            )
        )
        builder.adjust(1,2,2)
    return builder.as_markup()

def get_broadcast_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.confirm_yes'),
            callback_data="admin:confirm_broadcast_yes"
        ),
        InlineKeyboardButton(
            text=get_message('admin_panel.confirm_no'),
            callback_data="admin:confirm_broadcast_no"
        )
    )
    return builder.as_markup()

def get_goto_admin_panel() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.goto_panel'),
            callback_data="admin:back_to_panel"
        )
    )
    return builder.as_markup()

def get_waiters_report_period_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.report_today_button'),
            callback_data="admin:waiters_report_today"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.report_week_button'),
            callback_data="admin:waiters_report_week"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.report_month_button'),
            callback_data="admin:waiters_report_month"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.report_all_time_button'),
            callback_data="admin:waiters_report_all_time_final"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.goto_panel'),
            callback_data="admin:back_to_panel"
        )
    )
    builder.adjust(2,2,1)
    return builder.as_markup()

def get_serviced_clients_report_period_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.report_today_button'),
            callback_data="admin:serviced_clients_report_today"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.report_week_button'),
            callback_data="admin:serviced_clients_report_week"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.report_month_button'),
            callback_data="admin:serviced_clients_report_month"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.report_all_time_button'),
            callback_data="admin:serviced_clients_report_all_time_final"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_message('admin_panel.goto_panel'),
            callback_data="admin:back_to_panel"
        )
    )
    builder.adjust(2, 2, 1)
    return builder.as_markup()

