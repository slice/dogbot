"""
Reddit commands.
"""

import asyncio
import logging
import random

import discord
import praw
import prawcore
from discord.ext import commands
from dog import Cog
from dog.core import checks, utils

logger = logging.getLogger(__name__)


def create_post_embed(post) -> discord.Embed:
    endings = ('.gif', '.jpeg', '.png', '.jpg', '.webp')
    is_image = not post.is_self and any([post.url.endswith(ending) for ending in endings])

    embed = discord.Embed(title=post.title, url=post.url, description=post.selftext)
    embed.set_author(name='/r/%s \N{EM DASH} /u/%s' % (post.subreddit, post.author))
    if is_image:
        embed.set_image(url=post.url)
    return embed



class Reddit(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self.update_interval = 60 * 30 # 30 minutes
        self.feed_task = bot.loop.create_task(self.post_to_feeds())

    async def get_hot(self, channel: discord.TextChannel, sub: str):
        """ Returns a hot Post from a sub. """

        # appropriate post filter
        def post_filter(post):
            # if the channel is nsfw, no posts should be excluded. or else, only allow sfw posts
            appropriate = True if channel.is_nsfw() else not post.over_18
            return not post.stickied and appropriate

        # get the sub
        sub = self.bot.praw.subreddit(sub)

        # check if it exists
        try:
            sub.fullname
        except prawcore.exceptions.NotFound:
            logger.debug('Sub not found, not updating. sub=%s', sub)
            return

        # get some hot posts
        posts = list(filter(post_filter, sub.hot(limit=75)))

        if not posts:
            logger.debug('Could not find a suitable post. sub=%s', sub)
            return

        # just grab a random post
        return random.choice(posts)

    async def update_feed(self, feed):
        logger.debug('Feed update: cid=%d, sub=%s', feed['channel_id'], feed['subreddit'])

        # get the channel
        channel = self.bot.get_channel(feed['channel_id'])
        if not channel:
            # stale channel, continue
            logger.debug('Stale channel, not updating. cid=%d', feed['channel_id'])
            return

        # type to signal an upcoming post
        await channel.trigger_typing()

        # get a host post
        post = await self.get_hot(channel, feed['subreddit'])

        logger.debug('Feed make post: url=%s title=%s sub=%s', post.url, post.title, post.subreddit)

        # post it!
        try:
            await channel.send(embed=create_post_embed(post))
        except discord.Forbidden:
            # not allowed to send to the channel?
            logger.debug('Not allowed to post to feed channel in %d, cid=%d', feed['guild_id'], feed['channel_id'])

    async def post_to_feeds(self):
        # guilds aren't available until the bot is ready, and this task begins before the bot
        # is ready. so let's wait for it to be ready before updating feeds
        await self.bot.wait_until_ready()

        while True:
            # sleep up here so we don't update immediately
            # wait the main sleep interval
            await asyncio.sleep(self.update_interval)

            # fetch all feeds, and update them all
            async with self.bot.pgpool.acquire() as conn:
                feeds = await conn.fetch('SELECT * FROM reddit_feeds')

                # enumerate through all feeds
                for feed in feeds:
                    # wait a minute or two to prevent rate limiting (doesn't really help but w/e)
                    await asyncio.sleep(random.random() + 5)

                    # update the feed
                    await self.update_feed(feed)

    @commands.command()
    async def hot(self, ctx, sub: str):
        """ Fetches hot posts from a subreddit. """
        try:
            post = await self.get_hot(ctx.channel, sub)
            await ctx.send(embed=create_post_embed(post))
        except:
            await ctx.send('Failed to grab a post.')

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
        async with self.bot.pgpool.acquire() as conn:
            feeds = await conn.fetch('SELECT * FROM reddit_feeds WHERE guild_id = $1', ctx.guild.id)
            if not feeds:
                return await ctx.send('No feeds found! Set one up with `d?reddit watch <channel> <subreddit>`. See `d?help '
                                      'reddit watch` for more information.')
            text = '\n'.join(['\N{BULLET} <#{}> (/r/{})'.format(r['channel_id'], r['subreddit']) for r in feeds])
            await ctx.send('**Feeds in {}:**\n\n{}'.format(ctx.guild.name, text))

    @reddit.command(aliases=['unwatch'])
    @checks.is_moderator()
    async def drop(self, ctx, subreddit: str):
        """
        Drops a feed by subreddit name.

        If there are multiple feeds with the subreddit you have provided, all of them will
        be deleted. Only Dogbot Moderators may run this command.
        """
        async with self.bot.pgpool.acquire() as conn:
            await conn.execute('DELETE FROM reddit_feeds WHERE guild_id = $1 AND subreddit = $2', ctx.guild.id,
                               subreddit)
        await self.bot.ok(ctx)

    @reddit.command()
    @checks.is_moderator()
    async def watch(self, ctx, channel: discord.TextChannel, subreddit: str):
        """
        Sets up a channel for me to forward hot posts to, from a subreddit of your choosing.

        Only Dogbot Moderators may use this command.
        """
        # check that there isn't too many feeds
        async with self.bot.pgpool.acquire() as conn:
            count = (await conn.fetchrow('SELECT COUNT(*) FROM reddit_feeds WHERE guild_id = $1', ctx.guild.id))['count']
            logger.debug('Guild %s (%d) has %d feeds', ctx.guild.name, ctx.guild.id, count)
            if count >= 2:
                # they have 2 feeds, which is the max
                return await ctx.send('You have too many feeds! You can only have two at a time. Use `d?reddit feeds` '
                                      'check the feeds in this server.')
            await conn.execute('INSERT INTO reddit_feeds VALUES ($1, $2, $3)', ctx.guild.id, channel.id, subreddit)
        await self.bot.ok(ctx)


def setup(bot):
    bot.add_cog(Reddit(bot))
