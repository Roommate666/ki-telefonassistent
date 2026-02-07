"""
Text-to-Speech Engine mit Piper TTS und ElevenLabs Cloud TTS.
Wandelt Text in natuerlich klingende deutsche Sprache um.
Speziell fuer den Einsatz im Asterisk AGI-Kontext optimiert:
Subprozesse werden mit subprocess.Popen + start_new_session + close_fds
gestartet, damit sie komplett isoliert von AGIs stdin/stdout sind.
"""

import logging
import os
import struct
import subprocess
import tempfile
import time
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)


def _run_isolated(cmd_args, stdin_file_path=None, timeout=30):
    """
    Fuehrt einen Befehl komplett isoliert vom AGI-Kontext aus.

    Das Kernproblem: Im AGI-Kontext sind stdin/stdout mit Asterisk verbunden.
    Wenn ein Child-Prozess diese FDs erbt, kann er haengen weil er
    auf der AGI-Pipe liest/schreibt statt auf echtem stdin/stdout.

    Loesung: Alle 3 stdio FDs explizit auf Datei oder /dev/null setzen.
    start_new_session=True erstellt eine neue Prozessgruppe.
    close_fds=True schliesst alle geerbten FDs.
    KEIN subprocess.PIPE verwenden - das kann blocken wenn der
    Parent-Prozess (AGI) gekillt wird bevor die Pipe gelesen wird.
    """
    devnull_r = None
    devnull_w1 = None
    devnull_w2 = None
    stdin_fd = None
    try:
        # /dev/null oeffnen - separate Handles fuer stdout und stderr
        devnull_w1 = open(os.devnull, "w")
        devnull_w2 = open(os.devnull, "w")

        # stdin: entweder aus Datei oder /dev/null
        if stdin_file_path:
            stdin_fd = open(stdin_file_path, "r")
        else:
            devnull_r = open(os.devnull, "r")
            stdin_fd = devnull_r

        proc = subprocess.Popen(
            cmd_args,
            stdin=stdin_fd,
            stdout=devnull_w1,
            stderr=devnull_w2,
            close_fds=True,
            start_new_session=True,
        )

        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return -1, "Timeout"

        return proc.returncode, ""

    finally:
        if stdin_file_path and stdin_fd:
            stdin_fd.close()
        if devnull_r:
            devnull_r.close()
        if devnull_w1:
            devnull_w1.close()
        if devnull_w2:
            devnull_w2.close()


