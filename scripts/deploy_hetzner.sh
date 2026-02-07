#!/bin/bash
# ============================================================
# KI-Telefonassistent - Hetzner VPS Deployment
# Server: 78.47.249.176 (CX23, Ubuntu, Nuernberg)
# sipgate Trunk: Room8 (trunking 2 free)
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

INSTALL_DIR="/opt/ki-telefonassistent"
VENV_DIR="$INSTALL_DIR/venv"
SERVER_IP="78.47.249.176"

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} KI-Telefonassistent - Hetzner Deployment${NC}"
echo -e "${GREEN} Server: $SERVER_IP${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# Root-Check
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Bitte als root ausfuehren: sudo bash deploy_hetzner.sh${NC}"
    exit 1
fi

# -----------------------------------------------------------
# 1. System aktualisieren
# -----------------------------------------------------------
echo -e "${YELLOW}[1/9] System wird aktualisiert...${NC}"
export DEBIAN_FRONTEND=noninteractive
apt update && apt upgrade -y

# -----------------------------------------------------------
# 2. Grundpakete installieren
# -----------------------------------------------------------
echo -e "${YELLOW}[2/9] Grundpakete werden installiert...${NC}"
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
echo -e "${YELLOW}[3/9] Asterisk wird installiert...${NC}"
apt install -y asterisk asterisk-dev
usermod -a -G audio asterisk

# -----------------------------------------------------------
# 4. Piper TTS installieren (Deutsche Sprachausgabe)
# -----------------------------------------------------------
echo -e "${YELLOW}[4/9] Piper TTS wird installiert...${NC}"
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

if [ ! -f "$PIPER_DIR/piper" ]; then
    wget -q "https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_linux_${PIPER_ARCH}.tar.gz" \
        -O /tmp/piper.tar.gz
    tar -xzf /tmp/piper.tar.gz -C "$PIPER_DIR" --strip-components=1
    rm -f /tmp/piper.tar.gz
fi

VOICE_DIR="$PIPER_DIR/voices"
mkdir -p "$VOICE_DIR"
if [ ! -f "$VOICE_DIR/de_DE-thorsten-high.onnx" ]; then
    wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx" \
        -O "$VOICE_DIR/de_DE-thorsten-high.onnx"
    wget -q "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx.json" \
        -O "$VOICE_DIR/de_DE-thorsten-high.onnx.json"
fi
echo -e "${GREEN}Piper TTS installiert.${NC}"

# -----------------------------------------------------------
# 5. Python-Umgebung einrichten
# -----------------------------------------------------------
echo -e "${YELLOW}[5/9] Python-Umgebung wird eingerichtet...${NC}"
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
    pydub \
    soundfile \
    numpy \
    gunicorn

deactivate
echo -e "${GREEN}Python-Umgebung eingerichtet.${NC}"

# -----------------------------------------------------------
# 6. Projektdateien kopieren
# -----------------------------------------------------------
echo -e "${YELLOW}[6/9] Projektdateien werden kopiert...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Quellcode kopieren
cp -r "$PROJECT_DIR/src" "$INSTALL_DIR/"
cp -r "$PROJECT_DIR/config" "$INSTALL_DIR/"
cp -r "$PROJECT_DIR/prompts" "$INSTALL_DIR/"
cp -r "$PROJECT_DIR/scripts" "$INSTALL_DIR/"
mkdir -p "$INSTALL_DIR/audio"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/recordings"

echo -e "${GREEN}Projektdateien kopiert.${NC}"

# -----------------------------------------------------------
# 7. Konfiguration: .env + Asterisk
# -----------------------------------------------------------
echo -e "${YELLOW}[7/9] Konfiguration wird erstellt...${NC}"

# .env mit sipgate Credentials erstellen
cat > "$INSTALL_DIR/config/.env" << 'ENVEOF'
# ============================================================
# KI-Telefonassistent - Produktions-Konfiguration
# Server: 78.47.249.176 (Hetzner CX23)
# ============================================================

