#!/usr/bin/env python3
"""
KI-Telefonassistent - Haupteinstiegspunkt.
Startet alle Dienste und initialisiert das System.
"""

import sys
import logging
import signal
import time
from pathlib import Path

# Pfad zum Projekt
sys.path.insert(0, "/opt/ki-telefonassistent")

from src.config_loader import load_config, load_business_config
from src.stt_engine import init_stt
from src.llm_engine import create_llm_engine
from src.tts_engine import TTSEngine
from src.call_database import init_database


def setup_logging(level="INFO"):
    """Logging einrichten."""
    log_dir = Path("/opt/ki-telefonassistent/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "main.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("main")


def verify_system(config, logger):
    """Prüft ob alle Komponenten verfügbar sind."""
    checks = []

    # 1. Piper TTS
    piper_path = Path(config["piper_path"])
    voice_path = Path(config["piper_voice"])
    if piper_path.exists() and voice_path.exists():
        logger.info("[OK] Piper TTS gefunden")
        checks.append(True)
    else:
        logger.error("[FEHLER] Piper TTS nicht gefunden")
        if not piper_path.exists():
            logger.error(f"  Piper Binary: {piper_path}")
        if not voice_path.exists():
            logger.error(f"  Stimme: {voice_path}")
        checks.append(False)

    # 2. LLM-Provider
    try:
        llm = create_llm_engine(config)
        provider = config["llm_provider"]
        logger.info(f"[OK] LLM-Provider: {provider}")
        checks.append(True)
    except Exception as e:
        logger.error(f"[FEHLER] LLM-Provider ({config['llm_provider']}): {e}")
        checks.append(False)

    # 3. Whisper
    try:
        init_stt(
            model_size=config["whisper_model"],
            device=config["whisper_device"],
            language=config["whisper_language"],
        )
        logger.info(f"[OK] Whisper STT geladen (Modell: {config['whisper_model']})")
        checks.append(True)
    except Exception as e:
        logger.error(f"[FEHLER] Whisper STT: {e}")
        checks.append(False)

    # 4. Branchen-Konfiguration
    try:
        biz = load_business_config()
        logger.info(f"[OK] Branche: {biz.get('company_name')} ({config['active_business']})")
        checks.append(True)
    except Exception as e:
        logger.error(f"[FEHLER] Branchen-Konfiguration: {e}")
        checks.append(False)

    # 5. Datenbank
    try:
        init_database()
        logger.info("[OK] Datenbank initialisiert")
        checks.append(True)
    except Exception as e:
        logger.error(f"[FEHLER] Datenbank: {e}")
        checks.append(False)

    # 6. Verzeichnisse
    for dir_name in ["recordings_dir", "audio_dir"]:
        dir_path = Path(config[dir_name])
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"[OK] Verzeichnis: {dir_path}")

    return all(checks)


def main():
    """Startet den KI-Telefonassistenten."""
    config = load_config()
    logger = setup_logging(config["log_level"])

    logger.info("=" * 60)
    logger.info("  KI-Telefonassistent wird gestartet...")
    logger.info("=" * 60)

    # Systemprüfung
    logger.info("Systemprüfung...")
    if not verify_system(config, logger):
        logger.error(
            "Systemprüfung fehlgeschlagen! "
            "Bitte die obigen Fehler beheben und erneut starten."
        )
        sys.exit(1)

    logger.info("")
    logger.info("=" * 60)
    logger.info("  System bereit! Warte auf eingehende Anrufe...")
    logger.info(f"  Branche: {config['active_business']}")
    logger.info(f"  Dashboard: http://localhost:{config['web_port']}")
    logger.info("=" * 60)

    # Signal-Handler für sauberes Beenden
    def signal_handler(sig, frame):
        logger.info("Beende KI-Telefonassistenten...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Hauptschleife - wartet auf Asterisk AGI-Aufrufe
    # (Die eigentliche Arbeit passiert im agi_handler.py,
    #  der von Asterisk bei jedem Anruf gestartet wird)
    try:
        while True:
            time.sleep(60)
            # Periodische Health-Checks könnten hier laufen
    except KeyboardInterrupt:
        logger.info("Beendet durch Benutzer.")


if __name__ == "__main__":
    main()
