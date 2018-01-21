import discord
from discord.ext import commands
from discord.ext.commands import Converter, MemberConverter
from lifesaver.bot import Context


class SoftMember(Converter):
    """A MemberConverter that falls back to a :class:`discord.Object` when an ID is provided and they weren't found."""

    async def convert(self, ctx: Context, argument: str):
        try:
            member = await MemberConverter().convert(ctx, argument)
            return member
        except commands.BadArgument:
            if argument.isdigit():
                return discord.Object(id=int(argument))
            else:
                raise commands.BadArgument('Member not found')
