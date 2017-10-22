"""
Simple, embed+channel-based monitoring of Dogbot.
"""
import logging
import discord
from discord import Guild

from dog import Cog
from dog.core import botcollection, utils

logger = logging.getLogger(__name__)


class Colors:
    NEON_GREEN = 0x71ff5e
    ORANGE = 0xff945b
    LIGHT_RED = 0xff655b


class MonitorChannel(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.refuse_notify_left = []

    async def monitor_send(self, *args, **kwargs):
        """
        Sends a message to the monitoring channel.

        The monitoring channel is a channel usually only visible to the bot
        owner that will have messages like "New guild!" and "Left guild..."
        sent to it.

        All parameters are passed to `send()`.
        """
        logger.info('Monitor sending args=%s, kwargs=%s', args, kwargs)
        monitor_channels = self.bot.cfg['monitoring'].get('monitor_channels', [])

        # no specified channel
        if not monitor_channels:
            return

        channels = [self.bot.get_channel(c) for c in monitor_channels]

        # no resolved monitoring channels
        if not any(channels):
            return

        # form embed
        embed = discord.Embed(**kwargs)
        for name, value in kwargs.get('fields', []):
            embed.add_field(name=name, value=value)

        try:
            for channel in channels:
                await channel.send(*args, embed=embed)
        except discord.Forbidden:
            logger.warning('Forbidden to send to monitoring channel -- ignoring.')

    def guild_fields(self, g: Guild):
        """Returns a list of fields to be passed into :method:``monitor_send`` from a guild."""
        ratio = botcollection.user_to_bot_ratio(g)
        humans = utils.commas(sum(1 for u in g.members if not u.bot))
        bots = utils.commas(sum(1 for u in g.members if u.bot))

        return [
            ('Guild', f'{g.name}\n`{g.id}`'),
            ('Owner', f'{g.owner.mention} {g.owner}\n`{g.owner.id}`'),
            ('Info', f'Created {utils.ago(g.created_at)}'),
            ('Members', f'Members: {len(g.members)} (UTBR: {ratio})\n{humans} human(s), {bots} bot(s)')
        ]

    async def on_guild_join(self, g: Guild):
        logger.info('New guild: %s (%d)', g.name, g.id)
        fields = self.guild_fields(g)

        is_collection = await botcollection.is_bot_collection(self.bot, g)
        should_detect_collections = self.bot.cfg['bot'].get('bot_collection_detection', False)

        if await botcollection.is_blacklisted(self.bot, g.id) or (is_collection and should_detect_collections):
            # leave it
            self.refuse_notify_left.append(g.id)
            await g.leave()

            # monitor
            title = '\N{RADIOACTIVE SIGN} Left toxic guild'
            return await self.monitor_send(title=title, fields=fields, color=Colors.LIGHT_RED)

        # monitor
        await self.monitor_send(title='\N{INBOX TRAY} Added to new guild', fields=fields, color=Colors.NEON_GREEN)
        await self.bot.redis.incr('stats:guilds:adds')

    async def on_guild_remove(self, g: Guild):
        if g.id in self.refuse_notify_left:
            # refuse to notify that we got removed from the guild, because the "left bot collection"/"left blacklisted"
            # monitor message already does that
            self.refuse_notify_left.remove(g.id)
            return

        fields = self.guild_fields(g)
        await self.monitor_send(title='\N{OUTBOX TRAY} Removed from guild', fields=fields, color=Colors.ORANGE)
        await self.bot.redis.incr('stats:guilds:removes')


def setup(bot):
    bot.add_cog(MonitorChannel(bot))
