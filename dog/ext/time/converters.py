import datetime

import pytz
from discord.ext import commands


class Timezone(commands.Converter):
    async def convert(self, ctx, argument):
        cog = ctx.command.cog

        try:
            member = await commands.MemberConverter().convert(ctx, argument)
            timezone = cog.timezones.get(member.id)
            if timezone:
                return (member, pytz.timezone(timezone))
        except commands.BadArgument:
            pass

        try:
            timezone = pytz.timezone(argument)
            return (argument, timezone)
        except (pytz.exceptions.InvalidTimeError, pytz.exceptions.UnknownTimeZoneError):
            raise commands.BadArgument(
                "Invalid timezone. Specify a user to use their timezone or use a timezone code."
            )


def hour_minute(stamp):
    parts = stamp.split(":")
    if len(parts) != 2:
        raise commands.BadArgument("Invalid sleep time. Example: 7:00")
    try:
        hour = int(parts[0])
        minute = int(parts[1])

        return datetime.datetime(
            year=2018, month=3, day=15, hour=hour, minute=minute  # random date
        )
    except ValueError:
        raise commands.BadArgument("Invalid hour/minute numerals.")
