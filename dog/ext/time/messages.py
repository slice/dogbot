# explicit examples of the command, and what they can supply
TIME_SET_EXAMPLE = (
    "For example: `{prefix}t set London`, `{prefix}t set Arizona`, or "
    "`{prefix}t set Germany`. You can type in the name of a country, state, "
    "city, region, etc."
)

TIME_SET_EXAMPLE_THIRD_PERSON = TIME_SET_EXAMPLE.replace("You can", "They can")

UNKNOWN_LOCATION = (
    "I couldn't find that place. Please give a location as if you were "
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

TIMEZONE_SAVED_EMBED = (
    "Saved your timezone.\n\n"
    "Use `{prefix}t` to show others your time, or use `{prefix}t <user>` to check someone else's time."
)

TIMEZONE_SAVED = (
    "Saved your timezone. The current time is **{time}**.\n\n"
    "Use `{prefix}t` to show others your time, or use `{prefix}t <user>` to check someone else's time."
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

OPENSTREETMAP_ATTRIBUTION = (
    "Geolocation powered by OpenStreetMap (openstreetmap.org/copyright)"
)
