import asyncio
import audioop
import functools
from asyncio import TimeoutError

import youtube_dl
from discord import PCMVolumeTransformer, FFmpegPCMAudio

from .constants import VIDEO_DURATION_LIMIT, FFMPEG_OPTIONS, YTDL_OPTS
from .errors import YouTubeError

ytdl = youtube_dl.YoutubeDL(YTDL_OPTS)


class VolumeTransformer(PCMVolumeTransformer):
    """An uncapped :class:`discord.PCMVolumeTransformer`."""

    def read(self):
        ret = self.original.read()
        return audioop.mul(ret, 2, self._volume)


class YouTubeDLSource(VolumeTransformer):
    def __init__(self, source, info):
        super().__init__(source, 1.0)

        self.info = info
        self.title = info.get('title')
        self.url = info.get('url')

    @classmethod
    async def create(cls, url, bot):
        # extract info future
        future = bot.loop.run_in_executor(None,
                                          functools.partial(
                                              ytdl.extract_info,
                                              url,
                                              download=False))

        # the extract_info call won't stop but w/e
        try:
            info = await asyncio.wait_for(future, 12, loop=bot.loop)
        except TimeoutError:
            raise YouTubeError(
                'That took too long to fetch! Reminder: Playlists are not supported.'
            )

        # grab the first entry in the playlist
        if '_type' in info and info['_type'] == 'playlist':
            info = info['entries'][0]

        # check duration of video
        if info['duration'] >= VIDEO_DURATION_LIMIT:
            min = VIDEO_DURATION_LIMIT / 60
            raise YouTubeError(
                'That video is too long! The maximum video duration is **{} minutes**.'.
                format(min))

        executable = 'avconv' if 'docker' in bot.cfg else 'ffmpeg'

        return cls(
            FFmpegPCMAudio(
                info['url'], executable=executable, **FFMPEG_OPTIONS), info)
