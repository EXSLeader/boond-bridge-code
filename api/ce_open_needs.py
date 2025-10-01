# api/ce_open_needs.py
cat > api/ce_open_needs.py <<'PY'
# api/ce_open_needs.py
import os, json
from http import HTTPStatus
from werkzeug.wrappers import Request, Response

# Auth: reuse the same secret already configured for Boond
# (environment variable is managed in Vercel; nothing to reveal here)
GATEKEEPER = os.environ["GATEKEEPER_TOKEN"]

def _unauthorized():
    return Response("Unauthorized", HTTPStatus.UNAUTHORIZED, {"Content-Type": "text/plain"})

def app(environ, start_response):
    req = Request(environ)

    # Accept either X-Api-Key header or ?token=
    provided = req.headers.get("X-Api-Key") or req.args.get("token")
    if not provided or provided != GATEKEEPER:
        resp = _unauthorized()
        return resp(environ, start_response)

    if not req.path.endswith("/api/ce_open_needs"):
        resp = Response("Not found", 404, {"Content-Type": "text/plain"})
        return resp(environ, start_response)

    # Minimal normalized payload (stub for now) — replace later with live Connecting-Expertise fetch
    payload = {
        "meta": {
            "source": "CONNECTING-EXPERTISE-STUB",
            "note": "Replace with live CE fetch later"
        },
        "data": [],        # list of needs/opportunities (same idea as Boond)
        "included": []     # companies/contacts if you add them later
    }

    resp = Response(json.dumps(payload), 200, {"Content-Type": "application/json"})
    return resp(environ, start_response)
