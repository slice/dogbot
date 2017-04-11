import logging
from discord.ext import commands
from dog import Cog

log = logging.getLogger(__name__)

class Config(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.permitted_keys = [
            'woof_response'
        ]

    @commands.group()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def config(self, ctx):
        """ Manages server-specific configuration for the bot. """

    @config.command(name='set')
    async def config_set(self, ctx, name: str, value: str):
        """ Sets a config field for this server. """

        if name not in self.permitted_keys:
            await ctx.send('That configuration value is not allowed.')
            return

        await self.bot.redis.set(f'{ctx.guild.id}:{name}', value)
        await ctx.send('\N{OK HAND SIGN}')

    @config.command(name='permitted')
    async def config_permitted(self, ctx):
        """ Views permitted configuration keys. """
        await ctx.send(', '.join(self.permitted_keys))

    @config.command(name='is_set')
    async def config_is_set(self, ctx, name: str):
        """ Checks if a configuration key is set. """
        is_set = await self.bot.config_is_set(ctx.guild, name)
        await ctx.send('Yes, it is set.' if is_set else 'No, it is not set.')

    @config.command(name='get')
    async def config_get(self, ctx, name: str):
        """ Fetches a config field for this server. """

        result = await self.bot.redis.get(f'{ctx.guild.id}:{name}')

        if result is not None:
            result = result.decode()
        else:
            result = '`<nothing>`'

        await ctx.send(f'`{name}`: {result}')

def setup(bot):
    bot.add_cog(Config(bot))