# --- SIP-Trunk: sipgate (Room8, trunking 2 free) ---
SIP_PROVIDER=sipgate
SIP_USERNAME=3951721t0
SIP_PASSWORD=k64MG2m2XFZi
SIP_HOST=sipconnect.sipgate.de
SIP_PORT=5060

# --- KI-Provider ---
# Groq ist kostenlos und schnell - API Key holen: https://console.groq.com
LLM_PROVIDER=groq
GROQ_API_KEY=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
GROQ_MODEL=llama-3.1-8b-instant

# --- Piper TTS ---
PIPER_PATH=/opt/piper/piper
PIPER_VOICE=/opt/piper/voices/de_DE-thorsten-high.onnx

# --- Whisper STT ---
WHISPER_MODEL=small
WHISPER_LANGUAGE=de
WHISPER_DEVICE=cpu

# --- Allgemeine Einstellungen ---
LOG_LEVEL=INFO
RECORDINGS_DIR=/opt/ki-telefonassistent/recordings
AUDIO_DIR=/opt/ki-telefonassistent/audio
MAX_CALL_DURATION=300
SILENCE_TIMEOUT=5
GREETING_DELAY=1

# --- Web-Dashboard ---
WEB_HOST=0.0.0.0
WEB_PORT=5000
WEB_DEBUG=false
ADMIN_PASSWORD=Millionen11768381-$

# --- Aktive Branche ---
ACTIVE_BUSINESS=handwerk

# --- Booking-System ---
BOOKING_BUSINESS_ID=0

# --- E-Mail (optional) ---
EMAIL_ENABLED=false
# EMAIL_SMTP_HOST=smtp.gmail.com
# EMAIL_SMTP_PORT=587
# EMAIL_SMTP_USER=
# EMAIL_SMTP_PASS=
# EMAIL_FROM=
# EMAIL_TO=

# --- Telegram (optional) ---
TELEGRAM_ENABLED=false
# TELEGRAM_BOT_TOKEN=
# TELEGRAM_CHAT_ID=
ENVEOF

# Asterisk SIP-Konfiguration mit echten sipgate-Daten
cat > /etc/asterisk/sip.conf << SIPEOF
; ============================================================
; Asterisk SIP-Konfiguration - KI-Telefonassistent
; sipgate Trunk: Room8 (trunking 2 free)
; Server: 78.47.249.176
; ============================================================

[general]
context=default
allowoverlap=no
udpbindaddr=0.0.0.0
tcpenable=yes
tcpbindaddr=0.0.0.0
transport=udp
srvlookup=yes
language=de
tonezone=de

; NAT-Einstellungen (Hetzner = oeffentliche IP direkt)
nat=force_rport,comedia
externip=${SERVER_IP}
localnet=127.0.0.1/32

; Codecs
disallow=all
allow=alaw
allow=ulaw
allow=gsm

; Sicherheit
alwaysauthreject=yes

; Registrierung bei sipgate
register => 3951721t0:k64MG2m2XFZi@sipconnect.sipgate.de/ki-assistent

; ============================================================
; sipgate Trunk
; ============================================================
[sipgate]
type=peer
host=sipconnect.sipgate.de
username=3951721t0
secret=k64MG2m2XFZi
fromuser=3951721t0
fromdomain=sipconnect.sipgate.de
insecure=port,invite
context=eingehend
dtmfmode=rfc2833
disallow=all
allow=alaw
allow=ulaw
qualify=yes
nat=force_rport,comedia
directmedia=no
canreinvite=no
SIPEOF

# Asterisk Dialplan
cp "$PROJECT_DIR/config/asterisk/extensions.conf" /etc/asterisk/extensions.conf

echo -e "${GREEN}Konfiguration erstellt.${NC}"

# -----------------------------------------------------------
# 8. Berechtigungen + Firewall
# -----------------------------------------------------------
echo -e "${YELLOW}[8/9] Berechtigungen und Firewall...${NC}"

# Berechtigungen
chown -R asterisk:asterisk "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

# Firewall konfigurieren
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp        # HTTP (Nginx)
ufw allow 443/tcp       # HTTPS (Nginx + Certbot)
ufw allow 5060/udp      # SIP Signaling
ufw allow 5060/tcp      # SIP Signaling TCP
ufw allow 10000:20000/udp  # RTP Audio
echo "y" | ufw enable

