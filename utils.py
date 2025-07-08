import re
from datetime import datetime
from typing import Optional, Tuple

MONTHS = {
    'января': 1,
    'февраля': 2,
    'марта': 3,
    'апреля': 4,
    'мая': 5,
    'июня': 6,
    'июля': 7,
    'августа': 8,
    'сентября': 9,
    'октября': 10,
    'ноября': 11,
    'декабря': 12,
}

MONTHS_LIST = [
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
]

SHIFT_RE = re.compile(
    r"(?P<day>\d{1,2})\s+(?P<month>[а-яА-Я]+)(?:\s+(?P<year>\d{4}))?,\s*(?P<start>\d{1,2}:\d{2})\s*[\-\u2013\u2014]\s*(?P<end>\d{1,2}:\d{2})"
)


def parse_shift(text: str) -> Optional[Tuple[datetime, datetime]]:
    match = SHIFT_RE.search(text.strip())
    if not match:
        return None
    day = int(match.group('day'))
    month_name = match.group('month').lower()
    month = MONTHS.get(month_name)
    if not month:
        return None
    year_str = match.group('year')
    year = int(year_str) if year_str else datetime.now().year
    try:
        start_time = datetime.strptime(match.group('start'), '%H:%M').time()
        end_time = datetime.strptime(match.group('end'), '%H:%M').time()
    except ValueError:
        return None
    start = datetime(year, month, day, start_time.hour, start_time.minute)
    end = datetime(year, month, day, end_time.hour, end_time.minute)
    if end <= start:
        return None
    return start, end


STATUS_TEXT = {
    'active': '🟢 Активна',
    'offered': '🔁 Предложена',
    'confirmed': '✅ Подтверждена',
}


def format_shift(row: dict) -> str:
    start = datetime.fromisoformat(row['start_time'])
    end = datetime.fromisoformat(row['end_time'])
    status = STATUS_TEXT.get(row['status'], row['status'])
    pref = row.get('desired')
    pref_text = ''
    if pref == 'earlier':
        pref_text = ' (хочет раньше)'
    elif pref == 'later':
        pref_text = ' (хочет позже)'
    return (
        f"{row['id']}: {start.day} {MONTHS_LIST[start.month - 1]}, "
        f"{start.strftime('%H:%M')} — {end.strftime('%H:%M')} {status}{pref_text}"
    )


def format_shift_short(row: dict) -> str:
    start = datetime.fromisoformat(row['start_time'])
    end = datetime.fromisoformat(row['end_time'])
    pref = row.get('desired')
    pref_text = ''
    if pref == 'earlier':
        pref_text = ' (хочет раньше)'
    elif pref == 'later':
        pref_text = ' (хочет позже)'
    return (
        f"{start.day} {MONTHS_LIST[start.month - 1]}, "
        f"{start.strftime('%H:%M')} — {end.strftime('%H:%M')}{pref_text}"
    )


def format_shift_time(row: dict) -> str:
    """Return only time range from shift row."""
    start = datetime.fromisoformat(row['start_time'])
    end = datetime.fromisoformat(row['end_time'])
    return f"{start.strftime('%H:%M')} — {end.strftime('%H:%M')}"


TIME_RE = re.compile(r"(?P<start>\d{1,2}:\d{2})\s*[\-\u2013\u2014]\s*(?P<end>\d{1,2}:\d{2})")


def parse_time_range(text: str, date: datetime) -> Optional[Tuple[datetime, datetime]]:
    """Parse time range like '10:00-19:00' for a given date."""
    match = TIME_RE.search(text.strip())
    if not match:
        return None
    try:
        s_time = datetime.strptime(match.group('start'), '%H:%M').time()
        e_time = datetime.strptime(match.group('end'), '%H:%M').time()
    except ValueError:
        return None
    start = datetime.combine(date.date(), s_time)
    end = datetime.combine(date.date(), e_time)
    if end <= start:
        return None
    return start, end


def escape_md(text: str) -> str:
    """Escape text for MarkdownV2."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(rf"([{re.escape(escape_chars)}])", r"\\\1", text)
