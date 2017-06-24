import asyncio
import datetime
import urllib.parse
from html.parser import HTMLParser
from typing import Any, Dict

import discord
import timeago


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


def format_dict(d: Dict[Any, Any]) -> str:
    """ Formats a ``dict`` to look pretty. """
    code_block = '```\n'
    padding = len(max(d.keys(), key=len))

    for name, value in d.items():
        code_block += '{name: <{width}} = {value}\n'.format(name=name, width=padding, value=value)

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


def commas(number: int):
    """ Adds American-style commas to an `int`. """
    return '{:,d}'.format(number)
