import os
import json
from http import HTTPStatus
import requests
from pyboondmanager.auth import generate_jwt  # builds X-Jwt-Client

# Secrets (these will come from Vercel Environment Variables, not hardcoded)
USER_TOKEN   = os.environ["BOOND_USER_TOKEN"]
CLIENT_TOKEN = os.environ["BOOND_CLIENT_TOKEN"]
CLIENT_KEY   = os.environ["BOOND_CLIENT_KEY"]
GATEKEEPER   = os.environ["GATEKEEPER_TOKEN"]  # shared secret for GPT Action

API_BASES = [
    "https://api.boondmanager.com/api/v2",
    "https://api.boondmanager.com/api"        # fallback for some tenants
]

def fetch_missions():
    """Fetch active missions/projects from Boond."""
    jwt = generate_jwt(USER_TOKEN, CLIENT_TOKEN, CLIENT_KEY)
    headers = {"X-Jwt-Client": jwt, "Content-Type": "application/json"}

    # Try different endpoints (tenant versions differ)
    candidates = [
        ("/projects", {"status": "active"}),
        ("/missions", {"isActive": "true"}),
        ("/projects/search", None)
    ]

    for base in API_BASES:
        for path, params in candidates:
            try:
                url = f"{base}{path}"
                r = requests.get(url, headers=headers, params=params, timeout=30)
                if r.status_code == 200:
                    return r.json()
            except Exception:
                continue

    return {"error": "No endpoint matched"}

def app(environ, start_response):
    """Vercel entrypoint (WSGI app)."""
    from werkzeug.wrappers import Request, Response
    req = Request(environ)

    if req.path.endswith("/api/open_missions"):
        token = req.args.get("token", "")
        if token != GATEKEEPER:
            resp = Response("Unauthorized", HTTPStatus.UNAUTHORIZED, {"Content-Type": "text/plain"})
        else:
            data = fetch_missions()
            resp = Response(json.dumps(data), 200, {"Content-Type": "application/json"})
    else:
        resp = Response("Not found", 404, {"Content-Type": "text/plain"})

    return resp(environ, start_response)