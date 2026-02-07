#!/bin/bash
# ============================================================
# KI-Telefonassistent - VPS Installation (Cloud-Version)
# Für Hetzner, Netcup, Contabo etc.
# Ubuntu 22.04 / Debian 12
# ============================================================
# Benötigt: VPS mit mindestens 4 GB RAM, 2 vCPU
# Nutzt Cloud-KI (Groq/OpenAI/Gemini) statt lokalem LLM
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} KI-Telefonassistent - VPS Installation${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Prüfe Root-Rechte
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Bitte als root ausführen: sudo bash install_vps.sh${NC}"
    exit 1
fi

INSTALL_DIR="/opt/ki-telefonassistent"
VENV_DIR="$INSTALL_DIR/venv"

# -----------------------------------------------------------
# 1. System aktualisieren
# -----------------------------------------------------------
echo -e "${YELLOW}[1/6] System wird aktualisiert...${NC}"
apt update && apt upgrade -y

# -----------------------------------------------------------
# 2. Grundpakete installieren
# -----------------------------------------------------------
echo -e "${YELLOW}[2/6] Grundpakete werden installiert...${NC}"
apt install -y \
    python3 python3-pip python3-venv python3-dev \
    git curl wget ffmpeg sox libsox-fmt-all \
    build-essential pkg-config \
    sqlite3 libsqlite3-dev \
    nginx certbot python3-certbot-nginx \
    ufw

# -----------------------------------------------------------
# 3. Asterisk installieren
# -----------------------------------------------------------
echo -e "${YELLOW}[3/6] Asterisk wird installiert...${NC}"
apt install -y asterisk asterisk-dev
usermod -a -G audio asterisk

# -----------------------------------------------------------
# 4. Piper TTS installieren (Deutsche Sprachausgabe)
# -----------------------------------------------------------
echo -e "${YELLOW}[4/6] Piper TTS wird installiert...${NC}"
PIPER_DIR="/opt/piper"
mkdir -p "$PIPER_DIR"

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

# Deutsche Stimme herunterladen
VOICE_DIR="$PIPER_DIR/voices"
mkdir -p "$VOICE_DIR"
wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx" \
    -O "$VOICE_DIR/de_DE-thorsten-high.onnx"
wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx.json" \
    -O "$VOICE_DIR/de_DE-thorsten-high.onnx.json"

echo -e "${GREEN}Piper TTS mit deutscher Stimme installiert.${NC}"

# -----------------------------------------------------------
# 5. Python-Umgebung einrichten
# -----------------------------------------------------------
echo -e "${YELLOW}[5/6] Python-Umgebung wird eingerichtet...${NC}"
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
# 6. Projektdateien kopieren & Services einrichten
# -----------------------------------------------------------
echo -e "${YELLOW}[6/6] Projektdateien und Services...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cp -r "$PROJECT_DIR/src" "$INSTALL_DIR/"
cp -r "$PROJECT_DIR/config" "$INSTALL_DIR/"
cp -r "$PROJECT_DIR/prompts" "$INSTALL_DIR/"
mkdir -p "$INSTALL_DIR/audio"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/recordings"

# .env erstellen
if [ ! -f "$INSTALL_DIR/config/.env" ]; then
    cp "$INSTALL_DIR/config/.env.example" "$INSTALL_DIR/config/.env"
    echo -e "${YELLOW}Bitte config/.env anpassen!${NC}"
fi

# Berechtigungen
chown -R asterisk:asterisk "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

# Systemd Services
cat > /etc/systemd/system/ki-telefon.service << 'EOF'
[Unit]
Description=KI-Telefonassistent
After=network.target asterisk.service
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

cat > /etc/systemd/system/ki-telefon-web.service << 'EOF'
[Unit]
Description=KI-Telefonassistent Web-Dashboard
After=network.target ki-telefon.service

[Service]
Type=simple
User=asterisk
Group=asterisk
WorkingDirectory=/opt/ki-telefonassistent
ExecStart=/opt/ki-telefonassistent/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 2 src.web_dashboard:app
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

# -----------------------------------------------------------
# Firewall einrichten
# -----------------------------------------------------------
echo -e "${YELLOW}Firewall wird konfiguriert...${NC}"
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 5060/udp    # SIP
ufw allow 10000:20000/udp  # RTP (Audio)
ufw allow 80/tcp      # HTTP (für Nginx)
ufw allow 443/tcp     # HTTPS
ufw --force enable

# -----------------------------------------------------------
# Nginx Reverse Proxy für Dashboard
# -----------------------------------------------------------
echo -e "${YELLOW}Nginx wird konfiguriert...${NC}"
cat > /etc/nginx/sites-available/ki-telefon << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
EOF

ln -sf /etc/nginx/sites-available/ki-telefon /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} VPS-Installation abgeschlossen!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "Nächste Schritte:"
echo -e "  1. ${YELLOW}nano /opt/ki-telefonassistent/config/.env${NC}"
echo -e "     → GROQ_API_KEY eintragen (https://console.groq.com)"
echo -e "     → SIP-Zugangsdaten eintragen"
echo -e "  2. ${YELLOW}sudo bash /opt/ki-telefonassistent/scripts/setup_sip.sh${NC}"
echo -e "     → SIP-Trunk einrichten"
echo -e "  3. ${YELLOW}sudo systemctl start ki-telefon${NC}"
echo -e "  4. ${YELLOW}sudo systemctl start ki-telefon-web${NC}"
echo ""
echo -e "Dashboard: ${YELLOW}http://$(curl -s https://api.ipify.org 2>/dev/null || echo 'DEINE_SERVER_IP')${NC}"
echo -e "Logs:      ${YELLOW}journalctl -u ki-telefon -f${NC}"
echo ""
echo -e "${GREEN}Geschätzte monatliche Kosten:${NC}"
echo -e "  VPS (Hetzner CX22):  ~4€"
echo -e "  SIP-Trunk (sipgate):  ~0-3€"
echo -e "  Groq API:             0€ (kostenlos)"
echo -e "  ────────────────────────"
echo -e "  Gesamt:               ~4-7€/Monat"
