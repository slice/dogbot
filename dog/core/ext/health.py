"""
Commands used to check the health of the bot.
"""
import datetime

from discord.ext import commands

from dog import Cog
from dog.core.utils import Timer


class Health(Cog):
    @commands.command()
    async def ping(self, ctx):
        """Pong!"""

        # measure rest delay
        with Timer() as timer:
            msg = await ctx.send('Po\N{EM DASH}')

        pong_ws = round(ctx.bot.latency * 1000, 2)
        pong_rest = round(timer.interval * 1000, 2)
        pong_gateway_lag = round(
            (datetime.datetime.utcnow() - msg.created_at).total_seconds() *
            1000, 2)

        pong = f'Pong! W: `{pong_ws}ms`, R: `{pong_rest}ms`, G: `{pong_gateway_lag}ms`'
        await msg.edit(content=pong)


def setup(bot):
    bot.add_cog(Health(bot))
