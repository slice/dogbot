import asyncio
import aiohttp
import aioredis
import datetime
import logging
import discord
import traceback
import raven
from discord.ext import commands
from . import errors, botcollection
from .utils import pretty_timedelta
import dog_config as cfg

logger = logging.getLogger(__name__)


class DogBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # boot time (for uptime)
        self.boot_time = datetime.datetime.utcnow()

        # hack because __init__ cannot be async
        _loop = asyncio.get_event_loop()
        _redis_coroutine = aioredis.create_redis(
            (cfg.redis_url, 6379), loop=_loop)

        # aioredis connection
        self.redis = _loop.run_until_complete(_redis_coroutine)

        # sentry connection for reporting exceptions
        self.sentry = raven.Client(cfg.raven_client_url)

        # asyncio task that POSTs to bots.discord.pw with the guild count every
        # 10 minutes
        self.report_task = None

    async def command_is_disabled(self, guild, command_name):
        return await self.redis.exists(f'disabled:{guild.id}:{command_name}')

    async def disable_command(self, guild, command_name):
        logger.info('disabling %s in %d', command_name, guild.id)
        await self.redis.set(f'disabled:{guild.id}:{command_name}', 'on')

    async def enable_command(self, guild, command_name):
        logger.info('enabling %s in %d', command_name, guild.id)
        await self.redis.delete(f'disabled:{guild.id}:{command_name}')

    async def wait_for_response(self, ctx):
        def check(m):
            return m.channel.id == ctx.channel.id and m.author.id == ctx.author.id
        return await self.wait_for('message', check=check)

    def has_prefix(self, haystack):
        for prefix in list(cfg.prefix):
            if haystack.startswith(prefix):
                return True
        return False

    async def send_modlog(self, guild, *args, **kwargs):
        mod_log = discord.utils.get(guild.channels, name='mod-log')

        # don't post to mod-log, couldn't find the channel
        if mod_log is None:
            return

        await mod_log.send(*args, **kwargs)

    async def ok(self, ctx, emoji='\N{OK HAND SIGN}'):
        try:
            await ctx.message.add_reaction(emoji)
        except discord.Forbidden:
            await ctx.send(emoji)

    async def on_ready(self):
        logger.info('BOT IS READY')
        logger.info('owner id: %s', cfg.owner_id)
        logger.info('logged in')
        logger.info(f' name: {self.user.name}#{self.user.discriminator}')
        logger.info(f' id:   {self.user.id}')

        # helpful game
        short_prefix = min(cfg.prefix, key=len)
        help_game = discord.Game(name=f'{short_prefix}help')
        await self.change_presence(game=help_game)

        async def report_guilds_task():
            ENDPOINT = f'https://bots.discord.pw/api/bots/{self.user.id}/stats'
            while True:
                guilds = len(self.guilds)
                data = {'server_count': guilds}
                headers = {'Authorization': cfg.discordpw_token}
                logger.info('POSTing guild count to abal\'s website...')
                async with aiohttp.ClientSession() as cs:
                    # HTTP POST to the endpoint
                    async with cs.post(ENDPOINT, json=data, headers=headers)\
                            as resp:
                        if resp.status != 200:
                            logger.warn('Failed to post guild count...')
                            logger.warn('Resp: %s', await resp.text())
                        else:
                            logger.info('Posted guild count successfully!'
                                        ' (%d guilds)', guilds)
                await asyncio.sleep(60 * 10)  # only report every 10 minutes

        logger.info('Creating bots.discord.pw task')
        self.report_task = self.loop.create_task(report_guilds_task())

    async def monitor_send(self, *args, **kwargs):
        monitor_channels = getattr(cfg, 'owner_monitor_channels', [])
        channels = [self.get_channel(c) for c in monitor_channels]

        # no monitor channels
        if not channels or not any(channels):
            return

        for channel in channels:
            await channel.send(*args, **kwargs)

    async def notify_think_is_collection(self, guild):
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
                for channel in guild.channels:
                    # ignore voice channels
                    if not isinstance(channel, discord.TextChannel):
                        continue
                    can_speak = channel.permissions_for(guild.me).send_messages
                    if can_speak:
                        await channel.send(COLL_HDR_PUBLIC + COLL_REST)
                        return
                logger.info('Couldn\'t inform the server at all. Giving up.')

    async def on_guild_join(self, g):
        diff = pretty_timedelta(datetime.datetime.utcnow() - g.created_at)
        ratio = botcollection.user_to_bot_ratio(g)

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
                   f' Created {diff} ago, user to bot ratio: {ratio}')
            return await self.monitor_send(fmt)

        # monitor
        fmt = (f'\N{SMIRKING FACE} Added to new guild "{g.name}" (`{g.id}`)'
               f', {len(g.members)} members, owned by {g.owner.mention}'
               f' (`{g.owner.id}`). This guild was created {diff} ago.'
               f' User to bot ratio: {ratio}')
        await self.monitor_send(fmt)

    async def on_guild_remove(self, g):
        fmt = (f'\N{LOUDLY CRYING FACE} Removed from guild "{g.name}"'
               f' (`{g.id}`)!')
        await self.monitor_send(fmt)

    async def config_is_set(self, guild, name):
        return await self.redis.exists(f'{guild.id}:{name}')

    async def on_command_error(self, ex, ctx):
        if ctx.command:
            see_help = f'Run `d?help {ctx.command.name}` for more information.'

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
        elif isinstance(ex, commands.errors.CommandInvokeError):
            tb = ''.join(traceback.format_exception(
                type(ex.original), ex.original,
                ex.original.__traceback__
            ))

            header = f'Command error: {type(ex.original).__name__}: {ex.original}'
            message = header + '\n' + str(tb)

            # dispatch the message
            self.sentry.captureMessage(message)
            logger.error(message)
