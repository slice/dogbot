import discord
from discord.ext import commands
from dog import Cog


class Mod(Cog):
    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member):
        """ Kicks someone from the server. """
        await ctx.guild.kick(member)
        await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, days: int = 0):
        """ Bans someone from the server. """
        await ctx.guild.ban(member, days)
        await ctx.message.add_reaction('\N{OK HAND SIGN}')


def setup(bot):
    bot.add_cog(Mod(bot))