# ABANDONED · Modulare Wandstuecke fuer das Gebaeude "schule"
# Sieben Stuecke, zwei kachelbare Materialien ("Wand", "Detail") mit je 4096 x 4096 px,
# UV-Massstab 0,25 je Meter (1024 px/m). Export als glTF 2.0 mit gemeinsamen Texturdateien.
# Start: blender -b -P kit_schule.py  (oder mit dem bpy-Modul: python kit_schule.py).
# Das Skript setzt Blender auf Werkseinstellungen zurueck, also nicht in einem offenen Projekt ausfuehren.
import bpy, bmesh, math, random, os, time, json, zlib
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, Quaternion, noise, geometry
from mathutils.bvhtree import BVHTree

T0 = time.time()
def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)

GEB = "schule"
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
SHOTS = [s for s in os.environ.get("SHOTS", "vorne,hinten,lampe1,lampe2,lampe3,lampe4,nah1,nah2").split(",") if s]
SAMPLES = int(os.environ.get("SAMPLES", "64"))
RES = [int(v) for v in os.environ.get("RES", "1920x1080").split("x")]

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("io_scene_gltf2", default_set=True)
scene = bpy.context.scene

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
    """Kachelbares Rauschen (FFT), Pixel = 4 m / NPX. aniso > 1 streckt senkrecht (Laeufe)."""
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

def drip(M, length_m):
    """Laesst Flecken nach unten auslaufen (Zeile 0 = unten)."""
    D = M.copy()
    L = max(1.0, length_m * NPX / 4.0)
    s = 1
    while s < L:
        D = np.maximum(D, np.roll(D, -s, axis=0) * math.exp(-s / (0.6 * L)))
        s *= 2
    return D

