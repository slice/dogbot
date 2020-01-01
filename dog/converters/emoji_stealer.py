import functools
import re
from typing import List, Set

import discord
import lifesaver
from discord import PartialEmoji
from discord.ext import commands

EMOJI_REGEX = re.compile(
    r"""
    # A Discord emoji, as represented in raw message content.

    <
        # Animation flag
        (?P<animated>a?)
        :

        # Emoji name
        (?P<name>\w+)
        :

        # Emoji ID
        (?P<id>\d+)
    >
""",
    re.VERBOSE,
)

EMOJI_URL_REGEX = re.compile(
    r"""
    # A Discord emoji URL.

    # The standard part of the URL
    ^https?://
    cdn\.discordapp\.com
    /emojis/

    # Emoji ID
    (?P<id>\d+)

    # File extension
    \.
    (?P<extension>png|gif)
""",
    re.VERBOSE,
)


class EmojiStealer(commands.Converter):
    """A versatile converter intended to convert into :class:`discord.PartialEmoji`.

    The argument can be an emoji (as used normally), an emoji ID, or an emoji
    URL. If the string "recent" is passed, then the converter will scan for
    recently used custom emoji in the current channel to resolve. If there are
    multiple, the user is interactively prompted for selection.
    """

    @staticmethod
    async def recent(ctx: lifesaver.Context) -> PartialEmoji:
        def formatter(emoji: PartialEmoji, index: int) -> str:
            return f"{index + 1}. `:{emoji.name}:`"

        def reducer(
            emoji: Set[PartialEmoji], msg: discord.Message
        ) -> Set[PartialEmoji]:
            match = EMOJI_REGEX.search(msg.content)

            if not match:
                return emoji

            emoji_id = int(match.group("id"))

            # If the emoji used is already in the guild, ignore.
            if discord.utils.get(ctx.guild.emojis, id=emoji_id):
                return emoji

            new_emoji = PartialEmoji(
                animated=bool(match.group("animated")),
                name=match.group("name"),
                id=emoji_id,
            )

            return emoji | set([new_emoji])

        messages = await ctx.history(limit=50).flatten()
        results: List[PartialEmoji] = list(functools.reduce(reducer, messages, set()))

        if not results:
            raise commands.BadArgument("No stealable custom emoji were found.")

        if len(results) > 1:
            result = await ctx.pick_from_list(results, formatter=formatter)
        else:
            result = list(results)[0]

        return result

    async def convert(self, ctx: lifesaver.Context, argument: str) -> PartialEmoji:
        # Convert an emoji ID.
        if argument.isdigit():
            return PartialEmoji(id=int(argument), name=None, animated=False)

        # Convert from an emoji URL.
        url_match = EMOJI_URL_REGEX.search(argument)
        if url_match:
            return PartialEmoji(
                id=int(url_match.group("id")),
                name=None,
                animated=url_match.group("extension") == "png",
            )

        # Convert an actual emoji.
        try:
            return await commands.PartialEmojiConverter().convert(ctx, argument)
        except commands.BadArgument:
            pass

        # Scan recently used custom emoji.
        if argument == "recent":
            return await self.recent(ctx)

        raise commands.BadArgument(
            "Invalid emoji. You can use an actual emoji or an emoji ID or URL. "
            "You can also specify `recent` to select a recently used emoji."
        )
