from textwrap import dedent

import discord
import lifesaver
from discord.ext import commands
from lifesaver.utils import human_delta

from dog.converters import HardMember


def date(date) -> str:
    return f"{date}\n{human_delta(date)} ago"


class Info(lifesaver.Cog):
    """A cog that provides information about various entities like guilds or members."""

    @lifesaver.command(aliases=["about"])
    async def info(self, ctx: lifesaver.Context):
        """Information about me."""
        app_info = await ctx.bot.application_info()
        embed = discord.Embed(color=discord.Color.green())
        embed.set_author(
            name=ctx.bot.user,
            url="https://github.com/slice/dogbot",
            icon_url=str(ctx.bot.user.display_avatar),
        )
        embed.description = ctx.bot.description
        embed.add_field(
            name="Created", value=human_delta(ctx.bot.user.created_at) + " ago"
        )
        embed.set_footer(
            text=f"Owned by {app_info.owner}",
            icon_url=str(app_info.owner.display_avatar),
        )
        await ctx.send(embed=embed)

    @lifesaver.group(
        aliases=["guild", "guild_info", "server_info"], invoke_without_command=True
    )
    @commands.guild_only()
    async def server(self, ctx: lifesaver.Context):
        """Views information about this server."""
        embed = discord.Embed(title=ctx.guild.name)
        embed.set_thumbnail(url=str(ctx.guild.icon))
        embed.set_footer(
            text=f"Owned by {ctx.guild.owner}", icon_url=str(ctx.guild.owner.avatar)
        )

        g: discord.Guild = ctx.guild
        n_humans = sum(1 for m in g.members if not m.bot)
        n_bots = len(g.members) - n_humans
        embed.description = dedent(
            f"""\
            {n_humans} humans, {n_bots} bots ({n_humans + n_bots} members)

            Created {g.created_at}
            {human_delta(g.created_at)} ago
        """
        )

        embed.add_field(
            name="Entities",
            value=dedent(
                f"""\
            {len(g.text_channels)} text channels, {len(g.voice_channels)} voice channels, {len(g.categories)} categories
            {len(g.roles)} roles
        """
            ),
        )

        await ctx.send(embed=embed)

    @server.command(aliases=["icon_url"])
    @commands.guild_only()
    async def icon(self, ctx: lifesaver.Context):
        """Sends this server's icon."""
        if not ctx.guild.icon:
            await ctx.send("This server doesn't have a custom icon.")
            return

        await ctx.send(ctx.guild.icon.replace(format="png"))


async def setup(bot):
    await bot.add_cog(Info(bot))
