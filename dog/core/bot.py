"""
The core Dogbot bot.
"""

import asyncio
import logging
import traceback
from typing import List

import datadog as dd
import discord
import praw
import raven
from discord.ext import commands
from dog.core import utils
from dog.core.base import BaseBot

from . import botcollection, errors

logger = logging.getLogger(__name__)


class DogBot(BaseBot):
    """
    The main DogBot bot. It is automatically sharded. All parameters are passed
    to the constructor of :class:`discord.commands.AutoShardedBot`.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, command_prefix=self.prefix, **kwargs)

        # configuration dict
        self.cfg = kwargs.get('cfg')

        # sentry connection for reporting exceptions
        self.sentry = raven.Client(self.cfg['monitoring']['raven_client_url'])

        # praw (reddit)
        self.praw = praw.Reddit(**self.cfg['credentials']['reddit'])

        # tasks
        self.report_task = None
        self.datadog_task = None

        # list of extensions to reload (this means that new extensions are not picked up)
        # this is here so we can d?reload even if an syntax error occurs and it won't be present
        # in self.extensions
        self._exts_to_load = list(self.extensions.keys()).copy()

        self.prefix_cache = {}
        self.refuse_notify_left = []

    async def is_global_banned(self, user: discord.User):
        key = f'cache:globalbans:{user.id}'

        if await self.redis.exists(key):
            # use the cached value instead
            return (await self.redis.get(key)).decode() == 'banned'

        async with self.pgpool.acquire() as conn:
            # grab the record from postgres, if any
            banned = (await conn.fetchrow('SELECT * FROM globalbans WHERE user_id = $1', user.id)) is not None

            # cache the banned value for 2 hours
            await self.redis.set(key, 'banned' if banned else 'not banned', expire=7200)

            # return whether banned or not
            return banned

    async def on_message(self, msg):
        await self.redis.incr('stats:messages')

        if not msg.author.bot and await self.is_global_banned(msg.author):
            return

        await super().on_message(msg)

    async def get_prefixes(self, guild: discord.Guild) -> 'List[str]':
        """ Returns the supplementary prefixes for a guild. """
        if not guild:
            return []

        if self.prefix_cache.get(guild.id):
            return self.prefix_cache[guild.id]

        async with self.pgpool.acquire() as conn:
            prefixes = await conn.fetch('SELECT prefix FROM prefixes WHERE guild_id = $1', guild.id)
            prefix_strings = list(map(lambda r: r['prefix'], prefixes))
            if prefixes and not self.prefix_cache.get(guild.id):
                self.prefix_cache[guild.id] = prefix_strings
            return [] if not prefixes else prefix_strings

    async def prefix(self, bot, message: discord.Message):
        """ Returns prefixes for a message. """
        mention = [self.user.mention + ' ', f'<@!{self.user.id}> ']
        additional_prefixes = await self.get_prefixes(message.guild)
        return self.cfg['bot']['prefixes'] + mention + additional_prefixes

    async def close(self):
        # close stuff
        logger.info('close() called, cleaning up...')
        self.redis.close()
        await self.pgpool.close()
        await self.session.close()

        # cancel tasks
        if self.report_task:
            self.report_task.cancel()
        await super().close()

    async def command_is_disabled(self, guild: discord.Guild, command_name: str):
        """ Returns whether a command is disabled in a guild. """
        return await self.redis.exists(f'disabled:{guild.id}:{command_name}')

    async def disable_command(self, guild: discord.Guild, command_name: str):
        """ Disables a command in a guild. """
        logger.debug('Disabling %s in %d.', command_name, guild.id)
        await self.redis.set(f'disabled:{guild.id}:{command_name}', 'on')

    async def enable_command(self, guild: discord.Guild, command_name: str):
        """ Enables a command in a guild. """
        logger.debug('Enabling %s in %d.', command_name, guild.id)
        await self.redis.delete(f'disabled:{guild.id}:{command_name}')

    def has_prefix(self, text: str):
        """
        Checks if text starts with a bot prefix.

        .. NOTE::

            This does not rely on `discord.commands.ext.Bot.command_prefix`,
            but rather the list of prefixes present in `dog_config`.
        """
        return any([text.startswith(p) for p in self.cfg['bot']['prefixes']])

    async def send_modlog(self, guild: discord.Guild, *args, **kwargs):
        """
        Sends a message to the #mod-log channel of a guild.

        If there is no #mod-log channel, no message is sent. All parameters are
        passed to `send()`.
        """
        try:
            key = 'modlog_channel_id'
            manual_id = int(await self.config_get(guild, key))
            manual_mod_log = discord.utils.get(guild.text_channels, id=manual_id)
            if manual_mod_log is not None:
                logger.debug('Using a manual mod log for guild %d.', guild.id)
        except:
            logger.debug('Using automatic mod log or guild %d.', guild.id)
            manual_mod_log = None

        mod_log = manual_mod_log or discord.utils.get(guild.text_channels, name='mod-log')

        # don't post to mod-log, couldn't find the channel
        if mod_log is None:
            return
        
        try:
            await mod_log.send(*args, **kwargs)
            await self.redis.incr('stats:modlog:sends')
        except discord.Forbidden:
            # couldn't post to modlog
            logger.warning('Couldn\'t post to modlog for guild %d. No permissions.', guild.id)
            pass

    async def set_playing_statuses(self):
        short_prefix = min(self.cfg['bot']['prefixes'], key=len)
        for shard in self.shards.values():
            game = discord.Game(name=f'{short_prefix}help | shard {shard.id}')
            await shard.ws.change_presence(game=game)

    async def on_member_ban(self, guild, user):
        if await self.config_is_set(guild, 'pollr_announce'):
            bans = discord.utils.get(guild.text_channels, name='bans')

            if not bans:
                logger.debug('Not announcing ban, couldn\'t find channel. gid=%d', guild.id)
                return

            ban = '**Ban:** {0} (`{0.id}`)\n'.format(user)

            # get my permissions
            perms = guild.default_channel.permissions_for(guild.me)

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

    async def report_guilds(self):
        # bail if we don't have the token
        if 'discordpw_token' not in self.cfg['monitoring']:
            logger.warning('Not going to submit guild count, no discord.pw token.')
            return

        endpoint = f'https://bots.discord.pw/api/bots/{self.user.id}/stats'
        while True:
            guilds = len(self.guilds)
            data = {'server_count': guilds}
            headers = {'Authorization': self.cfg['monitoring']['discordpw_token']}
            logger.info('POSTing guild count to abal\'s website...')
            # HTTP POST to the endpoint
            async with self.session.post(endpoint, json=data, headers=headers) as resp:
                if resp.status != 200:
                    # probably just a hiccup on abal's side
                    logger.warning('Failed to post guild count, ignoring.')
                else:
                    logger.info('Posted guild count successfully! (%d guilds)', guilds)
            await asyncio.sleep(60 * 10)  # only report every 10 minutes

    async def datadog_increment(self, metric):
        if 'datadog' not in self.cfg['monitoring']:
            return

        try:
            await self.loop.run_in_executor(None, dd.statsd.increment, metric)
        except Exception:
            logger.exception('Failed to report metric')

    async def datadog_report(self):
        if 'datadog' not in self.cfg['monitoring']:
            logger.warning('No Datadog configuration detected, not going to report statistics.')
            return

        dd.initialize(api_key=self.cfg['monitoring']['datadog']['api_key'],
                      app_key=self.cfg['monitoring']['datadog']['app_key'])

        while True:
            def report():
                try:
                    dd.statsd.gauge('discord.guilds', len(self.guilds))
                    dd.statsd.gauge('discord.voice.clients', len(self.voice_clients))
                    dd.statsd.gauge('discord.users', len(self.users))
                    dd.statsd.gauge('discord.users.humans', sum(1 for user in self.users if not user.bot))
                    dd.statsd.gauge('discord.users.bots', sum(1 for user in self.users if user.bot))
                except RuntimeError:
                    logger.warning('Couldn\'t report metrics, trying again soon.')
                else:
                    logger.debug('Successfully reported metrics.')
            logger.debug('Reporting metrics to DataDog...')
            await self.loop.run_in_executor(None, report)
            await asyncio.sleep(5)

    async def on_ready(self):
        await super().on_ready()

        if not self.report_task:
            logger.info('Creating bots.discord.pw task.')
            self.report_task = self.loop.create_task(self.report_guilds())

        if not self.datadog_task:
            logger.info('Creating DataDog task.')
            self.datadog_task = self.loop.create_task(self.datadog_report())

        await self.set_playing_statuses()

    async def monitor_send(self, *args, **kwargs):
        """
        Sends a message to the monitoring channel.

        The monitoring channel is a channel usually only visible to the bot
        owner that will have messages like "New guild!" and "Left guild..."
        sent to it.

        All parameters are passed to `send()`.
        """
        logger.info('Monitor sending.')
        monitor_channels = self.cfg['monitoring'].get('monitor_channels', [])
        channels = [self.get_channel(c) for c in monitor_channels]

        # no monitor channels
        if not any(channels):
            return

        # form embed
        fields = kwargs.pop('fields', [])
        embed = discord.Embed(**kwargs)
        for name, value in fields:
            embed.add_field(name=name, value=value)

        try:
            for channel in channels:
                await channel.send(*args, embed=embed)
        except discord.Forbidden:
            logger.warning('Forbidden to send to monitoring channel -- ignoring.')

    async def notify_think_is_collection(self, guild: discord.Guild):
        """
        Notifies a guild that they are a collection.

        Steps are taken in order to notify a guild:

        - Send it to the default channel, but if that doesn't work, then
        - DM the owner of the guild, but if that doesn't work, then
        - Loop through all channels in the guild and message the first sendable
          one that we find.

        """
        support_invite = 'discord.gg/3dd7czT'
        header_public = "Hi there! Somebody added me to this server, "
        header_dm = f"Hi there! Somebody added me to your server, {guild.name} (`{guild.id}`), "
        content = """but my algorithms tell me that this is a bot collecion! (A server dedicated to keeping loads of
        bots in one place, which I don't like!) If this server is not a bot collection, please talk to me, here:
        {invite}, and I'll try to get back to you as soon as possible (make sure to include the ID of your server so I
        can whitelist you)! Thanks!
        """.strip().replace('\n', ' ')

        try:
            await guild.default_channel.send(header_public + content.format(invite=support_invite))
            logger.info('Notified %s (%d) that they were a collection.',
                        guild.name, guild.id)
        except discord.Forbidden:
            logger.info('Couldn\'t send to default channel. DMing owner!')
            try:
                await guild.owner.send(header_dm + content)
            except discord.Forbidden:
                logger.info('Couldn\'t inform the server at all. Giving up.')

    async def on_guild_join(self, g):
        # calculate the utb ratio
        ratio = botcollection.user_to_bot_ratio(g)
        diff = utils.ago(g.created_at)
        fields = [
            ('Guild', f'{g.name}\n`{g.id}`'),
            ('Owner', f'{g.owner.mention} {g.owner}\n`{g.owner.id}`'),
            ('Info', f'Created {diff}\nMembers: {len(g.members)}\nUTB ratio: {ratio}')
        ]

        logger.info('New guild: %s (%d)', g.name, g.id)

        if await botcollection.is_bot_collection(self, g):
            # uh oh!
            logger.info('I think %s (%d) by %s is a bot collection/is blacklisted! Leaving.',
                        g.name, g.id, str(g.owner))

            # notify that i'm leaving a collection
            is_blacklisted = await botcollection.is_blacklisted(self, g.id)
            if not is_blacklisted:
                # if they are a collection, just straight up leave (don't send a message)
                await self.notify_think_is_collection(g)

            # leave it
            self.refuse_notify_left.append(g.id)
            await g.leave()

            # monitor
            title = '\N{RADIOACTIVE SIGN} ' + ('Left blacklisted guild' if is_blacklisted else 'Left bot collection')
            return await self.monitor_send(title=title, fields=fields, color=0xff655b)

        # monitor
        await self.monitor_send(title='\N{INBOX TRAY} Added to new guild', fields=fields, color=0x71ff5e)
        await self.redis.incr('stats:guilds:adds')

        WELCOME_MESSAGE = ('\N{DOG FACE} Woof! Hey there! I\'m Dogbot! To get a list of all of my '
                           'commands, type `d?help` in chat, so I can DM you my commands! If you '
                           'need help, need to report a bug, or just want to request a feature, '
                           'please join the support server: https://discord.gg/3dd7czT Thanks!')

        logger.info('PMing owner of %s (%d)...', g.name, g.id)
        try:
            await g.owner.send(WELCOME_MESSAGE)
        except discord.Forbidden:
            logger.info('Failed to DM owner. Not caring...')
        await self.datadog_increment('discord.guilds.additions')

    async def on_guild_remove(self, g):
        if g.id in self.refuse_notify_left:
            # refuse to notify that we got removed from the guild, because the "left bot collection"/"left blacklisted"
            # monitor message already does that
            logger.debug('Refusing to notify guild leave, already sent a message about that. gid=%d', g.id)
            self.refuse_notify_left.remove(g.id)
            return

        diff = utils.ago(g.created_at)
        fields = [
            ('Guilds', f'{g.name}\n`{g.id}`'),
            ('Info', f'Created {diff}\nMembers: {len(g.members)}')
        ]
        await self.monitor_send(title='\N{OUTBOX TRAY} Removed from guild', fields=fields, color=0xff945b)
        await self.redis.incr('stats:guilds:removes')
        await self.datadog_increment('discord.guilds.removals')

    async def config_get(self, guild: discord.Guild, name: str):
        """
        Returns configuration data for a guild.
        """
        return (await self.redis.get(f'{guild.id}:{name}')).decode()

    async def config_is_set(self, guild: discord.Guild, name: str):
        """
        Returns whether a configuration key for a guild is set or not.

        .. NOTE::

            This does not look at the value of a configuration key; it just
            checks if it exists. In Dogbot, a configuration key existing
            signifies that it is set.
        """
        return await self.redis.exists(f'{guild.id}:{name}')

    async def handle_forbidden(self, ctx):
        cant_respond = ("Hey! I can't respond because I don't have the `Send Messages` "
                        "permission in the channel that you just sent that command in. Please "
                        "ask a server moderator/administrator to sort this out for you, if "
                        "applicable. If you are a server moderator/administrator, please fix "
                        "my permissions!")
        if not ctx.guild.me.permissions_in(ctx.channel).send_messages and ctx.command:
            await ctx.message.author.send(cant_respond)

    async def on_command(self, ctx):
        author = ctx.message.author
        checks = [c.__qualname__.split('.')[0] for c in ctx.command.checks]
        location = '[DM] ' if isinstance(ctx.channel, discord.DMChannel) else '[Guild] '
        logger.info('%sCommand invocation by %s (%d) "%s" checks=%s', location, author, author.id, ctx.message.content,
                    ','.join(checks) or '(none)')
        await self.datadog_increment('dogbot.commands')

    async def on_command_error(self, ctx, ex):
        if getattr(ex, 'should_suppress', False):
            logger.debug('Suppressing exception: %s', ex)
            return

        if ctx.command:
            see_help = f'Run `d?help {ctx.command.qualified_name}` for more information.'

        if isinstance(ex, commands.errors.BadArgument):
            message = str(ex)
            if not message.endswith('.'):
                message = message + '.'
            await ctx.send(f'Bad argument! {message} {see_help}')
        elif isinstance(ex, commands.errors.MissingRequiredArgument):
            await ctx.send(f'Uh oh! {ex} {see_help}')
        elif isinstance(ex, commands.NoPrivateMessage):
            await ctx.send('You can\'t do that in a DM.')
        elif isinstance(ex, errors.InsufficientPermissions):
            await ctx.send(ex)
        elif isinstance(ex, commands.errors.DisabledCommand):
            await ctx.send('That command has been globally disabled by the bot\'s owner.')
        elif isinstance(ex, asyncio.TimeoutError):
            await ctx.send('A request in that command took too long to run. Try running the command again.')
        elif isinstance(ex, commands.errors.CommandInvokeError):
            if isinstance(ex.original, discord.Forbidden):
                if ctx.command.name == 'help':
                    # can't dm that person :(
                    try:
                        await ctx.send(f'Hey, {ctx.author.mention}! I can\'t DM you my help. Do you have DMs enabled?')
                    except discord.Forbidden:
                        pass
                    return
                return await self.handle_forbidden(ctx)

            tb = ''.join(traceback.format_exception(
                type(ex.original), ex.original,
                ex.original.__traceback__
            ))

            header = f'Command error: {type(ex.original).__name__}: {ex.original}'
            message = header + '\n' + str(tb)

            # dispatch the message
            self.sentry.captureMessage(message)
            logger.error(message)
