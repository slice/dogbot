import datetime
import logging
import discord
import platform
from subprocess import check_output
from discord.ext import commands
from dog import Cog, checks
from dog_config import owner_id, github

logger = logging.getLogger(__name__)


class About(Cog):
    def __init__(self, bot):
        super().__init__(self, bot)
        self.maker = None

    @commands.command()
    async def about(self, ctx):
        """ Shows information about the bot. """
        git_revision = check_output(['git', 'rev-parse', '--short', 'HEAD'])\
            .strip().decode('utf-8')

        if self.maker is None:
            self.maker = await self.bot.get_user_info(owner_id)

        embed = discord.Embed(
            title='Dogbot',
            description=f'A nice Discord bot by {self.maker.mention} ({self.maker.id}).'
            f' Available on GitHub [here](https://github.com/{github})!')
        rev_link = (f'[{git_revision}](https://github.com/{github}/commit/'
                    f'{git_revision})')
        embed.add_field(name='Git revision', value=rev_link)
        embed.add_field(name='Python', value=platform.python_version())
        embed.set_footer(text=f'{self.maker.name}#{self.maker.discriminator}',
                         icon_url=self.maker.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(name='github', aliases=['git', 'source', 'source_code'])
    async def _github(self, ctx):
        """ Tells you my GitHub link! """
        gh = f'https://github.com/{github}'
        await ctx.send(f'I\'m on GitHub at {gh}. Feel free to use handy'
                       ' tidbits of my source code!')

    @commands.command()
    @checks.is_owner()
    async def stats(self, ctx):
        """ Shows participation info about the bot. """
        num_members = len(list(self.bot.get_all_members()))
        num_channels = len(list(self.bot.get_all_channels()))
        num_servers = len(self.bot.guilds)
        uptime = str(datetime.datetime.utcnow() - self.bot.boot_time)[:-7]

        embed = discord.Embed(title='Statistics')
        fields = {
            'Members': num_members,
            'Channels': num_channels,
            'Servers': num_servers,
            'Uptime': uptime,
        }
        for name, value in fields.items():
            embed.add_field(name=name, value=value)
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(About(bot))
