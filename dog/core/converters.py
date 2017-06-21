import datetime
import re
from collections import namedtuple

import discord
import parsedatetime
from discord.ext import commands
from discord.ext.commands import MemberConverter

BareCustomEmoji = namedtuple('BareCustomEmoji', 'id name')


class FormattedCustomEmoji(commands.Converter):
    regex = re.compile(r'<:([a-z0-9A-Z_-]+):(\d+)>')

    async def convert(self, ctx, argument):
        match = self.regex.match(argument)
        if not match:
            raise commands.BadArgument('Invalid custom emoji.')
        return BareCustomEmoji(id=int(match.group(2)), name=match.group(1))


class RawMember(commands.Converter):
    async def convert(self, ctx, argument):
        # garbo
        try:
            return await MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            try:
                return discord.Object(id=int(argument))
            except TypeError:
                raise commands.BadArgument('Invalid member ID. I also couldn\'t find the user by username.')


class HumanTime(commands.Converter):
    async def convert(self, ctx, argument):
        cal = parsedatetime.Calendar()
        dt, _ = cal.parseDT(argument)
        return (dt - datetime.datetime.now()).total_seconds()


class Guild(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            guild_id = int(argument)
            guild = ctx.bot.get_guild(guild_id)
            if not guild:
                raise commands.BadArgument(f'A guild by the ID of {guild_id} was not found.')
            return guild
        except TypeError:
            raise commands.BadArgument('Invalid guild ID.')
