import asyncio
import logging

import discord

from dog import Cog

logger = logging.getLogger(__name__)


class PollrBans(Cog):
    async def on_member_ban(self, guild, user):
        if not await self.bot.config_is_set(guild, 'pollr_mod_log'):
            return

        bans = discord.utils.get(guild.text_channels, name='bans')

        if not bans:
            logger.debug('Not announcing ban, couldn\'t find channel. gid=%d', guild.id)
            return

        ban = '**Ban:** {0} (`{0.id}`)\n'.format(user)

        # get my permissions
        perms = guild.me.guild_permissions

        if perms.view_audit_log:
            await asyncio.sleep(0.5)  # wait a bit
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=5):
                if entry.target == user:
                    ban += f'**Responsible:** {entry.user} (`{entry.user.id}`)'
                    if entry.reason:
                        ban += f'\n**Reason:** {entry.reason}'
                    break

        try:
            await bans.send(ban)
        except discord.Forbidden:
            logger.debug('Cannot announce ban, forbidden! gid=%d', guild.id)


def setup(bot):
    bot.add_cog(PollrBans(bot))