def normal_map(hgt_m):
    px = 4.0 / NPX
    dx = (np.roll(hgt_m, -1, 1) - np.roll(hgt_m, 1, 1)) / (2 * px)
    dz = (np.roll(hgt_m, -1, 0) - np.roll(hgt_m, 1, 0)) / (2 * px)
    n = np.dstack([-dx, -dz, np.ones_like(hgt_m)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5                       # OpenGL (+Y), wie glTF es verlangt

def save(name, arr, fmt, color):
    hgt, wid = arr.shape[:2]
    img = bpy.data.images.new(name, wid, hgt, alpha=False)
    rgba = np.ones((hgt, wid, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(arr, 0, 1)
    img.pixels.foreach_set(rgba.ravel())
    ext = ".jpg" if fmt == "JPEG" else ".png"
    img.filepath_raw = os.path.join(TEXDIR, name + ext)
    img.file_format = fmt
    img.save(quality=92) if fmt == "JPEG" else img.save()
    if not color:
        img.colorspace_settings.name = "Non-Color"
    return img

def write_set(prefix, alb, hgt_m, rough, metal):
    n = normal_map(hgt_m)
    orm = np.dstack([np.ones_like(rough), np.clip(rough, 0.03, 1), np.clip(metal, 0, 1)])
    imgs = {"base": save(prefix + "_Grundfarbe", alb, "JPEG", True),
            "normal": save(prefix + "_Normale", n, "PNG", False),
            "rough": save(prefix + "_Rauheit", orm, "PNG", False)}
    log("Textur", prefix, NPX)
    return imgs

def grid_xz(rows=None, z0=0.0):
    n = NPX
    r0, r1 = (0, n) if rows is None else rows
    xs = (np.arange(n, dtype=np.float32) + 0.5) * 4.0 / n
    zs = (np.arange(r0, r1, dtype=np.float32) + 0.5) * 4.0 / n - z0
    return np.repeat(xs[None, :], r1 - r0, 0), np.repeat(zs[:, None], n, 1)

# ---------------- Masse ----------------
W2, H, T2 = 1.9, 3.4, 0.1
TRENN = 1.2                    # Trennlinie: Oberkante der Vertaefelung, verdeckt von der Holzleiste
BW = 0.1                       # Brettbreite: 40 Bretter auf 4 m, Fugen bei x = 0,1 k (am 4-m-Weltraster)
BC = 0.003                     # Fase an jeder Brettkante: V-Fuge 6 mm breit, 3 mm tief
BZ1 = 1.17                     # Bretter vom Boden bis unter die Holzleiste
BT, LT = 0.012, 0.008          # Brettdicke und Lattung dahinter
YB = T2 - BT                   # Rueckseite der Bretter
YM = YB - LT                   # Mauer hinter der Lattung
LATTEN_Z = (0.22, 0.64, 1.06)  # Lattung hinter den Brettern (Mitte, 4 cm hoch)
PUTZ_T = 0.025                 # Putz auf dem Ziegel
EDGE = 0.4                     # Schaeden nie naeher an den Seitenkanten
MELDER_W, MELDER_H, MELDER_T = 0.15, 0.15, 0.05
CH = 0.25 / 3                  # Ziegelschicht in der Textur (Laeuferverband, Ziegel 25 cm)
BAND = 1.0                     # Baender fuer durchgehend abgebildeten Ziegel: 12 Schichten, das Muster laeuft durch
BAND_P = 0.42                  # Baender fuer den Grundputz hinter fehlenden Brettern
U_REV, REV_DZ = 0.125, 0.6     # Fensterlaibung: Stelle im Wandbild ohne Bildraender, Putzzone

# Detail-Atlas: waagerechte Bereiche (Hoehe in Metern), jeder kachelt in U
REG = {
    "ziegel": (0.00, 1.20), "bruch": (1.21, 1.50), "riss": (1.51, 1.60), "latte": (1.61, 1.67), "kerbe": (1.68, 1.74),
    "brett": (1.75, 1.87), "leiste": (1.88, 1.99), "sockel": (2.00, 2.16),
    "holz_24": (2.17, 2.42), "holz_10": (2.43, 2.53), "holz_07": (2.54, 2.61), "holz_05": (2.62, 2.67), "holz_03": (2.68, 2.71),
    "altputz": (2.72, 3.17), "rohr": (3.18, 3.39), "melder": (3.40, 3.60), "glas": (3.61, 3.69),
    "metall_10": (3.70, 3.80), "metall_07": (3.81, 3.88), "metall_03": (3.89, 3.92),
}

# ======================= Texturen =======================
def lin(a, b, t):
    return a * (1 - t) + b * t

# Einfache Strichschrift (Einheiten: Breite 0..2, Hoehe 0..4). Jeder Buchstabe besteht aus Linienzuegen,
# die sich nicht kreuzen; Enden, die an einem anderen Strich ansetzen, werden beim Schnitzen gekuerzt.
GLYPH = {
    "A": [[(0, 0), (1, 4), (2, 0)], [(0.45, 1.5), (1.55, 1.5)]],
    "C": [[(1.9, 3.4), (1.4, 4), (0.6, 4), (0.1, 3.3), (0, 2), (0.1, 0.7), (0.6, 0), (1.4, 0), (1.9, 0.6)]],
    "D": [[(0, 0), (0, 4), (1, 4), (1.7, 3.5), (2, 2.5), (2, 1.5), (1.7, 0.5), (1, 0), (0.35, 0)]],
    "E": [[(2, 4), (0, 4), (0, 0), (2, 0)], [(0, 2), (1.5, 2)]],
    "F": [[(2, 4), (0, 4), (0, 0)], [(0, 2), (1.4, 2)]],
    "H": [[(0, 0), (0, 4)], [(2, 0), (2, 4)], [(0, 2), (2, 2)]],
    "I": [[(1, 0), (1, 4)]],
    "J": [[(1.6, 4), (1.6, 0.8), (1.2, 0.1), (0.6, 0), (0.1, 0.6)]],
    "K": [[(0, 0), (0, 4)], [(2, 4), (0.45, 2), (2, 0)]],
    "L": [[(0, 4), (0, 0), (2, 0)]],
    "M": [[(0, 0), (0, 4), (1, 2), (2, 4), (2, 0)]],
    "N": [[(0, 0), (0, 4), (2, 0), (2, 4)]],
    "O": [[(1.0, 4), (0.3, 3.6), (0, 2.6), (0, 1.4), (0.3, 0.4), (1, 0), (1.7, 0.4), (2, 1.4), (2, 2.6), (1.7, 3.6), (1.25, 3.95)]],
    "P": [[(0, 0), (0, 4), (1.3, 4), (1.9, 3.5), (1.9, 2.5), (1.3, 2), (0.35, 2)]],
    "R": [[(0, 0), (0, 4), (1.3, 4), (1.9, 3.5), (1.9, 2.5), (1.3, 2), (0.35, 2)], [(1.0, 2), (2, 0)]],
    "S": [[(1.9, 3.5), (1.4, 4), (0.6, 4), (0.1, 3.5), (0.2, 2.6), (1, 2.1), (1.8, 1.6), (1.9, 0.6), (1.4, 0), (0.5, 0), (0, 0.5)]],
    "T": [[(0, 4), (2, 4)], [(1, 4), (1, 0)]],
    "U": [[(0, 4), (0, 1), (0.4, 0.2), (1, 0), (1.6, 0.2), (2, 1), (2, 4)]],
    "V": [[(0, 4), (1, 0), (2, 4)]],
    "W": [[(0, 4), (0.5, 0), (1, 2.4), (1.5, 0), (2, 4)]],
    "Y": [[(0, 4), (1, 2), (2, 4)], [(1, 2), (1, 0)]],
    "Z": [[(0, 4), (2, 4), (0, 0), (2, 0)]],
    "1": [[(0.3, 3), (1.2, 4), (1.2, 0)]],
    "2": [[(0, 3.2), (0.4, 3.85), (1, 4), (1.6, 3.8), (1.9, 3.2), (1.7, 2.4), (0, 0), (2, 0)]],
    "3": [[(0, 3.7), (0.7, 4), (1.5, 3.9), (1.9, 3.3), (1.6, 2.4), (0.8, 2.1), (1.6, 1.85), (1.95, 1.2), (1.7, 0.4), (1, 0), (0.2, 0.25)]],
    "7": [[(0, 4), (2, 4), (0.7, 0)]],
    "9": [[(1.6, 2.2), (1.2, 1.9), (0.6, 1.9), (0.1, 2.5), (0.1, 3.4), (0.7, 4), (1.4, 4), (1.9, 3.4), (1.9, 1.2), (1.5, 0.3), (0.9, 0), (0.2, 0.3)]],
    "+": [[(0, 2), (2, 2)], [(1, 3.1), (1, 2)], [(1, 2), (1, 0.9)]],
    "<": [[(1.12, 0.2), (1.75, 1.4), (2, 2.4), (1.9, 3.2), (1.5, 3.6), (1.15, 3.4), (1, 2.9), (0.85, 3.4), (0.5, 3.6),
           (0.1, 3.2), (0, 2.4), (0.25, 1.4), (0.88, 0.2)]],          # Herz, unten offen
}

def text_strokes(text, x0, z0, h, w=None, gap=None, slant=0.0):
    """Linienzuege eines Textes; Buchstabenhoehe h (m), Buchstaben ohne Ueberlappung nebeneinander."""
    w = w if w is not None else h * 0.55
    gap = gap if gap is not None else h * 0.28
    out = []
    x = x0
    for ch in text:
        if ch == " ":
            x += w * 0.8
            continue
        for line in GLYPH[ch]:
            out.append([(x + px / 2 * w + slant * pz / 4 * h, z0 + pz / 4 * h) for px, pz in line])
        x += w + gap
    return out

def raster_lines(S, lines, width, x_wrap=True, rough=0.0, seed=0):
    """Linienzuege (Meter im Bild, Ursprung unten links) als weiche Maske 0..1; kachelt in X."""
    n_r, n_c = S
    px = 4.0 / NPX
    M = np.zeros(S, np.float32)
    rng = np.random.default_rng(seed)
    for line in lines:
        for (ax, az), (bx, bz) in zip(line[:-1], line[1:]):
            wv = width * (1 + rough * (rng.random() - 0.5))
            for sh in ((-4.0, 0.0, 4.0) if x_wrap else (0.0,)):
                x0, x1 = min(ax, bx) + sh - wv * 2, max(ax, bx) + sh + wv * 2
                if x1 < 0 or x0 > 4.0:
                    continue
                c0, c1 = max(0, int(x0 / px)), min(n_c, int(x1 / px) + 2)
                r0, r1 = max(0, int((min(az, bz) - wv * 2) / px)), min(n_r, int((max(az, bz) + wv * 2) / px) + 2)
                if c1 <= c0 or r1 <= r0:
                    continue
                xs = (np.arange(c0, c1, dtype=np.float32) + 0.5) * px - sh
                zs = (np.arange(r0, r1, dtype=np.float32) + 0.5) * px
                PX, PZ = np.meshgrid(xs, zs)
                dx, dz = bx - ax, bz - az
                L2 = dx * dx + dz * dz + 1e-12
                t = np.clip(((PX - ax) * dx + (PZ - az) * dz) / L2, 0, 1)
                d = np.hypot(PX - (ax + t * dx), PZ - (az + t * dz))
                M[r0:r1, c0:c1] = np.maximum(M[r0:r1, c0:c1], sm(wv, wv * 0.35, d))
    return M

def pdist(X, c, period=4.0):
    """Abstand zu c auf einem Ring der Laenge period."""
    return np.abs(np.mod(X - c + period / 2, period) - period / 2)

def rect_sdf(X, Z, x0, x1, z0, z1):
    """Vorzeichenbehafteter Abstand zu einem Rechteck im kachelnden Bild (innen positiv)."""
    w = x1 - x0
    lx = np.mod(X - x0, 4.0)
    inx = lx <= w
    din = np.minimum(np.minimum(lx, w - lx), np.minimum(Z - z0, z1 - Z))
    dxo = np.where(inx, 0.0, np.minimum(lx - w, 4.0 - lx))
    dzo = np.maximum(0.0, np.maximum(z0 - Z, Z - z1))
    return np.where(inx & (Z >= z0) & (Z <= z1), din, -np.hypot(dxo, dzo))

def tex_wand():
    n = NPX
    X, Z = grid_xz()
    S = (n, n)
    rng = np.random.default_rng(71)
    # ================= Vertaefelung bis 1,2 m: 40 senkrechte Bretter je 10 cm, dunkel gebeizt =================
    col = np.floor(X / BW).astype(np.int32) % 40
    fx = X / BW - np.floor(X / BW)
    dj = np.minimum(fx, 1 - fx) * BW
    tone = rng.normal(0, 0.08, 40).astype(np.float32)
    warm = rng.normal(0, 0.06, 40).astype(np.float32)
    # Maserung: Jahresringe (5..9 mm). Stehende Jahresringe als feine Linien, liegende als Fladern (Bogen), wie bei
    # einem Brett, das nicht ganz parallel zum Kern geschnitten ist: Ringradius r = sqrt(dx^2 + (d0 + k z)^2)
    freq = rng.uniform(110, 200, 40).astype(np.float32)
    phase = rng.uniform(0, 50, 40).astype(np.float32)
    cath = (rng.random(40) < 0.45)
    cxo = rng.uniform(-0.02, 0.02, 40).astype(np.float32)
    d0 = rng.uniform(0.03, 0.12, 40).astype(np.float32)
    kz = (rng.uniform(0.012, 0.035, 40) * rng.choice([-1, 1], 40)).astype(np.float32)
    z0b = rng.uniform(0.0, 1.2, 40).astype(np.float32)
    wav = fr(S, 2.2, 201, aniso=8.0)
    wav2 = fr(S, 1.7, 202, aniso=4.0)
    dxl = (fx - 0.5) * BW - cxo[col]
    dep = np.abs(d0[col] + kz[col] * (Z - z0b[col])) + 0.004
    u_c = np.sqrt(dxl * dxl + dep * dep) * freq[col]
    u_s = X * freq[col] * 0.9
    u = np.where(cath[col], u_c, u_s) + phase[col] + 0.5 * wav + 0.12 * wav2
    fu = u - np.floor(u)
    late = sm(0.62, 0.9, fu) * sm(1.0, 0.94, fu) * (0.55 + 0.45 * sm(-1.0, 1.0, fr(S, 1.4, 239, aniso=6.0)))
    fib = fr(S, 0.35, 203, aniso=25.0, sigma_m=0.0004)
    pores = sm(1.9, 2.6, fr(S, 0.2, 204, aniso=14.0, sigma_m=0.0005))
    knot_r = np.full(S, 9.0, np.float32)
    for k in range(9):                                   # einzelne Aeste
        kx, kz_ = rng.uniform(0, 4), rng.uniform(0.15, 1.1)
        kx = (math.floor(kx / BW) + rng.uniform(0.3, 0.7)) * BW
        d = np.hypot(np.mod(X - kx + 2, 4) - 2, (Z - kz_) * 0.55)
        knot_r = np.minimum(knot_r, d / rng.uniform(0.008, 0.016))
    knot = sm(1.0, 0.6, knot_r)
    late = np.maximum(late, sm(0.3, 0.95, np.sin(knot_r * 6.0)) * sm(3.0, 1.0, knot_r))
    base = hexc("#4c3424") * (1 + tone[col] + 0.05 * fib)[..., None]
    base = base * np.stack([1 + warm[col], 1 + 0.2 * warm[col], 1 - warm[col]], -1)
    wood = mix(base, hexc("#24170f"), 0.55 * late)
    wood = mix(wood, hexc("#1d130c"), 0.7 * knot)
    wood = wood * (1 - 0.25 * pores)[..., None]
    # abgegriffen in Stuhllehnen- und Hand-Hoehe, Schrammen, eingeritzte Buchstaben, Staub in Fugennaehe
    wear = sm(0.58, 0.72, Z) * sm(1.06, 0.92, Z) * sm(-0.4, 1.2, fr(S, 1.2, 205) + 0.6 * fr(S, 0.5, 206, aniso=0.2))
    wear = np.clip(wear + 0.5 * sm(1.6, 2.4, fr(S, 0.7, 207, aniso=0.15)) * sm(0.3, 0.5, Z) * sm(1.16, 1.0, Z), 0, 1)
    segs = []
    for k in range(520):                                 # Schrammen: kurze, meist schraege Striche
        x0, z0 = rng.uniform(0, 4), rng.uniform(0.2, 1.15)
        ang = rng.normal(0.0, 0.5) + (math.pi / 2 if rng.random() < 0.25 else 0.0)
        L = rng.uniform(0.015, 0.14) * (1.0 if rng.random() < 0.85 else 2.5)
        segs.append([(x0, z0), (x0 + L * math.cos(ang), min(1.17, z0 + L * math.sin(ang)))])
    scr = raster_lines(S, segs, 0.0009, rough=0.8, seed=208) * sm(0.6, 1.4, fr(S, 0.9, 209) + 1.2)
    carve = []
    for txt, x0, z0, h, sl in (("ANNA", 0.33, 0.86, 0.035, 0.15), ("7A", 1.12, 0.97, 0.04, 0.0), ("TK+LS", 2.31, 0.78, 0.03, -0.1),
                               ("1979", 3.13, 0.92, 0.032, 0.1), ("JENS", 1.72, 0.55, 0.028, 0.05), ("DOOF", 3.62, 0.66, 0.03, -0.05)):
        carve += text_strokes(txt, x0, z0, h, slant=sl)
    carve += [[(3.3 + 0.012 * k, 1.04), (3.303 + 0.012 * k, 1.085)] for k in range(4)] + [[(3.295, 1.045), (3.345, 1.08)]]
    carv = raster_lines(S, carve, 0.0011, rough=0.5, seed=210)
    dent = sm(2.3, 2.8, fr(S, 0.3, 211, sigma_m=0.002)) * sm(0.2, 0.5, Z)
    grime = np.clip(sm(0.25, 0.0, Z) + 0.45 * sm(0.6, 2.4, fr(S, 1.3, 212)) + 0.5 * sm(0.006, 0.0025, dj), 0, 1)
    dust = sm(0.0, 1.5, fr(S, 1.4, 213)) * 0.5
    worn = mix(wood, hexc("#6e4f37") * (0.9 + 0.1 * fib[..., None]), 0.55 * wear)
    worn = mix(worn, hexc("#8a6a4c"), 0.6 * np.clip(scr + carv, 0, 1))
    worn = mix(worn, hexc("#3a3128"), 0.45 * grime)
    a_w = mix(worn, hexc("#6d665a"), 0.18 * dust)
    h_w = 0.00012 * late + 0.00004 * fib - 0.00025 * scr - 0.0006 * carv - 0.0003 * dent - 0.0003 * knot
    r_w = np.clip(0.42 + 0.06 * fib + 0.22 * wear + 0.2 * np.clip(scr + carv, 0, 1) + 0.2 * grime + 0.15 * dust, 0, 1)
    # ================= Putz ab 1,2 m: vergilbtes Creme, Bilderflecken, Klebestreifen, Kreide =================
    big = fr(S, 1.8, 221)
    mid = fr(S, 1.2, 222)
    grain = fr(S, 0.3, 223, sigma_m=0.0006)
    brush = fr(S, 0.6, 224, aniso=0.25)
    yel = np.clip(0.2 + 0.7 * sm(1.3, 3.4, Z) + 0.12 * big, 0, 1)
    clean = np.zeros(S, np.float32)
    dline = np.zeros(S, np.float32)
    # verblasste Flaechen abgehaengter Bilder: Plakate (Klebestreifen), Bilderrahmen (Nagel), eine Uhr (rund)
    rects = [(0.78, 1.22, 1.45, 1.98, "plakat"), (2.8, 3.2, 1.6, 1.95, "bild"), (1.72, 2.36, 2.52, 2.98, "bild"),
             (0.15, 0.57, 2.62, 3.0, "plakat")]
    nails = []
    tapes = []
    for x0, x1, z0, z1, kind in rects:
        sd = rect_sdf(X, Z, x0, x1, z0, z1)
        soft = 0.012 if kind == "plakat" else 0.004
        clean = np.maximum(clean, sm(-soft, soft, sd) * (0.45 if kind == "plakat" else 0.55))
        if kind == "bild":
            dline = np.maximum(dline, sm(0.006, 0.0, np.abs(Z - z1)) * (np.mod(X - x0, 4) <= x1 - x0))
            nails.append(((x0 + x1) / 2, z1 + rng.uniform(0.05, 0.12)))
        else:
            for cx, cz, sx, sz in ((x0, z0, 1, 1), (x1, z0, -1, 1), (x0, z1, 1, -1), (x1, z1, -1, -1)):
                if rng.random() < 0.85:
                    a = math.atan2(sz, sx) + rng.normal(0, 0.25)
                    tapes.append((cx + sx * 0.008, cz + sz * 0.008, a, rng.uniform(0.04, 0.06), rng.random() < 0.5))
    cx_, cz_, cr = 3.62, 2.78, 0.16                       # runder Fleck der Schuluhr
    dd = np.hypot(pdist(X, cx_), Z - cz_)
    clean = np.maximum(clean, sm(cr + 0.006, cr - 0.006, dd) * 0.45)
    nails.append((cx_, cz_ + 0.11))
    for k in range(9):                                    # einzelne Klebestreifen und Duebelloecher
        x, z = rng.uniform(0, 4), rng.uniform(1.35, 2.3)
        if 0.3 < x < 0.7:
            x += 0.5
        tapes.append((x, z, rng.uniform(0, math.pi), rng.uniform(0.03, 0.07), rng.random() < 0.3))
        nails.append((rng.uniform(0, 4), rng.uniform(1.4, 3.1)))
    tape = np.zeros(S, np.float32)
    paper = np.zeros(S, np.float32)
    pap_n = sm(0.2, 0.9, fr(S, 0.6, 225))
    for x, z, a, L, pap in tapes:
        ca, sa = math.cos(a), math.sin(a)
        lx = (np.mod(X - x + 2, 4) - 2) * ca + (Z - z) * sa
        lz = -(np.mod(X - x + 2, 4) - 2) * sa + (Z - z) * ca
        m = sm(0.0015, 0.0, np.abs(lz) - 0.0095) * sm(0.002, 0.0, np.abs(lx - L / 2) - L / 2)
        tape = np.maximum(tape, m)
        if pap:
            paper = np.maximum(paper, m * pap_n * sm(L * 0.3, L * 0.6, lx))
    nail = np.zeros(S, np.float32)
    for x, z in nails:
        d = np.hypot(pdist(X, x), Z - z)
        nail = np.maximum(nail, sm(0.0032, 0.0022, d))
    # Kreide: Wischspuren in Greifhoehe, ein paar Kritzeleien, Staub in Schwaden
    chalk = sm(1.7, 2.7, fr(S, 0.9, 226, aniso=0.2) + 0.8 * fr(S, 1.4, 227)) * sm(1.25, 1.4, Z) * sm(2.1, 1.7, Z)
    doodle = text_strokes("JA", 3.42, 1.52, 0.07, slant=0.2) + text_strokes("MATHE", 1.3, 1.62, 0.05, slant=-0.15)
    doodle += [[(2.55 + 0.03 * math.cos(t * 0.5) * (1 + t * 0.12), 1.48 + 0.03 * math.sin(t * 0.5) * (1 + t * 0.12)) for t in range(28)]]
    doodle += [[(0.42 + 0.025 * k, 1.36), (0.432 + 0.025 * k, 1.44)] for k in range(4)] + [[(0.41, 1.37), (0.52, 1.43)]]
    chalk_l = raster_lines(S, doodle, 0.0022, rough=0.6, seed=228) * sm(-0.6, 0.8, fr(S, 0.4, 229))
    chalk = np.clip(np.maximum(chalk * 0.45, chalk_l * 0.7), 0, 1)
    # Wasserflecken mit Raendern und Laeufern von der Decke, feine Risse, abblaetternde Farbe, Schrammen ueber der Leiste
    wf = fr(S, 1.6, 230) + 1.7 * sm(2.6, 3.4, Z) - 1.85
    stain = sm(0.0, 0.5, wf)
    tide = sm(0.04, 0.0, np.abs(wf - 0.05)) * sm(2.3, 2.8, Z)
    run = np.clip(drip(sm(0.3, 0.9, wf) * sm(1.6, 2.4, fr(S, 1.0, 231, aniso=10.0)), 0.9), 0, 1) * 0.35
    cr_n = fr(S, 1.25, 232)
    crack = sm(0.022, 0.006, np.abs(cr_n)) * sm(0.6, 1.6, fr(S, 1.4, 233)) * sm(1.3, 1.6, Z)
    flake = sm(1.8, 2.3, fr(S, 0.8, 234) + 0.5 * stain)
    scuff = sm(1.6, 2.4, fr(S, 0.7, 235, aniso=0.12)) * sm(1.24, 1.26, Z) * sm(1.5, 1.3, Z)
    pl = mix(hexc("#d7cdaa"), hexc("#c0ad7f"), yel) * (0.95 + 0.025 * mid + 0.015 * grain + 0.01 * brush)[..., None]
    grime = np.clip(sm(-0.2, 1.8, fr(S, 1.5, 236) + 0.9 * sm(1.6, 1.25, Z) + 0.7 * sm(2.7, 3.4, Z)), 0, 1)
    smudge = sm(1.0, 2.2, fr(S, 0.8, 237) + 0.6 * fr(S, 1.3, 238)) * sm(2.3, 1.6, Z)
    pl = mix(pl, hexc("#978a6e"), 0.4 * grime * (1 - 0.6 * clean))
    pl = mix(pl, hexc("#6f6656"), 0.35 * smudge)
    pl = mix(pl, hexc("#ddd5b9") * (0.97 + 0.02 * grain[..., None]), clean)
    pl = mix(pl, hexc("#8e8064"), 0.5 * dline)
    keep = 1 - 0.75 * clean                              # hinter Bildern und Plakaten blieb die Wand sauberer
    pl = mix(pl, pl * hexc("#c9b58b"), 0.5 * stain * keep)
    pl = mix(pl, hexc("#8a6f45"), 0.4 * tide * keep)
    pl = mix(pl, pl * hexc("#b39d72"), run * keep)
    pl = mix(pl, hexc("#a9ad98") * (0.95 + 0.05 * grain[..., None]), flake)
    pl = mix(pl, hexc("#6a604f"), 0.75 * crack)
    pl = mix(pl, hexc("#6f6a60"), 0.55 * scuff)
    pl = mix(pl, hexc("#bf9a52") * (0.95 + 0.05 * grain[..., None]), 0.55 * tape)
    pl = mix(pl, hexc("#ddd6c2"), 0.85 * paper)
    pl = mix(pl, hexc("#ece9df"), chalk)
    pl = mix(pl, hexc("#3b332b"), 0.85 * nail)
    h_p = 0.0005 * big + 0.0002 * grain + 0.00008 * brush - 0.0006 * crack + 0.0003 * flake + 0.00012 * tape + 0.0002 * paper \
        - 0.003 * nail
    r_p = np.clip(0.83 + 0.04 * big - 0.15 * stain - 0.4 * tape + 0.08 * chalk + 0.05 * flake + 0.05 * grime, 0, 1)
    up = (Z >= TRENN)
    alb = np.where(up[..., None], pl, a_w)
    hgt = np.where(up, h_p, h_w)
    rough = np.where(up, r_p, r_w)
    return write_set(f"T_{GEB}_Wand", alb, hgt, rough, np.zeros(S, np.float32))

def tex_detail():
    n = NPX
    alb = np.zeros((n, n, 3), np.float32)
    hgt = np.zeros((n, n), np.float32)
    rgh = np.full((n, n), 0.85, np.float32)
    met = np.zeros((n, n), np.float32)
    def region(name):
        z0, z1 = REG[name]
        r0, r1 = int(round(z0 * n / 4)), int(round(z1 * n / 4))
        X, Z = grid_xz((r0, r1), z0)
        return slice(r0, r1), X, Z, (r1 - r0, n), z1 - z0
    seed = [700]
    def nz(shape, beta, aniso=1.0, sigma_m=0.0):
        seed[0] += 1
        return fr(shape, beta, seed[0], aniso, sigma_m)
    # ---- Ziegel unter dem Putz (Laeuferverband, Kalkmoertel, Putzreste) ----
    sl, X, Z, S, hh = region("ziegel")
    course = np.floor(Z / CH).astype(np.int32)
    xo = X + (course % 2) * 0.125
    bi = np.floor(xo / 0.25).astype(np.int32) % 16
    fx, fz = xo / 0.25 - np.floor(xo / 0.25), Z / CH - course
    e = np.minimum(np.minimum(fx, 1 - fx) * 0.25, np.minimum(fz, 1 - fz) * CH)
    jw = 0.0055 + 0.0025 * sm(-1, 2, nz(S, 0.7))
    joint = e < jw
    rng = np.random.default_rng(51)
    C = int(course.max()) + 2
    ch = rng.random((C, 16)).astype(np.float32)
    tint = rng.normal(0, 0.05, (C, 16)).astype(np.float32)
    cc = ch[course, bi]
    bcol = np.where((cc < 0.5)[..., None], hexc("#7a4a3b"), np.where((cc < 0.75)[..., None], hexc("#8c5c4a"),
                    np.where((cc < 0.93)[..., None], hexc("#613e33"), hexc("#46302a"))))
    bcol = mix(bcol, hexc("#6d665d"), 0.22)
    bcol = bcol * (1 + tint[course, bi])[..., None] * (0.9 + 0.08 * nz(S, 0.9)[..., None])
    pits = sm(1.6, 2.3, nz(S, 0.15, sigma_m=0.001))
    bcol = bcol * (1 - 0.35 * pits)[..., None]
    mortar = hexc("#a39a85") * (0.88 + 0.1 * nz(S, 1.0)[..., None])
    a = np.where(joint[..., None], mortar, bcol)
    salt = sm(1.7, 2.5, nz(S, 1.2))
    damp = sm(0.0, 1.6, nz(S, 1.4))
    a = mix(a, hexc("#d8d2c2"), 0.45 * salt)
    a = a * (1 - 0.22 * damp)[..., None]
    rest = sm(1.0, 1.4, nz(S, 1.2) + 0.5 * nz(S, 0.7))
    a = mix(a, hexc("#b9b096") * (0.85 + 0.1 * nz(S, 0.9)[..., None]), 0.85 * rest)
    a = a * (1 - 0.25 * sm(0.2, 2.2, nz(S, 1.3)))[..., None]
    alb[sl] = a
    hgt[sl] = 0.003 * rest + np.where(joint, -0.009, -0.004 * (1 - sm(jw, jw + 0.004, e))) - 0.0012 * pits + 0.0004 * nz(S, 0.8)
    rgh[sl] = np.where(joint, 0.93, 0.85) - 0.25 * damp
    # ---- Bruchflaeche: Ziegelsplitt, Moertel, Putz; feinkoernig, damit einzeln gesetzte Flaechen keine Naehte zeigen ----
    sl, X, Z, S, hh = region("bruch")
    m = nz(S, 0.55, sigma_m=0.004)
    frag = sm(0.1, 0.6, m)
    grit = nz(S, 0.2, sigma_m=0.0012)
    cav = sm(1.2, 1.9, nz(S, 0.35, sigma_m=0.0025))
    plast = sm(1.1, 1.7, nz(S, 0.6, sigma_m=0.003))
    b = mix(hexc("#6f685b"), hexc("#7c4a3c") * (0.85 + 0.2 * nz(S, 0.5)[..., None]), 0.55 * frag)
    b = mix(b, hexc("#b3aa90"), 0.6 * plast)
    b = mix(b, hexc("#8b8679"), 0.35 * sm(-0.5, 1.5, nz(S, 1.2)))
    b = b * (0.9 + 0.1 * grit)[..., None] * (1 - 0.6 * cav)[..., None]
    alb[sl] = b
    hgt[sl] = 0.003 * m + 0.0012 * grit - 0.005 * cav + 0.0015 * frag
    rgh[sl] = 0.93
    # ---- Rissflanken ----
    sl, X, Z, S, hh = region("riss")
    q = nz(S, 0.9)
    alb[sl] = mix(hexc("#2a2622"), hexc("#7a705e"), sm(-0.8, 1.6, q)) * (0.85 + 0.15 * nz(S, 0.4)[..., None])
    hgt[sl] = 0.002 * q + 0.001 * nz(S, 0.5)
    rgh[sl] = 0.92
    # ---- Holzlatten (Putztraeger und Lattung): rohes, vergrautes Nadelholz, Putzreste, Nagelrost ----
    sl, X, Z, S, hh = region("latte")
    g = nz(S, 0.5, aniso=0.04) + 0.5 * nz(S, 0.25, aniso=0.02, sigma_m=0.0004)
    saw = 0.5 + 0.5 * np.sin(2 * math.pi * X / 0.0045 + 1.5 * nz(S, 1.4, aniso=0.3))
    l = mix(hexc("#6f604c"), hexc("#94826a"), sm(-1.2, 1.4, g)) * (0.92 + 0.06 * saw[..., None])
    lump = sm(1.3, 1.9, nz(S, 0.9))
    l = mix(l, hexc("#c7bea4") * (0.9 + 0.08 * nz(S, 0.6)[..., None]), 0.85 * lump)
    rs = sm(2.0, 2.6, nz(S, 0.5)) * sm(0.0, 1.0, nz(S, 1.2))
    l = mix(l, hexc("#5c3a24"), 0.7 * rs)
    alb[sl] = l * (1 - 0.25 * sm(0.4, 2.2, nz(S, 1.3)))[..., None]
    hgt[sl] = 0.0004 * g + 0.0002 * saw + 0.0015 * lump
    rgh[sl] = 0.9
    # ---- frisch angeritztes Holz unter der Beize (Schnitzereien, Bruchenden), mit Schmutz ----
    sl, X, Z, S, hh = region("kerbe")
    g = nz(S, 0.5, aniso=0.08) + 0.4 * nz(S, 0.2, aniso=0.05, sigma_m=0.0003)
    k = mix(hexc("#7b5b3f"), hexc("#a5835c"), sm(-1.3, 1.4, g))
    k = mix(k, hexc("#3e3023"), 0.55 * sm(0.0, 1.8, nz(S, 1.1)))
    alb[sl] = k
    hgt[sl] = 0.0005 * g
    rgh[sl] = 0.86
    # ---- Holz der Vertaefelung (Fasen, Kanten, Rueckseite der losen Bretter), dazu Leiste und Sockel ----
    def dark_wood(S, X, Z, base="#4a3323", lines="#25170f", along=0.05):
        g1 = nz(S, 1.2, aniso=along * 4)
        rr = np.sin(2 * math.pi * (Z / 0.0045 + 0.9 * g1)) * 0.5 + 0.5
        f = nz(S, 0.3, aniso=along, sigma_m=0.0004)
        w = mix(hexc(base) * (0.92 + 0.08 * nz(S, 1.4)[..., None]), hexc(lines), 0.5 * sm(0.55, 0.95, rr))
        return w * (1 + 0.05 * f)[..., None], 0.00008 * rr + 0.00004 * f
    sl, X, Z, S, hh = region("brett")
    w, h_ = dark_wood(S, X, Z)
    dirt = sm(0.2, 2.0, nz(S, 1.2))
    alb[sl] = mix(w, hexc("#3a3128"), 0.4 * dirt)
    hgt[sl] = h_
    rgh[sl] = 0.5 + 0.25 * dirt
    sl, X, Z, S, hh = region("leiste")
    w, h_ = dark_wood(S, X, Z)
    s_ = Z - 0.002
    nose = sm(0.005, 0.0, np.minimum(np.abs(s_ - 0.040), np.abs(s_ - 0.068))) * sm(-0.3, 1.0, nz(S, 0.9))
    topw = sm(0.066, 0.078, s_) * sm(0.3, 1.5, nz(S, 1.0, aniso=0.2))
    nicks = sm(1.9, 2.4, nz(S, 0.3, sigma_m=0.0008)) * sm(0.035, 0.045, s_) * sm(0.075, 0.065, s_)
    dust = sm(0.08, 0.092, s_) * 0.6
    w = mix(w, hexc("#7b5a3c"), 0.6 * np.clip(nose + 0.6 * topw + nicks, 0, 1))
    alb[sl] = mix(w, hexc("#6c665a"), dust)
    hgt[sl] = h_ - 0.0006 * nicks
    rgh[sl] = np.clip(0.42 + 0.25 * nose + 0.2 * topw + 0.4 * dust, 0, 1)
    sl, X, Z, S, hh = region("sockel")
    w, h_ = dark_wood(S, X, Z)
    s_ = Z - 0.002
    floor = sm(0.035, 0.0, s_) + 0.5 * sm(0.07, 0.0, s_) * sm(0.0, 1.5, nz(S, 1.1))
    shoe = sm(1.4, 2.3, nz(S, 0.7, aniso=0.07)) * sm(0.0, 0.03, s_) * sm(0.1, 0.05, s_)
    chip = sm(1.9, 2.4, nz(S, 0.35, sigma_m=0.001)) * (sm(0.09, 0.1, s_) + sm(0.02, 0.0, s_))
    topw = sm(0.093, 0.105, s_) * sm(0.0, 1.5, nz(S, 1.1))
    w = mix(w, hexc("#7a5b3e"), 0.55 * np.clip(chip + 0.6 * topw, 0, 1))
    w = mix(w, hexc("#17120e"), 0.65 * shoe)
    alb[sl] = mix(w, hexc("#4b443a"), 0.6 * np.clip(floor, 0, 1))
    hgt[sl] = h_ - 0.0006 * chip
    rgh[sl] = np.clip(0.48 + 0.3 * floor + 0.2 * chip - 0.1 * shoe, 0, 1)
    # ---- dunkles Holz fuer Zarge, Fensterrahmen, Baenke: Kanten heller abgegriffen, ganz schmale Flaechen = Kante ----
    for name in ("holz_24", "holz_10", "holz_07", "holz_05", "holz_03"):
        sl, X, Z, S, hh = region(name)
        w, h_ = dark_wood(S, X, Z, base="#3e2a1c", lines="#1f140c")
        d = np.minimum(Z, hh - Z)
        edge = 1.0 if name == "holz_03" else sm(0.009, 0.002, d)
        edge = edge * sm(-0.6, 0.8, nz(S, 1.0, aniso=0.2))
        scr = sm(2.1, 2.8, nz(S, 0.5, aniso=0.07))
        dirt = sm(0.4, 2.2, nz(S, 1.3))
        w = mix(w, hexc("#7d5c3d") * (0.9 + 0.1 * nz(S, 0.5)[..., None]), 0.75 * edge)
        w = mix(w, hexc("#8f7254"), 0.45 * scr)
        alb[sl] = mix(w, hexc("#433a30"), 0.35 * dirt)
        hgt[sl] = h_ - 0.00015 * scr
        rgh[sl] = np.clip(0.45 - 0.12 * edge + 0.2 * scr + 0.2 * dirt, 0, 1)
    # ---- Grundputz hinter der Vertaefelung, Putzbrocken: rauer Kalkputz, Staub, Spinnweben-Schatten ----
    sl, X, Z, S, hh = region("altputz")
    coarse = nz(S, 0.25, sigma_m=0.0012)
    p = hexc("#857b67") * (0.88 + 0.07 * nz(S, 1.4)[..., None] + 0.05 * coarse[..., None])
    sand = sm(1.5, 2.4, coarse)
    p = mix(p, hexc("#5d564b"), 0.45 * sand)
    blot = sm(0.0, 1.8, nz(S, 1.3))
    p = mix(p, hexc("#4b453b"), 0.55 * blot)
    runs = sm(0.8, 2.2, nz(S, 0.9, aniso=8.0))
    p = mix(p, hexc("#3e382f"), 0.4 * runs)
    mold = sm(1.9, 2.5, nz(S, 0.35, sigma_m=0.002)) * sm(0.4, 1.4, nz(S, 1.2))
    p = mix(p, hexc("#2c3026"), 0.7 * mold)
    paint = sm(1.7, 2.1, nz(S, 1.0))
    p = mix(p, hexc("#b9ad8a"), 0.5 * paint)
    alb[sl] = p
    hgt[sl] = 0.0012 * coarse + 0.001 * nz(S, 0.8) + 0.0004 * paint
    rgh[sl] = 0.93 - 0.05 * paint
    # ---- Heizungsrohre: Heizkoerperlack (Elfenbein), Abplatzer mit Rost, Staub ----
    sl, X, Z, S, hh = region("rohr")
    br = nz(S, 0.6, aniso=0.08)
    pc_ = hexc("#d3c8a6") * (0.92 + 0.04 * br[..., None] + 0.04 * nz(S, 1.4)[..., None])
    yell = sm(-0.5, 1.5, nz(S, 1.5))
    pc_ = mix(pc_, hexc("#bba878"), 0.5 * yell)
    chips = sm(1.8, 2.3, nz(S, 0.45, sigma_m=0.0015))
    rust = np.clip(chips * sm(-0.5, 0.8, nz(S, 0.6)) + 0.6 * sm(1.8, 2.6, nz(S, 0.9)), 0, 1)
    under = mix(hexc("#4e4c47"), hexc("#7a4527"), sm(-0.5, 1.0, nz(S, 0.7)))
    pc_ = mix(pc_, under, chips)
    pc_ = mix(pc_, hexc("#7e5233"), 0.6 * rust * (1 - chips))
    dust = sm(0.2, 1.8, nz(S, 1.2))
    alb[sl] = mix(pc_, hexc("#776f60"), 0.3 * dust)
    hgt[sl] = -0.00035 * chips + 0.00004 * br
    rgh[sl] = np.clip(0.48 + 0.3 * chips + 0.2 * rust + 0.2 * dust, 0, 1)
    met[sl] = 0.5 * chips * (1 - sm(0.3, 0.8, rust))
    # ---- Feuermelder: rot lackiertes Gehaeuse; Vorderseite einmalig bei U 0,5 (Beschriftung, Druckknopf hinter der Scheibe) ----
    sl, X, Z, S, hh = region("melder")
    red = hexc("#8f241b") * (0.9 + 0.08 * nz(S, 1.2)[..., None])
    scr = np.clip(sm(2.1, 2.9, nz(S, 0.6, aniso=0.1)), 0, 1)
    fade = sm(0.0, 1.5, nz(S, 1.4))
    a = mix(red, hexc("#a8544a"), 0.35 * fade)
    a = mix(a, hexc("#c9bfb0"), 0.45 * scr)
    a = mix(a, hexc("#3c302a"), 0.35 * sm(0.4, 2.2, nz(S, 1.3)))
    h_ = -0.0002 * scr
    r_ = 0.45 + 0.25 * scr + 0.15 * fade
    W, HH = MELDER_W, MELDER_H
    px, pz = X - 2.0, Z - 0.005
    inside = (px >= 0) & (px < W) & (pz >= 0) & (pz < HH)
    win = inside & (px > 0.025) & (px < W - 0.025) & (pz > 0.028) & (pz < 0.108)
    plate = hexc("#d6d2c6") * (1 - 0.25 * sm(0.3, 2.2, nz(S, 1.3)))[..., None]
    bc = np.hypot(px - W / 2, pz - 0.062)
    button = bc < 0.016
    ring = (bc >= 0.016) & (bc < 0.02)
    lines = np.zeros(S, bool)
    for zz in (0.092, 0.098):
        lines |= (np.abs(pz - zz) < 0.0012) & (np.abs(px - W / 2) < 0.04) & (np.mod(px * 260, 1.0) < 0.75)
    for zz in (0.034, 0.039):
        lines |= (np.abs(pz - zz) < 0.001) & (np.abs(px - W / 2) < 0.03) & (np.mod(px * 300, 1.0) < 0.7)
    fp = np.where(win[..., None], plate, a)
    fp = np.where((win & ring)[..., None], hexc("#4d4842"), fp)
    fp = np.where((win & button)[..., None], hexc("#1b1a19") * (0.8 + 0.4 * sm(0.016, 0.0, bc))[..., None], fp)
    fp = np.where((win & lines)[..., None], hexc("#3b3733"), fp)
    lw = 11 * 0.0058 + 10 * 0.0024
    label = text_strokes("FEUERMELDER", 2.0 + (W - lw) / 2, 0.005 + 0.118, 0.0105, w=0.0058, gap=0.0024)
    lab = raster_lines(S, label, 0.0011, x_wrap=False) * inside
    fp = mix(fp, hexc("#e2ddd2"), 0.9 * lab)
    screws = np.zeros(S, bool)
    for sx, sz in ((0.012, 0.012), (W - 0.012, 0.012), (0.012, HH - 0.012), (W - 0.012, HH - 0.012)):
        screws |= np.hypot(px - sx, pz - sz) < 0.003
    fp = np.where((inside & screws)[..., None], hexc("#77736b"), fp)
    a = np.where(inside[..., None], fp, a)
    h_ = np.where(inside, np.where(win & button, 0.002, 0.0) + 0.0003 * lab - 0.0005 * (win & lines) + 0.0006 * screws, h_)
    r_ = np.where(inside, np.where(win, np.where(button, 0.35, 0.55), 0.5 + 0.2 * scr), r_)
    alb[sl], hgt[sl], rgh[sl] = a, h_, r_
    met[sl] = np.where(inside & screws, 0.8, 0.0)
    # ---- Glas der eingeschlagenen Scheibe ----
    sl, X, Z, S, hh = region("glas")
    gq = nz(S, 1.0)
    alb[sl] = mix(hexc("#1f2a27"), hexc("#3f4f49"), sm(-1, 1.5, gq)) * (1 - 0.3 * sm(0.5, 2.0, nz(S, 1.2)))[..., None]
    hgt[sl] = 0.00005 * gq
    rgh[sl] = 0.08 + 0.2 * sm(0.5, 2.2, nz(S, 1.2))
    # ---- Stahl (Schellen, Halter, Hammer, Kette, Leerrohr): grau, Lackreste, Rost ----
    for name in ("metall_10", "metall_07", "metall_03"):
        sl, X, Z, S, hh = region(name)
        rust = np.clip(sm(1.0, 2.2, nz(S, 0.8)) + 0.5 * sm(0.012, 0.0, np.minimum(Z, hh - Z)), 0, 1)
        st = hexc("#6f706c") * (0.9 + 0.08 * nz(S, 1.3)[..., None])
        st = mix(st, hexc("#c9bf9f"), 0.35 * sm(0.3, 1.6, nz(S, 1.1)))
        rc = mix(hexc("#5c3220"), hexc("#8d532d"), sm(-1, 1.5, nz(S, 0.6)))
        alb[sl] = mix(st, rc, 0.8 * rust)
        hgt[sl] = 0.0002 * rust * nz(S, 0.4)
        rgh[sl] = 0.5 + 0.4 * rust
        met[sl] = 0.7 * (1 - rust)
    used = np.zeros(n, bool)
    for z0, z1 in REG.values():
        used[int(round(z0 * n / 4)):int(round(z1 * n / 4))] = True
    rows = np.arange(n)
    ur = rows[used]
    src = ur[np.clip(np.searchsorted(ur, rows), 0, len(ur) - 1)]
    lo = ur[np.clip(np.searchsorted(ur, rows) - 1, 0, len(ur) - 1)]
    src = np.where(np.abs(lo - rows) < np.abs(src - rows), lo, src)
    for arr in (alb, hgt, rgh, met):
        arr[~used] = arr[src[~used]]
    return write_set(f"T_{GEB}_Detail", alb, hgt, rgh, met)

log("Texturen ...")
IMG_W = tex_wand()
IMG_D = tex_detail()

def make_material(name, imgs):
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
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m

MAT_W = make_material(f"M_{GEB}_Wand", IMG_W)
MAT_D = make_material(f"M_{GEB}_Detail", IMG_D)

# ======================= Geometrie =======================
# UV-Regeln je Flaeche (werden am Ende vergeben)
R_KEEP, R_WM, R_WP, R_TOP, R_ENDX, R_REVX, R_REVZ, R_PLAN, R_METAL, R_BAND, R_BOXFRONT, R_SHARD, R_PLANAX, R_PLANFIX, \
    R_HOLZ, R_VFIX = range(16)
PLAN_REG = list(REG.keys())

def wall_u(x, side):
    return UVS * x + 0.5 if side < 0 else -UVS * x

class Piece:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.rule = self.bm.faces.layers.int.new("rule")
        self.reg = self.bm.faces.layers.int.new("reg")
        self.par = self.bm.faces.layers.float_vector.new("par")
        self.rng = random.Random(zlib.crc32(name.encode()))

    def face(self, pts, mat, rule, want=None, reg=0, par=(0, 0, 0), uvs=None, smooth=False):
        vs = [self.bm.verts.new(p) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = mat
        f[self.rule] = rule
        f[self.reg] = reg
        f[self.par] = par
        f.smooth = smooth
        if uvs is not None:
            for l, uv in zip(f.loops, uvs):
                l[self.uv].uv = uv
        if want is not None:
            f.normal_update()
            if f.normal.dot(Vector(want)) < 0:
                f.normal_flip()
        return f

    def tess(self, outer, holes, y, mat, rule, want, par=(0, 0, 0), reg=0):
        loops3 = [[Vector((x, y, z)) for (x, z) in loop] for loop in [outer] + holes]
        tris = geometry.tessellate_polygon(loops3)
        pts = [p for loop in loops3 for p in loop]
        for (a, b, c) in tris:
            if (pts[b] - pts[a]).cross(pts[c] - pts[a]).length < 2e-9:
                continue                       # kollineare Umrisspunkte ergeben Dreiecke ohne Flaeche
            self.face([pts[a], pts[b], pts[c]], mat, rule, want, par=par, reg=reg)

    def mark(self, faces, mat, rule, reg=0, par=(0, 0, 0), smooth=False):
        for f in faces:
            f.material_index = mat
            f[self.rule] = rule
            f[self.reg] = reg
            f[self.par] = par
            f.smooth = smooth

def planar_coords(f, e1_hint=None):
    n = f.normal.copy()
    if n.length < 1e-9:
        n = Vector((0, 0, 1))
    cands = ([e1_hint] if e1_hint is not None else []) + [Vector((0, 0, 1)).cross(n), Vector((1, 0, 0)), Vector((0, 1, 0))]
    for c in cands:
        e1 = c - n * c.dot(n)
        if e1.length > 1e-3:
            break
    e1.normalize()
    e2 = n.cross(e1)
    return [(l.vert.co.dot(e1), l.vert.co.dot(e2)) for l in f.loops]

def place_in_region(pc, f, co, reg_name, uoff=None, center=False):
    z0, z1 = REG[reg_name]
    vmin = min(c[1] for c in co)
    vmax = max(c[1] for c in co)
    ext = vmax - vmin
    room = (z1 - z0) - 0.004 - ext
    if room < 0:
        raise RuntimeError(f"{pc.name}: Flaeche {ext:.3f} m zu gross fuer Bereich {reg_name}")
    off = z0 + 0.002 + (room / 2 if center else pc.rng.random() * room)
    if uoff is None:
        uoff = pc.rng.random()
        if reg_name == "melder":
            uoff = pc.rng.random() * 0.2
    for l, c in zip(f.loops, co):
        l[pc.uv].uv = (uoff + UVS * c[0], UVS * (off + c[1] - vmin))

def wood_region(ext):
    for name, hgt in (("holz_03", 0.03), ("holz_05", 0.05), ("holz_07", 0.07), ("holz_10", 0.10), ("holz_24", 0.25)):
        if ext <= hgt - 0.004:
            return name
    raise RuntimeError(f"Holzflaeche {ext:.3f} m zu breit")

def metal_region(ext):
    for name, hgt in (("metall_03", 0.03), ("metall_07", 0.07), ("metall_10", 0.10)):
        if ext <= hgt - 0.004:
            return name
    raise RuntimeError(f"Metallflaeche {ext:.3f} m zu breit")

def apply_uvs(pc):
    bm, uv = pc.bm, pc.uv
    bm.normal_update()
    for f in bm.faces:
        r = f[pc.rule]
        if r == R_KEEP:
            continue
        if r in (R_WM, R_WP):
            side = -1 if r == R_WM else 1
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (wall_u(p.x, side), UVS * p.z)
        elif r == R_TOP:
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (wall_u(p.x, -1), UVS * (3.42 + (p.y + T2)))
        elif r == R_ENDX:
            s = 1 if f.normal.x > 0 else -1
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (0.5 + s * UVS * p.y, UVS * p.z)
        elif r == R_REVX:
            # Fensterlaibung: Putz aus einer ruhigen Stelle des Wandbilds, Hoehe in die Putzzone verschoben
            s = 1 if f.normal.x > 0 else -1
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (U_REV + s * UVS * p.y, UVS * (p.z + REV_DZ))
        elif r == R_REVZ:
            zref = f[pc.par][0]
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (wall_u(p.x, -1), UVS * (zref + 0.02 + (p.y + T2)))
        elif r == R_BAND:
            # durchgehend abgebildete Flaeche parallel zur Wand (Ziegel, Grundputz): Band ab zb im Bereich reg
            side = int(f[pc.par][0])
            zb = f[pc.par][1]
            name = PLAN_REG[f[pc.reg]]
            z0, z1 = REG[name]
            for l in f.loops:
                p = l.vert.co
                v = z0 + 0.01 + p.z - zb
                if not (z0 <= v <= z1):
                    raise RuntimeError(f"{pc.name}: Bereich {name} laeuft ueber ({v - z0:.3f})")
                l[uv].uv = (wall_u(p.x, side), UVS * v)
        elif r == R_BOXFRONT:
            bx, bz0, mir = f[pc.par]
            for l in f.loops:
                p = l.vert.co
                du = (bx - p.x) if mir < 0 else (p.x - bx)
                l[uv].uv = (0.5 + UVS * du, UVS * (REG["melder"][0] + 0.005 + (p.z - bz0)))
        elif r == R_PLAN:
            co = planar_coords(f)
            place_in_region(pc, f, co, PLAN_REG[f[pc.reg]])
        elif r == R_PLANAX:
            co = planar_coords(f, Vector(f[pc.par]))
            place_in_region(pc, f, co, PLAN_REG[f[pc.reg]], center=True)
        elif r == R_PLANFIX:
            co = planar_coords(f, Vector((0, 1, 0)))
            place_in_region(pc, f, co, PLAN_REG[f[pc.reg]], uoff=f[pc.par][0], center=True)
        elif r == R_VFIX:
            # senkrechte Fasen der Bretter: feste Lage (par[0]), damit die Kanten aller Stuecke gleich sind
            co = planar_coords(f, Vector((0, 0, 1)))
            place_in_region(pc, f, co, PLAN_REG[f[pc.reg]], uoff=f[pc.par][0], center=True)
        elif r in (R_METAL, R_HOLZ):
            ax = Vector(f[pc.par]) if Vector(f[pc.par]).length > 0 else None
            co = planar_coords(f, ax)
            ext = max(c[1] for c in co) - min(c[1] for c in co)
            ext2 = max(c[0] for c in co) - min(c[0] for c in co)
            if ext > ext2 and ax is None:
                co = [(c[1], -c[0]) for c in co]
                ext = ext2
            place_in_region(pc, f, co, (metal_region if r == R_METAL else wood_region)(ext), center=True)
        elif r == R_SHARD:
            # Putzschuppe (par 0) oder Brettstueck (par 1): Oberseite aus dem Wandbild
            co = planar_coords(f)
            umin = min(c[0] for c in co)
            vmin = min(c[1] for c in co)
            u0 = pc.rng.random()
            vz = (0.2 + pc.rng.random() * 0.8) if f[pc.par][0] > 0.5 else (1.45 + pc.rng.random() * 1.5)
            for l, c in zip(f.loops, co):
                l[uv].uv = (u0 + UVS * (c[0] - umin), UVS * (vz + c[1] - vmin))

# ---------- Bausteine ----------
def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]

def loop_area(loop):
    n = len(loop)
    return 0.5 * sum(loop[i][0] * loop[(i + 1) % n][1] - loop[(i + 1) % n][0] * loop[i][1] for i in range(n))

def edge_inward(loop, i, ccw):
    a, b = loop[i], loop[(i + 1) % len(loop)]
    dx, dz = b[0] - a[0], b[1] - a[1]
    return Vector((-dz, 0, dx)) if ccw else Vector((dz, 0, -dx))

def recess(pc, loop, side, depth_out, depth_in, mat_bottom, rule_bottom, par_bottom, rim_reg, reg_bottom="bruch", holes=()):
    """Vertiefung: Rand von depth_out bis depth_in (Abstand zur Wandmitte), Boden auf depth_in."""
    y_out, y_in = side * depth_out, side * depth_in
    n = len(loop)
    ccw = loop_area(loop) > 0
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        P = [Vector((a[0], y_out, a[1])), Vector((b[0], y_out, b[1])), Vector((b[0], y_in, b[1])), Vector((a[0], y_in, a[1]))]
        pc.face(P, 1, R_PLAN, edge_inward(loop, i, ccw), reg=PLAN_REG.index(rim_reg))
    pc.tess(loop, list(holes), y_in, mat_bottom, rule_bottom, (0, side, 0), par=par_bottom, reg=PLAN_REG.index(reg_bottom))

def groove(pc, pts, widths, side, depth, reg="riss"):
    """Riss als V-Nut entlang einer Linie. Gibt das Oeffnungs-Polygon zurueck."""
    L, Rr = [], []
    for i, p in enumerate(pts):
        if i == 0:
            d = Vector((pts[1][0] - p[0], pts[1][1] - p[1]))
        elif i == len(pts) - 1:
            d = Vector((p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]))
        else:
            d = Vector((pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]))
        d.normalize()
        nrm = Vector((-d.y, d.x))
        w = widths[i] / 2
        L.append((p[0] + nrm.x * w, p[1] + nrm.y * w))
        Rr.append((p[0] - nrm.x * w, p[1] - nrm.y * w))
    yf = side * T2
    yb = side * (T2 - depth)
    B = [Vector((p[0], yb, p[1])) for p in pts]
    for i in range(len(pts) - 1):
        for edge, sgn in ((L, 1), (Rr, -1)):
            a, b = edge[i], edge[i + 1]
            P = [Vector((a[0], yf, a[1])), Vector((b[0], yf, b[1])), B[i + 1], B[i]]
            mid = Vector(((a[0] + b[0]) / 2 - (pts[i][0] + pts[i + 1][0]) / 2, 0,
                          (a[1] + b[1]) / 2 - (pts[i][1] + pts[i + 1][1]) / 2))
            ax = (pts[i + 1][0] - pts[i][0], 0.0, pts[i + 1][1] - pts[i][1])
            pc.face(P, 1, R_PLANAX, -mid + Vector((0, side * 0.0001, 0)), reg=PLAN_REG.index(reg), par=ax)
    for i, k in ((0, 1), (len(pts) - 1, len(pts) - 2)):
        P = [Vector((L[i][0], yf, L[i][1])), Vector((Rr[i][0], yf, Rr[i][1])), B[i]]
        d = Vector((pts[i][0] - pts[k][0], 0, pts[i][1] - pts[k][1]))
        pc.face(P, 1, R_PLAN, -d + Vector((0, side * 0.0001, 0)), reg=PLAN_REG.index(reg))
    return L + Rr[::-1]

def profile_strip(pc, prof, x0, x1, side, reg, end_caps=True):
    """Profil (d, z) von unten nach oben, d = Abstand zur Wandflaeche, laeuft von x0 bis x1."""
    z0r, z1r = REG[reg]
    s = [0.0]
    for i in range(1, len(prof)):
        s.append(s[-1] + math.hypot(prof[i][0] - prof[i - 1][0], prof[i][1] - prof[i - 1][1]))
    assert s[-1] <= (z1r - z0r) - 0.004, (reg, s[-1])
    def yy(d):
        return side * (T2 + d)
    for i in range(len(prof) - 1):
        (d0, za), (d1, zb) = prof[i], prof[i + 1]
        P = [Vector((x0, yy(d0), za)), Vector((x1, yy(d0), za)), Vector((x1, yy(d1), zb)), Vector((x0, yy(d1), zb))]
        U = [wall_u(x0, side), wall_u(x1, side), wall_u(x1, side), wall_u(x0, side)]
        V = [UVS * (z0r + 0.002 + s[i])] * 2 + [UVS * (z0r + 0.002 + s[i + 1])] * 2
        want = Vector((0, side * (zb - za), -(d1 - d0)))
        if want.length < 1e-9:
            want = Vector((0, side, 0))
        pc.face(P, 1, R_KEEP, want, uvs=list(zip(U, V)))
    if end_caps:
        for x, sgn in ((x0, -1), (x1, 1)):
            P = [Vector((x, yy(d), z)) for d, z in prof]
            if prof[0][0] > 0:
                P = [Vector((x, yy(0), prof[0][1]))] + P
            if prof[-1][0] > 0:
                P = P + [Vector((x, yy(0), prof[-1][1]))]
            pc.face(P, 1, R_PLANFIX, (sgn, 0, 0), reg=PLAN_REG.index(reg), par=(0.37 if side > 0 else 0.13, 0, 0))

def noisy_loop(cx, cz, rx, rz, npts, seed, amp=0.18):
    pts = []
    for k in range(npts):
        a = 2 * math.pi * k / npts
        c, s = math.cos(a), math.sin(a)
        r = 1 + amp * noise.noise(Vector((c * 1.6, s * 1.6, seed))) + 0.45 * amp * noise.noise(Vector((c * 5, s * 5, seed + 3))) \
            + 0.22 * amp * noise.noise(Vector((c * 16, s * 16, seed + 7)))
        pts.append((cx + c * rx * r, cz + s * rz * r))
    return pts

def chunk(pc, center, size, seed, reg="bruch", subdiv=1):
    vs = bmesh.ops.create_icosphere(pc.bm, subdivisions=subdiv, radius=1.0)["verts"]
    off = Vector((seed * 1.7, seed * 2.3, seed * 0.9))
    for v in vs:
        d = 1.0 + 0.3 * noise.noise(v.co * 1.5 + off) + 0.1 * noise.noise(v.co * 3.7 + off)
        v.co = Vector((v.co.x * d * size[0], v.co.y * d * size[1], v.co.z * d * size[2]))
    rot = Matrix.Rotation(pc.rng.uniform(0, math.tau), 3, "Z") @ Matrix.Rotation(pc.rng.uniform(-0.5, 0.5), 3, "X")
    bmesh.ops.rotate(pc.bm, cent=Vector((0, 0, 0)), matrix=rot, verts=vs)
    bmesh.ops.translate(pc.bm, vec=Vector(center), verts=vs)
    zmin = min(v.co.z for v in vs)
    if zmin < 0:
        bmesh.ops.translate(pc.bm, vec=Vector((0, 0, -zmin)), verts=vs)
    faces = list({f for v in vs for f in v.link_faces})
    pc.mark(faces, 1, R_PLAN, PLAN_REG.index(reg))
    return vs

def shard(pc, x, y, seed, size=(0.03, 0.08), zbase=0.0, thick=0.008):
    """Putzschuppe: Oberseite aus dem Wand-Material (gestrichener Putz), Kanten Grundputz."""
    rng = random.Random(seed)
    a, b = rng.uniform(*size), rng.uniform(*size)
    pts = [(0, 0), (a, rng.uniform(-0.01, 0.01)), (a * rng.uniform(0.5, 1.0), b), (rng.uniform(-0.01, 0.02), b * rng.uniform(0.6, 1.0))]
    ang = rng.uniform(0, math.tau)
    ca, sa = math.cos(ang), math.sin(ang)
    tilt = rng.uniform(-0.15, 0.15)
    P = []
    for (px, py) in pts:
        rx, ry = px * ca - py * sa, px * sa + py * ca
        P.append((x + rx, y + ry))
    z0 = zbase + 0.001 + rng.uniform(0, 0.006)
    topz = [z0 + thick + tilt * (p[0] - x) for p in P]
    lift = max(0.0, zbase - min(z0 + tilt * (p[0] - x) for p in P))   # schraege Scherbe nicht unter den Boden
    top = [Vector((p[0], p[1], tz + lift)) for p, tz in zip(P, topz)]
    bot = [Vector((p[0], p[1], z0 + tilt * (p[0] - x) + lift)) for p in P]
    pc.face(top, 0, R_SHARD, (0, 0, 1))
    pc.face(bot[::-1], 1, R_PLAN, (0, 0, -1), reg=PLAN_REG.index("altputz"))
    c = sum(top, Vector()) / len(top)
    for i in range(len(P)):
        j = (i + 1) % len(P)
        Q = [bot[i], bot[j], top[j], top[i]]
        mid = (bot[i] + top[j]) / 2
        pc.face(Q, 1, R_PLAN, mid - c, reg=PLAN_REG.index("altputz"))

def box_faces(pc, lo, hi, rule, mat=1, reg=0, par=(0, 0, 0), bevel=0.0, axis=None):
    lo, hi = Vector(lo), Vector(hi)
    vs = bmesh.ops.create_cube(pc.bm, size=1.0)["verts"]
    bmesh.ops.scale(pc.bm, vec=hi - lo, verts=vs)
    bmesh.ops.translate(pc.bm, vec=(lo + hi) / 2, verts=vs)
    if bevel > 0:
        edges = list({e for v in vs for e in v.link_edges})
        res = bmesh.ops.bevel(pc.bm, geom=edges + vs, offset=bevel, offset_type="OFFSET", segments=1,
                              profile=0.5, affect="EDGES", clamp_overlap=True)
        vs = list({v for f in res["faces"] for v in f.verts})
    faces = list({f for v in vs for f in v.link_faces})
    p = par if axis is None else tuple(axis)
    pc.mark(faces, mat, rule, reg, p)
    return faces

def fillet(pts, radius, steps=4):
    """Knicke einer Linie zu Boegen runden (fuer verbogene Eisen)."""
    pts = [Vector(p) for p in pts]
    out = [pts[0]]
    for k in range(1, len(pts) - 1):
        a, b, c = pts[k - 1], pts[k], pts[k + 1]
        d0, d1 = b - a, c - b
        L0, L1 = d0.length, d1.length
        d0.normalize()
        d1.normalize()
        ang = math.acos(max(-1.0, min(1.0, d0.dot(d1))))
        if ang < 1e-3:
            out.append(b)
            continue
        tl = min(radius * math.tan(ang / 2), 0.45 * L0, 0.45 * L1)
        rr = tl / math.tan(ang / 2)
        p_in, p_out = b - d0 * tl, b + d1 * tl
        center = b + (d1 - d0).normalized() * (rr / math.cos(ang / 2))
        v0, v1 = p_in - center, p_out - center
        q = v0.rotation_difference(v1)
        for i in range(steps + 1):
            out.append(center + Quaternion().slerp(q, i / steps) @ v0)
    out.append(pts[-1])
    return out

def tube(pc, pts, r, reg, seg=8, smooth=True, caps=True, uoff=0.0):
    """Rohr entlang einer Linie mit gemeinsamen Vertices (weiche Normalen).
    Ringe per Parallelverschiebung (verdrehen nicht), in Knicken auf Gehrung gestreckt.
    UV: U = echte Laenge entlang jeder Mantellinie, V = Umfang (Sehnen), so bleibt die Dichte auch in Boegen bei 1024."""
    pts = [Vector(p) for p in pts]
    z0r, z1r = REG[reg]
    chord = 2 * r * math.sin(math.pi / seg)
    assert seg * chord <= (z1r - z0r) - 0.004, (reg, r)
    n = len(pts)
    tans = []
    for k in range(n):
        if k == 0:
            t = pts[1] - pts[0]
        elif k == n - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[k + 1] - pts[k]).normalized() + (pts[k] - pts[k - 1]).normalized()
        tans.append(t.normalized())
    ref = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    b1 = tans[0].cross(ref).normalized()
    rings = []
    for k, p in enumerate(pts):
        t = tans[k]
        if k > 0:
            b1 = tans[k - 1].rotation_difference(t) @ b1
            b1 = (b1 - t * b1.dot(t)).normalized()
        b2 = t.cross(b1).normalized()
        mdir, sc = None, 1.0
        if 0 < k < n - 1:
            d0 = (pts[k] - pts[k - 1]).normalized()
            d1 = (pts[k + 1] - pts[k]).normalized()
            half = math.acos(max(-1.0, min(1.0, d0.dot(d1)))) / 2
            if half > 1e-4:
                mdir = d1 - d0
                mdir = (mdir - t * mdir.dot(t)).normalized()
                sc = 1 / max(0.3, math.cos(half))
        ring = []
        for s_ in range(seg):
            o = (b1 * math.cos(2 * math.pi * s_ / seg) + b2 * math.sin(2 * math.pi * s_ / seg)) * r
            if mdir is not None:
                o = o + mdir * (o.dot(mdir) * (sc - 1))
            ring.append(pc.bm.verts.new(p + o))
        rings.append(ring)
    acc = [[0.0] * seg]
    for k in range(1, n):
        acc.append([acc[-1][s_] + (rings[k][s_].co - rings[k - 1][s_].co).length for s_ in range(seg)])
    for k in range(n - 1):
        for s_ in range(seg):
            s2 = (s_ + 1) % seg
            f = pc.bm.faces.new((rings[k][s_], rings[k][s2], rings[k + 1][s2], rings[k + 1][s_]))
            f.material_index = 1
            f[pc.rule] = R_KEEP
            f.smooth = smooth
            v0 = UVS * (z0r + 0.002 + chord * s_)
            v1 = UVS * (z0r + 0.002 + chord * (s_ + 1))
            uvs = ((uoff + UVS * acc[k][s_], v0), (uoff + UVS * acc[k][s2], v1),
                   (uoff + UVS * acc[k + 1][s2], v1), (uoff + UVS * acc[k + 1][s_], v0))
            for l, uv in zip(f.loops, uvs):
                l[pc.uv].uv = uv
    if caps:
        for ring, d in ((rings[0], pts[0] - pts[1]), (rings[-1], pts[-1] - pts[-2])):
            f = pc.bm.faces.new(ring)
            f.material_index = 1
            f[pc.rule] = R_PLAN
            f[pc.reg] = PLAN_REG.index(reg)
            f.normal_update()
            if f.normal.dot(d) < 0:
                f.normal_flip()
    return rings

# ---------- Bausteine Schule ----------
SOCKEL_PROF = [(0.025, 0.0), (0.025, 0.095), (0.022, 0.104), (0.016, 0.11), (0.008, 0.114), (0.0, 0.116)]
# Holzleiste auf 1,17 .. 1,235 m; ihre Unterseite reicht 3 mm hinter die Brettflaeche und schliesst die V-Fugen oben ab
LEISTE_PROF = [(-BC, BZ1), (0.016, BZ1), (0.022, 1.176), (0.026, 1.186), (0.028, 1.2), (0.028, 1.214), (0.024, 1.224),
               (0.016, 1.231), (0.006, 1.234), (0.0, 1.235)]
LEISTE_TOP = LEISTE_PROF[-1][1]
NB = int(round(2 * W2 / BW))          # 38 Bretter je Seite

def board_x(i):
    return -W2 + i * BW, -W2 + (i + 1) * BW

def point_in(poly, x, z):
    inside = False
    n = len(poly)
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
        if (z0 > z) != (z1 > z) and x < x0 + (z - z0) / (z1 - z0) * (x1 - x0):
            inside = not inside
    return inside

def line_hits(poly, axis, c):
    """Strecken einer Linie im Polygon: axis 'h' (z = c) liefert x-Bereiche, 'v' (x = c) z-Bereiche."""
    ts = []
    n = len(poly)
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
        a0, a1, b0, b1 = (z0, z1, x0, x1) if axis == "h" else (x0, x1, z0, z1)
        if (a0 - c) * (a1 - c) < 0:
            ts.append(b0 + (c - a0) / (a1 - a0) * (b1 - b0))
    ts.sort()
    return [(ts[i], ts[i + 1]) for i in range(0, len(ts) - 1, 2)]

def subtract_spans(lo, hi, cuts, pad):
    """Bereich lo..hi ohne die Strecken cuts (je um pad erweitert)."""
    spans = [(lo, hi)]
    for a, b in cuts:
        a, b = a - pad, b + pad
        nxt = []
        for s0, s1 in spans:
            if b <= s0 or a >= s1:
                nxt.append((s0, s1))
                continue
            if a > s0:
                nxt.append((s0, a))
            if b < s1:
                nxt.append((b, s1))
        spans = nxt
    return [(a, b) for a, b in spans if b - a > 0.01]

def drop_back(pc, faces, side, yface=None):
    """Rueckseite eines Anbauteils, die auf einer Flaeche liegt, entfernen (nie sichtbar, kein Flimmern)."""
    yface = T2 if yface is None else yface
    dead = []
    for f in faces:
        if not f.is_valid:
            continue
        f.normal_update()
        if f.normal.y * side < -0.99 and abs(f.calc_center_median().y - side * yface) < 1e-4:
            dead.append(f)
    bmesh.ops.delete(pc.bm, geom=dead, context="FACES_ONLY")

def check_holes(name, holes):
    for h in holes:
        xs = [p[0] for p in h]
        if min(xs) < -W2 + EDGE + 0.02 or max(xs) > W2 - EDGE - 0.02:
            raise RuntimeError(f"{name}: Schaden zu nah an der Kante ({min(xs):.3f} .. {max(xs):.3f})")

def new_verts(pc, before):
    """Vertices, die seit dem Schnappschuss before (Menge) entstanden sind. Nach Loeschungen belegt bmesh freie Plaetze
    neu, die Reihenfolge taugt dann nicht."""
    return [v for v in pc.bm.verts if v not in before]

def keep_in_front(pc, vs, side, lo=0.028, hi=0.115):
    """Teile am Boden: vor der Sockelleiste, hoechstens 11,5 cm vor der Wand."""
    ys = [side * v.co.y - T2 for v in vs]
    d = 0.0
    if max(ys) > hi:
        d = hi - max(ys)
    if min(ys) + d < lo:
        d = lo - min(ys)
    if d:
        for v in vs:
            v.co.y += side * d

def shell(pc):
    """Oberseite und Stirnseiten des Grundkoerpers."""
    pc.face([Vector((-W2, -T2, H)), Vector((W2, -T2, H)), Vector((W2, T2, H)), Vector((-W2, T2, H))], 0, R_TOP, (0, 0, 1))
    for x, sg in ((-W2, -1), (W2, 1)):
        pc.face([Vector((x, -T2, 0)), Vector((x, T2, 0)), Vector((x, T2, H)), Vector((x, -T2, H))], 0, R_ENDX, (sg, 0, 0))

def strips(pc, side, sockel_spans, leiste_spans):
    for a, b in sockel_spans:
        profile_strip(pc, SOCKEL_PROF, a, b, side, "sockel")
    for a, b in leiste_spans:
        profile_strip(pc, LEISTE_PROF, a, b, side, "leiste")

def surface(pc, outer, holes, y, side, rule, reg="altputz", band=None, mat=1):
    """Ebene Flaeche parallel zur Wand: Polygon ohne Loecher (die ueber den Rand gehen duerfen), per CDT.
    Mit band wird sie in waagerechte Baender zerlegt und jedes Band durchgehend abgebildet (R_BAND)."""
    def ccw(loop):
        return loop if loop_area(loop) > 0 else loop[::-1]
    loops = [ccw(outer)] + [ccw(h) for h in holes]
    zs = [p[1] for p in outer]
    za, zb_ = min(zs), max(zs)
    xs = [p[0] for p in outer]
    xa, xb = min(xs) - 0.01, max(xs) + 0.01
    verts, faces, edges = [], [], []
    for lp in loops:
        i0 = len(verts)
        verts += [Vector(p) for p in lp]
        faces.append(list(range(i0, i0 + len(lp))))
    if band:
        k = 1
        while za + k * band < zb_ - 1e-6:
            zc = za + k * band
            i0 = len(verts)
            verts += [Vector((xa, zc)), Vector((xb, zc))]
            edges.append((i0, i0 + 1))
            k += 1
    co, _, tris = geometry.delaunay_2d_cdt(verts, edges, faces, 1, 1e-7)[:3]
    for tri in tris:
        p2 = [co[i] for i in tri]
        cx, cz = sum(p.x for p in p2) / 3, sum(p.y for p in p2) / 3
        if not point_in(outer, cx, cz) or any(point_in(h, cx, cz) for h in holes):
            continue
        if abs((p2[1] - p2[0]).cross(p2[2] - p2[0])) < 2e-9:
            continue
        par = (side, za + math.floor((cz - za) / band) * band, 0) if band else (0, 0, 0)
        pc.face([Vector((p.x, y, p.y)) for p in p2], mat, rule, (0, side, 0), reg=PLAN_REG.index(reg), par=par)

# ---------- Vertaefelung ----------
def board_shape(i, cut=None):
    """Brett i: Vorderflaeche (Polygon) und Hoehe der linken/rechten Fase (None = keine Fase).
    cut = (ox0, ox1, oz0): Oeffnung ab Hoehe oz0 (Tuer: oz0 = 0, die Bretter enden unter der Bekleidung)."""
    bx0, bx1 = board_x(i)
    fx0, fx1 = bx0 + BC, bx1 - BC
    if cut is None or cut[1] <= bx0 or cut[0] >= bx1:
        return rect(fx0, fx1, 0.0, BZ1), BZ1, BZ1
    ox0, ox1, oz0 = cut
    if ox0 <= bx0 and ox1 >= bx1:
        if oz0 <= 0.0:
            return None, None, None
        return rect(fx0, fx1, 0.0, oz0), oz0, oz0
    if ox0 > bx0:
        if oz0 <= 0.0:
            return rect(fx0, ox0, 0.0, BZ1), BZ1, None
        return [(fx0, 0.0), (fx1, 0.0), (fx1, oz0), (ox0, oz0), (ox0, BZ1), (fx0, BZ1)], BZ1, oz0
    if oz0 <= 0.0:
        return rect(ox1, fx1, 0.0, BZ1), None, BZ1
    return [(fx0, 0.0), (fx1, 0.0), (fx1, BZ1), (ox1, BZ1), (ox1, oz0), (fx0, oz0)], oz0, BZ1

def chamfer(pc, side, xj, sgn, z0, z1):
    """Fase an der Fuge xj; sgn = +1: Brett rechts der Fuge, -1: links. Feste UV-Lage je Fuge."""
    if z1 - z0 < 1e-4:
        return
    s = side
    P = [Vector((xj, s * (T2 - BC), z0)), Vector((xj + sgn * BC, s * T2, z0)), Vector((xj + sgn * BC, s * T2, z1)),
         Vector((xj, s * (T2 - BC), z1))]
    uoff = (xj * 3.7 + (0.31 if s > 0 else 0.0) + (0.5 if sgn > 0 else 0.0)) % 1.0
    pc.face(P, 1, R_VFIX, (-sgn, s, 0), reg=PLAN_REG.index("brett"), par=(uoff, 0, 0))

def jag_line(x0, x1, zbase, rng, n=7, amp=0.01, spikes=2, spike=(0.015, 0.045)):
    """Gezackte Bruchkante quer ueber ein Brett, mit langen Splittern."""
    xs = [x0 + (x1 - x0) * k / (n - 1) for k in range(n)]
    zs = [zbase + rng.uniform(-amp, amp) for _ in range(n)]
    for k in rng.sample(range(1, n - 1), spikes):
        zs[k] += rng.uniform(*spike)
    return xs, zs

def end_strips(pc, s, bx0, bx1, xs, zf, zb, reg="kerbe"):
    """Bruchflaeche am oberen Ende eines Bretts: von der Vorderkante (mit Fasen) bis zur Rueckseite."""
    F = [Vector((bx0, s * (T2 - BC), zf[0]))] + [Vector((x, s * T2, z)) for x, z in zip(xs, zf)] + [Vector((bx1, s * (T2 - BC), zf[-1]))]
    B = [Vector((bx0, s * YB, zb[0]))] + [Vector((x, s * YB, z)) for x, z in zip(xs, zb)] + [Vector((bx1, s * YB, zb[-1]))]
    faces = []
    for k in range(len(F) - 1):
        ax = (F[k + 1] + B[k + 1]) / 2 - (F[k] + B[k]) / 2
        faces.append(pc.face([F[k], F[k + 1], B[k + 1], B[k]], 1, R_PLANAX, (0, 0, 1), par=(ax.x, ax.y, ax.z), reg=PLAN_REG.index(reg)))
    return faces

def board_broken(pc, side, i, xs, zf, holes=()):
    """Unterer Rest eines gebrochenen Bretts: Vorderseite bis zur Bruchkante, Fasen, Bruchflaeche, Rueckseite."""
    s = side
    bx0, bx1 = board_x(i)
    poly = [(bx0 + BC, 0.0), (bx1 - BC, 0.0)] + list(zip(xs[::-1], zf[::-1]))
    pc.tess(poly, list(holes), s * T2, 0, R_WM if s < 0 else R_WP, (0, s, 0))
    chamfer(pc, s, bx0, 1, 0.0, zf[0])
    chamfer(pc, s, bx1, -1, 0.0, zf[-1])
    rng = random.Random(int(i * 31 + s * 7))
    zb = [zf[0]] + [z + rng.uniform(-0.012, 0.006) for z in zf[1:-1]] + [zf[-1]]
    end_strips(pc, s, bx0, bx1, xs, zf, zb)
    back = [(bx0, 0.0), (bx1, 0.0), (bx1, zb[-1])] + list(zip(xs[::-1], zb[::-1])) + [(bx0, zb[0])]
    pc.tess(back, [], s * YB, 1, R_PLANAX, (0, -s, 0), par=(0, 0, 1), reg=PLAN_REG.index("brett"))

def board_loose(pc, side, i, tilt, twist, top, seed):
    """Loses Brett: oben abgebrochen, unten hinter der Sockelleiste noch fest, kippt nach vorn und verdreht sich.
    Die Vorderseite behaelt das Wandbild ihrer urspruenglichen Lage."""
    s = side
    rng = random.Random(seed)
    bx0, bx1 = board_x(i)
    n0 = set(pc.bm.verts)
    xs, zf = jag_line(bx0 + BC, bx1 - BC, top, rng)
    zb = [zf[0]] + [z + rng.uniform(-0.012, 0.006) for z in zf[1:-1]] + [zf[-1]]
    poly = [(bx0 + BC, 0.0), (bx1 - BC, 0.0)] + list(zip(xs[::-1], zf[::-1]))
    loop3 = [Vector((x, s * T2, z)) for x, z in poly]
    for a, b, c in geometry.tessellate_polygon([loop3]):
        P = [loop3[a], loop3[b], loop3[c]]
        pc.face(P, 0, R_KEEP, (0, s, 0), uvs=[(wall_u(p.x, s), UVS * p.z) for p in P])
    pc.face([Vector((bx0, s * (T2 - BC), 0.0)), Vector((bx0 + BC, s * T2, 0.0)), Vector((bx0 + BC, s * T2, zf[0])),
             Vector((bx0, s * (T2 - BC), zf[0]))], 1, R_PLANAX, (-1, s, 0), par=(0, 0, 1), reg=PLAN_REG.index("brett"))
    pc.face([Vector((bx1, s * (T2 - BC), 0.0)), Vector((bx1 - BC, s * T2, 0.0)), Vector((bx1 - BC, s * T2, zf[-1])),
             Vector((bx1, s * (T2 - BC), zf[-1]))], 1, R_PLANAX, (1, s, 0), par=(0, 0, 1), reg=PLAN_REG.index("brett"))
    for x, sg, zt in ((bx0, -1, zf[0]), (bx1, 1, zf[-1])):
        pc.face([Vector((x, s * (T2 - BC), 0.0)), Vector((x, s * YB, 0.0)), Vector((x, s * YB, zt)), Vector((x, s * (T2 - BC), zt))],
                1, R_PLANAX, (sg, 0, 0), par=(0, 0, 1), reg=PLAN_REG.index("brett"))
    end_strips(pc, s, bx0, bx1, xs, zf, zb)
    back = [(bx0, 0.0), (bx1, 0.0), (bx1, zb[-1])] + list(zip(xs[::-1], zb[::-1])) + [(bx0, zb[0])]
    pc.tess(back, [], s * YB, 1, R_PLANAX, (0, -s, 0), par=(0, 0, 1), reg=PLAN_REG.index("brett"))
    vs = new_verts(pc, n0)
    bmesh.ops.rotate(pc.bm, cent=Vector((bx0, s * YB, 0.0)), matrix=Matrix.Rotation(s * twist, 3, "Z"), verts=vs)
    bmesh.ops.rotate(pc.bm, cent=Vector((0.0, s * YB, 0.08)), matrix=Matrix.Rotation(-s * tilt, 3, "X"), verts=vs)
    zmin = min(v.co.z for v in vs)
    if zmin < 0.0:                                  # die untere Kante steht hinter der Sockelleiste auf dem Boden
        for v in vs:
            v.co.z -= zmin

def cavity(pc, side, xa, xb, tops, hole=None):
    """Hinter fehlenden oder gebrochenen Brettern: Grundputz, Lattung, Abschluss unter der Holzleiste.
    tops: je Brett (x0, x1, Hoehe des festen Rests) fuer die Lattung."""
    s = side
    surface(pc, rect(xa, xb, 0.0, BZ1), [hole] if hole else [], s * YM, s, R_BAND, reg="altputz", band=BAND_P)
    cuts = line_hits(hole, "h", BZ1 - 0.001) if hole else []
    for a, b in subtract_spans(xa, xb, cuts, 0.0):
        pc.face([Vector((a, s * YM, BZ1)), Vector((b, s * YM, BZ1)), Vector((b, s * (T2 - BC), BZ1)), Vector((a, s * (T2 - BC), BZ1))],
                1, R_PLAN, (0, 0, -1), reg=PLAN_REG.index("altputz"))
    li = PLAN_REG.index("latte")
    for zc in LATTEN_Z:
        z0, z1 = zc - 0.02, zc + 0.02
        spans = []
        for x0, x1, zt in tops:
            if zt < z1 - 0.002:
                if spans and abs(spans[-1][1] - x0) < 1e-6:
                    spans[-1] = (spans[-1][0], x1)
                else:
                    spans.append((x0, x1))
        for a0, b0 in spans:
            cuts = (line_hits(hole, "h", z0 + 0.001) + line_hits(hole, "h", z1 - 0.001)) if hole else []
            for a, b in subtract_spans(a0, b0, cuts, 0.0):
                y0, y1 = s * YM, s * YB
                pc.face([Vector((a, y1, z0)), Vector((b, y1, z0)), Vector((b, y1, z1)), Vector((a, y1, z1))], 1, R_PLANAX, (0, s, 0),
                        par=(1, 0, 0), reg=li)
                pc.face([Vector((a, y0, z1)), Vector((b, y0, z1)), Vector((b, y1, z1)), Vector((a, y1, z1))], 1, R_PLANAX, (0, 0, 1),
                        par=(1, 0, 0), reg=li)
                pc.face([Vector((a, y0, z0)), Vector((b, y0, z0)), Vector((b, y1, z0)), Vector((a, y1, z0))], 1, R_PLANAX, (0, 0, -1),
                        par=(1, 0, 0), reg=li)
                for x, sg, inner in ((a, -1, a > a0 + 1e-6), (b, 1, b < b0 - 1e-6)):
                    if inner:                     # vom Loch abgebrochen: Stirnflaeche sichtbar
                        pc.face([Vector((x, y0, z0)), Vector((x, y1, z0)), Vector((x, y1, z1)), Vector((x, y0, z1))], 1, R_PLAN,
                                (sg, 0, 0), reg=PLAN_REG.index("kerbe"))

def boards(pc, side, states=None, cut=None, carvings=None, hole=None):
    """Vertaefelung einer Seite: 38 Bretter mit V-Fugen.
    states: {i: ("fehlt",) | ("lose", kipp, dreh, oben, seed) | ("bruch", xs, zs)}; carvings: {i: [Oeffnungen]}."""
    s = side
    states = states or {}
    carvings = carvings or {}
    tops = []
    for i in range(NB):
        st = states.get(i, ("ok",))
        bx0, bx1 = board_x(i)
        if st[0] != "ok" and (bx0 < -W2 + EDGE + BW - 1e-6 or bx1 > W2 - EDGE - BW + 1e-6):
            raise RuntimeError(f"{pc.name}: Brett {i} zu nah an der Kante (40-cm-Regel)")
        if i in carvings and (bx0 < -W2 + EDGE + BW - 1e-6 or bx1 > W2 - EDGE - BW + 1e-6):
            raise RuntimeError(f"{pc.name}: Schnitzerei auf Brett {i} zu nah an der Kante")
        if st[0] == "ok":
            shape, zl, zr = board_shape(i, cut)
            if shape is None:
                tops.append((None, None, None))
                continue
            pc.tess(shape, list(carvings.get(i, [])), s * T2, 0, R_WM if s < 0 else R_WP, (0, s, 0))
            if zl is not None:
                chamfer(pc, s, bx0, 1, 0.0, zl)
            if zr is not None:
                chamfer(pc, s, bx1, -1, 0.0, zr)
            tops.append((zl, zr, None))
        elif st[0] == "bruch":
            xs, zs = st[1], st[2]
            board_broken(pc, s, i, xs, zs, carvings.get(i, []))
            tops.append((zs[0], zs[-1], min(zs)))
        else:
            if st[0] == "lose":
                board_loose(pc, s, i, *st[1:])
            tops.append((0.0, 0.0, 0.0))
    # Seitenflaechen an Fugen mit verschieden hohen Nachbarn (bis zur Mauer, schliesst den Spalt der Lattung)
    bi = PLAN_REG.index("brett")
    for i in range(1, NB):
        tl, tr = tops[i - 1][1], tops[i][0]
        if tl is None or tr is None or abs(tl - tr) < 1e-5:
            continue
        xj = board_x(i)[0]
        lo, hi = min(tl, tr), max(tl, tr)
        sg = 1 if tl > tr else -1
        pc.face([Vector((xj, s * (T2 - BC), lo)), Vector((xj, s * YM, lo)), Vector((xj, s * YM, hi)), Vector((xj, s * (T2 - BC), hi))],
                1, R_PLANAX, (sg, 0, 0), par=(0, 0, 1), reg=bi)
    # Hohlraeume hinter Laeufen beschaedigter Bretter
    i = 0
    while i < NB:
        if tops[i][2] is None:
            i += 1
            continue
        j = i
        while j + 1 < NB and tops[j + 1][2] is not None:
            j += 1
        tl = [(board_x(k)[0], board_x(k)[1], tops[k][2]) for k in range(i, j + 1)]
        cavity(pc, s, board_x(i)[0], board_x(j)[1], tl, hole)
        i = j + 1

# ---------- Schnitzereien ----------
def split_sharp(line, max_turn=2.3):
    """Linienzug an scharfen Knicken teilen (V-Nuten koennen sich dort sonst ueberschneiden)."""
    out, cur = [], [line[0]]
    for k in range(1, len(line) - 1):
        a, b, c = Vector(line[k - 1]), Vector(line[k]), Vector(line[k + 1])
        d0, d1 = (b - a).normalized(), (c - b).normalized()
        cur.append(line[k])
        if math.acos(max(-1.0, min(1.0, d0.dot(d1)))) > max_turn:
            out.append(cur)
            cur = [line[k]]
    cur.append(line[-1])
    out.append(cur)
    return out

def seg_dist(p, a, b):
    p, a, b = Vector(p), Vector(a), Vector(b)
    d = b - a
    t = max(0.0, min(1.0, (p - a).dot(d) / max(d.length_squared, 1e-12)))
    return (p - (a + d * t)).length

def trim_strokes(strokes, trim):
    """Enden, die auf einem anderen Strich liegen (oder ihn fast beruehren), um trim kuerzen."""
    out = []
    for si, st in enumerate(strokes):
        st = [Vector(p) for p in st]
        for end in (0, -1):
            p = st[end]
            near = False
            for sj, other in enumerate(strokes):
                pts = [Vector(q) for q in other]
                segs = list(zip(pts[:-1], pts[1:]))
                if sj == si:
                    segs = segs[1:] if end == 0 else segs[:-1]
                    segs = segs[1:] if end == 0 else segs[:-1]
                if any(seg_dist(p, a, b) < trim * 0.9 for a, b in segs):
                    near = True
                    break
            if near:
                q = st[1] if end == 0 else st[-2]
                d = q - p
                if d.length > trim * 1.6:
                    st[end] = p + d.normalized() * trim
        out.append([(v.x, v.y) for v in st])
    return out

def carve(pc, side, text, x0, z0, h, slant=0.0, depth=0.0022, wid=0.0028):
    """Eingeritzte Buchstaben als V-Nuten; jeder Buchstabe liegt ganz auf einem Brett. Gibt {Brett: [Oeffnungen]}."""
    w = h * 0.55
    gap = h * 0.3
    out = {}
    x = x0
    for ch in text:
        if ch == " ":
            x += w
            continue
        lo_off, hi_off = min(0.0, slant * h), w + max(0.0, slant * h)
        i = int(math.floor((x + lo_off + W2) / BW))
        bx0, bx1 = board_x(i)
        if x + lo_off < bx0 + BC + 0.006:
            x = bx0 + BC + 0.006 - lo_off
        if x + hi_off > bx1 - BC - 0.006:
            i += 1
            bx0, bx1 = board_x(i)
            x = bx0 + BC + 0.006 - lo_off
        lines = []
        for line in GLYPH[ch]:
            pts = [(x + px / 2 * w + slant * pz / 4 * h, z0 + pz / 4 * h) for px, pz in line]
            lines += split_sharp(pts)
        for st in trim_strokes(lines, 0.0035):
            pts = [st[0]]
            for a, b in zip(st[:-1], st[1:]):
                if math.hypot(b[0] - a[0], b[1] - a[1]) > 0.016:
                    pts.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
                pts.append(b)
            if len(pts) == 2:
                pts.insert(1, ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2))
            widths = [0.0012] + [wid] * (len(pts) - 2) + [0.0012]
            out.setdefault(i, []).append(groove(pc, pts, widths, side, depth, reg="kerbe"))
        x += hi_off - lo_off + gap
    return out

