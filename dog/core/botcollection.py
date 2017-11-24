import discord

from dog import Dogbot

WHITELISTED_GUILDS = {
    228317351672545290,  # bot testing zone
    110373943822540800  # discord bots
}
UTBR_MAXIMUM = 8


def user_to_bot_ratio(guild: discord.Guild):
    bots, users = 0, 0
    for member in guild.members:
        if member.bot:
            bots += 1
        else:
            users += 1

    return bots / users


async def is_blacklisted(bot: Dogbot, guild_id: int) -> bool:
    """Returns a bool indicating whether a guild has been blacklisted."""
    blacklisted_record = await bot.pgpool.fetchrow(
        'SELECT * FROM blacklisted_guilds WHERE guild_id = $1', guild_id)
    return blacklisted_record is not None


async def is_bot_collection(bot: Dogbot, guild: discord.Guild) -> bool:
    """Returns a bool indicating whether a guild is a collection."""
    if await is_blacklisted(bot, guild.id):
        return True

    # keywords in the guild name
    if any(keyword in guild.name.lower()
           for keyword in ('bot collection', 'bot hell')):
        return True

    # special guilds that shouldn't be classified as a bot collection
    if guild.id in WHITELISTED_GUILDS:
        return False

    # ratio too big!
    if user_to_bot_ratio(guild) >= UTBR_MAXIMUM:
        return True

    return False
