from discord.ext import commands


class DogbotHelpFormatter(commands.HelpFormatter):
    def get_ending_note(self):
        note = super().get_ending_note()
        invite = self.context.bot.cfg['bot']['woof']['invite']
        return note if not self.is_bot() else note + '\nNeed help? Visit the support server: ' + invite
