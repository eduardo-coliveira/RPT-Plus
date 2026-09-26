import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pymysql
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect

from backend import database


def _raise_database_error(config):
    raise pymysql.MySQLError("database unavailable")


class FakeCursor:
    def __init__(self, rows=()):
        self.rows = iter(rows)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params=None):
        self.executed.append((query, params))

    def fetchone(self):
        return next(self.rows, None)


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def cursor(self, *args, **kwargs):
        return self.fake_cursor

    def commit(self):
        self.committed = True


@pytest.fixture
def db_config():
    return database.DatabaseConfig(
        host="test-host",
        user="test-user",
        password="test-password",
        database="test-database",
    )


@pytest.fixture
def fake_db(monkeypatch, db_config):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr(database, "get_db_connection", lambda config: connection)
    return cursor, connection, db_config


def test_database_config_reads_environment_and_hides_password(monkeypatch):
    monkeypatch.setenv("DB_HOST", "db-host")
    monkeypatch.setenv("DB_USER", "db-user")
    monkeypatch.setenv("DB_PASSWORD", "db-password")
    monkeypatch.setenv("DB_NAME", "db-name")

    config = database.DatabaseConfig.from_env()

    assert config.host == "db-host"
    assert config.user == "db-user"
    assert config.password == "db-password"
    assert config.database == "db-name"
    assert "db-password" not in repr(config)


def test_database_config_rejects_missing_environment(monkeypatch):
    for variable in ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"):
        monkeypatch.delenv(variable, raising=False)

    with pytest.raises(ValueError, match="Missing database credentials"):
        database.DatabaseConfig.from_env()


def test_init_db_runs_migrations_then_seeds_default_users(monkeypatch, fake_db):
    cursor, connection, config = fake_db
    cursor.rows = iter([(0,)])
    migration = Mock()
    monkeypatch.setattr(database, "run_migrations", migration)
    users = [
        {"username": "learner-a", "password": "secret-a", "group_name": "group-a"},
        {"username": "learner-b", "password": "secret-b", "group_name": "group-b"},
    ]
    database.init_db(config, json.dumps(users))

    migration.assert_called_once_with(config)
    assert cursor.executed[0] == ("SELECT COUNT(*) FROM users", None)
    assert cursor.executed[1:] == [
        (
            "INSERT INTO users (username, password, group_name) VALUES (%s, %s, %s)",
            (user["username"], user["password"], user["group_name"]),
        )
        for user in users
    ]
    assert connection.committed


def test_initial_migration_creates_schema_and_tracks_revision(tmp_path):
    migration_config = AlembicConfig()
    migration_config.set_main_option(
        "script_location",
        str(Path(__file__).resolve().parents[1] / "backend" / "migrations"),
    )
    migration_config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path / 'migration.db'}")

    command.upgrade(migration_config, "head")

    engine = create_engine(migration_config.get_main_option("sqlalchemy.url"))
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())
    engine.dispose()

    assert {"users", "action_log", "alembic_version"} <= tables

    command.upgrade(migration_config, "head")


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"id": 7, "username": "learner", "group_name": "group-a"}, {"id": 7, "username": "learner", "group_name": "group-a"}),
        (None, None),
    ],
    ids=["matching-user", "unknown-user-or-password"],
)
def test_authenticate_user_returns_matching_row_or_none(fake_db, row, expected):
    cursor, _, config = fake_db
    cursor.rows = iter([row])

    result = database.authenticate_user("learner", "password", config)

    assert result == expected
    assert cursor.executed == [
        (
            "SELECT id, username, group_name FROM users WHERE username = %s AND password = %s",
            ("learner", "password"),
        )
    ]


def test_authenticate_user_returns_none_when_database_fails(monkeypatch, db_config):
    monkeypatch.setattr(
        database,
        "get_db_connection",
        _raise_database_error,
    )

    assert database.authenticate_user("learner", "password", db_config) is None


def test_log_action_entry_inserts_for_known_user_and_commits(fake_db):
    cursor, connection, config = fake_db
    cursor.rows = iter([{"id": 17}])

    result = database.log_action_entry(
        username="learner",
        exercise="0.isOvenReady",
        current_code="return true;",
        action="Diagnose",
        previous_code="return false;",
        code_status="correct",
        feedback="Looks good",
        hint_tree='{"Tree": []}',
        config=config,
    )

    assert result is True
    assert cursor.executed[0] == ("SELECT id FROM users WHERE username = %s", ("learner",))
    insert_query, insert_values = cursor.executed[1]
    assert "INSERT INTO action_log" in insert_query
    assert insert_values[1:] == (
        17,
        "0.isOvenReady",
        "return true;",
        "Diagnose",
        "return false;",
        "correct",
        "Looks good",
        '{"Tree": []}',
    )
    timestamp = datetime.fromisoformat(insert_values[0])
    assert timestamp.tzinfo is not None
    assert timestamp.utcoffset() in {timedelta(hours=1), timedelta(hours=2)}
    assert connection.committed


def test_log_action_entry_skips_insert_for_unknown_user(fake_db):
    cursor, connection, config = fake_db
    cursor.rows = iter([None])

    result = database.log_action_entry(
        username="missing",
        exercise="0.isOvenReady",
        current_code="code",
        action="Diagnose",
        config=config,
    )

    assert result is False
    assert cursor.executed == [("SELECT id FROM users WHERE username = %s", ("missing",))]
    assert not connection.committed


def test_log_action_entry_returns_false_when_database_fails(monkeypatch, db_config):
    monkeypatch.setattr(
        database,
        "get_db_connection",
        _raise_database_error,
    )

    result = database.log_action_entry(
        username="learner",
        exercise="0.isOvenReady",
        current_code="code",
        action="Diagnose",
        config=db_config,
    )

    assert result is False