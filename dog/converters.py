import re
from typing import Tuple, Union, Optional

import discord
from discord import PartialEmoji
from discord.ext import commands
from discord.ext.commands import Converter, MemberConverter
from lifesaver.bot import Context

# https://github.com/Rapptz/discord.py/commit/04d9dd9c0dc82b4d870c6269ecc3a9e46cd7292e
from lifesaver.utils import history_reducer

EMOJI_REGEX = re.compile(r'<(a?):([a-zA-Z0-9\_]+):([0-9]+)>$')
EMOJI_URL_REGEX = re.compile(r'https://cdn\.discordapp\.com/emojis/([0-9]+).(png|gif)')


class EmojiStealer(Converter):
    async def convert(self, ctx: Context, argument: str) -> Tuple[int, Union[None, str]]:
        # emoji id was provided
        if argument.isdigit():
            return PartialEmoji(id=int(argument), name=None, animated=False)

        # convert from a url grabbed from "copy link" context menu item when right-clicking on ane moji
        url_match = EMOJI_URL_REGEX.match(argument)
        if url_match:
            return PartialEmoji(
                id=int(url_match.group(1)),
                name=None,
                animated=url_match.group(2) == 'gif'
            )

        # convert an actual emoji
        try:
            await commands.PartialEmojiConverter().convert(ctx, argument)
        except commands.BadArgument:
            pass

        def _reducer(msg: discord.Message) -> Optional[PartialEmoji]:
            # search the message for custom emoji
            match = EMOJI_REGEX.search(msg.content)

            if not match:
                return None

            emoji_id = int(match.group(3))

            # check if the emoji is in the guild itself
            if emoji_id in {emoji.id for emoji in ctx.guild.emojis}:
                return None

            return PartialEmoji(
                animated=bool(match.group(1)),
                name=match.group(2),
                id=emoji_id
            )

        # recently used custom emoji?
        if argument == 'recent':
            custom_emoji = await history_reducer(
                ctx, _reducer, ignore_duplicates=True, limit=50
            )

            if not custom_emoji:
                raise commands.BadArgument(
                    "No recently used custom emoji (that aren't already in this server) were found."
                )

            if len(custom_emoji) > 1:
                # more than one custom emoji, pick from list
                to_steal = await ctx.pick_from_list(custom_emoji)
            else:
                # just one emoji, unwrap the list
                to_steal = custom_emoji[0]

            return to_steal

        raise commands.BadArgument(
            'No emoji provided. Provide an emoji ID, emoji, or "recent" to scan the channel for '
            'recently used custom emoji.'
        )


class HardMember(Converter):
    """A MemberConverter that falls back to a ``get_user_info`` call."""

    async def convert(self, ctx: Context, argument: str):
        try:
            member = await MemberConverter().convert(ctx, argument)
            return member
        except commands.BadArgument:
            pass

        if not argument.isdigit():
            raise commands.BadArgument('Member not found. Try specifying an ID.')

        argument_as_id = int(argument)

        try:
            user = await ctx.bot.get_user_info(argument_as_id)
            return user
        except discord.NotFound:
            raise commands.BadArgument('User not found.')
        except discord.HTTPException as exception:
            raise commands.BadArgument(f'Failed to get user information: `{exception}`')


class SoftMember(Converter):
    """A MemberConverter that falls back to a :class:`discord.Object` when an ID is provided and they weren't found."""

    async def convert(self, ctx: Context, argument: str):
        try:
            member = await MemberConverter().convert(ctx, argument)
            return member
        except commands.BadArgument:
            if argument.isdigit():
                return discord.Object(id=int(argument))
            else:
                raise commands.BadArgument('Member not found')
