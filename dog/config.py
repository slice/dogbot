from typing import Union, Dict

from lifesaver.bot import BotConfig


class DogConfig(BotConfig):
    oauth: Dict[str, Union[int, str]]
    web: Dict[str, str]
