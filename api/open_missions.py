# api/open_missions.py
import os, json, time
from http import HTTPStatus
import requests
import jwt  # PyJWT
from werkzeug.wrappers import Request, Response

# ---- Environment
BASE_URL     = os.environ["BOOND_BASE_URL"].rstrip("/")   # e.g. https://ui.boondmanager.com/api
USER_TOKEN   = os.environ["BOOND_USER_TOKEN"]
CLIENT_TOKEN = os.environ["BOOND_CLIENT_TOKEN"]
CLIENT_KEY   = os.environ["BOOND_CLIENT_KEY"]
GATEKEEPER   = os.environ["GATEKEEPER_TOKEN"]

def build_xjwt(user_token: str, client_token: str, client_key: str) -> str:
    now = int(time.time())
    payload = {
        "userToken": user_token,
        "clientToken": client_token,
        "iat": now,
        "exp": now + 300,  # valid 5 minutes
    }
    return jwt.encode(payload, client_key, algorithm="HS256")

def fetch_opportunities():
    token = build_xjwt(USER_TOKEN, CLIENT_TOKEN, CLIENT_KEY)
    headers = {
        "X-Jwt-Client-Boondmanager": token,
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/json",
        # helpful UI-like headers (optional)
        "X-Front-Boondmanager": "ember",
        "X-Front-Version": "9.0.4.0",
    }

    # default query (matches your DevTools capture: state=6, sorted by updateDate desc)
    params = {
        "maxResults": "30",
        "order": "desc",
        "page": "1",
        "saveSearch": "true",
        "sort": "updateDate",
        "opportunityStates": "6",  # “À pourvoir” (adjust later if needed)
        "returnMoreData": "previousAction,nextAction",
    }

    attempts = []
    url = f"{BASE_URL}/opportunities"
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        attempts.append({"url": r.url, "status": r.status_code, "ok": r.ok})
        if r.ok:
            return r.json()
    except Exception as e:
        attempts.append({"url": url, "error": str(e)})

    # fallback to projects for debug visibility if opps fail
    try:
        alt = f"{BASE_URL}/projects"
        r2 = requests.get(alt, headers=headers, timeout=30)
        attempts.append({"url": r2.url, "status": r2.status_code, "ok": r2.ok})
        if r2.ok:
            return r2.json()
    except Exception as e:
        attempts.append({"url": f'{BASE_URL}/projects', "error": str(e)})

    return {"error": "No endpoint matched", "attempts": attempts}

def app(environ, start_response):
    req = Request(environ)
    if req.path.endswith("/api/open_missions"):
        token = req.args.get("token", "")
        if token != GATEKEEPER:
            resp = Response("Unauthorized", HTTPStatus.UNAUTHORIZED, {"Content-Type": "text/plain"})
        else:
            data = fetch_opportunities()
            resp = Response(json.dumps(data), 200, {"Content-Type": "application/json"})
    else:
        resp = Response("Not found", 404, {"Content-Type": "text/plain"})
    return resp(environ, start_response)