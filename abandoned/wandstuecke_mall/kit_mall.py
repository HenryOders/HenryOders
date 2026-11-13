# ABANDONED · Modulare Wandstuecke fuer das Gebaeude "mall"
# Sieben Stuecke, zwei kachelbare Materialien ("Wand", "Detail") mit je 4096 x 4096 px,
# UV-Massstab 0,25 je Meter (1024 px/m). Export als glTF 2.0 mit gemeinsamen Texturdateien.
# Start: blender -b -P kit_mall.py  (oder mit dem bpy-Modul: python kit_mall.py).
# Das Skript setzt Blender auf Werkseinstellungen zurueck, also nicht in einem offenen Projekt ausfuehren.
import bpy, bmesh, math, random, os, time, json, zlib
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, Quaternion, noise, geometry
from mathutils.bvhtree import BVHTree

T0 = time.time()
def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)

GEB = "mall"
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
TRENN = 1.2                    # Trennlinie: Oberkante der Steinplatten, darueber Gipskarton
SCOLS = [-W2, -1.5, -0.9, -0.3, 0.3, 0.9, 1.5, W2]   # Fugen der Steinplatten (stueckbezogen): 60 cm, Randplatten 40 cm
SROWS = [(0.0, 0.6), (0.6, TRENN)]
JW = 0.0015                    # halbe Fugenbreite (Fuge 3 mm)
BC = 0.0015                    # Fase an den Plattenkanten
ST = 0.015                     # Steinplatte 15 mm
YS = T2 - ST                   # Kleberbett hinter den Platten
GZ = 1.208                     # Unterkante des Gipskartons: Schattenfuge 8 mm ueber dem Stein
GD = 0.012                     # Tiefe der Schattenfuge
GK = 0.025                     # Beplankung 2 x 12,5 mm
YG = T2 - GK                   # Rueckseite der Beplankung = Vorderseite der Staender
STUDS = [-1.25, -0.625, 0.0, 0.625, 1.25]   # CW-Staender alle 62,5 cm (stueckbezogen)
SW = 0.05                      # Flanschbreite der Staender
YI = YG - 0.006                # Vorderseite der Daemmung
PLH, PLD = 0.10, 0.015         # Sockel aus dunklem Stein: 10 cm hoch, 1,5 cm vor
EDGE = 0.4                     # Schaeden nie naeher an den Seitenkanten
KASTEN_W, KASTEN_H, KASTEN_T = 0.38, 0.62, 0.13      # Feuerloescherkasten, in die Wand eingelassen
LR = 0.05                      # Radius des Feuerloeschers
BAND_K, BAND_W, BAND_P = 0.2, 0.38, 0.26            # Baender: Kleberbett, Daemmwolle, Karton
JOINTS_TEX = [0.1, 0.5, 1.1, 1.7, 2.3, 2.9, 3.5, 3.9]   # Plattenfugen im Wandbild, 3,9 .. 4,1 = Pfosten
GK_JOINTS = [0.75, 2.0, 3.25]                        # Plattenstoesse des Gipskartons im Wandbild (x = -1,25 / 0 / 1,25)
U_REV, REV_DZ = 0.421875, 0.26 # Fensterlaibung: ruhige Stelle im Wandbild (zwischen zwei Schraubenreihen, kein Plattenstoss)

