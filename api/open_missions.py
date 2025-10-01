# api/open_missions.py
import os, json, time
from http import HTTPStatus
import requests
import jwt  # PyJWT
from werkzeug.wrappers import Request, Response

# ---- Environment (all must be set in Vercel)
# Example BASE_URL: https://ui.boondmanager.com/api
BASE_URL     = os.environ["BOOND_BASE_URL"].rstrip("/")
USER_TOKEN   = os.environ["BOOND_USER_TOKEN"]
CLIENT_TOKEN = os.environ["BOOND_CLIENT_TOKEN"]
CLIENT_KEY   = os.environ["BOOND_CLIENT_KEY"]
GATEKEEPER   = os.environ["GATEKEEPER_TOKEN"]

def build_xjwt(user_token: str, client_token: str, client_key: str) -> str:
    """Build the X-Jwt-Client token required by Boond."""
    now = int(time.time())
    payload = {
        "userToken": user_token,
        "clientToken": client_token,
        "iat": now,
        "exp": now + 300,  # valid 5 minutes
    }
    return jwt.encode(payload, client_key, algorithm="HS256")

def fetch_opportunities(query_params: dict):
    """
    Call Boond /api/opportunities with X-Jwt-Client.
    Default safe params are applied; any query params from the incoming request override them.
    """
    token = build_xjwt(USER_TOKEN, CLIENT_TOKEN, CLIENT_KEY)
    headers = {
        "X-Jwt-Client-Boondmanager": token,
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/json",
        # Optional UI-like headers (harmless, can help match UI behaviour)
        "X-Front-Boondmanager": "ember",
        "X-Front-Version": "9.0.4.0",
    }

    # Minimal defaults — do NOT hardcode a state; let caller supply it
    params = {
        "maxResults": "30",
        "order": "desc",
        "page": "1",
        "saveSearch": "true",
        "sort": "updateDate",
        # You can pass things like:
        # opportunityStates=6
        # viewMode=kanban
        # returnMoreData=previousAction,nextAction
    }

    # Merge caller params over defaults
    for k, v in (query_params or {}).items():
        if k.lower() != "token":  # never forward our gatekeeper token
            params[k] = v

    attempts = []
    url = f"{BASE_URL}/opportunities"
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        attempts.append({"url": r.url, "status": r.status_code, "ok": r.ok})
        if r.ok:
            return r.json()
    except Exception as e:
        attempts.append({"url": url, "error": str(e)})

    return {"error": "No endpoint matched", "attempts": attempts}

def app(environ, start_response):
    """WSGI entrypoint for Vercel Python functions."""
    req = Request(environ)

    if req.path.endswith("/api/open_missions"):
        # Simple gatekeeper to avoid exposing your connector publicly
        token = req.args.get("token", "")
        if token != GATEKEEPER:
            resp = Response("Unauthorized", HTTPStatus.UNAUTHORIZED, {"Content-Type": "text/plain"})
        else:
            # Forward all filters/query params to Boond (except the gatekeeper token)
            qp = {k: v for k, v in req.args.items() if k.lower() != "token"}
            data = fetch_opportunities(qp)
            resp = Response(json.dumps(data), 200, {"Content-Type": "application/json"})
    else:
        resp = Response("Not found", 404, {"Content-Type": "text/plain"})

    return resp(environ, start_response)