from aiogram_calendar import simple_calendar
from aiogram_calendar.schemas import CalendarLabels
from aiogram.types import CallbackQuery

# Russian labels for calendar buttons
RU_LABELS = CalendarLabels(
    days_of_week=["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    months=["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"],
    cancel_caption="Отмена",
    today_caption="Сегодня",
)


class RussianCalendar(simple_calendar.SimpleCalendar):
    """Calendar with russian captions"""

    def __init__(self):
        super().__init__()
        self._labels = RU_LABELS


SimpleCal = RussianCalendar()


async def start_calendar():
    return await SimpleCal.start_calendar()


async def process_calendar(query: CallbackQuery, callback_data: simple_calendar.SimpleCalendarCallback):
    return await SimpleCal.process_selection(query, callback_data)
