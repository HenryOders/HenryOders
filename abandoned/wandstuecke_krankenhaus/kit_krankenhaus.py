# ABANDONED · Modulare Wandstuecke fuer das Gebaeude "krankenhaus"
# Sieben Stuecke, zwei kachelbare Materialien ("Wand", "Detail") mit je 4096 x 4096 px,
# UV-Massstab 0,25 je Meter (1024 px/m). Export als glTF 2.0 mit gemeinsamen Texturdateien.
# Start: blender -b -P kit_krankenhaus.py  (oder mit dem bpy-Modul: python kit_krankenhaus.py).
# Das Skript setzt Blender auf Werkseinstellungen zurueck, also nicht in einem offenen Projekt ausfuehren.
import bpy, bmesh, math, random, os, time, json, zlib
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, Quaternion, noise, geometry
from mathutils.bvhtree import BVHTree

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
SHOTS = [s for s in os.environ.get("SHOTS", "vorne,hinten,lampe1,lampe2").split(",") if s]
SAMPLES = int(os.environ.get("SAMPLES", "64"))
RES = [int(v) for v in os.environ.get("RES", "1920x1080").split("x")]

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("io_scene_gltf2", default_set=True)
scene = bpy.context.scene

# ---------------- Masse ----------------
W2, H, T2 = 1.9, 3.4, 0.1
TS = 4.0 / 26                  # Fliese 15,4 cm: 26 Fliesen auf 4 m, damit die Textur nahtlos kachelt
TRENN = 1.2                    # Trennlinie Fliesen / Putz
PL = TRENN - 7 * TS            # Sockelhoehe 12,3 cm, darueber genau 7 Fliesenreihen
GROUT = 0.003
TILE_T = 0.008                 # Fliese
PUTZ_T = 0.02                  # Putz auf Ziegel
EDGE = 0.4                     # Schaeden nie naeher an den Seitenkanten

# Bereiche in der Detail-Textur (Meter von unten, 4 m = ganze Hoehe)
REG = {
    "ziegel": (0.00, 1.30), "kleber": (1.30, 2.20), "bruch": (2.20, 2.60), "riss": (2.60, 2.70),
    "metall_24": (2.70, 2.95), "metall_07": (2.96, 3.03), "metall_05": (3.04, 3.09), "metall_03": (3.10, 3.13),
    "sockel": (3.14, 3.30), "leiste": (3.31, 3.38), "kupfer": (3.39, 3.47), "rost": (3.48, 3.52),
    "kanal": (3.53, 3.73), "kasten": (3.74, 4.00),
}
KASTEN_W, KASTEN_H = 0.20, 0.25          # Notrufkasten, Vorderseite liegt bei U 0,5 bis 0,55

# ======================= Texturen =======================
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

def tex_wand():
    n = NPX
    X, Z = grid_xz()
    S = (n, n)
    # ---- Fliesen bis 1,2 m ----
    colf = X / TS
    col = np.floor(colf).astype(np.int32) % 26
    rz = (Z - PL) / TS
    row = np.floor(rz).astype(np.int32)
    fx, fz = colf - np.floor(colf), rz - row
    e = np.minimum(np.minimum(fx, 1 - fx), np.minimum(fz, 1 - fz)) * TS
    grout = e < GROUT / 2
    bevel = sm(GROUT / 2, GROUT / 2 + 0.0035, e)
    rng = np.random.default_rng(11)
    R = 14
    rr = np.clip(row + 2, 0, R - 1)
    turq = rng.random((R, 26)) < 0.36
    tint = rng.normal(0, 0.022, (R, 26)).astype(np.float32)
    yel = rng.random((R, 26)).astype(np.float32)
    weiss, tuerkis = hexc("#cbc6b4"), hexc("#8fafa6")
    tile = np.where(turq[rr, col][..., None], tuerkis, weiss) * (1 + tint[rr, col])[..., None]
    tile = mix(tile, tile * hexc("#f0e2bd"), 0.4 * (yel[rr, col] > 0.82))
    glaze = fr(S, 1.6, 21)
    low = sm(0.5, 0.0, Z)
    dirt = sm(0.1, 2.0, fr(S, 1.3, 22) + 1.5 * low)
    runs = sm(0.7, 2.2, fr(S, 1.0, 23, aniso=8.0)) * sm(0.1, 1.0, Z)
    src_t = sm(1.0, 2.0, fr(S, 1.0, 24, aniso=10.0)) * sm(1.0, 1.18, Z) * (Z < TRENN)
    wl_t = drip(src_t, 0.9) * (0.5 + 0.5 * sm(-0.5, 1.0, fr(S, 0.9, 25)))
    tile = tile * (1 + 0.015 * glaze)[..., None]
    tile = mix(tile, hexc("#5f5644"), 0.5 * dirt)
    tile = mix(tile, tile * hexc("#a08c62"), np.clip(0.55 * runs + 0.7 * wl_t, 0, 1))
    gmold = sm(0.4, 1.4, fr(S, 1.1, 26) + 1.4 * (low + sm(0.9, 1.19, Z)) - 0.7)
    groutc = mix(hexc("#58554c"), hexc("#262a22"), np.clip(0.6 * dirt + 0.7 * gmold, 0, 1))
    alb_t = np.where(grout[..., None], groutc, tile)
    h_t = np.where(grout, -0.0016, -0.0016 * (1 - bevel)) + 0.00008 * glaze
    r_t = np.where(grout, 0.9, 0.16 + 0.4 * dirt + 0.25 * runs + 0.2 * wl_t)
    # ---- Putz ab 1,2 m ----
    big = fr(S, 1.8, 31)
    grain = fr(S, 0.3, 32, sigma_m=0.0006)
    alb_p = hexc("#9cae9a") * (0.94 + 0.05 * big + 0.025 * grain)[..., None]
    zone = sm(2.6, 3.4, Z) + 0.6 * sm(1.75, 1.2, Z)
    damp = sm(0.0, 1.5, fr(S, 1.4, 33) + 1.6 * zone - 0.8)
    alb_p = alb_p * (1 - 0.22 * damp)[..., None]
    src = sm(1.5, 2.5, fr(S, 1.0, 34, aniso=12.0)) * sm(3.0, 3.38, Z)
    wl = drip(src, 1.7) * (0.6 + 0.4 * sm(-0.5, 1.0, fr(S, 0.9, 35)))
    alb_p = mix(alb_p, alb_p * hexc("#8a8068"), 0.6 * wl)
    spots = sm(2.3, 2.9, fr(S, 0.8, 36, sigma_m=0.012)) * sm(1.7, 2.6, Z)
    rust = np.clip(np.maximum(spots, drip(spots, 0.45) * 0.85), 0, 1)
    alb_p = mix(alb_p, hexc("#7a4828"), 0.72 * rust)
    mzone = sm(2.85, 3.4, Z) + 0.7 * sm(1.6, 1.22, Z)
    mmask = sm(0.3, 1.2, fr(S, 1.2, 37) + 1.2 * mzone - 0.6)
    speck = sm(1.1, 2.2, fr(S, 0.1, 38, sigma_m=0.0016))
    mold = np.clip(mmask * (0.35 * mmask + speck), 0, 1)
    alb_p = mix(alb_p, hexc("#2b3326"), 0.8 * mold)
    h_p = 0.0006 * big + 0.00025 * grain + 0.0002 * fr(S, 0.6, 39, sigma_m=0.0008) + 0.0003 * rust
    r_p = 0.8 + 0.05 * big - 0.32 * wl - 0.15 * damp + 0.08 * mold
    up = (Z >= TRENN)[..., None]
    alb = np.where(up, alb_p, alb_t)
    hgt = np.where(up[..., 0], h_p, h_t)
    rough = np.where(up[..., 0], r_p, r_t)
    return write_set(f"T_{GEB}_Wand", alb, hgt, rough, np.zeros(S, np.float32))

