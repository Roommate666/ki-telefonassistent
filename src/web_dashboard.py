"""
Web-Dashboard für den KI-Telefonassistenten.
Zeigt Anrufübersicht, Statistiken und Gesprächsverläufe.
"""

import logging
import functools
import json
import time
import queue
import threading
from flask import Flask, render_template_string, jsonify, request, Response
from flask_cors import CORS
from src.call_database import (
    init_database, get_recent_calls, get_stats, get_call_history,
)
from src.config_loader import load_config, list_available_businesses
from src.booking_database import init_booking_tables
from src.booking_api import booking_api
from src.booking_dashboard import booking_dashboard
from src.customer_api import customer_api
from src.customer_portal import customer_portal

logger = logging.getLogger(__name__)

app = Flask(__name__)

config = load_config()
app.secret_key = config["web_secret_key"]

# CORS fuer Booking-API und Kunden-API
CORS(app, resources={r"/api/booking/*": {"origins": "*"}, r"/api/kunde/*": {"origins": "*"}})

# --- Server-Sent Events fuer Echtzeit-Updates ---
sse_clients = []
sse_lock = threading.Lock()
_last_call_count = 0


def broadcast_update(event_type="update", data=None):
    """Sendet ein Update an alle verbundenen SSE-Clients."""
    if data is None:
        data = {}
    message = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    with sse_lock:
        dead_clients = []
        for client_queue in sse_clients:
            try:
                client_queue.put_nowait(message)
            except queue.Full:
                dead_clients.append(client_queue)
        for dead in dead_clients:
            sse_clients.remove(dead)


def check_for_new_calls():
    """Prueft periodisch auf neue Anrufe und sendet SSE-Updates."""
    global _last_call_count
    while True:
        try:
            stats = get_stats(30)
            current_count = stats.get("total_calls", 0)
            if current_count != _last_call_count:
                _last_call_count = current_count
                calls = get_recent_calls(50)
                broadcast_update("calls", {"stats": stats, "calls": calls})
        except Exception as e:
            logger.error(f"SSE check_for_new_calls Fehler: {e}")
        time.sleep(3)  # Alle 3 Sekunden pruefen


# Hintergrund-Thread starten fuer Anruf-Updates
_sse_thread = threading.Thread(target=check_for_new_calls, daemon=True)
_sse_thread.start()


# --- Admin-Auth (HTTP Basic Auth fuer Admin-Dashboard) ---
ADMIN_PASSWORD = config.get("admin_password", "")


