TIMEOUT = 60 * 4  # 4 minutes
VIDEO_DURATION_LIMIT = 60 * 12  # 12 minutes

YTDL_OPTS = {
    'format': 'webm[abr>0]/bestaudio/best',  # best audio
    'prefer_ffmpeg': True,
    'noplaylist': True,
    'nocheckcertificate': True  # ignore certs
}

# searching flavor text
SEARCHING_TEXT = ('Beep boop...', 'Searching...', 'Just a sec...')

# ffmpeg options
FFMPEG_OPTIONS = {
    'options': '-vn'  # disable video
}