def tex_detail():
    n = NPX
    alb = np.zeros((n, n, 3), np.float32)
    hgt = np.zeros((n, n), np.float32)
    rgh = np.full((n, n), 0.8, np.float32)
    met = np.zeros((n, n), np.float32)
    def region(name):
        z0, z1 = REG[name]
        r0, r1 = int(round(z0 * n / 4)), int(round(z1 * n / 4))
        X, Z = grid_xz((r0, r1), z0)
        return slice(r0, r1), X, Z, (r1 - r0, n), z1 - z0
    seed = [100]
    def nz(shape, beta, aniso=1.0, sigma_m=0.0):
        seed[0] += 1
        return fr(shape, beta, seed[0], aniso, sigma_m)
    # ---- Ziegel ----
    sl, X, Z, S, hh = region("ziegel")
    CH = 0.25 / 3
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
    bcol = np.where((cc < 0.5)[..., None], hexc("#74463a"), np.where((cc < 0.75)[..., None], hexc("#86584a"),
                    np.where((cc < 0.93)[..., None], hexc("#5b3a31"), hexc("#3f2c27"))))
    bcol = mix(bcol, hexc("#6d665d"), 0.25)
    bcol = bcol * (1 + tint[course, bi])[..., None] * (0.9 + 0.08 * nz(S, 0.9)[..., None])
    pits = sm(1.6, 2.3, nz(S, 0.15, sigma_m=0.001))
    bcol = bcol * (1 - 0.35 * pits)[..., None]
    mortar = hexc("#8c8576") * (0.88 + 0.1 * nz(S, 1.0)[..., None])
    a = np.where(joint[..., None], mortar, bcol)
    salt = sm(1.7, 2.5, nz(S, 1.2)) * sm(0.6, 0.0, Z)
    damp = sm(0.0, 1.6, nz(S, 1.4))
    a = mix(a, hexc("#cfc9bb"), 0.55 * salt)
    a = a * (1 - 0.25 * damp)[..., None]
    mold = sm(2.0, 2.7, nz(S, 0.3, sigma_m=0.002)) * sm(0.5, 1.4, nz(S, 1.2))
    a = mix(a, hexc("#2c3226"), 0.7 * mold)
    rest = sm(1.1, 1.5, nz(S, 1.2) + 0.5 * nz(S, 0.7))
    a = mix(a, hexc("#a9a291") * (0.85 + 0.1 * nz(S, 0.9)[..., None]), 0.85 * rest)
    a = a * (1 - 0.3 * sm(0.2, 2.2, nz(S, 1.3)))[..., None]
    alb[sl] = a
    hgt[sl] = 0.003 * rest + np.where(joint, -0.009, -0.004 * (1 - sm(jw, jw + 0.004, e))) - 0.0012 * pits + 0.0004 * nz(S, 0.8)
    rgh[sl] = np.where(joint, 0.93, 0.84) - 0.3 * damp + 0.05 * mold
    # ---- Fliesenkleber mit Rillen ----
    sl, X, Z, S, hh = region("kleber")
    wob = nz(S, 1.8)
    ridge = 0.5 + 0.5 * np.sin(2 * math.pi * Z / 0.011 + 2.2 * wob)
    imp = np.minimum(np.abs((X / TS) - np.round(X / TS)) * TS, np.abs((Z / TS) - np.round(Z / TS)) * TS)
    seam = sm(0.004, 0.0, imp)
    k = hexc("#8e8b83") * (0.86 + 0.12 * ridge[..., None] + 0.05 * nz(S, 1.0)[..., None])
    k = k * (1 - 0.25 * seam)[..., None] * (1 - 0.2 * sm(0.3, 2.0, nz(S, 1.3)))[..., None]
    alb[sl] = k
    hgt[sl] = 0.0015 * ridge - 0.001 * seam + 0.0003 * nz(S, 0.6)
    rgh[sl] = 0.86 + 0.05 * ridge
    # ---- Bruchflaeche (Ziegel, Moertel, Putz) ----
    # feinkoernig und gleichmaessig, damit einzeln platzierte Flaechen (Bruchkanten, Schutt) keine Naehte zeigen
    sl, X, Z, S, hh = region("bruch")
    m = nz(S, 0.55, sigma_m=0.004)
    frag = sm(0.1, 0.6, m)
    grit = nz(S, 0.2, sigma_m=0.0012)
    cav = sm(1.2, 1.9, nz(S, 0.35, sigma_m=0.0025))
    plast = sm(1.2, 1.8, nz(S, 0.6, sigma_m=0.003))
    b = mix(hexc("#6c675e"), hexc("#7b4434") * (0.85 + 0.2 * nz(S, 0.5)[..., None]), 0.8 * frag)
    b = mix(b, hexc("#a29c8c"), 0.5 * plast)
    b = b * (0.9 + 0.1 * grit)[..., None] * (1 - 0.6 * cav)[..., None]
    alb[sl] = b
    hgt[sl] = 0.003 * m + 0.0012 * grit - 0.005 * cav + 0.0015 * frag
    rgh[sl] = 0.93
    # ---- Rissflanken: dunkler Putz und Moertel ----
    sl, X, Z, S, hh = region("riss")
    q = nz(S, 0.9)
    alb[sl] = mix(hexc("#2a2724"), hexc("#6e695f"), sm(-0.8, 1.6, q)) * (0.85 + 0.15 * nz(S, 0.4)[..., None])
    hgt[sl] = 0.002 * q + 0.001 * nz(S, 0.5)
    rgh[sl] = 0.92
    # ---- weiss lackiertes Metall, Rost an den Kanten ----
    for name in ("metall_24", "metall_07", "metall_05", "metall_03"):
        sl, X, Z, S, hh = region(name)
        d = np.minimum(Z, hh - Z)
        edge = sm(0.011, 0.0, d - 0.006 * nz(S, 1.0))
        chips = sm(1.7, 2.2, nz(S, 0.9))
        spots = sm(2.1, 2.7, nz(S, 0.7))
        rust = np.clip(edge + spots + 0.6 * chips, 0, 1)
        paint = hexc("#d5d2c6") * (0.93 + 0.05 * nz(S, 1.4)[..., None])
        paint = paint * (1 - 0.25 * sm(0.2, 2.2, nz(S, 1.3)))[..., None]
        rc = mix(hexc("#5f3220"), hexc("#8e4f2a"), sm(-1, 1.5, nz(S, 0.6)))
        a = mix(paint, hexc("#8a8981"), 0.7 * chips * (1 - rust))
        alb[sl] = mix(a, rc, rust)
        hgt[sl] = -0.0003 * chips + 0.00025 * rust * nz(S, 0.4)
        rgh[sl] = 0.4 + 0.25 * sm(0.2, 2.2, nz(S, 1.3)) + 0.45 * rust
    # ---- Sockelfliesen ----
    sl, X, Z, S, hh = region("sockel")
    colf = X / TS
    fx = colf - np.floor(colf)
    gx = np.minimum(fx, 1 - fx) * TS < GROUT / 2
    rng = np.random.default_rng(61)
    st = rng.normal(0, 0.03, 26).astype(np.float32)
    ci = np.floor(colf).astype(np.int32) % 26
    s = hexc("#7d9d96") * (1 + st[ci])[..., None] * (0.95 + 0.03 * nz(S, 1.5)[..., None])
    grime = sm(0.05, 0.0, Z) + 0.6 * sm(0.3, 2.2, nz(S, 1.3))
    s = s * (1 - 0.35 * np.clip(grime, 0, 1))[..., None]
    alb[sl] = np.where(gx[..., None], hexc("#4e4b44"), s)
    hgt[sl] = np.where(gx, -0.0015, 0.0) + 0.00008 * nz(S, 1.6)
    rgh[sl] = np.where(gx, 0.9, 0.22 + 0.4 * np.clip(grime, 0, 1))
    # ---- Abschlussleiste ----
    sl, X, Z, S, hh = region("leiste")
    scr = np.clip(sm(2.0, 2.8, nz(S, 0.6, aniso=0.08)), 0, 1)
    l = hexc("#a8b2a5") * (1 - 0.3 * sm(0.0, 2.2, nz(S, 1.3)))[..., None]
    alb[sl] = mix(l, hexc("#d2d6cc"), 0.5 * scr)
    hgt[sl] = -0.0002 * scr
    rgh[sl] = 0.5 + 0.15 * scr
    # ---- Kupfer (Sauerstoffrohre) ----
    sl, X, Z, S, hh = region("kupfer")
    ox = sm(-0.5, 1.5, nz(S, 1.1))
    verd = sm(1.4, 2.1, nz(S, 0.9))
    c = mix(hexc("#a3633f"), hexc("#5f3f2b"), 0.7 * ox)
    c = mix(c, hexc("#5a8a74"), 0.85 * verd)
    alb[sl] = c * (1 - 0.2 * sm(0.3, 2.0, nz(S, 1.3)))[..., None]
    hgt[sl] = 0.0002 * verd * nz(S, 0.5)
    rgh[sl] = 0.32 + 0.3 * ox + 0.35 * verd
    met[sl] = np.clip(1.0 - verd - 0.4 * ox, 0, 1)
    # ---- Rost (Bewehrung) ----
    sl, X, Z, S, hh = region("rost")
    r = nz(S, 0.8)
    alb[sl] = mix(hexc("#4f2a1b"), hexc("#94562d"), sm(-1.2, 1.4, r))
    hgt[sl] = 0.0004 * nz(S, 0.3)
    rgh[sl] = 0.9
    # ---- Kabelkanal (Kunststoff) ----
    sl, X, Z, S, hh = region("kanal")
    seam = sm(0.0025, 0.0, np.minimum(np.abs(Z - 0.04), np.abs(Z - 0.10)))
    lid = sm(0.0015, 0.0, np.abs(Z - 0.075))
    p = hexc("#c4bca6") * (0.93 + 0.04 * nz(S, 1.4)[..., None])
    p = p * (1 - 0.3 * sm(0.3, 2.1, nz(S, 1.2, aniso=4.0)))[..., None]
    alb[sl] = p * (1 - 0.3 * seam - 0.5 * lid)[..., None]
    hgt[sl] = -0.0006 * lid - 0.0002 * seam
    rgh[sl] = 0.45 + 0.2 * sm(0.3, 2.1, nz(S, 1.2))
    # ---- Notrufkasten: rote Seiten links, Vorderseite bei U 0,5 ----
    sl, X, Z, S, hh = region("kasten")
    red = hexc("#8a2722") * (0.9 + 0.08 * nz(S, 1.2)[..., None])
    scr = np.clip(sm(2.1, 2.9, nz(S, 0.6, aniso=0.1)), 0, 1)
    d = np.minimum(Z, hh - Z)
    re = sm(0.008, 0.0, d - 0.004 * nz(S, 1.0))
    a = mix(red, hexc("#c9bfb0"), 0.4 * scr)
    a = mix(a, hexc("#5e2f1d"), re)
    h_ = -0.0002 * scr
    r_ = 0.42 + 0.3 * scr + 0.4 * re
    fx0 = 2.0
    inside = (X >= fx0) & (X < fx0 + KASTEN_W) & (Z >= 0.005) & (Z < 0.005 + KASTEN_H)
    px, pz = X - fx0, Z - 0.005
    border = (px < 0.016) | (px > KASTEN_W - 0.016) | (pz < 0.016) | (pz > KASTEN_H - 0.016)
    bc = np.hypot(px - KASTEN_W / 2, pz - 0.105)
    button = bc < 0.03
    ring = (bc >= 0.03) & (bc < 0.036)
    win = (px > 0.06) & (px < 0.14) & (pz > 0.175) & (pz < 0.215)
    panel = hexc("#d9d6cd") * (1 - 0.3 * sm(0.3, 2.2, nz(S, 1.3)))[..., None]
    fp = np.where(border[..., None], hexc("#9c2a23"), panel)
    fp = np.where(ring[..., None], hexc("#5a5650"), fp)
    fp = np.where(button[..., None], hexc("#b0261e") * (0.85 + 0.3 * sm(0.03, 0.0, bc))[..., None], fp)
    fp = np.where(win[..., None], hexc("#1f2326"), fp)
    a = np.where(inside[..., None], fp, a)
    h_ = np.where(inside, np.where(border, 0.0008, 0.0) + np.where(button, 0.004 * np.sqrt(np.clip(1 - (bc / 0.03) ** 2, 0, 1)), 0.0)
                  - np.where(win, 0.001, 0.0), h_)
    r_ = np.where(inside, np.where(win, 0.08, np.where(button, 0.3, 0.45)), r_)
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
R_KEEP, R_WM, R_WP, R_TOP, R_ENDX, R_REVX, R_REVZ, R_PLAN, R_METAL, R_ADH, R_BRICK, R_BOXFRONT, R_SHARD, R_PLANAX, R_PLANFIX = range(15)
PLAN_REG = ["ziegel", "kleber", "bruch", "metall_24", "metall_07", "metall_05", "metall_03", "sockel",
            "leiste", "kupfer", "rost", "kanal", "kasten", "riss"]

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

