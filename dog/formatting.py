import discord


def represent(entity: discord.Object) -> str:
    if isinstance(entity, (discord.User, discord.Member)):
        return f"{entity} (`{entity.id}`)"

    if isinstance(entity, discord.Object):
        return f"`{entity.id}`"
