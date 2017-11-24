from typing import Union

import arrow
import arrow.parser
from arrow import Arrow
from discord import Member
from discord.ext.commands import group, Converter, BadArgument, MemberConverter

from dog import Cog
from dog.core.checks import is_bot_admin
from dog.core.context import DogbotContext

TIMEZONE_KEY = 'dog:user_timezone:{0.id}'
TIME_FORMAT = 'MMM ddd YYYY-MM-DD HH:mm:ss (hh:mm:ss a)'
TIMEZONE_QUERY = """Use `{prefix}t set <timezone>` to set your timezone. With this set, others can check what
time it is for you with `{prefix}t <user>`.

Common timezones:

`REGION                 NAME (TYPE)     UTC OFFSET          `
`Eastern United States  US/Eastern    | (-05:00, -04:00 DST)`
`Central United States  US/Central    | (-06:00, -05:00 DST)`
`Western United States  US/Pacific    | (-08:00, -07:00 DST)`
`London                 Europe/London | (+00:00, +01:00 DST)`
`Western European       WET           | (+00:00, +01:00 DST)`
`Central European       MET           | (+01:00, +02:00 DST)`
`GMT-8                  Etc/GMT-8     | (+08:00, +08:00 DST)`

You want to type what's in the `NAME` column. A full list of timezones is here:
<https://goo.gl/yQNfZU>. Type what's under `TZ*`.
"""


class Timezone(Converter):
    async def convert(self, ctx: DogbotContext, argument: str) -> str:
        cog: 'Time' = ctx.command.instance

        # resolve another user's timezone
        try:
            member = await MemberConverter().convert(ctx, argument)
            timezone = await cog.get_timezone_for(member)
            if timezone:
                return timezone
        except BadArgument:
            pass

        # hippo checking
        blacklisted = list('`\\<>@')
        if any(character in argument
               for character in blacklisted) or len(argument) > 30:
            raise BadArgument("That doesn't look like a timezone.")

        # actually check if it's a valid timezone with arrow's parser
        try:
            arrow.utcnow().to(argument)
        except arrow.parser.ParserError:
            raise BadArgument('Invalid timezone.')

        return argument


class Time(Cog):
    async def get_timezone_for(self, who: Member) -> str:
        """Returns the timezone for a member."""
        return await self.redis.get(TIMEZONE_KEY.format(who), encoding='utf-8')

    async def set_timezone_for(self, who: Member, timezone: str):
        """Sets the timezone for a member."""
        await self.redis.set(TIMEZONE_KEY.format(who), timezone.encode())

    def format_time(self, time: Union[str, Arrow]) -> str:
        return time.format(TIME_FORMAT) if isinstance(
            time, Arrow) else arrow.utcnow().to(time).format(TIME_FORMAT)

    @group(aliases=['t'], invoke_without_command=True)
    async def time(self, ctx: DogbotContext, *, who: Member = None):
        """Views someone's time."""
        who = who or ctx.author
        timezone = await self.get_timezone_for(who)

        if not timezone:
            return await ctx.send(f'{who} has no timezone set.')

        formatted = self.format_time(timezone)
        await ctx.send(f'{who} (`{timezone}`): {formatted}')

    @time.command(name='write', hidden=True)
    @is_bot_admin()
    async def time_write(self, ctx: DogbotContext, target: Member,
                         timezone: Timezone):
        """Sets someone else's timezone."""
        await self.set_timezone_for(target, timezone)
        await ctx.ok()

    @time.command(name='set')
    async def time_set(self, ctx: DogbotContext, timezone: Timezone = None):
        """Sets your timezone."""
        if not timezone:
            return await ctx.send(TIMEZONE_QUERY.format(prefix=ctx.prefix))

        await self.set_timezone_for(ctx.author, timezone)
        await ctx.ok()

    @time.command(name='in')
    async def time_in(self, ctx, *, timezone: Timezone):
        """
        Views time in a timezone.

        List of valid timezone specifiers: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        The "TZ" column is what you want. You can also specify a UTC offset.
        """
        await ctx.send(self.format_time(arrow.utcnow().to(timezone)))

    @time.command(name='diff')
    async def time_diff(self, ctx, a: Timezone, b: Timezone):
        """Views the difference between two timezones."""
        a_u = arrow.now(a).utcoffset()
        b_u = arrow.now(b).utcoffset()

        if a_u == b_u:
            return await ctx.send(f'{a} and {b} have the **same UTC offset.**')

        diff = max(a_u, b_u) - min(a_u, b_u)
        await ctx.send(f'{a} and {b} are **{diff}** apart.')


def setup(bot):
    bot.add_cog(Time(bot))
