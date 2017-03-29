import datetime
import discord
from discord.ext import commands
from dog import Cog

class Utility(Cog):
    @commands.command()
    async def avatar(self, target: discord.User):
        """ Shows someone's avatar. """
        await self.bot.say(target.avatar_url)

    @commands.command()
    async def joined(self, target: discord.Member):
        """ Shows when someone joined this server and Discord. """
        def diff(date):
            now = datetime.datetime.utcnow()
            return str(now - date)[:-7]
        await self.bot.say(
            f'{target.display_name} joined this server {target.joined_at}'
            f' ({diff(target.joined_at)} ago).\n'
            f'They joined Discord on {target.created_at} ({diff(target.created_at)}'
            ' ago).'
        )

def setup(bot):
    bot.add_cog(Utility(bot))
