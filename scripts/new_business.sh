#!/bin/bash
# ============================================================
# Neue Branche hinzufügen
# Erstellt eine neue Branchen-Konfiguration aus einer Vorlage
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PROMPTS_DIR="/opt/ki-telefonassistent/prompts"

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  Neue Branche hinzufügen${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Bestehende Branchen anzeigen
echo "Vorhandene Branchen:"
for f in "$PROMPTS_DIR"/*.json; do
    name=$(basename "$f" .json)
    company=$(python3 -c "import json; print(json.load(open('$f'))['company_name'])" 2>/dev/null || echo "?")
    echo "  - $name ($company)"
done
echo ""

# Neue Branche
read -p "Name der neuen Branche (z.B. 'zahnarzt', 'autowerkstatt'): " BUSINESS_NAME
BUSINESS_NAME=$(echo "$BUSINESS_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '_' | tr -cd 'a-z0-9_')

if [ -f "$PROMPTS_DIR/$BUSINESS_NAME.json" ]; then
    echo -e "${YELLOW}Branche '$BUSINESS_NAME' existiert bereits!${NC}"
    exit 1
fi

# Firmendetails abfragen
echo ""
read -p "Firmenname: " COMPANY_NAME
read -p "Branche/Beschreibung: " INDUSTRY
read -p "Adresse: " ADDRESS
read -p "Telefon: " PHONE
read -p "E-Mail: " EMAIL

echo ""
echo "Begrüßungstext (1-2 Sätze):"
read -p "> " GREETING

# JSON erstellen
cat > "$PROMPTS_DIR/$BUSINESS_NAME.json" << HEREDOC
{
    "company_name": "$COMPANY_NAME",
    "industry": "$INDUSTRY",
    "address": "$ADDRESS",
    "phone": "$PHONE",
    "email": "$EMAIL",
    "website": "",

    "greeting": "$GREETING",

    "opening_hours": {
        "Montag - Freitag": "08:00 - 17:00 Uhr",
        "Samstag": "Geschlossen",
        "Sonntag": "Geschlossen"
    },

    "services": [
        "Dienstleistung 1 - bitte anpassen",
        "Dienstleistung 2 - bitte anpassen",
        "Dienstleistung 3 - bitte anpassen"
    ],

    "important_info": [
        "Wichtige Info 1 - bitte anpassen",
        "Wichtige Info 2 - bitte anpassen"
    ],

    "behavior_rules": [
        "Bei Terminanfragen: Name und Telefonnummer erfragen",
        "Freundlich und professionell kommunizieren",
        "Bei Fragen die nicht beantwortet werden koennen: Rueckruf anbieten"
    ],

    "faq": [
        {
            "question": "Beispielfrage?",
            "answer": "Beispielantwort - bitte anpassen"
        }
    ],

    "custom_instructions": ""
}
HEREDOC

echo ""
echo -e "${GREEN}Branche '$BUSINESS_NAME' erstellt!${NC}"
echo -e "Datei: ${CYAN}$PROMPTS_DIR/$BUSINESS_NAME.json${NC}"
echo ""
echo "Nächste Schritte:"
echo -e "  1. ${YELLOW}nano $PROMPTS_DIR/$BUSINESS_NAME.json${NC}"
echo "     → Öffnungszeiten, Dienstleistungen, FAQ anpassen"
echo -e "  2. ${YELLOW}In .env: ACTIVE_BUSINESS=$BUSINESS_NAME${NC}"
echo -e "  3. ${YELLOW}sudo systemctl restart ki-telefon${NC}"
