"""Build web assets: optimized WebP images + per-dish 3D plate models (GLB).

Run:  python tools/build.py
Input:  assets/dishes/*.jpg  (one photo per dish)  and  assets/cat/*.jpg (category fallbacks)
Output: img/*.webp  and  models/*.glb

The GLB is a "plate" mesh — a shallow dish with a food dome in the middle — with the
dish photograph mapped onto it and sized to a real 27 cm plate, so AR places it on the
table at true size. Replace any .glb with a real photogrammetry scan when you have one.

The texture is a composite, not the raw photo: a soft ceramic-plate gradient with the
food photo blended into just the dome area, so the rim reads as a plate edge instead of
whatever was in the background of the photo. A normal map derived from the photo's own
detail (rice grains, char, sauce texture) is baked in too, so the surface catches light
unevenly instead of looking like a photo glued onto a smooth bump.
"""
import io, json, math, os, struct, glob
from PIL import Image, ImageDraw, ImageFilter, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
os.makedirs("img", exist_ok=True)
os.makedirs("models", exist_ok=True)

# ---------------------------------------------------------------- images
def square(im: Image.Image, margin: float = 0.18) -> Image.Image:
    """Square crop around the food itself, not the middle of the frame.

    Food photography is rarely centred and often sits on a lot of empty dark table —
    a bowl in the lower-left corner would map onto the plate model as a black disc.
    Weighting pixels by saturation and brightness locates the dish, then the crop is
    taken around everything that scores highly, plus `margin` breathing room."""
    N = 64
    probe = im.convert("RGB").resize((N, N), Image.BILINEAR)
    px = probe.load()
    w = [[0.0] * N for _ in range(N)]
    peak = 0.0
    for y in range(N):
        for x in range(N):
            r, g, b = px[x, y]
            hi, lo = max(r, g, b), min(r, g, b)
            v = (0.35 + (hi - lo) / 255) * (0.2 + hi / 255)
            v *= 1 - 0.3 * (((x - (N - 1) / 2) / (N / 2)) ** 2 + ((y - (N - 1) / 2) / (N / 2)) ** 2) / 2
            w[y][x] = v
            peak = max(peak, v)
    cut = peak * 0.55
    xs = [x for y in range(N) for x in range(N) if w[y][x] >= cut]
    ys = [y for y in range(N) for x in range(N) if w[y][x] >= cut]
    if not xs:
        cx = cy = 0.5
        side = 1.0
    else:
        x0, x1, y0, y1 = min(xs), max(xs) + 1, min(ys), max(ys) + 1
        cx, cy = (x0 + x1) / 2 / N, (y0 + y1) / 2 / N
        side = max(x1 - x0, y1 - y0) / N * (1 + margin)

    short = min(im.size)
    s_px = round(min(max(side * short, short * 0.45), short))   # never crazier than 45% of the frame
    left = min(max(round(cx * im.width - s_px / 2), 0), im.width - s_px)
    top = min(max(round(cy * im.height - s_px / 2), 0), im.height - s_px)
    return im.crop((left, top, left + s_px, top + s_px))


def webp(im: Image.Image, out: str, width: int, quality: int) -> None:
    w, h = im.size
    im = im.resize((width, round(h * width / w)), Image.LANCZOS)
    im.save(out, "WEBP", quality=quality, method=6)

def build_images(src: str, slug: str, sizes=((560, 72), (1200, 76))) -> None:
    im = square(Image.open(src).convert("RGB"))
    for width, q in sizes:
        webp(im, f"img/{slug}-{width}.webp", width, q)

# ---------------------------------------------------------------- 3D plate
PLATE_D, DOME, RIM, DEPTH = 0.27, 0.055, 0.006, 0.014   # metres
NR, NS = 30, 60                                          # rings, segments
DOME_EDGE = 0.78   # fraction of plate radius where the food mound ends (matches FOOD_FRAC below)

# Real dishes aren't all the same shape — a rice mound piles up, a stew lies flat.
# Height is a multiplier on DOME; skipped dishes (incl. the 4 category fallbacks) get 1.0.
DOME_SCALE = {
    "chicken-biryani": 1.15, "mutton-pulao": 1.1,
    "mutton-karahi": 0.75, "chicken-karahi": 0.75,
    "beef-nihari": 0.55, "haleem": 0.5, "dal-makhani": 0.5,
    "seekh-kebab": 0.55, "chicken-tikka": 0.55,
}

def profile(t: float, scale: float = 1.0) -> float:
    food = DOME * scale * max(0.0, 1.0 - (t / DOME_EDGE) ** 2) ** 0.85
    return food + RIM * t ** 5

# ------------------------------------------------------------- plate texture
FOOD_FRAC = 0.74   # diameter of the food photo circle, as a fraction of the full texture —
                    # matched to DOME_EDGE so the texture's food patch lines up with the mesh's food dome

