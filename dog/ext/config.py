"""
Contains commands that have to do with configuring the bot for your server.
"""
import enum
import inspect
import logging
from collections import namedtuple
from enum import Enum
from typing import Any

import discord
from discord.ext import commands
from discord.ext.commands import clean_content, group

from dog import Cog
from dog.core.context import DogbotContext

log = logging.getLogger(__name__)
CONFIGKEYS_HELP = '<https://github.com/slice/dogbot/wiki/Configuration>'
PREFIX_KEY = 'dog:prefixes:{0.id}'


class Prefix(commands.Converter):
    async def convert(self, ctx: DogbotContext, arg: str):
        # limit
        if len(arg) > 140:
            raise commands.BadArgument(
                'Prefixes cannot be greater than 140 characters.')

        # scrub content of mentions, etc.
        return await clean_content().convert(ctx, arg)


class ConfigurationError(Exception):
    pass


class CustomKeyTypes(Enum):
    text_channel_id = enum.auto()


class Key(namedtuple('Key', 'type description')):
    def check(self, value: Any, ctx: DogbotContext) -> bool:
        # boolean configuration keys's active state are determined by their presence in redis, so they don't have an
        # associated value.
        if self.type is bool and value != 'on':
            raise ConfigurationError(
                "Don't provide a value to this configuration key. It can only be on or off."
            )

        if self.type is CustomKeyTypes.text_channel_id:
            # not a number
            if not value.isdigit():
                raise ConfigurationError(
                    "That doesn't look like a channel ID.")

            channel = discord.utils.get(ctx.guild.text_channels, id=int(value))

            if not channel:
                raise ConfigurationError(
                    f"A text channel with an ID of `{value}` was not found.")

            return True

        try:
            return_value = self.type(value)
            return return_value is not None
        except:
            return False


