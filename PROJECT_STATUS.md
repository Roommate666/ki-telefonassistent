# KI-Telefonassistent - Projektstatus

**Letzte Aktualisierung:** 2026-02-04
**Bearbeitet von:** Claude (KI-Assistent)

---

## Projektbeschreibung

Ein KI-gestützter Telefonassistent für deutsche Unternehmen. Das System nimmt automatisch Anrufe entgegen, versteht gesprochene Sprache, generiert intelligente Antworten und spricht diese natürlich aus. Unterstützt verschiedene Branchen (Handwerk, Arztpraxis, Gastronomie, etc.).

**STATUS: LIVE UND FUNKTIONSFAEHIG**

---

## Aktueller Stand

### Erledigt (ALLES FUNKTIONIERT)
- [x] Projektstruktur erstellt (src/, config/, prompts/, scripts/, audio/, logs/, recordings/)
- [x] AGI-Handler (agi_handler.py) - Asterisk-Integration, Gesprächsschleife
- [x] LLM-Engine (llm_engine.py) - Multi-Provider: Groq, OpenAI, Gemini, Anthropic, Ollama
- [x] TTS-Engine (tts_engine.py) - Piper TTS mit deutscher Stimme (Thorsten)
- [x] STT-Engine (stt_engine.py) - Faster-Whisper mit VAD-Filter
- [x] Config-Loader (config_loader.py) - .env und Branchen-JSON laden
- [x] Datenbank (call_database.py) - SQLite für Anruf-Logs
- [x] Benachrichtigungen (notifications.py) - E-Mail + Telegram
- [x] Web-Dashboard (web_dashboard.py) - Flask-basiertes Monitoring
- [x] Branchen-Profile: handwerk, arztpraxis, gastronomie, friseur, kosmetik, immobilien, anwalt, bestattung
- [x] Asterisk SIP-Konfiguration (sip.conf) - sipgate + easybell Templates
- [x] Asterisk Dialplan (extensions.conf) - Eingehende Anrufe + AGI-Anbindung
- [x] Installations-Skripte (install.sh, install_vps.sh)
- [x] SIP-Setup-Skript (setup_sip.sh)
- [x] Groq API-Key erstellt und konfiguriert
- [x] Groq-Server integriert als LLM-Provider
- [x] **Termin- & Anfragen-Management App** (booking_database.py, booking_api.py, booking_dashboard.py)
- [x] **Betriebe-Datenbank** - Tabellen: businesses, services, appointments, inquiries
- [x] **REST-API** - Token-basierte Auth, CRUD fuer Termine/Anfragen/Dienstleistungen
- [x] **PWA-Dashboard fuer Betriebe** - Mobile-first, installierbar, Dark Theme
- [x] **Kunden-Benachrichtigungen** (customer_notifications.py) - SMS primaer (sipgate), E-Mail nur optional
- [x] **Admin-Tool** (scripts/manage_business.py) - Betriebe anlegen, Zugangslinks generieren
- [x] **AGI-Anbindung** - Termine/Anfragen aus Anrufen automatisch in Booking-DB anlegen
- [x] **Booking-Datenextraktion** (llm_engine.py) - Strukturierte Daten aus Gespraechen extrahieren (BOOKING_EXTRACTION_PROMPT)
- [x] **Erinnerungs-SMS** (scripts/send_reminders.py) - 24h vor Termin automatische SMS an Kunden
- [x] **Anruf-Bestaetigungs-SMS** - Sofort nach Anruf bekommt Kunde SMS: "Ihre Anfrage wurde aufgenommen"
- [x] **SIP-Provider konfiguriert** - System ist live
- [x] **Server deployed** - Laeuft auf Hetzner
- [x] **End-to-End Test erfolgreich** - Telefonate funktionieren

### Bekannte Themen
- [ ] Anfragen erscheinen manchmal nicht im Dashboard - pruefen ob BOOKING_BUSINESS_ID korrekt gesetzt ist

---

## Technologie-Stack

