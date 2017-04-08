import random
import datetime
import discord
from asteval import Interpreter
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

    @commands.command()
    @commands.guild_only()
    async def earliest(self, ctx):
        """ Shows who in this server had the earliest Discord join time. """
        members = {m: m.created_at for m in ctx.guild.members if not m.bot}
        earliest_time = min(members.values())
        for member, time in members.items():
            if earliest_time == time:
                msg = (f'{member.name}#{member.discriminator} was the earliest'
                       f' to join Discord in this server. They joined Discord at {time}.')
                await ctx.send(msg)

    @commands.command(name='calc')
    async def calc(self, ctx, *, expression: str):
        """ Evaluates a math expression. """
        terp = Interpreter()
        result = terp.eval(expression)
        if result != '' and result is not None:
            await ctx.send(result)
        else:
            await ctx.send('Empty result.')

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
    @commands.guild_only()
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
