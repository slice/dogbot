import yaml

# change these
OUTPUT = '../dogbot.wiki/Command-List.md'
INPUT = 'cmdlist/command_list.yml'

data = yaml.load(open(INPUT, 'r'))
out = open(OUTPUT, 'w')

def w(*args):
    print(*args, file=out)

for section in data.keys():
    # beginning of this section
    w(f'## {section}')
    print('-->', section)

    commands = data[section]
    for name, command in commands.items():
        usage = f' {command["usage"]}' if 'usage' in command else ''
        w(f'### `d?{name}{usage}`')

        # output aliases
        if 'aliases' in command:
            w(f'#### Aliases')
            for alias in command['aliases']:
                w(f'- `d?{alias}`')
            w()

        if 'you_need' in command:
            MOD = '[Dog Moderator](https://github.com/sliceofcode/dogbot/wiki/Moderators)'
            you_need = [MOD if n == 'Dog Moderator' else n for n in command['you_need']]
            w(f'**You need:** {", ".join(you_need)}')
            w()

        if 'bot_needs' in command:
            w(f'**Bot needs:** {", ".join(command["bot_needs"])}')
            w()

        w(command['description'])

        if 'examples' in command:
            w('#### Examples')
            for example in command['examples']:
                w(f'- `d?{example["usage"]}`: {example["description"]}')
