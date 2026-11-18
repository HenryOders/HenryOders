# Amerikanischer Streifenwagen (Patrol Car) fuer Spiele: eigenes Limousinen-Design (keine echte Automarke) in
# klassischer Schwarz-Weiss-Lackierung mit POLICE-Schriftzug und eigenem Sternabzeichen (kein echtes Department).
# Erzeugt die Karosserie mit echten Spaltmassen, versenkten Scheiben und Leuchten mit Innenleben, Rammschutzbuegel,
# Suchscheinwerfer, rot-blauen Lichtbalken, Stahlfelgen mit Reifenprofil, Innenraum mit Trenngitter, Texturen,
# ein Skelett fuer Unreal Engine 5 (root + vier Radknochen), den Export als FBX und glTF sowie Vorschaubilder.
# Start: blender -b -P streifenwagen_us.py   (oder mit dem bpy-Modul: python streifenwagen_us.py)
# Das Skript setzt Blender auf Werkseinstellungen zurueck, also nicht in einem offenen Projekt ausfuehren.
# Koordinaten: X nach vorn, Y nach links, Z nach oben, Ursprung am Boden mittig zwischen den Achsen. Meter.
import bpy, bmesh, math, os, time, random
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, noise
from mathutils.bvhtree import BVHTree

T0 = time.time()
def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)

NAME = "Streifenwagen_US"                        # Dateinamen: SK_<NAME>.fbx/.glb, <name>_*.png, <name>.blend
OUT = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(OUT, "export")
TEXDIR = os.path.join(EXPORT, "Texturen")
os.makedirs(TEXDIR, exist_ok=True)
SHOTS = [s for s in os.environ.get("SHOTS", "vorne,hinten,seite,oben,detail,verfolger,strasse,nacht").split(",") if s]
SAMPLES = int(os.environ.get("SAMPLES", "64"))
RES = [int(v) for v in os.environ.get("RES", "1920x1080").split("x")]

bpy.ops.wm.read_factory_settings(use_empty=True)
for mod in ("io_scene_gltf2", "io_scene_fbx"):
    try:
        addon_utils.enable(mod, default_set=True)
    except Exception as e:
        log("Add-on", mod, "nicht geladen:", e)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0

# ---------------- Masse ----------------
LAENGE, BREITE = 5.10, 1.93
RADSTAND, SPUR = 2.96, 1.64
XV, XH = RADSTAND / 2, -RADSTAND / 2          # Vorder- und Hinterachse
RAD_R, RAD_B = 0.364, 0.245                   # Reifenradius, Reifenbreite (245/55 R18)
FELGE_R = 0.229                               # 18 Zoll
BOGEN_R = 0.402                               # Radlauf
YR = SPUR / 2                                  # Radmitte seitlich
RAEDER = {"wheel_fl": (XV, YR), "wheel_fr": (XV, -YR), "wheel_rl": (XH, YR), "wheel_rr": (XH, -YR)}

# ---------------- Werkzeuge ----------------
def pchip(pts):
    """Monotone kubische Interpolation (Fritsch-Carlson) durch (x, y)-Punkte; liefert f(x)."""
    pts = sorted(pts)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = max(0, min(n - 2, next(k for k in range(n - 1) if xs[k + 1] >= x)))
        t = (x - xs[i]) / h[i]
        t2, t3 = t * t, t * t * t
        return ((2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i]
                + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h[i] * m[i + 1])
    return f

def hexf(h):
    h = h.lstrip("#")
    return tuple((int(h[i:i + 2], 16) / 255) ** 2.2 for i in (0, 2, 4))     # sRGB -> linear

class Knoten:
    """Kurzschreibweise fuer Shader-Knoten: Zahlen werden Eingabewerte, Sockets werden verbunden."""
    def __init__(self, nt):
        self.nt = nt

    def ein(self, sock, x):
        if isinstance(x, (int, float)):
            sock.default_value = x
        elif isinstance(x, (tuple, list)):
            sock.default_value = x
        else:
            self.nt.links.new(x, sock)

    def m(self, op, a, b=None, c=None, clamp=False):
        n = self.nt.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, x in enumerate((a, b, c)):
            if x is not None:
                self.ein(n.inputs[i], x)
        return n.outputs[0]

    def add(self, *xs):
        s = xs[0]
        for x in xs[1:]:
            s = self.m("ADD", s, x)
        return s

    def mul(self, *xs):
        s = xs[0]
        for x in xs[1:]:
            s = self.m("MULTIPLY", s, x)
        return s

    def max(self, *xs):
        s = xs[0]
        for x in xs[1:]:
            s = self.m("MAXIMUM", s, x)
        return s

    def v(self, op, a, b=None):
        n = self.nt.nodes.new("ShaderNodeVectorMath")
        n.operation = op
        self.ein(n.inputs[0], a)
        if b is not None:
            self.ein(n.inputs[1], b)
        return n.outputs[1] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs[0]

    def glatt(self, x, a, b):
        """Weicher Uebergang von 0 (bei a) nach 1 (bei b); a > b kehrt die Richtung um."""
        n = self.nt.nodes.new("ShaderNodeMapRange")
        n.interpolation_type = "SMOOTHSTEP"
        n.clamp = True
        self.ein(n.inputs[0], x)
        self.ein(n.inputs[1], a)
        self.ein(n.inputs[2], b)
        return n.outputs[0]

    def rauschen(self, vec, skala, detail=6.0, rau=0.55, verzerrung=0.0):
        n = self.nt.nodes.new("ShaderNodeTexNoise")
        n.noise_dimensions = "3D"
        self.ein(n.inputs["Vector"], vec)
        n.inputs["Scale"].default_value = skala
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rau
        n.inputs["Distortion"].default_value = verzerrung
        return n.outputs["Fac"]

    def zellen(self, vec, skala):
        n = self.nt.nodes.new("ShaderNodeTexVoronoi")
        n.voronoi_dimensions = "3D"
        n.feature = "F1"
        self.ein(n.inputs["Vector"], vec)
        n.inputs["Scale"].default_value = skala
        n.inputs["Randomness"].default_value = 1.0
        return n.outputs["Distance"], self.trenne(n.outputs["Color"])

    def trenne(self, vec):
        n = self.nt.nodes.new("ShaderNodeSeparateXYZ")
        self.ein(n.inputs[0], vec)
        return n.outputs[0], n.outputs[1], n.outputs[2]

    def vektor(self, x, y, z):
        n = self.nt.nodes.new("ShaderNodeCombineXYZ")
        for i, w in enumerate((x, y, z)):
            self.ein(n.inputs[i], w)
        return n.outputs[0]

    def attribut(self, name):
        n = self.nt.nodes.new("ShaderNodeAttribute")
        n.attribute_type = "GEOMETRY"
        n.attribute_name = name
        return n.outputs["Fac"]

    def geometrie(self):
        n = self.nt.nodes.new("ShaderNodeNewGeometry")
        return n.outputs["Position"], n.outputs["Normal"]

def mathe(nt, op, a, b=None):
    return Knoten(nt).m(op, a, b)

# ---------------- Texturen (numpy, als PNG gespeichert und eingebunden) ----------------
def bild(name, arr_xy, farbe=True):
    """Bild aus einem Array [x, y, kanal] (Werte 0..1) anlegen, als PNG in export/Texturen speichern."""
    w, h = arr_xy.shape[0], arr_xy.shape[1]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = np.transpose(arr_xy[..., :3], (1, 0, 2))
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.colorspace_settings.name = "sRGB" if farbe else "Non-Color"
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = os.path.join(TEXDIR, name + ".png")
    img.file_format = "PNG"
    img.save()
    return img

def bild_hw(name, arr, farbe=True):
    """Bild aus einem Array [Zeile von unten, Spalte, Kanal] (1 oder 3 Kanaele, 0..1) als PNG speichern."""
    h, w = arr.shape[:2]
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = arr[..., :3] if arr.shape[2] >= 3 else arr[..., :1]
    img = bpy.data.images.new(name, w, h, alpha=False)
    img.colorspace_settings.name = "sRGB" if farbe else "Non-Color"
    img.pixels.foreach_set(np.clip(rgba, 0, 1).ravel())
    img.filepath_raw = os.path.join(TEXDIR, name + ".png")
    img.file_format = "PNG"
    img.save()
    return img

