# KI-Telefonassistent - Systemarchitektur

> Letzte Aktualisierung: 15.02.2026
> Server: Hetzner VPS (46.225.107.174)
> Pfad auf Server: `/opt/ki-telefonassistent/`

---

## System-Uebersicht

Der KI-Telefonassistent ist ein vollautomatisches Telefon-KI-System, das eingehende Anrufe entgegennimmt, mit Anrufern natuerlichsprachige Gespraeche fuehrt und die Ergebnisse in einer Web-Oberflaeche darstellt.

**Kernkomponenten:**

- **Asterisk PBX** -- Empfaengt eingehende Anrufe ueber einen SIP-Trunk von sipgate
- **AGI-Script (`agi_handler.py`)** -- Herzstuck des Systems; steuert den gesamten Gespraechsablauf
- **ElevenLabs Cloud TTS** -- Primaere Text-to-Speech-Engine (mit Piper als lokalem Fallback)
- **faster-whisper STT** -- Speech-to-Text-Erkennung (Medium-Modell, CPU, int8)
- **Claude Haiku 4.5** -- LLM von Anthropic fuer natuerlichsprachige Gespraechsfuehrung
- **Flask Web-Dashboard (PWA)** -- Verwaltungsoberflaeche fuer Anrufe und Termine
- **Telegram-Benachrichtigungen** -- Sofortige Benachrichtigung bei neuen Anrufen
- **Multi-Tenant-Architektur** -- Mehrere Unternehmen auf demselben System ueber DID-Routing

```
                    +-----------------+
  Anrufer --------->|  sipgate SIP    |
  (PSTN)            |  Trunk          |
                    +--------+--------+
                             |
                    +--------v--------+
                    |   Asterisk PBX  |
                    |  extensions.conf|
                    +--------+--------+
                             |
                    +--------v--------+
                    |  agi_handler.py  |
                    |  (AGI-Script)    |
                    +--------+--------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v---+  +------v------+  +----v-------+
     | faster-    |  | Claude      |  | ElevenLabs |
     | whisper    |  | Haiku 4.5   |  | TTS        |
     | (STT)      |  | (LLM)      |  | (+Piper)   |
     +------------+  +------+------+  +------------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v---+  +------v------+  +----v-------+
     | SQLite DB  |  | Telegram    |  | Flask      |
     | (Anrufe +  |  | Bot         |  | Dashboard  |
     |  Buchungen)|  |             |  | (PWA)      |
     +------------+  +-------------+  +------------+
```

---

## Telefonnummern

| Telefonnummer     | Branche       | business_id | Beschreibung                  |
|-------------------|---------------|-------------|-------------------------------|
| 08282-6388978     | Handwerk      | 1           | Handwerker-Betrieb            |
| 08282-6388979     | Versicherung  | 2           | Versicherungsberater (Leitung 1) |
| 08282-6388980     | Versicherung  | 2           | Versicherungsberater (Leitung 2) |

Alle Nummern laufen ueber den sipgate SIP-Trunk und werden per DID-Routing (`config/did-routing.json`) dem jeweiligen Business zugeordnet.

---

## Dateistruktur

Auf dem Server unter `/opt/ki-telefonassistent/`:

### Kern-Module (`src/`)

