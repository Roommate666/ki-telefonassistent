"""
Konfigurations-Loader für den KI-Telefonassistenten.
Lädt .env und Branchen-Konfigurationen.
"""

import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BASE_DIR = Path(os.environ.get("KI_BASE_DIR", "/opt/ki-telefonassistent"))
CONFIG_DIR = BASE_DIR / "config"
PROMPTS_DIR = BASE_DIR / "prompts"


def load_config():
    """Lädt die .env Konfiguration."""
    env_path = CONFIG_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        logger.warning(f".env nicht gefunden: {env_path}")
        load_dotenv()

    return {
        # SIP
        "sip_provider": os.getenv("SIP_PROVIDER", "sipgate"),
        "sip_username": os.getenv("SIP_USERNAME", ""),
        "sip_password": os.getenv("SIP_PASSWORD", ""),
        "sip_host": os.getenv("SIP_HOST", "sipconnect.sipgate.de"),
        "sip_port": int(os.getenv("SIP_PORT", "5060")),
        # sipgate Personal Access Token (fuer SMS)
        "sipgate_token_id": os.getenv("SIPGATE_TOKEN_ID", ""),
        "sipgate_token": os.getenv("SIPGATE_TOKEN", ""),
        # LLM-Provider
        "llm_provider": os.getenv("LLM_PROVIDER", "groq"),
        # Groq
        "groq_api_key": os.getenv("GROQ_API_KEY", ""),
        "groq_model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        # OpenAI
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        # Gemini
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        # Anthropic
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "anthropic_model": os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-20250414"),
        # Ollama (lokal)
        "ollama_host": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        "ollama_model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        # Piper TTS
        "piper_path": os.getenv("PIPER_PATH", "/opt/piper/piper"),
        "piper_voice": os.getenv("PIPER_VOICE", "/opt/piper/voices/de_DE-thorsten-high.onnx"),
        # Whisper STT
        "whisper_model": os.getenv("WHISPER_MODEL", "small"),
        "whisper_language": os.getenv("WHISPER_LANGUAGE", "de"),
        "whisper_device": os.getenv("WHISPER_DEVICE", "cpu"),
        # Allgemein
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "recordings_dir": os.getenv("RECORDINGS_DIR", str(BASE_DIR / "recordings")),
        "audio_dir": os.getenv("AUDIO_DIR", str(BASE_DIR / "audio")),
        "max_call_duration": int(os.getenv("MAX_CALL_DURATION", "300")),
        "silence_timeout": int(os.getenv("SILENCE_TIMEOUT", "5")),
        "greeting_delay": float(os.getenv("GREETING_DELAY", "1")),
        # Web
        "web_host": os.getenv("WEB_HOST", "0.0.0.0"),
        "web_port": int(os.getenv("WEB_PORT", "5000")),
        "web_secret_key": os.getenv("WEB_SECRET_KEY") or os.urandom(24).hex(),
        "web_debug": os.getenv("WEB_DEBUG", "").lower() in ("1", "true", "yes"),
        "admin_password": os.getenv("ADMIN_PASSWORD", ""),
        "web_base_url": os.getenv("WEB_BASE_URL", ""),
        # Branche
        "active_business": os.getenv("ACTIVE_BUSINESS", "handwerk"),
        # Booking-System: ID des Betriebs in der businesses-Tabelle
        "booking_business_id": int(os.getenv("BOOKING_BUSINESS_ID", "0")) or None,
        # E-Mail Benachrichtigung
        "email_enabled": os.getenv("EMAIL_ENABLED", "false").lower() == "true",
        "email_smtp_host": os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com"),
        "email_smtp_port": os.getenv("EMAIL_SMTP_PORT", "587"),
        "email_smtp_user": os.getenv("EMAIL_SMTP_USER", ""),
        "email_smtp_pass": os.getenv("EMAIL_SMTP_PASS", ""),
        "email_from": os.getenv("EMAIL_FROM", ""),
        "email_to": os.getenv("EMAIL_TO", ""),
        # Telegram Benachrichtigung
        "telegram_enabled": os.getenv("TELEGRAM_ENABLED", "false").lower() == "true",
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        # ElevenLabs Cloud TTS (optional, Fallback auf Piper)
        "elevenlabs_api_key": os.getenv("ELEVENLABS_API_KEY", ""),
        "elevenlabs_voice_id": os.getenv("ELEVENLABS_VOICE_ID", ""),
    }


def load_business_config(business_name=None):
    """
    Lädt die Branchen-Konfiguration.
    Sucht in prompts/{business_name}.json
    """
    if business_name is None:
        config = load_config()
        business_name = config["active_business"]

    business_file = PROMPTS_DIR / f"{business_name}.json"

    if not business_file.exists():
        logger.error(f"Branchen-Konfiguration nicht gefunden: {business_file}")
        logger.info(f"Verfügbare Branchen: {list_available_businesses()}")
        raise FileNotFoundError(f"Branche '{business_name}' nicht gefunden")

    with open(business_file, "r", encoding="utf-8") as f:
        business_config = json.load(f)

    logger.info(f"Branchen-Konfiguration geladen: {business_name}")
    return business_config


