"""
Adress-Validierung mit Nominatim (OpenStreetMap) Geocoding.
Prueft ob eine Adresse existiert und gibt die korrekte Schreibweise zurueck.
"""

import logging
import re
import time

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger(__name__)

# Nominatim API (kostenlos, aber rate-limited: 1 request/sec)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Cache um wiederholte Anfragen zu vermeiden
_address_cache = {}


def validate_address(address_text, country="Germany"):
    """
    Validiert eine Adresse und gibt die korrigierte Version zurueck.

    Args:
        address_text: Die vom Anrufer genannte Adresse (z.B. "Kammelweg 6, 86381 Krumbach")
        country: Land fuer die Suche

    Returns:
        dict mit:
        - valid: bool - Adresse gefunden?
        - formatted: str - Formatierte Adresse
        - street: str - Strassenname
        - house_number: str - Hausnummer
        - postcode: str - PLZ
        - city: str - Stadt
        - confidence: float - Wie sicher (0-1)
        - original: str - Original-Eingabe
    """
    if not requests:
        logger.warning("requests nicht verfuegbar - Adressvalidierung deaktiviert")
        return {"valid": False, "original": address_text, "error": "requests not available"}

    if not address_text or not address_text.strip():
        return {"valid": False, "original": address_text, "error": "empty address"}

    # Cache pruefen
    cache_key = address_text.lower().strip()
    if cache_key in _address_cache:
        logger.debug(f"Adresse aus Cache: {cache_key}")
        return _address_cache[cache_key]

    # Adresse bereinigen
    clean_address = _clean_address_input(address_text)

    try:
        # Nominatim Anfrage
        params = {
            "q": f"{clean_address}, {country}",
            "format": "json",
            "addressdetails": 1,
            "limit": 1,
            "countrycodes": "de",
        }

        headers = {
            "User-Agent": "KI-Telefonassistent/1.0 (German phone assistant)"
        }

        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=5)
        resp.raise_for_status()

        results = resp.json()

        if not results:
            logger.info(f"Adresse nicht gefunden: {address_text}")
            result = {
                "valid": False,
                "original": address_text,
                "error": "address not found",
                "suggestion": None,
            }
            _address_cache[cache_key] = result
            return result

        # Beste Uebereinstimmung nehmen
        best = results[0]
        addr = best.get("address", {})

        # Komponenten extrahieren
        street = addr.get("road", addr.get("street", ""))
        house_number = addr.get("house_number", "")
        postcode = addr.get("postcode", "")
        city = addr.get("city", addr.get("town", addr.get("village", addr.get("municipality", ""))))

        # Formatierte Adresse zusammenbauen
        if street and house_number:
            formatted = f"{street} {house_number}"
        elif street:
            formatted = street
        else:
            formatted = best.get("display_name", "").split(",")[0]

        if postcode and city:
            formatted += f", {postcode} {city}"
        elif city:
            formatted += f", {city}"

        # Confidence basierend auf Importance
        importance = float(best.get("importance", 0))
        confidence = min(importance * 1.5, 1.0)  # Skalieren auf 0-1

        result = {
            "valid": True,
            "formatted": formatted,
            "street": street,
            "house_number": house_number,
            "postcode": postcode,
            "city": city,
            "confidence": confidence,
            "original": address_text,
            "lat": best.get("lat"),
            "lon": best.get("lon"),
        }

        logger.info(f"Adresse validiert: '{address_text}' -> '{formatted}' (Confidence: {confidence:.2f})")

        _address_cache[cache_key] = result
        return result

    except requests.Timeout:
        logger.warning(f"Timeout bei Adressvalidierung: {address_text}")
        return {"valid": False, "original": address_text, "error": "timeout"}
    except Exception as e:
        logger.error(f"Fehler bei Adressvalidierung: {e}")
        return {"valid": False, "original": address_text, "error": str(e)}


