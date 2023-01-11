import toml
import humps

from typing import Callable, Union


class Website:
    def __init__(self, url: str, feed: str, update_freq: int = 30):
        self.url = url
        self.feed = feed
        self.update_freq = update_freq


class Configuration:
    def __init__(self, url: str, db: str, website: dict, actor: dict, message: dict):
        self.db = db

        self.url = url
        self.website = Website(**website)
        self.actor = Actor(self, **actor)
        self.message = Message(**message)


class Actor:
    def __init__(
        self,
        config: Configuration,
        username: str,
        public_key: str,
        private_key: str,
        display_name: str = None,
        summary: str = None,
        avatar: str = None,
        header: str = None,
        followings: [str] = None,
        attachments: {str: str} = None,
    ):
        self.config = config
        self.preferred_username = username
        self.display_name = display_name
        self.summary = summary
        self.avatar = avatar
        self.header = header
        self.following = followings if followings is not None else []
        self.attachments = attachments

        with open(public_key, "r") as file:
            self.public_key = file.read()
        with open(private_key, "r") as file:
            self.private_key = file.read()

    @property
    def id(self) -> str:
        return f"https://{self.config.url}/actors/{self.preferred_username}"

    @property
    def key_id(self) -> str:
        return f"{self.id}#main-key"

    @property
    def inbox(self) -> str:
        return f"{self.id}/inbox"

    @property
    def outbox(self) -> str:
        return f"{self.id}/outbox"

    @property
    def following_link(self) -> str:
        return f"{self.id}/following"

    @property
    def followers_link(self) -> str:
        return f"{self.id}/followers"


class Message:
    def __init__(
        self, format: str, tag_format: str = "camelCase", groups: [str] = None
    ):
        valid_tag_formats = self.get_tags_formatters().keys()

        self.format = format

        if tag_format not in valid_tag_formats:
            raise ValueError(
                "Invalid tag format, must be one of the following: %s"
                % ", ".join(valid_tag_formats)
            )

        self.tag_format = tag_format
        self.groups = groups if groups is not None else []

    @staticmethod
    def get_tags_formatters() -> {str: Callable}:
        return {
            "camelCase": humps.camelize,
            "CamelCase": humps.pascalize,
            "snake_case": humps.decamelize,
        }

    def get_tags_formatter(self) -> Union[Callable, None]:
        return self.get_tags_formatters().get(self.tag_format)


def get_config(file_path: str) -> Configuration:
    with open(file_path) as file:
        content = toml.loads(file.read())

    return Configuration(**content)