def merge_carvings(*ds):
    out = {}
    for d in ds:
        for k, v in d.items():
            out.setdefault(k, []).extend(v)
    return out

# ---------- Putzschaeden ----------
def missing_bricks(pc, loop, side, za, count):
    """Fehlende Ziegel genau im Raster der Ziegeltextur (Baender ab za, Schicht CH, Laeuferverband)."""
    rects = []
    tries = 0
    while len(rects) < count and tries < 400:
        tries += 1
        nc = pc.rng.randrange(1, 13)
        z0 = za - 0.01 + nc * CH + 0.004
        z1 = za - 0.01 + (nc + 1) * CH - 0.004
        j = pc.rng.randrange(0, 16)
        X0 = j * 0.25 - (nc % 2) * 0.125
        X1 = X0 + 0.25
        x0, x1 = (X0 - 2.0, X1 - 2.0) if side < 0 else (-X1, -X0)
        sh = 4.0 * round(-(x0 + x1) / 8.0)
        x0, x1 = x0 + sh + 0.004, x1 + sh - 0.004
        corners = [(x0 - 0.03, z0 - 0.03), (x1 + 0.03, z0 - 0.03), (x1 + 0.03, z1 + 0.03), (x0 - 0.03, z1 + 0.03)]
        if not all(point_in(loop, x, z) for x, z in corners):
            continue
        if any(not (x1 + 0.02 < r[0][0] or r[1][0] + 0.02 < x0 or z1 + 0.02 < r[0][1] or r[2][1] + 0.02 < z0) for r in rects):
            continue
        rects.append(rect(x0, x1, z0, z1))
    return rects

