# KI-Telefonassistent - Installationsanleitung

## Was ist das?

Ein KI-basierter Anrufbeantworter, der:
- Anrufe automatisch entgegennimmt
- Den Anrufer versteht (Sprache → Text)
- Intelligent antwortet (lokales KI-Modell)
- Natürlich klingende Antworten spricht (Text → Sprache)
- Alles protokolliert (Web-Dashboard)
- Für jede Branche konfigurierbar ist

**Laufende Kosten: ca. 5-15€/Monat** (nur SIP-Trunk + Strom)

---

## Schritt 1: Hardware besorgen

### Empfehlung: Gebrauchter Mini-PC

Suche auf eBay Kleinanzeigen nach:
- **Lenovo ThinkCentre M920q / M720q**
- **Dell OptiPlex Micro 7060 / 7070**
- **HP ProDesk 400 G5 Mini**

**Mindestanforderungen:**
- CPU: Intel i5 (8. Generation oder neuer)
- RAM: 16 GB
- SSD: 128 GB
- Preis: ca. 80-120€ gebraucht

**Optional (für schnellere KI):**
- Gebrauchte GPU: NVIDIA RTX 3060 (~150€ gebraucht)
- Dann einen normalen Tower-PC statt Mini-PC nehmen

---

## Schritt 2: Linux installieren

1. **Ubuntu 22.04 LTS** herunterladen:
   https://ubuntu.com/download/desktop

2. USB-Stick erstellen mit **Rufus** (Windows):
   https://rufus.ie

3. Vom USB-Stick booten und Ubuntu installieren
   - "Minimale Installation" wählen
   - Benutzername und Passwort merken!

4. Nach der Installation - Terminal öffnen und System updaten:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

---

## Schritt 3: Projekt auf den Linux-PC kopieren

Den gesamten Ordner `ki-telefonassistent` auf einen USB-Stick kopieren
und dann auf dem Linux-PC einfügen, z.B. nach `/home/deinname/`.

Oder per Git (wenn du ein Repository hast):
```bash
cd /home/deinname/
git clone DEIN_REPO_URL ki-telefonassistent
```

---

## Schritt 4: Installation ausführen

```bash
cd /home/deinname/ki-telefonassistent
sudo bash scripts/install.sh
```

Das Skript installiert automatisch:
- Asterisk (Telefonanlage)
- Ollama + Llama 3.1 (KI-Modell, ~4.7 GB Download)
- Piper TTS (Deutsche Stimme)
- Faster-Whisper (Spracherkennung)
- Alle Python-Abhängigkeiten

**Achtung:** Der Download des KI-Modells kann je nach Internet 10-30 Minuten dauern.

---

## Schritt 5: SIP-Trunk einrichten

### Option A: sipgate (empfohlen für den Start)

1. Gehe zu https://www.sipgate.de/basic
2. Erstelle einen **kostenlosen** Account
3. Du bekommst eine Telefonnummer
4. Im Dashboard: **Telefonie → SIP-Credentials** notieren

### Option B: easybell

1. Gehe zu https://www.easybell.de
2. Wähle einen VoIP-Tarif (ab ~1€/Monat)
3. Im Kundenportal: SIP-Zugangsdaten notieren

### Konfiguration

Entweder den Assistenten nutzen:
```bash
sudo bash /opt/ki-telefonassistent/scripts/setup_sip.sh
```

Oder manuell in der .env Datei:
```bash
sudo nano /opt/ki-telefonassistent/config/.env
```

Dort eintragen:
```
SIP_PROVIDER=sipgate
SIP_USERNAME=deine_sip_id
SIP_PASSWORD=dein_sip_passwort
SIP_HOST=sipconnect.sipgate.de
```

---

## Schritt 6: Branche konfigurieren

### Vorhandene Branchen (sofort nutzbar)

| Dateiname | Branche |
|-----------|---------|
| `handwerk.json` | Handwerk / Haustechnik |
| `arztpraxis.json` | Arztpraxis |
| `gastronomie.json` | Restaurant / Gasthof |
| `friseur.json` | Friseursalon |
| `kosmetik.json` | Kosmetik / Nagelstudio |
| `immobilien.json` | Immobilienmakler |
| `anwalt.json` | Rechtsanwalt |
| `bestattung.json` | Bestattungsinstitut |

### Branche aktivieren

In `/opt/ki-telefonassistent/config/.env`:
```
ACTIVE_BUSINESS=handwerk
```

### Branche anpassen

Die Branchen-Dateien liegen in `/opt/ki-telefonassistent/prompts/`.
Bearbeite die JSON-Datei deiner Branche:

```bash
sudo nano /opt/ki-telefonassistent/prompts/handwerk.json
```

