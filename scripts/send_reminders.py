#!/usr/bin/env python3
"""
Erinnerungs-SMS Cron-Job.
Sendet automatisch Erinnerungen an Kunden 24h vor bestaetigten Terminen.

Einrichtung als Cron-Job (taeglich um 18:00 ausfuehren):
    crontab -e
    0 18 * * * /opt/ki-telefonassistent/venv/bin/python /opt/ki-telefonassistent/scripts/send_reminders.py

Warum 18 Uhr? Die meisten Termine sind am naechsten Tag.
Die Abfrage sucht Termine deren confirmed_date = morgen ist.
"""

import sys
import logging

sys.path.insert(0, "/opt/ki-telefonassistent")

from src.booking_database import init_booking_tables, get_upcoming_reminders, mark_reminder_sent
from src.customer_notifications import get_customer_notifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("/opt/ki-telefonassistent/logs/reminders.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("send_reminders")


def main():
    init_booking_tables()
    notifier = get_customer_notifier()

    reminders = get_upcoming_reminders(hours_ahead=24)
    logger.info(f"{len(reminders)} Erinnerung(en) zu senden")

    sent = 0
    failed = 0

    for appointment in reminders:
        try:
            success = notifier.send_appointment_reminder(appointment)
            if success:
                mark_reminder_sent(appointment["id"])
                sent += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"Fehler bei Termin {appointment['id']}: {e}")
            failed += 1

    logger.info(f"Fertig: {sent} gesendet, {failed} fehlgeschlagen")


if __name__ == "__main__":
    main()