def lath_piece(pc, side, x0, x1, z0, z1, ends=(False, False), T=None):
    """Holzlatte vor dem Ziegel (Putztraeger): Vorder-, Ober- und Unterseite, sichtbare Bruchenden."""
    s = side
    y0, y1 = s * (T2 - PUTZ_T), s * (T2 - PUTZ_T + 0.01)
    T = T or (lambda v: v)
    li = PLAN_REG.index("latte")
    ax = T(Vector((x1, 0, 0))) - T(Vector((x0, 0, 0)))
    faces = [pc.face([T(Vector((x0, y1, z0))), T(Vector((x1, y1, z0))), T(Vector((x1, y1, z1))), T(Vector((x0, y1, z1)))], 1, R_PLANAX,
                     T(Vector((x0, y1 + s, z0))) - T(Vector((x0, y1, z0))), par=tuple(ax), reg=li)]
    for z, sg in ((z1, 1), (z0, -1)):
        faces.append(pc.face([T(Vector((x0, y0, z))), T(Vector((x1, y0, z))), T(Vector((x1, y1, z))), T(Vector((x0, y1, z)))], 1, R_PLANAX,
                             T(Vector((0, 0, z + sg))) - T(Vector((0, 0, z))), par=tuple(ax), reg=li))
    for x, sg, show in ((x0, -1, ends[0]), (x1, 1, ends[1])):
        if show:
            faces.append(pc.face([T(Vector((x, y0, z0))), T(Vector((x, y1, z0))), T(Vector((x, y1, z1))), T(Vector((x, y0, z1)))], 1, R_PLAN,
                                 T(Vector((x + sg, y0, z0))) - T(Vector((x, y0, z0))), reg=PLAN_REG.index("kerbe")))
    return faces

