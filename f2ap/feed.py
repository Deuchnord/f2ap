import feedparser
import logging

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from threading import Thread
from time import sleep

from . import activitypub
from .data import Database
from .config import Configuration
from .markdown import find_hashtags


class UpdateFeedThread(Thread):
    def __init__(self, config: Configuration, db: Database):
        super().__init__()
        self.config = config
        self.db = db
        self.stop = False

    def run(self) -> None:
        self.stop = False
        while not self.stop:
            activitypub.propagate_messages(
                self.config, self.get_inboxes(), self.update()
            )
            i = 0

            # we make smaller sleeps to prevent the thread being stuck when the app is stopped.
            while not self.stop and i < self.config.website.update_freq * 60:
                sleep(0.1)
                i += 0.1

    def get_inboxes(self):
        for follower in self.db.get_followers():
            actor = activitypub.get_actor(follower)

            if actor is None:
                logging.warning(
                    f"Could not get inbox for user {actor}, they won't receive the message."
                )
                continue

            yield actor["inbox"]

        for group in self.config.message.groups:
            yield group

    def update(self):
        logging.info("Update started")

        last_dt = self.db.get_last_note_datetime()
        if last_dt is not None:
            logging.debug(f"Last known article on {last_dt.isoformat()}.")
        else:
            logging.debug("No article known, fetching all the articles.")

        feed = feedparser.parse(self.config.website.feed, sanitize_html=True)

        messages = []

        for item in feed.entries:
            if "published" in item:
                published = item.published
            else:
                published = item.updated

            if feed.version.startswith("atom"):
                published = datetime.fromisoformat(published)
            elif feed.version.startswith("rss"):
                published = parsedate_to_datetime(published)

            if published.tzinfo is None:
                # If naive, consider UTC
                published = published.replace(tzinfo=timezone.utc)

            if last_dt is not None and published <= last_dt:
                continue

            logging.debug(
                f'New article: "{item.title}", published on {published.isoformat()} ({item.link})'
            )

            if "tags" in item:
                hashtags, tags = self.make_tags(tag["label"] for tag in item.tags)
            else:
                hashtags, tags = "", []

            message = self.parse_hashtags(
                self.config.message.format.format(
                    title=item.title if "title" in item else "",
                    url=item.link if "link" in item else "",
                    published=published,
                    summary=item.summary if "summary" in item else "",
                    author=item.author if "author" in item else "",
                    tags=hashtags,
                )
            )

            note, note_uuid = self.db.insert_note(
                message, published, item.link, tags=tags
            )
            logging.debug("Note saved: %s" % note_uuid)
            message = self.db.insert_message(note_uuid)
            logging.debug("Message saved: %s" % message.id)

            messages.append(message)

        logging.info("Update finished")

        return messages

    def make_tags(self, tags: [str]) -> (str, [str]):
        formatter = self.config.message.get_tags_formatter()

        hashtags_in_msg = []
        tags_list = []
        for tag in tags:
            formatted_tag = formatter(tag)
            hashtags_in_msg.append(f"#{formatted_tag}")
            tags_list.append(formatted_tag)

        return " ".join(hashtags_in_msg), tags_list

    def parse_hashtags(self, msg: str) -> str:
        new_msg = msg
        for hashtag in find_hashtags(msg):
            new_msg = new_msg.replace(
                f"#{hashtag}", f"[#{hashtag}](https://{self.config.url}/tags/{hashtag})"
            )

        return new_msg
