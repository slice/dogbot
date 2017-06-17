"""
Information extension.
"""
import datetime

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

    @commands.command()
    @commands.guild_only()
    async def roles(self, ctx):
        """ Views the roles (and their IDs) in this server. """
        sorted_roles = sorted(ctx.guild.roles, key=lambda r: r.position, reverse=True)
        code = '```\n' + '\n'.join([f'\N{BULLET} {r.name} ({r.id})' for r in sorted_roles]) + '\n```'
        try:
            await ctx.send(code)
        except discord.HTTPException:
            await ctx.send(f'You have too many roles ({len(ctx.guild.roles)}) for me to list!')

    def _make_joined_embed(self, member):
        embed = utils.make_profile_embed(member)
        joined_dif = utils.ago(member.created_at)
        embed.add_field(name='Joined Discord',
                        value=(f'{joined_dif}\n' +
                               utils.american_datetime(member.created_at)))
        return embed


    @commands.command()
    @commands.guild_only()
    async def joined(self, ctx, target: discord.Member=None):
        """
        Shows when someone joined this server and Discord.

        If no arguments were passed, your information is shown.
        """
        if target is None:
            target = ctx.message.author

        embed = self._make_joined_embed(target)
        joined_dif = utils.ago(target.joined_at)
        embed.add_field(name='Joined this Server',
                        value=(f'{joined_dif}\n' +
                               utils.american_datetime(target.joined_at)),
                        inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def earliest(self, ctx):
        """ Shows who in this server had the earliest Discord join time. """
        members = {m: m.created_at for m in ctx.guild.members if not m.bot}
        earliest_time = min(members.values())
        for member, time in members.items():
            if earliest_time == time:
                await ctx.send(embed=self._make_joined_embed(member))


def setup(bot):
    bot.add_cog(Info(bot))
