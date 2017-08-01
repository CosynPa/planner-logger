from typing import List, Optional, Tuple
from enum import Flag, auto
import datetime


class TimeType(Flag):
    NONE = 0
    TIME = auto()
    MONTH_DAY = auto()
    YEAR = auto()


def parse_duration(time_string: str) -> Optional[float]:
    """
    Parse duration such as "2h30min". If parse failed, returns None. "0" is parsed as 0.
    """
    days = time_string.split("d")
    day_number: Optional[float]
    if len(days) == 2:
        try:
            day_number = float(days[0])
        except ValueError:
            day_number = None
    else:
        day_number = None

    hours = days[-1].split("h")
    hour_number: Optional[float]
    if len(hours) == 2:
        try:
            hour_number = float(hours[0])
        except ValueError:
            hour_number = None
    else:
        hour_number = None

    minutes = hours[-1].split("min")
    minute_number: Optional[float]
    if len(minutes) == 2:
        try:
            minute_number = float(minutes[0])
        except ValueError:
            minute_number = None
    else:
        minute_number = None

    if day_number is None and hour_number is None and minute_number is None:
        if time_string == "0":
            return 0.
        else:
            return None
    else:
        return (day_number or 0.) * 86400. + (hour_number or 0.) * 3600. + (minute_number or 0.) * 60.


def duration_str(seconds: float) -> str:
    def positive_time(positive_seconds: float) -> str:
        days, left = divmod(positive_seconds, 86400)
        hours, left = divmod(left, 3600)
        minutes, left = divmod(left, 60)

        if days != 0:
            return "{day:d}d{hour:d}h{minute:d}min".format(day=int(days), hour=int(hours), minute=int(minutes))
        elif hours != 0:
            return "{hour:d}h{minute:d}min".format(hour=int(hours), minute=int(minutes))
        else:
            return "{minute:d}min".format(minute=int(minutes))

    if seconds >= 0:
        return positive_time(seconds)
    else:
        return "-" + positive_time(-seconds)


def parse_time(time_string: str) -> Tuple[TimeType, datetime.datetime]:
    formats = [
        ("%H:%M", TimeType.TIME),

        ("%m-%d", TimeType.MONTH_DAY),
        ("%Y-%m-%d", TimeType.YEAR | TimeType.MONTH_DAY),

        ("%m-%d %H:%M", TimeType.MONTH_DAY | TimeType.TIME),
        ("%Y-%m-%d %H:%M", TimeType.YEAR | TimeType.MONTH_DAY | TimeType.TIME)
    ]

    for a_format, a_type in formats:
        try:
            the_time = datetime.datetime.strptime(time_string, a_format)
            the_type = a_type
        except ValueError:
            pass
        else:
            break
    else:
        the_time = datetime.datetime.fromtimestamp(0)
        the_type = TimeType.NONE

    if the_type is TimeType.TIME:
        the_time = datetime.datetime.combine(datetime.datetime.now().date(), the_time.time())
    elif TimeType.YEAR not in the_type:
        the_time = the_time.replace(year=datetime.datetime.now().year)

    return the_type, the_time
