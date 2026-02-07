#!/bin/bash
# ============================================================
# SIP-Trunk Einrichtungsassistent
# Hilft bei der Konfiguration von sipgate oder easybell
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_DIR="/opt/ki-telefonassistent"
ASTERISK_CONF="/etc/asterisk"

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  SIP-Trunk Einrichtungsassistent${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Provider auswählen
echo "Welchen SIP-Provider möchtest du verwenden?"
echo "  1) sipgate (empfohlen - kostenlose Basisversion)"
echo "  2) easybell (günstig, ab ~1€/Monat)"
echo "  3) Anderer Provider (manuell)"
echo ""
read -p "Auswahl [1/2/3]: " PROVIDER_CHOICE

case $PROVIDER_CHOICE in
    1)
        PROVIDER="sipgate"
        SIP_HOST="sipconnect.sipgate.de"
        echo ""
        echo -e "${GREEN}sipgate ausgewählt.${NC}"
        echo ""
        echo "So richtest du sipgate ein:"
        echo "  1. Gehe zu https://www.sipgate.de/basic"
        echo "  2. Erstelle einen kostenlosen Account"
        echo "  3. Im Dashboard: Telefonie → SIP-Credentials"
        echo "  4. Notiere SIP-ID und SIP-Passwort"
        echo ""
        ;;
    2)
        PROVIDER="easybell"
        SIP_HOST="sip.easybell.de"
        echo ""
        echo -e "${GREEN}easybell ausgewählt.${NC}"
        echo ""
        echo "So richtest du easybell ein:"
        echo "  1. Gehe zu https://www.easybell.de"
        echo "  2. Wähle einen VoIP-Tarif"
        echo "  3. Im Kundenportal: Telefonnummern → SIP-Daten"
        echo "  4. Notiere SIP-Benutzername und Passwort"
        echo ""
        ;;
    3)
        PROVIDER="custom"
        read -p "SIP-Host (z.B. sip.provider.de): " SIP_HOST
        echo ""
        ;;
esac

# Zugangsdaten abfragen
read -p "SIP-Benutzername: " SIP_USER
read -s -p "SIP-Passwort: " SIP_PASS
echo ""

# .env aktualisieren
ENV_FILE="$INSTALL_DIR/config/.env"
if [ -f "$ENV_FILE" ]; then
    # Vorhandene .env aktualisieren
    sed -i "s|^SIP_PROVIDER=.*|SIP_PROVIDER=$PROVIDER|" "$ENV_FILE"
    sed -i "s|^SIP_USERNAME=.*|SIP_USERNAME=$SIP_USER|" "$ENV_FILE"
    sed -i "s|^SIP_PASSWORD=.*|SIP_PASSWORD=$SIP_PASS|" "$ENV_FILE"
    sed -i "s|^SIP_HOST=.*|SIP_HOST=$SIP_HOST|" "$ENV_FILE"
else
    cp "$INSTALL_DIR/config/.env.example" "$ENV_FILE"
    sed -i "s|^SIP_PROVIDER=.*|SIP_PROVIDER=$PROVIDER|" "$ENV_FILE"
    sed -i "s|^SIP_USERNAME=.*|SIP_USERNAME=$SIP_USER|" "$ENV_FILE"
    sed -i "s|^SIP_PASSWORD=.*|SIP_PASSWORD=$SIP_PASS|" "$ENV_FILE"
    sed -i "s|^SIP_HOST=.*|SIP_HOST=$SIP_HOST|" "$ENV_FILE"
fi

# Asterisk SIP-Konfiguration aktualisieren
SIP_CONF="$ASTERISK_CONF/sip.conf"
if [ -f "$INSTALL_DIR/config/asterisk/sip.conf" ]; then
    cp "$INSTALL_DIR/config/asterisk/sip.conf" "$SIP_CONF"

    # Platzhalter ersetzen
    sed -i "s|SIP_USERNAME|$SIP_USER|g" "$SIP_CONF"
    sed -i "s|SIP_PASSWORD|$SIP_PASS|g" "$SIP_CONF"

    # Provider-spezifische Konfiguration aktivieren
    if [ "$PROVIDER" = "easybell" ]; then
        # sipgate auskommentieren, easybell aktivieren
        sed -i '/^\[sipgate\]/,/^$/s/^/;/' "$SIP_CONF"
        sed -i '/^;\[easybell\]/,/^$/s/^;//' "$SIP_CONF"
    fi
fi

# Extensions kopieren
cp "$INSTALL_DIR/config/asterisk/extensions.conf" "$ASTERISK_CONF/extensions.conf"

# Externe IP ermitteln
echo ""
echo -e "${YELLOW}Ermittle öffentliche IP-Adresse...${NC}"
EXTERNAL_IP=$(curl -s https://api.ipify.org 2>/dev/null || echo "NICHT_ERMITTELT")

if [ "$EXTERNAL_IP" != "NICHT_ERMITTELT" ]; then
    sed -i "s|DEINE_OEFFENTLICHE_IP|$EXTERNAL_IP|" "$SIP_CONF"
    echo -e "${GREEN}Öffentliche IP: $EXTERNAL_IP${NC}"
else
    echo -e "${YELLOW}IP konnte nicht ermittelt werden. Bitte manuell in $SIP_CONF eintragen.${NC}"
fi

# Lokales Netzwerk ermitteln
LOCAL_NET=$(ip route | grep -oP 'src \K\S+' | head -1 || echo "")
if [ -n "$LOCAL_NET" ]; then
    echo -e "${GREEN}Lokale IP: $LOCAL_NET${NC}"
fi

# Asterisk neu laden
echo ""
echo -e "${YELLOW}Lade Asterisk-Konfiguration neu...${NC}"
asterisk -rx "sip reload" 2>/dev/null || systemctl restart asterisk

# Registrierung prüfen
sleep 3
echo ""
echo -e "${YELLOW}Prüfe SIP-Registrierung...${NC}"
REG_STATUS=$(asterisk -rx "sip show registry" 2>/dev/null || echo "Nicht verfügbar")
echo "$REG_STATUS"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  SIP-Einrichtung abgeschlossen!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Teste die Verbindung mit:"
echo -e "  ${CYAN}asterisk -rx 'sip show peers'${NC}"
echo -e "  ${CYAN}asterisk -rx 'sip show registry'${NC}"
echo ""
echo "Starte den Assistenten mit:"
echo -e "  ${CYAN}sudo systemctl start ki-telefon${NC}"
