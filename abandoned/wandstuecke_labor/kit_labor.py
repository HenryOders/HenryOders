# ABANDONED · Modulare Wandstuecke fuer das Gebaeude "labor"
# Sieben Stuecke, zwei kachelbare Materialien ("Wand", "Detail") mit je 4096 x 4096 px,
# UV-Massstab 0,25 je Meter (1024 px/m). Export als glTF 2.0 mit gemeinsamen Texturdateien.
# Start: blender -b -P kit_labor.py  (oder mit dem bpy-Modul: python kit_labor.py).
# Das Skript setzt Blender auf Werkseinstellungen zurueck, also nicht in einem offenen Projekt ausfuehren.
import bpy, bmesh, math, random, os, time, json, zlib
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, Quaternion, noise, geometry
from mathutils.bvhtree import BVHTree

T0 = time.time()
def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)

GEB = "labor"
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
TRENN = 1.2                    # Trennlinie: waagerechte Paneelfuge, verdeckt vom Kabeltrog
PANEL = 0.95                   # Paneelbreite: genau vier Paneele je Stueck
COLS = [-W2 + PANEL * k for k in range(5)]     # Fugenmitten -1,9 / -0,95 / 0 / 0,95 / 1,9
ROWS = [(0.0, TRENN), (TRENN, H)]
JW = 0.004                     # halbe Fugenbreite (Fuge 8 mm)
PT = 0.02                      # Paneele 2 cm tief gekantet
YR = T2 - PT                   # Rueckseite der Paneele = Vorderseite der Tragschienen
YC = T2 - 0.06                 # Betonoberflaeche hinter der Daemmung (Hohlraum 6 cm, Betonkern 8 cm)
RAMM_H, RAMM_D = 0.30, 0.025   # Rammschutz 30 cm hoch, 2,5 cm vor
EDGE = 0.4                     # Schaeden nie naeher an den Seitenkanten
KASTEN_W, KASTEN_H, KASTEN_T = 0.50, 0.40, 0.07   # Bedienfeld
BAND = 0.45                    # Hoehe der Baender fuer durchgehend abgebildete Flaechen (Beton, Daemmung)
JOINTS_TEX = [0.1, 1.05, 2.0, 2.95, 3.9]          # Fugen im Wandbild (stueckbezogen), 3,9..4,1 = Pfosten

# Detail-Atlas: waagerechte Bereiche (Hoehe in Metern), jeder kachelt in U
REG = {
    "beton": (0.00, 0.50), "wolle": (0.51, 1.06),
    "kabel_s": (1.07, 1.12), "kabel_g": (1.13, 1.18), "kabel_r": (1.19, 1.24), "kabel_b": (1.25, 1.30),
    "kabel_y": (1.31, 1.36),
    "stahl_24": (1.37, 1.62), "stahl_10": (1.63, 1.73), "stahl_07": (1.74, 1.81), "stahl_05": (1.82, 1.87),
    "stahl_03": (1.88, 1.91), "gummi": (1.92, 1.95), "warn": (1.96, 2.30), "trog": (2.31, 2.64),
    "rohr_a": (2.65, 2.86), "rohr_b": (2.87, 3.04), "panel": (3.05, 3.50), "blech": (3.51, 3.57),
    "schiene": (3.58, 3.63), "rot": (3.64, 3.78), "riss": (3.79, 3.89),
}
KABEL = ["kabel_s", "kabel_g", "kabel_r", "kabel_b", "kabel_y"]

# ======================= Texturen =======================
def drip_pad(M, length_m):
    """drip ohne Umlauf am oberen Rand (fuer Bereiche im Atlas)."""
    pad = int(length_m * NPX / 4.0) + 2
    P = np.concatenate([M, np.zeros((pad, M.shape[1]), M.dtype)], axis=0)
    return drip(P, length_m)[:M.shape[0]]

def lin(a, b, t):
    return a * (1 - t) + b * t

def pdist(X, c, period=4.0):
    """Abstand zu c auf einem Ring der Laenge period."""
    return np.abs(np.mod(X - c + period / 2, period) - period / 2)