def normal_aus_hoehe(hoehe, meter_u, meter_v):
    """Normal-Karte (OpenGL, +Y = +v) aus einer Hoehenkarte in Metern; u wiederholt sich nahtlos."""
    du = (np.roll(hoehe, -1, 0) - np.roll(hoehe, 1, 0)) / (2 * meter_u)
    dv = np.gradient(hoehe, axis=1) / meter_v
    n = np.stack([-du, -dv, np.ones_like(hoehe)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5

def textur_flakes(n=512, zellen=110, seed=7):
    """Metallic-Flakes: Voronoi-Zellen mit leicht gekippten Normalen, nahtlos kachelbar."""
    rng = np.random.default_rng(seed)
    g = zellen
    px = (np.arange(g)[:, None] + rng.random((g, g))) / g
    py = (np.arange(g)[None, :] + rng.random((g, g))) / g
    nx, ny = rng.normal(0, 0.28, (g, g)), rng.normal(0, 0.28, (g, g))
    u = (np.arange(n) + 0.5) / n
    U, V = np.meshgrid(u, u, indexing="ij")
    ci, cj = np.floor(U * g).astype(int), np.floor(V * g).astype(int)
    best = np.full((n, n), 1e9)
    bi, bj = np.zeros((n, n), int), np.zeros((n, n), int)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            ii, jj = ci + di, cj + dj
            qx = px[ii % g, jj % g] + np.floor_divide(ii, g)
            qy = py[ii % g, jj % g] + np.floor_divide(jj, g)
            d = (U - qx) ** 2 + (V - qy) ** 2
            m = d < best
            best[m], bi[m], bj[m] = d[m], ii[m] % g, jj[m] % g
    t = np.stack([nx[bi, bj], ny[bi, bj], np.ones((n, n))], -1)
    t /= np.linalg.norm(t, axis=-1, keepdims=True)
    return bild("T_Lack_Flakes_N", t * 0.5 + 0.5, farbe=False)

FACETTEN_KACHEL = 0.032       # Meter je Kachel der Reflektor-Facetten (8 x 8 Pyramiden, also 4 mm je Facette)
def textur_facetten(n=256, zellen=8, neigung=26.0):
    """Reflektor hinter dem Rueckleuchtenglas: Pyramidenfacetten, nahtlos kachelbar. Jede Facette spiegelt das
    Licht in eine andere Richtung; hinter rotem Glas entsteht das typische Funkeln."""
    u = (np.arange(n) + 0.5) / n * zellen
    U, V = np.meshgrid(u, u, indexing="ij")
    fu, fv = U % 1.0 - 0.5, V % 1.0 - 0.5
    s = math.sin(math.radians(neigung))
    nx = np.where(np.abs(fu) >= np.abs(fv), np.sign(fu), 0.0) * s
    ny = np.where(np.abs(fv) > np.abs(fu), np.sign(fv), 0.0) * s
    t = np.stack([nx, ny, np.full_like(nx, math.cos(math.radians(neigung)))], -1)
    return bild("T_Reflektor_N", t * 0.5 + 0.5, farbe=False)

KRATZER_KACHEL = 0.8          # Meter je Kachel der Kratzer-Textur auf "UV_Flakes"
def textur_kratzer(n=2048, seed=21):
    """Klarlack-Normalen, nahtlos kachelbar: leichte Orangenhaut, viele feine Waschanlagen-Kratzer in allen
    Richtungen (im Glanzlicht entstehen daraus die typischen Kringel) und einige laengere Kratzer."""
    rng = np.random.default_rng(seed)
    px_m = KRATZER_KACHEL / n
    # Orangenhaut: bandbegrenztes Rauschen um 3,5 mm Wellenlaenge (per FFT, dadurch von selbst periodisch)
    fr = np.fft.fftfreq(n, d=px_m)
    FR = np.hypot(fr[:, None], fr[None, :])
    band = np.exp(-((np.log(np.maximum(FR, 1e-3)) - np.log(1 / 0.0035)) ** 2) / (2 * 0.45 ** 2))
    haut = np.fft.ifft2(np.fft.fft2(rng.normal(size=(n, n))) * band).real
    # Kratzer als Rillen mit gaussfoermigem Querschnitt, auf einer gepolsterten Flaeche gezeichnet und dann
    # ringsum zurueckgefaltet (nahtlos)
    rand = 420
    gross = np.zeros((n + 2 * rand, n + 2 * rand), np.float32)
    def rille_px(p0, p1, breite, tiefe):
        p0, p1 = np.asarray(p0, float) + rand, np.asarray(p1, float) + rand
        r = 3 * breite + 1
        x0, x1 = int(max(min(p0[0], p1[0]) - r, 0)), int(min(max(p0[0], p1[0]) + r, gross.shape[0] - 1))
        y0, y1 = int(max(min(p0[1], p1[1]) - r, 0)), int(min(max(p0[1], p1[1]) + r, gross.shape[1] - 1))
        if x1 <= x0 or y1 <= y0:
            return
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5, indexing="ij")
        d = p1 - p0
        t = np.clip(((X - p0[0]) * d[0] + (Y - p0[1]) * d[1]) / max(d @ d, 1e-9), 0, 1)
        ab = np.hypot(X - p0[0] - t * d[0], Y - p0[1] - t * d[1])
        gross[x0:x1 + 1, y0:y1 + 1] -= tiefe * np.exp(-(ab / breite) ** 2)
    for _ in range(2600):                      # kurze, feine Kratzer (4 bis 40 mm)
        p = rng.random(2) * n
        w = rng.random() * math.pi
        l = (0.004 + 0.036 * rng.random() ** 2) / px_m
        rille_px(p, p + l * np.array((math.cos(w), math.sin(w))), 0.35 + 0.25 * rng.random(), 0.25 + 0.6 * rng.random())
    for _ in range(14):                        # Kringel: Kreisboegen um wenige Mittelpunkte
        c = rng.random(2) * n
        for _ in range(28):
            rr = (0.03 + 0.12 * rng.random()) / px_m
            w0, dw = rng.random() * 2 * math.pi, (0.15 + 0.5 * rng.random())
            pts = [c + rr * np.array((math.cos(w0 + dw * k / 5), math.sin(w0 + dw * k / 5))) for k in range(6)]
            br, ti = 0.35 + 0.2 * rng.random(), 0.2 + 0.4 * rng.random()
            for a, b in zip(pts, pts[1:]):
                rille_px(a, b, br, ti)
    for _ in range(36):                        # laengere, leicht gebogene Kratzer (5 bis 25 cm)
        p = rng.random(2) * n
        w = rng.random() * 2 * math.pi
        l = (0.05 + 0.2 * rng.random()) / px_m
        kr = rng.normal(0, 0.25)
        pts = [p]
        for k in range(8):
            w += kr / 8
            pts.append(pts[-1] + l / 8 * np.array((math.cos(w), math.sin(w))))
        br, ti = 0.5 + 0.4 * rng.random(), 0.6 + 0.6 * rng.random()
        for a, b in zip(pts, pts[1:]):
            rille_px(a, b, br, ti)
    kr = gross[rand:rand + n, rand:rand + n].copy()
    kr[:rand, :] += gross[n + rand:, rand:rand + n]
    kr[-rand:, :] += gross[:rand, rand:rand + n]
    kr[:, :rand] += gross[rand:rand + n, n + rand:]
    kr[:, -rand:] += gross[rand:rand + n, :rand]
    kr[:rand, :rand] += gross[n + rand:, n + rand:]
    kr[-rand:, -rand:] += gross[:rand, :rand]
    kr[:rand, -rand:] += gross[n + rand:, :rand]
    kr[-rand:, :rand] += gross[:rand, n + rand:]
    def grad(h):
        return (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / 2, (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / 2
    hx, hy = grad(haut)
    s_haut = 0.006 / max(np.hypot(hx, hy).std(), 1e-9)          # Orangenhaut: Neigung um 0,006
    kx, ky = grad(kr)
    gx, gy = hx * s_haut + kx * 0.16, hy * s_haut + ky * 0.16    # Kratzer: Flankenneigung bis etwa 0,3
    nrm = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    return bild("T_Lack_Kratzer_N", nrm * 0.5 + 0.5, farbe=False)

def text_dreiecke(text):
    """Text (Blender-Standardschrift) als Dreiecke [n, 3, 2] in der Ebene, mittig ausgerichtet."""
    cu = bpy.data.curves.new("_text", "FONT")
    cu.body = text
    cu.align_x = cu.align_y = "CENTER"
    cu.fill_mode = "FRONT"
    cu.resolution_u = 4
    ob = bpy.data.objects.new("_text", cu)
    scene.collection.objects.link(ob)
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    me.calc_loop_triangles()
    co = np.array([v.co[:2] for v in me.vertices])
    tri = np.array([t.vertices[:] for t in me.loop_triangles])
    bpy.data.meshes.remove(me)
    return co[tri]

def dreiecke_rastern(feld, tris, ss=3):
    """Dreiecke in Pixelkoordinaten (x = erste, y = zweite Achse von feld) kantengeglaettet aufaddieren."""
    for t in tris:
        lo = np.maximum(np.floor(t.min(0)).astype(int), 0)
        hi = np.minimum(np.ceil(t.max(0)).astype(int) + 1, feld.shape)
        if (hi <= lo).any():
            continue
        X, Y = np.meshgrid(lo[0] + (np.arange((hi[0] - lo[0]) * ss) + 0.5) / ss,
                           lo[1] + (np.arange((hi[1] - lo[1]) * ss) + 0.5) / ss, indexing="ij")
        (ax, ay), (bx, by), (cx, cy) = t
        d = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if abs(d) < 1e-12:
            continue
        w1 = ((bx - X) * (cy - Y) - (by - Y) * (cx - X)) / d
        w2 = ((cx - X) * (ay - Y) - (cy - Y) * (ax - X)) / d
        innen = (w1 >= 0) & (w2 >= 0) & (w1 + w2 <= 1)
        feld[lo[0]:hi[0], lo[1]:hi[1]] += innen.reshape(hi[0] - lo[0], ss, hi[1] - lo[1], ss).mean(axis=(1, 3))

# Reifen-UV: u = einmal um den Umfang (0..1), v = Profil von innen (0) nach aussen (1); die Aussenflanke liegt
# bei v 0,68..1 (1 = Wulst am Felgenhorn)
REIFEN_V = {"lauf0": 0.34, "lauf1": 0.66}
REIFEN_TEXTE = [("245/55 R18 98V", 0.06, 0.012), ("M+S", 0.17, 0.015), ("ALL SEASON", 0.31, 0.014),
                ("TUBELESS", 0.44, 0.010), ("245/55 R18 98V", 0.56, 0.012), ("M+S", 0.67, 0.015),
                ("ALL SEASON", 0.81, 0.014), ("RADIAL", 0.94, 0.010)]
def textur_reifen(w=8192, h=1024, seed=11):
    """Reifen ueber den ganzen Umfang: Profil (72 Bloecke), Lamellen, Riffelband und erhabene Beschriftung auf der
    Aussenflanke (nur allgemeine Angaben: Groesse, M+S, Bauart), dazu Staub auf Lauf- und Flanke."""
    rng = np.random.default_rng(seed)
    U, V = np.meshgrid((np.arange(w, dtype=np.float32) + 0.5) / w, (np.arange(h, dtype=np.float32) + 0.5) / h,
                       indexing="ij")
    UK = U * 8.0                                          # 8 Profil-Kacheln je Umdrehung
    hoehe = np.zeros((w, h), np.float32)
    kante = lambda d, breite, weich: np.clip((breite / 2 - np.abs(d)) / weich + 0.5, 0, 1)
    teilung = 1 / 9                                       # 9 Bloecke je Kachel (ca. 3,2 cm)
    # Querrillen in den Schulterrippen, leicht schraeg, laufen zur Flanke aus
    for v0, v1, sg in ((0.27, 0.405, -1), (0.595, 0.73, 1)):
        zone = np.clip((V - v0) / 0.01, 0, 1) * np.clip((v1 - V) / 0.01, 0, 1)
        auslauf = np.clip((0.5 - np.abs(V - 0.5) - 0.23) / 0.04, 0, 1)
        ph = (UK / teilung + sg * 1.6 * (V - 0.5)) % 1.0
        hoehe -= 0.006 * kante(ph - 0.5, 0.16, 0.03) * zone * (0.35 + 0.65 * auslauf)
    # Lamellen (feine Schlitze) in den Mittelrippen
    for v0, v1 in ((0.412, 0.458), (0.474, 0.526), (0.542, 0.588)):
        zone = np.clip((V - v0) / 0.004, 0, 1) * np.clip((v1 - V) / 0.004, 0, 1)
        ph = (UK / (teilung / 2) + 2.2 * (V - 0.5)) % 1.0
        hoehe -= 0.003 * kante(ph - 0.5, 0.06, 0.02) * zone
    # Flanke: feine Ringe am Felgenhorn, Riffelband
    for vr in (0.0, 1.0):
        nah = np.clip(1 - np.abs(V - vr) / 0.07, 0, 1)
        hoehe += 0.0005 * np.sin(2 * np.pi * V * h / 10) * nah
    for v0, v1 in ((0.17, 0.205), (0.795, 0.83)):
        zone = np.clip((V - v0) / 0.004, 0, 1) * np.clip((v1 - V) / 0.004, 0, 1)
        hoehe += 0.0004 * (np.sin(2 * np.pi * U * w / 6) > 0.3) * zone
    # Beschriftung: Buchstaben 0,7 mm erhaben; Lesrichtung im Uhrzeigersinn, Oberkante zur Lauflaeche
    schrift = np.zeros((w, h), np.float32)
    r_text = FELGE_R + 0.4 * (RAD_R - FELGE_R)
    u_je_m, v_je_m = 1 / (2 * np.pi * r_text), 1 / 0.45
    for text, u0, hoch in REIFEN_TEXTE:
        tris = text_dreiecke(text)
        y0, y1 = tris[..., 1].min(), tris[..., 1].max()
        k = hoch / (y1 - y0)
        px = np.empty_like(tris)
        px[..., 0] = (u0 + tris[..., 0] * k * u_je_m) * w
        px[..., 1] = (0.875 - (tris[..., 1] - (y0 + y1) / 2) * k * v_je_m) * h
        dreiecke_rastern(schrift, px)
    schrift = np.clip(schrift, 0, 1)
    hoehe += 0.0007 * schrift
    meter_u = 2 * np.pi * RAD_R / w
    meter_v = 0.43 / h
    nrm = normal_aus_hoehe(hoehe, meter_u, meter_v)
    # Grundfarbe: Gummi, in Rillen dunkler, Lauflaeche abgefahren etwas heller, Staub zur Wulst hin
    tief = np.clip(-hoehe / 0.006, 0, 1)
    flanke = np.clip((np.abs(V - 0.5) * 2 - 0.42) / 0.58, 0, 1)
    lauf = np.clip(1 - np.abs(V - 0.5) / 0.17, 0, 1) * (1 - tief)
    wolke = np.zeros((w, h), np.float32)
    for k in range(1, 6):
        wolke += np.sin(2 * np.pi * (k * 5 * U + rng.random())) * np.sin(2 * np.pi * (k * 2 * V + rng.random())) / k
    lin = 0.0105 * (1 - 0.5 * tief) * (1 + 0.15 * flanke) * (1 + 0.08 * wolke) * (1 + 0.45 * lauf)
    staub = np.clip((np.abs(V - 0.5) * 2 - 0.72) / 0.28, 0, 1) * np.clip(0.5 + 0.5 * wolke, 0, 1) * 0.22
    staub += tief * np.clip((0.12 - np.abs(V - 0.5)) / 0.12, 0, 1) * 0.25          # Staub in den Rillen
    farbe = np.stack([lin, lin, lin], -1) * (1 - staub[..., None]) + np.array(hexf("#5b5246"), np.float32) * staub[..., None] * 0.35
    srgb = np.clip(farbe, 0, 1) ** (1 / 2.2)
    return bild("T_Reifen_N", nrm, farbe=False), bild("T_Reifen_BC", srgb, farbe=True)

# ---------------- Materialien ----------------
MATS = {}
def material(name, farbe, metall=0.0, rauheit=0.5, lack=0.0, lack_rau=0.03, durch=0.0, ior=1.45, leuchten=0.0,
             leucht_farbe=None, normal=None, normal_uv="UVMap", normal_skala=1.0, normal_staerke=1.0,
             farb_bild=None, farb_uv="UVMap", farb_skala=1.0, lack_normal=None, lack_normal_skala=1.0,
             lack_normal_staerke=1.0):
    """Principled BSDF mit festen Werten und optional Texturen (exportiert sauber nach glTF und FBX)."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*farbe, 1.0)
    b.inputs["Metallic"].default_value = metall
    b.inputs["Roughness"].default_value = rauheit
    b.inputs["Coat Weight"].default_value = lack
    b.inputs["Coat Roughness"].default_value = lack_rau
    b.inputs["Transmission Weight"].default_value = durch
    b.inputs["IOR"].default_value = ior
    if leuchten:
        b.inputs["Emission Color"].default_value = (*(leucht_farbe or farbe), 1.0)
        b.inputs["Emission Strength"].default_value = leuchten
    def tex(img, uv, skala):
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = uv
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        if skala != 1.0:
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.inputs["Scale"].default_value = (skala, skala, 1.0)
            nt.links.new(uvn.outputs["UV"], mp.inputs["Vector"])
            nt.links.new(mp.outputs["Vector"], t.inputs["Vector"])
        else:
            nt.links.new(uvn.outputs["UV"], t.inputs["Vector"])
        return t
    if farb_bild is not None:
        nt.links.new(tex(farb_bild, farb_uv, farb_skala).outputs["Color"], b.inputs["Base Color"])
    if normal is not None:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.uv_map = normal_uv
        nm.inputs["Strength"].default_value = normal_staerke
        nt.links.new(tex(normal, normal_uv, normal_skala).outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if lack_normal is not None:                  # Kratzer und Orangenhaut im Klarlack (UV-Karte wie normal_uv)
        nk = nt.nodes.new("ShaderNodeNormalMap")
        nk.uv_map = normal_uv
        nk.inputs["Strength"].default_value = lack_normal_staerke
        nt.links.new(tex(lack_normal, normal_uv, lack_normal_skala).outputs["Color"], nk.inputs["Color"])
        nt.links.new(nk.outputs["Normal"], b.inputs["Coat Normal"])
    m.diffuse_color = (*farbe, 1.0)
    MATS[name] = m
    return m

def glas(name, farbe, rauheit=0.0):
    """Duennes Glas: Durchsicht ohne Brechung (IOR 1,0), Spiegelung ueber die Klarlackschicht."""
    return material(name, farbe, rauheit=rauheit, durch=1.0, ior=1.0, lack=1.0, lack_rau=0.0)

# ---------------- Geometrie ----------------
def objekt(name, bm, mats, glatt=False, auto_glatt=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    if glatt:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    if auto_glatt is not None:
        me.set_sharp_from_angle(angle=math.radians(auto_glatt))
    return ob

def anwenden(ob, mod):
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.ops.object.modifier_apply(modifier=mod.name)

def kasten(c, s, fase=0.0, segs=2, rot=None, mi=0):
    """Quader mit Mitte c und Groesse s, optional mit gerundeten Kanten und gedreht; als eigenes bmesh."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(s), verts=bm.verts)
    if fase > 0:
        bmesh.ops.bevel(bm, geom=bm.verts[:] + bm.edges[:], offset=fase, segments=segs, affect="EDGES",
                        profile=0.5, clamp_overlap=True)
    M = Matrix.Translation(Vector(c)) @ (rot.to_4x4() if rot is not None else Matrix.Identity(4))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    for f in bm.faces:
        f.material_index = mi
    return bm

def zylinder(c, r, h, achse="Y", segs=24, mi=0, deckel=True, r2=None):
    """Zylinder (oder Kegelstumpf mit r2) mit Mitte c entlang einer Achse; als eigenes bmesh."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=deckel, cap_tris=False, segments=segs, radius1=r, radius2=r if r2 is None else r2, depth=h)
    rot = {"X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(-math.pi / 2, 4, "X"), "Z": Matrix.Identity(4)}[achse]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(c)) @ rot, verts=bm.verts)
    for f in bm.faces:
        f.material_index = mi
    return bm

def kugel(c, r, segs=16, ringe=8, skala=(1, 1, 1), mi=0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=ringe, radius=r)
    bmesh.ops.scale(bm, vec=Vector(skala), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    for f in bm.faces:
        f.material_index = mi
    return bm

def einfuegen(ziel, teil):
    """bmesh 'teil' an bmesh 'ziel' anhaengen (Materialindizes bleiben)."""
    me = bpy.data.meshes.new("_tmp")
    teil.to_mesh(me)
    teil.free()
    ziel.from_mesh(me)
    bpy.data.meshes.remove(me)

def rohr(punkte, ra, rb=None, segs=10, mi=0, deckel=True, oben=(0, 0, 1), eckig=2.0):
    """Rohr oder abgerundetes Profil (eckig > 2) entlang eines Linienzugs; ra quer, rb in Richtung 'oben'."""
    rb = ra if rb is None else rb
    bm = bmesh.new()
    pts = [Vector(p) for p in punkte]
    up = Vector(oben)
    ringe = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        b = up - t * up.dot(t)
        b = b.normalized() if b.length > 1e-6 else Vector((1, 0, 0))
        a = b.cross(t)
        ring = []
        for k in range(segs):
            w = 2 * math.pi * (k + 0.5) / segs
            c, s = math.cos(w), math.sin(w)
            ca = math.copysign(abs(c) ** (2 / eckig), c) * ra
            cb = math.copysign(abs(s) ** (2 / eckig), s) * rb
            ring.append(bm.verts.new(p + a * ca + b * cb))
        ringe.append(ring)
    for r0, r1 in zip(ringe, ringe[1:]):
        for k in range(segs):
            f = bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
            f.material_index = mi
    if deckel:
        for r in (ringe[0], ringe[-1]):
            f = bm.faces.new(r)
            f.material_index = mi
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm

def chaikin(pts, n=2):
    """Geschlossenes Vieleck runden (Chaikin-Verfahren)."""
    for _ in range(n):
        neu = []
        for i in range(len(pts)):
            a, b = Vector(pts[i]), Vector(pts[(i + 1) % len(pts)])
            neu += [tuple(a.lerp(b, 0.25)), tuple(a.lerp(b, 0.75))]
        pts = neu
    return pts

def im_vieleck(p, poly):
    x, y = p
    drin = False
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            drin = not drin
    return drin

def abstand_rand(p, poly):
    best = 1e9
    P = Vector(p)
    for i in range(len(poly)):
        a, b = Vector(poly[i]), Vector(poly[(i + 1) % len(poly)])
        ab = b - a
        t = max(0.0, min(1.0, (P - a).dot(ab) / max(ab.length_squared, 1e-12)))
        best = min(best, (a + ab * t - P).length)
    return best

def bvh_von(ob):
    return BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())

def patch(umriss, ursprung, achse, e1, e2, bvh, raster=0.012):
    """Vieleck (Koordinaten a, b entlang e1, e2 um ursprung) gleichmaessig vernetzen und entlang achse auf die
    Flaeche projizieren. Liefert (bmesh, Fehlschuesse); Flaechen zeigen nach aussen, Ecknormalen sind gesetzt."""
    from mathutils.geometry import delaunay_2d_cdt
    rand = [Vector(p) for p in umriss]
    lo = Vector((min(p.x for p in rand), min(p.y for p in rand)))
    hi = Vector((max(p.x for p in rand), max(p.y for p in rand)))
    innen = []
    a = lo.x + raster / 2
    while a < hi.x:
        b = lo.y + raster / 2
        while b < hi.y:
            if im_vieleck((a, b), umriss) and abstand_rand((a, b), umriss) > raster * 0.45:
                innen.append(Vector((a, b)))
            b += raster
        a += raster
    pts = rand + innen
    n = len(rand)
    res = delaunay_2d_cdt(pts, [(i, (i + 1) % n) for i in range(n)], [list(range(n))], 1, 1e-7)
    bm = bmesh.new()
    O, d, E1, E2 = Vector(ursprung), Vector(achse).normalized(), Vector(e1), Vector(e2)
    vs = [bm.verts.new(O + E1 * c.x + E2 * c.y) for c in res[0]]
    for f in res[2]:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    fehl = 0
    for v in bm.verts:
        loc = bvh.ray_cast(v.co, d)[0]
        if loc is None:
            fehl += 1
        else:
            v.co = loc
    # Entspannen: innere Ecken gleichmaessig auf der Flaeche verteilen. Wo die Projektion die Flaeche streifend
    # trifft (Leuchten, die um die Ecke laufen), wuerden sich die Dreiecke sonst zusammenschieben und falten.
    rand = {v for e in bm.edges if len(e.link_faces) < 2 for v in e.verts}
    innen_v = [v for v in bm.verts if v not in rand and v.link_edges]
    for _ in range(12):
        neu = [sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges) for v in innen_v]
        for v, p in zip(innen_v, neu):
            v.co = bvh.find_nearest(p)[0]
    bm.normal_update()
    for f in bm.faces:                           # nach aussen ausrichten, gemessen an der Flaechennormale darunter
        aussen = bvh.find_nearest(f.calc_center_median())[1]
        if f.normal.dot(aussen if aussen is not None else -d) < 0:
            f.normal_flip()
    bm.normal_update()
    return bm, fehl

def schale(pb, aussen, tiefe, mi_wand, mi_boden, normalen=None):
    """Geschlossener Koerper aus einem Flaechenstueck: nach aussen und innen versetzt, mit Waenden.
    normalen: optional eigene Richtung je Ecke (Index), sonst die Ecknormalen des Flaechenstuecks."""
    out = bmesh.new()
    pb.verts.index_update()
    nrm = [(normalen[v.index] if normalen is not None else v.normal) for v in pb.verts]
    vo = [out.verts.new(v.co + nrm[v.index] * aussen) for v in pb.verts]
    vi = [out.verts.new(v.co - nrm[v.index] * tiefe) for v in pb.verts]
    for f in pb.faces:
        ids = [v.index for v in f.verts]
        out.faces.new([vo[i] for i in ids]).material_index = mi_wand
        out.faces.new([vi[i] for i in reversed(ids)]).material_index = mi_boden
    for e in pb.edges:
        if len(e.link_faces) == 1:
            i, j = e.verts[0].index, e.verts[1].index
            out.faces.new((vo[i], vo[j], vi[j], vi[i])).material_index = mi_wand
    bmesh.ops.recalc_face_normals(out, faces=out.faces)
    return out

def rille(bm, punkte, bvh, breite=0.0045, aussen=0.012, innen=0.009, mi=0, geschlossen=False, strahl=None):
    """Schneidekoerper fuer eine Fuge: schmaler Balken entlang eines Linienzugs, an die Flaeche angelegt.
    Mit strahl werden die Punkte in dieser Richtung auf die Flaeche geschossen, sonst zum naechsten Punkt gezogen."""
    locs, nors = [], []
    for p in punkte:
        hit = bvh.ray_cast(Vector(p), Vector(strahl)) if strahl is not None else (None,)
        loc, nor = hit[:2] if hit[0] is not None else bvh.find_nearest(Vector(p))[:2]
        locs.append(loc)
        nors.append(nor)
    m = len(locs)
    idx = (lambda i: i % m) if geschlossen else (lambda i: max(0, min(m - 1, i)))
    ringe = []
    for i in range(m):
        n = (nors[idx(i - 1)] + nors[i] * 2 + nors[idx(i + 1)]).normalized()
        t = (locs[idx(i + 1)] - locs[idx(i - 1)]).normalized()
        s = t.cross(n).normalized()
        p = locs[i]
        ringe.append([bm.verts.new(p + s * breite / 2 + n * aussen), bm.verts.new(p - s * breite / 2 + n * aussen),
                      bm.verts.new(p - s * breite / 2 - n * innen), bm.verts.new(p + s * breite / 2 - n * innen)])
    paare = list(zip(ringe, ringe[1:])) + ([(ringe[-1], ringe[0])] if geschlossen else [])
    neu = []
    for r0, r1 in paare:
        for k in range(4):
            neu.append(bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k])))
    if not geschlossen:
        neu.append(bm.faces.new(ringe[0]))
        neu.append(bm.faces.new(ringe[-1][::-1]))
    for f in neu:
        f.material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=neu)

# ---------------- Texturen und Materialien ----------------
log("Texturen ...")
FLAKES = textur_flakes()
KRATZER = textur_kratzer()
FACETTEN = textur_facetten()
REIFEN_N, REIFEN_BC = textur_reifen()
FLAKE_SKALA = 25.0            # Flake-Kacheln je Meter auf der UV-Karte "UV_Flakes" (Wuerfelprojektion, 1 UV = 1 m)

def lack(name, farbe, metall, flakes=0.3):
    """Metallic- oder Uni-Lack mit Klarlack; Flakes im Grundlack, Kratzer und Orangenhaut im Klarlack."""
    return material(name, farbe, metall=metall, rauheit=0.32, lack=1.0, lack_rau=0.012, normal=FLAKES,
                    normal_uv="UV_Flakes", normal_skala=FLAKE_SKALA, normal_staerke=flakes, lack_normal=KRATZER,
                    lack_normal_skala=1 / KRATZER_KACHEL, lack_normal_staerke=0.75)

M_LACK_S = lack("Lack_Schwarz", hexf("#0c0d0f"), 0.4)
M_LACK_W = lack("Lack_Weiss", hexf("#eef0f1"), 0.0, flakes=0.1)
M_SCHWARZ = material("Kunststoff_Schwarz", hexf("#151617"), rauheit=0.62)
M_GLAS = glas("Glas", hexf("#c4d2d0"))
M_GLAS_DUNKEL = glas("Glas_Getoent", hexf("#4f5857"))
M_TRIM = material("Hochglanz_Schwarz", hexf("#0b0c0d"), rauheit=0.1, lack=0.8, lack_rau=0.02)
M_SPALT = material("Spalt", hexf("#050505"), rauheit=0.9)
M_CHROM = material("Chrom", hexf("#dcdee0"), metall=1.0, rauheit=0.05)
M_SW_INNEN = material("Scheinwerfer_Innen", hexf("#2b2e32"), metall=1.0, rauheit=0.3)
M_SW_GLAS = glas("Scheinwerfer_Glas", hexf("#f1f4f6"))
M_REFLEKTOR = material("Reflektor", hexf("#e6e8ea"), metall=1.0, rauheit=0.07)
M_LED = material("Tagfahrlicht", hexf("#ffffff"), rauheit=0.2, leuchten=2.5)
M_RL_GLAS = glas("Ruecklicht_Glas", hexf("#d0121a"))
M_RL_LED = material("Ruecklicht_LED", hexf("#b0141a"), rauheit=0.3, leuchten=0.8, leucht_farbe=hexf("#ff2020"))
M_BLAULICHT = material("Blaulicht", hexf("#1a4cff"), rauheit=0.25, leuchten=0.0, leucht_farbe=hexf("#2a5bff"))
M_ROTLICHT = material("Rotlicht", hexf("#d0141c"), rauheit=0.25, leuchten=0.0, leucht_farbe=hexf("#ff1a1a"))
M_BL_KAPPE = glas("Lichtbalken_Blau", hexf("#6a8fff"))
M_ROT_KAPPE = glas("Lichtbalken_Rot", hexf("#ff6b6b"))
M_KLAR_KAPPE = glas("Lichtbalken_Klar", hexf("#eef2f4"))
M_FOLIE_S = material("Folie_Schwarz", hexf("#0a0a0b"), rauheit=0.35)
M_WEISS = material("Reflexfolie_Weiss", hexf("#eef0f0"), rauheit=0.36, lack=0.5, lack_rau=0.04)
M_GOLD = material("Abzeichen_Gold", hexf("#d4a21e"), metall=1.0, rauheit=0.3)
M_ABZ_BLAU = material("Abzeichen_Blau", hexf("#14254f"), rauheit=0.4)
M_RAMMSCHUTZ = material("Rammschutz", hexf("#111213"), metall=0.6, rauheit=0.45)
M_GUMMI = material("Reifen", hexf("#1c1d1e"), rauheit=0.88, normal=REIFEN_N, farb_bild=REIFEN_BC)
M_FELGE = material("Felge_Schwarz", hexf("#18191a"), metall=0.5, rauheit=0.35, lack=0.6, lack_rau=0.05)
M_FELGE_DUNKEL = material("Felge_Innen", hexf("#2a2c2e"), metall=0.6, rauheit=0.5)
M_BREMSE = material("Bremse", hexf("#5a5c5e"), metall=0.85, rauheit=0.38)
M_INNEN = material("Innenraum", hexf("#1e1f21"), rauheit=0.78)
M_INNEN_HELL = material("Innenraum_Stoff", hexf("#34363a"), rauheit=0.95)
M_SCHILD = material("Kennzeichen", hexf("#f4f4f0"), rauheit=0.35)
M_SCHILD_SCHRIFT = material("Kennzeichen_Schrift", hexf("#1c2f7a"), rauheit=0.35)
M_BLINKER = material("Blinker", hexf("#b88a55"), rauheit=0.3, leuchten=0.0, leucht_farbe=hexf("#ff8a10"))
M_BILDSCHIRM = material("Bildschirm", hexf("#0d1520"), rauheit=0.15, leuchten=0.0, leucht_farbe=hexf("#6f9fe0"))
M_GITTER = material("Trenngitter", hexf("#1a1b1c"), metall=0.7, rauheit=0.4)
M_INNEN_LEDER = material("Innenraum_Kunstleder", hexf("#161719"), rauheit=0.5, lack=0.15, lack_rau=0.3)
M_INSTRUMENT = material("Instrumente_Weiss", hexf("#e6e6e2"), rauheit=0.4)
M_RL_REFL = material("Ruecklicht_Reflektor", hexf("#d9dbdd"), metall=1.0, rauheit=0.12, normal=FACETTEN,
                     normal_uv="UV_Flakes", normal_skala=1 / FACETTEN_KACHEL)
M_BL_REFL = material("Blinker_Reflektor", hexf("#c98a2e"), metall=1.0, rauheit=0.22)
M_SEITE_GELB = material("Seitenleuchte_Gelb", hexf("#d98a1c"), rauheit=0.08, lack=1.0, lack_rau=0.01, normal=FACETTEN,
                        normal_uv="UV_Flakes", normal_skala=1.5 / FACETTEN_KACHEL, normal_staerke=0.6)
M_SEITE_ROT = material("Seitenleuchte_Rot", hexf("#a8121a"), rauheit=0.08, lack=1.0, lack_rau=0.01, normal=FACETTEN,
                       normal_uv="UV_Flakes", normal_skala=1.5 / FACETTEN_KACHEL, normal_staerke=0.6)

# ---------------- Karosserie: Querschnitte entlang X (Limousine mit Stufenheck) ----------------
Z_TOP = pchip([(2.55, 0.70), (2.52, 0.79), (2.47, 0.85), (2.32, 0.89), (1.95, 0.94), (1.50, 0.985), (1.30, 1.005),
               (1.22, 1.02), (1.00, 1.16), (0.75, 1.30), (0.50, 1.40), (0.28, 1.455), (0.0, 1.48), (-0.60, 1.48),
               (-0.95, 1.465), (-1.10, 1.43), (-1.35, 1.29), (-1.60, 1.14), (-1.76, 1.075), (-2.00, 1.06),
               (-2.30, 1.05), (-2.44, 1.025), (-2.51, 0.96), (-2.55, 0.82)])
Z_GURT = pchip([(2.55, 0.68), (2.45, 0.83), (2.20, 0.875), (1.50, 0.955), (1.20, 0.985), (0.0, 1.02), (-1.20, 1.04),
                (-1.70, 1.04), (-2.20, 1.03), (-2.42, 0.99), (-2.50, 0.93), (-2.55, 0.80)])
Z_BODEN = pchip([(2.55, 0.30), (2.45, 0.25), (2.25, 0.225), (1.95, 0.215), (-1.95, 0.215), (-2.25, 0.24), (-2.45, 0.30),
                 (-2.55, 0.36)])
W = pchip([(2.55, 0.79), (2.50, 0.87), (2.42, 0.915), (2.20, 0.94), (1.90, 0.95), (1.48, 0.948), (0.0, 0.94),
           (-1.48, 0.948), (-1.90, 0.95), (-2.30, 0.935), (-2.47, 0.90), (-2.55, 0.83)])
W_TOP = pchip([(2.55, 0.68), (2.45, 0.78), (2.20, 0.83), (1.60, 0.85), (1.30, 0.84), (1.10, 0.80), (0.60, 0.76),
               (0.20, 0.745), (-0.60, 0.74), (-1.00, 0.745), (-1.30, 0.77), (-1.60, 0.81), (-1.80, 0.835), (-2.20, 0.845),
               (-2.42, 0.83), (-2.55, 0.74)])
WOELB = pchip([(2.55, 0.012), (2.30, 0.022), (1.30, 0.025), (0.30, 0.025), (0.0, 0.03), (-1.00, 0.028), (-1.40, 0.02),
               (-1.80, 0.016), (-2.40, 0.012), (-2.55, 0.008)])
T_SEITE = (0.07, 0.22, 0.40, 0.55, 0.62, 0.72, 0.86, 0.96)
U_OBEN = (0.12, 0.45, 0.80, 1.0)
F_DACH = (0.8, 0.55, 0.28, 0.0)

def einzug(t):
    """Seitenwand: unten eingezogen (Schweller), zur Schulter hin leicht nach innen."""
    return 0.03 * max(0.0, 1 - t / 0.25) ** 2 + 0.022 * max(0.0, (t - 0.6) / 0.4) ** 2

def glatt01(a):
    a = min(1.0, max(0.0, a))
    return a * a * (3 - 2 * a)

def kotfluegel(x, t):
    """Ausgestellte Kotfluegel ueber den Raedern, zwischen den Achsen schmaler (Taille)."""
    beule = math.exp(-((x - XV) / 0.48) ** 2) + math.exp(-((x - XH) / 0.48) ** 2)
    return 0.018 * beule * glatt01((t - 0.04) / 0.30) * glatt01((0.97 - t) / 0.25)

def schnitt(x):
    """Rechte Haelfte eines Querschnitts von der Bodenmitte bis zur Dachmitte: Liste (y, z)."""
    zt, zg, zb, w, wt, cr = Z_TOP(x), Z_GURT(x), Z_BODEN(x), W(x), W_TOP(x), WOELB(x)
    zg = min(zg, zt - cr - 0.004)
    zu = zb - 0.03
    pts = [(0.0, zu), (0.45 * w, zu), (w - 0.13, zu + 0.004), (w - 0.045, zb)]
    for t in T_SEITE:
        kante = 0.004 if t == 0.86 else 0.0                       # Charakterlinie
        pts.append((w - einzug(t) + kotfluegel(x, t) + kante, zb + (zg - zb) * t))
    ws = w - 0.035
    pts.append((ws, zg))
    ze = zt - cr * 0.95
    for u in U_OBEN:
        pts.append((ws + (wt - ws) * u, zg + (ze - zg) * (1 - (1 - u) ** 1.2)))
    for f in F_DACH:
        pts.append((wt * f, zt - cr * f * f))
    return pts

def seiten_y(x, z):
    """Lage der Seitenwand (|y|) bei x und Hoehe z aus dem Querschnitt."""
    pts = schnitt(x)
    best = None
    for (y0, z0), (y1, z1) in zip(pts[3:13], pts[4:14]):
        if min(z0, z1) - 1e-6 <= z <= max(z0, z1) + 1e-6 and abs(z1 - z0) > 1e-6:
            best = y0 + (y1 - y0) * (z - z0) / (z1 - z0)
    return best if best is not None else W(x)

def schweller_z(x):
    """Unterkante der Tueren: Grenze zwischen Band 3 und 4 der Seitenwand."""
    zb, zg = Z_BODEN(x), min(Z_GURT(x), Z_TOP(x) - WOELB(x) - 0.004)
    return zb + (zg - zb) * 0.07

# Abschnitte (x von - bis): Fenster, Saeulen, Wasserkasten, Dach, Tueren
FENSTER_SEITE = [(-0.06, 1.18), (-1.14, -0.14)]
B_SAEULE = (-0.14, -0.06)
FRONTSCHEIBE = (0.28, 1.22)
WASSERKASTEN = (1.22, 1.32)
HECKSCHEIBE = (-1.72, -1.00)
DACH = (-1.00, 0.28)
AUFBAU = (-1.76, 1.32)              # Fahrgastzelle: Saeulen und Dach weiss
TUEREN = (-1.04, 1.04)              # weisse Tueren

def stationen():
    xs = set(round(v, 4) for v in np.arange(-2.55, 2.5501, 0.06))
    for a, b in FENSTER_SEITE + [B_SAEULE, FRONTSCHEIBE, WASSERKASTEN, HECKSCHEIBE, DACH, AUFBAU, TUEREN]:
        xs |= {round(a, 4), round(b, 4)}
    xs |= {-2.535, -2.52, -2.505, -2.485, 2.535, 2.52, 2.505, 2.485, -2.30, -2.44, 2.45, 2.40, 1.26, 0.32, 0.20}
    out = []
    for x in sorted(xs):
        if not out or x - out[-1] > 0.012:
            out.append(x)
    if out[-1] != 2.55:
        out[-1] = 2.55
    return out

def bereich(x, ranges):
    return any(a <= x <= b for a, b in ranges)

# Materialindizes der Karosserie
K_S, K_W, K_SCHWARZ, K_GLAS, K_TRIM, K_GLAS_D = range(6)

def flaechen_material(j, xm):
    """Materialindex fuer das Flaechenband j (zwischen Punkt j und j+1 der rechten Haelfte) bei x = xm."""
    if j <= 2:
        return K_SCHWARZ                           # Unterboden
    if j == 3:
        return K_S                                 # Schweller
    if j <= 11:
        return K_W if bereich(xm, [TUEREN]) else K_S
    if j <= 15:
        if bereich(xm, [B_SAEULE]):
            return K_TRIM
        if bereich(xm, FENSTER_SEITE):
            if j in (13, 14):
                return K_GLAS if bereich(xm, [FENSTER_SEITE[0]]) else K_GLAS_D
            return K_TRIM
        return K_W if bereich(xm, [AUFBAU]) else K_S
    if bereich(xm, [WASSERKASTEN]):
        return K_SCHWARZ
    if bereich(xm, [FRONTSCHEIBE]):
        return K_TRIM if j == 16 else K_GLAS
    if bereich(xm, [HECKSCHEIBE]):
        return K_TRIM if j == 16 else K_GLAS_D
    return K_W if bereich(xm, [DACH]) else K_S

def karosserie():
    xs = stationen()
    halb = [schnitt(x) for x in xs]
    nh = len(halb[0])
    bm = bmesh.new()
    ringe = []
    for x, pts in zip(xs, halb):
        rechts = [bm.verts.new((x, -y, z)) for (y, z) in pts]           # rechte Seite = -Y
        links = [bm.verts.new((x, y, z)) for (y, z) in pts[1:-1]]       # linke Seite ohne die beiden Mitten
        ringe.append((rechts, links))
    def L(lst, rr, i):
        return rr[i] if i in (0, nh - 1) else lst[i - 1]
    for k in range(len(xs) - 1):
        xm = (xs[k] + xs[k + 1]) / 2
        (ra, la), (rb, lb) = ringe[k], ringe[k + 1]
        for j in range(nh - 1):
            mi = flaechen_material(j, xm)
            bm.faces.new((ra[j], rb[j], rb[j + 1], ra[j + 1])).material_index = mi
            bm.faces.new((L(la, ra, j + 1), L(lb, rb, j + 1), L(lb, rb, j), L(la, ra, j))).material_index = mi
    # Stirnflaechen vorn und hinten: eingerueckte Ringe (leicht gewoelbt) und ein Faecher zur Mitte;
    # unterhalb der Bodenlinie Kunststoff, darueber schwarzer Lack
    kap = bm.faces.layers.int.new("kappe")
    for k, sg in ((0, -1), (len(xs) - 1, 1)):
        r, l = ringe[k]
        loop = r + l[::-1]
        cy = sum(v.co.y for v in loop) / len(loop)
        cz = sum(v.co.z for v in loop) / len(loop)
        x0 = loop[0].co.x
        prev = loop
        for sc, dx in ((0.93, 0.010), (0.78, 0.020), (0.55, 0.027), (0.30, 0.031)):
            ring = [bm.verts.new((x0 + sg * dx, cy + (v.co.y - cy) * sc, cz + (v.co.z - cz) * sc)) for v in loop]
            n = len(loop)
            for i in range(n):
                bm.faces.new((prev[i], prev[(i + 1) % n], ring[(i + 1) % n], ring[i]))[kap] = k + 1
            prev = ring
        mitte = bm.verts.new((x0 + sg * 0.032, cy, cz))
        for i in range(len(prev)):
            bm.faces.new((prev[i], prev[(i + 1) % len(prev)], mitte))[kap] = k + 1
        zb = Z_BODEN(x0)
        fl = [f for f in bm.faces if f[kap] == k + 1]
        geom = fl + list({e for f in fl for e in f.edges}) + list({v for f in fl for v in f.verts})
        bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0, 0, zb), plane_no=(0, 0, 1))
        for f in bm.faces:
            if f[kap] == k + 1:
                f.material_index = K_SCHWARZ if f.calc_center_median().z < zb else K_S
    bm.faces.layers.int.remove(kap)
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # Kantenschaerfe: Charakterlinie (Punkt 10), Schulter (12), Kante zwischen Seite und Dach/Haube (16)
    cl = bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")
    for k in range(len(xs) - 1):
        (ra, la), (rb, lb) = ringe[k], ringe[k + 1]
        for idx, wert in ((10, 0.9), (12, 0.8), (16, 0.45)):
            for va, vb in ((ra[idx], rb[idx]), (la[idx - 1], lb[idx - 1])):
                e = bm.edges.get((va, vb))
                if e is not None:
                    e[cl] = wert
    # Scheiben versenken: jede Scheibe 12 mm nach innen, ringsum eine 16 mm breite schwarze Einfassung
    rest = {f for f in bm.faces if f.material_index in (K_GLAS, K_GLAS_D)}
    while rest:
        f0 = rest.pop()
        region, stapel = [f0], [f0]
        while stapel:
            f = stapel.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g in rest:
                        rest.remove(g)
                        region.append(g)
                        stapel.append(g)
        res = bmesh.ops.inset_region(bm, faces=region, thickness=0.016, depth=-0.012, use_even_offset=True)
        for f in res["faces"]:
            f.material_index = K_TRIM
    for e in bm.edges:
        mats = {f.material_index for f in e.link_faces}
        if len(mats) == 2 and K_TRIM in mats and (mats & {K_GLAS, K_GLAS_D, K_W, K_S}):
            e[cl] = max(e[cl], 0.85)
    ob = objekt("Karosserie", bm, [M_LACK_S, M_LACK_W, M_SCHWARZ, M_GLAS, M_TRIM, M_GLAS_DUNKEL], glatt=True)
    sub = ob.modifiers.new("Glaetten", "SUBSURF")
    sub.levels = sub.render_levels = 1
    sub.subdivision_type = "CATMULL_CLARK"
    anwenden(ob, sub)
    return ob

# ---------------- Ausschnitte: Radlaeufe, Leuchten, Grill, Lufteinlaesse, Kennzeichenmulde, Griffmulden ----------------
VORN = dict(ursprung=(2.85, 0, 0), achse=(-1, 0, 0), e1=(0, 1, 0), e2=(0, 0, 1))
HINTEN = dict(ursprung=(-2.85, 0, 0), achse=(1, 0, 0), e1=(0, 1, 0), e2=(0, 0, 1))
def SEITE(sg):
    return dict(ursprung=(0, sg * 1.4, 0), achse=(0, -sg, 0), e1=(1, 0, 0), e2=(0, 0, 1))

def gespiegelt(umriss, sg):
    """Umriss (y, z) der linken Seite fuer sg = -1 spiegeln (Umlaufsinn bleibt gueltig)."""
    pts = [(sg * a, b) for (a, b) in umriss]
    return pts if sg > 0 else pts[::-1]

U_SCHEINWERFER = chaikin([(0.40, 0.602), (0.47, 0.592), (0.66, 0.590), (0.82, 0.602), (0.885, 0.625), (0.905, 0.66),
                          (0.89, 0.69), (0.80, 0.697), (0.62, 0.690), (0.43, 0.672)], 2)
U_GRILL = chaikin([(-0.33, 0.475), (0.33, 0.475), (0.365, 0.50), (0.375, 0.655), (0.35, 0.678), (-0.35, 0.678),
                   (-0.375, 0.655), (-0.365, 0.50)], 3)
U_EINLASS = chaikin([(-0.52, 0.31), (0.52, 0.31), (0.555, 0.345), (0.525, 0.40), (-0.525, 0.40), (-0.555, 0.345)], 3)
U_NEBEL = chaikin([(0.61, 0.325), (0.72, 0.33), (0.745, 0.42), (0.665, 0.445), (0.605, 0.41)], 3)
U_RUECKLICHT = chaikin([(0.50, 0.815), (0.70, 0.805), (0.86, 0.81), (0.928, 0.845), (0.935, 0.93), (0.89, 0.965),
                        (0.70, 0.965), (0.515, 0.945)], 2)
U_KENNZEICHEN = chaikin([(-0.168, 0.535), (0.168, 0.535), (0.168, 0.705), (-0.168, 0.705)], 2)
KENNZ_Z = 0.62
U_HECKBLITZER = chaikin([(0.24, 0.52), (0.36, 0.52), (0.36, 0.553), (0.24, 0.553)], 2)
GRIFFE = (0.52, -0.62)
GRIFF_Z = 0.90
def u_griffmulde(xg):
    return chaikin([(xg - 0.085, GRIFF_Z - 0.021), (xg + 0.085, GRIFF_Z - 0.021), (xg + 0.085, GRIFF_Z + 0.021),
                    (xg - 0.085, GRIFF_Z + 0.021)], 3)

PATCHES = {}
BVH_ROH = None
def ausschnitte(kar):
    """Alle Schneidekoerper bauen, mit der unversehrten Karosserie als Projektionsflaeche. Projiziert wird auf eine
    zweimal feiner unterteilte Kopie: Glaeser und Anbauteile liegen dann auf der glatten Grenzflaeche statt auf den
    Facetten des Netzes, und ihre Spiegelungen brechen nicht an Netzkanten."""
    global BVH_ROH
    kopie = kar.copy()
    kopie.data = kar.data.copy()
    scene.collection.objects.link(kopie)
    sub = kopie.modifiers.new("Fein", "SUBSURF")
    sub.levels = sub.render_levels = 2
    bvh = BVH_ROH = bvh_von(kopie)
    me = kopie.data
    bpy.data.objects.remove(kopie)
    bpy.data.meshes.remove(me)
    bm = bmesh.new()      # Materialien: 0 Radkasten, 1 Scheinwerfer innen, 2 Hochglanz schwarz, 3 Spalt, 4 Lack schwarz,
    #                       5 Rueckleuchten-Reflektor
    for name, (x, y) in RAEDER.items():
        einfuegen(bm, zylinder((x, math.copysign(0.94, y), RAD_R), BOGEN_R, 0.74, "Y", segs=56, mi=0))
    def aussparung(name, umriss, ansicht, tiefe, mi_wand, mi_boden, raster=0.012):
        pb, fehl = patch(umriss, ansicht["ursprung"], ansicht["achse"], ansicht["e1"], ansicht["e2"], bvh, raster)
        if fehl:
            log("  Warnung:", name, fehl, "Strahlen ohne Treffer")
        PATCHES[name] = pb
        einfuegen(bm, schale(pb, 0.03, tiefe, mi_wand, mi_boden))
    for sg, s in ((1, "l"), (-1, "r")):
        aussparung("scheinwerfer_" + s, gespiegelt(U_SCHEINWERFER, sg), VORN, 0.075, 1, 1, 0.010)
        aussparung("nebel_" + s, gespiegelt(U_NEBEL, sg), VORN, 0.05, 2, 2, 0.010)
        aussparung("ruecklicht_" + s, gespiegelt(U_RUECKLICHT, sg), HINTEN, 0.055, 5, 5, 0.010)
        aussparung("heckblitzer_" + s, gespiegelt(U_HECKBLITZER, sg), HINTEN, 0.02, 2, 2, 0.008)
        for xg in GRIFFE:
            aussparung(f"griff_{s}_{xg}", u_griffmulde(xg), SEITE(sg), 0.014, 4, 4, 0.008)
    aussparung("grill", U_GRILL, VORN, 0.06, 2, 3, 0.012)
    aussparung("einlass", U_EINLASS, VORN, 0.06, 2, 3, 0.012)
    aussparung("kennzeichen", U_KENNZEICHEN, HINTEN, 0.02, 4, 2, 0.012)
    schneider = objekt("_Schneider", bm, [M_SCHWARZ, M_SW_INNEN, M_TRIM, M_SPALT, M_LACK_S, M_RL_REFL])
    # Fugen: Tueren, Tuerunterkanten, Haube, Kofferraumdeckel, Stossfaenger, Tankdeckel
    bm = bmesh.new()
    def seite(x, z, sg):
        return (x, sg * (seiten_y(x, z) + 0.004), z)
    for sg in (-1, 1):
        for x0 in TUEREN + (-0.10,):
            rille(bm, [seite(x0, z, sg) for z in np.linspace(schweller_z(x0), Z_GURT(x0) - 0.012, 60)], bvh)
        rille(bm, [seite(x, schweller_z(x), sg) for x in np.linspace(TUEREN[0], TUEREN[1], 120)], bvh)
        # Stossfaenger vorn und hinten: vom Radlauf zur Leuchte
        a = math.radians(58)
        p0 = (XV + (BOGEN_R - 0.012) * math.cos(a), RAD_R + (BOGEN_R - 0.012) * math.sin(a))
        rille(bm, [seite(p0[0] + (2.44 - p0[0]) * t, p0[1] + (0.612 - p0[1]) * t - 0.012 * math.sin(math.pi * t), sg)
                   for t in np.linspace(0, 1, 50)], bvh)
        p0 = (XH - (BOGEN_R - 0.012) * math.cos(a), RAD_R + (BOGEN_R - 0.012) * math.sin(a))
        rille(bm, [seite(p0[0] + (-2.44 - p0[0]) * t, p0[1] + (0.808 - p0[1]) * t - 0.010 * math.sin(math.pi * t), sg)
                   for t in np.linspace(0, 1, 50)], bvh)
        # Kofferraumdeckel: Laengsfugen auf dem Deck
        rille(bm, [(x, sg * (W_TOP(x) - 0.07), 2.0) for x in np.linspace(-1.78, -2.43, 40)], bvh, strahl=(0, 0, -1))
    # Haube: geschlossene Linie (Seiten, Vorderkante, Wasserkasten)
    def hy(x):
        return W_TOP(x) - 0.07
    xe, xk = 2.495, 2.42
    haube = [(x, -hy(x), Z_TOP(x) + 0.02) for x in np.linspace(1.34, xk, 60)]
    haube += [(xk + (xe - xk) * math.sin(w), -hy(xk) * math.cos(w), Z_TOP(xk) + 0.02) for w in np.linspace(0.15, 1.25, 8)]
    haube += [(xe, y, Z_TOP(xe) + 0.02) for y in np.linspace(-hy(xk) * 0.3, hy(xk) * 0.3, 30)]
    haube += [(xk + (xe - xk) * math.sin(w), hy(xk) * math.cos(w), Z_TOP(xk) + 0.02) for w in np.linspace(1.25, 0.15, 8)]
    haube += [(x, hy(x), Z_TOP(x) + 0.02) for x in np.linspace(xk, 1.34, 60)]
    haube += [(1.34, y, Z_TOP(1.34) + 0.02) for y in np.linspace(hy(1.34) * 0.97, -hy(1.34) * 0.97, 60)]
    rille(bm, haube, bvh, geschlossen=True)
    # Kofferraumdeckel: Vorderkante unter der Heckscheibe und Hinterkante um Kennzeichen und Leuchten herum
    rille(bm, [(-1.78, y, 2.0) for y in np.linspace(-hy(-1.78), hy(-1.78), 70)], bvh, strahl=(0, 0, -1))
    heck = [(0.775, 1.015), (0.72, 0.978), (0.60, 0.966), (0.545, 0.955), (0.50, 0.93), (0.49, 0.85), (0.49, 0.79)]
    pts = [(-2.9, a, b) for a, b in heck] + [(-2.9, y, 0.79) for y in np.linspace(0.47, -0.47, 40)]
    pts += [(-2.9, -a, b) for a, b in heck[::-1]]
    rille(bm, pts, bvh, strahl=(1, 0, 0))
    tank = [(-1.60 + 0.085 * math.copysign(abs(math.cos(w)) ** 0.35, math.cos(w)),
             0.93 + 0.065 * math.copysign(abs(math.sin(w)) ** 0.35, math.sin(w))) for w in np.linspace(0, 2 * math.pi, 48, endpoint=False)]
    rille(bm, [seite(x, z, 1) for (x, z) in tank], bvh, geschlossen=True)
    fugen = objekt("_Fugen", bm, [M_SPALT])
    return schneider, fugen

def schneiden(kar, schneider, fugen):
    for cut, selbst in ((schneider, False), (fugen, True)):
        mod = kar.modifiers.new("Schnitt", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.material_mode = "TRANSFER"
        mod.use_self = selbst
        mod.object = cut
        anwenden(kar, mod)
        bpy.data.objects.remove(cut)
    kar.data.set_sharp_from_angle(angle=math.radians(35))

# ---------------- Details: Leuchten, Grill, Kennzeichen, Folien, Spiegel, Griffe, Dach, Innenraum ----------------
def auf_flaeche(ob, ziel, abstand=0.0008):
    """Objekt (Schrift) auf die Karosserie legen."""
    sw = ob.modifiers.new("Auflegen", "SHRINKWRAP")
    sw.target = ziel
    sw.wrap_method = "NEAREST_SURFACEPOINT"
    sw.offset = abstand
    anwenden(ob, sw)

def schrift(text, groesse, mat, rot, ort, name, ziel=None, abstand=0.0009):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.size = groesse
    cu.fill_mode = "FRONT"
    cu.resolution_u = 3
    tmp = bpy.data.objects.new(name + "_kurve", cu)
    scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    me.transform(Matrix.Translation(Vector(ort)) @ rot.to_4x4())
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    if ziel is not None:
        auf_flaeche(ob, ziel, abstand)
    return ob

def R(spalten):
    """Rotationsmatrix aus den Bildern der lokalen Achsen (x, y, z)."""
    return Matrix([[spalten[0][i], spalten[1][i], spalten[2][i]] for i in range(3)])

R_RECHTS = R(((1, 0, 0), (0, 0, 1), (0, -1, 0)))     # Seite -Y, liest von hinten nach vorn
R_LINKS = R(((-1, 0, 0), (0, 0, 1), (0, 1, 0)))      # Seite +Y
R_HAUBE = R(((0, 1, 0), (-1, 0, 0), (0, 0, 1)))      # auf der Haube, lesbar von vorn
R_HECK = R(((0, -1, 0), (0, 0, 1), (-1, 0, 0)))      # Heckklappe, lesbar von hinten
R_FRONT = R(((0, 1, 0), (0, 0, 1), (1, 0, 0)))       # Frontflaeche, lesbar von vorn

def auf(ansicht, a, b):
    """Punkt (a, b) der Ansicht auf die unversehrte Karosserie schiessen: (Ort, Normale nach aussen)."""
    O = Vector(ansicht["ursprung"]) + Vector(ansicht["e1"]) * a + Vector(ansicht["e2"]) * b
    d = Vector(ansicht["achse"])
    loc, nor = BVH_ROH.ray_cast(O, d)[:2]
    if loc is None:
        loc, nor = BVH_ROH.find_nearest(O)[:2]
    return loc, (-nor if nor.dot(d) > 0 else nor)

def pfad(ansicht, pts, tiefe):
    """Punkte (a, b) auf die Flaeche schiessen und um 'tiefe' nach innen setzen."""
    out = []
    for a, b in pts:
        loc, n = auf(ansicht, a, b)
        out.append(loc - n * tiefe)
    return out

def von_patch(key, mi, abstand=0.0008):
    """Abdeckung exakt auf der alten Flaeche ueber einer Aussparung (bmesh mit Materialindex)."""
    bm = PATCHES[key].copy()
    for v in bm.verts:
        v.co += v.normal * abstand
    for f in bm.faces:
        f.material_index = mi
    return bm

def ausrichten(bm, mitte, normale):
    """bmesh, das um den Ursprung mit Blick nach +X gebaut ist, an (mitte, normale) setzen."""
    rot = Vector(normale).to_track_quat("X", "Z").to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(mitte)) @ rot, verts=bm.verts)
    return bm

def waben(umriss, ansicht, R_, steg, dicke, tiefe, mi):
    """Wabengitter hinter einer Oeffnung; jede Ecke wird auf die Flaeche geschossen und nach innen gesetzt."""
    bm = bmesh.new()
    ri = R_ - steg / math.sqrt(3)
    a0, a1 = min(p[0] for p in umriss) - R_, max(p[0] for p in umriss) + R_
    b0, b1 = min(p[1] for p in umriss) - R_, max(p[1] for p in umriss) + R_
    i, a = 0, a0
    while a < a1:
        b = b0 + (math.sqrt(3) * R_ / 2 if i % 2 else 0.0)
        while b < b1:
            if im_vieleck((a, b), umriss) or abstand_rand((a, b), umriss) < R_ * 1.2:
                vo = [bm.verts.new((0, a + R_ * math.cos(math.pi / 3 * k), b + R_ * math.sin(math.pi / 3 * k))) for k in range(6)]
                vi = [bm.verts.new((0, a + ri * math.cos(math.pi / 3 * k), b + ri * math.sin(math.pi / 3 * k))) for k in range(6)]
                for k in range(6):
                    bm.faces.new((vo[k], vo[(k + 1) % 6], vi[(k + 1) % 6], vi[k])).material_index = mi
            b += math.sqrt(3) * R_
        a += 1.5 * R_
        i += 1
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.verts.index_update()
    normalen = {}
    for v in bm.verts:
        loc, n = auf(ansicht, v.co.y, v.co.z)
        v.co = loc - n * tiefe
        normalen[v.index] = n
    netz = schale(bm, 0.0, dicke, mi, mi, normalen)       # Dicke entlang der Flaechennormalen, ohne Ausreisser
    bm.free()
    return netz

def linse(ansicht, a, b, r, tiefe, mi_ring, mi_glas, mi_grund):
    """Rundes Lichtmodul: Chromring, gewoelbte Linse, dunkler Grund; an die Flaeche ausgerichtet."""
    loc, n = auf(ansicht, a, b)
    bm = bmesh.new()
    einfuegen(bm, zylinder((-0.004, 0, 0), r + 0.006, 0.014, "X", segs=28, mi=mi_ring, deckel=False))
    einfuegen(bm, kugel((0.002, 0, 0), r, segs=24, ringe=12, skala=(0.45, 1, 1), mi=mi_glas))
    einfuegen(bm, zylinder((-0.011, 0, 0), r + 0.010, 0.003, "X", segs=28, mi=mi_grund))
    return ausrichten(bm, loc - n * tiefe, n)

def linie_glatt(pts, n=2):
    """Offenen Linienzug runden (Chaikin); Anfang und Ende bleiben."""
    for _ in range(n):
        neu = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            a, b = Vector(a), Vector(b)
            neu += [tuple(a.lerp(b, 0.25)), tuple(a.lerp(b, 0.75))]
        neu.append(pts[-1])
        pts = neu
    return pts

def punkt_auf_linie(pts, t):
    """Punkt bei Anteil t (0..1) der Laenge eines Linienzugs."""
    pts = [Vector(p) for p in pts]
    laengen = [(b - a).length for a, b in zip(pts, pts[1:])]
    rest = t * sum(laengen)
    for a, b, l in zip(pts, pts[1:], laengen):
        if rest <= l or l == laengen[-1]:
            return tuple(a.lerp(b, min(1.0, rest / max(l, 1e-9))))
        rest -= l
    return tuple(pts[-1])

def projektor(ansicht, a, b, r, tiefe, mi_chrom, mi_glas, mi_schwarz):
    """Projektionsmodul: Reflektorschale aus Chrom, schwarzer Tubus, gewoelbte Linse, Zierring."""
    loc, n = auf(ansicht, a, b)
    bm = bmesh.new()
    einfuegen(bm, zylinder((-0.013, 0, 0), r * 0.85, 0.026, "X", segs=32, mi=mi_chrom, deckel=False, r2=r * 1.55))
    einfuegen(bm, zylinder((-0.012, 0, 0), r, 0.022, "X", segs=28, mi=mi_schwarz))
    einfuegen(bm, kugel((0.0012, 0, 0), r, segs=28, ringe=14, skala=(0.42, 1, 1), mi=mi_glas))
    ring = [(0.0005, r * 1.08 * math.cos(w), r * 1.08 * math.sin(w)) for w in np.linspace(0, 2 * math.pi, 41)]
    einfuegen(bm, rohr(ring, 0.0016, segs=8, mi=mi_chrom, deckel=False, oben=(1, 0, 0)))
    return ausrichten(bm, loc - n * tiefe, n)

def einfassung(ansicht, umriss, r, mi, abstand=0.0006):
    """Duenne Gummi-/Kunststoffeinfassung entlang des Randes einer Leuchte (deckt die Schnittkante ab)."""
    ring = []
    for a, b in umriss:
        loc, n = auf(ansicht, a, b)
        ring.append(loc + n * abstand)
    return rohr(ring + [ring[0]], r, segs=8, mi=mi, deckel=False, oben=tuple(-Vector(ansicht["achse"])))

def led_modul(mitte, richtung, laenge, anzahl, mi_led, mi_chrom, mi_grund, hoehe=0.028):
    """LED-Modul wie in echten Lichtbalken: Grundplatte, je LED ein Chrom-Reflektorbecher mit Leuchtpunkt."""
    bm = bmesh.new()
    einfuegen(bm, kasten((-0.009, 0, 0), (0.004, laenge, hoehe), fase=0.0012, mi=mi_grund))
    rr = min(laenge / anzahl, hoehe) * 0.45
    for k in range(anzahl):
        y = (k - (anzahl - 1) / 2) * laenge / anzahl
        einfuegen(bm, zylinder((-0.0035, y, 0), rr * 0.35, 0.007, "X", segs=16, mi=mi_chrom, deckel=False, r2=rr))
        einfuegen(bm, kugel((-0.005, y, 0), rr * 0.32, segs=10, ringe=5, mi=mi_led))
    rot = Vector(richtung).normalized().to_track_quat("X", "Z").to_matrix().to_4x4()
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(mitte)) @ rot, verts=bm.verts)
    return bm

def seitenleuchte(sg, xm, zm, laenge, hoehe, mi, mi_rand):
    """US-Seitenmarkierungsleuchte: flache Linse mit Reflektorfacetten auf dem Kotfluegel, schwarz eingefasst."""
    l, h = laenge / 2, hoehe / 2
    u = chaikin([(xm - l, zm - h), (xm + l, zm - h), (xm + l, zm + h), (xm - l, zm + h)], 3)
    a = SEITE(sg)
    pb, _ = patch(u, a["ursprung"], a["achse"], a["e1"], a["e2"], BVH_ROH, 0.005)
    teil = schale(pb, 0.0022, 0.0004, mi, mi)
    pb.free()
    einfuegen(teil, einfassung(a, u, 0.0015, mi_rand, abstand=0.0012))
    return teil


R_DACH = R(((0, -1, 0), (1, 0, 0), (0, 0, 1)))       # auf Dach oder Kofferraumdeckel, lesbar von hinten

def schrift_auf(text, groesse, mat, ort, normale, name):
    """Schrift flach auf eine Flaeche mit gegebener Normale, aufrecht und von aussen lesbar."""
    q = Vector(normale).to_track_quat("X", "Z").to_matrix().to_4x4()
    ob = schrift(text, groesse, mat, R_FRONT, (0, 0, 0), name)
    ob.data.transform(Matrix.Translation(Vector(ort)) @ q)
    return ob

def stern_abzeichen(sg, mitte_x, mitte_z, d, mi_gold, mi_blau):
    """Eigenes Abzeichen: goldener Ring, blaue Scheibe, sechszackiger Stern mit blauem Kern. Jede Ecke wird auf die
    Tuer geschossen; die Lagen liegen in kleinem Abstand uebereinander."""
    bm = bmesh.new()
    def ring(r0, r1, lage, mi, n=48):
        a = [Vector((mitte_x + r1 * math.cos(2 * math.pi * k / n), lage, mitte_z + r1 * math.sin(2 * math.pi * k / n))) for k in range(n)]
        if r0 <= 0:
            vs = [bm.verts.new(p) for p in a]
            bm.faces.new(vs).material_index = mi
            return
        i = [Vector((mitte_x + r0 * math.cos(2 * math.pi * k / n), lage, mitte_z + r0 * math.sin(2 * math.pi * k / n))) for k in range(n)]
        va, vi = [bm.verts.new(p) for p in a], [bm.verts.new(p) for p in i]
        for k in range(n):
            bm.faces.new((va[k], va[(k + 1) % n], vi[(k + 1) % n], vi[k])).material_index = mi
    r = d / 2
    ring(r * 0.88, r, 0.0011, mi_gold)                 # Ring
    ring(0.0, r * 0.88, 0.0008, mi_blau)               # Scheibe
    spitzen = []
    for k in range(12):
        w = math.pi / 2 + 2 * math.pi * k / 12
        rr = r * (0.74 if k % 2 == 0 else 0.36)
        spitzen.append(Vector((mitte_x + rr * math.cos(w), 0.0014, mitte_z + rr * math.sin(w))))
    mitte = bm.verts.new(Vector((mitte_x, 0.0014, mitte_z)))
    sv = [bm.verts.new(p) for p in spitzen]
    for k in range(12):
        bm.faces.new((mitte, sv[k], sv[(k + 1) % 12])).material_index = mi_gold
    ring(0.0, r * 0.2, 0.0017, mi_blau, n=24)          # Kern
    ring(0.0, r * 0.07, 0.0020, mi_gold, n=16)
    # Ecken auf die Tuer setzen: Lage (y-Wert) wird zum Abstand entlang der Flaechennormalen
    for v in bm.verts:
        lage = v.co.y
        loc, n = auf(SEITE(sg), v.co.x, v.co.z)
        v.co = loc + n * lage
    bm.normal_update()
    for f in bm.faces:
        if f.normal.y * sg < 0:
            f.normal_flip()
    return bm

def details(kar):
    teile = []
    bm = bmesh.new()
    (A_SCHWARZ, A_CHROM, A_TRIM, A_BLAU, A_ROT, A_SCHILD, A_SCHRIFT, A_LACK, A_BLKAPPE, A_ROTKAPPE, A_KLAR, A_RL, A_LED,
     A_BLINK, A_REFL, A_SWGLAS, A_RLGLAS, A_GOLD, A_ABZ, A_RAMM, A_BLREFL, A_SEITE_G, A_SEITE_R) = range(23)
    MATS_ANB = [M_SCHWARZ, M_CHROM, M_TRIM, M_BLAULICHT, M_ROTLICHT, M_SCHILD, M_SCHILD_SCHRIFT, M_LACK_S, M_BL_KAPPE,
                M_ROT_KAPPE, M_KLAR_KAPPE, M_RL_LED, M_LED, M_BLINKER, M_REFLEKTOR, M_SW_GLAS, M_RL_GLAS, M_GOLD,
                M_ABZ_BLAU, M_RAMMSCHUTZ, M_BL_REFL, M_SEITE_GELB, M_SEITE_ROT]
    for sg, s in ((1, "l"), (-1, "r")):
        rotblau = A_ROT if sg > 0 else A_BLAU             # Fahrerseite (links) rot, Beifahrerseite blau
        # --- Scheinwerfer: Glas mit Einfassung, zwei Projektionsmodule mit Chromschalen, flacher LED-Lichtleiter
        #     (Tagfahrlicht) in einem schwarzen Kanal, Blinker aus Einzel-LEDs vor einem Bernstein-Reflektor ---
        einfuegen(bm, von_patch("scheinwerfer_" + s, A_SWGLAS))
        einfuegen(bm, einfassung(VORN, gespiegelt(U_SCHEINWERFER, sg), 0.0024, A_TRIM))
        for a, b, r in ((0.535, 0.641, 0.026), (0.665, 0.645, 0.024)):
            einfuegen(bm, projektor(VORN, sg * a, b, r, 0.032, A_REFL, A_SWGLAS, A_TRIM))
        drl = linie_glatt([(sg * a, b) for a, b in ((0.445, 0.662), (0.55, 0.675), (0.66, 0.683), (0.77, 0.686),
                                                     (0.85, 0.681), (0.884, 0.665), (0.888, 0.645))], 2)
        einfuegen(bm, rohr(pfad(VORN, drl, 0.012), 0.0042, 0.0018, segs=12, mi=A_LED, oben=(1, 0, 0), eckig=5))
        einfuegen(bm, rohr(pfad(VORN, drl, 0.0155), 0.0064, 0.0016, segs=12, mi=A_TRIM, oben=(1, 0, 0), eckig=5))
        bl = linie_glatt([(sg * a, b) for a, b in ((0.48, 0.606), (0.62, 0.603), (0.76, 0.611), (0.84, 0.623))], 2)
        einfuegen(bm, rohr(pfad(VORN, bl, 0.025), 0.0068, 0.0012, segs=12, mi=A_BLREFL, oben=(1, 0, 0), eckig=5))
        for t in np.linspace(0.04, 0.96, 10):
            loc, n = auf(VORN, *punkt_auf_linie(bl, t))
            einfuegen(bm, ausrichten(zylinder((0, 0, 0), 0.0026, 0.003, "X", segs=10, mi=A_BLINK), loc - n * 0.022, n))
        # --- Nebelscheinwerfer mit Chromschale und Einfassung ---
        einfuegen(bm, projektor(VORN, sg * 0.675, 0.385, 0.026, 0.02, A_CHROM, A_SWGLAS, A_TRIM))
        einfuegen(bm, einfassung(VORN, gespiegelt(U_NEBEL, sg), 0.003, A_TRIM))
        # --- Rueckleuchten: rotes Glas vor facettiertem Reflektor, LED-Lichtleiter als C, LED-Reihe,
        #     Rueckfahrlicht mit Chromschale ---
        einfuegen(bm, von_patch("ruecklicht_" + s, A_RLGLAS))
        einfuegen(bm, einfassung(HINTEN, gespiegelt(U_RUECKLICHT, sg), 0.0022, A_TRIM))
        c = linie_glatt([(sg * a, b) for a, b in ((0.54, 0.86), (0.60, 0.832), (0.72, 0.822), (0.85, 0.827),
                                                   (0.905, 0.855), (0.91, 0.915), (0.87, 0.945), (0.72, 0.947),
                                                   (0.60, 0.93))], 2)
        einfuegen(bm, rohr(pfad(HINTEN, c, 0.014), 0.0048, 0.0018, segs=12, mi=A_RL, oben=(1, 0, 0), eckig=5))
        einfuegen(bm, rohr(pfad(HINTEN, c, 0.0175), 0.0068, 0.0015, segs=12, mi=A_TRIM, oben=(1, 0, 0), eckig=5))
        reihe = [(sg * 0.60, 0.886), (sg * 0.74, 0.888)]
        for t in np.linspace(0.0, 1.0, 7):
            loc, n = auf(HINTEN, *punkt_auf_linie(reihe, t))
            einfuegen(bm, ausrichten(kugel((0, 0, 0), 0.0045, segs=12, ringe=6, skala=(0.5, 1, 1), mi=A_RL),
                                     loc - n * 0.022, n))
        einfuegen(bm, projektor(HINTEN, sg * 0.79, 0.862, 0.014, 0.026, A_REFL, A_SWGLAS, A_TRIM))
        # --- Blitzer im hinteren Stossfaenger (links rot, rechts blau) ---
        einfuegen(bm, von_patch("heckblitzer_" + s, A_SWGLAS))
        loc, n = auf(HINTEN, sg * 0.30, 0.5365)
        einfuegen(bm, led_modul(loc - n * 0.004, n, 0.105, 4, rotblau, A_REFL, A_TRIM, hoehe=0.026))
        # --- Seitenmarkierungsleuchten (vorn gelb, hinten rot), wie in den USA vorgeschrieben ---
        einfuegen(bm, seitenleuchte(sg, 2.24, 0.665, 0.065, 0.019, A_SEITE_G, A_TRIM))
        einfuegen(bm, seitenleuchte(sg, -2.30, 0.865, 0.065, 0.019, A_SEITE_R, A_TRIM))
        # --- Reflektoren an den Stossfaengerecken ---
        u = chaikin([(0.60, 0.47), (0.78, 0.47), (0.78, 0.495), (0.60, 0.495)], 2)
        pb, _ = patch(gespiegelt(u, sg), HINTEN["ursprung"], HINTEN["achse"], HINTEN["e1"], HINTEN["e2"], BVH_ROH, 0.008)
        for v in pb.verts:
            v.co += v.normal * 0.0012
        for f in pb.faces:
            f.material_index = A_RLGLAS
        einfuegen(bm, pb)
        # --- Endrohre ---
        einfuegen(bm, zylinder((-2.585, sg * 0.60, 0.305), 0.042, 0.11, "X", segs=24, mi=A_CHROM, deckel=False))
        einfuegen(bm, zylinder((-2.57, sg * 0.60, 0.305), 0.036, 0.004, "X", segs=24, mi=A_TRIM))
    # --- Grill: Wabengitter, schwarzer Rahmen, rote und blaue Blitzer ---
    einfuegen(bm, waben(U_GRILL, VORN, 0.0165, 0.0035, 0.006, 0.026, A_TRIM))
    rahmen = [auf(VORN, a, b) for a, b in U_GRILL]
    einfuegen(bm, rohr([p + n * 0.002 for p, n in rahmen] + [rahmen[0][0] + rahmen[0][1] * 0.002], 0.004, segs=8,
                       mi=A_TRIM, deckel=False))
    for sg in (-1, 1):
        for yy in (0.13, 0.25):
            loc, n = auf(VORN, sg * yy, 0.585)
            einfuegen(bm, led_modul(loc - n * 0.008, n, 0.075, 3, A_ROT if sg > 0 else A_BLAU, A_REFL, A_TRIM,
                                    hoehe=0.024))
    einfuegen(bm, waben(U_EINLASS, VORN, 0.018, 0.004, 0.006, 0.028, A_TRIM))
    # --- Rammschutzbuegel mit Gummiauflagen, Blitzern und Sirenenlautsprecher ---
    xr = 2.705
    for sg in (-1, 1):
        y = sg * 0.30
        einfuegen(bm, rohr([(xr - 0.01, y, 0.255), (xr, y, 0.50), (xr, y, 0.775)], 0.028, 0.038, segs=12, mi=A_RAMM,
                           oben=(1, 0, 0), eckig=4))
        einfuegen(bm, rohr([(xr - 0.02, y, 0.29), (2.52, y, 0.275), (2.30, y, 0.27)], 0.022, 0.03, segs=10, mi=A_RAMM,
                           oben=(0, 0, 1), eckig=4))
        einfuegen(bm, kasten((xr + 0.042, y, 0.58), (0.016, 0.046, 0.30), fase=0.006, mi=A_SCHWARZ))
        einfuegen(bm, led_modul((xr + 0.038, sg * 0.18, 0.752), (1, 0, 0), 0.10, 4, A_ROT if sg > 0 else A_BLAU,
                                A_REFL, A_TRIM, hoehe=0.024))
    einfuegen(bm, rohr([(xr, y, 0.752) for y in np.linspace(-0.42, 0.42, 20)], 0.032, 0.026, segs=12, mi=A_RAMM, eckig=4))
    einfuegen(bm, rohr([(xr, y, 0.52) for y in np.linspace(-0.30, 0.30, 16)], 0.026, 0.024, segs=12, mi=A_RAMM, eckig=4))
    einfuegen(bm, kasten((2.635, 0.0, 0.40), (0.10, 0.22, 0.13), fase=0.012, mi=A_SCHWARZ))
    for k in range(5):
        einfuegen(bm, kasten((2.686, 0.0, 0.355 + 0.022 * k), (0.004, 0.19, 0.008), mi=A_TRIM))
    # --- US-Kennzeichen in der Mulde des Kofferraumdeckels ---
    loc, n = auf(HINTEN, 0.0, KENNZ_Z)
    einfuegen(bm, ausrichten(kasten((0, 0, 0), (0.006, 0.305, 0.152), fase=0.004, mi=A_SCHILD), loc - n * 0.015, n))
    teile.append(schrift_auf("EXEMPT", 0.03, M_SCHILD_SCHRIFT, loc - n * 0.0115 + Vector((0, 0, 0.05)), n, "Kennzeichen_oben"))
    teile.append(schrift_auf("PD 2740", 0.068, M_SCHILD_SCHRIFT, loc - n * 0.0115 + Vector((0, 0, -0.008)), n, "Kennzeichen"))
    # --- Spiegel: Gehaeuse schwarz, Spiegelglas, Arm ---
    for sg in (-1, 1):
        g = kugel((0, 0, 0), 1.0, segs=32, ringe=16, mi=A_LACK)
        for v in g.verts:
            x, y, z = v.co
            x = math.copysign(abs(x) ** 0.75, x) * (0.18 if x < 0 else 1.0)
            y = math.copysign(abs(y) ** 0.5, y)
            z = math.copysign(abs(z) ** 0.55, z) * (0.78 + 0.22 * (sg * y + 1) / 2)
            v.co = (x, y, z)
        bmesh.ops.scale(g, vec=(0.078, 0.112, 0.07), verts=g.verts)
        bmesh.ops.translate(g, vec=(1.07, sg * 1.06, 1.06), verts=g.verts)
        einfuegen(bm, g)
        einfuegen(bm, kugel((1.0545, sg * 1.063, 1.06), 1.0, segs=24, ringe=12, skala=(0.0025, 0.098, 0.06), mi=A_CHROM))
        einfuegen(bm, kasten((1.105, sg * 0.955, 1.02), (0.075, 0.08, 0.034), fase=0.012, mi=A_SCHWARZ))
        # --- Tuergriffe in den Griffmulden ---
        for xg in GRIFFE:
            loc, n = auf(SEITE(sg), xg, GRIFF_Z)
            einfuegen(bm, ausrichten(kasten((0, 0, 0), (0.016, 0.15, 0.022), fase=0.007, mi=A_CHROM), loc + n * 0.002, n))
        # --- Stern-Abzeichen auf den Vordertueren ---
        einfuegen(bm, stern_abzeichen(sg, 0.56, 0.68, 0.32, A_GOLD, A_ABZ))
    # --- Suchscheinwerfer an der linken A-Saeule (Fahrerseite) ---
    loc, n = auf(SEITE(1), 1.21, 1.10)
    kopf = loc + Vector((0.03, 0.105, 0.02))
    einfuegen(bm, rohr([loc - n * 0.01, loc + n * 0.06, kopf - Vector((0.02, 0.0, 0.0))], 0.011, segs=10, mi=A_CHROM))
    lampe = bmesh.new()
    einfuegen(lampe, zylinder((0.0, 0, 0), 0.056, 0.10, "X", segs=28, mi=A_CHROM))
    einfuegen(lampe, zylinder((0.055, 0, 0), 0.062, 0.016, "X", segs=28, mi=A_CHROM, deckel=False))
    einfuegen(lampe, zylinder((0.058, 0, 0), 0.052, 0.004, "X", segs=28, mi=A_SWGLAS))
    einfuegen(lampe, zylinder((0.052, 0, 0), 0.045, 0.004, "X", segs=28, mi=A_REFL))
    einfuegen(lampe, kugel((-0.05, 0, 0), 0.056, segs=20, ringe=10, skala=(0.5, 1, 1), mi=A_CHROM))
    bmesh.ops.translate(lampe, vec=kopf, verts=lampe.verts)
    einfuegen(bm, lampe)
    # --- Lichtbalken: links rot, rechts blau, in der Mitte klar mit weissen Arbeitslichtern und gelbem Warnlicht ---
    def dach(x, y):
        return BVH_ROH.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)))[0].z
    xb = -0.30
    zr = dach(xb, 0.0)
    einfuegen(bm, kasten((xb, 0.0, zr + 0.07), (0.32, 1.40, 0.04), fase=0.015, mi=A_TRIM))
    for sg in (-1, 1):
        for dx in (0.10, -0.10):
            zf = dach(xb + dx, sg * 0.60)
            einfuegen(bm, kasten((xb + dx, sg * 0.60, (zf + zr + 0.05) / 2), (0.06, 0.05, zr + 0.055 - zf), fase=0.008,
                                 mi=A_SCHWARZ))
        einfuegen(bm, kasten((xb, sg * 0.43, zr + 0.12), (0.30, 0.50, 0.065), fase=0.026,
                             mi=A_ROTKAPPE if sg > 0 else A_BLKAPPE))
        farbe = A_ROT if sg > 0 else A_BLAU
        for k in range(4):
            yk = sg * (0.24 + 0.11 * k)
            for dx, rx in ((0.103, 1), (-0.103, -1)):
                einfuegen(bm, led_modul((xb + dx, yk, zr + 0.118), (rx, 0, 0), 0.088, 3, farbe, A_REFL, A_TRIM))
        einfuegen(bm, led_modul((xb, sg * 0.672, zr + 0.118), (0, sg, 0), 0.12, 3, A_LED, A_REFL, A_TRIM))  # Seitenlicht
    einfuegen(bm, kasten((xb, 0.0, zr + 0.12), (0.30, 0.36, 0.065), fase=0.026, mi=A_KLAR))
    for yk in (-0.08, 0.08):
        einfuegen(bm, led_modul((xb + 0.103, yk, zr + 0.118), (1, 0, 0), 0.11, 4, A_LED, A_REFL, A_TRIM, hoehe=0.03))
    for yk in (-0.12, -0.04, 0.04, 0.12):
        einfuegen(bm, led_modul((xb - 0.103, yk, zr + 0.118), (-1, 0, 0), 0.065, 2, A_BLINK, A_REFL, A_TRIM,
                                hoehe=0.024))
    # --- Blitzer hinter der Heckscheibe (links rot, rechts blau) ---
    xd, zd = -1.075, Z_TOP(-1.075) - 0.075
    einfuegen(bm, kasten((xd, 0.0, zd), (0.05, 1.0, 0.035), fase=0.008, mi=A_TRIM))
    for sg in (-1, 1):
        for k in range(4):
            einfuegen(bm, led_modul((xd - 0.024, sg * (0.07 + 0.11 * k), zd), (-1, 0, 0), 0.085, 3,
                                    A_ROT if sg > 0 else A_BLAU, A_REFL, A_TRIM, hoehe=0.022))
    # --- Antennen auf dem Dach ---
    xa = -0.56                                         # zwischen Lichtbalken und Dachnummer
    for yy in (-0.32, 0.32):
        z0 = dach(xa, yy)
        einfuegen(bm, zylinder((xa, yy, z0 + 0.008), 0.016, 0.016, "Z", segs=12, mi=A_SCHWARZ))
        einfuegen(bm, zylinder((xa, yy, z0 + 0.17), 0.0032, 0.32, "Z", segs=6, mi=A_SCHWARZ))
    z0 = dach(xa, 0.0)
    einfuegen(bm, zylinder((xa, 0.0, z0 + 0.012), 0.045, 0.024, "Z", segs=20, mi=A_SCHWARZ, r2=0.035))
    # --- Scheibenwischer ---
    def auf_glas(x, y, ab):
        loc, nor = BVH_ROH.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)))[:2]
        return loc + nor * ab
    for y0, y1 in ((0.12, 0.70), (-0.48, 0.06)):
        einfuegen(bm, rohr([auf_glas(1.185 - 0.02 * t, y0 + (y1 - y0) * t, 0.012) for t in np.linspace(0, 1, 16)],
                           0.010, 0.006, segs=8, mi=A_SCHWARZ, eckig=3))
    anb = objekt("Anbauteile", bm, MATS_ANB, glatt=True, auto_glatt=35)
    teile.append(anb)
    # --- Beschriftung (Folie) ---
    for sg, rot in ((-1, R_RECHTS), (1, R_LINKS)):
        teile.append(schrift("POLICE", 0.18, M_FOLIE_S, rot, (-0.55, sg * 1.25, 0.66), "Schrift_Tuer", kar))
        teile.append(schrift("27", 0.13, M_WEISS, rot, (-2.02, sg * 1.25, 0.86), "Nummer_Seite", kar))
    # grosse flache Ziffern: etwas mehr Abstand, damit lange Flaechen nicht in die Dachwoelbung eintauchen
    teile.append(schrift("27", 0.46, M_FOLIE_S, R_DACH, (-0.80, 0.0, 1.8), "Nummer_Dach", kar, abstand=0.0035))
    teile.append(schrift("POLICE", 0.10, M_WEISS, R_HECK, (-2.9, 0.0, 0.858), "Schrift_Heck", kar))
    teile.append(innenraum())
    return teile

def polster(mitte, groesse, wulst=0.0, mulde=0.0, rot=None, mi=1, mi_wange=None, eck=0.3, segs=28, ringe=18):
    """Weich geformtes Teil (Polster, Kopfstuetze, Armlehne): abgerundeter Quader (Superellipsoid), oben mit
    Seitenwangen (wulst) und Mulde; Wangen optional in eigenem Material. Lokal: x Tiefe, y Breite, z Dicke."""
    a, b, c = groesse[0] / 2, groesse[1] / 2, groesse[2] / 2
    bm = kugel((0, 0, 0), 1.0, segs=segs, ringe=ringe, mi=mi)
    quer = {}
    for v in bm.verts:
        x, y, z = (math.copysign(abs(t) ** eck, t) for t in v.co)
        if z > 0:
            z += wulst * abs(y) ** 6 - mulde * (1 - y * y) * (1 - x * x) ** 2
        quer[v] = abs(y)
        v.co = (x * a, y * b, z * c)
    if mi_wange is not None:
        for f in bm.faces:
            if sum(quer[v] for v in f.verts) / len(f.verts) > 0.68:
                f.material_index = mi_wange
    M = Matrix.Translation(Vector(mitte)) @ (rot.to_4x4() if rot is not None else Matrix.Identity(4))
    bmesh.ops.transform(bm, matrix=M, verts=bm.verts)
    return bm

def profil_y(profil, y0, y1, n=24, mi=0):
    """Geschlossenes Profil (x, z) entlang Y extrudieren, mit Deckeln."""
    bm = bmesh.new()
    ringe = [[bm.verts.new((x, y, z)) for x, z in profil] for y in np.linspace(y0, y1, n)]
    m = len(profil)
    for r0, r1 in zip(ringe, ringe[1:]):
        for k in range(m):
            bm.faces.new((r0[k], r0[(k + 1) % m], r1[(k + 1) % m], r1[k])).material_index = mi
    for r in (ringe[0], ringe[-1][::-1]):
        bm.faces.new(r).material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm

def innenraum():
    """Innenraum, durch die Scheiben sichtbar: geformte Sitze, Armaturenbrett mit Instrumenten und Duesen,
    Lenkrad mit Airbag, Polizeitechnik (Funk, Sirenen-/Lichtsteuerung, Mikrofon mit Spiralkabel, Laptop),
    Innenspiegel, Sonnenblenden, Gurte, Trenngitter, harte Kunststoff-Rueckbank, Fussmatten, Tuerverkleidungen."""
    bm = bmesh.new()
    (I_KUNST, I_STOFF, I_GLANZ, I_GITTER, I_GLAS, I_SCHIRM, I_LEDER, I_CHROM, I_ROT, I_BLAU, I_GELB,
     I_WEISS) = range(12)
    # --- Armaturenbrett: gerundetes Profil ueber die ganze Breite ---
    profil = chaikin([(1.24, 0.985), (1.10, 0.985), (0.98, 0.975), (0.915, 0.952), (0.882, 0.925), (0.878, 0.86),
                      (0.90, 0.78), (0.95, 0.70), (1.05, 0.66), (1.22, 0.67), (1.27, 0.80), (1.27, 0.95)], 2)
    einfuegen(bm, profil_y(profil, -0.82, 0.82, n=30, mi=I_KUNST))
    for y in (-0.42, 0.42):                                             # Defroster-Schlitze
        einfuegen(bm, kasten((1.16, y, 0.986), (0.035, 0.42, 0.004), mi=I_GLANZ))
    # Instrumentenhutze und zwei Rundinstrumente vor dem Fahrer
    einfuegen(bm, polster((0.93, 0.37, 0.985), (0.16, 0.42, 0.09), eck=0.45, mi=I_KUNST))
    neig = Matrix.Rotation(math.radians(-18), 3, "Y")
    for dy in (-0.085, 0.085):
        c = Vector((0.892, 0.37 + dy, 0.925))
        einfuegen(bm, kasten(c, (0.004, 0.13, 0.13), rot=neig, fase=0.002, mi=I_GLANZ))
        ring = [c + neig @ Vector((-0.003, 0.055 * math.cos(w), 0.055 * math.sin(w))) for w in np.linspace(0, 2 * math.pi, 41)]
        einfuegen(bm, rohr(ring, 0.0028, segs=6, mi=I_CHROM, deckel=False, oben=tuple(neig @ Vector((1, 0, 0)))))
        for k in range(9):                                              # Skalenstriche
            w = math.radians(-135 + 270 * k / 8)
            einfuegen(bm, kasten(c + neig @ Vector((-0.003, 0.044 * math.sin(w), 0.044 * math.cos(w))),
                                 (0.002, 0.003, 0.01), rot=neig @ Matrix.Rotation(-w, 3, "X"), mi=I_WEISS))
        einfuegen(bm, kasten(c + neig @ Vector((-0.004, 0.012, 0.014)), (0.002, 0.003, 0.04),
                             rot=neig @ Matrix.Rotation(math.radians(-40), 3, "X"), mi=I_ROT))      # Zeiger
    # Mittelkonsole oben: Bildschirm, zwei eckige Duesen, Klimaregler; runde Duesen an den Enden
    einfuegen(bm, kasten((0.90, 0.0, 0.70), (0.06, 0.26, 0.30), fase=0.015, mi=I_KUNST))
    einfuegen(bm, kasten((0.872, 0.0, 0.875), (0.012, 0.24, 0.13), fase=0.004, rot=Matrix.Rotation(math.radians(-10), 3, "Y"), mi=I_GLANZ))
    for y in (-0.085, 0.085):
        einfuegen(bm, kasten((0.884, y, 0.785), (0.012, 0.075, 0.05), fase=0.004, mi=I_GLANZ))
        for k in range(4):
            einfuegen(bm, kasten((0.879, y, 0.768 + 0.011 * k), (0.004, 0.068, 0.0035), mi=I_KUNST))
    for y in (-0.05, 0.0, 0.05):
        einfuegen(bm, zylinder((0.865, y, 0.68), 0.015, 0.02, "X", segs=20, mi=I_KUNST))
        einfuegen(bm, zylinder((0.868, y, 0.68), 0.017, 0.006, "X", segs=20, mi=I_CHROM, deckel=False))
    for y in (-0.70, 0.70):
        c = Vector((0.892, y, 0.885))
        einfuegen(bm, zylinder(c, 0.036, 0.01, "X", segs=24, mi=I_GLANZ))
        ring = [c + Vector((-0.006, 0.037 * math.cos(w), 0.037 * math.sin(w))) for w in np.linspace(0, 2 * math.pi, 33)]
        einfuegen(bm, rohr(ring, 0.004, segs=6, mi=I_CHROM, deckel=False, oben=(1, 0, 0)))
        for k in range(5):
            einfuegen(bm, kasten((0.884, y, 0.861 + 0.012 * k), (0.004, 0.06, 0.003), mi=I_KUNST))
    einfuegen(bm, kasten((0.889, -0.45, 0.80), (0.004, 0.36, 0.004), mi=I_GLANZ))           # Handschuhfach-Fuge
    # --- Lenkrad mit Prallpolster, Lenksaeule und Hebeln ---
    lr = rohr([(0.0, 0.185 * math.cos(w), 0.185 * math.sin(w)) for w in np.linspace(0, 2 * math.pi, 49)], 0.018,
              segs=12, mi=I_LEDER, deckel=False, oben=(1, 0, 0))
    for w in (0.0, math.pi, math.pi * 3 / 2):
        einfuegen(lr, kasten((0.006, 0.105 * math.cos(w), 0.105 * math.sin(w)), (0.014, 0.15, 0.045),
                             rot=Matrix.Rotation(w, 3, "X"), fase=0.006, mi=I_KUNST))
    einfuegen(lr, polster((-0.012, 0, 0.0), (0.05, 0.17, 0.14), eck=0.4, rot=Matrix.Rotation(math.radians(-90), 3, "Y"), mi=I_KUNST))
    einfuegen(lr, zylinder((0.17, 0, 0), 0.042, 0.30, "X", segs=20, mi=I_KUNST, r2=0.05))
    for sy in (-1, 1):
        einfuegen(lr, rohr([(0.07, sy * 0.05, 0.0), (0.075, sy * 0.16, -0.01)], 0.006, segs=8, mi=I_KUNST))
    bmesh.ops.transform(lr, matrix=Matrix.Translation((0.80, 0.37, 0.96)) @ Matrix.Rotation(math.radians(-22), 4, "Y"),
                        verts=lr.verts)
    einfuegen(bm, lr)
    # --- Mittelkonsole mit Funk-Bedienteil, Sirenen-/Lichtsteuerung, Becherhaltern ---
    einfuegen(bm, kasten((0.38, 0.0, 0.44), (0.92, 0.24, 0.20), fase=0.03, mi=I_KUNST))
    kipp = Matrix.Rotation(math.radians(-28), 3, "Y")
    einfuegen(bm, kasten((0.70, 0.0, 0.575), (0.10, 0.20, 0.06), fase=0.006, rot=kipp, mi=I_KUNST))          # Funk
    funk = Vector((0.70, 0.0, 0.575))
    einfuegen(bm, kasten(funk + kipp @ Vector((0.0, 0.0, 0.031)), (0.04, 0.10, 0.002), rot=kipp, mi=I_SCHIRM))
    for k in range(6):
        einfuegen(bm, kasten(funk + kipp @ Vector((-0.033, -0.08 + 0.032 * k, 0.031)), (0.012, 0.018, 0.004),
                             rot=kipp, mi=I_GLANZ))
    c = Vector((0.40, 0.0, 0.575))
    einfuegen(bm, kasten(c, (0.13, 0.21, 0.06), fase=0.008, rot=kipp, mi=I_KUNST))                          # Sirene/Licht
    farben = [I_ROT, I_BLAU, I_GELB, I_WEISS, I_GLANZ, I_GLANZ]
    for reihe in range(2):
        for k in range(6):
            einfuegen(bm, kasten(c + kipp @ Vector((-0.03 + 0.045 * reihe, -0.075 + 0.03 * k, 0.031)), (0.022, 0.022, 0.006),
                                 fase=0.002, rot=kipp, mi=farben[(k + reihe) % 6] if reihe == 0 else I_GLANZ))
    for x in (0.08, 0.17):
        einfuegen(bm, zylinder((x, 0.0, 0.535), 0.038, 0.012, "Z", segs=24, mi=I_GLANZ, deckel=False))
    # Mikrofon am Armaturenbrett mit Spiralkabel zum Funkgeraet
    mik = Vector((0.875, 0.16, 0.64))
    einfuegen(bm, polster(mik, (0.035, 0.06, 0.085), eck=0.4, rot=Matrix.Rotation(math.radians(90), 3, "Y"), mi=I_KUNST))
    einfuegen(bm, kasten(mik + Vector((0.015, 0, 0.05)), (0.012, 0.03, 0.03), fase=0.003, mi=I_CHROM))
    a, b = mik + Vector((0.0, 0.0, -0.045)), Vector((0.66, 0.06, 0.56))
    spirale = []
    for t in np.linspace(0, 1, 260):
        p = a.lerp(b, t) + Vector((0, 0, -0.10 * math.sin(math.pi * t)))
        q = (b - a).normalized()
        e1 = q.cross(Vector((0, 0, 1))).normalized()
        e2 = q.cross(e1)
        w = 2 * math.pi * 22 * t
        spirale.append(p + (e1 * math.cos(w) + e2 * math.sin(w)) * 0.006)
    einfuegen(bm, rohr(spirale, 0.0016, segs=5, mi=I_KUNST))
    # Laptop (robustes Geraet) auf Schwenkhalter, zum Fahrer gedreht, mit Tastatur
    lap = bmesh.new()
    einfuegen(lap, kasten((0, 0, 0), (0.24, 0.33, 0.025), fase=0.006, mi=I_KUNST))
    for r_ in range(5):
        for k in range(13):
            einfuegen(lap, kasten((-0.085 + 0.033 * r_, -0.144 + 0.024 * k, 0.0135), (0.022, 0.018, 0.003), mi=I_GLANZ))
    deckel = Matrix.Rotation(math.radians(15), 3, "Y")
    scharnier = Vector((0.12, 0, 0.0125))
    einfuegen(lap, kasten(scharnier + deckel @ Vector((0, 0, 0.11)), (0.014, 0.33, 0.22), fase=0.006, rot=deckel, mi=I_KUNST))
    einfuegen(lap, kasten(scharnier + deckel @ Vector((-0.0075, 0, 0.11)), (0.002, 0.29, 0.18), rot=deckel, mi=I_SCHIRM))
    bmesh.ops.transform(lap, matrix=Matrix.Translation((0.58, 0.08, 0.80)) @ Matrix.Rotation(math.radians(-29), 4, "Z"),
                        verts=lap.verts)
    einfuegen(bm, lap)
    einfuegen(bm, rohr([(0.52, 0.0, 0.54), (0.56, 0.03, 0.70), (0.58, 0.07, 0.785)], 0.013, segs=10, mi=I_GITTER))
    einfuegen(bm, kasten((0.58, 0.08, 0.785), (0.12, 0.12, 0.012), mi=I_GITTER))
    # --- Vordersitze: Sitzflaeche und Lehne mit Seitenwangen (Mitte Stoff, Wangen Kunstleder), Kopfstuetzen,
    #     Sitzunterbau, Gurtschloss, Gurt an der B-Saeule ---
    for yy in (0.40, -0.40):
        sg = 1 if yy > 0 else -1
        einfuegen(bm, kasten((0.20, yy, 0.33), (0.44, 0.40, 0.16), fase=0.02, mi=I_KUNST))
        einfuegen(bm, polster((0.22, yy, 0.47), (0.52, 0.50, 0.13), wulst=0.6, mulde=0.22,
                              rot=Matrix.Rotation(math.radians(-5), 3, "Y"), mi=I_STOFF, mi_wange=I_LEDER))
        lehne = Matrix.Rotation(math.radians(76), 3, "Y")
        einfuegen(bm, polster((-0.04, yy, 0.83), (0.62, 0.50, 0.13), wulst=0.7, mulde=0.15, rot=lehne,
                              mi=I_STOFF, mi_wange=I_LEDER))
        einfuegen(bm, polster((-0.10, yy, 1.21), (0.10, 0.27, 0.17), eck=0.38, mi=I_LEDER))
        for dy in (-0.07, 0.07):
            einfuegen(bm, rohr([(-0.09, yy + dy, 1.13), (-0.075, yy + dy, 1.07)], 0.0055, segs=8, mi=I_CHROM))
        einfuegen(bm, kasten((0.02, yy - sg * 0.27, 0.53), (0.05, 0.03, 0.03), fase=0.006, mi=I_KUNST))   # Gurtschloss
        einfuegen(bm, kasten((0.02, yy - sg * 0.27, 0.552), (0.035, 0.022, 0.012), mi=I_CHROM))
        gurt = [(-0.15, sg * 0.79, 1.27), (-0.16, sg * 0.80, 0.95), (-0.17, sg * 0.81, 0.40)]
        einfuegen(bm, rohr(gurt, 0.0015, 0.024, segs=6, mi=I_KUNST, oben=(1, 0, 0), eckig=4))
    # Fussmatten
    for x, l in ((0.62, 0.42), (-0.62, 0.30)):
        for yy in (0.41, -0.41):
            einfuegen(bm, kasten((x, yy, 0.226), (l, 0.40, 0.012), fase=0.004, mi=I_KUNST))
    # --- Trenngitter: unten Stahlblech, oben Scheibe mit Schiebefenster, Rahmen aus Rohr ---
    xp = -0.30
    einfuegen(bm, kasten((xp, 0.0, 0.70), (0.012, 1.46, 0.50), fase=0.004, mi=I_GITTER))
    einfuegen(bm, kasten((xp, 0.0, 1.17), (0.008, 1.40, 0.42), mi=I_GLAS))
    rahmen = [(xp, -0.73, 0.45), (xp, -0.73, 1.36), (xp, 0.73, 1.36), (xp, 0.73, 0.45)]
    einfuegen(bm, rohr(rahmen, 0.014, segs=8, mi=I_GITTER))
    einfuegen(bm, rohr([(xp, -0.73, 0.95), (xp, 0.73, 0.95)], 0.012, segs=8, mi=I_GITTER))
    fenster = [(xp - 0.008, y, z) for y, z in ((-0.22, 1.02), (0.22, 1.02), (0.22, 1.28), (-0.22, 1.28), (-0.22, 1.02))]
    einfuegen(bm, rohr(fenster, 0.006, segs=6, mi=I_GITTER, deckel=False, oben=(1, 0, 0)))
    # --- Rueckbank aus hartem Kunststoff (zwei Sitzmulden), Lehne, Boden ---
    for yy in (0.36, -0.36):
        einfuegen(bm, polster((-0.86, yy, 0.46), (0.52, 0.68, 0.11), wulst=0.35, mulde=0.55, eck=0.25, mi=I_LEDER))
    einfuegen(bm, polster((-1.12, 0.0, 0.84), (0.60, 1.44, 0.10), mulde=0.2, eck=0.25,
                          rot=Matrix.Rotation(math.radians(72), 3, "Y"), mi=I_LEDER))
    einfuegen(bm, kasten((-0.86, 0.0, 0.33), (0.50, 1.44, 0.16), fase=0.02, mi=I_KUNST))
    for yy in (-0.50, 0.0, 0.50):
        einfuegen(bm, kasten((-1.20, yy, 1.19), (0.08, 0.24, 0.14), fase=0.035, mi=I_LEDER))
    einfuegen(bm, kasten((0.0, 0.0, 0.20), (2.60, 1.66, 0.04), mi=I_KUNST))                        # Boden
    einfuegen(bm, kasten((-1.45, 0.0, 1.03), (0.56, 1.42, 0.02), mi=I_KUNST))                      # Hutablage
    # --- Tuerverkleidungen mit Armlehne, Griff, Lautsprecher, Fensterheberschaltern ---
    for sg in (-1, 1):
        einfuegen(bm, kasten((0.0, sg * 0.86, 0.72), (2.30, 0.05, 0.42), fase=0.02, mi=I_KUNST))
        for xt in (0.52, -0.62):
            einfuegen(bm, polster((xt, sg * 0.82, 0.70), (0.38, 0.06, 0.045), eck=0.35, mi=I_LEDER))
            einfuegen(bm, kasten((xt + 0.22, sg * 0.832, 0.81), (0.07, 0.012, 0.022), fase=0.004, mi=I_CHROM))
            einfuegen(bm, zylinder((xt - 0.05, sg * 0.833, 0.46), 0.065, 0.01, "Y", segs=24, mi=I_GLANZ))
            for k in range(2):
                einfuegen(bm, kasten((xt + 0.06 + 0.03 * k, sg * 0.82, 0.726), (0.018, 0.012, 0.006), mi=I_GLANZ))
    # --- Dachhimmel mit Innenleuchte, Sonnenblenden, Innenspiegel ---
    einfuegen(bm, kasten((-0.36, 0.0, 1.395), (1.26, 1.32, 0.02), fase=0.01, mi=I_STOFF))
    einfuegen(bm, kasten((-0.36, 0.0, 1.383), (0.10, 0.22, 0.008), fase=0.003, mi=I_WEISS))
    for yy in (0.38, -0.38):
        einfuegen(bm, polster((0.33, yy, 1.375), (0.14, 0.36, 0.022), eck=0.25,
                              rot=Matrix.Rotation(math.radians(-14), 3, "Y"), mi=I_STOFF))
    einfuegen(bm, rohr([(0.33, 0.0, 1.43), (0.37, 0.0, 1.37)], 0.007, segs=8, mi=I_KUNST))
    einfuegen(bm, polster((0.38, 0.0, 1.355), (0.035, 0.26, 0.075), eck=0.35, mi=I_KUNST))
    einfuegen(bm, kasten((0.362, 0.0, 1.355), (0.002, 0.23, 0.058), mi=I_CHROM))
    return objekt("Innenraum", bm, [M_INNEN, M_INNEN_HELL, M_TRIM, M_GITTER, M_GLAS, M_BILDSCHIRM, M_INNEN_LEDER,
                                    M_CHROM, M_ROTLICHT, M_BLAULICHT, M_BLINKER, M_INSTRUMENT], glatt=True,
                  auto_glatt=40)

# ---------------- Raeder: Reifen mit Profil und Flankenbeschriftung, schwarze 18-Zoll-Stahlfelge mit Sicken,
# Chromkappe und Radmuttern, Ventil, innenbelueftete Bremsscheibe ----------------
def drehkoerper(bm, profil, segs, mi, uv=None, kacheln=8, geschlossen=False):
    """Profil [(r, a[, v])] um die Radachse (lokal Y) drehen. Mit uv-Layer: u laeuft um den Umfang
    (kacheln je Umdrehung), v kommt aus dem Profil. geschlossen: letzter Profilpunkt wird mit dem ersten verbunden."""
    ringe = []
    for i in range(segs):
        w = 2 * math.pi * i / segs
        c, s = math.cos(w), math.sin(w)
        ringe.append([bm.verts.new((p[0] * c, p[1], p[0] * s)) for p in profil])
    faces = []
    n = len(profil)
    for i in range(segs):
        r0, r1 = ringe[i], ringe[(i + 1) % segs]
        for j in range(n if geschlossen else n - 1):
            j1 = (j + 1) % n
            f = bm.faces.new((r0[j], r1[j], r1[j1], r0[j1]))
            f.material_index = mi
            if uv is not None:
                u0, u1 = i / segs * kacheln, (i + 1) / segs * kacheln
                v0, v1 = profil[j][2], profil[j1][2]
                for loop, (uu, vv) in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
                    loop[uv].uv = (uu, vv)
            faces.append(f)
    return faces

def reifen_profil():
    """Querschnitt von der inneren zur aeusseren Wulst: (r, a, v); vier Laengsrillen als Geometrie.
    Die Form ist auf Felgen- und Reifenradius bezogen und passt so zu jeder Reifengroesse."""
    r0 = FELGE_R - 0.003
    h = RAD_R - r0
    k = (RAD_B / 2) / 0.1185
    flanke = [(0.0, -0.103, 0.00), (0.092, -0.112, 0.03), (0.266, -0.1175, 0.08), (0.495, -0.1185, 0.14),
              (0.697, -0.116, 0.20), (0.844, -0.110, 0.25), (0.936, -0.100, 0.29), (0.982, -0.089, 0.32)]
    p = [(r0 + h * t, a * k, v) for t, a, v in flanke]
    lauf = [(RAD_R, -0.080 * k)]
    for c in (-0.050, -0.017, 0.017, 0.050):
        c *= k
        lauf += [(RAD_R, c - 0.0055), (RAD_R - 0.008, c - 0.004), (RAD_R - 0.008, c + 0.004), (RAD_R, c + 0.0055)]
    lauf.append((RAD_R, 0.080 * k))
    p += [(r, a, 0.34 + (a + 0.080 * k) / (0.160 * k) * 0.32) for (r, a) in lauf]
    p += [(r0 + h * t, -a * k, 1.0 - v) for t, a, v in reversed(flanke)]
    return p

def ausrichten_ref(faces, ref_r, ref_a, nach_aussen=True):
    """Offene Drehflaechen ausrichten: Normalen weg vom (bzw. hin zum) Referenzring (Radius ref_r bei a = ref_a)."""
    for f in faces:
        c = f.calc_center_median()
        r = math.hypot(c.x, c.z) or 1.0
        ref = Vector((ref_r * c.x / r, ref_a, ref_r * c.z / r))
        if ((c - ref).dot(f.normal) < 0) == nach_aussen:
            f.normal_flip()

SCHUESSEL = None
def stahlschuessel():
    """Gepresste Felgenschuessel (4 mm Blech) als geschlossener Koerper: schraeger Aussenring mit sechs ovalen
    Lueftungsloechern (Boolesche Differenz), erhabene Versteifungssicke, ebene Anlageflaeche fuer die Radmuttern,
    Mittelloch. Einmal gebaut und fuer alle Raeder wiederverwendet."""
    global SCHUESSEL
    if SCHUESSEL is None:
        bm = bmesh.new()
        aussen = [(0.214, 0.090), (0.204, 0.0865), (0.188, 0.0815), (0.170, 0.0765), (0.150, 0.0720), (0.134, 0.0695),
                  (0.126, 0.0715), (0.119, 0.0758), (0.112, 0.0775), (0.105, 0.0760), (0.098, 0.0700), (0.090, 0.0662),
                  (0.080, 0.0655), (0.058, 0.0652), (0.047, 0.0640), (0.041, 0.0605)]
        schnitt_ = aussen + [(r, a - 0.004) for r, a in reversed(aussen)]
        drehkoerper(bm, schnitt_, 96, 0, geschlossen=True)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        ob = objekt("_Schuessel", bm, [M_FELGE])
        bm = bmesh.new()
        for k in range(6):
            w = 2 * math.pi * k / 6 + math.pi / 6
            loch = zylinder((0, 0, 0), 1.0, 0.08, "Y", segs=28)
            bmesh.ops.scale(loch, vec=(0.020, 1.0, 0.031), verts=loch.verts)
            bmesh.ops.rotate(loch, cent=(0, 0, 0), matrix=Matrix.Rotation(-w, 3, "Y"), verts=loch.verts)
            bmesh.ops.translate(loch, vec=(0.153 * math.cos(w), 0.07, 0.153 * math.sin(w)), verts=loch.verts)
            einfuegen(bm, loch)
        cut = objekt("_Loecher", bm, [M_FELGE])
        mod = ob.modifiers.new("Loecher", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = cut
        anwenden(ob, mod)
        bpy.data.objects.remove(cut)
        SCHUESSEL = ob.data.copy()
        bpy.data.objects.remove(ob)
    bm = bmesh.new()
    bm.from_mesh(SCHUESSEL)
    for f in bm.faces:
        f.material_index = 1
    return bm

def rad_bmesh():
    """Ein Rad mit Aussenseite nach +Y (lokal), Mitte im Ursprung. Materialien: 0 Reifen, 1 Felge, 2 Felge innen,
    3 Chrom, 4 Bremse, 5 Gummi (Ventil)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    reifen = drehkoerper(bm, reifen_profil(), 96, 0, uv=uv, kacheln=1)
    bett = drehkoerper(bm, [(0.240, -0.104), (0.240, -0.097), (0.228, -0.095), (0.226, -0.080), (0.203, -0.072),
                            (0.199, -0.030), (0.199, 0.030), (0.212, 0.045), (0.226, 0.055), (0.228, 0.092)], 72, 2)
    horn = drehkoerper(bm, [(0.228, 0.092), (0.241, 0.096), (0.244, 0.103), (0.240, 0.1085), (0.229, 0.1085),
                            (0.216, 0.101), (0.211, 0.088)], 72, 1)
    einfuegen(bm, stahlschuessel())
    # sechs Radmuttern (Kegelsitz, Sechskant, gewoelbte Kappe), verchromte Mittelkappe mit schwarzem Ring
    for k in range(6):
        w = 2 * math.pi * k / 6
        c, s_ = 0.068 * math.cos(w), 0.068 * math.sin(w)
        einfuegen(bm, zylinder((c, 0.0665, s_), 0.0135, 0.004, "Y", segs=16, mi=3, r2=0.0108))
        einfuegen(bm, zylinder((c, 0.0745, s_), 0.0108, 0.012, "Y", segs=6, mi=3))
        einfuegen(bm, kugel((c, 0.0805, s_), 0.0094, segs=16, ringe=8, skala=(1, 0.55, 1), mi=3))
    einfuegen(bm, kugel((0, 0.060, 0), 0.054, segs=40, ringe=14, skala=(1, 0.32, 1), mi=3))
    ring = [(0.036 * math.cos(w), 0.0748, 0.036 * math.sin(w)) for w in np.linspace(0, 2 * math.pi, 41)]
    einfuegen(bm, rohr(ring, 0.0022, segs=6, mi=2, deckel=False, oben=(0, 1, 0)))
    # Ventil am Felgenrand
    wv = math.radians(30)
    fuss = Vector((0.207 * math.cos(wv), 0.062, 0.207 * math.sin(wv)))
    spitze = Vector((0.199 * math.cos(wv), 0.088, 0.199 * math.sin(wv)))
    einfuegen(bm, rohr([fuss, spitze], 0.0042, segs=10, mi=5))
    einfuegen(bm, rohr([spitze, spitze + (spitze - fuss).normalized() * 0.009], 0.0045, segs=10, mi=3))
    # innenbelueftete Bremsscheibe: zwei Reibringe mit radialen Kuehlrippen, Topf (rund, darf sich mitdrehen;
    # einen Bremssattel gibt es nicht, er wuerde mitdrehen)
    for a0, a1 in ((-0.012, -0.003), (-0.031, -0.022)):
        drehkoerper(bm, [(0.095, a0), (0.172, a0), (0.172, a1), (0.095, a1)], 72, 4, geschlossen=True)
    for k in range(36):
        w = 2 * math.pi * (k + 0.5) / 36
        einfuegen(bm, kasten((0.134 * math.cos(w), -0.0170, 0.134 * math.sin(w)), (0.074, 0.010, 0.0055),
                             rot=Matrix.Rotation(-w, 3, "Y"), mi=4))
    einfuegen(bm, zylinder((0, 0.004, 0), 0.092, 0.036, "Y", segs=40, mi=2))
    bm.normal_update()
    offen = set(reifen) | set(bett) | set(horn)
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f not in offen])
    ausrichten_ref(reifen, FELGE_R + 0.47 * (RAD_R - FELGE_R), 0.0, nach_aussen=True)
    ausrichten_ref(bett, 0.199, 0.0, nach_aussen=False)
    ausrichten_ref(horn, 0.226, 0.098, nach_aussen=True)
    bm.normal_update()
    return bm

def raeder():
    obs = {}
    for name, (x, y) in RAEDER.items():
        bm = rad_bmesh()
        if y < 0:
            bmesh.ops.scale(bm, vec=Vector((1, -1, 1)), verts=bm.verts)
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
            uv = bm.loops.layers.uv["UVMap"]
            for f in bm.faces:                         # Flankenschrift bleibt auf der rechten Seite lesbar
                if f.material_index == 0:
                    for l in f.loops:
                        l[uv].uv.x = 1.0 - l[uv].uv.x
        bmesh.ops.translate(bm, vec=Vector((x, y, RAD_R)), verts=bm.verts)
        obs[name] = objekt("Rad_" + name, bm, [M_GUMMI, M_FELGE, M_FELGE_DUNKEL, M_CHROM, M_BREMSE, M_SCHWARZ],
                           glatt=True, auto_glatt=40)
    return obs

# ---------------- Zusammenbauen und UV-Karten ----------------
log("Karosserie ...")
KAR = karosserie()
log("Ausschnitte und Fugen ...")
SCHNEIDER, FUGEN = ausschnitte(KAR)
schneiden(KAR, SCHNEIDER, FUGEN)
log("Details ...")
TEILE = details(KAR)
log("Raeder ...")
RAEDER_OB = raeder()
ALLE = [KAR] + TEILE + list(RAEDER_OB.values())

# Entartete Flaechen und Kanten entfernen (z. B. wo abgerundete Kanten duenner Kaesten aufeinandertreffen):
# unsichtbar, aber unsauber fuer ein Spiel-Asset
for ob in ALLE:
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    gesehen, doppelt = set(), []                    # Flaechen mit genau denselben Ecken nur einmal behalten
    for f in bm.faces:
        k = frozenset(f.verts)
        if k in gesehen:
            doppelt.append(f)
        gesehen.add(k)
    bmesh.ops.delete(bm, geom=doppelt, context="FACES_ONLY")
    bm.to_mesh(ob.data)
    bm.free()

# Hilfswerte je Ecke fuer das Schmutz-Backen (werden vor dem Export wieder entfernt):
# teil 0 = aussen, 1 = Rad, 2 = Innenraum; rad_r = Abstand zur Radachse, rad_a = Abstand zur Radmitte nach aussen
def eckwerte(ob, name, werte):
    a = ob.data.attributes.new(name, "FLOAT", "POINT")
    a.data.foreach_set("value", werte)

for ob in ALLE:
    n = len(ob.data.vertices)
    teil = 1.0 if ob in RAEDER_OB.values() else (2.0 if ob.name.startswith("Innenraum") else 0.0)
    eckwerte(ob, "teil", [teil] * n)
    if teil == 1.0:
        x0 = XV if ob.name.endswith(("fl", "fr")) else XH
        sy = 1.0 if ob.name.endswith(("fl", "rl")) else -1.0
        eckwerte(ob, "rad_r", [math.hypot(v.co.x - x0, v.co.z - RAD_R) for v in ob.data.vertices])
        eckwerte(ob, "rad_a", [sy * v.co.y - YR for v in ob.data.vertices])
    else:
        eckwerte(ob, "rad_r", [0.0] * n)
        eckwerte(ob, "rad_a", [0.0] * n)

# UV-Karten: "UVMap" ist ein gemeinsamer Atlas fuer alles ausser den Reifen (die haben eine eigene Abwicklung fuer
# die Profiltextur). Smart UV Project schneidet die Inseln, danach bekommt der Innenraum (nur durch die Scheiben zu
# sehen) halbe Aufloesung und alles wird neu gepackt. "UV_Flakes" ist eine Wuerfelprojektion in Metern fuer
# kachelnde Lacktexturen (Flakes, Kratzer).
log("UV-Karten ...")
bpy.context.tool_settings.mesh_select_mode = (False, False, True)
for ob in ALLE:
    me = ob.data
    if "UVMap" not in me.uv_layers:
        me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        p.select = me.materials[p.material_index].name != "Reifen"
bpy.ops.object.select_all(action="DESELECT")
for ob in ALLE:
    ob.select_set(True)
bpy.context.view_layer.objects.active = KAR
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.002, scale_to_bounds=False)
bpy.ops.object.mode_set(mode="OBJECT")
def inseln_skalieren(ob, faktor):
    """UV-Inseln um ihre Mitte skalieren. faktor(ob, Flaeche) liefert den Wunsch je Flaeche; Inseln werden dort
    getrennt, wo sich der Wunsch aendert (z. B. Scheibe und Einfassung), damit jede Insel einheitlich ist."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lay = bm.loops.layers.uv["UVMap"]
    bm.faces.ensure_lookup_table()
    wunsch = [faktor(ob, f) for f in bm.faces]
    eltern = list(range(len(bm.faces)))
    def wurzel(i):
        while eltern[i] != i:
            eltern[i] = eltern[eltern[i]]
            i = eltern[i]
        return i
    def uv_an(f, v):
        for l in f.loops:
            if l.vert is v:
                return l[lay].uv
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        if wunsch[f1.index] == wunsch[f2.index] and all((uv_an(f1, v) - uv_an(f2, v)).length < 1e-6 for v in e.verts):
            a, b = wurzel(f1.index), wurzel(f2.index)
            if a != b:
                eltern[a] = b
    inseln = {}
    for f in bm.faces:
        inseln.setdefault(wurzel(f.index), []).append(f)
    for fl in inseln.values():
        k = wunsch[fl[0].index]
        if k == 1.0:
            continue
        uvs = [l[lay] for f in fl for l in f.loops]
        mitte = sum((u.uv for u in uvs), Vector((0, 0))) / len(uvs)
        for u in uvs:
            u.uv = mitte + (u.uv - mitte) * k
    bm.to_mesh(ob.data)
    bm.free()

def uv_wunsch(ob, f):
    """Texturaufloesung je Flaeche: Innenraum, Glas (ohne Textur) und Unterboden brauchen wenig."""
    m = ob.data.materials[f.material_index]
    if m.name == "Reifen":
        return 1.0
    b = m.node_tree.nodes.get("Principled BSDF")
    if b is not None and b.inputs["Transmission Weight"].default_value >= 0.5:
        return 0.2
    if ob.name.startswith("Innenraum"):
        return 0.35
    if f.normal.z < -0.6 and f.calc_center_median().z < 0.45:
        return 0.3
    return 1.0

t0 = time.time()
for ob in ALLE:
    inseln_skalieren(ob, uv_wunsch)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.uv.select_all(action="SELECT")
bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method="FRACTION", margin=0.0008, shape_method="CONCAVE")
bpy.ops.object.mode_set(mode="OBJECT")
log(f"  Inseln skaliert und gepackt ({time.time() - t0:.0f} s)")

def texeldichte():
    """Atlas-Texel je Meter fuer die volle Aufloesung (sichtbare Aussenflaechen) bei 4096 Pixeln."""
    uv_flaeche = flaeche = 0.0
    for ob in ALLE:
        if ob.name.startswith("Innenraum"):
            continue
        me = ob.data
        uv = me.uv_layers["UVMap"].data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        p_bm = bm.faces
        for p in me.polygons:
            if uv_wunsch(ob, p_bm[p.index]) != 1.0 or me.materials[p.material_index].name == "Reifen":
                continue
            pts = [uv[i].uv for i in p.loop_indices]
            uv_flaeche += abs(sum(pts[i].x * pts[i - 1].y - pts[i - 1].x * pts[i].y for i in range(len(pts)))) / 2
            flaeche += p.area
        bm.free()
    return 4096 * math.sqrt(uv_flaeche / max(flaeche, 1e-9))

TEXEL_JE_M = texeldichte()
log(f"Atlas: {TEXEL_JE_M:.0f} Texel je Meter bei 4096 px ({1000 / TEXEL_JE_M:.2f} mm je Texel)")

for ob in ALLE:
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lay = bm.loops.layers.uv.new("UV_Flakes")
    for f in bm.faces:
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        a, b = ((1, 2), (0, 2), (0, 1))[ax]
        for l in f.loops:
            co = ob.matrix_world @ l.vert.co
            l[lay].uv = (co[a], co[b])
    bm.to_mesh(ob.data)
    bm.free()

def gruppe(ob, name):
    vg = ob.vertex_groups.new(name=name)
    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")

for ob in [KAR] + TEILE:
    gruppe(ob, "root")
for name, ob in RAEDER_OB.items():
    gruppe(ob, name)

bpy.ops.object.select_all(action="DESELECT")
for ob in ALLE:
    ob.select_set(True)
bpy.context.view_layer.objects.active = KAR
bpy.ops.object.join()
AUTO = bpy.context.view_layer.objects.active
AUTO.name = AUTO.data.name = "SK_" + NAME

# ---------------- Gebrauchsspuren: Schmutz, Staub, Regenstreifen, Steinschlaege, Kantenabrieb ----------------
# Cycles backt Masken in den gemeinsamen UV-Atlas ("UVMap"). Daraus entstehen drei Texturen, die alle Materialien
# des Autos teilen (ausser Glas und Reifen):
#   T_<NAME>_BaseColor  Farbe mit Schmutz und Abrieb (sRGB)
#   T_<NAME>_ORM        R = Umgebungsverdeckung, G = Rauheit, B = Metall (linear)
#   T_<NAME>_Klarlack   Klarlack-Staerke: dort, wo Schmutz liegt, glaenzt der Lack nicht mehr
# Bilder und Export verwenden dieselben Texturen; was gerendert wird, steckt also auch in FBX und GLB.
ATLAS = int(os.environ.get("ATLAS", "4096"))

# Je Material: (Schmutz-Anteil, Abrieb-Anteil, Abriebfarbe, Metall im Abrieb[, Schmutzfarbe]).
# Nicht genannte: (0.8, 0.25, heller, 0)
SCHMUTZ_REGELN = {
    "Lack_Schwarz": (1.0, 0.3, "#5d5f62", 0.0), "Lack_Weiss": (1.0, 0.3, "#5d5f62", 0.0),
    "Kunststoff_Schwarz": (1.0, 0.2, "#3c3d3e", 0.0), "Hochglanz_Schwarz": (0.6, 0.15, "#3a3b3c", 0.0),
    "Spalt": (0.0, 0.0, None, 0.0), "Chrom": (0.25, 0.0, None, 1.0), "Scheinwerfer_Innen": (0.05, 0.0, None, 0.0),
    "Reflektor": (0.05, 0.0, None, 1.0), "Tagfahrlicht": (0.1, 0.0, None, 0.0), "Ruecklicht_LED": (0.1, 0.0, None, 0.0),
    "Blaulicht": (0.15, 0.0, None, 0.0), "Rotlicht": (0.15, 0.0, None, 0.0), "Blinker": (0.15, 0.0, None, 0.0),
    "Folie_Schwarz": (1.0, 0.6, "#8d8e8f", 0.0), "Reflexfolie_Weiss": (1.0, 0.6, "#5d5f62", 0.0),
    "Abzeichen_Gold": (0.6, 0.3, "#8a6a1e", 1.0), "Abzeichen_Blau": (0.6, 0.3, "#c9a43a", 1.0),
    "Rammschutz": (1.0, 1.0, "#8b8e91", 1.0), "Felge_Schwarz": (1.0, 0.7, "#7c7f82", 1.0, "bremse"),
    "Felge_Innen": (1.0, 0.4, "#6d7073", 1.0, "bremse"), "Bremse": (1.0, 0.0, None, 1.0, "bremse"),
    "Innenraum": (0.25, 0.3, "#3a3b3d", 0.0), "Innenraum_Stoff": (0.2, 0.0, None, 0.0),
    "Kennzeichen": (0.7, 0.4, "#9a9c9e", 1.0), "Kennzeichen_Schrift": (0.7, 0.0, None, 0.0),
    "Bildschirm": (0.1, 0.0, None, 0.0), "Trenngitter": (0.6, 0.5, "#6a6d70", 1.0),
    "Ruecklicht_Reflektor": (0.0, 0.0, None, 1.0), "Blinker_Reflektor": (0.0, 0.0, None, 1.0),
    "Innenraum_Kunstleder": (0.2, 0.2, "#2c2d2f", 0.0), "Instrumente_Weiss": (0.1, 0.0, None, 0.0),
    "Seitenleuchte_Gelb": (0.5, 0.0, None, 0.0), "Seitenleuchte_Rot": (0.5, 0.0, None, 0.0),
}
SCHMUTZ_FARBEN = {
    "dreck": hexf("#4b4137"),      # Strassenschmutz, braun
    "dreck_grau": hexf("#55524d"), # Strassenschmutz, grau
    "staub": hexf("#9b9384"),      # heller Staub
    "streifen": hexf("#3b3732"),   # Regenstreifen
    "bremse": hexf("#261f1a"),     # Bremsstaub
    "stein": hexf("#8f8d88"),      # Steinschlag: Grundierung
}

def atlas_material(teil):
    """True, wenn das Material Texturen aus dem Atlas bekommt (Glas und Reifen nicht)."""
    if teil.name == "Reifen":
        return False
    b = teil.node_tree.nodes.get("Principled BSDF")
    return b is not None and b.inputs["Transmission Weight"].default_value < 0.5

def back_material(name, farbe_von, bild_ziel):
    """Material nur fuer das Backen: Emission mit der berechneten Farbe, Ziel ist das aktive Bild."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    aus = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(em.outputs[0], aus.inputs["Surface"])
    if farbe_von is not None:
        nt.links.new(farbe_von(Knoten(nt)), em.inputs["Color"])
    else:
        em.inputs["Color"].default_value = (0, 0, 0, 1)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bild_ziel
    nt.nodes.active = tex
    return m