# ---------- UV-Vergabe ----------
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
    for name, hgt in (("metall_03", 0.03), ("metall_05", 0.05), ("metall_07", 0.07), ("metall_24", 0.25)):
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
            s = 1 if f.normal.x > 0 else -1
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (0.25 + s * UVS * p.y, UVS * p.z)
        elif r == R_REVZ:
            zref = f[pc.par][0]
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (wall_u(p.x, -1), UVS * (zref + 0.02 + (p.y + T2)))
        elif r in (R_ADH, R_BRICK):
            side = int(f[pc.par][0])
            zb = f[pc.par][1]
            name = "kleber" if r == R_ADH else "ziegel"
            z0 = REG[name][0] + (0.03 if r == R_ADH else 0.02)
            for l in f.loops:
                p = l.vert.co
                v = z0 + p.z - zb
                if not (REG[name][0] <= v <= REG[name][1]):
                    raise RuntimeError(f"{pc.name}: {name} laeuft ueber ({v:.3f})")
                l[uv].uv = (wall_u(p.x, side), UVS * v)
        elif r == R_BOXFRONT:
            bx0, bz0 = f[pc.par][0], f[pc.par][1]
            for l in f.loops:
                p = l.vert.co
                l[uv].uv = (0.5 + UVS * (p.x - bx0), UVS * (REG["kasten"][0] + 0.005 + (p.z - bz0)))
        elif r == R_PLAN:
            co = planar_coords(f)
            place_in_region(pc, f, co, PLAN_REG[f[pc.reg]])
        elif r == R_PLANAX:
            co = planar_coords(f, Vector(f[pc.par]))
            place_in_region(pc, f, co, PLAN_REG[f[pc.reg]], center=True)
        elif r == R_PLANFIX:
            # feste Lage (z. B. Leistenenden an den Stueckkanten): bei allen Stuecken gleich
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
            co = planar_coords(f)
            umin = min(c[0] for c in co)
            vmin = min(c[1] for c in co)
            u0 = pc.rng.random()
            row = pc.rng.randrange(0, 6)
            vz = PL + row * TS + 0.012 + pc.rng.random() * 0.05
            for l, c in zip(f.loops, co):
                l[uv].uv = (u0 + UVS * (c[0] - umin), UVS * (vz + c[1] - vmin))