def ceramic_base(size: int, tint=(241, 235, 224)) -> Image.Image:
    """A plain plate is a gradient, not a texture: bright centre, gentle falloff,
    a thin bright ring where light catches the rim's bevel."""
    n = 128
    c = n / 2
    edge_shade = int(232 - 34 * 0.7 ** 1.3)   # matches the f=1.0 ring below — keeps the untextured corners consistent
    g = Image.new("L", (n, n), edge_shade)
    d = ImageDraw.Draw(g)
    for i in range(int(c), 0, -1):
        f = i / c
        shade = 232 - 34 * max(0.0, f - 0.3) ** 1.3
        shade += 16 * math.exp(-((f - 0.88) ** 2) / 0.006)
        d.ellipse([c - i, c - i, c + i, c + i], fill=int(max(0, min(255, shade))))
    g = g.filter(ImageFilter.GaussianBlur(2)).resize((size, size), Image.LANCZOS)
    return Image.merge("RGB", [g.point(lambda v, ch=ch: v * ch // 232) for ch in tint])

def build_texture(src_photo: str, tex_px: int) -> Image.Image:
    """Ceramic plate gradient with the dish photo feathered into the food-dome area only —
    the rim and underside stay a clean plate colour instead of showing photo background."""
    food = square(Image.open(src_photo).convert("RGB"), margin=0.03).resize((tex_px, tex_px), Image.LANCZOS)
    base = ceramic_base(tex_px)
    mask = Image.new("L", (tex_px, tex_px), 0)
    r = tex_px * FOOD_FRAC / 2
    c = tex_px / 2
    ImageDraw.Draw(mask).ellipse([c - r, c - r, c + r, c + r], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(tex_px * 0.02))
    return Image.composite(food, base, mask)

def make_normal_map(color_im: Image.Image, amplify: float = 3.0) -> Image.Image:
    """Cheap bump map from the texture's own luminance gradient — real food isn't flat,
    so letting rice grains / char / sauce ripples perturb the surface normal is what
    keeps the dome from reading as 'photo glued onto a smooth blob' as it catches light."""
    g = color_im.convert("L").filter(ImageFilter.GaussianBlur(0.7))
    dx = ImageChops.subtract(g, ImageChops.offset(g, -1, 0), scale=1.0 / amplify, offset=128)
    dy = ImageChops.subtract(g, ImageChops.offset(g, 0, -1), scale=1.0 / amplify, offset=128)
    b = Image.new("L", g.size, 255)
    return Image.merge("RGB", (dx, dy, b))

def build_glb(src_photo: str, out: str, tex_px: int = 768, dome_scale: float = 1.0) -> None:
    R = PLATE_D / 2
    pos, nrm, uv, idx = [], [], [], []

    def planar_uv(x, z):
        return (0.5 + 0.47 * x / R, 0.5 + 0.47 * z / R)

    # --- top surface (food dome + rim)
    for i in range(NR + 1):
        t = i / NR
        r = t * R
        y = profile(t, dome_scale)
        dt = 1e-4
        slope = (profile(min(1.0, t + dt), dome_scale) - profile(max(0.0, t - dt), dome_scale)) / ((min(1.0, t + dt) - max(0.0, t - dt)) * R)
        for j in range(NS):
            a = 2 * math.pi * j / NS
            cx, cz = math.cos(a), math.sin(a)
            x, z = r * cx, r * cz
            pos.append((x, y, z))
            n = (-slope * cx, 1.0, -slope * cz)
            L = math.sqrt(sum(c * c for c in n)) or 1.0
            nrm.append(tuple(c / L for c in n))
            uv.append(planar_uv(x, z))
    for i in range(NR):
        for j in range(NS):
            a = i * NS + j
            b = i * NS + (j + 1) % NS
            c = (i + 1) * NS + (j + 1) % NS
            d = (i + 1) * NS + j
            idx += [a, b, c, a, c, d]

    # --- outer wall
    base = len(pos)
    y_top = profile(1.0, dome_scale)
    for ring_y in (y_top, -DEPTH):
        for j in range(NS):
            a = 2 * math.pi * j / NS
            cx, cz = math.cos(a), math.sin(a)
            pos.append((R * cx, ring_y, R * cz))
            nrm.append((cx, 0.0, cz))
            uv.append(planar_uv(R * cx * 0.985, R * cz * 0.985))
    for j in range(NS):
        a = base + j
        b = base + (j + 1) % NS
        c = base + NS + (j + 1) % NS
        d = base + NS + j
        idx += [a, c, b, a, d, c]

    # --- bottom
    cbase = len(pos)
    pos.append((0.0, -DEPTH, 0.0)); nrm.append((0.0, -1.0, 0.0)); uv.append(planar_uv(R * 0.985, 0.0))
    for j in range(NS):
        a = 2 * math.pi * j / NS
        cx, cz = math.cos(a), math.sin(a)
        pos.append((R * cx, -DEPTH, R * cz)); nrm.append((0.0, -1.0, 0.0))
        uv.append(planar_uv(R * cx * 0.985, R * cz * 0.985))   # clean ceramic band, not the food photo — this face is barely ever seen
    for j in range(NS):
        idx += [cbase, cbase + 1 + (j + 1) % NS, cbase + 1 + j]

    # --- texture: ceramic plate + feathered food photo, plus a bump map derived from it
    color_im = build_texture(src_photo, tex_px)
    jpg = io.BytesIO(); color_im.save(jpg, "JPEG", quality=82, optimize=True); tex = jpg.getvalue()
    nrm_buf = io.BytesIO(); make_normal_map(color_im).save(nrm_buf, "JPEG", quality=80, optimize=True); nrm_tex = nrm_buf.getvalue()

    # --- binary buffer
    def pad4(b): return b + b"\x00" * ((4 - len(b) % 4) % 4)
    b_pos = struct.pack("<%df" % (len(pos) * 3), *[c for v in pos for c in v])
    b_nrm = struct.pack("<%df" % (len(nrm) * 3), *[c for v in nrm for c in v])
    b_uv  = struct.pack("<%df" % (len(uv) * 2), *[c for v in uv for c in v])
    u16 = len(pos) < 65536
    b_idx = struct.pack(("<%dH" if u16 else "<%dI") % len(idx), *idx)
    parts, views, off = [], [], 0
    for data, target in ((b_pos, 34962), (b_nrm, 34962), (b_uv, 34962), (b_idx, 34963), (tex, None), (nrm_tex, None)):
        d = pad4(data)
        v = {"buffer": 0, "byteOffset": off, "byteLength": len(data)}
        if target: v["target"] = target
        views.append(v); parts.append(d); off += len(d)
    blob = b"".join(parts)

    mins = [min(v[k] for v in pos) for k in range(3)]
    maxs = [max(v[k] for v in pos) for k in range(3)]
    gltf = {
        "asset": {"version": "2.0", "generator": "mastara plate builder"},
        "scene": 0, "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": os.path.basename(out)[:-4]}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                                    "indices": 3, "material": 0}]}],
        "materials": [{"name": "dish", "doubleSided": False,
                       "pbrMetallicRoughness": {"baseColorTexture": {"index": 0},
                                                "metallicFactor": 0.0, "roughnessFactor": 0.55},
                       "normalTexture": {"index": 1}}],
        "textures": [{"sampler": 0, "source": 0}, {"sampler": 0, "source": 1}],
        "images": [{"bufferView": 4, "mimeType": "image/jpeg"}, {"bufferView": 5, "mimeType": "image/jpeg"}],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 33071, "wrapT": 33071}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(pos), "type": "VEC3", "min": mins, "max": maxs},
            {"bufferView": 1, "componentType": 5126, "count": len(nrm), "type": "VEC3"},
            {"bufferView": 2, "componentType": 5126, "count": len(uv), "type": "VEC2"},
            {"bufferView": 3, "componentType": 5123 if u16 else 5125, "count": len(idx), "type": "SCALAR"},
        ],
        "bufferViews": views,
        "buffers": [{"byteLength": len(blob)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    glb = b"glTF" + struct.pack("<II", 2, 12 + 8 + len(js) + 8 + len(blob))
    glb += struct.pack("<I", len(js)) + b"JSON" + js
    glb += struct.pack("<I", len(blob)) + b"BIN\x00" + blob
    with open(out, "wb") as f:
        f.write(glb)

# ---------------------------------------------------------------- run
if __name__ == "__main__":
    jobs = [(p, os.path.basename(p)[:-4]) for p in sorted(glob.glob("assets/dishes/*.jpg"))]
    jobs += [(f"assets/cat/{n}.jpg", n) for n in ("thai", "chinese", "fastfood", "continental")]
    for src, slug in jobs:
        build_images(src, slug)
        build_glb(src, f"models/{slug}.glb", dome_scale=DOME_SCALE.get(slug, 1.0))
        print(f"{slug:20s} {os.path.getsize(f'models/{slug}.glb')//1024:5d} KB glb")
    hero = Image.open("assets/cat/hero.jpg").convert("RGB")
    for w in (900, 1600):
        webp(hero, f"img/hero-{w}.webp", w, 72)
    logo = Image.open("assets/brand/logo.png").convert("RGBA")
    logo.resize((320, round(logo.height * 320 / logo.width)), Image.LANCZOS).save("img/logo.webp", "WEBP", quality=88, method=6)
    print("images:", sum(os.path.getsize(f) for f in glob.glob("img/*")) // 1024, "KB total")
