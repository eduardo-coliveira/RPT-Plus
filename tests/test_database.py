import json
from datetime import datetime, timedelta

import pymysql
import pytest

from backend import database


def _raise_database_error():
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
def fake_db(monkeypatch):
    cursor = FakeCursor()
    connection = FakeConnection(cursor)
    monkeypatch.setattr(database, "get_db_connection", lambda: connection)
    return cursor, connection


def test_init_db_creates_tables_seeds_default_users_and_commits(monkeypatch, fake_db):
    cursor, connection = fake_db
    cursor.rows = iter([(0,)])
    users = [
        {"username": "learner-a", "password": "secret-a", "group_name": "group-a"},
        {"username": "learner-b", "password": "secret-b", "group_name": "group-b"},
    ]
    monkeypatch.setenv("DEFAULT_USERS", json.dumps(users))

    database.init_db()

    statements = [" ".join(query.split()) for query, _ in cursor.executed]
    assert "CREATE TABLE IF NOT EXISTS users" in statements[0]
    assert "CREATE TABLE IF NOT EXISTS action_log" in statements[1]
    assert "SELECT COUNT(*) FROM users" in statements[2]
    assert cursor.executed[3:] == [
        (
            "INSERT INTO users (username, password, group_name) VALUES (%s, %s, %s)",
            (user["username"], user["password"], user["group_name"]),
        )
        for user in users
    ]
    assert connection.committed


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"id": 7, "username": "learner", "group_name": "group-a"}, {"id": 7, "username": "learner", "group_name": "group-a"}),
        (None, None),
    ],
    ids=["matching-user", "unknown-user-or-password"],
)
def test_authenticate_user_returns_matching_row_or_none(fake_db, row, expected):
    cursor, _ = fake_db
    cursor.rows = iter([row])

    result = database.authenticate_user("learner", "password")

    assert result == expected
    assert cursor.executed == [
        (
            "SELECT id, username, group_name FROM users WHERE username = %s AND password = %s",
            ("learner", "password"),
        )
    ]


def test_authenticate_user_returns_none_when_database_fails(monkeypatch):
    monkeypatch.setattr(
        database,
        "get_db_connection",
        _raise_database_error,
    )

    assert database.authenticate_user("learner", "password") is None


def test_log_action_entry_inserts_for_known_user_and_commits(fake_db):
    cursor, connection = fake_db
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
    cursor, connection = fake_db
    cursor.rows = iter([None])

    result = database.log_action_entry(
        username="missing",
        exercise="0.isOvenReady",
        current_code="code",
        action="Diagnose",
    )

    assert result is False
    assert cursor.executed == [("SELECT id FROM users WHERE username = %s", ("missing",))]
    assert not connection.committed


def test_log_action_entry_returns_false_when_database_fails(monkeypatch):
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
    )

    assert result is False