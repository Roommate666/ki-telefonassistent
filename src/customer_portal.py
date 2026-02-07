"""
Kunden-Portal (PWA) - Zeigt Reservierungen und erlaubt Stornierung/Aenderung.
Erreichbar unter /kunde?t=TOKEN
"""

import logging
from flask import Blueprint, render_template_string, request

logger = logging.getLogger(__name__)

customer_portal = Blueprint("customer_portal", __name__)

CUSTOMER_PORTAL_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Meine Reservierungen</title>
    <meta name="theme-color" content="#0f172a">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <link rel="manifest" href="/kunde/manifest.json">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a; color: #e2e8f0; min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1e293b, #334155);
            padding: 20px; border-bottom: 1px solid #475569;
            text-align: center;
        }
        .header h1 { font-size: 1.3rem; color: #f1f5f9; }
        .header .sub { font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }
        .container { max-width: 600px; margin: 0 auto; padding: 16px; }
        .empty { text-align: center; padding: 40px 20px; color: #64748b; }
        .card {
            background: #1e293b; border: 1px solid #334155;
            border-radius: 12px; padding: 16px; margin-bottom: 12px;
        }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .card-service { font-size: 1rem; font-weight: 600; color: #f1f5f9; }
        .badge {
            display: inline-block; padding: 3px 10px;
            border-radius: 20px; font-size: 0.7rem; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.05em;
        }
        .badge-neu { background: #1e3a5f; color: #93c5fd; }
        .badge-bestaetigt { background: #064e3b; color: #6ee7b7; }
        .badge-abgelehnt { background: #7f1d1d; color: #fca5a5; }
        .badge-verschoben { background: #713f12; color: #fde047; }
        .badge-storniert { background: #44403c; color: #a8a29e; }
        .badge-erledigt { background: #1e293b; color: #64748b; }
        .card-details { font-size: 0.85rem; color: #94a3b8; }
        .card-details .row { display: flex; gap: 8px; margin-bottom: 4px; }
        .card-details .label { color: #64748b; min-width: 60px; }
        .card-notes { font-size: 0.8rem; color: #cbd5e1; margin-top: 8px;
                      padding-top: 8px; border-top: 1px solid #334155; }
        .card-actions { display: flex; gap: 8px; margin-top: 12px; }
        .btn {
            flex: 1; padding: 10px; border: none; border-radius: 8px;
            font-size: 0.85rem; font-weight: 600; cursor: pointer;
            transition: opacity 0.2s;
        }
        .btn:active { opacity: 0.7; }
        .btn-cancel { background: #7f1d1d; color: #fca5a5; }
        .btn-change { background: #1e3a5f; color: #93c5fd; }
        .btn-disabled { background: #334155; color: #64748b; cursor: not-allowed; }

        /* Modal */
        .modal-overlay {
            display: none; position: fixed; inset: 0;
            background: rgba(0,0,0,0.7); z-index: 100;
            justify-content: center; align-items: flex-end;
        }
        .modal-overlay.active { display: flex; }
        .modal {
            background: #1e293b; border-top-left-radius: 20px;
            border-top-right-radius: 20px; width: 100%; max-width: 600px;
            padding: 24px; max-height: 80vh; overflow-y: auto;
            animation: slideUp 0.3s ease;
        }
        @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
        .modal h3 { font-size: 1.1rem; margin-bottom: 16px; color: #f1f5f9; }
        .modal p { font-size: 0.9rem; color: #94a3b8; margin-bottom: 16px; }
        .modal-actions { display: flex; gap: 10px; }
        .btn-confirm { background: #dc2626; color: white; }
        .btn-submit { background: #3b82f6; color: white; }
        .btn-close { background: #334155; color: #e2e8f0; }
        .input-group { margin-bottom: 16px; }
        .input-group label { display: block; font-size: 0.8rem; color: #94a3b8; margin-bottom: 6px; }
        .input-group input[type="date"] {
            width: 100%; padding: 12px 14px; border: 1px solid #475569;
            border-radius: 8px; background: #0f172a; color: #e2e8f0;
            font-size: 1rem; cursor: pointer;
            -webkit-appearance: none; appearance: none;
        }
        .input-group input[type="date"]:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.3); }
        .input-group input[type="date"]::-webkit-calendar-picker-indicator {
            filter: invert(0.7); cursor: pointer; font-size: 1.2rem;
        }
        /* Uhrzeit-Grid */
        .time-grid {
            display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;
        }
        .time-slot {
            padding: 10px 4px; border: 1px solid #475569; border-radius: 8px;
            background: #0f172a; color: #94a3b8; font-size: 0.85rem;
            text-align: center; cursor: pointer; transition: all 0.15s;
            font-weight: 500;
        }
        .time-slot:hover { border-color: #3b82f6; color: #e2e8f0; }
        .time-slot.selected {
            background: #3b82f6; color: white; border-color: #3b82f6;
            font-weight: 700;
        }
        .time-slot.disabled {
            opacity: 0.3; cursor: not-allowed; pointer-events: none;
        }
        .selected-time-display {
            text-align: center; margin-top: 8px; font-size: 0.8rem; color: #64748b;
            min-height: 20px;
        }
        .loading { text-align: center; padding: 40px; color: #64748b; }
        .error { text-align: center; padding: 40px; color: #fca5a5; }
        .toast {
            position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
            background: #064e3b; color: #6ee7b7; padding: 12px 24px;
            border-radius: 8px; font-size: 0.85rem; font-weight: 600;
            z-index: 200; display: none; animation: fadeIn 0.3s;
        }
        .toast.error-toast { background: #7f1d1d; color: #fca5a5; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    </style>
</head>
<body>
    <div class="header">
        <h1 id="business-name">Meine Reservierungen</h1>
        <div class="sub" id="business-phone"></div>
    </div>
    <div class="container">
        <div class="loading" id="loading">Lade Reservierungen...</div>
        <div class="error" id="error" style="display:none;"></div>
        <div id="reservations"></div>
    </div>

    <!-- Stornierung Modal -->
    <div class="modal-overlay" id="cancel-modal">
        <div class="modal">
            <h3>Reservierung stornieren</h3>
            <p id="cancel-info"></p>
            <div class="modal-actions">
                <button class="btn btn-close" onclick="closeModal('cancel-modal')">Abbrechen</button>
                <button class="btn btn-confirm" id="cancel-confirm-btn">Stornieren</button>
            </div>
        </div>
    </div>

    <!-- Aenderung Modal -->
    <div class="modal-overlay" id="change-modal">
        <div class="modal">
            <h3>Termin aendern</h3>
            <p>Waehlen Sie Ihren neuen Wunschtermin:</p>
            <div class="input-group">
                <label>Neues Datum</label>
                <input type="date" id="new-date">
            </div>
            <div class="input-group">
                <label>Neue Uhrzeit</label>
                <div class="time-grid" id="time-grid"></div>
                <div class="selected-time-display" id="selected-time-display"></div>
                <input type="hidden" id="new-time">
            </div>
            <div class="modal-actions">
                <button class="btn btn-close" onclick="closeModal('change-modal')">Abbrechen</button>
                <button class="btn btn-submit" id="change-confirm-btn">Anfrage senden</button>
            </div>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        const TOKEN = new URLSearchParams(window.location.search).get('t');
        let currentAptId = null;

        const STATUS_MAP = {
            'neu': { label: 'Anfrage eingegangen', cls: 'badge-neu' },
            'bestaetigt': { label: 'Bestätigt', cls: 'badge-bestaetigt' },
            'abgelehnt': { label: 'Abgelehnt', cls: 'badge-abgelehnt' },
            'verschoben': { label: 'Verschoben', cls: 'badge-verschoben' },
            'storniert': { label: 'Storniert', cls: 'badge-storniert' },
            'erledigt': { label: 'Erledigt', cls: 'badge-erledigt' },
        };

        function esc(s) {
            if (!s) return '';
            return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
                .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
        }

        function formatDate(d) {
            if (!d) return '-';
            try {
                const parts = d.split('-');
                if (parts.length === 3) return parts[2] + '.' + parts[1] + '.' + parts[0];
            } catch(e) {}
            return d;
        }

        async function loadReservations() {
            if (!TOKEN) {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').textContent = 'Kein gültiger Zugangslink.';
                document.getElementById('error').style.display = 'block';
                return;
            }
            try {
                const resp = await fetch('/api/kunde/reservierungen?t=' + encodeURIComponent(TOKEN));
                if (!resp.ok) throw new Error('Token ungültig');
                const data = await resp.json();

                document.getElementById('business-name').textContent = data.business_name || 'Meine Reservierungen';
                if (data.business_phone) {
                    document.getElementById('business-phone').textContent = 'Tel: ' + data.business_phone;
                }
                document.getElementById('loading').style.display = 'none';

                const container = document.getElementById('reservations');
                if (!data.reservierungen || data.reservierungen.length === 0) {
                    container.innerHTML = '<div class="empty">Keine Reservierungen vorhanden.</div>';
                    return;
                }

                container.innerHTML = data.reservierungen.map(function(r) {
                    const st = STATUS_MAP[r.status] || { label: r.status, cls: 'badge-neu' };
                    const isActive = !['storniert', 'erledigt', 'abgelehnt'].includes(r.status);
                    const date = r.confirmed_date || r.requested_date;
                    const time = r.confirmed_time || r.requested_time;

                    return '<div class="card">' +
                        '<div class="card-header">' +
                            '<span class="card-service">' + esc(r.service_name) + '</span>' +
                            '<span class="badge ' + st.cls + '">' + esc(st.label) + '</span>' +
                        '</div>' +
                        '<div class="card-details">' +
                            '<div class="row"><span class="label">Datum:</span><span>' + esc(formatDate(date)) + '</span></div>' +
                            '<div class="row"><span class="label">Uhrzeit:</span><span>' + esc(time || '-') + '</span></div>' +
                            '<div class="row"><span class="label">Name:</span><span>' + esc(r.customer_name || '-') + '</span></div>' +
                        '</div>' +
                        (r.notes ? '<div class="card-notes">' + esc(r.notes) + '</div>' : '') +
                        (isActive ? '<div class="card-actions">' +
                            '<button class="btn btn-cancel" onclick="openCancel(' + r.id + ', \\'' + esc(formatDate(date)) + '\\', \\'' + esc(time || '') + '\\')">Stornieren</button>' +
                            '<button class="btn btn-change" onclick="openChange(' + r.id + ')">Termin ändern</button>' +
                        '</div>' : '') +
                    '</div>';
                }).join('');

            } catch(e) {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('error').textContent = 'Fehler beim Laden: ' + e.message;
                document.getElementById('error').style.display = 'block';
            }
        }

        function openCancel(id, date, time) {
            currentAptId = id;
            document.getElementById('cancel-info').textContent =
                'Möchten Sie die Reservierung am ' + date + (time ? ' um ' + time : '') + ' wirklich stornieren?';
            document.getElementById('cancel-modal').classList.add('active');
        }

        // Uhrzeit-Grid generieren (11:00 - 21:45 in 15-Min-Schritten)
        function buildTimeGrid() {
            const grid = document.getElementById('time-grid');
            grid.innerHTML = '';
            const slots = [];
            for (let h = 11; h <= 21; h++) {
                for (let m = 0; m < 60; m += 15) {
                    if (h === 21 && m > 45) break;
                    const hh = String(h).padStart(2, '0');
                    const mm = String(m).padStart(2, '0');
                    slots.push(hh + ':' + mm);
                }
            }
            slots.forEach(function(t) {
                const btn = document.createElement('div');
                btn.className = 'time-slot';
                btn.textContent = t;
                btn.dataset.time = t;
                btn.addEventListener('click', function() {
                    grid.querySelectorAll('.time-slot').forEach(function(s) { s.classList.remove('selected'); });
                    btn.classList.add('selected');
                    document.getElementById('new-time').value = t;
                    document.getElementById('selected-time-display').textContent = 'Gewählt: ' + t + ' Uhr';
                });
                grid.appendChild(btn);
            });
        }

        function openChange(id) {
            currentAptId = id;
            // Datum: min = heute
            var today = new Date().toISOString().split('T')[0];
            var dateInput = document.getElementById('new-date');
            dateInput.value = '';
            dateInput.setAttribute('min', today);
            // Uhrzeit zuruecksetzen
            document.getElementById('new-time').value = '';
            document.getElementById('selected-time-display').textContent = '';
            buildTimeGrid();
            document.getElementById('change-modal').classList.add('active');
        }

        function closeModal(id) {
            document.getElementById(id).classList.remove('active');
            currentAptId = null;
        }

        function showToast(msg, isError) {
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.className = 'toast' + (isError ? ' error-toast' : '');
            t.style.display = 'block';
            setTimeout(function() { t.style.display = 'none'; }, 3000);
        }

        document.getElementById('cancel-confirm-btn').addEventListener('click', async function() {
            if (!currentAptId) return;
            this.disabled = true;
            this.textContent = 'Wird storniert...';
            try {
                const resp = await fetch('/api/kunde/reservierungen/' + currentAptId + '/stornieren?t=' + encodeURIComponent(TOKEN), {
                    method: 'POST'
                });
                const data = await resp.json();
                if (resp.ok) {
                    showToast('Reservierung storniert');
                    closeModal('cancel-modal');
                    loadReservations();
                } else {
                    showToast(data.error || 'Fehler', true);
                }
            } catch(e) {
                showToast('Netzwerkfehler', true);
            }
            this.disabled = false;
            this.textContent = 'Stornieren';
        });

        document.getElementById('change-confirm-btn').addEventListener('click', async function() {
            if (!currentAptId) return;
            const newDate = document.getElementById('new-date').value;
            const newTime = document.getElementById('new-time').value;
            if (!newDate) {
                showToast('Bitte ein Datum auswählen', true);
                return;
            }
            if (!newTime) {
                showToast('Bitte eine Uhrzeit auswählen', true);
                return;
            }
            this.disabled = true;
            this.textContent = 'Wird gesendet...';
            try {
                const resp = await fetch('/api/kunde/reservierungen/' + currentAptId + '/aendern?t=' + encodeURIComponent(TOKEN), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ new_date: newDate, new_time: newTime })
                });
                const data = await resp.json();
                if (resp.ok) {
                    showToast('Änderungswunsch gesendet');
                    closeModal('change-modal');
                    loadReservations();
                } else {
                    showToast(data.error || 'Fehler', true);
                }
            } catch(e) {
                showToast('Netzwerkfehler', true);
            }
            this.disabled = false;
            this.textContent = 'Anfrage senden';
        });

        // Close modals on overlay click
        document.querySelectorAll('.modal-overlay').forEach(function(el) {
            el.addEventListener('click', function(e) {
                if (e.target === el) el.classList.remove('active');
            });
        });

        loadReservations();
    </script>
</body>
</html>
"""

PWA_MANIFEST = """{
    "name": "Meine Reservierungen",
    "short_name": "Reservierungen",
    "start_url": "/kunde",
    "display": "standalone",
    "background_color": "#0f172a",
    "theme_color": "#0f172a",
    "icons": []
}"""


@customer_portal.route("/kunde")
def portal():
    """Kunden-Portal Hauptseite."""
    return render_template_string(CUSTOMER_PORTAL_HTML)


@customer_portal.route("/kunde/manifest.json")
def portal_manifest():
    """PWA Manifest."""
    from flask import Response
    return Response(PWA_MANIFEST, mimetype="application/manifest+json")
