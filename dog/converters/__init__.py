import re

import discord
import lifesaver
from discord.ext import commands

from .emoji_stealer import EmojiStealer

class UserID(commands.Converter):
    """A converter that converts members to IDs."""

    async def convert(self, ctx: lifesaver.Context, argument: str):
        try:
            member = await commands.MemberConverter().convert(ctx, argument)
            return member.id
        except commands.BadArgument:
            pass

        if not argument.isdigit():
            raise commands.BadArgument('Invalid user ID.')

        return int(argument)


class HardMember(commands.Converter):
    """A MemberConverter that falls back to fetching the user's information
    using the Discord API.

    The fallback will only be used if an ID was passed.
    """

    async def convert(self, ctx: lifesaver.Context, argument: str):
        try:
            return await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            pass

        if not argument.isdigit():
            raise commands.BadArgument('Member not found. Try specifying a user ID.')

        try:
            return await ctx.bot.fetch_user(int(argument))
        except discord.NotFound:
            raise commands.BadArgument('User not found.')
        except discord.HTTPException as error:
            raise commands.BadArgument(f'Failed to fetch user information: `{error}`')


class SoftMember(commands.Converter):
    """A MemberConverter that falls back to a :class:`discord.Object` of the
    ID when provided.
    """

    async def convert(self, ctx: lifesaver.Context, argument: str):
        try:
            return await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            if argument.isdigit():
                return discord.Object(int(argument))

            raise commands.BadArgument('Member not found. Try specifying a user ID.')
