# KI-Telefonassistent

Ein KI-basierter Telefonassistent fuer deutsche Unternehmen. Nimmt Anrufe automatisch entgegen, versteht gesprochene Sprache, antwortet intelligent und erstellt Termine/Anfragen — alles vollautomatisch.

**Laufende Kosten: ca. 5-15 EUR/Monat** (SIP-Trunk + Server)

---

## Features

### Telefonie
- Automatische Anrufannahme ueber Asterisk PBX
- Spracherkennung (Faster-Whisper) und natuerliche Sprachausgabe (Piper TTS / ElevenLabs)
- Multi-Provider LLM: Groq (kostenlos), OpenAI, Google Gemini, Anthropic, Ollama (lokal)
- Automatischer Fallback bei Rate-Limits (Groq gross → Groq klein → Gemini)
- Barge-In: Anrufer kann die KI jederzeit unterbrechen
- IVR-Kategorien (z.B. Heizung / Sanitaer / Sonstiges)

### Termin- & Anfragen-Management
- **Zwei Modi** — automatisch nach Branchentyp:
  - **Termin-Modus**: Friseur, Kosmetik, Gastronomie, Restaurant, Hotel, Massage, etc.
  - **Auftrags-Modus**: Handwerk, Reparatur, allgemeine Anfragen
- Termine/Anfragen werden automatisch aus Telefongespraechen extrahiert
- Personenanzahl-Erkennung bei Gastronomie-Reservierungen
- Festnetz/Mobil-Erkennung (SMS nur bei Mobilnummern)

### Business-Dashboard (PWA)
- Mobile-first, installierbar als App
- Dark Theme, Echtzeit-Updates via SSE
- Branchenspezifische Ansicht (Friseur sieht Termine, Handwerker sieht Anfragen)
- Termin bestaetigen / ablehnen / verschieben
- Suchfunktion, Betriebsnotizen, Rueckruf-Tracking
- Duplikat-Warnung bei gleicher Telefonnummer

### Kunden-Portal (PWA)
- Jeder Kunde bekommt nach dem Anruf einen persoenlichen Link per SMS
- Stammkunden-Erkennung (gleiche Nummer + gleicher Betrieb = gleicher Token)
- Reservierungen einsehen, stornieren oder Aenderung anfragen
- Visueller Uhrzeit-Picker (15-Min-Slots) und Kalender-Auswahl
- Bei jeder Aktion: SMS an Kunde UND an Betrieb

### Benachrichtigungen
- **SMS** (sipgate API): Anruf-Bestaetigung, Termin-Updates, Erinnerung 24h vorher
- **Portal-Link** in jeder SMS fuer direkten Zugang zum Kunden-Portal
- **E-Mail** (SMTP): Optional als Zusatzkanal
- **Telegram**: Echtzeit-Benachrichtigung fuer den Betreiber

### Onboarding
- Interaktiver Wizard oder CLI-Modus
- Erstellt Betrieb in der Datenbank + Prompt-Profil in einem Schritt
- Setzt optional ACTIVE_BUSINESS und BOOKING_BUSINESS_ID in .env

---

## Unterstuetzte Branchen

| Branche | Modus | Profil |
|---------|-------|--------|
| Handwerk / Haustechnik | Auftrag | `handwerk.json` |
| Arztpraxis | Auftrag | `arztpraxis.json` |
| Gastronomie | Termin | `gastronomie.json` |
| Friseur | Termin | `friseur.json` |
| Kosmetik / Nagelstudio | Termin | `kosmetik.json` |
| Immobilienmakler | Auftrag | `immobilien.json` |
| Rechtsanwalt | Auftrag | `anwalt.json` |
| Bestattungsinstitut | Auftrag | `bestattung.json` |
| **Kupferdaechle** (Demo) | Termin | `kupferdaechle.json` |

Neue Branchen lassen sich einfach per JSON-Datei oder Onboarding-Script erstellen.

---

## Schnellstart

### 1. Installation (Linux-Server)

```bash
git clone https://github.com/Roommate666/ki-telefonassistent.git
cd ki-telefonassistent
sudo bash scripts/install.sh
```

### 2. Konfiguration

```bash
cp config/.env.example config/.env
nano config/.env
```

