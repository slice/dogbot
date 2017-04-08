import aiohttp
from discord.ext import commands
from dog import Cog

SHIBE_ENDPOINT = 'http://shibe.online/api/shibes?count=1&urls=true&httpsUrls=true'
DOGFACTS_ENDPOINT = 'https://dog-api.kinduff.com/api/facts'

async def _get_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

class Fun(Cog):
    @commands.command()
    async def shibe(self, ctx):
        """
        Woof!

        Grabs a random Shiba Inu picture from shibe.online.
        """
        await ctx.send((await _get_json(SHIBE_ENDPOINT))[0])

    @commands.command()
    async def dogfact(self, ctx):
        """ Returns a random dog fact. """
        facts = await _get_json(DOGFACTS_ENDPOINT)
        if not facts['success']:
            await ctx.send('I couldn\'t contact the Dog Facts API.')
            return
        await ctx.send(facts['facts'][0])

def setup(bot):
    bot.add_cog(Fun(bot))