# Detail-Atlas: waagerechte Bereiche (Hoehe in Metern), jeder kachelt in U
REG = {
    "kleber": (0.00, 0.22), "bruch_stein": (0.23, 0.37), "stein_kante": (0.38, 0.43), "riss": (0.44, 0.51),
    "gips": (0.52, 0.72), "karton": (0.73, 1.01), "wolle": (1.02, 1.42), "profil": (1.43, 1.71), "sockel": (1.72, 1.86),
    "alu_24": (1.87, 2.12), "alu_10": (2.13, 2.23), "alu_07": (2.24, 2.31), "alu_05": (2.32, 2.37), "alu_03": (2.38, 2.41),
    "gummi": (2.42, 2.45), "kanal": (2.46, 2.69), "rot": (2.70, 2.92), "kasten": (2.93, 3.33), "loescher": (3.34, 3.66),
    "schwarz": (3.67, 3.73), "messing": (3.74, 3.85), "stahl_07": (3.86, 3.93), "stahl_03": (3.94, 3.97),
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
    "X": [[(0, 0), (2, 4)], [(0, 4), (2, 0)]],
    "B": [[(0, 0), (0, 4), (1.3, 4), (1.8, 3.6), (1.8, 2.5), (1.3, 2.1), (0, 2.1)], [(1.3, 2.1), (1.95, 1.6), (1.95, 0.5), (1.4, 0), (0, 0)]],
    "G": [[(1.9, 3.4), (1.4, 4), (0.6, 4), (0.1, 3.3), (0, 2), (0.1, 0.7), (0.6, 0), (1.4, 0), (1.9, 0.6), (1.9, 1.7), (1.1, 1.7)]],
    "Ö": [[(1.0, 3.2), (0.3, 2.9), (0, 2.1), (0, 1.1), (0.3, 0.3), (1, 0), (1.7, 0.3), (2, 1.1), (2, 2.1), (1.7, 2.9), (1.0, 3.2)],
          [(0.55, 3.75), (0.6, 3.85)], [(1.4, 3.75), (1.45, 3.85)]],
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


def slab_cells(n):
    """Steinplatten im Wandbild als Pixel-Rechtecke (Nummer, Zeilen, Spalten); der Pfostenstreifen 3,9 .. 4,1 laeuft um."""
    cells, k = [], 0
    xs = JOINTS_TEX + [4.1]
    for z0, z1 in SROWS:
        rs = slice(int(round(z0 * n / 4)), int(round(z1 * n / 4)))
        for ci in range(len(xs) - 1):
            c0, c1 = int(round(xs[ci] * n / 4)), int(round(xs[ci + 1] * n / 4))
            cells.append((k, rs, np.arange(c0, c1) % n))
            k += 1
    return cells

def spray_mask(S, lines, width, seed, SPK, DRN=None, drips=0.0, halo=2.6):
    """Spruehfarbe: weicher Kern, Spruehnebel mit Punkten, auf Wunsch Laeufer nach unten."""
    core = raster_lines(S, lines, width, rough=0.35, seed=seed)
    fog = raster_lines(S, lines, width * halo, rough=0.2, seed=seed + 1)
    m = np.maximum(core, fog * (0.15 + 0.45 * SPK) * 0.7)
    if drips and DRN is not None:
        src = core * DRN
        m = np.maximum(m, np.clip(drip(src, drips), 0, 1) * 0.95)
    return np.clip(m, 0, 1)

def tex_wand():
    n = NPX
    X, Z = grid_xz()
    S = (n, n)
    rng = np.random.default_rng(81)
    cells = slab_cells(n)
    def per_slab(N):
        out = np.zeros_like(N)
        for k, rs, cols in cells:
            dr, dc = rng.integers(0, n, 2)
            rows = (np.arange(rs.start, rs.stop) + dr) % n
            out[rs, cols] = N[np.ix_(rows, (cols + dc) % n)]
        return out
    sid = np.zeros(S, np.int32)
    for k, rs, cols in cells:
        sid[rs, cols] = k
    # ================= Steinplatten bis 1,2 m: beiger Kalkstein, je Platte eigener Ton =================
    tone = rng.normal(0, 0.045, 16).astype(np.float32)
    warm = rng.normal(0, 0.03, 16).astype(np.float32)
    styl = (rng.random(16) < 0.55).astype(np.float32)
    dxj = np.full(S, 9.0, np.float32)
    for j in JOINTS_TEX:
        dxj = np.minimum(dxj, pdist(X, j))
    dj = np.minimum(dxj, np.minimum(np.abs(Z - 0.6), np.abs(Z - TRENN)))
    cloud = per_slab(fr(S, 2.0, 301))
    mott = per_slab(fr(S, 0.9, 302))
    fos = per_slab(fr(S, 0.2, 303, sigma_m=0.0012))
    shl = per_slab(fr(S, 0.25, 304, sigma_m=0.001))
    syn = per_slab(fr(S, 1.3, 305, aniso=0.12))
    base = hexc("#cdbc98") * (1 + tone[sid] + 0.05 * cloud)[..., None]
    base = base * np.stack([1 + warm[sid], 1 + 0.3 * warm[sid], 1 - warm[sid]], -1)
    base = mix(base, hexc("#b39f78"), 0.35 * sm(0.3, 1.7, mott))
    fossil = sm(1.9, 2.5, fos)
    shellf = sm(2.0, 2.6, shl)
    stylo = sm(0.03, 0.006, np.abs(syn)) * styl[sid] * sm(-0.6, 1.0, cloud)
    base = mix(base, hexc("#7d6c50"), 0.7 * fossil)
    base = mix(base, hexc("#e9e0c9"), 0.55 * shellf)
    base = mix(base, hexc("#6e5e45"), 0.6 * stylo)
    grime = np.clip(sm(0.34, 0.02, Z) * (0.7 + 0.3 * sm(-1, 1, fr(S, 1.2, 306))), 0, 1)
    mop = sm(0.012, 0.0, np.abs(Z - (0.17 + 0.025 * fr(S, 1.8, 307))))
    scuff = sm(1.5, 2.4, fr(S, 0.6, 308, aniso=0.08)) * sm(0.1, 0.14, Z) * sm(0.62, 0.45, Z)
    jd = sm(0.008, 0.0015, dj)
    dust = sm(0.0, 1.6, fr(S, 1.3, 309))
    src = sm(2.3, 2.8, fr(S, 0.7, 310)) * sm(0.35, 0.6, Z) * sm(1.15, 1.0, Z)
    run = np.clip(drip(src, 0.35), 0, 1)
    hc = sm(0.01, 0.003, np.abs(fr(S, 1.4, 311))) * np.isin(sid, [3, 9, 12]) * sm(0.4, 1.2, fr(S, 1.2, 312))
    a_s = mix(base, hexc("#5c5446"), 0.55 * grime)
    a_s = mix(a_s, hexc("#6f6553"), 0.45 * mop)
    a_s = mix(a_s, hexc("#2e2b27"), 0.5 * scuff)
    a_s = mix(a_s, hexc("#7b6f5c"), 0.5 * jd)
    a_s = mix(a_s, hexc("#a39a88"), 0.25 * dust)
    a_s = mix(a_s, hexc("#8a6a43"), 0.45 * run)
    a_s = mix(a_s, hexc("#4a4034"), 0.7 * hc)
    h_s = 0.00006 * cloud - 0.0004 * fossil + 0.00005 * shellf - 0.0003 * hc - 0.0001 * jd
    r_s = np.clip(0.2 + 0.25 * dust + 0.35 * grime + 0.2 * scuff + 0.3 * jd + 0.1 * run + 0.08 * fossil, 0, 1)
    # ================= Gipskarton ab 1,2 m: gestrichen, Stoesse, Schrauben, Schmutz, Stockflecken =================
    yel = sm(1.3, 3.4, Z)
    paint = mix(hexc("#dcd8cd"), hexc("#cbc4b1"), 0.8 * yel) * (0.97 + 0.02 * fr(S, 1.6, 320))[..., None]
    peel = fr(S, 0.3, 321, sigma_m=0.0008)
    dgj = np.full(S, 9.0, np.float32)
    for j in GK_JOINTS:
        dgj = np.minimum(dgj, pdist(X, j))
    hz = np.where((X >= 0.75) & (X < 2.0), 2.8, np.where((X >= 2.0) & (X < 3.25), 2.5, 2.65))
    dh = np.abs(Z - hz) + 9.0 * ((X > 3.85) | (X < 0.15))
    tape = np.maximum(sm(0.03, 0.022, dgj), sm(0.03, 0.022, dh))
    tedge = np.maximum(sm(0.003, 0.0, np.abs(dgj - 0.026)), sm(0.003, 0.0, np.abs(dh - 0.026))) * sm(-0.4, 1.0, fr(S, 1.0, 322))
    jcr = np.maximum(sm(0.0012, 0.0003, dgj), sm(0.0012, 0.0003, dh)) * sm(0.5, 1.3, fr(S, 1.0, 323, aniso=6.0))
    sx = np.array([0.75, 1.375, 2.0, 2.625, 3.25], np.float32)
    dsx = np.full(S, 9.0, np.float32)
    sxi = np.zeros(S, np.int32)
    for i, c in enumerate(sx):
        d = pdist(X, c)
        sxi = np.where(d < dsx, i, sxi)
        dsx = np.minimum(dsx, d)
    srow = np.clip(np.round((Z - 1.33) / 0.25), 0, 8)
    dsz = Z - (1.33 + 0.25 * srow)
    dsc = np.hypot(dsx, dsz)
    sh_ = np.mod(np.sin((sxi * 13 + srow) * 12.9898) * 43758.5453, 1.0)
    spack = sm(0.010, 0.007, dsc)
    rusts = (sh_ < 0.3) * sm(0.004, 0.002, dsc)
    rustr = np.clip(drip(rusts * 0.8, 0.06), 0, 1) * (sh_ < 0.3)
    grime_p = np.clip(sm(-0.2, 1.8, fr(S, 1.5, 324) + 0.9 * sm(1.7, 1.21, Z) + 0.7 * sm(2.8, 3.4, Z)), 0, 1)
    smudge = sm(1.2, 2.2, fr(S, 0.7, 325) + 0.5 * fr(S, 1.3, 326)) * sm(1.25, 1.4, Z) * sm(2.0, 1.6, Z)
    wmask = np.exp(-(pdist(X, 3.3) / 0.33) ** 2) * sm(2.3, 3.3, Z)
    wf = 2.2 * wmask + 0.6 * fr(S, 1.6, 327) - 1.0
    stain = sm(0.0, 0.4, wf)
    tide = sm(0.035, 0.0, np.abs(wf - 0.02)) * sm(2.2, 2.6, Z)
    wrun = np.clip(drip(sm(0.2, 0.6, wf) * sm(1.8, 2.4, fr(S, 1.0, 328, aniso=10.0)), 0.8), 0, 1) * 0.5
    zone = np.clip(0.9 * sm(1.6, 1.22, Z) + 0.8 * sm(2.9, 3.4, Z) + 0.9 * stain + 0.5 * sm(0.03, 0.0, np.minimum(dgj, dh)), 0, 1)
    cl = sm(0.2, 1.3, fr(S, 1.2, 329) + 1.4 * zone - 0.9)
    dots = sm(1.5, 2.2, fr(S, 0.15, 330, sigma_m=0.0009))
    mold = np.clip(cl * (0.3 * cl + dots), 0, 1)
    pl = mix(paint, hexc("#e2dfd6"), 0.35 * tape)
    pl = mix(pl, hexc("#a9a394"), 0.35 * tedge)
    pl = mix(pl, hexc("#5f5a50"), 0.8 * jcr)
    pl = mix(pl, hexc("#e6e3da"), 0.6 * spack)
    pl = mix(pl, hexc("#7a5636"), 0.7 * np.maximum(rusts, rustr * 0.6))
    pl = mix(pl, hexc("#8f8878"), 0.45 * grime_p)
    pl = mix(pl, hexc("#6d665a"), 0.35 * smudge)
    pl = mix(pl, pl * hexc("#c9b68e"), 0.55 * stain)
    pl = mix(pl, hexc("#8a6f45"), 0.45 * tide)
    pl = mix(pl, pl * hexc("#b9a479"), wrun)
    pl = mix(pl, hexc("#2a2d24") * (0.8 + 0.4 * sm(-1, 1, fr(S, 0.6, 331)))[..., None], 0.85 * mold)
    h_p = 0.00015 * peel + 0.0001 * tape - 0.0006 * jcr - 0.0004 * spack * 0 + 0.0002 * spack + 0.00003 * fr(S, 1.0, 332)
    r_p = 0.86 - 0.12 * tape + 0.05 * grime_p - 0.15 * stain + 0.05 * mold
    # Plakatreste: Kleisterflaeche, Papierfetzen mit verblichenem Druck, weisse Rissraender, Klammern
    pap_t = fr(S, 2.2, 333) + 0.18 * fr(S, 0.9, 345)
    pap_f = fr(S, 1.0, 334, aniso=0.6)
    for k, (x0, x1, z0, z1, keep) in enumerate(((0.25, 0.85, 1.45, 2.30, -0.3), (2.95, 3.55, 1.55, 1.98, 0.35),
                                               (3.62, 3.83, 1.35, 1.65, 0.1))):
        sd = rect_sdf(X, Z, x0, x1, z0, z1)
        inside = sm(-0.002, 0.002, sd)
        paste = sm(-0.006, 0.006, sd) * (0.6 + 0.4 * sm(-1, 1, pap_f))
        val = pap_t + 1.4 * sm(0.06, 0.0, sd) + keep
        remain = sm(0.5, 0.56, val) * inside
        rim = remain * sm(0.66, 0.56, val)
        lx = np.mod(X - x0, 4.0) / (x1 - x0)
        lz = (Z - z0) / (z1 - z0)
        rr = np.random.default_rng(400 + k)
        prn = np.zeros(S, np.float32)
        col = np.zeros(S + (3,), np.float32)
        for b in range(5):
            bx0, bz0 = rr.uniform(0.05, 0.6), rr.uniform(0.05, 0.75)
            bw, bh = rr.uniform(0.2, 0.45), rr.uniform(0.08, 0.3)
            m = ((lx > bx0) & (lx < bx0 + bw) & (lz > bz0) & (lz < bz0 + bh)).astype(np.float32)
            c = hexc(["#c25b4c", "#5274a0", "#d39b3c", "#3d3d3d", "#6e9a6a"][rr.integers(0, 5)])
            col = col * (1 - m[..., None]) + c * m[..., None]
            prn = np.maximum(prn, m)
        lines = ((np.mod(lz * 18, 1.0) < 0.35) & (lx > 0.1) & (lx < 0.9) & (lz < 0.3)).astype(np.float32)
        paper = mix(hexc("#e4dfd2"), col, 0.75 * prn)
        paper = mix(paper, hexc("#3f3f3d"), 0.7 * lines)
        paper = mix(paper, hexc("#b9ae92"), 0.25 * sm(0.0, 1.5, pap_f))
        pl = mix(pl, pl * hexc("#cdbf9c"), 0.5 * paste * (1 - remain))
        pl = mix(pl, paper, remain)
        pl = mix(pl, hexc("#f1eee6"), 0.8 * rim)
        h_p = h_p + 0.0003 * remain + 0.00015 * rim
        r_p = np.where(remain > 0.5, 0.9, r_p - 0.25 * paste * (1 - remain))
        for cx, cz in ((x0 + 0.015, z1 - 0.015), (x1 - 0.015, z1 - 0.015), (x0 + 0.015, z0 + 0.015), (x1 - 0.015, z0 + 0.015),
                       ((x0 + x1) / 2, z1 - 0.012)):
            st = (pdist(X, cx) < 0.005) & (np.abs(Z - cz) < 0.0012)
            pl = np.where(st[..., None], hexc("#8d8f8f"), pl)
            h_p = np.where(st, 0.0004, h_p)
    # Graffiti: silbernes Bubble-Piece ueber Tuerhoehe, Tags in Schwarz und Rot mit Laeufern, Gekritzel auf dem Plakat
    SPK = sm(0.6, 1.8, fr(S, 0.1, 335, sigma_m=0.0006))
    DRN = sm(2.2, 2.6, fr(S, 0.4, 336))
    nova = text_strokes("NOVA", 1.28, 2.66, 0.42, w=0.3, gap=0.08, slant=0.05)
    ghost = raster_lines(S, nova, 0.06, rough=0.3, seed=338)
    buff = sm(-0.01, 0.01, rect_sdf(X, Z, 1.18, 2.84, 2.56, 3.14) + 0.006 * fr(S, 0.8, 346))
    roller = 0.5 + 0.5 * np.sin(2 * math.pi * X / 0.23 + 1.5 * fr(S, 1.6, 347))
    tag1 = text_strokes("NOVA", 0.35, 2.66, 0.12, w=0.075, gap=0.025, slant=0.2)
    nv = spray_mask(S, tag1, 0.008, 339, SPK, DRN, drips=0.1)
    ok_ = text_strokes("OK", 3.4, 2.3, 0.18, w=0.13, gap=0.04, slant=0.05)
    okout = spray_mask(S, ok_, 0.034, 340, SPK)
    okfil = raster_lines(S, ok_, 0.022, rough=0.3, seed=341)
    rex = spray_mask(S, text_strokes("REX", 0.9, 1.52, 0.14, w=0.07, gap=0.025, slant=0.25), 0.009, 342, SPK, DRN, drips=0.12)
    kaz = spray_mask(S, text_strokes("KAZ", 2.86, 1.27, 0.15, w=0.13, gap=0.04, slant=0.15), 0.012, 343, SPK, DRN, drips=0.1)
    zero = spray_mask(S, text_strokes("ZERO", 0.3, 1.58, 0.09, w=0.1, gap=0.03, slant=-0.1), 0.005, 344, SPK, halo=2.0)
    fade = 0.85 + 0.15 * sm(-1, 1, fr(S, 1.4, 348))
    pl = mix(pl, hexc("#e0ddd3") * (0.97 + 0.02 * roller[..., None]), 0.85 * buff)
    pl = mix(pl, hexc("#b9b8b2"), 0.22 * ghost * buff)
    pl = mix(pl, hexc("#18181a"), 0.9 * np.maximum(np.maximum(rex, zero), nv) * fade)
    pl = mix(pl, hexc("#9b2a24"), 0.9 * kaz * fade)
    pl = mix(pl, hexc("#141416"), 0.9 * okout * fade)
    pl = mix(pl, hexc("#a9adb0") * (0.9 + 0.15 * SPK[..., None]), 0.95 * okfil * fade)
    gfil = okfil
    gout = okout + nv
    gsh = 0.3 * buff
    gall = np.clip(gout + gfil + rex + kaz + zero, 0, 1)
    r_p = np.clip(r_p - 0.3 * gall, 0, 1)
    up = (Z >= TRENN)
    alb = np.where(up[..., None], pl, a_s)
    hgt = np.where(up, h_p, h_s)
    rough = np.where(up, r_p, r_s)
    metal = np.where(up, 0.25 * gfil, 0.0).astype(np.float32)
    return write_set(f"T_{GEB}_Wand", alb, hgt, rough, metal)

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
    seed = [900]
    def nz(shape, beta, aniso=1.0, sigma_m=0.0):
        seed[0] += 1
        return fr(shape, beta, seed[0], aniso, sigma_m)
    # ---- Kleberbett, wo Platten abgefallen sind: Kammspuren, Steinreste, Staub ----
    sl, X, Z, S, hh = region("kleber")
    wob = nz(S, 1.8)
    ridge = 0.5 + 0.5 * np.sin(2 * math.pi * (Z + 0.35 * X) / 0.012 + 2.4 * wob)
    flat = sm(0.4, 1.6, nz(S, 1.2))
    ridge = lin(ridge, 0.6, flat)
    k = hexc("#a29e95") * (0.86 + 0.12 * ridge[..., None] + 0.05 * nz(S, 1.0)[..., None])
    rem = sm(1.4, 1.9, nz(S, 1.1))
    k = mix(k, hexc("#c9b892") * (0.9 + 0.1 * nz(S, 0.5)[..., None]), 0.85 * rem)
    k = mix(k, hexc("#6d695f"), 0.3 * sm(0.3, 2.0, nz(S, 1.3)))
    alb[sl] = k
    hgt[sl] = 0.0012 * ridge + 0.0008 * rem + 0.0003 * nz(S, 0.6)
    rgh[sl] = 0.88
    # ---- Bruchflaeche im Kalkstein ----
    sl, X, Z, S, hh = region("bruch_stein")
    g = nz(S, 0.3, sigma_m=0.0012)
    b = hexc("#d2c3a2") * (0.88 + 0.08 * nz(S, 1.0)[..., None] + 0.05 * g[..., None])
    b = mix(b, hexc("#8a7a5d"), 0.6 * sm(1.8, 2.4, nz(S, 0.25, sigma_m=0.0012)))
    b = mix(b, hexc("#9a968c"), 0.4 * sm(1.0, 2.0, nz(S, 1.1)))
    alb[sl] = b * (1 - 0.15 * sm(0.5, 2.0, nz(S, 1.3)))[..., None]
    hgt[sl] = 0.002 * nz(S, 0.6) + 0.0008 * g
    rgh[sl] = 0.9
    # ---- Plattenkanten: gesaegter Kalkstein ----
    sl, X, Z, S, hh = region("stein_kante")
    saw = nz(S, 0.6, aniso=0.03)
    alb[sl] = mix(hexc("#c2b18e") * (0.92 + 0.05 * saw[..., None]), hexc("#6e6555"), 0.35 * sm(0.3, 2.0, nz(S, 1.2)))
    hgt[sl] = 0.0002 * saw
    rgh[sl] = 0.7
    # ---- Rissflanken ----
    sl, X, Z, S, hh = region("riss")
    q = nz(S, 0.9)
    alb[sl] = mix(hexc("#2b2924"), hexc("#857a64"), sm(-0.8, 1.6, q)) * (0.85 + 0.15 * nz(S, 0.4)[..., None])
    hgt[sl] = 0.002 * q
    rgh[sl] = 0.93
    # ---- Gipskern mit Karton an beiden Seiten und Fuge zwischen den zwei Lagen ----
    sl, X, Z, S, hh = region("gips")
    c = hh / 2
    por = sm(1.6, 2.3, nz(S, 0.2, sigma_m=0.0008))
    gp = hexc("#d8d5cc") * (0.9 + 0.06 * nz(S, 1.0)[..., None] + 0.04 * nz(S, 0.3)[..., None])
    gp = gp * (1 - 0.3 * por)[..., None]
    papl = sm(0.0016, 0.0006, np.minimum(np.abs(Z - (c - 0.0125)), np.abs(Z - (c + 0.0125))))
    midl = sm(0.0012, 0.0004, np.abs(Z - c))
    gp = mix(gp, hexc("#e3dbc4"), 0.8 * papl)
    gp = mix(gp, hexc("#a9a598"), 0.6 * midl)
    alb[sl] = mix(gp, hexc("#8f8b81"), 0.25 * sm(0.3, 2.0, nz(S, 1.3)))
    hgt[sl] = 0.0012 * nz(S, 0.5) - 0.0008 * por
    rgh[sl] = 0.95
    # ---- Rueckseite der Gipskartonplatten: grauer Karton mit Stempel, Wasserflecken ----
    sl, X, Z, S, hh = region("karton")
    fib = nz(S, 0.4, aniso=0.3)
    kc = hexc("#a39883") * (0.9 + 0.06 * fib[..., None] + 0.05 * nz(S, 1.4)[..., None])
    stamp = ((np.mod(X, 0.9) < 0.42) & (np.abs(np.mod(Z, 0.28) - 0.14) < 0.012) & (np.mod(X * 55, 1.0) < 0.62)).astype(np.float32)
    kc = mix(kc, hexc("#4f5e74"), 0.55 * stamp * sm(-0.5, 1.0, nz(S, 1.0)))
    kc = mix(kc, hexc("#6f6250"), 0.45 * sm(0.4, 1.8, nz(S, 1.3)))
    alb[sl] = kc
    hgt[sl] = 0.0002 * fib
    rgh[sl] = 0.92
    # ---- gelbe Glaswolle ----
    sl, X, Z, S, hh = region("wolle")
    f1, f2, f3 = nz(S, 0.55, aniso=0.25), nz(S, 0.55, aniso=4.0), nz(S, 1.2)
    f4 = nz(S, 0.25, sigma_m=0.0008)
    fib = 0.45 * f1 + 0.45 * f2 + 0.3 * f4
    w = mix(hexc("#a8862f"), hexc("#dcc06a"), sm(-1.2, 1.4, fib))
    w = w * (0.82 + 0.14 * sm(-1.0, 1.5, f3))[..., None]
    alb[sl] = mix(w, hexc("#6e5f3a"), 0.4 * sm(0.6, 2.2, nz(S, 1.3)))
    hgt[sl] = 0.003 * f3 + 0.0012 * fib
    rgh[sl] = 0.96
    # ---- verzinkte Staender: Zinkblumen, Stanzungen im Steg (Mitte des Bereichs), Aufdruck ----
    sl, X, Z, S, hh = region("profil")
    sp = nz(S, 0.35, sigma_m=0.004)
    zc = hexc("#a6abac") * (0.9 + 0.07 * sp[..., None] + 0.03 * nz(S, 0.3)[..., None])
    c = 0.002 + 0.133
    hx = np.mod(X, 0.25)
    hole = ((np.abs(hx - 0.12) < 0.016) & (np.abs(Z - c) < 0.009)) | ((np.abs(hx - 0.12) < 0.006) & (np.abs(Z - c) < 0.024))
    printed = ((np.mod(X, 1.1) > 0.3) & (np.mod(X, 1.1) < 0.48) & (np.abs(Z - c - 0.04) < 0.006) & (np.mod(X * 90, 1.0) < 0.6))
    zc = mix(zc, hexc("#7b2c22"), 0.6 * printed.astype(np.float32))
    zc = mix(zc, hexc("#6c6a63"), 0.3 * sm(0.4, 2.2, nz(S, 1.3)))
    zc = mix(zc, hexc("#7a5a3e"), 0.5 * sm(2.0, 2.6, nz(S, 0.7)))
    alb[sl] = np.where(hole[..., None], hexc("#141414"), zc)
    hgt[sl] = np.where(hole, -0.002, 0.00005 * sp)
    rgh[sl] = np.where(hole, 1.0, 0.45 + 0.1 * sp)
    met[sl] = np.where(hole, 0.0, 0.8)
    # ---- dunkler Steinsockel (Granit, poliert) ----
    sl, X, Z, S, hh = region("sockel")
    gr = nz(S, 0.2, sigma_m=0.0015)
    gc = hexc("#262624") * (0.9 + 0.1 * nz(S, 1.2)[..., None])
    gc = mix(gc, hexc("#8f8c86"), 0.8 * sm(1.6, 2.3, gr))
    gc = mix(gc, hexc("#4d4a46"), 0.5 * sm(0.6, 1.4, nz(S, 0.4, sigma_m=0.002)))
    s_ = Z - 0.002
    floor = sm(0.03, 0.0, s_)
    scr = sm(2.0, 2.7, nz(S, 0.5, aniso=0.07)) * sm(0.01, 0.03, s_)
    edge = sm(0.093, 0.1, s_) * sm(0.0, 1.0, nz(S, 1.0))
    gc = mix(gc, hexc("#6e6a62"), 0.55 * scr)
    gc = mix(gc, hexc("#5b564c"), 0.5 * floor + 0.35 * edge)
    alb[sl] = gc
    hgt[sl] = -0.0002 * scr
    rgh[sl] = np.clip(0.16 + 0.3 * floor + 0.25 * scr + 0.2 * sm(0.5, 2.0, nz(S, 1.3)), 0, 1)
    # ---- eloxiertes Aluminium (Zarge, Schaufensterrahmen, Eckschutz) ----
    for name in ("alu_24", "alu_10", "alu_07", "alu_05", "alu_03"):
        sl, X, Z, S, hh = region(name)
        br = nz(S, 0.35, aniso=0.02)
        ox = sm(1.5, 2.2, nz(S, 0.4, sigma_m=0.0015)) * sm(0.0, 1.0, nz(S, 1.2))
        dirt = sm(0.4, 2.2, nz(S, 1.3))
        scr = sm(2.1, 2.8, nz(S, 0.5, aniso=0.06))
        d = np.minimum(Z, hh - Z)
        edge = 1.0 if name == "alu_03" else sm(0.006, 0.0015, d)
        a = hexc("#b3ad9f") * (0.9 + 0.05 * br[..., None])
        a = mix(a, hexc("#dcd9d0"), 0.6 * ox)
        a = mix(a, hexc("#77726a"), 0.35 * dirt)
        a = mix(a, hexc("#cfcbc2"), 0.35 * scr + 0.25 * edge)
        alb[sl] = a
        hgt[sl] = 0.00005 * br - 0.0001 * scr + 0.0001 * ox
        rgh[sl] = np.clip(0.38 + 0.25 * ox + 0.25 * dirt, 0, 1)
        met[sl] = np.clip(0.75 - 0.5 * ox - 0.3 * dirt, 0, 1)
    # ---- Gummi ----
    sl, X, Z, S, hh = region("gummi")
    alb[sl] = mix(hexc("#1b1c1d") * (0.9 + 0.1 * nz(S, 0.8)[..., None]), hexc("#4d4c48"), 0.35 * sm(0.8, 2.0, nz(S, 1.2)))
    hgt[sl] = -0.0004 * sm(2.2, 2.7, nz(S, 0.3, aniso=0.3))
    rgh[sl] = 0.85
    # ---- Kabelkanal (PVC), Deckelfugen an den Kanten des Profils ----
    sl, X, Z, S, hh = region("kanal")
    s_ = Z - 0.002
    seam = sm(0.002, 0.0, np.minimum(np.abs(s_ - 0.062), np.abs(s_ - 0.158)))
    p = hexc("#cdc9bf") * (0.93 + 0.04 * nz(S, 1.4)[..., None])
    p = mix(p, hexc("#b9ab88"), 0.35 * sm(-0.5, 1.5, nz(S, 1.5)))
    p = p * (1 - 0.3 * sm(0.3, 2.1, nz(S, 1.2, aniso=4.0)))[..., None]
    alb[sl] = p * (1 - 0.5 * seam)[..., None]
    hgt[sl] = -0.0006 * seam
    rgh[sl] = 0.5 + 0.2 * sm(0.3, 2.1, nz(S, 1.2))
    # ---- rot lackierter Stahl (Sprinklerrohr, Schellen, Kasten) ----
    sl, X, Z, S, hh = region("rot")
    r = hexc("#8e2a22") * (0.9 + 0.08 * nz(S, 1.2)[..., None])
    chips = sm(1.9, 2.4, nz(S, 0.4, sigma_m=0.0012))
    dust = sm(0.2, 1.8, nz(S, 1.2))
    r = mix(r, hexc("#3f3a36"), 0.85 * chips)
    alb[sl] = mix(r, hexc("#7b7468"), 0.35 * dust)
    hgt[sl] = -0.0003 * chips
    rgh[sl] = np.clip(0.4 + 0.3 * dust + 0.3 * chips, 0, 1)
    # ---- Feuerloescherkasten: Rueckwand mit Schild und Innenseite der Tuer (gedreht abgelegt: U = Hoehe, V = Breite) ----
    sl, X, Z, S, hh = region("kasten")
    base = hexc("#962a21") * (0.9 + 0.07 * nz(S, 1.3)[..., None])
    scr = sm(2.1, 2.8, nz(S, 0.6, aniso=0.1))
    dirt = sm(0.3, 2.0, nz(S, 1.2))
    a = mix(base, hexc("#c4b9ab"), 0.4 * scr)
    a = mix(a, hexc("#4a3a33"), 0.35 * dirt)
    h_ = -0.00015 * scr
    r_ = 0.45 + 0.2 * scr + 0.2 * dirt
    bw, bh = KASTEN_W - 0.02, KASTEN_H - 0.02             # Rueckwand
    pz, px = X - 2.0, Z - 0.005
    back = (pz >= 0) & (pz < bh) & (px >= 0) & (px < bw)
    sqx, sqz = bw - 0.075, bh - 0.17
    sq = back & (np.abs(px - sqx) < 0.05) & (np.abs(pz - sqz) < 0.05)
    plate = back & (np.abs(px - bw / 2) < 0.15) & (np.abs(pz - (bh - 0.035)) < 0.022)
    a = np.where(sq[..., None], hexc("#b3261c"), a)
    a = np.where(plate[..., None], hexc("#d9d6ce"), a)
    # Rettungszeichen: weisse Silhouette (Behaelter mit runder Schulter, Ventil, Griffhebel, Schlauch mit Duese)
    cxp, czp = sqx - 0.008, sqz - 0.004
    body = ((np.abs(px - cxp) < 0.0125) & (pz > czp - 0.034) & (pz < czp + 0.014)) \
        | (np.hypot(px - cxp, pz - (czp + 0.014)) < 0.0125) \
        | ((np.abs(px - cxp) < 0.0045) & (pz > czp) & (pz < czp + 0.034))
    strokes = [[(cxp - 0.015, czp + 0.035), (cxp + 0.011, czp + 0.041)],
               [(cxp + 0.003, czp + 0.03), (cxp + 0.019, czp + 0.026), (cxp + 0.026, czp + 0.008), (cxp + 0.026, czp - 0.016)],
               [(cxp + 0.026, czp - 0.016), (cxp + 0.026, czp - 0.026)]]
    lines = [[(2.0 + pz_, 0.005 + px_) for px_, pz_ in ln] for ln in strokes]
    ic = np.maximum(body.astype(np.float32), raster_lines(S, lines[:2], 0.0032, x_wrap=False))
    ic = np.maximum(ic, raster_lines(S, lines[2:], 0.0055, x_wrap=False)) * sq
    a = mix(a, hexc("#eeeae2"), 0.95 * ic)
    tw = 12 * 0.011 + 11 * 0.0035
    txt = text_strokes("FEUERLÖSCHER", bw / 2 - tw / 2, bh - 0.046, 0.022, w=0.011, gap=0.0035)
    tl = raster_lines(S, [[(2.0 + pz_, 0.005 + px_) for px_, pz_ in ln] for ln in txt], 0.0018, x_wrap=False) * plate
    a = mix(a, hexc("#a8231b"), 0.95 * tl)
    hook = back & (np.abs(px - bw / 2) < 0.03) & (np.abs(pz - 0.33) < 0.012)
    a = np.where(hook[..., None], hexc("#5a5a58"), a)
    dw, dh_ = KASTEN_W - 0.005, KASTEN_H - 0.005            # Innenseite der Tuer
    pz2, px2 = X - 2.8, Z - 0.005
    door = (pz2 >= 0) & (pz2 < dh_) & (px2 >= 0) & (px2 < dw)
    rib = door & ((np.abs(px2 - 0.03) < 0.006) | (np.abs(px2 - (dw - 0.03)) < 0.006) | (np.abs(pz2 - 0.03) < 0.006)
                  | (np.abs(pz2 - (dh_ - 0.03)) < 0.006))
    tag = door & (np.hypot(px2 - dw / 2, pz2 - (dh_ - 0.12)) < 0.025)
    tagc = np.where((np.mod(np.arctan2(pz2 - (dh_ - 0.12), px2 - dw / 2), 2 * math.pi) < 2.2)[..., None], hexc("#3f7a3e"), hexc("#d9d4c6"))
    lock = door & (np.abs(px2 - 0.025) < 0.008) & (np.abs(pz2 - dh_ / 2) < 0.05)
    a = np.where(rib[..., None], a * 0.82, a)
    a = np.where(tag[..., None], tagc, a)
    a = np.where(lock[..., None], hexc("#2c2c2c"), a)
    h_ = h_ + np.where(rib, 0.0006, 0.0) + np.where(lock, 0.001, 0.0)
    r_ = np.where(tag, 0.35, r_)
    alb[sl], hgt[sl], rgh[sl] = a, h_, r_
    # ---- Feuerloescher: roter Behaelter, Etikett an beiden Enden des Umfangs (zeigt nach vorn) ----
    sl, X, Z, S, hh = region("loescher")
    circ = 12 * 2 * LR * math.sin(math.pi / 12)
    v = Z - 0.002
    l = hexc("#a6271d") * (0.92 + 0.06 * nz(S, 1.4)[..., None])
    dust = sm(0.2, 1.8, nz(S, 1.2))
    lab = ((v < 0.045) | (v > circ - 0.045)) & (np.mod(X, 1.0) > 0.12) & (np.mod(X, 1.0) < 0.36)
    lv = np.where(v > circ / 2, v - circ, v)
    lx = np.mod(X, 1.0) - 0.12
    lc = np.where(((lx > 0.02) & (lx < 0.05))[..., None], hexc("#b3261c"), hexc("#dedbd2"))
    lc = np.where(((np.mod(lx * 60, 1.0) < 0.4) & (lx > 0.08) & (lx < 0.22) & (np.abs(lv) < 0.03))[..., None], hexc("#2d2d2d"), lc)
    for i, cc in enumerate(("#3c6fa5", "#d1a12b", "#4c8b45")):
        sqm = (np.abs(lx - 0.065) < 0.008) & (np.abs(lv - (i - 1) * 0.02) < 0.008)
        lc = np.where(sqm[..., None], hexc(cc), lc)
    l = np.where(lab[..., None], lc, l)
    alb[sl] = mix(l, hexc("#7d7468"), 0.3 * dust)
    rgh[sl] = np.where(lab, 0.5, 0.3 + 0.35 * dust)
    # ---- schwarzer Kunststoff, Messing, Stahl ----
    sl, X, Z, S, hh = region("schwarz")
    alb[sl] = hexc("#161616") * (0.9 + 0.15 * nz(S, 1.0)[..., None])
    rgh[sl] = 0.6
    sl, X, Z, S, hh = region("messing")
    alb[sl] = mix(hexc("#a8874a"), hexc("#5f5132"), 0.5 * sm(-0.5, 1.5, nz(S, 1.0)))
    rgh[sl] = 0.4 + 0.3 * sm(0.0, 1.5, nz(S, 1.1))
    met[sl] = 0.9
    for name in ("stahl_07", "stahl_03"):
        sl, X, Z, S, hh = region(name)
        ru = sm(1.4, 2.2, nz(S, 0.9))
        alb[sl] = mix(hexc("#979b9c") * (0.9 + 0.08 * nz(S, 1.0)[..., None]), hexc("#6b4a32"), 0.6 * ru)
        rgh[sl] = 0.5 + 0.3 * ru
        met[sl] = 0.8 * (1 - ru)
    used = np.zeros(n, bool)
    for z0, z1 in REG.values():
        used[int(round(z0 * n / 4)):int(round(z1 * n / 4))] = True
    rows = np.arange(n)
    ur = rows[used]
    hi_ = ur[np.clip(np.searchsorted(ur, rows), 0, len(ur) - 1)]
    lo_ = ur[np.clip(np.searchsorted(ur, rows) - 1, 0, len(ur) - 1)]
    src = np.where(np.abs(lo_ - rows) < np.abs(hi_ - rows), lo_, hi_)
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
R_KEEP, R_WM, R_WP, R_TOP, R_ENDX, R_REVX, R_REVZ, R_PLAN, R_METAL, R_BAND, R_BOXROT, R_SHARD, R_PLANAX, R_PLANFIX, \
    R_ALU = range(15)
PLAN_REG = list(REG.keys())

def wall_u(x, side):
    """Stueckbezogen: x = 0 liegt auf beiden Seiten bei 2,0 m im Wandbild. So treffen die Plattenfugen der Textur
    die Fugen der Geometrie, obwohl 60 cm nicht in 4 m aufgehen."""
    return UVS * x + 0.5 if side < 0 else -UVS * x + 0.5

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
        if reg_name == "kasten":
            uoff = pc.rng.random() * 0.2
    for l, c in zip(f.loops, co):
        l[pc.uv].uv = (uoff + UVS * c[0], UVS * (off + c[1] - vmin))

def alu_region(ext):
    for name, hgt in (("alu_03", 0.03), ("alu_05", 0.05), ("alu_07", 0.07), ("alu_10", 0.10), ("alu_24", 0.25)):
        if ext <= hgt - 0.004:
            return name
    raise RuntimeError(f"Aluminiumflaeche {ext:.3f} m zu breit")

def metal_region(ext):
    for name, hgt in (("stahl_03", 0.03), ("stahl_07", 0.07)):
        if ext <= hgt - 0.004:
            return name
    raise RuntimeError(f"Stahlflaeche {ext:.3f} m zu breit")

def lage(co):
    return (round(co.x, 6), round(co.y, 6), round(co.z, 6))

def apply_uvs(pc):
    bm, uv = pc.bm, pc.uv
    bm.normal_update()
    # Feste Reihenfolge und fester Zufall je Flaeche: Blenders Bevel legt Elemente je nach Speicheradressen in wechselnder
    # Folge an. Ohne das wanderten die zufaelligen UV-Verschiebungen und die Reihenfolge in der Datei von Lauf zu Lauf.
    for seq, key in ((bm.verts, lambda v: (lage(v.co), tuple(sorted(lage(f.calc_center_median()) for f in v.link_faces)))),
                     (bm.faces, lambda f: (lage(f.calc_center_median()), lage(f.normal), tuple(sorted(lage(v.co) for v in f.verts))))):
        for i, e in enumerate(sorted(seq, key=key)):
            e.index = i
        seq.sort()
    for f in bm.faces:
        pc.rng = random.Random(zlib.crc32(repr((lage(f.calc_center_median()), lage(f.normal))).encode()))
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
            # Fensterlaibung: Gipskarton aus einer ruhigen Stelle des Wandbilds, Hoehe in die Gipskartonzone verschoben
            s = 1 if f.normal.x > 0 else -1
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (U_REV + s * UVS * p.y, UVS * (p.z + REV_DZ))
        elif r == R_REVZ:
            zref = f[pc.par][0]
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (wall_u(p.x, -1), UVS * (zref - 0.08 + (p.y + T2)))      # Sturz: unter dem waagerechten Stoss
        elif r == R_BAND:
            # durchgehend abgebildete Flaeche parallel zur Wand (Fugenmasse, Kleberbett, Daemmung, Karton): Band ab zb
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
        elif r == R_BOXROT:
            # einmalige Flaechen des Feuerloescherkastens, im Atlas gedreht abgelegt: U = Hoehe, V = Breite von links
            bx, bz0, code = f[pc.par]
            mir = -1 if code < 0 else 1
            u0 = 0.5 + 0.2 * (abs(code) - 1)
            for l in f.loops:
                p = l.vert.co
                d = (bx - p.x) if mir < 0 else (p.x - bx)
                l[uv].uv = (u0 + UVS * (p.z - bz0), UVS * (REG["kasten"][0] + 0.005 + d))
        elif r == R_PLAN:
            co = planar_coords(f)
            place_in_region(pc, f, co, PLAN_REG[f[pc.reg]])
        elif r == R_PLANAX:
            co = planar_coords(f, Vector(f[pc.par]))
            name = PLAN_REG[f[pc.reg]]
            ext = max(c[1] for c in co) - min(c[1] for c in co)
            if ext > REG[name][1] - REG[name][0] - 0.004:
                # Fasen an Kanten quer zur Achse: Achse der Flaeche ist dann die andere Richtung
                co = [(c[1], -c[0]) for c in co]
            place_in_region(pc, f, co, name, center=True)
        elif r == R_PLANFIX:
            co = planar_coords(f, Vector((0, 1, 0)))
            place_in_region(pc, f, co, PLAN_REG[f[pc.reg]], uoff=f[pc.par][0], center=True)
        elif r in (R_METAL, R_ALU):
            ax = Vector(f[pc.par]) if Vector(f[pc.par]).length > 0 else None
            co = planar_coords(f, ax)
            ext = max(c[1] for c in co) - min(c[1] for c in co)
            ext2 = max(c[0] for c in co) - min(c[0] for c in co)
            if ext > ext2 and ax is None:
                co = [(c[1], -c[0]) for c in co]
                ext = ext2
            place_in_region(pc, f, co, (metal_region if r == R_METAL else alu_region)(ext), center=True)
        elif r == R_SHARD:
            # Gipskartonstueck (par 0) oder Steinscherbe (par 1): Oberseite aus dem Wandbild
            co = planar_coords(f)
            umin = min(c[0] for c in co)
            vmin = min(c[1] for c in co)
            u0 = pc.rng.random()
            vz = (0.25 + pc.rng.random() * 0.6) if f[pc.par][0] > 0.5 else (1.3 + pc.rng.random() * 1.0)
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

def chunk(pc, center, size, seed, reg="gips", subdiv=1):
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

# ---------- Bausteine Mall ----------
SOCKEL_PROF = [(PLD, 0.0), (PLD, PLH - 0.004), (PLD - 0.004, PLH), (0.0, PLH)]
KANAL_PROF = [(0.0, 3.26), (0.06, 3.26), (0.06, 3.36), (0.0, 3.36)]

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

def keep_in_front(pc, vs, side, lo=0.018, hi=0.115):
    """Teile am Boden: vor dem Sockel, hoechstens 11,5 cm vor der Wand."""
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

def surface(pc, outer, holes, y, side, rule, reg="kleber", band=None, mat=1, steiner=(), disp=None, borg=None):
    """Ebene Flaeche parallel zur Wand: Polygon ohne Loecher (die ueber den Rand gehen duerfen), per CDT.
    Mit band wird sie in waagerechte Baender zerlegt und jedes Band durchgehend abgebildet (R_BAND);
    borg verschiebt den Ursprung der Baender (Standard: Unterkante der Flaeche)."""
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
    b0 = za if borg is None else borg
    if band:
        k = 1
        while b0 + k * band < zb_ - 1e-6:
            zc = b0 + k * band
            if zc > za + 1e-6:
                i0 = len(verts)
                verts += [Vector((xa, zc)), Vector((xb, zc))]
                edges.append((i0, i0 + 1))
            k += 1
    verts += [Vector(p) for p in steiner]
    co, _, tris = geometry.delaunay_2d_cdt(verts, edges, faces, 1, 1e-7)[:3]
    for tri in tris:
        p2 = [co[i] for i in tri]
        cx, cz = sum(p.x for p in p2) / 3, sum(p.y for p in p2) / 3
        if not point_in(outer, cx, cz) or any(point_in(h, cx, cz) for h in holes):
            continue
        if abs((p2[1] - p2[0]).cross(p2[2] - p2[0])) < 2e-9:
            continue
        par = (side, b0 + math.floor((cz - b0) / band) * band, 0) if band else (0, 0, 0)
        pc.face([Vector((p.x, y + (disp(p.x, p.y) if disp else 0.0), p.y)) for p in p2], mat, rule, (0, side, 0),
                reg=PLAN_REG.index(reg), par=par)

# ---------- Sockel und Fugen ----------
def strips(pc, side, spans):
    for a, b in spans:
        profile_strip(pc, SOCKEL_PROF, a, b, side, "sockel")

def strip_face(pc, side, P, want, reg, vdir):
    """Lange schmale Flaeche mit fester UV-Lage: U wie die Wand entlang x, V entlang vdir ab dem Anfang des Bereichs."""
    z0r = REG[reg][0]
    vd = Vector(vdir)
    vmin = min(p.dot(vd) for p in P)
    f = pc.face(P, 1, R_KEEP, want)
    for l in f.loops:
        p = l.vert.co
        l[pc.uv].uv = (wall_u(p.x, side), UVS * (z0r + 0.002 + p.dot(vd) - vmin))
    return f

def shadow_gap(pc, side, spans):
    """Schattenfuge zwischen Stein und Gipskarton: Stufe auf der Fugenmasse, Rueckwand, Unterkante der Beplankung."""
    s = side
    for a, b in spans:
        strip_face(pc, s, [Vector((a, s * (T2 - GD), TRENN)), Vector((b, s * (T2 - GD), TRENN)), Vector((b, s * (T2 - BC), TRENN)),
                           Vector((a, s * (T2 - BC), TRENN))], (0, 0, 1), "stein_kante", (0, s, 0))
        strip_face(pc, s, [Vector((a, s * (T2 - GD), TRENN)), Vector((b, s * (T2 - GD), TRENN)), Vector((b, s * (T2 - GD), GZ)),
                           Vector((a, s * (T2 - GD), GZ))], (0, s, 0), "gips", (0, 0, 1))
        strip_face(pc, s, [Vector((a, s * (T2 - GD), GZ)), Vector((b, s * (T2 - GD), GZ)), Vector((b, s * T2, GZ)), Vector((a, s * T2, GZ))],
                   (0, 0, -1), "gips", (0, s, 0))

# ---------- Steinplatten ----------
def cell_rects(c, r):
    """Platte in Spalte c, Reihe r: Rechteck bis zur Fugenmitte und Vorderflaeche (um halbe Fuge und Fase eingerueckt)."""
    x0, x1 = SCOLS[c], SCOLS[c + 1]
    z0, z1 = SROWS[r]
    m = JW + BC
    return (x0, x1, z0, z1), (x0 + m, x1 - m, z0 + (m if z0 > 1e-9 else 0.0), z1 - m)

def cell_shape(a, cut):
    """Vorderflaeche (Polygon) und Kanten mit Fase [(P0, P1, aussen)]; Schnittkanten an Oeffnungen bleiben ohne Fase."""
    x0, x1, z0, z1 = a
    E = []
    bottom = z0 > 1e-9
    def add(p0, p1, out):
        if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > 1e-4:
            E.append((p0, p1, out))
    if cut is None or cut[1] <= x0 or cut[0] >= x1 or cut[2] >= z1:
        if bottom:
            add((x0, z0), (x1, z0), (0, -1))
        add((x1, z0), (x1, z1), (1, 0))
        add((x1, z1), (x0, z1), (0, 1))
        add((x0, z1), (x0, z0), (-1, 0))
        return rect(x0, x1, z0, z1), E
    ox0, ox1, oz0 = cut
    if ox0 <= x0 and ox1 >= x1:
        if oz0 <= z0 + 1e-6:
            return None, []
        if bottom:
            add((x0, z0), (x1, z0), (0, -1))
        add((x1, z0), (x1, oz0), (1, 0))
        add((x0, oz0), (x0, z0), (-1, 0))
        return rect(x0, x1, z0, oz0), E
    if ox0 > x0:
        if oz0 <= z0 + 1e-6:
            if bottom:
                add((x0, z0), (ox0, z0), (0, -1))
            add((ox0, z1), (x0, z1), (0, 1))
            add((x0, z1), (x0, z0), (-1, 0))
            return rect(x0, ox0, z0, z1), E
        if bottom:
            add((x0, z0), (x1, z0), (0, -1))
        add((x1, z0), (x1, oz0), (1, 0))
        add((ox0, z1), (x0, z1), (0, 1))
        add((x0, z1), (x0, z0), (-1, 0))
        return [(x0, z0), (x1, z0), (x1, oz0), (ox0, oz0), (ox0, z1), (x0, z1)], E
    if oz0 <= z0 + 1e-6:
        if bottom:
            add((ox1, z0), (x1, z0), (0, -1))
        add((x1, z0), (x1, z1), (1, 0))
        add((x1, z1), (ox1, z1), (0, 1))
        return rect(ox1, x1, z0, z1), E
    if bottom:
        add((x0, z0), (x1, z0), (0, -1))
    add((x1, z0), (x1, z1), (1, 0))
    add((x1, z1), (ox1, z1), (0, 1))
    add((x0, oz0), (x0, z0), (-1, 0))
    return [(x0, z0), (x1, z0), (x1, z1), (ox1, z1), (ox1, oz0), (x0, oz0)], E

def chamfer(pc, s, p0, p1, out):
    (xa, za), (xb, zb) = p0, p1
    ox, oz = out
    P = [Vector((xa, s * T2, za)), Vector((xb, s * T2, zb)), Vector((xb + ox * BC, s * (T2 - BC), zb + oz * BC)),
         Vector((xa + ox * BC, s * (T2 - BC), za + oz * BC))]
    pc.face(P, 1, R_PLANAX, (ox, s, oz), par=(xb - xa, 0, zb - za), reg=PLAN_REG.index("stein_kante"))

def rim(pc, s, loop, ytop, ybot, reg, hole=None):
    """Rand einer Vertiefung entlang loop, von |y| = ytop (Zahl oder je Kante) bis ybot; Teile im Loch entfallen."""
    n = len(loop)
    ccw = loop_area(loop) > 0
    ri = PLAN_REG.index(reg) if isinstance(reg, str) else None
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        yt = ytop[i] if isinstance(ytop, (list, tuple)) else ytop
        rg = ri if ri is not None else PLAN_REG.index(reg[i])
        segs = [(0.0, 1.0)]
        if hole is not None:
            mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            if point_in(hole, mx, mz):
                continue
        ax_ = (b[0] - a[0], 0.0, b[1] - a[1])
        P = [Vector((a[0], s * yt, a[1])), Vector((b[0], s * yt, b[1])), Vector((b[0], s * ybot, b[1])), Vector((a[0], s * ybot, a[1]))]
        pc.face(P, 1, R_PLANAX, edge_inward(loop, i, ccw), par=ax_, reg=rg)

def slab_gone(pc, s, ro, hole=None):
    """Platte abgefallen: Kleberbett mit Kammspuren, Rand an den Nachbarplatten."""
    x0, x1, z0, z1 = ro
    loop = rect(x0, x1, z0, z1)
    rim(pc, s, loop, T2 - BC, YS, "stein_kante", hole)
    surface(pc, loop, [hole] if hole else [], s * YS, s, R_BAND, reg="kleber", band=BAND_K)
    return loop

def slab_broken(pc, s, a, ro, corner, da, db, seed):
    """Ecke einer Platte abgebrochen: gezackte Bruchkante, darunter das Kleberbett."""
    rng = random.Random(seed)
    x0, x1, z0, z1 = a
    C = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    k = {"bl": 0, "br": 1, "tr": 2, "tl": 3}[corner]
    ck, cprev, cnext = C[k], C[(k - 1) % 4], C[(k + 1) % 4]
    def toward(p, q, d):
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        return (p[0] + (q[0] - p[0]) * d / L, p[1] + (q[1] - p[1]) * d / L)
    pB = toward(ck, cprev, db)
    pA = toward(ck, cnext, da)
    m = 6
    jag = []
    for i in range(1, m):
        t = i / m
        px, pz = pB[0] + (pA[0] - pB[0]) * t, pB[1] + (pA[1] - pB[1]) * t
        nx, nz_ = -(pA[1] - pB[1]), pA[0] - pB[0]
        L = math.hypot(nx, nz_)
        off = rng.uniform(-0.018, 0.018) * math.sin(math.pi * t)
        jag.append((px + nx / L * off, pz + nz_ / L * off))
    remain = [pA, cnext, C[(k + 2) % 4], cprev, pB] + jag
    pc.tess(remain, [], s * T2, 0, R_WM if s < 0 else R_WP, (0, s, 0))
    outs = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}             # Kante i laeuft von C[i] nach C[i+1]
    def edge_out(i):
        return outs[i % 4]
    for i in range(4):
        p0, p1 = C[i], C[(i + 1) % 4]
        if i == 0 and z0 <= 1e-9:
            continue
        if i == k:                       # Kante von ck nach cnext: nur ab pA
            p0 = pA
        if (i + 1) % 4 == k:             # Kante von cprev nach ck: nur bis pB
            p1 = pB
        chamfer(pc, s, p0, p1, edge_out(i))
    # Vertiefung bis zur Fugenmitte: Ecke der Fugen, Punkte an den Kanten nach aussen verlaengert
    oA, oB = edge_out(k), edge_out(k - 1)
    m_ = JW + BC
    ck_o = (ck[0] + (oA[0] + oB[0]) * m_, max(0.0, ck[1] + (oA[1] + oB[1]) * m_))     # nie unter den Boden
    pA_o = (pA[0] + oA[0] * m_, max(0.0, pA[1] + oA[1] * m_))
    pB_o = (pB[0] + oB[0] * m_, max(0.0, pB[1] + oB[1] * m_))
    raw = [pB_o, ck_o, pA_o, pA] + jag[::-1] + [pB]
    rt = [T2 - BC, T2 - BC, T2 - BC] + [T2] * (len(jag) + 1) + [T2 - BC]
    rr = ["stein_kante"] * 3 + ["bruch_stein"] * (len(jag) + 1) + ["stein_kante"]
    loop, tops, regs = [], [], []
    for p, t_, g_ in zip(raw, rt, rr):                 # am Boden fallen Punkte zusammen: doppelte entfernen
        if loop and math.hypot(p[0] - loop[-1][0], p[1] - loop[-1][1]) < 1e-6:
            tops[-1], regs[-1] = t_, g_
            continue
        loop.append(p)
        tops.append(t_)
        regs.append(g_)
    if math.hypot(loop[0][0] - loop[-1][0], loop[0][1] - loop[-1][1]) < 1e-6:
        loop.pop()
        tops.pop()
        regs.pop()
    rim(pc, s, loop, tops, YS, regs)
    surface(pc, loop, [], s * YS, s, R_BAND, reg="kleber", band=BAND_K)
    return loop

