import sqlite3
from pathlib import Path

from models.profile import UserProfile

_DB_PATH = Path(__file__).parent / "profiles.db"


def init_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            did       TEXT PRIMARY KEY,
            profile   TEXT NOT NULL,
            built_at  TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def get_profile(conn: sqlite3.Connection, did: str) -> UserProfile | None:
    row = conn.execute(
        "SELECT profile FROM profiles WHERE did = ?", (did,)
    ).fetchone()
    if row is None:
        return None
    return UserProfile.model_validate_json(row[0])


def save_profile(conn: sqlite3.Connection, profile: UserProfile) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO profiles (did, profile, built_at) VALUES (?, ?, ?)",
        (profile.did, profile.model_dump_json(), profile.built_at.isoformat()),
    )
    conn.commit()
