import aiohttp
import collections

import discord
from discord.ext import commands
from lifesaver.bot import Cog, command, group

from dog.converters import HardMember
from dog.ext.info import date

VERIFY_INSTRUCTIONS = """

You need to prove your identity!
If you are using Mastodon, you can add a profile metadata field with a value being `{user}` or your user ID: `{user.id}`
Alternatively, you can put either value anywhere in your bio.

Once you have linked your account, you can remove it from your profile.
"""


class MastodonUsername(collections.namedtuple('Mastodon', 'username instance')):
    @classmethod
    async def convert(cls, _ctx, acct: str):
        try:
            username, instance = acct.lstrip('@').split('@')
        except ValueError:
            raise commands.BadArgument('Invalid Mastodon username. Example: `@haru@mastodon.instance`')

        return cls(username, instance)

    def __str__(self):
        return f'{self.username}@{self.instance}'


def verify_actor(actor, user: discord.User):
    """Verify an ActivityPub actor to be linked to a Discord user."""

    def links_user(input: str) -> bool:
        return any(str(identifier) in input for identifier in (str(user), user.id))

    # find in `PropertyValue` `value`s in `attachment` (mastodon profile fields)
    property_value = discord.utils.find(
        lambda attachment: attachment['type'] == 'PropertyValue' and links_user(attachment['value']),
        actor.get('attachment', []),
    )

    if property_value is not None:
        return True

    # find in user summary (usually bio)
    return links_user(actor.get('summary', ''))


class Profile(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self.session._default_headers = {
            'User-Agent': 'dogbot/0.0.0 (https://github.com/slice)'
        }

    @group(aliases=['whois'], invoke_without_command=True)
    @commands.cooldown(1, 1, commands.BucketType.user)
    async def profile(self, ctx, user: HardMember = None):
        """Views information about a user."""
        user = user or ctx.author

        embed = discord.Embed(title=f'{user} ({user.id})')
        embed.add_field(name='Account Creation', value=date(user.created_at))
        embed.set_thumbnail(url=user.avatar_url)

        if isinstance(user, discord.Member) and user.guild is not None:
            embed.add_field(name=f'Joined {ctx.guild.name}', value=date(user.joined_at), inline=False)

        if user.bot:
            embed.title = f'{ctx.emoji("bot")} {embed.title}'
        else:
            async with ctx.pool.acquire() as conn:
                record = await conn.fetchrow("""
                    SELECT username, profile_page_link FROM activitypub_actor_links
                    WHERE user_id = $1
                """, user.id)

                if record is not None:
                    embed.description = f'{ctx.emoji("mastodon")} [{record["username"]}]({record["profile_page_link"]})'

        await ctx.send(embed=embed)

    @profile.command(name='link_ap', hidden=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def profile_link_ap(self, ctx, acct: MastodonUsername):
        """Links an ActivityPub actor to your profile.

        The actor is discovered with WebFinger.
        """
        loading_emoji = ctx.emoji('loading')

        progress = await ctx.send(f'{loading_emoji} Discovering account...')

        try:
            finger = await self.session.get(
                f'https://{acct.instance}/.well-known/webfinger',
                params={'resource': f'acct:{acct}'},
                headers={'Accept': 'application/json'},
            )
            finger.raise_for_status()
        except aiohttp.ClientError:
            await progress.edit(content=f'{ctx.tick(False)} Failed to discover account.')
            return

        finger = await finger.json()

        def find_link(*, type: str, rel: str):
            return discord.utils.find(
                lambda link: link.get('type') == type and link.get('rel') == rel,
                finger.get('links', []),
            )

        actor_link = find_link(type='application/activity+json', rel='self')
        profile_link = find_link(type='text/html', rel='http://webfinger.net/rel/profile-page')

        if not actor_link:
            await progress.edit(content=f'{ctx.tick(False)} Failed to find ActivityPub self link.')
            return

        if not profile_link:
            await progress.edit(content=f'{ctx.tick(False)} Failed to find WebFinger profile page link.')
            return

        await progress.edit(content=f'{loading_emoji} Discovering actor...')

        try:
            actor = await self.session.get(
                actor_link['href'],
                headers={'Accept': 'application/activity+json'}
            )
            actor.raise_for_status()
        except aiohttp.ClientError:
            await progress.edit(content=f'{ctx.tick(False)} Failed to discover actor.')
            return

        actor = await actor.json()

        if not verify_actor(actor, ctx.author):
            await progress.edit(
                content=f"{ctx.tick(False)} I couldn't verify your account." + VERIFY_INSTRUCTIONS.format(
                    user=ctx.author)
            )
            return

        async with ctx.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO activitypub_actor_links (user_id, actor_link, profile_page_link, username)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE SET actor_link = $2, profile_page_link = $3, username = $4;
            """, ctx.author.id, actor_link['href'], profile_link['href'], str(acct))

        await progress.edit(content=f'{ctx.tick()} Linked successfully.')

    @profile.command(name='avatar')
    async def profile_avatar(self, ctx, user: HardMember = None):
        """Views the avatar of a user."""
        user = user or ctx.author
        await ctx.send(user.avatar_url_as(format='png'))

    @command(aliases=['avatar_url'])
    async def avatar(self, ctx, user: HardMember = None):
        """Views the avatar of a user."""
        await ctx.invoke(self.profile_avatar, user)


def setup(bot):
    bot.add_cog(Profile(bot))