def _clean_address_input(text):
    """Bereinigt Adress-Eingabe von Whisper-Fehlern."""
    text_lower = text.lower().strip()

    # 1. Zahlwoerter zu Ziffern konvertieren
    number_words = {
        "null": "0", "eins": "1", "zwei": "2", "drei": "3", "vier": "4",
        "fünf": "5", "fuenf": "5", "sechs": "6", "sieben": "7", "acht": "8",
        "neun": "9", "zehn": "10", "elf": "11", "zwölf": "12", "zwoelf": "12",
        "dreizehn": "13", "vierzehn": "14", "fünfzehn": "15", "fuenfzehn": "15",
        "sechzehn": "16", "siebzehn": "17", "achtzehn": "18", "neunzehn": "19",
        "zwanzig": "20", "einundzwanzig": "21", "zweiundzwanzig": "22",
        "dreiundzwanzig": "23", "vierundzwanzig": "24", "fünfundzwanzig": "25",
        "fuenfundzwanzig": "25", "dreissig": "30", "vierzig": "40", "fünfzig": "50",
        "fuenfzig": "50", "sechzig": "60", "siebzig": "70", "achtzig": "80",
        "neunzig": "90", "hundert": "100",
    }
    for word, digit in number_words.items():
        # Nur ganze Woerter ersetzen (mit Wortgrenzen)
        text_lower = re.sub(rf'\b{word}\b', digit, text_lower)

    # 2. Haeufige Whisper-Transkriptionsfehler (phonetisch aehnlich)
    whisper_corrections = {
        # Strassentypen - haeufige Fehlschreibungen
        "strasse": "straße", "str.": "straße", "str ": "straße ",
        "strase": "straße", "strasse": "straße",
        "plaz": "platz", "platz": "platz",
        "alé": "allee", "alle": "allee",
        "gase": "gasse",
        # Haeufige phonetische Fehler bei Ortsnamen
        "muenchen": "münchen", "munchen": "münchen",
        "nuernberg": "nürnberg", "nurnberg": "nürnberg",
        "koeln": "köln", "coeln": "köln",
        "duesseldorf": "düsseldorf", "dusseldorf": "düsseldorf",
        # Projektspezifische Korrekturen (Krumbach/Kammelweg)
        "camelic": "kammelweg", "sammelwege": "kammelweg",
        "sammelweg": "kammelweg", "fammelweg": "kammelweg",
        "kammelveg": "kammelweg", "kamelveg": "kammelweg",
        "grumbach": "krumbach", "krombach": "krumbach",
        "krummbach": "krumbach",
        # Allgemeine Whisper-Fehler
        "haupt strasse": "hauptstraße", "haupt straße": "hauptstraße",
        "bahn hof": "bahnhof", "bahn hofstraße": "bahnhofstraße",
        "kirch": "kirch", "kirchstraße": "kirchstraße",
        "markt platz": "marktplatz",
        "schul": "schul", "schulstraße": "schulstraße",
    }
    for wrong, correct in whisper_corrections.items():
        text_lower = text_lower.replace(wrong, correct)

    # 3. PLZ-Format normalisieren
    # "8 6 3 8 1" -> "86381"
    plz_pattern = r'\b(\d)\s+(\d)\s+(\d)\s+(\d)\s+(\d)\b'
    text_lower = re.sub(plz_pattern, r'\1\2\3\4\5', text_lower)

    # "acht sechs drei acht eins" wurde bereits oben konvertiert

    # 4. Hausnummer-Zusaetze normalisieren
    # "6 a" -> "6a", "12 b" -> "12b"
    text_lower = re.sub(r'(\d+)\s+([a-z])\b', r'\1\2', text_lower)

    # 5. Ueberfluessige Leerzeichen entfernen
    text_lower = re.sub(r'\s+', ' ', text_lower).strip()

    # 6. "in" und "bei" entfernen wenn vor Ortsname
    # z.B. "Hauptstraße 1 in München" -> "Hauptstraße 1 München"
    text_lower = re.sub(r'\b(in|bei)\s+', '', text_lower)

    return text_lower


def validate_address_with_retry(address_text, country="Germany", max_retries=2):
    """
    Validiert eine Adresse mit Retry-Logik.
    Versucht bei Fehlschlag alternative Schreibweisen.
    """
    result = validate_address(address_text, country)
    if result.get("valid"):
        return result

    # Fallback 1: Nur PLZ + Stadt
    plz_match = re.search(r'\b(\d{5})\b', address_text)
    if plz_match and max_retries > 0:
        plz = plz_match.group(1)
        # Suche nur nach PLZ
        result_plz = validate_address(plz, country)
        if result_plz.get("valid"):
            result_plz["partial_match"] = True
            result_plz["original"] = address_text
            return result_plz

    # Fallback 2: Entferne Hausnummer und versuche nur Strasse + Stadt
    street_only = re.sub(r'\b\d+[a-z]?\b', '', address_text).strip()
    if street_only != address_text and max_retries > 1:
        result_street = validate_address(street_only, country)
        if result_street.get("valid"):
            result_street["partial_match"] = True
            result_street["original"] = address_text
            return result_street

    return result


def format_address_for_speech(validated_address):
    """
    Formatiert eine validierte Adresse fuer die Sprachausgabe.
    PLZ wird als einzelne Ziffern ausgesprochen.
    """
    if not validated_address.get("valid"):
        return validated_address.get("original", "")

    street = validated_address.get("street", "")
    house_number = validated_address.get("house_number", "")
    postcode = validated_address.get("postcode", "")
    city = validated_address.get("city", "")

    # PLZ als einzelne Ziffern
    if postcode:
        postcode_spoken = " ".join(postcode)
    else:
        postcode_spoken = ""

    parts = []
    if street:
        if house_number:
            parts.append(f"{street} {house_number}")
        else:
            parts.append(street)
    if postcode_spoken and city:
        parts.append(f"{postcode_spoken} {city}")
    elif city:
        parts.append(city)

    return ", ".join(parts)


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("=== Test: _clean_address_input ===\n")
    test_inputs = [
        ("Kammelweg sechs, 86381 Krumbach", "Erwarte: kammelweg 6, 86381 krumbach"),
        ("camelic 6 grumbach 8 6 3 8 1", "Erwarte: kammelweg 6 krumbach 86381"),
        ("Hauptstrasse eins in Augsburg", "Erwarte: hauptstraße 1 augsburg"),
        ("Bahnhofstr. 12 a, Muenchen", "Erwarte: bahnhofstraße 12a, münchen"),
    ]

    for input_text, expected in test_inputs:
        cleaned = _clean_address_input(input_text)
        print(f"Input:    {input_text}")
        print(f"Cleaned:  {cleaned}")
        print(f"{expected}")
        print()

    print("\n=== Test: validate_address (mit Nominatim) ===\n")
    test_addresses = [
        "Kammelweg 6, 86381 Krumbach",
        "camelic 6 grumbach 86381",
        "Hauptstrasse 1, 86150 Augsburg",
        "Marienplatz 1, 80331 München",
        "Bahnhofstraße zwölf, Berlin",
    ]

    for addr in test_addresses:
        print(f"--- Testing: {addr} ---")
        result = validate_address(addr)
        print(f"Valid: {result.get('valid')}")
        print(f"Formatted: {result.get('formatted')}")
        print(f"Components: {result.get('street')} {result.get('house_number')}, "
              f"{result.get('postcode')} {result.get('city')}")
        print(f"Confidence: {result.get('confidence', 0):.2f}")
        if result.get('error'):
            print(f"Error: {result.get('error')}")
        print()
        time.sleep(1.1)  # Nominatim rate limit