def tex_wand():
    n = NPX
    X, Z = grid_xz()
    S = (n, n)
    rng = np.random.default_rng(91)
    # ---- Paneele: Fugen stueckbezogen bei 0,1 / 1,05 / 2,0 / 2,95 / 3,9 m, 3,9..4,1 ist der Pfosten ----
    dj = np.full(S, 9.0, np.float32)
    for j in JOINTS_TEX:
        dj = np.minimum(dj, pdist(X, j))
    pidx = np.zeros(S, np.int32)
    for j in JOINTS_TEX[1:-1]:
        pidx += (X >= j).astype(np.int32)
    pidx = np.where((X < 0.1) | (X >= 3.9), 4, pidx)
    row = (Z >= TRENN).astype(np.int32)
    tone = rng.normal(0, 0.025, (2, 5)).astype(np.float32)[row, pidx]
    peel = fr(S, 0.25, 101, sigma_m=0.0006)
    cloud = fr(S, 1.5, 102)
    base = hexc("#b5b9b9") * (1 + tone + 0.025 * cloud)[..., None]
    base = np.where((Z < TRENN)[..., None], base * hexc("#e8eaea"), base)
    scr = sm(2.2, 2.9, fr(S, 0.5, 103, aniso=0.06)) * (0.4 + 0.6 * sm(0.2, 1.4, fr(S, 1.0, 104)))
    base = mix(base, hexc("#d4d7d6"), 0.35 * scr)
    scuff = sm(1.6, 2.5, fr(S, 0.7, 105, aniso=0.12)) * sm(0.3, 0.45, Z) * sm(1.1, 0.9, Z)
    base = mix(base, hexc("#5a5d5c"), 0.45 * scuff)
    # ---- Schraubenkoepfe: 2,5 cm neben jeder Fuge, im Pfostenbereich mittig ----
    cols = np.array([0.125, 1.025, 1.075, 1.975, 2.025, 2.925, 2.975, 3.875], np.float32)
    rows = np.array([0.42, 0.72, 1.02, 1.42, 1.77, 2.12, 2.47, 2.82, 3.17], np.float32)
    dxs = np.full(S, 9.0, np.float32)
    cxi = np.zeros(S, np.int32)
    for i, c in enumerate(cols):
        d = pdist(X, c)
        cxi = np.where(d < dxs, i, cxi)
        dxs = np.minimum(dxs, d)
    dzs = np.full(S, 9.0, np.float32)
    rzi = np.zeros(S, np.int32)
    for i, r in enumerate(rows):
        d = np.abs(Z - r)
        rzi = np.where(d < dzs, i, rzi)
        dzs = np.minimum(dzs, d)
    lx = np.mod(X - cols[cxi] + 2, 4) - 2
    lz = Z - rows[rzi]
    pl = np.mod(X + 2, 4) - 2
    prow = np.clip(np.round((Z - 0.45) / 0.3), 0, 9)
    plz = Z - (0.45 + 0.3 * prow)
    use_post = np.hypot(pl, plz) < np.hypot(lx, lz)
    lx = np.where(use_post, pl, lx)
    lz = np.where(use_post, plz, lz)
    sid = np.where(use_post, 100 + prow.astype(np.int32), cxi * 10 + rzi).astype(np.float32)
    ang = np.mod(sid * 2.39996, math.pi)
    ca, sa = np.cos(ang), np.sin(ang)
    rx_, rz_ = lx * ca + lz * sa, -lx * sa + lz * ca
    rr = np.hypot(lx, lz)
    head = rr < 0.0045
    dome = np.sqrt(np.clip(1 - (rr / 0.0045) ** 2, 0, 1))
    slot = head & (((np.abs(rx_) < 0.0005) & (np.abs(rz_) < 0.0026)) | ((np.abs(rz_) < 0.0005) & (np.abs(rx_) < 0.0026)))
    rusty = np.mod(np.sin(sid * 12.9898) * 43758.5453, 1.0) < 0.35
    ssrc = sm(0.009, 0.004, rr) * rusty
    # ---- Rostraender an den Fugen (senkrecht, an der Trennfuge, oben und unten), Rostlaeufer ----
    jr = sm(0.022, 0.004, dj) * sm(0.3, 1.5, fr(S, 0.9, 106) + 0.6 * fr(S, 0.4, 107))
    hz = np.minimum(np.abs(Z - TRENN), np.minimum(np.abs(Z - H), Z))
    jr = np.maximum(jr, sm(0.02, 0.004, hz) * sm(0.4, 1.6, fr(S, 0.9, 108)))
    jrun = drip(jr * 0.7, 0.4) * (0.4 + 0.6 * sm(-0.5, 1.5, fr(S, 0.6, 109, aniso=6.0)))
    rust = np.clip(np.maximum(jr, jrun) + 0.9 * np.maximum(ssrc, drip(ssrc * 0.8, 0.3)), 0, 1)
    # ---- Kondenswasser: Tropfen in Zonen (oben, an den Fugen) und Laufspuren ----
    zone = np.clip(sm(0.0, 1.2, fr(S, 1.3, 110) + 1.2 * sm(2.0, 3.3, Z) + 0.8 * sm(0.03, 0.0, dj)), 0, 1)
    dots = fr(S, 0.1, 111, sigma_m=0.0012)
    drop = sm(1.6, 2.1, dots) * zone
    trail = np.clip(drip(sm(2.1, 2.4, dots) * zone, 0.6), 0, 1) * (0.5 + 0.5 * sm(-0.5, 1.5, fr(S, 0.5, 112, aniso=8.0)))
    # ---- dunkle Schlieren von oben und von den Fugen ----
    ssrc2 = sm(1.5, 2.5, fr(S, 1.0, 113, aniso=10.0)) * sm(3.0, 3.38, Z) * sm(3.42, 3.38, Z)
    smear = np.clip(drip(ssrc2, 1.8) * (0.5 + 0.5 * sm(-0.5, 1.2, fr(S, 0.9, 114))), 0, 1)
    smear = np.maximum(smear, 0.6 * drip(sm(0.012, 0.0, dj) * sm(1.0, 2.0, fr(S, 1.0, 115)), 1.0))
    a = base * (1 - 0.35 * smear)[..., None]
    rustc = mix(hexc("#6e4a33"), hexc("#946546"), sm(-1.0, 1.5, fr(S, 0.6, 116)))
    a = mix(a, rustc, 0.75 * rust)
    a = a * (1 - 0.12 * drop - 0.08 * trail)[..., None]
    scol = mix(hexc("#8f9394"), hexc("#6a4632"), 0.8 * rusty)
    a = np.where(head[..., None], scol * (0.85 + 0.15 * dome)[..., None], a)
    a = np.where(slot[..., None], hexc("#2a2b2b"), a)
    h = 0.00004 * peel + 0.00003 * cloud - 0.00006 * scr + 0.0003 * drop
    h = np.where(head, 0.0008 * dome, h) - 0.0005 * slot
    rough = np.clip(0.45 + 0.08 * scr + 0.12 * scuff + 0.3 * rust + 0.1 * smear, 0, 1)
    rough = lin(rough, 0.06, np.clip(drop + 0.6 * trail, 0, 1))
    rough = np.where(head, np.where(rusty, 0.7, 0.35), rough)
    metal = np.where(head & ~rusty, 1.0, 0.0).astype(np.float32)
    return write_set(f"T_{GEB}_Wand", a, h, rough, metal)

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
    seed = [500]
    def nz(shape, beta, aniso=1.0, sigma_m=0.0):
        seed[0] += 1
        return fr(shape, beta, seed[0], aniso, sigma_m)
    # ---- Beton hinter der Verkleidung, Bruchflaechen ----
    sl, X, Z, S, hh = region("beton")
    c = hexc("#8a8781") * (0.92 + 0.05 * nz(S, 1.2)[..., None] + 0.04 * nz(S, 0.4)[..., None])
    pores = sm(2.0, 2.7, nz(S, 0.15, sigma_m=0.0012))
    damp = sm(0.2, 2.0, nz(S, 1.4))
    agg = sm(1.2, 1.6, nz(S, 0.3, sigma_m=0.002))
    c = mix(c, hexc("#a29d93"), 0.4 * agg)
    alb[sl] = c * (1 - 0.45 * pores - 0.2 * damp)[..., None]
    hgt[sl] = 0.0004 * nz(S, 0.6) - 0.0015 * pores + 0.0006 * agg
    rgh[sl] = 0.9 - 0.15 * damp
    # ---- Daemmwolle (Glaswolle) ----
    sl, X, Z, S, hh = region("wolle")
    f1, f2, f3 = nz(S, 0.55, aniso=0.25), nz(S, 0.55, aniso=4.0), nz(S, 1.2)
    f4 = nz(S, 0.25, sigma_m=0.0008)
    fib = 0.45 * f1 + 0.45 * f2 + 0.3 * f4
    w = mix(hexc("#978658"), hexc("#c7b98f"), sm(-1.2, 1.4, fib))
    w = w * (0.82 + 0.14 * sm(-1.0, 1.5, f3))[..., None]
    alb[sl] = mix(w, hexc("#6b6047"), 0.45 * sm(0.6, 2.2, nz(S, 1.3)))
    hgt[sl] = 0.003 * f3 + 0.0012 * fib
    rgh[sl] = 0.96
    # ---- Kabelmaentel ----
    for name, col in (("kabel_s", "#1e1f20"), ("kabel_g", "#6c7073"), ("kabel_r", "#8c2b25"), ("kabel_b", "#2b4a78"), ("kabel_y", "#b39a2c")):
        sl, X, Z, S, hh = region(name)
        dust = sm(0.6, 2.0, nz(S, 1.2))
        alb[sl] = mix(hexc(col) * (0.9 + 0.08 * nz(S, 1.0)[..., None]), hexc("#77746c"), 0.3 * dust)
        hgt[sl] = 0.0001 * nz(S, 0.4)
        rgh[sl] = 0.42 + 0.3 * dust
    # ---- gebuersteter Edelstahl (Zarge, Fensterrahmen, Schellen) ----
    for name in ("stahl_24", "stahl_10", "stahl_07", "stahl_05", "stahl_03"):
        sl, X, Z, S, hh = region(name)
        br = nz(S, 0.35, aniso=0.02)
        br2 = nz(S, 0.15, aniso=0.01, sigma_m=0.0003)
        smudge = sm(1.0, 2.4, nz(S, 1.2))
        spots = sm(1.9, 2.5, nz(S, 0.15, sigma_m=0.0012)) * sm(0.0, 1.0, nz(S, 1.3))
        b = hexc("#bfc2c4") * (0.88 + 0.04 * br[..., None] + 0.09 * br2[..., None])
        b = mix(b, hexc("#8f9294"), 0.15 * smudge)
        alb[sl] = mix(b, hexc("#8a6a52"), 0.12 * spots)
        hgt[sl] = 0.00008 * br2
        rgh[sl] = np.clip(0.48 + 0.04 * br + 0.07 * br2 + 0.08 * smudge + 0.15 * spots, 0, 1)
        met[sl] = 1.0 - 0.3 * spots
    # ---- Gummidichtung ----
    sl, X, Z, S, hh = region("gummi")
    crk = sm(2.2, 2.7, nz(S, 0.3, aniso=0.3))
    alb[sl] = mix(hexc("#1b1c1d") * (0.9 + 0.1 * nz(S, 0.8)[..., None]), hexc("#4d4c48"), 0.4 * sm(0.8, 2.0, nz(S, 1.2)))
    hgt[sl] = -0.0004 * crk
    rgh[sl] = 0.82
    # ---- Rammschutz: gelb-schwarz unter 45 Grad, Periode 20 cm, abgestossen ----
    sl, X, Z, S, hh = region("warn")
    yel = np.mod((X + Z) / 0.2, 1.0) < 0.5
    col = np.where(yel[..., None], hexc("#cf9f22"), hexc("#1f1f1d")) * (0.88 + 0.1 * nz(S, 1.2)[..., None])
    chip = np.clip(sm(1.7, 2.3, nz(S, 0.4)) + sm(0.27, 0.31, Z) * sm(1.2, 1.9, nz(S, 0.5)), 0, 1)
    scr = sm(2.0, 2.8, nz(S, 0.5, aniso=0.08))
    dirt = np.clip(sm(0.06, 0.0, Z) + 0.5 * sm(0.4, 2.2, nz(S, 1.3)), 0, 1)
    col = mix(col, hexc("#7c7f80"), chip)
    col = mix(col, hexc("#9a9d9e"), 0.5 * scr)
    col = mix(col, hexc("#4a4741"), 0.5 * dirt)
    alb[sl] = mix(col, hexc("#6e4630"), 0.6 * sm(0.5, 1.0, chip) * sm(0.0, 1.5, nz(S, 0.8)))
    hgt[sl] = -0.0003 * chip - 0.00008 * scr
    rgh[sl] = np.clip(0.5 + 0.25 * dirt + 0.2 * chip, 0, 1)
    # ---- Kabeltrog: verzinkt, Lochung in den Boeden ----
    sl, X, Z, S, hh = region("trog")
    spang = nz(S, 0.6, sigma_m=0.004)
    gz = hexc("#a3a8a8") * (0.9 + 0.07 * spang[..., None] + 0.03 * nz(S, 0.3)[..., None])
    s_ = Z - 0.002
    bottom = ((s_ > 0.008) & (s_ < 0.082)) | ((s_ > 0.236) & (s_ < 0.31))
    hole = bottom & (np.hypot(np.mod(X, 0.025) - 0.0125, np.mod(s_, 0.02) - 0.01) < 0.0035)
    rustt = sm(1.5, 2.3, nz(S, 0.9))
    drops = sm(2.2, 2.6, nz(S, 0.1, sigma_m=0.0012))
    t = mix(gz, hexc("#6f5039"), 0.6 * rustt)
    alb[sl] = np.where(hole[..., None], hexc("#121212"), t)
    hgt[sl] = -0.0015 * hole + 0.0002 * drops
    rgh[sl] = np.clip(0.62 + 0.08 * spang + 0.25 * rustt - 0.3 * drops, 0.05, 1)
    met[sl] = np.where(hole, 0.0, 0.75 - 0.6 * rustt)
    # ---- zwei Rohre: grau, farbige Kennzeichnung alle 1 m (Band + Pfeil nach vorn), Kondenswasser ----
    for name, band_col, r in (("rohr_a", "#2e7a4e", 0.03), ("rohr_b", "#d1a62b", 0.024)):
        sl, X, Z, S, hh = region(name)
        p = hexc("#8b9091") * (0.9 + 0.07 * nz(S, 1.2)[..., None])
        band = np.abs(np.mod(X - 0.5 + 0.5, 1.0) - 0.5) < 0.05
        ax = np.mod(X - 0.5, 1.0)
        zc = 0.002 + 6 * 2 * r * math.sin(math.pi / 12)
        arrow = ((ax > 0.08) & (ax < 0.17) & (np.abs(Z - zc) < 0.008)) | \
                ((ax >= 0.17) & (ax < 0.21) & (np.abs(Z - zc) < 0.018 * (1 - (ax - 0.17) / 0.04)))
        p = np.where(band[..., None], hexc(band_col) * (0.9 + 0.08 * nz(S, 1.0)[..., None]), p)
        p = np.where(arrow[..., None], hexc("#d9d9d2"), p)
        rustp = sm(1.4, 2.2, nz(S, 1.0))
        drops = sm(1.7, 2.2, nz(S, 0.1, sigma_m=0.0012))
        p = mix(p, hexc("#6d4a33"), 0.6 * rustp)
        alb[sl] = p * (1 - 0.1 * drops)[..., None]
        hgt[sl] = 0.0003 * drops - 0.0002 * rustp
        rgh[sl] = lin(np.clip(0.45 + 0.35 * rustp, 0, 1), 0.06, drops)
    # ---- Bedienfeld: Gehaeuse dunkelgrau, Vorderseite einmalig bei U 0,5 ----
    sl, X, Z, S, hh = region("panel")
    dirt = sm(0.5, 2.2, nz(S, 1.2))
    a = mix(hexc("#3b3f42") * (0.9 + 0.07 * nz(S, 1.3)[..., None]), hexc("#2a2c2d"), 0.3 * dirt)
    h_ = 0.00003 * nz(S, 0.3)
    r_ = 0.5 + 0.15 * dirt
    W, HH = KASTEN_W, KASTEN_H
    px, pz = X - 2.0, Z - 0.005
    inside = (px >= 0) & (px < W) & (pz >= 0) & (pz < HH)
    screen = inside & (px > 0.04) & (px < 0.30) & (pz > 0.17) & (pz < 0.37)
    bezel = inside & (px > 0.03) & (px < 0.31) & (pz > 0.16) & (pz < 0.38) & ~screen
    kx, kz = (px - 0.05) / 0.022, (pz - 0.025) / 0.022
    key = inside & (kx >= 0) & (kx < 3) & (kz >= 0) & (kz < 4) & (np.mod(kx, 1.0) < 0.82) & (np.mod(kz, 1.0) < 0.82)
    led_r = inside & (np.hypot(px - 0.36, pz - 0.36) < 0.003)
    led_g = inside & (np.hypot(px - 0.39, pz - 0.36) < 0.003)
    led_y = inside & (np.hypot(px - 0.42, pz - 0.36) < 0.003)
    label = inside & (px > 0.18) & (px < 0.30) & (pz > 0.05) & (pz < 0.09)
    plate = inside & (np.hypot(px - 0.43, pz - 0.085) < 0.032)
    btn_g = inside & (np.abs(px - 0.355) < 0.013) & (np.abs(pz - 0.30) < 0.013)
    btn_r = inside & (np.abs(px - 0.425) < 0.013) & (np.abs(pz - 0.30) < 0.013)
    btn_w = inside & (np.abs(px - 0.39) < 0.048) & (np.abs(pz - 0.23) < 0.013) & (np.abs(np.mod(px - 0.342, 0.035) - 0.0175) < 0.013)
    smudge = sm(0.4, 1.8, nz(S, 1.1))
    fp = mix(hexc("#43474a"), hexc("#2c2e30"), 0.35 * dirt)
    fp = np.where(bezel[..., None], hexc("#1c1e20"), fp)
    fp = np.where(screen[..., None], mix(hexc("#07090b"), hexc("#262a2d"), 0.35 * smudge), fp)
    fp = np.where(key[..., None], hexc("#7b7f82") * (0.9 + 0.1 * smudge[..., None]), fp)
    fp = np.where(label[..., None], hexc("#b7b5ad"), fp)
    fp = np.where(plate[..., None], hexc("#c79a24"), fp)
    fp = np.where((inside & (np.hypot(px - 0.43, pz - 0.085) < 0.0205))[..., None], hexc("#8e1f1a"), fp)
    fp = np.where(btn_g[..., None], hexc("#2f6b3a"), fp)
    fp = np.where(btn_r[..., None], hexc("#7a2521"), fp)
    fp = np.where(btn_w[..., None], hexc("#8e9192"), fp)
    fp = np.where(led_r[..., None], hexc("#4a1512"), fp)
    fp = np.where(led_g[..., None], hexc("#15381c"), fp)
    fp = np.where(led_y[..., None], hexc("#4d3a12"), fp)
    a = np.where(inside[..., None], fp, a)
    h_ = np.where(inside, 0.0004 * label + 0.0002 * key - 0.0003 * bezel, h_)
    r_ = np.where(inside, np.where(screen, 0.06 + 0.3 * smudge, np.where(key | label, 0.5, 0.45 + 0.2 * dirt)), r_)
    alb[sl], hgt[sl], rgh[sl] = a, h_, r_
    # ---- Kanten der Paneele (gekantetes Blech) ----
    sl, X, Z, S, hh = region("blech")
    ru = sm(1.0, 2.0, nz(S, 0.9))
    alb[sl] = mix(hexc("#adb1b1") * (0.9 + 0.07 * nz(S, 1.2)[..., None]), hexc("#6f4b33"), 0.6 * ru)
    hgt[sl] = -0.0002 * ru
    rgh[sl] = 0.5 + 0.3 * ru
    # ---- Tragschienen (verzinkt, dunkel) ----
    sl, X, Z, S, hh = region("schiene")
    ru = sm(1.2, 2.2, nz(S, 0.9))
    alb[sl] = mix(hexc("#6a6e6f") * (0.9 + 0.08 * nz(S, 1.0)[..., None]), hexc("#5e4433"), 0.6 * ru)
    rgh[sl] = 0.55 + 0.3 * ru
    met[sl] = 0.8 * (1 - ru)
    # ---- roter Kunststoff (Not-Aus) ----
    sl, X, Z, S, hh = region("rot")
    alb[sl] = hexc("#8e1f1a") * (0.88 + 0.1 * nz(S, 1.0)[..., None])
    rgh[sl] = 0.35 + 0.2 * sm(0.5, 2.0, nz(S, 1.2))
    # ---- Rissflanken im Beton ----
    sl, X, Z, S, hh = region("riss")
    q = nz(S, 0.9)
    alb[sl] = mix(hexc("#2b2a27"), hexc("#625f59"), sm(-0.8, 1.6, q)) * (0.85 + 0.15 * nz(S, 0.4)[..., None])
    hgt[sl] = 0.002 * q
    rgh[sl] = 0.93
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
R_KEEP, R_WM, R_WP, R_TOP, R_ENDX, R_REVX, R_REVZ, R_PLAN, R_METAL, R_BAND, R_BOXFRONT, R_SHARD, R_PLANAX, R_PLANFIX = range(14)
PLAN_REG = list(REG.keys())

