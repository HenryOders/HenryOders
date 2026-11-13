# ABANDONED · Modulare Wandstuecke fuer das Gebaeude "gefaengnis"
# Sieben Stuecke, zwei kachelbare Materialien ("Wand", "Detail") mit je 4096 x 4096 px,
# UV-Massstab 0,25 je Meter (1024 px/m). Export als glTF 2.0 mit gemeinsamen Texturdateien.
# Start: blender -b -P kit_gefaengnis.py  (oder mit dem bpy-Modul: python kit_gefaengnis.py).
# Das Skript setzt Blender auf Werkseinstellungen zurueck, also nicht in einem offenen Projekt ausfuehren.
import bpy, bmesh, math, random, os, time, json, zlib
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, Quaternion, noise, geometry
from mathutils.bvhtree import BVHTree

T0 = time.time()
def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)

GEB = "gefaengnis"
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
TRENN = 1.2                    # Farbkante: darunter graugruen gestrichen, darueber nackter Beton
PLH, PLD = 0.10, 0.025         # niedriger Betonsockel: 10 cm hoch, steht 2,5 cm vor
SPALL = 0.055                  # Abplatzungen gehen bis hinter die vorderen Eisen
DECK = 0.035                   # Betondeckung bis zum vorderen Eisen
BAR_R = 0.006                  # Bewehrung 12 mm
BAR_H = T2 - DECK - BAR_R      # Abstand Wandmitte - waagerechte Eisen (vorne)
BAR_V = BAR_H - 2 * BAR_R      # senkrechte Eisen liegen direkt dahinter
RASTER = 0.2                   # Bewehrung: senkrecht bei x = 0,2 k, waagerecht bei z = 0,1 + 0,2 k
EDGE = 0.4                     # Schaeden nie naeher an den Seitenkanten
KASTEN_W, KASTEN_H, KASTEN_T = 0.36, 0.44, 0.095

# Detail-Atlas: waagerechte Bereiche (Hoehe in Metern), jeder kachelt in U
REG = {
    "kern": (0.00, 1.80), "riss": (1.81, 1.91), "kratzer": (1.92, 1.97),
    "stahl_24": (1.98, 2.23), "stahl_10": (2.24, 2.34), "stahl_07": (2.35, 2.42), "stahl_05": (2.43, 2.48),
    "stahl_03": (2.49, 2.52), "sockel": (2.53, 2.70), "rohr": (2.71, 3.04), "rost": (3.05, 3.11),
    "kasten": (3.12, 3.62),
}

# ======================= Texturen =======================
def drip_pad(M, length_m):
    """drip ohne Umlauf am oberen Rand (fuer Bereiche im Atlas)."""
    pad = int(length_m * NPX / 4.0) + 2
    P = np.concatenate([M, np.zeros((pad, M.shape[1]), M.dtype)], axis=0)
    return drip(P, length_m)[:M.shape[0]]

def lin(a, b, t):
    return a * (1 - t) + b * t

def tri_mask(px, pz, cx, cz, side):
    """gleichseitiges Dreieck mit Spitze oben."""
    h = side * math.sqrt(3) / 2
    A = (cx, cz + 2 * h / 3)
    B = (cx - side / 2, cz - h / 3)
    C = (cx + side / 2, cz - h / 3)
    def s(P, Q):
        return (px - Q[0]) * (P[1] - Q[1]) - (P[0] - Q[0]) * (pz - Q[1])
    d1, d2, d3 = s(A, B), s(B, C), s(C, A)
    neg = (d1 < 0) | (d2 < 0) | (d3 < 0)
    pos = (d1 > 0) | (d2 > 0) | (d3 > 0)
    return ~(neg & pos)

def poly_mask(px, pz, poly):
    inside = np.zeros(px.shape, bool)
    n = len(poly)
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
        cross = (z0 > pz) != (z1 > pz)
        xi = x0 + (pz - z0) / ((z1 - z0) if z1 != z0 else 1e-9) * (x1 - x0)
        inside ^= cross & (px < xi)
    return inside

