from typing import List, Optional, Tuple, Union
from enum import Flag, auto
import datetime


class TimeType(Flag):
    NONE = 0
    TIME = auto()
    MONTH_DAY = auto()
    YEAR = auto()


def parse_duration(time_string: str) -> Optional[float]:
    """
    Parse duration such as "2h30m". If parse failed, returns None. "0" is parsed as 0. "5" is parsed as 5 minutes.
    """

    if len(time_string) >= 1 and time_string[0] == "-":
        sign = -1.
        positive_part = time_string[1:]
    else:
        sign = 1.
        positive_part = time_string

    days = positive_part.split("d")
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

    minutes = hours[-1].split("m")
    minute_number: Optional[float]
    if len(minutes) == 1 or len(minutes) == 2:  # When no "m" suffix, it's considered minute
        try:
            minute_number = float(minutes[0])
        except ValueError:
            minute_number = None
    else:
        minute_number = None

    if day_number is None and hour_number is None and minute_number is None:
        return None
    else:
        return sign * ((day_number or 0.) * 86400. + (hour_number or 0.) * 3600. + (minute_number or 0.) * 60.)


def time_str(time: Optional[Union[datetime.datetime, datetime.time]]) -> str:
    return time.strftime("%H:%M") if time is not None else ""


def duration_str(seconds: float) -> str:
    def positive_time(positive_seconds: float) -> str:
        days, left = divmod(positive_seconds, 86400)
        hours, left = divmod(left, 3600)
        minutes, left = divmod(left, 60)

        if days != 0:
            return "{day:d}d{hour:d}h{minute:d}".format(day=int(days), hour=int(hours), minute=int(minutes))
        elif hours != 0:
            return "{hour:d}h{minute:d}".format(hour=int(hours), minute=int(minutes))
        else:
            return "{minute:d}".format(minute=int(minutes))

    if seconds >= 0:
        return positive_time(seconds)
    else:
        return "-" + positive_time(-seconds)


def parse_time(time_string: str) -> Optional[datetime.time]:
    time_string = time_string.strip()

    a_format = "%H:%M"

    the_time: Optional[datetime.time]
    try:
        the_time = datetime.datetime.strptime(time_string, a_format).time()
    except ValueError:
        the_time = None

    return the_time


def parse_datetime(time_string: str) -> Tuple[Optional[datetime.datetime], TimeType]:
    time_string = time_string.strip()

    formats = [
        ("%H:%M", TimeType.TIME),

        ("%m-%d", TimeType.MONTH_DAY),
        ("%Y-%m-%d", TimeType.YEAR | TimeType.MONTH_DAY),

        ("%m-%d %H:%M", TimeType.MONTH_DAY | TimeType.TIME),
        ("%Y-%m-%d %H:%M", TimeType.YEAR | TimeType.MONTH_DAY | TimeType.TIME)
    ]

    the_time: Optional[datetime.datetime]
    the_type: TimeType
    for a_format, a_type in formats:
        try:
            the_time = datetime.datetime.strptime(time_string, a_format)
            the_type = a_type
        except ValueError:
            pass
        else:
            break
    else:
        the_time = None
        the_type = TimeType.NONE

    if the_type is TimeType.NONE:
        pass
    elif the_type is TimeType.TIME:
        the_time = datetime.datetime.combine(datetime.datetime.now().date(), the_time.time())
    elif TimeType.YEAR not in the_type:
        the_time = the_time.replace(year=datetime.datetime.now().year)

    return the_time, the_type


def time_diff(time1: datetime.time, time2: datetime.time) -> float:
    date = datetime.datetime.fromtimestamp(0).date()

    datetime1 = datetime.datetime.combine(date, time1)
    datetime2 = datetime.datetime.combine(date, time2)

    return (datetime1 - datetime2).total_seconds()

