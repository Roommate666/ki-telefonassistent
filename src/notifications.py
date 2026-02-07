"""
Benachrichtigungssystem für den KI-Telefonassistenten.
Sendet Anruf-Zusammenfassungen per E-Mail und/oder Telegram.
"""

import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger(__name__)


class NotificationManager:
    """Verwaltet alle Benachrichtigungskanäle."""

    def __init__(self, config):
        self.config = config
        self.channels = []

        # E-Mail aktivieren?
        if config.get("email_enabled") and config.get("email_to"):
            self.channels.append(EmailNotifier(config))
            logger.info("[OK] E-Mail-Benachrichtigungen aktiviert")

        # Telegram aktivieren?
        if config.get("telegram_enabled") and config.get("telegram_bot_token"):
            self.channels.append(TelegramNotifier(config))
            logger.info("[OK] Telegram-Benachrichtigungen aktiviert")

        if not self.channels:
            logger.warning(
                "Keine Benachrichtigungskanäle konfiguriert. "
                "Anruf-Infos sind nur im Dashboard sichtbar."
            )

    def notify_new_call(self, caller_info, call_data):
        """
        Benachrichtigt über einen neuen Anruf.

        Args:
            caller_info: Dict mit name, phone, concern, urgency, etc.
            call_data: Dict mit call_id, caller_number, duration, etc.
        """
        message = self._format_message(caller_info, call_data)
        subject = self._format_subject(caller_info)

        for channel in self.channels:
            try:
                channel.send(subject, message)
            except Exception as e:
                logger.error(f"Benachrichtigung fehlgeschlagen ({channel.name}): {e}")

    def _format_subject(self, caller_info):
        """Erstellt den Betreff / Titel."""
        urgency = caller_info.get("urgency", "mittel")
        urgency_icon = {"hoch": "🔴", "mittel": "🟡", "niedrig": "🟢"}.get(urgency, "⚪")
        concern = caller_info.get("concern", "Neuer Anruf")

        if caller_info.get("callback_requested"):
            return f"{urgency_icon} RÜCKRUF ERBETEN: {concern}"
        return f"{urgency_icon} Neuer Anruf: {concern}"

    def _format_message(self, caller_info, call_data):
        """Erstellt die Nachricht."""
        now = datetime.now().strftime("%d.%m.%Y um %H:%M Uhr")

        name = caller_info.get("name") or "Nicht genannt"
        phone = caller_info.get("phone") or call_data.get("caller_number", "Unbekannt")
        concern = caller_info.get("concern") or "Nicht erkannt"
        urgency = caller_info.get("urgency", "mittel")
        callback = "JA" if caller_info.get("callback_requested") else "Nein"
        appointment = "JA" if caller_info.get("appointment_requested") else "Nein"
        preferred_time = caller_info.get("preferred_time") or "-"
        duration = call_data.get("duration_seconds", 0)

        urgency_text = {
            "hoch": "🔴 HOCH - Bitte schnell reagieren!",
            "mittel": "🟡 Mittel",
            "niedrig": "🟢 Niedrig",
        }.get(urgency, "Unbekannt")

        message = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  NEUER ANRUF - {now}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 Name:           {name}
📞 Telefon:        {phone}
📋 Anliegen:       {concern}
⚡ Dringlichkeit:  {urgency_text}
📞 Rückruf:        {callback}
📅 Termin:         {appointment}
🕐 Wunschtermin:   {preferred_time}
⏱️ Gesprächsdauer: {duration} Sekunden

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        if caller_info.get("callback_requested"):
            message += f"""
⚠️ AKTION ERFORDERLICH:
   Bitte {name} unter {phone} zurückrufen!
"""
        return message.strip()


