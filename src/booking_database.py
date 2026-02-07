"""
Datenbank fuer Termin- und Anfragen-Management.
Erweitert die bestehende call_database um Betriebe, Termine, Angebote.
"""

import os
import sqlite3
import secrets
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(os.environ.get("KI_DB_PATH", "/opt/ki-telefonassistent/logs/calls.db"))

# Deutsche Mobilfunk-Vorwahlen (015x, 016x, 017x)
MOBILE_PREFIXES = (
    "015", "016", "017",   # Standard
    "+4915", "+4916", "+4917",  # International
    "004915", "004916", "004917",
)

# Branchentypen die im Termin-Modus laufen (alle anderen = Auftrag)
TERMIN_TYPES = {"friseur", "kosmetik", "beauty", "massage", "nagelstudio", "barbershop",
                "physiotherapie", "heilpraktiker", "tattoo", "piercing", "spa", "wellness",
                "gastronomie", "restaurant", "hotel", "cafe", "bistro", "bar", "pension"}


def detect_phone_type(phone_number):
    """
    Erkennt ob eine Nummer Mobil oder Festnetz ist.
    Mobilnummern in DE beginnen mit 015x, 016x, 017x.
    Alles andere (Vorwahlen wie 030, 089, 0821 etc.) ist Festnetz.
    """
    if not phone_number:
        return "unbekannt"
    clean = phone_number.strip().replace(" ", "").replace("-", "").replace("/", "")
    if any(clean.startswith(p) for p in MOBILE_PREFIXES):
        return "mobil"
    return "festnetz"


def guess_business_mode(business_type):
    """Leitet den Modus aus dem Branchentyp ab."""
    if business_type.lower() in TERMIN_TYPES:
        return "termin"
    return "auftrag"


