"""
Information extension.
"""

import discord
from discord.ext import commands

from dog import Cog
from dog.core import utils

cm = lambda v: utils.commas(v)

SERVER_INFO_MEMBERS = '''{} total member(s)
{} online, {} offline
{}% online'''

SERVER_INFO_COUNT = '''{} role(s)
{} text channel(s), {} voice channel(s)
{} channel(s)'''



class Info(Cog):
    @commands.command()
    @commands.guild_only()
    async def server(self, ctx):
        """ Shows information about the server. """
        g = ctx.guild
        embed = discord.Embed(title=g.name)

        # server icon
        if g.icon_url:
            embed.set_thumbnail(url=g.icon_url)

        # members
        total_members = len(g.members)
        num_online = len(list(filter(lambda m: m.status is discord.Status.online, g.members)))
        num_offline = len(list(filter(lambda m: m.status is discord.Status.offline, g.members)))
        embed.add_field(name='Members', value=SERVER_INFO_MEMBERS.format(
            cm(total_members), cm(num_online), cm(num_offline),
            round((num_online / total_members) * 100, 2)
        ))

        embed.add_field(name='Count', value=SERVER_INFO_COUNT.format(
            cm(len(g.roles)), cm(len(g.text_channels)), cm(len(g.voice_channels)),
            cm(len(g.channels))
        ))

        # guild owner
        embed.set_footer(text=f'Owned by {g.owner}', icon_url=g.owner.avatar_url)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Info(bot))
