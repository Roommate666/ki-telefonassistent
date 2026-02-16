"""
REST-API fuer das Versicherungsberater-Dashboard.
Liest aus calls + caller_info + messages + inquiries Tabellen.
Auth per Access-Token (gleicher Mechanismus wie booking_api.py).
"""

import logging
from functools import wraps
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify

from src.booking_database import get_business_by_token, get_db
from src.call_database import get_call_history
from src.push_notifications import save_push_subscription, remove_push_subscription

logger = logging.getLogger(__name__)

versicherung_api = Blueprint("versicherung_api", __name__, url_prefix="/api/v")


# ============================================================
# Auth-Middleware
# ============================================================

def require_business(f):
    """Prueft den Access-Token und laedt den Betrieb."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Access-Token") or request.args.get("token")
        if not token:
            return jsonify({"error": "Kein Access-Token angegeben"}), 401

        business = get_business_by_token(token)
        if not business:
            return jsonify({"error": "Ungueltiger oder inaktiver Token"}), 401

        kwargs["business"] = business
        return f(*args, **kwargs)
    return decorated


# ============================================================
# Hilfsfunktion: Anrufe laden
# ============================================================

def _get_anrufe(business_id, status=None, search=None, limit=50):
    """Holt Anrufe mit Details fuer einen Betrieb."""
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
        # Typ bestimmen: schaden, termin, frage
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


# ============================================================
# Dashboard (Stats + letzte Anrufe)
# ============================================================

@versicherung_api.route("/dashboard", methods=["GET"])
@require_business
def api_dashboard(business):
    """Dashboard-Daten: Stats + letzte Anrufe."""
    conn = get_db()
    today = datetime.now().strftime("%Y-%m-%d")

    # Anrufe heute
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM inquiries i
           LEFT JOIN calls c ON i.call_id = c.call_id
           WHERE i.business_id = ? AND DATE(COALESCE(c.start_time, i.created_at)) = ?""",
        (business["id"], today),
    ).fetchone()
    anrufe_heute = row["cnt"] if row else 0

    # Offene Rueckrufe
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM inquiries
           WHERE business_id = ? AND status IN ('neu', 'in_bearbeitung')
             AND callback_required = 1 AND callback_done = 0""",
        (business["id"],),
    ).fetchone()
    offene_rueckrufe = row["cnt"] if row else 0

    # Termine (appointment_requested via caller_info)
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM inquiries i
           LEFT JOIN caller_info ci ON i.call_id = ci.call_id
           WHERE i.business_id = ? AND (ci.appointment_requested = 1 OR i.category = 'termin')""",
        (business["id"],),
    ).fetchone()
    termine = row["cnt"] if row else 0

    # Schadensmeldungen
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM inquiries
           WHERE business_id = ? AND (category = 'schaden' OR urgency IN ('hoch', 'dringend'))""",
        (business["id"],),
    ).fetchone()
    schaeden = row["cnt"] if row else 0

    conn.close()

    anrufe = _get_anrufe(business["id"], limit=10)

    return jsonify({
        "business": {
            "id": business["id"],
            "name": business["name"],
        },
        "stats": {
            "anrufe_heute": anrufe_heute,
            "offene_rueckrufe": offene_rueckrufe,
            "termine": termine,
            "schaeden": schaeden,
        },
        "anrufe": anrufe,
    })


# ============================================================
# Alle Anrufe
# ============================================================

@versicherung_api.route("/anrufe", methods=["GET"])
@require_business
def api_anrufe(business):
    """Alle Anrufe mit Caller-Info + Inquiry-Status."""
    status = request.args.get("status")
    search = request.args.get("q")
    limit = request.args.get("limit", 50, type=int)
    anrufe = _get_anrufe(business["id"], status=status, search=search, limit=limit)
    return jsonify(anrufe)


# ============================================================
# Anruf-Detail + Transkript
# ============================================================

@versicherung_api.route("/anrufe/<int:inquiry_id>", methods=["GET"])
@require_business
def api_anruf_detail(inquiry_id, business):
    """Detail + Messages (Transkript)."""
    conn = get_db()
    row = conn.execute(
        """SELECT i.*, c.start_time, c.duration_seconds, c.caller_number,
                  ci.concern, ci.caller_name as ci_name, ci.callback_requested as ci_callback,
                  ci.appointment_requested, ci.preferred_time, ci.notes as ci_notes
           FROM inquiries i
           LEFT JOIN calls c ON i.call_id = c.call_id
           LEFT JOIN caller_info ci ON i.call_id = ci.call_id
           WHERE i.id = ? AND i.business_id = ?""",
        (inquiry_id, business["id"]),
    ).fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Anruf nicht gefunden"}), 404

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

@versicherung_api.route("/anrufe/<int:inquiry_id>/status", methods=["POST"])
@require_business
def api_update_status(inquiry_id, business):
    """Status aendern (zurueckgerufen, erledigt, etc.)."""
    data = request.get_json()
    if not data or not data.get("status"):
        return jsonify({"error": "Status erforderlich"}), 400

    new_status = data["status"]
    allowed = {"neu", "in_bearbeitung", "zurueckgerufen", "termin_eingetragen", "erledigt"}
    if new_status not in allowed:
        return jsonify({"error": "Ungueltiger Status"}), 400

    conn = get_db()
    conn.execute(
        "UPDATE inquiries SET status = ?, updated_at = ? WHERE id = ? AND business_id = ?",
        (new_status, datetime.now().isoformat(), inquiry_id, business["id"]),
    )
    if new_status == "zurueckgerufen":
        conn.execute(
            "UPDATE inquiries SET callback_done = 1 WHERE id = ? AND business_id = ?",
            (inquiry_id, business["id"]),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "status": new_status})


# ============================================================
# Notiz hinzufuegen
# ============================================================

@versicherung_api.route("/anrufe/<int:inquiry_id>/notiz", methods=["POST"])
@require_business
def api_add_notiz(inquiry_id, business):
    """Notiz hinzufuegen."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Keine Daten"}), 400

    notiz = data.get("notiz", "").strip()
    conn = get_db()
    conn.execute(
        "UPDATE inquiries SET business_notes = ?, updated_at = ? WHERE id = ? AND business_id = ?",
        (notiz, datetime.now().isoformat(), inquiry_id, business["id"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ============================================================
# Wochen-Statistik
# ============================================================

@versicherung_api.route("/stats/weekly", methods=["GET"])
@require_business
def api_stats_weekly(business):
    """Wochen-Statistik."""
    conn = get_db()
    wochentage = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    # Letzte 7 Tage
    days = []
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        weekday_idx = (datetime.now() - timedelta(days=i)).weekday()
        row = conn.execute(
            """SELECT COUNT(*) as cnt FROM inquiries i
               LEFT JOIN calls c ON i.call_id = c.call_id
               WHERE i.business_id = ? AND DATE(COALESCE(c.start_time, i.created_at)) = ?""",
            (business["id"], d),
        ).fetchone()
        days.append({
            "date": d,
            "label": wochentage[weekday_idx],
            "count": row["cnt"] if row else 0,
        })

    # Anliegen-Verteilung
    row_schaden = conn.execute(
        """SELECT COUNT(*) as cnt FROM inquiries
           WHERE business_id = ? AND (category = 'schaden' OR urgency IN ('hoch', 'dringend'))""",
        (business["id"],),
    ).fetchone()
    row_termin = conn.execute(
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
    schaeden = row_schaden["cnt"] if row_schaden else 0
    termine = row_termin["cnt"] if row_termin else 0
    fragen = max(0, total - schaeden - termine)

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
            "schaden": schaeden,
            "termin": termine,
            "frage": fragen,
        },
        "avg_dauer_sekunden": avg_dauer,
    })


# ============================================================
# Push-Benachrichtigungen
# ============================================================

@versicherung_api.route("/push/subscribe", methods=["POST"])
@require_business
def api_push_subscribe(business):
    """Push-Subscription speichern."""
    data = request.get_json()
    if not data or not data.get("subscription"):
        return jsonify({"error": "Subscription erforderlich"}), 400
    save_push_subscription(business["id"], data["subscription"])
    return jsonify({"ok": True})


@versicherung_api.route("/push/unsubscribe", methods=["POST"])
@require_business
def api_push_unsubscribe(business):
    """Push-Subscription entfernen."""
    data = request.get_json()
    if not data or not data.get("endpoint"):
        return jsonify({"error": "Endpoint erforderlich"}), 400
    remove_push_subscription(data["endpoint"])
    return jsonify({"ok": True})
