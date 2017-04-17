import logging
from discord.ext import commands
from dog import Cog

log = logging.getLogger(__name__)
CONFIGKEYS_HELP = '<https://github.com/sliceofcode/dogbot/wiki/Configuration>'

class Config(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.permitted_keys = [
            'woof_command_enabled',
            'unmute_announce',
            'mutesetup_disallow_read',
            'invisible_announce',
            'modlog_filter_allow_bot'
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

def setup(bot):
    bot.add_cog(Config(bot))
