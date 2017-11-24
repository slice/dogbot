from discord import Guild
from discord.ext import commands
from discord.ext.commands import check

from dog.core.checks import user_is_bot_admin, is_supporter
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
    # is a bot admin
    is_admin = await user_is_bot_admin(ctx, ctx.author)

    # whitelisted guilds can play music
    guild_is_whitelisted = ctx.guild and await is_whitelisted(
        ctx.bot, ctx.guild)

    # is supporter
    is_a_supporter = is_supporter(ctx.bot, ctx.author)

    return is_admin or guild_is_whitelisted or is_a_supporter


def can_use_music_check():
    return check(can_use_music)


async def must_be_in_voice(ctx: commands.Context):
    if not ctx.guild:
        return False

    if ctx.guild.voice_client is None:
        raise MustBeInVoice

    return True
