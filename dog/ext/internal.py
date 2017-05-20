"""
Dogbot internal commands.
"""

import io
from time import monotonic

import discord
import objgraph
from discord.ext import commands

from dog import Cog
from dog.core import utils

DETAILED_PING = '''**message create:** {}
**message edit:** {}
**message delete:** {}
'''


class Internal(Cog):
    async def __local_check(self, ctx):
        return await self.bot.is_owner(ctx.message.author)

    @commands.command()
    async def dping(self, ctx):
        """ Detailed ping. """
        def ms(before, after):
            return str(round((after - before) * 1000, 2)) + 'ms'

        # do it
        before_send = monotonic()
        msg = await ctx.send('...')
        after_send = monotonic()
        await msg.edit(content='..')
        after_edit = monotonic()
        await msg.delete()
        after_delete = monotonic()

        await ctx.send(DETAILED_PING.format(
            ms(before_send, after_send),
            ms(after_send, after_edit),
            ms(after_edit, after_delete)
        ))

    @commands.group()
    async def mem(self, ctx):
        """ Memory statistics. """
        pass

    @mem.command()
    async def count(self, ctx, type_name):
        """ Counts the amount of an object tracked by the GC. """
        cnt = objgraph.count(type_name)
        if not cnt:
            return await ctx.send('Not found.')
        await ctx.send('`{}`: {}'.format(type_name, utils.commas(cnt)))

    @mem.command()
    async def common_types(self, ctx, limit: int=5):
        """ Shows common types tracked by the GC. """
        with io.StringIO() as stdout:
            objgraph.show_most_common_types(limit=limit, file=stdout)
            await ctx.send('```\n{}\n```'.format(stdout.getvalue()))


def setup(bot):
    bot.add_cog(Internal(bot))
