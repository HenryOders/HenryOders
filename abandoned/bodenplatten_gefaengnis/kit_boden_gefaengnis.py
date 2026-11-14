# ABANDONED · Modulare Bodenplatten fuer das Gebaeude "gefaengnis"
# Fuenf Stuecke: vier Platten 4 x 4 m (Oberseite auf Z = 0, 20 cm dick) und eine Tuerschwelle 1,0 x 0,2 m.
# Zwei kachelbare Materialien ("Boden", "BodenDetail") mit je 4096 x 4096 px, 1024 px/m.
# Export als glTF 2.0 (.gltf + .bin), Texturen als relativer Pfad auf Texturen/gefaengnis/.
# Start: blender -b -P kit_boden_gefaengnis.py  (oder mit dem bpy-Modul: python kit_boden_gefaengnis.py).
# Das Skript setzt Blender auf Werkseinstellungen zurueck, also nicht in einem offenen Projekt ausfuehren.
import bpy, bmesh, math, random, os, time, json, zlib, struct
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, noise, geometry

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
FUGEN = (-1.0, 1.0)            # Dehnfugen alle 2 m, in x und in y
FW = 0.004                     # halbe Fugenbreite (Fuge 8 mm)
FT = 0.006                     # Tiefe bis zur Oberkante der Fugenmasse
RAMPE = 0.2                    # die Fuge wird auf den letzten 20 cm vor dem flachen Rand flacher
KH = 0.10                      # Rinne: halbe Breite (20 cm)
KR = 0.085                     # Innenkante des Rahmens = halbe Breite des Troges
KS = 0.065                     # Schlitze im Gitter: halbe Laenge (quer zur Rinne)
KG = 0.025                     # Dicke des Gitters
KT = -0.10                     # Boden des Troges
SCHLITZ, STEG, ABSCHNITT = 0.010, 0.014, 0.5      # Schlitzbreite, Steg zwischen Schlitzen, Gitterlaenge
SW, ST = 0.5, 0.1              # Schwelle: halbe Breite (x), halbe Tiefe (y)
BLECH = 0.008                  # Dicke des Riffelblechs

# Detail-Atlas: waagerechte Bereiche (Meter von unten, 4 m = ganze Hoehe). Bis 2,92 m laufen die Baender ueber die
# ganze Breite und kacheln in U. Darueber links die Mulde der Platte 03 (Einzelflaeche), rechts Kleinteile.
REG = {
    "laufweg": (0.00, 1.02), "markierung": (1.02, 1.14), "beton_roh": (1.14, 1.64), "rinne": (1.64, 2.44),
    "rinne_innen": (2.44, 2.69), "kante": (2.69, 2.89), "fuge": (2.89, 2.92),
    "riffelblech": (2.92, 3.12), "stahlkante": (3.12, 3.15), "bewehrung": (3.15, 3.20), "eisen": (3.20, 3.28),
    "schwelle_kante": (3.28, 3.48),
}
RECHTS = ("riffelblech", "stahlkante", "bewehrung", "eisen", "schwelle_kante")
U_RECHTS = (1.5, 4.0)
BAND_OBEN = 2.92
RINNE_M = 0.40                 # y = 0 der Rinne liegt 0,40 m ueber der Unterkante des Bandes "rinne"
MULDE_BLOCK = (0.0, 1.5, 2.92, 4.00)
MX, MY = 0.10, -0.05           # Mitte der Mulde auf Platte 03
M_A, M_B = 0.46, 0.28            # Halbachsen der Mulde (vor dem Zerfransen)
M_TIEF = 0.0145                # tiefster Punkt der Mulde (hoechstens 1,5 cm)
STAB_R = 0.006                 # Bewehrung 12 mm (Querstab 9 mm)
# Bewehrungsstaebe in der Mulde: Linienzug (x, y, Achshoehe z) und Radius. Die beiden Staebe laengs liegen frei,
# der Querstab liegt tiefer und schaut nur an der tiefsten Stelle heraus. Die Enden stecken im Beton.
STAEBE = [
    ([(MX - 0.62, MY - 0.118, -0.0080), (MX - 0.08, MY - 0.108, -0.0074), (MX + 0.62, MY - 0.122, -0.0080)], STAB_R),
    ([(MX - 0.62, MY + 0.128, -0.0080), (MX + 0.06, MY + 0.117, -0.0074), (MX + 0.62, MY + 0.124, -0.0080)], STAB_R),
    ([(MX + 0.03, MY - 0.42, -0.0104), (MX + 0.036, MY, -0.0101), (MX + 0.03, MY + 0.42, -0.0104)], 0.0045),
]

def _rund_noise(a, f, sx, sy, sz):
    return noise.noise(Vector((math.cos(a) * f + sx, math.sin(a) * f + sy, sz)))

def mulde_r(a):
    """Radius des Muldenrands in elliptischen Koordinaten (1 = Halbachsen M_A, M_B) beim Winkel a."""
    return (1.0 + 0.17 * _rund_noise(a, 1.3, 7.1, 2.3, 0.5) + 0.07 * _rund_noise(a, 4.1, 1.7, 5.3, 0.2)
            + 0.03 * _rund_noise(a, 11.0, 3.0, 1.0, 0.9) + 0.012 * _rund_noise(a, 27.0, 5.0, 8.0, 0.3))

def mulde_kante(a):
    """Hoehe der Bruchkante am Muldenrand (m)."""
    return max(0.0018, 0.0045 + 0.0028 * _rund_noise(a, 2.2, 4.4, 0.6, 0.1) + 0.0012 * _rund_noise(a, 9.0, 2.0, 3.0, 0.7))

def mulde_umriss(n=150):
    """Zerfranster Umriss der Mulde (gegen den Uhrzeigersinn): (x, y, Hoehe der Bruchkante)."""
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        r = mulde_r(a)
        out.append((MX + M_A * r * math.cos(a), MY + M_B * r * math.sin(a), mulde_kante(a)))
    return out

def mulde_boden(x, y):
    """Hoehe des Muldenbodens: am Rand -Bruchkante, zur Mitte bis -M_TIEF, mit rauer Bruchflaeche."""
    u, v = (x - MX) / M_A, (y - MY) / M_B
    a = math.atan2(v, u)
    t = min(1.0, math.hypot(u, v) / mulde_r(a))
    k = mulde_kante(a)
    g = 1.0 - t ** 2.2
    rau = 0.0011 * noise.noise(Vector((x * 23.0, y * 23.0, 0.4))) + 0.0007 * noise.noise(Vector((x * 61.0, y * 61.0, 1.7)))
    z = -(k + (M_TIEF - 0.0012 - k) * g) + rau * min(1.0, (1 - t) * 6)
    return max(-M_TIEF, min(-0.6 * k, z))

def mulde_ring(n=120):
    """Aeussere Grenze der freiliegenden, rostfleckigen Betonflaeche um die Mulde (Abplatzrand des Anstrichs)."""
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        r = (1.0 + 0.17 * _rund_noise(a, 1.3, 7.1, 2.3, 0.5) + 0.07 * _rund_noise(a, 4.1, 1.7, 5.3, 0.2)
             + 0.03 * _rund_noise(a, 11.0, 3.0, 1.0, 0.9))
        d = 0.11 + 0.04 * _rund_noise(a, 1.9, 0.3, 9.1, 0.4) + 0.02 * _rund_noise(a, 6.0, 8.0, 1.0, 0.6) \
            + 0.01 * _rund_noise(a, 17.0, 2.0, 6.0, 0.1)
        ex, ey = M_A * r + d, M_B * r + d
        out.append((MX + ex * math.cos(a), MY + ey * math.sin(a)))
    return out

def rost_rand(x, seite):
    """Abstand der Rostzone von der Rinnenmitte bei x (kachelt mit 4 m), seite = +1 oder -1."""
    a = 2 * math.pi * (x + P2) / 4.0
    o = 3.7 if seite > 0 else 9.2
    return (0.26 + 0.05 * _rund_noise(a, 1.4, o, 1.0, 0.3) + 0.03 * _rund_noise(a, 4.5, o + 2, 3.0, 0.7)
            + 0.015 * _rund_noise(a, 13.0, o + 5, 0.5, 0.1) + 0.008 * _rund_noise(a, 31.0, o + 1, 6.0, 0.4))

def gitter_schlitze():
    """Schlitze im Gussgitter einer Platte als (x von, x bis): Abschnitte von 0,5 m mit je 16 Schlitzen."""
    out = []
    n = 16
    L = n * SCHLITZ + (n - 1) * STEG
    for k in range(int(round(2 * P2 / ABSCHNITT))):
        a = -P2 + ABSCHNITT * k + (ABSCHNITT - L) / 2
        for i in range(n):
            xa = a + i * (SCHLITZ + STEG)
            out.append((xa, xa + SCHLITZ))
    return out

SCHRAUBEN = [(-0.38, 0.0), (-0.13, 0.0), (0.13, 0.0), (0.38, 0.0)]     # Senkschrauben der Schwelle
SCHRAUBE_R = 0.009

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

# ======================= Textur "Boden": grau gestrichener Beton, 4 x 4 m weltbezogen =======================
def beton_farbe(S, nz, grob=1.0):
    """Roher Beton (Zementhaut mit feinem Zuschlag): Farbe, Hoehe, Rauheit. Gleiche Palette in beiden Saetzen."""
    agg = nz(S, 0.6, sigma_m=0.0011)
    tone = nz(S, 1.7)
    a = hexc("#88837a") * (1 + 0.055 * tone)[..., None]
    a = mix(a, hexc("#9b968b"), 0.32 * sm(0.6, 1.6, agg))
    a = mix(a, hexc("#6b6760"), 0.30 * sm(-0.6, -1.6, agg))
    warm = sm(0.2, 1.8, nz(S, 2.2))
    a = mix(a, hexc("#8a7f6d"), 0.22 * warm)
    pores = sm(2.2, 3.0, nz(S, 0.3, sigma_m=0.0006)) * grob
    a = mix(a, hexc("#3b3935"), 0.55 * pores)
    h = 0.00008 * agg - 0.00025 * pores + 0.00006 * tone
    r = 0.88 + 0.03 * agg + 0.05 * pores
    return a, h, r

