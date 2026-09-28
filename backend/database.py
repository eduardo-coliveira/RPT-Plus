"""Database settings, connections, and persistence helpers."""

from dataclasses import dataclass, field
import os
import json
import pymysql
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, Optional

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy.engine import URL


@dataclass(frozen=True)
class DatabaseConfig:
    """Database settings loaded from the environment."""

    host: str
    user: str
    password: str = field(repr=False)
    database: str

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Build database settings from the environment."""

        values = {
            "DB_HOST": os.environ.get("DB_HOST"),
            "DB_USER": os.environ.get("DB_USER"),
            "DB_PASSWORD": os.environ.get("DB_PASSWORD"),
            "DB_NAME": os.environ.get("DB_NAME"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise ValueError("Missing database credentials in .env file")
        return cls(
            host=values["DB_HOST"],
            user=values["DB_USER"],
            password=values["DB_PASSWORD"],
            database=values["DB_NAME"],
        )

# --- Connection Management ---
def open_database_connection(config: DatabaseConfig):
    """Open a MySQL connection using the supplied settings."""

    try:
        return pymysql.connect(
            host=config.host,
            user=config.user,
            password=config.password,
            database=config.database,
            autocommit=False,
        )
    except pymysql.MySQLError as e:
        print(f"Database connection failed: {e}")
        raise

def apply_database_migrations(config: DatabaseConfig) -> None:
    """Apply pending migrations to the database."""

    alembic_config = AlembicConfig(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    database_url = URL.create(
        "mysql+pymysql",
        username=config.user,
        password=config.password,
        host=config.host,
        database=config.database,
    ).render_as_string(hide_password=False)
    alembic_config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    command.upgrade(alembic_config, "head")


def seed_users_if_empty(cursor, default_users_json: str) -> None:
    """Add the configured default users when the table is empty."""

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] != 0:
        return

    try:
        default_users = json.loads(default_users_json)
        if isinstance(default_users, list):
            for user in default_users:
                cursor.execute(
                    "INSERT INTO users (username, password, group_name) VALUES (%s, %s, %s)",
                    (user["username"], user["password"], user["group_name"]),
                )
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        print(f"Skipping default users (invalid DEFAULT_USERS): {error}")


def initialize_database(config: DatabaseConfig, default_users_json: Optional[str] = None) -> None:
    """Migrate the database and add its default users."""

    if default_users_json is None:
        default_users_json = os.environ.get("DEFAULT_USERS", "[]")

    apply_database_migrations(config)
    try:
        with open_database_connection(config) as conn:
            with conn.cursor() as cursor:
                seed_users_if_empty(cursor, default_users_json)
                conn.commit()
    except pymysql.MySQLError as error:
        print(f"Failed to initialize database: {error}")
        raise


def authenticate_user_credentials(
    username: str,
    password: str,
    config: DatabaseConfig,
) -> Optional[Dict[str, Any]]:
    """Check credentials and return the matching user record."""
    try:
        with open_database_connection(config) as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, username, group_name FROM users WHERE username = %s AND password = %s",
                    (username, password),
                )
                return cursor.fetchone()  # Returns dict with id, username, group_name
    except pymysql.MySQLError as e:
        print(f"Authentication error: {e}")
        return None

def record_action_log(
    username: str,
    exercise: str,
    current_code: str,
    action: str,
    previous_code: Optional[str] = None,
    code_status: Optional[str] = None,
    feedback: Optional[str] = None,
    hint_tree: Optional[str] = None,
    *,
    config: DatabaseConfig,
) -> bool:
    """Save one user action and report whether the write succeeded."""

    try:
        with open_database_connection(config) as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                if not user:
                    print(f"User {username} not found for logging")
                    return False

                user_id = user["id"]

                cursor.execute(
                    """
                    INSERT INTO action_log
                    (timestamp, user_id, exercise, current_code, action, previous_code, code_status, feedback, hint_tree)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        datetime.now(ZoneInfo('Europe/Amsterdam')).isoformat(),
                        user_id,
                        exercise,
                        current_code,
                        action,
                        previous_code,
                        code_status,
                        feedback,
                        hint_tree,
                    ),
                )
                conn.commit()
                return True
    except pymysql.MySQLError as e:
        print(f"Failed to log action: {e}")
        return False


# Compatibility aliases for scripts that are intentionally left unchanged.
get_db_connection = open_database_connection
run_migrations = apply_database_migrations
seed_default_users = seed_users_if_empty
init_db = initialize_database
authenticate_user = authenticate_user_credentials
log_action_entry = record_action_log