def tex_wand():
    n = NPX
    X, Z = grid_xz()
    S = (n, n)
    rng = np.random.default_rng(71)
    # ---- Sichtbeton aus 1 m breiten Schaltafeln: senkrechte Fugen bei x = 0,5 + k, Querfuge bei 2,4 m ----
    fxj = np.mod(X - 0.5, 1.0)
    dj = np.minimum(np.minimum(fxj, 1.0 - fxj), np.abs(Z - 2.4))
    col = np.floor(np.mod(X - 0.5, 4.0)).astype(np.int32)
    row = (Z >= 2.4).astype(np.int32)
    ptone = rng.normal(0, 0.035, (2, 4)).astype(np.float32)
    pstep = rng.uniform(-0.0012, 0.0012, (2, 4)).astype(np.float32)
    wj = 0.0011 + 0.0005 * sm(-1.0, 2.0, fr(S, 1.0, 72))
    joint = sm(wj + 0.0012, wj, dj)
    fin = sm(0.0045, 0.0015, dj) * (1 - joint) * sm(-0.3, 1.0, fr(S, 0.8, 73))
    cloud = fr(S, 1.7, 74)
    mid = fr(S, 1.0, 75)
    fine = fr(S, 0.35, 76, sigma_m=0.0007)
    conc = hexc("#8f8d86") * (1 + ptone[row, col] + 0.05 * cloud + 0.025 * mid)[..., None]
    conc = conc * (0.955 + 0.045 * fine)[..., None]
    pores = sm(2.3, 3.0, fr(S, 0.12, 77, sigma_m=0.0011)) * (0.5 + 0.5 * sm(-0.6, 1.4, fr(S, 1.1, 78)))
    conc = conc * (1 - 0.55 * pores - 0.35 * joint + 0.06 * fin)[..., None]
    # ---- runde Ankerloecher (25 mm): x = ganze Meter, Reihen 0,35 / 1,05 / 1,75 / 2,9 m ----
    tx = np.mod(X + 0.5, 1.0) - 0.5
    tk = np.mod(np.round(X), 4).astype(np.int32)
    dtie = np.full(S, 9.0, np.float32)
    trow = np.zeros(S, np.int32)
    for i, zr in enumerate((0.35, 1.05, 1.75, 2.9)):
        d = np.hypot(tx, Z - zr).astype(np.float32)
        trow = np.where(d < dtie, i, trow)
        dtie = np.minimum(dtie, d)
    R0 = 0.0125
    hole = sm(R0 + 0.0008, R0 - 0.0008, dtie)
    cone = sm(R0 + 0.007, R0 + 0.001, dtie) * (1 - hole)
    rusty = (rng.random((4, 4)) < 0.6)[trow, tk]
    rod = sm(0.0045, 0.003, dtie) * rusty
    rsrc = sm(R0 + 0.012, R0 - 0.002, dtie) * rusty * (Z > TRENN + 0.05)
    mod = sm(-0.6, 1.4, fr(S, 0.7, 79, aniso=6.0))
    runs = np.clip(drip(rsrc, 0.7) * (0.35 + 0.65 * mod), 0, 1) * (0.55 + 0.45 * sm(-1.0, 1.5, fr(S, 0.4, 96)))
    halo = sm(R0 + 0.022, R0, dtie) * rusty * (Z > TRENN + 0.05)
    # ---- Ausbluehungen: an der Querfuge, unter der Decke, fleckig ----
    esrc = sm(0.03, 0.0, np.abs(Z - 2.4)) * sm(0.2, 1.3, fr(S, 0.9, 80))
    esrc = np.maximum(esrc, sm(3.12, 3.32, Z) * sm(3.45, 3.38, Z) * sm(0.5, 1.5, fr(S, 1.2, 81)))
    esrc = np.maximum(esrc, sm(2.0, 2.7, fr(S, 1.4, 82)) * sm(TRENN + 0.05, TRENN + 0.25, Z) * sm(3.42, 3.35, Z))
    eff = np.clip(drip(esrc, 0.35) * (0.55 + 0.45 * sm(-0.5, 1.5, fr(S, 0.5, 83, aniso=5.0))), 0, 1)
    eff = eff * sm(TRENN, TRENN + 0.03, Z)
    # ---- Wasserlaeufe von oben ----
    wsrc = sm(1.6, 2.6, fr(S, 1.0, 84, aniso=12.0)) * sm(3.0, 3.36, Z) * sm(3.42, 3.38, Z)
    wl = drip(wsrc, 1.9) * (0.6 + 0.4 * sm(-0.5, 1.0, fr(S, 0.9, 85)))
    bare = conc * (1 - 0.25 * cone)[..., None]
    bare = mix(bare, hexc("#262320"), 0.92 * hole)
    bare = mix(bare, hexc("#6a361c"), rod)
    rustc = mix(hexc("#674733"), hexc("#8d6142"), sm(-1.0, 1.5, fr(S, 0.6, 86)))
    bare = mix(bare, rustc, np.clip(0.55 * runs + 0.4 * halo, 0, 1))
    bare = bare * (1 - 0.2 * wl)[..., None]
    bare = mix(bare, hexc("#dedcd4") * (0.95 + 0.05 * fine[..., None]), 0.8 * eff)
    # ---- Farbe bis 1,2 m: Graugruen, blaettert ab (Grundierung am Rand, darunter Beton) ----
    edge = TRENN + 0.0015 * fr(S, 0.8, 87) + 0.0008 * fr(S, 0.3, 88)
    painted = Z < edge
    pf = fr(S, 1.25, 89) + 0.55 * fr(S, 0.7, 90) + 0.25 * fr(S, 0.3, 91)
    pf = pf + 0.9 * sm(0.45, 0.1, Z) + 0.5 * sm(1.0, 1.19, Z)
    top_off = sm(1.52, 1.56, pf)
    peel = sm(1.6, 1.64, pf)
    chalk = sm(0.4, 2.0, fr(S, 1.5, 92))
    grime = np.clip(0.55 * sm(0.6, 0.12, Z) + 0.35 * sm(0.5, 2.2, fr(S, 1.2, 93)), 0, 1)
    scuff = sm(1.9, 2.6, fr(S, 0.6, 94, aniso=0.15)) * sm(0.15, 0.3, Z) * sm(0.95, 0.75, Z)
    plug = sm(R0 + 0.004, R0 - 0.001, dtie)
    pcol = hexc("#687867") * (0.93 + 0.06 * fr(S, 1.3, 95)[..., None] + 0.02 * fine[..., None])
    pcol = mix(pcol, hexc("#8b9987"), 0.35 * chalk)
    pcol = mix(pcol, hexc("#3e443b"), 0.45 * grime)
    pcol = mix(pcol, hexc("#2d302b"), 0.5 * scuff)
    pcol = pcol * (1 - 0.06 * plug - 0.15 * joint - 0.12 * wl)[..., None]
    under = mix(hexc("#b9b4a1") * (0.9 + 0.08 * fine[..., None]), conc, peel)
    psurf = mix(pcol, under, top_off)
    alb = np.where(painted[..., None], psurf, bare)
    h = 0.00012 * mid + 0.00012 * fine - 0.0015 * pores - 0.0012 * joint + 0.0006 * fin + pstep[row, col]
    h_bare = h - 0.009 * hole - 0.0022 * cone + 0.0004 * eff
    h_paint = h - 0.0008 * plug + 0.00045 * (1 - top_off) + 0.00015 * (top_off - peel)
    hgt = np.where(painted, h_paint, h_bare)
    r_bare = np.clip(0.9 + 0.05 * pores - 0.2 * wl + 0.05 * eff - 0.12 * runs, 0.05, 1)
    r_paint = np.clip(0.48 + 0.15 * chalk + 0.2 * grime + 0.1 * scuff, 0, 1)
    r_paint = lin(lin(r_paint, 0.75, top_off), 0.9, peel)
    rough = np.where(painted, r_paint, r_bare)
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
    seed = [300]
    def nz(shape, beta, aniso=1.0, sigma_m=0.0):
        seed[0] += 1
        return fr(shape, beta, seed[0], aniso, sigma_m)
    # ---- Betonkern: Zuschlag, Poren, Rostspuren der Eisen (gleiches Raster wie die Bewehrung) ----
    sl, X, Z, S, hh = region("kern")
    paste = hexc("#7b7871") * (0.9 + 0.08 * nz(S, 0.9)[..., None])
    st1 = nz(S, 0.3, sigma_m=0.003)
    st2 = nz(S, 0.25, sigma_m=0.0012)
    stones = sm(0.75, 1.05, st1)
    grit = sm(1.0, 1.4, st2) * (1 - stones)
    tint = nz(S, 0.5, sigma_m=0.004)
    stone_c = mix(hexc("#a19b90"), hexc("#686460"), sm(-1.0, 1.0, tint))
    stone_c = mix(stone_c, hexc("#a68d72"), 0.35 * sm(0.8, 1.6, nz(S, 0.4, sigma_m=0.004)))
    a = mix(paste, stone_c, 0.85 * stones)
    a = mix(a, hexc("#b3ada1"), 0.4 * grit)
    pores = sm(1.9, 2.6, nz(S, 0.2, sigma_m=0.0012))
    a = a * (1 - 0.55 * pores)[..., None]
    fxb = np.mod(X, RASTER)
    dxb = np.minimum(fxb, RASTER - fxb)
    fzb = np.mod(Z - 0.11, RASTER)
    dzb = np.minimum(fzb, RASTER - fzb)
    track = np.maximum(sm(0.013, 0.004, dxb), sm(0.013, 0.004, dzb))
    rsrc = track * sm(0.2, 1.2, nz(S, 0.8))
    rr = np.clip(np.maximum(rsrc, 0.6 * drip_pad(rsrc, 0.2)), 0, 1)
    rc = mix(hexc("#55301d"), hexc("#8d5630"), sm(-1.0, 1.4, nz(S, 0.6)))
    a = mix(a, rc, 0.4 * rr)
    damp = sm(0.2, 2.0, nz(S, 1.3))
    alb[sl] = a * (1 - 0.18 * damp)[..., None]
    hgt[sl] = 0.002 * stones * (0.7 + 0.3 * st1) + 0.0005 * st2 - 0.002 * pores - 0.0025 * track
    rgh[sl] = 0.92 - 0.12 * damp
    # ---- Rissflanken ----
    sl, X, Z, S, hh = region("riss")
    q = nz(S, 0.9)
    alb[sl] = mix(hexc("#2b2926"), hexc("#68655d"), sm(-0.8, 1.6, q)) * (0.85 + 0.15 * nz(S, 0.4)[..., None])
    hgt[sl] = 0.002 * q + 0.001 * nz(S, 0.5)
    rgh[sl] = 0.93
    # ---- Kratzer und Strichlisten: heller Betonstaub, Riefen laengs ----
    sl, X, Z, S, hh = region("kratzer")
    st = nz(S, 0.5, aniso=0.08)
    alb[sl] = mix(hexc("#8a877f"), hexc("#b0ada3"), sm(-1.0, 1.5, st)) * (0.92 + 0.08 * nz(S, 0.3)[..., None])
    hgt[sl] = 0.0004 * st
    rgh[sl] = 0.9
    # ---- massiver Stahl: dunkel gestrichen, Rost an den Kanten, Narben, blanke Stellen ----
    for name in ("stahl_24", "stahl_10", "stahl_07", "stahl_05", "stahl_03"):
        sl, X, Z, S, hh = region(name)
        d = np.minimum(Z, hh - Z)
        edge = sm(0.012, 0.0, d - 0.008 * nz(S, 1.0))
        pits = sm(1.8, 2.5, nz(S, 0.3, sigma_m=0.0015))
        blot = sm(0.9, 1.9, nz(S, 1.2))
        streak = sm(1.2, 2.4, nz(S, 0.9, aniso=0.15))
        rust = np.clip(edge + blot + 0.5 * pits + 0.35 * streak, 0, 1)
        worn = sm(2.0, 2.6, nz(S, 0.5, aniso=0.1)) * (1 - rust)
        paint = hexc("#3e4340") * (0.88 + 0.1 * nz(S, 1.3)[..., None])
        rc = mix(hexc("#47281a"), hexc("#7a4a2d"), sm(-1.0, 1.5, nz(S, 0.6)))
        a = mix(paint, hexc("#6d6c68"), worn)
        alb[sl] = mix(a, rc, rust)
        hgt[sl] = 0.0004 * rust * nz(S, 0.4) - 0.0006 * pits - 0.0001 * worn
        rgh[sl] = np.clip(0.55 + 0.38 * rust - 0.15 * worn, 0, 1)
        met[sl] = 0.9 * worn
    # ---- Betonsockel: dunkler, Schmutz am Boden, Farbspritzer oben, Fase abgestossen ----
    sl, X, Z, S, hh = region("sockel")
    c = hexc("#76736c") * (0.9 + 0.08 * nz(S, 1.2)[..., None] + 0.03 * nz(S, 0.3)[..., None])
    pores = sm(2.0, 2.7, nz(S, 0.15, sigma_m=0.0012))
    grime = np.clip(sm(0.05, 0.0, Z) + 0.5 * sm(0.4, 2.2, nz(S, 1.3)), 0, 1)
    c = c * (1 - 0.45 * grime - 0.4 * pores)[..., None]
    splash = sm(2.3, 2.9, nz(S, 0.2, sigma_m=0.0018)) * sm(0.085, 0.11, Z)
    c = mix(c, hexc("#5f6e5f"), 0.8 * splash)
    chips = sm(1.9, 2.5, nz(S, 0.5)) * sm(0.08, 0.095, Z) * sm(0.115, 0.1, Z)
    alb[sl] = mix(c, hexc("#9a968c"), 0.5 * chips)
    hgt[sl] = 0.0004 * nz(S, 0.6) - 0.0015 * pores - 0.0012 * chips
    rgh[sl] = 0.9
    # ---- dicke Stahlrohre und Schellen: dunkelgrau gestrichen, Rost ----
    sl, X, Z, S, hh = region("rohr")
    blot = sm(0.8, 1.8, nz(S, 1.1))
    band = sm(1.4, 2.2, nz(S, 0.7, aniso=0.2))
    pits = sm(1.9, 2.6, nz(S, 0.3, sigma_m=0.0015))
    rust = np.clip(blot + 0.5 * band + 0.4 * pits, 0, 1)
    paint = hexc("#4c524d") * (0.9 + 0.08 * nz(S, 1.3)[..., None])
    paint = mix(paint, hexc("#77807a"), 0.25 * sm(0.3, 2.0, nz(S, 1.5)))
    rc = mix(hexc("#4a2a1a"), hexc("#7c4a2c"), sm(-1.0, 1.5, nz(S, 0.6)))
    alb[sl] = mix(paint, rc, rust)
    hgt[sl] = 0.0005 * rust * nz(S, 0.4) - 0.0005 * pits
    rgh[sl] = np.clip(0.5 + 0.4 * rust, 0, 1)
    # ---- Bewehrung: Rippenstahl, verrostet ----
    sl, X, Z, S, hh = region("rost")
    ribs = sm(0.55, 0.9, 0.5 + 0.5 * np.sin(2 * math.pi * (X / 0.0085 + Z / 0.06)))
    r = nz(S, 0.8)
    flake = sm(1.4, 2.0, nz(S, 0.4))
    alb[sl] = mix(hexc("#472716"), hexc("#86512e"), sm(-1.2, 1.4, r)) * (1 - 0.25 * flake)[..., None] * (0.85 + 0.2 * ribs)[..., None]
    hgt[sl] = 0.0006 * ribs + 0.0003 * nz(S, 0.3) - 0.0003 * flake
    rgh[sl] = 0.88
    # ---- Schaltkasten aus Blech: grau, Rost; Vorderseite einmalig bei U 0,5 ----
    sl, X, Z, S, hh = region("kasten")
    paint = hexc("#9d9a8e") * (0.9 + 0.07 * nz(S, 1.3)[..., None])
    dirt = sm(0.3, 2.2, nz(S, 1.2))
    blot = sm(1.3, 2.1, nz(S, 1.0))
    scr = np.clip(sm(2.1, 2.9, nz(S, 0.6, aniso=0.1)), 0, 1)
    rc = mix(hexc("#55301e"), hexc("#83532f"), sm(-1.0, 1.5, nz(S, 0.6)))
    a = mix(paint, hexc("#5c5a52"), 0.4 * dirt)
    a = mix(a, hexc("#c4c1b6"), 0.4 * scr)
    a = mix(a, rc, 0.85 * blot)
    h_ = -0.0002 * scr + 0.0003 * blot * nz(S, 0.4)
    r_ = 0.5 + 0.2 * dirt + 0.35 * blot
    W, HH = KASTEN_W, KASTEN_H
    px, pz = X - 2.0, Z - 0.005
    inside = (px >= 0) & (px < W) & (pz >= 0) & (pz < HH)
    dm = np.minimum(np.minimum(px, W - px), np.minimum(pz, HH - pz))
    gap = inside & (np.abs(dm - 0.013) < 0.0012)
    slots = inside & (np.abs(px - W / 2) < 0.08) & (pz > 0.05) & (pz < 0.14) & (np.mod(pz - 0.05, 0.018) < 0.007)
    lips = inside & (np.abs(px - W / 2) < 0.08) & (pz > 0.05) & (pz < 0.15) & (np.mod(pz - 0.05, 0.018) >= 0.007) & (np.mod(pz - 0.05, 0.018) < 0.0095)
    tcx, tcz, tsd = W / 2, 0.33, 0.1
    tri = inside & tri_mask(px, pz, tcx, tcz, tsd)
    tri_in = inside & tri_mask(px, pz, tcx, tcz + 0.0035, tsd - 0.016)
    bolt_pts = [(0.006, 0.027), (-0.010, 0.000), (0.000, 0.000), (-0.008, -0.024), (0.011, 0.006), (0.001, 0.006), (0.010, 0.027)]
    bolt = tri_in & poly_mask(px, pz, [(tcx + bx, tcz - 0.004 + bz * 0.9) for bx, bz in bolt_pts])
    plate = inside & (np.abs(px - W / 2) < 0.065) & (np.abs(pz - 0.245) < 0.018)
    screws = plate & ((np.hypot(px - (W / 2 - 0.056), pz - 0.245) < 0.0025) | (np.hypot(px - (W / 2 + 0.056), pz - 0.245) < 0.0025))
    lock = inside & (np.hypot(px - (W - 0.035), pz - 0.22) < 0.008)
    lsrc = (lock | (gap & (pz < 0.02))).astype(np.float32)
    lrun = np.clip(drip_pad(lsrc, 0.12), 0, 1) * inside
    fp = mix(paint, hexc("#5c5a52"), 0.25 * dirt)
    fp = mix(fp, rc, 0.45 * blot)
    fp = mix(fp, rc, 0.6 * lrun)
    fp = np.where(gap[..., None], hexc("#1d1c1a"), fp)
    fp = np.where(slots[..., None], hexc("#151514"), fp)
    fp = np.where(lips[..., None], fp * 1.15, fp)
    fp = np.where(plate[..., None], mix(hexc("#c3c0b5"), hexc("#8e8a7e"), 0.4 * dirt), fp)
    fp = np.where(screws[..., None], hexc("#55534d"), fp)
    fp = np.where((tri & ~tri_in)[..., None], hexc("#1e1e1c"), fp)
    fp = np.where((tri_in & ~bolt)[..., None], mix(hexc("#c9a22b"), hexc("#8e7a3e"), 0.4 * dirt), fp)
    fp = np.where(bolt[..., None], hexc("#1e1e1c"), fp)
    fp = np.where(lock[..., None], hexc("#2a2a28"), fp)
    a = np.where(inside[..., None], fp, a)
    h_ = np.where(inside, -0.001 * gap - 0.002 * slots + 0.0006 * lips + 0.0004 * plate + 0.0002 * tri - 0.0015 * lock, h_)
    r_ = np.where(inside, np.where(plate, 0.4, np.where(tri_in, 0.45, 0.5 + 0.2 * dirt + 0.3 * lrun)), r_)
    alb[sl], hgt[sl], rgh[sl] = a, h_, r_
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
R_KEEP, R_WM, R_WP, R_TOP, R_ENDX, R_REVX, R_REVZ, R_PLAN, R_METAL, R_CORE, R_BOXFRONT, R_SHARD, R_PLANAX, R_PLANFIX = range(14)
PLAN_REG = ["kern", "riss", "kratzer", "stahl_24", "stahl_10", "stahl_07", "stahl_05", "stahl_03", "sockel",
            "rohr", "rost", "kasten"]

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
        if reg_name == "kasten":
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
            s = 1 if f.normal.x > 0 else -1
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (0.5 + s * UVS * p.y, UVS * p.z)
        elif r == R_REVX:
            s = 1 if f.normal.x > 0 else -1
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (0.25 + s * UVS * p.y, UVS * p.z)
        elif r == R_REVZ:
            # waagerechte Flaechen: Zeile im Wandbild frei waehlbar (par[0]), z. B. gestrichen unter 1,2 m
            zref = f[pc.par][0]
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (wall_u(p.x, -1), UVS * (zref + 0.02 + (p.y + T2)))
        elif r == R_CORE:
            # Boden einer Abplatzung: Wandraster bleibt erhalten, Rostspuren liegen auf den Eisen
            side = int(f[pc.par][0])
            zb = f[pc.par][1]
            z0, z1 = REG["kern"]
            for l in f.loops:
                p = l.vert.co
                v = z0 + 0.01 + p.z - zb
                if not (z0 <= v <= z1):
                    raise RuntimeError(f"{pc.name}: Kern laeuft ueber ({v:.3f})")
                l[uv].uv = (wall_u(p.x, side), UVS * v)
        elif r == R_BOXFRONT:
            bx, bz0, mir = f[pc.par]
            for l in f.loops:
                p = l.vert.co
                du = (bx - p.x) if mir < 0 else (p.x - bx)
                l[uv].uv = (0.5 + UVS * du, UVS * (REG["kasten"][0] + 0.005 + (p.z - bz0)))
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
            # Farbschuppe: Oberseite aus dem gestrichenen Teil des Wandbilds
            co = planar_coords(f)
            umin = min(c[0] for c in co)
            vmin = min(c[1] for c in co)
            u0 = pc.rng.random()
            vz = 0.2 + pc.rng.random() * 0.75
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