def crack_pts(a, rng, horizontal=True):
    """Riss quer ueber eine Platte (4 mm innerhalb der Kanten)."""
    x0, x1, z0, z1 = a
    if horizontal:
        p, q = (x0 + 0.004, rng.uniform(z0 + 0.15, z1 - 0.15)), (x1 - 0.004, rng.uniform(z0 + 0.15, z1 - 0.15))
    else:
        p, q = (rng.uniform(x0 + 0.12, x1 - 0.12), z0 + 0.004), (rng.uniform(x0 + 0.12, x1 - 0.12), z1 - 0.004)
    pts = [p]
    for t in (0.2, 0.4, 0.6, 0.8):
        pts.append((p[0] + (q[0] - p[0]) * t + rng.uniform(-0.012, 0.012) * (0 if horizontal else 1),
                    p[1] + (q[1] - p[1]) * t + rng.uniform(-0.02, 0.02) * (1 if horizontal else 0)))
    pts.append(q)
    return pts, [0.0006, 0.0014, 0.002, 0.0018, 0.0012, 0.0006]

def cladding(pc, side, states=None, cut=None, hole=None):
    """Steinplatten 60 x 60 cm bis 1,2 m: Vorderseite mit dem Wandbild, Fasen, dahinter die Fugenmasse.
    states: {(Spalte, Reihe): ("riss", horizontal, seed) | ("fehlt",) | ("bruch", Ecke, a, b, seed)}."""
    s = side
    states = states or {}
    holes = []
    for c in range(len(SCOLS) - 1):
        for r in range(len(SROWS)):
            ro, a = cell_rects(c, r)
            st = states.get((c, r), ("ok",))
            if st[0] != "ok" and c in (0, len(SCOLS) - 2):
                raise RuntimeError(f"{pc.name}: Randplatten bleiben heil (40-cm-Regel)")
            if st[0] == "fehlt":
                holes.append(slab_gone(pc, s, ro, hole))
                continue
            if st[0] == "bruch":
                holes.append(slab_broken(pc, s, a, ro, *st[1:]))
                continue
            poly, E = cell_shape(a, cut)
            if poly is None:
                continue
            ch = []
            if st[0] == "riss":
                pts, wid = crack_pts(a, random.Random(st[2]), st[1])
                ch.append(groove(pc, pts, wid, s, 0.006, reg="riss"))
            if hole is not None and any(point_in(hole, x, z) for x, z in poly):
                raise RuntimeError(f"{pc.name}: Platte {c},{r} liegt im Durchbruch")
            pc.tess(poly, ch, s * T2, 0, R_WM if s < 0 else R_WP, (0, s, 0))
            for p0, p1, out in E:
                chamfer(pc, s, p0, p1, out)
    if cut is not None:
        holes.append(rect(cut[0], cut[1], cut[2] if cut[2] > 0 else -0.01, TRENN + 0.01))
    if hole is not None:
        holes.append(hole)
    surface(pc, rect(-W2, W2, 0.0, TRENN), holes, s * (T2 - BC), s, R_BAND, reg="kleber", band=BAND_K)