| Datei                        | Beschreibung                                                        |
|------------------------------|---------------------------------------------------------------------|
| `src/agi_handler.py`        | Asterisk AGI Handler -- Herzstuck des Systems. Steuert den gesamten Gespraechsablauf: Begruessung, Aufnahme, STT, LLM, TTS, Datenextraktion. |
| `src/tts_engine.py`         | Text-to-Speech-Engine. Primaer ElevenLabs Cloud (`eleven_flash_v2_5`), mit automatischem Fallback auf lokales Piper TTS bei Fehlern oder Timeouts. |
| `src/stt_engine.py`         | Speech-to-Text mit faster-whisper. Laedt das Medium-Modell auf CPU mit int8-Quantisierung. |
| `src/llm_engine.py`         | LLM-Integration ueber die Anthropic API. Nutzt Claude Haiku 4.5 fuer Gespraechsfuehrung und Datenextraktion. |
| `src/config_loader.py`      | Laedt Konfiguration aus `.env` und Business-Configs aus `prompts/`. Stellt alle Einstellungen zentral bereit. |
| `src/call_database.py`      | Anruf-Datenbank (SQLite). Speichert alle Anrufe mit Transkript, Caller-Info, Status und Metadaten. |
| `src/booking_database.py`   | Termin- und Anfragen-Datenbank. Speichert extrahierte Buchungsdaten und Kundenanfragen. |
| `src/notifications.py`      | Telegram-Benachrichtigungen. Sendet formatierte Nachrichten bei neuen Anrufen an konfigurierte Chat-IDs. |
| `src/push_notifications.py` | Web Push Notifications (VAPID). Sendet Browser-Push-Nachrichten an das Dashboard. |
| `src/customer_notifications.py` | SMS-Benachrichtigungen an Kunden ueber sipgate API. |
| `src/address_validator.py`  | Adressvalidierung. Prueft und normalisiert Adressen aus Anrufer-Angaben. |

### Web-Dashboard (`src/`)

| Datei                        | Beschreibung                                                        |
|------------------------------|---------------------------------------------------------------------|
| `src/web_dashboard.py`      | Flask-App Hauptdatei. Erstellt die Flask-Anwendung und registriert alle Blueprints (Handwerk, Versicherung). |
| `src/booking_dashboard.py`  | Handwerk-Dashboard (Flask Blueprint). Web-Oberflaeche fuer den Handwerker-Betrieb. |
| `src/booking_api.py`        | Handwerk-API (Flask Blueprint). REST-API-Endpoints fuer das Handwerk-Dashboard. |
| `src/versicherung_app.py`   | Versicherungs-Dashboard PWA (Flask Blueprint). Single-Page-App mit Glassmorphism-Design. |
| `src/versicherung_api.py`   | Versicherungs-API (Flask Blueprint). REST-API-Endpoints fuer das Versicherungs-Dashboard. |

### Konfiguration (`config/`)

| Datei                        | Beschreibung                                                        |
|------------------------------|---------------------------------------------------------------------|
| `config/.env`               | Umgebungsvariablen: API-Keys (ElevenLabs, Anthropic, Telegram), Voice-IDs, Modell-Einstellungen, VAPID-Keys, sipgate-Token. |
| `config/did-routing.json`   | DID-basiertes Multi-Tenant-Routing. Ordnet eingehende Telefonnummern den jeweiligen Businesses zu. |

### Business-Konfigurationen (`prompts/`)

| Datei                        | Beschreibung                                                        |
|------------------------------|---------------------------------------------------------------------|
| `prompts/handwerk.json`     | Business-Config fuer den Handwerker. Enthaelt System-Prompt, Begruessung, Oeffnungszeiten, Extraktionsregeln. |
| `prompts/versicherung.json` | Business-Config fuer den Versicherungsberater. Enthaelt System-Prompt, Begruessung, Kategorisierung (Schaden/Termin/Frage). |

### Scripts und Tools

| Datei                        | Beschreibung                                                        |
|------------------------------|---------------------------------------------------------------------|
| `run_agi.sh`                | Startskript fuer das AGI-Script. Wird von Asterisk bei eingehenden Anrufen aufgerufen. Setzt Umgebungsvariablen und startet `agi_handler.py`. |
| `manage_business.py`        | Kommandozeilen-Tool zum Anlegen neuer Businesses in der Datenbank. |

### Weitere Verzeichnisse

| Verzeichnis                  | Beschreibung                                                        |
|------------------------------|---------------------------------------------------------------------|
| `audio/greeting_cache/`     | Gecachte Begrussungs-Audiodateien (WAV, nach MD5-Hash benannt).     |
| `logs/`                     | Log-Dateien des Systems.                                            |

---

## Anruf-Ablauf (Call Flow)

Der vollstaendige Ablauf eines eingehenden Anrufs:

