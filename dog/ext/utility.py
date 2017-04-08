import random
import datetime
import discord
from discord.ext import commands
from dog import Cog


class Utility(Cog):
    @commands.command()
    async def avatar(self, ctx, target: discord.User=None):
        """
        Shows someone's avatar.

        If no arguments were passed, your avatar is shown.
        """
        if target is None:
            target = ctx.message.author
        await ctx.send(target.avatar_url)

    @commands.command(aliases=['random', 'choose'])
    async def pick(self, ctx, *args):
        """
        Randomly picks things that you give it.

        d?pick one two three
            Makes the bot randomly pick from three words, and displays
            the chosen word.
        """
        await ctx.send(random.choice(args))

    @commands.command()
    async def joined(self, ctx, target: discord.Member=None):
        """
        Shows when someone joined this server and Discord.

        If no arguments were passed, your information is shown.
        """
        if target is None:
            target = ctx.message.author

        def diff(date):
            now = datetime.datetime.utcnow()
            return str(now - date)[:-7]

        await ctx.send(
            f'{target.display_name} joined this server {target.joined_at}'
            f' ({diff(target.joined_at)} ago).\n'
            f'They joined Discord on {target.created_at} '
            f'({diff(target.created_at)}'
            ' ago).'
        )


def setup(bot):
    bot.add_cog(Utility(bot))
