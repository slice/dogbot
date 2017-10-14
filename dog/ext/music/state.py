import logging

from discord import Guild, FFmpegPCMAudio

from .audio import VolumeTransformer, YouTubeDLSource

log = logging.getLogger(__name__)


class State:
    def __init__(self, guild: Guild):
        self.guild: Guild = guild

        self.looping = False
        self.to_loop = None

        # list of user IDs that have voted to skip
        self.skip_votes = []
        self.queue = []

    def advance(self, error=None):
        # uh oh
        if error is not None:
            log.error('State.advance() threw an exception. %s', error)

        # if we are looping and have a song to loop, don't pop the queue. instead, make a ffmpeg source
        # and play that.
        if self.looping and self.to_loop:
            log.debug('Bypassing State.advance() logic, looping %s.', self.to_loop['url'])
            self.play(
                VolumeTransformer(FFmpegPCMAudio(self.to_loop['url']))
            )
            return

        # out of sources in the queue -- oh well.
        if not self.queue:
            log.debug('Out of queue items.')
            return

        # get the latest source in the queue, then play it.
        next_up = self.queue.pop(0)
        self.play(next_up)

    @property
    def vc(self):
        """Returns this guild's voice client."""
        return self.guild.voice_client

    @property
    def channel(self):
        """Returns the channel that I am playing music in."""
        return self.vc.channel

    @property
    def connected(self):
        """Returns whether I am connected to voice chat."""
        return self.vc and self.vc.is_connected()

    def skip(self):
        if not self.vc:
            raise RuntimeError('Cannot State.skip() -- no voice client!')

        # clear the amount of skip votes
        self.skip_votes = []

        self.vc.stop()

    def play(self, source):
        # hm, we got kicked from voice?
        if not self.vc:
            log.debug('Cannot State.play() -- we might have gotten kicked from voice.')
            return

        # if we got a youtube source, make sure to make this the url to loop, if we're looping
        if isinstance(source, YouTubeDLSource):
            log.debug('Setting to-loop information.')
            self.to_loop = source.info

        self.vc.play(source, after=lambda e: self.advance(e))

    def pause(self):
        self.vc.pause()

    def is_playing(self):
        return self.vc and self.vc.is_playing()

    def is_paused(self):
        return self.vc and self.vc.is_paused()

    def resume(self):
        self.vc.resume()