def maske_id(K):
    v = K.m("DIVIDE", K.m("ADD", K.attribut("mat_id"), 1.0), 255.0)
    return K.vektor(v, v, v)

def maske_schmutz(K):
    """R = Strassenschmutz, G = Staub, B = Regenstreifen."""
    P, N = K.geometrie()
    x, y, z = K.trenne(P)
    nx, ny, nz = K.trenne(N)
    teil = K.attribut("teil")
    aussen = K.m("LESS_THAN", teil, 0.5)
    innen = K.m("GREATER_THAN", teil, 1.5)
    rad = K.m("SUBTRACT", K.m("SUBTRACT", 1.0, aussen), innen)
    fleck = K.rauschen(P, 2.6, detail=8, rau=0.6)
    fleck_fein = K.rauschen(P, 9.0, detail=6, rau=0.6)
    gischt = K.rauschen(K.v("MULTIPLY", P, (1.0, 9.0, 9.0)), 1.0, detail=6, rau=0.6)
    seite = K.glatt(K.m("ABSOLUTE", ny), 0.3, 0.7)
    # aussen: unten am meisten, um und hinter den Radlaeufen, am Heck (Sog), vorn unten, Unterboden
    teile = [K.mul(K.glatt(z, 0.50, 0.12), 0.45), K.mul(K.glatt(z, 0.30, 0.20), 0.65)]
    for a in (XV, XH):
        dx = K.m("SUBTRACT", x, a)
        dz = K.m("SUBTRACT", z, RAD_R)
        d = K.m("SQRT", K.add(K.mul(dx, dx), K.mul(dz, dz)))
        bogen = K.mul(K.glatt(d, BOGEN_R + 0.13, BOGEN_R + 0.02), K.add(0.35, K.mul(0.65, K.glatt(z, 0.75, 0.35))))
        t = K.m("DIVIDE", K.m("ADD", dx, 0.5), 0.42)
        hinter = K.mul(K.m("EXPONENT", K.mul(t, t, -1.0)), K.glatt(z, 0.62, 0.20), seite, 0.6)
        teile += [bogen, hinter]
    teile.append(K.mul(K.glatt(x, -2.15, -2.55), K.glatt(z, 0.80, 0.35), K.glatt(nx, -0.1, -0.6), 0.45))
    teile.append(K.mul(K.glatt(x, 2.25, 2.62), K.glatt(z, 0.55, 0.22), 0.35))
    teile.append(K.glatt(nz, -0.25, -0.75))
    roh = K.max(*teile)
    muster = K.mul(K.add(0.35, K.mul(0.65, K.glatt(fleck, 0.30, 0.72))), K.add(0.55, K.mul(0.9, gischt)))
    dreck_aussen = K.glatt(K.mul(roh, muster), 0.12, 0.9)
    oben = K.glatt(nz, 0.25, 0.85)
    staub_n = K.rauschen(P, 1.3, detail=6, rau=0.5)
    staub_aussen = K.add(K.mul(oben, K.add(0.15, K.mul(0.85, K.glatt(staub_n, 0.45, 0.8))), 0.35),
                         K.mul(0.03, K.glatt(staub_n, 0.5, 0.85)))
    senk = K.glatt(K.m("ABSOLUTE", nz), 0.55, 0.25)
    regen = K.rauschen(K.v("MULTIPLY", P, (22.0, 22.0, 0.9)), 1.0, detail=3, rau=0.5)
    streifen_aussen = K.mul(K.glatt(regen, 0.60, 0.72), senk, K.glatt(z, 1.02, 0.92), K.glatt(z, 0.30, 0.55),
                            K.add(0.3, K.mul(0.7, fleck)), 0.35)
    # Raeder: Bremsstaub, zur Mitte und zur Innenseite hin mehr
    rad_r = K.attribut("rad_r")
    rad_a = K.attribut("rad_a")
    dreck_rad = K.add(0.10, K.mul(0.15, fleck_fein), K.mul(0.12, K.glatt(rad_r, 0.14, 0.05)),
                      K.mul(0.35, K.glatt(rad_a, -0.03, -0.10)))
    # Innenraum: Boden schmutzig, waagrechte Flaechen leicht staubig
    dreck_innen = K.mul(K.glatt(z, 0.32, 0.24), oben, K.add(0.3, K.mul(0.7, fleck)), 0.6)
    staub_innen = K.mul(oben, K.glatt(staub_n, 0.3, 0.8), 0.25)
    r = K.add(K.mul(aussen, dreck_aussen), K.mul(rad, dreck_rad), K.mul(innen, dreck_innen))
    g = K.add(K.mul(aussen, staub_aussen), K.mul(rad, 0.08), K.mul(innen, staub_innen))
    b = K.mul(aussen, streifen_aussen)
    return K.vektor(r, g, b)

