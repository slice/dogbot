import random
from itertools import islice
from typing import Dict, Any, Tuple, List

import discord
import time
from discord import User
from discord.ext.commands import is_owner, BadArgument, cooldown, BucketType
from lifesaver.bot import Cog, command, Context
from lifesaver.bot.storage import AsyncJSONStorage
from lifesaver.utils.formatting import Table, codeblock, human_delta

CURRENCY_NAME = 'treat'
CURRENCY_NAME_PLURAL = 'treats'
CURRENCY_SYMBOL = '\N{MEAT ON BONE}'


# https://stackoverflow.com/a/783927/2491753
def truncate_float(f: float, n: int = 2) -> str:
    """Truncates/pads a float f to n decimal places without rounding."""
    s = '{}'.format(f)
    if 'e' in s or 'E' in s:
        return '{0:.{1}f}'.format(f, n)
    i, p, d = s.partition('.')
    return '.'.join([i, (d+'0'*n)[:n]])


def format(amount: float, *, symbol: bool = False) -> str:
    amount = truncate_float(amount)
    if symbol:
        return f'{amount} {CURRENCY_SYMBOL}'
    return f'{amount} {CURRENCY_NAME}' if amount == 1.0 else f'{amount} {CURRENCY_NAME_PLURAL}'


def currency(string: str) -> float:
    try:
        result = float(string)
        if result == float('inf') or result <= 0:
            raise BadArgument('Invalid amount.')
        return result
    except ValueError:
        raise BadArgument('Invalid number.')


Wallet = Dict[str, Any]


class CurrencyManager:
    def __init__(self, file, *, loop):
        self.storage = AsyncJSONStorage(file, loop=loop)

    def has_wallet(self, user: User) -> bool:
        return self.storage.get(user.id) is not None

    def get_wallet(self, user: User) -> Wallet:
        return self.storage.get(user.id)

    async def set_wallet(self, user: User, wallet: Wallet):
        await self.storage.put(user.id, wallet)

    ###

    def bal(self, user: User) -> float:
        return self.get_wallet(user)['balance']

    async def write(self, user: User, amount: float):
        wallet = self.get_wallet(user)
        wallet['balance'] = amount
        await self.set_wallet(user, wallet)

    async def register(self, user: User):
        """Creates a wallet for a user."""
        await self.set_wallet(user, {
            'balance': 0.0,
            'passive_chance': 0.3,
            'passive_cooldown': None,
            'last_stole': None,
        })

    ###

    async def add(self, user: User, amount: float):
        bal = self.bal(user)
        await self.write(user, bal + amount)

    async def add_passive(self, user: User, amount: float):
        wallet = self.get_wallet(user)
        if wallet['passive_cooldown'] and (time.time() - wallet['passive_cooldown']) < 60:
            return False
        wallet['passive_cooldown'] = time.time()
        wallet['balance'] += amount
        await self.set_wallet(user, wallet)
        return True

    async def sub(self, user: User, amount: float):
        return await self.add(user, -amount)

    def top(self, *, descending: bool = True) -> List[Tuple[int, Wallet]]:
        def key(entry):
            user_id, wallet = entry
            return wallet['balance']
        wallets = self.storage.all()
        return sorted(wallets.items(), key=key, reverse=descending)


