import random
import time
from itertools import islice
from typing import Any, Dict, List

import discord
import lifesaver
from discord import User
from discord.ext import commands
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
    return '.'.join([i, (d + '0' * n)[:n]])


def format(amount: float, *, symbol: bool = False) -> str:
    amount = truncate_float(amount)
    if symbol:
        return f'{amount} {CURRENCY_SYMBOL}'
    return f'{amount} {CURRENCY_NAME}' if amount == 1.0 else f'{amount} {CURRENCY_NAME_PLURAL}'


def currency(string: str) -> float:
    try:
        result = float(string)
        if result == float('inf') or result <= 0:
            raise commands.BadArgument('Invalid amount.')
        return result
    except ValueError:
        raise commands.BadArgument('Invalid number.')


def _wallet_mirror(key):
    @property
    def _generated(self):
        return self.wallet[key]

    @_generated.setter
    def _generated(self, value):
        self.wallet[key] = value

    return _generated


class Wallet:
    def __init__(self, user: User, wallet: Dict[str, Any], *, manager: 'CurrencyManager'):
        self.user = user
        self.manager = manager
        self.wallet = wallet

    balance = _wallet_mirror('balance')
    last_stole = _wallet_mirror('last_stole')
    passive_chance = _wallet_mirror('passive_chance')
    passive_cooldown = _wallet_mirror('passive_cooldown')

    def add_passive(self, amount: float):
        if self.passive_cooldown and (time.time() - self.passive_cooldown) < 60:
            return False
        self.passive_cooldown = time.time()
        self.balance += amount

    async def commit(self):
        await self.manager.set_raw_wallet(self.user, self.wallet)

    async def delete(self):
        await self.manager.storage.delete(self.user.id)

    @classmethod
    async def convert(cls, ctx: lifesaver.Context, argument: str):
        user = await commands.MemberConverter().convert(ctx, argument)
        cog: 'Currency' = ctx.cog
        if not cog.manager.has_wallet(user):
            raise BadArgument(f"{user} doesn't have a wallet. They can create one by sending `{ctx.prefix}register`.")
        return cog.manager.get_wallet(user)


class CurrencyManager:
    def __init__(self, file, *, bot):
        self.bot = bot
        self.storage = AsyncJSONStorage(file, loop=bot.loop)

    def has_wallet(self, user: User) -> bool:
        return self.storage.get(user.id) is not None

    def get_wallet(self, user: User) -> Wallet:
        return Wallet(user, self.storage.get(user.id), manager=self)

    async def set_raw_wallet(self, user: User, wallet: Dict[str, Any]):
        await self.storage.put(user.id, wallet)

    async def register(self, user: User):
        """Creates a wallet for a user."""
        await self.set_raw_wallet(user, {
            'balance': 1.0,
            'passive_chance': 0.3,
            'passive_cooldown': None,
            'last_stole': None,
        })

    def top(self, *, descending: bool = True) -> List[Wallet]:
        def expander(entry):
            user_id, wallet = entry
            return Wallet(self.bot.get_user(int(user_id)), wallet, manager=self)

        wallets = self.storage.all()
        return sorted(map(expander, wallets.items()), key=lambda wallet: wallet.balance, reverse=descending)


def invoker_has_wallet():
    def predicate(ctx):
        cog: Currency = ctx.cog
        if not cog.manager.has_wallet(ctx.author):
            raise commands.CheckFailure(f"You don't have a wallet! You can create one by sending `{ctx.prefix}register`.")
        ctx.wallet = cog.manager.get_wallet(ctx.author)
        return True

    return commands.check(predicate)


