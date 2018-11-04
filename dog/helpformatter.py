from discord.ext import commands


class HelpFormatter(commands.HelpFormatter):
    @property
    def should_dm(self):
        return sum(map(len, self._paginator.pages)) > 1000

    def get_ending_note(self):
        is_in_dm = self.context.guild is None
        ending_note = super().get_ending_note()
        invite = self.context.bot.config.server_invite

        if (is_in_dm or self.should_dm) and invite:
            return f'Join the server: {invite}\n{ending_note}'
        else:
            return ending_note
