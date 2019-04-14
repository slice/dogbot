__all__ = ['UserReference']

import re

from discord.ext import commands

DISCORDTAG_REGEX = re.compile(r'.{2,32}#\d{4}')


class UserReference(commands.Converter):
    async def convert(self, ctx, arg):
        if arg.isdigit() and (15 <= len(arg) <= 21):
            return int(arg)

        if DISCORDTAG_REGEX.match(arg) is not None:
            return arg

        raise commands.BadArgument('Invalid user. Specify an ID or DiscordTag.')