class TTSEngine:
    def __init__(self, piper_path="/opt/piper/piper",
                 voice_path="/opt/piper/voices/de_DE-thorsten-high.onnx"):
        self.piper_path = piper_path
        self.voice_path = voice_path
        self._verify_installation()

    def _verify_installation(self):
        """Prueft ob Piper installiert ist."""
        if not Path(self.piper_path).exists():
            raise FileNotFoundError(
                f"Piper nicht gefunden: {self.piper_path}. "
                "Bitte install.sh ausfuehren."
            )
        if not Path(self.voice_path).exists():
            raise FileNotFoundError(
                f"Piper-Stimme nicht gefunden: {self.voice_path}. "
                "Bitte install.sh ausfuehren."
            )
        logger.info(f"Piper TTS bereit. Stimme: {Path(self.voice_path).stem}")

    def synthesize(self, text, output_path=None):
        """
        Wandelt Text in Sprache um.

        Args:
            text: Der zu sprechende Text
            output_path: Pfad fuer die Ausgabedatei (optional, sonst temp)

        Returns:
            Pfad zur erzeugten WAV-Datei
        """
        if not text or not text.strip():
            logger.warning("Leerer Text fuer TTS uebergeben")
            return None

        # Text bereinigen
        text = self._clean_text(text)

        if output_path is None:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False, prefix="tts_"
            )
            output_path = tmp.name
            tmp.close()

        output_path = str(output_path)

        logger.info(f"TTS Synthesize Start: '{text[:60]}...' -> {output_path}")
        start = time.time()

        # Text in temporaere Datei schreiben
        text_file = None
        try:
            text_file = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, prefix="tts_input_"
            )
            text_file.write(text)
            text_file.close()

            # Piper starten - komplett isoliert vom AGI-Kontext
            logger.info("TTS: Starte Piper (isoliert)...")
            returncode, stderr = _run_isolated(
                [
                    self.piper_path,
                    "--model", self.voice_path,
                    "--output_file", output_path,
                ],
                stdin_file_path=text_file.name,
                timeout=30,
            )

            if returncode != 0:
                logger.error(f"Piper-Fehler (code {returncode}): {stderr[:200]}")
                return None

            # Pruefen ob Datei erzeugt wurde
            if not Path(output_path).exists() or Path(output_path).stat().st_size < 100:
                logger.error(f"Piper hat keine gueltige Datei erzeugt: {output_path}")
                return None

            duration = time.time() - start
            logger.info(f"TTS erzeugt ({duration:.1f}s): {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"TTS-Fehler: {e}")
            return None
        finally:
            # Text-Datei aufraeumen
            if text_file:
                try:
                    Path(text_file.name).unlink(missing_ok=True)
                except OSError:
                    pass

    def synthesize_to_asterisk_format(self, text, output_path):
        """
        Erzeugt Audio im Asterisk-kompatiblen Format.
        (16-bit PCM, 8kHz, Mono fuer alaw/ulaw)
        """
        # Erst normal erzeugen
        raw_path = self.synthesize(text)
        if raw_path is None:
            return None

        # Dann konvertieren mit sox (auch isoliert)
        try:
            logger.info("TTS: Starte Sox-Konvertierung (isoliert)...")
            returncode, stderr = _run_isolated(
                [
                    "sox", raw_path,
                    "-r", "8000",
                    "-c", "1",
                    "-b", "16",
                    output_path,
                ],
                timeout=10,
            )

            # Temporaere Datei aufraeumen
            Path(raw_path).unlink(missing_ok=True)

            if returncode != 0:
                logger.error(f"Sox-Fehler (code {returncode}): {stderr[:200]}")
                return None

            if Path(output_path).exists():
                logger.info(f"Sox-Konvertierung OK: {output_path}")
                return output_path
            else:
                logger.error("Konvertierung fehlgeschlagen")
                return None

        except Exception as e:
            logger.error(f"Audio-Konvertierung fehlgeschlagen: {e}")
            Path(raw_path).unlink(missing_ok=True)
            return None

    def _clean_text(self, text):
        """
        Bereinigt Text fuer die Sprachausgabe.
        Entfernt Sonderzeichen, die Piper nicht gut handhabt.
        Zahlen wie PLZ werden als Einzelziffern ausgesprochen.
        """
        import re

        # Markdown/Formatierung entfernen
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'#+\s*', '', text)
        text = re.sub(r'\[.*?\]\(.*?\)', '', text)

        # Aufzaehlungszeichen ersetzen
        text = re.sub(r'^[\-\*]\s+', '', text, flags=re.MULTILINE)

        # Mehrfache Leerzeichen
        text = re.sub(r'\s+', ' ', text)

        # Postleitzahlen (5 Ziffern) als einzelne Ziffern aussprechen
        # z.B. "86381" -> "8 6 3 8 1"
        def plz_to_digits(match):
            return ' '.join(match.group(0))
        text = re.sub(r'\b\d{5}\b', plz_to_digits, text)

        # Hausnummern (1-4 Ziffern nach Strassenname) normal lassen
        # Telefonnummern als Zifferngruppen aussprechen
        def phone_to_digits(match):
            num = match.group(0)
            # Ziffern einzeln mit Leerzeichen
            return ' '.join(num.replace('-', ' ').replace('/', ' '))
        text = re.sub(r'\b0\d[\d\-/]{6,}\b', phone_to_digits, text)

        # Datum formatieren fuer natuerliche Aussprache
        # z.B. "23.02.2026" -> "dreiundzwanzigster Februar zweitausendsechsundzwanzig"
        def date_to_speech(match):
            day = int(match.group(1))
            month = int(match.group(2))
            year = match.group(3) if match.group(3) else ""

            # Tage als Ordinalzahlen
            day_words = {
                1: "erster", 2: "zweiter", 3: "dritter", 4: "vierter", 5: "fuenfter",
                6: "sechster", 7: "siebter", 8: "achter", 9: "neunter", 10: "zehnter",
                11: "elfter", 12: "zwoelfter", 13: "dreizehnter", 14: "vierzehnter",
                15: "fuenfzehnter", 16: "sechzehnter", 17: "siebzehnter", 18: "achtzehnter",
                19: "neunzehnter", 20: "zwanzigster", 21: "einundzwanzigster",
                22: "zweiundzwanzigster", 23: "dreiundzwanzigster", 24: "vierundzwanzigster",
                25: "fuenfundzwanzigster", 26: "sechsundzwanzigster", 27: "siebenundzwanzigster",
                28: "achtundzwanzigster", 29: "neunundzwanzigster", 30: "dreissigster",
                31: "einunddreissigster"
            }

            # Monate
            month_words = {
                1: "Januar", 2: "Februar", 3: "Maerz", 4: "April", 5: "Mai", 6: "Juni",
                7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"
            }

            result = day_words.get(day, str(day)) + " " + month_words.get(month, str(month))

            if year:
                # Jahr nur wenn vorhanden und sinnvoll
                if len(year) == 4:
                    result += " " + year

            return result

        # Datum im Format DD.MM.YYYY oder DD.MM.
        text = re.sub(r'(\d{1,2})\.(\d{1,2})\.(\d{4})?', date_to_speech, text)

        # Uhrzeit formatieren
        # z.B. "14:30" -> "vierzehn Uhr dreissig"
        def time_with_minutes(match):
            hour = int(match.group(1))
            minute = match.group(2)

            hour_words = {
                0: "null", 1: "ein", 2: "zwei", 3: "drei", 4: "vier", 5: "fuenf",
                6: "sechs", 7: "sieben", 8: "acht", 9: "neun", 10: "zehn",
                11: "elf", 12: "zwoelf", 13: "dreizehn", 14: "vierzehn", 15: "fuenfzehn",
                16: "sechzehn", 17: "siebzehn", 18: "achtzehn", 19: "neunzehn",
                20: "zwanzig", 21: "einundzwanzig", 22: "zweiundzwanzig", 23: "dreiundzwanzig"
            }

            result = hour_words.get(hour, str(hour)) + " Uhr"

            if minute:
                min_val = int(minute)
                if min_val > 0:
                    if min_val < 10:
                        result += " null " + str(min_val)
                    else:
                        result += " " + str(min_val)

            return result

        # "15 Uhr" -> "fuenfzehn Uhr"
        def time_only_hour(match):
            hour = int(match.group(1))
            hour_words = {
                0: "null", 1: "ein", 2: "zwei", 3: "drei", 4: "vier", 5: "fuenf",
                6: "sechs", 7: "sieben", 8: "acht", 9: "neun", 10: "zehn",
                11: "elf", 12: "zwoelf", 13: "dreizehn", 14: "vierzehn", 15: "fuenfzehn",
                16: "sechzehn", 17: "siebzehn", 18: "achtzehn", 19: "neunzehn",
                20: "zwanzig", 21: "einundzwanzig", 22: "zweiundzwanzig", 23: "dreiundzwanzig"
            }
            return hour_words.get(hour, str(hour)) + " Uhr"

        # Uhrzeit im Format HH:MM Uhr (mit optionalem "Uhr" danach)
        text = re.sub(r'(\d{1,2}):(\d{2})\s*Uhr\b', time_with_minutes, text)
        # Uhrzeit im Format HH:MM (ohne "Uhr")
        text = re.sub(r'(\d{1,2}):(\d{2})', time_with_minutes, text)
        # Uhrzeit im Format "15 Uhr" (ohne Minuten)
        text = re.sub(r'(\d{1,2})\s*Uhr\b', time_only_hour, text)

        # Abkuerzungen aufloesen fuer bessere Aussprache
        replacements = {
            "z.B.": "zum Beispiel",
            "z. B.": "zum Beispiel",
            "d.h.": "das heisst",
            "d. h.": "das heisst",
            "u.a.": "unter anderem",
            "u. a.": "unter anderem",
            "ca.": "circa",
            "bzgl.": "bezueglich",
            "inkl.": "inklusive",
            "zzgl.": "zuzueglich",
            "MwSt.": "Mehrwertsteuer",
            "Tel.": "Telefon",
            "Nr.": "Nummer",
            "Str.": "Strasse",
            "€": "Euro",
        }
        for abbrev, full in replacements.items():
            text = text.replace(abbrev, full)

        # Natuerlichere Pausen einbauen (Komma = kurze Pause)
        text = text.replace(",", ", ")

        return text.strip()


