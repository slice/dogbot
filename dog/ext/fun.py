import aiohttp
from discord.ext import commands
from dog import Cog

SHIBE_ONLINE = 'http://shibe.online/api/shibes?count=1&urls=true&httpsUrls=true'

class Fun(Cog):
    @commands.command()
    async def shibe(self, ctx):
        """
        Woof!

        Grabs a random Shiba Inu picture from shibe.online.
        """

        async with aiohttp.ClientSession() as session:
            async with session.get(SHIBE_ONLINE) as shibe:
                url = (await shibe.json())[0]
                await ctx.send(url)

def setup(bot):
    bot.add_cog(Fun(bot))