# ---------- Gipskarton, Staender, Daemmung ----------
def crumble_rim(pc, s, loop, seed, y0=T2, y1=YG, reg="gips", amp=0.006):
    """Bruchrand der Beplankung: drei Lagen, die mittlere zerbroeselt (Gips bricht unregelmaessig).
    y0 darf eine Funktion von z sein (im Steinbereich beginnt der Rand auf dem Kleberbett)."""
    n = len(loop)
    y0f = y0 if callable(y0) else (lambda z: y0)
    cx = sum(p[0] for p in loop) / n
    cz = sum(p[1] for p in loop) / n
    rows = []
    for k in range(n):
        x, z = loop[k]
        ux, uz = x - cx, z - cz
        L = math.hypot(ux, uz) or 1.0
        ux, uz = ux / L, uz / L
        d = amp * (0.6 + noise.noise(Vector((x * 23, z * 23, seed))))
        ya = y0f(z)
        ym = (ya + y1) / 2
        rows.append([Vector((x, s * ya, z)), Vector((x + ux * d, s * ym, z + uz * d)), Vector((x + ux * d * 0.5, s * y1, z + uz * d * 0.5))])
    ccw = loop_area(loop) > 0
    ri = PLAN_REG.index(reg)
    for k in range(n):
        k2 = (k + 1) % n
        for j in range(2):
            P = [rows[k][j], rows[k2][j], rows[k2][j + 1], rows[k][j + 1]]
            e = rows[k2][j] - rows[k][j]
            pc.face(P, 1, R_PLANAX, edge_inward(loop, k, ccw), par=(e.x, e.y, e.z), reg=ri)
    return [(r[2].x, r[2].z) for r in rows]

