#!/usr/bin/env python3
"""
Admin-Tool: Betriebe anlegen und verwalten.

Nutzung:
    python scripts/manage_business.py add "Salon Anna" friseur --owner "Anna Mueller" --email anna@salon.de --phone 01234567
    python scripts/manage_business.py add "Neuer Kunde" versicherung --owner "Max" --password geheim123
    python scripts/manage_business.py list
    python scripts/manage_business.py link 1
    python scripts/manage_business.py set-password 2 --username versicherung
"""

import sys
import getpass
import argparse
from pathlib import Path

# Projekt-Root zum Python-Path hinzufuegen
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.booking_database import (
    init_booking_tables,
    create_business,
    list_businesses,
    get_business_by_id,
    create_user,
    get_user_by_username,
)


def cmd_add(args):
    """Neuen Betrieb anlegen."""
    init_booking_tables()
    result = create_business(
        name=args.name,
        business_type=args.type,
        owner_name=args.owner,
        email=args.email,
        phone=args.phone,
        address=args.address,
    )
    base_url = args.url or "http://localhost:5000"
    link = f"{base_url}/app?token={result['access_token']}"

    print(f"\nBetrieb erstellt!")
    print(f"  ID:    {result['id']}")
    print(f"  Name:  {args.name}")
    print(f"  Typ:   {args.type}")
    print(f"  Token: {result['access_token']}")
    print(f"\nZugangslink (diesen Link dem Betrieb geben):")
    print(f"  {link}")
    print(f"\nDer Betrieb kann diesen Link als App auf dem Homescreen installieren.")

    # Optional: User mit Passwort anlegen
    if args.password:
        username = args.username or args.name.lower().replace(" ", "_")
        user_id = create_user(result["id"], username, args.password)
        if user_id:
            print(f"\n  Login-User erstellt!")
            print(f"  Benutzername: {username}")
            print(f"  Login-URL:    {base_url}/login")
        else:
            print(f"\n  WARNUNG: Username '{username}' bereits vergeben!")


def cmd_list(args):
    """Alle Betriebe auflisten."""
    init_booking_tables()
    businesses = list_businesses()
    if not businesses:
        print("Keine Betriebe vorhanden.")
        return

    print(f"\n{'ID':<5} {'Name':<30} {'Typ':<15} {'Inhaber':<20} {'Aktiv':<6}")
    print("-" * 80)
    for b in businesses:
        print(f"{b['id']:<5} {b['name']:<30} {b['business_type']:<15} {b.get('owner_name') or '-':<20} {'Ja' if b['is_active'] else 'Nein':<6}")


def cmd_link(args):
    """Zugangslink fuer einen Betrieb anzeigen."""
    init_booking_tables()
    biz = get_business_by_id(args.id)
    if not biz:
        print(f"Betrieb mit ID {args.id} nicht gefunden.")
        return

    base_url = args.url or "http://localhost:5000"
    link = f"{base_url}/app?token={biz['access_token']}"
    print(f"\nBetrieb: {biz['name']} ({biz['business_type']})")
    print(f"Zugangslink:")
    print(f"  {link}")


def cmd_set_password(args):
    """Login-User fuer einen Betrieb erstellen oder Passwort aendern."""
    init_booking_tables()
    biz = get_business_by_id(args.id)
    if not biz:
        print(f"Betrieb mit ID {args.id} nicht gefunden.")
        return

    username = args.username or biz["name"].lower().replace(" ", "_")

    # Passwort abfragen
    if args.password:
        password = args.password
    else:
        password = getpass.getpass("Passwort: ")
        password2 = getpass.getpass("Passwort wiederholen: ")
        if password != password2:
            print("Fehler: Passwoerter stimmen nicht ueberein!")
            return

    if not password or len(password) < 4:
        print("Fehler: Passwort muss mindestens 4 Zeichen lang sein!")
        return

    # Pruefen ob User existiert
    existing = get_user_by_username(username)
    if existing:
        # Passwort aendern
        from src.booking_database import update_user_password
        update_user_password(existing["id"], password)
        print(f"\nPasswort geaendert fuer User '{username}'!")
    else:
        # Neuen User erstellen
        user_id = create_user(biz["id"], username, password)
        if user_id:
            print(f"\nUser erstellt!")
            print(f"  Benutzername: {username}")
            print(f"  Betrieb:      {biz['name']} (ID: {biz['id']})")
        else:
            print(f"Fehler: Username '{username}' bereits vergeben!")
            return

    base_url = args.url or "http://localhost:5000"
    print(f"  Login:        {base_url}/login")


def main():
    parser = argparse.ArgumentParser(description="Betriebe verwalten")
    sub = parser.add_subparsers(dest="command")

    # add
    p_add = sub.add_parser("add", help="Neuen Betrieb anlegen")
    p_add.add_argument("name", help="Firmenname")
    p_add.add_argument("type", help="Branchentyp (friseur, handwerk, arztpraxis, ...)")
    p_add.add_argument("--owner", help="Inhaber-Name")
    p_add.add_argument("--email", help="E-Mail")
    p_add.add_argument("--phone", help="Telefonnummer")
    p_add.add_argument("--address", help="Adresse")
    p_add.add_argument("--url", help="Basis-URL des Servers (Standard: http://localhost:5000)")
    p_add.add_argument("--password", help="Login-Passwort (erstellt automatisch einen User)")
    p_add.add_argument("--username", help="Login-Benutzername (Standard: Firmenname)")

    # list
    sub.add_parser("list", help="Alle Betriebe auflisten")

    # link
    p_link = sub.add_parser("link", help="Zugangslink anzeigen")
    p_link.add_argument("id", type=int, help="Betriebs-ID")
    p_link.add_argument("--url", help="Basis-URL des Servers")

    # set-password
    p_pw = sub.add_parser("set-password", help="Login-User erstellen oder Passwort aendern")
    p_pw.add_argument("id", type=int, help="Betriebs-ID")
    p_pw.add_argument("--username", help="Benutzername (Standard: Firmenname)")
    p_pw.add_argument("--password", help="Passwort (wird sonst interaktiv abgefragt)")
    p_pw.add_argument("--url", help="Basis-URL des Servers")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "link":
        cmd_link(args)
    elif args.command == "set-password":
        cmd_set_password(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
