import asyncio
import logging

import discord
from discord import Guild, AuditLogAction
from discord.utils import get

from dog import Cog
from dog.core.utils.formatting import describe
from dog.ext.modlog import DebounceProcessor

logger = logging.getLogger(__name__)


class PollrBans(Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ban_debounce = DebounceProcessor('pollr bans')

    async def on_member_dog_ban(self, member, moderator, reason):
        logger.debug('dog ban catch: member_id=%d mod=%s reason=%s', member.id,
                     moderator, reason)
        self.ban_debounce.add(
            member_id=member.id, moderator=moderator, reason=reason)

    async def on_member_ban(self, guild: Guild, user):
        if not await self.bot.config_is_set(guild, 'pollr_mod_log'):
            # not configured to announce bans here
            return

        logger.debug('pollr ban process: %d', user.id)

        # grab bans channel
        bans = discord.utils.get(guild.text_channels, name='bans')

        if not bans:
            logger.debug('not announcing ban, couldn\'t find channel. gid=%d',
                         guild.id)
            return

        ban = f'**Ban:** {describe(user)}'

        # get my permissions
        perms = guild.me.guild_permissions

        # check to see if they were banned via dogbot's ban command, and provide cleaner insight
        information = await self.ban_debounce.check(
            member_id=user.id,
            return_information=True,
            partial=True,
            wait_period=2.0)

        if information:
            reason = information['reason']
            responsible = information['moderator']
            ban += f'\n**Responsible:** {describe(responsible)}\n**Reason:** {reason}'

        if not information and perms.view_audit_log:
            # fall back to audit log

            await asyncio.sleep(
                1)  # wait a bit, because audit logs can be slow

            logs = await guild.audit_logs(
                action=AuditLogAction.ban, limit=5).flatten()

            # grab the entry that targeted our banned user
            entry = get(logs, target=user)

            if entry:
                ban += f'\n**Responsible:** {describe(entry.user)}'
                if entry.reason:
                    ban += f'\n**Reason:** {entry.reason}'

        try:
            # send the ban message
            await bans.send(ban)
        except discord.HTTPException as exc:
            logger.warning('Cannot announce ban, error! gid=%d %s', guild.id,
                           exc)


def setup(bot):
    bot.add_cog(PollrBans(bot))
