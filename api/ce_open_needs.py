# api/ce_open_needs.py
import os, json
from http import HTTPStatus
from werkzeug.wrappers import Request, Response

GATEKEEPER = os.environ["GATEKEEPER_TOKEN"]

def _unauthorized():
    return Response("Unauthorized", HTTPStatus.UNAUTHORIZED, {"Content-Type": "text/plain"})

def app(environ, start_response):
    req = Request(environ)

    # Auth via header or query param
    provided = req.headers.get("X-Api-Key") or req.args.get("token")
    if not provided or provided != GATEKEEPER:
        resp = _unauthorized()
        return resp(environ, start_response)

    if not req.path.endswith("/api/ce_open_needs"):
        resp = Response("Not found", 404, {"Content-Type": "text/plain"})
        return resp(environ, start_response)

    # Stub payload: same overall shape as Boond for easy reuse by the GPT
    payload = {
        "meta": {
            "source": "CONNECTING-EXPERTISE-STUB",
            "note": "Replace with live CE fetch later"
        },
        "data": [],
        "included": []
    }
    resp = Response(json.dumps(payload), 200, {"Content-Type": "application/json"})
    return resp(environ, start_response)