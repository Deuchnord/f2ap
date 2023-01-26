from os import path, remove
from uuid import uuid4

from f2ap.config import Configuration
from f2ap.data import Database


PATH_DIRNAME = path.dirname(__file__)


def get_fake_db(db_path: str = None, delete_first: bool = False) -> Database:
    if db_path is None:
        db_path = f"/files/database.{uuid4().hex}.db"

    realpath = f"{PATH_DIRNAME}/{db_path}"
    if delete_first and path.exists(realpath):
        remove(realpath)

    return Database(get_fake_config(db_path))


def get_fake_config(db_path: str):
    return Configuration(
        url="example.com",
        db=f"{PATH_DIRNAME}/{db_path}",
        website={
            "url": "https://example.com/blog",
            "feed": "https://example.com/blog.feed",
        },
        actor={
            "username": "test",
            "display_name": "The Test Profile",
            "summary": "What did you expect?",
            "followings": ["@coolperson@example.org"],
            "attachments": {
                "Website": "https://example.com",
            },
            "public_key": f"{PATH_DIRNAME}/files/fake-rsa/public",
            "private_key": f"{PATH_DIRNAME}/files/fake-rsa/private",
        },
        message={"format": ""},
    )