def bays(xa, xb):
    """Felder zwischen den Staendern im Bereich xa .. xb."""
    cuts = [x for x in STUDS if xa < x < xb]
    pts = [xa] + cuts + [xb]
    return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1) if pts[i + 1] - pts[i] > 0.01]

def flange(pc, s, x, za, zb, y=None):
    y = s * (YG - 0.0007) if y is None else y
    a, b = x - SW / 2, x + SW / 2
    pc.face([Vector((a, y, za)), Vector((b, y, za)), Vector((b, y, zb)), Vector((a, y, zb))], 1, R_PLANAX, (0, s, 0), par=(0, 0, 1),
            reg=PLAN_REG.index("stahl_07"))

def wool_disp(s, seed):
    """Daemmung wellt sich: etwas nach vorn gewoelbt, stellenweise eingesackt (bleibt hinter der Beplankung)."""
    def d(x, z):
        n1 = noise.noise(Vector((x * 9, z * 9, seed)))
        n2 = noise.noise(Vector((x * 4, z * 4, seed + 3)))
        return s * (0.003 * n1 - 0.006 * max(0.0, n2))
    return d

def stud_cavity(pc, s, region, rng, torn=1, skip=()):
    """Hohlraum hinter der Beplankung: Rueckseite der Gegenplatte, gelbe Daemmung je Feld (gewellt, stellenweise
    ausgerissen), vorne die Flansche der Staender."""
    xa, xb, za, zb = region
    surface(pc, rect(xa, xb, za, zb), [], -s * YG, s, R_BAND, reg="karton", band=BAND_P)
    wi = PLAN_REG.index("wolle")
    disp = wool_disp(s, rng.uniform(0, 50))
    for bx0, bx1 in bays(xa, xb):
        w, h = bx1 - bx0, zb - za
        # Baender mittig im Feld: oben und unten bleibt kein duenner Streifen, den die Wellung steil kippen wuerde
        borg = za - (BAND_W - h % BAND_W) / 2
        bands_z = [borg + k * BAND_W for k in range(1, 20) if za + 1e-6 < borg + k * BAND_W < zb - 1e-6]
        holes = []
        tries = 0
        while len(holes) < torn and tries < 12 and w >= 0.2 and h >= 0.2:
            tries += 1
            rx, rz = rng.uniform(0.04, min(0.09, w * 0.25)), rng.uniform(0.05, min(0.12, h * 0.25))
            cx = rng.uniform(bx0 + rx + 0.04, bx1 - rx - 0.04)
            cz = rng.uniform(za + rz + 0.04, zb - rz - 0.04)
            if any(abs(cz - zz) < rz * 1.3 + 0.03 for zz in bands_z):
                continue
            lp = noisy_loop(cx, cz, rx, rz, 16, rng.uniform(0, 50), 0.25)
            if any(point_in(h_, x, z) for h_ in holes for x, z in lp):
                continue
            holes.append(lp)
        # Rand und Inneres fein und gleichmaessig unterteilt, damit die Wellung keine schiefen Splitter erzeugt
        gx = max(1, int(round((bx1 - bx0) / 0.075)))
        gz = max(1, int(round((zb - za) / 0.075)))
        xs_ = [bx0 + (bx1 - bx0) * i / gx for i in range(gx + 1)]
        zs_ = [za + (zb - za) * j / gz for j in range(gz + 1)]
        outer = [(x, za) for x in xs_[:-1]] + [(bx1, z) for z in zs_[:-1]] + [(x, zb) for x in xs_[:0:-1]] + [(bx0, z) for z in zs_[:0:-1]]
        st = []
        for x in xs_[1:-1]:
            for z in [z_ for z_ in zs_[1:-1] if all(abs(z_ - zz) >= 0.02 for zz in bands_z)] + bands_z:
                if any(point_in(h_, x, z) or min(math.hypot(x - hx, z - hz) for hx, hz in h_) < 0.025 for h_ in holes):
                    continue
                st.append((x, z))
        surface(pc, outer, holes, s * YI, s, R_BAND, reg="wolle", band=BAND_W, steiner=st, disp=disp, borg=borg)
        for lp in holes:
            n = len(lp)
            ccw = loop_area(lp) > 0
            for i in range(n):
                a, b = lp[i], lp[(i + 1) % n]
                P = [Vector((a[0], s * YI + disp(*a), a[1])), Vector((b[0], s * YI + disp(*b), b[1])), Vector((b[0], -s * YG, b[1])),
                     Vector((a[0], -s * YG, a[1]))]
                pc.face(P, 1, R_PLANAX, edge_inward(lp, i, ccw), par=(b[0] - a[0], 0, b[1] - a[1]), reg=wi)
    for x in STUDS:
        if xa - SW / 2 < x < xb + SW / 2 and x not in skip:
            flange(pc, s, x, za, zb)

def gk_hole(pc, s, loop, seed, torn=1):
    """Loch im Gipskarton: zerbroeselter Rand, dahinter Staender und Daemmung."""
    rng = random.Random(seed)
    crumble_rim(pc, s, loop, seed)
    xs = [p[0] for p in loop]
    zs = [p[1] for p in loop]
    region = (max(-W2 + 0.3, min(xs) - 0.06), min(W2 - 0.3, max(xs) + 0.06), min(zs) - 0.06, min(H - 0.01, max(zs) + 0.06))
    stud_cavity(pc, s, region, rng, torn)
    return loop

