# explicit examples of the command, and what they can supply
TIME_SET_EXAMPLE = (
    "For example: `{prefix}t set London`, `{prefix}t set Arizona`, or "
    "`{prefix}t set Germany`. You can type in the name of a country, state, "
    "city, region, etc."
)

TIME_SET_EXAMPLE_THIRD_PERSON = TIME_SET_EXAMPLE.replace("You can", "They can")

UNABLE_TO_RESOLVE_LOCATION = (
    "Can't resolve that location. Please give a location as if you were "
    "searching for something on Google Maps.\n\n" + TIME_SET_EXAMPLE
)

# a "command" to the user to set their timezone before explicit examples
TYPE_COMMAND = "Type `{prefix}t set <location>` to set it. " + TIME_SET_EXAMPLE

NO_TIMEZONE_SO_NO_COMMAND = (
    "You haven't set your timezone yet, so you can't use this command. " + TYPE_COMMAND
)

NO_AUTHOR_TIMEZONE = "You haven't set your timezone yet. " + TYPE_COMMAND

NO_TARGET_TIMEZONE = (
    "{other} hasn't set their timezone yet. They can set it by typing "
    "`{prefix}t set <location>`. " + TIME_SET_EXAMPLE_THIRD_PERSON
)

TIMEZONE_SAVED = (
    "Saved your timezone. It is {time} right now. {greeting}\n\n"
    "Use `{prefix}t` to check the time, "
    "or `{prefix}t <user>` to check what time it is for someone else."
)

QUOTA_EXCEEDED = "Can't resolve that location right now. Please try again later."

HARD_OFFSET_WARNING = (
    "You are manually specifying a UTC offset. If your region uses daylight "
    "savings time, I won't be able to reflect clock changes when `{prefix}t` "
    "is used."
)

DEPRECATED_TIMEZONE = (
    "That timezone is too broad, vague, or ambiguous. "
    "In order for me to handle daylight saving time correctly, please provide "
    "a narrower timezone instead of a three-letter timezone code.\n\n"
    + TIME_SET_EXAMPLE
)

DIFFERENCE = (
    "You and {source} are **{difference}** hours away from each other.\n\n"
    "When it's {our_time} for you it would be {their_time} {possessive} {source}."
)
