import inspect
import itertools

from discord.ext.commands import Paginator, HelpFormatter
from discord.ext.commands.core import Command


class DogbotHelpFormatter(HelpFormatter):
    def get_ending_note(self):
        if self.context.bot.is_private:
            return super().get_ending_note()

        note = super().get_ending_note()
        invite = self.context.bot.cfg['bot']['woof']['invite']
        return note if not self.is_bot(
        ) else note + '\nNeed help? Visit the support server: ' + invite

    def format_help(self, description):
        # for each paragraph in the description, replace a newline with a space.
        return '\n\n'.join(
            para.replace('\n', ' ') for para in description.split('\n\n'))

    async def format(self):
        """A modified copy of Discord.py rewrite's vanilla HelpFormatter.format()."""
        self._paginator = Paginator()

        # we need a padding of ~80 or so
        description = self.command.description if not self.is_cog(
        ) else inspect.getdoc(self.command)

        if description:
            # <description> portion
            self._paginator.add_line(description, empty=True)

        if isinstance(self.command, Command):
            # <signature portion>
            signature = self.get_command_signature()
            self._paginator.add_line(signature, empty=True)

            # <long doc> section
            if self.command.help:
                self._paginator.add_line(
                    self.format_help(self.command.help), empty=True)

            # end it here if it's just a regular command
            if not self.has_subcommands():
                self._paginator.close_page()
                return self._paginator.pages

        max_width = self.max_name_size

        def category(tup):
            cog = tup[1].cog_name
            # we insert the zero width space there to give it approximate
            # last place sorting position.
            return cog + ':' if cog is not None else '\u200bCommands:'

        filtered = await self.filter_command_list()
        if self.is_bot():
            data = sorted(filtered, key=category)
            for category, commands in itertools.groupby(data, key=category):
                # there simply is no prettier way of doing this.
                commands = sorted(commands)
                if len(commands) > 0:
                    self._paginator.add_line(category)

                self._add_subcommands_to_page(max_width, commands)
        else:
            filtered = sorted(filtered)
            if filtered:
                self._paginator.add_line('Commands:')
                self._add_subcommands_to_page(max_width, filtered)

        # add the ending note
        self._paginator.add_line()
        ending_note = self.get_ending_note()
        self._paginator.add_line(ending_note)
        return self._paginator.pages