def recess(pc, loop, side, depth_out, depth_in, mat_bottom, rule_bottom, par_bottom, rim_reg, reg_bottom="kern", holes=()):
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
            if prof[0][0] != 0:
                P = [Vector((x, yy(0), prof[0][1]))] + P
            if prof[-1][0] != 0:
                P = P + [Vector((x, yy(0), prof[-1][1]))]
            pc.face(P, 1, R_PLANFIX, (sgn, 0, 0), reg=PLAN_REG.index(reg), par=(0.37 if side > 0 else 0.13, 0, 0))

def body(pc, outer, holes_m, holes_p, top=True, ends=True, xr=(-W2, W2)):
    pc.tess(outer, holes_m, -T2, 0, R_WM, (0, -1, 0))
    pc.tess(outer, holes_p, T2, 0, R_WP, (0, 1, 0))
    if top:
        pc.face([Vector((xr[0], -T2, H)), Vector((xr[1], -T2, H)), Vector((xr[1], T2, H)), Vector((xr[0], T2, H))], 0, R_TOP, (0, 0, 1))
    if ends:
        for x, s in ((xr[0], -1), (xr[1], 1)):
            pc.face([Vector((x, -T2, 0)), Vector((x, T2, 0)), Vector((x, T2, H)), Vector((x, -T2, H))], 0, R_ENDX, (s, 0, 0))

