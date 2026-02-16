"""
Telegram-Bot: Daily AI Image Prompts.
- Jeden Morgen automatisch surreale Architektur/Design Bild-Prompts
- Inspiriert von @homeofchirmi, @davidbzz_, @monde_singulier
- Auf Anfrage jederzeit neue Prompts ("prompt", "bild", "image")
"""

import os
import sys
import json
import time
import logging
import xml.etree.ElementTree as ET
import threading
import requests
import random
from datetime import datetime

from anthropic import Anthropic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler("/opt/ki-telefonassistent/logs/telegram_bot.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("telegram_bot")

# --- Config ---
ENV_PATH = "/opt/ki-telefonassistent/config/.env"

def load_env():
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    env[key.strip()] = val.strip().strip('"').strip("'")
    return env

env = load_env()
TG_TOKEN = env.get("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = env.get("TELEGRAM_CHAT_ID", "")
ALLOWED_CHATS = set(cid.strip() for cid in env.get("TELEGRAM_ALLOWED_CHATS", TG_CHAT_ID).split(",") if cid.strip())
if TG_CHAT_ID:
    ALLOWED_CHATS.add(TG_CHAT_ID)
ANTHROPIC_API_KEY = env.get("ANTHROPIC_API_KEY", "")

# Post-Zeiten in UTC (CET = UTC+1, CEST = UTC+2)
# 8:00 CET = 7 UTC (What-If Video Prompts)
WHATIF_HOUR_UTC = 7

if not TG_TOKEN or not ANTHROPIC_API_KEY:
    logger.error("TELEGRAM_BOT_TOKEN oder ANTHROPIC_API_KEY fehlt in .env")
    sys.exit(1)

client = Anthropic(api_key=ANTHROPIC_API_KEY)
TG_API = f"https://api.telegram.org/bot{TG_TOKEN}"


# ============================================================
# TREND FETCHER (Design/Architecture/Art Trends)
# ============================================================

DESIGN_FEEDS = [
    "https://www.dezeen.com/feed/",
    "https://www.designboom.com/feed/",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]

GEOPOLITICS_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://feeds.reuters.com/reuters/worldNews",
    "https://rss.dw.com/rdf/rss-en-world",
]


def _fetch_rss(feed_urls, max_per_feed=8, total_max=15):
    """Generische RSS-Fetch Funktion."""
    headlines = []
    for feed_url in feed_urls:
        try:
            resp = requests.get(feed_url, timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"
            })
            if resp.status_code != 200:
                continue
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[:max_per_feed]:
                title = item.findtext("title", "")
                if title:
                    headlines.append(title)
            if not headlines:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns)[:max_per_feed]:
                    title = entry.findtext("atom:title", "", ns)
                    if title:
                        headlines.append(title)
        except Exception as e:
            logger.warning(f"RSS fetch error ({feed_url[:40]}): {e}")
    random.shuffle(headlines)
    return headlines[:total_max]


def fetch_trend_headlines():
    """Hole aktuelle Design/Architektur/Welt-Trends als Inspiration."""
    return _fetch_rss(DESIGN_FEEDS)


def fetch_geopolitics_headlines():
    """Hole aktuelle geopolitische Nachrichten."""
    return _fetch_rss(GEOPOLITICS_FEEDS, max_per_feed=10, total_max=20)


# ============================================================
# WHAT-IF VIDEO PROMPT GENERATOR
# ============================================================