# ---------- Bausteine ----------
def rect(x0, x1, z0, z1):
    return [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]

def tile_cell(c, r):
    """Fliesenfeld c (Spalte im Weltraster) und r (Reihe ab Sockel)."""
    x0 = c * TS
    z0 = PL + r * TS
    return x0, x0 + TS, z0, z0 + TS

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
            if prof[0][0] != 0:
                P = [Vector((x, yy(0), prof[0][1]))] + P
            if prof[-1][0] != 0:
                P = P + [Vector((x, yy(0), prof[-1][1]))]
            pc.face(P, 1, R_PLANFIX, (sgn, 0, 0), reg=PLAN_REG.index(reg), par=(0.37 if side > 0 else 0.13, 0, 0))

SOCKEL_PROF = [(0.012, 0.0), (0.012, PL - 0.012), (0.0108, PL - 0.0058), (0.0072, PL - 0.0018), (0.0, PL)]
LEISTE_PROF = [(0.0, 1.187), (0.007, 1.187), (0.0108, 1.1905), (0.012, 1.2), (0.0108, 1.2095), (0.007, 1.213), (0.0, 1.213)]

def strips(pc, side, sockel_spans, leiste_spans):
    for a, b in sockel_spans:
        profile_strip(pc, SOCKEL_PROF, a, b, side, "sockel")
    for a, b in leiste_spans:
        profile_strip(pc, LEISTE_PROF, a, b, side, "leiste")

def body(pc, outer, holes_m, holes_p, top=True, ends=True, xr=(-W2, W2)):
    pc.tess(outer, holes_m, -T2, 0, R_WM, (0, -1, 0))
    pc.tess(outer, holes_p, T2, 0, R_WP, (0, 1, 0))
    if top:
        pc.face([Vector((xr[0], -T2, H)), Vector((xr[1], -T2, H)), Vector((xr[1], T2, H)), Vector((xr[0], T2, H))], 0, R_TOP, (0, 0, 1))
    if ends:
        for x, s in ((xr[0], -1), (xr[1], 1)):
            pc.face([Vector((x, -T2, 0)), Vector((x, T2, 0)), Vector((x, T2, H)), Vector((x, -T2, H))], 0, R_ENDX, (s, 0, 0))

def missing_tile(pc, c, r, side):
    x0, x1, z0, z1 = tile_cell(c, r)
    m = GROUT * 0.35
    loop = rect(x0 + m, x1 - m, z0 + m, z1 - m)
    zb = PL + (r - r % 5) * TS
    recess(pc, loop, side, T2, T2 - TILE_T, 1, R_ADH, (side, zb, 0), "kleber")
    return loop

def cracked_tile(pc, c, r, side, seed):
    rng = random.Random(seed)
    x0, x1, z0, z1 = tile_cell(c, r)
    a = (x0 + 0.004, z0 + rng.uniform(0.25, 0.75) * TS)
    b = (x1 - 0.004, z0 + rng.uniform(0.25, 0.75) * TS)
    pts = [a]
    for t in (0.33, 0.66):
        pts.append((a[0] + (b[0] - a[0]) * t + rng.uniform(-0.004, 0.004), a[1] + (b[1] - a[1]) * t + rng.uniform(-0.012, 0.012)))
    pts.append(b)
    return groove(pc, pts, [0.0006, 0.0016, 0.0014, 0.0006], side, 0.005)

def noisy_loop(cx, cz, rx, rz, npts, seed, amp=0.18):
    pts = []
    for k in range(npts):
        a = 2 * math.pi * k / npts
        c, s = math.cos(a), math.sin(a)
        r = 1 + amp * noise.noise(Vector((c * 1.6, s * 1.6, seed))) + 0.45 * amp * noise.noise(Vector((c * 5, s * 5, seed + 3))) \
            + 0.22 * amp * noise.noise(Vector((c * 16, s * 16, seed + 7)))
        pts.append((cx + c * rx * r, cz + s * rz * r))
    return pts

