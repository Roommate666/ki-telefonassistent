"""
REST-API fuer das Termin- und Anfragen-Management.
Betriebe authentifizieren sich per Access-Token (URL-Parameter oder Header).
"""

import logging
from functools import wraps
from flask import Blueprint, request, jsonify

from src.customer_notifications import get_customer_notifier
from src.booking_database import (
    get_business_by_token,
    get_business_stats,
    # Services
    create_service,
    get_services,
    update_service,
    delete_service,
    # Appointments
    create_appointment,
    get_appointments,
    get_appointment,
    update_appointment_status,
    # Inquiries
    create_inquiry,
    get_inquiries,
    get_inquiry,
    update_inquiry_status,
    # Business
    update_business,
    # Neue Funktionen
    update_business_notes,
    mark_callback_done,
    search_items,
    find_duplicates,
)

logger = logging.getLogger(__name__)

booking_api = Blueprint("booking_api", __name__, url_prefix="/api/booking")


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
# Dashboard / Uebersicht
# ============================================================

@booking_api.route("/dashboard", methods=["GET"])
@require_business
def api_dashboard(business):
    """Gibt die Dashboard-Daten fuer einen Betrieb zurueck."""
    stats = get_business_stats(business["id"])
    return jsonify({
        "business": {
            "id": business["id"],
            "name": business["name"],
            "business_type": business["business_type"],
            "mode": business.get("mode", "termin"),
        },
        "stats": stats,
    })


# ============================================================
# Betrieb bearbeiten
# ============================================================

@booking_api.route("/business", methods=["GET"])
@require_business
def api_get_business(business):
    """Gibt Betriebsdaten zurueck."""
    safe = {k: v for k, v in business.items() if k != "access_token"}
    return jsonify(safe)


@booking_api.route("/business", methods=["PUT"])
@require_business
def api_update_business(business):
    """Aktualisiert Betriebsdaten."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Keine Daten"}), 400

    update_business(business["id"], **data)
    return jsonify({"ok": True})


# ============================================================
# Dienstleistungen / Angebote
# ============================================================

@booking_api.route("/services", methods=["GET"])
@require_business
def api_list_services(business):
    """Listet alle Dienstleistungen eines Betriebs."""
    services = get_services(business["id"])
    return jsonify(services)


@booking_api.route("/services", methods=["POST"])
@require_business
def api_create_service(business):
    """Erstellt eine neue Dienstleistung."""
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Name ist erforderlich"}), 400

    service_id = create_service(
        business["id"],
        data["name"],
        description=data.get("description"),
        duration_minutes=data.get("duration_minutes", 30),
        price_cents=data.get("price_cents"),
    )
    return jsonify({"id": service_id}), 201


@booking_api.route("/services/<int:service_id>", methods=["PUT"])
@require_business
def api_update_service(service_id, business):
    """Aktualisiert eine Dienstleistung."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Keine Daten"}), 400

    update_service(service_id, business["id"], **data)
    return jsonify({"ok": True})


@booking_api.route("/services/<int:service_id>", methods=["DELETE"])
@require_business
def api_delete_service(service_id, business):
    """Loescht eine Dienstleistung (soft-delete)."""
    delete_service(service_id, business["id"])
    return jsonify({"ok": True})


# ============================================================
# Termine
# ============================================================

@booking_api.route("/appointments", methods=["GET"])
@require_business
def api_list_appointments(business):
    """Listet Termine eines Betriebs."""
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)
    appointments = get_appointments(business["id"], status=status, limit=limit)
    return jsonify(appointments)


