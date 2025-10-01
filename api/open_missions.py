import os
import json
import base64
from http import HTTPStatus
import requests

# === Secrets depuis Vercel ===
USER_TOKEN    = os.environ["BOOND_USER_TOKEN"]        # ex: 322e6578736f6c766165
CLIENT_TOKEN  = os.environ.get("BOOND_CLIENT_TOKEN")  # ex: 6578736f6c766165
CLIENT_KEY    = os.environ.get("BOOND_CLIENT_KEY")    # ex: 625af3a0380677306086
GATEKEEPER    = os.environ["GATEKEEPER_TOKEN"]

# Base API: on utilise l'UI proxy (confirmé) + externe v2
BASES = []
env_base = os.environ.get("BOOND_BASE_URL", "").rstrip("/")
if env_base:
    BASES.append(env_base)
# On s'assure d'avoir les 2 variantes courantes
for b in ("https://ui.boondmanager.com/api/v2",
          "https://ui.boondmanager.com/api/externe/v2"):
    if b not in BASES:
        BASES.append(b)

# Endpoints candidats (relatifs au "base")
CANDIDATES = [
    ("/projects", None),
    ("/missions", None),
    ("/projectneeds", None),
    ("/opportunities", None),
    ("/projects/search", None),
]

def _basic_header(user: str, pwd: str) -> dict:
    token = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}

def make_headers_variants():
    """
    On teste plusieurs variantes BasicAuth, car selon la conf Boond :
    - user = USER_TOKEN, password = CLIENT_KEY
    - user = USER_TOKEN, password = CLIENT_TOKEN
    - user = USER_TOKEN, password = "" (vide)
    On garde aussi une variante 'X-Jwt-Client' au cas où.
    """
    variants = []

    # Accept/Content par défaut
    common = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Front-Boondmanager": "ember",
    }

    # BasicAuth variantes
    if CLIENT_KEY:
        h1 = common.copy()
        h1.update(_basic_header(USER_TOKEN, CLIENT_KEY))
        variants.append(h1)

    if CLIENT_TOKEN:
        h2 = common.copy()
        h2.update(_basic_header(USER_TOKEN, CLIENT_TOKEN))
        variants.append(h2)

    # mot de passe vide
    h3 = common.copy()
    h3.update(_basic_header(USER_TOKEN, ""))
    variants.append(h3)

    # Variante JWT en secours si jamais BasicAuth n'est pas pris en compte
    try:
        from boondmanager.auth import get_jwt
        jwt = get_jwt(USER_TOKEN, CLIENT_TOKEN or "", CLIENT_KEY or "")
        h4 = common.copy()
        h4["X-Jwt-Client-Boondmanager"] = jwt
        variants.append(h4)
        h5 = common.copy()
        h5["X-Jwt-Client"] = jwt
        variants.append(h5)
    except Exception:
        pass

    return variants

def try_get(url, headers_list, params=None):
    attempts = []
    for headers in headers_list:
        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            attempts.append({
                "url": url + (f"?{requests.compat.urlencode(params)}" if params else ""),
                "status": r.status_code,
                "ok": r.ok,
                "len": len(r.text or ""),
                "auth_hdr": [k for k in headers.keys() if k.lower().startswith("authorization") or k.lower().startswith("x-jwt")]
            })
            if r.status_code == 200:
                # retourne du JSON ?
                try:
                    return r.json(), attempts
                except Exception:
                    continue
        except Exception as e:
            attempts.append({"url": url, "error": str(e)})
    return None, attempts

def fetch_missions(debug=False):
    attempts_all = []

    # 1) Ping de santé pour vérifier le domaine (pas authentifié)
    try:
        u = "https://ui.boondmanager.com/api/application/status"
        r = requests.get(u, timeout=15)
        attempts_all.append({"url": u, "status": r.status_code, "ok": r.ok})
    except Exception as e:
        attempts_all.append({"url": "https://ui.boondmanager.com/api/application/status", "error": str(e)})

    # 2) Essais authentifiés sur chaque base + endpoint
    headers_list = make_headers_variants()
    for base in BASES:
        for path, params in CANDIDATES:
            url = f"{base}{path}"
            data, attempts = try_get(url, headers_list, params=params)
            attempts_all.extend(attempts)
            if data is not None:
                return ({"data": data, "attempts": attempts_all} if debug else data)

    return {"error": "No endpoint matched"} if not debug else {"error": "No endpoint matched", "attempts": attempts_all}

def app(environ, start_response):
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