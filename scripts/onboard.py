#!/usr/bin/env python3
"""
Onboarding-Wizard: Neuen Betrieb in einem Schritt einrichten.

Interaktiver Modus:
    python scripts/onboard.py

CLI-Modus:
    python scripts/onboard.py --name "kupferdaechle" --type gastronomie \\
        --company "Cafe & Restaurant Kupferdaechle" --owner "Markus Keder" \\
        --phone "08282 1474" --address "Badweg 23, 86381 Krumbach" --set-active
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Projekt-Root zum Python-Path hinzufuegen
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Wenn KI_BASE_DIR/KI_DB_PATH nicht gesetzt, automatisch auf Projekt-Root setzen (lokaler Modus)
if not os.environ.get("KI_BASE_DIR"):
    os.environ["KI_BASE_DIR"] = str(PROJECT_ROOT)
if not os.environ.get("KI_DB_PATH"):
    db_path = PROJECT_ROOT / "logs" / "calls.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    os.environ["KI_DB_PATH"] = str(db_path)

from src.booking_database import init_booking_tables, create_business, list_businesses
from src.config_loader import list_available_businesses

PROMPTS_DIR = PROJECT_ROOT / "prompts"
CONFIG_DIR = PROJECT_ROOT / "config"


def get_available_templates():
    """Listet alle verfuegbaren Branchen-Templates auf."""
    templates = []
    if PROMPTS_DIR.exists():
        for f in sorted(PROMPTS_DIR.glob("*.json")):
            templates.append(f.stem)
    return templates


def interactive_wizard():
    """Interaktiver Onboarding-Wizard."""
    print("\n" + "=" * 60)
    print("  KI-Telefonassistent - Neuen Betrieb einrichten")
    print("=" * 60)

    # 1. Interner Name (fuer Dateien und Config)
    print("\n--- Schritt 1: Interner Name ---")
    print("Kurzer Name ohne Sonderzeichen (wird fuer Dateinamen verwendet)")
    name = input("Interner Name (z.B. kupferdaechle): ").strip()
    if not name:
        print("Abgebrochen.")
        return

    # 2. Branchentyp
    print("\n--- Schritt 2: Branchentyp ---")
    templates = get_available_templates()
    if templates:
        print("Vorhandene Templates:")
        for i, t in enumerate(templates, 1):
            print(f"  {i}. {t}")
    btype = input("Branchentyp (z.B. gastronomie, friseur, handwerk): ").strip()
    if not btype:
        print("Abgebrochen.")
        return

    # 3. Firmenname
    print("\n--- Schritt 3: Firmendaten ---")
    company = input("Firmenname (vollstaendig): ").strip() or name
    owner = input("Ansprechpartner/Inhaber: ").strip()
    phone = input("Telefonnummer: ").strip()
    address = input("Adresse (Strasse, PLZ Ort): ").strip()
    email = input("E-Mail (optional): ").strip()

    # 4. Zusammenfassung
    print("\n--- Zusammenfassung ---")
    print(f"  Interner Name: {name}")
    print(f"  Branchentyp:   {btype}")
    print(f"  Firmenname:    {company}")
    print(f"  Inhaber:       {owner or '-'}")
    print(f"  Telefon:       {phone or '-'}")
    print(f"  Adresse:       {address or '-'}")
    print(f"  E-Mail:        {email or '-'}")

    confirm = input("\nAlles korrekt? (j/n): ").strip().lower()
    if confirm not in ("j", "ja", "y", "yes"):
        print("Abgebrochen.")
        return

    # Betrieb erstellen
    result = setup_business(
        name=name,
        business_type=btype,
        company_name=company,
        owner_name=owner,
        phone=phone,
        address=address,
        email=email,
    )

    if not result:
        return

    # 5. Als aktiven Betrieb setzen?
    set_active = input("\nAls aktiven Betrieb setzen? (j/n): ").strip().lower()
    if set_active in ("j", "ja", "y", "yes"):
        update_env(name, result["id"])

    print("\n" + "=" * 60)
    print("  Onboarding abgeschlossen!")
    print("=" * 60)


def setup_business(name, business_type, company_name, owner_name="",
                   phone="", address="", email=""):
    """Erstellt den Betrieb in der Datenbank und prueft das Prompt-Profil."""
    init_booking_tables()

    # Pruefen ob Prompt-Profil existiert
    prompt_file = PROMPTS_DIR / f"{name}.json"
    if prompt_file.exists():
        print(f"\nPrompt-Profil gefunden: {prompt_file}")
    else:
        # Pruefen ob es ein Template fuer den Branchentyp gibt
        template_file = PROMPTS_DIR / f"{business_type}.json"
        if template_file.exists():
            print(f"\nKein eigenes Profil fuer '{name}' gefunden.")
            print(f"Template '{business_type}' wird als Basis verwendet.")
            create_prompt_from_template(template_file, prompt_file, company_name, phone, address)
        else:
            print(f"\nKein Prompt-Profil und kein Template gefunden.")
            print(f"Erstelle minimales Profil unter: {prompt_file}")
            create_minimal_prompt(prompt_file, company_name, business_type, phone, address)

    # Business in der Datenbank anlegen
    result = create_business(
        name=company_name,
        business_type=business_type,
        owner_name=owner_name,
        email=email,
        phone=phone,
        address=address,
    )

    base_url = "http://localhost:5000"
    env_path = CONFIG_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                if line.strip().startswith("WEB_BASE_URL="):
                    val = line.strip().split("=", 1)[1].strip()
                    if val:
                        base_url = val
                    break

    link = f"{base_url}/app?token={result['access_token']}"

    print(f"\nBetrieb erstellt!")
    print(f"  ID:         {result['id']}")
    print(f"  Name:       {company_name}")
    print(f"  Typ:        {business_type}")
    print(f"  Modus:      {result['mode']}")
    print(f"  Token:      {result['access_token']}")
    print(f"\nDashboard-Link:")
    print(f"  {link}")

    return result


def create_prompt_from_template(template_file, output_file, company_name, phone, address):
    """Erstellt ein Prompt-Profil aus einem bestehenden Template."""
    with open(template_file, "r", encoding="utf-8") as f:
        template = json.load(f)

    template["company_name"] = company_name
    if phone:
        template["phone"] = phone
    if address:
        template["address"] = address

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=4)

    print(f"  Profil erstellt: {output_file}")
    print(f"  HINWEIS: Bitte passe die Details in {output_file} manuell an!")


def create_minimal_prompt(output_file, company_name, business_type, phone, address):
    """Erstellt ein minimales Prompt-Profil."""
    profile = {
        "company_name": company_name,
        "industry": business_type.capitalize(),
        "address": address or "Nicht angegeben",
        "phone": phone or "Nicht angegeben",
        "greeting": f"Guten Tag, {company_name}. Leider koennen wir gerade nicht persoenlich ans Telefon gehen. Ich bin der digitale Assistent. Wie kann ich Ihnen helfen?",
        "opening_hours": {},
        "services": [],
        "important_info": [],
        "behavior_rules": [
            "MAXIMAL 2 Saetze pro Antwort",
            "Telefonnummer NICHT erfragen - die kommt automatisch"
        ],
        "faq": [],
        "custom_instructions": ""
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=4)

    print(f"  Minimales Profil erstellt: {output_file}")
    print(f"  HINWEIS: Bitte fuege Oeffnungszeiten, Services und FAQs manuell hinzu!")


def update_env(business_name, business_id):
    """Aktualisiert ACTIVE_BUSINESS und BOOKING_BUSINESS_ID in der .env Datei."""
    env_path = CONFIG_DIR / ".env"

    if not env_path.exists():
        print(f"  WARNUNG: {env_path} nicht gefunden. Bitte manuell setzen:")
        print(f"    ACTIVE_BUSINESS={business_name}")
        print(f"    BOOKING_BUSINESS_ID={business_id}")
        return

    with open(env_path, "r") as f:
        lines = f.readlines()

    updated_active = False
    updated_booking = False
    new_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("ACTIVE_BUSINESS="):
            new_lines.append(f"ACTIVE_BUSINESS={business_name}\n")
            updated_active = True
        elif stripped.startswith("BOOKING_BUSINESS_ID="):
            new_lines.append(f"BOOKING_BUSINESS_ID={business_id}\n")
            updated_booking = True
        else:
            new_lines.append(line)

    if not updated_active:
        new_lines.append(f"ACTIVE_BUSINESS={business_name}\n")
    if not updated_booking:
        new_lines.append(f"BOOKING_BUSINESS_ID={business_id}\n")

    with open(env_path, "w") as f:
        f.writelines(new_lines)

    print(f"\n  .env aktualisiert:")
    print(f"    ACTIVE_BUSINESS={business_name}")
    print(f"    BOOKING_BUSINESS_ID={business_id}")


def cli_mode(args):
    """CLI-Modus: Betrieb aus Kommandozeilen-Argumenten erstellen."""
    result = setup_business(
        name=args.name,
        business_type=args.type,
        company_name=args.company or args.name,
        owner_name=args.owner or "",
        phone=args.phone or "",
        address=args.address or "",
        email=args.email or "",
    )

    if result and args.set_active:
        update_env(args.name, result["id"])


def main():
    parser = argparse.ArgumentParser(
        description="Neuen Betrieb einrichten (Onboarding-Wizard)",
        epilog="Ohne Argumente wird der interaktive Wizard gestartet.",
    )
    parser.add_argument("--name", help="Interner Name (z.B. kupferdaechle)")
    parser.add_argument("--type", help="Branchentyp (z.B. gastronomie, friseur)")
    parser.add_argument("--company", help="Vollstaendiger Firmenname")
    parser.add_argument("--owner", help="Inhaber/Ansprechpartner")
    parser.add_argument("--phone", help="Telefonnummer")
    parser.add_argument("--address", help="Adresse")
    parser.add_argument("--email", help="E-Mail (optional)")
    parser.add_argument("--set-active", action="store_true",
                        help="Als aktiven Betrieb in .env setzen")

    args = parser.parse_args()

    # Wenn --name und --type angegeben: CLI-Modus
    if args.name and args.type:
        cli_mode(args)
    else:
        interactive_wizard()


if __name__ == "__main__":
    main()
