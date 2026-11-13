# ABANDONED · Modulare Bodenplatten fuer das Gebaeude "krankenhaus"
# Fuenf Stuecke: vier Platten 4 x 4 m (Oberseite auf Z = 0, 20 cm dick) und eine Tuerschwelle 1,0 x 0,2 m.
# Zwei kachelbare Materialien ("Boden", "BodenDetail") mit je 4096 x 4096 px, 1024 px/m.
# Export als glTF 2.0 (.gltf + .bin), Texturen als relativer Pfad auf Texturen/krankenhaus/.
# Start: blender -b -P kit_boden_krankenhaus.py  (oder mit dem bpy-Modul: python kit_boden_krankenhaus.py).
# Das Skript setzt Blender auf Werkseinstellungen zurueck, also nicht in einem offenen Projekt ausfuehren.
import bpy, bmesh, math, random, os, time, json, zlib, struct
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, noise, geometry

T0 = time.time()
def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)

GEB = "krankenhaus"
OUT = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(OUT, "PolyHaven")              # entspricht C:\Users\Henry\Abandoned\SourceArt\PolyHaven
MODELLE = os.path.join(ROOT, "Modelle")
TEXDIR = os.path.join(ROOT, "Texturen", GEB)
for d in (MODELLE, TEXDIR):
    os.makedirs(d, exist_ok=True)
TEXRES = 4096
TEXDIV = int(os.environ.get("TEXDIV", "1"))
NPX = TEXRES // TEXDIV
UVS = 0.25                                          # UV je Meter -> 1024 px/m
SHOTS = [s for s in os.environ.get("SHOTS", "uebersicht,kacheln,lampe1,lampe2,lampe3,lampe4,nah1,nah2,nah3,nah4").split(",") if s]
SAMPLES = int(os.environ.get("SAMPLES", "64"))
RES = [int(v) for v in os.environ.get("RES", "1920x1080").split("x")]

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("io_scene_gltf2", default_set=True)
scene = bpy.context.scene

# ---------------- Masse ----------------
P2 = 2.0                       # halbe Kantenlaenge der Platte
DICKE = 0.20
RAND = 0.05                    # die aeussersten 5 cm sind exakt flach auf Z = 0
INNEN = P2 - RAND
LOSE = 0.30                    # lose Teile nie naeher am Rand
LINO = 0.0025                  # Linoleum 2,5 mm
KT = 0.003                     # Bruchkante des Linoleums mit Kleberrest darunter
EZ = -0.003                    # Oberkante Estrich mit altem Kleber
NAEHTE = (-1.0, 1.0)           # verschweisste Naehte der 2 m breiten Bahnen
NAHT_E = (0.0018, 0.0065, 0.02, 0.042)       # Spalten des Nahtwulsts (Abstand von der Nahtmitte)
NAHT_P = (0.8, 1.0, 0.45, 0.0)               # Wulsthoehe dort (Anteil)
FL, FW, FT = 0.1, 0.0015, 0.002              # Fliese 10 cm, halbe Fugenbreite, Fugentiefe
SW, ST = 0.5, 0.1              # Schwelle: halbe Breite (x), halbe Tiefe (y)

# Detail-Atlas: waagerechte Bereiche (Meter von unten, 4 m = ganze Hoehe). Die Bereiche rechts der OP-Mitte
# belegen nur U 1,2 .. 4,0 m, die OP-Mitte selbst U 0 .. 1,2 m.
REG = {
    "estrich": (0.00, 1.60), "alu": (1.60, 1.70), "kante": (1.70, 1.90), "kante_fliese": (1.90, 2.10),
    "fliesen": (2.10, 2.70), "fliesenkante": (2.70, 2.72), "fuge": (2.72, 2.74), "edelstahl": (2.74, 2.80),
    "ruecken": (2.80, 3.30), "lino_schnitt": (3.30, 3.34), "schleif": (3.34, 3.40), "beton": (3.40, 3.70),
    "glas": (3.70, 3.78), "papier": (3.78, 4.00),
}
RECHTS = ("ruecken", "lino_schnitt", "schleif", "beton", "glas", "papier")
U_RECHTS = (1.2, 4.0)
ZENTRUM = (0.0, 1.2, 2.80, 4.00)             # U 0 .. 1,2 m, V 2,8 .. 4,0 m: x, y = -0,6 .. 0,6 der OP-Platte
ZR = 0.6
ABL_R = (0.098, 0.1, 0.137, 0.142)           # Ablauf: Topf, Rost, Beginn der Fase, Flansch (Radien); Fliesen rund geschnitten

# ======================= Texturen: Werkzeuge =======================
def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)

def sm(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)

def mix(a, b, t):
    t = np.asarray(t, dtype=np.float32)
    return a * (1 - t[..., None]) + b * t[..., None]

def fr(shape, beta, seed, aniso=1.0, sigma_m=0.0):
    """Kachelbares Rauschen (FFT), Pixel = 4 m / NPX. aniso > 1 streckt in Zeilenrichtung (V)."""
    h, w = shape
    rng = np.random.default_rng(seed)
    F = np.fft.rfft2(rng.standard_normal((h, w)).astype(np.float32))
    fy = np.fft.fftfreq(h)[:, None].astype(np.float32)
    fx = np.fft.rfftfreq(w)[None, :].astype(np.float32)
    f = np.sqrt(fx * fx + (fy * aniso) ** 2)
    f[0, 0] = 1.0
    F *= (1.0 / f ** beta).astype(np.float32)
    if sigma_m:
        sp = sigma_m * NPX / 4.0
        F *= np.exp(-2 * (math.pi * sp) ** 2 * (fx * fx + fy * fy)).astype(np.float32)
    F[0, 0] = 0
    r = np.fft.irfft2(F, s=(h, w)).astype(np.float32)
    return (r - r.mean()) / (r.std() + 1e-9)

def frh(shape, beta, seed, aniso=1.0, sigma_m=0.0):
    """Wie fr, aber in U-Richtung gestreckt (Schliff, Kratzer laengs)."""
    return np.ascontiguousarray(fr((shape[1], shape[0]), beta, seed, aniso, sigma_m).T)

def pdist(X, c, period=4.0):
    """Abstand zu c auf einem Ring der Laenge period."""
    return np.abs(np.mod(X - c + period / 2, period) - period / 2)

def raster_lines(S, lines, width, wrap=(4.0, 4.0), vals=None, rough=0.0, seed=0):
    """Linienzuege (Meter, Ursprung unten links des Bereichs) als weiche Maske 0..1, kachelt mit den Perioden wrap.
    Duenne Linien werden auf mindestens 0,8 Pixel verbreitert und dafuer schwaecher."""
    n_r, n_c = S
    px = 4.0 / NPX
    M = np.zeros(S, np.float32)
    rng = np.random.default_rng(seed)
    sx = (-wrap[0], 0.0, wrap[0]) if wrap[0] else (0.0,)
    sy = (-wrap[1], 0.0, wrap[1]) if wrap[1] else (0.0,)
    for li, line in enumerate(lines):
        val = 1.0 if vals is None else vals[li]
        for (ax, az), (bx, bz) in zip(line[:-1], line[1:]):
            wv = width * (1 + rough * (rng.random() - 0.5))
            k = val
            if wv < 0.8 * px:
                k *= wv / (0.8 * px)
                wv = 0.8 * px
            for ox in sx:
                for oy in sy:
                    x0, x1 = min(ax, bx) + ox - 2 * wv, max(ax, bx) + ox + 2 * wv
                    z0, z1 = min(az, bz) + oy - 2 * wv, max(az, bz) + oy + 2 * wv
                    c0, c1 = max(0, int(x0 / px)), min(n_c, int(x1 / px) + 2)
                    r0, r1 = max(0, int(z0 / px)), min(n_r, int(z1 / px) + 2)
                    if c1 <= c0 or r1 <= r0:
                        continue
                    xs = (np.arange(c0, c1, dtype=np.float32) + 0.5) * px - ox
                    zs = (np.arange(r0, r1, dtype=np.float32) + 0.5) * px - oy
                    PX, PZ = np.meshgrid(xs, zs)
                    dx, dz = bx - ax, bz - az
                    L2 = dx * dx + dz * dz + 1e-12
                    t = np.clip(((PX - ax) * dx + (PZ - az) * dz) / L2, 0, 1)
                    d = np.hypot(PX - (ax + t * dx), PZ - (az + t * dz))
                    M[r0:r1, c0:c1] = np.maximum(M[r0:r1, c0:c1], k * sm(wv, wv * 0.35, d))
    return M

def curve(p0, ang, length, bend, steps, rng=None, wob=0.0):
    """Sanft gebogener Linienzug ab p0 in Richtung ang (Bogenmass), Kruemmung bend (1/m)."""
    pts = [p0]
    x, y = p0
    ds = length / steps
    for _ in range(steps):
        ang += bend * ds + (rng.normal(0, wob) if rng is not None and wob else 0.0)
        x, y = x + math.cos(ang) * ds, y + math.sin(ang) * ds
        pts.append((x, y))
    return pts

def normal_map(hgt_m):
    px = 4.0 / NPX
    dx = (np.roll(hgt_m, -1, 1) - np.roll(hgt_m, 1, 1)) / (2 * px)
    dz = (np.roll(hgt_m, -1, 0) - np.roll(hgt_m, 1, 0)) / (2 * px)
    n = np.dstack([-dx, -dz, np.ones_like(hgt_m)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5                       # OpenGL (+Y), wie glTF es verlangt

def write_png(path, arr):
    """8-Bit-RGB-PNG. Zeile 0 der Matrix ist unten im Bild (wie in Blender). Jede Zeile mit Filter 'Up',
    so laesst sich die Datei auch ohne Bildbibliothek pruefen."""
    a = np.clip(np.round(np.asarray(arr) * 255.0), 0, 255).astype(np.uint8)[::-1]
    h, w = a.shape[:2]
    raw = np.ascontiguousarray(a).reshape(h, w * 3)
    up = raw.copy()
    up[1:] = raw[1:] - raw[:-1]
    data = np.hstack([np.full((h, 1), 2, np.uint8), up]).tobytes()
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(data, 6)) + chunk(b"IEND", b""))

