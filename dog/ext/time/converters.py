import datetime

import dateutil.tz
from discord.ext import commands


class Timezone(commands.Converter):
    async def convert(self, ctx, argument):
        cog = ctx.command.cog

        try:
            member = await commands.MemberConverter().convert(ctx, argument)
            timezone = cog.timezones.get(member.id)
            if timezone:
                return (member, dateutil.tz.gettz(timezone))
        except commands.BadArgument:
            pass

        timezone = dateutil.tz.gettz(argument)

        if timezone is None:
            raise commands.BadArgument(
                "Invalid timezone. "
                "Specify a timezone name (from the tz database) or a user "
                "to use their timezone."
            )

        return (argument, timezone)


def hour_minute(stamp):
    parts = stamp.split(":")
    error_message = "Invalid hour/minute numerals. Examples: `7:00`, `14:00`"

    if len(parts) != 2:
        raise commands.BadArgument(error_message)

    try:
        hour = int(parts[0])
        minute = int(parts[1])

        return datetime.datetime.utcnow().replace(hour=hour, minute=minute, second=0)
    except ValueError:
        raise commands.BadArgument(error_message)