def require_admin(f):
    """Schuetzt Admin-Routen mit HTTP Basic Auth."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not ADMIN_PASSWORD:
            # Kein Passwort gesetzt = kein Schutz (Entwicklungsmodus)
            return f(*args, **kwargs)
        auth = request.authorization
        if not auth or auth.password != ADMIN_PASSWORD:
            return Response(
                "Zugang verweigert. Bitte Admin-Passwort eingeben.",
                401,
                {"WWW-Authenticate": 'Basic realm="Admin Dashboard"'},
            )
        return f(*args, **kwargs)
    return decorated

# Booking-Module registrieren
app.register_blueprint(booking_api)
app.register_blueprint(booking_dashboard)

# Kunden-Portal registrieren
app.register_blueprint(customer_api)
app.register_blueprint(customer_portal)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KI-Telefonassistent - Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }

        .header {
            background: linear-gradient(135deg, #1e293b, #334155);
            padding: 20px 30px;
            border-bottom: 1px solid #475569;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .header h1 { font-size: 1.5rem; color: #f1f5f9; }
        .header .status {
            display: flex; align-items: center; gap: 8px;
            color: #4ade80; font-size: 0.9rem;
        }
        .header .status::before {
            content: ''; width: 10px; height: 10px;
            background: #4ade80; border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }

        .stat-card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
        }

        .stat-card .label {
            font-size: 0.8rem;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .stat-card .value {
            font-size: 2rem;
            font-weight: 700;
            color: #f1f5f9;
            margin-top: 5px;
        }

        .stat-card .sub { font-size: 0.8rem; color: #64748b; margin-top: 3px; }

        .section {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
        }

        .section h2 {
            font-size: 1.1rem;
            color: #f1f5f9;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #334155;
        }

        table { width: 100%; border-collapse: collapse; }
        th {
            text-align: left; padding: 10px 12px;
            font-size: 0.75rem; color: #94a3b8;
            text-transform: uppercase; letter-spacing: 0.05em;
            border-bottom: 1px solid #334155;
        }
        td {
            padding: 12px; border-bottom: 1px solid #1e293b;
            font-size: 0.9rem;
        }
        tr:hover td { background: #334155; }

        .badge {
            display: inline-block; padding: 3px 8px;
            border-radius: 6px; font-size: 0.75rem; font-weight: 600;
        }
        .badge-green { background: #064e3b; color: #6ee7b7; }
        .badge-yellow { background: #713f12; color: #fde047; }
        .badge-red { background: #7f1d1d; color: #fca5a5; }
        .badge-blue { background: #1e3a5f; color: #93c5fd; }

        .btn {
            padding: 6px 12px; border: none; border-radius: 6px;
            cursor: pointer; font-size: 0.8rem; font-weight: 600;
            background: #3b82f6; color: white;
        }
        .btn:hover { background: #2563eb; }

        .conversation {
            display: none; padding: 15px;
            background: #0f172a; border-radius: 8px;
            margin-top: 10px; max-height: 400px; overflow-y: auto;
        }

        .msg { padding: 8px 12px; border-radius: 8px; margin-bottom: 8px; max-width: 80%; }
        .msg-user {
            background: #1d4ed8; margin-left: auto; text-align: right;
        }
        .msg-assistant {
            background: #334155;
        }
        .msg-label {
            font-size: 0.7rem; color: #94a3b8; margin-bottom: 3px;
        }

        .refresh-bar {
            display: flex; justify-content: flex-end; margin-bottom: 10px;
        }

        @media (max-width: 768px) {
            .container { padding: 10px; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            table { font-size: 0.8rem; }
            td, th { padding: 8px 6px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>KI-Telefonassistent</h1>
        <div class="status">System aktiv</div>
    </div>

    <div class="container">
        <div class="refresh-bar">
            <button class="btn" onclick="loadData()">Aktualisieren</button>
        </div>

        <div class="stats-grid" id="stats-grid">
            <div class="stat-card">
                <div class="label">Anrufe (30 Tage)</div>
                <div class="value" id="stat-total">-</div>
            </div>
            <div class="stat-card">
                <div class="label">Durchschn. Dauer</div>
                <div class="value" id="stat-duration">-</div>
                <div class="sub">Sekunden</div>
            </div>
            <div class="stat-card">
                <div class="label">Rueckruf gewuenscht</div>
                <div class="value" id="stat-callbacks">-</div>
            </div>
            <div class="stat-card">
                <div class="label">Termine angefragt</div>
                <div class="value" id="stat-appointments">-</div>
            </div>
        </div>

        <div class="section">
            <h2>Letzte Anrufe</h2>
            <table>
                <thead>
                    <tr>
                        <th>Zeit</th>
                        <th>Anrufer</th>
                        <th>Name</th>
                        <th>Anliegen</th>
                        <th>Dauer</th>
                        <th>Dringlichkeit</th>
                        <th>Rueckruf</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody id="calls-table">
                    <tr><td colspan="8" style="text-align:center;color:#64748b;">Lade Daten...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        let eventSource = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 5;

        function updateDashboard(data) {
            if (data.stats) {
                document.getElementById('stat-total').textContent = data.stats.total_calls;
                document.getElementById('stat-duration').textContent = data.stats.avg_duration;
                document.getElementById('stat-callbacks').textContent = data.stats.callbacks_requested;
                document.getElementById('stat-appointments').textContent = data.stats.appointments_requested;
            }
            if (data.calls) {
                renderCalls(data.calls);
            }
        }

        function connectSSE() {
            if (eventSource) {
                eventSource.close();
            }

            eventSource = new EventSource('/api/sse');

            eventSource.addEventListener('calls', function(e) {
                try {
                    const data = JSON.parse(e.data);
                    updateDashboard(data);
                    reconnectAttempts = 0;
                    // Visuelles Feedback bei Update
                    const header = document.querySelector('.header .status');
                    if (header) {
                        header.style.color = '#4ade80';
                        header.textContent = 'Live - Aktualisiert';
                        setTimeout(() => {
                            header.textContent = 'System aktiv';
                        }, 2000);
                    }
                } catch (err) {
                    console.error('SSE Parsing Fehler:', err);
                }
            });

            eventSource.addEventListener('heartbeat', function(e) {
                // Verbindung ist aktiv
            });

            eventSource.onerror = function(e) {
                console.error('SSE Fehler:', e);
                eventSource.close();
                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
                    console.log(`SSE reconnect in ${delay}ms (Versuch ${reconnectAttempts})`);
                    setTimeout(connectSSE, delay);
                } else {
                    // Fallback auf Polling wenn SSE fehlschlaegt
                    console.log('SSE fehlgeschlagen, wechsle zu Polling');
                    setInterval(loadData, 10000);
                }
            };

            eventSource.onopen = function(e) {
                console.log('SSE verbunden');
                reconnectAttempts = 0;
            };
        }

        async function loadData() {
            try {
                const [statsResp, callsResp] = await Promise.all([
                    fetch('/api/stats'),
                    fetch('/api/calls')
                ]);
                const stats = await statsResp.json();
                const calls = await callsResp.json();

                document.getElementById('stat-total').textContent = stats.total_calls;
                document.getElementById('stat-duration').textContent = stats.avg_duration;
                document.getElementById('stat-callbacks').textContent = stats.callbacks_requested;
                document.getElementById('stat-appointments').textContent = stats.appointments_requested;

                renderCalls(calls);
            } catch (err) {
                console.error('Fehler beim Laden:', err);
            }
        }

        function renderCalls(calls) {
            const tbody = document.getElementById('calls-table');
            if (!calls.length) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center;color:#64748b;">Noch keine Anrufe</td></tr>';
                return;
            }

            tbody.innerHTML = calls.map(call => {
                const urgencyClass = {
                    'hoch': 'badge-red',
                    'mittel': 'badge-yellow',
                    'niedrig': 'badge-green'
                }[call.urgency] || 'badge-blue';

                const time = call.start_time ? new Date(call.start_time).toLocaleString('de-DE') : '-';

                return '<tr>' +
                    '<td>' + esc(time) + '</td>' +
                    '<td>' + esc(call.caller_number || '-') + '</td>' +
                    '<td>' + esc(call.caller_name || '-') + '</td>' +
                    '<td>' + esc(call.concern || '-') + '</td>' +
                    '<td>' + (call.duration_seconds || '-') + 's</td>' +
                    '<td><span class="badge ' + urgencyClass + '">' + esc(call.urgency || '-') + '</span></td>' +
                    '<td>' + (call.callback_requested ? '<span class="badge badge-red">Ja</span>' : 'Nein') + '</td>' +
                    '<td><button class="btn" onclick="toggleConversation(\\'' + esc(call.call_id) + '\\', this)">Anzeigen</button>' +
                        '<div class="conversation" id="conv-' + esc(call.call_id) + '"></div></td>' +
                '</tr>';
            }).join('');
        }

        async function toggleConversation(callId, btn) {
            const div = document.getElementById('conv-' + callId);
            if (div.style.display === 'block') {
                div.style.display = 'none';
                return;
            }

            try {
                const resp = await fetch('/api/calls/' + callId + '/messages');
                const messages = await resp.json();

                div.innerHTML = messages.map(msg => {
                    const cls = msg.role === 'user' ? 'msg-user' : 'msg-assistant';
                    const label = msg.role === 'user' ? 'Anrufer' : 'Assistent';
                    return '<div class="msg ' + cls + '">' +
                        '<div class="msg-label">' + label + '</div>' +
                        esc(msg.content) +
                    '</div>';
                }).join('');

                div.style.display = 'block';
            } catch (err) {
                div.innerHTML = '<p style="color:#ef4444;">Fehler beim Laden</p>';
                div.style.display = 'block';
            }
        }

        function esc(str) {
            if (!str) return '';
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        }

        // SSE starten fuer Echtzeit-Updates
        connectSSE();
    </script>
</body>
</html>
"""


