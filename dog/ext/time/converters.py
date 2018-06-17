import datetime

from discord.ext import commands


def hour_minute(stamp):
    parts = stamp.split(':')
    if len(parts) != 2:
        raise commands.BadArgument('Invalid sleep time. Example: 7:00')
    try:
        hour = int(parts[0])
        minute = int(parts[1])

        return datetime.datetime(
            year=2018, month=3, day=15,  # random date
            hour=hour, minute=minute
        )
    except ValueError:
        raise commands.BadArgument('Invalid hour/minute numerals.')
