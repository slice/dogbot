import re
import discord

from dog import Cog


class Shortlinks(Cog):
    _REPO = r'(.+)/([a-zA-Z_\.-]+)(?:#(\d+))?'
    GITHUB_SHORTLINK = ('github.com', re.compile(r'gh/' + _REPO))
    GITLAB_SHORTLINK = ('gitlab.com', re.compile(r'gl/' + _REPO))

    async def on_message(self, msg: discord.Message):
        if not msg.guild or not await self.bot.config_is_set(
                msg.guild, 'shortlinks_enabled'):
            return

        for host, shortlink in (self.GITHUB_SHORTLINK, self.GITLAB_SHORTLINK):
            match = shortlink.fullmatch(msg.content)

            if not match:
                continue

            owner, repository, issue_number = match.groups()

            if issue_number:
                await msg.channel.send(
                    f'https://{host}/{owner}/{repository}/issues/{issue_number}'
                )
            else:
                await msg.channel.send(f'https://{host}/{owner}/{repository}')


def setup(bot):
    bot.add_cog(Shortlinks(bot))