class Currency(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.manager = CurrencyManager('currency.json', loop=bot.loop)

    async def on_message(self, msg: discord.Message):
        if not msg.guild or msg.author.bot or self.bot.is_blacklisted(msg.author):
            return

        if not self.manager.has_wallet(msg.author):
            return

        wallet = self.manager.get_wallet(msg.author)
        if random.random() > (1.0 - wallet['passive_chance']):
            await self.manager.add_passive(msg.author, 0.3)

    @command(hidden=True)
    @is_owner()
    async def write(self, ctx: Context, target: discord.Member, amount: float):
        """Sets someone's balance."""
        if not self.manager.has_wallet(target):
            await ctx.send(f"{target} does not have a wallet.")
            return
        await self.manager.write(target, amount)
        await ctx.ok()

    @command(aliases=['transfer'])
    async def send(self, ctx: Context, target: discord.Member, amount: currency):
        """Sends currency to someone else."""
        if target == ctx.author:
            await ctx.send("You cannot send money to yourself.")
            return

        if not self.manager.has_wallet(ctx.author) or not self.manager.has_wallet(target):
            await ctx.send("One of you don't have a wallet!")
            return

        if amount > self.manager.bal(ctx.author):
            await ctx.send(f"You don't have that much money, {ctx.author.mention}.")
            return

        await self.manager.sub(ctx.author, amount)
        await self.manager.add(target, amount)

        await ctx.send("Transaction completed.")

    @command()
    async def register(self, ctx: Context):
        """Creates a wallet."""
        if self.manager.has_wallet(ctx.author):
            await ctx.send("You already have a wallet.")
            return
        await self.manager.register(ctx.author)
        await ctx.ok()

    @command(hidden=True)
    @is_owner()
    async def bail(self, ctx: Context, *, target: discord.Member = None):
        """Busts someone out of jail."""
        target = target or ctx.author

        wallet = self.manager.get_wallet(target)
        wallet['last_stole'] = None
        await self.manager.set_wallet(target, wallet)
        await ctx.send(f'\N{CHAINS} {"You are" if target == ctx.author else f"{target} is"} free to go.')

    @command()
    async def steal(self, ctx: Context, target: discord.Member, amount: currency):
        """
        Steals from someone.

        You cannot steal from someone who has never stolen.
        """
        if target == ctx.author:
            await ctx.send("You can't steal from yourself...? You okay?")
            return
        if not self.manager.has_wallet(target) or self.manager.bal(target) == 0:
            await ctx.send("You can't steal from someone who doesn't any money! For shame.")
            return
        if not self.manager.has_wallet(ctx.author):
            await ctx.send("You don't have a wallet.")
            return

        thief = self.manager.get_wallet(ctx.author)
        old_balance = thief['balance']
        victim = self.manager.get_wallet(target)

        if victim['balance'] < amount:
            await ctx.send(f"{target} doesn't have that much money.")
            return

        if thief['last_stole'] is not None and (time.time() - thief['last_stole']) < 60 * 60 * 8:
            jail_time = human_delta(60 * 60 * 8 - (time.time() - thief['last_stole']))
            await ctx.send(f"You can't steal yet, buddy. {jail_time} to go.")
            return

        thief['last_stole'] = time.time()
        await self.manager.set_wallet(ctx.author, thief)

        message = ''

        # chance #1: the amount of coins that the victim has
        # it gets easier to steal from someone with more coins, and vice versa
        # bottoms out at 60% success by 9.4 coins -- TODO: this isn't desirable, tweak this later.
        chance_result = random.uniform(0, 10)
        chance_threshold = max(-0.1 * (victim['balance'] ** 2) + 9, 6)

        # chance #2: the percentage of coins that the thief is trying to steal to the victim's wallet
        #            (100% is the victim's entire wallet, 0% is none)
        # stealing 10% is 90% chance, and stealing 100% is 0% chance (impossible)
        percentage = amount / victim['balance']
        amount_result = random.random()
        amount_threshold = 1 - (percentage ** 2)

        if chance_result > chance_threshold and amount_result < amount_threshold:
            await self.manager.add(ctx.author, amount)
            await self.manager.sub(target, amount)
            flavor = ['Nice one.', 'Do you feel the guilt sinking in?', 'But why would you do that?', 'Pretty evil.']
            message = f"**Steal succeeded.** {random.choice(flavor)}"
        else:
            new_balance = max(thief['balance'] - (amount / 2), 0)
            await self.manager.write(ctx.author, new_balance)
            flavor = ['You deserved that.', "That's what you get.", "Welp.", "Better try again later?", "Ouch."]
            message = f"**Steal failed.** {random.choice(flavor)}"

        # show difference in thief balances
        new_balance = self.manager.bal(ctx.author)
        results = (f'Your {CURRENCY_NAME_PLURAL}: '
                   f'{format(old_balance, symbol=True)} \N{RIGHTWARDS ARROW} {format(new_balance, symbol=True)}')

        # show chances of the stealing algorithm
        schance_balance = (10 - chance_threshold) / 10
        schance_amount = amount_threshold
        schance_overall = schance_balance * schance_amount
        TF = truncate_float  # shortcut
        results += (f'\n\nBased on how much they have: {TF(schance_balance * 100)}% chance of success\n'
                    f'Based on how much you wanted to steal: {TF(schance_amount * 100)}% chance of success\n\n'
                    f'**Overall chance of success: {TF(schance_overall * 100)}%**')

        await ctx.send(message + '\n\n' + results)

    @command()
    async def donate(self, ctx: Context, amount: currency):
        """
        Donates some currency.

        This will increase the chance of you passively gaining currency, to a maximum of 50%.
        """
        if not self.manager.has_wallet(ctx.author):
            await ctx.send("You don't have a wallet.")
            return

        wallet = self.manager.get_wallet(ctx.author)
        if wallet['passive_chance'] >= 0.5:
            await ctx.send("Your chance is at max! (50%)")
            return

        if wallet['balance'] < amount:
            await ctx.send("Not enough funds.")
            return

        percent_increase = min((amount / 100) * 0.5, 0.5 - wallet['passive_chance'])
        wallet['passive_chance'] += percent_increase
        now = wallet['passive_chance'] * 100

        await self.manager.set_wallet(ctx.author, wallet)
        await self.manager.sub(ctx.author, amount)
        await ctx.send(
            f'Your chance of gaining {CURRENCY_NAME_PLURAL} is now {truncate_float(now)}% '
            f'(up by {truncate_float(percent_increase * 100)}%).'
        )

    @command(aliases=['slots'])
    @cooldown(1, 3, BucketType.user)
    async def spin(self, ctx: Context):
        """Gamble your life away."""
        if not self.manager.has_wallet(ctx.author):
            await ctx.send("You can't spin your life away without a wallet!")
            return

        fee = 0.5

        if self.manager.bal(ctx.author) < fee:
            await ctx.send(f"You need at least 0.5 {CURRENCY_SYMBOL} to spin.")
            return

        SYMBOLS = ['\N{CHERRIES}', '\N{AUBERGINE}', '\N{TANGERINE}', '\N{LEMON}', '\N{GRAPES}', CURRENCY_SYMBOL]

        results = [random.choice(SYMBOLS) for _ in range(3)]
        results_formatted = ' '.join(results)
        net = -fee
        message = f"\N{CRYING FACE} Nothing interesting."
        is_triple = results.count(results[0]) == 3
        is_two_in_a_row = results[0] == results[1] or results[1] == results[2]  # [X X o] or [o X X]

        if is_triple and results[1] == CURRENCY_SYMBOL:
            net = 3
            message = f'\U0001f631 **TRIPLE {CURRENCY_SYMBOL}!**'
        elif is_triple:
            net = 2
            message = f'\U0001f62e **TRIPLE!** You got 3 {results[1]}!'
        elif is_two_in_a_row:
            net = 1
            message = f'\U0001f604 **Two in a row!** You got 2 {results[1]} in a row!'
        else:
            for result in results:
                if results.count(result) == 2:
                    net = 0.5
                    message = f'\U0001f642 **Double!** You got 2 {result}!'
                    break

        footer = (f'{message} You have lost {abs(net)} {CURRENCY_SYMBOL}.' if net < 0 else
                  f'{message} You have gained {net} {CURRENCY_SYMBOL}.')
        await ctx.send(f"{ctx.author.mention}'s Slot Machine\n\n|  {results_formatted}  |\n\n{footer}")
        await self.manager.add(ctx.author, net)

    @command()
    async def delete(self, ctx: Context):
        """Deletes your wallet."""
        if not await ctx.confirm(title='Are you sure?', message=f'All {CURRENCY_NAME_PLURAL} will be lost forever.',
                                 delete_after=True, cancellation_message='Cancelled.'):
            return

        # TODO: abstract
        await self.manager.storage.delete(ctx.author.id)
        await ctx.ok()

    @command(hidden=True)
    @is_owner()
    async def smash(self, ctx: Context, target: discord.Member):
        """Delete someone else's wallet."""
        if not self.manager.has_wallet(target):
            await ctx.send(f"{target} doesn't have a wallet.")
            return

        # TODO: abstract
        await self.manager.storage.delete(target.id)
        await ctx.ok()

    @command()
    async def top(self, ctx: Context):
        """Views the top users."""
        table = Table('User', 'Balance', 'Chance')
        for (user_id, wallet) in islice(self.manager.top(), 10):
            balance = wallet['balance']
            chance = f"{truncate_float(wallet['passive_chance'] * 100)}%"
            user = self.bot.get_user(int(user_id))
            table.add_row(str(user) if user else user_id, truncate_float(balance), chance)
        table = await table.render(loop=self.bot.loop)
        await ctx.send(codeblock(table))

    @command()
    async def wallet(self, ctx: Context, *, target: discord.Member = None):
        """Views your current wallet balance."""
        target = target or ctx.author
        if not self.manager.has_wallet(target):
            subject = 'You' if target == ctx.author else ctx.author
            verb = 'You can send' if target == ctx.author else 'Ask them to send'
            await ctx.send(f"{subject} don't have a wallet. {verb} `{ctx.prefix}register` to make one.")
            return

        bal = self.manager.bal(target)
        chance = f"{self.manager.get_wallet(target)['passive_chance'] * 100}%"
        await ctx.send(f'{target} > {format(bal, symbol=True)} ({truncate_float(chance)}% chance)')


def setup(bot):
    bot.add_cog(Currency(bot))
