"""
Kunden-Benachrichtigungen nach Terminbestaetigung/-ablehnung.
Primaerer Kanal: SMS an die Telefonnummer (kommt automatisch ueber Caller-ID).
E-Mail nur als optionaler Zusatzkanal (wenn vom Betrieb manuell eingetragen).
SMS-Versand ueber sipgate API.
"""

import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from src.config_loader import load_config
from src.booking_database import get_business_by_id, get_or_create_customer_token

logger = logging.getLogger(__name__)


class CustomerNotifier:
    """Benachrichtigt Kunden ueber Terminstatus-Aenderungen."""

    def __init__(self):
        self.config = load_config()
        self.web_base_url = self.config.get("web_base_url", "").rstrip("/")

    def _get_portal_link(self, business_id, customer_phone):
        """Erstellt den Portal-Link fuer den Kunden."""
        if not self.web_base_url or not customer_phone:
            return ""
        try:
            token = get_or_create_customer_token(business_id, customer_phone)
            return f"\nIhre Reservierungen: {self.web_base_url}/kunde?t={token}"
        except Exception as e:
            logger.warning(f"Portal-Link konnte nicht erstellt werden: {e}")
            return ""

    def notify_appointment_confirmed(self, appointment, business_id):
        """Benachrichtigt den Kunden ueber einen bestaetigten Termin."""
        business = get_business_by_id(business_id)
        if not business:
            logger.error(f"Betrieb {business_id} nicht gefunden")
            return

        date = appointment.get("confirmed_date") or appointment.get("requested_date") or "wird noch bekanntgegeben"
        time = appointment.get("confirmed_time") or appointment.get("requested_time") or ""
        datetime_str = f"{date} {time}".strip()

        portal_link = self._get_portal_link(business_id, appointment.get("customer_phone"))
        message = (
            f"Guten Tag {appointment.get('customer_name', '')}! "
            f"Ihr Termin bei {business['name']} wurde bestaetigt. "
            f"Datum/Uhrzeit: {datetime_str}. "
            f"Bei Fragen erreichen Sie uns unter {business.get('phone', '')}. "
            f"Wir freuen uns auf Sie!"
            f"{portal_link}"
        )

        self._send_to_customer(appointment, business, "Terminbestaetigung", message)

    def notify_appointment_rejected(self, appointment, business_id):
        """Benachrichtigt den Kunden ueber einen abgelehnten Termin."""
        business = get_business_by_id(business_id)
        if not business:
            return

        reason = appointment.get("rejection_reason", "")
        reason_text = f" Grund: {reason}" if reason else ""
        portal_link = self._get_portal_link(business_id, appointment.get("customer_phone"))

        message = (
            f"Guten Tag {appointment.get('customer_name', '')}. "
            f"Leider koennen wir Ihren Terminwunsch bei {business['name']} nicht wahrnehmen.{reason_text} "
            f"Bitte kontaktieren Sie uns fuer einen alternativen Termin unter {business.get('phone', '')}."
            f"{portal_link}"
        )

        self._send_to_customer(appointment, business, "Termin - Absage", message)

    def notify_appointment_rescheduled(self, appointment, business_id):
        """Benachrichtigt den Kunden ueber einen verschobenen Termin."""
        business = get_business_by_id(business_id)
        if not business:
            return

        date = appointment.get("confirmed_date", "")
        time = appointment.get("confirmed_time", "")
        datetime_str = f"{date} {time}".strip()
        portal_link = self._get_portal_link(business_id, appointment.get("customer_phone"))

        message = (
            f"Guten Tag {appointment.get('customer_name', '')}! "
            f"Ihr Termin bei {business['name']} wurde verschoben auf: {datetime_str}. "
            f"Falls der neue Termin nicht passt, melden Sie sich bitte unter {business.get('phone', '')}."
            f"{portal_link}"
        )

        self._send_to_customer(appointment, business, "Termin verschoben", message)

    def notify_inquiry_response(self, inquiry, business_id):
        """Benachrichtigt den Kunden ueber eine Antwort auf seine Anfrage."""
        business = get_business_by_id(business_id)
        if not business:
            return

        parts = [
            f"Guten Tag {inquiry.get('customer_name', '')}! ",
            f"{business['name']} hat auf Ihre Anfrage reagiert.",
        ]
        if inquiry.get("response_text"):
            parts.append(f" Nachricht: {inquiry['response_text']}")
        if inquiry.get("estimated_cost"):
            parts.append(f" Geschaetzte Kosten: {inquiry['estimated_cost']}.")
        if inquiry.get("scheduled_date"):
            parts.append(f" Geplanter Termin: {inquiry['scheduled_date']}.")

        parts.append(f" Kontakt: {business.get('phone', '')}")

        message = "".join(parts)
        self._send_to_customer(inquiry, business, "Antwort auf Ihre Anfrage", message)

    def notify_call_received(self, data, business_id, booking_type="termin"):
        """
        Sendet sofort nach dem Anruf eine Bestaetigungs-SMS an den Kunden.
        Gibt dem Kunden Sicherheit, dass sein Anliegen aufgenommen wurde.
        Nur bei Mobilnummern moeglich.
        """
        business = get_business_by_id(business_id)
        if not business:
            logger.error(f"Betrieb {business_id} nicht gefunden")
            return False

        customer_phone = data.get("customer_phone")
        phone_type = data.get("phone_type", "mobil")
        customer_name = data.get("customer_name", "")

        # Nur SMS bei Mobilnummern
        if not customer_phone or phone_type != "mobil":
            logger.info(f"Keine SMS moeglich: phone_type={phone_type}")
            return False

        # Personalisierte Anrede
        anrede = f"Guten Tag {customer_name}! " if customer_name and customer_name != "Unbekannt" else "Guten Tag! "
        portal_link = self._get_portal_link(business_id, customer_phone)

        if booking_type == "termin":
            message = (
                f"{anrede}"
                f"Vielen Dank fuer Ihren Anruf bei {business['name']}. "
                f"Ihre Terminanfrage wurde aufgenommen. "
                f"Wir melden uns in Kuerze bei Ihnen mit einer Bestaetigung. "
                f"Bei Fragen: {business.get('phone', '')}"
                f"{portal_link}"
            )
        else:
            message = (
                f"{anrede}"
                f"Vielen Dank fuer Ihren Anruf bei {business['name']}. "
                f"Ihre Anfrage wurde aufgenommen und wird bearbeitet. "
                f"Wir melden uns zeitnah bei Ihnen. "
                f"Bei Fragen: {business.get('phone', '')}"
                f"{portal_link}"
            )

        try:
            self._send_sms(customer_phone, message)
            logger.info(f"Anruf-Bestaetigungs-SMS gesendet an {customer_phone}")
            return True
        except Exception as e:
            logger.error(f"Anruf-Bestaetigungs-SMS fehlgeschlagen: {e}")
            return False

    def send_appointment_reminder(self, appointment):
        """Sendet eine Erinnerungs-SMS 24h vor dem Termin."""
        date = appointment.get("confirmed_date", "")
        time = appointment.get("confirmed_time", "")
        datetime_str = f"{date} um {time}" if time else date

        message = (
            f"Erinnerung: Ihr Termin bei {appointment.get('business_name', '')} "
            f"ist morgen ({datetime_str}). "
            f"Falls Sie absagen muessen, melden Sie sich bitte unter "
            f"{appointment.get('business_phone', '')}."
        )

        customer_phone = appointment.get("customer_phone")
        if customer_phone and appointment.get("phone_type") == "mobil":
            try:
                self._send_sms(customer_phone, message)
                logger.info(f"Erinnerungs-SMS gesendet an {customer_phone}")
                return True
            except Exception as e:
                logger.error(f"Erinnerungs-SMS fehlgeschlagen: {e}")
                return False
        return False

    def send_business_notification(self, business, message):
        """Sendet eine SMS an den Betrieb (z.B. bei Stornierung/Aenderung durch Kunden)."""
        business_phone = business.get("phone")
        if not business_phone:
            logger.warning(f"Betrieb {business.get('name')} hat keine Telefonnummer")
            return False
        try:
            self._send_sms(business_phone, message)
            logger.info(f"Betriebs-SMS gesendet an {business_phone}")
            return True
        except Exception as e:
            logger.error(f"Betriebs-SMS fehlgeschlagen: {e}")
            return False

    def notify_customer_cancellation(self, appointment, business):
        """Bestaetigungs-SMS an Kunden bei Stornierung."""
        customer_phone = appointment.get("customer_phone")
        if not customer_phone or appointment.get("phone_type") != "mobil":
            return False
        portal_link = self._get_portal_link(business["id"], customer_phone)
        message = (
            f"Ihre Reservierung bei {business['name']} "
            f"am {appointment.get('requested_date', '?')} um {appointment.get('requested_time', '?')} "
            f"wurde storniert. "
            f"Bei Fragen: {business.get('phone', '')}"
            f"{portal_link}"
        )
        try:
            self._send_sms(customer_phone, message)
            logger.info(f"Stornierungs-SMS an Kunden gesendet: {customer_phone}")
            return True
        except Exception as e:
            logger.error(f"Stornierungs-SMS fehlgeschlagen: {e}")
            return False

    def notify_customer_reschedule_request(self, appointment, business):
        """Bestaetigungs-SMS an Kunden bei Aenderungswunsch."""
        customer_phone = appointment.get("customer_phone")
        if not customer_phone or appointment.get("phone_type") != "mobil":
            return False
        portal_link = self._get_portal_link(business["id"], customer_phone)
        message = (
            f"Ihr Aenderungswunsch fuer die Reservierung bei {business['name']} "
            f"wurde uebermittelt. Wir melden uns in Kuerze bei Ihnen. "
            f"Bei Fragen: {business.get('phone', '')}"
            f"{portal_link}"
        )
        try:
            self._send_sms(customer_phone, message)
            logger.info(f"Aenderungs-SMS an Kunden gesendet: {customer_phone}")
            return True
        except Exception as e:
            logger.error(f"Aenderungs-SMS fehlgeschlagen: {e}")
            return False

    def _send_to_customer(self, data, business, subject, message):
        """
        Sendet die Benachrichtigung an den Kunden.
        - Mobilnummer: SMS senden
        - Festnetz: KEINE SMS moeglich -> Betrieb muss selber zurueckrufen
        - E-Mail: Nur wenn vom Betrieb manuell eingetragen
        """
        customer_phone = data.get("customer_phone")
        customer_email = data.get("customer_email")
        phone_type = data.get("phone_type", "mobil")
        sent = False

        # SMS nur bei Mobilnummern
        if customer_phone and phone_type == "mobil":
            try:
                self._send_sms(customer_phone, message)
                logger.info(f"Kunden-SMS gesendet an {customer_phone}")
                sent = True
            except Exception as e:
                logger.error(f"Kunden-SMS fehlgeschlagen: {e}")
        elif customer_phone and phone_type == "festnetz":
            logger.info(
                f"Festnetz-Nummer {customer_phone} - keine SMS moeglich. "
                f"Betrieb '{business['name']}' muss Kunden selber zurueckrufen."
            )

        # E-Mail nur als Zusatz wenn vorhanden (wird nicht am Telefon abgefragt)
        if customer_email:
            try:
                self._send_email(customer_email, subject, message, business)
                logger.info(f"Kunden-E-Mail gesendet an {customer_email}")
                sent = True
            except Exception as e:
                logger.error(f"Kunden-E-Mail fehlgeschlagen: {e}")

        if not sent and phone_type != "festnetz":
            logger.warning("Keine Benachrichtigung gesendet - weder Telefon noch E-Mail vorhanden")

    def _send_email(self, to_email, subject, message, business):
        """Sendet eine E-Mail an den Kunden."""
        smtp_host = self.config.get("email_smtp_host")
        smtp_port = int(self.config.get("email_smtp_port", "587"))
        smtp_user = self.config.get("email_smtp_user")
        smtp_pass = self.config.get("email_smtp_pass")
        from_addr = self.config.get("email_from") or smtp_user

        if not smtp_user or not smtp_pass:
            logger.warning("E-Mail nicht konfiguriert - ueberspringe")
            return

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{business['name']} <{from_addr}>"
        msg["To"] = to_email
        msg["Subject"] = f"{subject} - {business['name']}"

        # Plaintext
        msg.attach(MIMEText(message, "plain", "utf-8"))

        # HTML
        html = f"""
        <html><body style="font-family:-apple-system,Arial,sans-serif;background:#f5f5f5;padding:20px;">
        <div style="max-width:500px;margin:0 auto;background:white;border-radius:12px;padding:25px;
                    box-shadow:0 2px 10px rgba(0,0,0,0.1);">
            <h2 style="color:#1a1a2e;border-bottom:2px solid #3b82f6;padding-bottom:10px;">
                {business['name']}
            </h2>
            <p style="font-size:15px;line-height:1.6;color:#333;">{message}</p>
            <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
            <p style="font-size:12px;color:#999;">
                Diese Nachricht wurde automatisch versendet.
                {business.get('phone', '')} | {business.get('email', '')}
            </p>
        </div>
        </body></html>
        """
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

    def _send_sms(self, phone_number, message):
        """
        Sendet eine SMS ueber sipgate API.
        Erfordert sipgate Webex (Token-basierte Auth) oder Basic Auth.
        """
        sip_provider = self.config.get("sip_provider", "")

        if sip_provider == "sipgate":
            self._send_sms_sipgate(phone_number, message)
        else:
            logger.warning(f"SMS-Versand fuer Provider '{sip_provider}' nicht implementiert")

    def _send_sms_sipgate(self, phone_number, message):
        """SMS ueber sipgate REST API senden."""
        # Personal Access Token hat Vorrang (empfohlen)
        token_id = self.config.get("sipgate_token_id")
        token = self.config.get("sipgate_token")

        if token_id and token:
            # Personal Access Token Auth
            username = token_id
            password = token
            logger.debug("Verwende sipgate Personal Access Token")
        else:
            # Fallback auf SIP credentials (funktioniert nicht fuer SMS!)
            username = self.config.get("sip_username")
            password = self.config.get("sip_password")

        if not username or not password:
            logger.warning("sipgate Zugangsdaten fehlen - SMS uebersprungen")
            return

        # sipgate SMS API
        resp = requests.post(
            "https://api.sipgate.com/v2/sessions/sms",
            json={
                "smsId": "s0",
                "recipient": phone_number,
                "message": message,
            },
            auth=(username, password),
            timeout=10,
        )

        if resp.status_code == 204:
            logger.info(f"sipgate SMS gesendet an {phone_number}")
        else:
            logger.error(f"sipgate SMS Fehler {resp.status_code}: {resp.text}")
            raise RuntimeError(f"SMS-Versand fehlgeschlagen: {resp.status_code}")


# Singleton
_notifier = None

def get_customer_notifier():
    """Gibt die CustomerNotifier-Instanz zurueck."""
    global _notifier
    if _notifier is None:
        _notifier = CustomerNotifier()
    return _notifier
