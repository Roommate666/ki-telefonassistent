"""
PWA-Dashboard fuer Betriebe.
Zwei Modi:
  - 'termin': Friseur, Beauty, Massage, etc. -> Terminbuchungen verwalten
  - 'auftrag': Handwerk, Reparatur, etc. -> Auftragsanfragen verwalten
Zugang nur per Access-Token-Link.
"""

import logging
from flask import Blueprint, render_template_string, request

logger = logging.getLogger(__name__)

booking_dashboard = Blueprint("booking_dashboard", __name__)


# ============================================================
# PWA Manifest + Service Worker
# ============================================================

@booking_dashboard.route("/manifest.json")
def pwa_manifest():
    return {
        "name": "Terminverwaltung",
        "short_name": "Termine",
        "description": "Termin- und Anfragenverwaltung fuer Betriebe",
        "start_url": "/app?token=" + request.args.get("token", ""),
        "display": "standalone",
        "background_color": "#0f172a",
        "theme_color": "#3b82f6",
        "orientation": "any",
        "icons": [
            {"src": "/app/icon-192", "sizes": "192x192", "type": "image/svg+xml"},
            {"src": "/app/icon-512", "sizes": "512x512", "type": "image/svg+xml"},
        ],
    }


@booking_dashboard.route("/app/icon-192")
@booking_dashboard.route("/app/icon-512")
def pwa_icon():
    size = 512 if "512" in request.path else 192
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
        <rect width="{size}" height="{size}" rx="{size//8}" fill="#3b82f6"/>
        <text x="50%" y="55%" font-family="Arial" font-size="{size//3}" font-weight="bold"
              fill="white" text-anchor="middle" dominant-baseline="middle">T</text>
    </svg>"""
    return svg, 200, {"Content-Type": "image/svg+xml"}


@booking_dashboard.route("/sw.js")
def service_worker():
    js = """
