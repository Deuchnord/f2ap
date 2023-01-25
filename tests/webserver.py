from fastapi.testclient import TestClient

from f2ap import webserver

from . import get_fake_config, get_fake_db

DATABASE_FILE = "files/webserver.db"

get_fake_db(DATABASE_FILE, delete_first=True).init_database()
client = TestClient(webserver.get_server(get_fake_config(DATABASE_FILE)))


def test_webfinger():
    response = client.get("/.well-known/webfinger?resource=acct:test@example.com")

    assert response.status_code == 200
    assert response.headers.get("Content-Type") == "application/jrd+json"
    assert response.json() == {
        "subject": "acct:test@example.com",
        "links": [
            {
                "rel": "self",
                "type": "application/activity+json",
                "href": "https://example.com/actors/test",
            }
        ],
    }