class Config(Cog):
    CONFIG_KEYS = {
        'invisible_nag':
        Key(type=bool,
            description="Makes me nag at invisible users when enabled."),
        'modlog_filter_allow_bot':
        Key(type=bool,
            description="Allows bots' messages to be logged to the modlog."),
        'welcome_message':
        Key(type=str,
            description="Sets the welcome message sent to #welcome."),
        'modlog_notrack_deletes':
        Key(type=bool,
            description="Disables message deletion logging when enabled."),
        'modlog_notrack_edits':
        Key(type=bool,
            description="Disables message edit logging when enabled."),
        'modlog_channel_id':
        Key(type=CustomKeyTypes.text_channel_id,
            description=
            "The ID of the modlog channel to use, instead of #mod-log."),
        'pollr_mod_log':
        Key(type=bool,
            description="Logs pollr-style bans to #bans when enabled."),
        'log_all_message_events':
        Key(type=bool,
            description="Logs all messages, even from private channels when "
            "enabled."),
        'shortlinks_enabled':
        Key(type=bool, description='Enables "shortlinks".')
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @group(aliases=['cfg'])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def config(self, ctx: DogbotContext):
        """Manages server-specific configuration for the bot."""
        if ctx.invoked_subcommand is None:
            await ctx.send(
                f'You need to specify a valid subcommand to run. For help, run `{ctx.prefix}help cfg`.'
            )

    @config.command(name='set')
    async def config_set(self, ctx, name, *, value: str = 'on'):
        """Sets a config field for this server."""

        if len(value) > 1000:
            await ctx.send('That value is too long! 1000 characters max.')
            return

        # key isn't a valid key
        if name not in self.CONFIG_KEYS:
            return await ctx.send(await ctx._(
                'cmd.config.set.invalid', wikipage=CONFIGKEYS_HELP))

        key = self.CONFIG_KEYS[name]

        # check if the configuration value was actually valid
        try:
            if not key.check(value, ctx):
                return await ctx.send('Invalid configuration value.')
        except ConfigurationError as err:
            return await ctx.send(str(err))

        await self.bot.redis.set(f'{ctx.guild.id}:{name}', value)
        await ctx.ok()

    @config.command(name='permitted')
    async def config_permitted(self, ctx: DogbotContext):
        """Views configuration keys that you can set."""
        header = f'Need descriptions? Check here: {CONFIGKEYS_HELP}\n\n'

        def key_description(name: str, key: Key):
            key_type = \
                key.type.__name__ if inspect.isclass(key.type) else \
                key.type.name

            return '`{name}` (`{type}`): {description}'.format(
                name=name, type=key_type, description=key.description)

        keys = '\n'.join(
            key_description(key_name, key)
            for key_name, key in self.CONFIG_KEYS.items())
        await ctx.send(header + keys)

    @config.command(name='is_set')
    async def config_is_set(self, ctx: DogbotContext, name):
        """Checks if a configuration key is set in this server."""
        is_set = await self.bot.config_is_set(ctx.guild, name)
        await ctx.send('Yes, it is set.' if is_set else 'No, it is not set.')

    @config.command(name='list', aliases=['ls'])
    async def config_list(self, ctx: DogbotContext):
        """Lists set configuration keys in this server."""
        keys = [
            k.decode().split(':')[1]
            async for k in self.bot.redis.iscan(match=f'{ctx.guild.id}:*')
        ]
        if not keys:
            return await ctx.send(await ctx._('cmd.config.list.none'))
        await ctx.send(
            'Set configuration keys in this server: ' + ', '.join(keys))

    @config.command(name='remove', aliases=['rm', 'del', 'delete', 'unset'])
    async def config_remove(self, ctx: DogbotContext, name):
        """
        Removes a config field for this server.

        This effectively disables boolean configuration keys.
        """
        await self.bot.redis.delete(f'{ctx.guild.id}:{name}')
        await ctx.ok()

    @config.command(name='get', aliases=['cat'])
    async def config_get(self, ctx: DogbotContext, name):
        """Views a config field for this server."""
        if not await self.bot.config_is_set(ctx.guild, name):
            return await ctx.send('That config field is not set.')

        value = await self.bot.redis.get(f'{ctx.guild.id}:{name}')
        await ctx.send(f'`{name}`: {value.decode()}')

    @group()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx: DogbotContext):
        """
        Manages supplemental bot prefixes for this server.
        Only members with "Manage Server" may manage prefixes.

        By adding supplemental prefixes, prefixes such as d? will continue to
        function. When Dogbot references commands, like "d?ping", d? will always
        be used in the helptext. Don't worry as you can use your supplemental prefixes
        in place of "d?".
        """
        if ctx.invoked_subcommand is None:
            await ctx.send(
                f"You need to specify a valid subcommand to run. For help, run `{ctx.prefix}help prefix`."
            )

    @prefix.command(name='add')
    async def prefix_add(self, ctx: DogbotContext, prefix: Prefix):
        """
        Adds a prefix.

        In order to add a prefix with a space at the end, you must quote the argument.
        """
        await ctx.bot.redis.sadd(PREFIX_KEY.format(ctx.guild), prefix)
        await ctx.ok()

    @prefix.command(name='remove')
    async def prefix_remove(self, ctx: DogbotContext, prefix: Prefix):
        """Removes a prefix."""
        await ctx.bot.redis.sremove(PREFIX_KEY.format(ctx.guild), prefix)
        await ctx.ok()

    @prefix.command(name='list')
    async def prefix_list(self, ctx: DogbotContext):
        """Lists all supplemental prefixes."""
        prefixes = await ctx.bot.get_prefixes(ctx.guild)
        if not prefixes:
            return await ctx.send(
                'There are no supplemental prefixes for this server. Add one with '
                + '`d?prefix add <prefix>`.')
        prefix_list = ', '.join(f'`{p}`' for p in prefixes)
        await ctx.send(f'Prefixes for this server: {prefix_list}')


def setup(bot):
    bot.add_cog(Config(bot))
