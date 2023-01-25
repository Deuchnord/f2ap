import pytest

from os import utime
from shutil import copyfile

from f2ap.data import TABLES

from . import PATH_DIRNAME, get_fake_db


def test_init_database():
    db_path = "/files/database.db"

    db = get_fake_db(db_path, True)
    db.init_database()

    assert db.get_schema_info() == TABLES


def test_init_database_fails_if_file_exists():
    db_path = "/files/database.db"

    # Ensure the file exists (equivalent to the UNIX `touch` command)
    with open(f"{PATH_DIRNAME}{db_path}", "a"):
        utime(f"{PATH_DIRNAME}{db_path}")

    db = get_fake_db(db_path)

    assert db.is_database_initialized()

    with pytest.raises(IOError) as error:
        db.init_database()
        assert (
            error.value
            == "Database already exists. If you want to reinitialize the data, delete it or rename it first."
        )


def test_upgrade_database():
    v1_path = "/files/database/upgrade/database-v1.db"
    db_path = "/files/database/upgrade/database.db"

    copyfile(f"{PATH_DIRNAME}/{v1_path}", f"{PATH_DIRNAME}{db_path}")
    db = get_fake_db(db_path)

    assert db.upgrade_database()
    assert db.get_schema_info() == TABLES
