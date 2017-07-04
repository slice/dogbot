"""
Dogbot owner only music extension.
"""

import asyncio
import logging
import random

import discord
import youtube_dl
from discord.ext import commands

from dog import Cog
from dog.core import utils

logger = logging.getLogger(__name__)

YTDL_OPTS = {
    'format': 'webm[abr>0]/bestaudio/best',
    'prefer_ffmpeg': True
}

SEARCHING_TEXT = (
    'Beep boop...',
    'Travelling the interwebs...',
    'Hold up...',
    'Searching...',
    'Just a sec...'
)


class YouTubeDLSource(discord.FFmpegPCMAudio):
    def __init__(self, url):
        ytdl = youtube_dl.YoutubeDL(YTDL_OPTS)
        info = ytdl.extract_info(url, download=False)

        if '_type' in info and info['_type'] == 'playlist':
            info = info['entries'][0]

        self.url = url
        self.info = info

        super().__init__(info['url'])


async def youtube_search(bot, query: str) -> 'List[Dict[Any, Any]]':
    """
    Searches YouTube for videos. Returns a list of :class:`YouTubeResult`.
    """
    def search():
        ytdl = youtube_dl.YouTubeDL(YTDL_OPTS)
        info = ytdl.extract_info('ytsearch:' + query, download=False)
        return info
    return await bot.loop.run_in_executor(None, search)


async def must_be_in_voice(ctx: commands.Context):
    return ctx.guild.voice_client is not None


async def cannot_be_playing(ctx: commands.Context):
    return not ctx.guild.voice_client.is_playing()


async def is_whitelisted(bot, guild: discord.Guild):
    async with bot.pgpool.acquire() as conn:
        record = await conn.fetchrow('SELECT * FROM music_guilds WHERE guild_id = $1', guild.id)
        return record is not None


async def can_use_music(ctx: commands.Context):
    return await ctx.bot.is_owner(ctx.author) or (False if not ctx.guild else await is_whitelisted(ctx.bot, ctx.guild))


