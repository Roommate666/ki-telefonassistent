#!/usr/bin/env python3
"""
Asterisk AGI Handler - Das Herzstück des KI-Telefonassistenten.
Wird von Asterisk bei jedem eingehenden Anruf aufgerufen.

Ablauf:
1. Anruf entgegennehmen
2. Begrüßung abspielen
3. Schleife: Zuhören → Verstehen → Antworten
4. Zusammenfassung erstellen und speichern
"""

import sys
import os
import signal
import time
import logging
import tempfile
import subprocess
from pathlib import Path

# Pfad zum Projekt hinzufügen
sys.path.insert(0, "/opt/ki-telefonassistent")

from src.config_loader import load_config, load_business_config, build_system_prompt
from src.stt_engine import init_stt, transcribe
from src.llm_engine import create_llm_engine
from src.tts_engine import TTSEngine, create_tts_engine
from src.call_database import (
    init_database, start_call, end_call,
    save_message, save_caller_info, get_call_history,
)
from src.notifications import NotificationManager
from src.booking_database import (
    init_booking_tables,
    create_appointment,
    create_inquiry,
    get_business_by_id,
    guess_business_mode,
    set_call_summary,
    get_or_create_customer_token,
)
from src.address_validator import validate_address, validate_address_with_retry, format_address_for_speech
from src.customer_notifications import get_customer_notifier

# Logging einrichten
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("/opt/ki-telefonassistent/logs/agi.log"),
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("agi_handler")


class AsteriskAGI:
    """Minimaler AGI-Handler für Asterisk."""

    def __init__(self):
        self.env = {}
        self._read_env()

    def _read_env(self):
        """Liest AGI-Umgebungsvariablen von stdin."""
        while True:
            line = sys.stdin.readline().strip()
            if not line:
                break
            if ":" in line:
                key, value = line.split(":", 1)
                self.env[key.strip()] = value.strip()

    def execute(self, command):
        """Sendet einen AGI-Befehl und gibt das Ergebnis zurück."""
        sys.stdout.write(f"{command}\n")
        sys.stdout.flush()
        result = sys.stdin.readline().strip()
        return result

    def answer(self):
        """Anruf entgegennehmen."""
        return self.execute("ANSWER")

    def hangup(self):
        """Auflegen."""
        return self.execute("HANGUP")

    def stream_file(self, filename, escape_digits=""):
        """Audio-Datei abspielen."""
        return self.execute(f'STREAM FILE "{filename}" "{escape_digits}"')

    def record_file(self, filename, format="wav", escape_digits="#",
                    timeout=10000, silence=2):
        """Audio aufnehmen (ohne BEEP fuer natuerlicheren Gespraechsfluss)."""
        return self.execute(
            f'RECORD FILE "{filename}" "{format}" "{escape_digits}" '
            f'"{timeout}" 0 s={silence}'
        )

    def set_variable(self, name, value):
        """Asterisk-Variable setzen."""
        return self.execute(f'SET VARIABLE {name} "{value}"')

    def get_variable(self, name):
        """Asterisk-Variable lesen."""
        result = self.execute(f"GET VARIABLE {name}")
        if "(" in result and ")" in result:
            return result.split("(")[1].split(")")[0]
        return ""

    def set_music(self, on=True, music_class="default"):
        """Music on Hold starten/stoppen (non-blocking)."""
        if on:
            return self.execute(f'SET MUSIC ON {music_class}')
        else:
            return self.execute('SET MUSIC OFF')

    def verbose(self, message, level=1):
        """Log-Nachricht an Asterisk."""
        return self.execute(f'VERBOSE "{message}" {level}')