def tex_boden():
    n = NPX
    S = (n, n)
    px = 4.0 / n
    c = (np.arange(n, dtype=np.float32) + 0.5) * px
    X = np.broadcast_to(c[None, :], S)
    Y = np.broadcast_to(c[:, None], S)
    sd = [100]
    def nz(S_, beta, aniso=1.0, sigma_m=0.0):
        sd[0] += 1
        return fr(S_, beta, sd[0], aniso, sigma_m)
    rng = np.random.default_rng(51)
    def win(cx, cy, rad):
        r0, r1 = int((cy - rad) / px), int((cy + rad) / px) + 1
        c0, c1 = int((cx - rad) / px), int((cx + rad) / px) + 1
        ii = np.ix_(np.arange(r0, r1) % n, np.arange(c0, c1) % n)
        yy = ((np.arange(r0, r1) + 0.5) * px - cy).astype(np.float32)[:, None]
        xx = ((np.arange(c0, c1) + 0.5) * px - cx).astype(np.float32)[None, :]
        return ii, xx, yy
    # ---- Abstand zu den Dehnfugen (Welt x, y = -1 und +1 -> Bild 1 und 3) ----
    dx, dy = pdist(X, 1.0, 2.0), pdist(Y, 1.0, 2.0)
    dj = np.minimum(dx, dy)
    # ---- roher Beton unter dem Anstrich ----
    beton, h_b, r_b = beton_farbe(S, nz)
    trowel = nz(S, 1.2, aniso=0.35)
    beton = beton * (1 + 0.025 * trowel)[..., None]
    # ---- Anstrich: grau, stumpf, abgetreten und verschmutzt ----
    farbe = hexc("#656764") * (1 + 0.035 * nz(S, 2.3))[..., None]
    farbe = mix(farbe, hexc("#737571"), 0.35 * sm(0.3, 2.0, nz(S, 1.9)))
    duenn = sm(0.8, 2.2, nz(S, 1.7)) * sm(-0.5, 1.0, nz(S, 0.9))
    farbe = mix(farbe, beton * 0.8, 0.30 * duenn)
    # ---- Abplatzungen: grosse Flaechen, an den Fugen gehaeuft ----
    f = 0.6 * nz(S, 2.1) + 0.55 * nz(S, 1.5) + 0.25 * nz(S, 1.0, sigma_m=0.0015)
    f += 1.9 * np.exp(-dj / 0.09) + 0.5 * np.exp(-dj / 0.3)
    T = 1.29
    flake = sm(T - 0.02, T + 0.02, f)
    kante = sm(T - 0.13, T - 0.01, f) * (1 - flake)              # schmaler Saum im Anstrich am Abplatzrand
    schatten = sm(T + 0.16, T + 0.02, f) * flake                  # Schmutz auf dem Beton direkt am Rand
    alb = mix(farbe, beton, flake)
    log("  Anstrich abgeplatzt auf", round(float(flake.mean()) * 100, 1), "% der Flaeche")
    alb = mix(alb, hexc("#7e827d"), 0.32 * kante)
    alb = mix(alb, hexc("#3f3c37"), 0.30 * schatten)
    # ---- Schmutz entlang der Fugen und allgemein ----
    grime = sm(-0.2, 2.0, nz(S, 2.0) + 0.4 * nz(S, 1.2))
    alb = mix(alb, hexc("#3e3d37"), 0.16 * grime)
    alb = mix(alb, hexc("#34322d"), 0.38 * sm(0.06, 0.006, dj) * (0.5 + 0.5 * sm(-1.0, 1.0, nz(S, 1.3))))
    # ---- Schmutzraender: eingetrocknete Pfuetzen mit dunklen Raendern ----
    tide = np.zeros(S, np.float32)
    pud = np.zeros(S, np.float32)
    rings = [(0.6, 0.55, 0.34), (2.7, 3.2, 0.26), (3.35, 1.6, 0.4), (1.55, 2.45, 0.2), (0.35, 3.35, 0.28)]
    for k, (cx, cy, R0) in enumerate(rings):
        ii, xx, yy = win(cx, cy, R0 * 1.7 + 0.05)
        r = np.hypot(xx, yy)
        th = np.arctan2(yy, xx)
        rr = np.random.default_rng(800 + k)
        wob = sum(rr.uniform(0.08, 0.2) / kk * np.sin(kk * th + rr.uniform(0, 6.3)) for kk in range(2, 9))
        unev = np.clip(0.55 + 0.5 * np.sin(4 * th + rr.uniform(0, 6.3)) + 0.35 * np.sin(9 * th + rr.uniform(0, 6.3)), 0, 1)
        t_acc = np.zeros(r.shape, np.float32)
        p_acc = None
        for j, (fac, stv) in enumerate(((1.0, 1.0), (rr.uniform(0.62, 0.8), 0.22))):
            d = r - R0 * fac * (1 + wob)
            t_acc = np.maximum(t_acc, np.where(d > 0, sm(0.004, 0.0, d), sm(-0.022, 0.0, d)) * stv)
            if j == 0:
                p_acc = sm(0.0, -0.08, d)
        tide[ii] = np.maximum(tide[ii], t_acc * unev)
        pud[ii] = np.maximum(pud[ii], p_acc)
    alb = mix(alb, hexc("#55524a"), 0.06 * pud)
    alb = mix(alb, hexc("#34302a"), 0.32 * tide)
    damp = sm(0.5, 2.1, nz(S, 2.5))
    alb = alb * (1 - 0.1 * damp)[..., None]
    # ---- Gummistriemen von Schuhen, Spuren eines Essenswagens, Kratzer im Anstrich ----
    shoe = [curve((rng.uniform(0, 4), rng.uniform(0, 4)), rng.uniform(0, 6.3), rng.uniform(0.03, 0.12), rng.normal(0, 3.0), 4)
            for _ in range(120)]
    rub = raster_lines(S, shoe, 0.003, vals=rng.uniform(0.2, 0.6, len(shoe)), rough=0.8, seed=4)
    for (p0, a0, L, bend) in (((0.1, 1.55), 0.05, 3.9, 0.02), ((0.4, 2.5), -0.04, 3.4, -0.03)):
        mid = curve(p0, a0, L, bend, 60)
        for off in (-0.21, 0.21):
            pts = [(x, y + off) for x, y in mid]
            rub = np.maximum(rub, 0.3 * raster_lines(S, [pts], 0.012, vals=[0.35], rough=0.5, seed=5))
    alb = mix(alb, hexc("#1d1d1b"), 0.7 * rub * (1 - 0.6 * flake))
    scr_l = []
    for _ in range(1600):
        a = rng.uniform(0, math.pi)
        scr_l.append(curve((rng.uniform(0, 4), rng.uniform(0, 4)), a, rng.uniform(0.02, 0.14), rng.normal(0, 2.0), 3))
    scr = raster_lines(S, scr_l, 0.0004, vals=rng.uniform(0.3, 0.8, len(scr_l)), seed=6) * (1 - flake)
    alb = mix(alb, hexc("#8f938d"), 0.30 * scr)
    # ---- Flecken: Oel, Rostpunkte, zwei alte Duebelloecher einer Bettverankerung ----
    spots = sm(2.3, 3.0, nz(S, 0.25, sigma_m=0.0025))
    alb = mix(alb, hexc("#2c2a25"), 0.45 * spots)
    oil = sm(1.9, 2.6, nz(S, 1.4, sigma_m=0.02))
    alb = mix(alb, hexc("#26241f"), 0.35 * oil)
    rust = np.zeros(S, np.float32)
    loch = np.zeros(S, np.float32)
    for (cx, cy) in ((2.55, 2.32), (2.55, 1.62)):
        ii, xx, yy = win(cx, cy, 0.09)
        r = np.hypot(xx, yy)
        th = np.arctan2(yy, xx)
        rust[ii] = np.maximum(rust[ii], sm(0.06, 0.008, r) * (0.6 + 0.4 * np.sin(3 * th + cx * 7)) * 0.8)
        loch[ii] = np.maximum(loch[ii], sm(0.0065, 0.005, r))
    for k in range(9):
        cx, cy = rng.uniform(0, 4, 2)
        ii, xx, yy = win(cx, cy, 0.05)
        r = np.hypot(xx, yy)
        rust[ii] = np.maximum(rust[ii], sm(rng.uniform(0.01, 0.035), 0.0, r) * rng.uniform(0.3, 0.7))
    alb = mix(alb, hexc("#6a4329"), 0.65 * rust)
    alb = mix(alb, hexc("#171614"), 0.9 * loch)
    # ---- Fugen: Fugenmasse (Bitumen), stellenweise ausgebrochen; ausgefranste Kanten ----
    jr = (FW - 0.7 * px) * (1 - 0.22 * sm(0.0, 1.5, np.abs(nz(S, 1.0, sigma_m=0.001))))   # nie breiter als die echte Fuge
    jx = sm(jr + px * 0.7, jr - px * 0.7, dx)
    jy = sm(jr + px * 0.7, jr - px * 0.7, dy)
    joint = np.maximum(jx, jy)
    miss = sm(0.6, 1.4, nz(S, 1.2, aniso=0.2)) * 0.7
    seal = mix(hexc("#22201d") * (1 + 0.1 * nz(S, 0.8))[..., None], hexc("#0d0d0c"), miss)
    alb = mix(alb, seal, joint)
    # ---- Staub ----
    dust = sm(-0.4, 1.7, nz(S, 2.7))
    alb = mix(alb, hexc("#8b8a84"), 0.09 * dust * (1 - joint))
    # ---- Rauheit und Hoehe ----
    rough = np.where(flake > 0.5, r_b, 0.70 + 0.04 * nz(S, 1.0) - 0.08 * scr)
    rough = rough + 0.04 * grime + 0.05 * dust - 0.16 * damp - 0.06 * pud + 0.04 * tide + 0.05 * rub + 0.08 * rust
    rough = np.where(joint > 0.5, 0.72 + 0.1 * miss, rough)
    hgt = h_b + 0.00012 * trowel * flake
    hgt += 0.00032 * (1 - flake) + 0.00008 * kante + 0.00003 * nz(S, 0.9, sigma_m=0.0004) * (1 - flake)
    hgt += 0.00002 * tide - 0.00004 * scr - 0.0008 * loch
    hgt = hgt * (1 - joint) - 0.002 * joint
    return write_set(f"T_{GEB}_Boden", np.clip(alb, 0, 1), hgt, np.clip(rough, 0.42, 0.96))

