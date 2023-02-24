__all__ = ["compute_postscript", "format_dt"]

import datetime
import random
from typing import Optional

GLOBES = (
    "\N{EARTH GLOBE AMERICAS}",
    "\N{EARTH GLOBE EUROPE-AFRICA}",
    "\N{EARTH GLOBE ASIA-AUSTRALIA}",
)


def compute_postscript(dt: datetime.datetime) -> Optional[str]:
    match (dt.month, dt.day):
        case (1, 1):  # New Year's Day
            return "\N{FACE WITH PARTY HORN AND PARTY HAT} \N{PARTY POPPER}"
        case (_, 1):  # First of the month
            return "\N{SPIRAL CALENDAR PAD}\N{VARIATION SELECTOR-16}"
        case (10, 31):  # Halloween
            return "\N{JACK-O-LANTERN}"
        case (2, 14):  # Valentine's Day
            return "\N{TWO HEARTS}"
        case (4, 22):  # Earth's Day
            return random.choice(GLOBES)

    return None


def format_dt(
    dt: datetime.datetime,
    *,
    shorten: bool = True,
    time_only: bool = False,
    include_postscript: bool = True,
) -> str:
    # If `shorten` is `True`, we can omit the 12-hour representation
    # before noon as it is redundant (they are the same under both clock
    # representation systems).
    if dt.hour < 12 and shorten:
        time_format = "%H:%M"
    else:
        time_format = "%H:%M (%I:%M %p)"

    if time_only:
        full_format = time_format
    else:
        # Manually interpolate the day to avoid leading zeroes.
        date_format = f"%B {dt.day}"

        if dt.month == 1 and dt.day == 1:
            # Show the year on the first day of the year.
            date_format += ", %Y"

        full_format = f"{date_format}  {time_format}"

    formatted = dt.strftime(full_format)

    if include_postscript and (postscript := compute_postscript(dt)) is not None:
        return f"{formatted} {postscript}"

    return formatted