def wall_u(x, side):
    """Stueckbezogen: auf beiden Seiten liegt x = -1,9 / -0,95 / 0 / 0,95 / 1,9 bei 0,1 / 1,05 / 2,0 / 2,95 / 3,9 m
    im Wandbild. So sitzen Schrauben und Rostraender genau an den echten Fugen, in jeder Drehung des Stuecks."""
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
        if reg_name == "panel":
            uoff = pc.rng.random() * 0.2
    for l, c in zip(f.loops, co):
        l[pc.uv].uv = (uoff + UVS * c[0], UVS * (off + c[1] - vmin))

def metal_region(ext):
    for name, hgt in (("stahl_03", 0.03), ("stahl_05", 0.05), ("stahl_07", 0.07), ("stahl_10", 0.10), ("stahl_24", 0.25)):
        if ext <= hgt - 0.004:
            return name
    raise RuntimeError(f"Stahlflaeche {ext:.3f} m zu breit")

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
            # Stirnseiten: in einen Bereich des Wandbilds ohne Fugen und Schrauben (1,1 .. 1,9 m)
            s = 1 if f.normal.x > 0 else -1
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (0.375 + s * UVS * p.y, UVS * p.z)
        elif r == R_REVX:
            s = 1 if f.normal.x > 0 else -1
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (0.375 + s * UVS * p.y, UVS * p.z)
        elif r == R_REVZ:
            zref = f[pc.par][0]
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (wall_u(p.x, -1), UVS * (zref + 0.02 + (p.y + T2)))
        elif r == R_BAND:
            # durchgehend abgebildete Flaeche parallel zur Wand (Beton, Daemmung): Band ab zb im Bereich reg
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
                l[uv].uv = (0.5 + UVS * du, UVS * (REG["panel"][0] + 0.005 + (p.z - bz0)))
        elif r == R_PLAN:
            co = planar_coords(f)
            place_in_region(pc, f, co, PLAN_REG[f[pc.reg]])
        elif r == R_PLANAX:
            co = planar_coords(f, Vector(f[pc.par]))
            place_in_region(pc, f, co, PLAN_REG[f[pc.reg]], center=True)
        elif r == R_PLANFIX:
            co = planar_coords(f, Vector((0, 1, 0)))
            place_in_region(pc, f, co, PLAN_REG[f[pc.reg]], uoff=f[pc.par][0], center=True)
        elif r == R_METAL:
            ax = Vector(f[pc.par]) if Vector(f[pc.par]).length > 0 else None
            co = planar_coords(f, ax)
            ext = max(c[1] for c in co) - min(c[1] for c in co)
            ext2 = max(c[0] for c in co) - min(c[0] for c in co)
            if ext > ext2 and ax is None:
                co = [(c[1], -c[0]) for c in co]
                ext = ext2
            place_in_region(pc, f, co, metal_region(ext), center=True)
        elif r == R_SHARD:
            # Bruchstueck eines Paneels: Oberseite aus dem Wandbild (obere Paneele, abseits der Fugen)
            co = planar_coords(f)
            umin = min(c[0] for c in co)
            vmin = min(c[1] for c in co)
            u0 = 0.3 + 0.1 * pc.rng.random()
            vz = 1.5 + pc.rng.random() * 1.5
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
            if prof[0][0] != 0:
                P = [Vector((x, yy(0), prof[0][1]))] + P
            if prof[-1][0] != 0:
                P = P + [Vector((x, yy(0), prof[-1][1]))]
            pc.face(P, 1, R_PLANFIX, (sgn, 0, 0), reg=PLAN_REG.index(reg), par=(0.37 if side > 0 else 0.13, 0, 0))