def c_sweep(pc, pts, web=2 * YG, fl=SW, lip=0.008, t=0.0008, ref=(0, 1, 0)):
    """Gebogenes C-Profil entlang pts (Linie = Mitte der Stegaussenseite): Steg quer zur Wand, Flansche nach +x.
    Aussen- und Innenseite des Blechs; U = Laenge entlang des Profils, V = Abwicklung des Querschnitts."""
    pts = [Vector(p) for p in pts]
    n = len(pts)
    z0r = REG["profil"][0]
    tans = []
    for k in range(n):
        tt = (pts[1] - pts[0]) if k == 0 else (pts[-1] - pts[-2]) if k == n - 1 else \
            ((pts[k + 1] - pts[k]).normalized() + (pts[k] - pts[k - 1]).normalized())
        tans.append(tt.normalized())
    b1 = Vector(ref)
    b1 = (b1 - tans[0] * b1.dot(tans[0])).normalized()
    frames = []
    for k in range(n):
        if k > 0:
            b1 = tans[k - 1].rotation_difference(tans[k]) @ b1
            b1 = (b1 - tans[k] * b1.dot(tans[k])).normalized()
        frames.append((b1.copy(), tans[k].cross(b1).normalized()))
    outer = [(fl, web / 2 - lip), (fl, web / 2), (0, web / 2), (0, -web / 2), (fl, -web / 2), (fl, -web / 2 + lip)]
    inner = [(fl - t, web / 2 - lip), (fl - t, web / 2 - t), (t, web / 2 - t), (t, -web / 2 + t), (fl - t, -web / 2 + t), (fl - t, -web / 2 + lip)]
    def unroll(cs):
        a = [0.0]
        for j in range(1, len(cs)):
            a.append(a[-1] + math.hypot(cs[j][0] - cs[j - 1][0], cs[j][1] - cs[j - 1][1]))
        return a
    def ring(k, cs):
        q, p = frames[k]
        return [pts[k] + p * a + q * b for a, b in cs]
    O = [ring(k, outer) for k in range(n)]
    I = [ring(k, inner) for k in range(n)]
    for R, sgn, sv in ((O, 1, unroll(outer)), (I, -1, unroll(inner))):
        acc = [[0.0] * len(outer)]
        for k in range(1, n):
            acc.append([acc[-1][j] + (R[k][j] - R[k - 1][j]).length for j in range(len(outer))])
        for k in range(n - 1):
            for j in range(len(outer) - 1):
                P = [R[k][j], R[k][j + 1], R[k + 1][j + 1], R[k + 1][j]]
                mo = (O[k][j] + O[k][j + 1] + O[k + 1][j + 1] + O[k + 1][j]) / 4
                mi = (I[k][j] + I[k][j + 1] + I[k + 1][j + 1] + I[k + 1][j]) / 4
                uvs = [(UVS * acc[k][j], UVS * (z0r + 0.002 + sv[j])), (UVS * acc[k][j + 1], UVS * (z0r + 0.002 + sv[j + 1])),
                       (UVS * acc[k + 1][j + 1], UVS * (z0r + 0.002 + sv[j + 1])), (UVS * acc[k + 1][j], UVS * (z0r + 0.002 + sv[j]))]
                pc.face(P, 1, R_KEEP, (mo - mi) * sgn, uvs=uvs)

# ---------- Kleinteile ----------
def shard2(pc, x, y, seed, size=(0.03, 0.08), zbase=0.0, thick=0.0125, top=0, edge="gips"):
    """Bruchstueck einer Platte: Oberseite aus dem Wandbild (0 = Gipskarton, 1 = Stein), Kanten Bruch."""
    rng = random.Random(seed)
    a, b = rng.uniform(*size), rng.uniform(*size)
    pts = [(0, 0), (a, rng.uniform(-0.01, 0.01)), (a * rng.uniform(0.5, 1.0), b), (rng.uniform(-0.01, 0.02), b * rng.uniform(0.6, 1.0))]
    ang = rng.uniform(0, math.tau)
    ca, sa = math.cos(ang), math.sin(ang)
    tilt = rng.uniform(-0.15, 0.15)
    P = [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]
    z0 = zbase + 0.001 + rng.uniform(0, 0.004)
    lift = max(0.0, zbase - min(z0 + tilt * (p[0] - x) for p in P))
    top_ = [Vector((p[0], p[1], z0 + thick + tilt * (p[0] - x) + lift)) for p in P]
    bot = [Vector((p[0], p[1], z0 + tilt * (p[0] - x) + lift)) for p in P]
    pc.face(top_, 0, R_SHARD, (0, 0, 1), par=(top, 0, 0))
    ei = PLAN_REG.index(edge)
    pc.face(bot[::-1], 1, R_PLAN, (0, 0, -1), reg=ei)
    c = sum(top_, Vector()) / len(top_)
    for i in range(len(P)):
        j = (i + 1) % len(P)
        pc.face([bot[i], bot[j], top_[j], top_[i]], 1, R_PLAN, (bot[i] + top_[j]) / 2 - c, reg=ei)

def floor_debris(pc, x0, x1, side, n, seed, kinds=("gips", "platte", "wolle", "stein")):
    """Am Fuss der Wand: Gipsbroeckchen, Gipskartonstuecke, Daemmflocken, Steinscherben (hoechstens 12 cm vor der Wand)."""
    rng = random.Random(seed)
    s = side
    for k in range(n):
        kind = kinds[k % len(kinds)]
        x = rng.uniform(x0, x1)
        y = s * (T2 + rng.uniform(0.04, 0.08))
        n0 = set(pc.bm.verts)
        if kind == "gips":
            sz = rng.uniform(0.008, 0.02)
            chunk(pc, (x, y, sz * 0.4), (sz * 1.4, sz, sz * 0.6), seed * 10 + k, "gips", subdiv=0)
        elif kind == "wolle":
            sz = rng.uniform(0.015, 0.03)
            chunk(pc, (x, y, sz * 0.35), (sz * 1.5, sz, sz * 0.45), seed * 10 + k, "wolle", subdiv=0)
        elif kind == "platte":
            shard2(pc, x, y, seed * 100 + k, size=(0.02, 0.045), thick=0.0125, top=0, edge="gips")
        else:
            shard2(pc, x, y, seed * 100 + k, size=(0.015, 0.035), thick=0.015, top=1, edge="bruch_stein")
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
    """Umfassungszarge aus eloxiertem Aluminium: Spiegel beidseitig 6 cm breit und 2 cm vor der Wand,
    Futter in der Laibung, Anschlag mit Gummidichtung auf -Y, drei Baender."""
    x0, x1, zt = -0.65, 0.65, 2.2
    pl, fl, ft = 0.006, 0.06, 0.02
    yf = T2 + ft
    for a, b in ((x0 - fl, x0 + pl), (x1 - pl, x1 + fl)):
        box_faces(pc, (a, -yf, 0.0), (b, yf, zt - pl), R_ALU, bevel=0.002, axis=(0, 0, 1))
    box_faces(pc, (x0 - fl, -yf, zt - pl), (x1 + fl, yf, zt + fl), R_ALU, bevel=0.002, axis=(1, 0, 0))
    st, ys0, ys1 = 0.025, -0.045, -0.02
    zs = zt - pl - st
    box_faces(pc, (x0 + pl, ys0, 0.0), (x0 + pl + st, ys1, zs), R_ALU, axis=(0, 0, 1))
    box_faces(pc, (x1 - pl - st, ys0, 0.0), (x1 - pl, ys1, zs), R_ALU, axis=(0, 0, 1))
    box_faces(pc, (x0 + pl, ys0, zs), (x1 - pl, ys1, zt - pl), R_ALU, axis=(1, 0, 0))
    g = PLAN_REG.index("gummi")
    gy0, gy1 = ys0 - 0.007, ys0
    box_faces(pc, (x0 + pl + 0.007, gy0, 0.0), (x0 + pl + 0.019, gy1, zs - 0.019), R_PLANAX, reg=g, axis=(0, 0, 1))
    box_faces(pc, (x1 - pl - 0.019, gy0, 0.0), (x1 - pl - 0.007, gy1, zs - 0.019), R_PLANAX, reg=g, axis=(0, 0, 1))
    box_faces(pc, (x0 + pl + 0.007, gy0, zs - 0.019), (x1 - pl - 0.007, gy1, zs - 0.007), R_PLANAX, reg=g, axis=(1, 0, 0))
    for zc in (0.25, 1.05, 1.9):
        tube(pc, [(x0 + pl + 0.012, -0.062, zc), (x0 + pl + 0.012, -0.062, zc + 0.1)], 0.009, "stahl_07", seg=8)

def shop_window(pc):
    """Schaufenster: Laibung aus Gipskarton, Blendrahmen aus eloxiertem Aluminium (5 cm Ansicht, 10 cm tief) mit
    leerem Glasfalz (Glasleisten, Dichtungen), innen eine Bank aus dunklem Stein, aussen ein Alublech."""
    x0, x1, z0, z1 = -0.75, 0.75, 0.95, 2.35
    for x, sg in ((x0, 1), (x1, -1)):
        pc.face([Vector((x, -T2, z0)), Vector((x, T2, z0)), Vector((x, T2, z1)), Vector((x, -T2, z1))], 0, R_REVX, (sg, 0, 0))
    pc.face([Vector((x0, -T2, z1)), Vector((x1, -T2, z1)), Vector((x1, T2, z1)), Vector((x0, T2, z1))], 0, R_REVZ, (0, 0, -1), par=(z1, 0, 0))
    fw, fd, bev = 0.05, 0.05, 0.0015
    box_faces(pc, (x0, -fd, z0 + fw), (x0 + fw, fd, z1 - fw), R_ALU, bevel=bev, axis=(0, 0, 1))
    box_faces(pc, (x1 - fw, -fd, z0 + fw), (x1, fd, z1 - fw), R_ALU, bevel=bev, axis=(0, 0, 1))
    box_faces(pc, (x0, -fd, z1 - fw), (x1, fd, z1), R_ALU, bevel=bev, axis=(1, 0, 0))
    box_faces(pc, (x0, -fd, z0), (x1, fd, z0 + fw), R_ALU, bevel=bev, axis=(1, 0, 0))
    ix0, ix1, iz0, iz1 = x0 + fw, x1 - fw, z0 + fw, z1 - fw
    g = PLAN_REG.index("gummi")
    for ya, yb_ in ((-0.032, -0.013), (0.013, 0.032)):              # Glasleiste innen, Anschlag aussen
        box_faces(pc, (ix0, ya, iz0), (ix0 + 0.016, yb_, iz1), R_ALU, axis=(0, 0, 1))
        box_faces(pc, (ix1 - 0.016, ya, iz0), (ix1, yb_, iz1), R_ALU, axis=(0, 0, 1))
        box_faces(pc, (ix0 + 0.016, ya, iz1 - 0.016), (ix1 - 0.016, yb_, iz1), R_ALU, axis=(1, 0, 0))
        box_faces(pc, (ix0 + 0.016, ya, iz0), (ix1 - 0.016, yb_, iz0 + 0.016), R_ALU, axis=(1, 0, 0))
    for ya, yb_ in ((-0.013, -0.009), (0.009, 0.013)):               # Dichtungen am leeren Falz
        box_faces(pc, (ix0 + 0.004, ya, iz0 + 0.004), (ix0 + 0.016, yb_, iz1 - 0.004), R_PLANAX, reg=g, axis=(0, 0, 1))
        box_faces(pc, (ix1 - 0.016, ya, iz0 + 0.004), (ix1 - 0.004, yb_, iz1 - 0.004), R_PLANAX, reg=g, axis=(0, 0, 1))
        box_faces(pc, (ix0 + 0.016, ya, iz1 - 0.016), (ix1 - 0.016, yb_, iz1 - 0.004), R_PLANAX, reg=g, axis=(1, 0, 0))
        box_faces(pc, (ix0 + 0.016, ya, iz0 + 0.004), (ix1 - 0.016, yb_, iz0 + 0.016), R_PLANAX, reg=g, axis=(1, 0, 0))
    box_faces(pc, (x0 - 0.08, -(T2 + 0.03), z0 - 0.03), (x1 + 0.08, -fd, z0), R_PLANAX, reg=PLAN_REG.index("sockel"),
              axis=(1, 0, 0), bevel=0.003)
    box_faces(pc, (x0 - 0.06, fd, z0 - 0.02), (x1 + 0.06, T2 + 0.03, z0), R_ALU, bevel=0.0015, axis=(1, 0, 0))

def pipe_clamp(pc, side, x, yc, zc, r):
    """Rohrschelle (rot mitgestrichen) mit Gewindestange zur Wandplatte."""
    s = side
    rr = r + 0.004
    tube(pc, [(x - 0.011, s * yc, zc), (x + 0.011, s * yc, zc)], rr, "rot", seg=12, caps=True, uoff=0.3)
    ys = sorted((s * T2, s * (T2 + 0.005)))
    drop_back(pc, box_faces(pc, (x - 0.018, ys[0], zc - 0.022), (x + 0.018, ys[1], zc + 0.022), R_METAL, bevel=0.0015), s)
    ys2 = sorted((s * (T2 + 0.005), s * (yc - rr + 0.001)))
    box_faces(pc, (x - 0.005, ys2[0], zc - 0.005), (x + 0.005, ys2[1], zc + 0.005), R_METAL)

def sprinkler_head(pc, side, x, yc, zc, r):
    """Haengender Sprinkler unter dem Rohr: Fitting, Buegel, Glasfass, Spruehteller."""
    s = side
    zb = zc - r
    tube(pc, [(x, s * yc, zb + 0.004), (x, s * yc, zb - 0.018)], 0.012, "rot", seg=8, caps=True)
    tube(pc, [(x, s * yc, zb - 0.018), (x, s * yc, zb - 0.03)], 0.008, "messing", seg=8, caps=True)
    for dx in (-0.007, 0.007):
        box_faces(pc, (x + dx - 0.0015, s * yc - 0.002, zb - 0.058), (x + dx + 0.0015, s * yc + 0.002, zb - 0.03), R_PLAN,
                  reg=PLAN_REG.index("messing"))
    tube(pc, [(x, s * yc, zb - 0.033), (x, s * yc, zb - 0.052)], 0.0025, "rot", seg=6, caps=True)
    tube(pc, [(x, s * yc, zb - 0.058), (x, s * yc, zb - 0.061)], 0.016, "messing", seg=10, caps=True)

def ceiling_lines(pc, side):
    """Unter der Decke: Kabelkanal und rotes Sprinklerrohr mit Schellen und zwei Sprinklern, buendig an beiden Kanten."""
    s = side
    profile_strip(pc, KANAL_PROF, -W2, W2, s, "kanal")
    r, zc = 0.03, 3.14
    yc = T2 + 0.016 + r
    tube(pc, [(-W2, s * yc, zc), (W2, s * yc, zc)], r, "rot", seg=12, caps=False, uoff=0.0)
    for x in (-1.3, 0.0, 1.3):
        pipe_clamp(pc, s, x, yc, zc, r)
    for x in (-0.65, 0.65):
        sprinkler_head(pc, s, x, yc, zc, r)
    for x in (-1.0, 0.45):                                   # Klemmen, die den Kanal halten
        ys = sorted((s * T2, s * (T2 + 0.062)))
        box_faces(pc, (x - 0.01, ys[0], 3.254), (x + 0.01, ys[1], 3.26), R_METAL)

