import datetime
import time
from random import choice
from typing import Any

import discord
import lifesaver
from discord.ext import commands
from lifesaver.bot.storage import Storage
from lifesaver.utils import (
    ListPaginator,
    clean_mentions,
    human_delta,
    pluralize,
    truncate,
)

from .converters import Messages, QuoteName
from .utils import stringify_message

__all__ = ["Quoting"]


def embed_quote(*, name, quote) -> discord.Embed:
    embed = discord.Embed(title=name, description=quote["content"])
    embed.url = quote["jump_url"]

    creator = quote["created_by"]["tag"]
    channel = quote["created_in"]["name"]

    ago = human_delta(
        datetime.datetime.fromtimestamp(quote["created"], tz=datetime.timezone.utc)
    )
    embed.set_footer(text=f"Created by {creator} in #{channel} {ago} ago")

    return embed


class Quoting(lifesaver.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(bot, *args, **kwargs)
        self.storage = Storage[dict[str, dict[str, Any]]]("quotes.json")

    def quotes(self, guild: discord.Guild):
        return self.storage.get(str(guild.id), {})

    @lifesaver.command(aliases=["rq"])
    @commands.guild_only()
    async def random_quote(self, ctx):
        """Shows a random quote."""
        quotes = self.quotes(ctx.guild)

        if not quotes:
            await ctx.send(
                "There are no quotes in this server. Create some with "
                f"`{ctx.prefix}quote new`. For more information, see `{ctx.prefix}"
                "help quote`."
            )
            return

        (name, quote) = choice(list(quotes.items()))
        embed = embed_quote(name=name, quote=quote)

        name = clean_mentions(ctx.channel, name)

        await ctx.send(name, embed=embed)

    @lifesaver.group(aliases=["q"], invoke_without_command=True)
    @commands.guild_only()
    async def quote(self, ctx, *, name: QuoteName(must_exist=True)):
        """Views a quote.

        Quotes are essentially pictures of multiple messages and stores them
        in my database.

        You can specify multiple message IDs to store:

            d?quote new "my quote" 467753625024987136 467753572633673773 ...

        Alternatively, you can specify a message ID then a number of messages
        to store after that, like:

            d?quote new "my quote" 467753625024987136+5

        That would store message 467753625024987136 and the 5 messages after
        that. You can also combine them if you would like to simultaneously
        specify individual messages and groups of messages. Alternatively,
        you can select the last 5 messages like so:

            d?quote new "my quote" :-5

        The :n or +n (called the "range") will grab up to 50 messages both ways.

        Your quote's content has a length limit of 2048, Discord's embed
        description limit. You will be prompted to confirm if your created
        quote goes over this limit.

        To read a quote, just specify its name, and no message IDs:

            d?quote my quote

        The number of embeds in any message (if any) and any attachment URLs
        are preserved. Additionally, quotes contain a jump URL to jump to the
        first message in the quote directly with your client.

        If you want to create a quote without having the quote echo in chat,
        prefix the quote name with "!":

            d?quote !quote 467753625024987136+3

        The bot will DM you the quote instead of echoing it in chat, and no
        feedback will be provided in the channel. Keep in mind that the name of
        the created quote will not have the "!".

        Quotes contain the following data:
            - All message content, all numbers of embeds, all attachment URLs
            - Channel ID and name, first message ID, guild ID
            - Creation timestamp
            - Quote creator ID and username#discriminator
        """
        quotes = self.quotes(ctx.guild)
        quote = quotes.get(name)

        embed = embed_quote(name=name, quote=quote)
        await ctx.send(embed=embed)

    @quote.command(aliases=["new"])
    @commands.guild_only()
    async def create(
        self, ctx, name: QuoteName(must_not_exist=True), *messages: Messages
    ):
        """Creates a quote.

        See `d?help quote` for more information.
        """
        quotes = self.quotes(ctx.guild)

        silent = name.startswith("!")

        if silent:
            # Remove the !
            name = name[1:]

        # the converter can return multiple messages if a range is specified
        quoted = []
        for message in messages:
            if isinstance(message, list):
                quoted += message
            else:
                quoted.append(message)

        strings = map(stringify_message, quoted)
        quote_content = "\n".join(strings)

        if len(quote_content) > 2048:
            over_limit = pluralize(character=len(quote_content) - 2048)

            if not await ctx.confirm(
                "Quote is quite large...",
                (
                    f"This quote is pretty big. ({over_limit} over limit.) "
                    "It will be truncated to 2048 characters. Continue?"
                ),
            ):
                return

        quote = quotes[name] = {
            "content": truncate(quote_content, 2048),
            "jump_url": quoted[0].jump_url,
            "created": time.time(),
            "created_by": {"id": ctx.author.id, "tag": str(ctx.author)},
            "created_in": {"id": ctx.channel.id, "name": ctx.channel.name},
            "guild": {"id": ctx.guild.id},
        }

        await self.storage.put(str(ctx.guild.id), quotes)

        embed = embed_quote(name=name, quote=quote)
        await (ctx.author if silent else ctx).send(
            f'Created quote "{name}".', embed=embed
        )

    @quote.command()
    @commands.guild_only()
    async def list(self, ctx):
        """Lists quotes on this server."""
        quotes = self.quotes(ctx.guild)

        if not quotes:
            await ctx.send("No quotes exist for this server.")
            return

        tag_names = [clean_mentions(ctx.channel, name) for name in quotes.keys()]

        paginator = ListPaginator(
            tag_names,
            ctx.author,
            ctx.channel,
            title="All quotes",
            per_page=20,
            bot=ctx.bot,
        )
        await paginator.create()

    @quote.command()
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def rename(
        self,
        ctx,
        existing: QuoteName(must_exist=True),
        new: QuoteName(must_not_exist=True),
    ):
        """Renames a quote."""
        quotes = self.quotes(ctx.guild)

        quotes[new] = quotes[existing]
        del quotes[existing]

        await self.storage.put(str(ctx.guild.id), quotes)
        await ctx.send(f'Quote "{existing}" was renamed to "{new}".')

    @quote.command()
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def delete(self, ctx, *, quote: QuoteName(must_exist=True)):
        """Deletes a quote."""
        quotes = self.quotes(ctx.guild)

        del quotes[quote]

        await self.storage.put(str(ctx.guild.id), quotes)
        await ctx.ok()