def chunk(pc, center, size, seed, reg="beton", subdiv=1):
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
    """Splitter: Oberseite aus dem Wand-Material (Paneel), Kanten Bruch."""
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
    pc.face(bot[::-1], 1, R_PLAN, (0, 0, -1), reg=PLAN_REG.index("beton"))
    c = sum(top, Vector()) / len(top)
    for i in range(len(P)):
        j = (i + 1) % len(P)
        Q = [bot[i], bot[j], top[j], top[i]]
        mid = (bot[i] + top[j]) / 2
        pc.face(Q, 1, R_PLAN, mid - c, reg=PLAN_REG.index("beton"))

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

# ---------- Bausteine Labor ----------
RAMM_PROF = [(RAMM_D, 0.0), (RAMM_D, RAMM_H - 0.012), (RAMM_D - 0.012, RAMM_H), (0.0, RAMM_H)]
TROG_PROF = [(0.0, 1.17), (0.09, 1.17), (0.09, 1.24), (0.088, 1.24), (0.088, 1.172), (0.0, 1.172)]
TROG_KABEL = [(0.020, 0.0075, "kabel_s"), (0.037, 0.006, "kabel_g"), (0.052, 0.007, "kabel_b"), (0.068, 0.0055, "kabel_r")]

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
    return [(a, b) for a, b in spans if b - a > 0.02]

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

def shell(pc):
    """Oberseite und Stirnseiten des Grundkoerpers."""
    pc.face([Vector((-W2, -T2, H)), Vector((W2, -T2, H)), Vector((W2, T2, H)), Vector((-W2, T2, H))], 0, R_TOP, (0, 0, 1))
    for x, sg in ((-W2, -1), (W2, 1)):
        pc.face([Vector((x, -T2, 0)), Vector((x, T2, 0)), Vector((x, T2, H)), Vector((x, -T2, H))], 0, R_ENDX, (sg, 0, 0))

def strips(pc, side, ramm_spans, trog_spans):
    """Rammschutz unten und Kabeltrog auf 1,2 m mit vier Kabeln und Konsolen."""
    for a, b in ramm_spans:
        profile_strip(pc, RAMM_PROF, a, b, side, "warn")
    for a, b in trog_spans:
        profile_strip(pc, TROG_PROF, a, b, side, "trog")
        for k, (d, r, reg) in enumerate(TROG_KABEL):
            y, z = side * (T2 + d), 1.172 + r
            tube(pc, [(a, y, z), (b, y, z)], r, reg, seg=6, caps=False, uoff=0.1 * k + UVS * (a + W2))
        for xb in (-1.425, -0.475, 0.475, 1.425):
            if a + 0.03 < xb < b - 0.03:
                ys = sorted((side * T2, side * (T2 + 0.088)))
                drop_back(pc, box_faces(pc, (xb - 0.012, ys[0], 1.128), (xb + 0.012, ys[1], 1.17), R_PLANAX,
                                        reg=PLAN_REG.index("schiene"), axis=(0, 1, 0)), side)

def rect_minus(r, o):
    x0, x1, z0, z1 = r
    ox0, ox1, oz0, oz1 = o
    if ox1 <= x0 or ox0 >= x1 or oz1 <= z0 or oz0 >= z1:
        return [r]
    parts = []
    if oz0 > z0:
        parts.append((x0, x1, z0, oz0))
    if oz1 < z1:
        parts.append((x0, x1, oz1, z1))
    zl, zh = max(z0, oz0), min(z1, oz1)
    if ox0 > x0:
        parts.append((x0, ox0, zl, zh))
    if ox1 < x1:
        parts.append((ox1, x1, zl, zh))
    return [p for p in parts if p[1] - p[0] > 0.02 and p[3] - p[2] > 0.02]

def panel_cells(opening=None):
    """Rasterzellen (Spalte, Reihe, Rechteck); eine Oeffnung schneidet sie zurecht."""
    cells = []
    for ci in range(4):
        for ri, (z0, z1) in enumerate(ROWS):
            r = (COLS[ci], COLS[ci + 1], z0, z1)
            for p in ([r] if opening is None else rect_minus(r, opening)):
                cells.append((ci, ri, p))
    return cells

def inset(cell):
    """Paneelflaeche: halbe Fuge an jeder Kante, unten am Boden buendig."""
    x0, x1, z0, z1 = cell
    return x0 + JW, x1 - JW, z0 + (JW if z0 > 1e-6 else 0.0), z1 - JW

def returns(pc, s, corners, T):
    """Kantungen: von der Vorderkante 2 cm nach hinten; T bildet (x, y, z) in den Raum ab."""
    n = len(corners)
    cen = sum((T(x, s * T2, z) for x, z in corners), Vector()) / n
    for i in range(n):
        (xa, za), (xb, zb) = corners[i], corners[(i + 1) % n]
        P = [T(xa, s * T2, za), T(xb, s * T2, zb), T(xb, s * YR, zb), T(xa, s * YR, za)]
        e = P[1] - P[0]
        pc.face(P, 1, R_PLANAX, (P[0] + P[1]) / 2 - cen, reg=PLAN_REG.index("blech"), par=(e.x, e.y, e.z))

def panel(pc, side, x0, x1, z0, z1, dents=()):
    """Paneel: Vorderseite mit dem Wandbild auf |y| = 0,1, Kantungen; Dellen als Geometrie."""
    s = side
    rule = R_WM if s < 0 else R_WP
    if not dents:
        pc.face([Vector((x0, s * T2, z0)), Vector((x1, s * T2, z0)), Vector((x1, s * T2, z1)), Vector((x0, s * T2, z1))], 0, rule, (0, s, 0))
    else:
        rings = [dent(pc, s, x0, x1, z0, z1, d) for d in dents]
        pc.tess(rect(x0, x1, z0, z1), rings, s * T2, 0, rule, (0, s, 0))
    returns(pc, s, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], lambda x, y, z: Vector((x, y, z)))

def dent(pc, s, x0, x1, z0, z1, d, n=8):
    """Delle: feines Feld mit gemeinsamen Punkten (glatt), weich eingedrueckt, mit einer Knickfalte."""
    cx, cz, R, D, ang, seed = d
    qx0, qx1 = max(x0 + 0.02, cx - R), min(x1 - 0.02, cx + R)
    qz0, qz1 = max(z0 + 0.02, cz - R), min(z1 - 0.02, cz + R)
    gx = [qx0 + (qx1 - qx0) * i / n for i in range(n + 1)]
    gz = [qz0 + (qz1 - qz0) * j / n for j in range(n + 1)]
    ca, sa = math.cos(ang), math.sin(ang)
    V = [[None] * (n + 1) for _ in range(n + 1)]
    for i, x in enumerate(gx):
        for j, z in enumerate(gz):
            dep = 0.0
            if 0 < i < n and 0 < j < n:
                u, v = (x - cx) / R, (z - cz) / (R * 0.8)
                rr = u * u + v * v
                if rr < 1:
                    fold = max(0.0, 1 - abs(-sa * (x - cx) + ca * (z - cz)) / (0.12 * R))
                    dep = D * (1 - rr) ** 2 * (1 + 0.25 * noise.noise(Vector((x * 9, z * 9, seed))) + 0.6 * fold)
            V[i][j] = pc.bm.verts.new((x, s * (T2 - min(dep, 0.018)), z))
    rule = R_WM if s < 0 else R_WP
    for i in range(n):
        for j in range(n):
            f = pc.bm.faces.new((V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]))
            pc.mark([f], 0, rule, smooth=True)
            f.normal_update()
            if f.normal.y * s < 0:
                f.normal_flip()
    return [(gx[i], gz[0]) for i in range(n)] + [(gx[n], gz[j]) for j in range(n)] + \
           [(gx[n - i], gz[n]) for i in range(n)] + [(gx[0], gz[n - j]) for j in range(n)]

def hanging_panel(pc, side, x0, x1, z0, z1, fl, fr_, drop=0.012, nu=3, nv=6):
    """Oben losgerissenes Paneel: unten noch fest, oben nach vorn gekippt und verdreht (Blech biegt sich mit)."""
    s = side
    def T(x, y, z):
        u_, v_ = (x - x0) / (x1 - x0), (z - z0) / (z1 - z0)
        fwd = v_ * ((1 - u_) * fl + u_ * fr_)
        return Vector((x, y + s * fwd, z - drop * v_ * v_))
    gx = [x0 + (x1 - x0) * i / nu for i in range(nu + 1)]
    gz = [z0 + (z1 - z0) * j / nv for j in range(nv + 1)]
    V = [[pc.bm.verts.new(T(x, s * T2, z)) for z in gz] for x in gx]
    for i in range(nu):
        for j in range(nv):
            f = pc.bm.faces.new((V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]))
            pc.mark([f], 0, R_KEEP, smooth=True)
            corners = [(gx[i], gz[j]), (gx[i + 1], gz[j]), (gx[i + 1], gz[j + 1]), (gx[i], gz[j + 1])]
            for l, (x, z) in zip(f.loops, corners):
                l[pc.uv].uv = (wall_u(x, s), UVS * z)
            f.normal_update()
            if f.normal.y * s < 0:
                f.normal_flip()
    returns(pc, s, [(x0, z0), (x1, z0), (x1, z1), (x0, z1)], T)

