import datetime
import functools
import json
import logging
import re

import discord
from discord.ext import commands
from dog import Cog
from dog.core import checks, converters, utils

logger = logging.getLogger(__name__)


def require_logging_enabled(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # do not log dms
        if not args[1].guild:
            return

        # args[0] = self, args[1] = msg
        if not await args[0].bot.redis.exists(f'message_logging:{args[1].guild.id}:enabled'):
            return

        # don't log ourselves
        if args[1].author == args[0].bot.user:
            return
        return await func(*args, **kwargs)
    return wrapper


def format_record(r, cmd_flags):
    """
    Formats a messages row.
    """
    flags = {'E': r['edited'], 'D': r['deleted']}

    # render the flags
    flags_rendered = ''.join(fl for fl, value in flags.items() if value)
    # empty out of we are hiding flags, else pad it out
    flags_rendered = '' if 'hide-flags' in cmd_flags else f'{flags_rendered: <{len(flags)}} '

    # decide which content to show
    content = r['new_content'] or r['original_content']
    # override on show-original
    if 'show-original' in cmd_flags:
        content = r['original_content']

    # truncate
    content = utils.truncate(content, 1500)
    created_at = '' if 'hide-dates' in cmd_flags else f'{r["created_at"].strftime("%y-%m-%d %H:%M")} '
    message_id = f"{r['message_id']} " if 'show-ids' in cmd_flags else ''
    attachments = f" {r['attachments']}" if 'show-attachments' in cmd_flags else ''

    return f'{flags_rendered}{message_id}{created_at}{content}{attachments}'


def attachment_to_dict(attachment):
    return {
        'id': attachment.id,
        'size': attachment.size,
        'filename': attachment.filename,

        'height': attachment.height,
        'width': attachment.width,

        'url': attachment.url,
        'proxy_url': attachment.proxy_url
    }


def postprocess_message_content(content):
    return utils.prevent_codeblock_breakout(content.replace('\x00', ''))


class MessageLogging(Cog):
    @require_logging_enabled
    async def on_message(self, msg):
        async with self.bot.pgpool.acquire() as conn:
            insertion_sql = """
                INSERT INTO messages (message_id, guild_id, channel_id, author_id, original_content, new_content,
                    attachments, deleted, edited, deleted_at, edited_at, created_at)
                VALUES ($1, $2, $3, $4, $5, '', $6, FALSE, FALSE, NULL, NULL, $7);
            """
            encoded_attachments = json.dumps([attachment_to_dict(tch) for tch in msg.attachments])
            content = postprocess_message_content(msg.content)
            await conn.execute(insertion_sql, msg.id, msg.guild.id, msg.channel.id, msg.author.id, content,
                               encoded_attachments, msg.created_at)

    @require_logging_enabled
    async def on_message_edit(self, before, after):
        async with self.bot.pgpool.acquire() as conn:
            update_sql = """
                UPDATE messages SET edited = TRUE, new_content = $1, edited_at = $3 WHERE message_id = $2
            """
            content = postprocess_message_content(after.content)
            await conn.execute(update_sql, content, before.id, datetime.datetime.utcnow())

    @require_logging_enabled
    async def on_message_delete(self, msg):
        async with self.bot.pgpool.acquire() as conn:
            delete_sql = """
                UPDATE messages SET deleted = TRUE, deleted_at = $2 WHERE message_id = $1
            """
            await conn.execute(delete_sql, msg.id, datetime.datetime.utcnow())

    @commands.command()
    @checks.is_moderator()
    async def archive(self, ctx, user: discord.User, amount: int, *, flags: converters.Flags={}):
        """
        Fetches logged messages from a user.

        Only Dogbot Moderators can do this.

        The amount you specify is not equal to the amount of messages that will be shown to you.
        Rather, it will be the amount of messages that are fetched from the bot's database.

        Flags allow you to specify which messages you want to see, or how you want to see them.
        For more information, see https://github.com/slice/dogbot/wiki/Message-Logging.
        """
        async with ctx.acquire() as conn:
            fetch_sql = """
                SELECT * FROM messages WHERE author_id = $1 AND guild_id = $2 ORDER BY created_at DESC LIMIT $3
            """
            messages = await conn.fetch(fetch_sql, user.id, ctx.guild.id, amount)

        paginator = commands.Paginator()

        flag_processors = {
            'has-attachments': lambda value, msg: json.loads(msg['attachments']),
            'contains': lambda value, msg: value in msg,
            'edited': lambda value, msg: msg['edited'],
            'deleted': lambda value, msg: msg['deleted'],
            'channel': lambda value, msg: msg['channel_id'] == int(value),
            'mentions': lambda value, msg: re.search(f'<@!?{value}>', content) is None
        }

        # add messages
        for msg in messages:
            content = msg['new_content'] or msg['original_content']

            failed_flags = False
            for flag_name, processor in flag_processors.items():
                if flag_name in flags and not processor(flags[flag_name], msg):
                    failed_flags = True

            if not failed_flags:
                paginator.add_line(format_record(msg, flags))

        # send pages
        if not paginator.pages:
            return await ctx.send('```No results.```')
        for page in paginator.pages:
            await ctx.send(page)

    @archive.error
    async def archive_error(self, ctx, err):
        original = None if not isinstance(err, commands.CommandInvokeError) else err.original
        if isinstance(original, ValueError):
            await ctx.send('Invalid flag value provided.')
            err.should_suppress = True

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    @checks.is_supporter_check()
    async def logging(self, ctx, enable: bool):
        """
        Toggles logging in this server.

        Requires Dogbot supporter and Manage Messages.
        """
        key = f'message_logging:{ctx.guild.id}:enabled'

        if enable:
            await ctx.bot.redis.set(key, 'true')
        else:
            await ctx.bot.redis.delete(key)

        await ctx.ok()


def setup(bot):
    bot.add_cog(MessageLogging(bot))
