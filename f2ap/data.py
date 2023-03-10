import json
import logging
import sqlite3
import shutil

from datetime import datetime, timezone
from uuid import uuid4, UUID
from typing import Union, Optional
from os.path import exists

from . import model
from .config import Configuration
from .enum import Visibility

# Note: primary keys are defined as nullable because of a mistake made in the first version (I didn't even know this was possible).
# We need to alter tables later to fix that.
TABLES = {
    "metadata": {
        "key": {"type": "VARCHAR(50)", "primary": True, "nullable": True},
        "value": {"type": "TEXT", "primary": False, "nullable": True},
    },
    "messages": {
        "uuid": {"type": "VARCHAR(36)", "primary": True, "nullable": True},
        "msg_type": {"type": "VARCHAR(20)", "primary": False, "nullable": False},
        "note": {"type": "VARCHAR(36)", "primary": False, "nullable": False},
    },
    "notes": {
        "uuid": {"type": "VARCHAR(36)", "primary": True, "nullable": True},
        "published_time": {"type": "INTEGER", "primary": False, "nullable": False},
        "url": {"type": "VARCHAR(255)", "primary": False, "nullable": False},
        "name": {"type": "VARCHAR(500)", "primary": False, "nullable": True},
        "reply_to": {"type": "VARCHAR(255)", "primary": False, "nullable": True},
        "content": {"type": "TEXT", "primary": False, "nullable": False},
        "tags": {"type": "TEXT", "primary": False, "nullable": True},
    },
    "followers": {
        "uuid": {"type": "VARCHAR(36)", "primary": True, "nullable": True},
        "follower_since": {"type": "INTEGER", "primary": False, "nullable": False},
        "link": {"type": "VARCHAR(255)", "primary": False, "nullable": False},
    },
    "comments": {
        "uuid": {"type": "VARCHAR(36)", "primary": True, "nullable": True},
        "url": {"type": "VARCHAR(255)", "primary": False, "nullable": False},
        "attributed_to": {"type": "VARCHAR(255)", "primary": False, "nullable": True},
        "replying_to": {"type": "VARCHAR(36)", "primary": False, "nullable": False},
        "published_time": {"type": "INTEGER", "primary": False, "nullable": False},
        "content": {"type": "TEXT", "primary": False, "nullable": False},
        "visibility": {"type": "INTEGER", "primary": False, "nullable": False},
        "tags": {"type": "TEXT", "primary": False, "nullable": True},
    },
}

W3C_PUBLIC_STREAM = "https://www.w3.org/ns/activitystreams#Public"

DATABASE_VERSION = 2