echo -e "${GREEN}Firewall aktiviert.${NC}"

# -----------------------------------------------------------
# 9. Systemd Services + Nginx
# -----------------------------------------------------------
echo -e "${YELLOW}[9/9] Services werden eingerichtet...${NC}"

# ki-telefon-web Service (Dashboard + Booking App)
cat > /etc/systemd/system/ki-telefon-web.service << 'EOF'
[Unit]
Description=KI-Telefonassistent Web-Dashboard
After=network.target

[Service]
Type=simple
User=asterisk
Group=asterisk
WorkingDirectory=/opt/ki-telefonassistent
ExecStart=/opt/ki-telefonassistent/venv/bin/gunicorn --bind 127.0.0.1:5000 --workers 2 --timeout 120 src.web_dashboard:app
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Nginx Reverse Proxy
cat > /etc/nginx/sites-available/ki-telefonassistent << NGINXEOF
server {
    listen 80;
    server_name ${SERVER_IP};

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
NGINXEOF

# Nginx aktivieren
ln -sf /etc/nginx/sites-available/ki-telefonassistent /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

# Services starten
systemctl daemon-reload
systemctl enable asterisk.service
systemctl enable ki-telefon-web.service
systemctl restart asterisk
systemctl start ki-telefon-web.service

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN} Deployment abgeschlossen!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${BLUE}Server-Daten:${NC}"
echo -e "  IP:          ${SERVER_IP}"
echo -e "  Dashboard:   http://${SERVER_IP}"
echo -e "  Booking-App: http://${SERVER_IP}/app?token=XXXXX"
echo ""
echo -e "${BLUE}sipgate-Daten:${NC}"
echo -e "  SIP-ID:      3951721t0"
echo -e "  Registrar:   sipconnect.sipgate.de"
echo -e "  Nummern:     08282-6388978, -979, -980"
echo ""
echo -e "${YELLOW}WICHTIG - Noch zu tun:${NC}"
echo ""
echo -e "  1. ${YELLOW}Groq API Key eintragen:${NC}"
echo -e "     nano /opt/ki-telefonassistent/config/.env"
echo -e "     -> GROQ_API_KEY=dein_key (https://console.groq.com)"
echo ""
echo -e "  2. ${YELLOW}Admin-Passwort setzen:${NC}"
echo -e "     In der gleichen .env Datei:"
echo -e "     -> ADMIN_PASSWORD=dein_sicheres_passwort"
echo ""
echo -e "  3. ${YELLOW}Asterisk SIP-Status pruefen:${NC}"
echo -e "     asterisk -rx 'sip show peers'"
echo -e "     -> sipgate sollte 'OK' zeigen"
echo ""
echo -e "  4. ${YELLOW}Web-Service neustarten nach .env Aenderungen:${NC}"
echo -e "     systemctl restart ki-telefon-web"
echo ""
echo -e "  5. ${YELLOW}Ersten Betrieb anlegen:${NC}"
echo -e "     cd /opt/ki-telefonassistent"
echo -e "     ./venv/bin/python scripts/manage_business.py add \"Mein Betrieb\" handwerk"
echo -e "     -> Notiere dir den Token-Link!"
echo ""
echo -e "  6. ${YELLOW}Testanruf machen:${NC}"
echo -e "     Ruf 08282-6388978 an und teste den Assistenten"
echo ""
echo -e "${BLUE}Nuetzliche Befehle:${NC}"
echo -e "  Logs:          journalctl -u ki-telefon-web -f"
echo -e "  AGI-Logs:      tail -f /opt/ki-telefonassistent/logs/agi.log"
echo -e "  SIP-Status:    asterisk -rx 'sip show peers'"
echo -e "  SIP-Registry:  asterisk -rx 'sip show registry'"
echo -e "  Asterisk-CLI:  asterisk -rvvv"
echo -e "  Neustart:      systemctl restart ki-telefon-web asterisk"
echo ""
