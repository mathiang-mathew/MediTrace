"""
database.py
------------
Core database module for MediTrace.

Creates the SQLite database and all four tables (patients, care_details,
infections, chw_visits), and gives the rest of the team three small
helper functions to build every other feature on top of:

    get_connection()          -> open a connection (foreign keys ON, dict-like rows)
    run_query(query, params)  -> for SELECT statements, returns a list of rows
    run_insert(query, params) -> for INSERT/UPDATE/DELETE, returns lastrowid / rowcount

Run this file directly to (re)create an empty database with the schema:
    python3 database.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "meditrace.db"


def get_connection():
    """Open a connection to the MediTrace database.

    Rows behave like dicts (row["ward"] as well as row[0]), and foreign
    key enforcement is turned on, since SQLite leaves it off by default.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def run_query(query, params=()):
    """Run a SELECT statement and return all matching rows.

    Example:
        rows = run_query("SELECT * FROM patients WHERE gender = ?", ("F",))
        for row in rows:
            print(row["name"], row["age"])
    """
    conn = get_connection()
    try:
        cursor = conn.execute(query, params)
        return cursor.fetchall()
    finally:
        conn.close()


def run_insert(query, params=()):
    """Run an INSERT, UPDATE, or DELETE statement.

    Commits automatically. Returns the new row's id for INSERTs, or the
    number of rows affected for UPDATE/DELETE.

    Example:
        new_id = run_insert(
            "INSERT INTO patients (name, age, gender) VALUES (?, ?, ?)",
            ("David Boyo", 34, "M"),
        )
    """
    conn = get_connection()
    try:
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
    finally:
        conn.close()


def split_list(field_value):
    """Split a comma-separated care_details/infections field into a list.

    equipment, medications, and procedures are stored as "Item A, Item B"
    text, since a patient can have several of each. Use this whenever you
    need to count or group by one individual item rather than the whole
    comma-separated string (e.g. in HAI pattern analysis).

    Example:
        split_list("Ventilator 2, IV stand 5") -> ["Ventilator 2", "IV stand 5"]
        split_list(None) -> []
    """
    if not field_value:
        return []
    return [item.strip() for item in field_value.split(",") if item.strip()]


SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    age          INTEGER NOT NULL CHECK (age > 0),
    gender       TEXT NOT NULL CHECK (gender IN ('M', 'F')),
    illness      TEXT,
    contact      TEXT,
    num_visits   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS care_details (
    care_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id    INTEGER NOT NULL UNIQUE,
    ward          TEXT NOT NULL,
    doctor        TEXT NOT NULL,
    nurse         TEXT,
    equipment     TEXT,
    medications   TEXT,
    procedures    TEXT,
    last_updated  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
);

CREATE TABLE IF NOT EXISTS infections (
    infection_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id      INTEGER NOT NULL,
    infection_type  TEXT NOT NULL,
    date_of_onset   TEXT NOT NULL,
    ward            TEXT NOT NULL,
    doctor          TEXT NOT NULL,
    nurse           TEXT,
    equipment       TEXT,
    medications     TEXT,
    procedures      TEXT,
    logged_at       TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
);

CREATE TABLE IF NOT EXISTS chw_visits (
    visit_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id           INTEGER NOT NULL,
    visit_date           TEXT NOT NULL,
    reason               TEXT NOT NULL,
    notes                TEXT,
    next_followup_date   TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
);
"""


def create_tables():
    """Create all four MediTrace tables if they don't already exist."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    create_tables()
    print(f"MediTrace database ready at {DB_PATH}")
