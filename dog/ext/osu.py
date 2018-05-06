import asyncio
import datetime
import logging
from typing import List

import discord
from discord.ext.commands import BucketType, cooldown
from lifesaver.bot import Cog, Context, group
from lifesaver.utils import human_delta, truncate, pluralize

log = logging.getLogger(__name__)
BLOODCAT_ENDPOINT = 'https://bloodcat.com/osu'


class Beatmap:
    def __init__(self, data):
        self.ar = float(data.get('ar', '0.0'))
        self.mapper = data.get('author')
        self.bpm = float(data.get('bpm', '0.0'))
        self.cs = float(data.get('cs', '0.0'))
        self.hp = float(data.get('hp', '0.0'))
        self.length = int(data.get('length', '0'))
        self.name = data.get('name')
        self.od = float(data.get('od', '0.0'))
        self.stars = float(data.get('star', '0.0'))

    class Status:
        UNRANKED = 0
        RANKED = 1
        APPROVED = 2
        QUALIFIED = 3
        LOVED = 4

    def __str__(self):
        return f'{self.name} {self.stars:.2f} \N{BLACK STAR}'

    def __repr__(self):
        return f'<Beatmap name={self.name} mapper={self.mapper}>'


class Mapset:
    def __init__(self, data):
        self.artist_romanized = data.get('artist')
        self.artist_original = data.get('artistU')
        self.beatmaps = [Beatmap(b) for b in data['beatmaps']]
        self.mapper = data.get('creator')
        self.id = data.get('id')
        ranked_at = data.get('rankedAt')
        if ranked_at is not None:
            self.ranked_at = datetime.datetime.strptime(ranked_at, '%Y-%m-%d %H:%M:%S')
        else:
            self.ranked_at = None
        self.status = int(data.get('status'))
        self.source = data.get('source')
        self.tags = data.get('tags', [])
        self.title_romanized = data.get('title')
        self.title_original = data.get('titleU')

    @property
    def status_text(self):
        statuses = ['Unranked', 'Ranked', 'Approved', 'Qualified', 'Loved']
        return statuses[self.status]

    @property
    def artist(self):
        return self.artist_romanized or self.artist_original

    @property
    def title(self):
        return self.title_romanized or self.title_original

    @property
    def thumbnail_url(self):
        return f'https://b.ppy.sh/thumb/{self.id}l.jpg'

    @property
    def url(self):
        return f'https://osu.ppy.sh/beatmapsets/{self.id}'

    @property
    def embed(self):
        diffs = sorted(self.beatmaps, key=lambda b: b.stars, reverse=True)

        embed = discord.Embed(title=f'{self.artist} \N{EM DASH} {self.title}')
        embed.url = self.url
        embed.description = truncate('\n'.join(str(diff) for diff in diffs), 1000)
        if self.source:
            embed.add_field(name='Source', value=self.source)
        embed.add_field(name='Status', value=self.status_text)
        if self.status == 1:  # ranked
            embed.add_field(name='Ranked', value=human_delta(self.ranked_at) + ' ago')
        embed.set_thumbnail(url=self.thumbnail_url)
        embed.set_footer(text=f'Mapped by {self.mapper}')
        if self.beatmaps:
            length = self.beatmaps[0].length
            minutes, seconds = divmod(length, 60)
            embed.add_field(name='Length', value=f'{minutes:02n}:{seconds:02n}')
        return embed

    def __repr__(self):
        return f'<Mapset title={self.title} mapper={self.mapper}>'


beatmap_cooldown = cooldown(1, 5, BucketType.user)


class Osu(Cog):
    async def search(self, ctx: Context, query, status):
        # don't use the typing kwarg on the command decorator because this coro
        # will run for 5 minutes
        await ctx.channel.trigger_typing()

        mapsets = await self.beatmap_search(query, status)
        log.debug('Found %d mapsets: %s', len(mapsets), mapsets)

        if not mapsets:
            await ctx.send('No results.')
            return

        position = 0
        message = await ctx.send(
            content=f'Grabbed {len(mapsets)} {pluralize(mapset=len(mapsets))}.',
            embed=mapsets[position].embed
        )

        if len(mapsets) == 1:
            # don't bother paginating if there's only one mapset
            return

        try:
            await message.add_reaction('\U000023ee')
            await message.add_reaction('\U000023ed')
        except discord.HTTPException:
            # can't paginate, just bail
            return

        async def paginate():
            log.debug('Paginator started.')

            def check(reaction, user):
                return user == ctx.author and reaction.message.id == message.id

            while True:
                reaction, user = await self.bot.wait_for('reaction_add', check=check)

                log.debug('Received: %s, %s', reaction, user)

                async def attempt_remove(emoji):
                    try:
                        await message.remove_reaction(emoji, user)
                    except discord.HTTPException:
                        pass

                if not isinstance(reaction.emoji, str):
                    log.debug('Ignoring custom emoji.')
                    continue

                if reaction.emoji == '\U000023ee':
                    # prev
                    nonlocal position
                    position -= 1
                    # block
                    if position < 0:
                        position = 0
                    await attempt_remove('\U000023ee')
                elif reaction.emoji == '\U000023ed':
                    # next
                    position += 1
                    # wrap
                    if position > len(mapsets) - 1:
                        position = 0
                    await attempt_remove('\U000023ed')

                embed = mapsets[position].embed
                embed.set_footer(text=f'({position + 1}/{len(mapsets)}) {embed.footer.text}')
                await message.edit(embed=embed)

        try:
            log.debug('Going to paginate.')
            # paginate for 5 minutes
            await asyncio.wait_for(paginate(), timeout=60 * 5, loop=ctx.bot.loop)
        except asyncio.TimeoutError:
            log.debug('Stopped paginator.')
            pass

    @group(invoke_without_command=True)
    @beatmap_cooldown
    async def beatmap(self, ctx: Context, *, query=None):
        """Searches for ranked osu! beatmaps from Bloodcat."""
        await self.search(ctx, query, Beatmap.Status.RANKED)

    @beatmap.command(name='unranked')
    @beatmap_cooldown
    async def beatmap_unranked(self, ctx: Context, *, query=None):
        """Searches for unranked osu! beatmaps from Bloodcat."""
        await self.search(ctx, query, Beatmap.Status.UNRANKED)

    async def beatmap_search(self, query: str = None, status: int = Beatmap.Status.RANKED) -> List[Mapset]:
        query = {
            'mod': 'json',
            'q': query or '',
            'c': 'b',
            's': status,
            'm': 0,  # standard
            'p': 1,
        }

        headers = {
            'User-Agent': 'dog/0.0.0'
        }

        async with self.bot.session.get(BLOODCAT_ENDPOINT, headers=headers, params=query) as resp:
            json = await resp.json()
            return [Mapset(m) for m in json]


def setup(bot):
    bot.add_cog(Osu(bot))
