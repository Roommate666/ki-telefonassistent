"""
Datenbank für Anrufprotokollierung.
Speichert alle Anrufe, Gesprächsverläufe und extrahierte Informationen.
"""

import os
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("KI_DB_PATH", "/opt/ki-telefonassistent/logs/calls.db"))


def _connect():
    """Erstellt eine DB-Verbindung mit WAL-Modus fuer Concurrency."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_database():
    """Erstellt die Datenbank und Tabellen."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = _connect()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT UNIQUE NOT NULL,
            caller_number TEXT,
            start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            end_time DATETIME,
            duration_seconds INTEGER,
            business_type TEXT,
            status TEXT DEFAULT 'active',
            recording_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (call_id) REFERENCES calls(call_id)
        );

        CREATE TABLE IF NOT EXISTS caller_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT NOT NULL,
            caller_name TEXT,
            caller_phone TEXT,
            concern TEXT,
            appointment_requested BOOLEAN DEFAULT 0,
            preferred_time TEXT,
            urgency TEXT DEFAULT 'mittel',
            callback_requested BOOLEAN DEFAULT 0,
            notes TEXT,
            extracted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (call_id) REFERENCES calls(call_id)
        );

        CREATE TABLE IF NOT EXISTS daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE UNIQUE NOT NULL,
            total_calls INTEGER DEFAULT 0,
            avg_duration_seconds REAL DEFAULT 0,
            callbacks_requested INTEGER DEFAULT 0,
            appointments_requested INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_number);
        CREATE INDEX IF NOT EXISTS idx_calls_start ON calls(start_time);
        CREATE INDEX IF NOT EXISTS idx_messages_call ON messages(call_id);
    """)

    conn.commit()
    conn.close()
    logger.info(f"Datenbank initialisiert: {DB_PATH}")


def start_call(call_id, caller_number, business_type="handwerk"):
    """Registriert einen neuen Anruf."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO calls (call_id, caller_number, business_type) VALUES (?, ?, ?)",
        (call_id, caller_number, business_type),
    )
    conn.commit()
    conn.close()
    logger.info(f"Anruf gestartet: {call_id} von {caller_number}")


def end_call(call_id, recording_path=None):
    """Beendet einen Anruf."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """UPDATE calls
           SET end_time = CURRENT_TIMESTAMP,
               duration_seconds = CAST(
                   (julianday(CURRENT_TIMESTAMP) - julianday(start_time)) * 86400
                   AS INTEGER
               ),
               status = 'completed',
               recording_path = ?
           WHERE call_id = ?""",
        (recording_path, call_id),
    )
    conn.commit()
    conn.close()
    logger.info(f"Anruf beendet: {call_id}")


def save_message(call_id, role, content):
    """Speichert eine Nachricht im Gesprächsverlauf."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (call_id, role, content) VALUES (?, ?, ?)",
        (call_id, role, content),
    )
    conn.commit()
    conn.close()


def save_caller_info(call_id, info):
    """Speichert extrahierte Anrufer-Informationen."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO caller_info
           (call_id, caller_name, caller_phone, concern,
            appointment_requested, preferred_time, urgency, callback_requested)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            call_id,
            info.get("name"),
            info.get("phone"),
            info.get("concern"),
            info.get("appointment_requested", False),
            info.get("preferred_time"),
            info.get("urgency", "mittel"),
            info.get("callback_requested", False),
        ),
    )
    conn.commit()
    conn.close()
    logger.info(f"Anrufer-Info gespeichert für {call_id}")


def get_call_history(call_id):
    """Lädt den Gesprächsverlauf eines Anrufs."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content, timestamp FROM messages WHERE call_id = ? ORDER BY timestamp",
        (call_id,),
    )
    messages = [
        {"role": row[0], "content": row[1], "timestamp": row[2]}
        for row in cursor.fetchall()
    ]
    conn.close()
    return messages


def get_recent_calls(limit=50):
    """Lädt die letzten Anrufe für das Dashboard."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        """SELECT c.*, ci.caller_name, ci.concern, ci.urgency, ci.callback_requested
           FROM calls c
           LEFT JOIN caller_info ci ON c.call_id = ci.call_id
           ORDER BY c.start_time DESC
           LIMIT ?""",
        (limit,),
    )
    calls = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return calls


def get_stats(days=30):
    """Statistiken für das Dashboard."""
    conn = _connect()
    cursor = conn.cursor()

    cursor.execute(
        """SELECT
               COUNT(*) as total_calls,
               AVG(duration_seconds) as avg_duration,
               SUM(CASE WHEN ci.callback_requested THEN 1 ELSE 0 END) as callbacks,
               SUM(CASE WHEN ci.appointment_requested THEN 1 ELSE 0 END) as appointments
           FROM calls c
           LEFT JOIN caller_info ci ON c.call_id = ci.call_id
           WHERE c.start_time >= datetime('now', ?)""",
        (f"-{days} days",),
    )

    row = cursor.fetchone()
    stats = {
        "total_calls": row[0] or 0,
        "avg_duration": round(row[1] or 0, 1),
        "callbacks_requested": row[2] or 0,
        "appointments_requested": row[3] or 0,
    }

    # Anrufe pro Tag
    cursor.execute(
        """SELECT DATE(start_time) as date, COUNT(*) as count
           FROM calls
           WHERE start_time >= datetime('now', ?)
           GROUP BY DATE(start_time)
           ORDER BY date""",
        (f"-{days} days",),
    )
    stats["daily"] = [{"date": row[0], "count": row[1]} for row in cursor.fetchall()]

    conn.close()
    return stats
