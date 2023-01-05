import re
import requests
import logging

from typing import Union
from uuid import uuid4

from . import postie, model
from .config import Configuration
from .markdown import parse_markdown, find_hashtags

W3_PUBLIC_STREAM = "https://www.w3.org/ns/activitystreams#Public"

MIME_JSON_ACTIVITY = "application/activity+json"


def search_actor(domain: str, username: str) -> Union[None, dict]:
    try:
        actor = requests.get(
            f"https://{domain}/.well-known/webfinger",
            params={"resource": f"acct:{username}@{domain}"},
            headers={"Accept": MIME_JSON_ACTIVITY},
        )

        actor.raise_for_status()

        for link in actor.json().get("links"):
            if (
                link.get("rel") == "self"
                and link.get("type") == "application/activity+json"
            ):
                return get_actor(link.get("href"))

        return None

    except requests.HTTPError:
        return None


def get_actor(href: str):
    try:
        actor = requests.get(href, headers={"Accept": "application/activity+json"})
        actor.raise_for_status()
        return actor.json()
    except requests.HTTPError:
        return None


def parse_user(
    string: str, full_string: bool = True
) -> Union[Union[tuple[(str, str)], None], list[(str, str)]]:
    begin = "^" if full_string else ""
    end = "$" if full_string else ""

    pattern = re.compile(
        f"{begin}@(?P<username>[a-zA-Z0-9_]+)@(?P<domain>[a-z0-9_.-]+){end}"
    )
    matches = pattern.findall(string)

    if full_string:
        if len(matches) == 1:
            return matches[0]

        return None

    return matches


def follow_users(config: Configuration, users: [str]):
    for user in users:
        username, domain = parse_user(user)
        actor = search_actor(domain, username)

        if actor is None:
            logging.error(f"Cannot follow {user}: not found.")
            continue

        inbox = actor.get("inbox")
        if inbox is None:
            logging.error(f"Cannot follow {user}: no inbox.")
            continue

        try:
            postie.deliver(
                config,
                inbox,
                {
                    "id": f"https://{config.url}/{uuid4()}",
                    "type": "Follow",
                    "actor": config.actor.id,
                    "object": f"{actor.get('id')}",
                },
            )

            logging.debug(f"Sent follow request to {actor.get('id')}")
        except postie.DeliveryException as e:
            logging.error(f"Cannot follow {user}: {e.message}")


def unfollow_users(config: Configuration, users: [tuple[str, str]]):
    for follow_id, user in users:
        actor = get_actor(user)

        if actor is None:
            logging.error(f"Cannot unfollow {user}: not found.")
            continue

        inbox = actor.get("inbox")
        if inbox is None:
            logging.error(f"Cannot unfollow {user}: no inbox.")
            continue

        try:
            postie.deliver(
                config,
                inbox,
                {
                    "id": f"https://{config.url}/{uuid4()}",
                    "type": "Undo",
                    "actor": config.actor.id,
                    "object": {
                        "id": follow_id,
                        "type": "Follow",
                        "actor": config.actor.id,
                        "object": actor.get("id"),
                    },
                },
            )

            logging.debug(f"Unfollowed {actor.get('id')}")
        except postie.DeliveryException as e:
            logging.error(f"Cannot unfollow {user}: {e.message}")


def propagate_messages(
    config: Configuration, inboxes: [str], messages: [model.Message]
):
    for message in messages:
        message.object.content = parse_markdown(message.object.content)
        for inbox in inboxes:
            postie.deliver(config, inbox, message.dict())