| Komponente | Technologie | Status |
|---|---|---|
| Telefonie/PBX | Asterisk | LIVE |
| SIP-Provider | sipgate | LIVE |
| LLM/KI | Groq (llama-3.1-8b-instant) | LIVE |
| Speech-to-Text | Faster-Whisper | LIVE |
| Text-to-Speech | Piper TTS (de_DE-thorsten-high) | LIVE |
| Datenbank | SQLite | LIVE |
| Web-Dashboard | Flask | LIVE |
| Benachrichtigung | E-Mail (SMTP) + Telegram | LIVE |
| Termin-App | Flask + PWA | LIVE |
| Kunden-SMS | sipgate REST API | LIVE |
| Betriebe-Auth | Token-basierter Link-Zugang | LIVE |

---

## SIP-Provider Status

### sipgate (Aktiv)
- **Status:** LIVE und funktionsfaehig
- **SIP-Server:** sipconnect.sipgate.de
- **SMS-API:** Aktiv fuer Kunden-Benachrichtigungen

---

## Dateistruktur

```
ki-telefonassistent/
├── PROJECT_STATUS.md           <- DIESE DATEI (immer aktuell halten!)
├── ANLEITUNG.md                # Deutsche Installationsanleitung
├── requirements.txt            # Python-Abhängigkeiten
├── config/
│   ├── .env.example            # Konfigurations-Template
│   └── asterisk/
│       ├── sip.conf            # SIP-Trunk Konfiguration
│       └── extensions.conf     # Asterisk Dialplan
├── src/
│   ├── __init__.py
│   ├── agi_handler.py          # Asterisk AGI - Herzstück (Gesprächsschleife)
│   ├── call_database.py        # SQLite Datenbank (Anrufe)
│   ├── config_loader.py        # .env + JSON Config laden
│   ├── llm_engine.py           # LLM Multi-Provider (Groq, OpenAI, Gemini, etc.)
│   ├── main.py                 # Haupteinstiegspunkt
│   ├── notifications.py        # E-Mail + Telegram (intern, fuer Betreiber)
│   ├── stt_engine.py           # Speech-to-Text (Faster-Whisper)
│   ├── tts_engine.py           # Text-to-Speech (Piper TTS)
│   ├── web_dashboard.py        # Flask Web-Dashboard (Admin + Booking-Blueprints)
│   ├── booking_database.py     # [NEU] SQLite Tabellen: businesses, services, appointments, inquiries
│   ├── booking_api.py          # [NEU] REST-API fuer Terminverwaltung (Token-Auth)
│   ├── booking_dashboard.py    # [NEU] PWA-Frontend fuer Betriebe
│   └── customer_notifications.py # [NEU] Kunden-Benachrichtigung (E-Mail + sipgate SMS)
├── prompts/                    # Branchen-Profile (JSON)
│   ├── handwerk.json, arztpraxis.json, gastronomie.json, ...
├── scripts/
│   ├── install.sh              # Installations-Skript
│   ├── install_vps.sh          # VPS-optimierte Installation
│   ├── setup_sip.sh            # SIP-Setup Wizard
│   ├── new_business.sh         # Neues Branchen-Profil erstellen
│   ├── manage_business.py      # [NEU] Admin-Tool: Betriebe anlegen/verwalten
│   └── send_reminders.py      # [NEU] Cron-Job: Erinnerungs-SMS 24h vor Termin
├── audio/                      # Temporäre Audio-Dateien
├── logs/                       # Log-Dateien + calls.db
└── recordings/                 # Anruf-Aufnahmen
```

---

## Architektur-Ablauf

```
Anruf kommt rein
    ↓
Asterisk nimmt an (extensions.conf → [eingehend])
    ↓
AGI-Skript wird gestartet (agi_handler.py)
    ↓
Begrüßung generieren (Piper TTS) → Abspielen
    ↓
┌─── Gesprächsschleife (max 20 Runden) ───┐
│  1. Zuhören (Asterisk RECORD)            │
│  2. Sprache → Text (Faster-Whisper)      │
│  3. Text → KI-Antwort (Groq/LLM)        │
│  4. Antwort → Sprache (Piper TTS)        │
│  5. Abspielen                            │
│  6. Tschüss erkannt? → Beenden           │
└──────────────────────────────────────────┘
    ↓
Zusammenfassung erstellen (LLM)
    ↓
In Datenbank speichern (SQLite)
    ↓
Benachrichtigung senden (E-Mail/Telegram)
    ↓
Auflegen + Aufräumen
```

