"""
Contains censorship functionality.
"""

import logging
import re
from enum import Enum

import discord
from discord.ext import commands

from dog import Cog
from dog.core import utils

logger = logging.getLogger(__name__)
INVITE_RE = re.compile(r'(discordapp\.com\/invite|discord\.gg)\/([a-zA-Z_\-0-9]+)')


def has_invite(content: str) -> bool:
    return INVITE_RE.match(content) is not None


class CensorType(Enum):
    INVITES = 1


class Censorship(Cog):
    async def is_censoring(self, guild: discord.Guild, what: CensorType) -> bool:
        """ Returns whether something is being censored for a guild. """
        return await self.bot.redis.hexists(f'censor:{guild.id}', what.name)
    
    async def censor(self, guild: discord.Guild, what: CensorType):
        """ Censors something for a guild. """
        logger.info('Censoring %s for %s (%d)', what, guild.name, guild.id)
        await self.bot.redis.hset(f'censor:{guild.id}', what.name, 'on')

    async def uncensor(self, guild: discord.Guild, what: CensorType):
        """ Uncensors something for a guild. """
        logging.info('Uncensoring %s for %s (%d)', what, guild.name, guild.id)
        await self.bot.redis.hdel(f'censor:{guild.id}', what.name)

    @commands.group(aliases=['cs'])
    @commands.has_permissions(manage_guild=True)
    async def censorship(self, ctx):
        """
        Manages censorship.

        You must have the "Manage Server" permission in order to manage server censorship.
        """
        pass

    @censorship.command(name='censor')
    async def _censor(self, ctx, what: str):
        """ Censors a specific type of message. """
        censor_type = getattr(CensorType, what.upper(), None)
        if not censor_type:
            return await ctx.send('Invalid censorship type.')
        await self.censor(ctx.message.guild, censor_type)
        await self.bot.ok(ctx)

    @censorship.command(name='list')
    async def _list(self, ctx):
        """ Lists the censorship types. """
        types = ', '.join([f'`{t.name.lower()}`' for t in CensorType])
        await ctx.send(f'Censorship types: {types}')

    @censorship.command(name='censoring')
    async def _censoring(self, ctx, what: str):
        """ Views what types of messages are being censored. """
        censor_type = getattr(CensorType, what.upper(), None)
        if not censor_type:
            return await ctx.send('Invalid censorship type.')
        is_censoring = await self.is_censoring(ctx.guild, censor_type)

        if is_censoring:
            await ctx.send(f'Yes, `{what}` are being censored.')
        else:
            await ctx.send(f'No, `{what}` are not being censored.')

    @censorship.command(name='uncensor')
    async def _uncensor(self, ctx, what: str):
        """ Uncensors a specific type of message. """
        censor_type = getattr(CensorType, what.upper(), None)
        if not censor_type:
            return await ctx.send('Invalid censorship type.')
        await self.uncensor(ctx.message.guild, censor_type)
        await self.bot.ok(ctx)

    async def on_message(self, msg: discord.Message):
        if await self.is_censoring(msg.guild, CensorType.INVITES) and has_invite(msg.content):
            try:
                await msg.delete()
            except discord.Forbidden:
                await self.bot.send_modlog(msg.guild, ':x: I failed to censor a message because '
                                           'I couldn\'t delete it! Please fix my permissions.')
            else:
                title = '\u002a\u20e3 Invite-containing message censored'
                embed = self.bot.get_cog('Modlog')._make_message_embed(msg, title=title)
                await self.bot.send_modlog(msg.guild, embed=embed)
                

def setup(bot):
    bot.add_cog(Censorship(bot))