def banded_surface(pc, outer, holes, y, side, reg, band=BAND, mat=1):
    """Ebene Flaeche parallel zur Wand (Polygon mit Loechern), in waagerechte Baender zerlegt:
    jedes Band wird durchgehend abgebildet (R_BAND), Loecher duerfen ueber den Rand hinausgehen."""
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
        cx, cz = sum(p.x for p in p2) / len(p2), sum(p.y for p in p2) / len(p2)
        if not point_in(outer, cx, cz) or any(point_in(h, cx, cz) for h in holes):
            continue
        if abs((p2[1] - p2[0]).cross(p2[2] - p2[0])) < 2e-9:
            continue
        zb = za + math.floor((cz - za) / band) * band
        pc.face([Vector((p.x, y, p.y)) for p in p2], mat, R_BAND, (0, side, 0), reg=PLAN_REG.index(reg), par=(side, zb, 0))

def crack_at(pc, pts, widths, side, yface, depth, reg="riss"):
    """Riss als V-Nut in einer Flaeche bei |y| = yface. Gibt das Oeffnungs-Polygon zurueck."""
    L, Rr = [], []
    for i, p in enumerate(pts):
        if i == 0:
            d = Vector((pts[1][0] - p[0], pts[1][1] - p[1]))
        elif i == len(pts) - 1:
            d = Vector((p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]))
        else:
            d = Vector((pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]))
        d.normalize()
        w = widths[i] / 2
        L.append((p[0] - d.y * w, p[1] + d.x * w))
        Rr.append((p[0] + d.y * w, p[1] - d.x * w))
    yf, yb = side * yface, side * (yface - depth)
    B = [Vector((p[0], yb, p[1])) for p in pts]
    for i in range(len(pts) - 1):
        for edge in (L, Rr):
            a, b = edge[i], edge[i + 1]
            P = [Vector((a[0], yf, a[1])), Vector((b[0], yf, b[1])), B[i + 1], B[i]]
            mid = Vector(((a[0] + b[0]) / 2 - (pts[i][0] + pts[i + 1][0]) / 2, 0, (a[1] + b[1]) / 2 - (pts[i][1] + pts[i + 1][1]) / 2))
            pc.face(P, 1, R_PLANAX, -mid + Vector((0, side * 0.0001, 0)), reg=PLAN_REG.index(reg),
                    par=(pts[i + 1][0] - pts[i][0], 0.0, pts[i + 1][1] - pts[i][1]))
    for i, k in ((0, 1), (len(pts) - 1, len(pts) - 2)):
        P = [Vector((L[i][0], yf, L[i][1])), Vector((Rr[i][0], yf, Rr[i][1])), B[i]]
        pc.face(P, 1, R_PLAN, -Vector((pts[i][0] - pts[k][0], 0, pts[i][1] - pts[k][1])) + Vector((0, side * 0.0001, 0)),
                reg=PLAN_REG.index(reg))
    return L + Rr[::-1]

def batt(pc, s, x0, x1, z0, z1, state, rng):
    """Daemmplatte im Hohlraum; 'riss' = oben ausgerissen. Vorderseite durchgehend abgebildet."""
    yb = s * YC
    if state == "riss":
        top = [(x0 + (x1 - x0) * i / 8, z1 - rng.uniform(0.04, 0.17)) for i in range(9)]
        poly = [(x0, z0), (x1, z0)] + top[::-1]
        yf = s * (YR + 0.004)
        pc.tess(poly, [], yf, 1, R_BAND, (0, s, 0), par=(s, z0, 0), reg=PLAN_REG.index("wolle"))
    else:
        nx, nz_ = 4, 3
        seed = rng.random() * 50
        gx = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
        gz = [z0 + (z1 - z0) * j / nz_ for j in range(nz_ + 1)]
        V = [[None] * (nz_ + 1) for _ in range(nx + 1)]
        for i, x in enumerate(gx):
            for j, z in enumerate(gz):
                edge_ = 0 if (i in (0, nx) or j in (0, nz_)) else 1
                V[i][j] = pc.bm.verts.new((x, s * (YR + 0.002 + edge_ * (0.004 + 0.004 * noise.noise(Vector((x * 6, z * 6, seed))))), z))
        for i in range(nx):
            for j in range(nz_):
                f = pc.bm.faces.new((V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]))
                pc.mark([f], 1, R_BAND, PLAN_REG.index("wolle"), par=(s, z0, 0), smooth=True)
                f.normal_update()
                if f.normal.y * s < 0:
                    f.normal_flip()
        poly = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
        yf = s * (YR + 0.002)
    # sichtbare Kanten der Platte bis zum Beton
    n = len(poly)
    cx, cz = sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        P = [Vector((a[0], yf, a[1])), Vector((b[0], yf, b[1])), Vector((b[0], yb, b[1])), Vector((a[0], yb, a[1]))]
        pc.face(P, 1, R_PLAN, Vector(((a[0] + b[0]) / 2 - cx, 0, (a[1] + b[1]) / 2 - cz)), reg=PLAN_REG.index("wolle"))

def cable_strands(pc, s, x0, x1, z0, z1, count, rng, sag=True):
    """Kabelstraenge im Hohlraum: senkrecht, zu zweit oder dritt, manche haengen nach vorn durch."""
    for i in range(count):
        xc = rng.uniform(x0 + 0.08, x1 - 0.12)
        nb = rng.choice([1, 2, 3])
        out = rng.uniform(0.02, 0.06) if (sag and rng.random() < 0.6) else 0.0
        zm = (z0 + z1) / 2 + rng.uniform(-0.2, 0.2)
        for j in range(nb):
            r = rng.uniform(0.004, 0.0065)
            xo = xc + j * 0.014
            yb = YR + 0.006 + r + 0.002 * j
            pts = [Vector((xo, s * yb, max(0.002, z0 - 0.02))), Vector((xo + rng.uniform(-0.03, 0.03), s * (yb + out), zm)),
                   Vector((xo, s * yb, min(H - 0.002, z1 + 0.02)))]
            tube(pc, pts, r, rng.choice(KABEL), seg=6, caps=False, uoff=rng.random())

def cavity(pc, side, x0, x1, z0, z1, seed, batts=None, holes=(), cables=3, sag=True):
    """Untergrund in einer Rasterzelle ohne festes Paneel: Beton, Daemmplatten (teils fehlend), Kabelstraenge."""
    rng = random.Random(int(seed * 1000) + (7 if side > 0 else 3))
    cx0, cx1 = x0 + 0.02, x1 - 0.02
    banded_surface(pc, rect(cx0, cx1, z0, z1), list(holes), side * YC, side, "beton")
    zz, k = z0, 0
    while zz < z1 - 0.05:
        h = min(BAND - 0.02, z1 - zz)
        state = batts[k] if batts is not None and k < len(batts) else rng.choice(["ok", "ok", "fehlt", "riss"])
        if state != "fehlt":
            batt(pc, side, cx0 + 0.003, cx1 - 0.003, zz + 0.003, zz + h - 0.003, state, rng)
        zz += h
        k += 1
    cable_strands(pc, side, cx0, cx1, z0, z1, cables, rng, sag)

def rails(pc, side, cut=None):
    """Tragschienen hinter jeder Fuge (senkrecht) und hinter der Trennfuge (waagerecht); cut = Loch oder Oeffnung."""
    ya, yb = sorted((side * YC, side * YR))
    for xj in COLS:
        xa, xb = max(-W2 + 0.002, xj - 0.02), min(W2 - 0.002, xj + 0.02)
        hits = line_hits(cut, "v", xj) if cut else []
        for za, zb in subtract_spans(0.0, H, hits, 0.02):
            drop_back(pc, box_faces(pc, (xa, ya, za), (xb, yb, zb), R_PLANAX, reg=PLAN_REG.index("schiene"), axis=(0, 0, 1)), side, YC)
    for i in range(4):
        hits = line_hits(cut, "h", TRENN) if cut else []
        for xa, xb in subtract_spans(COLS[i] + 0.02, COLS[i + 1] - 0.02, hits, 0.02):
            drop_back(pc, box_faces(pc, (xa, ya, TRENN - 0.02), (xb, yb, TRENN + 0.02), R_PLANAX,
                                    reg=PLAN_REG.index("schiene"), axis=(1, 0, 0)), side, YC)

def check_holes(name, holes):
    for h in holes:
        xs = [p[0] for p in h]
        if min(xs) < -W2 + EDGE - 1e-6 or max(xs) > W2 - EDGE + 1e-6:
            raise RuntimeError(f"{name}: Schaden zu nah an der Kante ({min(xs):.3f} .. {max(xs):.3f})")