def plaster_loss(pc, loop, side, missing_bricks=2):
    """Putz grossflaechig abgefallen: 2 cm tief Ziegel, einzelne Ziegel fehlen (noch 3 cm tiefer)."""
    zb = min(p[1] for p in loop) - 0.02
    holes = []
    CH = 0.25 / 3
    tries = 0
    from mathutils.geometry import intersect_point_tri_2d
    poly3 = [Vector((x, z, 0)) for x, z in loop]
    tris = geometry.tessellate_polygon([poly3])
    def inside(x, z):
        P = Vector((x, z, 0))
        return any(intersect_point_tri_2d(P, poly3[a], poly3[b], poly3[c]) for a, b, c in tris)
    while len(holes) < missing_bricks and tries < 400:
        tries += 1
        k = pc.rng.randrange(1, 14)
        zz0 = zb - 0.02 + k * CH + 0.006
        zz1 = zz0 + CH - 0.012
        j = pc.rng.randrange(0, 16)
        if side < 0:
            xx0 = j * 0.25 - (k % 2) * 0.125 - 2.0 + 0.006
        else:
            xx0 = -((j + 1) * 0.25 - (k % 2) * 0.125) + 0.006
        xx0 = ((xx0 + 2.0) % 4.0) - 2.0
        xx1 = xx0 + 0.25 - 0.012
        cand = rect(xx0, xx1, zz0, zz1)
        ok = all(inside(x + (0.03 if x < (xx0 + xx1) / 2 else -0.03) * 0, z) for x, z in cand) and \
             all(inside(x, z) for x, z in [(xx0 - 0.03, zz0 - 0.03), (xx1 + 0.03, zz1 + 0.03), (xx0 - 0.03, zz1 + 0.03), (xx1 + 0.03, zz0 - 0.03)])
        if ok and all(abs(cand[0][0] - h[0][0]) > 0.3 or abs(cand[0][1] - h[0][1]) > 0.1 for h in holes):
            holes.append(cand)
    y_in = T2 - PUTZ_T
    recess(pc, loop, side, T2, y_in, 1, R_BRICK, (side, zb, 0), "bruch", holes=holes)
    for h in holes:
        recess(pc, h, side, y_in, y_in - 0.03, 1, R_PLAN, (0, 0, 0), "bruch", reg_bottom="bruch")
    return loop

def fix_plan_bottoms(pc):
    for f in pc.bm.faces:
        if f[pc.rule] == R_PLAN and f[pc.reg] == 0:
            f[pc.reg] = PLAN_REG.index("bruch")

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

def shard(pc, x, y, seed, size=(0.03, 0.08), zbase=0.0):
    """Fliesenscherbe: Oberseite glasiert (Wand-Material), Kanten Bruch."""
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
    topz = [z0 + TILE_T + tilt * (p[0] - x) for p in P]
    lift = max(0.0, zbase - min(z0 + tilt * (p[0] - x) for p in P))   # schraege Scherbe nicht unter den Boden
    top = [Vector((p[0], p[1], tz + lift)) for p, tz in zip(P, topz)]
    bot = [Vector((p[0], p[1], z0 + tilt * (p[0] - x) + lift)) for p in P]
    pc.face(top, 0, R_SHARD, (0, 0, 1))
    pc.face(bot[::-1], 1, R_PLAN, (0, 0, -1), reg=PLAN_REG.index("bruch"))
    c = sum(top, Vector()) / len(top)
    for i in range(len(P)):
        j = (i + 1) % len(P)
        Q = [bot[i], bot[j], top[j], top[i]]
        mid = (bot[i] + top[j]) / 2
        pc.face(Q, 1, R_PLAN, mid - c, reg=PLAN_REG.index("bruch"))

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

def col_of(x):
    return int(math.floor(x / TS))

def wand_01():
    pc = Piece(f"{GEB}_wand_01")
    hm = [missing_tile(pc, col_of(-0.95), 2, -1), missing_tile(pc, col_of(0.62), 5, -1), cracked_tile(pc, col_of(0.2), 3, -1, 3)]
    hp = [missing_tile(pc, col_of(-0.3), 4, 1), cracked_tile(pc, col_of(1.0), 1, 1, 5)]
    body(pc, OUTER, hm, hp)
    for side in (-1, 1):
        strips(pc, side, FULL, FULL)
    return finish(pc)

def tiles_region(pc, cols, heights, side):
    """Abgefallene Fliesen: Spalten cols, je Spalte Hoehe in Reihen ab dem Sockel (hoechstens 5)."""
    pts = [(cols[0] * TS, PL)]
    for i, c in enumerate(cols):
        h = PL + min(5, heights[i]) * TS
        pts += [(c * TS, h), ((c + 1) * TS, h)]
    pts.append(((cols[-1] + 1) * TS, PL))
    loop = []
    for p in pts:
        if loop and abs(loop[-1][0] - p[0]) < 1e-9 and abs(loop[-1][1] - p[1]) < 1e-9:
            continue
        loop.append(p)
    out = []
    n = len(loop)
    for i in range(n):
        a, b, c = loop[i - 1], loop[i], loop[(i + 1) % n]
        if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) < 1e-12:
            continue
        out.append(b)
    recess(pc, out, side, T2, T2 - TILE_T, 1, R_ADH, (side, PL, 0), "kleber")
    return out

def floor_shards(pc, x0, x1, side, count, seed):
    rng = random.Random(seed)
    for i in range(count):
        x = rng.uniform(x0, x1)
        y = side * rng.uniform(T2 + 0.015, T2 + 0.06)
        shard(pc, x, y, seed * 100 + i, size=(0.025, 0.05))

def wand_02():
    pc = Piece(f"{GEB}_wand_02")
    hm, hp = [], []
    # -Y: Putz oben links weg (Ziegel), Fliesen unten rechts weg, tiefer Riss
    loopA = noisy_loop(-0.3, 2.3, 0.9, 0.47, 80, 1.3, 0.2)
    hm.append(plaster_loss(pc, loopA, -1, 3))
    cols = list(range(col_of(0.32), col_of(1.3) + 1))
    heights = [2, 3, 5, 4, 5, 3, 2][:len(cols)] + [2] * max(0, len(cols) - 7)
    hm.append(tiles_region(pc, cols, heights, -1))
    crack = [(1.2, 3.31), (1.13, 3.05), (1.24, 2.78), (1.05, 2.5), (1.12, 2.2), (0.98, 1.92), (1.06, 1.62), (0.95, 1.34)]
    wid = [0.002, 0.008, 0.014, 0.022, 0.026, 0.02, 0.012, 0.004]
    hm.append(groove(pc, crack, wid, -1, 0.07))
    hm.append(missing_tile(pc, col_of(-1.05), 3, -1))
    hm.append(missing_tile(pc, col_of(-0.35), 1, -1))
    # +Y: Putz links weg, Fliesen darunter weg, Riss geht durch
    loopB = noisy_loop(-0.45, 2.1, 0.8, 0.46, 76, 4.1, 0.2)
    hp.append(plaster_loss(pc, loopB, 1, 2))
    colsB = list(range(col_of(-1.3), col_of(-0.5) + 1))
    hp.append(tiles_region(pc, colsB, [3, 4, 2, 4, 3, 1][:len(colsB)] + [2] * max(0, len(colsB) - 6), 1))
    hp.append(groove(pc, crack, [w * 0.8 for w in wid], 1, 0.07))
    hp.append(missing_tile(pc, col_of(0.25), 2, 1))
    hp.append(missing_tile(pc, col_of(1.15), 4, 1))
    body(pc, OUTER, hm, hp)
    for side in (-1, 1):
        strips(pc, side, FULL, FULL)
    # Scherben und Putzbrocken am Boden, hoechstens 12 cm vor der Wand
    floor_shards(pc, 0.32, 1.3, -1, 16, 21)
    floor_shards(pc, -1.3, -0.5, 1, 12, 22)
    for i in range(6):
        x = pc.rng.uniform(-1.1, 0.05)
        s = pc.rng.uniform(0.015, 0.03)
        chunk(pc, (x, -(T2 + pc.rng.uniform(0.02, 0.05)), s * 0.6), (s * 1.5, s, s * 0.6), 40 + i, "bruch")
    return finish(pc)