def laths(pc, side, loop, rng):
    """Spalierlatten unter dem abgefallenen Putz, einzelne fehlen, sind gebrochen oder haengen herab."""
    zs = [p[1] for p in loop]
    za, zb = min(zs), max(zs)
    z = za + 0.015
    while z + 0.036 < zb - 0.015:
        z0, z1 = z, z + 0.036
        hl = [line_hits(loop, "h", zz) for zz in (z0 + 0.001, (z0 + z1) / 2, z1 - 0.001)]
        z += 0.052
        if not all(hl):
            continue
        xa = min(h[0][0] for h in hl) - 0.02
        xb = max(h[-1][1] for h in hl) + 0.02
        st = rng.choice(["ok", "ok", "ok", "fehlt", "bruch", "haengt"])
        if st == "fehlt":
            continue
        if st == "ok" or xb - xa < 0.25:
            lath_piece(pc, side, xa, xb, z0, z1)
            continue
        xm = rng.uniform(xa + 0.35 * (xb - xa), xa + 0.65 * (xb - xa))
        g = rng.uniform(0.02, 0.08)
        lath_piece(pc, side, xa, xm - g / 2, z0, z1, (False, True))
        if st == "bruch":
            lath_piece(pc, side, xm + g / 2, xb, z0, z1, (True, False))
            continue
        # rechtes Stueck haengt: an seinem Ende noch genagelt, dreht nach unten und etwas nach vorn
        L = min(xb - (xm + g / 2), rng.uniform(0.18, 0.3))
        piv = Vector((xm + g / 2 + L, side * (T2 - PUTZ_T), (z0 + z1) / 2))
        ang = rng.uniform(0.35, 0.6)
        R = Matrix.Rotation(-ang, 3, "Y") @ Matrix.Rotation(-side * rng.uniform(0.08, 0.16), 3, "Z")
        T = lambda v, R=R, piv=piv: piv + R @ (v - piv)
        tip = T(Vector((xm + g / 2, 0, z0)))
        if not point_in(loop, tip.x, tip.z) or tip.z < za + 0.03:
            lath_piece(pc, side, xm + g / 2, xb, z0, z1, (True, False))
            continue
        lath_piece(pc, side, xm + g / 2, xm + g / 2 + L, z0, z1, (True, False), T)
        if xb > xm + g / 2 + L + 0.02:
            lath_piece(pc, side, xm + g / 2 + L + 0.004, xb, z0, z1, (True, False))

