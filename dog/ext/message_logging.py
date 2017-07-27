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
        # args[0] = self, args[1] = msg
        if not await args[0].bot.redis.exists(f'message_logging:{args[1].guild.id}:enabled'):
            return
        if args[1].author == args[0].bot.user:
            return
        return await func(*args, **kwargs)
    return wrapper


def format_record(r, cmd_flags):
    """
    Formats a messages row.
    """
    flags = {'E': r['edited'], 'D': r['deleted']}
    flags_rendered = ''.join(fl for fl, value in flags.items() if value)
    flags_rendered = '' if 'hide-flags' in cmd_flags else f'{flags_rendered: <{len(flags)}} '

    content = r['new_content'] or r['original_content']
    if 'always-show-original' in cmd_flags:
        content = r['original_content']
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
        """ Fetches logged messages from a user. """
        async with ctx.acquire() as conn:
            fetch_sql = """
                SELECT * FROM messages WHERE author_id = $1 AND guild_id = $2 ORDER BY created_at DESC LIMIT $3
            """
            messages = await conn.fetch(fetch_sql, user.id, ctx.guild.id, amount)

        paginator = commands.Paginator()

        # add messages
        for msg in messages:
            attachments = json.loads(msg['attachments'])
            content = msg['new_content'] or msg['original_content']
            mentions = re.findall(r'<@!?(\d+)>', content)

            # obey flags
            if not attachments and 'has-attachments' in flags:
                continue
            if 'contains' in flags and flags['contains'] not in content:
                continue
            if 'edited' in flags and not msg['edited']:
                continue
            if 'deleted' in flags and not msg['deleted']:
                continue
            if 'channel' in flags and not msg['channel_id'] == int(flags['channel']):
                continue
            if 'mention-count' in flags and len(mentions) != int(flags['mention-count']):
                continue
            if 'mentions' in flags and (re.search(f'<@!?{flags["mentions"]}>', content) is None):
                continue

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
