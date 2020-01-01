import collections

import aiohttp
import discord
import lifesaver
from discord.ext import commands

from dog.converters import HardMember
from dog.ext.info import date


class Profile(lifesaver.Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self.session._default_headers = {
            "User-Agent": "dogbot/0.0.0 (https://github.com/slice)"
        }

    @lifesaver.group(aliases=["whois"], invoke_without_command=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def profile(self, ctx, user: HardMember = None):
        """Views information about a user."""
        user = user or ctx.author

        embed = discord.Embed(title=f"{user} ({user.id})")
        embed.add_field(name="Account Creation", value=date(user.created_at))
        embed.set_thumbnail(url=user.avatar_url)

        if isinstance(user, discord.Member) and user.guild is not None:
            embed.add_field(
                name=f"Joined {ctx.guild.name}",
                value=date(user.joined_at),
                inline=False,
            )

        if user.bot:
            embed.title = f'{ctx.emoji("bot")} {embed.title}'

        await ctx.send(embed=embed)

    @profile.command(name="avatar")
    async def profile_avatar(self, ctx, user: HardMember = None):
        """Views the avatar of a user."""
        user = user or ctx.author
        await ctx.send(user.avatar_url_as(static_format="png"))

    @lifesaver.command(aliases=["avatar_url"])
    async def avatar(self, ctx, user: HardMember = None):
        """Views the avatar of a user."""
        await ctx.invoke(self.profile_avatar, user)


def setup(bot):
    bot.add_cog(Profile(bot))