def maske_stein(K):
    """R = Steinschlaege, G = feines Rauschen fuer den Kantenabrieb, B = Farbton des Schmutzes."""
    P, N = K.geometrie()
    x, y, z = K.trenne(P)
    nx, ny, nz = K.trenne(N)
    aussen = K.m("LESS_THAN", K.attribut("teil"), 0.5)
    dichte = K.max(K.mul(K.glatt(nx, 0.25, 0.8), K.glatt(x, 2.0, 2.45), 0.07),
                   K.mul(K.glatt(nz, 0.4, 0.8), K.glatt(x, 2.05, 2.45), 0.03),
                   K.mul(K.glatt(x, XV - 1.05, XV - 0.75), K.glatt(x, XV - 0.25, XV - 0.45), K.glatt(z, 0.6, 0.4), 0.04),
                   K.mul(K.glatt(z, 0.32, 0.22), 0.025))
    abst, (zr, zg, zb) = K.zellen(P, 90.0)
    radius = K.add(0.05, K.mul(0.08, zg))
    punkt = K.glatt(abst, K.add(radius, 0.04), radius)
    stein = K.mul(punkt, K.m("GREATER_THAN", zr, K.m("SUBTRACT", 1.0, dichte)), aussen)
    return K.vektor(stein, K.rauschen(P, 35.0, detail=4, rau=0.65), K.rauschen(P, 0.9, detail=3))

