"""
Contains commands that shows information about the bot itself, like statistics,
and who made me.
"""

import logging
import platform
from subprocess import check_output

import discord
from discord.ext import commands

from dog import Cog

logger = logging.getLogger(__name__)


class About(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.maker = None

    @commands.command(aliases=['inv'])
    async def invite(self, ctx):
        """ Tells you my invite link. """
        if ctx.bot.is_private:
            await ctx.send("This bot is private and can't be invited. Sorry!")
            return
        link = discord.utils.oauth_url((await self.bot.application_info()).id,
                                       permissions=(discord.Permissions.none()))
        await ctx.send(f'<{link}>')

    @commands.command(hidden=True, aliases=['ginvite', 'ginv'])
    async def generate_invite(self, ctx, *client_ids: int):
        """ Generates Discord invite URL(s) from a client ID. """
        if len(client_ids) > 25:
            return await ctx.send("That's too many for me. No more than 25, please!")
        urls = ['<' + discord.utils.oauth_url(client_id) + '>' for client_id in client_ids]
        await ctx.send('\n'.join(urls))

    @commands.command(aliases=['helpme', 'support'])
    async def wiki(self, ctx):
        """ Need help using Dogbot? """
        wiki = f'https://github.com/{ctx.bot.cfg["bot"]["github"]}/wiki'
        invite = ctx.bot.cfg['bot']['woof']['invite']
        await ctx.send(await ctx._('cmd.wiki', wiki=wiki, invite=invite))

    @commands.command(aliases=['info'])
    async def about(self, ctx):
        """ Shows information about the bot. """
        git_revision = check_output(['git', 'rev-parse', '--short', 'HEAD'])\
            .strip().decode('utf-8')

        if self.maker is None:
            self.maker = discord.utils.get(self.bot.get_all_members(), id=ctx.bot.cfg["bot"]["owner_id"])

        birthday = self.bot.user.created_at.strftime(await ctx._('cmd.about.birthday'))
        github = ctx.bot.cfg["bot"]["github"]

        embed = discord.Embed(title=await ctx._('cmd.about.title'), description=await ctx._('cmd.about.description',
                                                                                maker=self.maker))
        rev_link = f'[{git_revision}](https://github.com/{github}/commit/{git_revision})'
        embed.add_field(name=await ctx._('cmd.about.fields.git_rev'), value=rev_link)
        embed.add_field(name=await ctx._('cmd.about.fields.github_repo'), value='[{0}](https://www.github.com/{0})'.format(
            github))
        embed.add_field(name=await ctx._('cmd.about.fields.birthday'), value=birthday)
        embed.set_author(name=f'{self.maker.name}#{self.maker.discriminator}', icon_url=self.maker.avatar_url)

        pyversion = platform.python_version()
        version = discord.__version__
        embed.set_footer(text='Python {} \N{EM DASH} Discord.py {}'.format(pyversion, version),
                         icon_url='http://i.imgur.com/v1dAbXi.png')
        await ctx.send(embed=embed)

    @commands.command(name='github', aliases=['source'])
    async def _github(self, ctx):
        """ Tells you my GitHub link. """
        gh = f'https://github.com/{ctx.bot.cfg["bot"]["github"]}'
        await ctx.send(f'I\'m on GitHub at {gh}. Feel free to use handy tidbits of my source code!')


def setup(bot):
    bot.add_cog(About(bot))
