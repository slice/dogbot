from textwrap import dedent

import discord
from discord.ext.commands import guild_only
from lifesaver.bot import Cog, group, Context
from lifesaver.utils import human_delta


class Info(Cog):
    """A cog that provides information about various entities like guilds or members."""

    @group(aliases=['guild', 'guild_info', 'server_info'], invoke_without_command=True)
    @guild_only()
    async def server(self, ctx: Context):
        """Views information about this server."""
        embed = discord.Embed(title=ctx.guild.name)
        embed.set_thumbnail(url=ctx.guild.icon_url)
        embed.set_footer(text=f'Owned by {ctx.guild.owner}', icon_url=ctx.guild.owner.avatar_url)

        g: discord.Guild = ctx.guild
        n_humans = sum(1 for m in g.members if not m.bot)
        n_bots = len(g.members) - n_humans
        embed.description = dedent(f"""\
            {n_humans} humans, {n_bots} bots ({n_humans + n_bots} members)
            
            Created {g.created_at}
            {human_delta(g.created_at)} ago
        """)

        embed.add_field(name='Entities', value=dedent(f"""\
            {len(g.text_channels)} text channels, {len(g.voice_channels)} voice channels, {len(g.categories)} categories
            {len(g.roles)} roles
        """))

        await ctx.send(embed=embed)

    @server.command(aliases=['icon_url'])
    @guild_only()
    async def icon(self, ctx: Context):
        """Sends this server's icon."""
        if not ctx.guild.icon_url:
            await ctx.send('No server icon.')
            return

        await ctx.send(ctx.guild.icon_url_as(format='png'))


def setup(bot):
    bot.add_cog(Info(bot))
