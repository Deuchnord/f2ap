import re
import requests
import logging

from dateutil import parser as dateparser
from typing import Union, Optional, Callable
from uuid import uuid4

from . import postie, model, signature, html
from .config import Configuration
from .data import Database
from .enum import Visibility
from .exceptions import UnauthorizedHttpError
from .markdown import parse_markdown

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


def get_actor(href: str) -> dict:
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


def handle_inbox(
    config: Configuration,
    db: Database,
    headers: dict,
    inbox: dict,
    on_following_accepted: Callable,
) -> Union[None, tuple[dict, dict]]:
    actor = get_actor_from_inbox(db, inbox)
    if actor is None:
        return

    check_message_signature(config, actor, headers, inbox)

    return actor, handle_inbox_message(db, inbox, on_following_accepted, config.message.accept_responses)


def get_actor_from_inbox(db: Database, inbox: dict) -> dict:
    try:
        actor = requests.get(inbox.get("actor"), headers={"Accept": MIME_JSON_ACTIVITY})

        actor.raise_for_status()

        actor = actor.json()
        return actor

    except requests.exceptions.HTTPError:
        # If the message says the actor has been deleted, delete it from the followers (if they were following)
        if inbox.get("type") == "Delete" and inbox.get("actor") == inbox.get("object"):
            db.delete_follower(inbox.get("object"))

        return None


def check_message_signature(
    config: Configuration, actor: dict, headers: dict, inbox: dict
):
    public_key_pem = actor.get("publicKey", {}).get("publicKeyPem")

    try:
        if public_key_pem is None:
            raise ValueError("Missing public key on actor.")

        signature.validate_headers(
            public_key_pem, headers, f"/actors/{config.actor.preferred_username}/inbox"
        )

        return

    except ValueError as e:
        logging.debug(f"Could not validate signature: {e.args[0]}. Request rejected.")
        logging.debug(f"Headers: {headers}")
        logging.debug(f"Public key: {public_key_pem}")
        logging.debug(inbox)

        raise UnauthorizedHttpError(str(e))


def handle_inbox_message(
    db: Database, inbox: dict, on_following_accepted: Callable, accept_responses: bool
) -> Optional[dict]:
    if (
        inbox.get("type") == "Accept"
        and inbox.get("object", {}).get("type") == "Follow"
    ):
        on_following_accepted(inbox.get("object").get("id"), inbox.get("actor"))
        logging.debug(f"Following {inbox.get('actor')} successful.")
        return

    if inbox.get("type") == "Follow":
        db.insert_follower(inbox.get("actor"))
        return {"type": "Accept", "object": inbox}

    if inbox.get("type") == "Undo" and inbox.get("object", {}).get("type") == "Follow":
        db.delete_follower(inbox.get("actor"))
        return

    if accept_responses and inbox.get("type") == "Create" and inbox.get("object", {}).get("type") == "Note":
        # Save comments to a note
        note = inbox.get("object")
        in_reply_to = note.get("inReplyTo")
        if in_reply_to is None:
            return

        replying_to = db.get_note(in_reply_to)
        if replying_to is None:
            return

        content = html.sanitize(note["content"])
        published_at = dateparser.isoparse(note["published"])
        db.insert_comment(
            replying_to,
            note["id"],
            published_at,
            note["attributedTo"],
            content,
            get_note_visibility(note),
            note["tag"],
        )

        return

    if inbox.get("type") == "Delete":
        o = inbox.get("object", {})
        if not isinstance(o, dict):
            logging.debug(f"Tried to delete unsupported object: {inbox}")
            return

        # Tombstone might be a Note, try to delete it.
        # Note: this is always done, even when accept_responses is False, just in case it has been disabled lately.
        db.delete_comment(o.get("id"))

        return

    logging.debug(f"Unsupported message received in the inbox: {inbox}")


def get_note_visibility(note: dict) -> Visibility:
    author = get_actor(note.get("attributedTo"))
    if author is None:
        return Visibility.MENTIONED_ONLY

    if model.W3C_ACTIVITYSTREAMS_PUBLIC not in [*note.get("to"), *note.get("cc")]:
        if author.get("followers") in [*note.get("to", []), *note.get("cc", [])]:
            return Visibility.FOLLOWERS_ONLY

        return Visibility.MENTIONED_ONLY

    return Visibility.PUBLIC