def wall_side(pc, side, states, opening=None, cut=None, ramm=None, trog=None):
    """Eine Wandseite: Paneele je Zustand, Tragschienen, Rammschutz und Kabeltrog."""
    for ci, ri, cell in panel_cells(opening):
        st = states.get((ci, ri), ("ok",))
        x0, x1, z0, z1 = inset(cell)
        if st[0] in ("fehlt", "haengt", "loch"):
            if ci in (0, 3):
                raise RuntimeError("Randpaneele bleiben heil (40-cm-Regel)")
        if st[0] == "ok":
            panel(pc, side, x0, x1, z0, z1)
        elif st[0] == "delle":
            for d in st[1]:
                if not (-W2 + EDGE <= d[0] - d[2] and d[0] + d[2] <= W2 - EDGE):
                    raise RuntimeError("Delle zu nah an der Kante")
            panel(pc, side, x0, x1, z0, z1, dents=st[1])
        elif st[0] == "haengt":
            hanging_panel(pc, side, x0, x1, z0, z1, *st[1])
            cavity(pc, side, cell[0], cell[1], cell[2], cell[3], *st[2])
        elif st[0] == "fehlt":
            cavity(pc, side, cell[0], cell[1], cell[2], cell[3], *st[1])
    rails(pc, side, cut)
    strips(pc, side, ramm if ramm is not None else [(-W2, W2)], trog if trog is not None else [(-W2, W2)])

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
    """Zarge aus gebuerstetem Stahl: Futter in der Laibung, Flansche beidseitig 2 cm vor der Wand,
    Anschlag mit Gummidichtung, zwei Baender."""
    x0, x1, zt = -0.65, 0.65, 2.2
    pl, fl, ft = 0.006, 0.06, 0.02
    yf = T2 + ft
    for a, b in ((x0 - fl, x0 + pl), (x1 - pl, x1 + fl)):
        box_faces(pc, (a, -yf, 0.0), (b, yf, zt - pl), R_METAL, bevel=0.002, axis=(0, 0, 1))
    box_faces(pc, (x0 - fl, -yf, zt - pl), (x1 + fl, yf, zt + fl), R_METAL, bevel=0.002, axis=(1, 0, 0))
    st, ys0, ys1 = 0.025, -0.045, -0.02
    zs = zt - pl - st
    box_faces(pc, (x0 + pl, ys0, 0.0), (x0 + pl + st, ys1, zs), R_METAL, axis=(0, 0, 1))
    box_faces(pc, (x1 - pl - st, ys0, 0.0), (x1 - pl, ys1, zs), R_METAL, axis=(0, 0, 1))
    box_faces(pc, (x0 + pl, ys0, zs), (x1 - pl, ys1, zt - pl), R_METAL, axis=(1, 0, 0))
    g = PLAN_REG.index("gummi")
    gy0, gy1 = ys0 - 0.007, ys0
    box_faces(pc, (x0 + pl + 0.007, gy0, 0.0), (x0 + pl + 0.019, gy1, zs - 0.019), R_PLANAX, reg=g, axis=(0, 0, 1))
    box_faces(pc, (x1 - pl - 0.019, gy0, 0.0), (x1 - pl - 0.007, gy1, zs - 0.019), R_PLANAX, reg=g, axis=(0, 0, 1))
    box_faces(pc, (x0 + pl + 0.007, gy0, zs - 0.019), (x1 - pl - 0.007, gy1, zs - 0.007), R_PLANAX, reg=g, axis=(1, 0, 0))
    for zc in (0.3, 1.9):
        tube(pc, [(x0 + pl + 0.014, -0.065, zc), (x0 + pl + 0.014, -0.065, zc + 0.12)], 0.012, "stahl_10", seg=8)

def window_frame(pc):
    """Fensterzarge aus gebuerstetem Stahl (Flansche 2 cm, Baenke 5 cm), Rahmen in der Wandmitte
    mit Gummidichtung, wo die Scheibe sass. Ohne Glas, ohne Gitter."""
    x0, x1, z0, z1 = -0.75, 0.75, 0.95, 2.35
    pl, fl, ft = 0.006, 0.06, 0.02
    yf = T2 + ft
    for a, b in ((x0 - fl, x0 + pl), (x1 - pl, x1 + fl)):
        box_faces(pc, (a, -yf, z0 + pl), (b, yf, z1 - pl), R_METAL, bevel=0.002, axis=(0, 0, 1))
    box_faces(pc, (x0 - fl, -yf, z1 - pl), (x1 + fl, yf, z1 + fl), R_METAL, bevel=0.002, axis=(1, 0, 0))
    box_faces(pc, (x0 - fl, -yf, z0 - fl), (x1 + fl, yf, z0 + pl), R_METAL, bevel=0.002, axis=(1, 0, 0))
    for s in (-1, 1):
        ys = sorted((s * yf, s * (T2 + 0.05)))
        box_faces(pc, (x0 - fl - 0.02, ys[0], z0 - 0.014), (x1 + fl + 0.02, ys[1], z0 + pl), R_METAL, bevel=0.002, axis=(1, 0, 0))
    fw, fd = 0.05, 0.03
    ix0, ix1, iz0, iz1 = x0 + pl, x1 - pl, z0 + pl, z1 - pl
    box_faces(pc, (ix0, -fd, iz0 + fw), (ix0 + fw, fd, iz1 - fw), R_METAL, bevel=0.002, axis=(0, 0, 1))
    box_faces(pc, (ix1 - fw, -fd, iz0 + fw), (ix1, fd, iz1 - fw), R_METAL, bevel=0.002, axis=(0, 0, 1))
    box_faces(pc, (ix0, -fd, iz1 - fw), (ix1, fd, iz1), R_METAL, bevel=0.002, axis=(1, 0, 0))
    box_faces(pc, (ix0, -fd, iz0), (ix1, fd, iz0 + fw), R_METAL, bevel=0.002, axis=(1, 0, 0))
    g = PLAN_REG.index("gummi")
    gx0, gx1, gz0, gz1, gd = ix0 + fw, ix1 - fw, iz0 + fw, iz1 - fw, 0.008
    box_faces(pc, (gx0, -0.006, gz0 + gd), (gx0 + gd, 0.006, gz1 - gd), R_PLANAX, reg=g, axis=(0, 0, 1))
    box_faces(pc, (gx1 - gd, -0.006, gz0 + gd), (gx1, 0.006, gz1 - gd), R_PLANAX, reg=g, axis=(0, 0, 1))
    box_faces(pc, (gx0, -0.006, gz1 - gd), (gx1, 0.006, gz1), R_PLANAX, reg=g, axis=(1, 0, 0))
    box_faces(pc, (gx0, -0.006, gz0), (gx1, 0.006, gz0 + gd), R_PLANAX, reg=g, axis=(1, 0, 0))

def cable_bundle(pc, side, zc):
    """Gebuendelte Kabel unter der Decke: sieben Adern, Kabelbinder, Wandschellen; buendig an beiden Kanten."""
    s = side
    yc = T2 + 0.021
    offs = [(0.0, 0.0)] + [(0.013 * math.cos(k * math.pi / 3), 0.013 * math.sin(k * math.pi / 3)) for k in range(6)]
    regs = ["kabel_s", "kabel_g", "kabel_s", "kabel_b", "kabel_r", "kabel_g", "kabel_y"]
    for k, (dy, dz) in enumerate(offs):
        tube(pc, [(-W2, s * (yc + dy), zc + dz), (W2, s * (yc + dy), zc + dz)], 0.006, regs[k], seg=6, caps=False, uoff=0.07 * k)
    g = PLAN_REG.index("kabel_s")          # Kabelbinder: schwarzer Kunststoff
    for i in range(10):
        x = -1.44 + 0.32 * i
        ys = sorted((s * (yc - 0.0205), s * (yc + 0.0205)))
        box_faces(pc, (x - 0.0025, ys[0], zc - 0.0205), (x + 0.0025, ys[1], zc + 0.0205), R_PLANAX, reg=g, axis=(0, 1, 0))
        yh = sorted((s * (yc + 0.0205), s * (yc + 0.027)))
        box_faces(pc, (x - 0.004, yh[0], zc + 0.006), (x + 0.004, yh[1], zc + 0.016), R_PLAN, reg=g)
    for xs in (-1.3, 0.0, 1.3):
        ys = sorted((s * T2, s * (yc + 0.023)))
        drop_back(pc, box_faces(pc, (xs - 0.012, ys[0], zc - 0.024), (xs + 0.012, ys[1], zc + 0.024), R_PLANAX,
                                reg=PLAN_REG.index("schiene"), axis=(0, 0, 1)), s)

def pipe_clamp(pc, side, x, yc, zc, r):
    s = side
    rr = r + 0.004
    tube(pc, [(x - 0.012, s * yc, zc), (x + 0.012, s * yc, zc)], rr, "stahl_24", seg=12, caps=True, uoff=0.2)
    ys = sorted((s * T2, s * (T2 + 0.004)))
    drop_back(pc, box_faces(pc, (x - 0.02, ys[0], zc - 0.025), (x + 0.02, ys[1], zc + 0.025), R_METAL, bevel=0.0015), s)
    ys2 = sorted((s * (T2 + 0.004), s * (yc - rr + 0.001)))
    box_faces(pc, (x - 0.006, ys2[0], zc - 0.006), (x + 0.006, ys2[1], zc + 0.006), R_METAL)

def bedienfeld(pc, side, xc, zc):
    """Bedienfeld mit dunklem Bildschirm, Rahmen, Tasten und Not-Aus; Kabel nach unten in den Kabeltrog."""
    s = side
    bx0, bx1 = xc - KASTEN_W / 2, xc + KASTEN_W / 2
    bz0, bz1 = zc - KASTEN_H / 2, zc + KASTEN_H / 2
    y1 = T2 + KASTEN_T
    front_par = (bx1, bz0, -1) if s > 0 else (bx0, bz0, 1)
    def fronted(faces, yback):
        for f in faces:
            f.normal_update()
            if f.normal.y * s > 0.99:
                f[pc.rule] = R_BOXFRONT
                f[pc.par] = front_par
        drop_back(pc, faces, s, yback)
    ys = sorted((s * T2, s * y1))
    fronted(box_faces(pc, (bx0, ys[0], bz0), (bx1, ys[1], bz1), R_PLAN, reg=PLAN_REG.index("panel"), bevel=0.004), T2)
    def front_box(px0, px1, pz0, pz1, depth):
        xa, xb = (bx1 - px1, bx1 - px0) if s > 0 else (bx0 + px0, bx0 + px1)
        ya = sorted((s * y1, s * (y1 + depth)))
        fronted(box_faces(pc, (xa, ya[0], bz0 + pz0), (xb, ya[1], bz0 + pz1), R_PLAN, reg=PLAN_REG.index("panel")), y1)
    for a, b, c, d in ((0.03, 0.31, 0.16, 0.17), (0.03, 0.31, 0.37, 0.38), (0.03, 0.04, 0.17, 0.37), (0.30, 0.31, 0.17, 0.37)):
        front_box(a, b, c, d, 0.006)
    for cx_ in (0.355, 0.425):
        front_box(cx_ - 0.012, cx_ + 0.012, 0.288, 0.312, 0.006)
    for k in range(3):
        cx_ = 0.342 + 0.0175 + 0.035 * k
        front_box(cx_ - 0.012, cx_ + 0.012, 0.218, 0.242, 0.005)
    ex = bx1 - 0.43 if s > 0 else bx0 + 0.43
    tube(pc, [(ex, s * y1, bz0 + 0.085), (ex, s * (y1 + 0.022), bz0 + 0.085)], 0.02, "rot", seg=10, caps=True)
    kx = bx0 + 0.08 if s > 0 else bx1 - 0.08
    pts = fillet([Vector((kx, s * (T2 + 0.03), bz0 + 0.01)), Vector((kx, s * (T2 + 0.03), bz0 - 0.03)),
                  Vector((kx - 0.03, s * (T2 + 0.045), 1.26)), Vector((kx - 0.05, s * (T2 + 0.045), 1.2))], 0.02, 3)
    tube(pc, pts, 0.006, "kabel_s", seg=6, caps=True)

