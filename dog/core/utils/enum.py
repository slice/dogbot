from enum import Enum

from discord.ext import commands


class EnumConverter:
    """
    A class that when subclassed, turns an :class:`enum.Enum` into a converter that functions by looking up
    enum values' names when passed as arguments.
    """

    @classmethod
    async def convert(cls: Enum, ctx: 'DogbotContext', arg: str):
        try:
            if arg not in [e.name for e in cls]:
                return cls[arg.upper()]
            else:
                return cls[arg]
        except KeyError:
            # value in enum not found

            valid_keys = ', '.join(
                '`{}`'.format(num.name.lower()) for num in list(cls))
            raise commands.BadArgument(
                'Invalid type. Valid types: {}'.format(valid_keys))
