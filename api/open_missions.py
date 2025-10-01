# api/open_missions.py
import os
import time
import json
import jwt
import requests
from http import HTTPStatus

# --- Env (set in Vercel > Project > Settings > Environment Variables) ---
USER_TOKEN   = os.environ["BOOND_USER_TOKEN"]
CLIENT_TOKEN = os.environ["BOOND_CLIENT_TOKEN"]
CLIENT_KEY   = os.environ["BOOND_CLIENT_KEY"]
GATEKEEPER   = os.environ["GATEKEEPER_TOKEN"]     # your shared secret

# --- Auth helper (X-Jwt-Client-Boondmanager) ---
def generate_jwt(user_token: str, client_token: str, client_key: str) -> str:
    now = int(time.time())
    payload = {
        "iat": now,
        "exp": now + 60,           # short lived, like the app does
        "user_token": user_token,
        "client_token": client_token,
    }
    return jwt.encode(payload, client_key, algorithm="HS256")

# --- Call Boond: opportunities (kanban “open”) ---
def fetch_opportunities():
    """
    Mirrors the request you saw in Chrome DevTools:
    GET /api/opportunities?...&opportunityStates=6&viewMode=kanban
    """
    token = generate_jwt(USER_TOKEN, CLIENT_TOKEN, CLIENT_KEY)

    headers = {
        "X-Jwt-Client-Boondmanager": token,
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/json",
    }

    url = "https://ui.boondmanager.com/api/opportunities"
    params = {
        "activityAreas": "",
        "expertiseAreas": "",
        "maxResults": "30",
        "opportunityStates": "6",   # 6 = “open” in kanban
        "opportunityTypes": "",
        "order": "desc",
        "page": "1",
        "positioningStates": "",
        "returnMoreData": "previousAction,nextAction",
        "saveSearch": "true",
        "sort": "updateDate",
        "tools": "",
        "viewMode": "kanban",
    }

    r = requests.get(url, headers=headers, params=params, timeout=30)

    if r.status_code != 200:
        return {
            "error": "fetch_opportunities_failed",
            "status": r.status_code,
            "preview": r.text[:800],
        }

    return r.json()

# --- Vercel entrypoint (WSGI) with gatekeeper ---
def app(environ, start_response):
    from urllib.parse import parse_qs
    path = environ.get("PATH_INFO", "")
    qs = parse_qs(environ.get("QUERY_STRING", ""))

    def respond(status: int, body: dict, ctype="application/json"):
        payload = json.dumps(body).encode("utf-8")
        start_response(
            f"{status} {HTTPStatus(status).phrase}",
            [("Content-Type", ctype), ("Content-Length", str(len(payload)))],
        )
        return [payload]

    if path.rstrip("/") != "/api/open_missions":
        return respond(404, {"error": "not_found"})

    # simple shared-secret to avoid random hits
    token = (qs.get("token", [""])[0]).strip()
    if token != GATEKEEPER:
        return respond(401, {"error": "unauthorized"})

    try:
        data = fetch_opportunities()
        return respond(200, data)
    except Exception as e:
        return respond(500, {"error": "server_error", "detail": str(e)})