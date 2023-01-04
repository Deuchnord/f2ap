#!/usr/bin/env python3

import logging

from argparse import ArgumentParser

from .feed import UpdateFeedThread

from .config import get_config
from .data import Database
from .webserver import start_server


def main() -> int:
    args = get_args()
    configure_logging(args.log_level)
    config = get_config(args.config_file)
    db = Database(config)

    if not db.is_database_initialized():
        db.init_database()
        logging.info("Database created")
    elif not db.is_database_compatible():
        logging.critical("Database is created for a greater version of f2ap.")
        logging.critical("Please upgrade f2ap before continuing.")
        return 1
    elif db.upgrade_database():
        logging.info("Database has been upgraded")

    update_feed_thread = UpdateFeedThread(config, db)
    update_feed_thread.start()

    logging.info(f"Profile discoverable at @{config.actor.preferred_username}@{config.url}")

    start_server(
        config,
        args.webserver_port,
        args.log_level,
        args.skip_following
    )

    update_feed_thread.stop = True

    return 0


def configure_logging(log_level: str):
    logging.basicConfig(
        format="%(levelname)s:     [%(module)s] %(message)s",
        level=log_level
    )


def get_args():
    args = ArgumentParser()
    args.add_argument("--config", dest="config_file", type=str, help="Path to a configuration file", required=True)
    args.add_argument('--log-level', dest='log_level', type=str, choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], default="INFO")
    args.add_argument('--port', dest='webserver_port', type=int, default=8000)
    args.add_argument('--skip-following', dest='skip_following', action="store_true", help="Prevent following the accounts defined in the configuration file. Useful for development tests.")

    return args.parse_args()


if __name__ == '__main__':
    exit(main())
