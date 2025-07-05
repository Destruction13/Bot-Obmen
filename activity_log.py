from datetime import datetime
from utils import MONTHS_LIST

LOG_FILE = 'logs'


def _format_range(start: datetime, end: datetime) -> str:
    return f"{start.day} {MONTHS_LIST[start.month - 1]}, {start.strftime('%H:%M')} - {end.strftime('%H:%M')}"


def log_new_shift(user: str, start: datetime, end: datetime) -> None:
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{datetime.now().strftime('%d.%m.%Y %H:%M')} {user} создал(а) новую смену {_format_range(start, end)}\n")


def log_exchange(user1: str, user2: str, start1: datetime, end1: datetime, start2: datetime, end2: datetime) -> None:
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(
            f"{datetime.now().strftime('%d.%m.%Y %H:%M')} {user1} обменялся сменами с {user2}, {_format_range(start1, end1)} на {_format_range(start2, end2)}\n"
        )