WHATIF_SYSTEM_PROMPT = """Du bist ein Experte fuer virale YouTube Shorts / TikTok "What If" Videos.

Deine Aufgabe:
1. Analysiere die aktuellen geopolitischen Nachrichten
2. Erstelle daraus EIN dramatisches, fesselndes "What If" Szenario
3. Schreibe ein komplettes Video-Script (~30 Sekunden Sprechdauer)

Das Video muss:
- In den ersten 2 Sekunden fesseln (Hook)
- Ein realistisches aber extremes Szenario durchspielen
- Geopolitisch fundiert sein (nicht komplett unrealistisch)
- Emotional packen: Angst, Staunen, Neugier
- Am Ende einen Cliffhanger oder Denkanstoß haben

Format deiner Antwort:

GEOPOLITISCHE LAGE:
[Kurze Analyse der aktuellen Weltlage basierend auf den News, 3-4 Saetze]

WHAT-IF SZENARIO:
[Titel des Szenarios, z.B. "What if China invaded Taiwan tomorrow?"]

HOOK (erste 2 Sek):
[Der allererste Satz der sofort Aufmerksamkeit fesselt]

SCRIPT (30 Sek):
[Komplettes Vorleser-Script, dramatisch, packt den Zuschauer. Ca. 80-100 Woerter.]

VISUAL NOTES:
[Kurze Notizen welche Bilder/Maps/Animationen man zeigen sollte]

TAGS:
[10 YouTube-relevante Tags]

Regeln:
- Script auf DEUTSCH
- Dramatisch aber nicht reisserisch - fundiert und intelligent
- Beziehe dich auf ECHTE aktuelle Ereignisse
- Mach es so, dass der Zuschauer bis zum Ende dranbleibt
- Variiere die Themen: Militaer, Wirtschaft, Klima, Technologie, Allianzen"""


def generate_whatif_prompt():
    """Generiere ein What-If Video-Prompt basierend auf aktueller Geopolitik."""
    headlines = fetch_geopolitics_headlines()
    headlines_text = "\n".join(f"- {h}" for h in headlines) if headlines else "Keine aktuellen Headlines verfuegbar."

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            system=WHATIF_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Aktuelle Nachrichten-Headlines:\n\n"
                    f"{headlines_text}\n\n"
                    f"Erstelle basierend auf der aktuellen Lage EIN fesselndes "
                    f"What-If Video-Szenario mit komplettem 30-Sekunden-Script."
                ),
            }],
        )
        reply = ""
        for block in response.content:
            if hasattr(block, "text"):
                reply += block.text
        return reply or "Fehler bei der Prompt-Generierung."
    except Exception as e:
        logger.error(f"What-If generation error: {e}")
        return f"Fehler: {str(e)[:100]}"


# ============================================================
# AI IMAGE PROMPT GENERATOR
# ============================================================

IMAGE_SYSTEM_PROMPT = """You are an expert AI image prompt engineer specializing in surreal, dreamlike architectural and interior design visuals.

Your style references are Instagram accounts like @homeofchirmi, @davidbzz_, and @monde_singulier. They create stunning AI-generated images of:
- Impossible, surreal architecture that bends reality
- Dreamlike interior spaces with organic, biomorphic forms
- Sculptural furniture that looks alive: melting, flowing, breathing
- Luxury materials: raw concrete, veined marble, brushed brass, natural stone, travertine, boucle fabric
- Nature merging with architecture: living walls, trees growing through rooms, water features inside spaces
- Dramatic cinematic lighting: golden hour, volumetric light rays, moody shadows
- Monumental scale: tiny humans in vast impossible spaces
- Earth tones mixed with one bold accent color
- Wabi-sabi meets futurism: raw imperfection combined with sleek design
- Desert brutalism, organic modernism, neo-baroque surrealism

For EACH prompt, provide:

1. MIDJOURNEY PROMPT: A detailed, ready-to-paste Midjourney prompt. Use Midjourney v6 syntax. Include:
   - Subject and scene description (vivid, specific)
   - Materials and textures (be precise: "polished travertine", "raw beton brut", "hand-thrown ceramic")
   - Lighting description ("golden hour volumetric light", "soft diffused morning light through floor-to-ceiling windows")
   - Camera angle ("low angle wide shot", "birds eye view", "intimate close-up detail shot")
   - Style keywords ("architectural photography", "editorial design magazine", "surrealist art installation")
   - Mood ("dreamlike", "contemplative", "monumental", "ethereal")
   - End with: --ar 4:5 --style raw --v 6.1
   - Alternative: some prompts with --ar 16:9 for landscape formats

2. DALL-E PROMPT: Same concept rewritten for DALL-E 3 / ChatGPT image generation. More natural language, descriptive, no technical flags.

3. CAPTION: A short, aesthetic Instagram caption (1-2 lines, poetic, mysterious). In English.

4. HASHTAGS: 15 relevant hashtags for maximum reach.

Rules:
- ALL output in ENGLISH
- Generate exactly 3 prompts per request, numbered PROMPT 1, PROMPT 2, PROMPT 3
- Each prompt must be a DIFFERENT concept: vary between interior, exterior, furniture, and landscape
- Make them visually STUNNING: the kind of image that stops the scroll
- Be inspired by the trend headlines provided but transform them into VISUAL concepts
- Think like an art director: every detail matters
- Mix these sub-genres across the 3 prompts:
  * Surreal interior spaces (impossible rooms, dreamlike lounges)
  * Organic architecture (buildings that look grown, not built)
  * Sculptural furniture/objects (collectible design pieces in dramatic settings)
  * Desert/nature brutalism (raw architecture in dramatic landscapes)
  * Neo-baroque luxury (opulent but surreal, maximalist fantasy spaces)"""