def cabinet(pc, side, xc, zc):
    """Feuerloescherkasten, in die Staenderwand eingelassen: Blende 2,5 cm, Tuer 180 Grad aufgeklappt flach neben dem
    Kasten, innen Schild und Feuerloescher an der Halterung."""
    s = side
    W, HH, D = KASTEN_W, KASTEN_H, KASTEN_T
    bx0, bx1 = xc - W / 2, xc + W / 2
    bz0, bz1 = zc - HH / 2, zc + HH / 2
    yb = T2 - D
    ix0, ix1, iz0, iz1 = bx0 + 0.01, bx1 - 0.01, bz0 + 0.01, bz1 - 0.01
    ri = PLAN_REG.index("rot")
    # Innenraum: Seiten, Boden, Decke, Rueckwand mit Schild
    for P, want in (([(ix0, iz0), (ix0, iz1)], (1, 0, 0)), ([(ix1, iz1), (ix1, iz0)], (-1, 0, 0)),
                    ([(ix1, iz0), (ix0, iz0)], (0, 0, 1)), ([(ix0, iz1), (ix1, iz1)], (0, 0, -1))):
        (ax, az), (bx_, bz_) = P
        Q = [Vector((ax, s * T2, az)), Vector((bx_, s * T2, bz_)), Vector((bx_, s * yb, bz_)), Vector((ax, s * yb, az))]
        pc.face(Q, 1, R_PLANAX, want, par=(bx_ - ax, 0, bz_ - az), reg=ri)
    code = -1 if s > 0 else 1
    bref = ix1 if s > 0 else ix0
    pc.face([Vector((ix0, s * yb, iz0)), Vector((ix1, s * yb, iz0)), Vector((ix1, s * yb, iz1)), Vector((ix0, s * yb, iz1))], 1,
            R_BOXROT, (0, s, 0), par=(bref, iz0, code * 1))
    # Blende (Rahmen) 2,5 cm breit, 1 cm vor der Wand
    fw, ft = 0.025, 0.01
    ys = sorted((s * T2, s * (T2 + ft)))
    fs = box_faces(pc, (ix0 - fw, ys[0], iz0 - fw), (ix1 + fw, ys[1], iz0), R_PLANAX, reg=ri, bevel=0.002, axis=(1, 0, 0))
    fs += box_faces(pc, (ix0 - fw, ys[0], iz1), (ix1 + fw, ys[1], iz1 + fw), R_PLANAX, reg=ri, bevel=0.002, axis=(1, 0, 0))
    fs += box_faces(pc, (ix0 - fw, ys[0], iz0), (ix0, ys[1], iz1), R_PLANAX, reg=ri, bevel=0.002, axis=(0, 0, 1))
    fs += box_faces(pc, (ix1, ys[0], iz0), (ix1 + fw, ys[1], iz1), R_PLANAX, reg=ri, bevel=0.002, axis=(0, 0, 1))
    drop_back(pc, fs, s)
    # Tuer: um 180 Grad aufgeklappt, liegt mit 1,2 cm Abstand flach neben dem Kasten, Innenseite nach vorn
    hx = ix1 + fw if s > 0 else ix0 - fw
    dw, dh, dt = KASTEN_W - 0.005, KASTEN_H - 0.005, 0.02
    dx0, dx1 = (hx + 0.004, hx + 0.004 + dw) if s > 0 else (hx - 0.004 - dw, hx - 0.004)
    dz0 = zc - dh / 2
    yd0, yd1 = T2 + 0.012, T2 + 0.012 + dt
    ys = sorted((s * yd0, s * yd1))
    door = box_faces(pc, (dx0, ys[0], dz0), (dx1, ys[1], dz0 + dh), R_PLANAX, reg=ri, bevel=0.002, axis=(0, 0, 1))
    for f in door:
        f.normal_update()
        if f.normal.y * s > 0.99:
            f[pc.rule] = R_BOXROT
            f[pc.par] = ((dx1 if s > 0 else dx0), dz0, code * 2)
    drop_back(pc, door, s, yd0)
    for zz in (dz0 + 0.08, dz0 + dh - 0.12):
        tube(pc, [(hx, s * (T2 + 0.012), zz), (hx, s * (T2 + 0.012), zz + 0.05)], 0.006, "stahl_07", seg=8)
    # Feuerloescher an der Halterung
    ly = yb + 0.065
    lz0 = iz0 + 0.045
    hb = 0.34
    tube(pc, [(xc, s * ly, lz0), (xc, s * ly, lz0 + hb)], LR, "loescher", seg=12, caps=True)
    tube(pc, [(xc, s * ly, lz0 + hb), (xc, s * ly, lz0 + hb + 0.04)], 0.009, "schwarz", seg=6, caps=True)
    ys = sorted((s * (ly - 0.012), s * (ly + 0.012)))
    box_faces(pc, (xc - 0.012, ys[0], lz0 + hb + 0.04), (xc + 0.035, ys[1], lz0 + hb + 0.052), R_PLAN, reg=PLAN_REG.index("schwarz"))
    box_faces(pc, (xc - 0.04, ys[0], lz0 + hb + 0.052), (xc + 0.03, ys[1], lz0 + hb + 0.062), R_PLAN, reg=PLAN_REG.index("schwarz"))
    hose = fillet([Vector((xc + 0.02, s * ly, lz0 + hb + 0.03)), Vector((xc + 0.065, s * (ly + 0.02), lz0 + hb)),
                   Vector((xc + 0.07, s * (ly + 0.03), lz0 + 0.1)), Vector((xc + 0.045, s * (ly + 0.045), lz0 + 0.04))], 0.03, 3)
    tube(pc, hose, 0.007, "schwarz", seg=6, caps=True)
    ys = sorted((s * yb, s * (ly - 0.05)))
    drop_back(pc, box_faces(pc, (xc - 0.025, ys[0], lz0 + 0.22), (xc + 0.025, ys[1], lz0 + 0.25), R_METAL), s, yb)

# ======================= Durchbruch =======================
def through_hole_outline(seed=3.1, N=72):
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

def expand_loop(loop, d, amp, seed):
    """Umriss nach aussen schieben (sternfoermig um den Schwerpunkt), Abstand schwankt."""
    cx = sum(p[0] for p in loop) / len(loop)
    cz = sum(p[1] for p in loop) / len(loop)
    out = []
    for x, z in loop:
        ux, uz = x - cx, z - cz
        r = math.hypot(ux, uz) or 1.0
        dd = d * (1 + amp * noise.noise(Vector((x * 7, z * 7, seed))))
        out.append((cx + ux * (r + dd) / r, cz + uz * (r + dd) / r))
    return out

def bent_studs(pc, hole, rng):
    """Die Staender im Loch sind durchtrennt; die Stummel ragen verbogen in die Oeffnung. Gebogen wird vor allem zur
    Seite (schwache Achse, der Steg bleibt eben), nur wenig aus der Wand heraus (nie mehr als 12 cm vor)."""
    for x in STUDS:
        segs = line_hits(hole, "v", x)
        if not segs:
            continue
        lo, hi = segs[0][0], segs[-1][1]
        toward = -1 if x > 0.1 else 1 if x < -0.1 else rng.choice([-1, 1])
        for end, sgn in ((lo, 1), (hi, -1)):
            Lr = rng.uniform(0.16, 0.3)
            dx = toward * rng.uniform(0.07, 0.16)
            dy = rng.uniform(-0.035, 0.035)
            p0 = Vector((x, 0.0, end - sgn * 0.16))
            p1 = Vector((x, 0.0, end + sgn * 0.02))
            p2 = Vector((x + dx * 0.35, dy * 0.5, end + sgn * Lr * 0.6))
            p3 = Vector((x + dx, dy, end + sgn * Lr))
            c_sweep(pc, fillet([p0, p1, p2, p3], 0.12, 3), ref=(0, 1, 0))

def rubble(pc, side, xc, seed):
    """Schuttkegel bis 60 cm vor der Wand: Gipsbrocken und Gipsstaub, Gipskartonstuecke, Steinscherben, Daemmflocken,
    ein verbogenes Profilstueck."""
    rng = random.Random(int(seed * 100) + (5 if side > 0 else 1))
    nxp, nyp = 12, 6
    rx, ry, hmax = 0.78, 0.48, 0.17
    V = []
    for i in range(nxp + 1):
        sx = 2 * i / nxp - 1
        reach = min(1.0, 0.8 + 0.2 * noise.noise(Vector((sx * 2.2, side * 5.0, seed))))
        row = []
        for j in range(nyp + 1):
            t = j / nyp
            half = rx * math.sqrt(max(0.0, 1 - (0.8 * t) ** 2)) * (1 + 0.1 * noise.noise(Vector((t * 3.0, side * 3.0, seed + 1.4))))
            x = xc + half * sx
            yd = PLD + 0.004 + ry * reach * t
            fall = max(0.0, 1 - sx * sx) * max(0.0, 1 - t ** 1.4)
            fall *= 1 + 0.3 * noise.noise(Vector((x * 2.5, yd * 2.5, side * 3 + seed)))
            lump = 0.025 * noise.noise(Vector((x * 8, yd * 8, side + seed))) + 0.01 * noise.noise(Vector((x * 22, yd * 22, side + seed + 5)))
            z = hmax * fall + (lump * min(1.0, 4 * fall) if 0 < i < nxp and j < nyp else 0)
            row.append(Vector((x, side * (T2 + yd), max(0.0, z))))
        V.append(row)
    for i in range(nxp):
        for j in range(nyp):
            P = [V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]]
            if max(p.z for p in P) < 0.002:
                continue
            pc.face(P, 1, R_PLAN, (0, side * 0.3, 1), reg=PLAN_REG.index("gips"))
    idx = lambda i, j: i * (nyp + 1) + j
    tree = BVHTree.FromPolygons([v for row in V for v in row],
                                [(idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)) for i in range(nxp) for j in range(nyp)])
    def heap_z(x, yd):
        hit = tree.ray_cast(Vector((x, side * (T2 + yd), 2.0)), Vector((0, 0, -1)))
        return max(0.0, hit[0].z) if hit[0] is not None else 0.0
    off = 20 if side > 0 else 0
    for k in range(6):
        x, yd, s_ = xc + rng.uniform(-0.55, 0.55), rng.uniform(0.06, 0.34), rng.uniform(0.02, 0.045)
        chunk(pc, (x, side * (T2 + yd), heap_z(x, yd) + s_ * 0.3), (s_ * 1.4, s_, s_ * 0.6), 60 + k + off, "gips", subdiv=0)
    for k in range(4):
        x, yd, s_ = xc + rng.uniform(-0.6, 0.6), rng.uniform(0.06, 0.38), rng.uniform(0.04, 0.07)
        chunk(pc, (x, side * (T2 + yd), heap_z(x, yd) + s_ * 0.18), (s_ * 1.4, s_, s_ * 0.35), 200 + k + off, "wolle", subdiv=0)
    for k in range(7):
        x, yd = xc + rng.uniform(-0.6, 0.6), rng.uniform(0.06, 0.42)
        shard2(pc, x, side * (T2 + yd), 300 + k + off, size=(0.06, 0.14), zbase=max(0.0, heap_z(x, yd) - 0.004), thick=0.0125, top=0,
               edge="gips")
    for k in range(4):
        x, yd = xc + rng.uniform(-0.55, 0.55), rng.uniform(0.06, 0.35)
        shard2(pc, x, side * (T2 + yd), 400 + k + off, size=(0.05, 0.12), zbase=max(0.0, heap_z(x, yd) - 0.004), thick=0.015, top=1,
               edge="bruch_stein")
    x, yd = xc + rng.uniform(-0.3, 0.3), rng.uniform(0.18, 0.3)
    a = rng.uniform(-0.5, 0.5)
    p0 = Vector((x, side * (T2 + yd), heap_z(x, yd) + 0.02))
    d = Vector((math.cos(a), side * math.sin(a) * 0.3, 0.0))
    pts = [p0 + d * (0.07 * k) + Vector((0, 0, 0.03 * math.sin(k * 0.9))) for k in range(5)]
    for p in pts:
        p.z = max(p.z, heap_z(p.x, abs(p.y) - T2) + 0.012)
    c_sweep(pc, pts, web=0.1, ref=(0, 1, 0))

# ======================= Die sieben Stuecke =======================
FULL = [(-W2, W2)]
WALL = rect(-W2, W2, GZ, H)

def drywall(pc, side, outer, holes=(), crossing=False):
    if crossing:
        surface(pc, outer, list(holes), side * T2, side, R_WM if side < 0 else R_WP, mat=0)
    else:
        pc.tess(outer, list(holes), side * T2, 0, R_WM if side < 0 else R_WP, (0, side, 0))

def wand_01():
    pc = Piece(f"{GEB}_wand_01")
    shell(pc)
    cladding(pc, -1, {(2, 0): ("riss", True, 11)})
    cladding(pc, 1, {(4, 1): ("riss", False, 12)})
    for s in (-1, 1):
        drywall(pc, s, WALL)
        shadow_gap(pc, s, FULL)
        strips(pc, s, FULL)
    return finish(pc)

