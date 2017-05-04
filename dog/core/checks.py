from discord.ext import commands

from .errors import InsufficientPermissions

mod_names = [
    'Moderator', 'Mod',  # classic mod role names
    'moderator', 'mod',  # lowercase mod role names
    # dog specific
    'Dog Moderator', 'Woofer', 'woofer', 'dog moderator',
    'dog mod',
]


def config_is_set(name: str):
    """ Check: Checks if a guild-specific configuration key is set. """
    async def _predicate(ctx: commands.Context):
        return await ctx.bot.config_is_set(ctx.guild, name)

    return commands.check(_predicate)


def global_config_is_set(name: str):
    """ Check: Checks if a global configuration key is set. """
    async def _predicate(ctx: commands.Context):
        return await ctx.bot.redis.get(name) is not None

    return commands.check(_predicate)


def global_config_is_not_set(name: str):
    """
    Check: Checks if a global configuration key is **not** set.

    For example: ::

        @checks.global_config_is_not_set('explode_world')

    """
    async def _predicate(ctx):
        return await ctx.bot.redis.get(name) is None

    return commands.check(_predicate)


def _beautify_permission_code(p):
    return p.replace('_', ' ').replace('guild', 'server').title()


def bot_perms(**permissions):
    """
    Check: Checks if we have all permissions listed.

    For example: ::

        @checks.bot_perms(ban_members=True)

    If we do not have all permissions listed, then a special exception is
    thrown: `dog.core.errors.InsufficientPermissions`. This is so that
    it can be caught in `on_command_error`, and display a nice error message.
    """
    async def predicate(ctx):
        my_perms = ctx.guild.me.permissions_in(ctx.channel)
        # use a dict comprehension so if we are missing a permission we can
        # trace it back to which permission we don't have
        does_match = {perm: getattr(my_perms, perm, False) for perm in permissions}
        # if we don't have all of the permissions we need, raise an error
        if not all(does_match.values()):
            # which permissions we don't have (which we need)
            failing = [_beautify_permission_code(p) for p in does_match.keys() if not does_match[p]]
            raise InsufficientPermissions('I need these permissions to do that: ' +
                                          ', '.join(failing))
        return True
    return commands.check(predicate)


def is_dogbot_moderator(ctx):
    """
    Returns whether a person is a "Dogbot Moderator".
    """
    names = [r.name for r in ctx.author.roles]
    has_moderator_role = any([1 for name in names if name in mod_names])
    has_manage_server = ctx.author.guild_permissions.manage_guild
    is_server_owner = ctx.guild.owner == ctx.author
    return has_moderator_role or has_manage_server or is_server_owner


def is_moderator():
    """
    Check: Checks if a person is a "Dogbot Moderator".
    """
    async def _predicate(ctx):
        return is_dogbot_moderator(ctx)
    return commands.check(_predicate)
