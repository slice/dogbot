"""
Specific utilites relevant to the Dogbot support server.
"""

import logging

import discord
from discord.ext import commands

from dog import Cog

log = logging.getLogger(__name__)


def is_dogbot_support(msg):
    return isinstance(msg.channel, discord.TextChannel) and msg.guild.id == 302247144201388032


def get_subbed_role(ctx: commands.Context) -> discord.Role:
    return discord.utils.get(ctx.guild.roles, name='subbed')


class Doghouse(Cog):
    @commands.group(aliases=['dh'])
    @commands.check(is_dogbot_support)
    async def doghouse(self, ctx):
        """ Useful commands for Dogbot support. """
        pass

    @doghouse.command()
    @commands.is_owner()
    async def post(self, ctx, *, message: str):
        """ Posts something to subscribers. """
        subbed = get_subbed_role(ctx)
        channel = discord.utils.get(ctx.guild.channels, name='subscribers')

        # temporarily make the role mentionable
        # see https://github.com/Rapptz/RoboDanny/blob/master/cogs/api.py#L383-L420
        await subbed.edit(mentionable=True)

        # send the actual message
        await channel.send('{}: {}'.format(subbed.mention, message))

        # revert back
        await subbed.edit(mentionable=False)
        await self.bot.ok(ctx)

    @doghouse.command(aliases=['sub'])
    async def subscribe(self, ctx):
        """
        Subscribe to things like polls.

        Want to influence Dogbot's future? Subscribe to participate
        in bikeshedding and other stuff.
        """
        await ctx.message.author.add_roles(get_subbed_role(ctx))
        await self.bot.ok(ctx)

    @doghouse.command(aliases=['unsub'])
    async def unsubscribe(self, ctx):
        """ Unsubscribes to some alerts. """
        await ctx.message.author.remove_roles(get_subbed_role(ctx))
        await self.bot.ok(ctx)

    @doghouse.command()
    async def info(self, ctx):
        """ What's this? """
        await ctx.send('This command group provides useful utilities '
                       'to those in the Dogbot Support server! You '
                       'can run `d?help doghouse`')


def setup(bot):
    bot.add_cog(Doghouse(bot))
