import discord
from discord.ext import commands

from dog import Cog


class Wipe(Cog):
    @commands.command(aliases=['w'])
    async def wipe(self, ctx, messages: int):
        """ Wipe, wipe. """
        await ctx.message.delete()
        async for msg in ctx.channel.history(limit=messages):
            if msg.author == ctx.bot.user:
                await msg.delete()


def setup(bot):
    bot.add_cog(Wipe(bot))