const CACHE_NAME = 'termin-v3';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(clients.claim()));
self.addEventListener('fetch', e => {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
});
"""
    return js, 200, {"Content-Type": "application/javascript"}


# ============================================================
# Haupt-App
# ============================================================

@booking_dashboard.route("/app")
def app_main():
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
        body { font-family: -apple-system, sans-serif; background: #0f172a; color: #e2e8f0;
               display: flex; justify-content: center; align-items: center; min-height: 100vh; }
        .box { text-align: center; padding: 40px; background: #1e293b; border-radius: 16px;
               border: 1px solid #334155; max-width: 400px; }
        h1 { color: #f1f5f9; margin-bottom: 15px; }
        p { color: #94a3b8; }
    </style>
</head>
<body>
    <div class="box">
        <h1>Kein Zugang</h1>
        <p>Du brauchst einen gueltigen Zugangslink um die App zu nutzen.
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
    <meta name="theme-color" content="#3b82f6">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <link rel="manifest" href="/manifest.json?token={{ token }}">
    <title>Terminverwaltung</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --bg: #0f172a; --surface: #1e293b; --border: #334155;
            --text: #e2e8f0; --text-muted: #94a3b8; --text-dim: #64748b;
            --primary: #3b82f6; --primary-hover: #2563eb;
            --green: #4ade80; --green-bg: #064e3b;
            --yellow: #fde047; --yellow-bg: #713f12;
            --red: #fca5a5; --red-bg: #7f1d1d;
            --orange: #fb923c; --orange-bg: #7c2d12;
            --blue: #93c5fd; --blue-bg: #1e3a5f;
            --purple: #c4b5fd; --purple-bg: #3b0764;
        }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
               background: var(--bg); color: var(--text); min-height: 100vh; }

        /* Nav */
        .nav { position: fixed; bottom: 0; left: 0; right: 0; background: var(--surface);
               border-top: 1px solid var(--border); display: flex; z-index: 100;
               padding-bottom: env(safe-area-inset-bottom); }
        .nav-item { flex: 1; padding: 12px 0 8px; text-align: center; cursor: pointer;
                    color: var(--text-dim); font-size: 0.7rem; transition: color 0.2s; }
        .nav-item.active { color: var(--primary); }
        .nav-item svg { display: block; margin: 0 auto 4px; width: 24px; height: 24px; }
        .nav-item .notif { position: absolute; top: 6px; right: calc(50% - 18px);
                           background: #ef4444; color: white; border-radius: 10px;
                           font-size: 0.6rem; padding: 1px 5px; font-weight: 700; }

        /* Header */
        .header { background: linear-gradient(135deg, var(--surface), #334155);
                  padding: 16px 20px; border-bottom: 1px solid var(--border);
                  position: sticky; top: 0; z-index: 50; }
        .header h1 { font-size: 1.2rem; color: #f1f5f9; }
        .header .sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 2px; }

        /* Content */
        .content { padding: 15px 15px 90px; max-width: 800px; margin: 0 auto; }
        .page { display: none; }
        .page.active { display: block; }

        /* Stats */
        .stats-row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
        .stat-card { background: var(--surface); border: 1px solid var(--border);
                     border-radius: 12px; padding: 15px; }
        .stat-card .label { font-size: 0.7rem; color: var(--text-muted);
                            text-transform: uppercase; letter-spacing: 0.05em; }
        .stat-card .val { font-size: 1.8rem; font-weight: 700; margin-top: 4px; }

        /* Cards */
        .card { background: var(--surface); border: 1px solid var(--border);
                border-radius: 12px; padding: 15px; margin-bottom: 10px; }
        .card-header { display: flex; justify-content: space-between; align-items: flex-start; }
        .card-title { font-weight: 600; font-size: 0.95rem; }
        .card-sub { font-size: 0.8rem; color: var(--text-muted); margin-top: 3px; }
        .card-body { margin-top: 10px; font-size: 0.85rem; color: var(--text-muted); }
        .card-actions { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }

        /* Festnetz-Warnung */
        .festnetz-warn { background: var(--orange-bg); border: 1px solid var(--orange);
                         border-radius: 8px; padding: 8px 12px; margin-top: 8px;
                         font-size: 0.8rem; color: var(--orange); display: flex;
                         align-items: center; gap: 6px; }

        /* Badges */
        .badge { display: inline-block; padding: 3px 10px; border-radius: 20px;
                 font-size: 0.7rem; font-weight: 600; }
        .badge-neu { background: var(--blue-bg); color: var(--blue); }
        .badge-bestaetigt { background: var(--green-bg); color: var(--green); }
        .badge-abgelehnt { background: var(--red-bg); color: var(--red); }
        .badge-verschoben { background: var(--yellow-bg); color: var(--yellow); }
        .badge-in_bearbeitung { background: var(--yellow-bg); color: var(--yellow); }
        .badge-angebot_gesendet { background: var(--purple-bg); color: var(--purple); }
        .badge-erledigt { background: var(--green-bg); color: var(--green); }
        .badge-normal { background: var(--blue-bg); color: var(--blue); }
        .badge-dringend { background: var(--red-bg); color: var(--red); }
        .badge-hoch { background: var(--red-bg); color: var(--red); }
        .badge-notfall { background: #7f1d1d; color: #fca5a5; animation: pulse-red 1.5s infinite; }
        .badge-festnetz { background: var(--orange-bg); color: var(--orange); }
        .badge-mobil { background: var(--green-bg); color: var(--green); }

        @keyframes pulse-red { 0%,100% { opacity:1; } 50% { opacity:0.6; } }

        /* Buttons */
        .btn { padding: 8px 16px; border: none; border-radius: 8px; cursor: pointer;
               font-size: 0.8rem; font-weight: 600; transition: all 0.2s; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-success { background: #059669; color: white; }
        .btn-danger { background: #dc2626; color: white; }
        .btn-outline { background: transparent; color: var(--text-muted);
                       border: 1px solid var(--border); }
        .btn-call { background: #059669; color: white; }
        .btn-sm { padding: 6px 12px; font-size: 0.75rem; }

        /* Forms */
        .form-group { margin-bottom: 12px; }
        .form-group label { display: block; font-size: 0.8rem; color: var(--text-muted); margin-bottom: 4px; }
        .form-input { width: 100%; padding: 10px 12px; background: var(--bg);
                      border: 1px solid var(--border); border-radius: 8px; color: var(--text);
                      font-size: 0.9rem; }
        .form-input:focus { outline: none; border-color: var(--primary); }
        textarea.form-input { min-height: 80px; resize: vertical; }

        /* Modal */
        .modal-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7);
                         z-index: 200; justify-content: center; align-items: flex-end; }
        .modal-overlay.open { display: flex; }
        .modal { background: var(--surface); border-radius: 16px 16px 0 0; width: 100%;
                 max-width: 500px; max-height: 85vh; overflow-y: auto;
                 padding: 20px; padding-bottom: calc(20px + env(safe-area-inset-bottom)); }
        .modal h3 { margin-bottom: 15px; }
        .modal-close { float: right; background: none; border: none; color: var(--text-muted);
                       font-size: 1.5rem; cursor: pointer; }

        /* Filter */
        .filter-bar { display: flex; gap: 6px; margin-bottom: 15px; overflow-x: auto; }
        .filter-btn { padding: 6px 14px; border-radius: 20px; border: 1px solid var(--border);
                      background: transparent; color: var(--text-muted); font-size: 0.75rem;
                      cursor: pointer; white-space: nowrap; }
        .filter-btn.active { background: var(--primary); color: white; border-color: var(--primary); }

        .empty { text-align: center; padding: 40px 20px; color: var(--text-dim); }

        /* Suchleiste */
        .search-bar { position: relative; margin-bottom: 15px; }
        .search-bar input { width: 100%; padding: 10px 12px 10px 36px; background: var(--surface);
                            border: 1px solid var(--border); border-radius: 10px; color: var(--text);
                            font-size: 0.9rem; }
        .search-bar input:focus { outline: none; border-color: var(--primary); }
        .search-bar svg { position: absolute; left: 10px; top: 50%; transform: translateY(-50%);
                          width: 18px; height: 18px; color: var(--text-dim); }
        .search-bar .clear-btn { position: absolute; right: 10px; top: 50%; transform: translateY(-50%);
                                 background: none; border: none; color: var(--text-dim); cursor: pointer;
                                 font-size: 1.2rem; display: none; }

        /* Notizen */
        .notes-section { margin-top: 10px; border-top: 1px solid var(--border); padding-top: 8px; }
        .notes-display { font-size: 0.8rem; color: var(--text-muted); cursor: pointer;
                         padding: 4px 0; min-height: 20px; }
        .notes-display:hover { color: var(--text); }
        .notes-edit { display: none; }
        .notes-edit textarea { width: 100%; padding: 8px; background: var(--bg);
                               border: 1px solid var(--border); border-radius: 6px;
                               color: var(--text); font-size: 0.8rem; min-height: 50px; resize: vertical; }
        .notes-edit .notes-actions { display: flex; gap: 6px; margin-top: 6px; }

        /* Zusammenfassung */
        .call-summary { background: var(--bg); border-radius: 6px; padding: 8px 10px;
                        margin-top: 8px; font-size: 0.78rem; color: var(--text-muted);
                        border-left: 3px solid var(--primary); }

        /* Callback-done */
        .callback-done { background: var(--green-bg); border: 1px solid var(--green);
                         border-radius: 8px; padding: 6px 10px; margin-top: 8px;
                         font-size: 0.78rem; color: var(--green); }

        /* Duplikat-Warnung */
        .dupe-warn { background: var(--yellow-bg); border: 1px solid var(--yellow);
                     border-radius: 8px; padding: 8px 12px; margin-top: 8px;
                     font-size: 0.78rem; color: var(--yellow); }

        @media (min-width: 600px) { .stats-row { grid-template-columns: repeat(4, 1fr); } }
    </style>
</head>
<body>
    <div class="header">
        <h1 id="business-name">Laden...</h1>
        <div class="sub" id="business-type"></div>
    </div>

    <div class="content">
        <!-- DASHBOARD -->
        <div class="page active" id="page-dashboard">
            <div class="stats-row" id="stats-row"></div>
            <h3 style="margin-bottom:10px;font-size:0.95rem;" id="dash-section-title">Neues</h3>
            <div id="dash-items"></div>
        </div>

        <!-- TERMINE (Termin-Modus) / ANFRAGEN (Auftrags-Modus) -->
        <div class="page" id="page-items">
            <div class="search-bar">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <input type="text" id="search-input" placeholder="Name, Telefon, Datum suchen..." />
                <button class="clear-btn" id="search-clear" onclick="clearSearch()">&times;</button>
            </div>
            <div class="filter-bar" id="item-filters"></div>
            <div id="items-list"></div>
        </div>

        <!-- ANGEBOTE / DIENSTLEISTUNGEN -->
        <div class="page" id="page-services">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;">
                <h3 style="font-size:0.95rem;" id="services-title">Dienstleistungen</h3>
                <button class="btn btn-primary btn-sm" onclick="openServiceModal()">+ Neu</button>
            </div>
            <div id="services-list"></div>
        </div>

        <!-- EINSTELLUNGEN -->
        <div class="page" id="page-settings">
            <div class="card">
                <h3 style="font-size:0.95rem;margin-bottom:15px;">Betriebsdaten</h3>
                <div class="form-group">
                    <label>Firmenname</label>
                    <input class="form-input" id="set-name" />
                </div>
                <div class="form-group">
                    <label>Inhaber</label>
                    <input class="form-input" id="set-owner" />
                </div>
                <div class="form-group">
                    <label>E-Mail</label>
                    <input class="form-input" id="set-email" type="email" />
                </div>
                <div class="form-group">
                    <label>Telefon</label>
                    <input class="form-input" id="set-phone" type="tel" />
                </div>
                <div class="form-group">
                    <label>Adresse</label>
                    <input class="form-input" id="set-address" />
                </div>
                <button class="btn btn-primary" onclick="saveSettings()">Speichern</button>
            </div>
        </div>
    </div>

    <!-- NAVIGATION -->
    <div class="nav" id="main-nav"></div>

    <!-- MODALS -->
    <!-- Termin bestaetigen -->
    <div class="modal-overlay" id="modal-confirm">
        <div class="modal">
            <button class="modal-close" onclick="closeModal('modal-confirm')">&times;</button>
            <h3>Termin bestaetigen</h3>
            <div class="form-group">
                <label>Datum</label>
                <input class="form-input" id="confirm-date" type="date" />
            </div>
            <div class="form-group">
                <label>Uhrzeit</label>
                <input class="form-input" id="confirm-time" type="time" />
            </div>
            <input type="hidden" id="confirm-appt-id" />
            <div id="confirm-festnetz-hint" style="display:none;" class="festnetz-warn">
                Festnetz-Nummer - SMS nicht moeglich. Bitte Kunden telefonisch informieren!
            </div>
            <button class="btn btn-success" onclick="confirmAppointment()" style="width:100%;margin-top:10px;">
                Termin bestaetigen
            </button>
        </div>
    </div>

    <!-- Termin ablehnen -->
    <div class="modal-overlay" id="modal-reject">
        <div class="modal">
            <button class="modal-close" onclick="closeModal('modal-reject')">&times;</button>
            <h3>Termin ablehnen</h3>
            <div class="form-group">
                <label>Grund (optional)</label>
                <textarea class="form-input" id="reject-reason" placeholder="z.B. An dem Tag ausgebucht..."></textarea>
            </div>
            <input type="hidden" id="reject-appt-id" />
            <button class="btn btn-danger" onclick="rejectAppointment()" style="width:100%;margin-top:10px;">
                Ablehnen
            </button>
        </div>
    </div>

    <!-- Termin verschieben -->
    <div class="modal-overlay" id="modal-reschedule">
        <div class="modal">
            <button class="modal-close" onclick="closeModal('modal-reschedule')">&times;</button>
            <h3>Termin verschieben</h3>
            <div class="form-group">
                <label>Neues Datum</label>
                <input class="form-input" id="reschedule-date" type="date" />
            </div>
            <div class="form-group">
                <label>Neue Uhrzeit</label>
                <input class="form-input" id="reschedule-time" type="time" />
            </div>
            <input type="hidden" id="reschedule-appt-id" />
            <div id="reschedule-festnetz-hint" style="display:none;" class="festnetz-warn">
                Festnetz-Nummer - SMS nicht moeglich. Bitte Kunden telefonisch informieren!
            </div>
            <button class="btn btn-primary" onclick="rescheduleAppointment()" style="width:100%;margin-top:10px;">
                Verschieben
            </button>
        </div>
    </div>

    <!-- Anfrage beantworten (Auftrags-Modus) -->
    <div class="modal-overlay" id="modal-respond">
        <div class="modal">
            <button class="modal-close" onclick="closeModal('modal-respond')">&times;</button>
            <h3>Auf Anfrage reagieren</h3>
            <div class="form-group">
                <label>Status</label>
                <select class="form-input" id="respond-status">
                    <option value="in_bearbeitung">In Bearbeitung</option>
                    <option value="angebot_gesendet">Angebot gesendet</option>
                    <option value="erledigt">Erledigt</option>
                    <option value="abgelehnt">Abgelehnt</option>
                </select>
            </div>
            <div class="form-group">
                <label>Antwort / Kommentar</label>
                <textarea class="form-input" id="respond-text" placeholder="Nachricht..."></textarea>
            </div>
            <div class="form-group">
                <label>Geschaetzte Kosten (optional)</label>
                <input class="form-input" id="respond-cost" placeholder="z.B. 150-200 EUR" />
            </div>
            <div class="form-group">
                <label>Geplanter Termin (optional)</label>
                <input class="form-input" id="respond-date" type="date" />
            </div>
            <input type="hidden" id="respond-inq-id" />
            <button class="btn btn-primary" onclick="respondInquiry()" style="width:100%;margin-top:10px;">
                Absenden
            </button>
        </div>
    </div>

    <!-- Neue Dienstleistung -->
    <div class="modal-overlay" id="modal-service">
        <div class="modal">
            <button class="modal-close" onclick="closeModal('modal-service')">&times;</button>
            <h3 id="service-modal-title">Neue Dienstleistung</h3>
            <div class="form-group">
                <label>Name</label>
                <input class="form-input" id="svc-name" placeholder="z.B. Herrenhaarschnitt" />
            </div>
            <div class="form-group">
                <label>Beschreibung (optional)</label>
                <textarea class="form-input" id="svc-desc" placeholder="Details..."></textarea>
            </div>
            <div class="form-group">
                <label>Dauer (Minuten)</label>
                <input class="form-input" id="svc-duration" type="number" value="30" />
            </div>
            <div class="form-group">
                <label>Preis in Cent (z.B. 2500 = 25,00 EUR)</label>
                <input class="form-input" id="svc-price" type="number" placeholder="2500" />
            </div>
            <input type="hidden" id="svc-edit-id" />
            <button class="btn btn-primary" onclick="saveService()" style="width:100%;margin-top:10px;">
                Speichern
            </button>
        </div>
    </div>

    <script>
        const TOKEN = '{{ token }}';
        const API = '/api/booking';
        const headers = { 'Content-Type': 'application/json', 'X-Access-Token': TOKEN };
        let MODE = 'termin'; // wird beim Laden gesetzt
        let CURRENT_ITEMS = [];

        // ---- API ----
        async function api(path, method='GET', body=null) {
            const opts = { method, headers };
            if (body) opts.body = JSON.stringify(body);
            const resp = await fetch(API + path, opts);
            return resp.json();
        }

        // ---- Init ----
        async function init() {
            try {
                const data = await api('/dashboard');
                MODE = data.business.mode || 'termin';
                document.getElementById('business-name').textContent = data.business.name;
                document.getElementById('business-type').textContent = data.business.business_type;
                buildNav();
                await loadDashboard();
                loadItems();
                loadServices();
                loadSettings();
            } catch(e) { console.error('Init:', e); }
            if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(()=>{});
        }

        // ---- Navigation je nach Modus ----
        function buildNav() {
            const nav = document.getElementById('main-nav');
            const isTermin = MODE === 'termin';
            // Icons als inline SVG
            const homeIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>';
            const calIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>';
            const msgIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>';
            const toolIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>';
            const gearIcon = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>';

            const itemsLabel = isTermin ? 'Termine' : 'Anfragen';
            const itemsIcon = isTermin ? calIcon : msgIcon;

            nav.innerHTML =
                navItem('dashboard', homeIcon, 'Start', true) +
                navItem('items', itemsIcon, itemsLabel) +
                navItem('services', toolIcon, 'Angebote') +
                navItem('settings', gearIcon, 'Mehr');

            // Filter-Buttons je nach Modus
            const filterBar = document.getElementById('item-filters');
            if (isTermin) {
                filterBar.innerHTML =
                    filterBtn('', 'Alle', true) +
                    filterBtn('neu', 'Neu') +
                    filterBtn('bestaetigt', 'Bestaetigt') +
                    filterBtn('verschoben', 'Verschoben') +
                    filterBtn('abgelehnt', 'Abgelehnt');
            } else {
                filterBar.innerHTML =
                    filterBtn('', 'Alle', true) +
                    filterBtn('neu', 'Neu') +
                    filterBtn('in_bearbeitung', 'In Bearbeitung') +
                    filterBtn('angebot_gesendet', 'Angebot') +
                    filterBtn('erledigt', 'Erledigt');
            }

            // Services-Titel
            document.getElementById('services-title').textContent =
                isTermin ? 'Behandlungen / Dienstleistungen' : 'Leistungen / Angebote';

            // Event Listener
            nav.querySelectorAll('.nav-item').forEach(item => {
                item.addEventListener('click', () => {
                    nav.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
                    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
                    item.classList.add('active');
                    document.getElementById('page-' + item.dataset.page).classList.add('active');
                });
            });
            filterBar.querySelectorAll('.filter-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    filterBar.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    loadItems(btn.dataset.status);
                });
            });
        }

        function navItem(page, icon, label, active) {
            return '<div class="nav-item' + (active ? ' active' : '') + '" data-page="' + page +
                   '" style="position:relative;">' + icon + label + '</div>';
        }
        function filterBtn(status, label, active) {
            return '<button class="filter-btn' + (active ? ' active' : '') +
                   '" data-status="' + status + '">' + label + '</button>';
        }

        // ---- Dashboard ----
        async function loadDashboard() {
            const data = await api('/dashboard');
            const s = data.stats;
            const sr = document.getElementById('stats-row');
            const dashTitle = document.getElementById('dash-section-title');
            const dashItems = document.getElementById('dash-items');

            if (MODE === 'termin') {
                sr.innerHTML =
                    statCard('Neue Termine', s.appointments.neue || 0, 'var(--blue)') +
                    statCard('Bestaetigt', s.appointments.bestaetigt || 0, 'var(--green)') +
                    statCard('Abgelehnt', s.appointments.abgelehnt || 0, 'var(--red)') +
                    statCard('Angebote', s.services_count || 0, 'var(--text)');
                dashTitle.textContent = 'Neue Terminanfragen';
                const appts = await api('/appointments?status=neu&limit=10');
                dashItems.innerHTML = appts.length
                    ? appts.map(renderAppointmentCard).join('')
                    : '<div class="empty">Keine neuen Terminanfragen</div>';
            } else {
                sr.innerHTML =
                    statCard('Neue Anfragen', s.inquiries.neue || 0, 'var(--blue)') +
                    statCard('In Bearbeitung', s.inquiries.in_bearbeitung || 0, 'var(--yellow)') +
                    statCard('Erledigt', s.inquiries.erledigt || 0, 'var(--green)') +
                    statCard('Leistungen', s.services_count || 0, 'var(--text)');
                dashTitle.textContent = 'Neue Kundenanfragen';
                const inqs = await api('/inquiries?status=neu&limit=10');
                dashItems.innerHTML = inqs.length
                    ? inqs.map(renderInquiryCard).join('')
                    : '<div class="empty">Keine neuen Anfragen</div>';
            }
        }

        function statCard(label, value, color) {
            return '<div class="stat-card"><div class="label">' + label +
                   '</div><div class="val" style="color:' + color + '">' + value + '</div></div>';
        }

        // ---- Items (Termine oder Anfragen) ----
        async function loadItems(status) {
            const list = document.getElementById('items-list');
            if (MODE === 'termin') {
                const qs = status ? '?status=' + status : '';
                const items = await api('/appointments' + qs);
                CURRENT_ITEMS = items;
                list.innerHTML = items.length
                    ? items.map(renderAppointmentCard).join('')
                    : '<div class="empty">Keine Termine</div>';
            } else {
                const qs = status ? '?status=' + status : '';
                const items = await api('/inquiries' + qs);
                CURRENT_ITEMS = items;
                list.innerHTML = items.length
                    ? items.map(renderInquiryCard).join('')
                    : '<div class="empty">Keine Anfragen</div>';
            }
            // Duplikat-Check nach Laden
            checkDuplicatesForCards();
        }

        // ---- Termin-Card (Friseur/Beauty Modus) ----
        function renderAppointmentCard(a) {
            const isFestnetz = a.phone_type === 'festnetz';
            const statusBadge = '<span class="badge badge-' + a.status + '">' + statusText(a.status) + '</span>';
            const phoneBadge = isFestnetz
                ? ' <span class="badge badge-festnetz">Festnetz</span>'
                : ' <span class="badge badge-mobil">Mobil</span>';

            const svc = a.service_name || a.service_name_free || '';
            const staff = a.preferred_staff ? ' (Wunsch: ' + a.preferred_staff + ')' : '';
            const date = a.requested_date
                ? a.requested_date + (a.requested_time ? ' um ' + a.requested_time : '')
                : 'Kein Wunschtermin';

            // Anruf-Zusammenfassung
            let summaryHtml = '';
            if (a.call_summary) {
                summaryHtml = '<div class="call-summary">Anruf: ' + esc(a.call_summary) + '</div>';
            }

            let actions = '';
            if (a.status === 'neu') {
                actions = '<div class="card-actions">' +
                    '<button class="btn btn-success btn-sm" onclick="openConfirmModal(' + a.id + ',' + isFestnetz + ')">Bestaetigen</button>' +
                    '<button class="btn btn-danger btn-sm" onclick="openRejectModal(' + a.id + ')">Ablehnen</button>' +
                    '<button class="btn btn-outline btn-sm" onclick="openRescheduleModal(' + a.id + ',' + isFestnetz + ')">Verschieben</button>' +
                    (isFestnetz ? '<a href="tel:' + (a.customer_phone||'') + '" class="btn btn-call btn-sm">Anrufen</a>' : '') +
                '</div>';
            } else if (a.status === 'bestaetigt' || a.status === 'verschoben') {
                actions = '<div class="card-actions">' +
                    '<button class="btn btn-outline btn-sm" onclick="openRescheduleModal(' + a.id + ',' + isFestnetz + ')">Verschieben</button>' +
                '</div>';
            }
            if (a.confirmed_date) {
                actions += '<div style="margin-top:8px;font-size:0.8rem;color:var(--green);">Bestaetigt: ' +
                    a.confirmed_date + (a.confirmed_time ? ' ' + a.confirmed_time : '') + '</div>';
            }

            // Festnetz-Warnung + Rueckruf-Tracking
            let festnetzHint = '';
            if (isFestnetz && a.callback_required && !a.callback_done) {
                festnetzHint = '<div class="festnetz-warn">' +
                    'Festnetz - kein SMS. Bitte Kunden anrufen! ' +
                    '<button class="btn btn-sm" style="background:var(--orange);color:#000;margin-left:auto;" ' +
                    'onclick="markCallbackDone(\'termin\',' + a.id + ',this)">Erledigt</button></div>';
            } else if (isFestnetz && a.callback_done) {
                festnetzHint = '<div class="callback-done">Rueckruf erledigt</div>';
            }

            // Duplikat-Warnung (wird async geladen)
            const dupeId = 'dupe-appt-' + a.id;

            // Notizen
            const notesHtml = renderNotesSection('termin', a.id, a.business_notes || '');

            return '<div class="card" data-phone="' + esc(a.customer_phone||'') + '" data-type="termin" data-id="' + a.id + '">' +
                '<div class="card-header"><div>' +
                '<div class="card-title">' + esc(a.customer_name || 'Unbekannt') + '</div>' +
                '<div class="card-sub">' + esc(a.customer_phone || '') + phoneBadge + '</div>' +
                '</div>' + statusBadge + '</div>' +
                '<div class="card-body">' +
                (svc ? '<strong>' + esc(svc) + '</strong>' + esc(staff) + '<br>' : '') +
                'Wunschtermin: ' + esc(date) +
                (a.notes ? '<br>' + esc(a.notes) : '') + '</div>' +
                summaryHtml +
                '<div id="' + dupeId + '"></div>' +
                festnetzHint + actions + notesHtml + '</div>';
        }

        // ---- Anfrage-Card (Handwerker Modus) ----
        function renderInquiryCard(q) {
            const isFestnetz = q.phone_type === 'festnetz';
            const statusBadge = '<span class="badge badge-' + q.status + '">' + statusText(q.status) + '</span>';
            const urgBadge = q.urgency && q.urgency !== 'normal'
                ? ' <span class="badge badge-' + q.urgency + '">' + q.urgency + '</span>' : '';
            const phoneBadge = isFestnetz
                ? ' <span class="badge badge-festnetz">Festnetz</span>'
                : '';

            // Anruf-Zusammenfassung
            let summaryHtml = '';
            if (q.call_summary) {
                summaryHtml = '<div class="call-summary">Anruf: ' + esc(q.call_summary) + '</div>';
            }

            let actions = '';
            if (q.status === 'neu' || q.status === 'in_bearbeitung') {
                actions = '<div class="card-actions">' +
                    '<button class="btn btn-primary btn-sm" onclick="openRespondModal(' + q.id + ')">Reagieren</button>' +
                    '<a href="tel:' + (q.customer_phone||'') + '" class="btn btn-call btn-sm">Anrufen</a>' +
                '</div>';
            }
            if (q.response_text) {
                actions += '<div style="margin-top:8px;font-size:0.8rem;color:var(--text-muted);border-top:1px solid var(--border);padding-top:8px;">' +
                    '<strong>Antwort:</strong> ' + q.response_text +
                    (q.estimated_cost ? '<br><strong>Kosten:</strong> ' + q.estimated_cost : '') +
                    (q.scheduled_date ? '<br><strong>Termin:</strong> ' + q.scheduled_date : '') +
                    '</div>';
            }

            // Festnetz-Warnung + Rueckruf-Tracking
            let festnetzHint = '';
            if (isFestnetz && q.callback_required && !q.callback_done) {
                festnetzHint = '<div class="festnetz-warn">' +
                    'Festnetz - kein SMS. Bitte Kunden zurueckrufen! ' +
                    '<button class="btn btn-sm" style="background:var(--orange);color:#000;margin-left:auto;" ' +
                    'onclick="markCallbackDone(\'auftrag\',' + q.id + ',this)">Erledigt</button></div>';
            } else if (isFestnetz && q.callback_done) {
                festnetzHint = '<div class="callback-done">Rueckruf erledigt</div>';
            }

            // Duplikat-Warnung
            const dupeId = 'dupe-inq-' + q.id;

            // Notizen
            const notesHtml = renderNotesSection('auftrag', q.id, q.business_notes || '');

            return '<div class="card" data-phone="' + esc(q.customer_phone||'') + '" data-type="auftrag" data-id="' + q.id + '">' +
                '<div class="card-header"><div>' +
                '<div class="card-title">' + esc(q.customer_name || 'Unbekannt') + '</div>' +
                '<div class="card-sub">' + esc(q.customer_phone || '') + phoneBadge +
                (q.customer_address ? ' | ' + esc(q.customer_address) : '') + '</div>' +
                '</div><div>' + statusBadge + urgBadge + '</div></div>' +
                '<div class="card-body">' + esc(q.description || 'Keine Beschreibung') +
                (q.category ? '<br><strong>Kategorie:</strong> ' + esc(q.category) : '') + '</div>' +
                summaryHtml +
                '<div id="' + dupeId + '"></div>' +
                festnetzHint + actions + notesHtml + '</div>';
        }

        function statusText(s) {
            const map = {
                'neu': 'Neu', 'bestaetigt': 'Bestaetigt', 'abgelehnt': 'Abgelehnt',
                'verschoben': 'Verschoben', 'erledigt': 'Erledigt',
                'in_bearbeitung': 'In Bearbeitung', 'angebot_gesendet': 'Angebot gesendet'
            };
            return map[s] || s;
        }

        // ---- Services ----
        async function loadServices() {
            const svcs = await api('/services');
            const list = document.getElementById('services-list');
            list.innerHTML = svcs.length
                ? svcs.map(renderServiceCard).join('')
                : '<div class="empty">Noch keine Dienstleistungen angelegt.<br>Lege Angebote an, damit deine Kunden wissen was du anbietest.</div>';
        }

        function renderServiceCard(s) {
            const price = s.price_cents ? (s.price_cents / 100).toFixed(2).replace('.', ',') + ' EUR' : '-';
            return '<div class="card"><div class="card-header"><div><div class="card-title">' + s.name + '</div>' +
                '<div class="card-sub">' + s.duration_minutes + ' Min. | ' + price + '</div></div>' +
                '<div class="card-actions">' +
                '<button class="btn btn-outline btn-sm" onclick="editService(' + s.id + ',\'' +
                    esc(s.name) + '\',\'' + esc(s.description||'') + '\',' + s.duration_minutes + ',' + (s.price_cents||'null') + ')">Bearbeiten</button>' +
                '<button class="btn btn-danger btn-sm" onclick="deleteService(' + s.id + ')">Entfernen</button>' +
                '</div></div>' +
                (s.description ? '<div class="card-body">' + s.description + '</div>' : '') + '</div>';
        }

        function esc(str) {
            if (!str) return '';
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }

        // ---- Settings ----
        async function loadSettings() {
            const biz = await api('/business');
            document.getElementById('set-name').value = biz.name || '';
            document.getElementById('set-owner').value = biz.owner_name || '';
            document.getElementById('set-email').value = biz.email || '';
            document.getElementById('set-phone').value = biz.phone || '';
            document.getElementById('set-address').value = biz.address || '';
        }

        async function saveSettings() {
            await api('/business', 'PUT', {
                name: document.getElementById('set-name').value,
                owner_name: document.getElementById('set-owner').value,
                email: document.getElementById('set-email').value,
                phone: document.getElementById('set-phone').value,
                address: document.getElementById('set-address').value,
            });
            alert('Gespeichert!');
            loadDashboard();
        }

        // ---- Modals ----
        function openModal(id) { document.getElementById(id).classList.add('open'); }
        function closeModal(id) { document.getElementById(id).classList.remove('open'); }

        function openConfirmModal(apptId, isFestnetz) {
            document.getElementById('confirm-appt-id').value = apptId;
            document.getElementById('confirm-date').value = '';
            document.getElementById('confirm-time').value = '';
            document.getElementById('confirm-festnetz-hint').style.display = isFestnetz ? 'flex' : 'none';
            openModal('modal-confirm');
        }

        async function confirmAppointment() {
            const id = document.getElementById('confirm-appt-id').value;
            await api('/appointments/' + id + '/confirm', 'POST', {
                confirmed_date: document.getElementById('confirm-date').value,
                confirmed_time: document.getElementById('confirm-time').value,
            });
            closeModal('modal-confirm');
            loadDashboard(); loadItems();
        }

        function openRejectModal(apptId) {
            document.getElementById('reject-appt-id').value = apptId;
            document.getElementById('reject-reason').value = '';
            openModal('modal-reject');
        }

        async function rejectAppointment() {
            const id = document.getElementById('reject-appt-id').value;
            await api('/appointments/' + id + '/reject', 'POST', {
                reason: document.getElementById('reject-reason').value,
            });
            closeModal('modal-reject');
            loadDashboard(); loadItems();
        }

        function openRespondModal(inqId) {
            document.getElementById('respond-inq-id').value = inqId;
            document.getElementById('respond-text').value = '';
            document.getElementById('respond-cost').value = '';
            document.getElementById('respond-date').value = '';
            document.getElementById('respond-status').value = 'in_bearbeitung';
            openModal('modal-respond');
        }

        async function respondInquiry() {
            const id = document.getElementById('respond-inq-id').value;
            await api('/inquiries/' + id + '/respond', 'POST', {
                status: document.getElementById('respond-status').value,
                response_text: document.getElementById('respond-text').value,
                estimated_cost: document.getElementById('respond-cost').value,
                scheduled_date: document.getElementById('respond-date').value,
            });
            closeModal('modal-respond');
            loadDashboard(); loadItems();
        }

        // ---- Verschieben ----
        function openRescheduleModal(apptId, isFestnetz) {
            document.getElementById('reschedule-appt-id').value = apptId;
            document.getElementById('reschedule-date').value = '';
            document.getElementById('reschedule-time').value = '';
            document.getElementById('reschedule-festnetz-hint').style.display = isFestnetz ? 'flex' : 'none';
            openModal('modal-reschedule');
        }

        async function rescheduleAppointment() {
            const id = document.getElementById('reschedule-appt-id').value;
            const date = document.getElementById('reschedule-date').value;
            const time = document.getElementById('reschedule-time').value;
            if (!date) { alert('Bitte neues Datum angeben'); return; }
            await api('/appointments/' + id + '/reschedule', 'POST', {
                confirmed_date: date,
                confirmed_time: time,
            });
            closeModal('modal-reschedule');
            loadDashboard(); loadItems();
        }

        // ---- Notizen ----
        function renderNotesSection(itemType, itemId, currentNotes) {
            const displayText = currentNotes || '<span style="color:var(--text-dim);">Notiz hinzufuegen...</span>';
            return '<div class="notes-section">' +
                '<div class="notes-display" id="notes-display-' + itemType + '-' + itemId + '" ' +
                'onclick="toggleNotesEdit(\'' + itemType + '\',' + itemId + ')">' +
                '<strong style="font-size:0.7rem;text-transform:uppercase;color:var(--text-dim);">Notizen</strong><br>' +
                displayText + '</div>' +
                '<div class="notes-edit" id="notes-edit-' + itemType + '-' + itemId + '">' +
                '<textarea id="notes-text-' + itemType + '-' + itemId + '">' + esc(currentNotes) + '</textarea>' +
                '<div class="notes-actions">' +
                '<button class="btn btn-primary btn-sm" onclick="saveNotes(\'' + itemType + '\',' + itemId + ')">Speichern</button>' +
                '<button class="btn btn-outline btn-sm" onclick="toggleNotesEdit(\'' + itemType + '\',' + itemId + ')">Abbrechen</button>' +
                '</div></div></div>';
        }

        function toggleNotesEdit(itemType, itemId) {
            const display = document.getElementById('notes-display-' + itemType + '-' + itemId);
            const edit = document.getElementById('notes-edit-' + itemType + '-' + itemId);
            if (edit.style.display === 'block') {
                edit.style.display = 'none';
                display.style.display = 'block';
            } else {
                edit.style.display = 'block';
                display.style.display = 'none';
            }
        }

        async function saveNotes(itemType, itemId) {
            const text = document.getElementById('notes-text-' + itemType + '-' + itemId).value;
            await api('/notes/' + itemType + '/' + itemId, 'PUT', { notes: text });
            // Update display
            const display = document.getElementById('notes-display-' + itemType + '-' + itemId);
            display.innerHTML = '<strong style="font-size:0.7rem;text-transform:uppercase;color:var(--text-dim);">Notizen</strong><br>' +
                (text || '<span style="color:var(--text-dim);">Notiz hinzufuegen...</span>');
            toggleNotesEdit(itemType, itemId);
        }

        // ---- Rueckruf-Tracking ----
        async function markCallbackDone(itemType, itemId, btn) {
            await api('/callback/' + itemType + '/' + itemId, 'POST');
            // UI sofort aktualisieren
            const warn = btn.closest('.festnetz-warn');
            warn.outerHTML = '<div class="callback-done">Rueckruf erledigt</div>';
        }

        // ---- Suche ----
        let searchTimeout = null;

        function initSearch() {
            const input = document.getElementById('search-input');
            const clearBtn = document.getElementById('search-clear');
            input.addEventListener('input', () => {
                clearBtn.style.display = input.value ? 'block' : 'none';
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    if (input.value.length >= 2) {
                        searchItems(input.value);
                    } else if (input.value.length === 0) {
                        loadItems();
                    }
                }, 300);
            });
        }

        function clearSearch() {
            const input = document.getElementById('search-input');
            input.value = '';
            document.getElementById('search-clear').style.display = 'none';
            loadItems();
        }

        async function searchItems(query) {
            const list = document.getElementById('items-list');
            try {
                const items = await api('/search?q=' + encodeURIComponent(query));
                CURRENT_ITEMS = items;
                if (MODE === 'termin') {
                    list.innerHTML = items.length
                        ? items.map(renderAppointmentCard).join('')
                        : '<div class="empty">Keine Treffer fuer "' + esc(query) + '"</div>';
                } else {
                    list.innerHTML = items.length
                        ? items.map(renderInquiryCard).join('')
                        : '<div class="empty">Keine Treffer fuer "' + esc(query) + '"</div>';
                }
                checkDuplicatesForCards();
            } catch(e) { console.error('Suche:', e); }
        }

        // ---- Duplikat-Erkennung ----
        async function checkDuplicatesForCards() {
            const cards = document.querySelectorAll('.card[data-phone]');
            const checked = new Set();
            for (const card of cards) {
                const phone = card.dataset.phone;
                const type = card.dataset.type;
                const id = card.dataset.id;
                if (!phone || checked.has(phone)) continue;
                checked.add(phone);
                try {
                    const dupes = await api('/duplicates?phone=' + encodeURIComponent(phone) + '&exclude_id=' + id);
                    if (dupes.length > 0) {
                        // Warnung bei allen Cards mit dieser Nummer
                        document.querySelectorAll('.card[data-phone="' + phone + '"]').forEach(c => {
                            const dupeEl = c.querySelector('[id^="dupe-"]');
                            if (dupeEl) {
                                dupeEl.innerHTML = '<div class="dupe-warn">' +
                                    'Achtung: ' + dupes.length + ' weitere aktive ' +
                                    (type === 'termin' ? 'Termine' : 'Anfragen') +
                                    ' mit dieser Nummer vorhanden</div>';
                            }
                        });
                    }
                } catch(e) { /* ignorieren */ }
            }
        }

        function openServiceModal() {
            document.getElementById('service-modal-title').textContent = 'Neue Dienstleistung';
            document.getElementById('svc-edit-id').value = '';
            document.getElementById('svc-name').value = '';
            document.getElementById('svc-desc').value = '';
            document.getElementById('svc-duration').value = '30';
            document.getElementById('svc-price').value = '';
            openModal('modal-service');
        }

        function editService(id, name, desc, dur, price) {
            document.getElementById('service-modal-title').textContent = 'Bearbeiten';
            document.getElementById('svc-edit-id').value = id;
            document.getElementById('svc-name').value = name;
            document.getElementById('svc-desc').value = desc;
            document.getElementById('svc-duration').value = dur;
            document.getElementById('svc-price').value = price || '';
            openModal('modal-service');
        }

        async function saveService() {
            const editId = document.getElementById('svc-edit-id').value;
            const body = {
                name: document.getElementById('svc-name').value,
                description: document.getElementById('svc-desc').value,
                duration_minutes: parseInt(document.getElementById('svc-duration').value) || 30,
                price_cents: parseInt(document.getElementById('svc-price').value) || null,
            };
            if (!body.name) { alert('Name ist erforderlich'); return; }
            if (editId) { await api('/services/' + editId, 'PUT', body); }
            else { await api('/services', 'POST', body); }
            closeModal('modal-service');
            loadServices();
        }

        async function deleteService(id) {
            if (!confirm('Wirklich entfernen?')) return;
            await api('/services/' + id, 'DELETE');
            loadServices();
        }

        init();
        initSearch();
        setInterval(loadDashboard, 30000);
    </script>
</body>
</html>
"""
