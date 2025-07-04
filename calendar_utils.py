from aiogram_calendar import simple_calendar
from aiogram.types import CallbackQuery

SimpleCal = simple_calendar.SimpleCalendar()

async def start_calendar():
    return await SimpleCal.start_calendar()

async def process_calendar(query: CallbackQuery, callback_data: simple_calendar.SimpleCalendarCallback):
    """Process calendar selection and return (is_selected, date)."""
    return await SimpleCal.process_selection(query, callback_data)