def wand_02():
    pc = Piece(f"{GEB}_wand_02")
    shell(pc)
    crack = [(0.36, 3.33), (0.32, 3.05), (0.4, 2.78), (0.29, 2.5), (0.37, 2.2), (0.27, 1.9), (0.33, 1.6), (0.26, 1.32)]
    wid = [0.002, 0.007, 0.012, 0.018, 0.02, 0.015, 0.008, 0.003]
    # -Y: grosses Loch mit Staendern und Daemmung, ein kleineres, tiefer Riss; Platten abgefallen, gebrochen, gesprungen
    hm = [groove(pc, crack, wid, -1, 0.03, reg="gips")]
    hm.append(gk_hole(pc, -1, noisy_loop(-0.58, 2.2, 0.4, 0.48, 44, 1.3, 0.22), 21, torn=2))
    hm.append(gk_hole(pc, -1, noisy_loop(0.86, 1.68, 0.19, 0.2, 26, 2.9, 0.22), 22, torn=0))
    check_holes(pc.name, hm)
    drywall(pc, -1, WALL, hm)
    cladding(pc, -1, {(2, 1): ("fehlt",), (3, 1): ("bruch", "tr", 0.32, 0.26, 5), (4, 0): ("riss", True, 6), (3, 0): ("riss", False, 7)})
    # +Y: Loch rechts oben (nicht hinter den Loechern der -Y-Seite, sonst saehe man dort die Gegenplatte), der Riss geht durch
    hp = [groove(pc, crack, [w * 0.8 for w in wid], 1, 0.03, reg="gips")]
    hp.append(gk_hole(pc, 1, noisy_loop(0.98, 2.55, 0.3, 0.34, 40, 4.1, 0.22), 23, torn=1))
    check_holes(pc.name, hp)
    drywall(pc, 1, WALL, hp)
    cladding(pc, 1, {(4, 1): ("fehlt",), (2, 0): ("bruch", "bl", 0.28, 0.22, 8), (3, 1): ("riss", True, 9)})
    for s in (-1, 1):
        shadow_gap(pc, s, FULL)
        strips(pc, s, FULL)
    floor_debris(pc, -1.0, 0.0, -1, 14, 31)
    floor_debris(pc, 0.6, 1.1, -1, 5, 32, kinds=("gips", "platte"))
    floor_debris(pc, 0.7, 1.25, 1, 8, 33)
    floor_debris(pc, -0.5, 0.2, 1, 6, 34, kinds=("stein", "gips"))
    return finish(pc)

def wand_03():
    pc = Piece(f"{GEB}_wand_03")
    shell(pc)
    hm = [gk_hole(pc, -1, noisy_loop(-0.92, 2.62, 0.15, 0.17, 24, 6.1, 0.2), 41, torn=0)]
    check_holes(pc.name, hm)
    drywall(pc, -1, WALL, hm)
    cladding(pc, -1, {(3, 1): ("riss", True, 42)})
    xc, zc = 0.31, 1.58
    kb = rect(xc - KASTEN_W / 2 + 0.01, xc + KASTEN_W / 2 - 0.01, zc - KASTEN_H / 2 + 0.01, zc + KASTEN_H / 2 - 0.01)
    drywall(pc, 1, WALL, [kb])
    cladding(pc, 1)
    for s in (-1, 1):
        shadow_gap(pc, s, FULL)
        strips(pc, s, FULL)
    ceiling_lines(pc, 1)
    cabinet(pc, 1, xc, zc)
    floor_debris(pc, -1.05, -0.75, -1, 4, 43, kinds=("gips", "platte"))
    return finish(pc)

def wand_tuer():
    pc = Piece(f"{GEB}_wand_tuer")
    shell(pc)
    x0, x1, zt = -0.65, 0.65, 2.2
    outer = [(-W2, GZ), (x0, GZ), (x0, zt), (x1, zt), (x1, GZ), (W2, GZ), (W2, H), (-W2, H)]
    spans = [(-W2, x0), (x1, W2)]
    base = [(-W2, x0 - 0.06), (x1 + 0.06, W2)]
    drywall(pc, -1, outer)
    cladding(pc, -1, {(5, 0): ("riss", True, 51)}, cut=(x0, x1, 0.0))
    hp = [gk_hole(pc, 1, noisy_loop(1.05, 2.72, 0.17, 0.19, 26, 8.2, 0.2), 52, torn=1)]
    check_holes(pc.name, hp)
    drywall(pc, 1, outer, hp)
    cladding(pc, 1, cut=(x0, x1, 0.0))
    for s in (-1, 1):
        shadow_gap(pc, s, spans)
        strips(pc, s, base)
    door_frame(pc)
    floor_debris(pc, 0.85, 1.25, 1, 5, 53, kinds=("gips", "platte"))
    return finish(pc)

def wand_fenster():
    pc = Piece(f"{GEB}_wand_fenster")
    shell(pc)
    x0, x1, z0, z1 = -0.75, 0.75, 0.95, 2.35
    cut = (x0, x1, z0 - 0.03)
    outer = [(-W2, GZ), (x0, GZ), (x0, z1), (x1, z1), (x1, GZ), (W2, GZ), (W2, H), (-W2, H)]
    spans = [(-W2, x0), (x1, W2)]
    drywall(pc, -1, outer)
    cladding(pc, -1, {(1, 0): ("bruch", "tr", 0.3, 0.2, 61)}, cut=cut)
    hp = [gk_hole(pc, 1, noisy_loop(-1.1, 2.78, 0.16, 0.18, 24, 3.3, 0.2), 62, torn=0)]
    check_holes(pc.name, hp)
    drywall(pc, 1, outer, hp)
    cladding(pc, 1, {(5, 1): ("riss", False, 63)}, cut=cut)
    for s in (-1, 1):
        shadow_gap(pc, s, spans)
        strips(pc, s, FULL)
    shop_window(pc)
    floor_debris(pc, -1.35, -0.95, -1, 4, 64, kinds=("stein", "gips"))
    return finish(pc)

def wand_durchbruch():
    pc = Piece(f"{GEB}_wand_durchbruch")
    shell(pc)
    hole = through_hole_outline()
    check_holes(pc.name, [hole])
    rng = random.Random(71)
    hits = line_hits(hole, "h", TRENN + 0.001) + line_hits(hole, "h", GZ - 0.001)
    gap_spans = subtract_spans(-W2, W2, [(min(h[0] for h in hits), max(h[1] for h in hits))], 0.0)
    torn = expand_loop(hole, 0.07, 0.6, 4.4)
    def y0(z):
        return T2 if z >= GZ - 1e-6 else YS
    for s in (-1, 1):
        # Platten ueber und neben dem Loch sind abgefallen, das Loch geht durch das Kleberbett
        states = {}
        for c in range(1, len(SCOLS) - 2):
            ro, a = cell_rects(c, 1)
            box = rect(ro[0], ro[1], ro[2], ro[3])
            if any(ro[0] <= x <= ro[1] and ro[2] <= z <= ro[3] for x, z in hole) or any(point_in(hole, x, z) for x, z in box):
                states[(c, 1)] = ("fehlt",)
        states.setdefault((3, 0), ("riss", True, 72 + s))
        cladding(pc, s, states, hole=hole)
        loops = {-1: [noisy_loop(-1.12, 2.78, 0.26, 0.24, 30, 7.7, 0.2)], 1: [noisy_loop(1.1, 2.72, 0.26, 0.24, 30, 9.1, 0.2)]}[s]
        holes = [gk_hole(pc, s, lp, 80 + s, torn=0) for lp in loops]
        check_holes(pc.name, holes)
        drywall(pc, s, WALL, [hole] + holes, crossing=True)
        shadow_gap(pc, s, gap_spans)
        strips(pc, s, FULL)
        # zerbroeselter Rand der Beplankung (im Steinbereich auf dem Kleberbett), dahinter die Kartonrueckseite bis zur
        # ausgerissenen Daemmung
        crumble_rim(pc, s, hole, 5.0 + s, y0=y0, amp=0.012)
        surface(pc, torn, [hole], s * YG, -s, R_BAND, reg="karton", band=BAND_P)
    n = len(torn)
    ccw = loop_area(torn) > 0
    wi = PLAN_REG.index("wolle")
    for i in range(n):
        a, b = torn[i], torn[(i + 1) % n]
        P = [Vector((a[0], -YI, a[1])), Vector((b[0], -YI, b[1])), Vector((b[0], YI, b[1])), Vector((a[0], YI, a[1]))]
        pc.face(P, 1, R_PLANAX, edge_inward(torn, i, ccw), par=(b[0] - a[0], 0, b[1] - a[1]), reg=wi)
    bent_studs(pc, hole, rng)
    cx = sum(p[0] for p in hole) / len(hole)
    rubble(pc, -1, cx * 0.3, 3.3)
    rubble(pc, 1, cx * 0.3, 5.1)
    return finish(pc)

def wand_ecke():
    """Eckpfosten 21 x 21 cm: unten Steinplatten (zwei Reihen) mit Eckschutzwinkeln aus Aluminium, Schattenfuge,
    oben Gipskarton; Sockel aus dunklem Stein rundum. Alle Fasen und Fugenflaechen auf Gehrung."""
    pc = Piece(f"{GEB}_wand_ecke")
    a = 0.105
    faces = [((0, -1, 0), lambda c, dn, z: Vector((c, -a + dn, z))), ((1, 0, 0), lambda c, dn, z: Vector((a - dn, c, z))),
             ((0, 1, 0), lambda c, dn, z: Vector((c, a - dn, z))), ((-1, 0, 0), lambda c, dn, z: Vector((-a + dn, c, z)))]
    def post_u(nrm, p):
        if nrm == (0, -1, 0):
            return UVS * p.x
        if nrm == (0, 1, 0):
            return -UVS * p.x
        if nrm == (1, 0, 0):
            return UVS * p.y
        return -UVS * p.y
    def keep(P, nrm):
        f = pc.face(P, 0, R_KEEP, nrm)
        for l in f.loops:
            p = l.vert.co
            l[pc.uv].uv = (post_u(nrm, p), UVS * p.z)
    m = JW + BC
    for nrm, pos in faces:
        nv = Vector(nrm)
        tv = tuple(pos(1, 0, 0) - pos(0, 0, 0))
        def band(d0, z0, d1, z1, want, reg):
            """Streifen rundum auf Gehrung: von Tiefe d0 (Hoehe z0) bis d1 (Hoehe z1)."""
            P = [pos(-a + d0, d0, z0), pos(a - d0, d0, z0), pos(a - d1, d1, z1), pos(-a + d1, d1, z1)]
            pc.face(P, 1, R_PLANAX, want, par=tv, reg=PLAN_REG.index(reg))
        for z0, z1 in ((0.0, 0.6 - m), (0.6 + m, TRENN - m)):
            keep([pos(-a, 0, z0), pos(a, 0, z0), pos(a, 0, z1), pos(-a, 0, z1)], nrm)
        band(0.0, 0.6 - m, BC, 0.6 - m + BC, nv + Vector((0, 0, 1)), "stein_kante")
        band(BC, 0.6 + m - BC, 0.0, 0.6 + m, nv + Vector((0, 0, -1)), "stein_kante")
        band(0.0, TRENN - m, BC, TRENN - m + BC, nv + Vector((0, 0, 1)), "stein_kante")
        band(BC, 0.6 - m + BC, BC, 0.6 + m - BC, nv, "kleber")
        band(BC, TRENN - m + BC, BC, TRENN, nv, "kleber")
        band(BC, TRENN, GD, TRENN, (0, 0, 1), "stein_kante")
        band(GD, TRENN, GD, GZ, nv, "gips")
        band(GD, GZ, 0.0, GZ, (0, 0, -1), "gips")
        keep([pos(-a, 0, GZ), pos(a, 0, GZ), pos(a, 0, H), pos(-a, 0, H)], nrm)
    pc.face([Vector((-a, -a, H)), Vector((a, -a, H)), Vector((a, a, H)), Vector((-a, a, H))], 0, R_TOP, (0, 0, 1))
    # Eckschutzwinkel aus Aluminium ueber dem Sockel bis zur Oberkante der Platten
    L, t = 0.022, 0.0015
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        xa, xb = sorted((sx * (a - L), sx * (a + t)))
        ya, yb = sorted((sy * a, sy * (a + t)))
        box_faces(pc, (xa, ya, PLH), (xb, yb, TRENN - 0.002), R_ALU, axis=(0, 0, 1))
        xa, xb = sorted((sx * a, sx * (a + t)))
        ya, yb = sorted((sy * (a - L), sy * a))
        box_faces(pc, (xa, ya, PLH), (xb, yb, TRENN - 0.002), R_ALU, axis=(0, 0, 1))
    z0r = REG["sockel"][0]
    sprof = SOCKEL_PROF
    s_ = [0.0]
    for i in range(1, len(sprof)):
        s_.append(s_[-1] + math.hypot(sprof[i][0] - sprof[i - 1][0], sprof[i][1] - sprof[i - 1][1]))
    sides = [((0, -1, 0), (-a, -a), (a, -a)), ((1, 0, 0), (a, -a), (a, a)), ((0, 1, 0), (a, a), (-a, a)), ((-1, 0, 0), (-a, a), (-a, -a))]
    for nrm, p0, p1 in sides:
        nv = Vector(nrm)
        t_ = Vector((p1[0] - p0[0], p1[1] - p0[1], 0)).normalized()
        for i in range(len(sprof) - 1):
            (d0, za), (d1, zb) = sprof[i], sprof[i + 1]
            A0 = Vector((p0[0], p0[1], 0)) + nv * d0 - t_ * d0
            A1 = Vector((p1[0], p1[1], 0)) + nv * d0 + t_ * d0
            B0 = Vector((p0[0], p0[1], 0)) + nv * d1 - t_ * d1
            B1 = Vector((p1[0], p1[1], 0)) + nv * d1 + t_ * d1
            P = [Vector((A0.x, A0.y, za)), Vector((A1.x, A1.y, za)), Vector((B1.x, B1.y, zb)), Vector((B0.x, B0.y, zb))]
            ua = [post_u(nrm, P[k]) for k in range(4)]
            uvs = [(ua[0], UVS * (z0r + 0.002 + s_[i])), (ua[1], UVS * (z0r + 0.002 + s_[i])),
                   (ua[2], UVS * (z0r + 0.002 + s_[i + 1])), (ua[3], UVS * (z0r + 0.002 + s_[i + 1]))]
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
    "lampe1": (1, -1, (-1.0, 3.0, 1.6), (-0.2, 0, 1.6), (-0.2, 0, 1.5)),
    "lampe2": (5, 1, (-1.2, 3.0, 1.45), (0.05, 0, 1.2), (0.1, 0, 1.1)),
    "lampe3": (2, 1, (-0.9, 3.0, 1.9), (0.35, 0, 1.9), (0.35, 0, 2.0)),
    "lampe4": (4, -1, (-1.4, 2.8, 1.5), (0.0, 0, 1.5), (0.05, 0, 1.4)),
    "nah1": (0, -1, (-0.95, 1.35, 1.75), (-1.25, 0, 1.8), (-1.25, 0, 1.8), 28),
    "nah2": (2, 1, (0.15, 1.05, 1.62), (0.48, 0, 1.55), (0.48, 0, 1.55), 30),
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

