import asyncio
import discord
from discord.ext import commands
from dog import Cog, checks
from dog.humantime import HumanTime


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
    @commands.bot_has_permissions(manage_roles=True)
    @checks.is_moderator()
    async def mute(self, ctx, member: discord.Member, time: HumanTime):
        """ Mutes someone for a certain amount of time. """
        mute_role = discord.utils.get(ctx.guild.roles, name='Muted')

        if not mute_role:
            await ctx.send('\N{CROSS MARK} I can\'t find the "Muted" role.')
            return

        mute = '\N{SPEAKER WITH CANCELLATION STROKE}'
        msg = await ctx.send(f'{mute} Muting {member.name}#{member.discriminator}'
                             f' (`{member.id}`) for {time.seconds} seconds.')

        try:
            await member.add_roles(mute_role)
        except discord.Forbidden:
            await msg.edit(content='\N{CROSS MARK} I can\'t do that!'
                           ' I might be too low on the role hierarchy,'
                           ' or I need permissions.'
                           ' Ensure that the "Muter" role is placed above'
                           'the "Muted" role.')
        except:
            await msg.edit(content='\N{CROSS MARK} I failed to do that.')

        async def unmute_task():
            await asyncio.sleep(time.seconds)
            await member.remove_roles(mute_role)

        self.bot.loop.create_task(unmute_task())

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_nicknames=True)
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