class Music(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self.queues = {}

    @commands.group(aliases=['m', 'mus'])
    @commands.check(can_use_music)
    async def music(self, ctx):
        """ Music. Beep boop! """
        pass

    @music.command()
    @commands.is_owner()
    async def status(self, ctx):
        """ Views the status of Opus. """
        await ctx.send(f'Opus status: {discord.opus.is_loaded()}')

    @music.command(aliases=['summon'])
    async def join(self, ctx):
        """ Summons the bot to your voice channel. """
        msg = await ctx.send('\N{RUNNER} Connecting to voice...')
        if ctx.guild.voice_client is not None and ctx.guild.voice_client.is_connected():
            return await msg.edit(content='\N{CONFUSED FACE} I\'m already connected!')
        if ctx.author.voice is None:
            return await msg.edit(content='\N{CONFUSED FACE} I can\'t join you if you aren\'t in a voice channel!')
        await ctx.author.voice.channel.connect()
        await msg.edit(content='\N{OK HAND SIGN} Connected!')

    @music.command()
    @commands.check(must_be_in_voice)
    async def skip(self, ctx):
        """ Skips this song. """
        queue = self.queues.get(ctx.guild.id, [])
        if queue:
            await ctx.send('Skipping...! I\'ll play **{0.info[title]}** next.'.format(queue[0].original))
        else:
            await ctx.ok()

        ctx.guild.voice_client.stop()

    @music.command()
    @commands.check(must_be_in_voice)
    async def stop(self, ctx):
        """ Stops playing music and empties the queue. """
        self.queues[ctx.guild.id] = []
        ctx.guild.voice_client.stop()
        await ctx.ok('\N{BLACK SQUARE FOR STOP}')

    @music.command()
    @commands.check(must_be_in_voice)
    async def pause(self, ctx):
        """ Pauses the music. """
        ctx.guild.voice_client.pause()
        await ctx.ok('\N{DOUBLE VERTICAL BAR}')

    @music.command()
    @commands.check(must_be_in_voice)
    async def leave(self, ctx):
        """ Leaves the voice channel. """
        await ctx.guild.voice_client.disconnect()
        await ctx.ok()

    @music.command(aliases=['vol'])
    @commands.check(must_be_in_voice)
    async def volume(self, ctx, vol: float = None):
        """ Changes the volume. """
        if not vol:
            await ctx.send('The volume is: `{}`'.format(ctx.guild.voice_client.source.volume))
            return
        ctx.guild.voice_client.source.volume = vol
        await ctx.ok()

    @music.command(aliases=['np'])
    @commands.check(must_be_in_voice)
    async def now_playing(self, ctx):
        """ Shows what's playing. """
        if not ctx.guild.voice_client.is_playing():
            return await ctx.send('Nothing\'s playing at the moment.')
        src = ctx.guild.voice_client.source.original
        await ctx.send('**Now playing:** {0.info[title]} {0.info[webpage_url]}'.format(src))

    @music.command()
    @commands.check(must_be_in_voice)
    async def resume(self, ctx):
        """ Resumes the music. """
        ctx.guild.voice_client.resume()
        await ctx.ok('\N{BLACK RIGHT-POINTING TRIANGLE}')

    def advance(self, ctx: commands.Context, error):
        if error:
            print(error)

        queue = self.queues.get(ctx.guild.id, [])

        logger.info('advancing -- queue: %s', [s.original.url for s in queue])

        if not queue:
            logger.info('queue is empty')
            return

        logger.info('queue isn\'t empty, advancing...')
        next_up = queue.pop(0)
        logger.info('next up -- %s', next_up)

        # send message
        coro = ctx.send('**Next up!** {0.info[title]} (<{0.info[webpage_url]}>)'.format(next_up.original))
        fut = asyncio.run_coroutine_threadsafe(coro, ctx.bot.loop)
        fut.result()
        
        ctx.guild.voice_client.play(next_up, after=lambda e: self.advance(ctx, e))
        self.queues[ctx.guild.id] = queue

    async def _play(self, ctx, url, *, search=False):
        msg = await ctx.send(f'\N{INBOX TRAY} {random.choice(SEARCHING_TEXT)}')

        # grab
        url = 'ytsearch:' + url if search else url
        try:
            source = await ctx.bot.loop.run_in_executor(None, YouTubeDLSource, url)
        except youtube_dl.DownloadError:
            return await msg.edit(content='\U0001f4ed YouTube gave me nothin\'.')

        # make it adjustable
        source = discord.PCMVolumeTransformer(source, 1.0)
        disp = '**{}**'.format(source.original.info['title'])

        if not ctx.guild.voice_client.is_playing():
            # play immediately since we're not playing anything
            ctx.guild.voice_client.play(source, after=lambda e: self.advance(ctx, e))
            await msg.edit(content=f'\N{MULTIPLE MUSICAL NOTES} Playing {disp}!')
        else:
            # add it to the queue
            self.queues[ctx.guild.id] = self.queues.get(ctx.guild.id, []) + [source]
            await msg.edit(content=f'\N{LINKED PAPERCLIPS} Added {disp} to queue.')

    @music.command()
    async def queue(self, ctx):
        """ Views the queue. """
        queue = self.queues.get(ctx.guild.id, [])

        if not queue:
            await ctx.send('\N{SPIDER WEB} Queue is empty.')
        else:
            header = 'There are **{many}** item(s) in the queue. Run `d?m np` to view the currently playing song.\n\n'
            format = '{index}) {source.original.info[title]} (<{source.original.info[webpage_url]}>)'
            lst = '\n'.join([format.format(index=index + 1, source=source) for index, source in enumerate(queue)])
            await ctx.send(header.format(many=len(queue)) + lst)

    @music.command()
    @commands.check(must_be_in_voice)
    @commands.is_owner()
    async def multiqueue(self, ctx, *urls):
        """ Queues multiple URLs. """
        for url in urls:
            await self._play(ctx, url)

    @music.command(aliases=['p'])
    @commands.check(must_be_in_voice)
    async def play(self, ctx, *, query: str):
        """
        Plays music.

        You can specify a query to search for, or a URL.
        """
        try:
            await self._play(ctx, query, search='http' not in query)
        except:
            logger.exception('Error occurred searching.')
            await ctx.send('\N{UPSIDE-DOWN FACE} An error occurred fetching that URL. Sorry!')


def setup(bot):
    bot.add_cog(Music(bot))
