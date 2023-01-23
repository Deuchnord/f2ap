import logging

import toml
import humps
import requests

from typing import Callable, Union
from .enum import Visibility


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
        self.avatar_type = None
        self.header = header
        self.header_type = None
        self.following = followings if followings is not None else []
        self.attachments = attachments

        avatar_header_preferred_mimes = [
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
        ]

        for what, url in [("avatar", avatar), ("header", header)]:
            if url is None:
                continue

            try:
                r = requests.head(url)
                r.raise_for_status()
                content_type = r.headers.get("Content-Type")

                if content_type is None:
                    logging.warning(
                        f"Could not determine the type of the {what} at {url}:"
                        f" server does not provide a Content-Type."
                        f" It may not appear on social applications."
                    )
                elif not content_type.startswith("image/"):
                    logging.warning(
                        f"The {what} at {url} is reported with MIME type {content_type},"
                        f" which does not match an image. It may not appear on social applications."
                    )
                elif content_type not in avatar_header_preferred_mimes:
                    logging.warning(
                        f"The {what} at {url} is reported with MIME type {content_type},"
                        f" which is unusual image type for the Web"
                        f" (usual images types are {', '.join(avatar_header_preferred_mimes)})."
                        f" It may not appear on social applications."
                    )

                if what == "avatar":
                    self.avatar_type = content_type
                else:
                    self.header_type = content_type

            except requests.HTTPError as e:
                logging.warning(
                    f"Could not load the {what} metadata at {url}: {e}."
                    f" It may not appear correctly on social applications."
                )

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


class Comments:
    def __init__(
        self,
        enable: bool = False,
        js_widget: bool = False,
        minimal_visibility: Visibility = Visibility.PUBLIC,
        accept_sensitive: bool = False,
    ):
        self.enable = enable
        self.js_widget = js_widget
        self.minimal_visibility = minimal_visibility
        self.accept_sensitive = accept_sensitive


def get_config(file_path: str) -> Configuration:
    with open(file_path) as file:
        content = toml.loads(file.read())

    return Configuration(**content)