def noisy_loop(cx, cz, rx, rz, npts, seed, amp=0.18):
    pts = []
    for k in range(npts):
        a = 2 * math.pi * k / npts
        c, s = math.cos(a), math.sin(a)
        r = 1 + amp * noise.noise(Vector((c * 1.6, s * 1.6, seed))) + 0.45 * amp * noise.noise(Vector((c * 5, s * 5, seed + 3))) \
            + 0.22 * amp * noise.noise(Vector((c * 16, s * 16, seed + 7)))
        pts.append((cx + c * rx * r, cz + s * rz * r))
    return pts

def chunk(pc, center, size, seed, reg="kern", subdiv=1):
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
    """Scherbe oder Farbschuppe: Oberseite aus dem Wand-Material, Kanten Bruch."""
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
    pc.face(bot[::-1], 1, R_PLAN, (0, 0, -1), reg=PLAN_REG.index("kern"))
    c = sum(top, Vector()) / len(top)
    for i in range(len(P)):
        j = (i + 1) % len(P)
        Q = [bot[i], bot[j], top[j], top[i]]
        mid = (bot[i] + top[j]) / 2
        pc.face(Q, 1, R_PLAN, mid - c, reg=PLAN_REG.index("kern"))

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

# ---------- Bausteine Gefaengnis ----------
SOCKEL_PROF = [(PLD, 0.0), (PLD, PLH - 0.012), (PLD - 0.012, PLH), (0.0, PLH)]

def strips(pc, side, spans):
    for a, b in spans:
        profile_strip(pc, SOCKEL_PROF, a, b, side, "sockel")

def centroid(loop):
    return sum(p[0] for p in loop) / len(loop), sum(p[1] for p in loop) / len(loop)

def inset_loop(loop, d, amp, seed):
    """Umriss nach innen ziehen (sternfoermig um den Schwerpunkt), der Abstand schwankt."""
    cx, cz = centroid(loop)
    out = []
    for x, z in loop:
        ux, uz = x - cx, z - cz
        r = math.hypot(ux, uz) or 1.0
        dd = d * (1 + amp * noise.noise(Vector((x * 11, z * 11, seed))))
        f = max(0.3, (r - dd) / r)
        out.append((cx + ux * f, cz + uz * f))
    return out

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

def point_in(poly, x, z):
    inside = False
    n = len(poly)
    for i in range(n):
        (x0, z0), (x1, z1) = poly[i], poly[(i + 1) % n]
        if (z0 > z) != (z1 > z) and x < x0 + (z - z0) / (z1 - z0) * (x1 - x0):
            inside = not inside
    return inside

def _cross(p1, p2, q1, q2):
    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return o(q1, q2, p1) * o(q1, q2, p2) < 0 and o(p1, p2, q1) * o(p1, p2, q2) < 0

def check_holes(name, holes, gap=0.003):
    """Loecher einer Wandseite: keine Ueberschneidung, alles mindestens 40 cm von den Seitenkanten."""
    boxes = []
    for h in holes:
        xs, zs = [p[0] for p in h], [p[1] for p in h]
        if min(xs) < -W2 + EDGE - 1e-6 or max(xs) > W2 - EDGE + 1e-6:
            raise RuntimeError(f"{name}: Loch zu nah an der Kante ({min(xs):.3f} .. {max(xs):.3f})")
        boxes.append((min(xs) - gap, max(xs) + gap, min(zs) - gap, max(zs) + gap))
    for i in range(len(holes)):
        for j in range(i + 1, len(holes)):
            a, b = boxes[i], boxes[j]
            if a[1] < b[0] or b[1] < a[0] or a[3] < b[2] or b[3] < a[2]:
                continue
            A, B = holes[i], holes[j]
            hit = point_in(A, *B[0]) or point_in(B, *A[0])
            for k in range(len(A)):
                if hit:
                    break
                for m in range(len(B)):
                    if _cross(A[k], A[(k + 1) % len(A)], B[m], B[(m + 1) % len(B)]):
                        hit = True
                        break
            if hit:
                raise RuntimeError(f"{name}: Loecher {i} und {j} schneiden sich")

def drop_back(pc, faces, side=1):
    """Rueckseite eines Anbauteils, die auf der Wandflaeche liegt, entfernen (nie sichtbar, kein Flimmern)."""
    dead = []
    for f in faces:
        if not f.is_valid:
            continue
        f.normal_update()
        if f.normal.y * side < -0.99 and abs(f.calc_center_median().y - side * T2) < 1e-4:
            dead.append(f)
    bmesh.ops.delete(pc.bm, geom=dead, context="FACES_ONLY")

def spall(pc, loop, side, depth=SPALL, bars=True, slope=0.03, seed=1.0):
    """Abplatzung in zwei Stufen: Farbe und Betondeckung brechen unregelmaessig aus;
    ist sie tief genug, liegt die Bewehrung frei."""
    mid = inset_loop(loop, slope * 0.45, 0.9, seed + 0.37)
    inner = inset_loop(mid, slope * 0.55, 0.6, seed)
    zb = math.floor((min(p[1] for p in inner) - 0.015) / RASTER) * RASTER
    yi = side * (T2 - depth)
    ym = [side * (T2 - depth * (0.32 + 0.26 * (0.5 + 0.5 * noise.noise(Vector((x * 7, z * 7, seed + 1.9)))))) for x, z in mid]
    n = len(loop)
    ccw = loop_area(loop) > 0
    for i in range(n):
        j = (i + 1) % n
        want = edge_inward(loop, i, ccw) + Vector((0, side * 0.6, 0))
        P = [Vector((loop[i][0], side * T2, loop[i][1])), Vector((loop[j][0], side * T2, loop[j][1])),
             Vector((mid[j][0], ym[j], mid[j][1])), Vector((mid[i][0], ym[i], mid[i][1]))]
        pc.face(P, 1, R_PLAN, want, reg=PLAN_REG.index("kern"))
        P = [Vector((mid[i][0], ym[i], mid[i][1])), Vector((mid[j][0], ym[j], mid[j][1])),
             Vector((inner[j][0], yi, inner[j][1])), Vector((inner[i][0], yi, inner[i][1]))]
        pc.face(P, 1, R_PLAN, want, reg=PLAN_REG.index("kern"))
    pc.tess(inner, [], yi, 1, R_CORE, (0, side, 0), par=(side, zb, 0), reg=PLAN_REG.index("kern"))
    if bars and depth >= DECK + 2 * BAR_R:
        rebar_mesh(pc, inner, side, seed)
    return loop

