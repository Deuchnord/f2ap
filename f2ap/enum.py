from enum import Enum


class Visibility(Enum):
    PUBLIC = 1
    FOLLOWERS_ONLY = 2
    MENTIONED_ONLY = 3
    DIRECT_MESSAGE = MENTIONED_ONLY
