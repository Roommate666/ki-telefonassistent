"""
LLM-Engine mit Multi-Provider Support.
Unterstützt: Groq (kostenlos), OpenAI, Google Gemini, Anthropic, und Ollama (lokal).
"""

import logging
import time
import requests
import json
import os

logger = logging.getLogger(__name__)

# Fallback-Antwort bei Fehler
FALLBACK_RESPONSE = (
    "Es tut mir leid, es gibt gerade ein technisches Problem. "
    "Bitte versuchen Sie es später erneut oder hinterlassen Sie "
    "Ihren Namen und Ihre Telefonnummer."
)

EXTRACTION_PROMPT = """Extrahiere folgende Informationen aus dem Gespräch (falls vorhanden).
Antworte NUR im JSON-Format:
{
    "name": "Name des Anrufers oder null",
    "phone": "Telefonnummer oder null",
    "concern": "Kurze Zusammenfassung des Anliegens",
    "appointment_requested": true/false,
    "preferred_time": "Gewünschter Termin oder null",
    "urgency": "niedrig/mittel/hoch",
    "callback_requested": true/false
}"""

BOOKING_EXTRACTION_PROMPT = """Analysiere dieses Telefongespraech und extrahiere ALLE relevanten Informationen fuer die Terminverwaltung.
Antworte NUR im JSON-Format, OHNE zusaetzlichen Text:

{
    "has_booking_request": true/false,
    "booking_type": "termin" oder "anfrage",
    "customer_name": "Name des Anrufers oder null",
    "concern": "Kurze Zusammenfassung des Anliegens",
    "preferred_staff": "Gewuenschter Mitarbeiter/Stylist oder null",
    "service_name": "Gewuenschte Dienstleistung/Behandlung oder null",
    "requested_date": "Gewuenschtes Datum (YYYY-MM-DD Format wenn moeglich) oder null",
    "requested_time": "Gewuenschte Uhrzeit (HH:MM Format) oder null",
    "party_size": "Anzahl Personen (bei Gastronomie/Restaurant) oder null",
    "notes": "Zusaetzliche Hinweise/Wuensche oder null",
    "customer_address": "Adresse des Kunden (bei Handwerk/Reparatur) oder null",
    "category": "Kategorie des Problems (z.B. Heizung, Sanitaer, Elektro) oder null",
    "urgency": "niedrig/normal/hoch/notfall",
    "description": "Detaillierte Problembeschreibung (bei Anfragen) oder null"
}

Regeln:
- booking_type "termin" = Kunde will einen Termin (Friseur, Kosmetik, Massage etc.)
- booking_type "anfrage" = Kunde hat ein Problem/Auftrag/Frage (Handwerk, Reparatur, allgemeine Anfragen etc.)
- has_booking_request = IMMER true wenn ein echtes Gespraech stattgefunden hat (NICHT false bei einfachen Fragen!)
- Auch einfache Fragen (Oeffnungszeiten, Preise, Infos) sind Anfragen und sollen dokumentiert werden
- Datum: Versuche relative Angaben wie "naechsten Dienstag" oder "morgen" NICHT umzurechnen, schreibe sie woertlich wenn kein konkretes Datum genannt wurde
- urgency "notfall" nur bei echten Notfaellen (Wasserrohrbruch, Gasgeruch etc.)"""


def create_llm_engine(config):
    """
    Factory-Funktion: Erstellt die richtige LLM-Engine basierend auf der Konfiguration.
    Bei 'groq' wird automatisch ein Fallback zu Gemini eingerichtet.
    """
    provider = config.get("llm_provider", "groq").lower()

    engines = {
        "groq": GroqEngine,
        "openai": OpenAIEngine,
        "gemini": GeminiEngine,
        "anthropic": AnthropicEngine,
        "ollama": OllamaEngine,
    }

    engine_class = engines.get(provider)
    if engine_class is None:
        raise ValueError(
            f"Unbekannter LLM-Provider: '{provider}'. "
            f"Verfügbar: {list(engines.keys())}"
        )

    logger.info(f"LLM-Provider: {provider}")

    # Bei Groq: Automatisch Fallback zu Gemini einrichten (falls Gemini-Key vorhanden)
    if provider == "groq" and config.get("gemini_api_key"):
        logger.info("Fallback-LLM aktiviert: Gemini (bei Groq Rate-Limit)")
        return FallbackEngine(config)

    return engine_class(config)