```
1. Eingehender Anruf
   Anruf kommt ueber den sipgate SIP-Trunk bei Asterisk an.

2. Asterisk Routing
   extensions.conf wertet die angerufene Nummer (DID) aus
   und leitet den Anruf an das AGI-Script weiter.

3. AGI-Handler Start
   agi_handler.py wird gestartet:
   - Answer() -- Anruf annehmen
   - DID auslesen und Business per did-routing.json bestimmen
   - Business-Config (z.B. versicherung.json) laden

4. Begruessung abspielen
   - Pruefen, ob Begruessung im Cache liegt (audio/greeting_cache/)
   - Falls nicht: TTS generieren (ElevenLabs oder Piper) und cachen
   - Begruessung an den Anrufer abspielen

5. STT-Modell laden (parallel)
   Waehrend der Anrufer die Begruessung hoert, wird das
   faster-whisper Medium-Modell in den Speicher geladen.
   Das spart wertvolle Sekunden im Gespraechsverlauf.

6. Gespraechsschleife
   Wiederhole bis Gespraech beendet:
   a) Anrufer-Sprache aufnehmen (Record)
   b) Wartemusik einschalten (Music on Hold)
   c) Aufnahme per faster-whisper transkribieren (STT)
   d) Transkript + Gespraechsverlauf an Claude Haiku 4.5 senden (LLM)
   e) LLM-Antwort per ElevenLabs/Piper in Sprache umwandeln (TTS)
   f) Wartemusik ausschalten
   g) Generierte Antwort an Anrufer abspielen

7. Gespraechsende und Datenextraktion
   Nach Gespraechsende:
   - LLM extrahiert strukturierte Caller-Info (Name, Telefon, Adresse)
   - LLM extrahiert Booking-Data (Art der Anfrage, Details, Kategorie)

8. Speicherung und Benachrichtigung
   - Anruf-Daten in SQLite-Datenbank speichern
   - Termin/Anfrage in Booking-Datenbank speichern
   - Telegram-Nachricht an den zustaendigen Chat senden
   - Web-Push-Notification an das Dashboard senden
   - SMS an den Kunden senden (ueber sipgate)
```

### Zeitlicher Ablauf (typisch)

```
t=0s    Anruf eingehend, Answer()
t=0.5s  Begruessung abspielen (~3-5 Sekunden)
t=1s    STT-Modell laden beginnt (parallel zur Begruessung)
t=5s    Begruessung fertig, Anrufer spricht
t=5s    STT-Modell bereit (~5s Ladezeit, parallel abgeschlossen)
t=10s   Aufnahme fertig, Wartemusik an
t=11s   STT fertig (~1s)
t=12s   LLM-Antwort erhalten (~1-2s)
t=13s   TTS generiert (~1s)
t=13s   Wartemusik aus, Antwort abspielen
...     (Schleife wiederholt sich)
```

---

## Dashboard (Versicherung)

**URL:** `/v/dashboard?token=TOKEN`

### Allgemein

Das Versicherungs-Dashboard ist eine Progressive Web App (PWA) mit Glassmorphism-Design auf dunklem Hintergrund (`#0a0e1a`). Es ist als Single-Page-App aufgebaut und benoetigt keine separate Frontend-Build-Pipeline -- das gesamte HTML, CSS und JavaScript ist inline in den Flask-Templates enthalten.

### Design

- **Theme:** Dark Mode mit Glassmorphism-Effekten
- **Hintergrundfarbe:** `#0a0e1a`
- **Glas-Effekte:** `backdrop-filter: blur()` auf Karten und Modals
- **PWA:** Installierbar auf Mobilgeraeten, funktioniert offline (Grundfunktionen)

### Tabs

Das Dashboard hat 3 Hauptansichten:

1. **Live-Feed**
   - Zeigt die neuesten Anrufe in Echtzeit
   - Auto-Refresh alle 15 Sekunden
   - Farbcodierte Anruf-Karten nach Kategorie

2. **Alle Anrufe**
   - Vollstaendige Anruf-Historie
   - Filter- und Suchfunktionen
   - Sortierung nach Datum, Status, Kategorie

3. **Statistiken**
   - Anrufaufkommen pro Tag/Woche
   - Verteilung nach Kategorien
   - Wochenstatistiken

