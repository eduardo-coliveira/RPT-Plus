from dotenv import load_dotenv
load_dotenv()

import os
import json
import pymysql
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any

# --- Configuration ---
DB_HOST = os.environ.get("DB_HOST")
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_NAME = os.environ.get("DB_NAME")

if not all([DB_HOST, DB_USER, DB_PASSWORD, DB_NAME]):
    raise ValueError("Missing database credentials in .env file")

# --- Connection Management ---
def get_db_connection():
    try:
        return pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=False,
            # cursorclass=pymysql.cursors.DictCursor,  # Return rows as dictionaries
        )
    except pymysql.MySQLError as e:
        print(f"Database connection failed: {e}")
        raise

# --- Schema Initialization ---
def init_db():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(255) NOT NULL UNIQUE,
                        password VARCHAR(255) NOT NULL,
                        group_name VARCHAR(255) NOT NULL
                    )
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS action_log (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        user_id INT NOT NULL,
                        exercise VARCHAR(255) NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        previous_code TEXT,
                        current_code TEXT,                       
                        code_status VARCHAR(255),
                        feedback TEXT,
                        hint_tree TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("SELECT COUNT(*) FROM users")
                if cursor.fetchone()[0] == 0:
                    # Insert default users from .env
                    default_users_json = os.environ.get("DEFAULT_USERS", "[]")
                    try:
                        default_users = json.loads(default_users_json)
                        if isinstance(default_users, list):
                            for user in default_users:
                                cursor.execute(
                                    "INSERT INTO users (username, password, group_name) VALUES (%s, %s, %s)",
                                    (user["username"], user["password"], user["group_name"]),
                                )
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        print(f"Skipping default users (invalid DEFAULT_USERS): {e}")

                conn.commit()
    except pymysql.MySQLError as e:
        print(f"Failed to initialize database: {e}")
        raise

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user. Returns user dict or None."""
    try:
        with get_db_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    "SELECT id, username, group_name FROM users WHERE username = %s AND password = %s",
                    (username, password),
                )
                return cursor.fetchone()  # Returns dict with id, username, group_name
    except pymysql.MySQLError as e:
        print(f"Authentication error: {e}")
        return None

def log_action_entry(
    username: str,
    exercise: str,
    current_code: str,
    action: str,
    previous_code: Optional[str] = None,
    code_status: Optional[str] = None,
    feedback: Optional[str] = None,
    hint_tree: Optional[str] = None,
) -> bool:
    try:
        with get_db_connection() as conn:
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