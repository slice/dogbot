"""
Contains commands that have to do with configuring the bot for your server.
"""

import logging

import asyncpg
from discord.ext import commands

from dog import Cog

log = logging.getLogger(__name__)
CONFIGKEYS_HELP = '<https://github.com/slice/dogbot/wiki/Configuration>'


class Prefix(commands.Converter):
    async def convert(self, ctx: commands.Context, arg: str):
        if len(arg) > 140:
            raise commands.BadArgument('Prefixes cannot be greater than 140 characters.')
        return arg


class Config(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.permitted_keys = (
            'invisible_nag',
            'modlog_filter_allow_bot',
            'welcome_message',
            'modlog_notrack_deletes',
            'modlog_notrack_edits',
            'modlog_channel_id',
            'pollr_mod_log',
            'log_all_message_events'
        )

    @commands.group(aliases=['cfg'])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def config(self, ctx):
        """ Manages server-specific configuration for the bot. """
        if ctx.invoked_subcommand is None:
            await ctx.send('You need to specify a valid subcommand to run. For help, run `d?help cfg`.')

    @config.command(name='set')
    async def config_set(self, ctx, name: str, *, value: str='on'):
        """ Sets a config field for this server. """

        if len(value) > 1000:
            await ctx.send('That value is too long! 1000 characters max.')
            return

        if name not in self.permitted_keys:
            return await ctx.send(await ctx._('cmd.config.set.invalid', wikipage=CONFIGKEYS_HELP))

        await self.bot.redis.set(f'{ctx.guild.id}:{name}', value)
        await ctx.ok()

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
        keys = [k.decode().split(':')[1] async for k in self.bot.redis.iscan(match=f'{ctx.guild.id}:*')]
        if not keys:
            return await ctx.send(await ctx._('cmd.config.list.none'))
        await ctx.send('Set configuration keys in this server: ' + ', '.join(keys))

    @config.command(name='remove', aliases=['rm', 'del', 'delete'])
    async def config_remove(self, ctx, name: str):
        """ Removes a config field for this server. """
        await self.bot.redis.delete(f'{ctx.guild.id}:{name}')
        await ctx.ok()

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
    async def prefix_add(self, ctx, prefix: Prefix):
        """
        Adds a prefix.

        In order to add a prefix with a space at the end, you must quote the argument.

        Examples:
            d?prefix add "lol "
            d?prefix add "pls "
            d?prefix add ?
        """
        cache = ctx.bot.prefix_cache.get(ctx.guild.id, [])

        try:
            async with ctx.acquire() as conn:
                await conn.execute('INSERT INTO prefixes VALUES ($1, $2)', ctx.guild.id, prefix)
        except asyncpg.UniqueViolationError:
            await ctx.send('This server already has that prefix.')

        ctx.bot.prefix_cache[ctx.guild.id] = cache + [prefix]
        log.debug('Added "%s" to cache for %d', prefix, ctx.guild.id)

        await ctx.ok()

    @prefix.command(name='remove')
    async def prefix_remove(self, ctx, prefix: Prefix):
        """ Removes a prefix. """
        async with ctx.acquire() as conn:
            await conn.execute('DELETE FROM prefixes WHERE guild_id = $1 AND prefix = $2', ctx.guild.id,
                               prefix)
        try:
            cache = ctx.bot.prefix_cache.get(ctx.guild.id)
            cache.remove(prefix)
            ctx.bot.prefix_cache[ctx.guild.id] = cache
        except ValueError:
            pass
        log.debug('Removed "%s" from cache for %d', prefix, ctx.guild.id)

        await ctx.ok()

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
