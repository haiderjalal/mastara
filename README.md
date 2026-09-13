# Mastara — QR → 3D / AR menu

A guest scans the QR code on the table, the dish opens full-screen in 3D, and one tap
places it life-size on their table in augmented reality. Static site, no build step,
no framework — three HTML/JS files plus generated assets.

```
index.html   menu grid + ?d=<slug> dish view with 3D/AR   (all CSS + app JS inlined)
menu.js      41 dishes, 5 cuisines, venue details          (shared with qr.html)
qr.html      prints one QR table-tent per dish
img/         WebP photos (560 / 1200 wide) + hero + logo
models/      one .glb per dish photo
fonts/       Oswald + Raleway, self-hosted latin subsets
assets/      source material: original photos, logo, brand guideline PDF
tools/build.py  regenerates everything in img/ and models/ from assets/
```

## Run it

```bash
python -m http.server 8765
```

Open http://localhost:8765/ — and http://localhost:8765/qr.html to print the table cards.

Only `index.html`, `menu.js`, `qr.html`, `img/`, `models/` and `fonts/` need to be deployed;
`assets/` and `tools/` are source material (the brand PDF alone is 41 MB).

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