def rebar_mesh(pc, poly, side, seed):
    """Freiliegende Bewehrung, nicht wie gezeichnet: manche Eisen stecken noch im Beton, manche sind
    durchgerostet (Enden leicht nach vorn gebogen), die vorderen sind ausgebeult, die hinteren nur stellenweise frei."""
    rng = random.Random(int(seed * 1000) + (7 if side > 0 else 3))
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    def bar(pts, r, caps):
        tube(pc, [Vector(p) for p in pts], r, "rost", seg=5, caps=caps, uoff=rng.random())
    for k in range(math.ceil((min(zs) - 0.1) / RASTER), math.floor((max(zs) - 0.1) / RASTER) + 1):
        zc = 0.1 + k * RASTER
        for a, b in line_hits(poly, "h", zc):
            if b - a < 0.05:
                continue
            roll = rng.random()
            if roll < 0.15:
                continue
            r = BAR_R * rng.uniform(0.75, 1.0)
            y0 = side * BAR_H
            if roll < 0.45 and b - a > 0.3:
                g0 = a + rng.uniform(0.35, 0.6) * (b - a)
                g1 = g0 + rng.uniform(0.03, 0.08)
                yb1, yb2 = side * (BAR_H + rng.uniform(0.003, 0.008)), side * (BAR_H + rng.uniform(0.003, 0.008))
                bar([(a - 0.04, y0, zc), ((a + g0) / 2, side * (BAR_H + rng.uniform(0, 0.004)), zc + rng.uniform(-0.004, 0.004)),
                     (g0, yb1, zc + rng.uniform(-0.01, 0.006))], r, True)
                bar([(g1, yb2, zc + rng.uniform(-0.01, 0.006)), ((g1 + b) / 2, side * (BAR_H + rng.uniform(0, 0.004)), zc),
                     (b + 0.04, y0, zc)], r, True)
            else:
                bar([(a - 0.04, y0, zc), ((a + b) / 2, side * (BAR_H + rng.uniform(0.0, 0.006)), zc + rng.uniform(-0.005, 0.005)),
                     (b + 0.04, y0, zc)], r, False)
    for i in range(math.ceil(min(xs) / RASTER), math.floor(max(xs) / RASTER) + 1):
        xc = i * RASTER
        for a, b in line_hits(poly, "v", xc):
            if b - a < 0.2 or rng.random() < 0.45:
                continue
            bar([(xc, side * BAR_V, a - 0.04), (xc, side * BAR_V, b + 0.04)], BAR_R * rng.uniform(0.75, 1.0), False)

def scratch(pc, p0, p1, side, width=0.003, depth=0.0025, seed=0, wob=0.002, n=3):
    """Eingeritzte Linie als feine V-Nut."""
    rng = random.Random(seed)
    dx, dz = p1[0] - p0[0], p1[1] - p0[1]
    l = math.hypot(dx, dz)
    pts = []
    for k in range(n):
        t = k / (n - 1)
        x, z = p0[0] + dx * t, p0[1] + dz * t
        if 0 < k < n - 1:
            o = rng.uniform(-wob, wob)
            x, z = x - dz / l * o, z + dx / l * o
        pts.append((x, z))
    if n == 2:
        wid = [width * 0.8, width * 0.8]
    else:
        wid = [width * 0.35] + [width * rng.uniform(0.8, 1.1) for _ in range(n - 2)] + [width * 0.35]
    return groove(pc, pts, wid, side, depth, reg="kratzer")

def tally(pc, x0, z0, side, groups, extra, seed, h=0.1, dx=0.017, gap=0.032):
    """Strichliste: Gruppen aus vier Strichen mit Querstrich (in Stuecken, damit sich die Nuten nicht schneiden)."""
    rng = random.Random(seed)
    holes = []
    x = x0
    for g in range(groups + (1 if extra else 0)):
        k = 4 if g < groups else extra
        strokes = []
        for s in range(k):
            xa = x + rng.uniform(-0.002, 0.002)
            bot = z0 + rng.uniform(-0.008, 0.006)
            top = z0 + h + rng.uniform(-0.008, 0.008)
            lean = rng.uniform(-0.008, 0.008)
            holes.append(scratch(pc, (xa, bot), (xa + lean, top), side, seed=seed * 1000 + g * 10 + s, wob=0.0006))
            strokes.append((xa, bot, xa + lean, top))
            x += dx
        if g < groups:
            A = (strokes[0][0] - 0.014, z0 + 0.022)
            B = (strokes[-1][0] + 0.014, z0 + h - 0.02)
            ax_, az_ = B[0] - A[0], B[1] - A[1]
            ts = []
            for (xa, bot, xt, top) in strokes:
                bx_, bz_ = xt - xa, top - bot
                det = -ax_ * bz_ + bx_ * az_
                ts.append((-(xa - A[0]) * bz_ + bx_ * (bot - A[1])) / det)
            L = math.hypot(ax_, az_)
            clear = 0.0042 / L
            cuts = [0.0] + sorted(ts) + [1.0]
            for i in range(len(cuts) - 1):
                t0 = cuts[i] + (clear if i > 0 else 0.0)
                t1 = cuts[i + 1] - (clear if i < len(cuts) - 2 else 0.0)
                if t1 - t0 < 0.004 / L:
                    continue
                P0 = (A[0] + ax_ * t0, A[1] + az_ * t0)
                P1 = (A[0] + ax_ * t1, A[1] + az_ * t1)
                holes.append(scratch(pc, P0, P1, side, width=0.0028, seed=seed * 1000 + g * 10 + 7 + i, n=2))
        x += gap
    return holes

def scratch_cluster(pc, x0, z0, side, count, length, angle, seed, spacing=0.016):
    """Kratzspuren: mehrere fast parallele, leicht gebogene Riefen."""
    rng = random.Random(seed)
    ca, sa = math.cos(angle), math.sin(angle)
    holes = []
    for i in range(count):
        off = i * spacing + rng.uniform(-0.003, 0.003)
        L = length * rng.uniform(0.6, 1.0)
        s0 = rng.uniform(0, length - L)
        cx, cz = x0 - sa * off + ca * s0, z0 + ca * off + sa * s0
        holes.append(scratch(pc, (cx, cz), (cx + ca * L, cz + sa * L), side, width=rng.uniform(0.002, 0.0035),
                             depth=0.002, seed=seed * 50 + i, wob=0.003, n=4))
    return holes

def rivet(pc, x, y, z, side, r0=0.009, r1=0.0055, h=0.006, seg=6):
    """Nietkopf auf einer Flaeche bei y, der Kopf zeigt in Richtung side."""
    c = Vector((x, y, z))
    base, top = [], []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        base.append(pc.bm.verts.new((x + r0 * math.cos(a), y, z + r0 * math.sin(a))))
        top.append(pc.bm.verts.new((x + r1 * math.cos(a), y + side * h, z + r1 * math.sin(a))))
    reg = PLAN_REG.index("stahl_03")
    for k in range(seg):
        k2 = (k + 1) % seg
        f = pc.bm.faces.new((base[k], base[k2], top[k2], top[k]))
        pc.mark([f], 1, R_PLAN, reg, smooth=True)
        f.normal_update()
        mid = (base[k].co + base[k2].co) / 2 - c
        if f.normal.dot(mid + Vector((0, side * 0.3 * r0, 0))) < 0:
            f.normal_flip()
    f = pc.bm.faces.new(top)
    pc.mark([f], 1, R_PLAN, reg)
    f.normal_update()
    if f.normal.y * side < 0:
        f.normal_flip()

def floor_debris(pc, x0, x1, side, n_chunks, n_flakes, seed):
    """Betonbrocken und Farbschuppen am Fuss der Wand, hoechstens 12 cm vor der Wandflaeche."""
    rng = random.Random(seed)
    for i in range(n_chunks):
        x = rng.uniform(x0, x1)
        s = rng.uniform(0.012, 0.026)
        y = side * (T2 + rng.uniform(0.035, 0.06))
        chunk(pc, (x, y, s * 0.5), (s * 1.4, s, s * 0.7), seed * 10 + i, "kern", subdiv=0)
    for i in range(n_flakes):
        x = rng.uniform(x0, x1)
        y = side * rng.uniform(T2 + 0.02, T2 + 0.05)
        shard(pc, x, y, seed * 100 + i, size=(0.015, 0.035), thick=0.0012)