class Currency(lifesaver.Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.manager = CurrencyManager('currency.json', bot=bot)

    @lifesaver.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if not msg.guild or msg.author.bot or self.bot.is_blacklisted(msg.author):
            return

        if not self.manager.has_wallet(msg.author):
            return

        wallet = self.manager.get_wallet(msg.author)
        if random.random() > (1.0 - wallet.passive_chance):
            wallet.add_passive(0.3)
            await wallet.commit()

    @lifesaver.command(hidden=True)
    @commands.is_owner()
    async def write(self, ctx: lifesaver.Context, target: Wallet, amount: float):
        """Sets someone's balance."""
        target.balance = amount
        await target.commit()
        await ctx.ok()

    @lifesaver.command(aliases=['transfer'])
    @invoker_has_wallet()
    async def send(self, ctx: lifesaver.Context, target: Wallet, amount: currency):
        """Sends currency to someone else."""
        if target.user == ctx.author:
            await ctx.send("You cannot send money to yourself.")
            return

        if amount > ctx.wallet.balance:
            await ctx.send(f"You don't have that much money, {ctx.author.mention}.")
            return

        ctx.wallet.balance -= amount
        target.balance += amount
        await ctx.wallet.commit()
        await target.commit()

        await ctx.send("Transaction completed.")

    @lifesaver.command()
    async def register(self, ctx: lifesaver.Context):
        """Creates a wallet."""
        if self.manager.has_wallet(ctx.author):
            await ctx.send("You already have a wallet.")
            return
        await self.manager.register(ctx.author)
        await ctx.ok()

    @lifesaver.command(hidden=True)
    @commands.is_owner()
    @invoker_has_wallet()
    async def bail(self, ctx: lifesaver.Context, *, target: Wallet = None):
        """Busts someone out of jail."""
        wallet = target or ctx.wallet
        wallet.last_stole = None
        await wallet.commit()
        await ctx.send(f'\N{CHAINS} {"You are" if wallet.user == ctx.author else f"{target.user} is"} free to go.')

    @lifesaver.command()
    @invoker_has_wallet()
    async def steal(self, ctx: lifesaver.Context, target: Wallet, amount: currency):
        """
        Steals from someone.

        You cannot steal from someone who has never stolen.
        """
        if target.user == ctx.author:
            await ctx.send("You can't steal from yourself... You okay?")
            return
        if target.balance == 0:
            await ctx.send("You can't steal from someone who doesn't any money! For shame.")
            return

        thief: Wallet = ctx.wallet
        old_balance = thief.balance

        if target.balance < amount:
            await ctx.send(f"{target.user} doesn't have that much money.")
            return

        if thief.last_stole is not None and (time.time() - thief.last_stole) < 60 * 60 * 8:
            jail_time = human_delta(60 * 60 * 8 - (time.time() - thief.last_stole))
            await ctx.send(f"You can't steal yet, buddy. {jail_time} to go.")
            return

        thief.last_stole = time.time()
        await thief.commit()

        message = ''

        # chance #1: the amount of coins that the victim has
        # it gets easier to steal from someone with more coins, and vice versa
        # bottoms out at 60% success by 9.4 coins -- TODO: this isn't desirable, tweak this later.
        chance_result = random.uniform(0, 10)
        chance_threshold = max(-0.1 * (target.balance ** 2) + 9, 6)

        # chance #2: the percentage of coins that the thief is trying to steal to the victim's wallet
        #            (100% is the victim's entire wallet, 0% is none)
        # stealing 10% is 90% chance, and stealing 100% is 0% chance (impossible)
        percentage = amount / target.balance
        amount_result = random.random()
        amount_threshold = 1 - (percentage ** 2)

        if chance_result > chance_threshold and amount_result < amount_threshold:
            thief.balance += amount
            target.balance -= amount
            await thief.commit()
            await target.commit()
            flavor = ['Nice one.', 'Do you feel the guilt sinking in?', 'But why would you do that?', 'Pretty evil.']
            message = f"**Steal succeeded.** {random.choice(flavor)}"
        else:
            new_balance = max(thief.balance - (amount / 2), 0)
            thief.balance = new_balance
            await thief.commit()
            flavor = ['You deserved that.', "That's what you get.", "Welp.", "Better try again later?", "Ouch.",
                      "Bad dog."]
            message = f"**Steal failed.** {random.choice(flavor)}"

        # show difference in thief balances
        new_balance = thief.balance
        results = (f'Your {CURRENCY_NAME_PLURAL}: '
                   f'{format(old_balance, symbol=True)} \N{RIGHTWARDS ARROW} {format(new_balance, symbol=True)}')

        # show chances of the stealing algorithm
        schance_balance = (10 - chance_threshold) / 10
        schance_amount = amount_threshold
        schance_overall = schance_balance * schance_amount
        tf = truncate_float  # shortcut
        results += (f'\n\nBased on how much they have: {tf(schance_balance * 100)}% chance of success\n'
                    f'Based on how much you wanted to steal: {tf(schance_amount * 100)}% chance of success\n\n'
                    f'**Overall chance of success: {tf(schance_overall * 100)}%**')

        await ctx.send(f'{message}\n\n{results}')

    @lifesaver.command()
    @invoker_has_wallet()
    async def donate(self, ctx: lifesaver.Context, amount: currency):
        """
        Donates some currency.

        This will increase the chance of you passively gaining currency, to a maximum of 50%.
        """
        if ctx.wallet.passive_chance >= 0.5:
            await ctx.send("Your chance is at max! (50%)")
            return

        if ctx.wallet.balance < amount:
            await ctx.send("Not enough funds.")
            return

        percent_increase = min((amount / 100) * 0.5, 0.5 - ctx.wallet.passive_chance)
        ctx.wallet.passive_chance += percent_increase
        ctx.wallet.balance -= amount
        await ctx.wallet.commit()
        await ctx.send(
            f'Your chance of gaining {CURRENCY_NAME_PLURAL} is now {truncate_float(ctx.wallet.passive_chance * 100)}% '
            f'(up by {truncate_float(percent_increase * 100)}%).'
        )

    @lifesaver.command(aliases=['slots'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    @invoker_has_wallet()
    async def spin(self, ctx: lifesaver.Context):
        """Gamble your life away."""
        fee = 0.5

        if ctx.wallet.balance < fee:
            await ctx.send(f"You need at least 0.5 {CURRENCY_SYMBOL} to spin.")
            return

        emojis = ['\N{CHERRIES}', '\N{AUBERGINE}', '\N{TANGERINE}', '\N{LEMON}', '\N{GRAPES}', CURRENCY_SYMBOL]

        results = [random.choice(emojis) for _ in range(3)]
        results_formatted = ' '.join(results)
        net = -fee
        message = f"\N{NEUTRAL FACE} Nothing interesting."
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

        footer = (f'{message} You have lost {format(abs(net), symbol=True)}.' if net < 0 else
                  f'{message} You have gained {format(net, symbol=True)}.')
        await ctx.send(f"{ctx.author.mention}'s Slot Machine\n\n|  {results_formatted}  |\n\n{footer}")
        ctx.wallet.balance += net
        await ctx.wallet.commit()

    @lifesaver.command()
    @invoker_has_wallet()
    async def delete(self, ctx: lifesaver.Context):
        """Deletes your wallet."""
        if not await ctx.confirm(title='Are you sure?',
                                 message=f'All of your {CURRENCY_NAME_PLURAL} will be lost forever.',
                                 delete_after=True, cancellation_message='Cancelled.'):
            return

        await ctx.wallet.delete()
        await ctx.ok()

    @lifesaver.command(hidden=True)
    @commands.is_owner()
    async def smash(self, ctx: lifesaver.Context, target: Wallet):
        """Delete someone else's wallet."""
        await target.delete()
        await ctx.ok()

    @lifesaver.command()
    async def top(self, ctx: lifesaver.Context):
        """Views the top users."""
        table = Table('User', 'Balance', 'Chance')
        for wallet in islice(self.manager.top(), 10):
            chance = f"{truncate_float(wallet.passive_chance * 100)}%"
            table.add_row(str(wallet.user) if wallet.user else '???', truncate_float(wallet.balance), chance)
        table = await table.render(loop=self.bot.loop)
        await ctx.send(codeblock(table))

    @lifesaver.command()
    @invoker_has_wallet()
    async def wallet(self, ctx: lifesaver.Context, *, target: Wallet = None):
        """Views your current wallet balance."""
        wallet = target or ctx.wallet
        chance = f"{wallet.passive_chance * 100}%"
        await ctx.send(f'{wallet.user} > {format(wallet.balance, symbol=True)} ({truncate_float(chance)} chance)')


def setup(bot):
    bot.add_cog(Currency(bot))