def run_conversation(agi, call_id, caller_number, config, business_config):
    """
    Führt die Konversation mit dem Anrufer.
    """
    system_prompt = build_system_prompt(business_config)
    conversation = []
    max_turns = 20  # Maximale Gesprächsrunden
    audio_dir = Path(config["audio_dir"])
    audio_dir.mkdir(parents=True, exist_ok=True)

    # TTS-Engine ZUERST initialisieren (ElevenLabs oder Piper) - gleiche Stimme fuer alles
    tts = create_tts_engine(config)

    # Begrüßung generieren
    greeting = business_config.get(
        "greeting",
        f"Guten Tag, Sie sind verbunden mit {business_config.get('company_name', 'uns')}. "
        "Wie kann ich Ihnen helfen?"
    )

    # Begrüßung mit der konfigurierten TTS-Engine erzeugen (einheitliche Stimme!)
    logger.info("Erzeuge Begrüßung mit TTS...")
    greeting_audio = audio_dir / f"{call_id}_greeting"
    greeting_wav = str(greeting_audio) + ".wav"
    audio_file = tts.synthesize_to_asterisk_format(greeting, greeting_wav)
    if audio_file:
        result = agi.stream_file(str(greeting_audio))
        logger.info(f"stream_file Result: {result}")
        save_message(call_id, "assistant", greeting)
        conversation.append({"role": "assistant", "content": greeting})
    else:
        logger.error("Begrüßung konnte nicht erzeugt werden")
        return

    # STT erst NACH der Begruessung laden (dauert ~3s, Anrufer hoert inzwischen die Begruessung)
    logger.info("Lade Whisper STT...")
    init_stt(
        model_size=config["whisper_model"],
        device=config["whisper_device"],
        language=config["whisper_language"],
    )
    logger.info("Whisper STT bereit.")

    # LLM initialisieren (nutzt den in .env konfigurierten Provider)
    llm = create_llm_engine(config)

    # Gesprächsschleife
    for turn in range(max_turns):
        logger.info(f"Gesprächsrunde {turn + 1}/{max_turns}")

        # --- Zuhören ---
        record_path = audio_dir / f"{call_id}_turn{turn}"
        agi.record_file(
            str(record_path),
            format="wav",
            escape_digits="#",
            timeout=config["max_call_duration"] * 1000,
            silence=config["silence_timeout"],
        )

        record_wav = Path(str(record_path) + ".wav")
        if not record_wav.exists():
            logger.warning("Keine Aufnahme erhalten - Anrufer hat aufgelegt?")
            break

        # Prüfe ob die Aufnahme Audio enthält
        file_size = record_wav.stat().st_size
        if file_size < 1000:  # Sehr kleine Datei = wahrscheinlich Stille
            logger.info("Leere Aufnahme - Anrufer schweigt oder hat aufgelegt")
            # Nachfragen
            if turn > 0:
                break
            else:
                followup = "Hallo? Sind Sie noch dran? Wie kann ich Ihnen helfen?"
                followup_audio = audio_dir / f"{call_id}_followup{turn}"
                audio_file = tts.synthesize_to_asterisk_format(
                    followup, str(followup_audio) + ".wav"
                )
                if audio_file:
                    agi.stream_file(str(followup_audio))
                continue

        # Wartemusik SOFORT starten (waehrend STT + LLM + TTS arbeiten)
        agi.set_music(on=True, music_class="default")
        logger.info("Wartemusik gestartet")

        # --- Verstehen (Speech-to-Text) ---
        stt_result = transcribe(str(record_wav), config["whisper_language"])
        user_text = stt_result["text"].strip()

        if not user_text:
            logger.info("Kein Text erkannt")
            continue

        logger.info(f"Anrufer sagt: {user_text}")
        save_message(call_id, "user", user_text)
        conversation.append({"role": "user", "content": user_text})

        # Prüfe ob Anrufer auflegen will
        goodbye_phrases = [
            "tschüss", "auf wiedersehen", "danke tschüss",
            "bye", "wiederhören", "das war's", "das wars",
            "ich leg auf", "ich lege auf",
        ]
        if any(phrase in user_text.lower() for phrase in goodbye_phrases):
            farewell = "Auf Wiederhören! Ich wünsche Ihnen einen schönen Tag."
            farewell_audio = audio_dir / f"{call_id}_farewell"
            audio_file = tts.synthesize_to_asterisk_format(
                farewell, str(farewell_audio) + ".wav"
            )
            if audio_file:
                agi.stream_file(str(farewell_audio))
            save_message(call_id, "assistant", farewell)
            break

        # --- Antworten (LLM) ---
        # HINWEIS: Adressvalidierung deaktiviert - führte zu falschen Ergebnissen
        llm_result = llm.generate_response(system_prompt, conversation[:-1], user_text)
        response_text = llm_result["response"]

        logger.info(f"KI antwortet: {response_text}")
        save_message(call_id, "assistant", response_text)
        conversation.append({"role": "assistant", "content": response_text})

        # Prüfe ob KI das Gespräch beendet hat
        ki_goodbye_phrases = [
            "auf wiederhören", "auf wiederhoeren", "wiederhören",
            "wiederhoeren", "einen schönen tag", "schoenen tag",
        ]
        ki_ends_call = any(phrase in response_text.lower() for phrase in ki_goodbye_phrases)

        # Audio erzeugen
        response_audio = audio_dir / f"{call_id}_response{turn}"
        audio_file = tts.synthesize_to_asterisk_format(
            response_text, str(response_audio) + ".wav"
        )

        # Wartemusik stoppen und Antwort abspielen
        agi.set_music(on=False)

        if audio_file:
            # Barge-in: Anrufer kann mit beliebiger Taste unterbrechen (aber nicht bei Verabschiedung)
            if ki_ends_call:
                # Bei Verabschiedung: komplett abspielen ohne Unterbrechung
                agi.stream_file(str(response_audio))
                logger.info("KI hat sich verabschiedet - Anruf wird beendet")
                break
            else:
                result = agi.stream_file(str(response_audio), escape_digits="0123456789#*")
                if result and "digit=" in result:
                    # Anrufer hat unterbrochen - weiter zur naechsten Aufnahme
                    logger.info(f"Anrufer hat Wiedergabe unterbrochen: {result}")
        else:
            logger.error(f"TTS fehlgeschlagen für Runde {turn}")
            break

    # --- Zusammenfassung ---
    full_conversation = "\n".join(
        f"{'Anrufer' if m['role'] == 'user' else 'Assistent'}: {m['content']}"
        for m in conversation
    )
    caller_info = llm.extract_caller_info(full_conversation)
    save_caller_info(call_id, caller_info)

    # --- Booking-System: Termin/Anfrage automatisch anlegen ---
    booking_business_id = config.get("booking_business_id")
    if booking_business_id:
        try:
            booking_data = llm.extract_booking_data(full_conversation)

            if booking_data.get("has_booking_request"):
                business_mode = guess_business_mode(config["active_business"])
                booking_type = booking_data.get("booking_type") or business_mode

                customer_name = (
                    booking_data.get("customer_name")
                    or caller_info.get("name")
                    or "Unbekannt"
                )

                # Zusammenfassung fuer Dashboard
                summary = caller_info.get("concern", "")

                if booking_type == "termin":
                    # party_size in notes integrieren (bei Gastronomie)
                    raw_notes = booking_data.get("notes") or booking_data.get("concern") or ""
                    party_size = booking_data.get("party_size")
                    if party_size:
                        raw_notes = f"Personenanzahl: {party_size} | {raw_notes}".rstrip(" |")

                    apt_id = create_appointment(
                        booking_business_id,
                        customer_name,
                        caller_number,
                        call_id=call_id,
                        preferred_staff=booking_data.get("preferred_staff"),
                        service_name_free=booking_data.get("service_name"),
                        requested_date=booking_data.get("requested_date"),
                        requested_time=booking_data.get("requested_time"),
                        notes=raw_notes or None,
                    )
                    if summary:
                        set_call_summary("termin", apt_id, summary)
                    logger.info(
                        f"Termin aus Anruf erstellt: Appointment ID {apt_id} "
                        f"fuer Betrieb {booking_business_id}"
                    )

                    # Kunden-Token generieren (fuer Portal-Link in SMS)
                    try:
                        if caller_number and caller_number != "unbekannt":
                            get_or_create_customer_token(booking_business_id, caller_number)
                    except Exception as token_err:
                        logger.warning(f"Kunden-Token Erstellung fehlgeschlagen: {token_err}")

                    # SMS-Bestaetigung an Kunden senden
                    try:
                        from src.booking_database import get_appointment, detect_phone_type
                        apt_data = get_appointment(apt_id, booking_business_id)
                        if apt_data:
                            customer_notifier = get_customer_notifier()
                            customer_notifier.notify_call_received(
                                apt_data, booking_business_id, "termin"
                            )
                    except Exception as sms_err:
                        logger.warning(f"SMS-Bestaetigung fehlgeschlagen: {sms_err}")

                else:
                    # IVR-Kategorie als Fallback verwenden
                    ivr_kat = config.get("ivr_kategorie")
                    category_map = {"heizung": "Heizung/Wärmepumpe", "sanitaer": "Sanitär/Wasser", "sonstiges": "Sonstiges"}
                    category = booking_data.get("category") or category_map.get(ivr_kat, "")

                    inq_id = create_inquiry(
                        booking_business_id,
                        customer_name,
                        caller_number,
                        booking_data.get("description")
                        or booking_data.get("concern")
                        or "Aus Telefonanruf",
                        call_id=call_id,
                        customer_address=booking_data.get("customer_address"),
                        category=category,
                        urgency=booking_data.get("urgency", "normal"),
                    )
                    if summary:
                        set_call_summary("auftrag", inq_id, summary)
                    logger.info(
                        f"Anfrage aus Anruf erstellt: Inquiry ID {inq_id} "
                        f"fuer Betrieb {booking_business_id}"
                    )

                    # Kunden-Token generieren (fuer Portal-Link in SMS)
                    try:
                        if caller_number and caller_number != "unbekannt":
                            get_or_create_customer_token(booking_business_id, caller_number)
                    except Exception as token_err:
                        logger.warning(f"Kunden-Token Erstellung fehlgeschlagen: {token_err}")

                    # SMS-Bestaetigung an Kunden senden
                    try:
                        from src.booking_database import get_inquiry
                        inq_data = get_inquiry(inq_id, booking_business_id)
                        if inq_data:
                            customer_notifier = get_customer_notifier()
                            customer_notifier.notify_call_received(
                                inq_data, booking_business_id, "auftrag"
                            )
                    except Exception as sms_err:
                        logger.warning(f"SMS-Bestaetigung fehlgeschlagen: {sms_err}")
            else:
                logger.info(
                    "Kein Termin-/Auftragswunsch erkannt - "
                    "kein Booking-Eintrag erstellt"
                )
        except Exception as e:
            logger.error(f"Booking-Eintrag konnte nicht erstellt werden: {e}")
    else:
        logger.debug("Kein BOOKING_BUSINESS_ID konfiguriert - Booking uebersprungen")

    # --- Benachrichtigung senden ---
    try:
        notifier = NotificationManager(config)
        call_data = {
            "call_id": call_id,
            "caller_number": caller_number,
            "duration_seconds": len(conversation) * 15,  # Grobe Schätzung
        }
        notifier.notify_new_call(caller_info, call_data)
    except Exception as e:
        logger.warning(f"Benachrichtigung fehlgeschlagen: {e}")

    # Temporäre Audio-Dateien aufräumen
    for tmp_file in audio_dir.glob(f"{call_id}_*"):
        try:
            tmp_file.unlink()
        except OSError:
            pass

    logger.info(
        f"Anruf {call_id} beendet. "
        f"Anliegen: {caller_info.get('concern', 'Unbekannt')}"
    )


