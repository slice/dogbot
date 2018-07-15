import discord

from lifesaver.utils.formatting import pluralize, clean_mentions

__all__ = ['stringify_message']


def stringify_message(message: discord.Message) -> str:
    content = message.content
    content = clean_mentions(message.channel, content)

    if message.attachments:
        urls = [attachment.url for attachment in message.attachments]
        content += f' {" ".join(urls)}'

    if message.embeds:
        content += f' ({pluralize(with_quantity=True, embed=len(message.embeds))})'

    return f'<{message.author.name}> {content}'