def maske_licht(K):
    """R = Verdeckung im Nahbereich (Ritzen), G = Kante (Bevel-Abweichung), B = Umgebungsverdeckung."""
    P, N = K.geometrie()
    nt = K.nt
    ao_k = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao_k.samples, ao_k.only_local = 12, True
    ao_k.inputs["Distance"].default_value = 0.04
    ao_g = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao_g.samples, ao_g.only_local = 12, True
    ao_g.inputs["Distance"].default_value = 0.35
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.samples = 8
    bev.inputs["Radius"].default_value = 0.005
    kante = K.m("MULTIPLY", K.m("SUBTRACT", 1.0, K.v("DOT_PRODUCT", bev.outputs["Normal"], N)), 10.0, clamp=True)
    return K.vektor(ao_k.outputs["AO"], kante, ao_g.outputs["AO"])

def backen(auto, name, farbe_von, proben, aufl):
    """Ein Bake-Durchgang: alle Atlas-Materialien voruebergehend durch ein Emissions-Material ersetzen."""
    ziel = bpy.data.images.new("_bake_" + name, aufl, aufl, alpha=False, float_buffer=True)
    ziel.colorspace_settings.name = "Non-Color"
    leer = bpy.data.images.new("_bake_leer", 64, 64, alpha=False, float_buffer=True)
    m_atlas = back_material("_Bake_" + name, farbe_von, ziel)
    m_leer = back_material("_Bake_leer", None, leer)
    alt = list(auto.data.materials)
    for i, m in enumerate(alt):
        auto.data.materials[i] = m_atlas if atlas_material(m) else m_leer
    scene.cycles.samples = proben
    scene.render.bake.margin = 6
    scene.render.bake.margin_type = "EXTEND"
    bpy.ops.object.select_all(action="DESELECT")
    auto.select_set(True)
    bpy.context.view_layer.objects.active = auto
    t0 = time.time()
    bpy.ops.object.bake(type="EMIT", uv_layer="UVMap", margin=6, use_clear=True)
    for i, m in enumerate(alt):
        auto.data.materials[i] = m
    px = np.empty(aufl * aufl * 4, dtype=np.float32)
    ziel.pixels.foreach_get(px)
    for d in (m_atlas, m_leer):
        bpy.data.materials.remove(d)
    for d in (ziel, leer):
        bpy.data.images.remove(d)
    log(f"  gebacken: {name} ({time.time() - t0:.0f} s)")
    return px.reshape(aufl, aufl, 4)[..., :3]