def rubble(pc, side, xc, seed):
    """Schuttkegel bis 60 cm vor der Wand: unregelmaessiger Fuss, dicke Betonbrocken (manche mit Eisen), Farbschuppen."""
    rng = random.Random(int(seed * 100) + (5 if side > 0 else 1))
    nxp, nyp = 14, 7
    rx, ry, hmax = 0.82, 0.55, 0.24
    V = []
    for i in range(nxp + 1):
        sx = 2 * i / nxp - 1
        reach = min(1.0, 0.8 + 0.2 * noise.noise(Vector((sx * 2.2, side * 5.0, seed))))
        row = []
        for j in range(nyp + 1):
            t = j / nyp
            half = rx * math.sqrt(max(0.0, 1 - (0.8 * t) ** 2)) * (1 + 0.1 * noise.noise(Vector((t * 3.0, side * 3.0, seed + 1.4))))
            x = xc + half * sx
            yd = 0.004 + ry * reach * t
            fall = max(0.0, 1 - sx * sx) * max(0.0, 1 - t ** 1.4)
            fall *= 1 + 0.3 * noise.noise(Vector((x * 2.5, yd * 2.5, side * 3 + seed)))
            lump = 0.04 * noise.noise(Vector((x * 8, yd * 8, side + seed))) + 0.015 * noise.noise(Vector((x * 22, yd * 22, side + seed + 5)))
            z = hmax * fall + (lump * min(1.0, 4 * fall) if 0 < i < nxp and j < nyp else 0)
            row.append(Vector((x, side * (T2 + yd), max(0.0, z))))
        V.append(row)
    for i in range(nxp):
        for j in range(nyp):
            P = [V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]]
            if max(p.z for p in P) < 0.002:
                continue
            pc.face(P, 1, R_PLAN, (0, side * 0.3, 1), reg=PLAN_REG.index("kern"))
    idx = lambda i, j: i * (nyp + 1) + j
    tree = BVHTree.FromPolygons([v for row in V for v in row],
                                [(idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)) for i in range(nxp) for j in range(nyp)])
    def heap_z(x, yd):
        hit = tree.ray_cast(Vector((x, side * (T2 + yd), 2.0)), Vector((0, 0, -1)))
        return max(0.0, hit[0].z) if hit[0] is not None else 0.0
    for k in range(7):
        x = xc + rng.uniform(-0.6, 0.6)
        yd = rng.uniform(0.06, 0.34)
        s = rng.uniform(0.06, 0.1)
        c = Vector((x, side * (T2 + yd), heap_z(x, yd) + s * 0.35))
        chunk(pc, c, (s * 1.35, s, s * 0.75), 60 + k + (20 if side > 0 else 0), "kern")
        if k % 2 == 0:
            a = rng.uniform(0, math.tau)
            d = Vector((math.cos(a), math.sin(a) * 0.5, rng.uniform(0.1, 0.5))).normalized()
            p1 = c + d * (s * 1.1 + rng.uniform(0.05, 0.12))
            p1.y = max(-0.68, min(0.68, p1.y))
            p1.z = max(0.01, p1.z)
            tube(pc, [c.copy(), p1], 0.005, "rost", seg=5, caps=True, uoff=rng.random())
    for k in range(10):
        x = xc + rng.uniform(-0.7, 0.7)
        yd = rng.uniform(0.03, 0.46)
        s = rng.uniform(0.015, 0.035)
        chunk(pc, (x, side * (T2 + yd), heap_z(x, yd) * 0.95 + s * 0.3), (s * 1.3, s, s * 0.7),
              120 + k + (30 if side > 0 else 0), "kern", subdiv=0)
    for k in range(6):
        x = xc + rng.uniform(-0.7, 0.7)
        yd = rng.uniform(0.04, 0.42)
        shard(pc, x, side * (T2 + yd), 300 + k + (50 if side > 0 else 0), size=(0.02, 0.045),
              zbase=max(0.0, heap_z(x, yd) - 0.003), thick=0.0015)

def through_hole_outline(seed=2.7, N=96):
    """Unregelmaessiger Umriss an den Wandflaechen: 1,44 m breit, 1,32 m hoch, Unterkante bei 0,96 m."""
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
    cz = 0.96 + 0.66
    return [(p[0] * sx, cz + p[1] * sz) for p in pts]

def hole_bars(pc, hole, seed, count=26, n_long=14):
    """Viele verbogene Eisen: Stummel aller vier Lagen ragen aus der Bruchkante, die langen sind aus der Wand gebogen."""
    rng = random.Random(seed)
    xs, zs = [p[0] for p in hole], [p[1] for p in hole]
    cands = []
    for side in (-1, 1):
        for k in range(math.ceil((min(zs) - 0.1) / RASTER), math.floor((max(zs) - 0.1) / RASTER) + 1):
            zc = 0.1 + k * RASTER
            for a, b in line_hits(hole, "h", zc):
                cands += [(side, "h", zc, a, 1), (side, "h", zc, b, -1)]
        for i in range(math.ceil(min(xs) / RASTER), math.floor(max(xs) / RASTER) + 1):
            xc = i * RASTER
            for a, b in line_hits(hole, "v", xc):
                cands += [(side, "v", xc, a, 1), (side, "v", xc, b, -1)]
    rng.shuffle(cands)
    for n_, (side, ax, c, e, d) in enumerate(cands[:count]):
        y = side * (BAR_H if ax == "h" else BAR_V)
        if ax == "h":
            p_in, p_rim, dirv = Vector((e - d * 0.07, y, c)), Vector((e, y, c)), Vector((d, 0, 0))
        else:
            p_in, p_rim, dirv = Vector((c, y, e - d * 0.07)), Vector((c, y, e)), Vector((0, 0, d))
        if n_ >= n_long:
            tube(pc, [p_in, p_rim + dirv * rng.uniform(0.02, 0.07)], BAR_R, "rost", seg=5, caps=True, uoff=rng.random())
            continue
        p1 = p_rim + dirv * rng.uniform(0.06, 0.12)
        p2 = p1 + Vector((0, side * rng.uniform(0.085, 0.11), 0)) + dirv * rng.uniform(0.0, 0.05) + Vector((0, 0, -rng.uniform(0.0, 0.06)))
        p3 = p2 + Vector((rng.uniform(-0.06, 0.06), side * rng.uniform(0.0, 0.03), -rng.uniform(0.08, 0.22)))
        pts = [p_in, p1, p2, p3]
        for p in pts:
            p.y = max(-0.2, min(0.2, p.y))
            p.z = max(0.02, p.z)
        tube(pc, fillet(pts, rng.uniform(0.03, 0.05), 2), BAR_R, "rost", seg=5, caps=True, uoff=rng.random())

def door_frame(pc):
    """Zarge aus massivem Stahl: Futter in der Laibung, Flansche beidseitig 1,4 cm stark, Nietkoepfe bis 2 cm vor der Wand."""
    x0, x1, zt = -0.65, 0.65, 2.2
    pl, fl, ft = 0.008, 0.09, 0.014
    yf = T2 + ft
    for a, b in ((x0 - fl, x0 + pl), (x1 - pl, x1 + fl)):
        box_faces(pc, (a, -yf, 0.0), (b, yf, zt - pl), R_METAL, bevel=0.002, axis=(0, 0, 1))
    box_faces(pc, (x0 - fl, -yf, zt - pl), (x1 + fl, yf, zt + fl), R_METAL, bevel=0.002, axis=(1, 0, 0))
    # Anschlag auf der -Y-Seite
    st, ys0, ys1 = 0.03, -0.05, -0.02
    box_faces(pc, (x0 + pl, ys0, 0.0), (x0 + pl + st, ys1, zt - pl - st), R_METAL, axis=(0, 0, 1))
    box_faces(pc, (x1 - pl - st, ys0, 0.0), (x1 - pl, ys1, zt - pl - st), R_METAL, axis=(0, 0, 1))
    box_faces(pc, (x0 + pl, ys0, zt - pl - st), (x1 - pl, ys1, zt - pl), R_METAL, axis=(1, 0, 0))
    # schwere Baender
    for zc in (0.32, 1.92):
        tube(pc, [(x0 + pl + 0.018, -0.07, zc), (x0 + pl + 0.018, -0.07, zc + 0.16)], 0.016, "rohr", seg=8)
    # Nietkoepfe auf beiden Flanschen
    for side in (-1, 1):
        y = side * yf
        for xc in (x0 - fl / 2 + 0.004, x1 + fl / 2 - 0.004):
            z = 0.12
            while z < zt - 0.06:
                rivet(pc, xc, y, z, side)
                z += 0.16
            rivet(pc, xc, y, zt + fl / 2 - 0.004, side)
        x = -0.56
        while x <= 0.5601:
            rivet(pc, x, y, zt + fl / 2 - 0.004, side)
            x += 0.16

def pipe_clamp(pc, x, yc, zc, r):
    """Rohrschelle: Ring um das Rohr, Ohren mit Schrauben oben und unten, kurze Gewindestange zur Wandplatte."""
    rr = r + 0.004
    w = 0.015
    tube(pc, [(x - w, yc, zc), (x + w, yc, zc)], rr, "rohr", seg=12, caps=True, uoff=0.3)
    for s_ in (1, -1):
        za, zb = zc + s_ * (rr - 0.002), zc + s_ * (rr + 0.022)
        box_faces(pc, (x - w, yc - 0.0045, min(za, zb)), (x + w, yc + 0.0045, max(za, zb)), R_METAL, bevel=0.0015)
        zm = (za + zb) / 2 + s_ * 0.004
        box_faces(pc, (x - 0.007, yc + 0.0045, zm - 0.007), (x + 0.007, yc + 0.0105, zm + 0.007), R_METAL)
    tube(pc, [(x, T2 + 0.001, zc), (x, yc - rr + 0.002, zc)], 0.005, "rohr", seg=6, caps=False)
    drop_back(pc, box_faces(pc, (x - 0.03, T2, zc - 0.03), (x + 0.03, T2 + 0.006, zc + 0.03), R_METAL, bevel=0.002))

