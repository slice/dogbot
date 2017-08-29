"""
Commands used to check the health of the bot.
"""
import datetime
from time import monotonic

from dog import Cog

from discord.ext import commands


class Health(Cog):
    @commands.command()
    async def ping(self, ctx):
        """ Pong! """

        # measure gateway delay
        before = monotonic()
        msg = await ctx.send('\u200b')
        after = monotonic()

        pong_ws = round(ctx.bot.latency * 1000, 2)
        pong_rest = round((after - before) * 1000, 2)
        pong_gateway_lag = round((msg.created_at - datetime.datetime.utcnow()).total_seconds() * 1000, 2)

        pong = f'Pong! WS: {pong_ws}ms, REST: {pong_rest}ms, GW lag: {pong_gateway_lag}ms'
        await msg.edit(content=pong)


def setup(bot):
    bot.add_cog(Health(bot))