def save_jpg(name, arr):
    hgt, wid = arr.shape[:2]
    img = bpy.data.images.new(name, wid, hgt, alpha=False)
    rgba = np.ones((hgt, wid, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(arr, 0, 1)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = os.path.join(TEXDIR, name + ".jpg")
    img.file_format = "JPEG"
    img.save(quality=92)
    return img

def load_png(name):
    img = bpy.data.images.load(os.path.join(TEXDIR, name + ".png"))
    img.colorspace_settings.name = "Non-Color"
    return img

def write_set(prefix, alb, hgt_m, rough):
    """Grundfarbe (sRGB, JPG), Normale (OpenGL, PNG), Rauheit (PNG: Rot = 255, Gruen = Rauheit, Blau = 0)."""
    base = save_jpg(prefix + "_Grundfarbe", alb)
    write_png(os.path.join(TEXDIR, prefix + "_Normale.png"), normal_map(hgt_m))
    rgh = np.dstack([np.ones_like(rough), np.clip(rough, 0.03, 1.0), np.zeros_like(rough)])
    write_png(os.path.join(TEXDIR, prefix + "_Rauheit.png"), rgh)
    log("Textur", prefix, NPX)
    return {"base": base, "normal": load_png(prefix + "_Normale"), "rough": load_png(prefix + "_Rauheit")}

# ======================= Textur "Boden": graugruenes Linoleum, 4 x 4 m weltbezogen =======================
def offset_line(pts, d):
    out = []
    for i, (x, y) in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        L = math.hypot(tx, ty) or 1.0
        out.append((x - ty / L * d, y + tx / L * d))
    return out

def dashes(pts, rng, on=(0.15, 0.7), off=(0.05, 0.35)):
    """Linienzug in Striche mit Luecken zerlegen."""
    out, cur, state, left = [], [], True, rng.uniform(*on)
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if state:
            cur.append(a)
        left -= seg
        if left <= 0:
            if state:
                cur.append(b)
                if len(cur) > 1:
                    out.append(cur)
                cur = []
            state = not state
            left = rng.uniform(*(on if state else off))
    if state and cur:
        cur.append(pts[-1])
        out.append(cur)
    return out

def tex_boden():
    n = NPX
    S = (n, n)
    px = 4.0 / n
    c = (np.arange(n, dtype=np.float32) + 0.5) * px
    X = np.broadcast_to(c[None, :], S)
    Y = np.broadcast_to(c[:, None], S)
    sd = [100]
    def nz(beta, aniso=1.0, sigma_m=0.0):
        sd[0] += 1
        return fr(S, beta, sd[0], aniso, sigma_m)
    rng = np.random.default_rng(31)
    # ---- Bahnen 2 m breit, Naehte bei X = 1 und 3 (Welt x = -1 und +1); Marmorierung laeuft laengs der Bahn ----
    dn = np.minimum(pdist(X, 1.0), pdist(X, 3.0))
    mitte = (X >= 1.0) & (X < 3.0)
    alb = np.empty(S + (3,), np.float32)
    alb[...] = hexc("#778375")
    alb[mitte] = hexc("#7c8879")
    m = np.where(mitte, nz(1.45, aniso=7.0), nz(1.45, aniso=7.0))
    f = np.where(mitte, nz(0.9, aniso=4.0, sigma_m=0.0005), nz(0.9, aniso=4.0, sigma_m=0.0005))
    mf = m + 0.35 * f
    alb *= (1 + 0.04 * m + 0.03 * f)[..., None]
    alb = mix(alb, hexc("#a3ab9a"), 0.28 * sm(1.0, 2.0, mf))
    alb = mix(alb, hexc("#5a6657"), 0.26 * sm(-1.0, -2.0, mf))
    # ---- vergilbt, verschmutzt, stumpf abgelaufen ----
    yel = sm(-0.5, 1.7, nz(2.5))
    alb = mix(alb, hexc("#8f8a60"), 0.34 * yel)
    grime = sm(-0.2, 2.0, nz(2.1) + 0.45 * nz(1.3))
    alb = mix(alb, hexc("#4b4d43"), 0.30 * grime)
    wear = sm(0.2, 1.8, nz(2.3)) * sm(-0.6, 1.0, nz(1.1))
    alb = mix(alb, hexc("#8e9686"), 0.14 * wear)
    # ---- dunkle Wasserraender: mehrere Trocknungsstufen je Pfuetze ----
    tide = np.zeros(S, np.float32)
    pud = np.zeros(S, np.float32)
    def win(cx, cy, rad):
        r0, r1 = int((cy - rad) / px), int((cy + rad) / px) + 1
        c0, c1 = int((cx - rad) / px), int((cx + rad) / px) + 1
        ii = np.ix_(np.arange(r0, r1) % n, np.arange(c0, c1) % n)
        yy = ((np.arange(r0, r1) + 0.5) * px - cy).astype(np.float32)[:, None]
        xx = ((np.arange(c0, c1) + 0.5) * px - cx).astype(np.float32)[None, :]
        return ii, xx, yy
    rings = [(0.55, 0.62, 0.42), (2.95, 3.35, 0.30), (3.45, 1.05, 0.52), (1.25, 2.55, 0.22), (2.2, 0.35, 0.16),
             (0.3, 3.4, 0.35), (3.1, 2.3, 0.12), (1.85, 1.6, 0.27)]
    for k, (cx, cy, R0) in enumerate(rings):
        ii, xx, yy = win(cx, cy, R0 * 1.7 + 0.05)
        r = np.hypot(xx, yy)
        th = np.arctan2(yy, xx)
        rr = np.random.default_rng(700 + k)
        wob = sum(rr.uniform(0.05, 0.13) / kk * np.sin(kk * th + rr.uniform(0, 6.3)) for kk in range(2, 9))
        unev = np.clip(0.6 + 0.5 * np.sin(5 * th + rr.uniform(0, 6.3)) + 0.35 * np.sin(11 * th + rr.uniform(0, 6.3)), 0, 1)
        t_acc = np.zeros(r.shape, np.float32)
        for j, (fac, stv) in enumerate(((1.0, 1.0), (rr.uniform(0.72, 0.85), 0.35))):
            d = r - R0 * fac * (1 + wob)
            t_acc = np.maximum(t_acc, np.where(d > 0, sm(0.004, 0.0, d), sm(-0.03, 0.0, d)) * stv)
            if j == 0:
                p_acc = sm(0.0, -0.08, d)
        tide[ii] = np.maximum(tide[ii], t_acc * unev)
        pud[ii] = np.maximum(pud[ii], p_acc)
    alb = mix(alb, hexc("#6d6c52"), 0.14 * pud)
    alb = mix(alb, hexc("#47432f"), 0.5 * tide)
    damp = sm(0.4, 2.0, nz(2.6))
    alb = alb * (1 - 0.16 * damp)[..., None]
    # ---- Gummispuren: Betten (Radpaare 0,8 m), Rollstuehle (Boegen 0,56 m), Schuhe ----
    wide, wv = [], []
    for (p0, a0, L, bend) in (((0.2, 0.9), 0.35, 3.6, 0.12), ((3.6, 0.2), 1.75, 3.2, -0.18), ((1.0, 3.7), -0.2, 2.6, 0.25)):
        mid = curve(p0, a0, L, bend, 70)
        for off in (-0.4, 0.4):
            for dsh in dashes(offset_line(mid, off), rng):
                wide.append(dsh)
                wv.append(rng.uniform(0.18, 0.4))
    for (cx, cy, R, a0, span) in ((2.6, 1.2, 0.9, 0.4, 1.4), (0.9, 2.1, 1.25, 3.5, 1.1)):
        for dr in (0.0, 0.56):
            arc = [(cx + (R + dr) * math.cos(a0 + span * t / 40), cy + (R + dr) * math.sin(a0 + span * t / 40)) for t in range(41)]
            for dsh in dashes(arc, rng, on=(0.2, 0.9), off=(0.03, 0.2)):
                wide.append(dsh)
                wv.append(rng.uniform(0.25, 0.5))
    rub = 0.55 * raster_lines(S, wide, 0.016, vals=wv, rough=0.6, seed=3)
    shoe = [curve((rng.uniform(0, 4), rng.uniform(0, 4)), rng.uniform(0, 6.3), rng.uniform(0.03, 0.1), rng.normal(0, 3.0), 4)
            for _ in range(110)]
    rub = np.maximum(rub, raster_lines(S, shoe, 0.003, vals=rng.uniform(0.2, 0.55, len(shoe)), rough=0.8, seed=4))
    alb = mix(alb, hexc("#1f1f1d"), 0.75 * rub)
    # ---- feine Kratzer ----
    scr_l = []
    for _ in range(2600):
        a = rng.uniform(0, math.pi) if rng.random() < 0.6 else math.pi / 2 + rng.normal(0, 0.25)
        scr_l.append(curve((rng.uniform(0, 4), rng.uniform(0, 4)), a, rng.uniform(0.02, 0.16), rng.normal(0, 2.0), 3))
    scr = raster_lines(S, scr_l, 0.0004, vals=rng.uniform(0.3, 0.8, len(scr_l)), seed=5)
    alb = mix(alb, hexc("#a8ad9e"), 0.28 * scr)
    # ---- Flecken, Brandloecher, Rostring eines Metallstaenders ----
    spots = sm(2.3, 3.0, nz(0.25, sigma_m=0.0025))
    alb = mix(alb, hexc("#3f3a2e"), 0.5 * spots)
    burn = np.zeros(S, np.float32)
    for k in range(6):
        cx, cy = rng.uniform(0, 4, 2)
        ii, xx, yy = win(cx, cy, 0.03)
        r = np.hypot(xx, yy)
        rad = rng.uniform(0.003, 0.007)
        burn[ii] = np.maximum(burn[ii], sm(rad * 2.4, rad, r) * 0.5 + sm(rad, rad * 0.4, r) * 0.5)
    alb = mix(alb, hexc("#3a2a1c"), 0.8 * burn)
    ii, xx, yy = win(1.7, 1.45, 0.16)
    r = np.hypot(xx, yy)
    th = np.arctan2(yy, xx)
    rust = sm(0.004, 0.0, np.abs(r - 0.11)) * sm(-0.3, 0.6, np.sin(3 * th + 1.0) + 0.5 * np.sin(7 * th))
    rring = np.zeros(S, np.float32)
    rring[ii] = rust
    alb = mix(alb, hexc("#6e4a2e"), 0.7 * rring)
    # ---- Schweissschnur und Schmutz an den Naehten ----
    cord = sm(0.0021, 0.0013, dn)
    sdirt = sm(0.025, 0.0025, dn) * (1 - cord) * (0.35 + 0.65 * sm(-1.2, 1.2, nz(1.4, aniso=6.0)))
    alb = mix(alb, hexc("#3f4239"), 0.38 * sdirt)
    alb = mix(alb, hexc("#5e6a5c"), 0.88 * cord)
    ccrack = cord * sm(1.4, 2.1, nz(0.9, aniso=0.15))
    alb = mix(alb, hexc("#22241e"), 0.85 * ccrack)
    # ---- Staubschleier ----
    dust = sm(-0.4, 1.6, nz(2.8))
    alb = mix(alb, hexc("#8d8d85"), 0.10 * dust)
    rough = (0.60 + 0.025 * m + 0.10 * grime + 0.07 * dust + 0.10 * wear + 0.06 * tide - 0.07 * pud - 0.05 * damp
             - 0.14 * cord + 0.04 * rub + 0.12 * scr + 0.05 * spots + 0.1 * burn)
    hgt = 0.00004 * nz(0.8, sigma_m=0.0004) + 0.00002 * f
    hgt -= 0.00012 * sm(0.0029, 0.0022, dn) * sm(0.0012, 0.0019, dn)
    hgt += 0.00002 * tide + 0.000015 * rub - 0.00004 * scr - 0.0001 * ccrack - 0.0002 * burn
    return write_set(f"T_{GEB}_Boden", alb, hgt, np.clip(rough, 0.3, 0.95))

# ======================= Textur "BodenDetail": Atlas =======================
def tex_detail():
    n = NPX
    px = 4.0 / n
    alb = np.zeros((n, n, 3), np.float32)
    hgt = np.zeros((n, n), np.float32)
    rgh = np.full((n, n), 0.8, np.float32)
    sd = [500]
    def nz(S, beta, aniso=1.0, sigma_m=0.0, h=False):
        sd[0] += 1
        return (frh if h else fr)(S, beta, sd[0], aniso, sigma_m)
    rng = np.random.default_rng(41)
    def region(name):
        if name == "zentrum":
            u0, u1, v0, v1 = ZENTRUM
        else:
            v0, v1 = REG[name]
            u0, u1 = U_RECHTS if name in RECHTS else (0.0, 4.0)
        r0, r1 = int(round(v0 * n / 4)), int(round(v1 * n / 4))
        c0, c1 = int(round(u0 * n / 4)), int(round(u1 * n / 4))
        S = (r1 - r0, c1 - c0)
        xs = (np.arange(c0, c1, dtype=np.float32) + 0.5) * px - u0
        zs = (np.arange(r0, r1, dtype=np.float32) + 0.5) * px - v0
        return (slice(r0, r1), slice(c0, c1)), np.broadcast_to(xs[None, :], S), np.broadcast_to(zs[:, None], S), S
    def put(sl, a, h, r):
        alb[sl], hgt[sl], rgh[sl] = a, h, np.clip(r, 0.05, 1.0)

    # ---- Estrich mit altem Bitumenkleber (Zahnspachtel-Rillen) und Jute-Resten ----
    sl, X, Z, S = region("estrich")
    tone = 1 + 0.06 * nz(S, 2.0) + 0.035 * nz(S, 1.1)
    a = hexc("#8a877f") * tone[..., None]
    agg = nz(S, 0.35, sigma_m=0.0007)
    a = mix(a, hexc("#6c6963"), 0.35 * sm(1.4, 2.3, agg))
    a = mix(a, hexc("#a6a39b"), 0.25 * sm(-1.6, -2.4, agg))
    kl = sm(0.0, 0.45, nz(S, 2.3) + 0.5 * nz(S, 1.3))
    lam = 0.0048
    k1, k2 = round(4 * 0.82 / lam), round(4 * -0.35 / lam)          # ganze Zahl Rillen je 4 m: kachelt in U
    g1 = X * (k1 * lam / 4) + Z * 0.57 + 0.04 * nz(S, 2.6)
    g2 = X * (k2 * lam / 4) + Z * 0.94 + 0.04 * nz(S, 2.6)
    rid = 0.5 + 0.5 * np.sin(2 * np.pi * np.where(nz(S, 3.0) > 0, g1, g2) / lam)
    kc = mix(hexc("#1d1c1a"), hexc("#2d2a26"), sm(-1.2, 1.2, nz(S, 1.4)))
    a = mix(a, kc * (0.82 + 0.3 * rid)[..., None], 0.93 * kl)
    P = 4.0 / 1380
    weave = 0.5 + 0.25 * (np.sin(2 * np.pi * X / P) + np.sin(2 * np.pi * Z / P))
    ju = kl * sm(0.7, 1.4, nz(S, 1.9))
    jc = mix(hexc("#4a3f31"), hexc("#6b5b45"), np.clip(0.5 + 0.3 * nz(S, 0.7, aniso=6.0) + 0.3 * (weave - 0.5), 0, 1))
    a = mix(a, jc, 0.9 * ju)
    crl = []
    for _ in range(14):
        x, z = rng.uniform(0, 4), rng.uniform(0.05, 1.55)
        crl.append(curve((x, z), rng.uniform(0, 6.3), rng.uniform(0.2, 0.9), 0.0, 24, rng, 0.35))
    cr = raster_lines(S, crl, 0.0007, wrap=(4.0, None), seed=7)
    a = mix(a, hexc("#2d2b28"), 0.8 * cr * (1 - kl)[...])
    damp = sm(0.3, 1.8, nz(S, 2.4))
    a = a * (1 - 0.18 * damp)[..., None]
    dust = sm(-0.6, 1.4, nz(S, 2.6)) * (1 - 0.6 * kl)
    a = mix(a, hexc("#a3a098"), 0.22 * dust)
    put(sl, a, 0.00012 * agg * (1 - kl) + kl * (0.0003 + 0.00022 * rid) + ju * (0.0003 + 0.0002 * weave) - 0.0006 * cr,
        0.88 - kl * (0.32 + 0.12 * rid) + 0.06 * dust + 0.05 * ju - 0.1 * damp)

    # ---- Aluminium der Schwelle: Laengsschliff, Kratzer, Oxid, Schmutz an den Profilkanten ----
    sl, X, Z, S = region("alu")
    br = nz(S, 1.0, aniso=10.0, h=True)
    a = hexc("#8c9090") * (1 + 0.05 * br + 0.03 * nz(S, 2.0))[..., None]
    ox = sm(1.2, 2.2, nz(S, 0.6, sigma_m=0.002))
    a = mix(a, hexc("#c4c7c2"), 0.45 * ox)
    edge = np.maximum(sm(0.022, 0.012, Z), sm(0.078, 0.088, Z))
    a = mix(a, hexc("#55574f"), 0.5 * edge)
    scl = []
    for _ in range(700):
        ang = rng.normal(0, 0.12) if rng.random() < 0.8 else rng.uniform(0, math.pi)
        scl.append(curve((rng.uniform(0, 4), rng.uniform(0.012, 0.088)), ang, rng.uniform(0.01, 0.25), 0.0, 2))
    sc = raster_lines(S, scl, 0.00045, wrap=(4.0, None), vals=rng.uniform(0.35, 1.0, len(scl)), seed=8)
    a = mix(a, hexc("#d2d5d4"), 0.5 * sc)
    gol = [curve((rng.uniform(0, 4), rng.uniform(0.02, 0.08)), rng.normal(0, 0.08), rng.uniform(0.05, 0.4), 0.0, 3) for _ in range(9)]
    go = raster_lines(S, gol, 0.0011, wrap=(4.0, None), seed=9)
    a = mix(a, hexc("#5a5c59"), 0.55 * go)
    put(sl, a, 0.00002 * br - 0.00005 * sc - 0.00015 * go, 0.4 + 0.18 * edge + 0.15 * ox - 0.08 * sc + 0.1 * go)

    # ---- Schnitt durch die Linoleum-Platte: Beton, Estrich, Kleber, Linoleum (Z 0 = Unterseite, 0,2 = Oberseite) ----
    def beton_schnitt(S, X, Z):
        stone = nz(S, 0.9, sigma_m=0.003)
        conc = hexc("#76736d") * (1 + 0.08 * nz(S, 1.6))[..., None]
        conc = mix(conc, hexc("#8f8b83"), 0.5 * sm(1.0, 1.5, stone))
        conc = mix(conc, hexc("#5d5a55"), 0.45 * sm(-1.0, -1.5, stone))
        pores = sm(2.4, 3.1, nz(S, 0.2, sigma_m=0.0008))
        conc = mix(conc, hexc("#3a3835"), 0.6 * pores)
        scr = hexc("#99968e") * (1 + 0.04 * nz(S, 1.0))[..., None]
        a = np.where((Z > 0.14)[..., None], scr, conc)
        return a, 0.0002 * sm(1.0, 1.5, stone) - 0.0004 * pores + 0.0001 * nz(S, 0.6)
    sl, X, Z, S = region("kante")
    a, h = beton_schnitt(S, X, Z)
    a = np.where((Z > 0.197)[..., None], hexc("#2e2924"), a)
    a = np.where((Z > 0.1975)[..., None], hexc("#6e7a6b"), a)
    a = mix(a, hexc("#4a4740"), 0.25 * sm(0.7, 2.0, nz(S, 2.2)))
    put(sl, a, h, np.where(Z > 0.1975, 0.6, 0.9))

    # ---- Schnitt durch die Fliesen-Platte: Beton, Estrich, Moertelbett, Fliese mit Glasur, Fugen alle 10 cm ----
    sl, X, Z, S = region("kante_fliese")
    a, h = beton_schnitt(S, X, Z)
    a = np.where((Z > 0.18)[..., None], hexc("#8c8981") * (1 + 0.1 * nz(S, 0.7))[..., None], a)
    a = np.where((Z > 0.192)[..., None], hexc("#d6d0c3"), a)
    a = np.where((Z > 0.1995)[..., None], hexc("#e9e7df"), a)
    jt = (pdist(X, 0.0, FL) < FW) & (Z > 0.183)
    a = np.where(jt[..., None], hexc("#3b3a36"), a)
    put(sl, a, h, np.where(Z > 0.1995, 0.32, 0.88))

    # ---- OP-Fliesen 10 x 10 cm: Band mit sechs Reihen und die Mitte der OP-Platte ----
    def kacheln(S, X, Z, ncol, nrow, seed):
        rr = np.random.default_rng(seed)
        col = np.clip(np.floor(X / FL).astype(np.int32), 0, ncol - 1)
        row = np.clip(np.floor(Z / FL).astype(np.int32), 0, nrow - 1)
        tid = row * ncol + col
        nt = ncol * nrow
        tone = rr.normal(0, 1, nt).astype(np.float32)[tid]
        warm = rr.normal(0, 1, nt).astype(np.float32)[tid]
        craz = (rr.random(nt) < 0.3).astype(np.float32)[tid]
        de = np.minimum(pdist(X, 0.0, FL), pdist(Z, 0.0, FL))
        a = hexc("#e2e0d8") * (1 + 0.022 * tone)[..., None]
        a = mix(a, hexc("#e0d7c2"), 0.35 * np.clip(warm, 0, 1))
        ag = sm(-0.5, 1.8, nz(S, 2.0))
        a = mix(a, hexc("#c6c0ad"), 0.38 * ag)
        st = sm(1.6, 2.5, nz(S, 0.8, sigma_m=0.002))
        a = mix(a, hexc("#a39b82"), 0.45 * st)
        cq = sm(0.07, 0.0, np.abs(nz(S, 1.3, sigma_m=0.0006))) * craz
        a = mix(a, hexc("#8e8a7f"), 0.4 * cq)
        ed = sm(0.009, FW, de)
        a = mix(a, hexc("#8b8679"), 0.35 * ed)
        grout = de < FW
        a = np.where(grout[..., None], hexc("#3b3a36") * (1 + 0.12 * nz(S, 0.8))[..., None], a)
        cush = np.clip(1 - (de - FW) / 0.0022, 0, 1)
        h = np.where(grout, -FT, -0.0005 * cush ** 2) - 0.00002 * cq + 0.00003 * nz(S, 0.7, sigma_m=0.0003)
        r = np.where(grout, 0.88, 0.3 + 0.22 * ag + 0.2 * st + 0.25 * ed + 0.1 * cq)   # Glasur unter Schmutzfilm
        return a, h, r, grout
    sl, X, Z, S = region("fliesen")
    a, h, r, _ = kacheln(S, X, Z, 40, 6, 61)
    put(sl, a, h, r)
    sl, X, Z, S = region("zentrum")
    a, h, r, grout = kacheln(S, X, Z, 12, 12, 62)
    x, y = X - ZR, Z - ZR
    rad = np.hypot(x, y)
    th = np.arctan2(y, x)
    fl = (rad >= ABL_R[1]) & (rad <= ABL_R[3])
    circ = 0.5 + 0.5 * np.sin(2 * np.pi * rad / 0.0011 + 2.0 * nz(S, 1.4))
    a = np.where(fl[..., None], hexc("#a6a8a6") * (0.9 + 0.14 * circ)[..., None], a)
    gr = rad < ABL_R[1]
    a = np.where(gr[..., None], hexc("#8a8c89") * (0.9 + 0.1 * circ)[..., None], a)
    Rr = 0.36 + 0.08 * np.sin(2 * th + 1.0) + 0.05 * np.sin(3 * th + 2.1) + 0.03 * np.sin(5 * th + 0.4)
    Rr = Rr * (1 + 0.25 * nz(S, 2.2))
    streak = 0.6 + 0.4 * sm(-1.0, 1.0, nz(S, 1.5) + 0.5 * np.sin(9 * th + 2 * np.sin(4 * th)))
    rust = sm(Rr, Rr * 0.3, rad) * streak * sm(-1.5, 0.5, nz(S, 1.9))
    rust = np.where(grout, np.minimum(1.0, rust * 1.5), rust)
    near = sm(0.26, ABL_R[3], rad)
    a = mix(a, hexc("#7b4a29"), 0.62 * rust)
    a = mix(a, hexc("#4f2f1b"), 0.45 * near * rust)
    a = mix(a, hexc("#5a3a22"), 0.15 * sm(0.012, 0.0, np.abs(rad - Rr)) * sm(-0.5, 1.0, nz(S, 1.2)))
    lime = sm(0.2, ABL_R[3], rad) * (rad > ABL_R[3]) * sm(-0.3, 1.0, nz(S, 1.0))
    a = mix(a, hexc("#d3cec0"), 0.3 * lime)
    rs = sm(1.2, 2.2, nz(S, 0.5, sigma_m=0.001)) * (rad < ABL_R[3])
    a = mix(a, hexc("#6e3f22"), 0.6 * rs)
    r = np.where(fl | gr, 0.3 + 0.25 * rust + 0.3 * rs, r + 0.15 * rust)
    h = np.where(fl | gr, 0.00002 * circ, h) + 0.00002 * rs
    put(sl, a, h, r)

    # ---- Flanken der Fliesen in den Fugen (Glasur oben, Fugenschmutz unten), Fugengrund, Edelstahl ----
    sl, X, Z, S = region("fliesenkante")
    t = np.clip((Z - 0.004) / FT, 0, 1)
    a = mix(hexc("#4e4c47"), hexc("#dcd9d0"), sm(0.2, 0.9, t)) * (1 + 0.05 * nz(S, 0.8))[..., None]
    put(sl, a, 0.00002 * nz(S, 0.6), 0.85 - 0.55 * sm(0.2, 0.9, t))
    sl, X, Z, S = region("fuge")
    a = hexc("#3a3935") * (1 + 0.15 * nz(S, 0.6))[..., None]
    a = mix(a, hexc("#6c685f"), 0.3 * sm(1.0, 2.0, nz(S, 0.4, sigma_m=0.0005)))
    put(sl, a, 0.00004 * nz(S, 0.5), np.full(S, 0.9, np.float32))
    sl, X, Z, S = region("edelstahl")
    br = nz(S, 1.0, aniso=10.0, h=True)
    a = hexc("#a2a5a4") * (1 + 0.05 * br)[..., None]
    sludge = sm(0.035, 0.008, Z) * 0.8
    a = mix(a, hexc("#3f3a33"), sludge)
    rs = sm(1.5, 2.4, nz(S, 0.5, sigma_m=0.001))
    a = mix(a, hexc("#7a4a29"), 0.6 * rs)
    put(sl, a, 0.00002 * br, 0.33 + 0.4 * sludge + 0.3 * rs)

    # ---- Jute-Ruecken des Linoleums (Unterseite der Rolle und der angehobenen Raender) ----
    sl, X, Z, S = region("ruecken")
    P = 4.0 / 1380
    ph1 = 2 * np.pi * X / P + 1.2 * nz(S, 2.4)
    ph2 = 2 * np.pi * Z / P + 1.2 * nz(S, 2.4)
    cell = (np.floor(X / P) + np.floor(Z / P)) % 2
    w = np.where(cell > 0, 0.5 + 0.5 * np.cos(ph2), 0.5 + 0.5 * np.cos(ph1))
    fib = nz(S, 0.7, aniso=5.0)
    a = mix(hexc("#5b4a33"), hexc("#86704f"), np.clip(0.45 + 0.35 * w + 0.15 * fib, 0, 1))
    glue = sm(0.2, 1.2, nz(S, 2.0))
    a = mix(a, hexc("#2f2822"), 0.6 * glue)
    a = mix(a, hexc("#59624f"), 0.25 * sm(1.0, 2.0, nz(S, 1.8)))
    put(sl, a, 0.00025 * w + 0.00005 * fib + 0.0001 * glue, 0.9 - 0.25 * glue)

    # ---- Schnitt durch das Linoleum: Kleberrest, Jute, Linoleum (Z 0,004 .. 0,007) ----
    sl, X, Z, S = region("lino_schnitt")
    a = hexc("#66715f") * (1 + 0.06 * nz(S, 0.6))[..., None]
    a = mix(a, hexc("#8a9483"), 0.3 * sm(1.5, 2.5, nz(S, 0.3, sigma_m=0.0003)))
    a = np.where(((Z >= 0.0045) & (Z < 0.0053))[..., None], hexc("#6f5b3f"), a)
    a = np.where((Z < 0.0045)[..., None], hexc("#2e2924"), a)
    put(sl, a, 0.00002 * nz(S, 0.5), np.where(Z < 0.0045, 0.6, 0.8))

    # ---- Schleifspur: abgeriebenes Linoleum mit Gummiabrieb und Laengskratzern (Mitte bei Z 0,03) ----
    sl, X, Z, S = region("schleif")
    a = hexc("#5f6a5b") * (1 + 0.06 * nz(S, 1.0, aniso=8.0, h=True))[..., None]
    rub = sm(-0.2, 1.2, nz(S, 1.2, aniso=12.0, h=True)) * sm(0.012, 0.0, np.abs(Z - 0.03))
    a = mix(a, hexc("#1d1d1b"), 0.65 * rub)
    scl = [curve((rng.uniform(0, 2.8), rng.uniform(0.024, 0.036)), rng.normal(0, 0.02), rng.uniform(0.05, 0.6), 0.0, 3)
           for _ in range(160)]
    sc = raster_lines(S, scl, 0.0003, wrap=(None, None), vals=rng.uniform(0.3, 0.8, 160), seed=10)
    a = mix(a, hexc("#9aa192"), 0.4 * sc)
    put(sl, a, -0.00004 * sc + 0.00003 * nz(S, 0.7, aniso=8.0, h=True), 0.7 - 0.2 * rub + 0.1 * sc)

    # ---- Betonbrocken ----
    sl, X, Z, S = region("beton")
    agg = nz(S, 0.8, sigma_m=0.0015)
    a = hexc("#85827b") * (1 + 0.07 * nz(S, 1.5))[..., None]
    a = mix(a, hexc("#9b978e"), 0.5 * sm(0.8, 1.4, agg))
    a = mix(a, hexc("#5e5b55"), 0.45 * sm(-0.8, -1.4, agg))
    a = mix(a, hexc("#d8d4c8"), 0.6 * sm(1.0, 1.6, nz(S, 2.2)))
    pores = sm(2.4, 3.1, nz(S, 0.2, sigma_m=0.0008))
    a = mix(a, hexc("#3a3835"), 0.55 * pores)
    put(sl, a, 0.0004 * nz(S, 0.6) + 0.0002 * agg - 0.0003 * pores, np.full(S, 0.92, np.float32))

    # ---- Glasscherben (undurchsichtig: dunkel, glatt, staubig) ----
    sl, X, Z, S = region("glas")
    a = hexc("#2a332f") * (1 + 0.08 * nz(S, 1.5))[..., None]
    dust = sm(-0.2, 1.6, nz(S, 1.8))
    a = mix(a, hexc("#8b8a83"), 0.35 * dust)
    a = mix(a, hexc("#3d5a4e"), 0.3 * sm(0.0, 0.01, Z) * sm(0.08, 0.07, Z))
    put(sl, a, 0.00001 * nz(S, 0.4), 0.26 + 0.45 * dust)          # verstaubt, nie spiegelnd

    # ---- drei Papierblaetter (A4, quer im Bereich): vergilbt, Formular, Flecken, Knicke ----
    sl, X, Z, S = region("papier")
    a = np.empty(S + (3,), np.float32)
    a[...] = hexc("#3a3833")
    h = np.zeros(S, np.float32)
    r = np.full(S, 0.85, np.float32)
    for k, x0 in enumerate((0.05, 0.40, 0.75, 1.10)):          # k = 3: unbedruckte Rueckseite
        sx, sz = X - x0, Z - 0.005
        msk = (sx >= 0) & (sx < 0.297) & (sz >= 0) & (sz < 0.21)
        paper = hexc("#bdb398") * (1 + 0.05 * nz(S, 1.5))[..., None]
        paper = mix(paper, hexc("#a8976d"), 0.45 * sm(-0.3, 1.5, nz(S, 2.2)))
        paper = mix(paper, hexc("#6d6553"), 0.35 * sm(0.2, 1.8, nz(S, 1.6)))
        inside = (sx > 0.02) & (sx < 0.277)
        ink = ((sz > 0.178) & (sz < 0.193) & inside) * 0.85
        tab = np.zeros(S, bool)
        for zz in np.arange(0.03, 0.171, 0.0125):
            tab |= (np.abs(sz - zz) < 0.00035) & inside
        for xx in (0.02, 0.1, 0.2, 0.277):
            tab |= (np.abs(sx - xx) < 0.00035) & (sz > 0.03) & (sz < 0.17)
        ink = np.maximum(ink, tab * 0.6)
        txt = np.zeros(S, np.float32)
        for zz in np.arange(0.036, 0.166, 0.0125):
            row = (np.abs(sz - zz) < 0.0012) & (np.sin(2 * np.pi * sx / 0.0035 + 3 * k) > 0.1)
            row &= np.sin(2 * np.pi * sx / 0.031 + 7 * zz + k) > -0.55
            row &= ((sx > 0.025) & (sx < 0.095)) | ((sx > 0.105) & (sx < 0.13 + 0.06 * ((zz * 77 + k) % 1)))
            txt = np.maximum(txt, row * 0.75)
        ink = np.maximum(ink, txt) * (k < 3)
        p = mix(paper, hexc("#2b2f3a"), ink)
        cx, cy = x0 + 0.06 + 0.17 * ((k * 0.37) % 1), 0.04 + 0.1 * ((k * 0.61) % 1)
        rr_ = np.hypot(X - cx, Z - cy)
        p = mix(p, hexc("#7b5a36"), 0.5 * sm(0.0035, 0.0, np.abs(rr_ - 0.038)))
        stain = sm(0.4, 1.6, nz(S, 2.0))
        p = mix(p, hexc("#9c8659"), 0.35 * stain)
        fold = sm(0.0015, 0.0, np.abs((sx - 0.148) * 0.8 + (sz - 0.105) * 0.6 * (1 if k % 2 else -1)))
        a = np.where(msk[..., None], p, a)
        h = np.where(msk, -0.00025 * fold + 0.00006 * nz(S, 1.4), h)
    put(sl, a, h, r)
    return write_set(f"T_{GEB}_BodenDetail", alb, hgt, rgh)

# ======================= Materialien =======================
def make_material(name, imgs):
    """Principled BSDF: nur Grundfarbe, Normale und Rauheit (Gruenkanal) angeschlossen. Kein Metallic."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tb, tr, tn = (nt.nodes.new("ShaderNodeTexImage") for _ in range(3))
    tb.image, tr.image, tn.image = imgs["base"], imgs["rough"], imgs["normal"]
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tb.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tr.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Metallic"].default_value = 0.0
    m.use_backface_culling = True                 # einseitig (glTF: doubleSided = false)
    return m

log("Texturen ...")
IMG_B = tex_boden()
IMG_D = tex_detail()
MAT_BODEN = make_material(f"M_{GEB}_Boden", IMG_B)
MAT_DETAIL = make_material(f"M_{GEB}_BodenDetail", IMG_D)

# ======================= Geometrie: Werkzeuge =======================
MB, MD = 0, 1                  # Materialindex: Boden, BodenDetail

def glatt(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)

def randblende(x, y):
    """1 im Inneren, 0 in den aeussersten 5 cm, dazwischen ein weicher Uebergang ueber 20 cm."""
    m = max(abs(x), abs(y))
    return 1.0 if m <= INNEN - 0.2 else glatt((INNEN - m) / 0.2)

class Piece:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.rng = random.Random(zlib.crc32(name.encode()))

    def face(self, vs, mat, uvs, smooth=False, want=None):
        vs = [v if isinstance(v, bmesh.types.BMVert) else self.bm.verts.new(v) for v in vs]
        f = self.bm.faces.new(vs)
        f.material_index = mat
        f.smooth = smooth
        for l, uv in zip(f.loops, uvs):
            l[self.uv].uv = uv
        if want is not None:
            f.normal_update()
            if f.normal.dot(Vector(want)) < 0:
                f.normal_flip()
        return f

def uv_welt(x, y):
    return ((x + P2) * UVS, (y + P2) * UVS)

def reg_uv(reg, u_m, v_m):
    return (u_m * UVS, (REG[reg][0] + v_m) * UVS)

def u_anfang(pc, reg, length):
    if reg in RECHTS:
        room = U_RECHTS[1] - U_RECHTS[0] - length - 0.01
        if room < 0:
            raise RuntimeError(f"{pc.name}: Insel {length:.3f} m zu lang fuer Bereich {reg}")
        return U_RECHTS[0] + 0.005 + pc.rng.random() * room
    return pc.rng.random() * 4.0

def flach_uvs(pc, pts, reg, e1=None, v_rand=True):
    """Ebene Flaeche planar abwickeln und in einen Bereich des Atlas legen (1024 px/m)."""
    nrm = Vector((0.0, 0.0, 0.0))
    for a, b in zip(pts, pts[1:] + pts[:1]):
        nrm += a.cross(b)
    nrm = nrm.normalized() if nrm.length > 1e-12 else Vector((0, 0, 1))
    cands = ([Vector(e1)] if e1 is not None else []) + [Vector((0, 0, 1)).cross(nrm), Vector((1, 0, 0)), Vector((0, 1, 0))]
    for c in cands:
        e = c - nrm * c.dot(nrm)
        if e.length > 1e-3:
            break
    e.normalize()
    e2 = nrm.cross(e)
    co = [(p.dot(e), p.dot(e2)) for p in pts]
    h = REG[reg][1] - REG[reg][0]
    if max(c[1] for c in co) - min(c[1] for c in co) > h - 0.004:
        co = [(c[1], -c[0]) for c in co]
    u0, v0 = min(c[0] for c in co), min(c[1] for c in co)
    lu, lv = max(c[0] for c in co) - u0, max(c[1] for c in co) - v0
    if lv > h - 0.004:
        raise RuntimeError(f"{pc.name}: Flaeche {lv:.3f} m zu gross fuer Bereich {reg}")
    ua = u_anfang(pc, reg, lu)
    room = h - 0.004 - lv
    va = 0.002 + (pc.rng.random() * room if v_rand else room / 2)
    return [((ua + c[0] - u0) * UVS, (REG[reg][0] + va + c[1] - v0) * UVS) for c in co]

def plan_uvs(pc, verts, reg, achse):
    """UVs fuer fast waagerechte Streifen (Unterseiten): Draufsicht, U entlang achse (x, y). Liefert {Vertex: UV}."""
    ax = Vector((achse[0], achse[1])).normalized()
    co = {v: (v.co.x * ax.x + v.co.y * ax.y, -v.co.x * ax.y + v.co.y * ax.x) for v in verts}
    u0, v0 = min(c[0] for c in co.values()), min(c[1] for c in co.values())
    lu, lv = max(c[0] for c in co.values()) - u0, max(c[1] for c in co.values()) - v0
    h = REG[reg][1] - REG[reg][0]
    if lv > h - 0.004:
        raise RuntimeError(f"{pc.name}: Streifen {lv:.3f} m zu breit fuer Bereich {reg}")
    ua = u_anfang(pc, reg, lu)
    va = 0.002 + pc.rng.random() * (h - 0.004 - lv)
    return {v: ((ua + c[0] - u0) * UVS, (REG[reg][0] + va + c[1] - v0) * UVS) for v, c in co.items()}

def flach(pc, pts, reg, want, mat=MD, e1=None, v_rand=True, smooth=False):
    return pc.face(pts, mat, flach_uvs(pc, pts, reg, e1, v_rand), smooth=smooth, want=want)

def point_in(poly, x, y):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside

def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)

def poly_dist(poly, x, y):
    return min(seg_dist(x, y, *poly[i], *poly[(i + 1) % len(poly)]) for i in range(len(poly)))

def loop_area(loop):
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(loop, loop[1:] + loop[:1]))

def bbox(poly, m=0.0):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return (min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m)

def resample(path, step):
    """Linienzug gleichmaessig neu abtasten; liefert Punkte und Bogenlaengen."""
    seg = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:])]
    S = sum(seg)
    n = max(2, int(round(S / step)))
    out, ss = [], []
    for k in range(n + 1):
        s = S * k / n
        acc = 0.0
        for (a, b), L in zip(zip(path, path[1:]), seg):
            if acc + L >= s - 1e-12 or (a, b) == (path[-2], path[-1]):
                t = 0.0 if L < 1e-12 else min(1.0, (s - acc) / L)
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
                break
            acc += L
        ss.append(s)
    return out, ss, S

def tangents(pts):
    out = []
    for i in range(len(pts)):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        L = math.hypot(tx, ty) or 1.0
        out.append((tx / L, ty / L))
    return out

def welle_fn(seed, amp=0.0008):
    """Leichte Welligkeit des alten Estrichs (das Linoleum liegt darauf), am Rand auf 0."""
    off = Vector((seed * 3.1, seed * 1.7, seed * 0.9))
    def h(x, y):
        f = randblende(x, y)
        if f == 0.0:
            return 0.0
        return f * amp * (noise.noise(Vector((x * 0.8, y * 0.8, 0.0)) + off) + 0.4 * noise.noise(Vector((x * 2.1, y * 2.1, 0.5)) + off))
    return h

# ---------- Oberseite des Linoleums ----------
class Flaeche:
    """CDT der Oberseite: Punkte mit Zusatzhoehe, Zwangskanten, Loecher und Schleifrillen. Die aeusseren 5 cm
    bleiben durch eine Zwangskante bei +-1,95 m exakt flach auf Z = 0."""
    def __init__(self, welle):
        self.P, self.dz, self.tag = [], [], []
        self.E = []
        self.holes = []
        self.rillen = []
        self.sperr = []
        self.welle = welle

    def pt(self, x, y, dz=0.0, tag=None):
        self.P.append((x, y))
        self.dz.append(dz)
        self.tag.append(tag)
        return len(self.P) - 1

    def line(self, idx, closed=False):
        seq = list(idx) + ([idx[0]] if closed else [])
        for a, b in zip(seq, seq[1:]):
            if a != b:
                self.E.append((a, b))

    def z(self, x, y, dz=0.0):
        if max(abs(x), abs(y)) >= INNEN - 1e-9:
            return 0.0
        return self.welle(x, y) + dz * randblende(x, y)

    def gesperrt(self, x, y, extra=0.0):
        for poly, rand in self.sperr:
            bb = bbox(poly, rand + extra)
            if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]:
                if point_in(poly, x, y) or poly_dist(poly, x, y) < rand + extra:
                    return True
        return False

    def gitter(self, step=0.3, abstand=0.07):
        cell = {}
        for (x, y) in self.P:
            cell.setdefault((math.floor(x / abstand), math.floor(y / abstand)), []).append((x, y))
        hp = [[self.P[k] for k in h] for h in self.holes]
        lo = -INNEN + 0.1
        k = int(round(-2 * lo / step))
        for i in range(k + 1):
            for j in range(k + 1):
                x, y = lo - 2 * lo * i / k, lo - 2 * lo * j / k
                cx, cy = math.floor(x / abstand), math.floor(y / abstand)
                if any(math.hypot(px - x, py - y) < abstand for di in (-1, 0, 1) for dj in (-1, 0, 1)
                       for (px, py) in cell.get((cx + di, cy + dj), ())):
                    continue
                if self.gesperrt(x, y) or any(point_in(h, x, y) for h in hp):
                    continue
                self.pt(x, y)

    def bauen(self, pc):
        o = [self.pt(-P2, -P2), self.pt(P2, -P2), self.pt(P2, P2), self.pt(-P2, P2)]
        i = [self.pt(-INNEN, -INNEN), self.pt(INNEN, -INNEN), self.pt(INNEN, INNEN), self.pt(-INNEN, INNEN)]
        self.line(o, True)
        self.line(i, True)
        for h in self.holes:
            self.line(h, True)
        co, _, tris, orig_v, _, _ = geometry.delaunay_2d_cdt([Vector(p) for p in self.P], self.E, [], 0, 1e-9)
        neu = sum(1 for ov in orig_v if not ov)
        if neu:
            log("  Hinweis:", pc.name, neu, "Schnittpunkte von Zwangskanten in der Oberflaeche:",
                [tuple(round(v, 3) for v in co[k]) for k, ov in enumerate(orig_v) if not ov])
        holes2 = [(hh, bbox(hh)) for hh in ([self.P[k] for k in h] for h in self.holes)]
        rillen2 = [(poly, u0, bbox(poly)) for poly, u0 in self.rillen]
        bv, tg = [], []
        for k, c in enumerate(co):
            i0 = orig_v[k][0] if orig_v[k] else None
            bv.append(pc.bm.verts.new((c.x, c.y, self.z(c.x, c.y, self.dz[i0] if i0 is not None else 0.0))))
            tg.append(self.tag[i0] if i0 is not None else None)
        for (a, b, c) in tris:
            pa, pb, pcc = co[a], co[b], co[c]
            cr = (pb - pa).cross(pcc - pa)
            if abs(cr) < 1e-11:
                continue
            if cr < 0:
                b, c = c, b
            mx, my = (pa.x + pb.x + pcc.x) / 3, (pa.y + pb.y + pcc.y) / 3
            if any(bb[0] <= mx <= bb[2] and bb[1] <= my <= bb[3] and point_in(hh, mx, my) for hh, bb in holes2):
                continue
            ril = next((r for r in rillen2 if r[2][0] <= mx <= r[2][2] and r[2][1] <= my <= r[2][3] and point_in(r[0], mx, my)), None)
            if ril is None:
                pc.face([bv[a], bv[b], bv[c]], MB, [uv_welt(co[v].x, co[v].y) for v in (a, b, c)], smooth=True)
            else:
                uvs = []
                for v in (a, b, c):
                    t = tg[v] or ("rille", 0.0, 0.0)
                    uvs.append(reg_uv("schleif", ril[1] + t[1], 0.03 + t[2]))
                pc.face([bv[a], bv[b], bv[c]], MD, uvs, smooth=True)

# ---------- Naht, Riss, Schleifrille, Blase ----------
def naht(F, xs, amax, seed, bursts=()):
    """Verschweisste Naht bei x = xs: Wulst (aufgewoelbt), auf den Abschnitten bursts (y0, y1, Spaltbreite, Anhebung)
    aufgeplatzt. Liefert die aufgeplatzten Abschnitte fuer Bruchkanten, Unterseiten und Estrich."""
    off = seed * 7.3
    def amp(y):
        n1 = noise.noise(Vector((y * 1.3 + off, 0.5, off)))
        n2 = noise.noise(Vector((y * 3.7 + off, 1.5, off)))
        return amax * min(1.0, max(0.0, 0.55 + 0.9 * n1 + 0.3 * n2))
    ys = [-INNEN + 0.1 * k for k in range(39)] + [INNEN]
    for (y0, y1, g, L) in bursts:
        ys = [y for y in ys if not (y0 - 0.02 < y < y1 + 0.02)]
        m = max(2, int(round((y1 - y0) / 0.04)))
        ys += [y0 + (y1 - y0) * k / m for k in range(m + 1)]
    ys = sorted(ys)
    cols = {(sd, j): [[]] for sd in (1, -1) for j in range(len(NAHT_E))}
    proben = [[] for _ in bursts]
    for y in ys:
        if F.gesperrt(xs, y, 0.05):
            for key in cols:
                if cols[key][-1]:
                    cols[key].append([])
            continue
        a = amp(y)
        bi = next((b for b, bb in enumerate(bursts) if bb[0] - 1e-9 <= y <= bb[1] + 1e-9), None)
        g = L = 0.0
        if bi is not None:
            y0, y1, gmax, lmax = bursts[bi]
            t = (y - y0) / (y1 - y0)
            if 1e-6 < t < 1 - 1e-6:
                sn = math.sin(math.pi * t)
                g, L = gmax / 2 * sn ** 0.6, lmax * sn ** 0.8
        pr = {"P": (xs, y), "N": (-1.0, 0.0), "g": g, "cols": {}, "edge": {}}
        for sd in (1, -1):
            for j, (e, pf) in enumerate(zip(NAHT_E, NAHT_P)):
                dz = a * pf + L * math.exp(-e / 0.02)
                x = xs - sd * (g + e)
                cols[(sd, j)][-1].append(F.pt(x, y, dz))
                pr["cols"][(sd, j)] = (x, y, dz)
            if g > 0:
                ge = a * NAHT_P[0] + L
                pr["edge"][sd] = (F.pt(xs - sd * g, y, ge), xs - sd * g, y, ge)
        if bi is not None:
            proben[bi].append(pr)
    for segs in cols.values():
        for seg in segs:
            if len(seg) > 1:
                F.line(seg)
    runs = []
    for prs in proben:
        if len(prs) < 3:
            continue
        (x0, y0), (x1, y1) = prs[0]["P"], prs[-1]["P"]
        d0, d1 = amp(y0) * NAHT_P[0], amp(y1) * NAHT_P[0]
        e0, e1 = F.pt(x0, y0, d0), F.pt(x1, y1, d1)
        right = [pr["edge"][-1][0] for pr in prs if -1 in pr["edge"]]
        left = [pr["edge"][1][0] for pr in prs if 1 in pr["edge"]]
        F.holes.append([e0] + right + [e1] + left[::-1])
        runs.append({"proben": prs, "ende": ((x0, y0, d0), (x1, y1, d1)), "E": NAHT_E})
    return runs

def riss(F, pfad, gmax, lmax, E=(0.002, 0.007, 0.02)):
    """Kurzer Riss im Linoleum: Spalt bis gmax breit, die Raender bis lmax angehoben."""
    pts, ss, S = resample(pfad, 0.02)
    tg = tangents(pts)
    prs = []
    cols = {(sd, j): [] for sd in (1, -1) for j in range(len(E))}
    for k, ((x, y), (tx, ty), s) in enumerate(zip(pts, tg, ss)):
        N = (-ty, tx)
        sn = math.sin(math.pi * s / S)
        g, L = (gmax / 2 * sn ** 0.6, lmax * sn ** 0.8) if 0 < k < len(pts) - 1 else (0.0, 0.0)
        pr = {"P": (x, y), "N": N, "g": g, "cols": {}, "edge": {}}
        for sd in (1, -1):
            for j, e in enumerate(E):
                px, py = x + sd * N[0] * (g + e), y + sd * N[1] * (g + e)
                dz = L * math.exp(-e / 0.008)
                cols[(sd, j)].append(F.pt(px, py, dz))
                pr["cols"][(sd, j)] = (px, py, dz)
            if g > 0:
                px, py = x + sd * N[0] * g, y + sd * N[1] * g
                pr["edge"][sd] = (F.pt(px, py, L), px, py, L)
        prs.append(pr)
    for seg in cols.values():
        F.line(seg)
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    e0, e1 = F.pt(x0, y0, 0.0), F.pt(x1, y1, 0.0)
    right = [pr["edge"][-1][0] for pr in prs if -1 in pr["edge"]]
    left = [pr["edge"][1][0] for pr in prs if 1 in pr["edge"]]
    poly = [e0] + right + [e1] + left[::-1]
    if loop_area([F.P[k] for k in poly]) < 0:
        poly = poly[::-1]
    F.holes.append(poly)
    return {"proben": prs, "ende": ((x0, y0, 0.0), (x1, y1, 0.0)), "E": E}

def riss_extras(pc, F, run):
    """Bruchkanten (3 mm) beidseitig, Jute-Unterseite der angehobenen Raender, Estrich mit Kleber im Spalt."""
    prs, E = run["proben"], run["E"]
    (x0, y0, d0), (x1, y1, d1) = run["ende"]
    J = len(E)
    ss = [0.0]
    for a, b in zip(prs, prs[1:]):
        ss.append(ss[-1] + math.hypot(b["P"][0] - a["P"][0], b["P"][1] - a["P"][1]))
    for sd in (1, -1):
        # Bruchkante
        kette = [(x0, y0, d0)] + [pr["edge"][sd][1:] for pr in prs if sd in pr["edge"]] + [(x1, y1, d1)]
        tops = [Vector((x, y, F.z(x, y, d))) for (x, y, d) in kette]
        total = sum((b - a).length for a, b in zip(tops, tops[1:]))
        u0 = u_anfang(pc, "lino_schnitt", total + 0.01)
        s = 0.0
        for a, b in zip(tops, tops[1:]):
            L = (b - a).length
            mid = (a + b) / 2
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            nrm = (prs[0]["N"][0] * -sd, prs[0]["N"][1] * -sd, 0.0)
            pc.face([a, b, b - Vector((0, 0, KT)), a - Vector((0, 0, KT))], MD,
                    [reg_uv("lino_schnitt", u0 + s, 0.004 + KT), reg_uv("lino_schnitt", u0 + s + L, 0.004 + KT),
                     reg_uv("lino_schnitt", u0 + s + L, 0.004), reg_uv("lino_schnitt", u0 + s, 0.004)], want=nrm)
            s += L
        # Unterseite der angehobenen Raender: Reihen je Probe (Kante, dann die Spalten), Draufsicht-UV
        rows = []
        for k, pr in enumerate(prs):
            if sd in pr["edge"]:
                first = pr["edge"][sd][1:]
            else:
                first = (pr["P"][0], pr["P"][1], d0 if k == 0 else d1)
            row = [first] + [pr["cols"][(sd, j)] for j in range(J)]
            rows.append([pc.bm.verts.new((p[0], p[1], F.z(p[0], p[1], p[2]) - KT)) for p in row])
        uvm = plan_uvs(pc, [v for r in rows for v in r], "ruecken", (x1 - x0, y1 - y0))
        for k in range(len(rows) - 1):
            for j in range(J):
                q = [rows[k][j], rows[k][j + 1], rows[k + 1][j + 1], rows[k + 1][j]]
                pc.face(q, MD, [uvm[v] for v in q], smooth=True, want=(0, 0, -1))
    # Estrich im Spalt und unter den angehobenen Raendern
    ymin = min(min(pr["cols"][(1, J - 1)][1], pr["cols"][(-1, J - 1)][1]) for pr in prs) - 0.005
    def fl(p):
        return Vector((p[0], p[1], EZ + F.welle(p[0], p[1])))
    for a, b in zip(prs, prs[1:]):
        q = [fl(a["cols"][(1, J - 1)]), fl(b["cols"][(1, J - 1)]), fl(b["cols"][(-1, J - 1)]), fl(a["cols"][(-1, J - 1)])]
        pc.face(q, MD, [reg_uv("estrich", p.x + P2, 0.01 + p.y - ymin) for p in q], want=(0, 0, 1))

def schleifrille(F, pc, pfad, wmax, tiefe):
    """Lange flache Schleifspur (Bett mit blockiertem Rad): Rinne mit sanften Flanken, Boden im Atlas 'schleif'."""
    pts, ss, S = resample(pfad, 0.03)
    tg = tangents(pts)
    u0 = u_anfang(pc, "schleif", S + 0.02)
    lines = {t: [] for t in range(5)}
    for k, ((x, y), (tx, ty), s) in enumerate(zip(pts, tg, ss)):
        N = (-ty, tx)
        w = wmax * min(1.0, s / 0.12, (S - s) / 0.12) ** 0.7
        if k in (0, len(pts) - 1) or w < 1e-4:
            idx = F.pt(x, y, 0.0, ("rille", s, 0.0))
            for t in lines:
                lines[t].append(idx)
            continue
        for t, (o, f) in enumerate(((0.5, 0.0), (0.25, 0.7), (0.0, 1.0), (-0.25, 0.7), (-0.5, 0.0))):
            lines[t].append(F.pt(x + N[0] * o * w, y + N[1] * o * w, -tiefe * f * w / wmax, ("rille", s, o * w)))
    poly = lines[4] + lines[0][::-1][1:-1]
    for t in lines:
        F.line(lines[t])
    F.line(poly, True)
    F.rillen.append(([F.P[k] for k in poly], u0))

def blase(F, cx, cy, R, H):
    """Luftblase unter dem Linoleum."""
    F.pt(cx, cy, H)
    for r, n in ((0.4 * R, 8), (0.75 * R, 12), (R, 14)):
        for k in range(n):
            a = 2 * math.pi * (k + 0.5 * (n == 12)) / n
            F.pt(cx + r * math.cos(a), cy + r * math.sin(a), H * (1 - (r / R) ** 2) ** 2)

# ---------- Koerper ----------
def koerper(pc, x2=P2, y2=P2, kante="kante", unten=MD):
    """Seitenflaechen bis Z = -DICKE (Schnitt durch den Aufbau) und Unterseite."""
    v0 = REG[kante][0]
    for (ax, ay), (bx, by), nrm in (((-x2, -y2), (x2, -y2), (0, -1, 0)), ((x2, -y2), (x2, y2), (1, 0, 0)),
                                    ((x2, y2), (-x2, y2), (0, 1, 0)), ((-x2, y2), (-x2, -y2), (-1, 0, 0))):
        pts = [Vector((ax, ay, 0.0)), Vector((bx, by, 0.0)), Vector((bx, by, -DICKE)), Vector((ax, ay, -DICKE))]
        uvs = [(((p.x if nrm[1] else p.y) + P2) * UVS, (v0 + p.z + DICKE) * UVS) for p in pts]
        pc.face(pts, MD, uvs, want=nrm)
    if unten == MB:
        pts = [Vector((-x2, -y2, -DICKE)), Vector((x2, -y2, -DICKE)), Vector((x2, y2, -DICKE)), Vector((-x2, y2, -DICKE))]
        pc.face(pts, MB, [uv_welt(p.x, p.y) for p in pts], want=(0, 0, -1))
        return
    n = max(1, math.ceil(2 * y2 / 1.55))
    for k in range(n):
        ya, yb = -y2 + 2 * y2 * k / n, -y2 + 2 * y2 * (k + 1) / n
        pts = [Vector((-x2, ya, -DICKE)), Vector((x2, ya, -DICKE)), Vector((x2, yb, -DICKE)), Vector((-x2, yb, -DICKE))]
        pc.face(pts, MD, [reg_uv("estrich", p.x + P2, 0.01 + p.y - ya) for p in pts], want=(0, 0, -1))

# ---------- Schutt ----------
IKO_V = [(-1, 1.618, 0), (1, 1.618, 0), (-1, -1.618, 0), (1, -1.618, 0), (0, -1, 1.618), (0, 1, 1.618), (0, -1, -1.618),
         (0, 1, -1.618), (1.618, 0, -1), (1.618, 0, 1), (-1.618, 0, -1), (-1.618, 0, 1)]
IKO_F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]

def brocken(pc, x, y, zb, size, seed):
    """Betonbrocken: verformtes Ikosaeder, flach liegend, leicht eingesunken."""
    rng = random.Random(seed)
    sc = Vector((size, size * rng.uniform(0.7, 1.0), size * rng.uniform(0.45, 0.7)))
    rot = Matrix.Rotation(rng.uniform(0, math.tau), 3, "Z") @ Matrix.Rotation(rng.uniform(-0.3, 0.3), 3, "X")
    P = []
    for v in IKO_V:
        p = Vector(v).normalized() * (1 + rng.uniform(-0.22, 0.22))
        P.append(rot @ Vector((p.x * sc.x / 2, p.y * sc.y / 2, p.z * sc.z / 2)))
    zmin = min(p.z for p in P)
    P = [Vector((p.x + x, p.y + y, p.z - zmin + zb - 0.002)) for p in P]
    c = sum(P, Vector()) / len(P)
    for f in IKO_F:
        q = [P[i] for i in f]
        flach(pc, q, "beton", (sum(q, Vector()) / 3) - c)

def scherbe(pc, x, y, zb, size, seed):
    """Glasscherbe: duenne unregelmaessige Platte, leicht schraeg."""
    rng = random.Random(seed)
    n = rng.randint(4, 6)
    angs = sorted(rng.uniform(0, math.tau) for _ in range(n))
    poly = [(math.cos(a) * size * rng.uniform(0.35, 0.6), math.sin(a) * size * rng.uniform(0.35, 0.6)) for a in angs]
    rot = Matrix.Rotation(rng.uniform(-0.08, 0.08), 3, "X") @ Matrix.Rotation(rng.uniform(-0.08, 0.08), 3, "Y")
    top = [rot @ Vector((p[0], p[1], 0.003)) for p in poly]
    bot = [rot @ Vector((p[0], p[1], 0.0)) for p in poly]
    zmin = min(p.z for p in bot)
    off = Vector((x, y, zb - zmin + 0.0002))
    top = [p + off for p in top]
    bot = [p + off for p in bot]
    flach(pc, top, "glas", (0, 0, 1))
    flach(pc, bot[::-1], "glas", (0, 0, -1))
    for i in range(n):
        j = (i + 1) % n
        q = [bot[i], bot[j], top[j], top[i]]
        m = (q[0] + q[1]) / 2 - off
        flach(pc, q, "glas", (m.x, m.y, 0.0))

def papier(pc, x, y, zb, ang, k, seed):
    """Blatt A4, leicht gewellt, eine Ecke hochgebogen (Blatt k im Atlas)."""
    rng = random.Random(seed)
    W, Hh, nx, ny = 0.297, 0.21, 6, 4
    ca, sa = math.cos(ang), math.sin(ang)
    curl = rng.uniform(0.012, 0.022)
    V = {}
    for i in range(nx + 1):
        for j in range(ny + 1):
            u, v = i / nx * W, j / ny * Hh
            z = zb + 0.0008 + 0.0012 * noise.noise(Vector((u * 9 + seed, v * 9, 0.3))) + 0.0012
            t = max(0.0, (u / W + v / Hh) - 1.35) / 0.65
            z += curl * t * t
            lx, ly = u - W / 2, v - Hh / 2
            V[(i, j)] = (pc.bm.verts.new((x + ca * lx - sa * ly, y + sa * lx + ca * ly, z)), u, v)
    x0 = (0.05, 0.40, 0.75)[k]
    for i in range(nx):
        for j in range(ny):
            q = [V[(i, j)], V[(i + 1, j)], V[(i + 1, j + 1)], V[(i, j + 1)]]
            pc.face([e[0] for e in q], MD, [reg_uv("papier", U_RECHTS[0] + x0 + e[1], 0.005 + e[2]) for e in q],
                    smooth=True, want=(0, 0, 1))
    # Rueckseite (unbedrucktes Blatt k = 3 im Atlas, gespiegelt), damit die hochgebogene Ecke von unten nicht fehlt
    B = {key: pc.bm.verts.new(v[0].co) for key, v in V.items()}
    for i in range(nx):
        for j in range(ny):
            q = [(i, j), (i, j + 1), (i + 1, j + 1), (i + 1, j)]
            pc.face([B[e] for e in q], MD, [reg_uv("papier", U_RECHTS[0] + 1.10 + 0.297 - V[e][1], 0.005 + V[e][2]) for e in q],
                    smooth=True, want=(0, 0, -1))

def fetzen(pc, x, y, zb, size, seed):
    """Abgerissenes Stueck Linoleum: Oberseite Linoleum (weltbezogen), Unterseite Jute, Kanten im Schnitt."""
    rng = random.Random(seed)
    n = rng.randint(6, 8)
    angs = sorted(rng.uniform(0, math.tau) for _ in range(n))
    poly = [(x + math.cos(a) * size * rng.uniform(0.4, 0.75), y + math.sin(a) * size * rng.uniform(0.4, 0.75)) for a in angs]
    cu = rng.uniform(0.004, 0.009)
    far = max(poly, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
    def lift(p):
        d = math.hypot(p[0] - far[0], p[1] - far[1])
        return cu * max(0.0, 1 - d / size) ** 2
    top = [Vector((p[0], p[1], zb + LINO + lift(p))) for p in poly]
    bot = [Vector((p[0], p[1], zb + lift(p))) for p in poly]
    c = Vector((x, y, zb))
    for i in range(1, n - 1):
        tri = [top[0], top[i], top[i + 1]]
        pc.face(tri, MB, [uv_welt(p.x, p.y) for p in tri], want=(0, 0, 1))
    flach(pc, bot[::-1], "ruecken", (0, 0, -1))
    u0 = u_anfang(pc, "lino_schnitt", 1.0)
    s = 0.0
    for i in range(n):
        j = (i + 1) % n
        L = (top[j] - top[i]).length
        m = (top[i] + top[j]) / 2 - c
        pc.face([bot[i], bot[j], top[j], top[i]], MD,
                [reg_uv("lino_schnitt", u0 + s, 0.0045), reg_uv("lino_schnitt", u0 + s + L, 0.0045),
                 reg_uv("lino_schnitt", u0 + s + L, 0.0045 + LINO), reg_uv("lino_schnitt", u0 + s, 0.0045 + LINO)],
                want=(m.x, m.y, 0.0))
        s += L

# ======================= Abgerissenes Linoleum mit Rolle =======================
def abgerundet(cx, cy, ax, ay, rc, step):
    """Umriss eines abgerundeten Rechtecks gegen den Uhrzeigersinn, Start rechts auf der Oberkante: (x, y, nx, ny, seite)."""
    out = []
    def edge(p0, p1, nrm, tag):
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        n = max(1, int(round(L / step)))
        for k in range(n):
            t = k / n
            out.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, nrm[0], nrm[1], tag))
    def arc(c, a0):
        n = max(2, int(round(rc * math.pi / 2 / step)))
        for k in range(n):
            a = a0 + math.pi / 2 * k / n
            out.append((c[0] + rc * math.cos(a), c[1] + rc * math.sin(a), math.cos(a), math.sin(a), "bogen"))
    x0, x1, y0, y1 = cx - ax, cx + ax, cy - ay, cy + ay
    edge((x1 - rc, y1), (x0 + rc, y1), (0, 1), "oben")
    arc((x0 + rc, y1 - rc), math.pi / 2)
    edge((x0, y1 - rc), (x0, y0 + rc), (-1, 0), "links")
    arc((x0 + rc, y0 + rc), math.pi)
    edge((x0 + rc, y0), (x1 - rc, y0), (0, -1), "unten")
    arc((x1 - rc, y0 + rc), 1.5 * math.pi)
    edge((x1, y0 + rc), (x1, y1 - rc), (1, 0), "rechts")
    arc((x1 - rc, y1 - rc), 0.0)
    return out

AB_D = (0.006, 0.018, 0.035)        # Reihen hinter angehobenen Bruchkanten

def abriss(F, cx, cy, ax, ay, rc, hx, seed, hebungen):
    """Linoleum auf einer Flaeche abgerissen: zerfranster Umriss als Loch in der Oberflaeche. Auf der Oberkante
    zwischen hx[0] und hx[-1] liegt das Scharnier, an dem die aufgerollte Bahn haengt (dort keine Bruchkante).
    hebungen: (Anteil von, Anteil bis, Hoehe) des Umfangs, dort ist der Rand angehoben."""
    rng = random.Random(seed)
    yh = cy + ay
    base = [b for b in abgerundet(cx, cy, ax, ay, rc, 0.03) if not (b[4] == "oben" and hx[0] - 0.015 < b[0] < hx[-1] + 0.015)]
    k_in = next(k for k, b in enumerate(base) if b[4] == "oben" and b[0] < hx[0])
    base = base[:k_in] + [(x, yh, 0.0, 1.0, "scharnier") for x in hx[::-1]] + base[k_in:]
    n = len(base)
    rand = []
    zz = 1.0
    for k, (x, y, nx_, ny_, tag) in enumerate(base):
        s = k / n
        if tag == "scharnier":
            rand.append((x, y, 0.0, True, 0.0, nx_, ny_))
            continue
        zz = -zz * rng.uniform(0.4, 1.0)
        # vor allem nach innen gerissen: grosse Buchten, kleinere Zacken (nach aussen hoechstens gut 1 cm)
        jag = (-0.09 * (0.5 + 0.5 * noise.noise(Vector((s * 9 + seed, 2.3, 0.4))))
               - 0.025 * (0.5 + 0.5 * noise.noise(Vector((s * 26 + seed, 0.3, 0.7))))
               + 0.006 * noise.noise(Vector((s * 71 + seed, 1.3, 0.2))) + 0.0035 * zz)
        if tag == "oben":
            jag *= glatt(min(abs(x - hx[0]), abs(x - hx[-1])) / 0.08)
        L = 0.0
        for (a, b, hgt) in hebungen:
            if a < s < b:
                L = hgt * math.sin(math.pi * (s - a) / (b - a)) ** 0.8
        rand.append((x + nx_ * jag, y + ny_ * jag, L, False, L, nx_, ny_))
    idx = [F.pt(p[0], p[1], p[2]) for p in rand]
    F.holes.append(idx)
    arcs = []
    for (a, b, hgt) in hebungen:
        ks = [k for k in range(n) if a < k / n < b]
        rows = []
        for d in AB_D:
            row = []
            for k in ks:
                x, y, L, _, _, nx_, ny_ = rand[k]
                row.append(F.pt(x + nx_ * d, y + ny_ * d, L * math.exp(-d / 0.012)))
            F.line(row)
            rows.append(row)
        arcs.append(ks)
    poly = [(p[0], p[1]) for p in rand]
    F.sperr.append((poly, 0.05))
    return {"rand": rand, "arcs": arcs, "yh": yh, "hx": hx, "base": (cx, cy, ax, ay, rc)}

def abriss_extras(pc, F, ab):
    rand = ab["rand"]
    n = len(rand)
    # Bruchkanten (ausser am Scharnier), in Stuecken bis 2,6 m Laenge in den Atlas gelegt
    s, u0 = 0.0, u_anfang(pc, "lino_schnitt", 2.6)
    for k in range(n):
        a, b = rand[k], rand[(k + 1) % n]
        if a[3] and b[3]:
            continue
        ta = Vector((a[0], a[1], F.z(a[0], a[1], a[2])))
        tb = Vector((b[0], b[1], F.z(b[0], b[1], b[2])))
        L = (tb - ta).length
        if s + L > 2.6:
            s, u0 = 0.0, u_anfang(pc, "lino_schnitt", 2.6)
        d = Vector((b[0] - a[0], b[1] - a[1], 0.0))
        pc.face([ta, tb, tb - Vector((0, 0, KT)), ta - Vector((0, 0, KT))], MD,
                [reg_uv("lino_schnitt", u0 + s, 0.004 + KT), reg_uv("lino_schnitt", u0 + s + L, 0.004 + KT),
                 reg_uv("lino_schnitt", u0 + s + L, 0.004), reg_uv("lino_schnitt", u0 + s, 0.004)], want=(-d.y, d.x, 0.0))
        s += L
    # Unterseite der angehobenen Randstuecke
    for ks in ab["arcs"]:
        rows = []
        for k in ks:
            x, y, L, _, _, nx_, ny_ = rand[k]
            row = [(x, y, L)] + [(x + nx_ * d, y + ny_ * d, L * math.exp(-d / 0.012)) for d in AB_D]
            rows.append([pc.bm.verts.new((p[0], p[1], F.z(p[0], p[1], p[2]) - KT)) for p in row])
        a0, a1 = rand[ks[0]], rand[ks[-1]]
        uvm = plan_uvs(pc, [v for r in rows for v in r], "ruecken", (a1[0] - a0[0], a1[1] - a0[1]))
        for i in range(len(rows) - 1):
            for j in range(len(AB_D)):
                q = [rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]]
                pc.face(q, MD, [uvm[v] for v in q], smooth=True, want=(0, 0, -1))
    # Estrich mit Kleberresten: abgerundetes Rechteck um 4,5 cm groesser (reicht unter die Raender)
    cx, cy, ax, ay, rc = ab["base"]
    dd = 0.045
    out = [(b[0], b[1]) for b in abgerundet(cx, cy, ax + dd, ay + dd, rc + dd, 0.06)]
    pts = list(out)
    for i in range(int((2 * ax) / 0.25) + 1):
        for j in range(int((2 * ay) / 0.25) + 1):
            x, y = cx - ax + 0.1 + i * 0.25, cy - ay + 0.1 + j * 0.25
            if point_in(out, x, y) and poly_dist(out, x, y) > 0.08:
                pts.append((x, y))
    m = len(out)
    co, _, tris, _, _, _ = geometry.delaunay_2d_cdt([Vector(p) for p in pts], [(i, (i + 1) % m) for i in range(m)], [], 0, 1e-9)
    ymin = min(p[1] for p in out) - 0.005
    vs = [pc.bm.verts.new((c.x, c.y, EZ + F.welle(c.x, c.y))) for c in co]
    for (a, b, c) in tris:
        if (co[b] - co[a]).cross(co[c] - co[a]) < 0:
            b, c = c, b
        mx, my = (co[a].x + co[b].x + co[c].x) / 3, (co[a].y + co[b].y + co[c].y) / 3
        if not point_in(out, mx, my):
            continue
        pc.face([vs[a], vs[b], vs[c]], MD, [reg_uv("estrich", co[v].x + P2, 0.01 + co[v].y - ymin) for v in (a, b, c)])

def rolle(pc, F, hx, yh, R=0.026, turns=2.25, p=0.0035, seed=0):
    """Am Scharnier haengende, zur abgerissenen Seite hin aufgerollte Bahn (Oberseite aussen). Hoechstens 6 cm hoch."""
    rng = random.Random(seed)
    zH = -LINO / 2
    r_bot = R - p * 0.75
    Cz = EZ + LINO / 2 + r_bot
    R1 = Cz - zH
    Cq = R1 + R
    path = [(R1 * math.sin(math.pi / 2 * k / 6), zH + R1 - R1 * math.cos(math.pi / 2 * k / 6), 0.0) for k in range(7)]
    ns = int(turns * 18)
    for k in range(1, ns + 1):
        phi = turns * 2 * math.pi * k / ns
        r = R - p * phi / (2 * math.pi)
        path.append((Cq + r * math.cos(math.pi - phi), Cz + r * math.sin(math.pi - phi), phi))
    K = len(path)
    tg = []
    for k in range(K):
        a, b = path[max(0, k - 1)], path[min(K - 1, k + 1)]
        tq, tz = b[0] - a[0], b[1] - a[1]
        L = math.hypot(tq, tz)
        tg.append((tq / L, tz / L))
    nx = len(hx) - 1
    T, B = [], []
    for j, x in enumerate(hx):
        sig = 1 + 0.035 * noise.noise(Vector((x * 2.3 + seed, 0.4, 0.9)))
        dzh = F.welle(x, yh)
        tr, br = [], []
        for k, (q, z, phi) in enumerate(path):
            f = 1 + (sig - 1) * min(1.0, phi / math.pi)
            q2, z2 = Cq + (q - Cq) * f if phi > 0 else q, Cz + (z - Cz) * f if phi > 0 else z
            nq, nz = -tg[k][1], tg[k][0]
            tr.append(Vector((x, yh - (q2 + nq * LINO / 2), z2 + nz * LINO / 2 + dzh)))
            br.append(Vector((x, yh - (q2 - nq * LINO / 2), z2 - nz * LINO / 2 + dzh)))
        T.append(tr)
        B.append(br)
    def bogen(rows):
        out = []
        for row in rows:
            acc = [0.0]
            for a, b in zip(row, row[1:]):
                acc.append(acc[-1] + (b - a).length)
            out.append(acc)
        return out
    sT, sB = bogen(T), bogen(B)
    vT = [[pc.bm.verts.new(p) for p in row] for row in T]
    vB = [[pc.bm.verts.new(p) for p in row] for row in B]
    u0 = u_anfang(pc, "ruecken", hx[-1] - hx[0] + 0.01)
    for j in range(nx):
        for k in range(K - 1):
            nq, nz = -tg[k][1], tg[k][0]
            pc.face([vT[j][k], vT[j + 1][k], vT[j + 1][k + 1], vT[j][k + 1]], MB,
                    [uv_welt(hx[j], yh - sT[j][k]), uv_welt(hx[j + 1], yh - sT[j + 1][k]),
                     uv_welt(hx[j + 1], yh - sT[j + 1][k + 1]), uv_welt(hx[j], yh - sT[j][k + 1])],
                    smooth=True, want=(0, -nq, nz))
            pc.face([vB[j][k], vB[j][k + 1], vB[j + 1][k + 1], vB[j + 1][k]], MD,
                    [reg_uv("ruecken", u0 + hx[j] - hx[0], 0.01 + sB[j][k]), reg_uv("ruecken", u0 + hx[j] - hx[0], 0.01 + sB[j][k + 1]),
                     reg_uv("ruecken", u0 + hx[j + 1] - hx[0], 0.01 + sB[j + 1][k + 1]), reg_uv("ruecken", u0 + hx[j + 1] - hx[0], 0.01 + sB[j + 1][k])],
                    smooth=True, want=(0, nq, -nz))
    for j, sx in ((0, -1), (nx, 1)):
        sm_ = [(a_ + b_) / 2 for a_, b_ in zip(sT[j], sB[j])]
        u0 = u_anfang(pc, "lino_schnitt", sm_[-1] + 0.02)
        for k in range(K - 1):
            # je Viereck eben abgewickelt: U entlang der Mittellinie, V quer durch die Bahn (exakte Dichte)
            q = [T[j][k], T[j][k + 1], B[j][k + 1], B[j][k]]
            e1 = ((T[j][k + 1] + B[j][k + 1]) - (T[j][k] + B[j][k])).normalized()
            e2 = Vector((sx, 0, 0)).cross(e1).normalized()
            if e2.dot(T[j][k] - B[j][k]) < 0:
                e2 = -e2
            o = B[j][k]
            pc.face(q, MD, [reg_uv("lino_schnitt", u0 + sm_[k] + (p_ - o).dot(e1), 0.0045 + (p_ - o).dot(e2)) for p_ in q],
                    want=(sx, 0, 0))
    u0 = u_anfang(pc, "lino_schnitt", hx[-1] - hx[0] + 0.01)
    tq, tz = tg[-1]
    for j in range(nx):
        pc.face([T[j][-1], T[j + 1][-1], B[j + 1][-1], B[j][-1]], MD,
                [reg_uv("lino_schnitt", u0 + hx[j] - hx[0], 0.0045 + LINO), reg_uv("lino_schnitt", u0 + hx[j + 1] - hx[0], 0.0045 + LINO),
                 reg_uv("lino_schnitt", u0 + hx[j + 1] - hx[0], 0.0045), reg_uv("lino_schnitt", u0 + hx[j] - hx[0], 0.0045)],
                want=(0, -tq, tz))

# ======================= OP-Fliesen mit Bodenablauf =======================
XS = [-P2 + FL * i for i in range(41)]

def ablauf(pc):
    """Runder Bodenablauf aus Edelstahl in der Mitte: Flansch mit flacher Fase, Schlitzrost, Topf. Die Fliesen
    ringsum sind rund zugeschnitten."""
    R0, R1, R2, R3 = ABL_R
    n = 48
    zf = 0.0008
    def zuv(x, y):
        return ((ZENTRUM[0] + x + ZR) * UVS, (ZENTRUM[2] + y + ZR) * UVS)
    ring = lambda r, z: [Vector((r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), z)) for k in range(n)]
    c3 = ring(R3, 0.0)
    c2, c1, c1b = ring(R2, zf), ring(R1, zf), ring(R1, -0.003)
    for k in range(n):
        m = (k + 1) % n
        for (ra, rb) in ((c2, c3), (c1, c2)):
            q = [ra[k], rb[k], rb[m], ra[m]]
            pc.face(q, MD, [zuv(p.x, p.y) for p in q], want=(0, 0, 1))
        L = 2 * math.pi * R1 / n
        q = [c1[k], c1[m], c1b[m], c1b[k]]
        pc.face(q, MD, [reg_uv("edelstahl", k * L, 0.045 + zf), reg_uv("edelstahl", (k + 1) * L, 0.045 + zf),
                        reg_uv("edelstahl", (k + 1) * L, 0.042), reg_uv("edelstahl", k * L, 0.042)],
                want=(-c1[k].x, -c1[k].y, 0))
    # Rost mit 12 Schlitzen
    disc = ring(R1, -0.003)
    slots = []
    for k in range(12):
        a = 2 * math.pi * (k + 0.5) / 12
        ca, sa = math.cos(a), math.sin(a)
        sl = []
        for (r, w) in ((0.03, -0.0037), (0.088, -0.0037), (0.088, 0.0037), (0.03, 0.0037)):
            sl.append(Vector((ca * r - sa * w, sa * r + ca * w, -0.003)))
        slots.append(sl)
    pts = disc + [p for s_ in slots for p in s_]
    for (a, b, c) in geometry.tessellate_polygon([disc] + slots):
        tri = [pts[a], pts[b], pts[c]]
        if (tri[1] - tri[0]).cross(tri[2] - tri[0]).length < 1e-12:
            continue
        pc.face(tri, MD, [zuv(p.x, p.y) for p in tri], want=(0, 0, 1))
    for sl in slots:
        cen = sum(sl, Vector()) / 4
        u = 0.0
        for i in range(4):
            a, b = sl[i], sl[(i + 1) % 4]
            L = (b - a).length
            q = [a, b, b - Vector((0, 0, 0.003)), a - Vector((0, 0, 0.003))]
            m = (a + b) / 2
            pc.face(q, MD, [reg_uv("edelstahl", 2.0 + u, 0.05), reg_uv("edelstahl", 2.0 + u + L, 0.05),
                            reg_uv("edelstahl", 2.0 + u + L, 0.047), reg_uv("edelstahl", 2.0 + u, 0.047)],
                    want=(cen.x - m.x, cen.y - m.y, 0))
            u += L
    # Topf
    top, bot = ring(R0, -0.006), ring(R0, -0.06)
    L = 2 * math.pi * R0 / n
    for k in range(n):
        m = (k + 1) % n
        q = [top[k], top[m], bot[m], bot[k]]
        pc.face(q, MD, [reg_uv("edelstahl", 1.0 + k * L, 0.056), reg_uv("edelstahl", 1.0 + (k + 1) * L, 0.056),
                        reg_uv("edelstahl", 1.0 + (k + 1) * L, 0.002), reg_uv("edelstahl", 1.0 + k * L, 0.002)],
                want=(-top[k].x, -top[k].y, 0))
    flach(pc, bot, "estrich", (0, 0, 1))

def boden_fliesen(pc):
    rng = pc.rng
    rmap = [(j * 7 + 3) % 6 for j in range(40)]
    ush = [FL * ((j * 13 + 5) % 40) for j in range(40)]
    def tuv(i, j, x, y):
        if 14 <= i <= 25 and 14 <= j <= 25:
            return ((ZENTRUM[0] + x + ZR) * UVS, (ZENTRUM[2] + y + ZR) * UVS)
        return ((x + P2 + ush[j]) * UVS, (REG["fliesen"][0] + FL * rmap[j] + (y - XS[j])) * UVS)
    R3 = ABL_R[3]
    block = {(19, 19), (19, 20), (20, 19), (20, 20)}                       # ganz unter dem Flansch
    rund = {(18, 19), (18, 20), (21, 19), (21, 20), (19, 18), (20, 18), (19, 21), (20, 21)}   # rund zugeschnitten
    def in_fuge(x, y):
        if math.hypot(x, y) < R3:
            return False
        if abs(y) < INNEN:
            k = int(round((x + P2) / FL))
            if 1 <= k <= 39 and abs(x - XS[k]) < FW:
                return True
        if abs(x) < INNEN:
            k = int(round((y + P2) / FL))
            if 1 <= k <= 39 and abs(y - XS[k]) < FW:
                return True
        return False
    def ohne_kreis(x0, x1, y0, y1):
        """Rechteck ohne die Kreisscheibe des Flanschs, Umriss gegen den Uhrzeigersinn (Bogen im Uhrzeigersinn um 0)."""
        ec = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        seq = []
        for k in range(4):
            a, b = ec[k], ec[(k + 1) % 4]
            seq.append((a, "in" if math.hypot(*a) < R3 else "out"))
            dx, dy = b[0] - a[0], b[1] - a[1]
            A, B, C = dx * dx + dy * dy, 2 * (a[0] * dx + a[1] * dy), a[0] ** 2 + a[1] ** 2 - R3 * R3
            D = B * B - 4 * A * C
            if D > 0:
                for t in sorted(((-B - math.sqrt(D)) / (2 * A), (-B + math.sqrt(D)) / (2 * A))):
                    if 1e-9 < t < 1 - 1e-9:
                        seq.append(((a[0] + dx * t, a[1] + dy * t), "x"))
        n = len(seq)
        start = next(k for k in range(n) if seq[k][1] == "x" and seq[(k + 1) % n][1] == "out")
        poly = [seq[start][0]]
        k = (start + 1) % n
        while seq[k][1] != "x":
            poly.append(seq[k][0])
            k = (k + 1) % n
        ein = seq[k][0]
        poly.append(ein)
        t0, t1 = math.atan2(ein[1], ein[0]), math.atan2(poly[0][1], poly[0][0])
        if t1 > t0:
            t1 -= 2 * math.pi
        m = max(2, int(math.ceil((t0 - t1) / math.radians(5))))
        for q in range(1, m):
            t = t0 + (t1 - t0) * q / m
            poly.append((R3 * math.cos(t), R3 * math.sin(t)))
        return poly
    risse = [(5, 31), (12, 8), (27, 17), (33, 26), (17, 23), (8, 15)]
    chips = {(22, 33): 0, (30, 9): 2, (10, 24): 1, (24, 12): 3}
    luecken = {}
    def luecke(key, a, b):
        luecken.setdefault(key, []).append((a, b))
    for (i, j), c in chips.items():
        x0, x1, y0, y1 = XS[i] + FW, XS[i + 1] - FW, XS[j] + FW, XS[j + 1] - FW
        a, b = rng.uniform(0.005, 0.011), rng.uniform(0.005, 0.011)
        cx, cy = (x0, x1, x1, x0)[c], (y0, y0, y1, y1)[c]
        ex, ey = (1, -1, -1, 1)[c], (1, 1, -1, -1)[c]
        p1, p2 = (cx + ex * a, cy), (cx, cy + ey * b)
        hk = ("h", j, 1) if c in (0, 1) else ("h", j + 1, -1)
        vk = ("v", i, 1) if c in (0, 3) else ("v", i + 1, -1)
        luecke(hk, min(cx, p1[0]), max(cx, p1[0]))
        luecke(vk, min(cy, p2[1]), max(cy, p2[1]))
        poly = []
        for k, q in enumerate([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]):
            if k == c:
                poly += [p2, p1] if c in (0, 2) else [p1, p2]     # gegen den Uhrzeigersinn: erst die ankommende Seite
            else:
                poly.append(q)
        if loop_area(poly) < 0:
            poly = poly[::-1]
        p3 = [Vector((x, y, 0.0)) for x, y in poly]
        for t in range(1, len(p3) - 1):
            tri = [p3[0], p3[t], p3[t + 1]]
            pc.face(tri, MD, [tuv(i, j, p.x, p.y) for p in tri], want=(0, 0, 1))
        C, P1, P2_ = Vector((cx, cy, -FT)), Vector((p1[0], p1[1], 0.0)), Vector((p2[0], p2[1], 0.0))
        flach(pc, [C, P1, P2_], "fliesenkante", (0, 0, 1))
        flach(pc, [P1, P1 - Vector((0, 0, FT)), C], "fliesenkante", (0, -ey, 0))
        flach(pc, [P2_, P2_ - Vector((0, 0, FT)), C], "fliesenkante", (-ex, 0, 0))
    for (i, j) in risse:
        x0, x1, y0, y1 = XS[i] + FW, XS[i + 1] - FW, XS[j] + FW, XS[j + 1] - FW
        quer = rng.random() < 0.5
        t0, t1 = rng.uniform(0.25, 0.75), rng.uniform(0.25, 0.75)
        if quer:
            path = [(x0, y0 + t0 * (y1 - y0))] + [(x0 + (x1 - x0) * f, y0 + (y1 - y0) * (t0 + (t1 - t0) * f + rng.uniform(-0.08, 0.08)))
                                                  for f in (0.35, 0.65)] + [(x1, y0 + t1 * (y1 - y0))]
        else:
            path = [(x0 + t0 * (x1 - x0), y0)] + [(x0 + (x1 - x0) * (t0 + (t1 - t0) * f + rng.uniform(-0.08, 0.08)), y0 + (y1 - y0) * f)
                                                  for f in (0.35, 0.65)] + [(x0 + t1 * (x1 - x0), y1)]
        g = 0.0004
        ns_ = [(-(b[1] - a[1]), b[0] - a[0]) for a, b in zip(path, path[1:])]
        nrm = []
        for k in range(len(path)):
            a_ = ns_[max(0, k - 1)]
            b_ = ns_[min(len(ns_) - 1, k)]
            vx, vy = a_[0] + b_[0], a_[1] + b_[1]
            L = math.hypot(vx, vy)
            nrm.append((vx / L, vy / L))
        lo = [(p[0] - n_[0] * g, p[1] - n_[1] * g) for p, n_ in zip(path, nrm)]
        hi = [(p[0] + n_[0] * g, p[1] + n_[1] * g) for p, n_ in zip(path, nrm)]
        if quer:
            # Risspfad links -> rechts, Normale nach oben (+y): lo = unteres Stueck, hi = oberes Stueck
            lo[0], hi[0] = (x0, path[0][1] - g), (x0, path[0][1] + g)
            lo[-1], hi[-1] = (x1, path[-1][1] - g), (x1, path[-1][1] + g)
            pa = [(x0, y0), (x1, y0)] + lo[::-1]
            pb = hi + [(x1, y1), (x0, y1)]
        else:
            # Risspfad unten -> oben, Normale nach links (-x): hi = linkes Stueck, lo = rechtes Stueck
            lo[0], hi[0] = (path[0][0] + g, y0), (path[0][0] - g, y0)
            lo[-1], hi[-1] = (path[-1][0] + g, y1), (path[-1][0] - g, y1)
            pa = [(x0, y0)] + hi + [(x0, y1)]
            pb = [lo[0], (x1, y0), (x1, y1)] + lo[::-1][:-1]
        dz_b = -0.0003
        for poly, dz in ((pa, 0.0), (pb, dz_b)):
            if loop_area(poly) < 0:
                poly = poly[::-1]
            p3 = [Vector((x, y, dz)) for x, y in poly]
            for (a, b, c) in geometry.tessellate_polygon([p3]):
                tri = [p3[a], p3[b], p3[c]]
                if (tri[1] - tri[0]).cross(tri[2] - tri[0]).length < 1e-12:
                    continue
                pc.face(tri, MD, [tuv(i, j, p.x, p.y) for p in tri], want=(0, 0, 1))
        zf = -0.0012
        z_lo = 0.0 if quer else dz_b
        z_hi = dz_b if quer else 0.0
        for k in range(len(path) - 1):
            q = [Vector((lo[k][0], lo[k][1], zf)), Vector((lo[k + 1][0], lo[k + 1][1], zf)),
                 Vector((hi[k + 1][0], hi[k + 1][1], zf)), Vector((hi[k][0], hi[k][1], zf))]
            flach(pc, q, "fuge", (0, 0, 1), e1=(path[k + 1][0] - path[k][0], path[k + 1][1] - path[k][1], 0.0))
            for side, z_, s_ in ((lo, z_lo, 1), (hi, z_hi, -1)):          # Flanke zeigt in den Spalt
                a, b = side[k], side[k + 1]
                q = [Vector((a[0], a[1], z_)), Vector((b[0], b[1], z_)), Vector((b[0], b[1], zf)), Vector((a[0], a[1], zf))]
                flach(pc, q, "fliesenkante", (s_ * nrm[k][0], s_ * nrm[k][1], 0))
    for (i, j) in rund:
        poly = ohne_kreis(XS[i] + FW, XS[i + 1] - FW, XS[j] + FW, XS[j + 1] - FW)
        p3 = [Vector((x, y, 0.0)) for x, y in poly]
        for (a, b, c) in geometry.tessellate_polygon([p3]):
            tri = [p3[a], p3[b], p3[c]]
            if (tri[1] - tri[0]).cross(tri[2] - tri[0]).length < 1e-12:
                continue
            pc.face(tri, MD, [tuv(i, j, p.x, p.y) for p in tri], want=(0, 0, 1))
    # alle uebrigen Fliesen: Raster aus Teilflaechen, Fugenstreifen ausgespart
    for j in range(40):
        for i in range(40):
            if (i, j) in block or (i, j) in rund or (i, j) in chips or (i, j) in risse:
                continue
            bx = {XS[i], XS[i + 1]} | ({XS[i] + FW} if i >= 1 else set()) | ({XS[i + 1] - FW} if i + 1 <= 39 else set())
            by = {XS[j], XS[j + 1]} | ({XS[j] + FW} if j >= 1 else set()) | ({XS[j + 1] - FW} if j + 1 <= 39 else set())
            for v in (-INNEN, INNEN):
                if XS[i] < v < XS[i + 1]:
                    bx.add(v)
                if XS[j] < v < XS[j + 1]:
                    by.add(v)
            bx, by = sorted(bx), sorted(by)
            for a in range(len(bx) - 1):
                for b in range(len(by) - 1):
                    if in_fuge((bx[a] + bx[a + 1]) / 2, (by[b] + by[b + 1]) / 2):
                        continue
                    q = [(bx[a], by[b]), (bx[a + 1], by[b]), (bx[a + 1], by[b + 1]), (bx[a], by[b + 1])]
                    pc.face([Vector((x, y, 0.0)) for x, y in q], MD, [tuv(i, j, x, y) for x, y in q])
    # Fugen: Flanken der Fliesen, Fugengrund, Enden am flachen Rand
    def abschnitte(a, b, lk):
        segs = [(a, b)]
        for (c, d) in sorted(luecken.get(lk, [])):
            new = []
            for (s0, s1) in segs:
                if d <= s0 or c >= s1:
                    new.append((s0, s1))
                    continue
                if c > s0:
                    new.append((s0, c))
                if d < s1:
                    new.append((d, s1))
            segs = new
        return [s_ for s_ in segs if s_[1] - s_[0] > 1e-6]
    def kreisende(q):
        return math.sqrt(R3 * R3 - q * q) if abs(q) < R3 else None
    for k in range(1, 40):
        c = XS[k]
        for orient in ("v", "h"):
            def P(along, across, z):
                return Vector((c + across, along, z)) if orient == "v" else Vector((along, c + across, z))
            def al(p):
                return p.y if orient == "v" else p.x
            def ac(p):
                return (p.x if orient == "v" else p.y) - c
            for side in (-1, 1):
                e = kreisende(c + side * FW)
                for (a, b) in ([(-INNEN, INNEN)] if e is None else [(-INNEN, -e), (e, INNEN)]):
                    for (s0, s1) in abschnitte(a, b, (orient, k, side)):
                        q = [P(s0, side * FW, 0.0), P(s1, side * FW, 0.0), P(s1, side * FW, -FT), P(s0, side * FW, -FT)]
                        pc.face(q, MD, [reg_uv("fliesenkante", al(p) + P2, 0.004 + p.z + FT) for p in q],
                                want=P(0, -side, 0) - P(0, 0, 0))
            zf = -FT if orient == "v" else -FT - 0.0001
            e1, e2 = kreisende(c - FW), kreisende(c + FW)
            if e1 is None:
                stuecke = [((-INNEN, -INNEN), (INNEN, INNEN))]
            else:
                stuecke = [((-INNEN, -INNEN), (-e1, -e2)), ((e1, e2), (INNEN, INNEN))]
            for (a1, a2), (b1, b2) in stuecke:
                q = [P(a1, -FW, zf), P(b1, -FW, zf), P(b2, FW, zf), P(a2, FW, zf)]
                pc.face(q, MD, [reg_uv("fuge", al(p) + P2, 0.005 + ac(p) + FW) for p in q], want=(0, 0, 1))
                for (u1, u2), sg in (((a1, a2), 1), ((b1, b2), -1)):
                    q = [P(u1, -FW, 0.0), P(u2, FW, 0.0), P(u2, FW, -FT), P(u1, -FW, -FT)]
                    L = (q[1] - q[0]).length                        # am Flansch schraeg: echte Laenge fuer U
                    pc.face(q, MD, [reg_uv("fliesenkante", 3.0, 0.004 + FT), reg_uv("fliesenkante", 3.0 + L, 0.004 + FT),
                                    reg_uv("fliesenkante", 3.0 + L, 0.004), reg_uv("fliesenkante", 3.0, 0.004)],
                            want=P(sg, 0, 0) - P(0, 0, 0))
    ablauf(pc)

# ======================= Die fuenf Stuecke =======================
def boden_01():
    pc = Piece(f"{GEB}_boden_01")
    F = Flaeche(welle_fn(11))
    for xs, sd in zip(NAEHTE, (3, 4)):
        naht(F, xs, 0.0025, sd)
    for (cx, cy, R, H) in ((-0.55, 0.85, 0.13, 0.0028), (0.4, -1.1, 0.09, 0.0018), (1.45, 0.35, 0.07, 0.0015)):
        blase(F, cx, cy, R, H)
    F.gitter()
    F.bauen(pc)
    koerper(pc)
    return finish(pc)

def boden_02():
    pc = Piece(f"{GEB}_boden_02")
    F = Flaeche(welle_fn(12))
    runs = naht(F, -1.0, 0.0035, 5, bursts=[(-1.25, 0.2, 0.012, 0.007)])
    runs += naht(F, 1.0, 0.003, 6, bursts=[(0.35, 1.3, 0.009, 0.005)])
    runs.append(riss(F, [(0.2, -1.05), (0.27, -1.01), (0.33, -1.02), (0.41, -0.97), (0.5, -0.95)], 0.0028, 0.0013,
                     E=(0.002, 0.006, 0.014)))
    runs.append(riss(F, [(0.42, 0.85), (0.48, 0.91), (0.5, 0.97), (0.56, 1.04)], 0.0022, 0.001, E=(0.002, 0.006, 0.014)))
    mid = curve((-0.55, -1.55), 1.52, 2.7, 0.06, 30)
    for off in (-0.27, 0.27):
        schleifrille(F, pc, offset_line(mid, off), 0.009, 0.0006)
    schleifrille(F, pc, curve((0.1, -0.4), 0.4, 0.75, -0.3, 10), 0.006, 0.0005)
    blase(F, 0.55, 1.55, 0.08, 0.002)
    F.gitter()
    F.bauen(pc)
    for r in runs:
        riss_extras(pc, F, r)
    koerper(pc)
    return finish(pc)

def boden_03():
    pc = Piece(f"{GEB}_boden_03")
    F = Flaeche(welle_fn(13))
    hx = [-0.9 + 1.3 * j / 4 for j in range(5)]
    ab = abriss(F, -0.125, -0.55, 1.575, 0.72, 0.42, hx, 21, [(0.38, 0.47, 0.004), (0.6, 0.7, 0.003)])   # rund 1/4 der Flaeche
    for xs, sd in zip(NAEHTE, (7, 8)):
        naht(F, xs, 0.0025, sd)
    blase(F, 1.35, 1.2, 0.1, 0.0022)
    F.gitter()
    F.bauen(pc)
    abriss_extras(pc, F, ab)
    rolle(pc, F, hx, ab["yh"], seed=22)
    loch = [(p[0], p[1]) for p in ab["rand"]]
    def zb(x, y):
        return EZ + F.welle(x, y) if point_in(loch, x, y) else F.z(x, y)
    rng = random.Random(23)
    for (x, y, s) in ((-1.2, -0.9, 0.06), (-0.6, -1.05, 0.045), (0.2, -0.75, 0.07), (0.55, -1.1, 0.04),
                      (-1.35, -0.3, 0.05), (1.05, -0.2, 0.045), (-0.1, -0.35, 0.035), (0.75, -0.55, 0.03),
                      (-0.85, -0.6, 0.028), (0.0, -1.15, 0.05), (-0.35, -0.85, 0.022), (0.35, -0.3, 0.025),
                      (1.25, -0.95, 0.04)):
        brocken(pc, x, y, zb(x, y), s, rng.randint(0, 10 ** 6))
    for k in range(14):
        x, y = rng.uniform(-1.5, 1.2), rng.uniform(-1.2, -0.08)
        scherbe(pc, x, y, zb(x, y), rng.uniform(0.03, 0.08), rng.randint(0, 10 ** 6))
    papier(pc, 0.15, -1.0, zb(0.15, -1.0), 0.4, 0, 31)
    papier(pc, 1.1, 0.95, zb(1.1, 0.95), -0.9, 1, 32)
    fetzen(pc, -0.95, -1.0, zb(-0.95, -1.0), 0.09, 33)
    fetzen(pc, 0.45, -0.42, zb(0.45, -0.42), 0.07, 34)
    koerper(pc)
    return finish(pc)

def boden_04():
    pc = Piece(f"{GEB}_boden_04")
    boden_fliesen(pc)
    koerper(pc, kante="kante_fliese", unten=MB)
    return finish(pc)

def boden_schwelle():
    pc = Piece(f"{GEB}_boden_schwelle")
    top = [Vector((-SW, -ST, 0.0)), Vector((SW, -ST, 0.0)), Vector((SW, ST, 0.0)), Vector((-SW, ST, 0.0))]
    pc.face(top, MB, [uv_welt(p.x, p.y) for p in top], want=(0, 0, 1))
    koerper(pc, SW, ST)
    prof = [(-0.035, 0.0), (-0.025, 0.0035), (0.025, 0.0035), (0.035, 0.0)]
    sacc = [0.0]
    for a, b in zip(prof, prof[1:]):
        sacc.append(sacc[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    xk = [-0.45, -0.35, -0.25, -0.15, -0.05, 0.05, 0.15, 0.25, 0.30, 0.33, 0.36, 0.39, 0.42, 0.45]
    def hub(x):
        return 0.0065 * ((x - 0.30) / 0.15) ** 2 if x > 0.30 else 0.0
    rows = [[Vector((x, y, z + hub(x))) for (y, z) in prof] for x in xk]
    for k in range(len(xk) - 1):
        for m in range(3):
            dy, dz = prof[m + 1][0] - prof[m][0], prof[m + 1][1] - prof[m][1]
            q = [rows[k][m], rows[k + 1][m], rows[k + 1][m + 1], rows[k][m + 1]]
            pc.face(q, MD, [reg_uv("alu", p.x + P2, 0.015 + sacc[mm]) for p, mm in zip(q, (m, m, m + 1, m + 1))],
                    want=(0, -dz, dy))
        if xk[k + 1] > 0.30:
            q = [rows[k][3], rows[k + 1][3], rows[k + 1][0], rows[k][0]]
            pc.face(q, MD, [reg_uv("alu", p.x + P2, 0.015 + (p.y + 0.035)) for p in q], want=(0, 0, -1))
    flach(pc, rows[0][::-1], "alu", (-1, 0, 0))
    flach(pc, rows[-1], "alu", (1, 0, 0))
    for x in (-0.38, -0.13, 0.12):
        ztop = 0.0035 + 0.0003
        ring_t = [Vector((x + 0.0042 * math.cos(math.pi * k / 4), 0.0042 * math.sin(math.pi * k / 4), ztop)) for k in range(8)]
        ring_b = [p - Vector((0, 0, 0.0003)) for p in ring_t]
        flach(pc, ring_t, "edelstahl", (0, 0, 1), v_rand=False)
        for k in range(8):
            m = (k + 1) % 8
            flach(pc, [ring_b[k], ring_b[m], ring_t[m], ring_t[k]], "edelstahl", (ring_t[k].x - x, ring_t[k].y, 0), v_rand=False)
    return finish(pc)

# ======================= Fertigstellen, Export =======================
PIECES = []
def finish(pc):
    bm = pc.bm
    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    ngons = [f for f in bm.faces if len(f.verts) > 3]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons)
    bm.normal_update()
    me = bpy.data.meshes.new(pc.name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MAT_BODEN)
    me.materials.append(MAT_DETAIL)
    ob = bpy.data.objects.new(pc.name, me)
    scene.collection.objects.link(ob)
    me.calc_loop_triangles()
    uvl = me.uv_layers.active.data
    dens, A, W, flach_ = [], 0.0, 0.0, 0
    for lt in me.loop_triangles:
        a3 = lt.area
        if a3 < 1e-10:
            flach_ += 1
            continue
        (u1, v1), (u2, v2), (u3, v3) = (uvl[i].uv for i in lt.loops)
        a2 = abs((u2 - u1) * (v3 - v1) - (u3 - u1) * (v2 - v1)) / 2 * TEXRES * TEXRES
        d = math.sqrt(a2 / a3)
        if os.environ.get("DIAG") and (d < 990 or d > 1060):
            cen = sum((me.vertices[i].co for i in lt.vertices), Vector()) / 3
            log("  Ausreisser", pc.name, round(d), "Mat", me.polygons[lt.polygon_index].material_index,
                "bei", tuple(round(c, 4) for c in cen), "A", round(a3 * 1e4, 4), "cm2")
        dens.append(d)
        A += a3
        W += d * a3
    zs = [v.co.z for v in me.vertices]
    info = {"name": pc.name, "dreiecke": len(me.loop_triangles), "dichte_min": round(min(dens)), "dichte_max": round(max(dens)),
            "dichte_mittel": round(W / A), "z_max_cm": round(max(zs) * 100, 2), "ohne_flaeche": flach_}
    PIECES.append((ob, info))
    log("Stueck", info)
    return ob

def export(ob):
    folder = os.path.join(MODELLE, ob.name)
    os.makedirs(folder, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=os.path.join(folder, ob.name + ".gltf"), export_format="GLTF_SEPARATE",
                              use_selection=True, export_yup=True, export_apply=True, export_keep_originals=True,
                              export_materials="EXPORT", export_cameras=False, export_lights=False, export_extras=False)

log("Stuecke ...")
BUILD = [boden_01, boden_02, boden_03, boden_04, boden_schwelle]
OBJS = []
for fn in BUILD:
    ob = fn()
    OBJS.append(ob)
    export(ob)
    log("exportiert", ob.name)
with open(os.path.join(OUT, f"pruefung_boden_{GEB}.json"), "w", encoding="utf-8") as fjs:
    json.dump([info for _, info in PIECES], fjs, ensure_ascii=False, indent=1)

# ======================= Vorschau =======================
def setup_render():
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"

if SHOTS:
    setup_render()
    world = bpy.data.worlds.new("Welt")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    POS = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (15.0, 0.0), (10.0, -2.9)]
    for ob, (x, y) in zip(OBJS, POS):
        ob.location = (x, y, 0.0)
    def kopie(ob, x, y):
        o = bpy.data.objects.new(ob.name + "_probe", ob.data)
        scene.collection.objects.link(o)
        o.location = (x, y, 0.0)
        return o
    KX, KY = 2.0, 9.0
    for (k, dx, dy) in ((0, 0, 0), (1, 4, 0), (2, 0, 4), (0, 4, 4)):
        kopie(OBJS[k], KX + dx, KY + dy)
    for dx in (9.0, 13.0):
        kopie(OBJS[3], KX + dx, KY + 2)
    cam_d = bpy.data.cameras.new("Kamera")
    cam = bpy.data.objects.new("Kamera", cam_d)
    scene.collection.objects.link(cam)
    scene.camera = cam
    def aim(ob, target):
        ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
    sun_d = bpy.data.lights.new("Licht", "SUN")
    sun_d.angle = math.radians(8)
    sun = bpy.data.objects.new("Licht", sun_d)
    scene.collection.objects.link(sun)
    spot_d = bpy.data.lights.new("Taschenlampe", "SPOT")
    spot_d.spot_size = math.radians(52)
    spot_d.spot_blend = 0.5
    spot_d.color = (0.86, 0.92, 1.0)
    spot_d.shadow_soft_size = 0.02
    spot = bpy.data.objects.new("Taschenlampe", spot_d)
    scene.collection.objects.link(spot)
    # Taschenlampe: Stueck, Kamera relativ zur Mitte, Blickziel relativ, Brennweite
    LAMPE = {
        "lampe1": (0, (-0.7, -3.1, 1.65), (0.1, -0.2, 0.0), 22),
        "lampe2": (1, (-0.2, -3.1, 1.6), (-0.75, -0.35, 0.0), 22),
        "lampe3": (2, (0.6, -3.1, 1.6), (-0.35, -0.45, 0.0), 22),
        "lampe4": (3, (-0.8, -2.9, 1.65), (0.05, -0.1, 0.0), 22),
        "nah1": (3, (0.42, -0.5, 0.55), (0.0, 0.0, 0.0), 32),
        "nah2": (4, (-0.5, -0.62, 0.42), (0.3, 0.0, 0.004), 32),
        "nah3": (2, (0.25, -0.62, 0.5), (-0.3, 0.1, 0.02), 26),
        "nah4": (1, (-0.62, -0.95, 0.45), (-1.0, -0.45, 0.0), 30),
    }
    for shot in SHOTS:
        if shot in ("uebersicht", "kacheln"):
            bg.inputs["Color"].default_value = (0.5, 0.52, 0.55, 1)
            bg.inputs["Strength"].default_value = 0.7
            sun_d.energy = 3.0
            sun.rotation_euler = (math.radians(40), 0, math.radians(-30))
            spot_d.energy = 0
            if shot == "uebersicht":
                cam_d.lens = 28
                cam.location = (7.6, -13.5, 9.5)
                aim(cam, (7.6, -0.9, 0.0))
            else:
                cam_d.lens = 24
                cam.location = (KX + 7.2, KY - 5.5, 13.0)
                aim(cam, (KX + 7.2, KY + 2.2, 0.0))
        else:
            k, cp, tp, lens = LAMPE[shot]
            ox, oy = POS[k]
            bg.inputs["Color"].default_value = (0.02, 0.022, 0.026, 1)
            bg.inputs["Strength"].default_value = 0.3
            sun_d.energy = 0.0
            cam_d.lens = lens
            cam.location = (ox + cp[0], oy + cp[1], cp[2])
            tgt = (ox + tp[0], oy + tp[1], tp[2])
            aim(cam, tgt)
            spot.location = cam.location + Vector((0.22, 0.0, -0.18))
            aim(spot, tgt)
            dist = (spot.location - Vector(tgt)).length
            spot_d.energy = 380 * (dist / 3.4) ** 2
        scene.render.filepath = os.path.join(OUT, f"{GEB}_boden_{shot}.png")
        log("Render", shot)
        bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"{GEB}_bodenplatten.blend"))
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_mainfile()
log("fertig")

