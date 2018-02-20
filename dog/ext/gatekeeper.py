import logging
import datetime
import re
from typing import Optional

import discord
from discord import Member, Embed
from discord.ext import commands

from lifesaver.bot import Cog, Context
from lifesaver.bot.storage import AsyncJSONStorage
from lifesaver.utils import human_delta

from dog.formatting import represent

log = logging.getLogger(__name__)


class Block(Exception):
    """
    An exception that blocks a user from joining a guild.
    This should only be thrown inside of a :class:`GatekeeperCheck`.
    """
    pass


class Report(Exception):
    """
    An exception that immediately sends text to the broadcasting channel.
    This should only be thrown inside of a :class:`GatekeeperCheck`.
    """
    pass


class GatekeeperCheck:
    """A Gatekeeper check."""
    key = None

    async def check(self, config_value, member: Member):
        raise NotImplementedError


class BlockDefaultAvatarCheck(GatekeeperCheck):
    """A gatekeeper check that bounces users with a default avatar."""
    key = 'block_default_avatar'
    description = 'Blocks all users with a default avatar.'

    async def check(self, _, member: Member):
        if member.default_avatar_url == member.avatar_url:
            raise Block('Has default avatar')


class MinimumCreationTimeCheck(GatekeeperCheck):
    """A gatekeeper check that checks the minimum creation time of a user."""
    key = 'minimum_creation_time'
    description = (
        "Blocks users that don't meet a \"minimum creation time\" check. Specify the amount of seconds "
        "that an account has to exist for to be allowed to pass through.")

    async def check(self, time, member: Member):
        try:
            minimum_required = int(time)
            seconds_on_discord = (datetime.datetime.utcnow() - member.created_at).total_seconds()

            if seconds_on_discord < minimum_required:
                raise Block(
                    f'Failed minimum creation time check ({seconds_on_discord} < {minimum_required}')
        except ValueError:
            raise Report(
                'Invalid minimum creation time, must be a valid number.')


class BlockAllCheck(GatekeeperCheck):
    """A gatekeeper check that bounces all users that attempt to join."""
    key = 'block_all'
    description = 'Blocks all users that try to join.'

    async def check(self, _, member: Member) -> bool:
        raise Block('Blocking all users')


class UsernameRegexCheck(GatekeeperCheck):
    key = 'username_regex'
    description = 'Blocks all usernames that match a regex. Specify a regex.'

    async def check(self, regex: str, member: Member):
        try:
            regex = re.compile(regex)
            if regex.search(member.name):
                raise Block('Matched username regex')
        except re.error as err:
            raise Report(
                f"\N{CROSS MARK} `username_regex` was invalid: `{err}`, ignoring this check."
            )


GATEKEEPER_CHECKS = {
    BlockDefaultAvatarCheck, MinimumCreationTimeCheck, BlockAllCheck,
    UsernameRegexCheck
}


