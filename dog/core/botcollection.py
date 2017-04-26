import discord


def user_to_bot_ratio(guild: discord.Guild):
    """ Calculates the user to bot ratio for a guild. """
    bots = len(list(filter(lambda u: u.bot, guild.members)))
    users = len(list(filter(lambda u: not u.bot, guild.members)))

    ratio = bots / users
    return ratio


def is_bot_collection(guild: discord.Guild):
    """ Returns a bool indicating whether a guild is a collection. """
    # keywords in the guild name
    for keyword in ('bot collection', 'bot hell'):
        if keyword in guild.name.lower():
            return True

    # special guilds that shouldn't be classified as a
    # bot collection
    if guild.id in (110373943822540800, 228317351672545290):
        return False

    if user_to_bot_ratio(guild) >= 5:
        # ratio too big!
        return True

    return False
