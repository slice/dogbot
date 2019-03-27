from discord.ext import commands


class HelpCommand(commands.DefaultHelpCommand):
    def get_ending_note(self):
        ending_note = super().get_ending_note()
        invite = self.context.bot.config.server_invite

        if self.get_destination() == self.context.author:
            return f'Join the server: {invite}\n{ending_note}'

        return ending_note
