"""
Einheitliche REST-API fuer das universelle Dashboard.
Merged aus versicherung_api.py + booking_api.py mit require_auth.
Unterstuetzt alle Branchen (Versicherung, Handwerk, etc.).
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

from src.auth import require_auth
from src.booking_database import (
    get_db,
    get_business_stats,
    get_appointments,
    get_appointment,
    update_appointment_status,
    get_inquiries,
    get_inquiry,
    update_inquiry_status,
    update_business_notes,
    mark_callback_done,
    search_items,
)
from src.call_database import get_call_history
from src.push_notifications import save_push_subscription, remove_push_subscription

logger = logging.getLogger(__name__)

universal_api = Blueprint("universal_api", __name__, url_prefix="/api/d")


# ============================================================
# Hilfsfunktionen
# ============================================================

def _is_versicherung(business):
    """Prueft ob es ein Versicherungs-Business ist (liest aus inquiries mit calls)."""
    btype = (business.get("business_type") or "").lower()
    return btype in ("versicherung", "versicherungsberater", "versicherungsmakler", "insurance")


def _get_versicherung_anrufe(business_id, status=None, search=None, limit=50):
    """Holt Anrufe mit caller_info fuer Versicherungs-Businesses."""
    conn = get_db()
    query = """
        SELECT i.id, i.call_id, i.customer_name, i.customer_phone, i.description,
               i.category, i.urgency, i.status, i.business_notes, i.callback_required,
               i.callback_done, i.created_at, i.phone_type,
               c.start_time, c.duration_seconds, c.caller_number,
               ci.concern, ci.caller_name as ci_name, ci.callback_requested as ci_callback,
               ci.appointment_requested
        FROM inquiries i
        LEFT JOIN calls c ON i.call_id = c.call_id
        LEFT JOIN caller_info ci ON i.call_id = ci.call_id
        WHERE i.business_id = ?
    """
    params = [business_id]

    if status:
        if status == "offen":
            query += " AND i.status IN ('neu', 'in_bearbeitung')"
        elif status == "dringend":
            query += " AND (i.urgency IN ('hoch', 'dringend') OR i.category = 'schaden')"
        elif status == "erledigt":
            query += " AND i.status IN ('erledigt', 'zurueckgerufen', 'termin_eingetragen')"
        else:
            query += " AND i.status = ?"
            params.append(status)

    if search:
        query += """ AND (i.customer_name LIKE ? OR i.customer_phone LIKE ?
                     OR i.description LIKE ? OR ci.concern LIKE ?)"""
        s = f"%{search}%"
        params.extend([s, s, s, s])

    query += " ORDER BY COALESCE(c.start_time, i.created_at) DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        anruf_typ = "frage"
        cat = (d.get("category") or "").lower()
        urg = (d.get("urgency") or "").lower()
        if cat == "schaden" or urg in ("hoch", "dringend"):
            anruf_typ = "schaden"
        elif d.get("appointment_requested") or cat == "termin":
            anruf_typ = "termin"

        d["anruf_typ"] = anruf_typ
        d["name"] = d.get("customer_name") or d.get("ci_name") or "Unbekannt"
        d["telefon"] = d.get("customer_phone") or d.get("caller_number") or ""
        d["anliegen"] = d.get("concern") or d.get("description") or ""
        d["uhrzeit"] = d.get("start_time") or d.get("created_at") or ""
        d["dauer"] = d.get("duration_seconds") or 0
        result.append(d)

    return result


def _get_handwerk_items(business_id, status=None, search=None, limit=50):
    """Holt Eintraege fuer Handwerk-Businesses (Appointments + Inquiries)."""
    mode = "auftrag"  # Handwerk default
    conn = get_db()

    # Inquiries laden
    query = "SELECT * FROM inquiries WHERE business_id = ?"
    params = [business_id]

    if status:
        if status == "offen":
            query += " AND status IN ('neu', 'in_bearbeitung')"
        elif status == "erledigt":
            query += " AND status IN ('erledigt', 'abgelehnt')"
        else:
            query += " AND status = ?"
            params.append(status)

    if search:
        s = f"%{search}%"
        query += """ AND (customer_name LIKE ? OR customer_phone LIKE ?
                     OR description LIKE ? OR category LIKE ?)"""
        params.extend([s, s, s, s])

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        cat = (d.get("category") or "").lower()
        if cat in ("auftrag", "reparatur", "notfall"):
            d["anruf_typ"] = "auftrag"
        elif cat == "termin":
            d["anruf_typ"] = "termin"
        else:
            d["anruf_typ"] = "beratung"
        d["name"] = d.get("customer_name") or "Unbekannt"
        d["telefon"] = d.get("customer_phone") or ""
        d["anliegen"] = d.get("description") or ""
        d["uhrzeit"] = d.get("created_at") or ""
        d["dauer"] = 0
        result.append(d)

    return result


# ============================================================
# Dashboard (Stats + letzte Eintraege)
# ============================================================

@universal_api.route("/dashboard", methods=["GET"])
@require_auth
def api_dashboard(business):
    """Dashboard-Daten: Stats + letzte Eintraege."""
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    if _is_versicherung(business):
        # Versicherungs-Stats
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM inquiries i
               LEFT JOIN calls c ON i.call_id = c.call_id
               WHERE i.business_id = ? AND DATE(COALESCE(c.start_time, i.created_at)) = ?""",
            (business["id"], today),
        ).fetchone()
        stat1 = row["cnt"] if row else 0

        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM inquiries
               WHERE business_id = ? AND status IN ('neu', 'in_bearbeitung')
                 AND callback_required = 1 AND callback_done = 0""",
            (business["id"],),
        ).fetchone()
        stat2 = row["cnt"] if row else 0

        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM inquiries i
               LEFT JOIN caller_info ci ON i.call_id = ci.call_id
               WHERE i.business_id = ? AND (ci.appointment_requested = 1 OR i.category = 'termin')""",
            (business["id"],),
        ).fetchone()
        stat3 = row["cnt"] if row else 0

        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM inquiries
               WHERE business_id = ? AND (category = 'schaden' OR urgency IN ('hoch', 'dringend'))""",
            (business["id"],),
        ).fetchone()
        stat4 = row["cnt"] if row else 0

        conn.close()
        items = _get_versicherung_anrufe(business["id"], limit=10)

        return jsonify({
            "business": {
                "id": business["id"],
                "name": business["name"],
                "type": business.get("business_type", ""),
                "mode": business.get("mode", "auftrag"),
            },
            "stats": {
                "values": [stat1, stat2, stat3, stat4],
            },
            "items": items,
        })
    else:
        # Handwerk / Allgemein Stats
        stats = get_business_stats(business["id"])
        inq = stats.get("inquiries", {})
        apt = stats.get("appointments", {})

        stat1 = (inq.get("neue", 0) or 0) + (apt.get("neue", 0) or 0)
        stat2 = (inq.get("in_bearbeitung", 0) or 0)
        stat3 = (apt.get("bestaetigt", 0) or 0) + (apt.get("neue", 0) or 0)
        stat4 = (inq.get("erledigt", 0) or 0)

        conn.close()
        items = _get_handwerk_items(business["id"], limit=10)

        return jsonify({
            "business": {
                "id": business["id"],
                "name": business["name"],
                "type": business.get("business_type", ""),
                "mode": business.get("mode", "auftrag"),
            },
            "stats": {
                "values": [stat1, stat2, stat3, stat4],
            },
            "items": items,
        })


# ============================================================
# Alle Eintraege (Items)
# ============================================================

@universal_api.route("/items", methods=["GET"])
@require_auth
def api_items(business):
    """Alle Eintraege mit Filtern."""
    status = request.args.get("status")
    search = request.args.get("q")
    limit = request.args.get("limit", 50, type=int)

    if _is_versicherung(business):
        items = _get_versicherung_anrufe(business["id"], status=status, search=search, limit=limit)
    else:
        items = _get_handwerk_items(business["id"], status=status, search=search, limit=limit)

    return jsonify(items)


# ============================================================
# Item-Detail + Transkript
# ============================================================

@universal_api.route("/items/<int:item_id>", methods=["GET"])
@require_auth
def api_item_detail(item_id, business):
    """Detail + Messages (Transkript)."""
    conn = get_db()

    if _is_versicherung(business):
        row = conn.execute(
            """SELECT i.*, c.start_time, c.duration_seconds, c.caller_number,
                      ci.concern, ci.caller_name as ci_name, ci.callback_requested as ci_callback,
                      ci.appointment_requested, ci.preferred_time, ci.notes as ci_notes
               FROM inquiries i
               LEFT JOIN calls c ON i.call_id = c.call_id
               LEFT JOIN caller_info ci ON i.call_id = ci.call_id
               WHERE i.id = ? AND i.business_id = ?""",
            (item_id, business["id"]),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM inquiries WHERE id = ? AND business_id = ?",
            (item_id, business["id"]),
        ).fetchone()

    conn.close()

    if not row:
        return jsonify({"error": "Eintrag nicht gefunden"}), 404

    d = dict(row)

    # Transkript laden
    messages = []
    if d.get("call_id"):
        messages = get_call_history(d["call_id"])
    d["messages"] = messages

    d["name"] = d.get("customer_name") or d.get("ci_name") or "Unbekannt"
    d["telefon"] = d.get("customer_phone") or d.get("caller_number") or ""
    d["anliegen"] = d.get("concern") or d.get("description") or ""

    return jsonify(d)


# ============================================================
# Status aendern
# ============================================================

@universal_api.route("/items/<int:item_id>/status", methods=["POST"])
@require_auth
def api_update_status(item_id, business):
    """Status aendern."""
    data = request.get_json()
    if not data or not data.get("status"):
        return jsonify({"error": "Status erforderlich"}), 400

    new_status = data["status"]

    conn = get_db()
    conn.execute(
        "UPDATE inquiries SET status = ?, updated_at = ? WHERE id = ? AND business_id = ?",
        (new_status, datetime.now().isoformat(), item_id, business["id"]),
    )
    if new_status == "zurueckgerufen":
        conn.execute(
            "UPDATE inquiries SET callback_done = 1 WHERE id = ? AND business_id = ?",
            (item_id, business["id"]),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "status": new_status})


# ============================================================
# Notiz speichern
# ============================================================

@universal_api.route("/items/<int:item_id>/notes", methods=["POST"])
@require_auth
def api_save_notes(item_id, business):
    """Notiz hinzufuegen/aendern."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Keine Daten"}), 400

    notiz = data.get("notiz", "").strip()
    conn = get_db()
    conn.execute(
        "UPDATE inquiries SET business_notes = ?, updated_at = ? WHERE id = ? AND business_id = ?",
        (notiz, datetime.now().isoformat(), item_id, business["id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ============================================================
# Wochen-Statistik
# ============================================================

@universal_api.route("/stats/weekly", methods=["GET"])
@require_auth
def api_stats_weekly(business):
    """Wochen-Statistik."""
    conn = get_db()
    wochentage = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    days = []
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        weekday_idx = (datetime.now() - timedelta(days=i)).weekday()

        if _is_versicherung(business):
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM inquiries i
                   LEFT JOIN calls c ON i.call_id = c.call_id
                   WHERE i.business_id = ? AND DATE(COALESCE(c.start_time, i.created_at)) = ?""",
                (business["id"], d),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM inquiries WHERE business_id = ? AND DATE(created_at) = ?",
                (business["id"], d),
            ).fetchone()
        days.append({
            "date": d,
            "label": wochentage[weekday_idx],
            "count": row["cnt"] if row else 0,
        })

    # Verteilung
    if _is_versicherung(business):
        row_cat1 = conn.execute(
            """SELECT COUNT(*) as cnt FROM inquiries
               WHERE business_id = ? AND (category = 'schaden' OR urgency IN ('hoch', 'dringend'))""",
            (business["id"],),
        ).fetchone()
        row_cat2 = conn.execute(
            """SELECT COUNT(*) as cnt FROM inquiries i
               LEFT JOIN caller_info ci ON i.call_id = ci.call_id
               WHERE i.business_id = ? AND (ci.appointment_requested = 1 OR i.category = 'termin')""",
            (business["id"],),
        ).fetchone()
        row_total = conn.execute(
            "SELECT COUNT(*) as cnt FROM inquiries WHERE business_id = ?",
            (business["id"],),
        ).fetchone()
        total = row_total["cnt"] if row_total else 0
        cat1 = row_cat1["cnt"] if row_cat1 else 0
        cat2 = row_cat2["cnt"] if row_cat2 else 0
        cat3 = max(0, total - cat1 - cat2)
    else:
        row_cat1 = conn.execute(
            "SELECT COUNT(*) as cnt FROM inquiries WHERE business_id = ? AND category = 'auftrag'",
            (business["id"],),
        ).fetchone()
        row_cat2 = conn.execute(
            "SELECT COUNT(*) as cnt FROM inquiries WHERE business_id = ? AND category = 'termin'",
            (business["id"],),
        ).fetchone()
        row_total = conn.execute(
            "SELECT COUNT(*) as cnt FROM inquiries WHERE business_id = ?",
            (business["id"],),
        ).fetchone()
        total = row_total["cnt"] if row_total else 0
        cat1 = row_cat1["cnt"] if row_cat1 else 0
        cat2 = row_cat2["cnt"] if row_cat2 else 0
        cat3 = max(0, total - cat1 - cat2)

    # Durchschnittliche Gespraechsdauer
    row_dur = conn.execute(
        """SELECT AVG(c.duration_seconds) as avg_dur FROM inquiries i
           JOIN calls c ON i.call_id = c.call_id
           WHERE i.business_id = ? AND c.duration_seconds > 0""",
        (business["id"],),
    ).fetchone()
    avg_dauer = round(row_dur["avg_dur"] or 0) if row_dur else 0

    conn.close()

    return jsonify({
        "woche": days,
        "verteilung": {
            "cat1": cat1,
            "cat2": cat2,
            "cat3": cat3,
        },
        "avg_dauer_sekunden": avg_dauer,
    })


# ============================================================
# Push-Benachrichtigungen
# ============================================================

@universal_api.route("/push/subscribe", methods=["POST"])
@require_auth
def api_push_subscribe(business):
    """Push-Subscription speichern."""
    data = request.get_json()
    if not data or not data.get("subscription"):
        return jsonify({"error": "Subscription erforderlich"}), 400
    save_push_subscription(business["id"], data["subscription"])
    return jsonify({"ok": True})


@universal_api.route("/push/unsubscribe", methods=["POST"])
@require_auth
def api_push_unsubscribe(business):
    """Push-Subscription entfernen."""
    data = request.get_json()
    if not data or not data.get("endpoint"):
        return jsonify({"error": "Endpoint erforderlich"}), 400
    remove_push_subscription(data["endpoint"])
    return jsonify({"ok": True})
