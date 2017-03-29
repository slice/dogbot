from time import monotonic
from discord.ext import commands
from dog import Cog

class Admin(Cog):
    @commands.command()
    async def ping(self):
        """ You know what this does. """
        begin = monotonic()
        msg = await self.bot.say('Pong!')
        end = monotonic()
        difference_ms = round((end - begin) * 1000, 2)
        await self.bot.edit_message(msg, f'Pong! Took `{difference_ms}ms`.')

    @commands.command()
    async def prefixes(self):
        """ Lists the bot's prefixes. """
        prefixes = ', '.join([f'`{p}`' for p in self.bot.command_prefix])
        await self.bot.say(f'My prefixes are: {prefixes}')

def setup(bot):
    bot.add_cog(Admin(bot))