def generate_image_prompts():
    """Generiere surreale Design/Architektur Bild-Prompts."""
    headlines = fetch_trend_headlines()
    headlines_text = "\n".join(f"- {h}" for h in headlines[:12]) if headlines else "No specific trends today."

    # Zufaellige Themen-Variation
    themes = [
        "Focus on INTERIOR spaces today: impossible rooms, surreal lounges, dreamlike bedrooms.",
        "Focus on EXTERIOR architecture today: buildings in dramatic landscapes, desert brutalism, organic towers.",
        "Focus on FURNITURE and OBJECTS today: sculptural collectible pieces, art installations, surreal product design.",
        "Mix it up today: one interior, one exterior, one furniture/object piece.",
        "Go MAXIMALIST today: neo-baroque, opulent, dripping in luxury materials and dramatic lighting.",
        "Go MINIMAL today: wabi-sabi, raw concrete, negative space, one perfect object in a vast room.",
        "Focus on NATURE + ARCHITECTURE today: overgrown ruins, trees through buildings, water features, living walls.",
    ]
    theme_hint = random.choice(themes)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4000,
            system=IMAGE_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Today's design/architecture/world trends for inspiration:\n\n"
                    f"{headlines_text}\n\n"
                    f"Theme direction: {theme_hint}\n\n"
                    f"Generate 3 stunning AI image prompts. Make them scroll-stopping, "
                    f"gallery-worthy, and impossible to ignore."
                ),
            }],
        )

        reply = ""
        for block in response.content:
            if hasattr(block, "text"):
                reply += block.text
        return reply or "Failed to generate prompts."

    except Exception as e:
        logger.error(f"Image prompt generation error: {e}")
        return f"Error generating prompts: {str(e)[:100]}"


# ============================================================
# TELEGRAM HELPERS
# ============================================================

