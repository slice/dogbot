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


class Reddit(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.feed_task = bot.loop.create_task(self.post_to_feeds())

    async def post_to_feeds(self):
        await self.bot.wait_until_ready()
        while True:
            logger.debug('Posting to feeds!')
            async with self.bot.pgpool.acquire() as conn:
                records = await conn.fetch('SELECT * FROM reddit_feeds')
                for record in records:
                    logger.debug('Feed post: cid=%d, sub=%s', record['channel_id'], record['subreddit'])

                    # get the channel
                    channel = self.bot.get_channel(record['channel_id'])
                    if not channel:
                        # stale channel, continue
                        logger.debug('Stale channel, not posting... cid=%d', record['channel_id'])
                        continue
                    await channel.trigger_typing()

                    # appropriate post filter
                    def post_filter(post):
                        appropriate = True if channel.is_nsfw() else not post.over_18
                        return not post.stickied and appropriate

                    # get the sub
                    sub = self.bot.praw.subreddit(record['subreddit'])

                    # check if it exists
                    try:
                        sub.fullname
                    except prawcore.exceptions.NotFound:
                        logger.debug('Sub not found. sub=%s', record['subreddit'])
                        continue

                    # get some hot posts
                    posts = list(filter(post_filter, sub.hot(limit=75)))

                    if not posts:
                        logger.debug('Could not find a suitable post. sub=%s', record['subreddit'])
                        continue

                    post = random.choice(posts)

                    endings = ('.gif', '.jpeg', '.png', '.jpg', '.webp')
                    is_image = not post.is_self and any([post.url.endswith(ending) for ending in endings])

                    logger.debug('Feed make post: url=%s title=%s sub=%s', post.url, post.title, post.subreddit)

                    # post it!
                    embed = discord.Embed(title=post.title, url=post.url, description=post.selftext)
                    embed.set_author(name='/r/%s \N{EM DASH} /u/%s' % (post.subreddit, post.author))
                    if is_image:
                        embed.set_image(url=post.url)
                    await channel.send(embed=embed)
            await asyncio.sleep(60 * 10)

    @commands.group()
    @commands.guild_only()
    @checks.is_moderator()
    async def reddit(self, ctx):
        """
        This command group contains all commands related to reddit.

        Feeds will be updated every 10 minutes. Both self and link posts will be posted to the channel. NSFW posts will
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
            records = await conn.fetch('SELECT * FROM reddit_feeds WHERE guild_id = $1', ctx.guild.id)
            if not records:
                return await ctx.send('No feeds found! Set one up with `d?reddit watch <channel> <subreddit>`. See `d?help '
                                      'reddit watch` for more information.')
            text = '\n'.join(['\N{BULLET} <#{}> (/r/{})'.format(r['channel_id'], r['subreddit']) for r in records])
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
