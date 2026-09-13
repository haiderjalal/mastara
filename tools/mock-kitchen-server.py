"""A stand-in for whatever system finally receives the orders.

It serves the menu AND the orders API from one origin, so the whole loop runs
with a single command and no CORS to think about:

    python tools/mock-kitchen-server.py       # http://localhost:8799/

    config.js →  orderEndpoint.url : "/orders"
                 kitchenFeedUrl    : "/orders"

    POST  /orders       accepts one order payload, appends it to orders.json
    GET   /orders       every order, newest first (what kitchen.html polls)
    PATCH /orders/<id>  {"status": "preparing"} updates one order
    anything else       served as a static file from the project folder

It is a demo tool, not production: no auth, no database, CORS wide open.
Whoever builds the real endpoint only has to match these three routes — or
change CONFIG.orderEndpoint to match theirs.
"""
import json, os, re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = 8799
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
STORE = os.path.join(HERE, "orders.json")


def load():
    try:
        with open(STORE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save(orders):
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def _send(self, code, body=None):
        # 204 must carry no body at all — a browser preflight hangs if it does.
        payload = b"" if code == 204 else json.dumps(body if body is not None else {"ok": True}).encode()
        self.send_response(code)
        if payload:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self._send(204)

    def do_GET(self):
        if self.path.split("?")[0].rstrip("/") == "/orders":
            self._send(200, sorted(load(), key=lambda o: o.get("placedAt", ""), reverse=True))
        else:
            super().do_GET()          # serve the menu itself

    def do_POST(self):
        if not self.path.startswith("/orders"):
            return self._send(404, {"error": "not found"})
        try:
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            order = json.loads(raw)
        except ValueError:
            return self._send(400, {"error": "invalid JSON"})

        if not order.get("orderId") or not order.get("items"):
            return self._send(422, {"error": "orderId and items are required"})

        orders = [o for o in load() if o.get("orderId") != order["orderId"]]  # idempotent
        order["status"] = "new"
        orders.append(order)
        save(orders)

        # ASCII only: a Windows console is cp1252 and a stray tick mark kills the server.
        print(f"  [order] table {order.get('table', '?'):>3}  {order['orderId']}  "
              f"{len(order['items'])} lines  {order.get('totals', {}).get('total', 0)}")
        self._send(201, {"ok": True, "orderId": order["orderId"]})

    def do_PATCH(self):
        m = re.match(r"^/orders/([A-Za-z0-9-]+)$", self.path)
        if not m:
            return self._send(404, {"error": "not found"})
        try:
            patch = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except ValueError:
            return self._send(400, {"error": "invalid JSON"})

        orders = load()
        for o in orders:
            if o.get("orderId") == m.group(1):
                o.update({k: patch[k] for k in ("status",) if k in patch})
                save(orders)
                return self._send(200, o)
        self._send(404, {"error": "unknown order"})

    def log_message(self, *args):
        pass          # the POST handler prints something more useful


if __name__ == "__main__":
    print(f"Menu      http://localhost:{PORT}/")
    print(f"Kitchen   http://localhost:{PORT}/kitchen.html")
    print(f"Orders    http://localhost:{PORT}/orders   (stored in {STORE})")
    print('Set orderEndpoint.url and kitchenFeedUrl to "/orders" in config.js.')

    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
