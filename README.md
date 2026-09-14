# Mastara — QR → 3D / AR menu → order to the kitchen

A guest scans the QR code on their table. The menu opens with the table number already
known. Any dish spins in 3D and can be placed life-size on the table in AR. They add
what they want, send the order, and it arrives at the kitchen tagged **Table 12**.

Static site, no build step, no framework.

```
index.html    menu, 3D/AR dish view, cart, order form, confirmation  (CSS + app JS inlined)
menu.js       41 dishes across 5 cuisines, prices, venue details
config.js     everything you change: prices behaviour, tax, tables, where orders go
order.js      cart, order payload, delivery + offline retry queue
kitchen.html  counter / kitchen display — live tickets, start-cooking, mark-served
qr.html       prints QR cards: one per table, or one per dish
img/          WebP photos (560 / 1200 wide) + hero + logo
models/       one .glb per dish photo
fonts/        Oswald + Raleway, self-hosted latin subsets
assets/       source material: original photos, logo, brand guideline PDF
tools/build.py              rebuilds img/ and models/ from assets/
tools/mock-kitchen-server.py  stand-in for the real order system, for demos
docs/order-payload.md       the JSON contract for whoever receives the orders
```

Rebuilding this for a different restaurant? [`BLUEPRINT.md`](BLUEPRINT.md) is the
portable spec — hand that one file to a new project and it has everything: what to ask
the client, the scraping recipe, the 3D numbers, the order contract, and the gotchas.

## Run it

```bash
python tools/mock-kitchen-server.py
```

One command serves everything on http://localhost:8799 —

| | |
|---|---|
| http://localhost:8799/?t=12 | the menu, as a guest at table 12 sees it |
| http://localhost:8799/kitchen.html | the kitchen / counter display |
| http://localhost:8799/qr.html | print the table QR cards |

Add dishes, send the order, and watch the ticket land on the kitchen screen. Orders are
written to `tools/orders.json`.

(`python -m http.server` also serves the site — you just get the WhatsApp fallback
instead of a kitchen screen, because there is no orders API behind it.)

Only `index.html`, `menu.js`, `qr.html`, `img/`, `models/` and `fonts/` need to be deployed;
`assets/` and `tools/` are source material (the brand PDF alone is 41 MB).

## Ordering, and where the orders go

Everything about ordering is in [`config.js`](config.js). The important line:

```js
orderEndpoint: { url: "/orders", ... }   // ← point this at the real system
```

- **Set a URL** and every order is `POST`ed there as JSON. The exact shape is in
  [`docs/order-payload.md`](docs/order-payload.md) — that file is what you hand to
  whoever builds the receiving end (POS, KDS, internal API, Zapier/n8n webhook, a sheet).
- **No URL, or the endpoint is down**: the order is saved on the guest's phone, the guest
  is offered a WhatsApp button with the ticket already written out to Mastara's number,
  and the menu retries the POST by itself on their next page load. An order is never lost
  and never silently dropped.
- `taxPercent` / `servicePercent` default to **0** — set them only to what Mastara
  actually charges, they print on the guest's ticket.
- `tableCount` controls how many table QR cards `qr.html` prints.
- `orderingEnabled: false` turns the whole thing back into a browse-only 3D menu.

⚠️ **Prices in `menu.js` are placeholders.** The public menu lists none, so plausible
figures are in there to make the flow work. Replace every one before this goes on a table.

## Deploy

Any static host (Vercel, Netlify, Cloudflare Pages). **AR requires HTTPS**, which all of
them provide; `localhost` also works for testing. Then open `qr.html`, paste the live URL,
and print. Nothing else to configure — no server, no database.

## Where the content came from

Everything is pulled from Mastara's own material, captured Sep 2026:

- **Menu** — all 41 dishes, descriptions and badges from `mastararestaurants.com/menu`
  (Desi, Thai, Chinese, Fast Food, Continental).
- **Brand** — colours `#d32f23` / `#000` / `#fff`, Oswald + Raleway, and the logo, taken
  from the live site. The official brand guideline PDF is saved in `assets/brand/`.
- **Photography** — the nine Desi dishes use Mastara's own photos. The other four
  cuisines had no per-dish photography on the site, so each of those dishes shares its
  category image. Drop real photos in `assets/dishes/<slug>.jpg` and rerun the build.
- **Venue** — address, hours, phone and WhatsApp number from the contact page; the
  "Bite & Bubbles" line comes from the logo lockup.

Prices are blank because the public menu doesn't list any. Fill `price` in `menu.js`
and it appears on both the card and the dish page.

## The 3D models

`tools/build.py` generates a GLB per dish: a 27 cm plate — a shallow dish with a food
dome — with the dish photograph mapped onto it. Sized in real-world metres, so AR places
it at true size on the table. ~190 KB each, and only the one dish being viewed is ever
downloaded.

```bash
python tools/build.py     # needs Pillow:  pip install pillow
```

This is a convincing stand-in, not a scan. For photoreal dishes, scan the plated food with
Polycam or Luma AI (~5 min per dish), export `.glb` at real-world scale, drop it in
`models/<slug>.glb`, and the site picks it up — no code change.

## AR support

Handled by `<model-viewer>`: Scene Viewer on Android, Quick Look on iOS (the USDZ is
generated on the fly from the GLB), WebXR where available. Desktop browsers show 3D only
and the AR button says so.

## Performance

First load of the menu is ~290 KB on a phone (6.6 KB HTML gzipped, 68 KB fonts, 115 KB
hero, lazy cards) with no framework and no render-blocking requests. The model-viewer
library (~150 KB gzipped) and the GLB are fetched *only* when a dish page opens, behind an
instant poster image. Images are WebP with `srcset`, explicit dimensions, and lazy loading
below the fold.