@booking_api.route("/appointments", methods=["POST"])
@require_business
def api_create_appointment(business):
    """
    Erstellt einen neuen Termin manuell (z.B. Walk-in, Telefon-Notiz).
    Sendet optional SMS-Bestaetigung an den Kunden.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Keine Daten"}), 400

    customer_name = data.get("customer_name")
    customer_phone = data.get("customer_phone")

    if not customer_name or not customer_phone:
        return jsonify({"error": "Name und Telefonnummer sind erforderlich"}), 400

    appointment_id = create_appointment(
        business["id"],
        customer_name,
        customer_phone,
        customer_email=data.get("customer_email"),
        preferred_staff=data.get("preferred_staff"),
        service_id=data.get("service_id"),
        service_name_free=data.get("service_name_free"),
        requested_date=data.get("requested_date"),
        requested_time=data.get("requested_time"),
        notes=data.get("notes"),
    )

    # SMS-Bestaetigung senden wenn gewuenscht
    send_sms = data.get("send_sms", True)
    sms_sent = False
    if send_sms:
        try:
            appt = get_appointment(appointment_id, business["id"])
            if appt and appt.get("phone_type") == "mobil":
                get_customer_notifier().notify_call_received(
                    appt, business["id"], "termin"
                )
                sms_sent = True
                logger.info(f"SMS nach manueller Terminbuchung gesendet: {appointment_id}")
        except Exception as e:
            logger.warning(f"SMS nach Terminbuchung fehlgeschlagen: {e}")

    return jsonify({
        "id": appointment_id,
        "sms_sent": sms_sent,
    }), 201


@booking_api.route("/appointments/<int:appointment_id>", methods=["GET"])
@require_business
def api_get_appointment(appointment_id, business):
    """Holt einen einzelnen Termin."""
    appointment = get_appointment(appointment_id, business["id"])
    if not appointment:
        return jsonify({"error": "Termin nicht gefunden"}), 404
    return jsonify(appointment)


@booking_api.route("/appointments/<int:appointment_id>/confirm", methods=["POST"])
@require_business
def api_confirm_appointment(appointment_id, business):
    """Bestaetigt einen Termin."""
    data = request.get_json() or {}
    update_appointment_status(
        appointment_id,
        business["id"],
        "bestaetigt",
        confirmed_date=data.get("confirmed_date"),
        confirmed_time=data.get("confirmed_time"),
    )
    # Kunden benachrichtigen
    appt = get_appointment(appointment_id, business["id"])
    if appt:
        try:
            get_customer_notifier().notify_appointment_confirmed(appt, business["id"])
        except Exception as e:
            logger.error(f"Kundenbenachrichtigung fehlgeschlagen: {e}")
    return jsonify({"ok": True, "status": "bestaetigt"})


@booking_api.route("/appointments/<int:appointment_id>/reject", methods=["POST"])
@require_business
def api_reject_appointment(appointment_id, business):
    """Lehnt einen Termin ab."""
    data = request.get_json() or {}
    update_appointment_status(
        appointment_id,
        business["id"],
        "abgelehnt",
        rejection_reason=data.get("reason"),
    )
    appt = get_appointment(appointment_id, business["id"])
    if appt:
        try:
            get_customer_notifier().notify_appointment_rejected(appt, business["id"])
        except Exception as e:
            logger.error(f"Kundenbenachrichtigung fehlgeschlagen: {e}")
    return jsonify({"ok": True, "status": "abgelehnt"})


@booking_api.route("/appointments/<int:appointment_id>/reschedule", methods=["POST"])
@require_business
def api_reschedule_appointment(appointment_id, business):
    """Verschiebt einen Termin auf neues Datum/Uhrzeit."""
    data = request.get_json()
    if not data or not data.get("confirmed_date"):
        return jsonify({"error": "Neues Datum erforderlich"}), 400

    update_appointment_status(
        appointment_id,
        business["id"],
        "verschoben",
        confirmed_date=data["confirmed_date"],
        confirmed_time=data.get("confirmed_time"),
    )
    appt = get_appointment(appointment_id, business["id"])
    if appt:
        try:
            get_customer_notifier().notify_appointment_rescheduled(appt, business["id"])
        except Exception as e:
            logger.error(f"Kundenbenachrichtigung fehlgeschlagen: {e}")
    return jsonify({"ok": True, "status": "verschoben"})


# ============================================================
# Anfragen (fuer Handwerker etc.)
# ============================================================

@booking_api.route("/inquiries", methods=["GET"])
@require_business
def api_list_inquiries(business):
    """Listet Anfragen eines Betriebs."""
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)
    inquiries = get_inquiries(business["id"], status=status, limit=limit)
    return jsonify(inquiries)


@booking_api.route("/inquiries", methods=["POST"])
@require_business
def api_create_inquiry(business):
    """
    Erstellt eine neue Anfrage manuell.
    Sendet optional SMS-Bestaetigung an den Kunden.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Keine Daten"}), 400

    customer_name = data.get("customer_name")
    customer_phone = data.get("customer_phone")
    description = data.get("description", "Manuelle Anfrage")

    if not customer_name or not customer_phone:
        return jsonify({"error": "Name und Telefonnummer sind erforderlich"}), 400

    inquiry_id = create_inquiry(
        business["id"],
        customer_name,
        customer_phone,
        description,
        customer_email=data.get("customer_email"),
        customer_address=data.get("customer_address"),
        category=data.get("category"),
        urgency=data.get("urgency", "normal"),
    )

    # SMS-Bestaetigung senden wenn gewuenscht
    send_sms = data.get("send_sms", True)
    sms_sent = False
    if send_sms:
        try:
            inq = get_inquiry(inquiry_id, business["id"])
            if inq and inq.get("phone_type") == "mobil":
                get_customer_notifier().notify_call_received(
                    inq, business["id"], "auftrag"
                )
                sms_sent = True
                logger.info(f"SMS nach manueller Anfrage gesendet: {inquiry_id}")
        except Exception as e:
            logger.warning(f"SMS nach Anfrage fehlgeschlagen: {e}")

    return jsonify({
        "id": inquiry_id,
        "sms_sent": sms_sent,
    }), 201