def schaltkasten(pc, xc, zc):
    """Verschlossener Schaltkasten aus Blech auf der +Y-Seite: Baender links, Vorhaengeschloss rechts, Leerrohr in die Wand."""
    bx0, bx1 = xc - KASTEN_W / 2, xc + KASTEN_W / 2
    bz0, bz1 = zc - KASTEN_H / 2, zc + KASTEN_H / 2
    y0, y1 = T2, T2 + KASTEN_T
    faces = box_faces(pc, (bx0, y0, bz0), (bx1, y1, bz1), R_PLAN, reg=PLAN_REG.index("kasten"), bevel=0.003)
    for f in faces:
        f.normal_update()
        if f.normal.y > 0.99:
            f[pc.rule] = R_BOXFRONT
            f[pc.par] = (bx1, bz0, -1)          # von +Y gesehen: Schild nicht gespiegelt
    drop_back(pc, faces)
    # Baender (von +Y gesehen links)
    for zh in (bz0 + 0.07, bz1 - 0.07):
        tube(pc, [(bx1 + 0.004, y1 - 0.01, zh - 0.025), (bx1 + 0.004, y1 - 0.01, zh + 0.025)], 0.006, "rohr", seg=6)
    # Lasche mit Vorhaengeschloss (rechts)
    yl = y1 - 0.018
    box_faces(pc, (bx0 - 0.012, yl - 0.005, zc + 0.01), (bx0, yl + 0.005, zc + 0.04), R_METAL, bevel=0.001)
    lx0, lx1 = bx0 - 0.034, bx0 - 0.004
    box_faces(pc, (lx0, yl - 0.009, zc - 0.035), (lx1, yl + 0.009, zc + 0.002), R_METAL, bevel=0.002)
    xa, xb = lx0 + 0.007, lx1 - 0.007
    sh = fillet([Vector((xa, yl, zc + 0.001)), Vector((xa, yl, zc + 0.034)), Vector((xb, yl, zc + 0.034)), Vector((xb, yl, zc + 0.001))], 0.006, 2)
    tube(pc, sh, 0.0035, "rohr", seg=5, caps=False)
    # Leerrohr nach oben, unter den Rohren in die Wand
    yc_ = T2 + 0.0125 + 0.003
    pts = fillet([Vector((xc, yc_, bz1 - 0.01)), Vector((xc, yc_, 2.92)), Vector((xc, T2 - 0.03, 2.92))], 0.04, 3)
    tube(pc, pts, 0.0125, "rohr", seg=8, caps=False)
    for zz in (2.0, 2.55):
        drop_back(pc, box_faces(pc, (xc - 0.02, T2, zz - 0.012), (xc + 0.02, yc_ + 0.0145, zz + 0.012), R_METAL))

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

# ======================= Die sieben Stuecke =======================
OUTER = rect(-W2, W2, 0, H)
FULL = [(-W2, W2)]

def wand_01():
    pc = Piece(f"{GEB}_wand_01")
    hm = tally(pc, -0.95, 0.82, -1, 4, 2, 11)
    hm.append(spall(pc, noisy_loop(0.85, 0.36, 0.15, 0.11, 30, 2.2, 0.25), -1, depth=0.02, bars=False, slope=0.012, seed=2.2))
    hp = scratch_cluster(pc, 0.15, 1.38, 1, 6, 0.3, -0.35, 12)
    hp.append(spall(pc, noisy_loop(-0.75, 2.62, 0.12, 0.1, 28, 3.3, 0.25), 1, depth=0.018, bars=False, slope=0.01, seed=3.3))
    check_holes(pc.name + " -Y", hm)
    check_holes(pc.name + " +Y", hp)
    body(pc, OUTER, hm, hp)
    for side in (-1, 1):
        strips(pc, side, FULL)
    return finish(pc)

def wand_02():
    pc = Piece(f"{GEB}_wand_02")
    hm, hp = [], []
    # -Y: grosse Abplatzung oben, zweite ueber der Farbkante, tiefer Riss rechts
    hm.append(spall(pc, noisy_loop(-0.4, 2.42, 0.82, 0.5, 60, 1.3, 0.2), -1, seed=1.3))
    hm.append(spall(pc, noisy_loop(0.88, 0.72, 0.42, 0.38, 48, 2.9, 0.2), -1, seed=2.9))
    crack = [(1.16, 3.36), (1.1, 3.1), (1.2, 2.84), (1.03, 2.56), (1.1, 2.26), (0.98, 1.98), (1.04, 1.7), (0.96, 1.42)]
    wid = [0.002, 0.008, 0.014, 0.022, 0.026, 0.02, 0.012, 0.004]
    hm.append(groove(pc, crack, wid, -1, 0.07))
    # +Y: grosse Abplatzung quer ueber die Farbkante, kleine unten links, Riss oben, Strichliste
    hp.append(spall(pc, noisy_loop(0.25, 1.52, 0.82, 0.52, 64, 4.1, 0.2), 1, seed=4.1))
    hp.append(spall(pc, noisy_loop(-0.98, 0.56, 0.3, 0.26, 36, 5.5, 0.2), 1, seed=5.5))
    hp.append(groove(pc, crack[:4], [0.002, 0.007, 0.011, 0.004], 1, 0.07))
    hp += tally(pc, -1.42, 1.25, 1, 2, 2, 21)
    check_holes(pc.name + " -Y", hm)
    check_holes(pc.name + " +Y", hp)
    body(pc, OUTER, hm, hp)
    for side in (-1, 1):
        strips(pc, side, FULL)
    floor_debris(pc, 0.45, 1.3, -1, 9, 7, 23)
    floor_debris(pc, -1.2, 0.9, 1, 10, 8, 24)
    return finish(pc)

def wand_03():
    pc = Piece(f"{GEB}_wand_03")
    hm = tally(pc, -0.95, 1.3, -1, 4, 1, 51) + tally(pc, -0.95, 1.46, -1, 2, 3, 52)
    hm += scratch_cluster(pc, 0.55, 0.62, -1, 4, 0.22, -0.3, 53)
    hp = [spall(pc, noisy_loop(0.65, 0.5, 0.14, 0.11, 30, 6.1, 0.25), 1, depth=0.02, bars=False, slope=0.012, seed=6.1)]
    check_holes(pc.name + " -Y", hm)
    check_holes(pc.name + " +Y", hp)
    body(pc, OUTER, hm, hp)
    for side in (-1, 1):
        strips(pc, side, FULL)
    # zwei dicke Stahlrohre (89 und 76 mm) in Schellen unter der Decke, buendig an beiden Kanten
    for zc, r in ((3.28, 0.0445), (3.12, 0.038)):
        yc = T2 + 0.012 + r
        tube(pc, [(-W2, yc, zc), (W2, yc, zc)], r, "rohr", seg=12, caps=True, uoff=0.5 - UVS * W2)
        for x in (-1.3, 0.0, 1.3):
            pipe_clamp(pc, x, yc, zc, r)
    schaltkasten(pc, -0.5, 1.4)
    return finish(pc)

def wand_tuer():
    pc = Piece(f"{GEB}_wand_tuer")
    outer = [(-W2, 0), (-0.65, 0), (-0.65, 2.2), (0.65, 2.2), (0.65, 0), (W2, 0), (W2, H), (-W2, H)]
    hm = scratch_cluster(pc, -1.38, 1.0, -1, 6, 0.3, 0.45, 41)
    hm.append(spall(pc, noisy_loop(1.15, 0.42, 0.13, 0.1, 28, 4.4, 0.25), -1, depth=0.02, bars=False, slope=0.012, seed=4.4))
    hp = tally(pc, 0.95, 1.32, 1, 3, 3, 42)
    check_holes(pc.name + " -Y", hm)
    check_holes(pc.name + " +Y", hp)
    body(pc, outer, hm, hp)
    door_frame(pc)
    spans = [(-W2, -0.74), (0.74, W2)]
    for side in (-1, 1):
        strips(pc, side, spans)
    return finish(pc)

