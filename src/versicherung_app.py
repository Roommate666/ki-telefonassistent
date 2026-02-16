"""
PWA-Dashboard fuer Versicherungsberater.
Premium-Design mit Glassmorphism, Echtzeit-Updates, Gespraechsprotokolle.
Zugang nur per Access-Token-Link.
"""

import logging
from flask import Blueprint, render_template_string, request

logger = logging.getLogger(__name__)

versicherung_app = Blueprint("versicherung_app", __name__)


# ============================================================
# PWA Manifest + Service Worker + Icons
# ============================================================

@versicherung_app.route("/v/manifest.json")
def v_pwa_manifest():
    return {
        "name": "AssistentPro - Versicherung",
        "short_name": "AssistentPro",
        "description": "Professionelles Versicherungsberater-Dashboard",
        "start_url": "/v/dashboard?token=" + request.args.get("token", ""),
        "display": "standalone",
        "background_color": "#0a0e1a",
        "theme_color": "#6366f1",
        "orientation": "any",
        "icons": [
            {"src": "/v/icon-192", "sizes": "192x192", "type": "image/svg+xml"},
            {"src": "/v/icon-512", "sizes": "512x512", "type": "image/svg+xml"},
        ],
    }


@versicherung_app.route("/v/icon-192")
@versicherung_app.route("/v/icon-512")
def v_pwa_icon():
    size = 512 if "512" in request.path else 192
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
        <defs>
            <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#6366f1"/>
                <stop offset="100%" style="stop-color:#8b5cf6"/>
            </linearGradient>
        </defs>
        <rect width="{size}" height="{size}" rx="{size//6}" fill="url(#g)"/>
        <text x="50%" y="38%" font-family="Arial" font-size="{size//4}" font-weight="bold"
              fill="white" text-anchor="middle" dominant-baseline="middle">AP</text>
        <text x="50%" y="68%" font-family="Arial" font-size="{size//8}"
              fill="rgba(255,255,255,0.7)" text-anchor="middle" dominant-baseline="middle">PRO</text>
    </svg>"""
    return svg, 200, {"Content-Type": "image/svg+xml"}


@versicherung_app.route("/v/sw.js")
def v_service_worker():
    js = """
const CACHE_NAME = 'assistentpro-v3';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(names => Promise.all(
            names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n))
        )).then(() => clients.claim())
    );
});
self.addEventListener('fetch', e => {
    // API-Aufrufe NIEMALS cachen - immer live holen
    if (e.request.url.includes('/api/')) {
        e.respondWith(fetch(e.request));
        return;
    }
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});

// Push-Benachrichtigungen
self.addEventListener('push', function(e) {
    var data = {title: 'Neuer Anruf', body: 'Ein neuer Anruf ist eingegangen', url: '/v/dashboard'};
    try { data = e.data.json(); } catch(err) {}
    e.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/v/icon-192',
            badge: '/v/icon-192',
            vibrate: [200, 100, 200],
            data: { url: data.url || '/v/dashboard' },
            actions: [
                { action: 'open', title: 'Öffnen' },
                { action: 'dismiss', title: 'Später' }
            ]
        })
    );
});

self.addEventListener('notificationclick', function(e) {
    e.notification.close();
    var url = (e.notification.data && e.notification.data.url) || '/v/dashboard';
    e.waitUntil(
        clients.matchAll({type: 'window', includeUncontrolled: true}).then(function(list) {
            for (var i = 0; i < list.length; i++) {
                if (list[i].url.indexOf('/v/dashboard') !== -1) {
                    list[i].focus();
                    return;
                }
            }
            return clients.openWindow(url);
        })
    );
});
"""
    return js, 200, {"Content-Type": "application/javascript", "Cache-Control": "no-cache"}


@versicherung_app.route("/v/vapid-key")
def v_vapid_key():
    import os
    key = os.environ.get("VAPID_PUBLIC_KEY", "")
    return {"key": key}


# ============================================================
# Haupt-App
# ============================================================

@versicherung_app.route("/v/dashboard")
def v_dashboard():
    token = request.args.get("token")
    if not token:
        return render_template_string(NO_TOKEN_HTML), 401
    return render_template_string(APP_HTML, token=token)


# ============================================================
# HTML Templates
# ============================================================

NO_TOKEN_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zugang verweigert</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: #0a0e1a; color: #e2e8f0; display: flex; justify-content: center;
               align-items: center; min-height: 100vh; margin: 0; }
        .box { text-align: center; padding: 40px; border-radius: 20px; max-width: 400px;
               background: rgba(255,255,255,0.05); backdrop-filter: blur(20px);
               -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1);
               box-shadow: 0 8px 32px rgba(0,0,0,0.4); }
        .icon { font-size: 3rem; margin-bottom: 15px; }
        h1 { color: #f1f5f9; margin-bottom: 10px; font-size: 1.3rem; }
        p { color: #94a3b8; font-size: 0.9rem; line-height: 1.6; }
    </style>
</head>
<body>
    <div class="box">
        <div class="icon">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="1.5">
                <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>
            </svg>
        </div>
        <h1>Kein Zugang</h1>
        <p>Du brauchst einen gueltigen Zugangslink um das Dashboard zu nutzen.
           Kontaktiere deinen Anbieter fuer einen Link.</p>
    </div>
</body>
</html>
"""