### Farbcodierung der Anruf-Karten

| Farbe  | Kategorie    | Bedeutung                          |
|--------|--------------|------------------------------------|
| Rot    | Schaden      | Schadensmeldung (hohe Prioritaet)  |
| Gelb   | Termin       | Terminanfrage                      |
| Gruen  | Frage        | Allgemeine Frage                   |

### Detail-Modal

Beim Klick auf eine Anruf-Karte oeffnet sich ein Detail-Modal mit:

- **Gespraechsprotokoll** im Chat-Bubble-Style (wie eine Messenger-App)
  - Linke Bubbles: Anrufer
  - Rechte Bubbles: KI-Assistent
- **Caller-Info:** Name, Telefonnummer, extrahierte Daten
- **Kategorie und Zusammenfassung**
- **Quick-Actions:**
  - "Zurueckgerufen" -- Markiert, dass der Kunde zurueckgerufen wurde
  - "Termin eingetragen" -- Markiert, dass der Termin im Kalender steht
  - "Erledigt" -- Markiert den Anruf als abgeschlossen
- **Notizfeld:** Freitext-Notizen pro Anruf

### Auto-Refresh

Das Dashboard aktualisiert sich automatisch alle 15 Sekunden per AJAX-Request. Neue Anrufe erscheinen sofort im Live-Feed, ohne die Seite neu laden zu muessen.

### Push-Notifications

- Nutzt die Web Push API mit VAPID-Schluesseln
- Benachrichtigt sofort bei neuen Anrufen
- **Hinweis:** Funktioniert nur ueber HTTPS (aktuell noch nicht konfiguriert)

---

## API Endpoints (Versicherung)

Alle Endpoints sind unter dem Praefix `/api/v/` erreichbar.

### Authentifizierung

Jeder Request muss authentifiziert sein. Zwei Moeglichkeiten:

1. **Header:** `X-Access-Token: <TOKEN>`
2. **Query-Parameter:** `?token=<TOKEN>`

### Endpoints

#### `GET /api/v/dashboard`

Dashboard-Uebersicht mit Statistiken und den letzten Anrufen.

**Response:**
```json
{
  "stats": {
    "total_calls": 42,
    "today_calls": 5,
    "categories": {
      "schaden": 12,
      "termin": 18,
      "frage": 12
    }
  },
  "recent_calls": [...]
}
```

#### `GET /api/v/anrufe`

Alle Anrufe mit optionalen Filtern.

**Query-Parameter:**
- `kategorie` -- Filter nach Kategorie (schaden, termin, frage)
- `status` -- Filter nach Status
- `datum_von` -- Startdatum (YYYY-MM-DD)
- `datum_bis` -- Enddatum (YYYY-MM-DD)
- `seite` -- Seitennummer fuer Pagination
- `limit` -- Anzahl pro Seite

**Response:**
```json
{
  "anrufe": [...],
  "total": 42,
  "seite": 1,
  "seiten_gesamt": 3
}
```

#### `GET /api/v/anrufe/<id>`

Detail-Ansicht eines einzelnen Anrufs inklusive vollstaendigem Transkript.

**Response:**
```json
{
  "id": 1,
  "anrufer_nummer": "+4917612345678",
  "anrufer_name": "Max Mustermann",
  "kategorie": "schaden",
  "zusammenfassung": "Wasserschaden in der Kueche...",
  "transkript": [
    {"rolle": "assistent", "text": "Guten Tag..."},
    {"rolle": "anrufer", "text": "Hallo, ich habe..."}
  ],
  "status": "neu",
  "notiz": null,
  "erstellt_am": "2026-02-15T10:30:00"
}
```

#### `POST /api/v/anrufe/<id>/status`

Status eines Anrufs aendern.

**Request Body:**
```json
{
  "status": "zurueckgerufen"
}
```

**Moegliche Status-Werte:** `neu`, `zurueckgerufen`, `termin_eingetragen`, `erledigt`

#### `POST /api/v/anrufe/<id>/notiz`

Notiz zu einem Anruf hinzufuegen oder aktualisieren.

