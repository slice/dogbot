"""Reddit commands."""

import asyncio
import logging
import random

import discord
import praw
import prawcore
from discord.ext import commands
from dog import Cog
from dog.core import checks, utils
from dog.core.checks import is_bot_admin

logger = logging.getLogger(__name__)
UPDATE_INTERVAL = 60 * 30  # 30 minutes
FUZZ_INTERVAL = 5


def create_post_embed(post) -> discord.Embed:
    endings = ('.gif', '.jpeg', '.png', '.jpg', '.webp')
    is_image = not post.is_self and any(
        post.url.endswith(ending) for ending in endings)

    embed = discord.Embed(
        title=utils.truncate(post.title, 256),
        url=post.url,
        description=utils.truncate(post.selftext, 2048))
    embed.set_author(name='/r/%s \N{EM DASH} /u/%s' % (post.subreddit,
                                                       post.author))
    if is_image:
        embed.set_image(url=post.url)
    return embed


class Reddit(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        logger.info('Reddit cog created!')

        self.praw = praw.Reddit(**bot.cfg['credentials']['reddit'])

        self.update_interval = UPDATE_INTERVAL
        self.fuzz_interval = FUZZ_INTERVAL
        self.feed_task = bot.loop.create_task(self.post_to_feeds())

    def __unload(self):
        logger.info('Reddit cog unloading, cancelling feed task...')
        self.feed_task.cancel()

    def reboot_feed_task(self):
        logger.info('Rebooting feed task.')
        self.feed_task.cancel()
        self.bot.loop.create_task(self.post_to_feeds())

    async def notify_error(self, channel: discord.TextChannel, text: str):
        embed = discord.Embed(
            title='\N{WARNING SIGN} Feed error',
            description=text,
            color=0xff4747)
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            # wow
            pass

    async def get_hot(self, channel: discord.TextChannel, sub: str):
        """Returns a hot Post from a sub."""

        # appropriate post filter
        def post_filter(post):
            # if the channel is nsfw, no posts should be excluded. or else, only allow sfw posts
            appropriate = True if channel.is_nsfw() else not post.over_18
            return not post.stickied and appropriate

        # get the sub
        sub = self.praw.subreddit(sub)

        logger.debug(
            'Attempting to fetch subreddit: %s inside of executor, this can time out',
            sub)

        # check if it exists
        def fetch():
            sub.fullname  # yes, this actually fetches the subreddit

        try:
            await self.bot.loop.run_in_executor(None, fetch)
        except (prawcore.exceptions.NotFound, prawcore.exceptions.Redirect):
            logger.debug('Sub not found, not updating. sub=%s', sub)
            await self.notify_error(channel,
                                    f'The subreddit /r/{sub} was not found.')
            return
        except prawcore.exceptions.BadRequest:
            logger.warning('Received bad request from Reddit. sub=%s', sub)
            return

        logger.debug('Fetched subreddit: %s, fetching posts!', sub)

        # get some hot posts
        def exhaust_generator():
            lazy_posts = sub.hot(limit=250)
            return list(lazy_posts)

        hot_posts = await self.bot.loop.run_in_executor(
            None, exhaust_generator)
        logger.debug('Ran sub.hot() in executor. len=%d', len(hot_posts))
        posts = list(filter(post_filter, hot_posts))

        logger.debug('Filtered %d posts from %s!', len(posts), sub.fullname)

        if not posts:
            logger.debug('Could not find a suitable post. sub=%s', sub)
            return

        logger.debug('Fetching nonexhausted posts...')

        # just grab a random, non-exhausted post
        nonexhausted = [
            p for p in posts
            if not await self.is_exhausted(channel.guild.id, p.id)
        ]

        if not nonexhausted:
            # all posts have been exhausted, wew
            logger.debug('All posts have been exhausted.')
            return

        chosen_post = random.choice(nonexhausted)

        logger.debug('Chose a post! Returning.')

        # exhaust the post we chose
        await self.add_exhausted(channel.guild.id, chosen_post.id)
        logger.debug('%d posts left unexhausted', len(nonexhausted) - 1)

        return chosen_post

    async def update_feed(self, feed):
        logger.debug('Feed update: cid=%d, sub=%s', feed['channel_id'],
                     feed['subreddit'])

        # get the channel
        channel = self.bot.get_channel(feed['channel_id'])
        if not channel:
            # stale channel, continue
            logger.debug('Stale channel, not updating. cid=%d',
                         feed['channel_id'])
            return

        # type to signal an upcoming post
        try:
            await channel.trigger_typing()
        except discord.Forbidden:
            logger.debug('Couldn\'t post in #%s (%d), returning.',
                         channel.name, channel.id)
            return

        # get a host post
        try:
            post = await asyncio.wait_for(
                self.get_hot(channel, feed['subreddit']), 6.5)
        except asyncio.TimeoutError:
            logger.error(
                'get_hot timed out, cannot update feed (sub=%s, cid=%d)',
                feed['subreddit'], feed['channel_id'])
            return

        if not post:
            logger.debug('Refusing to update this feed, no post.')
            return

        logger.debug('Feed make post: url=%s title=%s sub=%s', post.url,
                     post.title, post.subreddit)

        # post it!
        try:
            await channel.send(embed=create_post_embed(post))
        except discord.Forbidden:
            # not allowed to send to the channel?
            logger.debug('Not allowed to post to feed channel in %d, cid=%d',
                         feed['guild_id'], feed['channel_id'])

    async def is_exhausted(self, guild_id: int, post_id: str) -> bool:
        """Returns whether a post IDs is exhausted."""
        record = await self.bot.pgpool.fetchrow(
            'SELECT * FROM exhausted_reddit_posts WHERE guild_id = $1 AND post_id = $2',
            guild_id, post_id)

        return record is not None

    async def add_exhausted(self, guild_id: int, post_id: str):
        """Adds an exhausted post ID to the database."""
        logger.debug('Exhausting post %s (guild = %d)', post_id, guild_id)
        await self.bot.pgpool.execute(
            "INSERT INTO exhausted_reddit_posts VALUES ($1, $2)", guild_id,
            post_id)

    async def post_to_feeds(self):
        # guilds aren't available until the bot is ready, and this task begins before the bot
        # is ready. so let's wait for it to be ready before updating feeds
        await self.bot.wait_until_ready()

        logger.debug('Bot is ready, proceeding to Reddit feed update loop...')

        while True:
            # sleep up here so we don't update immediately
            # wait the main sleep interval
            await asyncio.sleep(self.update_interval)

            logger.debug('Going to update all feeds...')

            # fetch all feeds, and update them all
            feeds = await self.bot.pgpool.fetch('SELECT * FROM reddit_feeds')

            # enumerate through all feeds
            for idx, feed in enumerate(feeds):
                logger.debug('Updating feed {}/{}!'.format(
                    idx + 1, len(feeds)))
                # wait a minute or two to prevent rate limiting (doesn't really help but w/e)
                await asyncio.sleep(random.random() + self.fuzz_interval)

                # update the feed
                await self.update_feed(feed)

            logger.debug('Updated.')

    @commands.command()
    async def hot(self, ctx, sub: str):
        """Fetches hot posts from a subreddit."""
        try:
            async with ctx.typing():
                post = await self.get_hot(ctx.channel, sub)
                if not post:
                    return await ctx.send('No suitable posts were found.')
                await ctx.send(embed=create_post_embed(post))
        except Exception:
            await ctx.send('Failed to grab a post, sorry!')
            logger.exception('Failed to grab a post:')

    @commands.group()
    @commands.guild_only()
    @checks.is_moderator()
    async def reddit(self, ctx):
        """
        This command group contains all commands related to Reddit feeds.

        Feeds will be updated every 30 minutes. Both self and link posts will be posted to the channel. NSFW posts will
        only be posted if the channel that the bot is posting in is NSFW. Stickied posts are never posted.
        """
        pass

    @reddit.command()
    @checks.is_moderator()
    async def feeds(self, ctx):
        """
        Lists all feeds in this server.

        Only Dogbot Moderators may run this command.
        """
        feeds = await self.bot.pgpool.fetch(
            'SELECT * FROM reddit_feeds WHERE guild_id = $1', ctx.guild.id)

        if not feeds:
            return await ctx.send(
                f'No feeds found! Set one up with `{ctx.prefix}reddit watch <channel> <subreddit>`. See '
                f'`{ctx.prefix}help reddit watch` for more information.')

        text = '\n'.join(
            '\N{BULLET} <#{}> (/r/{})'.format(r['channel_id'], r['subreddit'])
            for r in feeds)
        await ctx.send('**Feeds in {}:**\n\n{}'.format(ctx.guild.name, text))

    @reddit.command()
    @is_bot_admin()
    async def debug(self, ctx):
        """Drastically lowers feed timers. Applied globally."""
        self.update_interval = 3
        self.fuzz_interval = 1
        self.reboot_feed_task()
        await ctx.ok()

    @reddit.command()
    @is_bot_admin()
    async def debug_revert(self, ctx):
        """Reverts lowered feed timers."""
        self.update_interval = UPDATE_INTERVAL
        self.fuzz_interval = FUZZ_INTERVAL
        self.reboot_feed_task()
        await ctx.ok()

    @reddit.command()
    @is_bot_admin()
    async def update_all_now(self, ctx):
        """Forces a feed update now."""
        logger.debug('[FORCED] Updating all feeds NOW...')

        # fetch all feeds, and update them all
        feeds = await self.bot.pgpool.fetch('SELECT * FROM reddit_feeds')

        # enumerate through all feeds
        for idx, feed in enumerate(feeds):
            logger.debug('[FORCED] Updating feed {}/{}!'.format(
                idx + 1, len(feeds)))

            # update the feed
            await self.update_feed(feed)

        logger.debug('[FORCED] Updated all feeds.')

    @reddit.command(aliases=['unwatch'])
    @checks.is_moderator()
    async def drop(self, ctx, subreddit: str):
        """
        Drops a feed by subreddit name.

        If there are multiple feeds with the subreddit you have provided, all of them will
        be deleted. Only Dogbot Moderators may run this command.
        """
        await self.bot.pgpool.execute(
            'DELETE FROM reddit_feeds WHERE guild_id = $1 AND subreddit = $2',
            ctx.guild.id, subreddit)
        await ctx.ok()

    @reddit.command()
    @checks.is_moderator()
    async def watch(self, ctx, channel: discord.TextChannel, subreddit: str):
        """
        Sets up a channel for me to forward hot posts to, from a subreddit of your choosing.

        Only Dogbot Moderators may use this command.
        """
        # check that there isn't too many feeds
        async with self.bot.pgpool.acquire() as conn:
            count = (await conn.fetchrow(
                'SELECT COUNT(*) FROM reddit_feeds WHERE guild_id = $1',
                ctx.guild.id))['count']
            logger.debug('Guild %s (%d) has %d feeds', ctx.guild.name,
                         ctx.guild.id, count)
            if count >= 2:
                # they have 2 feeds, which is the max
                return await ctx.send(
                    f'You have too many feeds! You can only have two at a time. Use `{ctx.prefix}reddit feeds` '
                    'check the feeds in this server.')
            await conn.execute('INSERT INTO reddit_feeds VALUES ($1, $2, $3)',
                               ctx.guild.id, channel.id, subreddit)
        await ctx.ok()


def setup(bot):
    if 'reddit' not in bot.cfg['credentials']:
        logger.warning('Not adding Reddit cog, not present in configuration!')
        return

    bot.add_cog(Reddit(bot))