def wand_03():
    pc = Piece(f"{GEB}_wand_03")
    hm = [missing_tile(pc, col_of(-0.7), 2, -1), missing_tile(pc, col_of(0.9), 4, -1)]
    hp = [missing_tile(pc, col_of(-1.15), 3, 1), cracked_tile(pc, col_of(-0.2), 1, 1, 9)]
    body(pc, OUTER, hm, hp)
    for side in (-1, 1):
        strips(pc, side, FULL, FULL)
    y0 = T2
    # zwei Sauerstoffrohre (Kupfer) und ein Kabelkanal unter der Decke, buendig an beiden Kanten
    for (zc, r, yc) in ((3.27, 0.011, y0 + 0.032), (3.21, 0.0075, y0 + 0.032)):
        tube(pc, [(-W2, yc, zc), (W2, yc, zc)], r, "kupfer", seg=12, caps=True, uoff=0.5 - UVS * W2)
    # Kabelkanal 6 x 4 cm
    prof = [(0.0, 3.04), (0.04, 3.04), (0.04, 3.10), (0.0, 3.10)]
    s = [0.0, 0.04, 0.10, 0.14]
    z0r = REG["kanal"][0]
    for i in range(3):
        (d0, za), (d1, zb) = prof[i], prof[i + 1]
        P = [Vector((-W2, y0 + d0, za)), Vector((W2, y0 + d0, za)), Vector((W2, y0 + d1, zb)), Vector((-W2, y0 + d1, zb))]
        U = [wall_u(-W2, 1), wall_u(W2, 1), wall_u(W2, 1), wall_u(-W2, 1)]
        V = [UVS * (z0r + 0.002 + s[i])] * 2 + [UVS * (z0r + 0.002 + s[i + 1])] * 2
        want = Vector((0, zb - za, -(d1 - d0)))
        pc.face(P, 1, R_KEEP, want, uvs=list(zip(U, V)))
    for x, sg in ((-W2, -1), (W2, 1)):
        pc.face([Vector((x, y0, 3.04)), Vector((x, y0 + 0.04, 3.04)), Vector((x, y0 + 0.04, 3.10)), Vector((x, y0, 3.10))], 1, R_PLAN, (sg, 0, 0), reg=PLAN_REG.index("kanal"))
    # Halterungen
    for x in (-1.25, 0.0, 1.25):
        box_faces(pc, (x - 0.015, y0, 3.0), (x + 0.015, y0 + 0.012, 3.31), R_METAL, bevel=0.002)
        for (zc, r) in ((3.27, 0.011), (3.21, 0.0075)):
            box_faces(pc, (x - 0.012, y0 + 0.012, zc - r - 0.004), (x + 0.012, y0 + 0.032 + r + 0.004, zc - r - 0.001), R_METAL)
            box_faces(pc, (x - 0.012, y0 + 0.012, zc + r + 0.001), (x + 0.012, y0 + 0.032 + r + 0.004, zc + r + 0.004), R_METAL)
            box_faces(pc, (x - 0.012, y0 + 0.032 + r + 0.001, zc - r - 0.004), (x + 0.012, y0 + 0.032 + r + 0.004, zc + r + 0.004), R_METAL)
    # Notrufkasten in Brusthoehe mit Leerrohr zum Kabelkanal
    bx0, bz0 = 0.6 - KASTEN_W / 2, 1.38
    faces = box_faces(pc, (bx0, y0, bz0), (bx0 + KASTEN_W, y0 + 0.07, bz0 + KASTEN_H), R_PLAN, reg=PLAN_REG.index("kasten"))
    for f in faces:
        f.normal_update()
        if f.normal.y > 0.9:
            f[pc.rule] = R_BOXFRONT
            f[pc.par] = (bx0, bz0, 0)
    bc = Vector((0.6, y0 + 0.07, bz0 + 0.105))
    ring = []
    seg = 16
    for s_ in range(seg):
        a = 2 * math.pi * s_ / seg
        ring.append((bc.x + 0.03 * math.cos(a), bc.z + 0.03 * math.sin(a)))
    for i in range(seg):
        a, b = ring[i], ring[(i + 1) % seg]
        P = [Vector((a[0], bc.y, a[1])), Vector((b[0], bc.y, b[1])), Vector((b[0], bc.y + 0.009, b[1])), Vector((a[0], bc.y + 0.009, a[1]))]
        pc.face(P, 1, R_PLAN, Vector(((a[0] + b[0]) / 2 - bc.x, 0, (a[1] + b[1]) / 2 - bc.z)), reg=PLAN_REG.index("kasten"))
    pc.face([Vector((p[0], bc.y + 0.009, p[1])) for p in ring], 1, R_BOXFRONT, (0, 1, 0), par=(bx0, bz0, 0))
    tube(pc, [(0.6, y0 + 0.011, bz0 + KASTEN_H), (0.6, y0 + 0.011, 3.04)], 0.009, "kanal", seg=10)
    for zc in (2.0, 2.6):
        box_faces(pc, (0.6 - 0.014, y0, zc - 0.012), (0.6 + 0.014, y0 + 0.024, zc + 0.012), R_METAL)
    return finish(pc)

def door_frame(pc):
    """Stahlzarge um die Tueroeffnung, steht beidseitig 2 cm vor."""
    x0, x1, zt = -0.65, 0.65, 2.2
    fl, inner = 0.05, 0.015
    y = T2 + 0.02
    for a, b in ((x0 - fl, x0 + inner), (x1 - inner, x1 + fl)):
        box_faces(pc, (a, -y, 0.0), (b, y, zt - inner), R_METAL, bevel=0.002, axis=(0, 0, 1))
    box_faces(pc, (x0 - fl, -y, zt - inner), (x1 + fl, y, zt + fl), R_METAL, bevel=0.002, axis=(1, 0, 0))
    # Anschlag auf der -Y-Seite
    box_faces(pc, (x0 + inner, -0.05, 0.0), (x0 + inner + 0.014, -0.03, zt - inner), R_METAL, axis=(0, 0, 1))
    box_faces(pc, (x1 - inner - 0.014, -0.05, 0.0), (x1 - inner, -0.03, zt - inner), R_METAL, axis=(0, 0, 1))
    box_faces(pc, (x0 + inner, -0.05, zt - inner - 0.014), (x1 - inner, -0.03, zt - inner), R_METAL, axis=(1, 0, 0))
    # Baender
    for zc in (0.25, 1.95):
        tube(pc, [(x0 + inner + 0.006, -0.06, zc), (x0 + inner + 0.006, -0.06, zc + 0.11)], 0.008, "metall_07", seg=8)

