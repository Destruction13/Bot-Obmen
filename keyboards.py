from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="\u2795 Добавить смену")],
        [KeyboardButton(text="\U0001F4C4 Доступные смены")],
        [KeyboardButton(text="\U0001F4CC Мои смены")],
        [KeyboardButton(text="\U0001F5D1 Удалить смену")],
    ],
    resize_keyboard=True,
)
