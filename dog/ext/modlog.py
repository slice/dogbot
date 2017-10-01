""" Contains the moderator log. """
import asyncio
import datetime
import logging

import discord
from discord.ext import commands

from dog import Cog, DogBot
from dog.core import utils
from dog.core.utils import describe, filesize
from dog.core.context import DogbotContext
from dog.ext.censorship import CensorshipFilter

logger = logging.getLogger(__name__)


async def is_publicly_visible(bot: DogBot, channel: discord.TextChannel) -> bool:
    """
    Returns whether a text channel should be considered as "publicly visible".
    If the guild has been configured to log all message events, this will always return True.

    Args:
        bot: The bot instance.
        channel: The channel to check for.

    Returns:
        Whether the text channel is considered "publicly visible".
    """
    # guild is configured to log all message events
    if await bot.config_is_set(channel.guild, 'log_all_message_events'):
        return True

    # find the @everyone overwrite for the channel
    everyone_overwrite = discord.utils.find(lambda t: t[0].name == '@everyone', channel.overwrites)
    return everyone_overwrite is None or everyone_overwrite[1].read_messages is not False


def diff(before: list, after: list) -> (list, list):
    additions = [item for item in after if item not in before]
    removals = [item for item in before if item not in after]
    return additions, removals


def describe_differences(bot: DogBot, added: list, removed: list) -> str:
    diffs = ([f'{bot.green_tick} {describe(item)}' for item in added] +
             [f'{bot.red_tick} {describe(item)}' for item in removed])
    return ', '.join(diffs)


class DebounceProcessor:
    def __init__(self, name):
        self.name = name
        self.debounces = []
        self.log = logging.getLogger('dog.debounce.' + name.replace(' ', '_'))
        self.log.info('created')

    def add(self, **info):
        self.debounces.append(info)

    async def check(self, *_args, wait_period=1.0, **info):
        await asyncio.sleep(wait_period)

        if info in self.debounces:
            self.log.debug('caught debounce (%s)', info)
            self.debounces.remove(info)
            return True

        self.log.debug('no debounce (%s)', info)
        return False

    async def check_batch(self, item, *_args, wait_period=1.0):
        await asyncio.sleep(wait_period)

        for debounce in self.debounces.copy():
            for _key, item_list in debounce.items():
                if item in item_list:
                    self.log.debug('batch: caught debounce (%s)', item)
                    self.debounces.remove(debounce)
                    return True

        self.log.debug('batch: no debounce (%s)', item)
        return False

    def __repr__(self):
        return f'<Debounce name={self.name} debounces={self.debounces}>'


