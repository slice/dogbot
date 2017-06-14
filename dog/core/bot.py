"""
The core Dogbot bot.
"""

import asyncio
import datetime
import importlib
import logging
import os
import random
import sys
import traceback
from typing import Any, List

import aiohttp
import aioredis
import asyncpg
import discord
import dog_config as cfg
import praw
import raven
from discord.ext import commands
from dog.core import utils

from . import botcollection, errors
from .utils import pretty_timedelta

logger = logging.getLogger(__name__)


class DogBot(commands.Bot):
    """
    The main DogBot bot. It is automatically sharded. All parameters are passed
    to the constructor of :class:`discord.commands.AutoShardedBot`.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # boot time (for uptime)
        self.boot_time = datetime.datetime.utcnow()

        # hack because __init__ cannot be async
        loop = asyncio.get_event_loop()
        redis_coroutine = aioredis.create_redis(
            (cfg.redis_url, 6379), loop=loop)

        # aioredis connection
        self.redis = loop.run_until_complete(redis_coroutine)

        # asyncpg
        self.pgpool = loop.run_until_complete(asyncpg.create_pool(**cfg.postgresql_auth))

        # aiohttp session used for fetching data
        self.session = aiohttp.ClientSession()

        # sentry connection for reporting exceptions
        self.sentry = raven.Client(cfg.raven_client_url)

        # praw (reddit)
        self.praw = praw.Reddit(**cfg.reddit)

        # tasks
        self.report_task = None
        self.rotate_game_task = None

        # load core extensions
        self.load_exts_recursively('dog/core/ext', 'Core recursive load')

        with open('resources/playing_status_flavor_text.txt') as f:
            self.flavor_text = [line.strip() for line in f.readlines()]
        logger.info('Loaded %d flavor text line(s)', len(self.flavor_text))

        # list of extensions to reload (this means that new extensions are not picked up)
        # this is here so we can d?reload even if an syntax error occurs and it won't be present
        # in self.extensions
        self._exts_to_load = list(self.extensions.keys()).copy()

    async def close(self):
        # close stuff
        logger.info('close() called, cleaning up...')
        self.redis.close()
        await self.pgpool.close()
        await self.session.close()

        # cancel tasks
        if self.report_task:
            self.report_task.cancel()
        self.rotate_game_task.cancel()
        await super().close()

    def load_exts_recursively(self, directory: str, prefix: str = 'Recursive load'):
        """ Loads extensions from a directory recursively. """
        def ext_filter(f):
            return f not in ('__init__.py', '__pycache__') and not f.endswith('.pyc')

        exts = []

        # walk the ext directory to find extensions
        for path, _, files in os.walk(directory):
            # replace the base path/like/this to path.like.this
            # add the filename at the end, but without the .py
            # filter out stuff we don't need
            exts += [path.replace('/', '.').replace('\\', '.') + '.' + file.replace('.py', '')
                     for file in filter(ext_filter, files)]

        for ext in exts:
            logger.info('%s: %s', prefix, ext)
            self.load_extension(ext)

        # update exts to load
        self._exts_to_load = list(self.extensions.keys()).copy()

    def reload_extension(self, name: str):
        """ Reloads an extension. """
        self.unload_extension(name)
        self.load_extension(name)

    def perform_full_reload(self):
        """ Fully reloads Dogbot.

        This reloads all Dogbot related modules, and all
        extensions.
        """
        logger.info('*** Performing full reload! ***')
        self.reload_all_extensions()
        self.reload_modules()

    def reload_all_extensions(self):
        """ Reloads all extensions. """
        logger.info('Reloading all %d extensions', len(self._exts_to_load))
        for name in self._exts_to_load:
            try:
                logger.info('Reloading extension: %s', name)
                self.reload_extension(name)
            except:
                logger.exception('While reloading all: Failed extension reload for %s', name)
                raise

    def reload_modules(self):
        """ Reloads all Dogbot related modules. """
        # get applicable modules to reload
        modules = {k: m for k, m in sys.modules.items() if 'dog' in k and 'ext' not in k and
                   k != 'dog'}
        for name, module in modules.items():
            logger.info('Reloading bot module: %s', name)
            importlib.reload(module)
        logger.info('Finished reloading bot modules!')

    async def pick_from_list(self, ctx: commands.Context, choices: List[Any]) -> Any:
        """ Shows the user a list of items to pick from. Returns the picked item. """
        # format list of stuff
        choices_list = utils.format_list(choices)

        # send list of stuff
        await ctx.send('Pick one, or send `cancel`.\n\n' + choices_list)
        remaining_tries = 3
        picked = None

        while True:
            if remaining_tries <= 0:
                await ctx.send('You ran out of tries, I give up!')
                return None

            # wait for a message
            msg = await self.wait_for_response(ctx)

            # user wants to cancel?
            if msg.content == 'cancel':
                await ctx.send('Canceled selection.')
                break

            try:
                chosen_index = int(msg.content) - 1
            except ValueError:
                # they didn't enter a valid number
                await ctx.send('That wasn\'t a number! Send a message that '
                               'solely contains the number of the item that '
                               'you want.')
                remaining_tries -= 1
                continue

            if chosen_index < 0 or chosen_index > len(choices) - 1:
                # out of range
                await ctx.send('Invalid choice! Send a message that solely '
                               'contains the number of the item that you '
                               'want.')
                remaining_tries -= 1
            else:
                # they chose correctly
                picked = choices[chosen_index]
                break

        return picked

    async def command_is_disabled(self, guild: discord.Guild, command_name: str):
        """ Returns whether a command is disabled in a guild. """
        return await self.redis.exists(f'disabled:{guild.id}:{command_name}')

    async def disable_command(self, guild: discord.Guild, command_name: str):
        """ Disables a command in a guild. """
        logger.info('disabling %s in %d', command_name, guild.id)
        await self.redis.set(f'disabled:{guild.id}:{command_name}', 'on')

    async def enable_command(self, guild: discord.Guild, command_name: str):
        """ Enables a command in a guild. """
        logger.info('enabling %s in %d', command_name, guild.id)
        await self.redis.delete(f'disabled:{guild.id}:{command_name}')

    async def wait_for_response(self, ctx: commands.Context):
        """
        Waits for a message response from the message author, then returns the
        new message.

        The message we are waiting for will only be accepted if it was sent by
        the original command invoker, and it was sent in the same channel as
        the command message.
        """
        def check(m):
            if isinstance(m.channel, discord.DMChannel):
                # accept any message, because we are in a dm
                return True
            return m.channel.id == ctx.channel.id and m.author == ctx.author
        return await self.wait_for('message', check=check)

    def has_prefix(self, text: str):
        """
        Checks if text starts with a bot prefix.

        .. NOTE::

            This does not rely on `discord.commands.ext.Bot.command_prefix`,
            but rather the list of prefixes present in `dog_config`.
        """
        return any([text.startswith(p) for p in cfg.prefixes])

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
        except:
            manual_mod_log = None

        mod_log = manual_mod_log or discord.utils.get(guild.text_channels, name='mod-log')

        # don't post to mod-log, couldn't find the channel
        if mod_log is None:
            return
        
        try:
            await mod_log.send(*args, **kwargs)
        except discord.Forbidden:
            # couldn't post to modlog
            pass

    async def ok(self, ctx: commands.Context, emoji: str='\N{OK HAND SIGN}'):
        """
        Adds a reaction to the command message, or sends it to the channel if
        we can't add reactions. This should be used as feedback to commands,
        just like how most bots send out `:ok_hand:` when a command completes
        successfully.
        """
        try:
            await ctx.message.add_reaction(emoji)
        except discord.Forbidden:
            # can't add reactions
            await ctx.send(emoji)
        except discord.NotFound:
            # the command message got deleted somehow
            pass

    async def rotate_game(self):
        prefixes = (
            f'{utils.commas(len(self.guilds))} servers',
            f'{utils.commas(len(self.users))} users'
        )

        short_prefix = min(cfg.prefixes, key=len)
        prefix = random.choice(prefixes)
        flavor = random.choice(self.flavor_text)
        game = discord.Game(name=f'{short_prefix}help \N{EM DASH} {prefix} \N{EM DASH} {flavor}')
        await self.change_presence(game=game)

        # wait a bit

    async def change_game_task(self):
        while True:
            await self.rotate_game()
            await asyncio.sleep(60 * 10)

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

    async def on_ready(self):
        logger.info('*** Bot is ready! ***')
        logger.info('Owner ID: %s', cfg.owner_id)
        logger.info('Logged in!')
        logger.info(f' Name: {self.user.name}#{self.user.discriminator}')
        logger.info(f' ID:   {self.user.id}')

        async def report_guilds_task():
            # bail if we don't have the token
            if not hasattr(cfg, 'discordpw_token'):
                logger.warning('Not going to submit guild count, no discord.pw token.')
                return

            ENDPOINT = f'https://bots.discord.pw/api/bots/{self.user.id}/stats'
            while True:
                guilds = len(self.guilds)
                data = {'server_count': guilds}
                headers = {'Authorization': cfg.discordpw_token}
                logger.info('POSTing guild count to abal\'s website...')
                # HTTP POST to the endpoint
                async with self.session.post(ENDPOINT, json=data, headers=headers) as resp:
                    if resp.status != 200:
                        # probably just a hiccup on abal's side
                        logger.warning('Failed to post guild count, ignoring.')
                    else:
                        logger.info('Posted guild count successfully!'
                                    ' (%d guilds)', guilds)
                await asyncio.sleep(60 * 10)  # only report every 10 minutes

        if not self.report_task:
            logger.info('Creating bots.discord.pw task')
            self.report_task = self.loop.create_task(report_guilds_task())
        if not self.rotate_game_task:
            logger.info('Creating game rotater task')
            self.rotate_game_task = self.loop.create_task(self.change_game_task())

    async def monitor_send(self, *args, **kwargs):
        """
        Sends a message to the monitoring channel.

        The monitoring channel is a channel usually only visible to the bot
        owner that will have messages like "New guild!" and "Left guild..."
        sent to it.

        All parameters are passed to `send()`.
        """
        logger.info('Monitor sending.')
        monitor_channels = getattr(cfg, 'owner_monitor_channels', [])
        channels = [self.get_channel(c) for c in monitor_channels]

        # no monitor channels
        if not channels or not any(channels):
            return

        try:
            for channel in channels:
                await channel.send(*args, **kwargs)
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
        COLL_ISSUES = f'https://github.com/{cfg.github}/issues'
        COLL_HDR_PUBLIC = "Hi there! Somebody added me to this server, "
        COLL_HDR_PRIVATE = ("Hi there! Somebody added me to your server, "
                            f"{guild.name} (`{guild.id}`), ")
        COLL_REST = ("but my algorithms tell me that this is a bot"
                     " collection! (A server dedicated to keeping"
                     " loads of bots in one place, which I don't like"
                     "!) If this server is not a bot collection, "
                     "please open an issue here: <" + COLL_ISSUES +
                     "> and I'll try to get back to you as soon as"
                     " possible (make sure to include the name of"
                     " your server so I can whitelist you)! Thanks!")

        try:
            await guild.default_channel.send(COLL_HDR_PUBLIC + COLL_REST)
            logger.info('Notified %s (%d) that they were a collection.',
                        guild.name, guild.id)
        except discord.Forbidden:
            logger.info('Couldn\'t send to default channel. DMing owner!')
            try:
                await guild.owner.send(COLL_HDR_PRIVATE + COLL_REST)
            except discord.Forbidden:
                logger.info('Couldn\'t DM the owner of the guild. Looping.')
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        return await channel.send(COLL_HDR_PUBLIC + COLL_REST)
                logger.info('Couldn\'t inform the server at all. Giving up.')

    async def on_guild_join(self, g):
        diff = pretty_timedelta(datetime.datetime.utcnow() - g.created_at)
        ratio = botcollection.user_to_bot_ratio(g)

        logger.info('New guild: %s (%d)', g.name, g.id)

        if botcollection.is_bot_collection(g):
            # uh oh!
            logger.info('I think %s (%d) by %s is a bot collection! Leaving.',
                        g.name, g.id, str(g.owner))

            # notify that i'm leaving a collection
            await self.notify_think_is_collection(g)

            # leave it
            await g.leave()

            # monitor
            fmt = (f'\N{FACE WITH ROLLING EYES} Left bot collection {g.name}'
                   f' (`{g.id}`), owned by {g.owner.mention} (`{g.owner.id}`)'
                   f' Created {diff}, user to bot ratio: {ratio}')
            return await self.monitor_send(fmt)

        # monitor
        fmt = (f'\N{SMIRKING FACE} Added to new guild "{g.name}" (`{g.id}`)'
               f', {len(g.members)} members, owned by {g.owner.mention}'
               f' (`{g.owner.id}`). This guild was created {diff}.'
               f' User to bot ratio: {ratio}')
        await self.monitor_send(fmt)

        WELCOME_MESSAGE = ('\N{DOG FACE} Woof! Hey there! I\'m Dogbot! To get a list of all of my '
                           'commands, type `d?help` in chat, so I can DM you my commands! If you '
                           'need help, need to report a bug, or just want to request a feature, '
                           'please join the support server: https://discord.gg/3dd7czT Thanks!')

        logger.info('PMing owner of %s (%d)...', g.name, g.id)
        try:
            await g.owner.send(WELCOME_MESSAGE)
        except discord.Forbidden:
            logger.info('Failed to DM owner. Not caring...')

    async def on_guild_remove(self, g):
        fmt = (f'\N{LOUDLY CRYING FACE} Removed from guild "{g.name}"'
               f' (`{g.id}`)!')
        await self.monitor_send(fmt)

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

    async def on_message(self, msg):
        # do not process messages from other bots
        if msg.author.bot:
            return

        await self.process_commands(msg)

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
        logger.info('Command invocation by %s (%d) "%s" checks=%s', author, author.id,
                    ctx.message.content, ','.join(checks) or '(none)')

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
            await ctx.send('You can\'t do that in a private message.')
        elif isinstance(ex, errors.InsufficientPermissions):
            await ctx.send(ex)
        elif isinstance(ex, commands.errors.DisabledCommand):
            await ctx.send('That command has been globally disabled by the bot\'s owner.')
        elif isinstance(ex, commands.errors.CommandInvokeError):
            if isinstance(ex.original, discord.Forbidden):
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
