""" Contains the moderator log. """
import asyncio
import datetime

import discord
import logging
from discord.ext import commands

from dog import Cog
from dog.core import checks, utils

logger = logging.getLogger(__name__)


async def is_publicly_visible(bot, channel: discord.TextChannel) -> bool:
    """ Returns whether a channel is publicly visible with the default role. """
    if await bot.config_is_set(channel.guild, 'log_all_message_events'):
        logger.debug('All mesasge events are being logged for this guild, returning True.')
        return True

    everyone_overwrite = discord.utils.find(lambda t: t[0].name == '@everyone',
                                            channel.overwrites)
    return everyone_overwrite is None or everyone_overwrite[1].read_messages is not False


class Modlog(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.ban_debounces = []
        self.bulk_deletes = []
        self.do_not_log_deletes = []

    def modlog_msg(self, msg):
        now = datetime.datetime.utcnow()
        return '`[{0.hour:02d}:{0.minute:02d}]` {1}'.format(now, msg)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):

        async def send(m):
            await self.bot.send_modlog((before.channel.guild if before.channel else after.channel.guild), m)
        voice = '\N{PUBLIC ADDRESS LOUDSPEAKER}'

        if before.channel is not None and after.channel is None:
            # left
            await send(self.modlog_msg(f'{voice} {member} left {before.channel}'))
        elif before.channel is None and after.channel is not None:
            # joined
            await send(self.modlog_msg(f'{voice} {member} joined {after.channel}'))
        elif before.channel != after.channel:
            # moved
            await send(self.modlog_msg(f'{voice} {member} moved from {before.channel} to {after.channel}'))

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content:
            return

        if (not await is_publicly_visible(self.bot, before.channel) or
                await self.bot.config_is_set(before.guild, 'modlog_notrack_edits')):
            return

        m_before = utils.prevent_codeblock_breakout(utils.truncate(before.content, 850))
        m_after = utils.prevent_codeblock_breakout(utils.truncate(after.content, 850))
        fmt = f'\N{MEMO} Message by {before.author} edited: ```{m_before}``` to ```{m_after}```'
        await self.bot.send_modlog(before.guild, self.modlog_msg(fmt))

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            msg = self.modlog_msg(f'\N{NAME BADGE} Nick for {before} updated: `{before.nick}` to `{after.nick}`')
            await self.bot.send_modlog(before.guild, msg)
        elif before.name != after.name:
            msg = self.modlog_msg(f'\N{NAME BADGE} Username for {before} updated: `{before.name}` to `{after.name}`')
            await self.bot.send_modlog(before.guild, msg)

    async def on_raw_bulk_message_delete(self, message_ids, channel_id):
        self.bulk_deletes += message_ids

        channel = discord.utils.get(self.bot.get_all_channels(), id=channel_id)
        if not channel:
            return
        fmt = self.modlog_msg(f'\U0001f6ae {len(message_ids)} message(s) deleted in {channel.mention}')
        await self.bot.send_modlog(channel.guild, fmt)

    async def on_message_delete(self, msg: discord.Message):
        if not isinstance(msg.channel, discord.TextChannel):
            return

        # race conditions, yay!
        # we do this because this message could possibly maybe be censored
        await asyncio.sleep(0.5)

        # do not process bulk message deletes
        # TODO: do this but cleanly, maybe paste website?
        if msg.id in self.bulk_deletes or msg.id in self.do_not_log_deletes:
            return

        if (not await is_publicly_visible(self.bot, msg.channel) or
                await self.bot.config_is_set(msg.guild, 'modlog_notrack_deletes')):
            return

        if msg.author.bot:
            if not await self.bot.config_is_set(msg.guild, 'modlog_filter_allow_bot'):
                return

        content = utils.prevent_codeblock_breakout(utils.truncate(msg.content, 1500))
        fmt = f'\U0001f6ae Message by {msg.author} deleted: ```{content}``` ({len(msg.attachments)} attachments)'
        await self.bot.send_modlog(msg.guild, self.modlog_msg(fmt))

    async def on_member_join(self, member: discord.Member):
        new = '\N{SQUARED NEW} ' if (datetime.datetime.utcnow() - member.created_at).total_seconds() <= 604800 else ''
        msg = self.modlog_msg(f'\N{INBOX TRAY} {new}{member} joined, created {utils.ago(member.created_at)}')
        await self.bot.send_modlog(member.guild, msg)

    def format_member_departure(self, member, *, verb='left', emoji='\N{OUTBOX TRAY}'):
        created_ago = utils.ago(member.created_at)

        # if it's a user, return bare info
        if isinstance(member, discord.User):
            return f'{emoji} {member} {verb}, created {created_ago}'

        bounce = '\U0001f3c0 ' if (datetime.datetime.utcnow() - member.joined_at).total_seconds() <= 1500 else ''
        joined_ago = utils.ago(member.joined_at)
        return self.modlog_msg(f'{emoji} {bounce}{member} {verb}, created {created_ago}, joined {joined_ago}')

    async def get_responsible(self, target, action, *, guild=None):
        gld = guild if isinstance(target, discord.User) else target.guild
        try:
            entries = await gld.audit_logs(limit=1, action=getattr(discord.AuditLogAction, action)).flatten()

            def check(entry):
                return entry.target == target and (datetime.datetime.utcnow() - entry.created_at).total_seconds() <= 2
            return discord.utils.find(check, entries)
        except discord.Forbidden:
            pass

    def format_reason(self, entry):
        return f' with reason `{entry.reason}`' if entry.reason else ' with no attached reason'

    async def on_member_unban(self, guild, user):
        base_msg = f'\N{HAMMER} {user} (`{user.id}`) was unbanned'
        ml_msg = self.modlog_msg(base_msg + '.')
        msg = await self.bot.send_modlog(guild, ml_msg)

        if not msg:
            return

        entry = await self.get_responsible(user, 'unban', guild=guild)

        if not entry:
            return

        ml_msg = self.modlog_msg(f'{base_msg} by {entry.user}{self.format_reason(entry)}.')
        await msg.edit(content=ml_msg)

    async def on_member_ban(self, guild, user):
        # don't make on_member_remove process this user's departure
        self.ban_debounces.append(user.id)

        msg = await self.bot.send_modlog(guild, self.format_member_departure(user, verb='banned', emoji='\N{HAMMER}'))

        if not msg:
            return

        entry = await self.get_responsible(user, 'ban')

        if not entry:
            return

        fmt = self.format_member_departure(user, verb=f'banned by {entry.user}{self.format_reason(entry)}',
                                           emoji='\N{HAMMER}')
        await msg.edit(content=fmt)

    async def on_member_remove(self, member):
        # this is called also when someone gets banned, but we don't want duplicate messages, so bail if
        # this person got banned as we already send a message
        if member.id in self.ban_debounces:
            self.ban_debounces.remove(member.id)
            return

        msg = self.format_member_departure(member)
        ml_msg = await self.bot.send_modlog(member.guild, msg)

        if not ml_msg:
            return

        entry = await self.get_responsible(member, 'kick')

        if not entry:
            return

        reason = self.format_reason(entry)
        fmt = self.format_member_departure(member, verb=f'kicked by {entry.user}{reason}', emoji='\N{WOMANS BOOTS}')
        await ml_msg.edit(content=fmt)

    @commands.command(hidden=True)
    async def is_public(self, ctx, channel: discord.TextChannel=None):
        """
        Checks if a channel is public.

        This command is in the Modlog cog because the modlog does not process message edit and
        delete events for private channels.

        If you have turned 'log_all_message_events' on, this will always say public.
        """
        channel = channel if channel else ctx.channel
        public = f'{channel.mention} {{}} public to @\u200beveryone.'
        await ctx.send(public.format('is' if await is_publicly_visible(self.bot, channel) else '**is not**'))


def setup(bot):
    bot.add_cog(Modlog(bot))
