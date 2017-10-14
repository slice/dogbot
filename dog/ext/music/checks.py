from discord import Guild
from discord.ext import commands

from dog.core.checks import user_is_bot_admin
from dog.core.context import DogbotContext
from dog.core.errors import MustBeInVoice


async def is_whitelisted(bot, guild: Guild):
    query = """
        SELECT *
        FROM music_guilds
        WHERE guild_id = $1
    """

    record = await bot.pgpool.fetchrow(query, guild.id)
    return record is not None


async def can_use_music(ctx: DogbotContext):
    is_admin = await user_is_bot_admin(ctx, ctx.author)

    # false if in dm
    guild_is_whitelisted = False if not ctx.guild else await is_whitelisted(ctx.bot, ctx.guild)

    return is_admin or guild_is_whitelisted


async def must_be_in_voice(ctx: commands.Context):
    if not ctx.guild:
        return False

    if ctx.guild.voice_client is None:
        raise MustBeInVoice

    return True
