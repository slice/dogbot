import discord
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


def beautify_permission_name(p):
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
            failing = [beautify_permission_name(p) for p in does_match.keys() if not does_match[p]]
            raise InsufficientPermissions('I need these permissions to do that: ' +
                                          ', '.join(failing))
        return True
    return commands.check(predicate)


def member_is_moderator(member: discord.Member) -> bool:
    names = [r.name for r in member.roles]
    has_moderator_role = any([1 for name in names if name in mod_names])
    has_manage_server = member.guild_permissions.manage_guild
    is_server_owner = member.guild.owner == member
    return has_moderator_role or has_manage_server or is_server_owner


def is_dogbot_moderator(ctx):
    """ Returns whether a person is a "Dogbot Moderator". """
    if isinstance(ctx.channel, discord.DMChannel):
        return False
    return member_is_moderator(ctx.author)


def is_moderator():
    """ Check: Checks if a person is a "Dogbot Moderator". """
    return commands.check(lambda ctx: is_dogbot_moderator(ctx))


def is_supporter(bot, user):
    """ Returns whether a user has the supporter role in the woof server. """
    # get the server
    woof_guild: discord.Guild = bot.get_guild(bot.cfg['bot']['woof']['guild_id'])

    # guild doesn't exist, or user is not in the server
    if not woof_guild or user not in woof_guild.members:
        return False

    # get the user, but in the woof server
    woof_member = woof_guild.get_member(user.id)

    # get the donator role id in the woof server
    # or alternatively a list of role ids
    donator_role = bot.cfg['bot']['woof']['donator_role']

    # list of role ids that this user has
    ids = [r.id for r in woof_member.roles]

    # if there are multiple donator roles, check all of them
    if isinstance(donator_role, list):
        return any([donator_role_id in ids for donator_role_id in donator_role])
    else:
        return donator_role in ids


def is_supporter_check():
    return commands.check(lambda ctx: is_supporter(ctx.bot, ctx.author))
