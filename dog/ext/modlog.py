""" Contains the moderator log. """
import asyncio
import datetime
import logging

import discord
from discord.ext import commands

from dog import Cog
from dog.core import utils
from dog.core.utils import describe

logger = logging.getLogger(__name__)


async def is_publicly_visible(bot, channel: discord.TextChannel) -> bool:
    """
    Returns whether a channel is publicly visible with the default role.

    This will always return True if the guild has been configured to log all message
    events.
    """
    if await bot.config_is_set(channel.guild, 'log_all_message_events'):
        return True

    everyone_overwrite = discord.utils.find(lambda t: t[0].name == '@everyone', channel.overwrites)
    return everyone_overwrite is None or everyone_overwrite[1].read_messages is not False


class Modlog(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        #: A list of user IDs to not process due to being banned.
        self.ban_debounces = []

        #: A list of message IDs to not process due to them being bulk deleted.
        self.bulk_deletes = []

        #: A list of message IDs to not process.
        self.censored_messages = []

    def modlog_msg(self, msg):
        now = datetime.datetime.utcnow()
        return '`[{0.hour:02d}:{0.minute:02d}]` {1}'.format(now, msg)

    async def log(self, guild, text):
        return await self.bot.send_modlog(guild, self.modlog_msg(text))

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):

        async def send(m):
            await self.log((before.channel.guild if before.channel else after.channel.guild), m)

        emoji = '\N{PUBLIC ADDRESS LOUDSPEAKER}'

        if before.channel is not None and after.channel is None:
            # left
            await send(f'{emoji} {describe(member)} left {describe(before.channel)}')
        elif before.channel is None and after.channel is not None:
            # joined
            await send(f'{emoji} {describe(member)} joined {describe(after.channel)}')
        elif before.channel != after.channel:
            # moved
            await send(f'{emoji} {describe(member)} moved from {describe(before.channel)} to {describe(after.channel)}')

    async def on_message_censor(self, filter, msg):
        # we don't want to log message deletes for this message
        self.censored_messages.append(msg.id)

        title = filter.mod_log_description
        content = f': {msg.content}' if getattr(filter, 'show_content', True) else ''
        await self.log(msg.guild, f'\u002a\u20e3 Message by {describe(msg.author)} censored: {title}{content}')

    async def on_member_autorole(self, member: discord.Member, roles_added):
        # make embed
        msg = (f'\N{BOOKMARK} Automatically assigned roles to {describe(member)}' if isinstance(roles_added, list) else
               f'\N{CLOSED BOOK} Failed to automatically assign roles for {describe(member)}')

        if roles_added:
            # if roles were added, add them to the message
            msg += ', added roles: ' + ', '.join(describe(role) for role in roles_added)

        await self.log(member.guild, msg)

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        # if message author was a bot, or the embeds were added by discord, bail
        if before.author.bot or before.content == after.content:
            return

        if (not await is_publicly_visible(self.bot, before.channel) or
                await self.bot.config_is_set(before.guild, 'modlog_notrack_edits')):
            return

        m_before = utils.prevent_codeblock_breakout(utils.truncate(before.content, 900))
        m_after = utils.prevent_codeblock_breakout(utils.truncate(after.content, 900))
        fmt = (f'\N{MEMO} Message by {describe(before.author)} in {describe(before.channel, mention=True)} edited: '
               f'```\n{m_before}\n``` to ```\n{m_after}\n```')
        await self.log(before.guild, fmt)

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            await self.log(before.guild,
                           f'\N{NAME BADGE} Nick for {describe(before)} updated: `{before.nick}` to `{after.nick}`')
        elif before.name != after.name:
            await self.log(before.guild,
                           f'\N{NAME BADGE} Username for {describe(before)} updated: `{before.name}` to `{after.name}`')
        elif before.roles != after.roles:
            differences = []
            differences += [f'{describe(role)} was removed' for role in before.roles if role not in after.roles]
            differences += [f'{describe(role)} was added' for role in after.roles if role not in before.roles]
            await self.log(before.guild, f'\N{KEY} Roles for {describe(before)} were updated: {", ".join(differences)}')

    async def on_raw_bulk_message_delete(self, message_ids, channel_id):
        # add to list of bulk deletes so we don't process message delete events for these messages
        self.bulk_deletes += message_ids

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        await self.log(channel.guild, f'\U0001f6ae {len(message_ids)} message(s) deleted in {channel.mention}')

    async def on_message_delete(self, msg: discord.Message):
        if not isinstance(msg.channel, discord.TextChannel):
            return

        # race conditions, yay!
        # we do this because this message could possibly maybe be censored or bulk deleted
        await asyncio.sleep(0.5)

        # do not process bulk message deletes, or message censors (the censor cog does that already)
        # TODO: do this but cleanly, maybe paste website?
        if msg.id in self.bulk_deletes or msg.id in self.censored_messages:
            return

        # if this channel isn't publicly visible or deletes shouldn't be tracked, bail
        if (not await is_publicly_visible(self.bot, msg.channel) or
                await self.bot.config_is_set(msg.guild, 'modlog_notrack_deletes')):
            return

        # if the author was a bot and we aren't configured to allow bots, return
        if msg.author.bot and not await self.bot.config_is_set(msg.guild, 'modlog_filter_allow_bot'):
            return

        content = utils.prevent_codeblock_breakout(utils.truncate(msg.content, 1800))
        fmt = (f'\U0001f6ae Message by {describe(msg.author)} deleted in {msg.channel.mention}: ```\n{content}\n``` '
               f'({len(msg.attachments)} attachment(s))')
        await self.log(msg.guild, fmt)

    async def on_member_join(self, member: discord.Member):
        new = '\N{SQUARED NEW} ' if (datetime.datetime.utcnow() - member.created_at).total_seconds() <= 604800 else ''
        await self.log(member.guild, f'\N{INBOX TRAY} {new}{describe(member, created=True)}')

    def format_member_departure(self, member, *, verb='left', emoji='\N{OUTBOX TRAY}'):
        # if it's a user, return bare info
        if isinstance(member, discord.User):
            return f'{emoji} {describe(member, before=verb, created=True)}'

        bounce = '\U0001f3c0 ' if (datetime.datetime.utcnow() - member.joined_at).total_seconds() <= 1500 else ''
        return f'{emoji} {bounce}{describe(member, before=verb, created=True, joined=True)}'

    async def get_responsible(self, guild, target, action):
        """
        Returns a audit log entry for some recent action performed on someone.
        """
        try:
            # get the audit logs for the action specified
            entries = await guild.audit_logs(limit=1, action=getattr(discord.AuditLogAction, action)).flatten()

            # only check for entries performed on target, and happened in the last 2 seconds
            def check(entry):
                return entry.target == target and (datetime.datetime.utcnow() - entry.created_at).total_seconds() <= 2

            return discord.utils.find(check, entries)
        except discord.Forbidden:
            pass

    def format_reason(self, entry):
        return f'with reason `{entry.reason}`' if entry.reason else 'with no attached reason'

    async def on_member_unban(self, guild, user):
        base_msg = f'\N{HAMMER} {describe(user)} was unbanned'
        msg = await self.log(guild, base_msg + '.')

        if not msg:
            return

        entry = await self.get_responsible(guild, user, 'unban')

        if not entry:
            return

        await msg.edit(content=(self.modlog_msg(f'{base_msg} by {describe(entry.user)} {self.format_reason(entry)}.')))

    async def on_member_ban(self, guild, user):
        # don't make on_member_remove process this user's departure
        self.ban_debounces.append(user.id)

        msg = await self.log(guild, self.format_member_departure(user, verb='banned', emoji='\N{HAMMER}'))

        if not msg:
            return

        entry = await self.get_responsible(guild, user, 'ban')

        if not entry:
            return

        fmt = self.format_member_departure(user, verb=f'banned by {describe(entry.user)} {self.format_reason(entry)}',
                                           emoji='\N{HAMMER}')
        await msg.edit(content=self.modlog_msg(fmt))

    async def on_member_remove(self, member):
        # this is called also when someone gets banned, but we don't want duplicate messages, so bail if
        # this person got banned as we already send a message
        if member.id in self.ban_debounces:
            self.ban_debounces.remove(member.id)
            return

        msg = self.format_member_departure(member)
        ml_msg = await self.log(member.guild, msg)

        if not ml_msg:
            return

        entry = await self.get_responsible(member.guild, member, 'kick')

        if not entry:
            return

        fmt = self.format_member_departure(member, verb=f'kicked by {describe(entry.user)} {self.format_reason(entry)}',
                                           emoji='\N{WOMANS BOOTS}')
        await ml_msg.edit(content=self.modlog_msg(fmt))

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