**Request Body:**
```json
{
  "notiz": "Kunde wird morgen nochmal anrufen."
}
```

#### `GET /api/v/stats/weekly`

Wochenstatistik mit Anrufaufkommen pro Tag.

**Response:**
```json
{
  "woche": "2026-W07",
  "tage": [
    {"tag": "Montag", "datum": "2026-02-09", "anrufe": 8},
    {"tag": "Dienstag", "datum": "2026-02-10", "anrufe": 5}
  ],
  "gesamt": 35
}
```

---

## Technologie-Stack

| Komponente       | Technologie                                              |
|------------------|----------------------------------------------------------|
| **Server**       | Hetzner VPS (Ubuntu), IP: 46.225.107.174                |
| **PBX**          | Asterisk mit sipgate SIP-Trunk                          |
| **TTS (primaer)**| ElevenLabs Cloud (`eleven_flash_v2_5`)                  |
| **TTS (Fallback)**| Piper TTS (lokal, offline-faehig)                      |
| **STT**          | faster-whisper (Modell: `medium`, Device: `cpu`, Compute Type: `int8`) |
| **LLM**          | Anthropic Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) |
| **Backend**      | Flask (Python)                                           |
| **Datenbank**    | SQLite                                                   |
| **Frontend**     | Inline HTML/CSS/JS (kein Build-Prozess, PWA)            |
| **Design**       | Glassmorphism, Dark Theme (`#0a0e1a`)                   |
| **Notifications**| Telegram Bot API, Web Push (VAPID), sipgate SMS API     |
| **Music on Hold**| Custom Ambient Tracks (mit sox generiert)               |

### Warum diese Technologien?

- **ElevenLabs + Piper:** ElevenLabs liefert natuerlich klingende Stimmen, Piper sorgt fuer Zuverlaessigkeit bei API-Ausfaellen.
- **faster-whisper:** Schnellere Alternative zu OpenAI Whisper, optimiert fuer CPU-Betrieb mit int8-Quantisierung.
- **Claude Haiku 4.5:** Schnelles und kostenguenstiges LLM, ideal fuer Echtzeit-Gespraeche.
- **SQLite:** Kein separater Datenbankserver noetig, perfekt fuer den aktuellen Umfang.
- **Inline Frontend:** Keine Build-Pipeline, keine Node.js-Abhaengigkeit, einfaches Deployment.

---

## Greeting-Cache

Um die Antwortzeit beim ersten Anruf zu minimieren, werden Begrussungs-Audiodateien gecached.

### Funktionsweise

1. Beim ersten Anruf wird der Begrussungstext aus der Business-Config geladen
2. Ein MD5-Hash des Textes wird berechnet
3. Falls eine WAV-Datei mit diesem Hash im Cache existiert, wird sie direkt abgespielt
4. Falls nicht, wird die Begruessung per TTS generiert, als WAV gespeichert und dann abgespielt

### Cache-Pfad

```
/opt/ki-telefonassistent/audio/greeting_cache/
```

### Vorteile

- **Zeitersparnis:** 2+ Sekunden beim ersten Anruf (keine TTS-Generierung noetig)
- **Konsistenz:** Gleicher Text ergibt immer die gleiche Datei
- **Automatische Invalidierung:** Bei Aenderung des Begrussungstextes wird ein neuer Hash generiert und eine neue Datei erzeugt

### Dateiformat

```
greeting_cache/
  a1b2c3d4e5f6...md5hash.wav    # 8kHz, 16bit, mono (Asterisk-kompatibel)
```

---

## DID-Routing (config/did-routing.json)

Das DID-Routing ermoeglicht Multi-Tenant-Betrieb: Mehrere Unternehmen nutzen dasselbe System, die Zuordnung erfolgt ueber die angerufene Telefonnummer (DID = Direct Inward Dialing).

### Konfiguration

```json
{
  "default": "versicherung",
  "default_booking_business_id": 2,
  "routes": {
    "+4982826388978": {
      "business": "handwerk",
      "telegram_chat_id": "6859301779",
      "booking_business_id": 1
    },
    "+4982826388979": {
      "business": "versicherung",
      "booking_business_id": 2
    },
    "+4982826388980": {
      "business": "versicherung",
      "booking_business_id": 2
    }
  }
}
```

