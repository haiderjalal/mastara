# Blueprint — QR → 3D/AR menu → order to the kitchen

**What this file is.** Everything needed to rebuild this product for a different
restaurant, without the client or the developer explaining it again. Drop it into a new
empty project folder and say:

> Read BLUEPRINT.md and build this for **\<restaurant name\>** — here is their website:
> \<url\>. Reference implementation: `git@github.com:haiderjalal/mastara.git` (branch `dev`).

Rename it to `CLAUDE.md` in the new folder if you want Claude Code to load it automatically.

---

## 1. The product in one paragraph

A guest sits down and scans the QR code on their table. A menu opens on their phone,
already knowing which table they are at. Every dish has a photo, a price, and a **View in
3D** button — tapping it spins the dish in 3D and places it life-size on their actual
table in augmented reality. They add what they want, review the order, and send it. It
appears on a kitchen/counter screen seconds later, tagged with the table number. No app
to install, no waiter needed to take the order, no printed menu to reprint when prices
change.

**Two audiences, two screens:**

| Guest (phone) | Staff (kitchen/counter tablet) |
|---|---|
| Scan → menu → 3D/AR → add → send | Live tickets, table number, items, notes, start-cooking / mark-served |

---

## 2. Non-negotiable constraints

These are what make it work in a real restaurant, on real phones, on Pakistani mobile
data. Do not trade them away:

1. **Static site. No framework, no build step, no server required.** Plain HTML/CSS/JS
   files. It deploys to any static host and survives the client's hosting being changed.
2. **Fast on a phone on 4G.** First load under ~300 KB. No render-blocking requests.
   The 3D library and the model are fetched *only* when a dish page is opened.
3. **AR must be one tap** from the dish, and the dish must be at true physical size.
4. **An order is never lost.** If the kitchen system is down or not built yet, the order
   is saved on the phone, the guest gets a prefilled WhatsApp ticket, and the site retries
   by itself later.
5. **Where orders go is one config line,** never a code change.
6. **Never invent business data.** Prices, tax %, service charge, and table count come
   from the client. If they haven't given them, use obvious placeholders and shout about
   it in the file header, the README, and the handover message.

---

## 3. What to collect from the client first

Ask for these up front. Most can be scraped from their website; the last four cannot.

| Input | Where it usually comes from | Needed for |
|---|---|---|
| Website URL | the client | menu, brand, contact |
| Instagram handle | the client | bio, tagline, cuisines, extra photos |
| Logo (PNG/SVG, transparent) | `/logo/…` on their site | header, QR cards |
| Brand colours | CSS custom properties on their live site | the whole theme |
| Fonts | `getComputedStyle(body).fontFamily` on their site | the whole theme |
| Brand guideline PDF | often linked in the footer | sanity-check colours/usage |
| Dish photos | their menu page (`/menu/`) | cards, posters, 3D models |
| Menu: names, descriptions, categories, badges | their menu page | everything |
| **Prices** | **must be asked for — rarely published** | ordering |
| **Tax % and service charge %** | **must be asked for** | guest ticket |
| **Number of tables** | **must be asked for** | QR cards |
| **WhatsApp number for orders** | contact page, confirm it is monitored | fallback channel |
| **Where orders should go** | may be "decided later" — that is fine | the endpoint plug |

### Scraping recipe (saves an hour)

Use the browser tool on their site, then run this in the page to lift the brand system
in one shot:

```js
// brand tokens, fonts, images, links — all at once
const vars = {};
for (const s of document.styleSheets)
  try { for (const r of s.cssRules)
    if (r.selectorText?.includes(":root"))
      for (const p of r.style) if (p.startsWith("--")) vars[p] = r.style.getPropertyValue(p).trim();
  } catch {}
({ vars,
   fonts: [getComputedStyle(document.body).fontFamily,
           getComputedStyle(document.querySelector("h1") || document.body).fontFamily],
   imgs: [...document.images].map(i => ({ alt: i.alt, src: i.currentSrc })),
   links: [...new Set([...document.querySelectorAll("a")].map(a => a.getAttribute("href")))] })
```

- Menu pages are usually **tabbed** — click each cuisine tab, wait ~2 s, and scrape again.
  One pass only gets the first tab.
- **Instagram will hit a login wall.** Read the profile header before the wall appears
  (bio, phone, address, highlight names) and stop there. Never log in. Paid scrapers may
  be rate-limited — don't block on it, the bio is usually enough.
- Check for **broken images** (`naturalWidth === 0` after load, or a `404`). Two of
  Mastara's category images were dead Unsplash links — worth reporting to the client as a
  finding.