class Modlog(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self.ban_debounces = DebounceProcessor('ban')
        self.bulk_deletes = DebounceProcessor('bulk deletes')
        self.censored_messages = DebounceProcessor('censorship')
        self.autorole_debounces = DebounceProcessor('autorole')

    def modlog_msg(self, msg: str) -> str:
        """
        Adds the hour and minute before a string. This is used to ensure that moderators can tell the exact
        time that something happened.

        :param msg: The message to format.
        :return: The formatted message.
        """
        return '`[{0.hour:02d}:{0.minute:02d}]` {1}'.format(datetime.datetime.utcnow(), msg)

    async def log(self, guild: discord.Guild, text: str, *, do_not_format: bool=False) -> discord.Message:
        """
        Directly logs a message to a guild's modlog channel.

        :param guild: The guild to log to.
        :param text: The text to log.
        :param do_not_format: Disables automatic time formatting.
        :return: The sent message.
        """
        return await self.bot.send_modlog(guild, text if do_not_format else self.modlog_msg(text))

    async def on_guild_emojis_update(self, guild: discord.Guild, before: 'List[discord.Emoji]',
                                     after: 'List[discord.Emoji]'):

        added, removed = diff(before, after)
        if not added and not removed:
            # TODO: Handle renames
            return
        differences = describe_differences(self.bot, added, removed)
        await self.log(guild, f'\N{FRAME WITH PICTURE} Emoji updated: {differences}')

    async def on_command_completion(self, ctx: DogbotContext):
        if not ctx.guild:
            return

        cmd = utils.prevent_codeblock_breakout(ctx.message.content)
        await self.log(ctx.guild,
                       (f'\N{WRENCH} Command invoked by {describe(ctx.author)} in '
                        f'{describe(ctx.message.channel, mention=True)}:\n```{cmd}```'))

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState):

        async def send(m):
            await self.log((before.channel.guild if before.channel else after.channel.guild), m)

        emoji = '\N{PUBLIC ADDRESS LOUDSPEAKER}'

        if before.channel is not None and after.channel is None:
            # left
            await send(f'{emoji}\U0001f4e4 {describe(member)} left {describe(before.channel)}')
        elif before.channel is None and after.channel is not None:
            # joined
            await send(f'{emoji}\U0001f4e5 {describe(member)} joined {describe(after.channel)}')
        elif before.channel != after.channel:
            # moved
            await send(f'{emoji}\U0001f504 {describe(member)} moved from {describe(before.channel)} to '
                       f'{describe(after.channel)}')

    async def on_message_censor(self, filter: CensorshipFilter, msg: discord.Message):
        # we don't want to log message deletes for this message
        self.censored_messages.add(message_id=msg.id)

        content = f': {msg.content}' if getattr(filter, 'show_content', True) else ''
        fmt = (f'\u002a\u20e3 Message by {describe(msg.author)} in {describe(msg.channel, mention=True)} censored: '
               f'{filter.mod_log_description}{content}')
        await self.log(msg.guild, fmt)

    async def on_member_autorole(self, member: discord.Member, roles_added: 'List[discord.Role]'):
        # make embed
        msg = (f'\N{BOOKMARK} Automatically assigned roles to {describe(member)}' if isinstance(roles_added, list) else
               f'\N{CLOSED BOOK} Failed to automatically assign roles for {describe(member)}')

        if roles_added:
            # if roles were added, add them to the message
            msg += ', added roles: ' + ', '.join(describe(role) for role in roles_added)

            # make sure to add to debounce so we don't spew out "roles updated" messages
            self.autorole_debounces.add(
                role_ids=[role.id for role in roles_added],
                member_id=member.id
            )

        await self.log(member.guild, msg)

    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        # if message author was a bot, or the embeds were added by discord, bail
        if before.author.bot or before.content == after.content:
            return

        # if this channel isn't publicly visible or we aren't tracking edits, bail
        if (not await is_publicly_visible(self.bot, before.channel) or
                await self.bot.config_is_set(before.guild, 'modlog_notrack_edits')):
            return

        # truncate :blobsweats:
        m_before = utils.prevent_codeblock_breakout(utils.truncate(before.content, 900))
        m_after = utils.prevent_codeblock_breakout(utils.truncate(after.content, 900))

        # format
        fmt = (f'\N{MEMO} Message by {describe(before.author)} in {describe(before.channel, mention=True)} edited: '
               f'```\n{m_before}\n``` to ```\n{m_after}\n```')
        await self.log(before.guild, fmt)

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.nick != after.nick:
            nick_before = before.nick or '<no nickname>'
            nick_after = after.nick or '<no nickname>'
            await self.log(before.guild,
                           f'\N{NAME BADGE} Nick for {describe(before)} updated: `{nick_before}` → `{nick_after}`')
        elif before.name != after.name:
            await self.log(before.guild,
                           f'\N{NAME BADGE} Username for {describe(before)} updated: `{before.name}` → `{after.name}`')
        elif before.roles != after.roles:
            added_roles, removed_roles = diff(before.roles, after.roles)

            if await self.autorole_debounces.check(
                member_id=before.id,
                role_ids=[role.id for role in added_roles]
            ) and not removed_roles:
                return

            fmt_before = f'\N{KEY} Roles for {describe(before)} were updated'
            fmt_diffs = describe_differences(self.bot, added_roles, removed_roles)

            msg = await self.log(before.guild, f'{fmt_before}: {fmt_diffs}')

            def formatter(entry):
                return f'{fmt_before} by {describe(entry.user)}: {fmt_diffs}'
            await self.autoformat_responsible(msg, before, 'member_role_update', formatter)

    async def on_raw_bulk_message_delete(self, message_ids, channel_id: int):
        # add to list of bulk deletes so we don't process message delete events for these messages
        self.bulk_deletes.add(message_ids=message_ids)

        # resolve the channel that the message was deleted in
        channel = self.bot.get_channel(channel_id)

        # don't handle non-existent channels or dms
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        # log
        await self.log(channel.guild, f'\U0001f6ae {len(message_ids)} message(s) deleted in {channel.mention}')

    async def on_message_delete(self, msg: discord.Message):
        # don't handle message deletion elsewhere
        if not isinstance(msg.channel, discord.TextChannel):
            return

        # do not process bulk message deletes, or message censors (the censor cog does that already)
        # TODO: do this but cleanly, maybe paste website?
        if await self.bulk_deletes.check_batch(msg.id) or await self.censored_messages.check(message_id=msg.id):
            return

        # if this channel isn't publicly visible or deletes shouldn't be tracked, bail
        if (not await is_publicly_visible(self.bot, msg.channel) or
                await self.bot.config_is_set(msg.guild, 'modlog_notrack_deletes')):
            return

        # if the author was a bot and we aren't configured to allow bots, return
        if msg.author.bot and not await self.bot.config_is_set(msg.guild, 'modlog_filter_allow_bot'):
            return

        # format attachment list
        attachments = 'no attachments' if not msg.attachments else f'{len(msg.attachments)} attachment(s): ' + \
            ', '.join(f'{a.filename}, {filesize(a.size)}' for a in msg.attachments)

        content = utils.prevent_codeblock_breakout(utils.truncate(msg.content, 1500))
        fmt = (f'\U0001f6ae Message by {describe(msg.author)} deleted in {msg.channel.mention}: ```\n{content}\n``` '
               f'({attachments}, {len(msg.embeds)} embed(s)')
        await self.log(msg.guild, fmt)

    async def on_guild_role_create(self, role: discord.Role):
        base = f'\N{KEY} {self.bot.tick("green", guild=role.guild)} Role created: {describe(role)}'
        msg = await self.log(role.guild, base)
        await self.autoformat_responsible_nontarget(msg, action='role_create', base=base)

    async def on_guild_role_delete(self, role: discord.Role):
        base = f'\N{KEY} {self.bot.tick("red", guild=role.guild)} Role deleted: {describe(role)}'
        msg = await self.log(role.guild, base)
        await self.autoformat_responsible_nontarget(msg, action='role_delete', base=base)

    async def on_member_join(self, member: discord.Member):
        new = '\N{SQUARED NEW} ' if (datetime.datetime.utcnow() - member.created_at).total_seconds() <= 604800 else ''
        await self.log(member.guild, f'\N{INBOX TRAY} {new}{describe(member, created=True)}')

    def format_member_departure(self, member: discord.Member, *, verb: str = 'left', emoji: str ='\N{OUTBOX TRAY}') -> str:
        """
        Formats a member's departure from the server. Can be customized.

        This function automatically adds the basketball emoji before the member's description if the joined recently.
        If the provided member is a ``discord.User``, the joined and basketball emoji are always omitted.

        Account creation information is always shown.

        :param member: The member who left.
        :param verb: The verb to append right after the name. For example, providing "was banned" will format the
                     departure as "User#1234 was banned [...]"
        :param emoji: The emoji to place before the user's description.
        :return: The formatted departure.
        """
        # if it's a user, return bare info
        if isinstance(member, discord.User):
            return f'{emoji} {describe(member, before=verb, created=True)}'

        # did they bounce?
        bounce = '\U0001f3c0 ' if (datetime.datetime.utcnow() - member.joined_at).total_seconds() <= 1500 else ''
        return f'{emoji} {bounce}{describe(member, before=verb, created=True, joined=True)}'

    async def get_responsible(self, guild: discord.Guild, action: str, *, target: discord.Member=None) -> discord.AuditLogEntry:
        """
        Checks the audit log for recent action performed on some user.

        :param guild: The :class:`discord.Guild` to look at.
        :param action: The name of the :class:`discord.AuditLogAction` attribute to check for.
        :param target: The targeted user to check for.
        :returns: The audit log entry.
        """
        try:
            # get the audit logs for the action specified
            entries = await guild.audit_logs(limit=1, action=getattr(discord.AuditLogAction, action)).flatten()

            # only check for entries performed on target, and happened in the last 2 seconds
            def check(entry):
                created_ago = (datetime.datetime.utcnow() - entry.created_at).total_seconds()
                return (entry.target == target if target else True) and created_ago <= 2

            return discord.utils.find(check, entries)
        except discord.Forbidden:
            pass

    def format_reason(self, entry: discord.AuditLogEntry) -> str:
        """
        Automatically formats an `discord.AuditLogEntry`'s reason.

        :param entry: The entry to format.
        :return: The entry, formatted.
        """
        return f'with reason `{entry.reason}`' if entry.reason else 'with no attached reason'

    async def autoformat_responsible_nontarget(self, log_message: discord.Message, *, action: str, base: str):
        """
        Automatically edits a message sent in the audit log to include responsible information.

        :param log_message: The :class:`discord.Message` that was sent in the log channel.
        :param action: The name of the :class:`discord.AuditLogAction` attr to check for.
        :param base: The text to prepend.
        """
        action = await self.get_responsible(log_message.guild, action=action)

        if action:
            await log_message.edit(content=self.modlog_msg(f'{base} by {describe(action.user)}'))

    async def autoformat_responsible(self,
                                     log_message: discord.Message,
                                     targeted: discord.Member,
                                     action: str,
                                     format_to: '(entry: discord.AuditLogEntry) -> str' = None, *,
                                     departure: bool = False,
                                     departure_extra: str = None,
                                     departure_emoji: str = None):
        """
        Automatically edits a message sent in the audit log to include responsible information for a moderator action
        that includes a "targeted" user.

        :param log_message: The `discord.Message` that was sent in the log channel.
        :param targeted: The `discord.Member` that was targeted.
        :param action: The name of the `discord.AuditLogAction` attr to check for.
        :param format_to: A callable that will return the log message's new content. It will automatically be formatted
                          to include time. It receives one parameter, the AuditLogEntry.
        :param departure: If this parameter is True, the autoformatter will attempt to use format_member_departure.
        :param departure_extra: Specifies what happened to the user when formatting the departure.
        :param departure_emoji: Specifies which emoji to use when formatting the departure.
        """
        if not log_message:
            # no log message to edit...
            return

        audit_log_entry = await self.get_responsible(log_message.guild, action, target=targeted)

        if not audit_log_entry:
            # couldn't find audit log entry...
            return

        if departure:
            # formatting using departure

            # [banned] by [user (user id)] [with no attached reason|with reason blah blah...]
            verb = f'{departure_extra} by {describe(audit_log_entry.user)} {self.format_reason(audit_log_entry)}'
            fmt = self.format_member_departure(targeted, verb=verb, emoji=departure_emoji)
            await log_message.edit(content=self.modlog_msg(fmt))
        elif format_to:
            await log_message.edit(content=self.modlog_msg(format_to(audit_log_entry)))

    async def on_member_ban(self, guild: discord.Guild, user: discord.Guild):
        # don't make on_member_remove process this user's departure
        self.ban_debounces.add(user_id=user.id, guild_id=guild.id)

        verb = 'was banned'

        msg = await self.log(guild, self.format_member_departure(user, verb=verb, emoji='\N{HAMMER}'))
        await self.autoformat_responsible(msg, user, 'ban', departure=True, departure_extra=verb,
                                          departure_emoji='\N{HAMMER}')

    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        base_msg = f'\N{HAMMER} {describe(user)} was unbanned'
        msg = await self.log(guild, base_msg + '.')

        def formatter(entry: discord.AuditLogEntry) -> str:
            return f'{base_msg} by {describe(entry.user)} {self.format_reason(entry)}.'
        await self.autoformat_responsible(msg, user, 'unban', format_to=formatter)

    async def on_member_remove(self, member: discord.Member):
        # this is called also when someone gets banned, but we don't want duplicate messages, so bail if this person
        # got banned as we already sent a message earlier.
        if await self.ban_debounces.check(user_id=member.id, guild_id=member.guild.id):
            return

        msg = await self.log(member.guild, self.format_member_departure(member))

        # this member might've gotten kicked, check for that.
        await self.autoformat_responsible(msg, member, 'kick', departure=True, departure_extra='was kicked',
                                          departure_emoji='\N{WOMANS BOOTS}')

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