# ======================= Textur "BodenDetail": Atlas =======================
def tex_detail():
    n = NPX
    px = 4.0 / n
    alb = np.zeros((n, n, 3), np.float32)
    hgt = np.zeros((n, n), np.float32)
    rgh = np.full((n, n), 0.85, np.float32)
    sd = [500]
    def nz(S, beta, aniso=1.0, sigma_m=0.0, h=False):
        sd[0] += 1
        return (frh if h else fr)(S, beta, sd[0], aniso, sigma_m)
    rng = np.random.default_rng(61)
    def region(name):
        if name == "mulde":
            u0, u1, v0, v1 = MULDE_BLOCK
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
        alb[sl], hgt[sl], rgh[sl] = np.clip(a, 0, 1), h, np.clip(r, 0.42, 1.0)

    def kiesel(S, dichte, rmin, rmax, seed, wrap=True, flach=0.0):
        """Runde Kiesel im Zementleim: Maske, Farbe je Kiesel, Kuppe (m). wrap: kachelt in U."""
        rr = np.random.default_rng(seed)
        h_, w_ = S
        N = int(dichte * h_ * w_ * px * px)
        mask = np.zeros(S, np.float32)
        col = np.zeros(S + (3,), np.float32)
        dome = np.zeros(S, np.float32)
        pal = [hexc(c) for c in ("#8e897f", "#a1998a", "#6c6963", "#978871", "#5d5954", "#aca595", "#7d7264", "#857f78")]
        for _ in range(N):
            cx, cz = rr.uniform(0, w_ * px), rr.uniform(0, h_ * px)
            r = rmin * (rmax / rmin) ** rr.random()
            el, ang = rr.uniform(0.55, 1.0), rr.uniform(0, math.pi)
            R = r + 2 * px
            c0, c1 = int((cx - R) / px), int((cx + R) / px) + 2
            r0, r1 = max(0, int((cz - R) / px)), min(h_, int((cz + R) / px) + 2)
            if r1 <= r0:
                continue
            cols = np.arange(c0, c1)
            if not wrap:
                cols = cols[(cols >= 0) & (cols < w_)]
                if len(cols) == 0:
                    continue
            xx = ((cols + 0.5) * px - cx).astype(np.float32)[None, :]
            zz = ((np.arange(r0, r1) + 0.5) * px - cz).astype(np.float32)[:, None]
            ca, sa = math.cos(ang), math.sin(ang)
            xr, zr = xx * ca + zz * sa, -xx * sa + zz * ca
            q = np.sqrt((xr / r) ** 2 + (zr / (r * el)) ** 2)
            m = sm(1.0, 0.82, q)
            ii = np.ix_(np.arange(r0, r1), cols % w_)
            neu = m > mask[ii]
            c = pal[rr.integers(len(pal))] * (1 + 0.07 * rr.normal())
            col[ii] = np.where(neu[..., None], c, col[ii])
            mask[ii] = np.maximum(mask[ii], m)
            dome[ii] = np.maximum(dome[ii], np.clip(1 - q * q, 0, 1) ** 0.5 * r * (0.45 - flach))
        return mask, col, dome

    def roh(S, Z=None, dunkel=0.0, grob=1.0, seed=0, flach=0.15):
        """Gebrochener roher Beton mit Kieseln (Zuschlag), staubig und stellenweise feucht."""
        a, h, r = beton_farbe(S, nz, grob=1.0)
        a = a * (0.93 - 0.12 * dunkel)
        km, kc, kd = kiesel(S, 2600 * grob, 0.0025, 0.011, 700 + seed, flach=flach)
        kc = kc * (1 + 0.06 * nz(S, 0.9))[..., None]
        a = mix(a, kc, 0.92 * km)
        crev = sm(0.05, 0.3, km) * sm(0.85, 0.5, km)          # Fuge zwischen Kiesel und Zementleim
        a = mix(a, hexc("#2e2c29"), 0.15 * crev)
        rau = nz(S, 1.2, sigma_m=0.0012) + 0.5 * nz(S, 0.8, sigma_m=0.0006)
        dust = sm(0.2, 1.8, nz(S, 2.3))
        a = mix(a, hexc("#a29d93"), 0.16 * dust)
        damp = sm(0.6, 2.0, nz(S, 2.4)) * (0.6 + 0.6 * dunkel)
        a = a * (1 - 0.2 * damp)[..., None]
        h = h + 0.0005 * rau + kd - 0.0003 * crev
        r = r + 0.03 * km - 0.18 * damp + 0.03 * dust
        return a, h, r, km

    # ---- Laufweg: Anstrich abgelaufen, Beton glatt getreten (U entlang des Wegs) ----
    def abgelaufen(S, X, Z, hoehe, raender=True):
        a, h, r = beton_farbe(S, nz, grob=0.45)
        a = mix(a, hexc("#7a766e"), 0.35)
        km, kc, kd = kiesel(S, 5200, 0.0012, 0.004, 900 + int(hoehe * 100), flach=0.3)
        a = mix(a, kc * 0.95, 0.55 * km)
        streif = frh(S, 1.6, sd[0] + 1, 6.0)
        sd[0] += 1
        grime = sm(-0.4, 1.6, nz(S, 1.6) + 0.4 * streif)
        a = mix(a, hexc("#3f3d38"), 0.16 * grime)
        a = a * 0.93
        damp = sm(0.6, 2.1, nz(S, 2.5))
        a = a * (1 - 0.15 * damp)[..., None]
        rand = (np.exp(-Z / 0.09) + np.exp(-(hoehe - Z) / 0.09)) if raender else np.zeros(S, np.float32)
        reste = sm(1.75, 1.85, 0.8 * nz(S, 1.9) + 0.35 * nz(S, 1.1, sigma_m=0.002) + 1.1 * rand)
        farbe = hexc("#656764") * (1 + 0.04 * nz(S, 1.5))[..., None]
        a = mix(a, farbe, reste)
        a = mix(a, hexc("#7f837e"), 0.3 * sm(1.6, 1.75, 0.8 * nz(S, 1.9) + 1.1 * rand) * (1 - reste))
        shoe = [curve((rng.uniform(0, 4), rng.uniform(0, hoehe)), rng.normal(0, 0.3) + (math.pi if rng.random() < 0.5 else 0.0),
                      rng.uniform(0.03, 0.12), rng.normal(0, 0.8), 4) for _ in range(int(130 * hoehe))]
        rub = raster_lines(S, shoe, 0.006, wrap=(4.0, None), vals=rng.uniform(0.15, 0.4, len(shoe)), rough=0.7,
                           seed=int(hoehe * 1000))
        a = mix(a, hexc("#2a2926"), 0.4 * rub * (1 - reste))
        scl = [curve((rng.uniform(0, 4), rng.uniform(0, hoehe)), rng.normal(0, 0.12), rng.uniform(0.04, 0.3), rng.normal(0, 0.8), 4)
               for _ in range(int(160 * hoehe))]
        scr = raster_lines(S, scl, 0.0004, wrap=(4.0, None), vals=rng.uniform(0.3, 0.8, len(scl)), seed=int(hoehe * 1000) + 1)
        a = mix(a, hexc("#8f8c85"), 0.14 * scr)
        h = 0.4 * h + 0.3 * kd + 0.0003 * reste - 0.00003 * scr + 0.00004 * streif
        r = 0.66 + 0.05 * nz(S, 1.0) + 0.08 * grime - 0.12 * damp + 0.06 * reste + 0.06 * rub
        return a, h, r, reste

    sl, X, Z, S = region("laufweg")
    a, h, r, _ = abgelaufen(S, X, Z, REG["laufweg"][1] - REG["laufweg"][0])
    put(sl, a, h, r)

    # ---- gelbe Wegmarkierung, 10 cm breit (Z 0,01 .. 0,11), verblasst und durchgetreten ----
    sl, X, Z, S = region("markierung")
    a, h, r, _ = abgelaufen(S, X, Z, 0.12, raender=False)
    zack = 0.0012 * nz(S, 1.0, sigma_m=0.0008)
    linie = sm(0.0095, 0.0105, Z + zack) * sm(0.1105, 0.1095, Z - zack)
    wear = 0.9 * nz(S, 1.6) + 0.45 * nz(S, 0.9, sigma_m=0.0012)
    bleibt = sm(-0.5, -0.2, wear) * linie
    gelb = hexc("#958552") * (1 + 0.05 * nz(S, 1.4))[..., None]
    gelb = mix(gelb, hexc("#aaa083"), 0.3 * sm(0.2, 1.8, nz(S, 2.0)))
    gelb = mix(gelb, hexc("#5a5240"), 0.35 * sm(-0.2, 1.8, nz(S, 2.2)))
    duenn = sm(0.3, -0.2, wear) * linie * (1 - bleibt)
    a = mix(a, gelb, 0.85 * bleibt)
    a = mix(a, mix(a, gelb, 0.4), duenn)
    h = h + 0.0003 * bleibt
    r = np.where(bleibt > 0.5, 0.7 + 0.05 * nz(S, 1.0), r)
    put(sl, a, h, r)

    # ---- roher Beton mit Kieseln (Abplatzungen, Rissflanken, Bruchkanten, Kruemel, Unterseiten) ----
    sl, X, Z, S = region("beton_roh")
    a, h, r, _ = roh(S, Z, dunkel=0.2, seed=1)
    put(sl, a, h, r)

    # ---- Rinne: Gitter, Rahmen, Rostzone mit Rostlaeufern (y = 0 bei Z = RINNE_M) ----
    sl, X, Z, S = region("rinne")
    y = Z - RINNE_M
    ay = np.abs(y)
    a_b, h_b, r_b = beton_farbe(S, nz)
    nass = sm(0.30, 0.10, ay) * (0.6 + 0.4 * sm(-1.0, 1.0, nz(S, 1.5)))
    a = a_b * (1 - 0.32 * nass)[..., None]
    a = mix(a, hexc("#433e36"), 0.3 * sm(0.0, 1.8, nz(S, 2.2)))
    lauf = np.zeros(S, np.float32)
    for k in range(90):
        x0 = (rng.uniform(0, 8) // 1) * 0.5 + rng.normal(0, 0.03) if rng.random() < 0.45 else rng.uniform(0, 4)
        L = rng.uniform(0.04, 0.3)
        w = rng.uniform(0.008, 0.04)
        sg = 1 if rng.random() < 0.5 else -1
        pts = [(x0 + 0.02 * math.sin(t * 7 + k) * t, RINNE_M + sg * (KH + t * L)) for t in np.linspace(0, 1, 12)]
        m = raster_lines(S, [pts], w, wrap=(4.0, None), vals=[rng.uniform(0.4, 0.9)], rough=0.6, seed=2000 + k)
        lauf = np.maximum(lauf, m * sm(KH + L * 1.05, KH, ay))
    lauf = lauf * (0.6 + 0.4 * sm(-1.2, 1.2, nz(S, 1.2)))
    halo = sm(0.2, 0.1, ay) * (0.5 + 0.5 * sm(-1.0, 1.0, nz(S, 1.8)))
    a = mix(a, hexc("#6a3f25"), 0.75 * np.maximum(lauf, 0.6 * halo))
    a = mix(a, hexc("#3c2a1d"), 0.4 * lauf * sm(0.12, 0.1, ay))
    schlamm = sm(0.125, 0.1, ay) * sm(0.2, 1.4, nz(S, 1.3) + 0.6)
    a = mix(a, hexc("#2d261f"), 0.6 * schlamm)
    h = h_b * 0.8 + 0.00004 * lauf
    r = r_b - 0.25 * nass - 0.05 * lauf
    # Rahmen (Stahlwinkel), Spalt, Gussgitter, Schlitze, Stoesse der Gitterstuecke
    eisen = hexc("#3b3733") * (1 + 0.08 * nz(S, 1.4))[..., None]
    rost = sm(-0.3, 1.2, nz(S, 1.7) + 0.4 * nz(S, 0.8))
    eisen = mix(eisen, hexc("#5d3b26"), 0.7 * rost)
    eisen = mix(eisen, hexc("#7a4a2b"), 0.35 * sm(1.0, 2.0, nz(S, 1.2)))
    grat = sm(-0.5, 1.0, nz(S, 0.9, sigma_m=0.0008))
    rahmen = (ay > KR + 0.001) & (ay <= KH)
    gitter = ay <= KR - 0.001
    spalt = np.abs(ay - KR) <= 0.001
    a = np.where((rahmen | gitter)[..., None], eisen, a)
    slot = np.zeros(S, bool)
    for (xa, xb) in gitter_schlitze():
        slot |= (X >= xa + P2) & (X < xb + P2)
    slot &= ay < KS
    stoss = (pdist(X, 0.0, ABSCHNITT) < 0.0012) & (ay <= KR)
    tief = slot | stoss | spalt
    a = np.where(tief[..., None], hexc("#0f0e0d"), a)
    abgetreten = gitter & ~slot & (sm(-0.2, 1.0, nz(S, 1.1)) > 0.5)
    a = np.where(abgetreten[..., None], a * 0.82 + hexc("#4a4744") * 0.18, a)
    h = np.where(rahmen | gitter, 0.00004 * grat, h)
    h = np.where(tief, -0.004, h)
    r = np.where(rahmen | gitter, 0.78 + 0.08 * rost - 0.1 * abgetreten, r)
    r = np.where(tief, 0.9, r)
    put(sl, a, h, r)

    # ---- Inneres des Troges: Waende (Z 0 .. 0,075 = z -0,10 .. -0,025) und Boden mit Schlamm (Z 0,08 .. 0,25) ----
    sl, X, Z, S = region("rinne_innen")
    wand = hexc("#35302b") * (1 + 0.08 * nz(S, 1.2))[..., None]
    wand = mix(wand, hexc("#5a3824"), 0.6 * sm(-0.4, 1.2, nz(S, 1.6)))
    linien = sm(0.6, 1.0, np.sin(2 * np.pi * Z / 0.013 + 1.5 * nz(S, 1.4)) * 0.5 + 0.5) * (Z < 0.075)
    wand = mix(wand, hexc("#211c18"), 0.35 * linien + 0.5 * sm(0.025, 0.0, Z))
    boden = hexc("#231d18") * (1 + 0.12 * nz(S, 1.0))[..., None]
    km, kc, kd = kiesel(S, 900, 0.002, 0.007, 1300)
    boden = mix(boden, kc * 0.55, 0.7 * km)
    boden = mix(boden, hexc("#4d3020"), 0.4 * sm(0.0, 1.6, nz(S, 1.5)))
    istb = Z >= 0.0775
    a = np.where(istb[..., None], boden, wand)
    h = np.where(istb, 0.0004 * nz(S, 1.0) + kd * 0.6, 0.0002 * nz(S, 1.3))
    r = np.where(istb, 0.5 + 0.1 * km + 0.08 * nz(S, 1.0), 0.8 + 0.06 * nz(S, 1.0))
    put(sl, a, h, r)

    # ---- Plattenkante: Schnitt durch Beton (Z 0 .. 0,2 = z -0,2 .. 0), Estrich, Anstrich oben ----
    sl, X, Z, S = region("kante")
    a, h, r, km = roh(S, Z, dunkel=0.0, seed=2)
    est = Z > 0.16
    a_e, h_e, r_e = beton_farbe(S, nz, grob=0.6)
    a = np.where(est[..., None], a_e * 0.97, a)
    h = np.where(est, h_e, h)
    r = np.where(est, r_e, r)
    a = np.where((np.abs(Z - 0.16) < 0.0012)[..., None], hexc("#4e4a44"), a)
    a = np.where((Z > 0.1994)[..., None], hexc("#656764"), a)
    put(sl, a, h, r)

    # ---- Fuge: Flanke (Z 0,002 .. 0,010 ueber dem Fugengrund) und Fugenmasse (Z 0,016 .. 0,024) ----
    sl, X, Z, S = region("fuge")
    flanke = hexc("#77736b") * (1 + 0.08 * nz(S, 1.2))[..., None]
    flanke = mix(flanke, hexc("#3b3934"), 0.5 * sm(0.006, 0.002, Z))
    masse = hexc("#201e1b") * (1 + 0.12 * nz(S, 0.8))[..., None]
    fehlt = sm(0.5, 1.3, nz(S, 1.2, aniso=0.15))
    masse = mix(masse, hexc("#0c0c0b"), 0.7 * fehlt)
    masse = mix(masse, hexc("#6c675e"), 0.2 * sm(0.5, 1.8, nz(S, 1.8)))
    istm = Z > 0.0125
    a = np.where(istm[..., None], masse, flanke)
    h = np.where(istm, -0.0006 * fehlt + 0.00005 * nz(S, 0.7), 0.00008 * nz(S, 1.0))
    r = np.where(istm, 0.72 + 0.12 * fehlt, 0.88)
    put(sl, a, h, r)

    # ---- Riffelblech der Schwelle (1,0 x 0,2 m, Einzelflaeche): Traenenmuster, verrostet ----
    sl, X, Z, S = region("riffelblech")
    xl, yl = X, Z
    p = 0.025
    ii_, jj_ = np.floor(xl / p), np.floor(yl / p)
    fx, fy = xl - (ii_ + 0.5) * p, yl - (jj_ + 0.5) * p
    sgn = np.where(((ii_ + jj_) % 2) == 0, 1.0, -1.0)
    ua, va = (fx + sgn * fy) / math.sqrt(2), (-sgn * fx + fy) / math.sqrt(2)
    q = np.sqrt((ua / 0.0095) ** 2 + (va / 0.0026) ** 2)
    rib = np.clip(1 - q * q, 0, 1) ** 0.5
    stahl = hexc("#4b4038") * (1 + 0.07 * nz(S, 1.3))[..., None]
    rost = sm(-1.9, -0.1, nz(S, 1.8) + 0.5 * nz(S, 1.0))
    a = mix(stahl, hexc("#7a4a2c"), 0.9 * rost)
    a = mix(a, hexc("#8a552f"), 0.3 * sm(0.8, 2.0, nz(S, 1.1)))
    mitte = sm(0.06, 0.0, np.abs(yl - 0.1)) * sm(0.05, 0.12, xl) * sm(0.95, 0.88, xl)
    a = mix(a, hexc("#2f2a25"), 0.45 * rib * mitte)
    a = mix(a, hexc("#29231e"), 0.35 * (1 - rib) * sm(0.0, 1.5, nz(S, 1.4)))
    pits = sm(2.0, 2.8, nz(S, 0.3, sigma_m=0.0008))
    a = mix(a, hexc("#1d1915"), 0.6 * pits)
    kopf = np.zeros(S, np.float32)
    schlitz = np.zeros(S, np.float32)
    for (sx, sy) in SCHRAUBEN:
        rr_ = np.hypot(xl - (sx + SW), yl - (sy + ST))
        kopf = np.maximum(kopf, sm(SCHRAUBE_R + 0.0008, SCHRAUBE_R, rr_))
        schlitz = np.maximum(schlitz, (np.abs(yl - (sy + ST)) < 0.0011) * (rr_ < SCHRAUBE_R - 0.0015))
    a = mix(a, hexc("#4a3a2c") * (1 + 0.1 * nz(S, 1.0))[..., None], kopf)
    a = mix(a, hexc("#0e0d0c"), schlitz)
    a = mix(a, hexc("#16130f"), sm(SCHRAUBE_R + 0.0015, SCHRAUBE_R + 0.0004, np.min(
        [np.hypot(xl - (sx + SW), yl - (sy + ST)) for sx, sy in SCHRAUBEN], axis=0)) * (1 - kopf))
    h = 0.0013 * rib * (1 - kopf) - 0.0002 * pits + 0.00006 * nz(S, 1.2) - 0.0009 * schlitz
    r = 0.8 + 0.08 * rost - 0.2 * rib * mitte + 0.05 * pits
    put(sl, a, h, r)

    # ---- Kante des Blechs, Bewehrung, Gusseisen ----
    sl, X, Z, S = region("stahlkante")
    a = mix(hexc("#3b342e"), hexc("#61402a"), 0.6 * sm(-0.5, 1.2, nz(S, 1.4)))
    put(sl, a * (1 + 0.08 * nz(S, 1.0))[..., None], 0.0001 * nz(S, 1.2, h=True), 0.82 + 0.05 * nz(S, 1.0))
    sl, X, Z, S = region("bewehrung")
    c_ = Z - 0.009
    umf = 2 * math.pi * STAB_R
    rippe = sm(0.16, 0.06, np.abs(np.mod((X + 0.25 * c_) / 0.0072, 1.0) - 0.5))
    laengs = np.maximum(sm(0.0011, 0.0, np.abs(c_ - umf * 0.25)), sm(0.0011, 0.0, np.abs(c_ - umf * 0.75)))
    rost = sm(-0.8, 1.0, nz(S, 1.6))
    a = mix(hexc("#4b3426"), hexc("#74482d"), 0.55 * rost)
    a = mix(a, hexc("#2b2119"), 0.45 * sm(0.6, 1.8, nz(S, 1.1)))
    a = mix(a, a * 0.75, 0.4 * rippe)
    put(sl, a, 0.0005 * np.maximum(rippe, laengs) + 0.00008 * nz(S, 1.0), 0.86 + 0.06 * rost)
    sl, X, Z, S = region("schwelle_kante")
    a, h, r, km = roh(S, Z, dunkel=0.1, seed=4)
    blech = Z > 0.2 - BLECH
    a_s = mix(hexc("#3b342e"), hexc("#61402a"), 0.6 * sm(-0.5, 1.2, nz(S, 1.4)))
    a = np.where(blech[..., None], a_s, a)
    a = np.where((np.abs(Z - (0.2 - BLECH)) < 0.0008)[..., None], hexc("#2a2622"), a)
    h = np.where(blech, 0.0001 * nz(S, 1.2, h=True), h)
    r = np.where(blech, 0.82, r)
    put(sl, a, h, r)
    sl, X, Z, S = region("eisen")
    a = hexc("#37332f") * (1 + 0.09 * nz(S, 1.3))[..., None]
    a = mix(a, hexc("#5a3925"), 0.6 * sm(-0.3, 1.3, nz(S, 1.6)))
    put(sl, a, 0.00012 * nz(S, 1.2), 0.82 + 0.05 * nz(S, 1.0))

    # ---- Mulde der Platte 03 (Einzelflaeche): Bruchflaeche mit Kieseln, rostige Bewehrung, Rostwasser ----
    sl, X, Z, S = region("mulde")
    u0, u1, v0, v1 = MULDE_BLOCK
    xw = MX + X - (u1 - u0) / 2
    yw = MY + Z - (v1 - v0) / 2
    ue, ve = (xw - MX) / M_A, (yw - MY) / M_B
    ang = np.arctan2(ve, ue)
    tab_a = np.linspace(-math.pi, math.pi, 2049)
    tab_r = np.array([mulde_r(t) for t in tab_a], np.float32)
    t = np.hypot(ue, ve) / np.interp(ang, tab_a, tab_r)
    innen = t < 1.0
    a_o, h_o, r_o = beton_farbe(S, nz)
    a_o = mix(a_o, hexc("#45413a"), 0.35 * sm(-0.3, 1.8, nz(S, 2.0)))
    ring = mulde_ring()
    phi_r = np.array([math.atan2(y - MY, x - MX) for x, y in ring])
    rho_r = np.array([math.hypot(x - MX, y - MY) for x, y in ring])
    o = np.argsort(phi_r)
    phi_r, rho_r = phi_r[o], rho_r[o]
    phi_r = np.concatenate([phi_r - 2 * math.pi, phi_r, phi_r + 2 * math.pi])
    rho_r = np.concatenate([rho_r, rho_r, rho_r])
    t_ring = np.hypot(xw - MX, yw - MY) / np.interp(np.arctan2(yw - MY, xw - MX), phi_r, rho_r)
    a_o = mix(a_o, hexc("#3a3731"), 0.45 * sm(0.75, 1.0, t_ring))
    lauf = sm(0.4, 1.6, nz(S, 1.6) + 0.8 * sm(1.4, 1.0, t)) * sm(1.0, 0.85, t_ring)
    a_o = mix(a_o, hexc("#5b3f2a"), 0.35 * lauf)
    a_o = a_o * 0.9
    a_i, h_i, r_i, km = roh(S, None, dunkel=1.0, grob=1.2, seed=3, flach=0.3)
    a_i = a_i * 0.86
    a_i = mix(a_i, hexc("#9b968c"), 0.25 * sm(0.93, 1.0, t))
    rost = np.zeros(S, np.float32)
    nah_rand = sm(1.12, 1.0, t)
    fleck = sm(-0.6, 1.2, nz(S, 1.3))
    for pfad, rs in STAEBE:
        for (x0, y0, _), (x1, y1, _) in zip(pfad, pfad[1:]):
            dxs, dys = x1 - x0, y1 - y0
            L2 = dxs * dxs + dys * dys
            tt = np.clip(((xw - x0) * dxs + (yw - y0) * dys) / L2, 0, 1)
            d = np.hypot(xw - (x0 + tt * dxs), yw - (y0 + tt * dys))
            rost = np.maximum(rost, np.exp(-np.maximum(d - rs, 0) / 0.006) * np.where(innen, 0.3 + 0.5 * fleck, 0.35 * fleck * nah_rand))
    pfuetze = sm(0.45, 0.25, t + 0.15 * nz(S, 1.8))
    rand_p = sm(0.02, 0.0, np.abs(t + 0.15 * nz(S, 1.8) - 0.43))
    a_i = mix(a_i, hexc("#5a3a26"), 0.45 * pfuetze)
    a_i = mix(a_i, hexc("#3c2618"), 0.55 * rand_p)
    a = np.where(innen[..., None], a_i, a_o)
    a = mix(a, hexc("#6a432a"), 0.55 * rost)
    a = mix(a, hexc("#45291a"), 0.35 * rost * innen)
    h = np.where(innen, h_i, h_o) + 0.00003 * rost
    r = np.where(innen, r_i - 0.2 * pfuetze, r_o) + 0.04 * rost
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

def welle_fn(seed, amp=0.0007):
    """Leichte Unebenheit des alten Betons, am Rand auf 0."""
    off = Vector((seed * 3.1, seed * 1.7, seed * 0.9))
    def h(x, y):
        f = randblende(x, y)
        if f == 0.0:
            return 0.0
        return f * amp * (noise.noise(Vector((x * 0.8, y * 0.8, 0.0)) + off) + 0.4 * noise.noise(Vector((x * 2.1, y * 2.1, 0.5)) + off))
    return h

def rampe(s):
    """Tiefe der Fuge entlang der Fuge: 1 im Inneren, 0 am flachen Rand."""
    return glatt((INNEN - abs(s)) / RAMPE)

def rechteck(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

def umfang_t(x, y, h):
    """Lage eines Punkts auf dem Rand eines Quadrats (halbe Seite h), gegen den Uhrzeigersinn ab (-h, -h)."""
    if abs(y + h) < 1e-7:
        return x + h
    if abs(x - h) < 1e-7:
        return 2 * h + (y + h)
    if abs(y - h) < 1e-7:
        return 4 * h + (h - x)
    return 6 * h + (h - y)

def uv_rinne(x, y):
    return ((x + P2) * UVS, (REG["rinne"][0] + RINNE_M + y) * UVS)

def uv_mulde(x, y):
    u0, u1, v0, v1 = MULDE_BLOCK
    return ((u0 + (u1 - u0) / 2 + x - MX) * UVS, (v0 + (v1 - v0) / 2 + y - MY) * UVS)

# ---------- Oberseite ----------
class Oberflaeche:
    """CDT der Oberseite: Punkte mit Zusatzhoehe, Zwangskanten, Loecher (Fugen, Rinne, Risse, Mulde) und Bereiche,
    die im Detail-Atlas liegen. Die aeusseren 5 cm bleiben durch die Zwangskante bei +-1,95 m exakt flach auf Z = 0."""
    def __init__(self, welle, maske=None):
        self.P, self.dz, self.key = [], [], {}
        self.E = []
        self.holes = []          # Indexschleifen (Zwangskante und Loch)
        self.loecher = []        # Polygone fuer den Schwerpunkttest
        self.regionen = []       # (Polygon, Huelle, uv-Funktion): Flaechen im Detail-Atlas
        self.sperr = []          # (Polygon, Abstand): keine Fuellpunkte
        self.innen, self.aussen = [], []
        self.welle = welle
        self.maske = maske or (lambda x, y: 1.0)

    def pt(self, x, y, dz=0.0):
        k = (round(x, 6), round(y, 6))
        i = self.key.get(k)
        if i is not None:
            self.dz[i] = min(self.dz[i], dz)
            return i
        self.P.append((x, y))
        self.dz.append(dz)
        self.key[k] = len(self.P) - 1
        return len(self.P) - 1

    def line(self, idx, closed=False):
        seq = list(idx) + ([idx[0]] if closed else [])
        for a, b in zip(seq, seq[1:]):
            if a != b:
                self.E.append((a, b))

    def loch(self, poly):
        self.loecher.append((poly, bbox(poly)))

    def region(self, poly, uvf, vorne=False):
        e = (poly, bbox(poly), uvf)
        if vorne:
            self.regionen.insert(0, e)
        else:
            self.regionen.append(e)

    def z(self, x, y, dz=0.0):
        if max(abs(x), abs(y)) >= INNEN - 1e-9:
            return 0.0
        return self.welle(x, y) * self.maske(x, y) + dz * randblende(x, y)

    def gesperrt(self, x, y, extra=0.0):
        for poly, rand in self.sperr:
            bb = bbox(poly, rand + extra)
            if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]:
                if point_in(poly, x, y) or poly_dist(poly, x, y) < rand + extra:
                    return True
        return False

    def gitter(self, step=0.3, abstand=0.07, bereich=None):
        cell = {}
        for (x, y) in self.P:
            cell.setdefault((math.floor(x / abstand), math.floor(y / abstand)), []).append((x, y))
        x0, y0, x1, y1 = bereich or (-INNEN + 0.1, -INNEN + 0.1, INNEN - 0.1, INNEN - 0.1)
        nx_, ny_ = max(1, int(round((x1 - x0) / step))), max(1, int(round((y1 - y0) / step)))
        for i in range(nx_ + 1):
            for j in range(ny_ + 1):
                x, y = x0 + (x1 - x0) * i / nx_, y0 + (y1 - y0) * j / ny_
                cx, cy = math.floor(x / abstand), math.floor(y / abstand)
                if any(math.hypot(px - x, py - y) < abstand for di in (-1, 0, 1) for dj in (-1, 0, 1)
                       for (px, py) in cell.get((cx + di, cy + dj), ())):
                    continue
                if self.gesperrt(x, y) or any(bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3] and point_in(h, x, y)
                                              for h, bb in self.loecher):
                    continue
                self.pt(x, y)
                cell.setdefault((cx, cy), []).append((x, y))

    def bauen(self, pc):
        for hh, extra in ((P2, self.aussen), (INNEN, self.innen)):
            pts = {(round(p[0], 6), round(p[1], 6)) for p in [(-hh, -hh), (hh, -hh), (hh, hh), (-hh, hh)] + list(extra)}
            pts = sorted(pts, key=lambda p: umfang_t(p[0], p[1], hh))
            self.line([self.pt(p[0], p[1]) for p in pts], True)
        for h in self.holes:
            self.line(h, True)
        co, _, tris, orig_v, _, _ = geometry.delaunay_2d_cdt([Vector(p) for p in self.P], self.E, [], 0, 1e-9)
        neu = sum(1 for ov in orig_v if not ov)
        if neu:
            log("  Hinweis:", pc.name, neu, "Schnittpunkte von Zwangskanten in der Oberflaeche:",
                [tuple(round(v, 3) for v in co[k]) for k, ov in enumerate(orig_v) if not ov][:8])
        bv = []
        for k, c in enumerate(co):
            i0 = orig_v[k][0] if orig_v[k] else None
            bv.append(pc.bm.verts.new((c.x, c.y, self.z(c.x, c.y, self.dz[i0] if i0 is not None else 0.0))))
        for (a, b, c) in tris:
            pa, pb, pcc = co[a], co[b], co[c]
            cr = (pb - pa).cross(pcc - pa)
            if abs(cr) < 1e-11:
                continue
            if cr < 0:
                b, c = c, b
            mx, my = (pa.x + pb.x + pcc.x) / 3, (pa.y + pb.y + pcc.y) / 3
            if any(bb[0] <= mx <= bb[2] and bb[1] <= my <= bb[3] and point_in(hh, mx, my) for hh, bb in self.loecher):
                continue
            reg = next((r for r in self.regionen if r[1][0] <= mx <= r[1][2] and r[1][1] <= my <= r[1][3]
                        and point_in(r[0], mx, my)), None)
            if reg is None:
                pc.face([bv[a], bv[b], bv[c]], MB, [uv_welt(co[v].x, co[v].y) for v in (a, b, c)], smooth=True)
            else:
                pc.face([bv[a], bv[b], bv[c]], MD, [reg[2](co[v].x, co[v].y) for v in (a, b, c)], smooth=True)