class BaseLLMEngine:
    """Basis-Klasse für alle LLM-Engines."""

    def generate_response(self, system_prompt, conversation_history, user_message, max_tokens=None):
        raise NotImplementedError

    def extract_caller_info(self, conversation_text):
        """Extrahiert Anrufer-Informationen aus dem Gespräch."""
        try:
            result = self.generate_response(
                EXTRACTION_PROMPT, [], conversation_text, max_tokens=500
            )
            content = result.get("response", "")
            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                return json.loads(json_str)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Konnte Anrufer-Info nicht extrahieren: {e}")

        return {
            "name": None, "phone": None, "concern": "Nicht erkannt",
            "appointment_requested": False, "preferred_time": None,
            "urgency": "mittel", "callback_requested": False,
        }

    def extract_booking_data(self, conversation_text):
        """Extrahiert strukturierte Booking-Daten aus dem Gespraech."""
        try:
            result = self.generate_response(
                BOOKING_EXTRACTION_PROMPT, [], conversation_text, max_tokens=500
            )
            content = result.get("response", "")
            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                data = json.loads(json_str)
                logger.info(f"Booking-Daten extrahiert: type={data.get('booking_type')}, "
                            f"has_request={data.get('has_booking_request')}")
                return data
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Konnte Booking-Daten nicht extrahieren: {e}")

        return {
            "has_booking_request": False,
            "booking_type": None,
            "customer_name": None,
            "concern": "Nicht erkannt",
            "preferred_staff": None,
            "service_name": None,
            "party_size": None,
            "requested_date": None,
            "requested_time": None,
            "notes": None,
            "customer_address": None,
            "category": None,
            "urgency": "normal",
            "description": None,
        }

    def _build_messages(self, system_prompt, conversation_history, user_message):
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def _error_response(self, error_msg):
        return {
            "response": FALLBACK_RESPONSE,
            "processing_time": 0,
            "model": getattr(self, "model", "unknown"),
            "tokens_used": 0,
            "error": error_msg,
        }


# ============================================================
# FALLBACK ENGINE - Automatischer Wechsel bei Rate-Limit
# ============================================================
class FallbackEngine(BaseLLMEngine):
    """
    Wrapper-Engine die bei Fehlern automatisch auf einen Fallback-Provider wechselt.
    Primaer: Groq mit konfiguriertem Modell (z.B. llama-3.3-70b-versatile)
    Fallback 1: Groq mit kleinerem Modell (llama-3.1-8b-instant) - hoeheres Rate-Limit
    Fallback 2: Gemini (falls verfuegbar)
    """

    def __init__(self, config):
        self.config = config
        self.primary = GroqEngine(config)
        self.fallback_groq = None
        self.fallback_gemini = None
        self.model = self.primary.model

        # Fallback-Modelle
        self._groq_fallback_model = "llama-3.1-8b-instant"  # Kleineres Modell = hoeheres Rate-Limit
        self._gemini_available = bool(config.get("gemini_api_key"))

        logger.info(f"FallbackEngine: Primary=Groq ({self.primary.model}), "
                    f"Fallback1=Groq ({self._groq_fallback_model}), "
                    f"Fallback2={'Gemini' if self._gemini_available else 'None'}")

    def _get_groq_fallback(self):
        """Erstellt eine Groq-Engine mit kleinerem Modell."""
        if self.fallback_groq is None:
            try:
                fallback_config = dict(self.config)
                fallback_config["groq_model"] = self._groq_fallback_model
                self.fallback_groq = GroqEngine(fallback_config)
                logger.info(f"Groq-Fallback initialisiert: {self._groq_fallback_model}")
            except Exception as e:
                logger.error(f"Groq-Fallback konnte nicht initialisiert werden: {e}")
        return self.fallback_groq

    def _get_gemini_fallback(self):
        """Lazy-Initialisierung des Gemini-Fallbacks."""
        if self.fallback_gemini is None and self._gemini_available:
            try:
                self.fallback_gemini = GeminiEngine(self.config)
                logger.info("Gemini-Fallback initialisiert")
            except Exception as e:
                logger.error(f"Gemini-Fallback konnte nicht initialisiert werden: {e}")
                self._gemini_available = False
        return self.fallback_gemini

    def generate_response(self, system_prompt, conversation_history, user_message, max_tokens=None):
        # Versuche zuerst Primary (Groq mit grossem Modell)
        result = self.primary.generate_response(
            system_prompt, conversation_history, user_message, max_tokens
        )

        # Bei Fehler (Rate-Limit, Timeout, etc.): Fallbacks versuchen
        if result.get("error"):
            error_msg = result.get("error", "")
            logger.warning(f"Primary LLM (Groq {self.primary.model}) fehlgeschlagen: {error_msg}")

            # Rate-Limit -> Fallbacks versuchen
            if "429" in error_msg or "rate" in error_msg.lower() or "timeout" in error_msg.lower():

                # Fallback 1: Groq mit kleinerem Modell (hoeheres Rate-Limit)
                groq_fallback = self._get_groq_fallback()
                if groq_fallback:
                    logger.info(f"Wechsle zu Groq-Fallback ({self._groq_fallback_model})...")
                    fallback_result = groq_fallback.generate_response(
                        system_prompt, conversation_history, user_message, max_tokens
                    )
                    if not fallback_result.get("error"):
                        fallback_result["fallback_used"] = "groq_small"
                        self.model = groq_fallback.model
                        return fallback_result
                    logger.warning(f"Groq-Fallback auch fehlgeschlagen: {fallback_result.get('error')}")

                # Fallback 2: Gemini
                gemini_fallback = self._get_gemini_fallback()
                if gemini_fallback:
                    logger.info("Wechsle zu Gemini-Fallback...")
                    fallback_result = gemini_fallback.generate_response(
                        system_prompt, conversation_history, user_message, max_tokens
                    )
                    if not fallback_result.get("error"):
                        fallback_result["fallback_used"] = "gemini"
                        self.model = gemini_fallback.model
                        return fallback_result
                    logger.error(f"Gemini-Fallback auch fehlgeschlagen: {fallback_result.get('error')}")

        return result