@booking_api.route("/inquiries/<int:inquiry_id>/respond", methods=["POST"])
@require_business
def api_respond_inquiry(inquiry_id, business):
    """Betrieb reagiert auf eine Anfrage."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Keine Daten"}), 400

    update_inquiry_status(
        inquiry_id,
        business["id"],
        data.get("status", "in_bearbeitung"),
        response_text=data.get("response_text"),
        estimated_cost=data.get("estimated_cost"),
        scheduled_date=data.get("scheduled_date"),
    )
    # Kunden ueber Antwort informieren
    from src.booking_database import get_inquiries
    inqs = get_inquiries(business["id"])
    inq = next((i for i in inqs if i["id"] == inquiry_id), None)
    if inq:
        try:
            get_customer_notifier().notify_inquiry_response(inq, business["id"])
        except Exception as e:
            logger.error(f"Kundenbenachrichtigung fehlgeschlagen: {e}")
    return jsonify({"ok": True})


# ============================================================
# Notizen (Business Notes)
# ============================================================

@booking_api.route("/notes/<item_type>/<int:item_id>", methods=["PUT"])
@require_business
def api_update_notes(item_type, item_id, business):
    """Speichert Betriebsnotizen fuer einen Termin oder eine Anfrage."""
    if item_type not in ("termin", "auftrag"):
        return jsonify({"error": "Ungueltiger Typ"}), 400

    data = request.get_json()
    if data is None:
        return jsonify({"error": "Keine Daten"}), 400

    update_business_notes(item_type, item_id, business["id"], data.get("notes", ""))
    return jsonify({"ok": True})


# ============================================================
# Rueckruf-Tracking
# ============================================================

@booking_api.route("/callback/<item_type>/<int:item_id>", methods=["POST"])
@require_business
def api_mark_callback(item_type, item_id, business):
    """Markiert einen Rueckruf als erledigt."""
    if item_type not in ("termin", "auftrag"):
        return jsonify({"error": "Ungueltiger Typ"}), 400

    mark_callback_done(item_type, item_id, business["id"])
    return jsonify({"ok": True})


# ============================================================
# Suche
# ============================================================

@booking_api.route("/search", methods=["GET"])
@require_business
def api_search(business):
    """Sucht Termine/Anfragen nach Name, Telefon, Datum."""
    query = request.args.get("q", "").strip()
    if not query or len(query) < 2:
        return jsonify({"error": "Suchbegriff zu kurz (min. 2 Zeichen)"}), 400

    mode = business.get("mode", "termin")
    results = search_items(business["id"], mode, query)
    return jsonify(results)


# ============================================================
# Duplikat-Erkennung
# ============================================================

@booking_api.route("/duplicates", methods=["GET"])
@require_business
def api_check_duplicates(business):
    """Prueft ob fuer eine Telefonnummer bereits aktive Eintraege existieren."""
    phone = request.args.get("phone", "").strip()
    if not phone:
        return jsonify([])

    mode = business.get("mode", "termin")
    exclude_id = request.args.get("exclude_id", type=int)
    dupes = find_duplicates(business["id"], phone, mode, exclude_id=exclude_id)
    return jsonify(dupes)
