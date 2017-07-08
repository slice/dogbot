"""
Dogbot owner only music extension.
"""

import asyncio
import logging
import random

import discord
import functools
import youtube_dl
from discord.ext import commands

from dog import Cog
from dog.core import checks
from dog.core.errors import MustBeInVoice

TIMEOUT = 60 * 4  # 4 minutes
VIDEO_DURATION_LIMIT = 420  # 7 minutes

logger = logging.getLogger(__name__)

YTDL_OPTS = {
    'format': 'webm[abr>0]/bestaudio/best',
    'prefer_ffmpeg': True,
    'noplaylist': True,
    'nocheckcertificate': True
}

ytdl = youtube_dl.YoutubeDL(YTDL_OPTS)

SEARCHING_TEXT = (
    'Beep boop...',
    'Searching...',
    'Just a sec...'
)

FFMPEG_OPTIONS = {
    'before_options': '-nostdin',
    'options': '-vn'  # disable video
}


class YouTubeError(commands.CommandError):
    pass


class YouTubeDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, info):
        super().__init__(source, 1.0)
        self.info = info
        self.title = info.get('title')
        self.url = info.get('url')

    @classmethod
    async def create(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()

        future = loop.run_in_executor(None, functools.partial(ytdl.extract_info, url, download=False))
        # the extract_info call won't stop but w/e
        try:
            info = await asyncio.wait_for(future, 7, loop=loop)
        except asyncio.TimeoutError:
            raise YouTubeError('That took too long to fetch! Make sure you aren\'t playing playlists \N{EM DASH} '
                               'those take too long to process!')

        # grab the first entry in the playlist
        if '_type' in info and info['_type'] == 'playlist':
            info = info['entries'][0]

        # check if it's too long
        if info['duration'] >= VIDEO_DURATION_LIMIT:
            min = VIDEO_DURATION_LIMIT / 60
            raise YouTubeError('That video is too long! The maximum video duration is **{} minutes**.'.format(min))

        return cls(discord.FFmpegPCMAudio(info['url'], **FFMPEG_OPTIONS), info)


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
    if not ctx.guild:
        return False
    if ctx.guild.voice_client is None:
        raise MustBeInVoice
    return True


async def is_whitelisted(bot, guild: discord.Guild):
    async with bot.pgpool.acquire() as conn:
        record = await conn.fetchrow('SELECT * FROM music_guilds WHERE guild_id = $1', guild.id)
        return record is not None


async def can_use_music(ctx: commands.Context):
    return await ctx.bot.is_owner(ctx.author) or (False if not ctx.guild else await is_whitelisted(ctx.bot, ctx.guild))


def required_votes(number_of_people: int) -> int:
    return max(round(number_of_people / 2.5), 1)


class Music(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self.queues = {}
        self.skip_votes = {}
        self.leave_tasks = {}

        self.looping_lock = asyncio.Lock()
        self.looping = {}

    async def __error(self, ctx, err):
        if isinstance(err, MustBeInVoice):
            await ctx.send('I need to be in a voice channel to do that. To connect me, type `d?m join`.')
            err.should_suppress = True

    async def on_voice_state_update(self, member, before, after):
        if not member.guild.voice_client or not member.guild.voice_client.channel:
            return
        vc = member.guild.voice_client
        my_channel = vc.channel

        logger.debug('There are now %d people in this voice channel.', len(my_channel.members))

        if len(my_channel.members) == 1:
            if not vc.is_paused():
                logger.debug('Automatically pausing stream.')
                vc.pause()
            async def leave():
                await asyncio.sleep(TIMEOUT)  # 5 minutes
                if vc.is_connected():
                    # XXX: have to unpause before disconnecting or else ffmpeg never dies
                    if vc.is_paused():
                        vc.resume()
                    logger.debug('Automatically disconnecting from guild %d.', member.guild.id)
                    await vc.disconnect()
            if member.guild.id in self.leave_tasks:
                logger.debug('I got moved to another empty channel, and I already have a leave task. Ignoring!')
                return
            logger.debug('Nobody\'s in this voice channel! Creating a leave task.')
            self.leave_tasks[member.guild.id] = self.bot.loop.create_task(leave())
        else:
            logger.debug('Yay, someone rejoined!')
            if vc.is_paused():
                logger.debug('Automatically unpausing.')
                vc.resume()
            if member.guild.id in self.leave_tasks:
                self.leave_tasks[member.guild.id].cancel()
                del self.leave_tasks[member.guild.id]
                logger.debug('Cancelling leave task for guild %d.', member.guild.id)

    @commands.group(aliases=['m', 'mus'])
    @commands.guild_only()
    async def music(self, ctx):
        """ Music. Beep boop! """
        pass

    @music.command()
    @commands.is_owner()
    async def status(self, ctx):
        """ Views the status of voice clients. """
        embed = discord.Embed(title='Voice status', color=discord.Color.blurple())

        clients = len(ctx.bot.voice_clients)
        idle = sum(1 for cl in ctx.bot.voice_clients if not cl.is_playing())
        paused = sum(1 for cl in ctx.bot.voice_clients if cl.is_paused())
        active = sum(1 for cl in ctx.bot.voice_clients if cl.is_playing())
        embed.description = '{} client(s)\n{} idle, {} active, {} paused'.format(clients, idle, active, paused)

        await ctx.send(embed=embed)

    @music.command(aliases=['summon'])
    async def join(self, ctx):
        """ Summons the bot to your voice channel. """
        msg = await ctx.send('\N{RUNNER} Connecting to voice...')
        if ctx.guild.voice_client is not None and ctx.guild.voice_client.is_connected():
            return await msg.edit(content='\N{CONFUSED FACE} I\'m already connected!')
        if ctx.author.voice is None:
            return await msg.edit(content='\N{CONFUSED FACE} I can\'t join you if you aren\'t in a voice channel!')

        ch = ctx.author.voice.channel

        if not ctx.guild.me.permissions_in(ch).connect:
            return await msg.edit(content='\N{LOCK} I can\'t connect to that channel.')

        try:
            await ch.connect()
        except asyncio.TimeoutError:
            await msg.edit(content='\N{ALARM CLOCK} Couldn\'t connect, I took too long to reach Discord\'s servers.')
            logger.warning('Timed out while connecting to Discord\'s voice servers.')
        except discord.ClientException:
            await msg.edit(content='\N{CONFUSED FACE} I\'m already connected.')
            logger.warning('I couldn\'t detect being connected.')
        else:
            await msg.edit(content='\N{OK HAND SIGN} Connected!')

    @music.command()
    @checks.is_moderator()
    @commands.check(must_be_in_voice)
    async def loop(self, ctx):
        """
        Toggles looping of the current song.

        Only Dogbot Moderators can do this.
        """
        enabled = ctx.guild.id in self.looping

        if not ctx.guild.voice_client.is_playing():
            return await ctx.send('Play something first!')

        if not enabled:
            title = ctx.guild.voice_client.source.info['title']
            await ctx.send('Okay. I\'ll loop **{title}** from now on, until you run `d?m loop` again.'.format(
                title=title))

            async with self.looping_lock:
                self.looping[ctx.guild.id] = ctx.guild.voice_client.source.info
            logger.debug('Enabled looping for guild %d.', ctx.guild.id)
        else:
            await ctx.send('Alright, I turned off looping.')
            if ctx.guild.id in self.looping:
                async with self.looping_lock:
                    del self.looping[ctx.guild.id]
                logger.debug('Disabled looping for guild %d.', ctx.guild.id)

    @music.command()
    @commands.check(must_be_in_voice)
    async def skip(self, ctx):
        """
        Votes to skip this song.

        40% of users in the voice channel must skip in order for the song to be skipped.
        If someone leaves the voice channel, just rerun this command to recalculate the amount
        of votes needed.

        If you are a Dogbot Moderator, the song is skipped instantly.
        """

        if not ctx.guild.voice_client.is_playing():
            return await ctx.send('I\'m not playing anything at the moment.')

        async def insta_skip():
            # clear voteskips
            self.skip_votes[ctx.guild.id] = []

            # get the next song, say it
            queue = self.queues.get(ctx.guild.id, [])
            if queue:
                await ctx.send('Skipping...! I\'ll play **{0.title}** next.'.format(queue[0]))
            else:
                await ctx.send('Skipping!')

            # stop!!!
            ctx.guild.voice_client.stop()

        if checks.is_dogbot_moderator(ctx):
            logger.debug('Instantly skipping.')
            await insta_skip()
        else:
            existing_votes = self.skip_votes.get(ctx.guild.id, [])  # votes we already have
            voice_members = len(ctx.guild.voice_client.channel.members)  # how many people in the channel?
            votes_with_this_one = len(existing_votes) + 1  # votes with this one counted
            required = required_votes(voice_members)  # how many votes do we need?

            # recalculate amount of users it takes to vote, not counting this vote.
            # (just in case someone left the channel)
            if len(existing_votes) >= required:
                logger.debug('Voteskip: Recalculated. Skipping. %d/%d', len(existing_votes), required)
                return await insta_skip()

            # check if they already voted
            if ctx.author.id in existing_votes:
                return await ctx.send('You already voted to skip. **{}** more vote(s) needed to skip.'.format(required -
                                      len(existing_votes)))

            # ok, their vote counts. now check if we surpass required votes with this vote!
            if votes_with_this_one >= required:
                logger.debug('Voteskip: Fresh vote! Skipping. %d/%d', votes_with_this_one, required)
                return await insta_skip()

            # add the vote
            self.skip_votes[ctx.guild.id] = existing_votes + [ctx.author.id]

            # how many more?
            more_votes = required - votes_with_this_one
            await ctx.send('Your request to skip this song has been acknowledged. **{}** more vote(s) to '
                           'skip.'.format(more_votes))

            logger.debug('Voteskip: Now at %d/%d (%d more needed to skip.)', votes_with_this_one, required, more_votes)

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
    async def volume(self, ctx, vol: int = None):
        """
        Changes or views the volume.

        If you provide a number from 0-200, the volume will be set. Otherwise, you will
        view the current volume.
        """
        if not ctx.guild.voice_client.is_playing():
            return await ctx.send('You can\'t adjust the volume of silence.')

        if not vol:
            return await ctx.send('The volume is at: `{}%`'.format(ctx.guild.voice_client.source.volume * 100))

        if vol > 200:
            return await ctx.send('You can\'t set the volume over 200%.')

        ctx.guild.voice_client.source.volume = vol / 100
        await ctx.ok()

    @music.command(aliases=['np'])
    @commands.check(must_be_in_voice)
    async def now_playing(self, ctx):
        """ Shows what's playing. """
        if not ctx.guild.voice_client.is_playing():
            return await ctx.send('Nothing\'s playing at the moment.')
        src = self.looping[ctx.guild.id] if ctx.guild.id in self.looping else \
            ctx.guild.voice_client.source.info

        minutes, seconds = divmod(src['duration'], 60)
        await ctx.send('**Now playing:** {0[title]} {0[webpage_url]} ({1:02d}:{2:02d})'.format(src, minutes, seconds))

    @music.command(aliases=['unpause'])
    @commands.check(must_be_in_voice)
    async def resume(self, ctx):
        """ Resumes the music. """
        ctx.guild.voice_client.resume()
        await ctx.ok('\N{BLACK RIGHT-POINTING TRIANGLE}')

    def advance(self, ctx: commands.Context, error):
        if error:
            print(error)

        logger.debug('Clearing voteskips for %d.', ctx.guild.id)
        # clear voteskips
        self.skip_votes[ctx.guild.id] = []

        queue = self.queues.get(ctx.guild.id, [])
        looping = ctx.guild.id in self.looping

        logger.debug('Advancing to the next song. Queue: %s', [s.url for s in queue])

        if not queue and not looping:
            logger.debug('Queue is empty. Just going to sit here.')
            return

        if looping:
            logger.debug('Looping has been enabled, taking the saved URL.')
            src = self.looping[ctx.guild.id]['url']
            logger.debug('Looping %s.', src)
            next_up = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(src))
        else:
            logger.debug('Popping queue.')
            next_up = queue.pop(0)
            logger.debug('Next up! %s', next_up)

        # send message
        if not looping:
            coro = ctx.send('**Next up!** {0.title} (<{0.info[webpage_url]}>)'.format(next_up))
            fut = asyncio.run_coroutine_threadsafe(coro, ctx.bot.loop)
            fut.result()

        try:
            ctx.guild.voice_client.play(next_up, after=lambda e: self.advance(ctx, e))
        except AttributeError:
            # probably got kicked /shrug
            logger.warning('Unable to play, probably got kicked from the channel. Ignoring.')
        self.queues[ctx.guild.id] = queue

    async def _play(self, ctx, url, *, search=False):
        msg = await ctx.send(f'\N{INBOX TRAY} {random.choice(SEARCHING_TEXT)}')

        # grab
        url = 'ytsearch:' + url if search else url
        try:
            source = await YouTubeDLSource.create(url, loop=ctx.bot.loop)
        except youtube_dl.DownloadError:
            return await msg.edit(content='\U0001f4ed YouTube gave me nothin\'.')
        except YouTubeError as yterr:
            return await msg.edit(content='\N{CROSS MARK} {}'.format(yterr))

        disp = '**{}**'.format(source.title)

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
            format = '{index}) {source.title} (<{source.info[webpage_url]}>)'
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
