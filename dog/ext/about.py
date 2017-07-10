"""
Contains commands that shows information about the bot itself, like statistics,
and who made me.
"""

import datetime
import logging
import platform
from subprocess import check_output

import discord
from discord.ext import commands

from dog import Cog
from dog.core import utils
from dog_config import github, owner_id

logger = logging.getLogger(__name__)


class About(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.maker = None

    @commands.command(aliases=['oauth'])
    async def invite(self, ctx):
        """ Tells you my invite (OAuth) link. """
        perms = discord.Permissions(permissions=8)
        client_id = (await self.bot.application_info()).id
        link = discord.utils.oauth_url(client_id, permissions=perms)
        await ctx.send(link)

    @commands.command(aliases=['helpme', 'support'])
    async def wiki(self, ctx):
        """ Need help using Dogbot? """
        wiki = 'https://github.com/slice/dogbot/wiki'
        invite = 'https://discord.gg/Ucs96UH'
        await ctx.send(f'Need help with Dogbot? The wiki ({wiki}) has all'
                       f' of your answers! Support server: {invite}')

    @commands.command(hidden=True)
    async def command_list(self, ctx):
        """ Shows you my detailed list of commands. """
        await ctx.send('The command list has been deprecated in favor of my `d?help` command.')

    @commands.command(aliases=['info'])
    async def about(self, ctx):
        """ Shows information about the bot. """
        git_revision = check_output(['git', 'rev-parse', '--short', 'HEAD'])\
            .strip().decode('utf-8')

        if self.maker is None:
            self.maker = discord.utils.get(self.bot.get_all_members(), id=owner_id)

        birthday = self.bot.user.created_at.strftime('%B %m (born %Y)')

        embed = discord.Embed(
            title='Dogbot',
            description=f'A handy Discord bot by {self.maker.mention} ({self.maker.id}).')
        rev_link = (f'[{git_revision}](https://github.com/{github}/commit/'
                    f'{git_revision})')
        embed.add_field(name='Git revision', value=rev_link)
        embed.add_field(name='GitHub repository',
                        value='[{0}](https://www.github.com/{0})'.format(github))
        embed.add_field(name='Birthday', value=birthday)
        embed.set_author(name=f'{self.maker.name}#{self.maker.discriminator}',
                         icon_url=self.maker.avatar_url)
        pyversion = platform.python_version()
        version = discord.__version__
        embed.set_footer(text='Python {} \N{EM DASH} Discord.py {}'.format(pyversion, version),
                         icon_url='http://i.imgur.com/v1dAbXi.png')
        await ctx.send(embed=embed)

    @commands.command(name='github', aliases=['source'])
    async def _github(self, ctx):
        """ Tells you my GitHub link. """
        gh = f'https://github.com/{github}'
        await ctx.send(f'I\'m on GitHub at {gh}. Feel free to use handy'
                       ' tidbits of my source code!')


def setup(bot):
    bot.add_cog(About(bot))
