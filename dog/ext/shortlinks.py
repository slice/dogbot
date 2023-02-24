import re

import discord
import lifesaver

STOP_WORDS = {
    "[no-link]",
    "[no-links]",
    "[nolink]",
    "[nolinks]",
    "[no-shortlink]",
    "[no-shortlinks]",
    "[noshortlink]",
    "[noshortlinks]",
}


class Shortlink:
    CONVERTERS = {
        "int": int,
        "float": float,
    }

    def __init__(self, pattern, fmt, *, call_format: bool = False):
        self.pattern = re.compile(pattern)
        self.format = fmt
        self.call_format = call_format

    def convert_groups(self, dct):
        converted = {}
        for name, value in dct.items():
            if "__" not in name:
                converted[name] = value
                continue
            name, converter = name.split("__")
            converted[name] = self.CONVERTERS[converter](value)
        return converted

    def expand_match(self, match):
        if self.call_format:
            groups = self.convert_groups(match.groupdict())
            return self.format.format(**groups)
        return match.expand(self.format)

    def execute(self, text):
        matches = list(self.pattern.finditer(text))
        if not matches:
            return []

        return [self.expand_match(match) for match in matches]


SHORTLINKS = {
    "mastodon": Shortlink(
        r"@(?P<username>\w+)@(?P<instance>\w{2,}\.[a-z]{2,10})",
        "https://\\g<instance>/@\\g<username>",
    ),
    "pep": Shortlink(
        r"PEP#(?P<pep__int>\d{1,4})",
        "https://www.python.org/dev/peps/pep-{pep:04}",
        call_format=True,
    ),
    "keybase": Shortlink(r"kb/(?P<username>\w+)", "https://keybase.io/\\g<username>",),
    "osu": Shortlink(
        r"osu/(?P<username>\w+)", "https://osu.ppy.sh/users/\\g<username>",
    ),
}


class Shortlinks(lifesaver.Cog):
    @lifesaver.Cog.listener()
    async def on_message(self, msg):
        if not msg.guild or msg.author.bot:
            return

        config = self.bot.guild_configs.get(msg.guild, {})
        shortlinks_config = config.get("shortlinks", {})
        if not shortlinks_config.get("enabled", False):
            return
        whitelist = shortlinks_config.get("whitelist", [])
        blacklist = shortlinks_config.get("blacklist", [])

        if any(text in msg.content for text in STOP_WORDS):
            return

        expanded = set()
        for (name, shortlink) in SHORTLINKS.items():
            if (whitelist and (name not in whitelist)) or (name in blacklist):
                continue
            expanded |= set(shortlink.execute(msg.content))

        if not expanded:
            return

        try:
            await msg.channel.send("\n".join(expanded))
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(Shortlinks(bot))
