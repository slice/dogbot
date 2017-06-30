import asyncpg
from discord.ext import commands
from dog import Cog


class PyDocs(Cog):
    @commands.group(aliases=['d'], invoke_without_command=True)
    async def docs(self, ctx, *, name):
        """ Views a doc. """
        async with ctx.bot.pgpool.acquire() as conn:
            record = await conn.fetchrow('SELECT * FROM docs WHERE name = $1', name)
            if not record:
                # you flubbed up
                return await ctx.message.delete()
            await ctx.message.edit(content=record['content'])

    @docs.command(name='edit')
    async def docs_edit(self, ctx, name, *, content):
        """ Edits a doc. """
        async with ctx.bot.pgpool.acquire() as conn:
            try:
                await conn.execute('UPDATE docs SET content = $2 WHERE name = $1', name, content)
                await ctx.ok()
            except asyncpg.PostgresError:
                await ctx.message.edit(content='Doc not found.')

    @docs.command(name='list')
    async def docs_list(self, ctx):
        async with ctx.bot.pgpool.acquire() as conn:
            docs = await conn.fetch('SELECT name FROM docs')

            if not docs:
                return await ctx.message.edit(content='No docs.')

            docs = ['`{}`'.format(r['name']) for r in docs]
            await ctx.message.edit(content='{} docs available: {}'.format(len(docs), ', '.join(docs)))

    @docs.command(name='create', aliases=['make'])
    async def docs_create(self, ctx, name, *, content):
        """ Creates a doc. """
        async with ctx.bot.pgpool.acquire() as conn:
            try:
                await conn.execute('INSERT INTO docs (name, content) VALUES ($1, $2)', name, content)
                await ctx.ok()
            except asyncpg.UniqueViolationError:
                await ctx.message.edit(content='There\'s already a doc with that name.')

    @docs.command(name='delete', aliases=['del'])
    async def docs_delete(self, ctx, name):
        """ Deletes a doc. """
        async with ctx.bot.pgpool.acquire() as conn:
            await conn.execute('DELETE FROM docs WHERE name = $1', name)
        await ctx.ok()


def setup(bot):
    bot.add_cog(PyDocs(bot))