def zipper(pc, A, B, mat, uvf, want):
    """Dreiecksband zwischen zwei Raendern A und B: Listen von (s, Vector) mit steigendem s, gleiche Enden."""
    va = [(s, pc.bm.verts.new(p)) for s, p in A]
    vb = [(s, pc.bm.verts.new(p)) for s, p in B]
    i = j = 0
    while i < len(va) - 1 or j < len(vb) - 1:
        if j == len(vb) - 1 or (i < len(va) - 1 and va[i + 1][0] <= vb[j + 1][0]):
            tri = [va[i][1], va[i + 1][1], vb[j][1]]
            i += 1
        else:
            tri = [va[i][1], vb[j + 1][1], vb[j][1]]
            j += 1
        if (tri[1].co - tri[0].co).cross(tri[2].co - tri[0].co).length < 1e-12:
            continue
        pc.face(tri, mat, [uvf(v.co) for v in tri], want=want)

# ---------- Dehnfugen ----------
class Seite:
    """Rand eines Feldes entlang einer Fuge oder der Rinne; Punkte (s, Zusatzhoehe) entlang der Seite."""
    def __init__(self, ori, c, s0, s1, nach, art):
        self.ori, self.c, self.s0, self.s1, self.nach, self.art = ori, c, s0, s1, nach, art
        self.p = {}
        n = max(1, math.ceil((s1 - s0) / 0.25 - 1e-9))
        for k in range(n + 1):
            self.add(s0 + (s1 - s0) * k / n)
        for s in (-1.9, -1.85, -1.8, -1.75, 1.75, 1.8, 1.85, 1.9):
            if s0 < s < s1:
                self.add(s)

    def add(self, s, dz=0.0):
        k = round(s, 6)
        self.p[k] = min(self.p.get(k, 0.0), dz)

    def absenken(self, s0, s1, f):
        for k in list(self.p):
            if s0 < k < s1:
                self.p[k] = min(self.p[k], f(k))

    def xy(self, s):
        return (self.c, s) if self.ori == "v" else (s, self.c)

    def punkte(self):
        return sorted(self.p.items())