- Self-host the fonts: fetch `https://fonts.googleapis.com/css2?family=…` with a desktop
  UA, take the `@font-face` block whose `unicode-range` contains `U+0000-00FF` (latin),
  download the `.woff2`. Two variable fonts ≈ 70 KB and removes two third-party hops.

---

## 4. File map

Everything reusable is in the reference repo. Copy, then re-skin.

```
index.html    menu + dish 3D/AR view + cart + order form + confirmation
              (all CSS and app JS inlined — one request paints the page)
menu.js       CATEGORIES, BADGES, MENU[], VENUE{}  ← per restaurant
config.js     money, tables, ordering, orderEndpoint, kitchen feed  ← per restaurant
order.js      Cart, Table, Order (payload, send, retry queue), money()
kitchen.html  counter display: live tickets, alert sound, status, print
qr.html       prints QR cards — table cards (?t=N) and dish cards (?d=slug)
img/          <slug>-560.webp, <slug>-1200.webp, hero-900/1600, logo
models/       <slug>.glb — one per dish photo
fonts/        two self-hosted woff2 latin subsets
assets/       SOURCE material: original photos, logo, brand PDF (not deployed)
tools/build.py                 regenerates img/ and models/ from assets/
tools/mock-kitchen-server.py   serves the site + a real orders API, for demos
docs/order-payload.md          JSON contract for whoever receives orders
```

| Copy unchanged | Re-skin | Rewrite per restaurant |
|---|---|---|
| `order.js`, `tools/build.py`, `tools/mock-kitchen-server.py`, `docs/order-payload.md` | `index.html`, `kitchen.html`, `qr.html` (colours, fonts, copy) | `menu.js`, `config.js`, all of `img/` `models/` `fonts/` `assets/` |

Deploy only: `index.html`, `menu.js`, `config.js`, `order.js`, `kitchen.html`, `qr.html`,
`img/`, `models/`, `fonts/`. Keep `assets/` and `tools/` out of the deploy (brand PDFs are
often 40 MB+).

---

## 5. Design system

Take the palette and fonts from the client's live site — do not invent a look. Structure
them as CSS custom properties on `:root` so a re-skin is one block:

```css
:root{
  --red:#d32f23; --red-dark:#b52419; --red-light:#e54a3f;   /* client accent */
  --black:#000; --g1:#0c0c0c; --g2:#1a1a1a; --g3:#2a2a2a;   /* surfaces */
  --white:#fff; --muted:#9a9a9a; --green:#67d38b;           /* text + success */
  --head:Oswald,"Arial Narrow",system-ui,sans-serif;        /* client display face */
  --body:Raleway,system-ui,sans-serif;                      /* client body face */
  --pad:clamp(16px,5vw,32px); --max:1120px;
}
```

**Rules that make it look designed rather than generated:**

- Dark ground. Food photography sings on black and it suits evening dining. A daytime
  café may want the inverse — flip the surface tokens, keep the structure.
- Display face: uppercase, letter-spacing `.04em`–`.34em`, weights 500–600. Body face:
  normal case, 15–16 px, line-height ~1.6.
- One accent colour, used for: active tab, primary button, price on the dish page, the
  "View in 3D" pill, and section eyebrows. Nothing else.
- Cards: 16 px radius, 1 px `#1d1d1d` border, 4:3 photo with a bottom gradient scrim.
- Motion, all CSS, no library: hero text rise (stagger 100 ms), 18 s hero slow-zoom,
  34 s marquee ribbon, cards fade-up on `IntersectionObserver` (45 ms stagger, capped at
  6), image scale 1.06 on hover, `document.startViewTransition` for navigation.
- **`prefers-reduced-motion` kills all of it** — one media block, non-negotiable.
- Touch targets ≥ 36 px. Visible `:focus-visible` outline. Badges carry a glyph *and* a
  word, never colour alone.

---

## 6. The 3D pipeline

### Default: photo-mapped plates (`tools/build.py`)

Real photogrammetry scans are better but need a shoot. To ship a full menu on day one,
generate a GLB per dish: a **27 cm plate** — a shallow dish with a food dome — with the
dish photograph mapped onto it, built in real-world metres so AR sizing is true.

Proven numbers, do not "improve" them without measuring:

| Parameter | Value | Why |
|---|---|---|
| Plate diameter | 0.27 m | real plate; AR at true size |
| Dome height / depth / rim | 0.055 / 0.014 / 0.006 m, × a per-dish scale | a rice mound and a soup aren't the same shape — see below |
| Mesh rings × segments | 30 × 60 | smooth enough; halving from 44×80 halved file size |
| Indices | `uint16` (5123) | verts < 65536, halves index bytes |
| Texture | 768 px, JPEG q82 colour + q80 normal map, embedded | ~200–270 KB GLB total |
| Profile | `dome·(1−(t/0.78)²)^0.85 + 0.006·t⁵` | food mound + slight rim curl |
| UV | planar, `0.5 ± 0.47·(x/R)` | photo maps top-down onto the dome |