APP_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#6366f1">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <link rel="manifest" href="/v/manifest.json?token={{ token }}">
    <title>AssistentPro</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        :root {
            --bg: #0a0e1a;
            --surface: rgba(255,255,255,0.05);
            --surface-hover: rgba(255,255,255,0.08);
            --border: rgba(255,255,255,0.08);
            --border-light: rgba(255,255,255,0.12);
            --text: #e2e8f0;
            --text-muted: #94a3b8;
            --text-dim: #64748b;
            --accent-1: #6366f1;
            --accent-2: #8b5cf6;
            --gradient: linear-gradient(135deg, #6366f1, #8b5cf6);
            --red: #ef4444;
            --red-bg: rgba(239,68,68,0.15);
            --yellow: #f59e0b;
            --yellow-bg: rgba(245,158,11,0.15);
            --green: #22c55e;
            --green-bg: rgba(34,197,94,0.15);
            --blue: #3b82f6;
            --blue-bg: rgba(59,130,246,0.15);
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* ===== HEADER ===== */
        .header {
            background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(139,92,246,0.1));
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 50;
        }
        .header-top { display: flex; justify-content: space-between; align-items: center; }
        .header h1 {
            font-size: 1.15rem;
            color: #f1f5f9;
            background: var(--gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header .live-dot {
            width: 8px; height: 8px; background: var(--green); border-radius: 50%;
            display: inline-block; margin-right: 6px; animation: pulse-dot 2s infinite;
        }
        .header .sub {
            font-size: 0.78rem; color: var(--text-muted); margin-top: 3px;
            display: flex; align-items: center; gap: 4px;
        }
        @keyframes pulse-dot { 0%,100% { opacity:1; } 50% { opacity:0.4; } }

        /* ===== BOTTOM NAV ===== */
        .nav {
            position: fixed; bottom: 0; left: 0; right: 0; z-index: 100;
            background: rgba(10,14,26,0.85);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-top: 1px solid var(--border);
            display: flex;
            padding-bottom: env(safe-area-inset-bottom);
        }
        .nav-item {
            flex: 1; padding: 12px 0 10px; text-align: center; cursor: pointer;
            color: var(--text-dim); font-size: 0.72rem; transition: all 0.3s ease;
            position: relative; -webkit-tap-highlight-color: rgba(99,102,241,0.2);
            user-select: none; -webkit-user-select: none;
        }
        .nav-item.active { color: var(--accent-1); }
        .nav-item.active::before {
            content: ''; position: absolute; top: 0; left: 50%; transform: translateX(-50%);
            width: 24px; height: 2px; background: var(--gradient); border-radius: 2px;
        }
        .nav-item svg { display: block; margin: 0 auto 3px; width: 22px; height: 22px; }
        .nav-badge {
            position: absolute; top: 4px; right: calc(50% - 18px);
            background: var(--red); color: white; border-radius: 10px;
            font-size: 0.55rem; padding: 1px 5px; font-weight: 700;
            min-width: 16px; text-align: center;
        }

        /* ===== CONTENT ===== */
        .content { padding: 15px 15px 85px; max-width: 600px; margin: 0 auto; }
        .page { display: none; }
        .page.active { display: block; }

        /* ===== STAT CARDS ===== */
        .stats-grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 18px;
        }
        .stat-card {
            background: var(--surface);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .stat-card:active { transform: scale(0.97); }
        .stat-card .label {
            font-size: 0.65rem; color: var(--text-dim);
            text-transform: uppercase; letter-spacing: 0.06em; font-weight: 500;
        }
        .stat-card .val {
            font-size: 1.8rem; font-weight: 700; margin-top: 4px;
            background: var(--gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .stat-card.accent-red .val { background: linear-gradient(135deg, #ef4444, #f97316); -webkit-background-clip: text; background-clip: text; }
        .stat-card.accent-yellow .val { background: linear-gradient(135deg, #f59e0b, #eab308); -webkit-background-clip: text; background-clip: text; }
        .stat-card.accent-green .val { background: linear-gradient(135deg, #22c55e, #10b981); -webkit-background-clip: text; background-clip: text; }

        /* ===== SECTION TITLE ===== */
        .section-title {
            font-size: 0.85rem; font-weight: 600; color: var(--text-muted);
            margin-bottom: 12px; display: flex; align-items: center; gap: 8px;
        }
        .section-title .count {
            background: var(--surface); border: 1px solid var(--border);
            border-radius: 12px; padding: 2px 8px; font-size: 0.7rem;
        }

        /* ===== CALL CARDS ===== */
        .call-card {
            background: var(--surface);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 14px 14px 14px 18px;
            margin-bottom: 10px;
            position: relative;
            overflow: hidden;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .call-card:hover { background: var(--surface-hover); border-color: var(--border-light); }
        .call-card:active { transform: scale(0.98); }

        /* Farbiger Seitenstreifen */
        .call-card::before {
            content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
        }
        .call-card.typ-schaden::before { background: var(--red); }
        .call-card.typ-termin::before { background: var(--yellow); }
        .call-card.typ-frage::before { background: var(--green); }

        .call-card .card-top {
            display: flex; justify-content: space-between; align-items: flex-start;
        }
        .call-card .name { font-weight: 600; font-size: 0.95rem; color: #f1f5f9; }
        .call-card .phone { font-size: 0.78rem; color: var(--text-muted); margin-top: 2px; }
        .call-card .anliegen {
            font-size: 0.82rem; color: var(--text-muted); margin-top: 8px;
            display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
        }
        .call-card .card-bottom {
            display: flex; justify-content: space-between; align-items: center; margin-top: 10px;
        }
        .call-card .zeit { font-size: 0.7rem; color: var(--text-dim); }

        /* Slide-in Animation */
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .call-card.new-item { animation: slideIn 0.4s ease-out; }

        /* ===== BADGES ===== */
        .badge {
            display: inline-flex; align-items: center; gap: 4px;
            padding: 3px 10px; border-radius: 20px;
            font-size: 0.65rem; font-weight: 600; letter-spacing: 0.02em;
        }
        .badge-schaden { background: var(--red-bg); color: var(--red); }
        .badge-termin { background: var(--yellow-bg); color: var(--yellow); }
        .badge-frage { background: var(--green-bg); color: var(--green); }
        .badge-dringend { background: var(--red-bg); color: var(--red); animation: pulse-badge 1.5s infinite; }
        .badge-offen { background: var(--blue-bg); color: var(--blue); }
        .badge-erledigt { background: var(--green-bg); color: var(--green); }
        .badge-zurueckgerufen { background: var(--green-bg); color: var(--green); }
        .badge-festnetz { background: rgba(99,102,241,0.15); color: var(--accent-1); font-size: 0.6rem; }
        .badge-mobil { background: rgba(139,92,246,0.15); color: var(--accent-2); font-size: 0.6rem; }
        @keyframes pulse-badge { 0%,100% { opacity:1; } 50% { opacity:0.6; } }

        /* ===== QUICK ACTION BUTTON ===== */
        .btn-quick {
            padding: 6px 14px; border: none; border-radius: 10px;
            font-size: 0.72rem; font-weight: 600; cursor: pointer;
            transition: all 0.2s ease;
        }
        .btn-action {
            background: var(--gradient); color: white;
            box-shadow: 0 2px 8px rgba(99,102,241,0.3);
        }
        .btn-action:hover { box-shadow: 0 4px 12px rgba(99,102,241,0.5); }
        .btn-done {
            background: var(--green-bg); color: var(--green); border: 1px solid rgba(34,197,94,0.2);
        }
        .btn-outline {
            background: transparent; color: var(--text-muted);
            border: 1px solid var(--border);
        }
        .btn-outline:hover { border-color: var(--border-light); color: var(--text); }
        .btn-call-action {
            background: rgba(34,197,94,0.15); color: var(--green);
            border: 1px solid rgba(34,197,94,0.2);
        }

        /* ===== SEARCH BAR ===== */
        .search-bar { position: relative; margin-bottom: 12px; }
        .search-bar input {
            width: 100%; padding: 11px 14px 11px 38px;
            background: var(--surface); backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid var(--border); border-radius: 12px;
            color: var(--text); font-size: 0.88rem;
            transition: border-color 0.3s ease;
        }
        .search-bar input:focus { outline: none; border-color: var(--accent-1); }
        .search-bar input::placeholder { color: var(--text-dim); }
        .search-bar svg {
            position: absolute; left: 12px; top: 50%; transform: translateY(-50%);
            width: 16px; height: 16px; color: var(--text-dim);
        }
        .search-bar .clear-btn {
            position: absolute; right: 10px; top: 50%; transform: translateY(-50%);
            background: none; border: none; color: var(--text-dim); cursor: pointer;
            font-size: 1.1rem; display: none; padding: 4px;
        }

        /* ===== FILTER CHIPS ===== */
        .filter-bar { display: flex; gap: 6px; margin-bottom: 14px; overflow-x: auto; -webkit-overflow-scrolling: touch; }
        .filter-bar::-webkit-scrollbar { display: none; }
        .chip {
            padding: 6px 14px; border-radius: 20px;
            border: 1px solid var(--border); background: transparent;
            color: var(--text-muted); font-size: 0.72rem; font-weight: 500;
            cursor: pointer; white-space: nowrap; transition: all 0.2s ease;
        }
        .chip.active {
            background: var(--gradient); color: white;
            border-color: transparent;
            box-shadow: 0 2px 8px rgba(99,102,241,0.3);
        }

        /* ===== MODAL ===== */
        .modal-overlay {
            display: none; position: fixed; inset: 0;
            background: rgba(0,0,0,0.6); backdrop-filter: blur(4px);
            -webkit-backdrop-filter: blur(4px);
            z-index: 200; justify-content: center; align-items: flex-end;
        }
        .modal-overlay.open { display: flex; }
        .modal {
            background: #0f1424;
            border: 1px solid var(--border);
            border-radius: 20px 20px 0 0;
            width: 100%; max-width: 540px; max-height: 90vh; overflow-y: auto;
            padding: 20px; padding-bottom: calc(20px + env(safe-area-inset-bottom));
            animation: modalSlideUp 0.3s ease-out;
        }
        @keyframes modalSlideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
        .modal-handle {
            width: 36px; height: 4px; background: rgba(255,255,255,0.2);
            border-radius: 2px; margin: 0 auto 16px;
        }
        .modal-close {
            float: right; background: none; border: none; color: var(--text-dim);
            font-size: 1.4rem; cursor: pointer; padding: 4px; margin: -4px -4px 0 0;
        }
        .modal h3 {
            font-size: 1.1rem; color: #f1f5f9; margin-bottom: 4px;
        }
        .modal .modal-phone {
            font-size: 0.85rem; color: var(--accent-1); margin-bottom: 16px;
            text-decoration: none; display: inline-flex; align-items: center; gap: 6px;
        }
        .modal .modal-phone:hover { color: var(--accent-2); }

        /* Transkript */
        .transcript { margin: 16px 0; }
        .transcript-title {
            font-size: 0.75rem; color: var(--text-dim); text-transform: uppercase;
            letter-spacing: 0.05em; margin-bottom: 10px; font-weight: 500;
        }
        .msg {
            padding: 10px 14px; border-radius: 14px; margin-bottom: 6px;
            max-width: 85%; font-size: 0.84rem; line-height: 1.5;
        }
        .msg-user {
            background: rgba(99,102,241,0.2); border: 1px solid rgba(99,102,241,0.15);
            margin-left: auto; border-bottom-right-radius: 4px;
        }
        .msg-assistant {
            background: var(--surface); border: 1px solid var(--border);
            border-bottom-left-radius: 4px;
        }
        .msg-label {
            font-size: 0.65rem; color: var(--text-dim); margin-bottom: 3px;
            font-weight: 600; text-transform: uppercase; letter-spacing: 0.03em;
        }

        /* Modal Actions */
        .modal-actions {
            display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0;
        }
        .modal-actions .btn-quick { padding: 10px 18px; font-size: 0.78rem; border-radius: 12px; }

        /* Notiz-Feld */
        .notiz-section { margin-top: 16px; }
        .notiz-section label {
            font-size: 0.72rem; color: var(--text-dim); text-transform: uppercase;
            letter-spacing: 0.05em; font-weight: 500; display: block; margin-bottom: 6px;
        }
        .notiz-input {
            width: 100%; padding: 10px 14px; min-height: 70px; resize: vertical;
            background: var(--surface); border: 1px solid var(--border);
            border-radius: 12px; color: var(--text); font-size: 0.85rem;
            font-family: inherit;
        }
        .notiz-input:focus { outline: none; border-color: var(--accent-1); }
        .notiz-actions { display: flex; gap: 8px; margin-top: 8px; }

        /* Modal Meta */
        .modal-meta {
            display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0;
            font-size: 0.75rem; color: var(--text-dim);
        }
        .modal-meta span { display: flex; align-items: center; gap: 4px; }

        /* Anliegen Box */
        .anliegen-box {
            background: var(--surface); border: 1px solid var(--border);
            border-radius: 12px; padding: 12px 14px; margin: 12px 0;
            font-size: 0.85rem; color: var(--text-muted); line-height: 1.5;
            border-left: 3px solid var(--accent-1);
        }

        /* ===== STATISTIK ===== */
        .chart-container {
            background: var(--surface); backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid var(--border); border-radius: 14px;
            padding: 18px; margin-bottom: 14px;
        }
        .chart-title {
            font-size: 0.78rem; font-weight: 600; color: var(--text-muted); margin-bottom: 14px;
        }
        .bar-chart { display: flex; align-items: flex-end; gap: 6px; height: 120px; }
        .bar-col {
            flex: 1; display: flex; flex-direction: column; align-items: center;
            justify-content: flex-end; height: 100%;
        }
        .bar {
            width: 100%; border-radius: 6px 6px 0 0; background: var(--gradient);
            min-height: 4px; transition: height 0.5s ease;
            box-shadow: 0 0 10px rgba(99,102,241,0.2);
        }
        .bar-label {
            font-size: 0.65rem; color: var(--text-dim); margin-top: 6px; font-weight: 500;
        }
        .bar-value {
            font-size: 0.7rem; color: var(--text-muted); margin-bottom: 4px; font-weight: 600;
        }

        /* Verteilung */
        .dist-row {
            display: flex; align-items: center; gap: 10px;
            padding: 10px 0; border-bottom: 1px solid var(--border);
        }
        .dist-row:last-child { border-bottom: none; }
        .dist-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
        .dist-label { font-size: 0.82rem; color: var(--text); flex: 1; }
        .dist-val { font-size: 0.82rem; font-weight: 600; color: var(--text); }
        .dist-bar-bg {
            flex: 2; height: 6px; background: rgba(255,255,255,0.05); border-radius: 3px; overflow: hidden;
        }
        .dist-bar-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }

        /* Avg Duration */
        .avg-stat {
            text-align: center; padding: 20px;
        }
        .avg-stat .big {
            font-size: 2.5rem; font-weight: 700;
            background: var(--gradient); -webkit-background-clip: text;
            -webkit-text-fill-color: transparent; background-clip: text;
        }
        .avg-stat .unit { font-size: 0.8rem; color: var(--text-dim); margin-top: 4px; }

        /* ===== EMPTY STATE ===== */
        .empty {
            text-align: center; padding: 40px 20px; color: var(--text-dim);
            font-size: 0.88rem;
        }
        .empty svg { margin-bottom: 12px; opacity: 0.4; }

        /* ===== RESPONSIVE ===== */
        @media (min-width: 500px) {
            .stats-grid { grid-template-columns: repeat(4, 1fr); }
        }
    </style>
</head>
<body>
    <!-- HEADER -->
    <div class="header">
        <div class="header-top">
            <div>
                <h1 id="biz-name">AssistentPro</h1>
                <div class="sub">
                    <span class="live-dot"></span>
                    <span id="header-sub">Live</span>
                </div>
            </div>
        </div>
    </div>

    <!-- CONTENT -->
    <div class="content">

        <!-- TAB 1: LIVE-FEED -->
        <div class="page active" id="page-live">
            <div class="stats-grid" id="stats-grid"></div>
            <div class="section-title">
                Aktuelle Anrufe
                <span class="count" id="live-count">0</span>
            </div>
            <div id="live-feed"></div>
        </div>

        <!-- TAB 2: ALLE ANRUFE -->
        <div class="page" id="page-alle">
            <div class="search-bar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <input type="text" id="search-input" placeholder="Name, Telefon suchen..." />
                <button class="clear-btn" id="search-clear">&times;</button>
            </div>
            <div class="filter-bar" id="filter-bar">
                <button class="chip active" data-filter="">Alle</button>
                <button class="chip" data-filter="offen">Offen</button>
                <button class="chip" data-filter="erledigt">Erledigt</button>
                <button class="chip" data-filter="dringend">Dringend</button>
            </div>
            <div id="alle-liste"></div>
        </div>

        <!-- TAB 3: STATISTIKEN -->
        <div class="page" id="page-stats">
            <div class="chart-container">
                <div class="chart-title">Anrufe diese Woche</div>
                <div class="bar-chart" id="week-chart"></div>
            </div>
            <div class="chart-container">
                <div class="chart-title">Anliegen-Verteilung</div>
                <div id="dist-chart"></div>
            </div>
            <div class="chart-container">
                <div class="chart-title">Durchschn. Gespraechsdauer</div>
                <div class="avg-stat" id="avg-dauer">
                    <div class="big">-</div>
                    <div class="unit">Sekunden</div>
                </div>
            </div>
        </div>
    </div>

    <!-- NAVIGATION -->
    <div class="nav">
        <div class="nav-item active" data-page="live" onclick="switchTab('live')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            Live
        </div>
        <div class="nav-item" data-page="alle" onclick="switchTab('alle')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>
            Anrufe
            <span class="nav-badge" id="badge-alle" style="display:none;">0</span>
        </div>
        <div class="nav-item" data-page="stats" onclick="switchTab('stats')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>
            Statistik
        </div>
    </div>

    <!-- DETAIL MODAL -->
    <div class="modal-overlay" id="detail-modal">
        <div class="modal">
            <div class="modal-handle"></div>
            <button class="modal-close" onclick="closeDetail()">&times;</button>
            <h3 id="modal-name">-</h3>
            <a href="#" class="modal-phone" id="modal-phone">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3a2 2 0 012 1.72c.127.96.361 1.903.7 2.81a2 2 0 01-.45 2.11L8.09 9.91a16 16 0 006 6l1.27-1.27a2 2 0 012.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0122 16.92z"/></svg>
                <span id="modal-phone-text">-</span>
            </a>
            <div class="modal-meta" id="modal-meta"></div>
            <div class="anliegen-box" id="modal-anliegen">-</div>
            <div class="modal-actions" id="modal-actions"></div>
            <div class="transcript" id="modal-transcript"></div>
            <div class="notiz-section">
                <label>Notizen</label>
                <textarea class="notiz-input" id="modal-notiz" placeholder="Notiz hinzufuegen..."></textarea>
                <div class="notiz-actions">
                    <button class="btn-quick btn-action" onclick="saveNotiz()">Speichern</button>
                </div>
            </div>
        </div>
    </div>

    <script>
    const TOKEN = '{{ token }}';
    const API = '/api/v';
    const headers = { 'Content-Type': 'application/json', 'X-Access-Token': TOKEN };
    let currentFilter = '';
    let currentSearch = '';
    let currentDetailId = null;
    let knownIds = new Set();
    let refreshTimer = null;

    // ===== API =====
    async function api(path, method, body) {
        method = method || 'GET';
        const opts = { method, headers };
        if (body) opts.body = JSON.stringify(body);
        const resp = await fetch(API + path, opts);
        return resp.json();
    }

    // ===== INIT =====
    async function init() {
        try {
            const data = await api('/dashboard');
            document.getElementById('biz-name').textContent = data.business.name || 'AssistentPro';
            renderStats(data.stats);
            renderLiveFeed(data.anrufe, false);
            loadAlleAnrufe();
            loadStats();
        } catch(e) { console.error('Init:', e); }
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/v/sw.js').then(function(reg) {
                setupPush(reg);
            }).catch(function(){});
        }
        startAutoRefresh();
    }

    // ===== TAB SWITCHING =====
    function switchTab(tab) {
        try {
            document.querySelectorAll('.nav-item').forEach(function(n) { n.classList.remove('active'); });
            document.querySelectorAll('.page').forEach(function(p) { p.classList.remove('active'); });
            var navEl = document.querySelector('[data-page="' + tab + '"]');
            var pageEl = document.getElementById('page-' + tab);
            if (navEl) navEl.classList.add('active');
            if (pageEl) pageEl.classList.add('active');
            if (tab === 'stats') loadStats();
            if (tab === 'alle') loadAlleAnrufe();
        } catch(e) { console.error('switchTab error:', e); }
    }

    // ===== STATS =====
    function renderStats(s) {
        document.getElementById('stats-grid').innerHTML =
            statCard('Anrufe heute', s.anrufe_heute, '') +
            statCard('Offene Rückrufe', s.offene_rueckrufe, 'accent-yellow') +
            statCard('Termine', s.termine, 'accent-green') +
            statCard('Schäden', s.schaeden, 'accent-red');
        document.getElementById('header-sub').textContent = 'Live \u00b7 Heute: ' + s.anrufe_heute + ' Anrufe';
        // Badge
        var badge = document.getElementById('badge-alle');
        if (s.offene_rueckrufe > 0) {
            badge.textContent = s.offene_rueckrufe;
            badge.style.display = 'block';
        } else {
            badge.style.display = 'none';
        }
    }

    function statCard(label, val, cls) {
        return '<div class="stat-card ' + cls + '">' +
            '<div class="label">' + label + '</div>' +
            '<div class="val">' + val + '</div></div>';
    }

    // ===== LIVE FEED =====
    function renderLiveFeed(anrufe, animate) {
        var el = document.getElementById('live-feed');
        document.getElementById('live-count').textContent = anrufe.length;
        if (!anrufe.length) {
            el.innerHTML = '<div class="empty">' +
                '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 16.92v3a2 2 0 01-2.18 2 19.79 19.79 0 01-8.63-3.07 19.5 19.5 0 01-6-6 19.79 19.79 0 01-3.07-8.67A2 2 0 014.11 2h3"/></svg>' +
                '<div>Noch keine Anrufe heute</div></div>';
            return;
        }
        var newIds = new Set();
        anrufe.forEach(function(a) { newIds.add(a.id); });
        el.innerHTML = anrufe.map(function(a) {
            var isNew = animate && !knownIds.has(a.id);
            return renderCallCard(a, isNew);
        }).join('');
        knownIds = newIds;
    }

    function renderCallCard(a, isNew) {
        var typClass = 'typ-' + (a.anruf_typ || 'frage');
        var animClass = isNew ? ' new-item' : '';
        var urgBadge = '';
        var urg = (a.urgency || '').toLowerCase();
        if (urg === 'hoch' || urg === 'dringend') {
            urgBadge = '<span class="badge badge-dringend">Dringend</span> ';
        }
        var typBadge = '';
        if (a.anruf_typ === 'schaden') typBadge = '<span class="badge badge-schaden">Schaden</span>';
        else if (a.anruf_typ === 'termin') typBadge = '<span class="badge badge-termin">Termin</span>';
        else typBadge = '<span class="badge badge-frage">Frage</span>';

        // Festnetz/Mobil Badge
        var phoneBadge = '';
        var pt = (a.phone_type || '').toLowerCase();
        if (pt === 'mobil') phoneBadge = ' <span class="badge badge-mobil">Mobil</span>';
        else if (pt === 'festnetz') phoneBadge = ' <span class="badge badge-festnetz">Festnetz</span>';

        var statusBadge = '';
        var st = (a.status || 'neu');
        if (st === 'erledigt' || st === 'zurueckgerufen' || st === 'termin_eingetragen') {
            statusBadge = ' <span class="badge badge-erledigt">' + statusText(st) + '</span>';
        } else if (st === 'neu' || st === 'in_bearbeitung') {
            statusBadge = ' <span class="badge badge-offen">' + statusText(st) + '</span>';
        }

        var zeit = formatTime(a.uhrzeit);

        var quickBtn = '';
        if (st === 'neu' || st === 'in_bearbeitung') {
            quickBtn = '<button class="btn-quick btn-action" onclick="event.stopPropagation();quickCallback(' + a.id + ',this)">Zurückgerufen</button>';
        }

        return '<div class="call-card ' + typClass + animClass + '" onclick="openDetail(' + a.id + ')">' +
            '<div class="card-top"><div>' +
            '<div class="name">' + esc(a.name) + '</div>' +
            '<div class="phone">' + esc(a.telefon) + '</div>' +
            '</div><div>' + urgBadge + typBadge + phoneBadge + statusBadge + '</div></div>' +
            '<div class="anliegen">' + esc(a.anliegen) + '</div>' +
            '<div class="card-bottom">' +
            '<span class="zeit">' + zeit + (a.dauer ? ' \u00b7 ' + a.dauer + 's' : '') + '</span>' +
            quickBtn +
            '</div></div>';
    }

    // ===== ALLE ANRUFE =====
    async function loadAlleAnrufe() {
        var el = document.getElementById('alle-liste');
        try {
            el.innerHTML = '<div class="empty">Laden...</div>';
            var params = '';
            var parts = [];
            if (currentFilter) parts.push('status=' + currentFilter);
            if (currentSearch) parts.push('q=' + encodeURIComponent(currentSearch));
            if (parts.length) params = '?' + parts.join('&');

            var anrufe = await api('/anrufe' + params);
            if (!anrufe || !anrufe.length) {
                el.innerHTML = '<div class="empty">Keine Anrufe gefunden</div>';
                return;
            }
            el.innerHTML = anrufe.map(function(a) { return renderCallCard(a, false); }).join('');
        } catch(e) {
            console.error('loadAlleAnrufe:', e);
            el.innerHTML = '<div class="empty">Fehler beim Laden: ' + e.message + '</div>';
        }
    }

    // ===== FILTER & SEARCH =====
    document.getElementById('filter-bar').addEventListener('click', function(e) {
        var chip = e.target.closest('.chip');
        if (!chip) return;
        document.querySelectorAll('.chip').forEach(function(c) { c.classList.remove('active'); });
        chip.classList.add('active');
        currentFilter = chip.dataset.filter;
        loadAlleAnrufe();
    });

    var searchTimeout = null;
    var searchInput = document.getElementById('search-input');
    var searchClear = document.getElementById('search-clear');
    searchInput.addEventListener('input', function() {
        searchClear.style.display = searchInput.value ? 'block' : 'none';
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(function() {
            currentSearch = searchInput.value;
            if (searchInput.value.length >= 2 || searchInput.value.length === 0) {
                loadAlleAnrufe();
            }
        }, 300);
    });
    searchClear.addEventListener('click', function() {
        searchInput.value = '';
        searchClear.style.display = 'none';
        currentSearch = '';
        loadAlleAnrufe();
    });

    // ===== DETAIL MODAL =====
    async function openDetail(id) {
        currentDetailId = id;
        document.getElementById('detail-modal').classList.add('open');
        document.getElementById('modal-name').textContent = 'Laden...';
        document.getElementById('modal-phone-text').textContent = '';
        document.getElementById('modal-anliegen').textContent = '';
        document.getElementById('modal-transcript').innerHTML = '';
        document.getElementById('modal-actions').innerHTML = '';
        document.getElementById('modal-notiz').value = '';
        document.getElementById('modal-meta').innerHTML = '';

        var d = await api('/anrufe/' + id);

        document.getElementById('modal-name').textContent = d.name || 'Unbekannt';
        var phone = d.telefon || d.customer_phone || '';
        document.getElementById('modal-phone-text').textContent = phone;
        document.getElementById('modal-phone').href = 'tel:' + phone;
        document.getElementById('modal-anliegen').textContent = d.anliegen || d.description || 'Kein Anliegen erfasst';
        document.getElementById('modal-notiz').value = d.business_notes || '';

        // Meta
        var meta = '';
        if (d.start_time || d.created_at) meta += '<span>' + formatTime(d.start_time || d.created_at) + '</span>';
        if (d.duration_seconds) meta += '<span>' + d.duration_seconds + 's Dauer</span>';
        var cat = (d.category || '').toLowerCase();
        if (cat) meta += '<span>' + esc(d.category) + '</span>';
        document.getElementById('modal-meta').innerHTML = meta;

        // Actions
        var st = d.status || 'neu';
        var actions = '';
        if (st === 'neu' || st === 'in_bearbeitung') {
            actions += '<button class="btn-quick btn-action" onclick="setStatus(' + id + ',\\'zurueckgerufen\\')">Zurückgerufen</button>';
            actions += '<button class="btn-quick btn-call-action" onclick="setStatus(' + id + ',\\'termin_eingetragen\\')">Termin eingetragen</button>';
            actions += '<button class="btn-quick btn-done" onclick="setStatus(' + id + ',\\'erledigt\\')">Erledigt</button>';
        } else {
            actions += '<span class="badge badge-erledigt" style="padding:8px 16px;font-size:0.8rem;">' + statusText(st) + '</span>';
            if (st !== 'neu') {
                actions += '<button class="btn-quick btn-outline" onclick="setStatus(' + id + ',\\'neu\\')">Wieder öffnen</button>';
            }
        }
        document.getElementById('modal-actions').innerHTML = actions;

        // Transcript
        if (d.messages && d.messages.length) {
            var html = '<div class="transcript-title">Gespraechsprotokoll</div>';
            html += d.messages.map(function(m) {
                var cls = m.role === 'user' ? 'msg-user' : 'msg-assistant';
                var lbl = m.role === 'user' ? 'Anrufer' : 'Assistent';
                return '<div class="msg ' + cls + '"><div class="msg-label">' + lbl + '</div>' + esc(m.content) + '</div>';
            }).join('');
            document.getElementById('modal-transcript').innerHTML = html;
        } else {
            document.getElementById('modal-transcript').innerHTML =
                '<div class="transcript-title">Gespraechsprotokoll</div>' +
                '<div style="color:var(--text-dim);font-size:0.82rem;">Kein Transkript verfuegbar</div>';
        }
    }

    function closeDetail() {
        document.getElementById('detail-modal').classList.remove('open');
        currentDetailId = null;
    }

    // Close modal on overlay click
    document.getElementById('detail-modal').addEventListener('click', function(e) {
        if (e.target === this) closeDetail();
    });

    // ===== STATUS ACTIONS =====
    async function setStatus(id, status) {
        await api('/anrufe/' + id + '/status', 'POST', { status: status });
        closeDetail();
        refreshDashboard();
        loadAlleAnrufe();
    }

    async function quickCallback(id, btn) {
        btn.disabled = true;
        btn.textContent = '...';
        await api('/anrufe/' + id + '/status', 'POST', { status: 'zurueckgerufen' });
        btn.textContent = 'Erledigt';
        btn.className = 'btn-quick btn-done';
        btn.disabled = false;
        refreshDashboard();
    }

    async function saveNotiz() {
        if (!currentDetailId) return;
        var notiz = document.getElementById('modal-notiz').value;
        await api('/anrufe/' + currentDetailId + '/notiz', 'POST', { notiz: notiz });
        // Visual feedback
        var btn = document.querySelector('.notiz-actions .btn-action');
        var orig = btn.textContent;
        btn.textContent = 'Gespeichert!';
        setTimeout(function() { btn.textContent = orig; }, 1500);
    }

    // ===== STATISTIKEN =====
    async function loadStats() {
        try {
            var data = await api('/stats/weekly');
            renderWeekChart(data.woche);
            renderDistChart(data.verteilung);
            var min = Math.floor(data.avg_dauer_sekunden / 60);
            var sec = data.avg_dauer_sekunden % 60;
            var display = min > 0 ? min + ':' + String(sec).padStart(2, '0') : data.avg_dauer_sekunden + 's';
            document.getElementById('avg-dauer').innerHTML =
                '<div class="big">' + display + '</div>' +
                '<div class="unit">' + (min > 0 ? 'Minuten' : 'Sekunden') + '</div>';
        } catch(e) { console.error('loadStats:', e); }
    }

    function renderWeekChart(days) {
        var max = Math.max.apply(null, days.map(function(d) { return d.count; }));
        if (max === 0) max = 1;
        document.getElementById('week-chart').innerHTML = days.map(function(d) {
            var h = Math.max(4, (d.count / max) * 100);
            return '<div class="bar-col">' +
                '<div class="bar-value">' + d.count + '</div>' +
                '<div class="bar" style="height:' + h + '%"></div>' +
                '<div class="bar-label">' + d.label + '</div></div>';
        }).join('');
    }

    function renderDistChart(v) {
        var total = (v.schaden || 0) + (v.termin || 0) + (v.frage || 0);
        if (total === 0) total = 1;
        var items = [
            { label: 'Schadensmeldung', val: v.schaden || 0, color: 'var(--red)' },
            { label: 'Terminwunsch', val: v.termin || 0, color: 'var(--yellow)' },
            { label: 'Frage / Beratung', val: v.frage || 0, color: 'var(--green)' }
        ];
        document.getElementById('dist-chart').innerHTML = items.map(function(it) {
            var pct = Math.round((it.val / total) * 100);
            return '<div class="dist-row">' +
                '<div class="dist-dot" style="background:' + it.color + '"></div>' +
                '<div class="dist-label">' + it.label + '</div>' +
                '<div class="dist-bar-bg"><div class="dist-bar-fill" style="width:' + pct + '%;background:' + it.color + '"></div></div>' +
                '<div class="dist-val">' + it.val + '</div></div>';
        }).join('');
    }

    // ===== AUTO REFRESH =====
    function startAutoRefresh() {
        refreshTimer = setInterval(refreshDashboard, 15000);
    }

    async function refreshDashboard() {
        try {
            var data = await api('/dashboard');
            renderStats(data.stats);
            // Only update live feed if we're on the live tab
            if (document.getElementById('page-live').classList.contains('active')) {
                renderLiveFeed(data.anrufe, true);
            }
        } catch(e) { console.error('Refresh:', e); }
    }

    // ===== HELPERS =====
    function esc(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function formatTime(ts) {
        if (!ts) return '';
        try {
            var d = new Date(ts);
            if (isNaN(d.getTime())) return ts;
            var now = new Date();
            var isToday = d.toDateString() === now.toDateString();
            var time = d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
            if (isToday) return time + ' Uhr';
            return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit' }) + ' ' + time;
        } catch(e) { return ts; }
    }

    function statusText(s) {
        var map = {
            'neu': 'Neu', 'in_bearbeitung': 'In Bearbeitung',
            'zurueckgerufen': 'Zurückgerufen', 'termin_eingetragen': 'Termin eingetragen',
            'erledigt': 'Erledigt'
        };
        return map[s] || s;
    }

    // ===== PUSH NOTIFICATIONS =====
    function urlBase64ToUint8Array(base64String) {
        var padding = '='.repeat((4 - base64String.length % 4) % 4);
        var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        var rawData = window.atob(base64);
        var outputArray = new Uint8Array(rawData.length);
        for (var i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
        return outputArray;
    }

    async function setupPush(reg) {
        try {
            var permission = await Notification.requestPermission();
            if (permission !== 'granted') return;

            var resp = await fetch('/v/vapid-key');
            var data = await resp.json();
            if (!data.key) return;

            var sub = await reg.pushManager.getSubscription();
            if (!sub) {
                sub = await reg.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(data.key)
                });
            }
            await fetch(API + '/push/subscribe', {
                method: 'POST', headers: headers,
                body: JSON.stringify({ subscription: sub.toJSON() })
            });
            console.log('Push aktiviert');
        } catch(e) { console.log('Push setup:', e); }
    }

    // ===== GO =====
    init();
    </script>
</body>
</html>
"""
