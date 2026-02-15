"""
Login/Logout + Session-Management fuer das universelle Dashboard.
Unterstuetzt Session-Auth (Login) und Token-Auth (Legacy).
"""

import logging
from functools import wraps
from datetime import timedelta

from flask import (
    Blueprint, request, session, redirect, url_for,
    render_template_string, jsonify,
)

from src.booking_database import (
    verify_user_password, update_last_login,
    get_business_by_token, get_business_by_id,
)

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


# ============================================================
# require_auth Decorator
# ============================================================

def require_auth(f):
    """
    Prueft Authentifizierung in dieser Reihenfolge:
    1. Flask-Session (session["business_id"])
    2. Token (X-Access-Token Header oder ?token= Param)
    3. Redirect zu /login (Webseiten) oder 401 (API)
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        business = None

        # 1. Session-Auth
        if session.get("business_id"):
            business = get_business_by_id(session["business_id"])
            if business and not business.get("is_active"):
                business = None
                session.clear()

        # 2. Token-Auth (Legacy)
        if not business:
            token = request.headers.get("X-Access-Token") or request.args.get("token")
            if token:
                business = get_business_by_token(token)

        # 3. Nicht authentifiziert
        if not business:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Nicht authentifiziert"}), 401
            return redirect(url_for("auth.login_page"))

        kwargs["business"] = business
        return f(*args, **kwargs)
    return decorated


# ============================================================
# Login-Seite
# ============================================================

@auth_bp.route("/login", methods=["GET"])
def login_page():
    """Login-Seite anzeigen."""
    if session.get("business_id"):
        return redirect("/dashboard")
    error = request.args.get("error", "")
    return render_template_string(LOGIN_HTML, error=error)


@auth_bp.route("/login", methods=["POST"])
def login_submit():
    """Credentials pruefen, Session setzen."""
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username or not password:
        return redirect("/login?error=Bitte+Benutzername+und+Passwort+eingeben")

    user = verify_user_password(username, password)
    if not user:
        logger.warning(f"Fehlgeschlagener Login-Versuch: {username}")
        return redirect("/login?error=Benutzername+oder+Passwort+falsch")

    # Session setzen
    session.permanent = True
    session["user_id"] = user["id"]
    session["business_id"] = user["business_id"]
    session["username"] = user["username"]

    update_last_login(user["id"])
    logger.info(f"Login erfolgreich: {username} (Business: {user['business_id']})")

    return redirect("/dashboard")


@auth_bp.route("/logout")
def logout():
    """Session loeschen, Redirect zu /login."""
    username = session.get("username", "?")
    session.clear()
    logger.info(f"Logout: {username}")
    return redirect("/login")


# ============================================================
# Login-Page HTML (Glassmorphism Dark Theme)
# ============================================================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="#0a0e1a">
    <title>Login - AssistentPro</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0e1a;
            color: #e2e8f0;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        /* Animated background gradient */
        body::before {
            content: '';
            position: fixed;
            inset: 0;
            background:
                radial-gradient(circle at 20% 50%, rgba(99,102,241,0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(139,92,246,0.06) 0%, transparent 50%),
                radial-gradient(circle at 50% 80%, rgba(99,102,241,0.04) 0%, transparent 50%);
            z-index: 0;
        }
        .login-card {
            position: relative;
            z-index: 1;
            width: 100%;
            max-width: 400px;
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 24px;
            padding: 40px 30px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }
        .logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .logo svg {
            width: 56px;
            height: 56px;
            margin-bottom: 12px;
        }
        .logo h1 {
            font-size: 1.4rem;
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .logo p {
            font-size: 0.82rem;
            color: #64748b;
            margin-top: 4px;
        }
        .form-group {
            margin-bottom: 18px;
        }
        .form-group label {
            display: block;
            font-size: 0.75rem;
            color: #94a3b8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 6px;
            font-weight: 500;
        }
        .form-group input {
            width: 100%;
            padding: 12px 16px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            color: #e2e8f0;
            font-size: 0.95rem;
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
        }
        .form-group input:focus {
            outline: none;
            border-color: #6366f1;
            box-shadow: 0 0 0 3px rgba(99,102,241,0.15);
        }
        .form-group input::placeholder { color: #475569; }
        .btn-login {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            border: none;
            border-radius: 12px;
            color: white;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(99,102,241,0.3);
            margin-top: 6px;
        }
        .btn-login:hover {
            box-shadow: 0 6px 20px rgba(99,102,241,0.5);
            transform: translateY(-1px);
        }
        .btn-login:active {
            transform: translateY(0);
        }
        .error-msg {
            background: rgba(239,68,68,0.12);
            border: 1px solid rgba(239,68,68,0.25);
            border-radius: 10px;
            padding: 10px 14px;
            margin-bottom: 18px;
            font-size: 0.82rem;
            color: #fca5a5;
            text-align: center;
        }
        @media (max-width: 440px) {
            .login-card { padding: 30px 22px; }
        }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="logo">
            <svg viewBox="0 0 56 56" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:#6366f1"/>
                        <stop offset="100%" style="stop-color:#8b5cf6"/>
                    </linearGradient>
                </defs>
                <rect width="56" height="56" rx="14" fill="url(#g)"/>
                <text x="50%" y="38%" font-family="Arial" font-size="18" font-weight="bold"
                      fill="white" text-anchor="middle" dominant-baseline="middle">AP</text>
                <text x="50%" y="66%" font-family="Arial" font-size="9"
                      fill="rgba(255,255,255,0.7)" text-anchor="middle" dominant-baseline="middle">PRO</text>
            </svg>
            <h1>AssistentPro</h1>
            <p>Melden Sie sich an</p>
        </div>

        {% if error %}
        <div class="error-msg">{{ error }}</div>
        {% endif %}

        <form method="POST" action="/login">
            <div class="form-group">
                <label for="username">Benutzername</label>
                <input type="text" id="username" name="username" placeholder="Benutzername eingeben" autocomplete="username" autofocus required>
            </div>
            <div class="form-group">
                <label for="password">Passwort</label>
                <input type="password" id="password" name="password" placeholder="Passwort eingeben" autocomplete="current-password" required>
            </div>
            <button type="submit" class="btn-login">Anmelden</button>
        </form>
    </div>
</body>
</html>
"""