class Netz:
    """Felder zwischen den Dehnfugen (alle 2 m, bei x und y = +-1) und, auf Platte 04, der Rinne."""
    def __init__(self, F, kanal=False):
        self.F, self.kanal = F, kanal
        XI = [(-INNEN, FUGEN[0] - FW), (FUGEN[0] + FW, FUGEN[1] - FW), (FUGEN[1] + FW, INNEN)]
        YI = list(XI) if not kanal else [(-INNEN, FUGEN[0] - FW), (FUGEN[0] + FW, -KH), (KH, FUGEN[1] - FW), (FUGEN[1] + FW, INNEN)]
        self.XI, self.YI = XI, YI
        self.seiten = {}
        for (xa, xb) in XI:
            for (ya, yb) in YI:
                if xa > -INNEN + 1e-9:
                    self._seite("v", xa, ya, yb, -1, "fuge")
                if xb < INNEN - 1e-9:
                    self._seite("v", xb, ya, yb, 1, "fuge")
                if ya > -INNEN + 1e-9:
                    self._seite("h", ya, xa, xb, -1, "rinne" if kanal and abs(ya - KH) < 1e-9 else "fuge")
                if yb < INNEN - 1e-9:
                    self._seite("h", yb, xa, xb, 1, "rinne" if kanal and abs(yb + KH) < 1e-9 else "fuge")
        for c in FUGEN:
            for sg in (-1, 1):
                F.innen += [(c - FW, sg * INNEN), (c + FW, sg * INNEN), (sg * INNEN, c - FW), (sg * INNEN, c + FW)]
            F.loch(rechteck(c - FW, -INNEN, c + FW, INNEN))
            F.loch(rechteck(-INNEN, c - FW, INNEN, c + FW))
            F.sperr.append((rechteck(c - FW, -INNEN, c + FW, INNEN), 0.03))
            F.sperr.append((rechteck(-INNEN, c - FW, INNEN, c + FW), 0.03))
        if kanal:
            F.innen += [(sg * INNEN, sk * KH) for sg in (-1, 1) for sk in (-1, 1)]
            F.loch(rechteck(-INNEN, -KH, INNEN, KH))
            F.sperr.append((rechteck(-INNEN, -KH, INNEN, KH), 0.03))

    def _seite(self, ori, c, s0, s1, nach, art):
        self.seiten[(ori, round(c, 6), round(s0, 6), round(s1, 6))] = Seite(ori, c, s0, s1, nach, art)

    def seite_bei(self, ori, c, s):
        for (o, cc, s0, s1), sd in self.seiten.items():
            if o == ori and abs(cc - c) < 1e-6 and s0 - 1e-9 <= s <= s1 + 1e-9:
                return sd
        raise RuntimeError(f"keine Feldseite {ori} {c} bei {s}")

    def fertig(self):
        """Seiten als Zwangskanten in die Oberflaeche eintragen (nach allen Abplatzungen und Kreuzungen)."""
        for sd in self.seiten.values():
            self.F.line([self.F.pt(*sd.xy(s), dz) for s, dz in sd.punkte()])

    def boden_z(self, sd, s):
        x, y = sd.xy(s)
        return self.F.z(x, y) - FT * rampe(s)

    def bauen(self, pc):
        F = self.F
        v0 = REG["fuge"][0]
        # Flanken
        for sd in self.seiten.values():
            if sd.art != "fuge":
                continue
            want = (sd.nach, 0, 0) if sd.ori == "v" else (0, sd.nach, 0)
            pts = sd.punkte()
            for (sa, da), (sb, db) in zip(pts, pts[1:]):
                (xa, ya), (xb, yb) = sd.xy(sa), sd.xy(sb)
                ta, tb = F.z(xa, ya, da), F.z(xb, yb, db)
                ba, bb = self.boden_z(sd, sa), self.boden_z(sd, sb)
                q = [(Vector((xa, ya, ta)), sa, ta - ba), (Vector((xb, yb, tb)), sb, tb - bb),
                     (Vector((xb, yb, bb)), sb, 0.0), (Vector((xa, ya, ba)), sa, 0.0)]
                q = [e for k, e in enumerate(q) if not (k >= 2 and abs(q[3 - k][2]) < 1e-7)]
                if len(q) < 3:
                    continue
                pc.face([e[0] for e in q], MD, [((e[1] + P2) * UVS, (v0 + 0.002 + e[2]) * UVS) for e in q], want=want)
        # Fugengrund (Fugenmasse)
        def kante(sd):
            return [(s, Vector((*sd.xy(s), self.boden_z(sd, s)))) for s, _ in sd.punkte()]
        for c in FUGEN:
            for (ya, yb) in self.YI:
                A = kante(self.seiten[("v", round(c - FW, 6), round(ya, 6), round(yb, 6))])
                B = kante(self.seiten[("v", round(c + FW, 6), round(ya, 6), round(yb, 6))])
                zipper(pc, A, B, MD, lambda p, c=c: ((p.y + P2) * UVS, (v0 + 0.016 + p.x - (c - FW)) * UVS), (0, 0, 1))
                for yk in (ya, yb):
                    if self.kanal and abs(abs(yk) - KH) < 1e-9:
                        sg = 1 if yk > 0 else -1
                        zf = -FT * rampe(yk)
                        q = [Vector((c - FW, yk, 0.0)), Vector((c + FW, yk, 0.0)), Vector((c + FW, yk, zf)), Vector((c - FW, yk, zf))]
                        flach(pc, q, "eisen", (0, sg, 0))
            A, B = [], []
            for (xa, xb) in self.XI:
                A += kante(self.seiten[("h", round(c - FW, 6), round(xa, 6), round(xb, 6))])
                B += kante(self.seiten[("h", round(c + FW, 6), round(xa, 6), round(xb, 6))])
            zipper(pc, A, B, MD, lambda p, c=c: ((p.x + P2) * UVS, (v0 + 0.016 + p.y - (c - FW)) * UVS), (0, 0, 1))