Dort anpassen:
- `company_name` → Dein Firmenname
- `address` → Deine Adresse
- `phone` → Deine Telefonnummer
- `opening_hours` → Deine Öffnungszeiten
- `services` → Deine Dienstleistungen
- `faq` → Häufige Fragen deiner Kunden
- `greeting` → Begrüßungstext

### Neue Branche erstellen

```bash
sudo bash /opt/ki-telefonassistent/scripts/new_business.sh
```

Oder einfach eine vorhandene JSON-Datei kopieren und anpassen:
```bash
cd /opt/ki-telefonassistent/prompts/
sudo cp handwerk.json autowerkstatt.json
sudo nano autowerkstatt.json
```

---

## Schritt 7: System starten

```bash
# KI-Telefonassistent starten
sudo systemctl start ki-telefon

# Web-Dashboard starten
sudo systemctl start ki-telefon-web

# Status prüfen
sudo systemctl status ki-telefon
sudo systemctl status ki-telefon-web
```

### Dashboard öffnen

Im Browser auf dem Linux-PC:
```
http://localhost:5000
```

Oder von einem anderen PC im Netzwerk:
```
http://IP_DES_LINUX_PCS:5000
```

(IP herausfinden mit: `ip addr | grep inet`)

---

## Schritt 8: Router konfigurieren (Port-Forwarding)

Damit Anrufe von außen ankommen, muss dein Router den SIP-Traffic durchlassen.

In deinem Router (z.B. Fritz!Box):
1. Internet → Freigaben → Gerät für Freigaben hinzufügen
2. Dein Linux-PC auswählen
3. Ports freigeben:
   - **UDP 5060** (SIP)
   - **UDP 10000-20000** (RTP/Audio)

### Fritz!Box spezifisch:
- Telefonie → Eigene Rufnummern → Neue Rufnummer
- Art: "Internetrufnummer"
- SIP-Daten eintragen

---

## Testen

### 1. Asterisk prüfen
```bash
# SIP-Registrierung prüfen
sudo asterisk -rx "sip show registry"

# SIP-Peers anzeigen
sudo asterisk -rx "sip show peers"
```

### 2. Testanruf machen
Rufe einfach die Telefonnummer an, die du bei sipgate/easybell bekommen hast.

### 3. Logs anschauen
```bash
# Live-Log des Assistenten
sudo journalctl -u ki-telefon -f

# Asterisk-Log
sudo asterisk -rvvv
```

---

## Fehlerbehebung

### "Ollama nicht erreichbar"
```bash
sudo systemctl start ollama
sudo systemctl status ollama
```

### "Whisper-Modell lädt nicht"
Evtl. zu wenig RAM. Kleineres Modell nutzen:
In `.env`: `WHISPER_MODEL=small` (statt medium)

### "Keine Anrufe kommen an"
1. SIP-Registrierung prüfen: `sudo asterisk -rx "sip show registry"`
2. Firewall prüfen: `sudo ufw status`
3. Ports freigeben: `sudo ufw allow 5060/udp && sudo ufw allow 10000:20000/udp`

### "Audio klingt schlecht"
- Codec prüfen: alaw sollte aktiv sein
- Netzwerk: LAN-Kabel statt WLAN verwenden

---

## Projektstruktur

```
ki-telefonassistent/
├── config/
│   ├── .env.example          # Konfigurationsvorlage
│   └── asterisk/
│       ├── sip.conf           # SIP-Trunk Konfiguration
│       └── extensions.conf    # Asterisk Dialplan
├── prompts/
│   ├── handwerk.json          # Branchen-Konfigurationen
│   ├── arztpraxis.json
│   ├── gastronomie.json
│   ├── friseur.json
│   ├── kosmetik.json
│   ├── immobilien.json
│   ├── anwalt.json
│   └── bestattung.json
├── src/
│   ├── main.py                # Hauptprogramm
│   ├── agi_handler.py         # Asterisk AGI (Anruf-Logik)
│   ├── config_loader.py       # Konfiguration laden
│   ├── stt_engine.py          # Spracherkennung (Whisper)
│   ├── llm_engine.py          # KI-Antworten (Ollama)
│   ├── tts_engine.py          # Sprachausgabe (Piper)
│   ├── call_database.py       # Anruf-Datenbank
│   └── web_dashboard.py       # Web-Dashboard
├── scripts/
│   ├── install.sh             # Installations-Skript
│   ├── setup_sip.sh           # SIP-Einrichtung
│   └── new_business.sh        # Neue Branche erstellen
├── audio/                     # Temporäre Audio-Dateien
├── logs/                      # Log-Dateien + Datenbank
├── recordings/                # Anruf-Aufnahmen
└── ANLEITUNG.md               # Diese Datei
```