# ============================================================
# E-Mail Benachrichtigung
# ============================================================
class EmailNotifier:
    """Sendet Benachrichtigungen per E-Mail (SMTP)."""

    name = "E-Mail"

    def __init__(self, config):
        self.smtp_host = config.get("email_smtp_host", "smtp.gmail.com")
        self.smtp_port = int(config.get("email_smtp_port", "587"))
        self.smtp_user = config.get("email_smtp_user", "")
        self.smtp_pass = config.get("email_smtp_pass", "")
        self.from_addr = config.get("email_from", self.smtp_user)
        self.to_addrs = [
            addr.strip()
            for addr in config.get("email_to", "").split(",")
            if addr.strip()
        ]

    def send(self, subject, message):
        """Sendet eine E-Mail."""
        if not self.to_addrs:
            logger.warning("Keine E-Mail-Empfänger konfiguriert")
            return

        msg = MIMEMultipart()
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(self.to_addrs)
        msg["Subject"] = subject

        # HTML-Version (schöner formatiert)
        html_body = self._text_to_html(message)
        msg.attach(MIMEText(message, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)

            logger.info(f"E-Mail gesendet an: {', '.join(self.to_addrs)}")
        except smtplib.SMTPException as e:
            logger.error(f"E-Mail-Versand fehlgeschlagen: {e}")
            raise

    def _text_to_html(self, text):
        """Wandelt die Text-Nachricht in HTML um."""
        # Einfache Konvertierung
        html_text = text.replace("\n", "<br>")
        html_text = html_text.replace("━", "─")

        return f"""
        <html>
        <body style="font-family: -apple-system, Arial, sans-serif;
                     background: #f5f5f5; padding: 20px;">
            <div style="max-width: 500px; margin: 0 auto; background: white;
                        border-radius: 12px; padding: 25px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h2 style="color: #1a1a2e; border-bottom: 2px solid #e94560;
                           padding-bottom: 10px;">
                    KI-Telefonassistent
                </h2>
                <pre style="font-family: -apple-system, Arial, sans-serif;
                            font-size: 14px; line-height: 1.8; color: #333;">
{text}
                </pre>
            </div>
        </body>
        </html>
        """


# ============================================================
# Telegram Benachrichtigung
# ============================================================
class TelegramNotifier:
    """Sendet Benachrichtigungen per Telegram Bot."""

    name = "Telegram"

    def __init__(self, config):
        self.bot_token = config.get("telegram_bot_token", "")
        self.chat_ids = [
            cid.strip()
            for cid in config.get("telegram_chat_id", "").split(",")
            if cid.strip()
        ]
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send(self, subject, message):
        """Sendet eine Telegram-Nachricht."""
        if not self.chat_ids:
            logger.warning("Keine Telegram Chat-ID konfiguriert")
            return

        # Telegram-formatierte Nachricht
        telegram_text = f"*{subject}*\n\n{message}"

        for chat_id in self.chat_ids:
            try:
                resp = requests.post(
                    f"{self.api_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": telegram_text,
                        "parse_mode": "Markdown",
                    },
                    timeout=10,
                )
                resp.raise_for_status()
                logger.info(f"Telegram gesendet an Chat: {chat_id}")
            except requests.RequestException as e:
                logger.error(f"Telegram-Fehler für Chat {chat_id}: {e}")
                raise

    def get_chat_id_helper(self):
        """
        Hilfsfunktion: Zeigt die Chat-ID an.
        Nutzer muss zuerst dem Bot eine Nachricht schicken,
        dann diese Funktion aufrufen.
        """
        try:
            resp = requests.get(f"{self.api_url}/getUpdates", timeout=10)
            resp.raise_for_status()
            updates = resp.json().get("result", [])

            chat_ids = set()
            for update in updates:
                msg = update.get("message", {})
                chat = msg.get("chat", {})
                if chat.get("id"):
                    chat_ids.add(
                        (chat["id"], chat.get("first_name", ""), chat.get("username", ""))
                    )

            if chat_ids:
                print("\nGefundene Chats:")
                for cid, name, username in chat_ids:
                    print(f"  Chat-ID: {cid}  ({name} @{username})")
                print("\nTrage die Chat-ID in die .env Datei ein:")
                print(f"  TELEGRAM_CHAT_ID={','.join(str(c[0]) for c in chat_ids)}")
            else:
                print("\nKeine Chats gefunden.")
                print("Bitte sende zuerst eine Nachricht an deinen Bot")
                print("und rufe dann diese Funktion erneut auf.")

            return list(chat_ids)
        except requests.RequestException as e:
            print(f"Fehler: {e}")
            return []
