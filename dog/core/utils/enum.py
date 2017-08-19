from discord.ext import commands


class EnumConverter:
    @classmethod
    async def convert(cls, ctx, arg):
        try:
            if arg not in [e.name for e in cls]:
                return cls[arg.upper()]
            else:
                return cls[arg]
        except KeyError:
            valid_keys = ', '.join('`{}`'.format(num.name.lower()) for num in list(cls))
            raise commands.BadArgument('Invalid type. Valid types: {}'.format(valid_keys))
