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


class Flags(commands.Converter):
    async def convert(self, ctx, argument):
        result = {}
        for flag in argument.split(' '):
            if '=' in flag:
                parts = flag.split('=')
                result[parts[0][2:]] = parts[1]
            else:
                result[flag[2:]] = True
        return result


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


SAFE_IMAGE_HOSTS = ('https://i.imgur.com', 'https://cdn.discordapp.com', 'https://images.discordapp.net',
                    'https://i.redd.it')


async def _get_recent_image(channel):
    async for msg in channel.history(limit=25):
        for attachment in msg.attachments:
            # return url for image
            if attachment.height:
                return attachment.proxy_url


class Image(commands.Converter):
    async def convert(self, ctx, argument):
        # scan channel
        if argument == 'recent':
            result = await _get_recent_image(ctx.channel)
            if not result:
                raise commands.BadArgument('No recent image attachment was found in this channel.')
            return result

        try:
            # resolve avatar
            memb = await MemberConverter().convert(ctx, argument)
            return memb.avatar_url_as(format='png')
        except commands.BadArgument:
            # ok image
            if any(argument.startswith(safe_url) for safe_url in SAFE_IMAGE_HOSTS):
                return argument

            # lol wtf
            err = 'Invalid image URL or user. Valid image hosts: ' + ','.join(f'`{url}`' for url in SAFE_IMAGE_HOSTS)
            raise commands.BadArgument(err)


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
        except ValueError:
            raise commands.BadArgument('Invalid guild ID.')