Mindestens eintragen:
- `SIP_USERNAME` / `SIP_PASSWORD` (von sipgate oder easybell)
- `GROQ_API_KEY` (kostenlos: https://console.groq.com)
- `ACTIVE_BUSINESS` (z.B. `handwerk`, `friseur`, `kupferdaechle`)

### 3. Betrieb einrichten

```bash
# Interaktiver Wizard
python scripts/onboard.py

# Oder per CLI
python scripts/onboard.py \
    --name "kupferdaechle" \
    --type gastronomie \
    --company "Cafe und Restaurant Kupferdaechle" \
    --owner "Markus Keder" \
    --phone "08282 1474" \
    --address "Badweg 23, 86381 Krumbach" \
    --set-active
```

### 4. Starten

```bash
sudo systemctl start ki-telefon
sudo systemctl start ki-telefon-web
```

Dashboard: `http://SERVER_IP:5000`

---

## Architektur

```
Anruf kommt rein
    |
Asterisk nimmt an (extensions.conf)
    |
AGI-Handler startet (agi_handler.py)
    |
Begruessung generieren (TTS) --> Abspielen
    |
+--- Gespraechsschleife (max 20 Runden) ---+
|  1. Zuhoeren (Asterisk RECORD)            |
|  2. Sprache -> Text (Faster-Whisper)      |
|  3. Text -> KI-Antwort (Groq/LLM)        |
|  4. Antwort -> Sprache (Piper TTS)        |
|  5. Abspielen                             |
|  6. Tschuess erkannt? -> Beenden          |
+-------------------------------------------+
    |
Booking-Daten extrahieren (LLM)
    |
Termin/Anfrage in DB anlegen + Kunden-Token generieren
    |
SMS-Bestaetigung mit Portal-Link senden
    |
Benachrichtigung (E-Mail/Telegram)
    |
Auflegen
```

---

## Projektstruktur

```
ki-telefonassistent/
├── config/
│   ├── .env.example              # Konfigurations-Template
│   └── asterisk/
│       ├── sip.conf              # SIP-Trunk Konfiguration
│       └── extensions.conf       # Asterisk Dialplan
├── prompts/                      # Branchen-Profile (JSON)
│   ├── handwerk.json
│   ├── gastronomie.json
│   ├── friseur.json
│   ├── kupferdaechle.json        # Demo: Restaurant in Krumbach
│   └── ...
├── src/
│   ├── agi_handler.py            # Asterisk AGI - Gespraechsschleife
│   ├── llm_engine.py             # Multi-Provider LLM (Groq, OpenAI, Gemini, etc.)
│   ├── stt_engine.py             # Speech-to-Text (Faster-Whisper)
│   ├── tts_engine.py             # Text-to-Speech (Piper / ElevenLabs)
│   ├── config_loader.py          # .env + JSON Config laden
│   ├── call_database.py          # Anruf-Datenbank (SQLite)
│   ├── booking_database.py       # Termine, Anfragen, Betriebe, Kunden-Tokens
│   ├── booking_api.py            # REST-API fuer Betriebe (Token-Auth)
│   ├── booking_dashboard.py      # Business-Dashboard (PWA)
│   ├── customer_api.py           # REST-API fuer Kunden-Portal
│   ├── customer_portal.py        # Kunden-Portal (PWA)
│   ├── customer_notifications.py # SMS + E-Mail an Kunden
│   ├── web_dashboard.py          # Admin-Dashboard + Blueprint-Registry
│   ├── notifications.py          # E-Mail + Telegram (intern)
│   └── address_validator.py      # Adress-Validierung
├── scripts/
│   ├── onboard.py                # Onboarding-Wizard (interaktiv + CLI)
│   ├── manage_business.py        # Betriebe verwalten
│   ├── send_reminders.py         # Erinnerungs-SMS (Cron-Job)
│   ├── install.sh                # Installations-Script
│   ├── install_vps.sh            # VPS-optimierte Installation
│   ├── setup_sip.sh              # SIP-Einrichtung
│   └── deploy_hetzner.sh         # Hetzner-Deployment
└── logs/                         # SQLite-DB + Logs (nicht im Repo)
```

---

## Technologie-Stack

| Komponente | Technologie |
|---|---|
| Telefonie/PBX | Asterisk |
| SIP-Provider | sipgate / easybell |
| LLM/KI | Groq, OpenAI, Gemini, Anthropic, Ollama |
| Speech-to-Text | Faster-Whisper |
| Text-to-Speech | Piper TTS / ElevenLabs |
| Datenbank | SQLite (WAL-Modus) |
| Web-Framework | Flask |
| Dashboards | PWA (Progressive Web App) |
| SMS | sipgate REST API |
| Benachrichtigung | SMTP E-Mail, Telegram Bot |

---

## API-Endpunkte

### Business-Dashboard (`/api/booking/`)
Token-Auth per `?token=BUSINESS_TOKEN`

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| GET | `/api/booking/appointments` | Termine auflisten |
| PUT | `/api/booking/appointments/<id>/status` | Status aendern |
| GET | `/api/booking/inquiries` | Anfragen auflisten |
| PUT | `/api/booking/inquiries/<id>/status` | Status aendern |
| GET | `/api/booking/services` | Dienstleistungen |
| GET | `/api/booking/stats` | Statistiken |

### Kunden-Portal (`/api/kunde/`)
Token-Auth per `?t=CUSTOMER_TOKEN`

| Methode | Endpunkt | Beschreibung |
|---------|----------|-------------|
| GET | `/api/kunde/reservierungen` | Alle Reservierungen |
| POST | `/api/kunde/reservierungen/<id>/stornieren` | Stornieren |
| POST | `/api/kunde/reservierungen/<id>/aendern` | Aenderungswunsch |

---

## Lokales Testen (Windows/Mac)

Pfade sind per Umgebungsvariable ueberschreibbar:

```bash
# Umgebungsvariablen setzen
export KI_BASE_DIR=/pfad/zum/projekt
export KI_DB_PATH=/pfad/zum/projekt/logs/calls.db

# Oder einfach das Test-Script nutzen:
python test_local.py
```

Das Onboarding-Script setzt die Pfade automatisch fuer lokalen Betrieb.

---

## Erinnerungs-SMS einrichten

Cron-Job fuer taegliche Erinnerungen 24h vor Termin:

```bash
# Crontab oeffnen
crontab -e

# Taeglich um 18:00 Uhr ausfuehren
0 18 * * * /usr/bin/python3 /opt/ki-telefonassistent/scripts/send_reminders.py
```

---

## Lizenz

Dieses Projekt ist fuer den privaten und geschaeftlichen Einsatz bestimmt.

---

## Mitwirken

Issues und Pull Requests sind willkommen.
