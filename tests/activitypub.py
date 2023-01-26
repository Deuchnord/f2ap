from uuid import uuid4
from pytest_mock import MockerFixture

from . import get_fake_db

from f2ap import activitypub
from f2ap.enum import Visibility
from f2ap.model import W3C_ACTIVITYSTREAMS_PUBLIC, Note


def test_get_note_visibility_public_note():
    activitypub.get_actor = lambda s: {"followers": f"{s}/followers"}

    assert Visibility.PUBLIC == activitypub.get_note_visibility(
        {
            "attributedTo": "https://example.com/users/actor",
            "to": ["https://example.org/users/test"],
            "cc": [W3C_ACTIVITYSTREAMS_PUBLIC],
        }
    )

    assert Visibility.PUBLIC == activitypub.get_note_visibility(
        {
            "attributedTo": "https://example.com/users/actor",
            "to": ["https://example.org/users/test", W3C_ACTIVITYSTREAMS_PUBLIC],
            "cc": [],
        }
    )


def test_get_note_visibility_followers_only_note():
    activitypub.get_actor = lambda s: {"followers": f"{s}/followers"}

    assert Visibility.FOLLOWERS_ONLY == activitypub.get_note_visibility(
        {
            "attributedTo": "https://example.com/users/actor",
            "to": ["https://example.org/users/test"],
            "cc": ["https://example.com/users/actor/followers"],
        }
    )

    assert Visibility.FOLLOWERS_ONLY == activitypub.get_note_visibility(
        {
            "attributedTo": "https://example.com/users/actor",
            "to": [
                "https://example.org/users/test",
                "https://example.com/users/actor/followers",
            ],
            "cc": [],
        }
    )


def test_get_note_visibility_mentioned_only_note():
    activitypub.get_actor = lambda s: {"followers": f"{s}/followers"}

    assert Visibility.MENTIONED_ONLY == Visibility.DIRECT_MESSAGE

    assert Visibility.MENTIONED_ONLY == activitypub.get_note_visibility(
        {
            "attributedTo": "https://example.com/users/actor",
            "to": ["https://example.org/users/test"],
            "cc": ["https://example.net/users/anotherUser"],
        }
    )


def test_inbox_can_handle_comments(mocker: MockerFixture):
    db = get_fake_db()
    comment_uuid = uuid4()
    mocker.patch.object(db, "insert_comment", return_value=comment_uuid)

    activitypub.handle_inbox()

    replying_to = Note(
        uuid=comment_uuid,
        id=42,
        name=
    )
    url = n
    published_on = n
    author_url = n
    content = n
    visibility = n
    tags = []

    db.insert_comment.assert_called_with(replying_to, url, published_on, author_url, content, visibility, tags)
