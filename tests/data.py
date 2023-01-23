import pytest

from os import path, remove, utime
from shutil import copyfile

from f2ap.data import Database, TABLES
from f2ap.config import Configuration

PATH_DIRNAME = path.dirname(__file__)


def get_fake_db(db_path: str) -> Database:
    return Database(
        Configuration(
            "",
            db_path,
            {"url": "", "feed": ""},
            {
                "username": "",
                "public_key": f"{PATH_DIRNAME}/files/fake-rsa/public",
                "private_key": f"{PATH_DIRNAME}/files/fake-rsa/private",
            },
            {"format": ""},
        )
    )


def test_init_database():
    db_path = f"{PATH_DIRNAME}/files/database.db"

    if path.exists(db_path):
        remove(db_path)

    db = get_fake_db(db_path)
    db.init_database()

    assert db.get_schema_info() == TABLES


def test_init_database_fails_if_file_exists():
    db_path = f"{PATH_DIRNAME}/files/database.db"

    # Ensure the file exists (equivalent to the UNIX `touch` command)
    with open(db_path, "a"):
        utime(db_path)

    with pytest.raises(IOError) as error:
        get_fake_db(db_path).init_database()
        assert (
            error.value
            == "Database already exists. If you want to reinitialize the data, delete it or rename it first."
        )


def test_upgrade_database():
    v1_path = f"{PATH_DIRNAME}/files/database/upgrade/database-v1.db"
    db_path = f"{PATH_DIRNAME}/files/database/upgrade/database.db"

    copyfile(v1_path, db_path)
    db = get_fake_db(db_path)

    assert db.upgrade_database()

    assert db.get_schema_info() == TABLES
