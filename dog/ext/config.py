"""
Contains commands that have to do with configuring the bot for your server.

This extension also contains commands that globally configure the bot, but only
the owner can use those.
"""

import logging

from discord.ext import commands

from dog import Cog

log = logging.getLogger(__name__)
CONFIGKEYS_HELP = '<https://github.com/sliceofcode/dogbot/wiki/Configuration>'

class Prefix(commands.Converter):
    async def convert(self, ctx: commands.Context, arg: str):
        if len(arg) > 140:
            raise commands.BadArgument('Prefixes cannot be greater than 140 characters.')
        return arg


class Config(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.permitted_keys = [
            'woof_command_enabled',
            'unmute_announce',
            'mutesetup_disallow_read',
            'invisible_announce',
            'modlog_filter_allow_bot',
            'welcome_message',
            'modlog_notrack_deletes',
            'modlog_notrack_edits',
            'modlog_channel_id',
            'pollr_announce'
        ]

    @commands.group(aliases=['gcfg'])
    @commands.is_owner()
    async def global_config(self, ctx):
        """ Manages global configuration for the bot. """

    @global_config.command(name='set')
    async def global_config_set(self, ctx, name: str, value: str='on'):
        """ Sets a config field. """
        await self.bot.redis.set(name, value)
        await self.bot.ok(ctx)

    @global_config.command(name='remove', aliases=['rm', 'del', 'delete'])
    async def global_config_remove(self, ctx, name: str):
        """ Remove a config field. """
        await self.bot.redis.delete(name)
        await self.bot.ok(ctx)

    @global_config.command(name='get', aliases=['cat'])
    async def global_config_get(self, ctx, name: str):
        """ Views a config field. """
        value = await self.bot.redis.get(name)
        if value is None:
            await ctx.send(f'`{name}` is unset.')
        else:
            await ctx.send(f'`{name}`: {value.decode()}')

    @commands.group(aliases=['cfg'])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def config(self, ctx):
        """ Manages server-specific configuration for the bot. """

    @config.command(name='set')
    async def config_set(self, ctx, name: str, value: str='on'):
        """ Sets a config field for this server. """

        if len(value) > 1000:
            await ctx.send('That value is too long! 1000 characters max.')
            return

        if name not in self.permitted_keys:
            await ctx.send(
                'Whoops! That configuration key is not allowed to be set.'
                ' For a list of configurable config keys, execute'
                f' `d?cfg permitted`. Visit {CONFIGKEYS_HELP} for descriptions.')
            return

        await self.bot.redis.set(f'{ctx.guild.id}:{name}', value)
        await self.bot.ok(ctx)

    @config.command(name='permitted')
    async def config_permitted(self, ctx):
        """ Views permitted configuration keys. """
        header = f'Need descriptions? Check here: {CONFIGKEYS_HELP}\n\n'
        await ctx.send(header + ', '.join(self.permitted_keys))

    @config.command(name='is_set')
    async def config_is_set(self, ctx, name: str):
        """ Checks if a configuration key is set. """
        is_set = await self.bot.config_is_set(ctx.guild, name)
        await ctx.send('Yes, it is set.' if is_set else 'No, it is not set.')

    @config.command(name='list', aliases=['ls'])
    async def config_list(self, ctx):
        """ Lists set configuration keys for this server. """
        keys = [k.decode().split(':')[1] for k in await self.bot.redis.keys(f'{ctx.guild.id}:*')]
        if not keys:
            await ctx.send('No set configuration keys in this server!'
                           '\nTry running `d?config permitted` to see a list'
                           ' of configurable keys.')
            return
        await ctx.send('Set configuration keys in this server: ' + ', '.join(keys))

    @config.command(name='remove', aliases=['rm', 'del', 'delete'])
    async def config_remove(self, ctx, name: str):
        """ Removes a config field for this server. """
        await self.bot.redis.delete(f'{ctx.guild.id}:{name}')
        await self.bot.ok(ctx)

    @config.command(name='get', aliases=['cat'])
    async def config_get(self, ctx, name: str):
        """ Views a config field for this server. """
        if not await self.bot.config_is_set(ctx.guild, name):
            await ctx.send('That config field is not set.')
            return
        else:
            value = await self.bot.redis.get(f'{ctx.guild.id}:{name}')
            await ctx.send(f'`{name}`: {value.decode()}')

    @commands.group()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx):
        """
        Manages supplemental bot prefixes for this server.
        Only members with "Manage Server" may manage prefixes.

        By adding supplemental prefixes, prefixes such as d? will continue to
        function. When Dogbot references commands, like "d?ping", d? will always
        be used in the helptext. Don't worry as you can use your supplemental prefixes
        in place of "d?".
        """

    @prefix.command(name='add')
    async def prefix_add(self, ctx: commands.Context, prefix: Prefix):
        """
        Adds a prefix.

        In order to add a prefix with a space at the end, you must quote the argument.

        Examples:
            d?prefix add "lol "
            d?prefix add "pls "
            d?prefix add ?
        """
        cache = ctx.bot.prefix_cache.get(ctx.guild.id, [])

        # cache is guaranteed to be populated by now, because it is populated before
        # commands are ran
        if prefix in cache:
            return await ctx.send('This server already has that prefix.')

        async with ctx.bot.pgpool.acquire() as conn:
            await conn.execute('INSERT INTO prefixes VALUES ($1, $2)', ctx.guild.id, prefix)

        ctx.bot.prefix_cache[ctx.guild.id] = cache + [prefix]
        log.debug('Added "%s" to cache for %d', prefix, ctx.guild.id)

        await ctx.bot.ok(ctx)

    @prefix.command(name='remove')
    async def prefix_remove(self, ctx: commands.Context, prefix: Prefix):
        """ Removes a prefix. """
        async with ctx.bot.pgpool.acquire() as conn:
            await conn.execute('DELETE FROM prefixes WHERE guild_id = $1 AND prefix = $2', ctx.guild.id,
                               prefix)
        try:
            cache = ctx.bot.prefix_cache.get(ctx.guild.id)
            cache.remove(prefix)
            ctx.bot.prefix_cache[ctx.guild.id] = cache
        except ValueError:
            pass
        log.debug('Removed "%s" from cache for %d', prefix, ctx.guild.id)

        await ctx.bot.ok(ctx)

    @prefix.command(name='list')
    async def prefix_list(self, ctx: commands.Context):
        """ Lists all supplemental prefixes. """
        prefixes = await ctx.bot.get_prefixes(ctx.guild)
        if not prefixes:
            return await ctx.send('There are no supplemental prefixes for this server. Add one with ' +
                                  '`d?prefix add <prefix>`.')
        prefix_list = ', '.join([f'`{p}`' for p in prefixes])
        footer = 'View non-supplemental prefixes with `d?prefixes`.'
        await ctx.send(f'Supplemental prefixes for this server: {prefix_list}\n\n' + footer)

def setup(bot):
    bot.add_cog(Config(bot))
