import discord

from dog.ext.censorship.enums import CensorType


class CensorshipFilter:
    censor_type: CensorType = None
    mod_log_description: str = 'Message censored'

    async def does_violate(self, msg: discord.Message) -> bool:
        raise NotImplementedError
