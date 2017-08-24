import datetime
import discord
from discord.ext import commands

from dog import Cog
from dog.core import checks, context, utils
from dog.core.utils import describe


class Gatekeeper(Cog):
    CUSTOMIZATION_KEYS = (
        'block_default_avatar',   # blocks users with default avatars
        'minimum_creation_time',  # minimum discord registration time in seconds
        'bounce_message',         # message to send to users right before getting bounced
        'block_all',              # blocks all users
    )

    async def __local_check(self, ctx):
        return ctx.guild and checks.member_is_moderator(ctx.author)

    async def on_member_join(self, member: discord.Member):
        if not await self.bot.redis.exists(f'gatekeeper:{member.guild.id}:enabled'):
            return

        settings = await self.bot.redis.hgetall(f'gatekeeper:{member.guild.id}:settings')  # get customization keys
        settings = {key.decode(): value.decode() for key, value in settings.items()}  # decode keys and values

        async def report(*args, **kwargs):
            """ Sends a message to the broadcast channel for this guild. """
            try:
                cid = int((await self.bot.redis.get(f'gatekeeper:{member.guild.id}:broadcast_channel')).decode())
                broadcast_channel = self.bot.get_channel(cid)

                # no channel
                if not broadcast_channel:
                    return

                # send
                return await broadcast_channel.send(*args, **kwargs)
            except (TypeError, discord.Forbidden):
                # couldn't send or parse the broadcast channel id
                pass

        async def block(reason: str):
            """ Bounces a user from this guild."""

            # send bounce message
            if 'bounce_message' in settings:
                try:
                    await member.send(settings['bounce_message'])
                except discord.Forbidden:
                    pass

            try:
                # adios
                await member.kick(reason=f'Gatekeeper check(s) failed ({reason})')
            except discord.Forbidden:
                await report(f"\N{CROSS MARK} Couldn't kick {describe(member)}, no permissions.")
            else:
                # report
                embed = discord.Embed(color=discord.Color.red(), title=f'Bounced {describe(member)}')
                embed.add_field(name='Account creation', value=utils.ago(member.created_at))
                embed.add_field(name='Reason', value=reason)
                embed.set_thumbnail(url=member.avatar_url)
                await report(embed=embed)

        if 'block_all' in settings:
            return await block('blocking all users')

        if 'minimum_creation_time' in settings:
            try:
                minimum_required = int(settings['minimum_creation_time'])
                seconds_on_discord = (datetime.datetime.utcnow() - member.created_at).total_seconds()
                ago = utils.ago(member.created_at)

                if seconds_on_discord < minimum_required:
                    return await block(f'failed minimum creation time check ({seconds_on_discord} < {minimum_required}'
                                       f', created {ago})')
            except ValueError:
                pass

        if 'block_default_avatar' in settings:
            if member.default_avatar_url == member.avatar_url:
                return await block('has default avatar')

        # joined!
        embed = discord.Embed(color=discord.Color.green(), title=f'{describe(member)} joined',
                              description='This user has passed all Gatekeeper checks and has joined the server.')
        embed.set_thumbnail(url=member.avatar_url)
        await report(embed=embed)

    @commands.group(aliases=['gk'])
    async def gatekeeper(self, ctx: commands.Context):
        """ Manages Gatekeeper. """
        if ctx.invoked_subcommand is None:
            return await ctx.send(f'You need to specify a valid subcommand to run. For help, run `{ctx.prefix}help gk`.')

    @gatekeeper.command()
    async def unset(self, ctx: context.DogbotContext, key):
        """ Unsets a Gatekeeper criteria. """
        await ctx.bot.redis.hdel(f'gatekeeper:{ctx.guild.id}:settings', key)
        await ctx.send(f'\N{OK HAND SIGN} Deleted `{key}`.')

    @gatekeeper.command(aliases=['engage', 'on'])
    async def enable(self, ctx: context.DogbotContext):
        """ Turns on Gatekeeper. """
        await ctx.bot.redis.set(f'gatekeeper:{ctx.guild.id}:enabled', 'true')
        await ctx.bot.redis.set(f'gatekeeper:{ctx.guild.id}:broadcast_channel', ctx.channel.id)
        await ctx.send("\U0001f6a8 Gatekeeper was **enabled**. I'll be broadcasting join messages to this channel.")

    @gatekeeper.command(aliases=['disengage', 'off'])
    async def disable(self, ctx: context.DogbotContext):
        """ Turns off Gatekeeper. """
        if await ctx.confirm(title='Are you sure you want to disable Gatekeeper?',
                             description='I will stop screening member joins.') is True:
            await ctx.bot.redis.delete(f'gatekeeper:{ctx.guild.id}:enabled')
            await ctx.bot.redis.delete(f'gatekeeper:{ctx.guild.id}:broadcast_channel')
            await ctx.send('\U0001f6a8 Gatekeeper was **disabled**.')

    @gatekeeper.command()
    async def set(self, ctx: context.DogbotContext, key, *, value: commands.clean_content = 'true'):
        """ Sets a Gatekeeper criteria. """

        # check for valid customization keys
        if key not in self.CUSTOMIZATION_KEYS:
            keys = ', '.join(f'`{key}`' for key in self.CUSTOMIZATION_KEYS)
            return await ctx.send(f'Invalid key. Valid keys: {keys}')

        hash_key = f'gatekeeper:{ctx.guild.id}:settings'
        await ctx.bot.redis.hset(hash_key, key, value)
        await ctx.send(f'\N{OK HAND SIGN} Set `{key}` to `{value}`.')

    @gatekeeper.command()
    async def status(self, ctx: context.DogbotContext):
        """ Views the current status of Gatekeeper. """
        enabled = await ctx.gatekeeper_enabled()

        description = "I'm not screening member joins at the moment." if not enabled else "I'm screening member joins."
        embed = discord.Embed(color=discord.Color.green() if not enabled else discord.Color.red(),
                              title='Gatekeeper is ' + ('active' if enabled else 'disabled') + '.',
                              description=description)

        # add customization keys
        customs = await ctx.bot.redis.hgetall(f'gatekeeper:{ctx.guild.id}:settings')
        customs_field = '\n'.join([f'`{key.decode()}`: `{value.decode()}`' for key, value in customs.items()])
        if customs_field:
            embed.add_field(name='Settings', value=customs_field)

        # broadcasting channel
        broadcast_channel = await ctx.bot.redis.get(f'gatekeeper:{ctx.guild.id}:broadcast_channel')
        if broadcast_channel:
            try:
                broadcast_channel = ctx.bot.get_channel(int(broadcast_channel.decode()))
                embed.add_field(name='Broadcast channel', value=describe(broadcast_channel, mention=True), inline=False)
            except ValueError:
                pass

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Gatekeeper(bot))