### Felder

| Feld                         | Beschreibung                                              |
|------------------------------|-----------------------------------------------------------|
| `default`                    | Standard-Business, falls DID nicht zugeordnet             |
| `default_booking_business_id`| Standard business_id fuer Buchungen                       |
| `routes`                     | Zuordnung DID -> Business-Konfiguration                   |
| `routes.*.business`          | Name der Business-Config (laedt `prompts/<name>.json`)    |
| `routes.*.telegram_chat_id`  | Telegram-Chat fuer Benachrichtigungen dieses Business     |
| `routes.*.booking_business_id`| ID des Business in der Booking-Datenbank                 |

### Ablauf

1. Asterisk uebergibt die angerufene Nummer (DID) an `agi_handler.py`
2. `config_loader.py` liest `did-routing.json`
3. Die DID wird im E.164-Format (`+49...`) in den Routes gesucht
4. Falls gefunden: Entsprechende Business-Config wird geladen
5. Falls nicht gefunden: Default-Business wird verwendet

---

## Wichtige Konfiguration (.env)

Die zentrale Konfigurationsdatei liegt unter `config/.env` und enthaelt alle sensiblen Zugangsdaten und Einstellungen.

### ElevenLabs (TTS)

```
ELEVENLABS_API_KEY=<API-Key>
ELEVENLABS_VOICE_ID=pMrwpTuGOma7Nubxs5jo
```

- Voice-ID verweist auf eine Community-Voice
- Modell: `eleven_flash_v2_5` (schnell, kostenguenstig)

### Anthropic (LLM)

```
ANTHROPIC_API_KEY=<API-Key>
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
```

### Telegram (Benachrichtigungen)

```
TELEGRAM_BOT_TOKEN=<Bot-Token>
TELEGRAM_ALLOWED_CHATS=<Chat-ID-1>,<Chat-ID-2>
```

### Whisper (STT)

```
WHISPER_MODEL=medium
WHISPER_DEVICE=cpu
```

- Medium-Modell bietet gute Balance zwischen Genauigkeit und Geschwindigkeit
- CPU-Betrieb, da der VPS keine GPU hat
- int8-Quantisierung reduziert Speicherverbrauch

### Web Push (VAPID)

```
VAPID_PUBLIC_KEY=<Public-Key>
VAPID_PRIVATE_KEY=<Private-Key>
```

- Generiert mit `pywebpush`
- Benoetigt HTTPS fuer die Auslieferung an den Browser

### sipgate (SMS)

```
SIPGATE_TOKEN_ID=<Token-ID>
SIPGATE_TOKEN=<Token>
```

- Fuer ausgehende SMS an Kunden nach Gespraechsende

---

## Bekannte Einschraenkungen

### Push-Notifications funktionieren nur mit HTTPS

Web Push Notifications (ueber die Push API / Service Worker) erfordern eine sichere HTTPS-Verbindung. Der Server ist aktuell noch nicht mit einem SSL-Zertifikat konfiguriert. Bis dahin funktionieren nur Telegram-Benachrichtigungen zuverlaessig.

**Loesung:** Let's Encrypt Zertifikat einrichten (certbot) und nginx als Reverse-Proxy vor Flask schalten.

### sipgate SMS gibt 401 zurueck

Die SMS-Funktion ueber die sipgate API gibt aktuell einen HTTP 401 Fehler zurueck (Unauthorized). Die Token-Berechtigungen im sipgate-Account muessen ueberprueft und ggf. neu konfiguriert werden.

**Zu pruefen:**
- Token-ID und Token korrekt in `.env`?
- Hat der Token die Berechtigung `sessions:sms:write`?
- Ist der richtige Web-SMS-Extension (`s0` etc.) konfiguriert?

### Whisper Medium Ladezeit