Geometry, not texture, dominates once the texture is small — that is why ring/segment
count and 16-bit indices matter.

**The texture is a composite, not the raw photo — this is what makes it read as a plate
instead of a photo glued onto a blob.** Two things were wrong with mapping the dish photo
straight onto the whole mesh: the rim and underside showed whatever was in the photo's
*background* (table, other bowls) instead of a plate colour, and a flat photo on a curved
dome has no per-pixel shading, so it looks like exactly what it is — a picture wrapped
around a bump.

- **Ceramic base + feathered photo.** Generate a soft radial-gradient "plate" (bright
  centre, gentle falloff, a thin bright ring near the rim from `ceramic_base()`), then
  `Image.composite()` the dish photo into just the centre through a Gaussian-blurred
  circular mask sized to `FOOD_FRAC = 0.74` of the texture diameter — matched to the
  `0.78` dome-edge constant in the height profile, so the texture's food patch and the
  mesh's food mound line up. Everything outside that circle (rim, outer wall, underside)
  samples the ceramic gradient, never the photo.
- **A normal map derived from the same composite**, not a separate asset: blur slightly,
  then take the luminance gradient (`ImageChops.subtract` against a 1px-offset copy, once
  per axis) and pack it as (dx, dy, 255) into an RGB image. Real food isn't flat — rice
  grains, char, sauce ripples — so this lets the surface catch light unevenly instead of
  shading like a smooth dome. Save as JPEG, not PNG: a lossless normal map is "more
  correct" but a mostly-flat-plus-fine-detail image compresses far worse as PNG (~490 KB
  vs ~80 KB here) for a difference nobody will see at this amplification.
- **Every UV sample outside the food circle must land in the ceramic zone**, including
  the ones that seem unimportant. The underside cap originally sampled a small radius
  near texture-centre (inside the food circle) on the theory that it's "barely ever seen"
  — but `max-camera-orbit` allows dragging to 95° polar, and at a grazing angle the
  underside *is* visible, showing raw food-photo colour (a mint leaf read as a dark green
  smear across what should be a plain plate bottom). Point every non-dome UV sample at
  the same safe radius the wall uses (`R·cx·0.985`), not just the obviously-visible ones.
- **Per-dish dome height** (`DOME_SCALE`, a slug → multiplier dict): a rice dish
  (biryani, pulao) piles up, so scale >1; a stew or soup (nihari, haleem, dal) lies
  almost flat, so scale ~0.5; skewered/grilled items (kebab, tikka) are flatter
  arrangements, ~0.55. Unlisted dishes (and the 4 category-fallback models) default to
  1.0. Cheap to add, and the single biggest tell if skipped — a 5.5 cm-tall mound of dal
  looks wrong next to the real bowl on the table.

**Subject-aware cropping is essential.** A centre crop puts an off-centre bowl at the
edge of the plate and renders a black disc. Score each pixel of a 64×64 probe by
saturation × brightness with a mild centre bias, take the bounding box of everything
above 55 % of peak, crop square around it with ~10 % margin (never tighter than 45 % of
the frame). This fixed the Thai bowl that rendered as an empty black plate.

### Viewer settings that took trial and error

```html
camera-orbit="25deg 65deg 0.78m"  field-of-view="30deg"
min-camera-orbit="auto 0deg 0.4m" max-camera-orbit="auto 95deg 1.6m"
auto-rotate auto-rotate-delay="600" rotation-per-second="22deg"
shadow-intensity="1.1" shadow-softness="0.8" exposure="1.05" environment-image="neutral"
ar ar-modes="webxr scene-viewer quick-look" ar-placement="floor" ar-scale="fixed"
poster="img/<slug>-1200.webp"
```

A **fixed** camera radius, not `auto` — auto frames each dish differently and a burger
ends up filling the screen while a plate looks tiny.

`<model-viewer>` 4.3.1 from jsdelivr, loaded with a dynamic `import()` **only on the dish
view**. iOS Quick Look gets a USDZ generated on the fly from the GLB; no separate file.

### Upgrading to real scans

Drop a real `.glb` into `models/<slug>.glb` — no code change. Guidance for the client's
photographer:

- Scans well: burgers, kebabs, steaks, pizza, platters, cakes. Scans badly: drinks in
  glass, glossy gravies, soups, fine noodles.