def plaster_loss(pc, side, loop, missing=2, lathing=False, seed=0):
    """Putz abgefallen: Bruchrand im Putz, darunter Ziegel (durchgehend abgebildet, Raster wie die Textur),
    einzelne Ziegel fehlen; auf Wunsch Holzlatten als Putztraeger."""
    s = side
    yb = T2 - PUTZ_T
    n = len(loop)
    ccw = loop_area(loop) > 0
    ai = PLAN_REG.index("altputz")
    for k in range(n):
        a, b = loop[k], loop[(k + 1) % n]
        P = [Vector((a[0], s * T2, a[1])), Vector((b[0], s * T2, b[1])), Vector((b[0], s * yb, b[1])), Vector((a[0], s * yb, a[1]))]
        pc.face(P, 1, R_PLAN, edge_inward(loop, k, ccw), reg=ai)
    za = min(p[1] for p in loop)
    holes = missing_bricks(pc, loop, side, za, missing)
    surface(pc, loop, holes, s * yb, s, R_BAND, reg="ziegel", band=BAND)
    for h in holes:
        recess(pc, h, side, yb, yb - 0.03, 1, R_PLAN, (0, 0, 0), "bruch", reg_bottom="bruch")
    if lathing:
        laths(pc, side, loop, random.Random(seed))
    return loop

# ---------- Kleinteile am Boden ----------
def splinter(pc, p0, d, L, w, t, n=None, reg="kerbe"):
    """Holzsplitter: flacher Keil von p0 in Richtung d, laeuft zur Spitze aus; n = Breitenrichtung."""
    d = Vector(d).normalized()
    n = (Vector(n) if n is not None else Vector((0, 0, 1)).cross(d)).normalized()
    n = (n - d * n.dot(d)).normalized()
    up = d.cross(n)
    p0 = Vector(p0)
    p1 = p0 + d * L
    A = [p0 - n * w / 2, p0 + n * w / 2, p0 + n * w / 2 + up * t, p0 - n * w / 2 + up * t]
    B = [p1 - n * w * 0.12, p1 + n * w * 0.12, p1 + n * w * 0.12 + up * t * 0.3, p1 - n * w * 0.12 + up * t * 0.3]
    ri = PLAN_REG.index(reg)
    mid = (p0 + p1) / 2 + up * t * 0.3
    for k in range(4):
        k2 = (k + 1) % 4
        cen = (A[k] + A[k2] + B[k2] + B[k]) / 4
        pc.face([A[k], A[k2], B[k2], B[k]], 1, R_PLANAX, cen - mid, par=(d.x, d.y, d.z), reg=ri)
    pc.face(A[::-1], 1, R_PLAN, -d, reg=ri)
    pc.face(B, 1, R_PLAN, d, reg=ri)

def glass_shard(pc, x, y, z, rng, size=(0.01, 0.025), t=0.002, normal=(0, 0, 1)):
    """Glasscherbe: duennes Dreieck (Prisma)."""
    nrm = Vector(normal).normalized()
    e1 = nrm.orthogonal().normalized()
    e2 = nrm.cross(e1)
    a = rng.uniform(0, math.tau)
    pts = []
    for k in range(3):
        r = rng.uniform(*size)
        aa = a + k * 2.1 + rng.uniform(-0.3, 0.3)
        pts.append(Vector((x, y, z)) + (e1 * math.cos(aa) + e2 * math.sin(aa)) * r)
    lift = max(0.0, 0.0002 - min(p.z for p in pts))
    pts = [p + Vector((0, 0, lift)) for p in pts]
    top = [p + nrm * t for p in pts]
    gi = PLAN_REG.index("glas")
    pc.face(top, 1, R_PLAN, nrm, reg=gi)
    pc.face(pts[::-1], 1, R_PLAN, -nrm, reg=gi)
    c = sum(pts, Vector()) / 3
    for k in range(3):
        k2 = (k + 1) % 3
        pc.face([pts[k], pts[k2], top[k2], top[k]], 1, R_PLAN, (pts[k] + pts[k2]) / 2 - c, reg=gi)

def floor_debris(pc, x0, x1, side, n, seed, kinds=("putz", "schuppe", "ziegel", "splitter")):
    """Am Fuss der Wand: Putzbrocken, Putzschuppen, Ziegelbroeckchen, Holzsplitter (hoechstens 12 cm vor der Wand)."""
    rng = random.Random(seed)
    s = side
    for k in range(n):
        kind = kinds[k % len(kinds)]
        x = rng.uniform(x0, x1)
        y = s * (T2 + rng.uniform(0.045, 0.085))
        n0 = set(pc.bm.verts)
        if kind == "putz":
            sz = rng.uniform(0.012, 0.03)
            chunk(pc, (x, y, sz * 0.4), (sz * 1.5, sz, sz * 0.45), seed * 10 + k, "altputz", subdiv=0)
        elif kind == "ziegel":
            sz = rng.uniform(0.01, 0.022)
            chunk(pc, (x, y, sz * 0.5), (sz * 1.4, sz, sz * 0.8), seed * 10 + k, "bruch", subdiv=0)
        elif kind == "schuppe":
            shard(pc, x, y, seed * 100 + k, size=(0.015, 0.035), thick=0.004)
        else:
            a = rng.uniform(0, math.tau)
            splinter(pc, (x, y, 0.0005), (math.cos(a), math.sin(a), 0.03), rng.uniform(0.03, 0.08), rng.uniform(0.004, 0.009),
                     rng.uniform(0.002, 0.004))
        keep_in_front(pc, new_verts(pc, n0), s)

# ---------- Fertigstellen, Pruefen, Export ----------
PIECES = []
def finish(pc):
    bm = pc.bm
    bm.normal_update()
    quads = [f for f in bm.faces if f[pc.rule] in (R_PLAN, R_PLANAX, R_METAL) and len(f.verts) > 3]
    if quads:
        bmesh.ops.triangulate(bm, faces=quads)
    apply_uvs(pc)
    # Rohre: Seitenflaechen nach aussen drehen (Mittelpunkt der Flaeche minus Achse)
    me = bpy.data.meshes.new(pc.name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MAT_W)
    me.materials.append(MAT_D)
    ob = bpy.data.objects.new(pc.name, me)
    scene.collection.objects.link(ob)
    me.calc_loop_triangles()
    tris = len(me.loop_triangles)
    uvl = me.uv_layers.active.data
    dens, area_sum, wsum = [], 0.0, 0.0
    for lt in me.loop_triangles:
        a3 = lt.area
        if a3 < 1e-10 and os.environ.get("DIAG"):
            cen = sum((me.vertices[i].co for i in lt.vertices), Vector()) / 3
            log("  entartet", pc.name, "Flaeche", lt.polygon_index, "Ecken", len(me.polygons[lt.polygon_index].vertices),
                "Mat", me.polygons[lt.polygon_index].material_index, "bei", tuple(round(c, 4) for c in cen))
        if a3 < 2e-7:
            continue
        (u1, v1), (u2, v2), (u3, v3) = (uvl[i].uv for i in lt.loops)
        a2 = abs((u2 - u1) * (v3 - v1) - (u3 - u1) * (v2 - v1)) / 2 * TEXRES * TEXRES
        d = math.sqrt(a2 / a3)
        if os.environ.get("DIAG") and (d > 1100 or d < 950):
            cen = sum((me.vertices[i].co for i in lt.vertices), Vector()) / 3
            log("  Ausreisser", pc.name, round(d), "Flaeche", lt.polygon_index, "Mat", me.polygons[lt.polygon_index].material_index,
                "Ecken", len(me.polygons[lt.polygon_index].vertices), "bei", tuple(round(c, 3) for c in cen), "A", round(a3 * 1e4, 3), "cm2")
        dens.append(d)
        area_sum += a3
        wsum += d * a3
    ymax = max(abs(v.co.y) for v in me.vertices)
    info = {"name": pc.name, "dreiecke": tris, "dichte_min": round(min(dens)), "dichte_max": round(max(dens)),
            "dichte_mittel": round(wsum / area_sum), "vorstand_cm": round((ymax - T2) * 100, 1)}
    PIECES.append((ob, info))
    log("Stueck", info)
    return ob

def export(ob):
    folder = os.path.join(MODELLE, ob.name)
    os.makedirs(folder, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(folder, ob.name + ".gltf"), export_format="GLTF_SEPARATE",
                              use_selection=True, export_yup=True, export_apply=True,
                              export_texture_dir=f"../../Texturen/{GEB}", export_image_format="AUTO",
                              export_materials="EXPORT", export_cameras=False, export_lights=False)

# ======================= Anbauteile =======================
def door_frame(pc):
    """Zarge aus dunklem Holz: Futter in der Laibung, Bekleidung beidseitig 9 cm breit und 2 cm vor der Wand,
    Anschlag auf der -Y-Seite, zwei Baender. Die Kanten sind gefast (abgegriffen, heller)."""
    x0, x1, zt = -0.65, 0.65, 2.2
    cw, cd, bev = 0.09, 0.02, 0.004
    for x, sg in ((x0, 1), (x1, -1)):
        pc.face([Vector((x, -T2, 0.0)), Vector((x, T2, 0.0)), Vector((x, T2, zt)), Vector((x, -T2, zt))], 1, R_HOLZ, (sg, 0, 0), par=(0, 0, 1))
    pc.face([Vector((x0, -T2, zt)), Vector((x1, -T2, zt)), Vector((x1, T2, zt)), Vector((x0, T2, zt))], 1, R_HOLZ, (0, 0, -1), par=(1, 0, 0))
    for s in (-1, 1):
        ys = sorted((s * T2, s * (T2 + cd)))
        fs = box_faces(pc, (x0 - cw, ys[0], 0.0), (x0, ys[1], zt), R_HOLZ, bevel=bev, axis=(0, 0, 1))
        fs += box_faces(pc, (x1, ys[0], 0.0), (x1 + cw, ys[1], zt), R_HOLZ, bevel=bev, axis=(0, 0, 1))
        fs += box_faces(pc, (x0 - cw, ys[0], zt), (x1 + cw, ys[1], zt + cw), R_HOLZ, bevel=bev, axis=(1, 0, 0))
        drop_back(pc, fs, s)
    st = 0.016
    for a, b in ((x0, x0 + st), (x1 - st, x1)):
        box_faces(pc, (a, -0.062, 0.0), (b, -0.04, zt - st), R_HOLZ, bevel=0.002, axis=(0, 0, 1))
    box_faces(pc, (x0 + st, -0.062, zt - st), (x1 - st, -0.04, zt), R_HOLZ, bevel=0.002, axis=(1, 0, 0))
    for zc in (0.28, 1.92):
        tube(pc, [(x0 + 0.006, -0.071, zc), (x0 + 0.006, -0.071, zc + 0.11)], 0.007, "metall_07", seg=8)

def window_frame(pc):
    """Fenster: Putzlaibung, Blendrahmen aus dunklem Holz in der Wandmitte (ohne Glas, ohne Fluegel, ohne Gitter),
    Holzbaenke auf beiden Seiten, Bekleidung 9 cm breit und 2 cm vor der Wand."""
    x0, x1, z0, z1 = -0.75, 0.75, 0.95, 2.35
    for x, sg in ((x0, 1), (x1, -1)):
        pc.face([Vector((x, -T2, z0)), Vector((x, T2, z0)), Vector((x, T2, z1)), Vector((x, -T2, z1))], 0, R_REVX, (sg, 0, 0))
    pc.face([Vector((x0, -T2, z1)), Vector((x1, -T2, z1)), Vector((x1, T2, z1)), Vector((x0, T2, z1))], 0, R_REVZ, (0, 0, -1), par=(z1, 0, 0))
    fw, fd, bev = 0.06, 0.03, 0.003
    box_faces(pc, (x0, -fd, z0 + fw), (x0 + fw, fd, z1 - fw), R_HOLZ, bevel=bev, axis=(0, 0, 1))
    box_faces(pc, (x1 - fw, -fd, z0 + fw), (x1, fd, z1 - fw), R_HOLZ, bevel=bev, axis=(0, 0, 1))
    box_faces(pc, (x0, -fd, z1 - fw), (x1, fd, z1), R_HOLZ, bevel=bev, axis=(1, 0, 0))
    box_faces(pc, (x0, -fd, z0), (x1, fd, z0 + fw), R_HOLZ, bevel=bev, axis=(1, 0, 0))
    # Falz: schmale Leiste, an der die Fluegel anschlugen
    box_faces(pc, (x0 + fw, -0.012, z0 + fw), (x0 + fw + 0.012, 0.012, z1 - fw), R_HOLZ, axis=(0, 0, 1))
    box_faces(pc, (x1 - fw - 0.012, -0.012, z0 + fw), (x1 - fw, 0.012, z1 - fw), R_HOLZ, axis=(0, 0, 1))
    box_faces(pc, (x0 + fw + 0.012, -0.012, z1 - fw - 0.012), (x1 - fw - 0.012, 0.012, z1 - fw), R_HOLZ, axis=(1, 0, 0))
    for s in (-1, 1):
        ys = sorted((s * fd, s * (T2 + 0.04)))
        box_faces(pc, (x0 - 0.1, ys[0], z0 - 0.03), (x1 + 0.1, ys[1], z0), R_HOLZ, bevel=0.004, axis=(1, 0, 0))
        ys = sorted((s * T2, s * (T2 + 0.02)))
        fs = box_faces(pc, (x0 - 0.09, ys[0], z0), (x0, ys[1], z1), R_HOLZ, bevel=0.004, axis=(0, 0, 1))
        fs += box_faces(pc, (x1, ys[0], z0), (x1 + 0.09, ys[1], z1), R_HOLZ, bevel=0.004, axis=(0, 0, 1))
        fs += box_faces(pc, (x0 - 0.09, ys[0], z1), (x1 + 0.09, ys[1], z1 + 0.09), R_HOLZ, bevel=0.004, axis=(1, 0, 0))
        drop_back(pc, fs, s)
    # Baender, an denen die Fluegel hingen
    for x in (x0 + fw + 0.006, x1 - fw - 0.006):
        for zc in (z0 + 0.2, z1 - 0.3):
            tube(pc, [(x, -0.02, zc), (x, -0.02, zc + 0.07)], 0.006, "metall_07", seg=8)

