import asyncio
import datetime
import urllib.parse
from html.parser import HTMLParser
from typing import Any, Dict

import discord
import timeago
from discord.ext import commands


class Paginator:
    def __init__(self, text, max = 2000):
        self.text = text
        self.current_page = 0
        self.chunks = [text[i:i + max] for i in range(0, len(text), max)]
        self.message = None

    def jump_to(self, page):
        self.current_page = page

    def next_page(self):
        if self.current_page == len(self.chunks) - 1:
            return
        self.current_page += 1

    def prev_page(self):
        if self.current_page == 0:
            return
        self.current_page -= 1

    async def paginate(self, ctx):
        self.message = await ctx.send(self.chunks[self.current_page])

        emoji = [
            '\N{LEFTWARDS BLACK ARROW}',
            '\N{BLACK RIGHTWARDS ARROW}',
            '\N{BLACK SQUARE FOR STOP}'
        ]

        # add the arrows we need
        for codepoint in emoji:
            await self.message.add_reaction(codepoint)

        async def invalidate():
            await self.message.edit(content=self.chunks[self.current_page])

        def check(reaction, adder):
            return adder.id == ctx.author.id and reaction.message.id == self.message.id

        while True:
            try:
                reaction, adder = await ctx.bot.wait_for('reaction_add', check=check, timeout=20)
                try:
                    # fetch the action
                    value = emoji.index(reaction.emoji)
                    if value == 0:
                        self.prev_page()
                        await invalidate()
                    elif value == 1:
                        self.next_page()
                        await invalidate()
                    elif value == 2:
                        break

                    # remove the emoji
                    await self.message.remove_reaction(reaction.emoji, adder)
                except ValueError:
                    pass
                except discord.Forbidden:
                    pass
            except asyncio.TimeoutError:
                await self.message.delete()
                await ctx.send('Timed out!', delete_after=4.5)
                return
        await self.message.delete()


class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.strict = False
        self.convert_charrefs = True
        self.fed = []

    def handle_data(self, d):
        self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def format_dict(d: Dict[Any, Any], *, style='equals') -> str:
    """ Formats a ``dict`` to look pretty. """
    code_block = '```{}\n'.format('ini' if style == 'ini' else '')
    padding = len(max(d.keys(), key=len))

    for name, value in d.items():
        if style == 'equals':
            code_block += '{name: <{width}} = {value}\n'.format(name=name, width=padding, value=value)
        elif style == 'ini':
            code_block += '{name: <{width}} {value}\n'.format(name=f'[{name}]', width=padding + 2, value=value)

    code_block += '```'
    return code_block


def make_profile_embed(member: discord.Member):
    """ Creates an embed with the author containing the name and icon of a `discord.Member`. """
    embed = discord.Embed()
    embed.set_author(name=str(member), icon_url=member.avatar_url)
    return embed


def strip_tags(text: str):
    """ Strips HTML tags from text. """
    s = MLStripper()
    s.feed(text)
    return s.get_data()


def urlescape(text: str):
    """ "Quotes" text using urllib. `" "` -> `"%20"` """
    return urllib.parse.quote_plus(text)


def american_datetime(dt):
    """
    Formats a `datetime.datetime` to the American style: ::

        MONTH/DAY/YEAR HOUR/MINUTE/SECOND [AM/PM]
    """
    return dt.strftime('%m/%d/%Y %I:%M:%S %p')


def format_list(lst):
    return '\n'.join('`{:03d}`: {}'.format(index + 1, value)
                     for index, value in enumerate(lst))


def now():
    """ Returns an American-formatted datetime with a "UTC" suffix. """
    return american_datetime(datetime.datetime.utcnow()) + ' UTC'


def ago(dt):
    """ Returns a `pretty_timedelta` since the provided `datetime.timedelta`. """
    return timeago.format(dt, datetime.datetime.utcnow())


def truncate(text: str, desired_length: int):
    """
    Truncates text, and adds `...` at the end if it surpasses the desired length.

    .. NOTE::

        The returned `str` is guaranteed to be `desired_length` long.
    """
    if len(text) > desired_length:
        return text[:desired_length - 3] + '...'
    return text


def commas(number: 'Union[int, float]'):
    """ Adds American-style commas to an number. """
    return '{:,d}'.format(number)


class EnumConverter(commands.Converter):
    async def convert(self, ctx, argument):
        enum_type = getattr(self.enum, argument.upper(), None)
        if not enum_type:
            raise commands.BadArgument(self.bad_argument_text)
        return enum_type

# from rowboat https://github.com/b1naryth1ef/rowboat/blob/master/rowboat/util/zalgo.py
zalgo_glyphs = [
    '\u030d', '\u030e', '\u0304', '\u0305', '\u033f', '\u0311', '\u0306', '\u0310', '\u0352', '\u0357', '\u0351',
    '\u0307', '\u0308', '\u030a', '\u0342', '\u0343', '\u0344', '\u034a', '\u034b', '\u034c', '\u0303', '\u0302',
    '\u030c', '\u0350', '\u0300', '\u030b', '\u030f', '\u0312', '\u0313', '\u0314', '\u033d', '\u0309', '\u0363',
    '\u0364', '\u0365', '\u0366', '\u0367', '\u0368', '\u0369', '\u036a', '\u036b', '\u036c', '\u036d', '\u036e',
    '\u036f', '\u033e', '\u035b', '\u0346', '\u031a', '\u0315', '\u031b', '\u0340', '\u0341', '\u0358', '\u0321',
    '\u0322', '\u0327', '\u0328', '\u0334', '\u0335', '\u0336', '\u034f', '\u035c', '\u035d', '\u035e', '\u035f',
    '\u0360', '\u0362', '\u0338', '\u0337', '\u0361', '\u0489', '\u0316', '\u0317', '\u0318', '\u0319', '\u031c',
    '\u031d', '\u031e', '\u031f', '\u0320', '\u0324', '\u0325', '\u0326', '\u0329', '\u032a', '\u032b', '\u032c',
    '\u032d', '\u032e', '\u032f', '\u0330', '\u0331', '\u0332', '\u0333', '\u0339', '\u033a', '\u033b', '\u033c',
    '\u0345', '\u0347', '\u0348', '\u0349', '\u034d', '\u034e', '\u0353', '\u0354', '\u0355', '\u0356', '\u0359',
    '\u035a', '\u0323'
]