def split_message(text, max_len=4000):
    """Teile lange Nachrichten an sinnvollen Stellen."""
    chunks = []
    while len(text) > max_len:
        split_at = text.rfind("\nPROMPT ", 0, max_len)
        if split_at == -1:
            split_at = text.rfind("\n\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        chunks.append(text)
    return chunks


def send_telegram(chat_id, text):
    """Sende Telegram-Nachricht(en), splittet automatisch bei Ueberlaenge."""
    chunks = split_message(text) if len(text) > 4000 else [text]
    for i, chunk in enumerate(chunks):
        try:
            requests.post(f"{TG_API}/sendMessage", json={
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            }, timeout=10)
            if i < len(chunks) - 1:
                time.sleep(1)
        except Exception as e:
            logger.error(f"Telegram send error: {e}")


# ============================================================
# MORNING SCHEDULER
# ============================================================

_posted_slots = set()


def send_whatif():
    """Generiere und sende What-If Video Prompt."""
    logger.info("Generating morning What-If prompt...")
    prompt = generate_whatif_prompt()
    header = (
        f"WHAT-IF VIDEO PROMPT\n"
        + datetime.utcnow().strftime("%d.%m.%Y") + "\n"
        + "=" * 30 + "\n\n"
    )
    for cid in ALLOWED_CHATS:
        send_telegram(cid, header + prompt)
    logger.info("Morning What-If prompt sent!")


def send_image_prompts(label):
    """Generiere und sende Image Prompts."""
    logger.info(f"Generating {label} image prompts...")
    prompts = generate_image_prompts()
    header = (
        f"AI IMAGE PROMPTS ({label})\n"
        + datetime.utcnow().strftime("%d.%m.%Y") + "\n"
        + "=" * 30 + "\n\n"
    )
    for cid in ALLOWED_CHATS:
        send_telegram(cid, header + prompts)
    logger.info(f"{label} image prompts sent!")


def check_schedule():
    """Pruefe alle 30s ob es Zeit fuer geplante Posts ist."""
    global _posted_slots
    while True:
        try:
            now = datetime.utcnow()
            today_str = now.strftime("%Y-%m-%d")
            slot_key = f"{today_str}_{now.hour}"

            if now.hour == WHATIF_HOUR_UTC and slot_key not in _posted_slots:
                _posted_slots.add(slot_key)
                send_whatif()

            # Alte Eintraege aufraeumen (aelter als 24h)
            old_keys = [k for k in _posted_slots if not k.startswith(today_str)]
            for k in old_keys:
                _posted_slots.discard(k)
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
        time.sleep(30)


# ============================================================
# MESSAGE HANDLER
# ============================================================

def process_message(text):
    """Verarbeite eine Nachricht und gib Antwort zurueck."""
    text_lower = text.lower().strip()

    # What-If Anfrage
    if any(kw in text_lower for kw in [
        "whatif", "what if", "what-if", "video", "youtube", "szenario",
        "/whatif", "geopolitik", "nachrichten",
    ]):
        return generate_whatif_prompt()

    # Image Prompt-Anfrage
    if any(kw in text_lower for kw in [
        "prompt", "bild", "image", "design", "midjourney", "dalle",
        "idee", "content", "/prompt", "/start", "new", "neu", "generate",
    ]):
        return generate_image_prompts()

    # Alles andere an Claude weiterleiten
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=(
                "Du bist ein kreativer Assistent fuer AI-generierte Design/Architektur-Bilder. "
                "Antworte kurz und hilfreich. "
                "Wenn jemand nach Prompts, Bildern, Content oder Ideen fragt, "
                "sag ihm er soll 'prompt' schreiben fuer neue AI Image Prompts. "
                "Die Prompts sind im Stil von @homeofchirmi, @davidbzz_, @monde_singulier: "
                "surreale Architektur, traumhafte Interiors, skulpturale Moebel."
            ),
            messages=[{"role": "user", "content": text}],
        )
        reply = ""
        for block in response.content:
            if hasattr(block, "text"):
                reply += block.text
        return reply or "Konnte Anfrage nicht verarbeiten."
    except Exception as e:
        logger.error(f"Claude API Fehler: {e}")
        return f"Fehler: {str(e)[:100]}"


# ============================================================
# MAIN POLLING LOOP
# ============================================================

def poll_updates():
    """Long-Polling fuer Telegram-Updates."""
    offset = 0
    logger.info("Telegram-Bot gestartet (What-If Video Prompts)")

    scheduler = threading.Thread(target=check_schedule, daemon=True)
    scheduler.start()
    logger.info("Scheduler aktiv: What-If 8:00 CET")

    while True:
        try:
            resp = requests.get(
                f"{TG_API}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35,
            )
            if resp.status_code != 200:
                time.sleep(5)
                continue

            data = resp.json()
            if not data.get("ok"):
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue
                chat_id = str(msg["chat"]["id"])
                text = msg.get("text", "")
                user_name = msg.get("from", {}).get("first_name", "")
                if not text:
                    continue

                # Nur erlaubte Chats
                if chat_id not in ALLOWED_CHATS:
                    logger.warning(f"Zugriff verweigert fuer Chat-ID: {chat_id} (User: {user_name})")
                    send_telegram(chat_id, "Zugriff verweigert. Deine Chat-ID: " + chat_id)
                    continue

                logger.info(f"Nachricht von {user_name} ({chat_id}): {text[:80]}")

                reply = process_message(text)
                send_telegram(chat_id, reply)
                logger.info(f"Antwort gesendet ({len(reply)} Zeichen)")

        except requests.exceptions.Timeout:
            continue
        except requests.exceptions.ConnectionError:
            logger.error("Verbindungsfehler, warte 10s...")
            time.sleep(10)
        except Exception as e:
            logger.error(f"Polling-Fehler: {e}")
            time.sleep(5)


if __name__ == "__main__":
    poll_updates()