class Gatekeeper(Cog):
    CUSTOMIZATION_KEYS = (
        'block_default_avatar',  # blocks users with default avatars
        'minimum_creation_time',  # minimum discord registration time in seconds
        'bounce_message',  # message to send to users right before getting bounced
        'block_all',  # blocks all users
        'username_regex',  # username regex
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.storage = AsyncJSONStorage('gatekeeper.json', loop=self.bot.loop)

    async def __local_check(self, ctx: Context):
        return ctx.guild and ctx.author.guild_permissions.ban_members

    def state(self, guild: discord.Guild):
        return self.storage.get(guild.id, {})

    def is_enabled(self, guild: discord.Guild) -> bool:
        return self.state(guild).get('is_enabled', False)

    async def on_member_join(self, member: Member):
        if not self.is_enabled(member.guild):
            return

        state = self.state(member.guild)
        settings = state.get('settings', {})

        async def report(*args, **kwargs) -> Optional[discord.Message]:
            """Sends a message to the broadcast channel for this guild."""
            try:
                channel_id = state.get('broadcast_channel_id')
                broadcast_channel = self.bot.get_channel(channel_id)

                # no channel
                if not broadcast_channel:
                    log.warning("Couldn't find broadcast channel for guild %d.", member.guild.id)
                    return

                # send
                return await broadcast_channel.send(*args, **kwargs)
            except (TypeError, discord.Forbidden):
                # couldn't send or parse the broadcast channel id
                pass

        async def block(reason: str):
            """Bounces a user from this guild."""

            # person got bounced, send bounce message
            if 'bounce_message' in settings:
                try:
                    await member.send(settings['bounce_message'])
                except discord.HTTPException:
                    pass

            try:
                # adios
                await member.kick(reason=f'Gatekeeper check(s) failed ({reason})')
            except discord.Forbidden:
                await report(
                    f"\N{CROSS MARK} Couldn't kick {represent(member)}, no permissions. You will have to kick them "
                    "manually."
                )
            else:
                # report
                embed = Embed(color=discord.Color.red(), title=f'Bounced {represent(member)}')
                embed.add_field(
                    name='Account creation',
                    value=f'{human_delta(member.created_at)} ago\n{member.created_at}'
                )
                embed.add_field(name='Reason', value=reason)
                embed.timestamp = datetime.datetime.utcnow()
                embed.set_thumbnail(url=member.avatar_url)
                await report(embed=embed)

        for check in GATEKEEPER_CHECKS:
            # if the check's config key hasn't been set, skip it
            if check.key not in settings:
                continue

            try:
                # run the check
                await check().check(settings[check.key], member)
            except Block as block_exc:
                # we have bounced this user, no point in checking anymore
                return await block(str(block_exc))
            except Report as report_exc:
                # something went wrong...report it
                await report(str(report_exc))

        # this person has passed all checks
        embed = Embed(
            color=discord.Color.green(),
            title=f'{represent(member)} joined',
            description=
            'This user has passed all Gatekeeper checks and has joined the server.'
        )
        embed.set_thumbnail(url=member.avatar_url)
        embed.timestamp = datetime.datetime.utcnow()
        await report(embed=embed)

    @commands.group(aliases=['gk'])
    async def gatekeeper(self, ctx: commands.Context):
        """
        Manages Gatekeeper.

        Gatekeeper is an advanced mechanism of Dogbot that allows you to screen member joins in realtime,
        and automatically kick those who don't fit a certain criteria. Only users who can ban can use it.
        This is very useful when your server is undergoing raids, unwanted attention, unwanted members, etc.
        """
        if ctx.invoked_subcommand is None:
            return await ctx.send(
                f'You need to specify a valid subcommand to run. For help, run `{ctx.prefix}help gk`.'
            )

    @gatekeeper.command()
    async def settings(self, ctx: Context):
        """Lists all possible settings that you can configure."""
        message = ''

        for check in GATEKEEPER_CHECKS:
            message += f'`{check.key}`: {check.description}\n'

        # synthetic
        message += """`bounce_message`: A message that will be sent to users right before being kicked."""

        await ctx.send(message)

    @gatekeeper.command()
    async def unset(self, ctx: Context, key):
        """Unsets a Gatekeeper criteria."""
        settings = self.state(ctx.guild).get('settings', {})

        try:
            del settings[key]
        except KeyError:
            pass

        await self.storage.put(ctx.guild.id, {
            **self.state(ctx.guild),
            'settings': settings
        })
        await ctx.send(f'\N{OK HAND SIGN} Deleted `{key}`.')

    @gatekeeper.command(aliases=['engage', 'on'])
    async def enable(self, ctx: Context):
        """Turns on Gatekeeper."""
        if not ctx.guild.me.guild_permissions.kick_members:
            await ctx.send("I can't kick members, so Gatekeeper won't be useful.")
            return

        state = self.state(ctx.guild)
        state['is_enabled'] = True
        state['broadcast_channel_id'] = ctx.channel.id
        await self.storage.put(ctx.guild.id, state)

        await ctx.send("\U0001f6a8 Gatekeeper was **enabled**. I'll be broadcasting join messages to this channel.")

    @gatekeeper.command(aliases=['disengage', 'off'])
    async def disable(self, ctx: Context):
        """Turns off Gatekeeper."""
        state = self.state(ctx.guild)
        state['is_enabled'] = False
        await self.storage.put(ctx.guild.id, state)

        await ctx.send('\U0001f6a8 Gatekeeper was **disabled**.')

    @gatekeeper.command()
    async def set(self, ctx: Context, key, *, value: commands.clean_content = 'true'):
        """
        Sets a Gatekeeper criteria.
        With this command, you can set a criteria for Dogbot to check on newly added members.
        """

        # check for valid customization keys
        if key not in self.CUSTOMIZATION_KEYS:
            keys = ', '.join(f'`{key}`' for key in self.CUSTOMIZATION_KEYS)
            return await ctx.send(f'Invalid key. Valid keys: {keys}')

        settings = self.state(ctx.guild).get('settings', {})
        settings[key] = value
        await self.storage.put(ctx.guild.id, {
            **self.state(ctx.guild),
            'settings': settings
        })

        await ctx.send(f'\N{OK HAND SIGN} Set `{key}` to `{value}`.')

    @gatekeeper.command()
    async def status(self, ctx: Context):
        """Views the current status of Gatekeeper."""
        enabled = self.is_enabled(ctx.guild)

        description = "I'm not screening member joins at the moment." if not enabled else "I'm screening member joins."
        embed = Embed(
            color=discord.Color.green()
            if not enabled else discord.Color.red(),
            title='Gatekeeper is ' + ('active' if enabled else 'disabled') + '.',
            description=description
        )

        # add customization keys
        customs = self.state(ctx.guild).get('settings', {})
        customs_field = '\n'.join(
            f'`{key}`: `{value}`'
            for key, value in customs.items()
        )
        if customs_field:
            embed.add_field(name='Settings', value=customs_field)

        # broadcasting channel
        broadcast_channel = self.state(ctx.guild).get('broadcast_channel_id')
        channel = ctx.bot.get_channel(broadcast_channel)
        if channel:
            embed.add_field(name='Join broadcast channel', value=channel.mention, inline=False)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Gatekeeper(bot))