class Database:
    def __init__(self, config: Configuration):
        self.file_path = config.db
        self.config = config

    def execute(self, sql: str, params: {str: str} = None):
        with sqlite3.connect(self.file_path) as connection:
            return connection.cursor().execute(
                sql, params if params is not None else {}
            )

    def get_metadata(self, key: str):
        result = self.execute(
            "SELECT value FROM metadata WHERE key = :key", {"key": key}
        ).fetchone()

        if result is None:
            return None

        (v,) = result

        return v

    def set_metadata(self, key: str, value):
        if self.get_metadata(key) is None:
            self.execute(
                "INSERT INTO metadata(key, value) VALUES(:key, :value)",
                {"key": key, "value": value},
            )
            return

        self.execute(
            "UPDATE metadata SET value = :value WHERE key = :key",
            {"key": key, "value": value},
        )

    def get_schema_info(self) -> dict:
        tables = {}

        for _, table_name, _type, _, _, _ in self.execute("PRAGMA main.table_list"):
            if _type != "table" or table_name == "sqlite_schema":
                continue

            tables[table_name] = {}

            for _, field_name, field_type, not_null, _, is_primary in self.execute(
                f"PRAGMA table_info('{table_name}')"
            ):
                tables[table_name][field_name] = {
                    "type": field_type,
                    "nullable": not not_null,
                    "primary": bool(is_primary),
                }

        return tables

    def get_database_version(self):
        return int(self.get_metadata("version"))

    def is_database_initialized(self) -> bool:
        return exists(self.file_path)

    def is_database_compatible(self):
        return self.get_database_version() <= DATABASE_VERSION

    def upgrade_database(self) -> bool:
        """Returns True if the database has been upgraded

        Note: except for versions < 1.0 and major releases, modifying this function is forbidden,
        as it means breaking backwards compatibility.
        """
        current_db_version = self.get_database_version()
        if current_db_version == DATABASE_VERSION:
            return False

        logging.info("Started upgrade database")

        backup = f"{self.config.db}.{int(datetime.utcnow().timestamp())}.bak"
        shutil.copyfile(self.config.db, backup)

        logging.info(f"Database backed up to {backup}")

        ##########################################
        # BEGIN incremental upgrade instructions #
        ##########################################

        if current_db_version == 1:
            logging.debug("Upgrading from v1 to v2...")
            self.init_database(update=True, only_tables=["comments"])
            self.execute(
                """
                ALTER TABLE notes
                ADD name VARCHAR(500)
            """
            )

            results = self.execute(
                """
                SELECT uuid, url
                FROM notes
            """
            ).fetchall()

            # We import them here to prevent importing useless libraries outside the upgrade path
            import requests
            from bs4 import BeautifulSoup

            for uuid, url in results:
                logging.debug(f"Updating note: {url}")
                try:
                    r = requests.get(url)
                    r.raise_for_status()
                    soup = BeautifulSoup(r.text, features="html.parser")

                    self.execute(
                        """
                        UPDATE notes
                        SET name = :name
                        WHERE uuid = :uuid
                    """,
                        {"name": soup.title.string, "uuid": uuid},
                    )
                except requests.HTTPError as e:
                    logging.warning(
                        f"Could not update note at {url}: {e}."
                        f" It might be unreachable on some social application."
                    )

            logging.debug("Upgraded to v2!")

            current_db_version += 1

        ########################################
        # END incremental upgrade instructions #
        ########################################

        if current_db_version != DATABASE_VERSION:
            shutil.copyfile(backup, self.config.db)

            raise ValueError(
                f"Database version mismatch after upgrade: expected {DATABASE_VERSION},"
                f" got {current_db_version}. The database has not been upgraded."
            )

        logging.info("Upgrade finished! You can remove the backup safely.")

        self.set_metadata("version", DATABASE_VERSION)

        return True

    def init_database(self, update: bool = False, only_tables: [str] = None):
        only_tables = [] if only_tables is None else only_tables

        if not update and exists(self.file_path):
            raise IOError(
                "Database already exists. If you really want to reinitialize the data, delete it or rename it first."
            )

        if update and len(only_tables) == 0:
            raise ValueError("Update mode requires a list of tables.")

        with sqlite3.connect(self.file_path) as connection:
            cursor = connection.cursor()
            for table in TABLES:
                if update and table not in only_tables:
                    continue

                sql = f"CREATE TABLE {table}("
                sep = ""

                for field in TABLES[table]:
                    field_info = TABLES[table][field]
                    sql += f"{sep}{field} {field_info.get('type', 'TEXT')}"

                    if field_info.get("primary", False):
                        sql += " PRIMARY KEY"
                    if not field_info.get("nullable", True):
                        sql += " NOT NULL"

                    sep = ", "

                sql += ")"

                logging.debug(sql)
                cursor.execute(sql)

        self.set_metadata("version", DATABASE_VERSION)

    def get_message(self, uuid: UUID) -> Optional[model.Message]:
        result = self.execute(
            """
            SELECT m.uuid as msg_uuid, m.msg_type, n.url
            FROM messages m
            JOIN notes n ON n.uuid = m.note
            WHERE msg_uuid = :uuid
        """,
            {"uuid": str(uuid)},
        ).fetchone()

        if result is None:
            return None

        msg_uuid, msg_type, url = result
        note = self.get_note(url)

        return model.Message(
            id=f"https://{self.config.url}/messages/{msg_uuid}",
            type=msg_type,
            actor=self.config.actor.id,
            published=note.published,
            object=note,
        )

    def get_note(self, url: str) -> Optional[model.Note]:
        query = self.execute(
            f"""
            SELECT uuid, published_time, name, url, reply_to, content, tags
            FROM notes
            WHERE url = :url
        """,
            {"url": url},
        ).fetchone()

        if query is None:
            return None

        uuid, published, name, url, reply_to, content, tags = query

        return model.Note(
            uuid=uuid,
            id=url,
            name=name,
            in_reply_to=reply_to,
            published=datetime.fromtimestamp(published, tz=timezone.utc),
            url=url,
            attributedTo=self.config.actor.id,
            content=model.Markdown(content),
            cc=self.config.message.groups + [self.config.actor.followers_link],
            tag=json.loads(tags),
        )

    def insert_note(
        self,
        content: str,
        published_on: datetime,
        url: str,
        name: str,
        reply_to: str = None,
        tags: [str] = None,
    ) -> (model.Note, UUID):
        if tags is None:
            tags = []

        uuid = uuid4()
        self.execute(
            """
            INSERT INTO notes(uuid, content, published_time, reply_to, url, name, tags)
            VALUES(:uuid, :content, :published_time, :reply_to, :url, :name, :tags)
        """,
            {
                "uuid": str(uuid),
                "content": content,
                "published_time": int(
                    published_on.astimezone(timezone.utc).timestamp()
                ),
                "reply_to": reply_to,
                "url": url,
                "name": name,
                "tags": json.dumps(tags),
            },
        )

        return self.get_note(url), uuid

    def insert_message(
        self, note_uuid: UUID, msg_type: str = "Create"
    ) -> model.Message:
        uuid = uuid4()
        self.execute(
            """
            INSERT INTO messages(uuid, msg_type, note)
            VALUES(:uuid, :msg_type, :note_uuid)
        """,
            {
                "uuid": str(uuid),
                "msg_type": msg_type,
                "note_uuid": str(note_uuid),
            },
        )

        return self.get_message(uuid)

    def get_messages(self, order: str = "DESC") -> [dict]:
        results = self.execute(
            f"""
            SELECT m.uuid as m_uuid, m.msg_type, n.url
            FROM messages m
            JOIN notes n ON m.note = n.uuid
            ORDER BY n.published_time {order}
        """
        ).fetchall()

        messages = []

        for (
            message_uuid,
            message_type,
            url,
        ) in results:
            note = self.get_note(url)
            messages.append(
                model.Message(
                    id=f"https://{self.config.url}/messages/{message_uuid}",
                    actor=self.config.actor.id,
                    published=note.published,
                    object=note,
                )
            )

        return messages

    def insert_comment(
        self,
        replying_to: model.Note,
        url: str,
        published_on: datetime,
        author_url: str,
        content: str,
        visibility: Visibility,
        tags: [model.Tag] = None,
    ) -> UUID:
        if tags is None:
            tags = []

        uuid = uuid4()

        self.execute(
            """
            INSERT INTO comments(uuid, url, published_time, attributed_to, replying_to, content, visibility, tags)
            VALUES(:uuid, :url, :published_time, :attributed_to, :replying_to, :content, :visibility, :tags)
        """,
            {
                "uuid": str(uuid),
                "url": url,
                "published_time": published_on.astimezone(timezone.utc).timestamp(),
                "attributed_to": author_url,
                "replying_to": replying_to.id,
                "content": content,
                "visibility": visibility.value,
                "tags": json.dumps(tags),
            },
        )

        return uuid

    def get_comments(self, note: model.Note, urls_only: bool = False):
        pass

    def delete_comment(self, url: str):
        self.execute("DELETE FROM comments WHERE url = :url", {"url": url})

    def get_last_note_datetime(self) -> Union[None, datetime]:
        (result,) = self.execute(
            "SELECT MAX(published_time) as dt FROM notes"
        ).fetchone()

        if result is None:
            return None

        return datetime.fromtimestamp(result, tz=timezone.utc)

    def insert_follower(self, account: str) -> UUID:
        uuid = uuid4()
        self.execute(
            """
            INSERT INTO followers(uuid, follower_since, link)
            VALUES(:uuid, :since, :account)
        """,
            {
                "uuid": str(uuid),
                "since": datetime.utcnow().timestamp(),
                "account": account,
            },
        )

        return uuid

    def delete_follower(self, account: str):
        self.execute(
            """
            DELETE FROM followers
            WHERE link = :account
        """,
            {
                "account": account,
            },
        )

    def count_followers(self) -> int:
        (result,) = self.execute("SELECT COUNT(uuid) FROM followers").fetchone()

        return result

    def get_followers(self) -> [str]:
        query = self.execute(
            """
            SELECT link
            FROM followers
            ORDER BY follower_since DESC
        """
        ).fetchall()

        followers = []
        for (link,) in query:
            followers.append(link)

        return followers