def abplatzung(F, netz, ori, c, seite, s0, L, d, h, seed):
    """Abgeplatzte Kante an einer Fuge (Fuge bei x = c fuer ori 'v', y = c fuer 'h'); seite +1: Feld auf der +Seite.
    L Laenge entlang der Fuge, d Tiefe ins Feld, h Absenkung an der Fugenkante."""
    lc = c + seite * FW
    sd = netz.seite_bei(ori, lc, s0)
    n = max(6, int(round(L / 0.007)))
    nx, ny = (seite, 0) if ori == "v" else (0, seite)
    def senk(s):
        t = (s - s0) / (L / 2)
        prof = max(0.0, 1 - t * t)
        return -h * prof ** 1.2 * (0.85 + 0.15 * noise.noise(Vector((s * 60 + seed, 0.3, 0.1))))
    sd.absenken(s0 - L / 2, s0 + L / 2, senk)
    umr, mitte = [], []
    for k in range(n + 1):
        t = -1 + 2 * k / n
        s = s0 + t * L / 2
        prof = max(0.0, 1 - t * t)
        dz = senk(s)
        sd.add(s, dz)
        dep = d * prof ** 0.6 * (1 + 0.3 * noise.noise(Vector((s * 45 + seed, 1.7, 0.4))) + 0.12 * noise.noise(Vector((s * 140 + seed, 0.2, 0.9))))
        x, y = sd.xy(s)
        umr.append((x + nx * dep, y + ny * dep))
        if 0 < k < n:
            mitte.append((x + nx * dep * 0.45, y + ny * dep * 0.45, dz * 0.5))
    F.line([F.pt(x, y) for x, y in umr])
    for (x, y, dz) in mitte:
        F.pt(x, y, dz)
    vb = REG["beton_roh"][0] + 0.05
    if ori == "v":
        uvf = lambda x, y: ((y + P2) * UVS, (vb + abs(x - lc)) * UVS)
    else:
        uvf = lambda x, y: ((x + P2) * UVS, (vb + abs(y - lc)) * UVS)
    F.region(umr, uvf, vorne=True)
    F.sperr.append((umr, 0.03))

# ---------- Risse im Beton ----------
def betonriss(F, pfad, gmax, tmax, seed):
    """Feiner Riss: Spalt bis gmax breit und tmax tief, an den Enden auslaufend."""
    pts, ss, S = resample(pfad, 0.012)
    tg = tangents(pts)
    li, re = [], []
    for k, ((x, y), (tx, ty), s) in enumerate(zip(pts, tg, ss)):
        N = (-ty, tx)
        sn = math.sin(math.pi * s / S)
        g = gmax / 2 * sn ** 0.7 * (1 + 0.3 * noise.noise(Vector((s * 30 + seed, 0.5, 0.2)))) if 0 < k < len(pts) - 1 else 0.0
        li.append((x + N[0] * g, y + N[1] * g))
        re.append((x - N[0] * g, y - N[1] * g))
    tiefe = [tmax * math.sin(math.pi * s / S) ** 0.5 for s in ss]
    poly = [li[0]] + re[1:-1] + [li[-1]] + li[1:-1][::-1]
    if loop_area(poly) < 0:
        poly = poly[::-1]
    idx = [F.pt(x, y) for x, y in poly]
    F.holes.append(idx)
    F.loch(poly)
    F.sperr.append((poly, 0.03))
    return {"li": li, "re": re, "s": ss, "tiefe": tiefe, "pfad": pts}

def riss_bauen(pc, F, r):
    li, re, ss, tf = r["li"], r["re"], r["s"], r["tiefe"]
    vb = REG["beton_roh"][0]
    u0 = pc.rng.random() * 3.0
    for seite, pts in ((1, li), (-1, re)):
        bog = [0.0]
        for k in range(len(pts) - 1):
            bog.append(bog[-1] + math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]))
        for k in range(len(pts) - 1):
            (xa, ya), (xb, yb) = pts[k], pts[k + 1]
            ta, tb = F.z(xa, ya), F.z(xb, yb)
            q = [(Vector((xa, ya, ta)), bog[k], tf[k]), (Vector((xb, yb, tb)), bog[k + 1], tf[k + 1]),
                 (Vector((xb, yb, tb - tf[k + 1])), bog[k + 1], 0.0), (Vector((xa, ya, ta - tf[k])), bog[k], 0.0)]
            q = [e for i, e in enumerate(q) if not (i >= 2 and q[3 - i][2] < 1e-7)]
            if len(q) < 3:
                continue
            mx, my = (xa + xb) / 2, (ya + yb) / 2
            cx, cy = r["pfad"][k]
            pc.face([e[0] for e in q], MD, [((u0 + e[1]) * UVS, (vb + 0.02 + e[2]) * UVS) for e in q],
                    want=(cx - mx, cy - my, 0.0))
    # Grund des Risses (fast waagerecht: Draufsicht in den Atlas)
    ymin = min(p[1] for p in li + re)
    if max(p[1] for p in li + re) - ymin > 0.4:
        raise RuntimeError("Riss zu hoch fuer den Bereich beton_roh")
    for k in range(len(li) - 1):
        ecken = [(li[k], ss[k], tf[k], 1), (li[k + 1], ss[k + 1], tf[k + 1], 1), (re[k + 1], ss[k + 1], tf[k + 1], -1), (re[k], ss[k], tf[k], -1)]
        uniq = []
        for (pxy, s_, t_, sg) in ecken:
            p = Vector((pxy[0], pxy[1], F.z(*pxy) - t_))
            if all((p - u[0]).length > 1e-9 for u in uniq):
                c = r["pfad"][ss.index(s_)]
                uniq.append((p, s_, sg * math.hypot(pxy[0] - c[0], pxy[1] - c[1])))
        if len(uniq) < 3:
            continue
        pc.face([u[0] for u in uniq], MD, [((u[0].x + P2) * UVS, (vb + 0.06 + u[0].y - ymin) * UVS) for u in uniq], want=(0, 0, 1))

# ---------- Plattenkoerper ----------
def koerper(pc, x2=P2, y2=P2, kante="kante", unten=MD, blech=0.0):
    """Seitenflaechen bis Z = -DICKE (Schnitt durch den Aufbau) und Unterseite. blech > 0: oben ein Stahlblech."""
    v0 = REG[kante][0]
    for (ax, ay), (bx, by), nrm in (((-x2, -y2), (x2, -y2), (0, -1, 0)), ((x2, -y2), (x2, y2), (1, 0, 0)),
                                    ((x2, y2), (-x2, y2), (0, 1, 0)), ((-x2, y2), (-x2, -y2), (-1, 0, 0))):
        zt = -blech
        pts = [Vector((ax, ay, zt)), Vector((bx, by, zt)), Vector((bx, by, -DICKE)), Vector((ax, ay, -DICKE))]
        uvs = [(((p.x if nrm[1] else p.y) + P2) * UVS, (v0 + p.z + DICKE) * UVS) for p in pts]
        pc.face(pts, MD, uvs, want=nrm)
        if blech:
            pts = [Vector((ax, ay, 0.0)), Vector((bx, by, 0.0)), Vector((bx, by, -blech)), Vector((ax, ay, -blech))]
            vs = REG["stahlkante"][0] + 0.01
            uvs = [((U_RECHTS[0] + 0.1 + (p.x if nrm[1] else p.y) + x2) * UVS, (vs + p.z + blech) * UVS) for p in pts]
            pc.face(pts, MD, uvs, want=nrm)
    if unten == MB:
        pts = [Vector((-x2, -y2, -DICKE)), Vector((x2, -y2, -DICKE)), Vector((x2, y2, -DICKE)), Vector((-x2, y2, -DICKE))]
        pc.face(pts, MB, [uv_welt(p.x, p.y) for p in pts], want=(0, 0, -1))
        return
    h = REG["beton_roh"][1] - REG["beton_roh"][0] - 0.02
    n = max(1, math.ceil(2 * y2 / h))
    for k in range(n):
        ya, yb = -y2 + 2 * y2 * k / n, -y2 + 2 * y2 * (k + 1) / n
        pts = [Vector((-x2, ya, -DICKE)), Vector((x2, ya, -DICKE)), Vector((x2, yb, -DICKE)), Vector((-x2, yb, -DICKE))]
        pc.face(pts, MD, [reg_uv("beton_roh", p.x + P2, 0.01 + p.y - ya) for p in pts], want=(0, 0, -1))