def floor_debris(pc, x0, x1, side, n, seed):
    """Am Fuss der Wand: Betonbroeckchen, Daemmflocken, Paneelsplitter (hoechstens 12 cm vor der Wand)."""
    rng = random.Random(seed)
    for i in range(n):
        x = rng.uniform(x0, x1)
        kind = i % 3
        y = side * (T2 + RAMM_D + rng.uniform(0.02, 0.045))
        if kind == 0:
            s_ = rng.uniform(0.01, 0.022)
            chunk(pc, (x, y, s_ * 0.5), (s_ * 1.4, s_, s_ * 0.7), seed * 10 + i, "beton", subdiv=0)
        elif kind == 1:
            s_ = rng.uniform(0.015, 0.03)
            chunk(pc, (x, y, s_ * 0.35), (s_ * 1.5, s_, s_ * 0.45), seed * 10 + i, "wolle", subdiv=0)
        else:
            shard(pc, x, side * (T2 + RAMM_D + rng.uniform(0.01, 0.022)), seed * 100 + i, size=(0.015, 0.035), thick=0.0015)

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

def through_hole_outline(seed=3.1, N=80):
    """Unregelmaessiger Umriss im Betonkern: 1,44 m breit, 1,32 m hoch, Unterkante bei 0,96 m."""
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

def torn_cables(pc, side, hole, ends, seed):
    """Abgerissene Kabel: aus den Enden des Kabeltrogs und vom oberen Lochrand haengen sie herunter."""
    rng = random.Random(seed + (5 if side > 0 else 0))
    s = side
    for xe, dirx in ends:
        for k, (d, r, reg) in enumerate(TROG_KABEL):
            if rng.random() < 0.2:
                continue
            y0, z0 = s * (T2 + d), 1.172 + r
            L1 = rng.uniform(0.05, 0.16)
            fall = rng.uniform(0.25, 0.55)
            p0 = Vector((xe - dirx * 0.02, y0, z0))
            p1 = Vector((xe + dirx * L1, y0, z0 + rng.uniform(-0.005, 0.02)))
            p2 = Vector((xe + dirx * (L1 + rng.uniform(0.03, 0.08)), s * (T2 + d + rng.uniform(0.0, 0.03)), z0 - fall * 0.5))
            p3 = Vector((p2.x + dirx * rng.uniform(-0.03, 0.05), s * min(0.2, T2 + d + rng.uniform(0.0, 0.05)), z0 - fall))
            tube(pc, fillet([p0, p1, p2, p3], 0.04, 2), r, reg, seg=6, caps=True, uoff=rng.random())
    for i in range(7):
        x = -0.5 + i / 6.0 + rng.uniform(-0.05, 0.05)
        segs = line_hits(hole, "v", x)
        if not segs:
            continue
        zt = segs[-1][1]
        r = rng.uniform(0.004, 0.0065)
        L = rng.uniform(0.15, 0.55)
        y0 = s * (YR + 0.01)
        pts = [Vector((x, y0, zt + 0.1)), Vector((x, y0, zt - 0.01)),
               Vector((x + rng.uniform(-0.05, 0.05), s * (YR + rng.uniform(-0.02, 0.04)), zt - L * 0.6)),
               Vector((x + rng.uniform(-0.08, 0.08), s * rng.uniform(0.0, 0.09), zt - L))]
        tube(pc, fillet(pts, 0.03, 2), r, rng.choice(KABEL), seg=6, caps=True, uoff=rng.random())

def rubble(pc, side, xc, seed):
    """Schuttkegel bis 60 cm vor der Wand: Betonbrocken, Daemmflocken, Paneelsplitter, Kabelreste."""
    rng = random.Random(int(seed * 100) + (5 if side > 0 else 1))
    nxp, nyp = 12, 6
    rx, ry, hmax = 0.78, 0.5, 0.2
    V = []
    for i in range(nxp + 1):
        sx = 2 * i / nxp - 1
        reach = min(1.0, 0.8 + 0.2 * noise.noise(Vector((sx * 2.2, side * 5.0, seed))))
        row = []
        for j in range(nyp + 1):
            t = j / nyp
            half = rx * math.sqrt(max(0.0, 1 - (0.8 * t) ** 2)) * (1 + 0.1 * noise.noise(Vector((t * 3.0, side * 3.0, seed + 1.4))))
            x = xc + half * sx
            yd = RAMM_D + 0.004 + ry * reach * t
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
            pc.face(P, 1, R_PLAN, (0, side * 0.3, 1), reg=PLAN_REG.index("beton"))
    idx = lambda i, j: i * (nyp + 1) + j
    tree = BVHTree.FromPolygons([v for row in V for v in row],
                                [(idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)) for i in range(nxp) for j in range(nyp)])
    def heap_z(x, yd):
        hit = tree.ray_cast(Vector((x, side * (T2 + yd), 2.0)), Vector((0, 0, -1)))
        return max(0.0, hit[0].z) if hit[0] is not None else 0.0
    for k in range(5):
        x, yd, s_ = xc + rng.uniform(-0.55, 0.55), rng.uniform(0.08, 0.32), rng.uniform(0.05, 0.09)
        chunk(pc, (x, side * (T2 + yd), heap_z(x, yd) + s_ * 0.35), (s_ * 1.35, s_, s_ * 0.75), 60 + k + (20 if side > 0 else 0), "beton")
    for k in range(6):
        x, yd, s_ = xc + rng.uniform(-0.65, 0.65), rng.uniform(0.05, 0.42), rng.uniform(0.015, 0.035)
        chunk(pc, (x, side * (T2 + yd), heap_z(x, yd) * 0.95 + s_ * 0.3), (s_ * 1.3, s_, s_ * 0.7), 120 + k + (30 if side > 0 else 0), "beton", subdiv=0)
    for k in range(4):
        x, yd, s_ = xc + rng.uniform(-0.6, 0.6), rng.uniform(0.06, 0.38), rng.uniform(0.04, 0.07)
        chunk(pc, (x, side * (T2 + yd), heap_z(x, yd) + s_ * 0.2), (s_ * 1.4, s_, s_ * 0.4), 200 + k + (30 if side > 0 else 0), "wolle", subdiv=0)
    for k in range(5):
        x, yd = xc + rng.uniform(-0.6, 0.6), rng.uniform(0.06, 0.4)
        shard(pc, x, side * (T2 + yd), 300 + k + (50 if side > 0 else 0), size=(0.05, 0.11),
              zbase=max(0.0, heap_z(x, yd) - 0.004), thick=0.0015)
    for k in range(2):
        x, yd = xc + rng.uniform(-0.5, 0.5), rng.uniform(0.1, 0.35)
        a = rng.uniform(0, math.pi)
        p0 = Vector((x, side * (T2 + yd), heap_z(x, yd) + 0.006))
        p1 = p0 + Vector((math.cos(a) * 0.25, side * math.sin(a) * 0.08, 0.0))
        p1.z = heap_z(p1.x, abs(p1.y) - T2) + 0.006
        tube(pc, [p0, (p0 + p1) / 2 + Vector((0, 0, 0.01)), p1], 0.005, rng.choice(KABEL), seg=6, caps=True, uoff=rng.random())

# ======================= Die sieben Stuecke =======================
FULL = [(-W2, W2)]

def wand_01():
    pc = Piece(f"{GEB}_wand_01")
    shell(pc)
    wall_side(pc, -1, {(1, 0): ("delle", [(-0.55, 0.72, 0.16, 0.012, 0.6, 1.1)])})
    wall_side(pc, 1, {(3, 1): ("delle", [(1.22, 2.35, 0.17, 0.014, -0.4, 2.3)])})
    return finish(pc)

