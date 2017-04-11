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
        """ Kicks someone. """
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
    async def unmute(self, ctx, member: discord.Member):
        """ Instantly unmutes someone. """
        mute_role = discord.utils.get(ctx.guild.roles, name='Muted')

        if not mute_role:
            await ctx.send('\N{CROSS MARK} I can\'t find the "Muted" role.')
            return

        if mute_role not in member.roles:
            await ctx.send(f'\N{SPEAKER} That person isn\'t muted.')
            return

        try:
            await member.remove_roles(mute_role)
            await ctx.send(f'\N{SPEAKER} Unmuted {member.name}#{member.discriminator}'
                           f' (`{member.id}`)')
        except discord.Forbidden:
            await ctx.send('\N{CROSS MARK} I can\'t do that!')
        except:
            await ctx.send('\N{CROSS MARK} I failed to do that.')

    @commands.command()
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @checks.is_moderator()
    async def mute(self, ctx, member: discord.Member, time: HumanTime):
        """
        Mutes someone for a certain amount of time.

        The "Muted" role must exist on the server in order for this to work.
        The bot will not setup "Muted" channel overrides for you, you must
        do it yourself.

        d?mute <someone> 5m
            Mutes someone for 5 minutes.
        d?mute <someone> 2h5m
            Mutes someone for 2 hours and 5 minutes.
        d?mute <someone> 5s
            Mutes someone for 5 seconds.
        """
        mute_role = discord.utils.get(ctx.guild.roles, name='Muted')

        if not mute_role:
            await ctx.send('\N{CROSS MARK} I can\'t find the "Muted" role.')
            return

        mute = '\N{SPEAKER WITH CANCELLATION STROKE}'
        msg = await ctx.send(f'{mute} Muting {member.name}#{member.discriminator}'
                             f' (`{member.id}`) for {time.seconds} second(s).')

        try:
            await member.add_roles(mute_role)
        except discord.Forbidden:
            await msg.edit(content='\N{CROSS MARK} I can\'t do that!'
                           ' I might be too low on the role hierarchy,'
                           ' or I need permissions.'
                           ' Ensure that the my bot role is placed above'
                           ' the "Muted" role.')
        except:
            await msg.edit(content='\N{CROSS MARK} I failed to do that.')

        async def unmute_task():
            await asyncio.sleep(time.seconds)
            await member.remove_roles(mute_role)
            if await self.bot.config_is_set(ctx.guild, 'unmute_announce'):
                await ctx.send(f'\N{SPEAKER} {member.name}#{member.discriminator}'
                               f' (`{member.id}`) has been unmuted.')

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