def pipe_clamp(pc, side, x, yc, zc, r):
    """Rohrschelle, mitgestrichen, mit Wandplatte und Stift."""
    s = side
    rr = r + 0.004
    tube(pc, [(x - 0.011, s * yc, zc), (x + 0.011, s * yc, zc)], rr, "rohr", seg=12, caps=True, uoff=0.3)
    ys = sorted((s * T2, s * (T2 + 0.005)))
    drop_back(pc, box_faces(pc, (x - 0.018, ys[0], zc - 0.022), (x + 0.018, ys[1], zc + 0.022), R_METAL, bevel=0.0015), s)
    ys2 = sorted((s * (T2 + 0.005), s * (yc - rr + 0.001)))
    box_faces(pc, (x - 0.006, ys2[0], zc - 0.006), (x + 0.006, ys2[1], zc + 0.006), R_METAL)

def heating(pc, side):
    """Heizungsrohre: Vor- und Ruecklauf in Kniehoehe, zwei Rohre unter der Decke; buendig an beiden Kanten."""
    for zc, r, gap in ((0.40, 0.021, 0.022), (0.50, 0.021, 0.022), (3.13, 0.02, 0.014), (3.24, 0.026, 0.014)):
        yc = T2 + gap + r
        tube(pc, [(-W2, side * yc, zc), (W2, side * yc, zc)], r, "rohr", seg=12, caps=False, uoff=0.0)
        for x in (-1.3, 0.0, 1.3):
            pipe_clamp(pc, side, x, yc, zc, r)

def feuermelder(pc, side, xc, zc):
    """Druckknopfmelder: rotes Gehaeuse, Scheibe eingeschlagen (Scherben im Rahmen und am Boden), dahinter der Knopf,
    Nothammer an einer Kette, Leerrohr nach oben zu einer Abzweigdose."""
    s = side
    W, HH, T = MELDER_W, MELDER_H, MELDER_T
    bx0, bx1 = xc - W / 2, xc + W / 2
    bz0, bz1 = zc - HH / 2, zc + HH / 2
    y1 = T2 + T
    par = (bx1, bz0, -1) if s > 0 else (bx0, bz0, 1)
    def fx(px):
        return bx1 - px if s > 0 else bx0 + px
    wx0, wx1 = sorted((fx(0.025), fx(W - 0.025)))
    wz0, wz1 = bz0 + 0.028, bz0 + 0.108
    win = rect(wx0, wx1, wz0, wz1)
    pc.tess(rect(bx0, bx1, bz0, bz1), [win], s * y1, 1, R_BOXFRONT, (0, s, 0), par=par)
    mi = PLAN_REG.index("melder")
    corners = [(bx0, bz0), (bx1, bz0), (bx1, bz1), (bx0, bz1)]
    for k in range(4):
        a, b = corners[k], corners[(k + 1) % 4]
        P = [Vector((a[0], s * T2, a[1])), Vector((b[0], s * T2, b[1])), Vector((b[0], s * y1, b[1])), Vector((a[0], s * y1, a[1]))]
        pc.face(P, 1, R_PLAN, edge_inward(corners, k, True) * -1, reg=mi)
    yr = y1 - 0.012
    wc = [(wx0, wz0), (wx1, wz0), (wx1, wz1), (wx0, wz1)]
    for k in range(4):
        a, b = wc[k], wc[(k + 1) % 4]
        P = [Vector((a[0], s * y1, a[1])), Vector((b[0], s * y1, b[1])), Vector((b[0], s * yr, b[1])), Vector((a[0], s * yr, a[1]))]
        pc.face(P, 1, R_PLAN, edge_inward(wc, k, True), reg=mi)
    pc.tess(win, [], s * yr, 1, R_BOXFRONT, (0, s, 0), par=par)
    # Scherben, die noch im Rahmen stecken
    rng = random.Random(23)
    gi = PLAN_REG.index("glas")
    yg = s * (y1 - 0.004)
    for (ax, az), (bx, bz), (cx, cz) in (((wx0, wz1), (wx0 + 0.035, wz1), (wx0 + 0.008, wz1 - 0.03)),
                                         ((wx1, wz0), (wx1, wz0 + 0.04), (wx1 - 0.022, wz0 + 0.006)),
                                         ((wx0, wz0), (wx0 + 0.018, wz0), (wx0, wz0 + 0.024)),
                                         ((wx1 - 0.03, wz1), (wx1, wz1), (wx1, wz1 - 0.05)),
                                         ((wx0 + 0.045, wz0), (wx0 + 0.075, wz0), (wx0 + 0.058, wz0 + 0.016))):
        P = [Vector((ax, yg, az)), Vector((bx, yg, bz)), Vector((cx, yg, cz))]
        Q = [p + Vector((0, -s * 0.002, 0)) for p in P]
        pc.face(P, 1, R_PLAN, (0, s, 0), reg=gi)
        pc.face(Q[::-1], 1, R_PLAN, (0, -s, 0), reg=gi)
        cen = sum(P, Vector()) / 3
        for k in range(3):
            k2 = (k + 1) % 3
            pc.face([P[k], P[k2], Q[k2], Q[k]], 1, R_PLAN, (P[k] + P[k2]) / 2 - cen, reg=gi)
    for k in range(9):
        x = xc + rng.uniform(-0.18, 0.18)
        glass_shard(pc, x, s * (T2 + rng.uniform(0.04, 0.09)), 0.0005, rng, size=(0.006, 0.02), t=0.0018,
                    normal=(rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 1))
    # Nothammer an der Kette (Glieder abwechselnd quer)
    hx = bx0 - 0.03 if s > 0 else bx1 + 0.03
    eye = Vector((bx0 if s > 0 else bx1, s * (T2 + 0.025), bz1 - 0.02))
    end = Vector((hx, s * (T2 + 0.014), bz1 - 0.13))
    nl = 9
    for k in range(nl):
        c = eye.lerp(end, (k + 0.5) / nl) + Vector((0.004 * math.sin(k * 1.3), 0, 0))
        d = (end - eye).normalized()
        q = d.cross(Vector((0, 1, 0))).normalized() if k % 2 else Vector((0, 1, 0))
        q = (q - d * q.dot(d)).normalized()
        r_ = d.cross(q)
        L, Wl, Tl = (end - eye).length / nl * 0.62, 0.0045, 0.0015
        P = [c + d * a * L + q * b * Wl + r_ * e * Tl for a, b, e in
             ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1))]
        for quad, nrm in (((0, 1, 2, 3), -r_), ((4, 5, 6, 7), r_), ((0, 1, 5, 4), -q), ((3, 2, 6, 7), q), ((0, 3, 7, 4), -d),
                          ((1, 2, 6, 5), d)):
            pc.face([P[i] for i in quad], 1, R_PLAN, nrm, reg=PLAN_REG.index("metall_03"))
    hz1 = end.z - 0.003
    ys = sorted((s * (T2 + 0.008), s * (T2 + 0.02)))
    box_faces(pc, (hx - 0.005, ys[0], hz1 - 0.075), (hx + 0.005, ys[1], hz1), R_PLAN, reg=mi, bevel=0.0015)
    ys = sorted((s * (T2 + 0.006), s * (T2 + 0.022)))
    box_faces(pc, (hx - 0.019, ys[0], hz1 - 0.089), (hx + 0.019, ys[1], hz1 - 0.075), R_METAL, bevel=0.002)
    # Leerrohr zur Abzweigdose
    yl = s * (T2 + 0.009)
    tube(pc, [(xc, yl, bz1), (xc, yl, 2.95)], 0.008, "metall_07", seg=8, caps=False)
    for zz in (bz1 + 0.25, bz1 + 0.75, 2.85):
        ys = sorted((s * T2, s * (T2 + 0.019)))
        drop_back(pc, box_faces(pc, (xc - 0.012, ys[0], zz - 0.006), (xc + 0.012, ys[1], zz + 0.006), R_METAL), s)
    ys = sorted((s * T2, s * (T2 + 0.035)))
    drop_back(pc, box_faces(pc, (xc - 0.035, ys[0], 2.95), (xc + 0.035, ys[1], 3.02), R_METAL, bevel=0.003), s)

# ======================= Durchbruch =======================
def through_hole_outline(seed=3.1, N=80):
    """Unregelmaessiger Umriss: 1,44 m breit, 1,32 m hoch, Unterkante bei 0,96 m."""
    pts = []
    for k in range(N):
        a = 2 * math.pi * k / N
        c, s = math.cos(a), math.sin(a)
        r = 1 + 0.17 * noise.noise(Vector((c * 1.4, s * 1.4, seed))) + 0.07 * noise.noise(Vector((c * 4.5, s * 4.5, seed + 2))) \
            + 0.045 * noise.noise(Vector((c * 14, s * 14, seed + 5))) + 0.02 * noise.noise(Vector((c * 34, s * 34, seed + 9)))
        pts.append((c * r, s * r))
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    sx = 0.72 / max(abs(min(xs)), abs(max(xs)))
    sz = 0.66 / max(abs(min(zs)), abs(max(zs)))
    return [(p[0] * sx, 1.62 + p[1] * sz) for p in pts]

def board_piece(pc, p, ang, L, w, t, tilt=0.0):
    """Brettstueck im Schutt: Oberseite mit dem Holz der Vertaefelung, Rest frisches Bruchholz."""
    d = Vector((math.cos(ang), math.sin(ang), 0))
    n = Vector((-math.sin(ang), math.cos(ang), 0))
    up = Vector((0, 0, 1))
    R = Matrix.Rotation(tilt, 3, d)
    c = Vector(p)
    def P(a, b, h):
        return c + R @ (d * a + n * b + up * h)
    bot = [P(-L / 2, -w / 2, 0), P(L / 2, -w / 2, 0), P(L / 2, w / 2, 0), P(-L / 2, w / 2, 0)]
    top = [P(-L / 2, -w / 2, t), P(L / 2, -w / 2, t), P(L / 2, w / 2, t), P(-L / 2, w / 2, t)]
    pc.face(top, 0, R_SHARD, R @ up, par=(1, 0, 0))
    ki = PLAN_REG.index("kerbe")
    pc.face(bot[::-1], 1, R_PLANAX, -(R @ up), par=tuple(d), reg=PLAN_REG.index("brett"))
    cen = c + R @ (up * t / 2)
    for k in range(4):
        k2 = (k + 1) % 4
        Q = [bot[k], bot[k2], top[k2], top[k]]
        pc.face(Q, 1, R_PLANAX, (bot[k] + top[k2]) / 2 - cen, par=tuple(d), reg=ki)

def rubble(pc, side, xc, seed):
    """Schuttkegel bis 60 cm vor der Wand: Ziegelbrocken, Putzbrocken und -schuppen, Brettstuecke, Splitter, Latten."""
    rng = random.Random(int(seed * 100) + (5 if side > 0 else 1))
    nxp, nyp = 12, 6
    rx, ry, hmax = 0.8, 0.5, 0.2
    V = []
    for i in range(nxp + 1):
        sx = 2 * i / nxp - 1
        reach = min(1.0, 0.8 + 0.2 * noise.noise(Vector((sx * 2.2, side * 5.0, seed))))
        row = []
        for j in range(nyp + 1):
            t = j / nyp
            half = rx * math.sqrt(max(0.0, 1 - (0.8 * t) ** 2)) * (1 + 0.1 * noise.noise(Vector((t * 3.0, side * 3.0, seed + 1.4))))
            x = xc + half * sx
            yd = 0.029 + ry * reach * t
            fall = max(0.0, 1 - sx * sx) * max(0.0, 1 - t ** 1.4)
            fall *= 1 + 0.3 * noise.noise(Vector((x * 2.5, yd * 2.5, side * 3 + seed)))
            lump = 0.03 * noise.noise(Vector((x * 8, yd * 8, side + seed))) + 0.012 * noise.noise(Vector((x * 22, yd * 22, side + seed + 5)))
            z = hmax * fall + (lump * min(1.0, 4 * fall) if 0 < i < nxp and j < nyp else 0)
            row.append(Vector((x, side * (T2 + yd), max(0.0, z))))
        V.append(row)
    for i in range(nxp):
        for j in range(nyp):
            P = [V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]]
            if max(p.z for p in P) < 0.002:
                continue
            pc.face(P, 1, R_PLAN, (0, side * 0.3, 1), reg=PLAN_REG.index("bruch"))
    idx = lambda i, j: i * (nyp + 1) + j
    tree = BVHTree.FromPolygons([v for row in V for v in row],
                                [(idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)) for i in range(nxp) for j in range(nyp)])
    def heap_z(x, yd):
        hit = tree.ray_cast(Vector((x, side * (T2 + yd), 2.0)), Vector((0, 0, -1)))
        return max(0.0, hit[0].z) if hit[0] is not None else 0.0
    off = 20 if side > 0 else 0
    for k in range(6):
        x, yd, s_ = xc + rng.uniform(-0.55, 0.55), rng.uniform(0.08, 0.32), rng.uniform(0.045, 0.075)
        chunk(pc, (x, side * (T2 + yd), heap_z(x, yd) + s_ * 0.35), (s_ * 1.5, s_ * 0.8, s_ * 0.6), 60 + k + off,
              "ziegel" if k % 2 else "bruch")
    for k in range(6):
        x, yd, s_ = xc + rng.uniform(-0.65, 0.65), rng.uniform(0.05, 0.42), rng.uniform(0.015, 0.035)
        chunk(pc, (x, side * (T2 + yd), heap_z(x, yd) * 0.95 + s_ * 0.3), (s_ * 1.3, s_, s_ * 0.7), 120 + k + off, "bruch", subdiv=0)
    for k in range(4):
        x, yd, s_ = xc + rng.uniform(-0.6, 0.6), rng.uniform(0.06, 0.38), rng.uniform(0.04, 0.07)
        chunk(pc, (x, side * (T2 + yd), heap_z(x, yd) + s_ * 0.18), (s_ * 1.4, s_, s_ * 0.35), 200 + k + off, "altputz", subdiv=0)
    for k in range(6):
        x, yd = xc + rng.uniform(-0.6, 0.6), rng.uniform(0.06, 0.4)
        shard(pc, x, side * (T2 + yd), 300 + k + off, size=(0.04, 0.08), zbase=max(0.0, heap_z(x, yd) - 0.004), thick=0.012)
    for k in range(4):
        x, yd = xc + rng.uniform(-0.5, 0.5), rng.uniform(0.1, 0.36)
        L = rng.uniform(0.12, 0.26)
        board_piece(pc, (x, side * (T2 + yd), heap_z(x, yd) + 0.002), math.pi / 2 + rng.uniform(-0.5, 0.5), L, BW - 2 * BC, BT,
                    tilt=rng.uniform(-0.25, 0.25))
    for k in range(7):
        x, yd = xc + rng.uniform(-0.6, 0.6), rng.uniform(0.06, 0.45)
        a = rng.uniform(0, math.tau)
        L = rng.uniform(0.05, 0.14)
        z = heap_z(x, yd) + 0.001
        x2, yd2 = x + math.cos(a) * L, yd + math.sin(a) * L * side
        z2 = heap_z(x2, max(0.03, yd2)) + 0.001
        splinter(pc, (x, side * (T2 + yd), z), (math.cos(a), math.sin(a), (z2 - z) / L), L, rng.uniform(0.005, 0.012),
                 rng.uniform(0.002, 0.004))
    for k in range(2):
        x, yd = xc + rng.uniform(-0.4, 0.4), rng.uniform(0.12, 0.3)
        a = rng.uniform(-0.6, 0.6)
        z = heap_z(x, yd) + 0.002
        splinter(pc, (x, side * (T2 + yd), z), (math.cos(a), side * math.sin(a), 0.05), rng.uniform(0.2, 0.3), 0.036, 0.01, reg="latte")

def jag_splinters(pc, side, xs, zf, rng, n=2, free=(-9.0, 9.0)):
    """Lange Splitter, die aus der Bruchkante nach oben und etwas nach vorn stehen (nur wo keine Leiste darueber ist)."""
    ks = [k for k in range(1, len(xs) - 1) if free[0] + 0.012 < xs[k] < free[1] - 0.012]
    for k in rng.sample(ks, min(n, len(ks))):
        d = Vector((rng.uniform(-0.25, 0.25), side * rng.uniform(0.1, 0.35), 1.0))
        splinter(pc, (xs[k], side * (T2 - 0.004), zf[k] - 0.006), d, rng.uniform(0.04, 0.1), rng.uniform(0.005, 0.01),
                 rng.uniform(0.002, 0.003), n=(1, 0, 0))

# ======================= Die sieben Stuecke =======================
FULL = [(-W2, W2)]
WALL = rect(-W2, W2, BZ1, H)

def plaster(pc, side, outer, holes=()):
    pc.tess(outer, list(holes), side * T2, 0, R_WM if side < 0 else R_WP, (0, side, 0))

def wand_01():
    pc = Piece(f"{GEB}_wand_01")
    shell(pc)
    cm = merge_carvings(carve(pc, -1, "MAJA", -1.07, 0.88, 0.045, slant=0.08), carve(pc, -1, "<", 0.42, 0.8, 0.05),
                        carve(pc, -1, "1973", 0.91, 0.66, 0.04, slant=-0.05))
    cp = merge_carvings(carve(pc, 1, "UWE", -0.38, 0.95, 0.045), carve(pc, 1, "7C", 0.72, 0.6, 0.04, slant=0.1))
    boards(pc, -1, carvings=cm)
    boards(pc, 1, carvings=cp)
    for s in (-1, 1):
        plaster(pc, s, WALL)
        strips(pc, s, FULL, FULL)
    return finish(pc)

def broken_state(i, zbase, seed, spikes=2):
    rng = random.Random(seed)
    bx0, bx1 = board_x(i)
    xs, zs = jag_line(bx0 + BC, bx1 - BC, zbase, rng, spikes=spikes)
    return ("bruch", xs, zs)