---

## Wichtige Konfigurationswerte

### Groq (LLM - bereits konfiguriert)
- Provider: `groq`
- Modell: `llama-3.1-8b-instant`
- API-URL: `https://api.groq.com/openai/v1/chat/completions`
- Kostenlos, sehr schnell (~0.2s pro Antwort)

### sipgate (SIP - noch einzutragen)
- Host: `sipconnect.sipgate.de`
- Port: `5060`
- Tarif: trunking 2 free (2 Kanäle, kostenlos)

### Piper TTS
- Stimme: `de_DE-thorsten-high` (deutsche Männerstimme)
- Format: 8kHz, Mono, 16-bit PCM (Asterisk-kompatibel via sox)

### Faster-Whisper
- Modell: `small` (für VPS) oder `medium`/`large` (lokal)
- Sprache: `de`
- VAD-Filter: aktiviert

---

## Termin- & Anfragen-Management App (NEU)

### Konzept
PWA-App (installierbar als App ueber Link) fuer Betriebe. Jeder Betrieb bekommt ein Paket passend zu seiner Branche - man sieht NUR das was fuer die eigene Branche relevant ist.

### Zwei Modi (automatisch je nach Branchentyp)

**Termin-Modus** (friseur, kosmetik, beauty, massage, barbershop, tattoo, piercing, spa, wellness, physiotherapie, heilpraktiker):
- Nav: Start | Termine | Angebote | Mehr
- Dashboard: Neue Termine, Bestaetigte, Abgelehnte
- Termin-Cards: Kundenname, Telefon (Mobil/Festnetz Badge), Wunsch-Stylist, Behandlung, Wunschtermin
- Aktionen: Bestaetigen, Ablehnen, Verschieben
- Dienstleistungen verwalten (Name, Dauer, Preis)

**Auftrags-Modus** (handwerk, und alle die nicht in Termin-Typen sind):
- Nav: Start | Anfragen | Angebote | Mehr
- Dashboard: Neue Anfragen, In Bearbeitung, Erledigt
- Anfrage-Cards: Kundenname, Adresse, Problembeschreibung, Kategorie, Dringlichkeit
- Aktionen: Reagieren (Status, Antwort, Kosten, Termin), Anrufen
- Leistungen/Angebote verwalten

### Festnetz-Erkennung
- Telefonnummern werden automatisch erkannt (015x/016x/017x = Mobil, alles andere = Festnetz)
- Mobilnummer: SMS-Bestaetigung wird automatisch gesendet
- Festnetz: Orange "Festnetz" Badge + Warnung "Kein SMS moeglich" + "Anrufen"-Button (tel:-Link)
- callback_required Flag wird automatisch gesetzt

### Technische Umsetzung
- `src/booking_database.py` - SQLite-Tabellen mit phone_type, mode, callback_required Feldern
- `src/booking_api.py` - Flask Blueprint REST-API mit Token-Auth, gibt mode zurueck
- `src/booking_dashboard.py` - PWA mit dynamischem UI je nach mode (buildNav() baut komplett andere Navigation)
- `src/customer_notifications.py` - SMS primaer (nur bei Mobil), E-Mail nur wenn manuell eingetragen
- `scripts/manage_business.py` - CLI-Tool, mode wird automatisch aus Branchentyp abgeleitet