Das faster-whisper Medium-Modell benoetigt ca. 5 Sekunden zum Laden in den Speicher. Dies geschieht bewusst parallel zur Begruessung, sodass der Anrufer keine Verzoegerung bemerkt. Bei sehr kurzen Begruessungen kann es jedoch zu einer minimalen Wartezeit kommen.

**Moegliche Optimierung:** Modell dauerhaft im Speicher halten (persistenter Worker-Prozess statt Neustart pro Anruf).

### ElevenLabs Community-Voices

Community-Voices auf ElevenLabs koennen gelegentlich langsamer sein als professionelle Voices, da sie auf geteilter Infrastruktur laufen. In seltenen Faellen kann die Latenz 2-3 Sekunden betragen.

**Fallback:** Bei Timeout oder Fehler wird automatisch auf Piper (lokal) umgeschaltet, was eine unterbrechungsfreie Anruferfahrung gewaehrleistet.

---

## Neuen Kunden hinzufuegen

Anleitung zum Onboarding eines neuen Kunden (Business) auf dem System:

### Schritt 1: Business-Config erstellen

Eine neue JSON-Datei unter `prompts/` anlegen, z.B. `prompts/neuerkunde.json`:

```json
{
  "business_name": "Neuer Kunde GmbH",
  "greeting": "Guten Tag, Sie erreichen die Neuer Kunde GmbH. Wie kann ich Ihnen helfen?",
  "system_prompt": "Du bist ein freundlicher Telefonassistent fuer die Neuer Kunde GmbH...",
  "extraction_fields": ["name", "telefon", "anliegen"],
  "categories": ["anfrage", "beschwerde", "information"]
}
```

### Schritt 2: DID-Routing konfigurieren

In `config/did-routing.json` die neue Telefonnummer dem Business zuordnen:

```json
{
  "routes": {
    "+49XXXXXXXXXXX": {
      "business": "neuerkunde",
      "telegram_chat_id": "<CHAT_ID>",
      "booking_business_id": 3
    }
  }
}
```

### Schritt 3: Business in Datenbank anlegen

```bash
python manage_business.py --name "Neuer Kunde GmbH" --id 3
```

### Schritt 4: Dashboard erstellen (optional)

Falls der Kunde ein eigenes Dashboard benoetigt:

1. `src/neuerkunde_app.py` erstellen (Flask Blueprint fuer das Dashboard)
2. `src/neuerkunde_api.py` erstellen (Flask Blueprint fuer die API)
3. Sich an `versicherung_app.py` / `versicherung_api.py` als Vorlage orientieren

### Schritt 5: Blueprints registrieren

In `src/web_dashboard.py` die neuen Blueprints importieren und registrieren:

```python
from neuerkunde_app import neuerkunde_bp
from neuerkunde_api import neuerkunde_api_bp

app.register_blueprint(neuerkunde_bp)
app.register_blueprint(neuerkunde_api_bp)
```

### Schritt 6: Testen

1. Asterisk-Konfiguration pruefen (`extensions.conf`)
2. Testanruf auf die neue Nummer
3. Dashboard aufrufen und Anruf-Daten pruefen
4. Telegram-Benachrichtigung pruefen

---

## Systemadministration

### Services neustarten

```bash
# Asterisk neustarten
sudo systemctl restart asterisk

# Web-Dashboard neustarten
sudo systemctl restart ki-telefonassistent-web

# Logs anzeigen
sudo journalctl -u ki-telefonassistent-web -f
tail -f /opt/ki-telefonassistent/logs/agi.log
```

### Wichtige Pfade auf dem Server

| Pfad                                          | Beschreibung                    |
|-----------------------------------------------|---------------------------------|
| `/opt/ki-telefonassistent/`                  | Projektverzeichnis              |
| `/opt/ki-telefonassistent/audio/greeting_cache/` | Greeting-Cache             |
| `/opt/ki-telefonassistent/logs/`             | Log-Dateien                     |
| `/opt/ki-telefonassistent/config/.env`       | Umgebungsvariablen              |
| `/etc/asterisk/extensions.conf`              | Asterisk Dialplan               |
| `/etc/asterisk/sip.conf`                     | Asterisk SIP-Konfiguration      |

---
