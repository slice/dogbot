from collections import namedtuple
import logging
import aiohttp
import youtube_dl
import discord
from bs4 import BeautifulSoup
from discord.ext import commands
from dog import Cog, utils

YouTubeResult = namedtuple('YouTubeResult', 'name url')
logger = logging.getLogger(__name__)

class YouTubeDLSource(discord.FFmpegPCMAudio):
    def __init__(self, url):
        opts = {
            'format': 'webm[abr>0]/bestaudio/best',
            'prefer_ffmpeg': True,
        }

        self.url = url

        ytdl = youtube_dl.YoutubeDL(opts)
        info = ytdl.extract_info(url, download=False)
        super().__init__(info['url'])

async def youtube_search(query):
    query_escaped = utils.urlescape(query)
    url = f'https://www.youtube.com/results?q={query_escaped}'
    watch = 'https://www.youtube.com{}'

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            soup = BeautifulSoup(text, 'html.parser')
            nodes = soup.find_all('a', {'class': 'yt-uix-tile-link'})
            return [YouTubeResult(name=n.contents[0],
                    url=watch.format(n['href'])) for n in nodes]

class Music(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self.queues = {}

    @commands.group(aliases=['m', 'mus'])
    @commands.is_owner()
    async def music(self, ctx):
        """ Music bot! Owner only. """
        pass

    async def must_be_in_voice(ctx):
        return ctx.guild.voice_client is not None

    async def cannot_be_playing(ctx):
        return not ctx.guild.voice_client.is_playing()

    @music.command()
    async def status(self, ctx):
        """ Views the status of Opus. """
        await ctx.send(f'Opus status: {discord.opus.is_loaded()}')

    @music.command(aliases=['summon'])
    async def join(self, ctx):
        """ Summons the bot to your voice channel. """
        msg = await ctx.send('\N{RUNNER} Connecting to voice...')
        if ctx.guild.voice_client is not None and ctx.guild.voice_client.is_connected():
            return await msg.edit(content='\N{CONFUSED FACE} I\'m already connected!')
        await ctx.author.voice.channel.connect()
        await msg.edit(content='\N{OK HAND SIGN}')

    @music.command()
    @commands.check(must_be_in_voice)
    async def skip(self, ctx):
        """ Skips this song. """
        ctx.guild.voice_client.stop()
        await self.bot.ok(ctx, '\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE}')

    @music.command()
    @commands.check(must_be_in_voice)
    async def stop(self, ctx):
        """ Stops playing music and empties the queue. """
        self.queues[ctx.guild.id] = []
        ctx.guild.voice_client.stop()
        await self.bot.ok(ctx, '\N{BLACK SQUARE FOR STOP}')

    @music.command()
    @commands.check(must_be_in_voice)
    async def pause(self, ctx):
        """ Pauses the music. """
        ctx.guild.voice_client.pause()
        await self.bot.ok(ctx, '\N{DOUBLE VERTICAL BAR}')

    @music.command()
    @commands.check(must_be_in_voice)
    async def resume(self, ctx):
        """ Resumes the music. """
        ctx.guild.voice_client.resume()
        await self.bot.ok(ctx, '\N{BLACK RIGHT-POINTING TRIANGLE}')

    def advance(self, ctx, error):
        if error:
            print(error)

        queue = self.queues.get(ctx.guild.id, [])

        logger.info('advancing -- queue: %s', queue)

        if not queue:
            logger.info('queue is empty')
            return

        logger.info('queue isn\'t empty, advancing...')
        next_up = queue.pop(0)
        logger.info('next up -- %s', next_up)
        ctx.guild.voice_client.play(next_up, after=lambda e: self.advance(ctx, e))
        self.queues[ctx.guild.id] = queue

    async def _play_yt(self, ctx, url):
        msg = await ctx.send('\N{GEAR} Fetching information...')
        source = YouTubeDLSource(url)

        if not ctx.guild.voice_client.is_playing():
            # play immediately since we're not playing anything
            ctx.guild.voice_client.play(source, after=lambda e: self.advance(ctx, e))
            await msg.edit(content='\N{MULTIPLE MUSICAL NOTES} Playing!')
        else:
            # add it to the queue
            queue = self.queues.get(ctx.guild.id, [])
            queue.append(source)
            self.queues[ctx.guild.id] = queue
            await msg.edit(content='\N{WHITE HEAVY CHECK MARK} Added to queue.')

    @music.command()
    async def queue(self, ctx):
        """ Views the queue. """
        queue = self.queues.get(ctx.guild.id, [])

        if not queue:
            await ctx.send('\N{SPIDER WEB} Queue is empty.')
        else:
            lst = '\n'.join([f'\N{BULLET} <{s.url}>' for s in queue])
            await ctx.send(lst)

    @music.command()
    @commands.check(must_be_in_voice)
    async def search(self, ctx, *, query: str):
        """ Searches YouTube for videos. """
        results = (await youtube_search(query))[:5]

        if len(results) > 1:
            lst = '\n'.join([f'{idx + 1}) **{utils.truncate(r.name, 50)}**'
                            for idx, r in enumerate(results)])
            await ctx.send(f'Pick one, or `cancel`.\n\n{lst}')
            while True:
                msg = await self.bot.wait_for_response(ctx)

                if msg.content == 'cancel':
                    return

                num = int(msg.content)

                if num < 1 or num > len(results):
                    await ctx.send('\N{PENSIVE FACE} Invalid choice.')
                else:
                    link = results[num - 1]
                    break
        else:
            link = results[0]

        await self._play_yt(ctx, link.url)

    @music.command()
    @commands.check(must_be_in_voice)
    async def multiqueue(self, ctx, *urls):
        """ Queues multiple URLs. """
        for url in urls:
            await self._play_yt(ctx, url)

    @music.command()
    @commands.check(must_be_in_voice)
    async def play(self, ctx, url: str):
        """ Plays a URL. """
        try:
            await self._play_yt(ctx, url)
        except:
            await ctx.send('\N{UPSIDE-DOWN FACE} An error occurred fetching '
                           'that URL. Sorry!')

def setup(bot):
    bot.add_cog(Music(bot))