def list_available_businesses():
    """Listet alle verfügbaren Branchen-Konfigurationen auf."""
    if not PROMPTS_DIR.exists():
        return []
    return [f.stem for f in PROMPTS_DIR.glob("*.json")]


def build_system_prompt(business_config):
    """
    Baut den System-Prompt aus der Branchen-Konfiguration zusammen.
    """
    biz = business_config

    prompt = f"""Du bist ein freundlicher und professioneller KI-Telefonassistent für folgendes Unternehmen:

UNTERNEHMEN: {biz.get('company_name', 'Firma')}
BRANCHE: {biz.get('industry', 'Allgemein')}
ADRESSE: {biz.get('address', 'Nicht angegeben')}
TELEFON: {biz.get('phone', 'Nicht angegeben')}
EMAIL: {biz.get('email', 'Nicht angegeben')}

ÖFFNUNGSZEITEN:
{_format_hours(biz.get('opening_hours', {}))}

DIENSTLEISTUNGEN:
{_format_list(biz.get('services', []))}

WICHTIGE INFORMATIONEN:
{_format_list(biz.get('important_info', []))}

VERHALTENSREGELN:
{_format_list(biz.get('behavior_rules', []))}

HÄUFIGE FRAGEN UND ANTWORTEN:
{_format_faq(biz.get('faq', []))}

KERNREGEL - ANTWORTLAENGE:
Deine Antworten werden am Telefon vorgelesen. Sei EXTREM kurz!
MAXIMAL 1 kurzer Satz. Nie mehr als 12 Woerter.
Antworte NUR auf Deutsch. Keine Floskeln, keine Emojis.

GESPRAECHSABLAUF - Strikt befolgen:

Schritt 1: Anliegen verstehen
- Hoere zu was der Anrufer will
- Wenn unklar, frage kurz nach: "Was genau ist das Problem?"

Schritt 2: Name erfragen
- "Wie ist Ihr Name bitte?"
- WARTE auf Antwort, dann BESTAETIGEN: "Herr [Name], richtig?"
- Wenn falsch, nochmal fragen

Schritt 3: Adresse erfragen
- "Wie ist Ihre Adresse?"
- WARTE auf Antwort
- Das System validiert die Adresse automatisch mit einer Datenbank
- Wenn im Kontext [SYSTEM: Die genannte Adresse wurde validiert als: X] steht, nutze DIESE Adresse
- BESTAETIGEN: "Also [validierte Adresse], korrekt?"
- Wenn falsch, nochmal fragen

Schritt 4: Termin erfragen
- "Wann passt es Ihnen?"
- WARTE auf Antwort

Schritt 5: Alles zusammenfassen
- Wiederhole ALLES: "[Name], [Adresse], [Problem], [Termin]. Stimmt das?"
- WARTE auf "Ja" vom Anrufer

Schritt 6: Extra-Wuensche erfragen
- "Moechten Sie noch etwas hinzufuegen?"
- WARTE auf Antwort
- Wenn ja: notieren und kurz bestaetigen
- Wenn nein oder "das wars": weiter zu Schritt 7

Schritt 7: Abschliessen
- "Alles klar, ist notiert. Wir melden uns bei Ihnen. Schoenen Tag noch!"

ABSOLUTE REGELN:
- IMMER nur EINE Frage pro Antwort
- IMMER Daten bestaetigen bevor du weitergehst
- NIEMALS zwei Fragen kombinieren
- NIEMALS erfundene Daten annehmen
- NIEMALS verwirrendes Zeug sagen
- Wenn du etwas nicht verstehst: "Koennten Sie das bitte wiederholen?"
- Telefonnummer NICHT erfragen (haben wir schon)
"""

    # Branchenspezifische Zusatz-Anweisungen
    if "custom_instructions" in biz:
        prompt += f"\nZUSÄTZLICHE ANWEISUNGEN:\n{biz['custom_instructions']}\n"

    return prompt


def _format_hours(hours):
    """Formatiert Öffnungszeiten."""
    if not hours:
        return "Nicht angegeben"
    lines = []
    for day, time in hours.items():
        lines.append(f"  {day}: {time}")
    return "\n".join(lines)


def _format_list(items):
    """Formatiert eine Liste."""
    if not items:
        return "  Keine angegeben"
    return "\n".join(f"  - {item}" for item in items)


def _format_faq(faq_list):
    """Formatiert FAQ."""
    if not faq_list:
        return "  Keine angegeben"
    lines = []
    for faq in faq_list:
        lines.append(f"  F: {faq.get('question', '')}")
        lines.append(f"  A: {faq.get('answer', '')}")
        lines.append("")
    return "\n".join(lines)
