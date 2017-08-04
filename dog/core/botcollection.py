import discord


def user_to_bot_ratio(guild: discord.Guild):
    bots, users = 0, 0
    for member in guild.members:
        if member.bot:
            bots += 1
        else:
            users += 1

    return bots / users


async def is_blacklisted(bot, guild_id: int) -> bool:
    """ Returns a bool indicating whether a guild has been blacklisted. """
    async with bot.pgpool.acquire() as conn:
        blacklisted_record = await conn.fetchrow('SELECT * FROM blacklisted_guilds WHERE guild_id = $1', guild_id)
        return blacklisted_record is not None


async def is_bot_collection(bot, guild: discord.Guild):
    """ Returns a bool indicating whether a guild is a collection. """
    if await is_blacklisted(bot, guild.id):
        return True

    # keywords in the guild name
    if any([keyword in guild.name.lower() for keyword in ('bot collection', 'bot hell')]):
        return True

    # special guilds that shouldn't be classified as a bot collection
    if guild.id in (110373943822540800, 228317351672545290):
        return False

    # ratio too big!
    if user_to_bot_ratio(guild) >= 8:
        return True

    return False
