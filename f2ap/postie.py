import requests
import json
import base64
import hashlib
import logging

from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urlparse

from . import signature
from .config import Configuration
from .json import ActivityJsonEncoder


class DeliveryException(requests.exceptions.HTTPError):
    def __init__(self, status_code: int, msg: str):
        self.status_code = status_code
        self.message = msg

    def __str__(self):
        return f"Got HTTP {self.status_code} status code. Message was: {self.message}"


def deliver(config: Configuration, inbox: str, message: dict):
    parsed_inbox = urlparse(inbox)

    if "@context" not in message:
        message["@context"] = "https://www.w3.org/ns/activitystreams"

    logging.debug(f"Sending message to {inbox}:")
    logging.debug(message)

    digest = hashlib.sha256(json.dumps(message, cls=ActivityJsonEncoder).encode())
    b64digest = base64.b64encode(digest.digest()).decode()
    fdt = datetime.now(tz=timezone.utc)

    headers = {
        "Host": parsed_inbox.hostname,
        "Date": format_datetime(fdt, usegmt=True),
        "Digest": f"SHA-256={b64digest}",
        "Content-Type": "application/activity+json",
        "Accept": "application/activity+json",
    }

    headers["Signature"] = signature.sign_headers(config, parsed_inbox.path, headers)

    req = requests.post(
        inbox, data=json.dumps(message, cls=ActivityJsonEncoder), headers=headers
    )

    try:
        req.raise_for_status()
    except requests.HTTPError:
        raise DeliveryException(req.status_code, req.content.decode())