# ---------- Kruemel und Bewehrung ----------
IKO_V = [(-1, 1.618, 0), (1, 1.618, 0), (-1, -1.618, 0), (1, -1.618, 0), (0, -1, 1.618), (0, 1, 1.618), (0, -1, -1.618),
         (0, 1, -1.618), (1.618, 0, -1), (1.618, 0, 1), (-1.618, 0, -1), (-1.618, 0, 1)]
IKO_F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8),
         (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]

def kruemel(pc, x, y, zb, size, seed):
    """Betonkruemel: verformtes Ikosaeder, flach liegend, leicht eingesunken."""
    rng = random.Random(seed)
    sc = Vector((size, size * rng.uniform(0.6, 1.0), size * rng.uniform(0.4, 0.7)))
    rot = Matrix.Rotation(rng.uniform(0, math.tau), 3, "Z") @ Matrix.Rotation(rng.uniform(-0.3, 0.3), 3, "X")
    P = []
    for v in IKO_V:
        p = Vector(v).normalized() * (1 + rng.uniform(-0.25, 0.25))
        P.append(rot @ Vector((p.x * sc.x / 2, p.y * sc.y / 2, p.z * sc.z / 2)))
    zmin = min(p.z for p in P)
    P = [Vector((p.x + x, p.y + y, p.z - zmin + max(zb - 0.0012, -0.0148))) for p in P]
    c = sum(P, Vector()) / len(P)
    for f in IKO_F:
        q = [P[i] for i in f]
        flach(pc, q, "beton_roh", (sum(q, Vector()) / 3) - c)

def stab(pc, pfad, r, seiten=10):
    """Bewehrungsstab als Prisma entlang eines Linienzugs; die Enden liegen im Beton."""
    P = [Vector(p) for p in pfad]
    L = sum((b - a).length for a, b in zip(P, P[1:]))
    umf = 2 * math.pi * r
    u0 = u_anfang(pc, "bewehrung", L)
    v0 = REG["bewehrung"][0] + 0.009
    ringe, us = [], []
    s = 0.0
    for i, c in enumerate(P):
        t = (P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).normalized()
        n1 = Vector((-t.y, t.x, 0.0)).normalized()
        n2 = t.cross(n1).normalized()
        if n2.z < 0:
            n2 = -n2
        ringe.append([c + r * (math.cos(2 * math.pi * k / seiten) * n1 + math.sin(2 * math.pi * k / seiten) * n2) for k in range(seiten)])
        if i:
            s += (P[i] - P[i - 1]).length
        us.append(u0 + s)
    for i in range(len(P) - 1):
        for k in range(seiten):
            m = (k + 1) % seiten
            q = [ringe[i][k], ringe[i + 1][k], ringe[i + 1][m], ringe[i][m]]
            vk, vm = v0 + umf * k / seiten, v0 + umf * (k + 1) / seiten
            mid = (P[i] + P[i + 1]) / 2
            pc.face(q, MD, [(us[i] * UVS, vk * UVS), (us[i + 1] * UVS, vk * UVS), (us[i + 1] * UVS, vm * UVS), (us[i] * UVS, vm * UVS)],
                    smooth=True, want=(q[0] + q[1] + q[2] + q[3]) / 4 - mid)

# ======================= Mulde (Platte 03) =======================
def mulde_vorbereiten(F):
    umr = mulde_umriss()
    poly = [(x, y) for x, y, k in umr]
    F.holes.append([F.pt(x, y) for x, y in poly])
    F.loch(poly)
    ring = mulde_ring()
    u0, u1, v0, v1 = MULDE_BLOCK
    for (x, y) in ring:
        if abs(x - MX) > (u1 - u0) / 2 - 0.015 or abs(y - MY) > (v1 - v0) / 2 - 0.015:
            raise RuntimeError("Mulde passt nicht in ihren Bereich im Atlas")
    F.line([F.pt(x, y) for x, y in ring], True)
    F.region(ring, uv_mulde)
    F.sperr.append((poly, 0.02))
    return umr

def mulde_bauen(pc, F, umr):
    """Bruchkante rundum und Muldenboden (rau, bis 1,45 cm tief)."""
    n = len(umr)
    vb = REG["beton_roh"][0] + 0.30
    u0 = pc.rng.random() * 2.0
    s = 0.0
    tops = [Vector((x, y, F.z(x, y))) for x, y, k in umr]
    bots = [Vector((x, y, mulde_boden(x, y))) for x, y, k in umr]
    for i in range(n):
        j = (i + 1) % n
        L = (tops[j].xy - tops[i].xy).length
        hi, hj = tops[i].z - bots[i].z, tops[j].z - bots[j].z
        q = [tops[i], tops[j], bots[j], bots[i]]
        uvs = [((u0 + s) * UVS, (vb + hi) * UVS), ((u0 + s + L) * UVS, (vb + hj) * UVS),
               ((u0 + s + L) * UVS, vb * UVS), ((u0 + s) * UVS, vb * UVS)]
        mid = (tops[i] + tops[j]) / 2
        pc.face(q, MD, uvs, want=(MX - mid.x, MY - mid.y, 0.0))
        s += L
    poly = [(x, y) for x, y, k in umr]
    pts = list(poly)
    x0, y0, x1, y1 = bbox(poly)
    st = 0.028
    for i in range(int((x1 - x0) / st) + 1):
        for j in range(int((y1 - y0) / st) + 1):
            x, y = x0 + st * (i + 0.5 * (j % 2)), y0 + st * j * 0.866
            if point_in(poly, x, y) and poly_dist(poly, x, y) > 0.012:
                pts.append((x, y))
    m = len(poly)
    co, _, tris, _, _, _ = geometry.delaunay_2d_cdt([Vector(p) for p in pts], [(i, (i + 1) % m) for i in range(m)], [], 0, 1e-9)
    vs = [pc.bm.verts.new((c.x, c.y, mulde_boden(c.x, c.y))) for c in co]
    for (a, b, c) in tris:
        if (co[b] - co[a]).cross(co[c] - co[a]) < 0:
            b, c = c, b
        mx, my = (co[a].x + co[b].x + co[c].x) / 3, (co[a].y + co[b].y + co[c].y) / 3
        if not point_in(poly, mx, my):
            continue
        pc.face([vs[a], vs[b], vs[c]], MD, [uv_mulde(co[v].x, co[v].y) for v in (a, b, c)], smooth=True, want=(0, 0, 1))

# ======================= Rinne (Platte 04) =======================
def rinne_vorbereiten(F):
    for sg in (-1, 1):
        F.aussen += [(sg * P2, -KH), (sg * P2, KH)]
        for sk in (-1, 1):
            F.line([F.pt(sg * INNEN, sk * KH), F.pt(sg * P2, sk * KH)])
        xa, xb = sorted((sg * INNEN, sg * (P2 + 0.01)))
        F.region(rechteck(xa, -KH, xb, KH), uv_rinne)

def rostzone(F, netz):
    """Rostlaeufer um die Rinne: Bereich bis rost_rand(x), dort endet der abgeplatzte Anstrich (Zwangskante)."""
    teile = [(-P2, FUGEN[0] - FW), (FUGEN[0] + FW, FUGEN[1] - FW), (FUGEN[1] + FW, P2)]
    rand = {}
    for sg in (-1, 1):
        kette = []
        for (xa, xb) in teile:
            xs = {round(xa, 6), round(xb, 6)}
            xs |= {round(-P2 + 0.02 * k, 6) for k in range(201) if xa < -P2 + 0.02 * k < xb}
            xs |= {v for v in (-INNEN, INNEN) if xa < v < xb}
            pts = [(x, sg * rost_rand(x, sg)) for x in sorted(xs)]
            F.line([F.pt(x, y) for x, y in pts])
            for (x, y) in (pts[0], pts[-1]):
                if abs(abs(x) - P2) < 1e-9:
                    F.aussen.append((x, y))
                else:
                    netz.seite_bei("v", x, y).add(y)
            for (x, y) in pts:
                if abs(abs(x) - INNEN) < 1e-9:
                    F.innen.append((x, y))
            kette += pts
        rand[sg] = kette
    F.region(rand[1] + rand[-1][::-1], uv_rinne)

def rinne_bauen(pc, F, netz):
    """Gussrinne 20 cm: Rahmen und Gitter buendig auf Z = 0, Schlitze als echte Oeffnungen, Trog bis 10 cm tief."""
    schl = gitter_schlitze()
    xin = sorted({round(v, 6) for v in [-INNEN, INNEN] + [v for ab in schl for v in ab]})
    uvr = lambda p: uv_rinne(p.x, p.y)
    for sg in (-1, 1):
        A = [(x, Vector((x, sg * KS, 0.0))) for x in xin]
        B = []
        for (xa, xb) in netz.XI:
            sd = netz.seiten[("h", round(sg * KH, 6), round(xa, 6), round(xb, 6))]
            B += [(s, Vector((*sd.xy(s), 0.0))) for s, dz in sd.punkte()]
        zipper(pc, A, B, MD, uvr, (0, 0, 1))
    slot = {(round(a, 6), round(b, 6)) for a, b in schl}
    for xa, xb in zip(xin, xin[1:]):
        if (xa, xb) in slot:
            continue
        q = [Vector((xa, -KS, 0.0)), Vector((xb, -KS, 0.0)), Vector((xb, KS, 0.0)), Vector((xa, KS, 0.0))]
        pc.face(q, MD, [uvr(p) for p in q], want=(0, 0, 1))
    for (xa, xb) in schl:
        for (a, b), w in ((((xa, -KS), (xa, KS)), (1, 0, 0)), (((xb, KS), (xb, -KS)), (-1, 0, 0)),
                          (((xb, -KS), (xa, -KS)), (0, 1, 0)), (((xa, KS), (xb, KS)), (0, -1, 0))):
            q = [Vector((a[0], a[1], 0.0)), Vector((b[0], b[1], 0.0)), Vector((b[0], b[1], -KG)), Vector((a[0], a[1], -KG))]
            flach(pc, q, "eisen", w)
    vi = REG["rinne_innen"][0]
    for sg in (-1, 1):
        q = [Vector((-INNEN, sg * KR, -KG)), Vector((INNEN, sg * KR, -KG)), Vector((INNEN, sg * KR, KT)), Vector((-INNEN, sg * KR, KT))]
        pc.face(q, MD, [((p.x + P2) * UVS, (vi + p.z - KT) * UVS) for p in q], want=(0, -sg, 0))
        q = [Vector((sg * INNEN, -KR, -KG)), Vector((sg * INNEN, KR, -KG)), Vector((sg * INNEN, KR, KT)), Vector((sg * INNEN, -KR, KT))]
        flach(pc, q, "eisen", (-sg, 0, 0))
    q = [Vector((-INNEN, -KR, KT)), Vector((INNEN, -KR, KT)), Vector((INNEN, KR, KT)), Vector((-INNEN, KR, KT))]
    pc.face(q, MD, [((p.x + P2) * UVS, (vi + 0.08 + p.y + KR) * UVS) for p in q], want=(0, 0, 1))

