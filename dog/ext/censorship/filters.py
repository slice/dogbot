import re

import discord

from dog.core import utils
from dog.ext.censorship import CensorshipFilter, CensorType


class ReCensorshipFilter(CensorshipFilter):
    async def does_violate(self, msg: discord.Message) -> bool:
        return self.regex.search(msg.content) is not None


class InviteCensorshipFilter(ReCensorshipFilter):
    censor_type = CensorType.INVITES
    mod_log_description = 'Invite censored'
    regex = re.compile(r'(discordapp\.com/invite|discord\.gg)/([a-zA-Z_\-0-9]+)')


class VideositeCensorshipFilter(ReCensorshipFilter):
    censor_type = CensorType.VIDEOSITES
    mod_log_description = 'Videosite censored'
    regex = re.compile(r'(https?://)?(www\.)?(twitch\.tv|youtube\.com)/(.+)')


media_types = ('png', 'webp', 'jpg', 'jpeg', 'gif', 'gifv', 'tif', 'tiff', 'webm', 'mp4', 'mkv', 'mov', 'avi', 'ogg',
               'ogv', 'wmv')

executable_types = ('exe', 'scr', 'app', 'sh', 'terminal', 'pif', 'application', 'com', 'hta', 'cpl', 'msc', 'jar',
                    'bat', 'cmd', 'vb', 'vbs', 'vbe', 'js', 'jse', 'ws', 'wsf', 'wsc', 'wsh', 'ps1', 'ps1xml', 'ps2',
                    'ps2xml', 'psc1', 'psc2', 'msh', 'msh1', 'msh2', 'mshxml', 'msh1xml', 'msh2xml', 'lnk', 'inf',
                    'scf', 'reg')


def _link_regex(types: 'Tuple[str]') -> str:
    return r'(https?://)?([^ ]+)\.([^ ]+)/([^ ]+)\.(' + '|'.join(types) + ')'


class MediaLinksCensorshipFilter(ReCensorshipFilter):
    censor_type = CensorType.MEDIALINKS
    mod_log_description = 'Image link censored'
    regex = re.compile(_link_regex(media_types))


class ExecutableLinksCensorshipFilter(ReCensorshipFilter):
    censor_type = CensorType.EXECUTABLELINKS
    mod_log_description = 'Link to executable file censored'
    regex = re.compile(_link_regex(executable_types))


class ZalgoCensorshipFilter(CensorshipFilter):
    censor_type = CensorType.ZALGO
    mod_log_description = 'Zalgo censored'

    async def does_violate(self, msg: discord.Message) -> bool:
        return any([glyph in msg.content for glyph in utils.zalgo_glyphs])