### Status
- [x] Datenbank-Schema (businesses mit mode, appointments mit phone_type/preferred_staff, inquiries mit phone_type)
- [x] Backend-API mit mode-Rueckgabe
- [x] PWA-Dashboard mit zwei komplett verschiedenen Modi
- [x] Festnetz-Erkennung + Rueckruf-Hinweise
- [x] SMS nur bei Mobilnummern, Festnetz = Betrieb muss anrufen
- [x] Admin-Tool mit automatischer Modus-Erkennung
- [x] Anbindung an KI-Telefonassistent (Termine aus Anrufen automatisch anlegen)
- [x] Erinnerungs-SMS 24h vor Termin (Cron-Job: scripts/send_reminders.py)
- [x] **Suchfunktion** in PWA-Dashboard (Name, Telefon, Datum, Beschreibung)
- [x] **Verschieben-Button** mit Modal (Datum + Uhrzeit, Festnetz-Hinweis)
- [x] **Anruf-Zusammenfassung** in Termin-/Anfrage-Cards (call_summary Feld)
- [x] **Betriebsnotizen** editierbar in jeder Card (business_notes Feld)
- [x] **Rueckruf-Tracking** fuer Festnetz (Erledigt-Button, callback_done Status)
- [x] **Duplikat-Warnung** bei gleicher Telefonnummer (mehrere aktive Eintraege)

### Zugang fuer Betriebe
1. Admin legt Betrieb an: `python scripts/manage_business.py add "Salon Anna" friseur`
   -> Modus "termin" wird automatisch erkannt
2. Oder: `python scripts/manage_business.py add "Mueller Haustechnik" handwerk`
   -> Modus "auftrag" wird automatisch erkannt
3. System generiert Zugangslink: `https://server/app?token=XXXXX`
4. Betrieb oeffnet Link -> sieht NUR sein branchenspezifisches Dashboard
5. Kann als App installiert werden (PWA)

---

## Hinweise fuer die naechste KI-Session

**SYSTEM IST LIVE - Alle Grundfunktionen laufen!**

1. **System laeuft auf Hetzner** - Server deployed und funktionsfaehig
2. **sipgate aktiv** - SIP-Trunk + SMS-API funktionieren
3. **Groq integriert** - LLM-Engine laeuft
4. **Termin-App ist live** - PWA mit zwei Modi (termin/auftrag), Festnetz-Erkennung, SMS nur bei Mobil
5. **Jeder Betrieb sieht NUR sein Paket** - Friseur sieht Termine, Handwerker sieht Anfragen
6. **BOOKING_BUSINESS_ID** - In .env muss die ID des Betriebs aus der businesses-Tabelle eingetragen werden
7. **Erinnerungs-SMS** - Cron-Job `scripts/send_reminders.py` taeglich um 18 Uhr ausfuehren, sendet SMS 24h vor Termin
8. **Betrieb anlegen** - `python scripts/manage_business.py add "Name" typ` generiert Zugangslink
9. **PWA-Zugang** - Betriebe oeffnen `/app?token=XXX` und koennen die Seite als App installieren
10. **Suchfunktion** - Im Termine/Anfragen-Tab: Echtzeit-Suche nach Name, Telefonnummer, Datum, Beschreibung
11. **Verschieben-Button** - Direkt in jeder Termin-Card, oeffnet Modal mit Datum+Uhrzeit, sendet SMS
12. **Betriebsnotizen** - Klick auf "Notizen" oeffnet Textfeld, Speichern per API
13. **Anruf-Zusammenfassung** - Blaue Box in der Card zeigt das Anliegen des Anrufers
14. **Rueckruf-Tracking** - Festnetz-Kunden: Orange-Box mit "Erledigt"-Button
15. **Duplikat-Warnung** - Gelbe Warnung wenn Telefonnummer bereits aktive Eintraege hat
16. **Anruf-Bestaetigungs-SMS** - Direkt nach dem Anruf bekommt der Kunde eine SMS (nur bei Mobilnummern)

### Debugging: Anfrage erscheint nicht im Dashboard?
1. Pruefe ob `BOOKING_BUSINESS_ID` in `.env` gesetzt ist
2. Pruefe die Logs: `/opt/ki-telefonassistent/logs/agi.log`
3. Pruefe ob `has_booking_request` vom LLM erkannt wurde