def wand_02():
    pc = Piece(f"{GEB}_wand_02")
    shell(pc)
    crack = [(0.42, 3.33), (0.37, 3.1), (0.46, 2.86), (0.34, 2.6), (0.41, 2.36), (0.31, 2.12), (0.36, 1.9)]
    wid = [0.002, 0.008, 0.014, 0.02, 0.018, 0.01, 0.003]
    # -Y: grosse Putzabplatzung mit Ziegel, darunter eine kleinere mit Holzlatten, tiefer Riss, Bretter fehlen/lose/gebrochen
    hm = [groove(pc, crack, wid, -1, 0.07)]
    hm.append(plaster_loss(pc, -1, noisy_loop(-0.55, 2.25, 0.56, 0.42, 44, 1.3, 0.2), missing=3))
    hm.append(plaster_loss(pc, -1, noisy_loop(0.9, 1.68, 0.3, 0.26, 36, 2.9, 0.18), missing=1, lathing=True, seed=5))
    check_holes(pc.name, hm)
    plaster(pc, -1, WALL, hm)
    cm = carve(pc, -1, "TOM", 0.72, 0.93, 0.04, slant=0.1)
    boards(pc, -1, states={9: ("fehlt",), 10: ("fehlt",), 15: broken_state(15, 0.58, 3), 21: ("lose", 0.08, 0.07, 1.1, 77)},
           carvings=cm)
    # +Y: Abplatzung mit Holzlatten, kleine mit Ziegel, der Riss geht durch
    hp = [groove(pc, crack, [w * 0.8 for w in wid], 1, 0.07)]
    hp.append(plaster_loss(pc, 1, noisy_loop(-0.7, 2.45, 0.44, 0.38, 44, 4.1, 0.2), missing=2, lathing=True, seed=8))
    hp.append(plaster_loss(pc, 1, noisy_loop(1.0, 2.9, 0.22, 0.2, 32, 6.6, 0.18), missing=1))
    check_holes(pc.name, hp)
    plaster(pc, 1, WALL, hp)
    boards(pc, 1, states={24: ("fehlt",), 13: ("lose", 0.075, -0.06, 1.12, 78), 18: broken_state(18, 0.45, 4)})
    for s in (-1, 1):
        strips(pc, s, FULL, FULL)
    floor_debris(pc, -1.1, 0.15, -1, 14, 21)
    floor_debris(pc, 0.6, 1.2, -1, 6, 22, kinds=("putz", "splitter", "schuppe"))
    floor_debris(pc, -1.15, -0.25, 1, 12, 23)
    floor_debris(pc, 0.3, 0.7, 1, 4, 24, kinds=("splitter",))
    return finish(pc)

def wand_03():
    pc = Piece(f"{GEB}_wand_03")
    shell(pc)
    cm = carve(pc, -1, "OLE", 0.12, 0.88, 0.045)
    boards(pc, -1, states={26: ("lose", 0.07, -0.05, 1.12, 31)}, carvings=cm)
    hm = [plaster_loss(pc, -1, noisy_loop(-0.85, 2.85, 0.26, 0.2, 32, 6.1, 0.18), missing=1)]
    check_holes(pc.name, hm)
    plaster(pc, -1, WALL, hm)
    boards(pc, 1)
    plaster(pc, 1, WALL)
    for s in (-1, 1):
        strips(pc, s, FULL, FULL)
    heating(pc, 1)
    feuermelder(pc, 1, 0.55, 1.52)
    floor_debris(pc, -1.05, -0.65, -1, 4, 31, kinds=("putz", "schuppe"))
    return finish(pc)

def wand_tuer():
    pc = Piece(f"{GEB}_wand_tuer")
    shell(pc)
    cut = (-0.735, 0.735, 0.0)
    outer = [(-W2, BZ1), (-0.65, BZ1), (-0.65, 2.2), (0.65, 2.2), (0.65, BZ1), (W2, BZ1), (W2, H), (-W2, H)]
    spans = [(-W2, -0.74), (0.74, W2)]
    cm = carve(pc, -1, "KLO", -1.18, 0.98, 0.04)
    boards(pc, -1, states={29: ("fehlt",)}, cut=cut, carvings=cm)
    plaster(pc, -1, outer)
    hp = [plaster_loss(pc, 1, noisy_loop(-1.05, 2.75, 0.24, 0.22, 32, 8.2, 0.18), missing=1, lathing=True, seed=9)]
    check_holes(pc.name, hp)
    boards(pc, 1, cut=cut)
    plaster(pc, 1, outer, hp)
    for s in (-1, 1):
        strips(pc, s, spans, spans)
    door_frame(pc)
    floor_debris(pc, -1.3, -0.85, 1, 5, 41, kinds=("putz", "schuppe", "ziegel"))
    return finish(pc)

def wand_fenster():
    pc = Piece(f"{GEB}_wand_fenster")
    shell(pc)
    x0, x1, z0, z1 = -0.75, 0.75, 0.95, 2.35
    cut = (x0, x1, z0 - 0.03)
    outer = [(-W2, BZ1), (x0, BZ1), (x0, z1), (x1, z1), (x1, BZ1), (W2, BZ1), (W2, H), (-W2, H)]
    boards(pc, -1, states={7: ("lose", 0.075, 0.06, 1.1, 41)}, cut=cut)
    plaster(pc, -1, outer)
    cp = carve(pc, 1, "JA", 1.02, 0.7, 0.045)
    boards(pc, 1, cut=cut, carvings=cp)
    hp = [plaster_loss(pc, 1, noisy_loop(1.08, 2.86, 0.24, 0.22, 32, 3.3, 0.18), missing=1)]
    check_holes(pc.name, hp)
    plaster(pc, 1, outer, hp)
    spans_l = [(-W2, -0.84), (0.84, W2)]
    for s in (-1, 1):
        strips(pc, s, FULL, spans_l)
    window_frame(pc)
    floor_debris(pc, 0.85, 1.3, 1, 4, 51, kinds=("putz", "schuppe"))
    return finish(pc)

def wand_durchbruch():
    pc = Piece(f"{GEB}_wand_durchbruch")
    shell(pc)
    hole = through_hole_outline()
    check_holes(pc.name, [hole])
    hits = line_hits(hole, "h", BZ1 + 0.002) + line_hits(hole, "h", LEISTE_TOP - 0.002)
    cut_lo, cut_hi = min(h[0] for h in hits) - 0.05, max(h[1] for h in hits) + 0.05
    spans_l = [(-W2, cut_lo), (cut_hi, W2)]
    loops = {-1: [noisy_loop(-1.08, 2.78, 0.3, 0.28, 36, 7.7, 0.15)], 1: [noisy_loop(1.06, 2.72, 0.3, 0.28, 36, 9.1, 0.15)]}
    for s in (-1, 1):
        rng = random.Random(17 + s)
        states = {}
        tops = {}
        idx = [i for i in range(NB) if board_x(i)[1] > cut_lo and board_x(i)[0] < cut_hi]
        mid = sorted(idx, key=lambda i: abs(sum(board_x(i)) / 2 - (0.12 if s > 0 else -0.08)))
        gone = set(mid[:2])
        loose = mid[3]
        for i in idx:
            bx0, bx1 = board_x(i)
            if i in gone:
                states[i] = ("fehlt",)
                continue
            if i == loose:
                states[i] = ("lose", 0.07, 0.09 * s, 0.74 + rng.uniform(-0.05, 0.05), 90 + i)
                continue
            xs, dz = jag_line(bx0 + BC, bx1 - BC, 0.0, rng, spikes=2, spike=(0.03, 0.08))
            cen = abs((bx0 + bx1) / 2) / 0.75
            drop = rng.uniform(0.0, 0.32) * max(0.0, 1.0 - cen) ** 0.7
            zf = []
            for x, d in zip(xs, dz):
                segs = line_hits(hole, "v", x)
                zh = segs[0][0] if segs else 9.0
                zf.append(min(BZ1 - 0.004, min(BZ1 - rng.uniform(0.015, 0.04), zh - rng.uniform(0.012, 0.035)) - drop + d))
            states[i] = ("bruch", xs, zf)
            tops[i] = (xs, zf)
        boards(pc, s, states=states, hole=hole)
        for i, (xs, zf) in tops.items():
            jag_splinters(pc, s, xs, zf, rng, n=2 if i % 2 else 3, free=(cut_lo, cut_hi))
        # Unterkante des Putzes zwischen dem Ende der Leiste und dem Loch
        for a, b in subtract_spans(cut_lo, cut_hi, line_hits(hole, "h", BZ1 + 0.0005), 0.0):
            pc.face([Vector((a, s * (T2 - BC), BZ1)), Vector((b, s * (T2 - BC), BZ1)), Vector((b, s * T2, BZ1)), Vector((a, s * T2, BZ1))],
                    1, R_PLAN, (0, 0, -1), reg=PLAN_REG.index("altputz"))
        holes = [plaster_loss(pc, s, lp, missing=1, lathing=(s > 0), seed=12) for lp in loops[s]]
        check_holes(pc.name, holes)
        surface(pc, WALL, [hole] + holes, s * T2, s, R_WM if s < 0 else R_WP, mat=0)
        strips(pc, s, FULL, spans_l)
    # Bruchflaeche durch die Wand: im Putzbereich von Flaeche zu Flaeche, unten von Mauer zu Mauer (Bretter sind weg)
    n = len(hole)
    cx = sum(p[0] for p in hole) / n
    cz = sum(p[1] for p in hole) / n
    grid = []
    for k in range(n):
        x, z = hole[k]
        ux, uz = x - cx, z - cz
        l = math.hypot(ux, uz) or 1.0
        ux, uz = ux / l, uz / l
        yo = T2 if z >= BZ1 else YM
        colm = []
        for j in range(5):
            y = -yo + 2 * yo * j / 4
            if 0 < j < 4:
                d = 0.03 * noise.noise(Vector((x * 5, y * 9, z * 5))) + 0.012 * noise.noise(Vector((x * 18, y * 18, z * 18))) + 0.018
                colm.append(Vector((min(0.795, max(-0.795, x + ux * d)), y, min(2.395, max(0.905, z + uz * d)))))
            else:
                colm.append(Vector((x, y, z)))
        grid.append(colm)
    ccw = loop_area(hole) > 0
    for k in range(n):
        k2 = (k + 1) % n
        for j in range(4):
            P = [grid[k][j], grid[k2][j], grid[k2][j + 1], grid[k][j + 1]]
            pc.face(P, 1, R_PLAN, edge_inward(hole, k, ccw), reg=PLAN_REG.index("bruch"))
    rubble(pc, -1, cx * 0.3, 3.3)
    rubble(pc, 1, cx * 0.3, 5.1)
    return finish(pc)

def wand_ecke():
    """Eckpfosten 21 x 21 cm: unten Vertaefelung mit V-Fugen im 10-cm-Raster, oben Putz; Sockel- und Holzleiste rundum."""
    pc = Piece(f"{GEB}_wand_ecke")
    a = 0.105
    # je Seite: Normale, Lage eines Punkts (c = Weltkoordinate entlang der Seite, dn = Tiefe nach innen)
    faces = [((0, -1, 0), lambda c, dn, z: Vector((c, -a + dn, z))), ((1, 0, 0), lambda c, dn, z: Vector((a - dn, c, z))),
             ((0, 1, 0), lambda c, dn, z: Vector((c, a - dn, z))), ((-1, 0, 0), lambda c, dn, z: Vector((-a + dn, c, z)))]
    def post_u(nrm, p):
        if nrm == (0, -1, 0):
            return UVS * p.x
        if nrm == (0, 1, 0):
            return -UVS * p.x + 0.5
        if nrm == (1, 0, 0):
            return UVS * p.y
        return -UVS * p.y + 0.5
    def keep(P, nrm):
        f = pc.face(P, 0, R_KEEP, nrm)
        for l in f.loops:
            l[pc.uv].uv = (post_u(nrm, l.vert.co), UVS * l.vert.co.z)
    bi = PLAN_REG.index("brett")
    for nrm, pos in faces:
        keep([pos(-a, 0, BZ1), pos(a, 0, BZ1), pos(a, 0, H), pos(-a, 0, H)], nrm)
        edges = [-a, -0.1, 0.0, 0.1, a]
        for k in range(4):
            c0 = edges[k] + (BC if k > 0 else 0.0)
            c1 = edges[k + 1] - (BC if k < 3 else 0.0)
            keep([pos(c0, 0, 0.0), pos(c1, 0, 0.0), pos(c1, 0, BZ1), pos(c0, 0, BZ1)], nrm)
        for g in (-0.1, 0.0, 0.1):
            for sg in (-1, 1):
                P = [pos(g, BC, 0.0), pos(g + sg * BC, 0, 0.0), pos(g + sg * BC, 0, BZ1), pos(g, BC, BZ1)]
                out = Vector(nrm) + (pos(g + sg, 0, 0) - pos(g, 0, 0))
                pc.face(P, 1, R_VFIX, out, reg=bi, par=((g * 3.7 + 0.2 * sg + 0.1 * nrm[0] + 0.3 * nrm[1]) % 1.0, 0, 0))
    pc.face([Vector((-a, -a, H)), Vector((a, -a, H)), Vector((a, a, H)), Vector((-a, a, H))], 0, R_TOP, (0, 0, 1))
    sides = [((0, -1, 0), (-a, -a), (a, -a)), ((1, 0, 0), (a, -a), (a, a)), ((0, 1, 0), (a, a), (-a, a)), ((-1, 0, 0), (-a, a), (-a, -a))]
    for prof, reg in ((SOCKEL_PROF, "sockel"), (LEISTE_PROF, "leiste")):
        z0r = REG[reg][0]
        s = [0.0]
        for i in range(1, len(prof)):
            s.append(s[-1] + math.hypot(prof[i][0] - prof[i - 1][0], prof[i][1] - prof[i - 1][1]))
        for nrm, p0, p1 in sides:
            nv = Vector(nrm)
            t = Vector((p1[0] - p0[0], p1[1] - p0[1], 0)).normalized()
            for i in range(len(prof) - 1):
                (d0, za), (d1, zb) = prof[i], prof[i + 1]
                A0 = Vector((p0[0], p0[1], 0)) + nv * d0 - t * d0
                A1 = Vector((p1[0], p1[1], 0)) + nv * d0 + t * d0
                B0 = Vector((p0[0], p0[1], 0)) + nv * d1 - t * d1
                B1 = Vector((p1[0], p1[1], 0)) + nv * d1 + t * d1
                P = [Vector((A0.x, A0.y, za)), Vector((A1.x, A1.y, za)), Vector((B1.x, B1.y, zb)), Vector((B0.x, B0.y, zb))]
                ua = [post_u(nrm, P[k]) for k in range(4)]
                uvs = [(ua[0], UVS * (z0r + 0.002 + s[i])), (ua[1], UVS * (z0r + 0.002 + s[i])),
                       (ua[2], UVS * (z0r + 0.002 + s[i + 1])), (ua[3], UVS * (z0r + 0.002 + s[i + 1]))]
                want = nv * (zb - za) + Vector((0, 0, -(d1 - d0)))
                if want.length < 1e-9:
                    want = nv
                pc.face(P, 1, R_KEEP, want, uvs=uvs)
    return finish(pc)

log("Stuecke ...")
BUILD = [wand_01, wand_02, wand_03, wand_tuer, wand_fenster, wand_durchbruch, wand_ecke]
OBJS = []
for fn in BUILD:
    ob = fn()
    OBJS.append(ob)
    export(ob)
    log("exportiert", ob.name)

with open(os.path.join(OUT, f"pruefung_{GEB}.json"), "w", encoding="utf-8") as fjs:
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

# Taschenlampen-Bilder: Stueck, Seite, Kamera (x relativ zur Mitte, |y|, z), Blickziel, Lichtziel
LAMPE = {
    "lampe1": (1, -1, (-1.0, 3.0, 1.55), (-0.1, 0, 1.55), (-0.1, 0, 1.45)),
    "lampe2": (5, 1, (-1.2, 3.0, 1.45), (0.05, 0, 1.2), (0.1, 0, 1.1)),
    "lampe3": (2, 1, (-1.0, 3.0, 1.75), (0.3, 0, 1.75), (0.3, 0, 1.8)),
    "lampe4": (3, -1, (-1.5, 2.8, 1.5), (0.0, 0, 1.2), (0.05, 0, 1.1)),
    "nah1": (0, -1, (-0.78, 0.75, 1.02), (-0.98, 0, 0.9), (-0.98, 0, 0.9), 35),
    "nah2": (2, 1, (0.32, 0.75, 1.55), (0.55, 0, 1.45), (0.55, 0, 1.45), 35),
}

if SHOTS:
    setup_render()
    world = bpy.data.worlds.new("Welt")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    xs = []
    x = 0.0
    for ob in OBJS:
        w = 0.21 if ob.name.endswith("ecke") else 3.8
        ob.location = (x + w / 2, 0, 0)
        xs.append(x + w / 2)
        x += w + 0.5
    total = x - 0.5
    bpy.ops.mesh.primitive_plane_add(size=1, location=(total / 2, 0, 0))
    fl = bpy.context.active_object
    fl.scale = (total + 8, 12, 1)
    fm = bpy.data.materials.new("Boden")
    fm.use_nodes = True
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.09, 0.085, 0.08, 1)
    fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    fl.data.materials.append(fm)
    cam_d = bpy.data.cameras.new("Kamera")
    cam = bpy.data.objects.new("Kamera", cam_d)
    scene.collection.objects.link(cam)
    scene.camera = cam
    def aim(ob, target):
        ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()
    sun_d = bpy.data.lights.new("Licht", "SUN")
    sun_d.energy = 3.0
    sun_d.angle = math.radians(10)
    sun = bpy.data.objects.new("Licht", sun_d)
    scene.collection.objects.link(sun)
    spot_d = bpy.data.lights.new("Taschenlampe", "SPOT")
    spot_d.energy = 0
    spot_d.spot_size = math.radians(58)
    spot_d.spot_blend = 0.55
    spot_d.color = (0.86, 0.92, 1.0)
    spot_d.shadow_soft_size = 0.02
    spot = bpy.data.objects.new("Taschenlampe", spot_d)
    scene.collection.objects.link(spot)
    for shot in SHOTS:
        if shot in ("vorne", "hinten"):
            sgn = -1 if shot == "vorne" else 1
            bg.inputs["Color"].default_value = (0.5, 0.52, 0.55, 1)
            bg.inputs["Strength"].default_value = 0.6
            sun_d.energy = 3.0
            sun.rotation_euler = (math.radians(55), 0, math.radians(-25 if sgn < 0 else 155))
            spot_d.energy = 0
            cam_d.lens = 35
            scene.render.resolution_x, scene.render.resolution_y = RES[0], int(RES[0] * 0.24)
            dist = (total + 1.0) * 35 / 36
            cam.location = (total / 2, sgn * dist, 1.9)
            aim(cam, (total / 2, 0, 1.75))
        else:
            k, sgn, cpos, ctar, ltar = LAMPE[shot][:5]
            lens = LAMPE[shot][5] if len(LAMPE[shot]) > 5 else 20
            ox = OBJS[k].location.x
            bg.inputs["Color"].default_value = (0.02, 0.022, 0.026, 1)
            bg.inputs["Strength"].default_value = 0.3
            sun_d.energy = 0.0
            dist = (Vector((cpos[0], cpos[1], cpos[2])) - Vector((ltar[0], 0, ltar[2]))).length
            spot_d.energy = 420 if lens <= 20 else 420 * (dist / 3.2) ** 2
            cam_d.lens = lens
            scene.render.resolution_x, scene.render.resolution_y = RES
            cam.location = (ox + cpos[0], sgn * cpos[1], cpos[2])
            aim(cam, (ox + ctar[0], 0, ctar[2]))
            spot.location = cam.location + Vector((0.25, 0, -0.2))
            aim(spot, (ox + ltar[0], 0, ltar[2]))
        scene.render.filepath = os.path.join(OUT, f"{GEB}_{shot}.png")
        log("Render", shot)
        bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"{GEB}_wandstuecke.blend"))
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_mainfile()
log("fertig")