def get_db():
    """Gibt eine DB-Verbindung mit Row-Factory zurueck (WAL-Modus fuer Concurrency)."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_booking_tables():
    """Erstellt die zusaetzlichen Tabellen fuer Terminverwaltung."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        -- Betriebe (Kunden die unseren Service nutzen)
        -- mode: 'termin' (Friseur, Beauty, Massage etc.) oder 'auftrag' (Handwerk, Reparatur etc.)
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            business_type TEXT NOT NULL,
            mode TEXT DEFAULT 'termin',
            owner_name TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            access_token TEXT UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- Dienstleistungen / Angebote eines Betriebs
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            duration_minutes INTEGER DEFAULT 30,
            price_cents INTEGER,
            is_active BOOLEAN DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        );

        -- Termine (kommen ueber KI-Telefonassistent rein)
        -- phone_type: 'mobil' (SMS moeglich) oder 'festnetz' (kein SMS, Rueckruf noetig)
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            call_id TEXT,
            customer_name TEXT,
            customer_phone TEXT,
            customer_email TEXT,
            phone_type TEXT DEFAULT 'mobil',
            preferred_staff TEXT,
            service_id INTEGER,
            service_name_free TEXT,
            requested_date TEXT,
            requested_time TEXT,
            notes TEXT,
            status TEXT DEFAULT 'neu',
            confirmed_date TEXT,
            confirmed_time TEXT,
            rejection_reason TEXT,
            callback_required BOOLEAN DEFAULT 0,
            callback_done BOOLEAN DEFAULT 0,
            reminder_sent BOOLEAN DEFAULT 0,
            business_notes TEXT,
            call_summary TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE SET NULL,
            FOREIGN KEY (call_id) REFERENCES calls(call_id)
        );

        -- Anfragen (fuer Handwerker, Reparatur, etc. - detailliertere Anfragen)
        -- phone_type: 'mobil' oder 'festnetz'
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            call_id TEXT,
            customer_name TEXT,
            customer_phone TEXT,
            customer_email TEXT,
            customer_address TEXT,
            phone_type TEXT DEFAULT 'mobil',
            category TEXT,
            description TEXT,
            urgency TEXT DEFAULT 'normal',
            status TEXT DEFAULT 'neu',
            response_text TEXT,
            estimated_cost TEXT,
            scheduled_date TEXT,
            callback_required BOOLEAN DEFAULT 0,
            callback_done BOOLEAN DEFAULT 0,
            business_notes TEXT,
            call_summary TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            FOREIGN KEY (call_id) REFERENCES calls(call_id)
        );

        -- Kunden-Tokens fuer das Kunden-Portal
        CREATE TABLE IF NOT EXISTS customer_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            customer_phone TEXT NOT NULL,
            access_token TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
            UNIQUE(business_id, customer_phone)
        );

        CREATE INDEX IF NOT EXISTS idx_appointments_business ON appointments(business_id);
        CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);
        CREATE INDEX IF NOT EXISTS idx_inquiries_business ON inquiries(business_id);
        CREATE INDEX IF NOT EXISTS idx_inquiries_status ON inquiries(status);
        CREATE INDEX IF NOT EXISTS idx_services_business ON services(business_id);
        CREATE INDEX IF NOT EXISTS idx_businesses_token ON businesses(access_token);
        CREATE INDEX IF NOT EXISTS idx_customer_tokens_token ON customer_tokens(access_token);
        CREATE INDEX IF NOT EXISTS idx_customer_tokens_business_phone ON customer_tokens(business_id, customer_phone);
    """)

    conn.commit()

    # Migration: Spalten nachrüsten (fuer bestehende Datenbanken)
    migrations = [
        ("appointments", "reminder_sent", "BOOLEAN DEFAULT 0"),
        ("appointments", "callback_done", "BOOLEAN DEFAULT 0"),
        ("appointments", "business_notes", "TEXT"),
        ("appointments", "call_summary", "TEXT"),
        ("inquiries", "callback_done", "BOOLEAN DEFAULT 0"),
        ("inquiries", "business_notes", "TEXT"),
        ("inquiries", "call_summary", "TEXT"),
    ]
    conn = get_db()
    for table, column, coltype in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        except sqlite3.OperationalError:
            pass  # Spalte existiert bereits
    conn.commit()
    conn.close()

    logger.info("Booking-Tabellen initialisiert")


# ============================================================
# Betriebe (Businesses)
# ============================================================

def create_business(name, business_type, owner_name=None, email=None, phone=None, address=None, mode=None):
    """Erstellt einen neuen Betrieb und gibt den Access-Token zurueck."""
    token = secrets.token_urlsafe(32)
    if mode is None:
        mode = guess_business_mode(business_type)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO businesses (name, business_type, mode, owner_name, email, phone, address, access_token)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, business_type, mode, owner_name, email, phone, address, token),
    )
    business_id = cursor.lastrowid
    conn.commit()
    conn.close()
    logger.info(f"Betrieb erstellt: {name} (ID: {business_id}, Modus: {mode})")
    return {"id": business_id, "access_token": token, "mode": mode}


def get_business_by_token(token):
    """Findet einen Betrieb anhand seines Access-Tokens."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM businesses WHERE access_token = ? AND is_active = 1", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_business_by_id(business_id):
    """Findet einen Betrieb anhand seiner ID."""
    conn = get_db()
    row = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_business(business_id, **kwargs):
    """Aktualisiert Betriebsdaten."""
    allowed = {"name", "business_type", "owner_name", "email", "phone", "address"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False

    fields["updated_at"] = datetime.now().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [business_id]

    conn = get_db()
    conn.execute(f"UPDATE businesses SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return True


def list_businesses():
    """Listet alle aktiven Betriebe."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM businesses WHERE is_active = 1 ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# Dienstleistungen / Angebote (Services)
# ============================================================

def create_service(business_id, name, description=None, duration_minutes=30, price_cents=None):
    """Erstellt eine neue Dienstleistung."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO services (business_id, name, description, duration_minutes, price_cents)
           VALUES (?, ?, ?, ?, ?)""",
        (business_id, name, description, duration_minutes, price_cents),
    )
    service_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return service_id


def get_services(business_id, active_only=True):
    """Holt alle Dienstleistungen eines Betriebs."""
    conn = get_db()
    query = "SELECT * FROM services WHERE business_id = ?"
    params = [business_id]
    if active_only:
        query += " AND is_active = 1"
    query += " ORDER BY sort_order, name"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_service(service_id, business_id, **kwargs):
    """Aktualisiert eine Dienstleistung."""
    allowed = {"name", "description", "duration_minutes", "price_cents", "is_active", "sort_order"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [service_id, business_id]

    conn = get_db()
    conn.execute(
        f"UPDATE services SET {set_clause} WHERE id = ? AND business_id = ?", values
    )
    conn.commit()
    conn.close()
    return True


def delete_service(service_id, business_id):
    """Loescht eine Dienstleistung (soft-delete)."""
    conn = get_db()
    conn.execute(
        "UPDATE services SET is_active = 0 WHERE id = ? AND business_id = ?",
        (service_id, business_id),
    )
    conn.commit()
    conn.close()
    return True


# ============================================================
# Termine (Appointments)
# ============================================================

def create_appointment(business_id, customer_name, customer_phone, **kwargs):
    """Erstellt einen neuen Termin. Erkennt automatisch Festnetz/Mobil."""
    phone_type = detect_phone_type(customer_phone)
    callback_required = 1 if phone_type == "festnetz" else 0

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO appointments
           (business_id, call_id, customer_name, customer_phone, customer_email,
            phone_type, preferred_staff, service_id, service_name_free,
            requested_date, requested_time, notes, callback_required)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            business_id,
            kwargs.get("call_id"),
            customer_name,
            customer_phone,
            kwargs.get("customer_email"),
            phone_type,
            kwargs.get("preferred_staff"),
            kwargs.get("service_id"),
            kwargs.get("service_name_free"),
            kwargs.get("requested_date"),
            kwargs.get("requested_time"),
            kwargs.get("notes"),
            callback_required,
        ),
    )
    appointment_id = cursor.lastrowid
    conn.commit()
    conn.close()
    sms_info = "SMS moeglich" if phone_type == "mobil" else "FESTNETZ - Rueckruf noetig!"
    logger.info(f"Termin erstellt: ID {appointment_id} ({sms_info})")
    return appointment_id


def get_appointments(business_id, status=None, limit=50):
    """Holt Termine eines Betriebs."""
    conn = get_db()
    query = """SELECT a.*, s.name as service_name
               FROM appointments a
               LEFT JOIN services s ON a.service_id = s.id
               WHERE a.business_id = ?"""
    params = [business_id]

    if status:
        query += " AND a.status = ?"
        params.append(status)

    query += " ORDER BY a.created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_appointment(appointment_id, business_id):
    """Holt einen einzelnen Termin."""
    conn = get_db()
    row = conn.execute(
        """SELECT a.*, s.name as service_name
           FROM appointments a
           LEFT JOIN services s ON a.service_id = s.id
           WHERE a.id = ? AND a.business_id = ?""",
        (appointment_id, business_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_appointment_status(appointment_id, business_id, status, **kwargs):
    """
    Aktualisiert den Status eines Termins.
    Status: neu, bestaetigt, abgelehnt, verschoben, erledigt
    """
    conn = get_db()
    fields = {"status": status, "updated_at": datetime.now().isoformat()}

    if status in ("bestaetigt", "verschoben"):
        fields["confirmed_date"] = kwargs.get("confirmed_date")
        fields["confirmed_time"] = kwargs.get("confirmed_time")
    elif status == "abgelehnt":
        fields["rejection_reason"] = kwargs.get("rejection_reason")

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [appointment_id, business_id]

    conn.execute(
        f"UPDATE appointments SET {set_clause} WHERE id = ? AND business_id = ?", values
    )
    conn.commit()
    conn.close()
    logger.info(f"Termin {appointment_id} Status -> {status}")
    return True


# ============================================================
# Anfragen (Inquiries) - fuer Handwerker etc.
# ============================================================

def create_inquiry(business_id, customer_name, customer_phone, description, **kwargs):
    """Erstellt eine neue Anfrage. Erkennt automatisch Festnetz/Mobil."""
    phone_type = detect_phone_type(customer_phone)
    callback_required = 1 if phone_type == "festnetz" else 0

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO inquiries
           (business_id, call_id, customer_name, customer_phone, customer_email,
            customer_address, phone_type, category, description, urgency, callback_required)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            business_id,
            kwargs.get("call_id"),
            customer_name,
            customer_phone,
            kwargs.get("customer_email"),
            kwargs.get("customer_address"),
            phone_type,
            kwargs.get("category"),
            description,
            kwargs.get("urgency", "normal"),
            callback_required,
        ),
    )
    inquiry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    sms_info = "SMS moeglich" if phone_type == "mobil" else "FESTNETZ - Rueckruf noetig!"
    logger.info(f"Anfrage erstellt: ID {inquiry_id} ({sms_info})")
    return inquiry_id


def get_inquiries(business_id, status=None, limit=50):
    """Holt Anfragen eines Betriebs."""
    conn = get_db()
    query = "SELECT * FROM inquiries WHERE business_id = ?"
    params = [business_id]

    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_inquiry(inquiry_id, business_id):
    """Holt eine einzelne Anfrage."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM inquiries WHERE id = ? AND business_id = ?",
        (inquiry_id, business_id),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_inquiry_status(inquiry_id, business_id, status, **kwargs):
    """
    Aktualisiert den Status einer Anfrage.
    Status: neu, in_bearbeitung, angebot_gesendet, erledigt, abgelehnt
    """
    conn = get_db()
    fields = {"status": status, "updated_at": datetime.now().isoformat()}

    if kwargs.get("response_text"):
        fields["response_text"] = kwargs["response_text"]
    if kwargs.get("estimated_cost"):
        fields["estimated_cost"] = kwargs["estimated_cost"]
    if kwargs.get("scheduled_date"):
        fields["scheduled_date"] = kwargs["scheduled_date"]

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [inquiry_id, business_id]

    conn.execute(
        f"UPDATE inquiries SET {set_clause} WHERE id = ? AND business_id = ?", values
    )
    conn.commit()
    conn.close()
    logger.info(f"Anfrage {inquiry_id} Status -> {status}")
    return True


# ============================================================
# Statistiken fuer Betriebe
# ============================================================

def get_business_stats(business_id):
    """Statistiken fuer ein Betriebs-Dashboard."""
    conn = get_db()

    stats = {}

    # Termine
    row = conn.execute(
        """SELECT
               COUNT(*) as total,
               SUM(CASE WHEN status = 'neu' THEN 1 ELSE 0 END) as neue,
               SUM(CASE WHEN status = 'bestaetigt' THEN 1 ELSE 0 END) as bestaetigt,
               SUM(CASE WHEN status = 'abgelehnt' THEN 1 ELSE 0 END) as abgelehnt
           FROM appointments WHERE business_id = ?""",
        (business_id,),
    ).fetchone()
    stats["appointments"] = dict(row) if row else {}

    # Anfragen
    row = conn.execute(
        """SELECT
               COUNT(*) as total,
               SUM(CASE WHEN status = 'neu' THEN 1 ELSE 0 END) as neue,
               SUM(CASE WHEN status = 'in_bearbeitung' THEN 1 ELSE 0 END) as in_bearbeitung,
               SUM(CASE WHEN status = 'erledigt' THEN 1 ELSE 0 END) as erledigt
           FROM inquiries WHERE business_id = ?""",
        (business_id,),
    ).fetchone()
    stats["inquiries"] = dict(row) if row else {}

    # Dienstleistungen
    row = conn.execute(
        "SELECT COUNT(*) as total FROM services WHERE business_id = ? AND is_active = 1",
        (business_id,),
    ).fetchone()
    stats["services_count"] = row["total"] if row else 0

    conn.close()
    return stats


# ============================================================
# Erinnerungen
# ============================================================

def get_upcoming_reminders(hours_ahead=24):
    """
    Findet bestaetigte Termine die in den naechsten X Stunden stattfinden
    und fuer die noch keine Erinnerung gesendet wurde.
    Nur Mobilnummern (SMS moeglich).
    """
    conn = get_db()
    # confirmed_date ist im Format YYYY-MM-DD, confirmed_time ist HH:MM
    # Wir suchen Termine deren confirmed_date morgen ist
    rows = conn.execute(
        """SELECT a.*, b.name as business_name, b.phone as business_phone
           FROM appointments a
           JOIN businesses b ON a.business_id = b.id
           WHERE a.status = 'bestaetigt'
             AND a.reminder_sent = 0
             AND a.phone_type = 'mobil'
             AND a.confirmed_date IS NOT NULL
             AND a.confirmed_date = DATE('now', '+1 day')""",
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_reminder_sent(appointment_id):
    """Markiert eine Erinnerung als gesendet."""
    conn = get_db()
    conn.execute(
        "UPDATE appointments SET reminder_sent = 1 WHERE id = ?",
        (appointment_id,),
    )
    conn.commit()
    conn.close()


# ============================================================
# Notizen (Business Notes)
# ============================================================

def update_business_notes(item_type, item_id, business_id, notes):
    """Speichert Betriebsnotizen fuer einen Termin oder eine Anfrage."""
    table = "appointments" if item_type == "termin" else "inquiries"
    conn = get_db()
    conn.execute(
        f"UPDATE {table} SET business_notes = ?, updated_at = ? WHERE id = ? AND business_id = ?",
        (notes, datetime.now().isoformat(), item_id, business_id),
    )
    conn.commit()
    conn.close()
    return True


# ============================================================
# Rueckruf-Tracking
# ============================================================

def mark_callback_done(item_type, item_id, business_id):
    """Markiert einen Rueckruf als erledigt."""
    table = "appointments" if item_type == "termin" else "inquiries"
    conn = get_db()
    conn.execute(
        f"UPDATE {table} SET callback_done = 1, updated_at = ? WHERE id = ? AND business_id = ?",
        (datetime.now().isoformat(), item_id, business_id),
    )
    conn.commit()
    conn.close()
    return True


# ============================================================
# Anruf-Zusammenfassung
# ============================================================

def set_call_summary(item_type, item_id, summary):
    """Speichert die Anruf-Zusammenfassung bei einem Termin/Anfrage."""
    table = "appointments" if item_type == "termin" else "inquiries"
    conn = get_db()
    conn.execute(
        f"UPDATE {table} SET call_summary = ? WHERE id = ?",
        (summary, item_id),
    )
    conn.commit()
    conn.close()
    return True


# ============================================================
# Suche
# ============================================================

def search_items(business_id, mode, query, limit=50):
    """
    Sucht Termine oder Anfragen nach Name, Telefonnummer oder Datum.
    """
    conn = get_db()
    search = f"%{query}%"

    if mode == "termin":
        rows = conn.execute(
            """SELECT a.*, s.name as service_name
               FROM appointments a
               LEFT JOIN services s ON a.service_id = s.id
               WHERE a.business_id = ?
                 AND (a.customer_name LIKE ?
                      OR a.customer_phone LIKE ?
                      OR a.requested_date LIKE ?
                      OR a.confirmed_date LIKE ?
                      OR a.notes LIKE ?
                      OR a.service_name_free LIKE ?)
               ORDER BY a.created_at DESC LIMIT ?""",
            (business_id, search, search, search, search, search, search, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM inquiries
               WHERE business_id = ?
                 AND (customer_name LIKE ?
                      OR customer_phone LIKE ?
                      OR description LIKE ?
                      OR category LIKE ?
                      OR customer_address LIKE ?)
               ORDER BY created_at DESC LIMIT ?""",
            (business_id, search, search, search, search, search, limit),
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# Duplikat-Erkennung
# ============================================================

def find_duplicates(business_id, customer_phone, mode, exclude_id=None):
    """
    Findet bestehende Eintraege mit gleicher Telefonnummer.
    Gibt aktive (nicht erledigte/abgelehnte) Eintraege zurueck.
    """
    if not customer_phone:
        return []

    conn = get_db()
    if mode == "termin":
        query = """SELECT id, customer_name, status, requested_date, created_at
                   FROM appointments
                   WHERE business_id = ? AND customer_phone = ?
                     AND status NOT IN ('erledigt', 'abgelehnt')"""
        params = [business_id, customer_phone]
        if exclude_id:
            query += " AND id != ?"
            params.append(exclude_id)
        query += " ORDER BY created_at DESC LIMIT 5"
    else:
        query = """SELECT id, customer_name, status, description, created_at
                   FROM inquiries
                   WHERE business_id = ? AND customer_phone = ?
                     AND status NOT IN ('erledigt', 'abgelehnt')"""
        params = [business_id, customer_phone]
        if exclude_id:
            query += " AND id != ?"
            params.append(exclude_id)
        query += " ORDER BY created_at DESC LIMIT 5"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============================================================
# Kunden-Portal Tokens
# ============================================================

def get_or_create_customer_token(business_id, customer_phone):
    """Holt einen bestehenden Token oder erstellt einen neuen. Stammkunden bekommen immer den gleichen Token."""
    conn = get_db()
    row = conn.execute(
        "SELECT access_token FROM customer_tokens WHERE business_id = ? AND customer_phone = ?",
        (business_id, customer_phone),
    ).fetchone()
    if row:
        conn.close()
        return row["access_token"]

    token = secrets.token_urlsafe(32)
    try:
        conn.execute(
            "INSERT INTO customer_tokens (business_id, customer_phone, access_token) VALUES (?, ?, ?)",
            (business_id, customer_phone, token),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # Race condition: Token wurde zwischenzeitlich erstellt
        row = conn.execute(
            "SELECT access_token FROM customer_tokens WHERE business_id = ? AND customer_phone = ?",
            (business_id, customer_phone),
        ).fetchone()
        token = row["access_token"] if row else token
    conn.close()
    logger.info(f"Kunden-Token erstellt/geholt fuer Betrieb {business_id}")
    return token


def get_customer_by_token(token):
    """Laedt Kunden-Daten und Business-Name anhand eines Tokens."""
    conn = get_db()
    row = conn.execute(
        """SELECT ct.*, b.name as business_name, b.phone as business_phone
           FROM customer_tokens ct
           JOIN businesses b ON ct.business_id = b.id
           WHERE ct.access_token = ?""",
        (token,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_customer_appointments(business_id, customer_phone):
    """Holt alle Termine eines Kunden bei einem bestimmten Betrieb."""
    conn = get_db()
    rows = conn.execute(
        """SELECT a.*, s.name as service_name
           FROM appointments a
           LEFT JOIN services s ON a.service_id = s.id
           WHERE a.business_id = ? AND a.customer_phone = ?
           ORDER BY a.created_at DESC""",
        (business_id, customer_phone),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def customer_cancel_appointment(apt_id, business_id, customer_phone):
    """Storniert einen Termin (nur wenn er dem Kunden gehoert)."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, status FROM appointments WHERE id = ? AND business_id = ? AND customer_phone = ?",
        (apt_id, business_id, customer_phone),
    ).fetchone()
    if not row:
        conn.close()
        return False
    if row["status"] in ("storniert", "erledigt"):
        conn.close()
        return False
    conn.execute(
        "UPDATE appointments SET status = 'storniert', updated_at = ? WHERE id = ?",
        (datetime.now().isoformat(), apt_id),
    )
    conn.commit()
    conn.close()
    logger.info(f"Termin {apt_id} vom Kunden storniert")
    return True


def customer_request_reschedule(apt_id, business_id, customer_phone, new_date, new_time):
    """Speichert einen Aenderungswunsch in business_notes."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, status, business_notes FROM appointments WHERE id = ? AND business_id = ? AND customer_phone = ?",
        (apt_id, business_id, customer_phone),
    ).fetchone()
    if not row:
        conn.close()
        return False
    if row["status"] in ("storniert", "erledigt"):
        conn.close()
        return False

    note = f"[AENDERUNGSWUNSCH] Neuer Termin: {new_date} um {new_time}"
    existing = row["business_notes"] or ""
    updated_notes = f"{existing}\n{note}".strip() if existing else note

    conn.execute(
        "UPDATE appointments SET business_notes = ?, updated_at = ? WHERE id = ?",
        (updated_notes, datetime.now().isoformat(), apt_id),
    )
    conn.commit()
    conn.close()
    logger.info(f"Aenderungswunsch fuer Termin {apt_id} gespeichert")
    return True
