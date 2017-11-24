"""
Contains commands that shows information about the bot itself, like statistics,
and who made me.
"""

import logging
import platform

import discord
from discord.ext.commands import command

from dog import Cog
from dog.core.context import DogbotContext
from dog.core.converters import RawMember
from dog.core.utils import shell

logger = logging.getLogger(__name__)


class About(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.maker = None

    @command(aliases=['inv'])
    async def invite(self, ctx: DogbotContext):
        """Sends you my invite link."""

        if ctx.bot.is_private:
            return await ctx.send(
                "This bot is private and can't be invited. Sorry!")

        link = discord.utils.oauth_url(
            ctx.bot.user.id, permissions=discord.Permissions.none())
        await ctx.send(f'<{link}>')

    @command(hidden=True, aliases=['ginvite', 'ginv'])
    async def generate_invite(self, ctx, *client_ids: RawMember):
        """Generates Discord invite URL(s) from a client ID."""

        if not client_ids:
            return await ctx.send(
                "Provide some client IDs or bot mentions for me to process.")

        if len(client_ids) > 25:
            return await ctx.send(
                "That's too many for me. No more than 25, please!")

        urls = [
            '<' + discord.utils.oauth_url(bot.id) + '>' for bot in client_ids
        ]

        await ctx.send('\n'.join(urls))

    @command(aliases=['helpme', 'support'])
    async def wiki(self, ctx):
        """Need help using Dogbot?"""

        wiki = f'https://github.com/{ctx.bot.cfg["bot"]["github"]}/wiki'
        invite = ctx.bot.cfg['bot']['woof']['invite']

        await ctx.send(await ctx._('cmd.wiki', wiki=wiki, invite=invite))

    @command(aliases=['info'])
    async def about(self, ctx):
        """Shows information about the bot."""

        git_revision = (await shell('git rev-parse --short HEAD')).strip()

        if self.maker is None:
            self.maker = discord.utils.get(
                self.bot.get_all_members(), id=ctx.bot.cfg["bot"]["owner_id"])

        birthday = self.bot.user.created_at.strftime(
            await ctx._('cmd.about.birthday'))
        github = ctx.bot.cfg["bot"]["github"]

        embed = discord.Embed(
            title=await ctx._('cmd.about.title'),
            description=await ctx._('cmd.about.description', maker=self.maker))

        rev_link = f'[{git_revision}](https://github.com/{github}/commit/{git_revision})'

        # git revision
        embed.add_field(
            name=await ctx._('cmd.about.fields.git_rev'), value=rev_link)

        # github repo link
        embed.add_field(
            name=await ctx._('cmd.about.fields.github_repo'),
            value='[{0}](https://www.github.com/{0})'.format(github))

        # birthday
        embed.add_field(
            name=await ctx._('cmd.about.fields.birthday'), value=birthday)

        # who made me?
        embed.set_author(
            name=f'{self.maker.name}#{self.maker.discriminator}',
            icon_url=self.maker.avatar_url)

        # information about python and discord.py
        pyversion = platform.python_version()
        version = discord.__version__
        embed.set_footer(
            text='Python {} \N{EM DASH} Discord.py {}'.format(
                pyversion, version),
            icon_url='http://i.imgur.com/v1dAbXi.png')

        await ctx.send(embed=embed)

    @command(name='github')
    async def _github(self, ctx):
        """Tells you my GitHub link."""
        gh = f'https://github.com/{ctx.bot.cfg["bot"]["github"]}'
        await ctx.send(
            f"I'm on GitHub at {gh}. Feel free to use handy tidbits of my source code!"
        )


def setup(bot):
    bot.add_cog(About(bot))