- Matte plain surface, soft even light, 4–5 tracking markers around (not on) the plate,
  locked focus/exposure, three orbits at ~15° / 45° / 75°, ~2 min of 4K video, dish
  filling two-thirds of frame. Stills (60–120) beat video.
- Apps: Polycam, RealityScan, Scaniverse, Kiri Engine. Export GLB under 5 MB, textures
  ≤ 2048 px, real-world scale. Also ask for the plate diameter in cm.
- For dishes photogrammetry can't handle, single-image AI-to-3D (Meshy / Tripo / Rodin)
  is a cheap stand-in.
- Scan only the signature dishes. Nobody scans a QR expecting cheese sticks in AR.

---

## 7. Ordering

### Data flow

```
guest phone                        the restaurant's system (chosen later)
┌──────────────────────────┐        ┌────────────────────────────┐
│ Cart (localStorage)      │        │ POST  /orders   accept     │
│  ↓ review + table no.    │  JSON  │ GET   /orders   feed       │
│ Order.build() → payload  │ ─────► │ PATCH /orders/:id  status  │
│  ↓ Order.send()          │        └────────────────────────────┘
│ fail → queue + WhatsApp  │                     ↓
│  ↓ retry on next load    │            kitchen.html (polls feed)
└──────────────────────────┘
```

### Payload

Full contract in `docs/order-payload.md` — that file is the deliverable you hand to
whoever builds the receiving end.

```json
{ "orderId":"MST-12-140034-R3X", "placedAt":"2026-09-14T07:34:21.905Z",
  "venue":"Mastara", "source":"qr-3d-menu", "table":"12",
  "guest":{"name":"Haider","phone":""}, "note":"less spicy", "currency":"PKR",
  "items":[{"slug":"beef-nihari","name":"Beef Nihari","category":"desi",
            "unitPrice":1150,"qty":1,"lineTotal":1150}],
  "totals":{"subtotal":2750,"taxPercent":0,"tax":0,
            "servicePercent":0,"service":0,"total":2750} }
```

Rules for the receiver: **be idempotent on `orderId`** (retries are by design),
**re-price server-side** (totals arrive from a phone), rate-limit (the endpoint is public
to anyone who can read a QR code).

### Behaviour that matters

- Table comes from `?t=12` in the QR, is stored, and pre-fills the order form. A guest
  can correct it; it is required before sending unless `requireTable:false`.
- Cart survives reloads (`localStorage`), and drops any dish that no longer exists in
  `menu.js` so an edited menu can never produce a bogus line.
- Every `localStorage` read/write is wrapped in `try/catch` — it throws in private mode
  and in some in-app webviews. A storage failure must not take the menu down.
- Validation before send: table present, cart non-empty, phone format if given.
- Confirmation screen shows an order number and a plain-text ticket the guest can show a
  waiter — that is the universal fallback when everything else fails.
- WhatsApp is a *link the guest taps*, prefilled with the ticket. Never auto-send.
- 8 s timeout on the POST. Non-2xx or timeout → queue + retry on next page load.

### Kitchen display

Light background (bright kitchens), huge table number, quantities first, the guest's note
highlighted, total, and `new → preparing → served` buttons. Audible alert on new tickets
(WebAudio beep, off until the user enables it — browsers block autoplay). Polls the feed;
with no feed configured it shows that device's own orders, which is enough to demo.

---

## 8. QR codes

`qr.html` generates and prints both kinds, using qrcodejs from cdnjs:

- **Table cards `?t=N`** — the important one. Logo, "TABLE", huge number, QR, "Scan to
  view the menu in 3D & order". Print 1…`CONFIG.tableCount`.
- **Dish cards `?d=slug`** — one dish straight into 3D/AR. Good for specials, counters,
  or a printed menu insert.

Print stylesheet: 3-up grid, dashed cut lines, `page-break-inside: avoid`, dark-on-white.
The operator pastes the live URL into one field and hits print.

---

## 9. Performance budget

Measured on the reference build — hold a new build to the same numbers.

| | |
|---|---|
| First load (phone) | ~290 KB — 6.6 KB HTML gzipped, 68 KB fonts, 115 KB hero, lazy cards |
| Requests to first paint | 9 |
| Dish page extra | model-viewer ~150 KB gz + one GLB ~190 KB, behind an instant poster |

Techniques: inline all CSS and app JS; preload fonts + hero with `imagesrcset`; WebP with
`srcset`/`sizes`; explicit `width`/`height` on every image (zero CLS); `loading="lazy"`
below the fold; self-hosted fonts with `font-display:swap`; dynamic `import()` for the 3D
library; no framework, no analytics unless asked.