def wand_fenster():
    pc = Piece(f"{GEB}_wand_fenster")
    x0, x1, z0, z1 = -0.75, 0.75, 0.95, 2.35
    bt, st = 0.05, 0.07                 # Betonfasche steht 5 cm vor, Bank 7 cm
    xb, xs, zt, sz0 = x1 + 0.12, x1 + 0.17, z1 + 0.12, z0 - 0.12
    outline = [(-xs, sz0), (xs, sz0), (xs, z0), (xb, z0), (xb, zt), (-xb, zt), (-xb, z0), (-xs, z0)]
    hm = [outline] + tally(pc, 1.0, 1.25, -1, 3, 2, 31)
    hp = [outline] + scratch_cluster(pc, -1.36, 1.55, 1, 5, 0.26, -0.55, 32)
    check_holes(pc.name + " -Y", hm)
    check_holes(pc.name + " +Y", hp)
    body(pc, OUTER, hm, hp)
    yo, yb = T2 + bt, T2 + st
    for s in (-1, 1):
        rule = R_WM if s < 0 else R_WP
        # Fasche: Vorderseite, Aussenkanten, Oberseite
        U = [(-xb, z0), (x0, z0), (x0, z1), (x1, z1), (x1, z0), (xb, z0), (xb, zt), (-xb, zt)]
        pc.tess(U, [], s * yo, 0, rule, (0, s, 0))
        for x, sg in ((-xb, -1), (xb, 1)):
            pc.face([Vector((x, s * T2, z0)), Vector((x, s * yo, z0)), Vector((x, s * yo, zt)), Vector((x, s * T2, zt))], 0, R_ENDX, (sg, 0, 0))
        pc.face([Vector((-xb, s * T2, zt)), Vector((xb, s * T2, zt)), Vector((xb, s * yo, zt)), Vector((-xb, s * yo, zt))], 0, R_REVZ, (0, 0, 1), par=(2.55, 0, 0))
        # Bank: Vorderseite, Enden, Unterseite
        pc.face([Vector((-xs, s * yb, sz0)), Vector((xs, s * yb, sz0)), Vector((xs, s * yb, z0)), Vector((-xs, s * yb, z0))], 0, rule, (0, s, 0))
        for x, sg in ((-xs, -1), (xs, 1)):
            pc.face([Vector((x, s * T2, sz0)), Vector((x, s * yb, sz0)), Vector((x, s * yb, z0)), Vector((x, s * T2, z0))], 0, R_ENDX, (sg, 0, 0))
        pc.face([Vector((-xs, s * T2, sz0)), Vector((xs, s * T2, sz0)), Vector((xs, s * yb, sz0)), Vector((-xs, s * yb, sz0))], 0, R_REVZ, (0, 0, -1), par=(0.38, 0, 0))
    # Laibung durch Wand und Fasche
    for x, sg in ((x0, 1), (x1, -1)):
        pc.face([Vector((x, -yo, z0)), Vector((x, yo, z0)), Vector((x, yo, z1)), Vector((x, -yo, z1))], 0, R_REVX, (sg, 0, 0))
    pc.face([Vector((x0, -yo, z1)), Vector((x1, -yo, z1)), Vector((x1, yo, z1)), Vector((x0, yo, z1))], 0, R_REVZ, (0, 0, -1), par=(2.37, 0, 0))
    # Oberseite beider Baenke und Sohle der Oeffnung in einem Stueck (z = 0,95)
    top = [(-xs, -yb), (xs, -yb), (xs, -T2), (xb, -T2), (xb, -yo), (x1, -yo), (x1, yo), (xb, yo), (xb, T2), (xs, T2),
           (xs, yb), (-xs, yb), (-xs, T2), (-xb, T2), (-xb, yo), (x0, yo), (x0, -yo), (-xb, -yo), (-xb, -T2), (-xs, -T2)]
    pts = [Vector((x, y, z0)) for x, y in top]
    for a, b, c in geometry.tessellate_polygon([pts]):
        if (pts[b] - pts[a]).cross(pts[c] - pts[a]).length < 2e-9:
            continue
        pc.face([pts[a], pts[b], pts[c]], 0, R_REVZ, (0, 0, 1), par=(0.6, 0, 0))
    # Stahlrahmen in der Wandmitte, ohne Glas und ohne Gitter, mit Nieten auf der Innenseite
    fw, fd = 0.07, 0.03
    box_faces(pc, (x0, -fd, z0 + fw), (x0 + fw, fd, z1 - fw), R_METAL, bevel=0.003, axis=(0, 0, 1))
    box_faces(pc, (x1 - fw, -fd, z0 + fw), (x1, fd, z1 - fw), R_METAL, bevel=0.003, axis=(0, 0, 1))
    box_faces(pc, (x0, -fd, z1 - fw), (x1, fd, z1), R_METAL, bevel=0.003, axis=(1, 0, 0))
    box_faces(pc, (x0, -fd, z0), (x1, fd, z0 + fw), R_METAL, bevel=0.003, axis=(1, 0, 0))
    for z in (1.2, 1.5, 1.8, 2.1):
        rivet(pc, x0 + fw / 2, -fd, z, -1)
        rivet(pc, x1 - fw / 2, -fd, z, -1)
    for x in (-0.6, -0.3, 0.0, 0.3, 0.6):
        rivet(pc, x, -fd, z0 + fw / 2, -1)
        rivet(pc, x, -fd, z1 - fw / 2, -1)
    for side in (-1, 1):
        strips(pc, side, FULL)
    return finish(pc)

def wand_durchbruch():
    pc = Piece(f"{GEB}_wand_durchbruch")
    hole = through_hole_outline()
    hm = [hole, spall(pc, noisy_loop(-1.12, 2.62, 0.26, 0.3, 36, 7.7, 0.18), -1, seed=7.7)]
    hp = [hole, spall(pc, noisy_loop(1.1, 0.62, 0.27, 0.24, 36, 9.1, 0.18), 1, seed=9.1)]
    check_holes(pc.name + " -Y", hm)
    check_holes(pc.name + " +Y", hp)
    body(pc, OUTER, hm, hp)
    # Bruchflaeche durch die Wand: in der Dicke unterteilt, grob verformt (dicke Brocken), Loch bleibt in den Grenzen
    n = len(hole)
    cx = sum(p[0] for p in hole) / n
    cz = sum(p[1] for p in hole) / n
    layers = 5
    grid = []
    for k in range(n):
        x, z = hole[k]
        ux, uz = x - cx, z - cz
        l = math.hypot(ux, uz) or 1.0
        ux, uz = ux / l, uz / l
        colm = []
        for j in range(layers):
            y = -T2 + 2 * T2 * j / (layers - 1)
            if 0 < j < layers - 1:
                d = 0.06 * noise.noise(Vector((x * 5, y * 7, z * 5))) + 0.025 * noise.noise(Vector((x * 18, y * 18, z * 18))) + 0.035
                colm.append(Vector((min(0.795, max(-0.795, x + ux * d)), y, min(2.395, max(0.905, z + uz * d)))))
            else:
                colm.append(Vector((x, y, z)))
        grid.append(colm)
    ccw = loop_area(hole) > 0
    for k in range(n):
        k2 = (k + 1) % n
        for j in range(layers - 1):
            P = [grid[k][j], grid[k2][j], grid[k2][j + 1], grid[k][j + 1]]
            pc.face(P, 1, R_PLAN, edge_inward(hole, k, ccw), reg=PLAN_REG.index("kern"))
    hole_bars(pc, hole, 61)
    for side in (-1, 1):
        strips(pc, side, FULL)
    rubble(pc, -1, cx * 0.3, 3.3)
    rubble(pc, 1, cx * 0.3, 5.1)
    return finish(pc)

def wand_ecke():
    pc = Piece(f"{GEB}_wand_ecke")
    a = 0.105
    sides = [((0, -1, 0), (-a, -a), (a, -a)), ((1, 0, 0), (a, -a), (a, a)), ((0, 1, 0), (a, a), (-a, a)), ((-1, 0, 0), (-a, a), (-a, -a))]
    # U wie bei einer Wand, deren Mitte 2 m neben dem Pfosten liegt (4-m-Raster). An den X-Seiten wie eine um 90 Grad
    # gedrehte Wand. So liegen die Fliesenfugen auf Pfosten und Wand in jeder Drehung auf demselben 15,4-cm-Raster.
    def post_u(nrm, p):
        if nrm == (0, -1, 0):
            return UVS * p.x
        if nrm == (0, 1, 0):
            return -UVS * p.x + 0.5
        if nrm == (1, 0, 0):
            return UVS * p.y
        return -UVS * p.y + 0.5
    for nrm, p0, p1 in sides:
        P = [Vector((p0[0], p0[1], 0)), Vector((p1[0], p1[1], 0)), Vector((p1[0], p1[1], H)), Vector((p0[0], p0[1], H))]
        f = pc.face(P, 0, R_KEEP, nrm)
        for l in f.loops:
            p = l.vert.co
            l[pc.uv].uv = (post_u(nrm, p), UVS * p.z)
    f = pc.face([Vector((-a, -a, H)), Vector((a, -a, H)), Vector((a, a, H)), Vector((-a, a, H))], 0, R_TOP, (0, 0, 1))
    # Sockel und Leiste rundherum, auf Gehrung
    for prof, reg in ((SOCKEL_PROF, "sockel"),):
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
    "lampe1": (1, -1, (-1.1, 3.1, 1.6), (0.15, 0, 1.55), (0.2, 0, 1.45)),
    "lampe2": (5, 1, (-1.2, 3.0, 1.4), (0.05, 0, 1.08), (0.1, 0, 1.0)),
    "lampe3": (2, 1, (0.9, 2.9, 1.75), (-0.35, 0, 2.15), (-0.3, 0, 2.0)),
    "lampe4": (3, -1, (-1.5, 2.8, 1.5), (0.0, 0, 1.2), (0.05, 0, 1.1)),
    "nah1": (0, -1, (-0.5, 0.75, 1.02), (-0.72, 0, 0.87), (-0.72, 0, 0.87), 35),
    "nah2": (3, -1, (-1.25, 0.95, 1.5), (-0.72, 0, 1.25), (-0.75, 0, 1.2), 35),
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