class ElevenLabsTTSEngine:
    """
    ElevenLabs Cloud TTS - extrem schnelle, natuerlich klingende Stimme.
    Nutzt Streaming API mit ulaw_8000 Format (direkt Asterisk-kompatibel).
    Fallback auf Piper wenn ElevenLabs nicht verfuegbar.
    """

    # Native deutsche Stimme - Adrian (vertrauenswuerdig, professionell)
    DEFAULT_VOICE_ID = "aduJlSmEKqbhRQAAMzV2"  # Adrian - native German male voice

    def __init__(self, api_key, voice_id=None, piper_path=None, piper_voice=None):
        self.api_key = api_key
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID
        self.model_id = "eleven_flash_v2_5"  # Schnellstes Modell (~75ms)
        self.api_url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"
        self._piper_fallback = None
        if piper_path and piper_voice:
            self._piper_fallback = TTSEngine(piper_path, piper_voice)
        self._text_cleaner = TTSEngine.__new__(TTSEngine)
        logger.info(f"ElevenLabs TTS bereit. Voice: {self.voice_id}, Model: {self.model_id}")

    def synthesize_to_asterisk_format(self, text, output_path):
        """
        Erzeugt Audio im Asterisk-Format ueber ElevenLabs Streaming API.
        Nutzt pcm_16000 und konvertiert via sox zu 8kHz WAV.
        Fallback auf Piper bei Fehler.
        """
        if not text or not text.strip():
            logger.warning("Leerer Text fuer TTS")
            return None

        if not requests:
            logger.warning("requests nicht verfuegbar, nutze Piper Fallback")
            return self._fallback_piper(text, output_path)

        # Text bereinigen (nutzt die gleiche Logik wie Piper)
        text = self._text_cleaner._clean_text(text)

        logger.info(f"ElevenLabs TTS Start: '{text[:60]}...'")
        start = time.time()

        try:
            resp = requests.post(
                self.api_url,
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "model_id": self.model_id,
                    "voice_settings": {
                        "stability": 0.35,  # Niedriger = natuerlichere Aussprache (gut fuer Namen)
                        "similarity_boost": 0.80,
                        "style": 0.15,  # Etwas expressiver
                        "use_speaker_boost": True,
                    },
                    "output_format": "mp3_22050_32",
                },
                stream=True,
                timeout=15,
            )

            if resp.status_code != 200:
                logger.error(f"ElevenLabs API Fehler {resp.status_code}: {resp.text[:200]}")
                return self._fallback_piper(text, output_path)

            # MP3-Daten in temp-Datei streamen
            mp3_file = tempfile.NamedTemporaryFile(
                suffix=".mp3", delete=False, prefix="elevenlabs_"
            )
            total_bytes = 0
            for chunk in resp.iter_content(chunk_size=4096):
                if chunk:
                    mp3_file.write(chunk)
                    total_bytes += len(chunk)
            mp3_file.close()

            if total_bytes < 100:
                logger.error("ElevenLabs hat keine gueltigen Audiodaten geliefert")
                Path(mp3_file.name).unlink(missing_ok=True)
                return self._fallback_piper(text, output_path)

            # MP3 -> WAV 8kHz konvertieren mit sox (isoliert)
            returncode, stderr = _run_isolated(
                [
                    "sox",
                    mp3_file.name,
                    "-r", "8000", "-c", "1", "-b", "16",
                    output_path,
                ],
                timeout=10,
            )

            Path(mp3_file.name).unlink(missing_ok=True)

            if returncode != 0:
                logger.error(f"Sox-Fehler bei ElevenLabs-Audio: {stderr[:200]}")
                return self._fallback_piper(text, output_path)

            duration = time.time() - start
            logger.info(f"ElevenLabs TTS fertig ({duration:.1f}s): {output_path}")
            return output_path

        except requests.Timeout:
            logger.warning("ElevenLabs Timeout - nutze Piper Fallback")
            return self._fallback_piper(text, output_path)
        except Exception as e:
            logger.error(f"ElevenLabs Fehler: {e} - nutze Piper Fallback")
            return self._fallback_piper(text, output_path)

    def _fallback_piper(self, text, output_path):
        """Fallback auf lokales Piper TTS."""
        if self._piper_fallback:
            logger.info("Fallback auf Piper TTS...")
            return self._piper_fallback.synthesize_to_asterisk_format(text, output_path)
        logger.error("Kein Piper-Fallback konfiguriert!")
        return None


def create_tts_engine(config):
    """
    Factory-Funktion: Erstellt die passende TTS-Engine basierend auf Konfiguration.
    Nutzt ElevenLabs wenn API-Key vorhanden, sonst Piper.
    """
    elevenlabs_key = config.get("elevenlabs_api_key", "")
    elevenlabs_voice = config.get("elevenlabs_voice_id", "")

    if elevenlabs_key:
        logger.info("Verwende ElevenLabs Cloud TTS (mit Piper Fallback)")
        return ElevenLabsTTSEngine(
            api_key=elevenlabs_key,
            voice_id=elevenlabs_voice or None,
            piper_path=config.get("piper_path"),
            piper_voice=config.get("piper_voice"),
        )
    else:
        logger.info("Verwende lokales Piper TTS")
        return TTSEngine(config["piper_path"], config["piper_voice"])
