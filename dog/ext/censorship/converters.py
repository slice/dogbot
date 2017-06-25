from dog.core.utils import EnumConverter
from dog.ext.censorship import CensorType, PunishmentType


class CensorTypeConverter(EnumConverter):
    enum = CensorType
    bad_argument_text = 'Invalid censorship type! Use `d?cs list` to view valid censorship types.'


class PunishmentTypeConverter(EnumConverter):
    enum = PunishmentType
    bad_argument_text = 'Invalid punishment type. List of punishment types: ' \
                        '<https://github.com/sliceofcode/dogbot/wiki/Censorship#punishments>'
