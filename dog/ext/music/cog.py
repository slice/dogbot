import asyncio
import logging
import random
from asyncio import TimeoutError

import discord
import youtube_dl
from discord import PCMVolumeTransformer, ClientException
from discord.ext import commands
from discord.ext.commands import guild_only

from dog import Cog
from dog.core import checks
from dog.core.checks import is_bot_admin
from dog.core.context import DogbotContext
from dog.core.errors import MustBeInVoice

from .checks import must_be_in_voice, can_use_music_check
from .constants import TIMEOUT, YTDL_OPTS, SEARCHING_TEXT
from .errors import YouTubeError
from .state import State
from .audio import YouTubeDLSource

log = logging.getLogger(__name__)
ytdl = youtube_dl.YoutubeDL(YTDL_OPTS)


async def youtube_search(bot, query):
    """Searches YouTube for videos. Returns a list of :class:`YouTubeResult`."""

    def search():
        info = ytdl.extract_info('ytsearch:' + query, download=False)
        return info

    return await bot.loop.run_in_executor(None, search)


def required_votes(number_of_people: int) -> int:
    return max(round(number_of_people / 2.5), 1)


class Music(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self.states = {}
        self.leave_tasks = {}

    def state_for(self, guild: discord.Guild):
        """Returns a State instance for a guild. If one does not exist, it is created."""
        if guild.id not in self.states:
            self.states[guild.id] = State(guild)
        return self.states[guild.id]

    async def __error(self, ctx, err):
        if isinstance(err, MustBeInVoice):
            await ctx.send('I need to be in a voice channel to do that. To connect me, type `d?m join`.')
            err.should_suppress = True

    async def on_voice_state_update(self, member, _before, _after):
        # skip if we aren't even connected
        if not member.guild.voice_client or not member.guild.voice_client.channel:
            return

        vc = member.guild.voice_client
        my_channel = vc.channel

        log.debug('There are now %d people in this voice channel.', len(my_channel.members))

        if len(my_channel.members) == 1:
            if not vc.is_paused():
                log.debug('Automatically pausing stream.')
                vc.pause()

            # task that waits a bit, then disconnects if we are still connected in order to save resources
            async def leave():
                await asyncio.sleep(TIMEOUT)  # 5 minutes
                if vc.is_connected():
                    # XXX: have to unpause before disconnecting or else ffmpeg never dies
                    if vc.is_paused():
                        vc.resume()
                    log.debug('Automatically disconnecting from guild %d.', member.guild.id)
                    await vc.disconnect()

            if member.guild.id in self.leave_tasks:
                log.debug('I got moved to another empty channel, and I already have a leave task. Ignoring!')
                return

            log.debug('Nobody\'s in this voice channel! Creating a leave task.')
            self.leave_tasks[member.guild.id] = self.bot.loop.create_task(leave())
        else:
            log.debug('Someone has rejoined.')

            # automatically unpause.
            if vc.is_paused():
                log.debug('Automatically unpausing.')
                vc.resume()

            if member.guild.id in self.leave_tasks:
                self.leave_tasks[member.guild.id].cancel()
                del self.leave_tasks[member.guild.id]
                log.debug('Cancelling leave task for guild %d.', member.guild.id)

    @commands.group(aliases=['m'])
    @can_use_music_check()
    @guild_only()
    async def music(self, ctx: DogbotContext):
        """Music. Beep boop!"""
        pass

    @music.command()
    @is_bot_admin()
    async def status(self, ctx: DogbotContext):
        """Views the status of voice clients."""
        embed = discord.Embed(title='Voice status', color=discord.Color.blurple())

        clients = len(ctx.bot.voice_clients)
        idle = sum(1 for cl in ctx.bot.voice_clients if not cl.is_playing())
        paused = sum(1 for cl in ctx.bot.voice_clients if cl.is_paused())
        active = sum(1 for cl in ctx.bot.voice_clients if cl.is_playing())

        embed.description = '{} client(s)\n{} idle, **{} active**, {} paused'.format(clients, idle, active, paused)

        await ctx.send(embed=embed)

    @music.command(aliases=['summon'])
    async def join(self, ctx):
        """Summons the bot to your voice channel."""
        msg = await ctx.send('\N{RUNNER} Connecting to voice...')

        state = self.state_for(ctx.guild)

        # already connected?
        if state.connected:
            return await msg.edit(content='I\'m already playing music in `{}`.'.format(state.channel))

        # can't join if we aren't in a voice channel.
        if ctx.author.voice is None:
            return await msg.edit(content='I can\'t join you if you aren\'t in a voice channel.')

        # the channel that the command invoker is in
        ch = ctx.author.voice.channel

        # check if we can join that channel.
        if not ctx.guild.me.permissions_in(ch).connect:
            return await msg.edit(content='\N{LOCK} I can\'t connect to that channel.')

        try:
            log.debug('Connecting to %s.', ch)
            await ch.connect()
        except TimeoutError:
            await msg.edit(content='\N{ALARM CLOCK} Couldn\'t connect, I took too long to reach Discord\'s servers.')
            log.warning('Timed out while connecting to Discord\'s voice servers.')
        except ClientException:
            await msg.edit(content='\N{CONFUSED FACE} I\'m already connected.')
            log.warning('I couldn\'t detect being connected.')
        else:
            await msg.edit(content='\N{OK HAND SIGN} Connected!')

    @music.command()
    @checks.is_moderator()
    @commands.check(must_be_in_voice)
    async def loop(self, ctx: DogbotContext):
        """
        Toggles looping of the current song.

        Only Dogbot Moderators can do this.
        """
        state = self.state_for(ctx.guild)

        if not state.looping:
            await ctx.send('Okay. I\'ll repeat songs once they finish playing.')
            state.looping = True
            log.debug('Enabled looping for guild %d.', ctx.guild.id)
        else:
            await ctx.send('Okay, I turned off looping. The queue will proceed as normal.')
            state.looping = False
            log.debug('Disabled looping for guild %d.', ctx.guild.id)

    @music.command()
    @commands.check(must_be_in_voice)
    async def skip(self, ctx: DogbotContext):
        """
        Votes to skip this song.

        40% of users in the voice channel must skip in order for the song to be skipped.
        If someone leaves the voice channel, just rerun this command to recalculate the amount
        of votes needed.

        If you are a Dogbot Moderator, the song is skipped instantly.
        """

        state = self.state_for(ctx.guild)

        if not state.is_playing():
            return await ctx.send('I\'m not playing anything at the moment.')

        # if the command invoker is a moderator, instantly skip.
        if checks.member_is_moderator(ctx.author):
            log.debug('Instantly skipping.')
            state.skip()
            return

        state = self.state_for(ctx.guild)
        existing_votes = state.skip_votes
        voice_members = len(state.channel.members)  # how many people in the channel?
        votes_with_this_one = len(existing_votes) + 1  # votes with this one counted
        required = required_votes(voice_members)  # how many votes do we need?

        # recalculate amount of users it takes to vote, not counting this vote.
        # (just in case someone left the channel)
        if len(existing_votes) >= required:
            log.debug('Voteskip: Recalculated. Skipping. %d/%d', len(existing_votes), required)
            state.skip()
            return

        # check if they already voted
        if ctx.author.id in existing_votes:
            return await ctx.send(
                'You already voted to skip. **{}** more vote(s) needed to skip.'.format(
                    required - len(existing_votes)
                )
            )

        # ok, their vote counts. now check if we surpass required votes with this vote!
        if votes_with_this_one >= required:
            log.debug('Voteskip: Fresh vote! Skipping. %d/%d', votes_with_this_one, required)
            state.skip()
            return

        # add the vote
        state.skip_votes.append(ctx.author.id)

        # how many more?
        more_votes = required - votes_with_this_one
        await ctx.send(
            'Your request to skip this song has been acknowledged. '
            '**{}** more vote(s) are required to skip.'.format(more_votes)
        )

        log.debug('Voteskip: Now at %d/%d (%d more needed to skip.)', votes_with_this_one, required, more_votes)

    @music.command()
    @commands.check(must_be_in_voice)
    async def stop(self, ctx: DogbotContext):
        """Stops playing music and empties the queue."""
        self.state_for(ctx.guild).queue = []
        ctx.guild.voice_client.stop()
        await ctx.ok('\N{BLACK SQUARE FOR STOP}')

    @music.command()
    @commands.check(must_be_in_voice)
    async def pause(self, ctx: DogbotContext):
        """Pauses the music."""
        ctx.guild.voice_client.pause()
        await ctx.ok('\N{DOUBLE VERTICAL BAR}')

    @music.command()
    @commands.check(must_be_in_voice)
    async def leave(self, ctx: DogbotContext):
        """Leaves the voice channel."""
        await ctx.guild.voice_client.disconnect()
        await ctx.ok()

    @music.command(aliases=['vol'])
    @commands.check(must_be_in_voice)
    async def volume(self, ctx, vol: int = None):
        """
        Changes or views the volume.

        If you provide a number, the volume will be set. Otherwise, you will
        view the current volume.
        """
        if not ctx.guild.voice_client.is_playing():
            return await ctx.send('You can\'t adjust the volume of silence.')

        if not vol:
            return await ctx.send('The volume is at: `{}%`'.format(ctx.guild.voice_client.source.volume * 100))

        ctx.guild.voice_client.source.volume = vol / 100
        await ctx.ok()

    @music.command(aliases=['np'])
    @commands.check(must_be_in_voice)
    async def now_playing(self, ctx):
        """Shows what's playing."""
        if not ctx.guild.voice_client.is_playing():
            return await ctx.send('Nothing\'s playing at the moment.')

        state = self.state_for(ctx.guild)
        src = state.to_loop if isinstance(state.vc.source, PCMVolumeTransformer) else state.vc.source.info

        minutes, seconds = divmod(src['duration'], 60)
        await ctx.send('**Now playing:** {0[title]} {0[webpage_url]} ({1:02d}:{2:02d})'.format(src, minutes, seconds))

    @music.command(aliases=['unpause'])
    @commands.check(must_be_in_voice)
    async def resume(self, ctx: DogbotContext):
        """Resumes the music."""
        ctx.guild.voice_client.resume()
        await ctx.ok('\N{BLACK RIGHT-POINTING TRIANGLE}')

    async def _play(self, ctx: DogbotContext, url, *, search=False):
        msg = await ctx.send(f'\N{INBOX TRAY} {random.choice(SEARCHING_TEXT)}')

        # grab the source
        url = 'ytsearch:' + url if search else url
        try:
            source = await YouTubeDLSource.create(url, ctx.bot)
        except youtube_dl.DownloadError:
            return await msg.edit(content='\U0001f4ed YouTube gave me nothing.')
        except YouTubeError as yterr:
            return await msg.edit(content='\N{CROSS MARK} ' + str(yterr))

        disp = '**{}**'.format(source.title)

        state = self.state_for(ctx.guild)

        if state.is_playing():
            # add it to the queue
            log.debug('Adding to queue.')
            state.queue.append(source)
            await msg.edit(content=f'\N{LINKED PAPERCLIPS} Added {disp} to queue.')
        else:
            # play immediately since we're not playing anything
            log.debug('Playing immediately.')
            state.play(source)
            await msg.edit(content=f'\N{MULTIPLE MUSICAL NOTES} Playing {disp}.')

    @music.command()
    async def queue(self, ctx: DogbotContext):
        """Views the queue."""
        queue = self.state_for(ctx.guild).queue
        if not queue:
            await ctx.send('Queue is empty.')
        else:
            header = 'There are **{many}** item(s) in the queue. Run `d?m np` to view the currently playing song.\n\n'
            format = '`{index}.` {source.title} (<{source.info[webpage_url]}>)'
            lst = '\n'.join(format.format(index=index + 1, source=source) for index, source in enumerate(queue))
            await ctx.send(header.format(many=len(queue)) + lst)

    @music.command(aliases=['p'])
    @commands.check(must_be_in_voice)
    async def play(self, ctx: DogbotContext, *, query):
        """
        Plays music.

        You can specify a query to search for, or a URL.
        """
        try:
            search = 'http' not in query  # TODO: this can be better
            await self._play(ctx, query, search=search)
        except:
            log.exception('Error occurred searching.')
            await ctx.send('\N{UPSIDE-DOWN FACE} An error has occurred. Sorry!')