def wand_tuer():
    pc = Piece(f"{GEB}_wand_tuer")
    outer = [(-W2, 0), (-0.65, 0), (-0.65, 2.2), (0.65, 2.2), (0.65, 0), (W2, 0), (W2, H), (-W2, H)]
    hm = [missing_tile(pc, col_of(-1.3), 3, -1), cracked_tile(pc, col_of(1.05), 4, -1, 11)]
    hp = [missing_tile(pc, col_of(1.25), 1, 1)]
    body(pc, outer, hm, hp)
    door_frame(pc)
    spans = [(-W2, -0.70), (0.70, W2)]
    for side in (-1, 1):
        strips(pc, side, spans, spans)
    return finish(pc)

def wand_fenster():
    pc = Piece(f"{GEB}_wand_fenster")
    x0, x1, z0, z1 = -0.75, 0.75, 0.95, 2.35
    win = rect(x0, x1, z0, z1)
    hm = [win, missing_tile(pc, col_of(-1.2), 4, -1)]
    hp = [win, missing_tile(pc, col_of(0.45), 2, 1), cracked_tile(pc, col_of(-1.0), 3, 1, 13)]
    body(pc, OUTER, hm, hp)
    # Laibung
    for x, s in ((x0, 1), (x1, -1)):
        pc.face([Vector((x, -T2, z0)), Vector((x, T2, z0)), Vector((x, T2, z1)), Vector((x, -T2, z1))], 0, R_REVX, (s, 0, 0))
    pc.face([Vector((x0, -T2, z1)), Vector((x1, -T2, z1)), Vector((x1, T2, z1)), Vector((x0, T2, z1))], 0, R_REVZ, (0, 0, -1), par=(z1, 0, 0))
    pc.face([Vector((x0, -T2, z0)), Vector((x1, -T2, z0)), Vector((x1, T2, z0)), Vector((x0, T2, z0))], 0, R_REVZ, (0, 0, 1), par=(z0, 0, 0))
    # Fensterrahmen aus Metall, ohne Glas
    fw, fd = 0.06, 0.035
    box_faces(pc, (x0, -fd, z0 + fw), (x0 + fw, fd, z1 - fw), R_METAL, bevel=0.002, axis=(0, 0, 1))
    box_faces(pc, (x1 - fw, -fd, z0 + fw), (x1, fd, z1 - fw), R_METAL, bevel=0.002, axis=(0, 0, 1))
    box_faces(pc, (x0, -fd, z1 - fw), (x1, fd, z1), R_METAL, bevel=0.002, axis=(1, 0, 0))
    box_faces(pc, (x0, -fd, z0), (x1, fd, z0 + fw), R_METAL, bevel=0.002, axis=(1, 0, 0))
    # Fensterbank innen (-Y) und Blech aussen (+Y)
    box_faces(pc, (x0 - 0.05, -(T2 + 0.04), z0 - 0.03), (x1 + 0.05, -fd, z0 + 0.002), R_METAL, bevel=0.003, axis=(1, 0, 0))
    yo = T2 + 0.05
    P = [Vector((x0 - 0.04, fd, z0)), Vector((x1 + 0.04, fd, z0)), Vector((x1 + 0.04, yo, z0 - 0.025)), Vector((x0 - 0.04, yo, z0 - 0.025))]
    pc.face(P, 1, R_METAL, (0, 0.2, 1), par=(1, 0, 0))
    P = [Vector((x0 - 0.04, yo, z0 - 0.025)), Vector((x1 + 0.04, yo, z0 - 0.025)), Vector((x1 + 0.04, yo, z0 - 0.045)), Vector((x0 - 0.04, yo, z0 - 0.045))]
    pc.face(P, 1, R_METAL, (0, 1, 0), par=(1, 0, 0))
    for x, s in ((x0 - 0.04, -1), (x1 + 0.04, 1)):
        P = [Vector((x, fd, z0)), Vector((x, yo, z0 - 0.025)), Vector((x, yo, z0 - 0.045)), Vector((x, fd, z0 - 0.02))]
        pc.face(P, 1, R_METAL, (s, 0, 0))
    pc.face([Vector((x0 - 0.04, fd, z0 - 0.02)), Vector((x1 + 0.04, fd, z0 - 0.02)), Vector((x1 + 0.04, yo, z0 - 0.045)), Vector((x0 - 0.04, yo, z0 - 0.045))],
            1, R_METAL, (0, 0, -1), par=(1, 0, 0))
    spans_s = FULL
    spans_l = [(-W2, x0), (x1, W2)]
    for side in (-1, 1):
        strips(pc, side, spans_s, spans_l)
    return finish(pc)

def through_hole_outline(seed=2.7):
    """Unregelmaessiger Umriss: hoechstens 1,6 m breit, 1,5 m hoch, Unterkante mindestens 0,9 m."""
    pts = []
    N = 110
    for k in range(N):
        a = 2 * math.pi * k / N
        c, s = math.cos(a), math.sin(a)
        r = 1 + 0.17 * noise.noise(Vector((c * 1.4, s * 1.4, seed))) + 0.07 * noise.noise(Vector((c * 4.5, s * 4.5, seed + 2))) \
            + 0.045 * noise.noise(Vector((c * 14, s * 14, seed + 5))) + 0.02 * noise.noise(Vector((c * 34, s * 34, seed + 9)))
        pts.append((c * r, s * r))
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    sx = 0.74 / max(abs(min(xs)), abs(max(xs)))
    sz = 0.67 / max(abs(min(zs)), abs(max(zs)))
    cz = 0.94 + 0.67
    return [(p[0] * sx, cz + p[1] * sz) for p in pts]

