__all__ = ["compute_postscript", "format_dt"]

import datetime
import random
import typing as T

MatcherValue = T.Optional[T.Union[range, int]]
Matcher = T.Tuple[MatcherValue, MatcherValue, MatcherValue, MatcherValue]

POSTSCRIPTS: T.Dict[Matcher, T.Union[str, T.List[str]]] = {
    # new year's day
    (1, 1, 0, range(31)): "\N{face with party horn and party hat} \N{party popper}",
    # first day of the month
    (None, 1, None, None): "\N{spiral calendar pad}\N{variation selector-16}",
    # halloween
    (10, 31, None, None): "\N{jack-o-lantern}",
    # valentine's day
    (2, 14, None, None): "\N{two hearts}",
    # earth day
    (4, 22, None, None): [
        "\N{earth globe americas}",
        "\N{earth globe europe-africa}",
        "\N{earth globe asia-australia}",
    ],
}


def compute_postscript(dt: datetime.datetime) -> T.Optional[str]:
    def _match(value: int, matcher: MatcherValue) -> bool:
        if matcher is None:
            # `None` means we don't care about the value, so always match
            return True
        if isinstance(matcher, range):
            return value in matcher
        return value == matcher

    postscript = next(
        (
            postscript
            for ((month, day, hour, minute), postscript) in POSTSCRIPTS.items()
            if _match(dt.month, month)
            and _match(dt.day, day)
            and _match(dt.hour, hour)
            and _match(dt.minute, minute)
        ),
        None,
    )

    if postscript is None:
        return None

    if isinstance(postscript, list):
        return random.choice(postscript)

    return postscript


def format_dt(
    dt: datetime.datetime,
    *,
    shorten: bool = True,
    time_only: bool = False,
    include_postscript: bool = True,
) -> str:
    # if `shorten` is `True`, we can omit the 12-hour representation
    # before noon as it is redundant (they are the same under both clock
    # representation systems)
    if dt.hour < 12 and shorten:
        time_format = "%H:%M"
    else:
        time_format = "%H:%M (%I:%M %p)"

    if time_only:
        full_format = time_format
    else:
        date_format = "%B %d"

        if dt.month == 1 and dt.day == 1:
            # Show the year on the first day of the year.
            date_format += ", %Y"

        full_format = f"{date_format}  {time_format}"

    formatted = dt.strftime(full_format)

    if include_postscript and (postscript := compute_postscript(dt)) is not None:
        return f"{formatted} {postscript}"

    return formatted