# ============================================================
# GROQ - Kostenlos, sehr schnell (empfohlen)
# ============================================================
class GroqEngine(BaseLLMEngine):
    """
    Groq Cloud API - Kostenloser Tier verfügbar.
    Extrem schnelle Inferenz (~0.2s pro Antwort).
    https://console.groq.com
    """

    def __init__(self, config):
        self.api_key = config.get("groq_api_key", "")
        self.model = config.get("groq_model", "llama-3.1-8b-instant")
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY nicht gesetzt. "
                "Kostenlos registrieren: https://console.groq.com"
            )
        self._check_connection()

    def _check_connection(self):
        try:
            resp = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5,
            )
            resp.raise_for_status()
            logger.info(f"Groq verbunden. Modell: {self.model}")
        except requests.RequestException as e:
            logger.error(f"Groq nicht erreichbar: {e}")
            raise

    def generate_response(self, system_prompt, conversation_history, user_message, max_tokens=None):
        messages = self._build_messages(system_prompt, conversation_history, user_message)
        logger.debug(f"Groq-Anfrage: {user_message[:100]}")
        start = time.time()

        try:
            resp = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": max_tokens or 250,
                    "top_p": 0.9,
                },
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()

            response_text = result["choices"][0]["message"]["content"].strip()
            duration = time.time() - start
            tokens = result.get("usage", {}).get("total_tokens", 0)

            logger.info(f"Groq-Antwort ({duration:.1f}s, {tokens} Tokens): '{response_text[:100]}'")

            return {
                "response": response_text,
                "processing_time": duration,
                "model": self.model,
                "tokens_used": tokens,
            }
        except requests.Timeout:
            logger.error("Groq-Timeout")
            return self._error_response("timeout")
        except requests.RequestException as e:
            logger.error(f"Groq-Fehler: {e}")
            return self._error_response(str(e))


# ============================================================
# OPENAI - GPT-4o-mini (sehr günstig, hohe Qualität)
# ============================================================
class OpenAIEngine(BaseLLMEngine):
    """
    OpenAI API - GPT-4o-mini ist extrem günstig.
    ~0.002€ pro Anruf.
    """

    def __init__(self, config):
        self.api_key = config.get("openai_api_key", "")
        self.model = config.get("openai_model", "gpt-4o-mini")
        self.api_url = "https://api.openai.com/v1/chat/completions"

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY nicht gesetzt.")
        self._check_connection()

    def _check_connection(self):
        try:
            resp = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5,
            )
            resp.raise_for_status()
            logger.info(f"OpenAI verbunden. Modell: {self.model}")
        except requests.RequestException as e:
            logger.error(f"OpenAI nicht erreichbar: {e}")
            raise

    def generate_response(self, system_prompt, conversation_history, user_message, max_tokens=None):
        messages = self._build_messages(system_prompt, conversation_history, user_message)
        start = time.time()

        try:
            resp = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": max_tokens or 250,
                },
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()

            response_text = result["choices"][0]["message"]["content"].strip()
            duration = time.time() - start
            tokens = result.get("usage", {}).get("total_tokens", 0)

            logger.info(f"OpenAI-Antwort ({duration:.1f}s): '{response_text[:100]}'")

            return {
                "response": response_text,
                "processing_time": duration,
                "model": self.model,
                "tokens_used": tokens,
            }
        except requests.Timeout:
            return self._error_response("timeout")
        except requests.RequestException as e:
            logger.error(f"OpenAI-Fehler: {e}")
            return self._error_response(str(e))


