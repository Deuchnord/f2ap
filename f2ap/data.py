import json
import sqlite3
import markdown

from datetime import datetime, timezone
from uuid import uuid4, UUID
from typing import Union, Optional
from os.path import exists

from . import model
from .config import Configuration

W3C_PUBLIC_STREAM = "https://www.w3.org/ns/activitystreams#Public"

DATABASE_VERSION = 1


class Database:
    def __init__(self, config: Configuration):
        self.file_path = config.db
        self.config = config

    def execute(self, sql: str, params: {str: str} = None):
        with sqlite3.connect(self.file_path) as connection:
            return connection.cursor().execute(
                sql,
                params if params is not None else {}
            )

    def get_metadata(self, key: str):
        result = self.execute("SELECT value FROM metadata WHERE key = :key", {"key": key}).fetchone()

        if result is None:
            return None

        v, = result

        return v

    def set_metadata(self, key: str, value):
        if self.get_metadata(key) is None:
            self.execute("INSERT INTO metadata(key, value) VALUES(:key, :value)", {"key": key, "value": value})
            return

        self.execute("UPDATE metadata SET value = :value WHERE key = :key", {"key": key, "value": value})

    def get_database_version(self):
        return int(self.get_metadata("version"))

    def is_database_initialized(self) -> bool:
        return exists(self.file_path)

    def is_database_compatible(self):
        return self.get_database_version() <= DATABASE_VERSION

    def upgrade_database(self) -> bool:
        """Returns True if the database has been upgraded"""
        if self.get_database_version() == DATABASE_VERSION:
            return False

        # Add upgrade instructions here

        self.set_metadata("version", DATABASE_VERSION)

        return True

    def init_database(self):
        if exists(self.file_path):
            raise IOError(f"Database already exists. If you really want to reinitialize the data, delete it or rename it first.")

        tables = {
            "metadata": {
                "key": "VARCHAR(50) PRIMARY KEY",
                "value": "TEXT",
            },
            "messages": {
                "uuid": "VARCHAR(36) PRIMARY KEY",
                "msg_type": "VARCHAR(20) NOT NULL",
                "note": "VARCHAR(36) NOT NULL",
            },
            "notes": {
                "uuid": "VARCHAR(36) PRIMARY KEY",
                "published_time": "INTEGER NOT NULL",
                "url": "VARCHAR(255) NOT NULL",
                "reply_to": "VARCHAR(255)",
                "content": "TEXT NOT NULL",
                "tags": "TEXT",
            },
            "followers": {
                "uuid": "VARCHAR(36) PRIMARY KEY",
                "follower_since": "INTEGER NOT NULL",
                "link": "VARCHAR(255) NOT NULL",
            }
        }

        with sqlite3.connect(self.file_path) as connection:
            cursor = connection.cursor()
            for table in tables:
                sql = f"CREATE TABLE {table}("
                sep = ""

                for field in tables[table]:
                    sql += f"{sep}{field} {tables[table][field]}"
                    sep = ", "

                sql += ")"
                cursor.execute(sql)

        self.set_metadata("version", DATABASE_VERSION)

    def get_message(self, uuid: UUID) -> Optional[model.Message]:
        result = self.execute("""
            SELECT m.uuid as msg_uuid, m.msg_type,
                n.uuid as note_uuid, n.published_time, n.url, n.reply_to, n.content
            FROM messages m
            JOIN notes n ON n.uuid = m.note
            WHERE msg_uuid = :uuid
        """, {'uuid': str(uuid)}).fetchone()

        if result is None:
            return None

        msg_uuid, msg_type, note_uuid, published, url, reply_to, content = result
        published_at = datetime.fromtimestamp(published)

        return model.Message(
            id=f"https://{self.config.url}/messages/{msg_uuid}",
            type=msg_type,
            actor=self.config.actor.id,
            published=published_at,
            object=model.Note(
                id=f"https://{self.config.url}/notes/{note_uuid}",
                published=published_at,
                url=url,
                attributedTo=self.config.actor.id,
                inReplyTo=reply_to,
                content=content,
            )
        )

    def get_note(self, url: str) -> Optional[model.Note]:
        query = self.execute(f"""
            SELECT uuid, published_time, url, reply_to, content, tags
            FROM notes
            WHERE url = :url
        """, {"url": url}).fetchone()

        if query is None:
            return None

        uuid, published, url, reply_to, content, tags = query

        return model.Note(
            id=url,
            in_reply_to=reply_to,
            published=datetime.fromtimestamp(published, tz=timezone.utc),
            url=url,
            attributedTo=self.config.actor.id,
            content=model.Markdown(content),
            cc=[self.config.actor.followers_link],
            tag=json.loads(tags)
        )

    def insert_note(self, content: str, published_on: datetime, url: str, reply_to: str = None, tags: [str] = None) -> (model.Note, UUID):
        if tags is None:
            tags = []

        uuid = uuid4()
        self.execute("""
            INSERT INTO notes(uuid, content, published_time, reply_to, url, tags)
            VALUES(:uuid, :content, :published_time, :reply_to, :url, :tags)
        """, {
            "uuid": str(uuid),
            "content": content,
            "published_time": int(published_on.astimezone(timezone.utc).timestamp()),
            "reply_to": reply_to,
            "url": url,
            "tags": json.dumps(tags)
        })

        return self.get_note(url), uuid

    def insert_message(self, note_uuid: UUID, msg_type: str = "Create") -> model.Message:
        uuid = uuid4()
        self.execute("""
            INSERT INTO messages(uuid, msg_type, note)
            VALUES(:uuid, :msg_type, :note_uuid)
        """, {
            "uuid": str(uuid),
            "msg_type": msg_type,
            "note_uuid": str(note_uuid),
        })

        return self.get_message(uuid)

    def get_messages(self, order: str = "DESC") -> [dict]:
        results = self.execute(f"""
            SELECT m.uuid as m_uuid, m.msg_type,
                   n.uuid as n_uuid, n.content, n.published_time, n.reply_to, n.url
            FROM messages m
            JOIN notes n ON m.note = n.uuid
            ORDER BY n.published_time {order}
        """).fetchall()

        messages = []

        for message_uuid, message_type, note_uuid, note_content, note_published_time, reply_to, url in results:
            published = datetime.fromtimestamp(note_published_time, tz=timezone.utc)
            messages.append(model.Message(
                id=f"https://{self.config.url}/messages/{message_uuid}",
                actor=self.config.actor.id,
                published=published,
                object=model.Note(
                    id=f"https://{self.config.url}/notes/{note_uuid}",
                    inReplyTo=reply_to,
                    published=published.isoformat(),
                    url=url,
                    cc=[self.config.actor.followers_link],
                    attributedTo=self.config.actor.id,
                    content=markdown.markdown(note_content, extensions=["markdown.extensions.nl2br", "mdx_linkify"]),
                )
            ))

        return messages

    def get_last_note_datetime(self) -> Union[None, datetime]:
        result, = self.execute("SELECT MAX(published_time) as dt FROM notes").fetchone()

        if result is None:
            return None

        return datetime.fromtimestamp(result, tz=timezone.utc)

    def insert_follower(self, account: str) -> UUID:
        uuid = uuid4()
        self.execute("""
            INSERT INTO followers(uuid, follower_since, link)
            VALUES(:uuid, :since, :account)
        """, {
            "uuid": str(uuid),
            "since": datetime.utcnow().timestamp(),
            "account": account,
        })

        return uuid

    def delete_follower(self, account: str):
        self.execute("""
            DELETE FROM followers
            WHERE link = :account
        """, {
            "account": account,
        })

    def count_followers(self) -> int:
        result, = self.execute("SELECT COUNT(uuid) FROM followers").fetchone()

        return result

    def get_followers(self) -> [str]:
        query = self.execute("""
            SELECT link
            FROM followers
            ORDER BY follower_since DESC
        """).fetchall()

        followers = []
        for link, in query:
            followers.append(link)

        return followers
