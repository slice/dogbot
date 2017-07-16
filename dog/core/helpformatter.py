from discord.ext import commands

INVITE = 'https://discord.gg/JMYdXtq'


class DogbotHelpFormatter(commands.HelpFormatter):
    pass
    # def get_ending_note(self):
    #     note = super().get_ending_note()
    #     return note if not self.is_bot() else note + '\nNeed help? Visit the support server: ' + INVITE
