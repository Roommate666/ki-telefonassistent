"""
Kunden-REST-API fuer das Kunden-Portal.
Erlaubt Kunden ihre Reservierungen einzusehen, zu stornieren und Aenderungen anzufragen.
Auth per Token-Parameter (?t=TOKEN).
"""

import logging
from flask import Blueprint, jsonify, request

from src.booking_database import (
    get_customer_by_token,
    get_customer_appointments,
    customer_cancel_appointment,
    customer_request_reschedule,
    get_appointment,
    get_business_by_id,
)

logger = logging.getLogger(__name__)

customer_api = Blueprint("customer_api", __name__)


def _get_customer():
    """Authentifiziert den Kunden anhand des Tokens."""
    token = request.args.get("t")
    if not token:
        return None
    return get_customer_by_token(token)


@customer_api.route("/api/kunde/reservierungen")
def api_customer_reservations():
    """Gibt alle Reservierungen des Kunden zurueck."""
    customer = _get_customer()
    if not customer:
        return jsonify({"error": "Ungültiger oder fehlender Token"}), 401

    appointments = get_customer_appointments(
        customer["business_id"], customer["customer_phone"]
    )

    # Sensible Daten entfernen
    safe_appointments = []
    for apt in appointments:
        safe_appointments.append({
            "id": apt["id"],
            "service_name": apt.get("service_name") or apt.get("service_name_free") or "Reservierung",
            "requested_date": apt.get("requested_date"),
            "requested_time": apt.get("requested_time"),
            "confirmed_date": apt.get("confirmed_date"),
            "confirmed_time": apt.get("confirmed_time"),
            "status": apt.get("status"),
            "notes": apt.get("notes"),
            "customer_name": apt.get("customer_name"),
            "created_at": apt.get("created_at"),
        })

    return jsonify({
        "business_name": customer["business_name"],
        "business_phone": customer.get("business_phone", ""),
        "reservierungen": safe_appointments,
    })


@customer_api.route("/api/kunde/reservierungen/<int:apt_id>/stornieren", methods=["POST"])
def api_customer_cancel(apt_id):
    """Storniert eine Reservierung."""
    customer = _get_customer()
    if not customer:
        return jsonify({"error": "Ungültiger oder fehlender Token"}), 401

    success = customer_cancel_appointment(
        apt_id, customer["business_id"], customer["customer_phone"]
    )

    if not success:
        return jsonify({"error": "Stornierung nicht möglich"}), 400

    # SMS an Betrieb senden
    try:
        from src.customer_notifications import get_customer_notifier
        notifier = get_customer_notifier()
        business = get_business_by_id(customer["business_id"])
        apt_data = get_appointment(apt_id, customer["business_id"])
        if business and apt_data:
            notifier.notify_customer_cancellation(apt_data, business)
            notifier.send_business_notification(
                business,
                f"Stornierung: {apt_data.get('customer_name', 'Kunde')} hat den Termin "
                f"am {apt_data.get('requested_date', '?')} um {apt_data.get('requested_time', '?')} storniert.",
            )
    except Exception as e:
        logger.warning(f"SMS-Benachrichtigung bei Stornierung fehlgeschlagen: {e}")

    return jsonify({"success": True, "message": "Reservierung wurde storniert"})


@customer_api.route("/api/kunde/reservierungen/<int:apt_id>/aendern", methods=["POST"])
def api_customer_reschedule(apt_id):
    """Speichert einen Aenderungswunsch."""
    customer = _get_customer()
    if not customer:
        return jsonify({"error": "Ungültiger oder fehlender Token"}), 401

    data = request.get_json(silent=True) or {}
    new_date = data.get("new_date")
    new_time = data.get("new_time")

    if not new_date or not new_time:
        return jsonify({"error": "Datum und Uhrzeit erforderlich"}), 400

    success = customer_request_reschedule(
        apt_id, customer["business_id"], customer["customer_phone"],
        new_date, new_time,
    )

    if not success:
        return jsonify({"error": "Änderung nicht möglich"}), 400

    # SMS an Betrieb und Kunden senden
    try:
        from src.customer_notifications import get_customer_notifier
        notifier = get_customer_notifier()
        business = get_business_by_id(customer["business_id"])
        apt_data = get_appointment(apt_id, customer["business_id"])
        if business and apt_data:
            notifier.notify_customer_reschedule_request(apt_data, business)
            notifier.send_business_notification(
                business,
                f"Aenderungswunsch: {apt_data.get('customer_name', 'Kunde')} moechte den Termin "
                f"am {apt_data.get('requested_date', '?')} verschieben auf {new_date} um {new_time}.",
            )
    except Exception as e:
        logger.warning(f"SMS-Benachrichtigung bei Aenderung fehlgeschlagen: {e}")

    return jsonify({"success": True, "message": "Änderungswunsch wurde übermittelt"})