# ============================================================
# GOOGLE GEMINI - Kostenloser Tier, gute Qualität
# ============================================================
class GeminiEngine(BaseLLMEngine):
    """
    Google Gemini API - Kostenloser Tier verfügbar.
    https://aistudio.google.com/app/apikey
    """

    def __init__(self, config):
        self.api_key = config.get("gemini_api_key", "")
        self.model = config.get("gemini_model", "gemini-2.0-flash")
        self.api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.model}:generateContent"
        )

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY nicht gesetzt. "
                "Kostenlos: https://aistudio.google.com/app/apikey"
            )
        logger.info(f"Gemini konfiguriert. Modell: {self.model}")

    def generate_response(self, system_prompt, conversation_history, user_message, max_tokens=None):
        start = time.time()

        # Gemini-Format: system_instruction + contents
        contents = []
        for msg in conversation_history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        try:
            resp = requests.post(
                f"{self.api_url}?key={self.api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "system_instruction": {"parts": [{"text": system_prompt}]},
                    "contents": contents,
                    "generationConfig": {
                        "temperature": 0.7,
                        "maxOutputTokens": max_tokens or 150,
                        "topP": 0.9,
                    },
                },
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()

            response_text = (
                result["candidates"][0]["content"]["parts"][0]["text"].strip()
            )
            duration = time.time() - start
            tokens = result.get("usageMetadata", {}).get("totalTokenCount", 0)

            logger.info(f"Gemini-Antwort ({duration:.1f}s): '{response_text[:100]}'")

            return {
                "response": response_text,
                "processing_time": duration,
                "model": self.model,
                "tokens_used": tokens,
            }
        except requests.Timeout:
            return self._error_response("timeout")
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error(f"Gemini-Fehler: {e}")
            return self._error_response(str(e))


# ============================================================
# ANTHROPIC - Claude (hochwertigste Antworten)
# ============================================================
class AnthropicEngine(BaseLLMEngine):
    """
    Anthropic Claude API - Beste Qualität, etwas teurer.
    """

    def __init__(self, config):
        self.api_key = config.get("anthropic_api_key", "")
        self.model = config.get("anthropic_model", "claude-haiku-4-20250414")
        self.api_url = "https://api.anthropic.com/v1/messages"

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY nicht gesetzt.")
        logger.info(f"Anthropic konfiguriert. Modell: {self.model}")

    def generate_response(self, system_prompt, conversation_history, user_message, max_tokens=None):
        messages = []
        for msg in conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        start = time.time()

        try:
            resp = requests.post(
                self.api_url,
                headers={
                    "x-api-key": self.api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.model,
                    "system": system_prompt,
                    "messages": messages,
                    "max_tokens": max_tokens or 250,
                    "temperature": 0.7,
                },
                timeout=15,
            )
            resp.raise_for_status()
            result = resp.json()

            response_text = result["content"][0]["text"].strip()
            duration = time.time() - start
            tokens = result.get("usage", {}).get("input_tokens", 0) + \
                     result.get("usage", {}).get("output_tokens", 0)

            logger.info(f"Anthropic-Antwort ({duration:.1f}s): '{response_text[:100]}'")

            return {
                "response": response_text,
                "processing_time": duration,
                "model": self.model,
                "tokens_used": tokens,
            }
        except requests.Timeout:
            return self._error_response("timeout")
        except requests.RequestException as e:
            logger.error(f"Anthropic-Fehler: {e}")
            return self._error_response(str(e))


# ============================================================
# OLLAMA - Lokal (kein Internet nötig, aber braucht starke Hardware)
# ============================================================
class OllamaEngine(BaseLLMEngine):
    """Ollama - Lokales LLM. Nur wenn genug RAM/GPU vorhanden."""

    def __init__(self, config):
        self.host = config.get("ollama_host", "http://localhost:11434").rstrip("/")
        self.model = config.get("ollama_model", "llama3.1:8b")
        self.api_url = f"{self.host}/api/chat"
        self._check_connection()

    def _check_connection(self):
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=5)
            resp.raise_for_status()
            logger.info(f"Ollama verbunden. Modell: {self.model}")
        except requests.ConnectionError:
            logger.error(f"Ollama nicht erreichbar unter {self.host}")
            raise

    def generate_response(self, system_prompt, conversation_history, user_message, max_tokens=None):
        messages = self._build_messages(system_prompt, conversation_history, user_message)
        start = time.time()

        try:
            resp = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                        "num_predict": max_tokens or 150,
                    },
                },
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

            response_text = result.get("message", {}).get("content", "").strip()
            duration = time.time() - start

            logger.info(f"Ollama-Antwort ({duration:.1f}s): '{response_text[:100]}'")

            return {
                "response": response_text,
                "processing_time": duration,
                "model": self.model,
                "tokens_used": result.get("eval_count", 0),
            }
        except requests.Timeout:
            return self._error_response("timeout")
        except requests.RequestException as e:
            logger.error(f"Ollama-Fehler: {e}")
            return self._error_response(str(e))
