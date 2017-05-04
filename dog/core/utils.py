import datetime
import locale
import urllib.parse

import discord


def make_profile_embed(member: discord.Member):
    """ Creates an embed with the author containing the name and icon of a `discord.Member`. """
    embed = discord.Embed()
    embed.set_author(name=str(member), icon_url=member.avatar_url)
    return embed


def urlescape(text: str):
    """ "Quotes" text using urllib. `" "` -> `"%20"` """
    return urllib.parse.quote_plus(text)


def american_datetime(dt):
    """
    Formats a `datetime.datetime` to the American style: ::

        MONTH/DAY/YEAR HOUR/MINUTE/SECOND [AM/PM]
    """
    return dt.strftime('%m/%d/%Y %I:%M:%S %p')


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
    # http://stackoverflow.com/a/1823101
    locale.setlocale(locale.LC_ALL, 'en_US.utf8')
    return locale.format('%d', number, grouping=True)


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
