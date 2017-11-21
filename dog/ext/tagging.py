"""
Extension that implements tags, a way to store pieces of useful text for later.
"""

import datetime
import re
from collections import namedtuple
from typing import Union

import discord
from discord.ext import commands
from discord.ext.commands import clean_content, guild_only

from dog import Cog
from dog.core import checks, utils
from dog.core.context import DogbotContext

Tag = namedtuple('Tag', 'name value creator created_at uses')


class Tagging(Cog):
    async def create_tag(self, ctx: DogbotContext, name: str, value: str):
        insert = """
            INSERT INTO tags
            (name, guild_id, creator_id, value, uses, created_at)
            VALUES ($1, $2, $3, $4, 0, $5)
        """
        await self.bot.pgpool.execute(
            insert, name, ctx.guild.id, ctx.author.id, value,
            datetime.datetime.utcnow()
        )

    async def edit_tag(self, name: str, value: str):
        await self.bot.pgpool.execute(
            'UPDATE tags SET value = $1 WHERE name = $2',
            value, name
        )

    async def get_tag(self, ctx: DogbotContext, name: str) -> Union[None, Tag]:
        """Finds a tag, and returns it as a :class:``Tag`` object."""
        query = """
            SELECT * FROM tags
            WHERE guild_id = $1 AND name = $2
        """
        record = await self.bot.pgpool.fetchrow(query, ctx.guild.id, name)

        if not record:
            return None

        creator = ctx.guild.get_member(record['creator_id']) or record['creator_id']
        return Tag(
            value=record['value'], creator=creator, uses=record['uses'], name=name,
            created_at=record['created_at']
        )

    async def delete_tag(self, ctx: DogbotContext, name: str):
        """Deletes a tag."""
        await self.bot.pgpool.execute(
            'DELETE FROM tags WHERE guild_id = $1 AND name = $2',
            ctx.guild.id, name
        )

    def can_touch_tag(self, ctx: DogbotContext, tag: Tag) -> bool:
        """Returns whether someone can touch a tag (modify, delete, or edit it)."""
        perms = ctx.author.guild_permissions

        predicates = [
            # they can manage the server
            perms.manage_guild,

            # they own the server
            ctx.author.guild.owner == ctx.author,

            # they created the tag
            tag.creator == ctx.author,

            # is dogbot moderator
            checks.member_is_moderator(ctx.author)
        ]

        return any(predicates)

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def tag(self, ctx, name: clean_content, *, value: clean_content=None):
        """
        Tag related operations.

        If you provide a value, a tag is created if it doesn't exist. If it
        does exist, it will be overwritten provided that you can touch that
        tag.

        If you don't provide a value, the tag's contents are sent.

        You may only touch a tag if any of the following conditions are met:
            You have the "Manage Server" permission,
            you are the owner of the server.
            you have created that tag.
            you are a Dogbot Moderator.
        """

        # a value was provided, create or overwrite a tag
        if value:
            tag = await self.get_tag(ctx, name)

            # tag already exists, check if we can touch it
            if tag and not self.can_touch_tag(ctx, tag):
                # cannot overwrite
                return await ctx.send(
                    "\N{NO PEDESTRIANS} You can't overwrite that tag's contents."
                )

            # set a tag
            if tag:
                await self.edit_tag(name, value)
            else:
                await self.create_tag(ctx, name, value)

            # we good
            await ctx.ok('\N{MEMO}' if tag else '\N{DELIVERY TRUCK}')

            return

        # see the value of a tag
        tag = await self.get_tag(ctx, name)

        if tag:
            # send the tag's value
            await ctx.send(tag.value)

            # increment usage count
            update = """
                UPDATE tags
                SET uses = uses + 1
                WHERE name = $1 AND guild_id = $2
            """
            await self.bot.pgpool.execute(update, name, ctx.guild.id)
        else:
            await ctx.send('Tag not found.')

    @tag.command(name='list', aliases=['ls'])
    @guild_only()
    async def tag_list(self, ctx):
        """Lists tags in this server."""
        tags = await self.bot.pgpool.fetch('SELECT * FROM tags WHERE guild_id = $1', ctx.guild.id)
        tag_names = [record['name'] for record in tags]

        if not tags:
            return await ctx.send('There are no tags in this server.')

        try:
            await ctx.send(f'**{len(tag_names)} tag(s):** ' + ', '.join(tag_names))
        except discord.HTTPException:
            await ctx.send('There are too many tags to display.')

    @tag.command(name='delete', aliases=['rm', 'remove', 'del'])
    @guild_only()
    async def tag_delete(self, ctx: DogbotContext, name):
        """
        Deletes a tag.

        You may only do so if you can touch that tag. For more information,
        see d?help tag.
        """
        tag = await self.get_tag(ctx, name)

        if not tag:
            return await ctx.send('Tag not found.')

        if not self.can_touch_tag(ctx, tag):
            return await ctx.send('\N{NO PEDESTRIANS} You can\'t do that.')

        await self.delete_tag(ctx, name)
        await ctx.ok('\N{PUT LITTER IN ITS PLACE SYMBOL}')

    @tag.command(name='markdown', aliases=['raw'])
    @guild_only()
    async def tag_markdown(self, ctx: DogbotContext, name):
        """Views the markdown of a tag."""
        tag = await self.get_tag(ctx, name)

        if not tag:
            return await ctx.send('Tag not found.')

        content = tag.value
        escape_regex = r'(`|\*|~|_|<|\\)'
        # no, those two strings can't be together
        content = re.sub(escape_regex, r'\\' + '\\1', content)

        await ctx.send(content)

    @tag.command(name='info', aliases=['about'])
    @guild_only()
    async def tag_info(self, ctx: DogbotContext, name):
        """Shows you information about a certain tag."""
        tag = await self.get_tag(ctx, name)

        if tag:
            embed = discord.Embed(title=tag.name, description=tag.value)
            embed.add_field(name='Created', value=utils.standard_datetime(tag.created_at) + ' UTC')
            embed.add_field(name='Created by', value=tag.creator.mention, inline=False)
            embed.add_field(name='Uses', value=tag.uses)
            await ctx.send(embed=embed)
        else:
            await ctx.send('Tag not found.')


def setup(bot):
    bot.add_cog(Tagging(bot))
