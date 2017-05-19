import datetime
import urllib.parse
from html.parser import HTMLParser
from typing import Any, Dict

import discord


class MLStripper(HTMLParser):
    def __init__(self):
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
        code_block += '{name: <{width}} {value}\n'.format(name=name, width=padding, value=value)

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
    return pretty_timedelta(datetime.datetime.utcnow() - dt)


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


def pretty_timedelta(delta):
    """ Returns a `datetime.timedelta` as a string, but pretty. """
    big_parts = []

    if delta.days >= 365:
        years = round(delta.days / 365, 2)
        plural = 's' if years == 0 or years > 1 else ''
        big_parts.append(f'{years} year{plural}')

    if delta.days >= 7 and delta.days < 365:
        weeks = round(delta.days / 7, 2)
        plural = 's' if weeks == 0 or weeks > 1 else ''
        big_parts.append(f'{weeks} week{plural}')

    m, s = divmod(delta.seconds, 60)
    h, m = divmod(m, 60)
    big = ', '.join(big_parts)
    hms = '{}{}{}'.format(f'{h}h' if h else '', f'{m}m' if m else '', f'{s}s' if s else '')
    return '{}, {} ago'.format(big, hms) if big else (f'{hms} ago' if hms else 'just now')
