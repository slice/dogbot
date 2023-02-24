import discord


def represent(entity: discord.abc.Snowflake) -> str:
    if isinstance(entity, (discord.User, discord.Member)):
        return f"{entity} (`{entity.id}`)"

    return f"`{entity.id}`"
