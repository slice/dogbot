import arrow
from discord.ext.commands import group

from dog import Cog


class Time(Cog):
    @group()
    async def time(self, ctx):
        """ Time-related commands. """
        if ctx.invoked_subcommand is None:
            await ctx.send(f'You must specify a valid subcommand to run. For help, run `{ctx.prefix}?help time`.')

    @time.command(name='in')
    async def time_in(self, ctx, *, timezone):
        """
        Views time in a timezone.

        List of valid timezone specifiers: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        The "TZ" column is what you want. You can also specify a UTC offset.
        """
        try:
            time = arrow.utcnow().to(timezone)
            await ctx.send(time.format('YYYY-MM-DD (MMM, ddd) HH:mm:ss (hh:mm:ss A) ZZ'))
        except arrow.parser.ParserError:
            await ctx.send('Invalid timezone.')

    @time.command(name='tzdifference', aliases=['tzdiff', 'tzd'])
    async def time_tzdifference(self, ctx, a, b):
        """
        Views the difference between two timezones.
        """
        try:
            a_u = arrow.now(a).utcoffset()
            b_u = arrow.now(b).utcoffset()
            if a_u == b_u:
                return await ctx.send(f'{a} and {b} have the **same UTC offset.**')
            diff = max(a_u, b_u) - min(a_u, b_u)
            await ctx.send(f'{a} and {b} are **{diff}** apart.')
        except arrow.parser.ParserError:
            await ctx.send('Parsing error. Typically, this means your timezones were invalid.')


def setup(bot):
    bot.add_cog(Time(bot))