def mischen(mats, id_px, schmutz, stein, licht):
    """Texturen aus den Masken und den Materialwerten berechnen (numpy, je Texel)."""
    n = len(mats)
    albedo = np.zeros((n + 1, 3), np.float32)
    rau, metall, lack = np.zeros(n + 1, np.float32), np.zeros(n + 1, np.float32), np.zeros(n + 1, np.float32)
    f_dreck, f_abrieb = np.zeros(n + 1, np.float32), np.zeros(n + 1, np.float32)
    abrieb_farbe, abrieb_metall = np.zeros((n + 1, 3), np.float32), np.zeros(n + 1, np.float32)
    bremsstaub = np.zeros(n + 1, bool)
    for i, m in enumerate(mats, start=1):
        b = m.node_tree.nodes["Principled BSDF"]
        albedo[i] = b.inputs["Base Color"].default_value[:3]
        rau[i] = b.inputs["Roughness"].default_value
        metall[i] = b.inputs["Metallic"].default_value
        lack[i] = b.inputs["Coat Weight"].default_value
        regel = SCHMUTZ_REGELN.get(m.name, (0.8, 0.25, None, 0.0))
        d, a, farbe, am = regel[:4]
        f_dreck[i], f_abrieb[i], abrieb_metall[i] = d, a, am
        bremsstaub[i] = len(regel) > 4 and regel[4] == "bremse"
        abrieb_farbe[i] = hexf(farbe) if farbe else np.minimum(albedo[i] * 1.8 + 0.03, 1.0)
    idx = np.clip(np.rint(id_px[..., 0] * 255.0), 0, n).astype(np.int32)
    sd, sa = f_dreck[idx], f_abrieb[idx]
    dreck = schmutz[..., 0] * sd
    staub = schmutz[..., 1] * sd
    streifen = schmutz[..., 2] * sd
    ao_k, kante, ao_g = licht[..., 0], licht[..., 1], licht[..., 2]
    ritze = np.clip((0.8 - ao_k) / 0.5, 0, 1) ** 1.2
    dreck = np.clip(dreck + ritze * 0.35 * sd, 0, 1)
    konvex = np.clip((ao_k - 0.82) / 0.12, 0, 1)
    abrieb = np.clip((kante * konvex * (0.4 + stein[..., 1]) - 0.5) * 3.0, 0, 1) * sa
    stein_m = np.clip(stein[..., 0] * sa, 0, 1)
    F = SCHMUTZ_FARBEN
    def mix(a, b, t):
        return a + (b - a) * t[..., None]
    farbe = albedo[idx]
    farbe = mix(farbe, np.array(F["staub"], np.float32), staub * 0.4)
    farbe = mix(farbe, np.array(F["streifen"], np.float32), streifen * 0.5)
    dreck_farbe = mix(np.broadcast_to(np.array(F["dreck"], np.float32), farbe.shape),
                      np.array(F["dreck_grau"], np.float32), stein[..., 2])
    bs = bremsstaub[idx]
    dreck_farbe[bs] = F["bremse"]
    farbe = farbe + (dreck_farbe - farbe) * (dreck * 0.75)[..., None]
    farbe = farbe + (abrieb_farbe[idx] - farbe) * abrieb[..., None]
    farbe = mix(farbe, np.array(F["stein"], np.float32), stein_m)
    belag = np.clip(dreck * 0.9 + staub * 0.5 + streifen * 0.4, 0, 1)
    r = rau[idx] + (0.9 - rau[idx]) * belag
    r = r + (0.5 - r) * np.maximum(abrieb, stein_m)
    mt = metall[idx] * (1 - np.clip(dreck + staub * 0.5, 0, 1))
    mt = mt + (abrieb_metall[idx] - mt) * abrieb
    kl = lack[idx] * (1 - np.clip(dreck * 1.1 + staub * 0.6 + streifen * 0.3 + abrieb + stein_m, 0, 1))
    ao = 0.25 + 0.75 * ao_g
    leer = idx == 0
    farbe[leer] = 0.5
    srgb = np.clip(farbe, 0, 1) ** (1 / 2.2)
    orm = np.stack([ao, np.clip(r, 0.03, 1), np.clip(mt, 0, 1)], -1)
    orm[leer] = (1.0, 0.5, 0.0)
    kl[leer] = 0.0
    k = kl.reshape(kl.shape[0] // 2, 2, kl.shape[1] // 2, 2).mean(axis=(1, 3))      # halbe Aufloesung genuegt
    return srgb, orm, k[..., None]

SAUBER = {}       # unverschmutzte Kopien der Materialien (fuer die Zivilautos in der Strassenszene)
def schmutz_texturen(auto):
    log("Gebrauchsspuren backen ...")
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    mats = list(auto.data.materials)
    ids = np.array([p.material_index for p in auto.data.polygons], dtype=np.float32)
    a = auto.data.attributes.new("mat_id", "FLOAT", "FACE")
    a.data.foreach_set("value", ids)
    id_px = backen(auto, "id", maske_id, 1, ATLAS)
    schmutz = backen(auto, "schmutz", maske_schmutz, 1, ATLAS)
    stein = backen(auto, "stein", maske_stein, 1, ATLAS)
    licht = backen(auto, "licht", maske_licht, 6, ATLAS)
    auto.data.attributes.remove(auto.data.attributes["mat_id"])
    t0 = time.time()
    srgb, orm, klar = mischen(mats, id_px, schmutz, stein, licht)
    del id_px, schmutz, stein, licht
    bc = bild_hw("T_" + NAME + "_BaseColor", srgb, farbe=True)
    orm_bild = bild_hw("T_" + NAME + "_ORM", orm, farbe=False)
    klar_bild = bild_hw("T_" + NAME + "_Klarlack", klar, farbe=False)
    log(f"  Texturen gemischt und gespeichert ({time.time() - t0:.0f} s)")
    # Materialien umstellen: Farbe, Rauheit/Metall (und AO fuer glTF) und Klarlack aus dem Atlas
    gltf_gruppe = bpy.data.node_groups.get("glTF Material Output")
    if gltf_gruppe is None:
        gltf_gruppe = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        gltf_gruppe.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        gltf_gruppe.interface.new_socket("Thickness", in_out="INPUT", socket_type="NodeSocketFloat")
        gltf_gruppe.nodes.new("NodeGroupInput")
        gltf_gruppe.nodes.new("NodeGroupOutput")
    for m in mats:
        if not atlas_material(m):
            continue
        kopie = m.copy()
        kopie.name = m.name + "_sauber"
        SAUBER[m.name] = kopie
        nt = m.node_tree
        b = nt.nodes["Principled BSDF"]
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = "UVMap"
        def tex(img):
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = img
            nt.links.new(uvn.outputs["UV"], t.inputs["Vector"])
            return t
        nt.links.new(tex(bc).outputs["Color"], b.inputs["Base Color"])
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(tex(orm_bild).outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
        nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
        gl = nt.nodes.new("ShaderNodeGroup")
        gl.node_tree = gltf_gruppe
        nt.links.new(sep.outputs["Red"], gl.inputs["Occlusion"])
        if b.inputs["Coat Weight"].default_value > 0:
            nt.links.new(tex(klar_bild).outputs["Color"], b.inputs["Coat Weight"])

schmutz_texturen(AUTO)

# Skelett: root am Boden zwischen den Achsen, je ein Knochen pro Rad (alle gleich ausgerichtet wie root)
arm_data = bpy.data.armatures.new(NAME + "_Skelett")
ARM = bpy.data.objects.new("Armature", arm_data)       # Unreal uebernimmt einen Knoten namens "Armature" nicht als Extra-Knochen
scene.collection.objects.link(ARM)
bpy.ops.object.select_all(action="DESELECT")
ARM.select_set(True)
bpy.context.view_layer.objects.active = ARM
bpy.ops.object.mode_set(mode="EDIT")
root = arm_data.edit_bones.new("root")
root.head, root.tail = (0, 0, 0), (0, 0, 0.3)
for name, (x, y) in RAEDER.items():
    b = arm_data.edit_bones.new(name)
    b.head, b.tail = (x, y, RAD_R), (x, y, RAD_R + 0.3)
    b.parent = root
bpy.ops.object.mode_set(mode="OBJECT")
AUTO.parent = ARM
mod = AUTO.modifiers.new("Skelett", "ARMATURE")
mod.object = ARM

AUTO.data.calc_loop_triangles()
DREIECKE = len(AUTO.data.loop_triangles)
log(NAME + ":", DREIECKE, "Dreiecke,", len(AUTO.data.materials), "Materialien")

def auswahl():
    bpy.ops.object.select_all(action="DESELECT")
    ARM.select_set(True)
    AUTO.select_set(True)
    bpy.context.view_layer.objects.active = ARM

def skalieren(f):
    AUTO.data.transform(Matrix.Scale(f, 4))
    auswahl()
    bpy.ops.object.mode_set(mode="EDIT")
    for b in ARM.data.edit_bones:
        b.head, b.tail = b.head * f, b.tail * f
    bpy.ops.object.mode_set(mode="OBJECT")

for name in ("teil", "rad_r", "rad_a"):                 # Hilfswerte des Schmutz-Backens gehoeren nicht in den Export
    if name in AUTO.data.attributes:
        AUTO.data.attributes.remove(AUTO.data.attributes[name])

# Vielecke mit mehr als vier Ecken triangulieren (sauber auch bei konkaven Flaechen, und erst dann schreibt der
# FBX-Exporter Tangenten), danach doppelte Flaechen entfernen; beide Exporte bekommen genau dieses Netz
bm = bmesh.new()
bm.from_mesh(AUTO.data)
bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4], quad_method="BEAUTY", ngon_method="BEAUTY")
gesehen, doppelt = set(), []
for f in bm.faces:
    k = frozenset(f.verts)
    if k in gesehen:
        doppelt.append(f)
    gesehen.add(k)
