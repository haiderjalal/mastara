# Order payload

This is the contract between the menu and whatever system ends up receiving orders —
a POS, a KDS, an internal API, a Zapier/Make webhook, an n8n flow, a Google Sheet.
Nothing in the menu needs changing when that system is chosen; set
`CONFIG.orderEndpoint.url` in [`config.js`](../config.js) and orders start arriving.

## Request

```
POST <CONFIG.orderEndpoint.url>
Content-Type: application/json
<plus any headers you put in CONFIG.orderEndpoint.headers, e.g. Authorization>
```

```json
{
  "orderId": "MST-12-140034-R3X",
  "placedAt": "2026-09-14T07:34:21.905Z",
  "venue": "Mastara",
  "source": "qr-3d-menu",
  "table": "12",
  "guest": { "name": "Haider", "phone": "" },
  "note": "Table by the railing, less spicy",
  "currency": "PKR",
  "items": [
    { "slug": "beef-nihari",  "name": "Beef Nihari",  "category": "desi", "unitPrice": 1150, "qty": 1, "lineTotal": 1150 },
    { "slug": "haleem",       "name": "Haleem",       "category": "desi", "unitPrice": 900,  "qty": 1, "lineTotal": 900 },
    { "slug": "chicken-tikka","name": "Chicken Tikka","category": "desi", "unitPrice": 700,  "qty": 1, "lineTotal": 700 }
  ],
  "totals": {
    "subtotal": 2750,
    "taxPercent": 0, "tax": 0,
    "servicePercent": 0, "service": 0,
    "total": 2750
  }
}
```

| Field | Notes |
|---|---|
| `orderId` | `MST-<table>-<DDHHMM>-<random>`. Unique per order; **treat a repeat as the same order** — the menu resends queued orders after a network failure. |
| `placedAt` | UTC, ISO 8601. Guest device clock — don't bill off it. |
| `table` | What the guest scanned (`?t=12`) or typed. Up to 6 characters, `A–Z 0–9 -`. Empty only if `CONFIG.requireTable` is turned off. |
| `guest` | Both fields optional and often blank. |
| `note` | Free text from the guest, max 400 chars. Show it to the kitchen. |
| `items[].slug` | Stable id — match on this, not on `name`. |
| `items[].unitPrice` | Whole rupees at the moment of ordering. |
| `totals` | Computed client-side. **Re-compute server-side before billing** — the client is not a source of truth. |

## Response

Any `2xx` means accepted; the guest sees "Order sent". Anything else (or a timeout,
default 8 s) means the order is queued on the guest's device, the guest is offered the
WhatsApp fallback, and the menu retries the POST on their next page load.

Return whatever body you like — it is not parsed.

## Kitchen feed (optional)

[`kitchen.html`](../kitchen.html) is a counter/kitchen display. Point
`CONFIG.kitchenFeedUrl` at an endpoint that returns the orders as JSON — either a bare
array or `{ "orders": [...] }` — each entry being an order payload plus a `status` of
`new` | `preparing` | `served`. It polls every `CONFIG.kitchenPollMs`.

With no feed URL it shows the orders placed on that same device, which is enough to
demo the flow but is not a real kitchen screen.

## Try it end to end

[`tools/mock-kitchen-server.py`](../tools/mock-kitchen-server.py) is a ~90-line stand-in
for the real system. It serves the menu *and* the orders API on one origin:

```bash
python tools/mock-kitchen-server.py
```

- menu → http://localhost:8799/
- kitchen display → http://localhost:8799/kitchen.html
- raw orders → http://localhost:8799/orders (also written to `tools/orders.json`)

`config.js` ships pointing at `/orders`, so this works with no edits. Scan or open
`?t=12`, add dishes, send — the ticket appears on the kitchen screen within seconds.

## Notes for whoever builds the real endpoint

- **Be idempotent on `orderId`.** Retries are by design.
- **Re-price server-side.** `unitPrice` and `totals` arrive from a phone.
- **Rate-limit and size-cap.** The endpoint is public; anyone who can read a QR code can POST.
- **CORS**: if the API lives on a different domain from the menu, it must allow the
  menu's origin and answer the `OPTIONS` preflight. Same-origin (`/orders`) avoids this entirely.
- The menu never retries a `4xx` in a loop — a rejected order stays queued until the
  guest reloads, and they always have the WhatsApp fallback.
