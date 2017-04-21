from .errors import InsufficientPermissions
from discord.ext import commands

mod_names = [
    'Moderator', 'Mod',  # classic mod role names
    'moderator', 'mod',  # lowercase mod role names
    # dog specific
    'Dog Moderator', 'Woofer', 'woofer', 'dog moderator',
    'dog mod',
]

def config_is_set(name):
    async def _predicate(ctx):
        return await ctx.bot.config_is_set(ctx.guild, name)

    return commands.check(_predicate)

def global_config_is_set(name):
    async def _predicate(ctx):
        return await ctx.bot.redis.get(name) is not None

    return commands.check(_predicate)

def global_config_is_not_set(name):
    async def _predicate(ctx):
        return await ctx.bot.redis.get(name) is None

    return commands.check(_predicate)

def bot_perms(**permissions):
    async def predicate(ctx):
        my_perms = ctx.guild.me.permissions_in(ctx.channel)
        # use a dict comprehension so if we are missing a permission we can
        # trace it back to which permission we don't have
        does_match = {perm: getattr(my_perms, perm, False) for perm in permissions.keys()}
        # if we don't have all of the permissions we need, raise an error
        if not all(does_match.values()):
            # which permissions we don't have (which we need)
            failing = [p for p in does_match.keys() if not does_match[p]]
            raise InsufficientPermissions('Insufficient permissions: ' +
                                          ', '.join(failing))
        return True
    return commands.check(predicate)

def is_dogbot_moderator(ctx):
    names = [r.name for r in ctx.author.roles]
    has_moderator_role = any([1 for name in names if name in mod_names])
    has_manage_server = ctx.author.guild_permissions.manage_guild
    is_server_owner = ctx.guild.owner == ctx.author
    return has_moderator_role or has_manage_server or is_server_owner

def is_moderator():
    async def _predicate(ctx):
        return is_dogbot_moderator(ctx)
    return commands.check(_predicate)
