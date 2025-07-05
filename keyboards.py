from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="\u2795 Добавить смену")],
        [KeyboardButton(text="\U0001F4C5 Доступные смены")],
        [KeyboardButton(text="\U0001F4CC Мои смены")],
        [KeyboardButton(text="\U0001F5D1 Удалить смену")],
    ],
    resize_keyboard=True,
)


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import format_shift, format_shift_short, format_shift_time


def shifts_keyboard(shifts, prefix: str) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=format_shift(s), callback_data=f"{prefix}:{s['id']}")]
        for s in shifts
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def shift_detail_keyboard(username: str, shift_id: int) -> InlineKeyboardMarkup:
    contact_link = f"https://t.me/{username}" if username else None
    buttons = []
    if contact_link:
        buttons.append([InlineKeyboardButton(text="✉️ Написать", url=contact_link)])
    buttons.append([
        InlineKeyboardButton(text="🔁 Предложить обмен", callback_data=f"offer:{shift_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def delete_shift_keyboard(shifts) -> InlineKeyboardMarkup:
    """Keyboard for deleting user's shifts."""
    buttons = [
        [InlineKeyboardButton(text=format_shift_short(s), callback_data=f"del:{s['id']}")]
        for s in shifts
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def my_shifts_keyboard(shifts) -> InlineKeyboardMarkup:
    """Keyboard for selecting user's shift for offer."""
    buttons = [
        [InlineKeyboardButton(text=format_shift_time(s), callback_data=f"myshift:{s['id']}")]
        for s in shifts
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def offer_action_keyboard(offer_id: int) -> InlineKeyboardMarkup:
    """Keyboard with approve/decline buttons for an offer."""
    buttons = [[
        InlineKeyboardButton(text="✅ Принять обмен", callback_data=f"approve:{offer_id}"),
        InlineKeyboardButton(text="❌ Отклонить обмен", callback_data=f"decline:{offer_id}")
    ]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