bmesh.ops.delete(bm, geom=doppelt, context="FACES_ONLY")
bm.to_mesh(AUTO.data)
bm.free()
AUTO.data.calc_loop_triangles()
DREIECKE = len(AUTO.data.loop_triangles)
log("fuer den Export:", DREIECKE, "Dreiecke")

# glTF in Metern
auswahl()
bpy.ops.export_scene.gltf(filepath=os.path.join(EXPORT, "SK_" + NAME + ".glb"), export_format="GLB", use_selection=True,
                          export_yup=True, export_apply=False, export_skins=True, export_animations=False,
                          export_cameras=False, export_lights=False, export_image_format="AUTO")
# FBX fuer Unreal: Zentimeter, ueberall Skalierung 1. Mesh und Knochen werden dafuer kurz x100 gesetzt und die
# Szeneneinheit auf 0,01; danach geht alles zurueck.
scene.unit_settings.scale_length = 0.01
skalieren(100.0)
auswahl()
bpy.ops.export_scene.fbx(filepath=os.path.join(EXPORT, "SK_" + NAME + ".fbx"), use_selection=True,
                         object_types={"ARMATURE", "MESH"}, apply_unit_scale=True, global_scale=1.0,
                         apply_scale_options="FBX_SCALE_NONE", add_leaf_bones=False, primary_bone_axis="Y",
                         secondary_bone_axis="X", use_armature_deform_only=True, bake_anim=False,
                         mesh_smooth_type="FACE", use_mesh_modifiers=False, use_tspace=True,
                         path_mode="COPY", embed_textures=True)
skalieren(0.01)
scene.unit_settings.scale_length = 1.0
log("exportiert:", sorted(os.listdir(EXPORT)), sorted(os.listdir(TEXDIR)))

# ---------------- Vorschaubilder: Fotostudio und Strasse bei Nacht ----------------
def welt(farbe, staerke=1.0):
    w = bpy.data.worlds.new("Welt")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*farbe, 1)
    bg.inputs["Strength"].default_value = staerke
    return w

