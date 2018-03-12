import discord


def _noop(*args, **kwargs):
    return True


def check_event_arg(obj, *, target, location):
    def _check_messagelike(m):
        return m.author == target and m.channel == location

    if isinstance(obj, discord.Message):
        return _check_messagelike(obj)
    elif isinstance(obj, (discord.User, discord.Member)):
        return obj == target
    elif isinstance(obj, discord.Reaction):
        return obj.message.channel == location

    return True


class InteractivePaginator:
    EMOJIS = {
        'NEXT': '\U000023ed',
        'PREV': '\U000023ee',
        'STOP': '\U000023f9'
    }

    def __init__(self, things, *, target, location, bot):
        self.things = things
        self.target = target
        self.location = location
        self.bot = bot
        self.message = None

    def embed(self):
        embed = discord.Embed(color=discord.Color.blurple(), description='')
        for thing in self.things:
            embed.description += f'\N{BULLET} {thing}'
        return embed

    def check(self, reaction, user):
        return user == self.target and reaction.message.id == self.message.id

    async def loop(self):
        while True:
            reaction, user = await self.bot.wait_for('reaction_add',
                                                     check=self.check)
            action, _ = discord.utils.find(
                lambda action, emoji: emoji == reaction.emoji,
                list(self.EMOJIS.items())
            )

    async def start(self):
        message = self.message = self.location.send(embed=self.embed())
        for reaction in self.EMOJIS.values():
            await message.add_reaction(reaction)
        await self.loop()


class Wizard:
    CONFIRM_EMOJIS = {
        'positive': '\N{WHITE HEAVY CHECK MARK}',
        'negative': '\N{NO ENTRY SIGN}'
    }

    def __init__(self, *, target, location, bot):
        self.bot = bot
        self.target = target
        self.location = location

    async def wait_for(self, event, *, check=_noop):
        def _check(*args, **kwargs):
            for arg in args:
                result = check_event_arg(arg, target=self.target,
                                         location=self.location)
                if not result:
                    return False
            return check(*args, **kwargs)
        return await self.bot.wait_for(event, check=_check)

    async def prompt(self, *args, check=None, **kwargs):
        await self.location.send(*args, **kwargs)
        while True:
            response = await self.wait_for('message')
            if not check or check(response):
                return response.content

    async def pick(self, choices, *args, **kwargs):
        def check(message):
            return message.content in choices
        return await self.prompt(*args, **kwargs, check=check)

    async def confirm(self, *args, emoji=None, **kwargs):
        emoji = emoji or self.CONFIRM_EMOJIS
        message = await self.location.send(*args, **kwargs)
        for emoji in self.CONFIRM_EMOJIS.values():
            await message.add_reaction(emoji)
        while True:
            reaction, user = await self.wait_for('reaction_add')
            if reaction.emoji in self.CONFIRM_EMOJIS.values():
                return reaction.emoji == self.CONFIRM_EMOJIS['positive']
