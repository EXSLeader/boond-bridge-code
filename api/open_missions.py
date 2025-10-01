# api/open_missions.py
import os, json
from http import HTTPStatus
import requests
from werkzeug.wrappers import Request, Response

# ---- Secrets / Config (from Vercel env) ----
USER_TOKEN    = os.environ["BOOND_USER_TOKEN"]
CLIENT_TOKEN  = os.environ["BOOND_CLIENT_TOKEN"]
CLIENT_KEY    = os.environ["BOOND_CLIENT_KEY"]
GATEKEEPER    = os.environ["GATEKEEPER_TOKEN"]
BASE_URL      = os.environ.get("BOOND_BASE_URL", "https://ui.boondmanager.com/api").rstrip("/")

def _get_jwt():
    """
    Your tenant already accepts X-Jwt-Client* headers (we saw 200s).
    We reuse the same header form. If Boond later requires a signed token,
    this function can be swapped for a real signer.
    """
    return f"{USER_TOKEN}:{CLIENT_TOKEN}:{CLIENT_KEY}"

def _headers():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Front-Boondmanager": "ember",
        "X-Jwt-Client-Boondmanager": _get_jwt()
    }

# ---------- Flatteners ----------
def _index_included(included):
    by_type = {}
    for inc in included or []:
        by_type.setdefault(inc.get("type"), {})[inc.get("id")] = inc
    return by_type

def _get_attr(obj, path, default=None):
    cur = obj
    for key in path:
        if not isinstance(cur, dict): return default
        cur = cur.get(key)
        if cur is None: return default
    return cur

def _flatten_opportunities(opps_json):
    """
    Normalize Boond 'opportunities' into a compact, match-ready list.
    We try to extract: id, title, company name, optional start/end/status.
    """
    data = opps_json.get("data", [])
    included = opps_json.get("included", [])
    by_type = _index_included(included)

    out = []
    for opp in data:
        attrs = opp.get("attributes", {}) or {}
        rels  = opp.get("relationships", {}) or {}

        # Company via relationships or included
        comp_rel = _get_attr(rels, ["company", "data"])
        company_name = None
        if comp_rel:
            comp_obj = by_type.get("company", {}).get(comp_rel.get("id"))
            if comp_obj:
                company_name = _get_attr(comp_obj, ["attributes", "name"])

        out.append({
            "opportunity_id": opp.get("id"),
            "title": attrs.get("title"),
            "company": company_name,
            "start": attrs.get("startDate") or attrs.get("beginDate") or attrs.get("start_date"),
            "end": attrs.get("endDate") or attrs.get("dueDate") or attrs.get("end_date"),
            "status": attrs.get("status") or attrs.get("state"),
            "updated": attrs.get("updateDate") or attrs.get("updated_at"),
        })
    return out

# ---------- Fetchers ----------
def fetch_opportunities():
    url = f"{BASE_URL}/opportunities"
    r = requests.get(url, headers=_headers(), timeout=30)
    if r.status_code == 200:
        return {"opportunities": _flatten_opportunities(r.json())}
    return {"error": f"Boond returned {r.status_code}", "body": r.text[:500]}

# ---------- Vercel Entrypoint ----------
def app(environ, start_response):
    req = Request(environ)
    if req.path.endswith("/api/open_missions"):
        token = req.args.get("token", "")
        if token != GATEKEEPER:
            resp = Response("Unauthorized", HTTPStatus.UNAUTHORIZED, {"Content-Type": "text/plain"})
        else:
            debug = req.args.get("debug") == "1"
            if debug:
                probe = requests.get(f"{BASE_URL}/opportunities", headers=_headers(), timeout=30)
                payload = {
                    "attempt": {"url": f"{BASE_URL}/opportunities", "status": probe.status_code},
                    "preview": (_flatten_opportunities(probe.json())[:5] if probe.ok else None)
                }
            else:
                payload = fetch_opportunities()
            resp = Response(json.dumps(payload), 200, {"Content-Type": "application/json"})
    else:
        resp = Response("Not found", 404, {"Content-Type": "text/plain"})
    return resp(environ, start_response)