@app.route("/")
@require_admin
def dashboard():
    """Haupt-Dashboard."""
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/stats")
@require_admin
def api_stats():
    """Statistik-API."""
    days = request.args.get("days", 30, type=int)
    return jsonify(get_stats(days))


@app.route("/api/calls")
@require_admin
def api_calls():
    """Letzte Anrufe."""
    limit = request.args.get("limit", 50, type=int)
    return jsonify(get_recent_calls(limit))


@app.route("/api/calls/<call_id>/messages")
@require_admin
def api_call_messages(call_id):
    """Gesprächsverlauf eines Anrufs."""
    return jsonify(get_call_history(call_id))


@app.route("/api/businesses")
@require_admin
def api_businesses():
    """Verfügbare Branchen-Konfigurationen."""
    return jsonify(list_available_businesses())


@app.route("/api/sse")
@require_admin
def api_sse():
    """Server-Sent Events Endpoint fuer Echtzeit-Updates."""
    def generate():
        client_queue = queue.Queue(maxsize=10)
        with sse_lock:
            sse_clients.append(client_queue)
        try:
            # Initiale Daten senden
            stats = get_stats(30)
            calls = get_recent_calls(50)
            yield f"event: calls\ndata: {json.dumps({'stats': stats, 'calls': calls})}\n\n"

            while True:
                try:
                    message = client_queue.get(timeout=30)
                    yield message
                except queue.Empty:
                    # Heartbeat senden um Verbindung aufrecht zu erhalten
                    yield f"event: heartbeat\ndata: {{}}\n\n"
        finally:
            with sse_lock:
                if client_queue in sse_clients:
                    sse_clients.remove(client_queue)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    init_database()
    init_booking_tables()

    if ADMIN_PASSWORD:
        logger.info("Admin-Dashboard mit Passwort-Schutz gestartet")
    else:
        logger.warning(
            "ADMIN_PASSWORD nicht gesetzt! Dashboard ist OHNE Authentifizierung erreichbar. "
            "Setze ADMIN_PASSWORD in .env fuer Produktion."
        )

    app.run(
        host=config["web_host"],
        port=config["web_port"],
        debug=config.get("web_debug", False),
    )