def flaechenlicht(name, ort, ziel, sx, sy, energie, farbe=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA")
    d.shape = "RECTANGLE"
    d.size, d.size_y = sx, sy
    d.energy = energie
    d.color = farbe
    ob = bpy.data.objects.new(name, d)
    scene.collection.objects.link(ob)
    ob.location = ort
    if ziel is not None:
        ob.rotation_euler = (Vector(ziel) - Vector(ort)).to_track_quat("-Z", "Y").to_euler()
    ob.visible_camera = False
    return ob

def punktlicht(name, ort, energie, farbe, radius=0.05, art="POINT", ziel=None, kegel=60):
    d = bpy.data.lights.new(name, art)
    d.energy = energie
    d.color = farbe
    d.shadow_soft_size = radius
    if art == "SPOT":
        d.spot_size = math.radians(kegel)
        d.spot_blend = 0.4
    ob = bpy.data.objects.new(name, d)
    scene.collection.objects.link(ob)
    ob.location = ort
    if ziel is not None:
        ob.rotation_euler = (Vector(ziel) - Vector(ort)).to_track_quat("-Z", "Y").to_euler()
    return ob

def kamera(ort, ziel, brennweite, blende=None):
    cam = scene.camera
    cam.location = ort
    cam.data.lens = brennweite
    cam.rotation_euler = (Vector(ziel) - Vector(ort)).to_track_quat("-Z", "Y").to_euler()
    cam.data.dof.use_dof = blende is not None
    if blende is not None:
        cam.data.dof.aperture_fstop = blende
        cam.data.dof.focus_distance = (Vector(ziel) - Vector(ort)).length

def leuchten(blau, rot, weiss, blinker=0.0, schirm=0.0):
    for m, s in ((M_BLAULICHT, blau), (M_ROTLICHT, blau), (M_RL_LED, rot), (M_LED, weiss), (M_BLINKER, blinker),
                 (M_BILDSCHIRM, schirm)):
        m.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = s

def glas_schatten():
    """Nur fuer die Bilder: Schattenstrahlen gehen durch Glas, sonst bliebe der Innenraum dunkel."""
    for m in bpy.data.materials:
        if not m.use_nodes or "Principled BSDF" not in m.node_tree.nodes:
            continue
        b = m.node_tree.nodes["Principled BSDF"]
        if b.inputs["Transmission Weight"].default_value < 0.5:
            continue
        nt = m.node_tree
        lp = nt.nodes.new("ShaderNodeLightPath")
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        tr.inputs["Color"].default_value = b.inputs["Base Color"].default_value
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Shadow Ray"], mix.inputs[0])
        nt.links.new(b.outputs["BSDF"], mix.inputs[1])
        nt.links.new(tr.outputs["BSDF"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])

def studio():
    """Fotostudio: Boden geht in eine runde Hohlkehle ueber, grosse Softboxen spiegeln sich im Lack."""
    bm = bmesh.new()
    prof = [(0.0, 0.0), (5.0, 0.0), (10.5, 0.0)]
    prof += [(10.5 + 3.0 * math.sin(w), 3.0 - 3.0 * math.cos(w)) for w in np.linspace(0.2, math.pi / 2, 7)] + [(13.5, 10.0)]
    ringe = []
    for i in range(96):
        w = 2 * math.pi * i / 96
        ringe.append([bm.verts.new((r * math.cos(w), r * math.sin(w), z)) for r, z in prof])
    for i in range(96):
        a, b = ringe[i], ringe[(i + 1) % 96]
        for j in range(len(prof) - 1):
            bm.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.normal_update()
    boden = [f for f in bm.faces if f.calc_center_median().z < 0.01]
    if sum(f.normal.z for f in boden) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    ob = objekt("Studio", bm, [material("Studio", hexf("#2a2c30"), rauheit=0.42)], glatt=True)
    lichter = [flaechenlicht("Decke", (0, 0, 6.2), None, 9.0, 4.0, 3200),
               flaechenlicht("Seite_L", (0, 5.6, 1.9), (0, 0, 0.8), 8.0, 0.9, 1700),
               flaechenlicht("Seite_R", (0, -5.6, 1.9), (0, 0, 0.8), 8.0, 0.9, 1700),
               flaechenlicht("Front", (7.5, -3.6, 3.2), (0, 0, 0.7), 3.0, 2.0, 1400),
               flaechenlicht("Heck", (-7.5, 3.6, 3.2), (0, 0, 0.7), 3.0, 2.0, 1000)]
    welt((0.022, 0.024, 0.027))
    return [ob] + lichter

def fassade_material():
    """Hausfassaden: Putz mit Fensterraster, zufaellig beleuchtete Fenster."""
    m = bpy.data.materials.new("Fassade")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    u = mathe(nt, "DIVIDE", sep.outputs["X"], 2.1)
    v = mathe(nt, "DIVIDE", sep.outputs["Z"], 3.1)
    fu, fv = mathe(nt, "FRACT", u), mathe(nt, "FRACT", v)
    maske = mathe(nt, "MULTIPLY", mathe(nt, "MULTIPLY", mathe(nt, "GREATER_THAN", fu, 0.30), mathe(nt, "LESS_THAN", fu, 0.70)),
                  mathe(nt, "MULTIPLY", mathe(nt, "GREATER_THAN", fv, 0.36), mathe(nt, "LESS_THAN", fv, 0.80)))
    maske = mathe(nt, "MULTIPLY", maske, mathe(nt, "GREATER_THAN", sep.outputs["Z"], 3.4))
    cz = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(mathe(nt, "FLOOR", u), cz.inputs[0])
    nt.links.new(mathe(nt, "FLOOR", v), cz.inputs[1])
    zufall = nt.nodes.new("ShaderNodeTexWhiteNoise")
    zufall.noise_dimensions = "3D"
    nt.links.new(cz.outputs[0], zufall.inputs["Vector"])
    an = mathe(nt, "MULTIPLY", maske, mathe(nt, "GREATER_THAN", zufall.outputs["Value"], 0.58))
    farbe = nt.nodes.new("ShaderNodeMix")
    farbe.data_type = "RGBA"
    farbe.inputs[6].default_value = (*hexf("#4c4844"), 1)
    farbe.inputs[7].default_value = (0.012, 0.014, 0.018, 1)
    nt.links.new(maske, farbe.inputs[0])
    nt.links.new(farbe.outputs[2], b.inputs["Base Color"])
    rau = mathe(nt, "ADD", mathe(nt, "MULTIPLY", maske, -0.75), 0.88)
    nt.links.new(rau, b.inputs["Roughness"])
    b.inputs["Emission Color"].default_value = (1.0, 0.72, 0.42, 1)
    nt.links.new(mathe(nt, "MULTIPLY", an, mathe(nt, "ADD", mathe(nt, "MULTIPLY", zufall.outputs["Value"], 2.0), 0.4)),
                 b.inputs["Emission Strength"])
    return m

def asphalt_material():
    m = bpy.data.materials.new("Asphalt_nass")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 0.3
    n1.inputs["Detail"].default_value = 6.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.47, 0.55
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 70.0
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
    nt.links.new(n1.outputs["Fac"], ramp.inputs["Fac"])
    farbe = nt.nodes.new("ShaderNodeMix")
    farbe.data_type = "RGBA"
    farbe.inputs[6].default_value = (0.032, 0.032, 0.034, 1)
    farbe.inputs[7].default_value = (0.010, 0.010, 0.011, 1)
    nt.links.new(ramp.outputs["Color"], farbe.inputs[0])
    nt.links.new(farbe.outputs[2], bsdf.inputs["Base Color"])
    rau = nt.nodes.new("ShaderNodeMapRange")
    rau.inputs["To Min"].default_value, rau.inputs["To Max"].default_value = 0.5, 0.03
    nt.links.new(ramp.outputs["Color"], rau.inputs["Value"])
    nt.links.new(rau.outputs["Result"], bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.2
    nt.links.new(n2.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m

def strasse_nacht():
    """Nasse Stadtstrasse: Asphalt mit Mittellinie, Bordstein, Gehweg, Hausfassaden, Laternen."""
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=45)
    obs = [objekt("Asphalt", bm, [asphalt_material()])]
    bm = bmesh.new()
    for x in np.arange(-40, 40, 9.0):
        einfuegen(bm, kasten((x, -2.7, 0.002), (4.5, 0.12, 0.004)))
    obs.append(objekt("Markierung", bm, [material("Markierung", hexf("#cfcfc8"), rauheit=0.45)]))
    bm = bmesh.new()
    einfuegen(bm, kasten((0, 1.34, 0.06), (90, 0.16, 0.12), fase=0.012, mi=0))
    einfuegen(bm, kasten((0, 3.1, 0.055), (90, 3.4, 0.11), mi=1))
    rng = random.Random(4)
    x = -40.0
    while x < 40:
        breite, hoehe = rng.uniform(9, 16), rng.uniform(10, 19)
        einfuegen(bm, kasten((x + breite / 2, 4.8 + 4.0, hoehe / 2), (breite - 0.3, 8.0, hoehe), mi=2))
        x += breite
    for xl in (-12.0, 7.5, 24.0):
        einfuegen(bm, zylinder((xl, 1.75, 3.3), 0.065, 6.6, "Z", segs=12, mi=3))
        einfuegen(bm, kasten((xl, 1.35, 6.55), (0.12, 0.9, 0.08), mi=3))
        einfuegen(bm, kasten((xl, 0.95, 6.5), (0.55, 0.28, 0.09), fase=0.02, mi=3))
        einfuegen(bm, kasten((xl, 0.95, 6.452), (0.45, 0.2, 0.006), mi=4))
        obs.append(punktlicht("Laterne", (xl, 0.95, 6.35), 900, (1.0, 0.76, 0.52), radius=0.18))
    obs.append(objekt("Stadt", bm, [material("Bordstein", hexf("#8a8a86"), rauheit=0.7),
                                     material("Gehweg", hexf("#4f4f4d"), rauheit=0.55), fassade_material(),
                                     material("Mast", hexf("#2a2c2e"), metall=0.7, rauheit=0.5),
                                     material("Lampe", hexf("#ffe2b8"), leuchten=25.0)]))
    return obs

# ---------------- Tagesszene: eigene amerikanische Innenstadtstrasse (kein Nachbau eines bestimmten Spiels) ----------------
def textur_material(name, art, farben, skala, rauheit=0.8, fuge=None, bump=0.3):
    """Prozedurale Oberflaechen: 'ziegel' (Fassade x/z), 'platten' (Gehweg x/y), 'asphalt'."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rauheit
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    cz = nt.nodes.new("ShaderNodeCombineXYZ")
    if art == "ziegel":
        nt.links.new(sep.outputs["X"], cz.inputs[0])
        nt.links.new(sep.outputs["Z"], cz.inputs[1])
    else:
        nt.links.new(sep.outputs["X"], cz.inputs[0])
        nt.links.new(sep.outputs["Y"], cz.inputs[1])
    farbe_out = None
    if art in ("ziegel", "platten"):
        br = nt.nodes.new("ShaderNodeTexBrick")
        br.offset = 0.5 if art == "ziegel" else 0.0
        br.inputs["Scale"].default_value = 1.0
        br.inputs["Brick Width"].default_value, br.inputs["Row Height"].default_value = skala
        br.inputs["Mortar Size"].default_value = fuge
        br.inputs["Mortar Smooth"].default_value = 0.3
        br.inputs["Color1"].default_value = (*farben[0], 1)
        br.inputs["Color2"].default_value = (*farben[1], 1)
        br.inputs["Mortar"].default_value = (*farben[2], 1)
        br.inputs["Bias"].default_value = 0.0
        nt.links.new(cz.outputs[0], br.inputs["Vector"])
        farbe_out = br.outputs["Color"]
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = bump
        bmp.invert = True
        nt.links.new(br.outputs["Fac"], bmp.inputs["Height"])
        nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    # feine Verschmutzung/Unruhe ueber alles
    no = nt.nodes.new("ShaderNodeTexNoise")
    no.inputs["Scale"].default_value = 1.6 if art != "asphalt" else 0.9
    no.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], no.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 0.35
    if farbe_out is not None:
        nt.links.new(farbe_out, mix.inputs[6])
    else:
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (*farben[0], 1)
        ramp.color_ramp.elements[1].color = (*farben[1], 1)
        ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.35, 0.65
        no2 = nt.nodes.new("ShaderNodeTexNoise")
        no2.inputs["Scale"].default_value = 0.25
        no2.inputs["Detail"].default_value = 4.0
        nt.links.new(tc.outputs["Object"], no2.inputs["Vector"])
        nt.links.new(no2.outputs["Fac"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], mix.inputs[6])
        fein = nt.nodes.new("ShaderNodeTexNoise")
        fein.inputs["Scale"].default_value = 160.0
        bmp = nt.nodes.new("ShaderNodeBump")
        bmp.inputs["Strength"].default_value = bump
        nt.links.new(tc.outputs["Object"], fein.inputs["Vector"])
        nt.links.new(fein.outputs["Fac"], bmp.inputs["Height"])
        nt.links.new(bmp.outputs["Normal"], b.inputs["Normal"])
    nt.links.new(no.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    return m

def us_stadt():
    """Innenstadtstrasse: zwei Fahrspuren mit gelber Doppellinie, Parkstreifen, Zebrastreifen und Haltelinie,
    Bordsteine, Gehwege mit Fugen, Haeuserzeilen mit Laeden und Fenstern, Laternen, Ampel mit Strassenschild,
    Hydrant, Parkuhren, Kanaldeckel."""
    rng = random.Random(27)
    obs = []
    # Asphalt
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=320)
    obs.append(objekt("Fahrbahn", bm, [textur_material("Asphalt", "asphalt", (hexf("#3b3b3d"), hexf("#2a2a2c")), None,
                                                       rauheit=0.9, bump=0.25)]))
    # Markierungen
    bm = bmesh.new()       # 0 weiss, 1 gelb, 2 Kanaldeckel
    for y in (-0.09, 0.09):
        einfuegen(bm, kasten((50.0, y, 0.003), (220.0, 0.10, 0.006), mi=1))
    for y in (-3.3, 3.3):
        einfuegen(bm, kasten((50.0, y, 0.003), (220.0, 0.12, 0.006), mi=0))
    for k in range(9):
        einfuegen(bm, kasten((21.0, -5.0 + 1.25 * k, 0.003), (3.0, 0.6, 0.006), mi=0))     # Zebrastreifen
    einfuegen(bm, kasten((19.0, -2.75, 0.003), (0.45, 5.4, 0.006), mi=0))                   # Haltelinie
    for x, y in ((-9.0, -1.9), (12.0, 1.6), (33.0, -2.2)):
        einfuegen(bm, zylinder((x, y, 0.004), 0.33, 0.008, "Z", segs=24, mi=2))
    obs.append(objekt("Markierung", bm, [material("Markierung_Weiss", hexf("#e4e4de"), rauheit=0.55),
                                          material("Markierung_Gelb", hexf("#e0ad1c"), rauheit=0.55),
                                          material("Gusseisen", hexf("#2a2622"), metall=0.7, rauheit=0.6)]))
    # Bordsteine und Gehwege
    bm = bmesh.new()
    for sg in (-1, 1):
        einfuegen(bm, kasten((50.0, sg * 5.58, 0.075), (220.0, 0.16, 0.15), fase=0.015, mi=0))
        einfuegen(bm, kasten((50.0, sg * 7.68, 0.07), (220.0, 4.04, 0.14), mi=1))
    obs.append(objekt("Gehweg", bm, [material("Bordstein", hexf("#8e8d88"), rauheit=0.75),
                                      textur_material("Gehwegplatten", "platten",
                                                      (hexf("#9c9a94"), hexf("#8f8d88"), hexf("#5d5c58")),
                                                      (1.5, 1.5), rauheit=0.85, fuge=0.008, bump=0.4)]))
    # Haeuserzeilen
    bau_mats = [textur_material("Ziegel_Rot", "ziegel", (hexf("#8a4433"), hexf("#7a3c2e"), hexf("#b8b0a2")), (0.25, 0.075),
                                fuge=0.012, bump=0.5),
                textur_material("Ziegel_Hell", "ziegel", (hexf("#b5916a"), hexf("#a6845f"), hexf("#d2c8b8")), (0.25, 0.075),
                                fuge=0.012, bump=0.5),
                material("Putz", hexf("#c8bba0"), rauheit=0.9), material("Beton", hexf("#9c9c98"), rauheit=0.85),
                material("Rahmen", hexf("#e2ddd2"), rauheit=0.6), material("Fensterglas", hexf("#1b232a"), rauheit=0.04),
                material("Markise_Rot", hexf("#8e1d1d"), rauheit=0.8), material("Markise_Gruen", hexf("#1f4d2e"), rauheit=0.8),
                material("Schild", hexf("#1d1f22"), rauheit=0.4), material("Gesims", hexf("#cfc8ba"), rauheit=0.7),
                material("Fensterglas_Hell", hexf("#3a4650"), rauheit=0.08)]
    laeden = ["DINER", "COFFEE", "PHARMACY", "BAKERY", "BOOKS", "HARDWARE", "LAUNDRY", "PIZZA", "DELI", "BARBER",
              "FLOWERS", "TAILOR", "MARKET", "SHOES"]
    bm = bmesh.new()
    for sg in (-1, 1):
        x = -60.0
        while x < 160.0:
            breite = rng.choice([8.0, 9.0, 10.0, 12.0, 14.0])
            etagen = rng.choice([2, 3, 3, 4, 5, 6])
            hoehe = 4.5 + 3.2 * etagen
            stil = rng.randrange(4)
            yf = sg * 9.7
            xm = x + breite / 2
            einfuegen(bm, kasten((xm, sg * 15.7, hoehe / 2), (breite - 0.15, 12.0, hoehe), mi=stil))
            einfuegen(bm, kasten((xm, yf - sg * 0.12, hoehe - 0.25), (breite - 0.1, 0.30, 0.35), mi=9))
            einfuegen(bm, kasten((xm, yf - sg * 0.10, 4.35), (breite - 0.1, 0.22, 0.22), mi=9))
            # Laden im Erdgeschoss: Schaufenster mit Rahmen, Tuer, Schild, Markise
            sb = breite - 3.2
            einfuegen(bm, kasten((xm - 0.6, yf - sg * 0.01, 1.75), (sb, 0.02, 2.6), mi=5))
            for dz, hz in ((0.42, 0.12), (3.08, 0.12)):
                einfuegen(bm, kasten((xm - 0.6, yf - sg * 0.05, dz), (sb + 0.2, 0.10, hz), mi=4))
            for dx in (-sb / 2, sb / 2):
                einfuegen(bm, kasten((xm - 0.6 + dx, yf - sg * 0.05, 1.75), (0.12, 0.10, 2.78), mi=4))
            einfuegen(bm, kasten((x + breite - 1.25, yf - sg * 0.01, 1.2), (1.1, 0.02, 2.3), mi=10))
            einfuegen(bm, kasten((xm, yf - sg * 0.06, 3.75), (breite - 2.0, 0.10, 0.62), mi=8))
            name = laeden[rng.randrange(len(laeden))]
            obs.append(schrift_auf(name, 0.42, MATS.get("Markierung_Weiss"), (xm, yf - sg * 0.115, 3.62),
                                   (0, -sg, 0), "Ladenschild"))
            if rng.random() < 0.6:
                neigung = Matrix.Rotation(sg * math.radians(22), 3, "X")
                einfuegen(bm, kasten((xm - 0.6, yf - sg * 0.72, 3.05), (sb + 0.3, 1.45, 0.05), rot=neigung,
                                     mi=6 if rng.random() < 0.5 else 7))
            # Fenster in den Obergeschossen: Glas buendig, Rahmen und Fensterbank stehen vor
            n = max(1, int((breite - 1.0) // 2.0))
            for k in range(etagen):
                zf = 4.5 + 3.2 * k + 0.85
                for i in range(n):
                    xf = x + (breite - (n - 1) * 2.0) / 2 + i * 2.0
                    einfuegen(bm, kasten((xf, yf - sg * 0.005, zf + 0.8), (1.1, 0.01, 1.6), mi=5 if rng.random() < 0.7 else 10))
                    for dx in (-0.6, 0.6):
                        einfuegen(bm, kasten((xf + dx, yf - sg * 0.04, zf + 0.8), (0.1, 0.08, 1.8), mi=4))
                    einfuegen(bm, kasten((xf, yf - sg * 0.04, zf + 1.65), (1.3, 0.08, 0.1), mi=4))
                    einfuegen(bm, kasten((xf, yf - sg * 0.06, zf - 0.04), (1.4, 0.12, 0.08), mi=4))
            x += breite
    obs.append(objekt("Haeuser", bm, bau_mats))
    # Strassenmoebel
    bm = bmesh.new()       # 0 Mast grau, 1 Leuchte, 2 Ampelgelb, 3 schwarz, 4 Rot (Hydrant), 5 Gruen (Schild), 6 Ampel rot,
    #                        7 Ampel gelb, 8 Ampel gruen (an), 9 Parkuhr
    for sg in (-1, 1):
        for xl in (-14.0, 11.0, 36.0, 61.0, 86.0, 111.0, 136.0):
            einfuegen(bm, zylinder((xl, sg * 6.15, 4.0), 0.08, 8.0, "Z", segs=14, mi=0, r2=0.055))
            einfuegen(bm, rohr([(xl, sg * 6.15, 7.9), (xl, sg * 5.4, 8.15), (xl, sg * 3.9, 8.2)], 0.04, segs=8, mi=0))
            einfuegen(bm, kasten((xl, sg * 3.55, 8.16), (0.75, 0.36, 0.14), fase=0.05, mi=0))
            einfuegen(bm, kasten((xl, sg * 3.55, 8.085), (0.55, 0.26, 0.02), mi=1))
    einfuegen(bm, zylinder((21.6, -6.3, 3.3), 0.13, 6.6, "Z", segs=16, mi=0))
    einfuegen(bm, rohr([(21.6, -6.3, 6.15), (21.6, -3.0, 6.35), (21.6, -0.6, 6.45)], 0.075, segs=10, mi=0))
    for ys, zs in ((-3.9, 5.75), (-1.3, 5.85)):
        einfuegen(bm, kasten((21.5, ys, zs), (0.32, 0.34, 1.0), fase=0.03, mi=2))
        einfuegen(bm, kasten((21.67, ys, zs), (0.02, 0.55, 1.2), mi=3))
        for dz, mi in ((0.31, 6), (0.0, 7), (-0.31, 8)):
            einfuegen(bm, zylinder((21.335, ys, zs + dz), 0.10, 0.02, "X", segs=20, mi=mi))
            einfuegen(bm, zylinder((21.30, ys, zs + dz + 0.05), 0.115, 0.10, "X", segs=20, mi=3, deckel=False))
    einfuegen(bm, kasten((21.55, -2.55, 6.62), (0.03, 1.3, 0.32), fase=0.02, mi=5))
    obs.append(schrift_auf("MAIN ST", 0.20, MATS.get("Markierung_Weiss"), (21.53, -2.55, 6.56), (-1, 0, 0), "Strassenschild"))
    hx, hy = -4.2, -6.15
    einfuegen(bm, zylinder((hx, hy, 0.17), 0.16, 0.06, "Z", segs=20, mi=4))
    einfuegen(bm, zylinder((hx, hy, 0.45), 0.11, 0.55, "Z", segs=20, mi=4))
    einfuegen(bm, kugel((hx, hy, 0.72), 0.115, segs=20, ringe=10, skala=(1, 1, 0.6), mi=4))
    einfuegen(bm, zylinder((hx, hy, 0.80), 0.035, 0.06, "Z", segs=6, mi=4))
    for sx in (-1, 1):
        einfuegen(bm, zylinder((hx, hy + sx * 0.14, 0.55), 0.05, 0.10, "Y", segs=14, mi=4))
    einfuegen(bm, zylinder((hx + 0.14, hy, 0.52), 0.065, 0.10, "X", segs=14, mi=4))
    for xp in np.arange(-30.0, 18.0, 6.5):
        einfuegen(bm, zylinder((xp, 6.05, 0.70), 0.03, 1.12, "Z", segs=8, mi=3))
        einfuegen(bm, kasten((xp, 6.05, 1.36), (0.13, 0.11, 0.26), fase=0.03, mi=9))
    obs.append(objekt("Strassenmoebel", bm, [material("Mast", hexf("#6e7173"), metall=0.6, rauheit=0.5),
                                              material("Leuchte", hexf("#f2efe6"), rauheit=0.2),
                                              material("Ampelgelb", hexf("#d9b21c"), rauheit=0.5),
                                              material("Schwarz_matt", hexf("#141414"), rauheit=0.7),
                                              material("Hydrant_Rot", hexf("#b51a17"), rauheit=0.45, lack=0.3),
                                              material("Schild_Gruen", hexf("#1d6b3a"), rauheit=0.35),
                                              material("Ampel_Rot", hexf("#3a0606"), rauheit=0.2),
                                              material("Ampel_Gelb", hexf("#3a2a04"), rauheit=0.2),
                                              material("Ampel_Gruen", hexf("#1aff7a"), rauheit=0.2, leuchten=6.0),
                                              material("Parkuhr", hexf("#4a4f55"), metall=0.6, rauheit=0.4)],
                      glatt=True, auto_glatt=35))
    return obs

def zivilauto(farbe, ort, gier, name):
    """Geparktes Zivilauto aus derselben eigenen Karosserie: einfarbig, Scheinwerfer- und Rueckleuchtenglas,
    silberne Felgen, ohne Polizeiausstattung."""
    kar = karosserie()
    s_, f_ = ausschnitte(kar)
    schneiden(kar, s_, f_)
    lz = lack("Lack_" + name, hexf(farbe), 0.6)
    kar.data.materials[K_S] = lz
    kar.data.materials[K_W] = lz
    teile = [kar]
    bm = bmesh.new()
    for key in list(PATCHES):
        if key.startswith(("scheinwerfer", "nebel")):
            einfuegen(bm, von_patch(key, 0))
        elif key.startswith(("ruecklicht", "heckblitzer")):
            einfuegen(bm, von_patch(key, 1))
    teile.append(objekt(name + "_Licht", bm, [M_SW_GLAS, M_RL_GLAS]))
    silber = material("Felge_Silber", hexf("#c3c7cb"), metall=1.0, rauheit=0.25)
    for ob in raeder().values():
        ob.data.materials[1] = silber
        teile.append(ob)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in teile:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = kar
    bpy.ops.object.join()
    for i, m in enumerate(kar.data.materials):          # saubere Materialien statt der verschmutzten Atlas-Materialien
        if m is not None and m.name in SAUBER:
            kar.data.materials[i] = SAUBER[m.name]
    kar.name = name
    kar.location = ort
    kar.rotation_euler = (0, 0, gier)
    return kar

def himmel_tag():
    """Physikalischer Himmel (ohne Sonnenscheibe) plus Sonne als Lampe fuer scharfe Schatten."""
    w = bpy.data.worlds.new("Himmel")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_disc = False
    hoehe, richtung = math.radians(40), math.radians(258)
    sky.sun_elevation = hoehe
    sky.sun_rotation = richtung + math.pi / 2
    sky.dust_density = 1.6
    nt.links.new(sky.outputs["Color"], nt.nodes["Background"].inputs["Color"])
    nt.nodes["Background"].inputs["Strength"].default_value = 0.16
    d = Vector((math.cos(hoehe) * math.cos(richtung), math.cos(hoehe) * math.sin(richtung), math.sin(hoehe)))
    sonne = bpy.data.objects.new("Sonne", bpy.data.lights.new("Sonne", "SUN"))
    scene.collection.objects.link(sonne)
    sonne.data.energy = 5.5
    sonne.data.angle = math.radians(0.7)
    sonne.data.color = (1.0, 0.96, 0.9)
    sonne.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    return sonne

if SHOTS:
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 10
    scene.cycles.glossy_bounces = 6
    scene.cycles.transmission_bounces = 10
    scene.cycles.transparent_max_bounces = 16
    scene.cycles.caustics_reflective = scene.cycles.caustics_refractive = False
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    glas_schatten()
    cd = bpy.data.cameras.new("Kamera")
    cd.clip_end = 300
    cam = bpy.data.objects.new("Kamera", cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    STUDIO = {
        "vorne": ((6.3, -4.6, 1.0), (0.30, 0.0, 0.66), 45, None),
        "hinten": ((-6.2, 4.7, 1.25), (-0.35, 0.0, 0.74), 45, None),
        "seite": ((0.0, -9.4, 0.9), (0.0, 0.0, 0.74), 50, None),
        "oben": ((-5.0, -5.6, 6.2), (-0.15, 0.0, 0.55), 40, None),
        "detail": ((4.45, -2.3, 0.86), (2.5, -0.45, 0.62), 55, 2.8),
    }
    for i, k in enumerate(os.environ.get("KAMERAS", "").split("|")):    # Testansichten: "ort;ziel;brennweite|..."
        if k:
            o, z, f = k.split(";")
            STUDIO[f"test{i}"] = (tuple(map(float, o.split(","))), tuple(map(float, z.split(","))), float(f), None)
    studio_shots = [s for s in SHOTS if s in STUDIO]
    if studio_shots:
        szene = studio()
        leuchten(0.0, 0.8, 2.5)
        for s in studio_shots:
            kamera(*STUDIO[s])
            scene.render.filepath = os.path.join(OUT, f"{NAME.lower()}_{s}.png")
            log("Render", s)
            bpy.ops.render.render(write_still=True)
        for ob in szene:
            bpy.data.objects.remove(ob)
    STRASSE = {
        "verfolger": ((-7.6, -1.8, 2.55), (3.0, -1.65, 0.95), 32, None),
        "strasse": ((9.0, -7.4, 1.35), (0.5, -1.8, 0.85), 38, None),
    }
    tag_shots = [s for s in SHOTS if s in STRASSE]
    if tag_shots:
        szene = us_stadt() + [himmel_tag()]
        log("Zivilautos ...")
        szene += [zivilauto("#6e1416", (-13.5, -4.35, 0.0), 0.0, "Zivil_Rot"),
                  zivilauto("#a9adb2", (13.0, -4.35, 0.0), 0.0, "Zivil_Silber"),
                  zivilauto("#1c2b45", (3.5, 4.35, 0.0), math.pi, "Zivil_Blau")]
        ARM.location.y = -1.8                      # rechte Fahrspur
        leuchten(30.0, 2.0, 8.0)
        for s in tag_shots:
            kamera(*STRASSE[s])
            scene.render.filepath = os.path.join(OUT, f"{NAME.lower()}_{s}.png")
            log("Render", s)
            bpy.ops.render.render(write_still=True)
        for ob in szene:
            bpy.data.objects.remove(ob)
        ARM.location.y = 0.0
        leuchten(0.0, 0.8, 2.5)
    if "nacht" in SHOTS:
        strasse_nacht()
        welt((0.0025, 0.0035, 0.007))
        leuchten(8.0, 5.0, 12.0, schirm=1.5)
        xb, zk = -0.30, Z_TOP(-0.30) + 0.12
        for sg in (-1, 1):
            farbe = (1.0, 0.06, 0.04) if sg > 0 else (0.12, 0.3, 1.0)       # Fahrerseite rot, Beifahrerseite blau
            for ort, ri in (((xb + 0.17, sg * 0.43, zk), (1, 0, -0.3)), ((xb - 0.17, sg * 0.43, zk), (-1, 0, -0.3)),
                            ((xb, sg * 0.70, zk), (0, sg, -0.3))):
                punktlicht("Lichtbalken", ort, 900, farbe, radius=0.02, art="SPOT", ziel=tuple(Vector(ort) + Vector(ri)),
                           kegel=165)
            punktlicht("Rammschutzblitzer", (2.78, sg * 0.18, 0.752), 40, farbe, radius=0.02)
            punktlicht("Grillblitzer", (2.66, sg * 0.19, 0.585), 30, farbe, radius=0.02)
            punktlicht("Heckscheibenblitzer", (-1.16, sg * 0.25, Z_TOP(-1.075) - 0.075), 60, farbe, radius=0.03)
            punktlicht("Scheinwerfer", (2.60, sg * 0.62, 0.645), 1000, (1.0, 0.95, 0.88), radius=0.03, art="SPOT",
                       ziel=(9.5, sg * 1.2, 0.0), kegel=55)
            punktlicht("Ruecklicht", (-2.64, sg * 0.72, 0.89), 12, (1.0, 0.05, 0.03), radius=0.05)
        kamera((5.9, -4.1, 0.78), (0.3, 0.4, 0.95), 32)
        scene.use_nodes = True
        nt = scene.node_tree
        gl = nt.nodes.new("CompositorNodeGlare")
        gl.glare_type = "BLOOM"
        gl.quality = "HIGH"
        gl.inputs["Threshold"].default_value = 1.0
        gl.inputs["Strength"].default_value = 0.5
        gl.inputs["Size"].default_value = 0.55
        nt.links.new(nt.nodes["Render Layers"].outputs["Image"], gl.inputs["Image"])
        nt.links.new(gl.outputs["Image"], nt.nodes["Composite"].inputs["Image"])
        scene.render.filepath = os.path.join(OUT, f"{NAME.lower()}_nacht.png")
        log("Render nacht")
        bpy.ops.render.render(write_still=True)
        leuchten(0.0, 0.8, 2.5)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, NAME.lower() + ".blend"), compress=True)
bpy.ops.file.make_paths_relative()                 # Texturen relativ zur .blend (export/Texturen), damit sie mitwandern
bpy.ops.wm.save_mainfile(compress=True)
log("fertig")

