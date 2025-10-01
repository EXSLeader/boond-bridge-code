import os
import json
from http import HTTPStatus
import requests
from boondmanager.auth import get_jwt  # builds X-Jwt-Client

# Secrets (from Vercel env)
USER_TOKEN   = os.environ["BOOND_USER_TOKEN"]
CLIENT_TOKEN = os.environ["BOOND_CLIENT_TOKEN"]
CLIENT_KEY   = os.environ["BOOND_CLIENT_KEY"]
GATEKEEPER   = os.environ["GATEKEEPER_TOKEN"]

# API base comes from env so we never hardcode tenant
BOOND_BASE_URL = os.environ.get("BOOND_BASE_URL", "").rstrip("/")
if not BOOND_BASE_URL:
    raise RuntimeError("Missing BOOND_BASE_URL (e.g. https://ui.boondmanager.com/api/v2)")

# Candidate endpoints/params we will try in order (relative to BOOND_BASE_URL)
CANDIDATES = [
    ("/projects", None),
    ("/projects", {"status": "active"}),
    ("/projects", {"isActive": "true"}),
    ("/projects/search", None),
    ("/missions", None),
    ("/missions", {"isActive": "true"}),
    ("/missions", {"status": "active"}),
    ("/projectneeds", None),
    ("/opportunities", None),
]

def fetch_missions(debug=False):
    """Try multiple endpoints against BOOND_BASE_URL; return first 200 OK JSON. If debug, include attempts."""
    jwt = get_jwt(USER_TOKEN, CLIENT_TOKEN, CLIENT_KEY)
    headers = {"X-Jwt-Client": jwt, "Content-Type": "application/json"}
    attempts = []

    for path, params in CANDIDATES:
        url = f"{BOOND_BASE_URL}{path}"
        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            attempts.append({
                "url": url + (f"?{requests.compat.urlencode(params)}" if params else ""),
                "status": r.status_code,
                "ok": r.ok,
                "len": len(r.text or "")
            })
            if r.status_code == 200:
                try:
                    data = r.json()
                except Exception:
                    continue
                return data if not debug else {"data": data, "attempts": attempts}
        except Exception as e:
            attempts.append({"url": url, "error": str(e)})

    return {"error": "No endpoint matched"} if not debug else {"error": "No endpoint matched", "attempts": attempts}

def app(environ, start_response):
    """Vercel WSGI entrypoint."""
    from werkzeug.wrappers import Request, Response
    req = Request(environ)

    if req.path.endswith("/api/open_missions"):
        token = req.args.get("token", "")
        if token != GATEKEEPER:
            resp = Response("Unauthorized", HTTPStatus.UNAUTHORIZED, {"Content-Type": "text/plain"})
        else:
            debug = req.args.get("debug") == "1"
            payload = fetch_missions(debug=debug)
            resp = Response(json.dumps(payload), 200, {"Content-Type": "application/json"})
    else:
        resp = Response("Not found", 404, {"Content-Type": "text/plain"})

    return resp(environ, start_response)