---

## 10. Gotchas — read this before debugging

Each of these cost real time on the first build.

1. **`mv.canActivateAR` is meaningless until the model loads.** Check it inside the
   `load` handler, not straight after creating the element, or every phone is told "AR
   needs a phone".
2. **Centre-cropping food photos breaks the 3D plates** — use the saliency crop (§6).
3. **Cross-origin POST from a phone/webview** needs CORS *and* an `OPTIONS` preflight.
   Simplest cure: serve the orders API on the **same origin** as the menu. A `204`
   preflight response must carry **no body** — a body makes browsers hang with
   `ERR_EMPTY_RESPONSE`.
4. **Use `ThreadingHTTPServer`**, not `HTTPServer`, for any local API — a single-threaded
   one wedges on a browser's keep-alive connection.
5. **Windows consoles are cp1252.** A `✓` in a `print()` crashes a Python server thread.
   ASCII only in server logs.
6. **Static dev servers cache aggressively.** If an edit "didn't apply", reload with
   `?v=2` before debugging code that is already correct.
7. **Kill stale background servers** before starting a new one — the old process keeps
   the port and you debug code that isn't running.
8. **AR requires HTTPS** in production (`localhost` is exempt). Any of Vercel / Netlify /
   Cloudflare Pages gives it free.
9. Don't nest a `<button>` inside an `<a>` for "Add to cart" — invalid HTML and the click
   navigates. Use an `<article>` with separate links and buttons.
10. Re-render the whole view on cart change and you destroy the loaded 3D model. Patch
    only the affected controls (`[data-buy]` nodes) plus the sticky bar.

---

## 11. Build order

Roughly a day's work for a restaurant with a decent website.

1. Scrape site: brand tokens, fonts, logo, full menu (all tabs), contact, hours. Note
   anything broken to report back.
2. Download dish photos + logo into `assets/`. Self-host the two fonts.
3. Write `menu.js` (categories, dishes, badges, VENUE) and `config.js`. **Ask for prices**;
   if unavailable, use flagged placeholders.
4. Run `tools/build.py` → `img/*.webp` + `models/*.glb`. Eyeball a contact sheet of the
   crops before trusting them.
5. Re-skin `index.html` to the brand. Check the menu, a dish, 3D load, and AR button
   state on a mobile viewport.
6. Wire ordering: cart, order form, confirmation. Test the full loop against
   `tools/mock-kitchen-server.py` — the order must reach a *separate process*, not just
   localStorage.
7. `kitchen.html` + `qr.html`. Print-preview the table cards.
8. README + `docs/order-payload.md` with the client's specifics.
9. Deploy to a static host, open `qr.html`, paste the live URL, print.

---

## 12. Definition of done

- [ ] Menu, dish 3D, AR button, cart, order, confirmation all work on a 375 px viewport
- [ ] An order placed in the browser arrives in a **separate process** (verify the JSON)
- [ ] Kitchen screen shows it with the right table number, items, note and total
- [ ] Endpoint unreachable → order queued, WhatsApp ticket offered, retried on reload
- [ ] Table QR `?t=N` pre-fills the table; dish QR `?d=slug` opens that dish in 3D
- [ ] No console errors; no 404s; no layout shift
- [ ] `prefers-reduced-motion` respected; keyboard navigable; focus visible
- [ ] First load ≤ ~300 KB; 3D library not requested on the menu page
- [ ] Placeholder prices flagged in `menu.js`, README and the handover message
- [ ] README states what is placeholder, what is real, and what the client must supply

---

## 13. Scope guardrails

Build only what is listed here unless the client asks. Deliberately **not** included:
guest accounts, online payment, editing an order after sending, per-item notes, loyalty,
table reservations, a CMS or admin UI, analytics, multi-language. Each is a real feature
with real maintenance; none is needed for the QR → 3D → order loop to earn its keep.

When the client picks a real POS/KDS, *that* API decides how order editing and payment
should work — so building them first is guaranteed rework.

---

## 14. Handover message template

> **What you have:** a QR menu where guests see dishes in 3D/AR and send orders straight
> to the kitchen, live at \<url\>.
> **To go live:** (1) replace the placeholder prices in `menu.js`, (2) set `taxPercent` /
> `servicePercent` in `config.js` to what you actually charge, (3) confirm `tableCount`
> and print the cards from `qr.html`, (4) when you choose a POS/kitchen system, give them
> `docs/order-payload.md` and put their URL in `config.js`.
> **Today, with no system connected:** orders reach you as a prefilled WhatsApp message,
> and the guest can always show the waiter their confirmation screen.
