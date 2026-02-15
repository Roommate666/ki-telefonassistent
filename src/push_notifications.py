"""
Web Push Notifications fuer das Versicherungsberater-Dashboard.
Sendet Push-Benachrichtigungen an PWA-Installationen bei neuen Anrufen.
"""

import json
import logging
import os

from src.booking_database import get_db

logger = logging.getLogger(__name__)

VAPID_CLAIMS = {"sub": "mailto:noreply@assistentpro.de"}


def _get_vapid_keys():
    """Lazy-Load VAPID Keys (werden erst nach load_config() verfuegbar)."""
    return (
        os.environ.get("VAPID_PRIVATE_KEY", ""),
        os.environ.get("VAPID_PUBLIC_KEY", ""),
    )


def init_push_tables():
    """Erstellt die Push-Subscriptions Tabelle."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_id INTEGER NOT NULL,
            endpoint TEXT UNIQUE NOT NULL,
            subscription_json TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_push_business ON push_subscriptions(business_id)"
    )
    conn.commit()
    conn.close()


def save_push_subscription(business_id, subscription):
    """Speichert eine Push-Subscription."""
    conn = get_db()
    endpoint = subscription.get("endpoint", "")
    sub_json = json.dumps(subscription)
    try:
        conn.execute(
            """INSERT INTO push_subscriptions (business_id, endpoint, subscription_json)
               VALUES (?, ?, ?)
               ON CONFLICT(endpoint) DO UPDATE SET subscription_json = ?, business_id = ?""",
            (business_id, endpoint, sub_json, sub_json, business_id),
        )
        conn.commit()
        logger.info(f"Push-Subscription gespeichert fuer Betrieb {business_id}")
    except Exception as e:
        logger.error(f"Push-Subscription speichern fehlgeschlagen: {e}")
    conn.close()


def remove_push_subscription(endpoint):
    """Entfernt eine Push-Subscription."""
    conn = get_db()
    conn.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
    conn.commit()
    conn.close()


def get_push_subscriptions(business_id):
    """Holt alle Push-Subscriptions fuer einen Betrieb."""
    conn = get_db()
    rows = conn.execute(
        "SELECT subscription_json FROM push_subscriptions WHERE business_id = ?",
        (business_id,),
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        try:
            result.append(json.loads(row["subscription_json"]))
        except (json.JSONDecodeError, KeyError):
            pass
    return result


def send_push_to_business(business_id, title, body, url=None):
    """Sendet Push-Benachrichtigung an alle Abonnenten eines Betriebs."""
    vapid_private, _ = _get_vapid_keys()
    if not vapid_private:
        logger.debug("Keine VAPID-Keys konfiguriert - Push uebersprungen")
        return

    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush nicht installiert - Push nicht verfuegbar")
        return

    subscriptions = get_push_subscriptions(business_id)
    if not subscriptions:
        return

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url or "/dashboard",
    })

    sent = 0
    for sub in subscriptions:
        try:
            webpush(
                subscription_info=sub,
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims=VAPID_CLAIMS,
            )
            sent += 1
        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                remove_push_subscription(sub.get("endpoint", ""))
                logger.info("Abgelaufene Push-Subscription entfernt")
            else:
                logger.error(f"Push fehlgeschlagen: {e}")
        except Exception as e:
            logger.error(f"Push Fehler: {e}")

    if sent:
        logger.info(f"Push gesendet: {sent}/{len(subscriptions)} fuer Betrieb {business_id}")