# ======================= Stuecke =======================
def platte(name, seed, abpl, kanal=False):
    pc = Piece(f"{GEB}_{name}")
    maske = (lambda x, y: glatt((abs(y) - KH) / 0.15)) if kanal else None
    F = Oberflaeche(welle_fn(seed), maske)
    N = Netz(F, kanal)
    for k, (ori, c, sg, s0, L, d, h) in enumerate(abpl):
        abplatzung(F, N, ori, c, sg, s0, L, d, h, seed * 10 + k)
    return pc, F, N

def boden_01():
    pc, F, N = platte("boden_01", 21, [("v", -1, 1, 0.42, 0.075, 0.024, 0.0032), ("h", 1, -1, -0.35, 0.055, 0.02, 0.0027),
                                       ("v", 1, -1, -1.25, 0.095, 0.03, 0.004), ("h", -1, 1, 1.32, 0.045, 0.016, 0.0022)])
    N.fertig()
    F.gitter()
    F.bauen(pc)
    N.bauen(pc)
    koerper(pc)
    return finish(pc)

def boden_02():
    pc, F, N = platte("boden_02", 22, [("v", 1, 1, 0.55, 0.08, 0.026, 0.0034), ("h", -1, 1, -0.62, 0.11, 0.03, 0.004),
                                       ("v", -1, -1, -1.42, 0.06, 0.022, 0.003), ("h", 1, 1, 0.9, 0.07, 0.024, 0.0033),
                                       ("v", -1, 1, 1.38, 0.05, 0.018, 0.0024)])
    lw, mk = REG["laufweg"][0] + 0.01, REG["markierung"][0] + 0.01
    for sg in (-1, 1):
        y = sg * 0.05
        for (xa, xb) in N.XI:
            n = max(1, math.ceil((xb - xa) / 0.25))
            F.line([F.pt(xa + (xb - xa) * k / n, y) for k in range(n + 1)])
        for c in FUGEN:
            N.seite_bei("v", c - FW, y).add(y)
            N.seite_bei("v", c + FW, y).add(y)
        for sx in (-1, 1):
            F.innen.append((sx * INNEN, y))
            F.aussen += [(sx * P2, y), (sx * P2, sg * (1 - FW))]
            F.line([F.pt(sx * INNEN, y), F.pt(sx * P2, y)])
            F.line([F.pt(sx * INNEN, sg * (1 - FW)), F.pt(sx * P2, sg * (1 - FW))])
    F.region(rechteck(-P2 - 0.01, -0.05, P2 + 0.01, 0.05), lambda x, y: ((x + P2) * UVS, (mk + y + 0.05) * UVS))
    F.region(rechteck(-P2 - 0.01, -(1 - FW), P2 + 0.01, -0.05), lambda x, y: ((x + P2) * UVS, (lw + y + 1.0) * UVS))
    F.region(rechteck(-P2 - 0.01, 0.05, P2 + 0.01, 1 - FW), lambda x, y: ((x + P2 + 2.0) * UVS, (lw + y) * UVS))
    risse = [betonriss(F, [(-0.78, -0.64), (-0.66, -0.6), (-0.55, -0.52), (-0.42, -0.49), (-0.3, -0.4)], 0.0016, 0.004, 1),
             betonriss(F, [(0.22, 1.27), (0.3, 1.36), (0.33, 1.47), (0.44, 1.55), (0.5, 1.63)], 0.0014, 0.0035, 2),
             betonriss(F, [(-1.58, -1.46), (-1.47, -1.38), (-1.42, -1.27), (-1.3, -1.2)], 0.0012, 0.003, 3)]
    N.fertig()
    F.gitter()
    F.bauen(pc)
    N.bauen(pc)
    for r in risse:
        riss_bauen(pc, F, r)
    koerper(pc)
    return finish(pc)

def boden_03():
    pc, F, N = platte("boden_03", 23, [("v", 1, -1, 0.6, 0.085, 0.028, 0.0038), ("h", -1, -1, 1.45, 0.06, 0.022, 0.003),
                                       ("h", 1, 1, -0.75, 0.07, 0.025, 0.0034)])
    umr = mulde_vorbereiten(F)
    risse = [betonriss(F, [(-1.52, 1.22), (-1.44, 1.31), (-1.36, 1.36), (-1.27, 1.49)], 0.0013, 0.0032, 4)]
    N.fertig()
    F.gitter()
    F.bauen(pc)
    N.bauen(pc)
    mulde_bauen(pc, F, umr)
    for r in risse:
        riss_bauen(pc, F, r)
    for pfad, r in STAEBE:
        stab(pc, pfad, r)
    rng = random.Random(31)
    poly = [(x, y) for x, y, k in umr]
    n = 0
    while n < 18:
        x, y = MX + rng.uniform(-0.48, 0.48), MY + rng.uniform(-0.32, 0.32)
        if point_in(poly, x, y) and poly_dist(poly, x, y) > 0.02:
            kruemel(pc, x, y, mulde_boden(x, y), rng.uniform(0.006, 0.024), rng.randint(0, 10 ** 6))
            n += 1
    ring = mulde_ring()
    n = 0
    while n < 7:
        x, y = MX + rng.uniform(-0.75, 0.75), MY + rng.uniform(-0.5, 0.5)
        if point_in(ring, x, y) and not point_in(poly, x, y) and poly_dist(poly, x, y) > 0.02:
            kruemel(pc, x, y, F.z(x, y), rng.uniform(0.005, 0.014), rng.randint(0, 10 ** 6))
            n += 1
    koerper(pc)
    return finish(pc)

def boden_04():
    pc, F, N = platte("boden_04", 24, [("v", -1, -1, 1.12, 0.07, 0.024, 0.0033), ("h", 1, -1, 0.42, 0.06, 0.022, 0.003),
                                       ("v", 1, 1, -1.38, 0.08, 0.026, 0.0035)], kanal=True)
    rinne_vorbereiten(F)
    rostzone(F, N)
    N.fertig()
    F.gitter()
    F.bauen(pc)
    N.bauen(pc)
    rinne_bauen(pc, F, N)
    koerper(pc)
    return finish(pc)

def boden_schwelle():
    """Stahlschwelle: Riffelblech 1,0 x 0,2 m buendig auf Z = 0, vier leicht eingesunkene Senkschrauben."""
    pc = Piece(f"{GEB}_boden_schwelle")
    ur, vr = U_RECHTS[0], REG["riffelblech"][0]
    uvs = lambda x, y: ((ur + x + SW) * UVS, (vr + y + ST) * UVS)
    pts = rechteck(-SW, -ST, SW, ST)
    E = [(i, (i + 1) % 4) for i in range(4)]
    ringe = []
    for (sx, sy) in SCHRAUBEN:
        b = len(pts)
        ring = [(sx + SCHRAUBE_R * math.cos(2 * math.pi * k / 16), sy + SCHRAUBE_R * math.sin(2 * math.pi * k / 16)) for k in range(16)]
        pts += ring
        E += [(b + k, b + (k + 1) % 16) for k in range(16)]
        ringe.append(ring)
    co, _, tris, _, _, _ = geometry.delaunay_2d_cdt([Vector(p) for p in pts], E, [], 0, 1e-9)
    vs = [pc.bm.verts.new((c.x, c.y, 0.0)) for c in co]
    for (a, b, c) in tris:
        if (co[b] - co[a]).cross(co[c] - co[a]) < 0:
            b, c = c, b
        mx, my = (co[a].x + co[b].x + co[c].x) / 3, (co[a].y + co[b].y + co[c].y) / 3
        if any(point_in(r, mx, my) for r in ringe):
            continue
        pc.face([vs[a], vs[b], vs[c]], MD, [uvs(co[v].x, co[v].y) for v in (a, b, c)], want=(0, 0, 1))
    zk = -0.0007
    for ring in ringe:
        kopf = [Vector((x, y, zk)) for x, y in ring]
        pc.face(kopf, MD, [uvs(p.x, p.y) for p in kopf], want=(0, 0, 1))
        cx, cy = sum(p[0] for p in ring) / 16, sum(p[1] for p in ring) / 16
        for k in range(16):
            m = (k + 1) % 16
            q = [Vector((ring[k][0], ring[k][1], 0.0)), Vector((ring[m][0], ring[m][1], 0.0)), kopf[m], kopf[k]]
            flach(pc, q, "eisen", (cx - (q[0].x + q[1].x) / 2, cy - (q[0].y + q[1].y) / 2, 0.0))
    # Seiten: ein Band rundum (Stahlkante oben, darunter Beton), Unterseite mit dem Boden-Material
    u = U_RECHTS[0] + 0.05
    v0 = REG["schwelle_kante"][0]
    for (ax, ay), (bx, by), nrm in (((-SW, -ST), (SW, -ST), (0, -1, 0)), ((SW, -ST), (SW, ST), (1, 0, 0)),
                                    ((SW, ST), (-SW, ST), (0, 1, 0)), ((-SW, ST), (-SW, -ST), (-1, 0, 0))):
        L = math.hypot(bx - ax, by - ay)
        q = [Vector((ax, ay, 0.0)), Vector((bx, by, 0.0)), Vector((bx, by, -DICKE)), Vector((ax, ay, -DICKE))]
        pc.face(q, MD, [(u * UVS, (v0 + 0.2) * UVS), ((u + L) * UVS, (v0 + 0.2) * UVS), ((u + L) * UVS, v0 * UVS), (u * UVS, v0 * UVS)],
                want=nrm)
        u += L
    q = [Vector((-SW, -ST, -DICKE)), Vector((SW, -ST, -DICKE)), Vector((SW, ST, -DICKE)), Vector((-SW, ST, -DICKE))]
    pc.face(q, MB, [uv_welt(p.x, p.y) for p in q], want=(0, 0, -1))
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
                "bei", tuple(round(c, 4) for c in cen), "A", round(a3 * 1e4, 4), "cm2",
                [tuple(round(c, 4) for c in me.vertices[i].co) for i in lt.vertices], [tuple(round(c * 4, 4) for c in uvl[i].uv) for i in lt.loops])
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
    for (k, dx, dy) in ((1, 0, 0), (1, 4, 0), (0, 0, 4), (2, 4, 4)):
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
        "lampe2": (1, (-3.3, 0.35, 1.65), (0.3, -0.15, 0.0), 22),
        "lampe3": (2, (0.6, -3.1, 1.6), (0.0, -0.1, 0.0), 22),
        "lampe4": (3, (-0.9, -2.9, 1.65), (0.1, 0.0, 0.0), 22),
        "nah1": (3, (0.35, -0.65, 0.5), (-0.05, 0.0, -0.01), 32),
        "nah2": (4, (-0.32, -0.5, 0.5), (0.12, 0.0, 0.0), 30),
        "nah3": (2, (MX + 0.42, MY - 0.62, 0.48), (MX - 0.05, MY + 0.02, -0.008), 30),
        "nah4": (1, (1.45, -0.55, 0.5), (0.95, 0.05, 0.0), 30),
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

