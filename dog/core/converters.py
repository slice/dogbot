import datetime
import re
from collections import namedtuple

import parsedatetime
from discord.ext import commands

BareCustomEmoji = namedtuple('BareCustomEmoji', 'id name')


class FormattedCustomEmoji(commands.Converter):
    regex = re.compile(r'<:([a-z0-9A-Z_-]+):(\d+)>')

    async def convert(self, ctx, argument):
        match = self.regex.match(argument)
        if not match:
            raise commands.errors.BadArgument('Invalid custom emoji.')
        return BareCustomEmoji(id=int(match.group(2)), name=match.group(1))


class HumanTime(commands.Converter):
    async def convert(self, ctx, argument):
        cal = parsedatetime.Calendar()
        dt, _ = cal.parseDT(argument)
        return (dt - datetime.datetime.now()).total_seconds()