def wand_02():
    pc = Piece(f"{GEB}_wand_02")
    shell(pc)
    # -Y: oben links Paneel weg (Riss im Beton), oben rechts losgerissen, unten zwei Paneele verbeult
    crack = [(-0.33, 3.33), (-0.38, 3.05), (-0.29, 2.8), (-0.45, 2.52), (-0.4, 2.22), (-0.55, 1.95), (-0.5, 1.66), (-0.62, 1.38)]
    wid = [0.002, 0.007, 0.012, 0.018, 0.02, 0.016, 0.01, 0.003]
    opening = crack_at(pc, crack, wid, -1, YC, 0.05)
    wall_side(pc, -1, {
        (1, 1): ("fehlt", (1.3, ["fehlt", "riss", "fehlt", "ok", "fehlt", "fehlt"], [opening], 3, True)),
        (2, 1): ("haengt", (0.1, 0.06), (2.1, ["ok", "fehlt", "ok", "riss", "ok", "ok"], (), 2, False)),
        (1, 0): ("delle", [(-0.5, 0.75, 0.2, 0.016, 0.9, 3.1), (-0.25, 0.42, 0.1, 0.01, -0.3, 3.7)]),
        (2, 0): ("delle", [(0.45, 0.9, 0.22, 0.017, 2.2, 4.4)]),
    })
    # +Y: oben rechts Paneel weg, unten links Paneel weg, oben links verbeult
    wall_side(pc, 1, {
        (2, 1): ("fehlt", (5.2, ["ok", "riss", "fehlt", "ok", "fehlt", "ok"], (), 4, True)),
        (1, 0): ("fehlt", (6.4, ["fehlt", "ok", "riss"], (), 3, True)),
        (1, 1): ("delle", [(-0.45, 2.6, 0.24, 0.016, 1.4, 5.9)]),
    })
    floor_debris(pc, -0.85, 0.8, -1, 11, 23)
    floor_debris(pc, -0.85, 0.85, 1, 9, 24)
    return finish(pc)

def wand_03():
    pc = Piece(f"{GEB}_wand_03")
    shell(pc)
    wall_side(pc, -1, {(2, 1): ("delle", [(0.5, 1.75, 0.15, 0.011, 0.3, 7.7)])})
    wall_side(pc, 1, {})
    # Leitungen auf +Y unter der Decke, buendig an beiden Kanten
    cable_bundle(pc, 1, 3.27)
    for zc, r, reg in ((3.1, 0.03, "rohr_a"), (2.96, 0.024, "rohr_b")):
        yc = T2 + 0.012 + r
        tube(pc, [(-W2, yc, zc), (W2, yc, zc)], r, reg, seg=12, caps=False, uoff=0.025)
        for x in (-1.3, 0.0, 1.3):
            pipe_clamp(pc, 1, x, yc, zc, r)
    bedienfeld(pc, 1, -0.45, 1.52)
    return finish(pc)

def wand_tuer():
    pc = Piece(f"{GEB}_wand_tuer")
    shell(pc)
    opening = (-0.68, 0.68, 0.0, 2.23)
    cut = rect(*opening[:2], *opening[2:])
    spans = [(-W2, -0.71), (0.71, W2)]
    wall_side(pc, -1, {(0, 1): ("delle", [(-1.2, 2.8, 0.15, 0.012, 0.7, 8.1)])}, opening, cut, spans, spans)
    wall_side(pc, 1, {}, opening, cut, spans, spans)
    door_frame(pc)
    return finish(pc)

def wand_fenster():
    pc = Piece(f"{GEB}_wand_fenster")
    shell(pc)
    opening = (-0.78, 0.78, 0.92, 2.38)
    cut = rect(*opening[:2], *opening[2:])
    trog = [(-W2, -0.81), (0.81, W2)]
    wall_side(pc, -1, {}, opening, cut, FULL, trog)
    wall_side(pc, 1, {(3, 0): ("delle", [(1.25, 0.75, 0.15, 0.012, 2.6, 9.3)])}, opening, cut, FULL, trog)
    window_frame(pc)
    return finish(pc)

def wand_durchbruch():
    pc = Piece(f"{GEB}_wand_durchbruch")
    shell(pc)
    hole = through_hole_outline()
    check_holes(pc.name, [hole])
    hits = line_hits(hole, "h", TRENN)
    xl, xr = hits[0][0], hits[-1][1]
    trog = [(-W2, xl - 0.06), (xr + 0.06, W2)]
    states = {(1, 0): ("loch",), (2, 0): ("loch",), (1, 1): ("loch",), (2, 1): ("loch",)}
    for side in (-1, 1):
        wall_side(pc, side, states, cut=hole, trog=trog)
        # Hohlraum der beiden mittleren Spalten: Beton mit Loch, Daemmung eingerissen
        banded_surface(pc, rect(-0.93, 0.93, 0.0, H), [hole], side * YC, side, "beton")
        torn = expand_loop(hole, 0.06, 0.6, 4.4 + side)
        for ci in (1, 2):
            bx0, bx1 = COLS[ci] + 0.023, COLS[ci + 1] - 0.023
            zz = 0.0
            while zz < H - 0.05:
                h = min(BAND - 0.02, H - zz)
                banded_surface(pc, rect(bx0, bx1, zz + 0.003, zz + h - 0.003), [torn], side * (YR + 0.002), side, "wolle")
                zz += h
        cxh = sum(p[0] for p in torn) / len(torn)
        czh = sum(p[1] for p in torn) / len(torn)
        for i in range(len(torn)):
            a, b = torn[i], torn[(i + 1) % len(torn)]
            mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            inside = any(COLS[ci] + 0.025 < mx < COLS[ci + 1] - 0.025 for ci in (1, 2)) and 0.0 < mz < H
            if not inside:
                continue
            P = [Vector((a[0], side * (YR + 0.002), a[1])), Vector((b[0], side * (YR + 0.002), b[1])),
                 Vector((b[0], side * YC, b[1])), Vector((a[0], side * YC, a[1]))]
            pc.face(P, 1, R_PLAN, Vector((cxh - mx, 0, czh - mz)), reg=PLAN_REG.index("wolle"))
        torn_cables(pc, side, hole, [(xl - 0.06, 1), (xr + 0.06, -1)], 11)
    # Bruchflaeche durch den Betonkern, in der Mitte grob verformt; das Loch bleibt in den Grenzen
    n = len(hole)
    cx = sum(p[0] for p in hole) / n
    cz = sum(p[1] for p in hole) / n
    grid = []
    for k in range(n):
        x, z = hole[k]
        ux, uz = x - cx, z - cz
        l = math.hypot(ux, uz) or 1.0
        ux, uz = ux / l, uz / l
        colm = []
        for j, y in enumerate((-YC, 0.0, YC)):
            if j == 1:
                d = 0.03 * noise.noise(Vector((x * 5, 3.0, z * 5))) + 0.012 * noise.noise(Vector((x * 18, 7.0, z * 18))) + 0.015
                colm.append(Vector((min(0.795, max(-0.795, x + ux * d)), y, min(2.395, max(0.905, z + uz * d)))))
            else:
                colm.append(Vector((x, y, z)))
        grid.append(colm)
    ccw = loop_area(hole) > 0
    for k in range(n):
        k2 = (k + 1) % n
        for j in range(2):
            P = [grid[k][j], grid[k2][j], grid[k2][j + 1], grid[k][j + 1]]
            pc.face(P, 1, R_PLAN, edge_inward(hole, k, ccw), reg=PLAN_REG.index("beton"))
    rubble(pc, -1, cx * 0.3, 3.3)
    rubble(pc, 1, cx * 0.3, 5.1)
    return finish(pc)

def wand_ecke():
    """Eckpfosten 21 x 21 cm: Paneelstreifen auf allen vier Seiten, Rammschutz und Kabeltrog rundum,
    die Trogkabel laufen als Ring um den Pfosten."""
    pc = Piece(f"{GEB}_wand_ecke")
    a = 0.105
    sides = [((0, -1, 0), (-a, -a), (a, -a)), ((1, 0, 0), (a, -a), (a, a)), ((0, 1, 0), (a, a), (-a, a)), ((-1, 0, 0), (-a, a), (-a, -a))]
    def post_u(nrm, p):
        if nrm == (0, -1, 0):
            return UVS * p.x
        if nrm == (0, 1, 0):
            return -UVS * p.x
        if nrm == (1, 0, 0):
            return UVS * p.y
        return -UVS * p.y
    for nrm, p0, p1 in sides:
        P = [Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0)), Vector((p1[0], p1[1], H)), Vector((p0[0], p0[1], H))]
        f = pc.face(P, 0, R_KEEP, nrm)
        for l in f.loops:
            l[pc.uv].uv = (post_u(nrm, l.vert.co), UVS * l.vert.co.z)
    f = pc.face([Vector((-a, -a, H)), Vector((a, -a, H)), Vector((a, a, H)), Vector((-a, a, H))], 0, R_KEEP, (0, 0, 1))
    for l in f.loops:
        l[pc.uv].uv = (UVS * l.vert.co.x, UVS * (3.42 + l.vert.co.y + a))
    for prof, reg in ((RAMM_PROF, "warn"), (TROG_PROF, "trog")):
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
    for d, r, reg in TROG_KABEL:
        R = a + d
        z = 1.172 + r
        loop = [Vector((R, 0, z)), Vector((R, R, z)), Vector((-R, R, z)), Vector((-R, -R, z)), Vector((R, -R, z)), Vector((R, 0, z))]
        tube(pc, fillet(loop, min(0.02, d), 1), r, reg, seg=5, caps=False)
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
    "lampe1": (1, -1, (-1.1, 3.1, 1.9), (0.1, 0, 2.15), (0.15, 0, 2.05)),
    "lampe2": (5, 1, (-1.2, 3.0, 1.45), (0.05, 0, 1.2), (0.1, 0, 1.1)),
    "lampe3": (2, 1, (0.9, 2.9, 1.95), (-0.25, 0, 2.3), (-0.3, 0, 2.2)),
    "lampe4": (3, -1, (-1.5, 2.8, 1.5), (0.0, 0, 1.2), (0.05, 0, 1.1)),
    "nah1": (1, -1, (-0.25, 1.15, 2.25), (-0.45, 0, 2.15), (-0.45, 0, 2.15), 28),
    "nah2": (4, -1, (-0.35, 0.75, 1.32), (-0.64, 0, 1.08), (-0.64, 0, 1.08), 35),
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
            spot_d.energy = 420 if lens <= 20 else 140
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

