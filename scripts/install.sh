#!/bin/bash
# ============================================================
# KI-Telefonassistent - Installations-Skript
# Für Ubuntu 22.04 / Debian 12
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} KI-Telefonassistent - Installation${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Prüfe Root-Rechte
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Bitte als root ausführen: sudo bash install.sh${NC}"
    exit 1
fi

INSTALL_DIR="/opt/ki-telefonassistent"
VENV_DIR="$INSTALL_DIR/venv"

# -----------------------------------------------------------
# 1. System aktualisieren
# -----------------------------------------------------------
echo -e "${YELLOW}[1/8] System wird aktualisiert...${NC}"
apt update && apt upgrade -y

# -----------------------------------------------------------
# 2. Grundpakete installieren
# -----------------------------------------------------------
echo -e "${YELLOW}[2/8] Grundpakete werden installiert...${NC}"
apt install -y \
    python3 python3-pip python3-venv python3-dev \
    git curl wget ffmpeg sox libsox-fmt-all \
    build-essential pkg-config \
    sqlite3 libsqlite3-dev \
    nginx certbot

# -----------------------------------------------------------
# 3. Asterisk installieren
# -----------------------------------------------------------
echo -e "${YELLOW}[3/8] Asterisk wird installiert...${NC}"
apt install -y asterisk asterisk-dev

# Asterisk-Benutzer konfigurieren
usermod -a -G audio asterisk

# -----------------------------------------------------------
# 4. Ollama installieren (Lokales LLM)
# -----------------------------------------------------------
echo -e "${YELLOW}[4/8] Ollama wird installiert...${NC}"
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi

# Deutsches Modell herunterladen (Llama 3.1 8B - gut für Deutsch)
echo -e "${YELLOW}Lade KI-Modell herunter (kann dauern)...${NC}"
ollama pull llama3.1:8b

# -----------------------------------------------------------
# 5. Piper TTS installieren (Deutsche Sprachausgabe)
# -----------------------------------------------------------
echo -e "${YELLOW}[5/8] Piper TTS wird installiert...${NC}"
PIPER_DIR="/opt/piper"
mkdir -p "$PIPER_DIR"

# Piper Binary herunterladen
PIPER_VERSION="2023.11.14-2"
ARCH=$(dpkg --print-architecture)
if [ "$ARCH" = "amd64" ]; then
    PIPER_ARCH="amd64"
elif [ "$ARCH" = "arm64" ]; then
    PIPER_ARCH="arm64"
else
    PIPER_ARCH="amd64"
fi

wget -q "https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_linux_${PIPER_ARCH}.tar.gz" \
    -O /tmp/piper.tar.gz
tar -xzf /tmp/piper.tar.gz -C "$PIPER_DIR" --strip-components=1
rm /tmp/piper.tar.gz

# Deutsche Stimme herunterladen (Thorsten - natürlich klingende deutsche Stimme)
VOICE_DIR="$PIPER_DIR/voices"
mkdir -p "$VOICE_DIR"
wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx" \
    -O "$VOICE_DIR/de_DE-thorsten-high.onnx"
wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx.json" \
    -O "$VOICE_DIR/de_DE-thorsten-high.onnx.json"

echo -e "${GREEN}Piper TTS mit deutscher Stimme installiert.${NC}"

# -----------------------------------------------------------
# 6. Faster-Whisper installieren (Speech-to-Text)
# -----------------------------------------------------------
echo -e "${YELLOW}[6/8] Python-Umgebung wird eingerichtet...${NC}"
mkdir -p "$INSTALL_DIR"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install \
    faster-whisper \
    requests \
    flask \
    flask-cors \
    python-dotenv \
    pyst2 \
    asterisk-ami \
    pydub \
    soundfile \
    numpy \
    schedule \
    gunicorn

deactivate
echo -e "${GREEN}Python-Umgebung eingerichtet.${NC}"

# -----------------------------------------------------------
# 7. Projektdateien kopieren
# -----------------------------------------------------------
echo -e "${YELLOW}[7/8] Projektdateien werden kopiert...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cp -r "$PROJECT_DIR/src" "$INSTALL_DIR/"
cp -r "$PROJECT_DIR/config" "$INSTALL_DIR/"
cp -r "$PROJECT_DIR/prompts" "$INSTALL_DIR/"
mkdir -p "$INSTALL_DIR/audio"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/recordings"

# .env Datei erstellen falls nicht vorhanden
if [ ! -f "$INSTALL_DIR/config/.env" ]; then
    cp "$INSTALL_DIR/config/.env.example" "$INSTALL_DIR/config/.env"
    echo -e "${YELLOW}Bitte config/.env anpassen!${NC}"
fi

# Berechtigungen setzen
chown -R asterisk:asterisk "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

# -----------------------------------------------------------
# 8. Systemd Services einrichten
# -----------------------------------------------------------
echo -e "${YELLOW}[8/8] Systemd Services werden eingerichtet...${NC}"

# Hauptdienst
cat > /etc/systemd/system/ki-telefon.service << 'EOF'
[Unit]
Description=KI-Telefonassistent
After=network.target asterisk.service ollama.service
Requires=asterisk.service

[Service]
Type=simple
User=asterisk
Group=asterisk
WorkingDirectory=/opt/ki-telefonassistent
ExecStart=/opt/ki-telefonassistent/venv/bin/python /opt/ki-telefonassistent/src/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Web-Dashboard Service
cat > /etc/systemd/system/ki-telefon-web.service << 'EOF'
[Unit]
Description=KI-Telefonassistent Web-Dashboard
After=network.target ki-telefon.service

[Service]
Type=simple
User=asterisk
Group=asterisk
WorkingDirectory=/opt/ki-telefonassistent
ExecStart=/opt/ki-telefonassistent/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 src.web_dashboard:app
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ki-telefon.service
systemctl enable ki-telefon-web.service
systemctl enable asterisk.service

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} Installation abgeschlossen!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "Nächste Schritte:"
echo -e "  1. ${YELLOW}nano /opt/ki-telefonassistent/config/.env${NC}"
echo -e "     → SIP-Zugangsdaten eintragen"
echo -e "  2. ${YELLOW}nano /opt/ki-telefonassistent/config/business.json${NC}"
echo -e "     → Firmendaten anpassen"
echo -e "  3. ${YELLOW}sudo systemctl start ki-telefon${NC}"
echo -e "     → Dienst starten"
echo -e "  4. ${YELLOW}sudo systemctl start ki-telefon-web${NC}"
echo -e "     → Web-Dashboard starten (Port 5000)"
echo ""
echo -e "Logs ansehen: ${YELLOW}journalctl -u ki-telefon -f${NC}"
echo -e "Dashboard:    ${YELLOW}http://localhost:5000${NC}"
