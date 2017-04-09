import discord
from discord.ext import commands
from dog import Cog


class Mod(Cog):
    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member):
        """ Kicks someone from the server. """
        await ctx.guild.kick(member)
        await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def ban(self, ctx, member: discord.Member, days: int=0):
        """ Bans someone from the server. """
        await ctx.guild.ban(member, days)
        await ctx.message.add_reaction('\N{OK HAND SIGN}')

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def attentionseek(self, ctx, replace_with: str='💩'):
        """
        Changes attention-seeking nicknames.

        This will change the nickname of anybody whose name starts with "!"
        to a name you specify. By default, they are renamed to "💩".

        The renaming of attention-seekers is borrowed from the Discord API
        server.
        """
        attention_seekers = [m for m in ctx.guild.members if
                             m.display_name.startswith('!')]
        succeeded = len(attention_seekers)
        for seeker in attention_seekers:
            try:
                await seeker.edit(nick=replace_with)
            except:
                succeeded -= 1
        failed_count = len(attention_seekers) - succeeded
        await ctx.send(f'Renamed {succeeded} attention seeker(s).'
                       f' Failed to rename {failed_count}.')


def setup(bot):
    bot.add_cog(Mod(bot))
