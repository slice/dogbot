import datetime
import re
import typing
from collections import namedtuple
from typing import Tuple, Union, Optional

import discord
import parsedatetime
from discord import Message
from discord.ext import commands
from discord.ext.commands import MemberConverter, UserConverter, Converter, BadArgument

from dog.core.context import DogbotContext
from dog.core.utils import history_reducer


class BareCustomEmoji(namedtuple('BareCustomEmoji', 'id name')):
    def __str__(self):
        return f'`:{self.name}:` (`{self.id}`)'


EMOJI_REGEX = re.compile(r'<:([a-z0-9A-Z_-]+):(\d+)>')


class FormattedCustomEmoji(commands.Converter):
    async def convert(self, ctx, argument):
        match = EMOJI_REGEX.match(argument)
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


class BannedUser(commands.Converter):
    """A converter that attempts to a resolve a banned user by ID, username, or username#discriminator."""
    async def convert(self, ctx: commands.Context, argument):
        def finder(entry):
            try:
                user_id = int(argument)
            except ValueError:
                user_id = None

            return (str(entry.user) == argument or  # username#discriminator
                    entry.user.name == argument or  # username
                    entry.user.id == user_id)       # id

        try:
            entry = discord.utils.find(finder, await ctx.guild.bans())

            if entry is None:
                raise commands.BadArgument(
                    'Banned user not found. You can specify by ID, username, or username#discriminator.'
                )

            return entry.user
        except discord.Forbidden:
            raise commands.BadArgument("I can't view the bans for this server.")


class RawUser(commands.Converter):
    """A MemberConverter that falls back to UserConverter, then get_user_info."""
    async def convert(self, ctx, argument):
        for converter in (MemberConverter, UserConverter):
            try:
                return await converter().convert(ctx, argument)
            except commands.BadArgument:
                pass

        try:
            return await ctx.bot.get_user_info(argument)
        except discord.HTTPException:
            raise commands.BadArgument("That user wasn't found.")


class RawMember(commands.Converter):
    """A converter that attempts to convert to user, then falls back to a discord.Object with an ID."""
    async def convert(self, ctx, argument):
        try:
            return await MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            try:
                return discord.Object(id=int(argument))
            except ValueError:
                raise commands.BadArgument('Invalid member ID. I also couldn\'t find the user by username.')


SAFE_IMAGE_HOSTS = ('https://i.imgur.com', 'https://cdn.discordapp.com', 'https://images.discordapp.net',
                    'https://i.redd.it', 'https://media.discordapp.net')


async def _get_recent_image(channel: discord.TextChannel) -> typing.Optional[discord.Message]:
    async for msg in channel.history(limit=100):
        # Scan any attached images.
        for attachment in msg.attachments:
            if attachment.height:
                return attachment.proxy_url

        # Scan any embeds in the message.
        for embed in msg.embeds:
            if embed.image is discord.Embed.Empty:
                continue
            return embed.image.proxy_url


class Image(commands.Converter):
    """
    Resolves an image, returns the URL to the image.

    Could be passed "attached" to use an attached image.
    Could be passed "recent" to scan the channel for recent images.
    Could be passed a member to use their avatar.
    Could be passed an image URL to use it, however, only whitelisted image hosts will work.
    """
    async def convert(self, ctx, argument):
        # Scan attached images.
        if argument == 'attached':
            for attachment in ctx.message.attachments:
                if attachment.height:
                    return attachment.proxy_url

        # Scan channel for any recent images.
        if argument == 'recent':
            result = await _get_recent_image(ctx.channel)
            if not result:
                raise commands.BadArgument('No recent image was found in this channel.')
            return result

        try:
            # Resolve avatar.
            user = await UserConverter().convert(ctx, argument)
            return user.avatar_url_as(format='png')
        except commands.BadArgument:
            pass

        # ok image
        if any(argument.startswith(safe_url) for safe_url in SAFE_IMAGE_HOSTS):
            return argument

        error = ("Invalid image URL or user. To use a recent image from this channel, specify `recent`. You can also "
                 "attach any image and specify `attached` to use that image.")
        raise commands.BadArgument(error)


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
                raise commands.BadArgument(f'A guild with an ID of `{guild_id}` was not found.')
            return guild
        except ValueError:
            raise commands.BadArgument('Invalid guild ID.')


class DeleteDays(commands.Converter):
    async def convert(self, ctx, arg):
        try:
            days = int(arg)
            if days < 0 or days > 7:
                raise commands.BadArgument('Invalid `delete_days`: cannot be lower than 0, or higher than 7.')
        except ValueError:
            raise commands.BadArgument('Invalid `delete_days`: not a valid number.')
        return days


class EmojiStealer(Converter):
    async def convert(self, ctx: DogbotContext, argument: str) -> Tuple[int, Union[None, str]]:
        # Emoji ID?
        if argument.isdigit():
            return BareCustomEmoji(id=int(argument), name=None)

        # Emoji?
        match = EMOJI_REGEX.match(argument)
        if match:
            return BareCustomEmoji(id=match.group(2), name=match.group(1))

        def _reducer(msg: Message) -> Optional[BareCustomEmoji]:
            # search the message for custom emoji
            match = EMOJI_REGEX.search(msg.content)

            if not match:
                return None

            emoji_id = int(match.group(2))

            # check if the emoji is in the guild itself
            if emoji_id in {emoji.id for emoji in ctx.guild.emojis}:
                return None

            return BareCustomEmoji(id=int(match.group(2)), name=match.group(1))

        # Recently used custom emoji?
        if argument == 'recent':
            custom_emoji = await history_reducer(ctx, _reducer, ignore_duplicates=True, limit=50)

            if not custom_emoji:
                raise BadArgument("No recently used custom emoji (that aren't already in this server) were found.")

            if len(custom_emoji) > 1:
                # More than one custom emoji, pick from list.
                to_steal = await ctx.pick_from_list(custom_emoji)
            else:
                # Just one emoji, unwrap the list.
                to_steal = custom_emoji[0]

            return to_steal

        raise BadArgument('No emoji provided. Provide an emoji ID, emoji, or "recent" to scan the channel for '
                          'recently used custom emoji.')