def wand_durchbruch():
    pc = Piece(f"{GEB}_wand_durchbruch")
    hole = through_hole_outline()
    hm, hp = [hole], [hole]
    # Putz ueber dem Loch abgeplatzt, Fliesen darunter abgefallen
    hm.append(plaster_loss(pc, noisy_loop(-1.08, 2.74, 0.34, 0.3, 40, 7.7, 0.15), -1, 1))
    hp.append(plaster_loss(pc, noisy_loop(1.06, 2.7, 0.33, 0.3, 40, 9.1, 0.15), 1, 1))
    zmin = min(p[1] for p in hole)
    for side, cs in ((-1, (col_of(-0.45), col_of(-0.05), col_of(0.35))), (1, (col_of(-0.2), col_of(0.42)))):
        for c in cs:
            r = 4
            if PL + (r + 1) * TS < zmin - 0.03:
                (hm if side < 0 else hp).append(missing_tile(pc, c, r, side))
    body(pc, OUTER, hm, hp)
    # Bruchflaeche durch die Wand: in der Dicke unterteilt und verformt
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
        col = []
        for j in range(layers):
            y = -T2 + 2 * T2 * j / (layers - 1)
            mid = 0 < j < layers - 1
            d = (0.045 * noise.noise(Vector((x * 7, y * 9, z * 7))) + 0.02 * noise.noise(Vector((x * 23, y * 23, z * 23))) + 0.03) if mid else 0.0
            col.append(Vector((x + ux * d, y, z + uz * d)))
        grid.append(col)
    ccw = loop_area(hole) > 0
    for k in range(n):
        k2 = (k + 1) % n
        for j in range(layers - 1):
            P = [grid[k][j], grid[k2][j], grid[k2][j + 1], grid[k][j + 1]]
            pc.face(P, 1, R_PLAN, edge_inward(hole, k, ccw), reg=PLAN_REG.index("bruch"))
    # Bewehrung: verbogene Stummel aus der Bruchkante
    def edge_point(ang):
        return min(hole, key=lambda p: abs((math.atan2(p[1] - cz, p[0] - cx) - ang + math.pi) % (2 * math.pi) - math.pi))
    bars = [(math.pi, 0.0, -0.04, (0.18, 0.06, -0.08)), (math.pi * 0.82, 0.25, 0.04, (0.2, 0.09, 0.05)),
            (0.0, -0.1, 0.03, (-0.22, -0.1, -0.06)), (math.pi * 0.5, 0.0, -0.035, (0.05, -0.12, -0.25)),
            (math.pi * 1.5, 0.0, 0.035, (-0.04, 0.1, 0.2)), (math.pi * 0.12, 0.0, -0.03, (-0.15, -0.13, 0.12))]
    for ang, dz, yb, bend in bars:
        ex, ez = edge_point(ang)
        ux, uz = ex - cx, ez - cz
        l = math.hypot(ux, uz)
        ux, uz = ux / l, uz / l
        inner = Vector((ex + ux * 0.12, yb, ez + uz * 0.12 + dz))
        p0 = Vector((ex, yb, ez + dz))
        p1 = p0 + Vector((-ux * 0.12, 0, -uz * 0.12))
        p2 = p1 + Vector(bend)
        p2.y = max(-T2 - 0.1, min(T2 + 0.1, p2.y))
        tube(pc, fillet([inner, p0, p1, p2], 0.035, 4), 0.0055, "rost", seg=6)
    # Leiste ist im Loch unterbrochen
    xs_at = [p[0] for p in hole if abs(p[1] - 1.2) < 0.08]
    lo, hi = min(xs_at) - 0.04, max(xs_at) + 0.04
    spans_l = [(-W2, lo), (hi, W2)]
    for side in (-1, 1):
        strips(pc, side, FULL, spans_l)
    # Schuttkegel auf beiden Seiten (bis 60 cm vor der Wand)
    for side in (-1, 1):
        nxp, nyp = 16, 8
        rx, ry, hmax = 0.85, 0.58, 0.26
        xc = cx * 0.3
        V = []
        for i in range(nxp + 1):
            sx = 2 * i / nxp - 1                                   # quer: -1 .. 1
            reach = min(1.0, 0.8 + 0.2 * noise.noise(Vector((sx * 2.2, side * 5.0, 2.7))))   # unregelmaessiger Fuss
            row = []
            for j in range(nyp + 1):
                t = j / nyp                                        # von der Wand weg: 0 .. 1
                half = rx * math.sqrt(max(0.0, 1 - (0.8 * t) ** 2)) * (1 + 0.1 * noise.noise(Vector((t * 3.0, side * 3.0, 4.1))))
                x = xc + half * sx
                yd = 0.004 + ry * reach * t
                fall = max(0.0, 1 - sx * sx) * max(0.0, 1 - t ** 1.4)
                fall *= 1 + 0.3 * noise.noise(Vector((x * 2.5, yd * 2.5, side * 3)))
                lump = 0.035 * noise.noise(Vector((x * 9, yd * 9, side))) + 0.015 * noise.noise(Vector((x * 24, yd * 24, side + 5)))
                z = hmax * fall + (lump * min(1.0, 4 * fall) if 0 < i < nxp and j < nyp else 0)
                row.append(Vector((x, side * (T2 + yd), max(0.0, z))))
            V.append(row)
        for i in range(nxp):
            for j in range(nyp):
                P = [V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1]]
                if max(p.z for p in P) < 0.002:
                    continue
                pc.face(P, 1, R_PLAN, (0, side * 0.3, 1), reg=PLAN_REG.index("bruch"))
        # Brocken und Scherben genau auf die Oberflaeche des Haufens legen
        idx = lambda i, j: i * (nyp + 1) + j
        tree = BVHTree.FromPolygons([v for row in V for v in row],
                                    [(idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)) for i in range(nxp) for j in range(nyp)])
        def heap_z(x, yd):
            hit = tree.ray_cast(Vector((x, side * (T2 + yd), 2.0)), Vector((0, 0, -1)))
            return max(0.0, hit[0].z) if hit[0] is not None else 0.0
        for k in range(14):
            x = xc + pc.rng.uniform(-0.7, 0.7)
            yd = pc.rng.uniform(0.04, 0.42)
            s = pc.rng.uniform(0.03, 0.08)
            chunk(pc, (x, side * (T2 + yd), heap_z(x, yd) + s * 0.3), (s * 1.4, s, s * 0.8), 60 + k + (20 if side > 0 else 0), "bruch")
        for k in range(12):
            x = xc + pc.rng.uniform(-0.75, 0.75)
            yd = pc.rng.uniform(0.03, 0.5)
            s = pc.rng.uniform(0.015, 0.035)
            chunk(pc, (x, side * (T2 + yd), heap_z(x, yd) * 0.95 + s * 0.3), (s * 1.3, s, s * 0.7), 120 + k + (30 if side > 0 else 0), "bruch", subdiv=0)
        for k in range(12):
            x = xc + pc.rng.uniform(-0.8, 0.8)
            yd = pc.rng.uniform(0.05, 0.5)
            shard(pc, x, side * (T2 + yd), 300 + k + (50 if side > 0 else 0), size=(0.03, 0.07), zbase=max(0.0, heap_z(x, yd) - 0.004))
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

with open(os.path.join(OUT, "pruefung_krankenhaus.json"), "w", encoding="utf-8") as fjs:
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
    # Reihe aufstellen
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
    spot_d.spot_size = math.radians(32)
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
            ob = OBJS[1] if shot == "lampe1" else OBJS[5]
            sgn = -1 if shot == "lampe1" else 1
            bg.inputs["Color"].default_value = (0.02, 0.022, 0.026, 1)
            bg.inputs["Strength"].default_value = 0.3
            sun_d.energy = 0.0
            spot_d.energy = 420
            spot_d.spot_size = math.radians(58)
            cam_d.lens = 20
            scene.render.resolution_x, scene.render.resolution_y = RES
            ox = ob.location.x
            if shot == "lampe1":
                cam.location = (ox - 1.1, sgn * 3.1, 1.6)
                aim(cam, (ox + 0.15, 0, 1.6))
                spot.location = cam.location + Vector((0.25, 0, -0.2))
                aim(spot, (ox + 0.2, 0, 1.5))
            else:
                cam.location = (ox - 1.2, sgn * 3.0, 1.4)
                aim(cam, (ox + 0.05, 0, 1.08))
                spot.location = cam.location + Vector((0.25, 0, -0.2))
                aim(spot, (ox + 0.1, 0, 1.0))
        scene.render.filepath = os.path.join(OUT, f"krankenhaus_{shot}.png")
        log("Render", shot)
        bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f"{GEB}_wandstuecke.blend"))
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_mainfile()
log("fertig")