def main():
    """Haupteinstiegspunkt - wird von Asterisk aufgerufen."""
    # SIGHUP ignorieren damit Asterisk den Prozess nicht killt bei Hangup
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        # AGI initialisieren
        agi = AsteriskAGI()

        # Parameter von Asterisk lesen
        call_id = sys.argv[1] if len(sys.argv) > 1 else f"call_{int(time.time())}"
        caller_number = sys.argv[2] if len(sys.argv) > 2 else "unbekannt"
        kategorie = sys.argv[3] if len(sys.argv) > 3 else None  # IVR-Kategorie

        logger.info(f"=== Neuer Anruf: {call_id} von {caller_number} (Kategorie: {kategorie or 'keine'}) ===")
        agi.verbose(f"KI-Assistent: Anruf {call_id} von {caller_number} Kat:{kategorie}")

        # Konfiguration laden
        config = load_config()
        business_config = load_business_config()

        # Kategorie-spezifische Anpassungen
        if kategorie:
            config["ivr_kategorie"] = kategorie
            # Kategorie-spezifische Begrüßung
            kategorie_greetings = {
                "heizung": f"Willkommen im Bereich Heizung und Wärmepumpe bei {business_config.get('company_name', 'uns')}. Wie kann ich Ihnen helfen?",
                "sanitaer": f"Willkommen im Bereich Sanitär und Wasserinstallation bei {business_config.get('company_name', 'uns')}. Was kann ich für Sie tun?",
                "sonstiges": f"Willkommen bei {business_config.get('company_name', 'uns')}. Wie kann ich Ihnen helfen?",
            }
            if kategorie in kategorie_greetings:
                business_config["greeting"] = kategorie_greetings[kategorie]

        # Datenbank initialisieren
        init_database()
        init_booking_tables()

        # Anruf in DB registrieren
        start_call(call_id, caller_number, config["active_business"])

        # WICHTIG: STT wird NICHT hier geladen, sondern erst in run_conversation()
        # nach der Begruessung, damit der Anrufer sofort etwas hoert statt 3-5s zu warten.

        # Konversation führen
        run_conversation(agi, call_id, caller_number, config, business_config)

        # Anruf beenden
        recording_path = config["recordings_dir"] + f"/{call_id}.wav"
        end_call(call_id, recording_path)

        agi.hangup()

    except Exception as e:
        logger.exception(f"Fehler im AGI-Handler: {e}")
        try:
            agi.hangup()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
