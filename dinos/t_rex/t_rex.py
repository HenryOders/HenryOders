# Tyrannosaurus rex fuer Spiele: eigenes, realistisches Design (schuppige Haut, Lippen am Kieferrand), kein Nachbau
# aus einem Film. Das Skript erzeugt die Form aus weich verschmolzenen Grundkoerpern (Abstandsfelder), ein sauberes
# Netz, Zaehne, Augen und Krallen, ein Skelett fuer Unreal Engine 5 mit weichen Gewichten, die Animationen Stehen,
# Laufen und Bruellen, gebackene Haut-Texturen, den Export als FBX und glTF, Vorschaubilder und kurze Videos.
# Start: blender -b -P t_rex.py   (oder mit dem bpy-Modul: python t_rex.py)
# Das Skript setzt Blender auf Werkseinstellungen zurueck, also nicht in einem offenen Projekt ausfuehren.
# Koordinaten: X nach vorn, Y nach links, Z nach oben, Ursprung am Boden unter den Hueftgelenken. Meter.
# Schalter (Umgebungsvariablen): SHOTS, VIDEOS, SAMPLES, RES, ATLAS, FEIN, NETZ, HAUT (siehe LIESMICH.md).
import bpy, bmesh, math, os, time, random
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, Quaternion, Euler
from mathutils.bvhtree import BVHTree

T0 = time.time()
def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)

NAME = "TRex"                                     # Dateinamen: SK_<NAME>.fbx/.glb, t_rex_*.png, t_rex.blend
DATEI = "t_rex"
OUT = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(OUT, "export")
TEXDIR = os.path.join(EXPORT, "Texturen")
os.makedirs(TEXDIR, exist_ok=True)
SHOTS = [s for s in os.environ.get("SHOTS", "dschungel,bruellen,seite,vorne,kopf").split(",") if s]
SAMPLES = int(os.environ.get("SAMPLES", "64"))
RES = [int(v) for v in os.environ.get("RES", "1920x1080").split("x")]
NETZ = float(os.environ.get("NETZ", "0.035"))     # Kantenlaenge des Spielnetzes in Metern
FEIN = float(os.environ.get("FEIN", "0.012"))     # Kantenlaenge des feinen Netzes fuer die Normal-Textur
ATLAS = int(os.environ.get("ATLAS", "4096"))

bpy.ops.wm.read_factory_settings(use_empty=True)
for mod in ("io_scene_gltf2", "io_scene_fbx"):
    try:
        addon_utils.enable(mod, default_set=True)
    except Exception as e:
        log("Add-on", mod, "nicht geladen:", e)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0
scene.render.fps = 30

# ---------------- Werkzeuge (wie beim Streifenwagen) ----------------
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
            self.ein(n.inputs[3] if op == "SCALE" else n.inputs[1], b)
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

# ---------------- Abstandsfelder: Bausteine, weiches Verschmelzen, Gitter, Oberflaechennetz ----------------
# Die Form ist eine Folge von Bausteinen mit je einer Abstandsfunktion d (negativ = innen). "plus"-Bausteine werden
# weich vereinigt (Uebergangsradius k), "minus"-Bausteine weich abgezogen. Daraus entsteht auf einem Gitter das Feld,
# aus dem Surface Nets ein geschlossenes Vierecksnetz bauen; die Ecken werden danach genau auf die Flaeche gesetzt.
def smin(a, b, k):
    """Weiches Minimum (Vereinigung). k darf ein Array sein."""
    k = np.maximum(k, 1e-9)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)

def smax(a, b, k):
    return -smin(-a, -b, k)

def drehung(achse, grad):
    """3x3-Drehmatrix (numpy) um eine Weltachse."""
    return np.array(Matrix.Rotation(math.radians(grad), 3, achse))

def ausrichtung(z_achse, x_hinweis=(1, 0, 0)):
    """Drehmatrix (Spalten = lokale Achsen in Weltkoordinaten), deren lokale z-Achse in z_achse zeigt."""
    z = np.array(z_achse, float)
    z /= np.linalg.norm(z)
    x = np.array(x_hinweis, float)
    x = x - z * (x @ z)
    if np.linalg.norm(x) < 1e-6:
        x = np.array((0, 1, 0), float) - z * z[1]
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], axis=1)

class Baustein:
    """Teil der Form. gruppe: Koerperteil fuer die Gewichte (rumpf, kiefer, bein_l, ...); art: plus oder minus;
    k: Uebergangsradius (Zahl) oder Funktion k(P)."""
    def __init__(self, gruppe, k=0.05, art="plus"):
        self.gruppe, self.k, self.art = gruppe, k, art

    def k_bei(self, P):
        return self.k(P) if callable(self.k) else self.k

    def k_max(self):
        return 0.12 if callable(self.k) else self.k

    def huelle(self):
        raise NotImplementedError

    def d(self, P):
        raise NotImplementedError

class Kugel(Baustein):
    def __init__(self, c, r, **kw):
        super().__init__(**kw)
        self.c, self.r = np.array(c, float), r

    def huelle(self):
        return self.c - self.r, self.c + self.r

    def d(self, P):
        return np.linalg.norm(P - self.c, axis=1) - self.r

class Ellipsoid(Baustein):
    """Ellipsoid mit Halbachsen r (lokal x, y, z) und Drehung M (Spalten = lokale Achsen in Weltkoordinaten)."""
    def __init__(self, c, r, M=None, **kw):
        super().__init__(**kw)
        self.c, self.r = np.array(c, float), np.array(r, float)
        self.M = np.eye(3) if M is None else np.array(M, float)

    def huelle(self):
        e = np.abs(self.M) @ self.r
        return self.c - e, self.c + e

    def d(self, P):
        L = (P - self.c) @ self.M
        k0 = np.linalg.norm(L / self.r, axis=1)
        k1 = np.linalg.norm(L / (self.r * self.r), axis=1)
        return np.where(k1 > 1e-12, k0 * (k0 - 1.0) / np.maximum(k1, 1e-12), -self.r.min())

class Kegel(Baustein):
    """Abgerundeter Kegel (Kapsel mit zwei Radien) von a (r1) nach b (r2)."""
    def __init__(self, a, b, r1, r2, **kw):
        super().__init__(**kw)
        self.a, self.b, self.r1, self.r2 = np.array(a, float), np.array(b, float), r1, r2

    def huelle(self):
        r = max(self.r1, self.r2)
        return np.minimum(self.a, self.b) - r, np.maximum(self.a, self.b) + r

    def d(self, P):
        a, b, r1, r2 = self.a, self.b, self.r1, self.r2
        ba = b - a
        l2 = ba @ ba
        rr = r1 - r2
        a2 = l2 - rr * rr
        il2 = 1.0 / l2
        pa = P - a
        y = pa @ ba
        z = y - l2
        q = pa * l2 - np.outer(y, ba)
        x2 = np.einsum("ij,ij->i", q, q)
        y2 = y * y * l2
        z2 = z * z * l2
        k = np.sign(rr) * rr * rr * x2
        d1 = np.sqrt(x2 + z2) * il2 - r2
        d2 = np.sqrt(x2 + y2) * il2 - r1
        d3 = (np.sqrt(np.maximum(x2 * a2 * il2, 0.0)) + y * rr) * il2 - r1
        return np.where(np.sign(z) * a2 * z2 > k, d1, np.where(np.sign(y) * a2 * y2 < k, d2, d3))

class Profil(Baustein):
    """Laengskoerper entlang der lokalen x-Achse aus Profilkurven: Oberkante, Unterkante, halbe Breite, Exponent der
    Superellipse (2 = Ellipse, groesser = eckiger), schief (> 0 oben breiter). Die Enden werden auf rund_hinten bzw.
    rund_vorn Metern elliptisch zugespitzt. Optional um drehpunkt mit der Drehung M (lokal -> Welt) gedreht."""
    def __init__(self, xs, oben, unten, breite, expo, schief, rund_hinten=0.0, rund_vorn=0.0, drehpunkt=None, M=None,
                 **kw):
        super().__init__(**kw)
        self.xs = np.asarray(xs, float)
        self.zt, self.zb, self.w = (np.asarray(v, float) for v in (oben, unten, breite))
        self.n, self.a = np.asarray(expo, float), np.asarray(schief, float)
        x0, x1 = self.xs[0], self.xs[-1]
        f = np.ones_like(self.xs)
        if rund_hinten > 0:
            t = np.clip((x0 + rund_hinten - self.xs) / rund_hinten, 0, 1)
            f *= np.sqrt(np.clip(1 - t * t, 0, 1))
        if rund_vorn > 0:
            t = np.clip((self.xs - (x1 - rund_vorn)) / rund_vorn, 0, 1)
            f *= np.sqrt(np.clip(1 - t * t, 0, 1))
        zc = 0.5 * (self.zt + self.zb)
        hb = 0.5 * (self.zt - self.zb) * f
        self.zt, self.zb, self.w = zc + hb, zc - hb, self.w * f
        self.p0 = None if drehpunkt is None else np.array(drehpunkt, float)
        self.M = None if M is None else np.array(M, float)

    def lokal(self, P):
        if self.M is None:
            return P
        return (P - self.p0) @ self.M + self.p0

    def huelle(self):
        lo = np.array([self.xs[0], -np.max(self.w * (1 + np.abs(self.a))), self.zb.min()])
        hi = np.array([self.xs[-1], np.max(self.w * (1 + np.abs(self.a))), self.zt.max()])
        if self.M is None:
            return lo, hi
        ecken = np.array([[lo[0] if i & 1 else hi[0], lo[1] if i & 2 else hi[1], lo[2] if i & 4 else hi[2]]
                          for i in range(8)])
        welt = (ecken - self.p0) @ self.M.T + self.p0
        return welt.min(0), welt.max(0)

    def d(self, P):
        L = self.lokal(P)
        x = L[:, 0]
        zt, zb = np.interp(x, self.xs, self.zt), np.interp(x, self.xs, self.zb)
        w, n, a = np.interp(x, self.xs, self.w), np.interp(x, self.xs, self.n), np.interp(x, self.xs, self.a)
        zc = 0.5 * (zt + zb)
        b = np.maximum(0.5 * (zt - zb), 1e-4)
        v = (L[:, 2] - zc) / b
        we = np.maximum(w * (1 + a * np.clip(v, -1, 1)), 1e-4)
        u = L[:, 1] / we
        r = (np.abs(u) ** n + np.abs(v) ** n) ** (1.0 / n)
        d = (r - 1.0) * np.minimum(we, b)
        aus = np.maximum(self.xs[0] - x, x - self.xs[-1])
        return np.where(aus > 0, np.sqrt(np.maximum(d, 0) ** 2 + aus ** 2), d)

class Feld:
    """Die ganze Form: Bausteine in Reihenfolge; optional eine Feinstruktur (Falten), die abgezogen wird."""
    def __init__(self, bausteine, falten=None):
        self.bausteine, self.falten = bausteine, falten

    def werte(self, P, gruppen=False):
        """Feldwert an Punkten P (N, 3). Mit gruppen=True zusaetzlich die Abstaende je Gruppe (nur plus-Bausteine)."""
        f = np.full(len(P), 10.0)
        je_gruppe = {}
        for b in self.bausteine:
            lo, hi = b.huelle()
            rand = b.k_max() + 0.05
            sel = np.nonzero(np.all((P >= lo - rand) & (P <= hi + rand), axis=1))[0]
            if len(sel) == 0:
                continue
            Q = P[sel]
            d = b.d(Q)
            k = b.k_bei(Q)
            if b.art == "plus":
                f[sel] = smin(f[sel], d, k)
                if gruppen:
                    g = je_gruppe.setdefault(b.gruppe, np.full(len(P), 10.0))
                    g[sel] = np.minimum(g[sel], d)
            else:
                f[sel] = smax(f[sel], -d, k)
        if self.falten is not None:
            f = f - self.falten(P)
        return (f, je_gruppe) if gruppen else f

    def gitter(self, lo, hi, h):
        """Feld auf einem regelmaessigen Gitter (Bausteine nur in ihrer Huelle ausgewertet)."""
        lo = np.asarray(lo, float)
        n = np.ceil((np.asarray(hi, float) - lo) / h).astype(int) + 1
        f = np.full(tuple(n), 10.0, dtype=np.float32)
        for b in self.bausteine:
            blo, bhi = b.huelle()
            rand = b.k_max() + 2 * h
            i0 = np.clip(np.floor((blo - rand - lo) / h).astype(int), 0, n - 1)
            i1 = np.clip(np.ceil((bhi + rand - lo) / h).astype(int) + 1, 1, n)
            schritt = max(1, int(3_000_000 // max(1, (i1[1] - i0[1]) * (i1[2] - i0[2]))))
            ys = lo[1] + h * np.arange(i0[1], i1[1])
            zs = lo[2] + h * np.arange(i0[2], i1[2])
            for a in range(i0[0], i1[0], schritt):
                e = min(a + schritt, i1[0])
                xs = lo[0] + h * np.arange(a, e)
                X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
                P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
                d = b.d(P)
                k = b.k_bei(P)
                block = f[a:e, i0[1]:i1[1], i0[2]:i1[2]].reshape(-1).astype(np.float64)
                block = smin(block, d, k) if b.art == "plus" else smax(block, -d, k)
                f[a:e, i0[1]:i1[1], i0[2]:i1[2]] = block.reshape(X.shape)
        if self.falten is not None:
            for a in range(0, n[0], 16):
                e = min(a + 16, n[0])
                X, Y, Z = np.meshgrid(lo[0] + h * np.arange(a, e), lo[1] + h * np.arange(n[1]),
                                      lo[2] + h * np.arange(n[2]), indexing="ij")
                P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
                nah = np.abs(f[a:e].reshape(-1)) < 0.05
                if nah.any():
                    blk = f[a:e].reshape(-1)
                    blk[nah] -= self.falten(P[nah]).astype(np.float32)
                    f[a:e] = blk.reshape(X.shape)
        return f, lo

    def gradient(self, P, eps=0.003):
        g = np.zeros_like(P)
        for i in range(3):
            e = np.zeros(3)
            e[i] = eps
            g[:, i] = (self.werte(P + e) - self.werte(P - e)) / (2 * eps)
        return g

    def auf_flaeche(self, V, schritte=2):
        """Ecken mit Newton-Schritten genau auf die Nullflaeche setzen."""
        for _ in range(schritte):
            f0 = self.werte(V)
            g = self.gradient(V)
            V = V - (f0 / np.maximum((g * g).sum(1), 1e-6))[:, None] * g
        return V

def surface_nets(f, lo, h):
    """Surface Nets: je Gitterzelle mit Vorzeichenwechsel eine Ecke (Mittel der Kantenschnittpunkte), je Gitterkante
    mit Vorzeichenwechsel ein Viereck aus den vier anliegenden Zellen. Liefert (Ecken (V, 3), Vierecke (Q, 4))."""
    n = np.array(f.shape)
    innen = f < 0
    zn = n - 1                                             # Zellen je Achse
    zid_all, punkt_all, kanten = [], [], []
    for achse in range(3):
        s0 = [slice(None)] * 3
        s1 = [slice(None)] * 3
        s0[achse], s1[achse] = slice(0, -1), slice(1, None)
        wechsel = innen[tuple(s0)] != innen[tuple(s1)]
        idx = np.nonzero(wechsel)
        I = np.stack(idx, axis=1)
        fa = f[tuple(s0)][idx].astype(np.float64)
        fb = f[tuple(s1)][idx].astype(np.float64)
        t = fa / (fa - fb)
        p = I.astype(np.float64)
        p[:, achse] += t
        punkt = lo + h * p
        o1, o2 = (achse + 1) % 3, (achse + 2) % 3
        zellen = []
        for d1, d2 in ((-1, -1), (0, -1), (0, 0), (-1, 0)):
            c = I.copy()
            c[:, o1] += d1
            c[:, o2] += d2
            zellen.append(c)
        gueltig = np.ones(len(I), bool)
        for c in zellen:
            gueltig &= np.all((c >= 0) & (c < zn), axis=1)
        ids = [((c[:, 0] * zn[1] + c[:, 1]) * zn[2] + c[:, 2])[gueltig] for c in zellen]
        drin = innen[tuple(s0)][idx][gueltig]
        quad = np.stack(ids, axis=1)
        quad[~drin] = quad[~drin][:, ::-1]
        kanten.append(quad)
        for z in ids:
            zid_all.append(z)
            punkt_all.append(punkt[gueltig])
    zid_all = np.concatenate(zid_all)
    punkt_all = np.concatenate(punkt_all)
    eindeutig, inv = np.unique(zid_all, return_inverse=True)
    summe = np.zeros((len(eindeutig), 3))
    np.add.at(summe, inv, punkt_all)
    anzahl = np.bincount(inv, minlength=len(eindeutig))
    V = summe / anzahl[:, None]
    Q = np.searchsorted(eindeutig, np.concatenate(kanten))
    return V, Q

def netz_glaetten(V, Q, feld, schritte=3, staerke=0.5):
    """Tangentiales Glaetten (gleichmaessigere Vierecke), danach wieder auf die Flaeche setzen."""
    kanten = np.concatenate([Q[:, [0, 1]], Q[:, [1, 2]], Q[:, [2, 3]], Q[:, [3, 0]]])
    for _ in range(schritte):
        summe = np.zeros_like(V)
        np.add.at(summe, kanten[:, 0], V[kanten[:, 1]])
        np.add.at(summe, kanten[:, 1], V[kanten[:, 0]])
        anz = np.bincount(kanten.ravel(), minlength=len(V))[:, None]
        delta = summe / np.maximum(anz, 1) - V
        g = feld.gradient(V)
        nrm = g / np.maximum(np.linalg.norm(g, axis=1, keepdims=True), 1e-9)
        delta -= nrm * (delta * nrm).sum(1, keepdims=True)
        V = feld.auf_flaeche(V + staerke * delta, schritte=1)
    return V

def netz_objekt(name, V, Q, mats):
    me = bpy.data.meshes.new(name)
    me.from_pydata(V.tolist(), [], Q.tolist())
    me.validate(clean_customdata=False)
    for m in mats:
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob

# ---------------- Form des Tyrannosaurus (erwachsenes Tier, etwa 12,3 m lang) ----------------
# Rumpf von der Schwanzspitze bis zur Schnauze als Profilkoerper (Seitenlinie oben/unten, Draufsicht-Breite),
# dazu Muskeln, Beine, Arme und der Unterkiefer als eigene Bausteine. Der Unterkiefer steht in der Bindepose
# 12 Grad offen; geschlossen liegen die Lippen aufeinander.
X_HINTEN, X_VORN = -7.30, 5.10
XS = np.linspace(X_HINTEN, X_VORN, int(round((X_VORN - X_HINTEN) / 0.01)) + 1)

def profil(pts, xs=XS):
    f = pchip(pts)
    return np.array([f(x) for x in xs])

RUMPF_OBEN = [(-7.30, 1.86), (-6.5, 2.07), (-5.5, 2.34), (-4.5, 2.61), (-3.5, 2.87), (-2.5, 3.09), (-1.5, 3.28),
              (-0.8, 3.40), (-0.2, 3.47), (0.4, 3.47), (1.0, 3.39), (1.6, 3.31), (2.2, 3.22), (2.65, 3.17),
              (3.05, 3.22), (3.40, 3.42), (3.68, 3.68), (3.90, 3.81), (4.08, 3.82), (4.35, 3.74), (4.65, 3.61),
              (4.90, 3.49), (5.05, 3.40), (5.12, 3.31)]
RUMPF_UNTEN = [(-7.30, 1.80), (-6.5, 1.91), (-5.5, 2.05), (-4.5, 2.17), (-3.5, 2.26), (-2.5, 2.31), (-1.5, 2.31),
               (-0.8, 2.20), (-0.3, 2.00), (0.15, 1.86), (0.6, 1.82), (1.2, 1.84), (1.8, 1.94), (2.3, 2.12),
               (2.7, 2.36), (3.1, 2.56), (3.45, 2.66), (3.68, 2.72), (3.82, 2.88), (3.95, 3.06), (4.3, 3.04),
               (4.7, 3.05), (4.95, 3.08), (5.12, 3.13)]
RUMPF_BREITE = [(-7.30, 0.035), (-6.5, 0.10), (-5.5, 0.17), (-4.5, 0.24), (-3.5, 0.31), (-2.5, 0.39), (-1.5, 0.48),
                (-0.8, 0.56), (0.0, 0.62), (0.6, 0.70), (1.2, 0.74), (1.8, 0.70), (2.3, 0.60), (2.7, 0.50),
                (3.1, 0.45), (3.45, 0.43), (3.70, 0.44), (3.95, 0.42), (4.15, 0.335), (4.45, 0.235), (4.75, 0.18),
                (5.0, 0.145), (5.12, 0.12)]
RUMPF_EXPO = [(-7.3, 2.3), (-1.0, 2.3), (0.5, 2.15), (2.5, 2.2), (3.3, 2.4), (3.8, 2.9), (4.4, 3.0), (5.1, 2.7)]
RUMPF_SCHIEF = [(-7.3, -0.05), (-3.0, -0.10), (-1.0, -0.10), (0.0, 0.05), (1.2, 0.08), (2.3, 0.02), (3.3, 0.0),
                (3.8, -0.12), (4.4, -0.22), (5.1, -0.20)]
BREITE_F = pchip(RUMPF_BREITE)
OBEN_F, UNTEN_F = pchip(RUMPF_OBEN), pchip(RUMPF_UNTEN)

# Unterkiefer (lokal, geschlossen), Drehpunkt im Kiefergelenk
KIEFER_GELENK = (3.80, 0.0, 3.02)
KIEFER_AUF = float(os.environ.get("KIEFER_AUF", "12"))  # Grad offen in der Bindepose
KIEFER_M = drehung("Y", KIEFER_AUF)
XJ = np.linspace(3.62, 5.05, 144)
KIEFER_OBEN = [(3.62, 2.98), (3.72, 3.01), (3.85, 3.025), (4.1, 3.03), (4.6, 3.035), (4.9, 3.05), (5.05, 3.07)]
KIEFER_UNTEN = [(3.62, 2.84), (3.72, 2.66), (3.88, 2.56), (4.1, 2.57), (4.4, 2.62), (4.7, 2.70), (4.92, 2.78),
                (5.05, 2.86)]

def kiefer_breite(x):
    if x <= 3.9:
        return float(np.interp(x, [3.62, 3.75, 3.9], [0.34, 0.40, 0.405]))
    return min(0.405, 1.04 * BREITE_F(x) - 0.04)

def kiefer_welt(p):
    """Punkt aus dem geschlossenen Kiefer (lokal) in die Bindepose (Welt)."""
    p0 = np.array(KIEFER_GELENK)
    return KIEFER_M @ (np.array(p, float) - p0) + p0

# Gelenke der Bindepose (linke Seite, y > 0); die rechte Seite ist gespiegelt
BEIN = {"huefte": (0.00, 0.40, 3.00), "knie": (0.50, 0.50, 1.86), "knoechel": (-0.08, 0.47, 0.78),
        "ballen": (0.14, 0.45, 0.13), "zehe": (0.62, 0.45, 0.05)}
ARM = {"schulter": (2.20, 0.40, 2.56), "ellbogen": (2.18, 0.55, 2.22), "handgelenk": (2.40, 0.52, 2.08),
       "hand": (2.53, 0.49, 2.02)}

def spiegel(p, sg):
    return (p[0], sg * p[1], p[2])

KRALLEN = []          # (Basis, Richtung, Laenge, Breite, Hoehe, Kruemmung, Knochen) fuer die Krallen

def bein_bausteine(sg):
    g = "bein_l" if sg > 0 else "bein_r"
    s = "l" if sg > 0 else "r"
    J = {k: np.array(spiegel(v, sg)) for k, v in BEIN.items()}
    teile = []
    femur = J["knie"] - J["huefte"]
    # Oberschenkel: grosse Muskelmasse am Becken, Kegel bis zum Knie
    teile.append(Ellipsoid((0.10, sg * 0.60, 2.45), (0.74, 0.38, 0.84), M=ausrichtung(femur, (1, 0, 0)),
                           gruppe=g, k=0.24))
    teile.append(Kegel(J["huefte"], J["knie"], 0.40, 0.25, gruppe=g, k=0.14))
    teile.append(Kugel(J["knie"] + np.array((0.03, 0, 0)), 0.23, gruppe=g, k=0.08))
    # Unterschenkel mit Wadenmuskel hinten oben
    teile.append(Kegel(J["knie"], J["knoechel"], 0.24, 0.145, gruppe=g, k=0.08))
    schien = J["knoechel"] - J["knie"]
    teile.append(Ellipsoid(J["knie"] + 0.34 * schien + np.array((-0.10, 0, -0.02)), (0.23, 0.21, 0.52),
                           M=ausrichtung(schien, (1, 0, 0)), gruppe=g, k=0.10))
    teile.append(Kugel(J["knoechel"], 0.15, gruppe=g, k=0.05))
    # Mittelfuss, Ballen, drei Zehen mit Polstern, kleine erste Zehe hinten innen
    teile.append(Kegel(J["knoechel"], J["ballen"], 0.14, 0.125, gruppe=g, k=0.05))
    teile.append(Ellipsoid(J["ballen"] + np.array((0.03, 0, -0.04)), (0.26, 0.22, 0.10), gruppe=g, k=0.06))
    for winkel, l1, l2, r0 in ((-24, 0.23, 0.19, 0.105), (0, 0.28, 0.23, 0.118), (22, 0.23, 0.19, 0.105)):
        w = math.radians(winkel)
        rich = np.array((math.cos(w), sg * math.sin(w), 0.0))
        p0 = J["ballen"] + np.array((0.02, 0, -0.01)) + rich * 0.03
        p1 = p0 + rich * l1 + np.array((0, 0, -0.03))
        p2 = p1 + rich * l2 + np.array((0, 0, -0.025))
        teile.append(Kegel(p0, p1, r0, r0 * 0.8, gruppe=g, k=0.03))
        teile.append(Kegel(p1, p2, r0 * 0.8, r0 * 0.62, gruppe=g, k=0.025))
        teile.append(Ellipsoid(p1 + np.array((0, 0, -0.03)), (0.07, 0.055, 0.04), gruppe=g, k=0.02))
        KRALLEN.append((p2 + rich * 0.02 + np.array((0, 0, 0.005)), rich + np.array((0, 0, -0.25)),
                        0.15 if winkel == 0 else 0.12, r0 * 1.15, r0 * 0.85, 0.35, "toe_" + s))
    teile.append(Kegel(np.array((-0.02, sg * 0.41, 0.36)), np.array((-0.10, sg * 0.39, 0.27)), 0.045, 0.035,
                       gruppe=g, k=0.03))
    KRALLEN.append((np.array((-0.115, sg * 0.385, 0.255)), np.array((-0.6, sg * -0.1, -0.8)), 0.06, 0.05, 0.04,
                    0.6, "foot_" + s))
    return teile

def arm_bausteine(sg):
    g = "arm_l" if sg > 0 else "arm_r"
    J = {k: np.array(spiegel(v, sg)) for k, v in ARM.items()}
    teile = [Kegel(J["schulter"], J["ellbogen"], 0.12, 0.08, gruppe=g, k=0.08),
             Kegel(J["ellbogen"], J["handgelenk"], 0.075, 0.058, gruppe=g, k=0.03),
             Kegel(J["handgelenk"], J["hand"], 0.058, 0.046, gruppe=g, k=0.02)]
    for dy, dz in ((0.025, -0.02), (-0.025, -0.035)):
        a = J["hand"] + np.array((0.0, sg * dy, 0.0))
        b = a + np.array((0.11, sg * dy * 0.6, dz - 0.04))
        teile.append(Kegel(a, b, 0.036, 0.03, gruppe=g, k=0.015))
        KRALLEN.append((b + (b - a) / np.linalg.norm(b - a) * 0.015, b - a, 0.075, 0.034, 0.03, 0.9,
                        "hand_" + ("l" if sg > 0 else "r")))
    return teile

# Auge: Mittelpunkt und Blickrichtung (links); Augapfel-Radius
AUGE_R = 0.055
AUGE_RICHTUNG = np.array((0.55, 0.83, 0.05)) / np.linalg.norm((0.55, 0.83, 0.05))
AUGE_MITTE = np.array((4.0, 0.318, 3.60))

def t_rex_feld(fein=False):
    KRALLEN.clear()
    teile = []
    # Rumpf, Hals, Kopf (Oberschaedel) und Schwanz
    teile.append(Profil(XS, profil(RUMPF_OBEN), profil(RUMPF_UNTEN), profil(RUMPF_BREITE), profil(RUMPF_EXPO),
                        profil(RUMPF_SCHIEF), rund_hinten=0.35, rund_vorn=0.22, gruppe="rumpf"))
    for sg in (1, -1):
        # Halsmuskeln, Kiefermuskeln hinter dem Auge, Jochbeinleiste, Brauenwulst, Hoecker vor dem Auge, Schulter
        teile.append(Ellipsoid((3.22, sg * 0.22, 3.02), (0.20, 0.17, 0.46), M=ausrichtung((0.9, 0, 0.42), (0, 0, 1)),
                               gruppe="rumpf", k=0.10))
        teile.append(Ellipsoid((3.70, sg * 0.34, 3.46), (0.20, 0.12, 0.17), gruppe="rumpf", k=0.09))
        teile.append(Ellipsoid((3.98, sg * 0.38, 3.22), (0.22, 0.05, 0.05), gruppe="rumpf", k=0.06))
        teile.append(Ellipsoid((3.93, sg * 0.315, 3.69), (0.11, 0.07, 0.045), gruppe="rumpf", k=0.07))
        teile.append(Ellipsoid((4.04, sg * 0.29, 3.675), (0.19, 0.065, 0.045), gruppe="rumpf", k=0.08))
        teile.append(Ellipsoid((4.20, sg * 0.225, 3.725), (0.10, 0.05, 0.03), gruppe="rumpf", k=0.07))
        teile.append(Ellipsoid((2.20, sg * 0.50, 2.74), (0.30, 0.12, 0.30), gruppe="rumpf", k=0.10))
    for sg in (1, -1):
        teile += bein_bausteine(sg)
        teile += arm_bausteine(sg)
    # Unterkiefer: an den Lippen schmaler Uebergang (Mundspalte bleibt offen), zum Hals hin weich
    kj = lambda P: 0.022 + 0.07 * np.clip((3.0 - P[:, 2]) / 0.15, 0, 1)
    teile.append(Profil(XJ, profil(KIEFER_OBEN, XJ), profil(KIEFER_UNTEN, XJ), [kiefer_breite(x) for x in XJ],
                        [2.5] * len(XJ), [0.30] * len(XJ), rund_hinten=0.10, rund_vorn=0.10,
                        drehpunkt=KIEFER_GELENK, M=KIEFER_M, gruppe="kiefer", k=kj))
    # Mundhoehle: Gaumen oben, Mulde im Unterkiefer, Rachen; danach die Zunge
    teile.append(Ellipsoid((4.25, 0, 3.035), (0.68, 0.16, 0.06), gruppe="mund", art="minus", k=0.02))
    teile.append(Ellipsoid(kiefer_welt((4.25, 0, 3.075)), (0.68, 0.15, 0.085), M=KIEFER_M, gruppe="mund",
                           art="minus", k=0.02))
    teile.append(Ellipsoid((3.80, 0, 3.03), (0.22, 0.13, 0.07), gruppe="mund", art="minus", k=0.03))
    teile.append(Ellipsoid(kiefer_welt((4.12, 0, 2.995)), (0.50, 0.11, 0.04), M=KIEFER_M, gruppe="kiefer", k=0.02))
    # Augenhoehlen und Nasenloecher
    for sg in (1, -1):
        m = AUGE_MITTE * np.array((1, sg, 1))
        r = AUGE_RICHTUNG * np.array((1, sg, 1))
        teile.append(Ellipsoid(m + r * 0.05, (0.045, 0.068, 0.07), M=ausrichtung(r, (0, 0, 1)), gruppe="auge",
                               art="minus", k=0.022))
        teile.append(Ellipsoid((4.36, sg * (BREITE_F(4.36) * 0.98 + 0.038), 3.41), (0.28, 0.05, 0.13), gruppe="mulde",
                               art="minus", k=0.10))
        teile.append(Ellipsoid((5.00, sg * 0.08, 3.285), (0.042, 0.024, 0.02),
                               M=ausrichtung((0.5, sg * 0.5, 0.7), (1, 0, 0)), gruppe="nase", art="minus", k=0.012))
    return Feld(teile, falten=hautfalten if fein else None)

def hautfalten(P):
    """Feine Hautfalten (nur im feinen Netz fuer die Normal-Textur): Querfalten an Kehle und Halsunterseite,
    an Knie, Knoechel und Zehen, Laengsfalten an der Schwanzunterseite."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    out = np.zeros(len(P))
    kehle = np.clip((x - 2.6) / 0.3, 0, 1) * np.clip((3.95 - x) / 0.2, 0, 1) * np.clip((UNTEN_F_V(x) + 0.28 - z) / 0.12, 0, 1)
    out += 0.006 * kehle * np.sin(2 * np.pi * x / 0.085 + 3 * np.sin(y * 9))
    for sg in (1, -1):
        for gel, r, wl in (("knie", 0.32, 0.07), ("knoechel", 0.2, 0.05), ("ballen", 0.25, 0.045)):
            c = np.array(spiegel(BEIN[gel], sg))
            nah = np.clip(1 - np.linalg.norm(P - c, axis=1) / r, 0, 1)
            out += 0.004 * nah * np.sin(2 * np.pi * z / wl + 2 * np.sin(x * 11))
    schwanz = np.clip((-0.6 - x) / 0.5, 0, 1) * np.clip((UNTEN_F_V(x) + 0.12 - z) / 0.1, 0, 1)
    out += 0.003 * schwanz * np.sin(2 * np.pi * y / 0.06)
    return out

_UNTEN_DICHT = profil(RUMPF_UNTEN)
def UNTEN_F_V(x):
    return np.interp(x, XS, _UNTEN_DICHT)

# ---------------- Zaehne, Augen, Krallen (eigene Teile, starr an ihrem Knochen) ----------------
def aussen_y(prof, x, z, lokal=False):
    """Seitliche Lage der Oberflaeche eines Profilkoerpers bei (x, z) per Halbierung (lokale Koordinaten)."""
    lo, hi = 0.0, 1.2
    for _ in range(30):
        m = 0.5 * (lo + hi)
        P = np.array([[x, m, z]])
        if lokal and prof.M is not None:
            P = (P - prof.p0) @ prof.M.T + prof.p0
        d = prof.d(P)[0]
        lo, hi = (m, hi) if d < 0 else (lo, m)
    return lo

def zahn(basis, runter, hinten, laenge, breite, mi, ringe=9, segs=8):
    """Gebogener Zahn: von der Basis in Richtung 'runter', zur Spitze nach 'hinten' gekruemmt, ovaler Querschnitt
    (vorn-hinten breiter als seitlich)."""
    bm = bmesh.new()
    lay = bm.verts.layers.float.new("spitze")
    basis, d, h = Vector(basis), Vector(runter).normalized(), Vector(hinten).normalized()
    reihen = []
    for i in range(ringe - 1):
        t = i / (ringe - 1)
        mitte = basis + d * (laenge * t) + h * (laenge * 0.22 * t * t)
        tang = (d + h * 0.44 * t).normalized()
        hh = (h - tang * h.dot(tang)).normalized()
        ss = tang.cross(hh)
        a = breite / 2 * (1 - t) ** 0.8
        b = a * 0.62
        reihen.append([bm.verts.new(mitte + hh * (a * math.cos(w)) + ss * (b * math.sin(w)))
                       for w in np.linspace(0, 2 * math.pi, segs, endpoint=False)])
        for v in reihen[-1]:
            v[lay] = t
    spitze = bm.verts.new(basis + d * laenge + h * (laenge * 0.22))
    spitze[lay] = 1.0
    for r0, r1 in zip(reihen, reihen[1:]):
        for k in range(segs):
            bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
    for k in range(segs):
        bm.faces.new((reihen[-1][k], reihen[-1][(k + 1) % segs], spitze))
    bm.faces.new(reihen[0][::-1])
    for f in bm.faces:
        f.material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm

def zahn_laenge(x):
    """Kronenlaenge (sichtbar plus 3 cm in der Lippe) entlang des Kiefers: vorn mittel, Mitte am groessten."""
    return float(np.interp(x, [3.95, 4.15, 4.45, 4.7, 4.95, 5.1], [0.07, 0.11, 0.15, 0.14, 0.11, 0.08]))

ZAEHNE = []                    # (Ort, Knochen) zum Pruefen
def zaehne(feld):
    """Oben 15, unten 14 Zaehne je Seite, unterschiedlich lang (Ersatzzaehne) und leicht verdreht. Die Basis sitzt
    5 cm tief im Zahnfleisch hinter der Lippe; oben reichen sie geschlossen aussen am Unterkiefer vorbei, unten
    sitzen sie weiter innen."""
    rng = np.random.default_rng(11)
    rumpf = feld.bausteine[0]
    kiefer = next(b for b in feld.bausteine if b.gruppe == "kiefer" and isinstance(b, Profil))
    oben, unten = bmesh.new(), bmesh.new()
    for sg in (1, -1):
        for x in np.linspace(3.98, 5.05, 15):
            zl = float(np.interp(x, rumpf.xs, rumpf.zb))
            y = aussen_y(rumpf, x, zl + 0.05) - 0.035
            sichtbar = 0.78 * (zahn_laenge(x) - 0.03) * rng.uniform(0.72, 1.08)
            basis = (x, sg * y, zl + 0.05)
            runter = (rng.normal(0, 0.04), sg * 0.06 + rng.normal(0, 0.03), -1)
            einfuegen(oben, zahn(basis, runter, (-1, 0, 0.0), sichtbar + 0.05, (sichtbar + 0.05) * 0.40, 0))
            ZAEHNE.append((basis, "head"))
        for x in np.linspace(4.02, 4.98, 14):
            zl = float(np.interp(x, kiefer.xs, kiefer.zt))
            y = aussen_y(kiefer, x, zl - 0.05, lokal=True) - 0.045
            sichtbar = 0.78 * (0.9 * zahn_laenge(x) - 0.03) * rng.uniform(0.72, 1.08)
            basis = kiefer_welt(np.array((x, sg * y, zl - 0.05)))
            runter = KIEFER_M @ np.array((rng.normal(0, 0.04), -sg * 0.05 + rng.normal(0, 0.03), 1.0))
            hinten = KIEFER_M @ np.array((-1.0, 0, 0))
            einfuegen(unten, zahn(tuple(basis), tuple(runter), tuple(hinten), sichtbar + 0.05, (sichtbar + 0.05) * 0.40, 0))
            ZAEHNE.append((tuple(basis), "jaw"))
    return oben, unten

def kralle(basis, richtung, laenge, breite, hoehe, kruemmung, mi, ringe=8, segs=10):
    """Kralle: elliptischer Querschnitt (breite x hoehe), zur Spitze schmaler, nach unten gekruemmt."""
    bm = bmesh.new()
    lay = bm.verts.layers.float.new("spitze")
    d = Vector(richtung).normalized()
    seite = d.cross(Vector((0, 0, 1)))
    if seite.length < 1e-4:
        seite = Vector((0, 1, 0))
    seite.normalize()
    auf = seite.cross(d).normalized()
    reihen = []
    for i in range(ringe - 1):
        t = i / (ringe - 1)
        w = kruemmung * t
        tang = (d * math.cos(w) - auf * math.sin(w)).normalized()
        rad = laenge / kruemmung
        mitte = Vector(basis) + d * (rad * math.sin(w)) - auf * (rad * (1 - math.cos(w)))
        oben_v = seite.cross(tang).normalized()
        f = (1 - t) ** 0.7
        reihen.append([bm.verts.new(mitte + seite * (breite / 2 * f * math.cos(a)) + oben_v * (hoehe / 2 * f * math.sin(a)))
                       for a in np.linspace(0, 2 * math.pi, segs, endpoint=False)])
        for v in reihen[-1]:
            v[lay] = t
    w = kruemmung
    rad = laenge / max(kruemmung, 1e-6)
    spitze = bm.verts.new(Vector(basis) + d * (rad * math.sin(w)) - auf * (rad * (1 - math.cos(w))))
    spitze[lay] = 1.0
    for r0, r1 in zip(reihen, reihen[1:]):
        for k in range(segs):
            bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
    for k in range(segs):
        bm.faces.new((reihen[-1][k], reihen[-1][(k + 1) % segs], spitze))
    bm.faces.new(reihen[0][::-1])
    for fc in bm.faces:
        fc.material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm

def textur_auge(n=512):
    """Auge von vorn (planare Abbildung des Augapfels, Mitte = Blickrichtung): goldbraune Iris mit feiner Maserung
    und Flecken, dunkler Rand, runde Pupille, ausserhalb dunkle Haut. Radius r im Bild <-> Winkel asin(2r) vom Pol."""
    rng = np.random.default_rng(5)
    u = (np.arange(n) + 0.5) / n - 0.5
    X, Y = np.meshgrid(u, u, indexing="ij")
    th = np.arcsin(np.clip(2 * np.hypot(X, Y), 0, 1))
    ph = np.arctan2(Y, X)
    pupille = 0.19 * (1 + 0.10 * np.sin(ph) ** 2)
    iris = 0.62
    maserung = np.zeros_like(X)
    for k, a in ((17, 0.5), (29, 0.3), (53, 0.2)):
        maserung += a * np.sin(ph * k + rng.random() * 6 + 4 * th + 2 * np.sin(ph * 3))
    flecken = np.zeros_like(X)
    for _ in range(45):
        p0, t0, r0 = rng.random() * 2 * math.pi, 0.22 + rng.random() * 0.36, 0.02 + 0.035 * rng.random()
        d = np.hypot(np.angle(np.exp(1j * (ph - p0))) * np.sin(th), th - t0)
        flecken += np.clip(1 - d / r0, 0, 1) * (rng.random() - 0.4)
    t = np.clip((th - pupille) / (iris - pupille), 0, 1)
    innen, aussen, rand_f = np.array(hexf("#6e4313")), np.array(hexf("#a7782f")), np.array(hexf("#2e1c0b"))
    farbe = innen[None, None, :] * (1 - t[..., None]) + aussen[None, None, :] * t[..., None]
    farbe *= (1 + 0.07 * maserung + 0.3 * flecken)[..., None]
    farbe *= (0.7 + 0.3 * np.clip((th - pupille) / 0.06, 0, 1))[..., None]        # dunkler Saum an der Pupille
    rand = np.clip(1 - np.abs(th - iris + 0.03) / 0.08, 0, 1)
    farbe = farbe * (1 - 0.85 * rand[..., None]) + rand_f * 0.85 * rand[..., None]
    farbe[th < pupille] = 0.002
    farbe[th > iris + 0.03] = np.array(hexf("#241a12"))
    return bild("T_TRex_Auge", np.clip(farbe, 0, 1) ** (1 / 2.2), farbe=True)

def augen():
    bm = bmesh.new()
    for sg in (1, -1):
        k = bmesh.new()
        bmesh.ops.create_uvsphere(k, u_segments=48, v_segments=24, radius=AUGE_R)
        uvl = k.loops.layers.uv.new("UVMap")
        for f in k.faces:                        # planar von vorn; die Rueckseite liegt am Bildrand
            for l in f.loops:
                x, y, z = l.vert.co
                r = math.hypot(x, y)
                if z >= 0:
                    l[uvl].uv = (0.5 + 0.5 * x / AUGE_R, 0.5 + 0.5 * y / AUGE_R)
                else:
                    l[uvl].uv = (0.5 + 0.497 * x / max(r, 1e-9), 0.5 + 0.497 * y / max(r, 1e-9))
        r = AUGE_RICHTUNG * np.array((1, sg, 1))
        M = Matrix(ausrichtung(r, (0, 0, 1)).tolist()).to_4x4()
        bmesh.ops.transform(k, matrix=Matrix.Translation(Vector(AUGE_MITTE * np.array((1, sg, 1)))) @ M,
                            verts=k.verts)
        einfuegen(bm, k)
    return bm

def kleinteile(feld):
    """Zaehne, Augen und Krallen als eigene Objekte mit Material und dem Knochen, an dem sie haengen."""
    m_zahn = material("Zahn", hexf("#d9ceb2"), rauheit=0.32, lack=0.3, lack_rau=0.2)
    m_kralle = material("Kralle", hexf("#2d2924"), rauheit=0.38, lack=0.2, lack_rau=0.25)
    m_auge = material("Auge", hexf("#b8781c"), rauheit=0.05, lack=1.0, lack_rau=0.0, farb_bild=textur_auge())
    oben, unten = zaehne(feld)
    teile = [(objekt("Zaehne_oben", oben, [m_zahn], glatt=True), "head"),
             (objekt("Zaehne_unten", unten, [m_zahn], glatt=True), "jaw"),
             (objekt("Augen", augen(), [m_auge], glatt=True), "head")]
    for basis, richtung, laenge, breite, hoehe, kr, knochen in KRALLEN:
        teile.append((objekt("Kralle_" + knochen, kralle(tuple(basis), tuple(richtung), laenge, breite, hoehe, kr, 0),
                             [m_kralle], glatt=True), knochen))
    return teile

# ---------------- Skelett fuer Unreal Engine 5 und weiche Gewichte ----------------
# 36 Knochen: root am Boden, pelvis an der Huefte, Wirbelsaeule (spine_01-03), Hals (neck_01-03), head, jaw,
# Schwanz (tail_01-12), je Bein thigh/calf/foot/toe, je Arm upperarm/lowerarm/hand.
SCHWANZ = [(0.0, 3.08), (-0.55, 3.06), (-1.12, 3.00), (-1.70, 2.91), (-2.30, 2.80), (-2.90, 2.68), (-3.50, 2.56),
           (-4.10, 2.44), (-4.70, 2.33), (-5.30, 2.22), (-5.90, 2.11), (-6.55, 2.00), (-7.15, 1.88)]
ACHSE = [("pelvis", (0.0, 0, 3.05), (0.62, 0, 3.10)), ("spine_01", (0.62, 0, 3.10), (1.35, 0, 3.08)),
         ("spine_02", (1.35, 0, 3.08), (2.05, 0, 3.00)), ("spine_03", (2.05, 0, 3.00), (2.65, 0, 2.94)),
         ("neck_01", (2.65, 0, 2.94), (3.08, 0, 3.03)), ("neck_02", (3.08, 0, 3.03), (3.42, 0, 3.20)),
         ("neck_03", (3.42, 0, 3.20), (3.72, 0, 3.36)), ("head", (3.72, 0, 3.36), (4.95, 0, 3.40))]

def knochen_liste():
    """(Name, Kopf, Ende, Eltern, verbunden) in Reihenfolge Eltern vor Kindern."""
    L = [("root", (0, 0, 0), (0, 0, 0.5), None, False)]
    eltern = "root"
    for name, a, b in ACHSE:
        L.append((name, a, b, eltern, eltern != "root"))
        eltern = name
    L.append(("jaw", KIEFER_GELENK, tuple(kiefer_welt((4.95, 0, 3.02))), "head", False))
    for i in range(12):
        (x0, z0), (x1, z1) = SCHWANZ[i], SCHWANZ[i + 1]
        L.append((f"tail_{i + 1:02d}", (x0, 0, z0 if i else 3.05), (x1, 0, z1), "pelvis" if i == 0 else f"tail_{i:02d}",
                  i > 0))
    for sg, s in ((1, "l"), (-1, "r")):
        B = {k: spiegel(v, sg) for k, v in BEIN.items()}
        L += [(f"thigh_{s}", B["huefte"], B["knie"], "pelvis", False),
              (f"calf_{s}", B["knie"], B["knoechel"], f"thigh_{s}", True),
              (f"foot_{s}", B["knoechel"], B["ballen"], f"calf_{s}", True),
              (f"toe_{s}", B["ballen"], B["zehe"], f"foot_{s}", True)]
        A = {k: spiegel(v, sg) for k, v in ARM.items()}
        L += [(f"upperarm_{s}", A["schulter"], A["ellbogen"], "spine_03", False),
              (f"lowerarm_{s}", A["ellbogen"], A["handgelenk"], f"upperarm_{s}", True),
              (f"hand_{s}", A["handgelenk"], A["hand"], f"lowerarm_{s}", True)]
    return L

def skelett():
    daten = bpy.data.armatures.new(NAME + "_Skelett")
    arm = bpy.data.objects.new("Armature", daten)      # Unreal uebernimmt einen Knoten namens "Armature" nicht als Knochen
    scene.collection.objects.link(arm)
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name, a, b, eltern, verb in knochen_liste():
        k = daten.edit_bones.new(name)
        k.head, k.tail = a, b
        richtung = Vector(b) - Vector(a)
        k.align_roll((0, 0, 1) if abs(richtung.normalized().z) < 0.7 else (1, 0, 0))
        if eltern:
            k.parent = daten.edit_bones[eltern]
            k.use_connect = verb
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm

def achs_gewichte(x):
    """Gewichte entlang der Koerperachse (Schwanzspitze bis Kopf) aus der x-Lage: innen 1, an den Gelenken
    weicher Uebergang; der Schaedel ist starr."""
    teile = [(f"tail_{12 - i:02d}", SCHWANZ[12 - i][0], SCHWANZ[11 - i][0]) for i in range(12)]
    teile += [(n, a[0], b[0]) for n, a, b in ACHSE]
    teile[-2] = ("neck_03", teile[-2][1], 3.68)
    teile[-1] = ("head", 3.68, teile[-1][2])
    grenzen = [teile[i][2] for i in range(len(teile) - 1)]
    r = [0.08 if teile[i + 1][0] == "head" else
         min(0.18, 0.35 * (teile[i][2] - teile[i][1]), 0.35 * (teile[i + 1][2] - teile[i + 1][1]))
         for i in range(len(grenzen))]
    W = {}
    for i, (n, a, b) in enumerate(teile):
        w = np.ones_like(x)
        if i > 0:
            w = w * np.clip((x - (grenzen[i - 1] - r[i - 1])) / (2 * r[i - 1]), 0, 1)
        if i < len(teile) - 1:
            w = w * np.clip(((grenzen[i] + r[i]) - x) / (2 * r[i]), 0, 1)
        W[n] = w
    return W

def ketten_gewichte(P, glieder, sigma):
    """Weiche Zuordnung zu den Gliedern einer Kette ueber den Abstand zu den Knochenstrecken."""
    D = []
    for name, a, b in glieder:
        a, b = np.array(a), np.array(b)
        ab = b - a
        t = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
        D.append(np.linalg.norm(P - (a + t[:, None] * ab), axis=1))
    D = np.stack(D, 1)
    E = np.exp(-(D - D.min(1, keepdims=True)) / sigma)
    E /= E.sum(1, keepdims=True)
    return {name: E[:, i] for i, (name, a, b) in enumerate(glieder)}

def gewichte(V, feld):
    """Je Ecke bis zu 4 Knochen mit Summe 1. Erst die Zugehoerigkeit zu Koerperteilen (weiches Minimum der
    Abstaende je Gruppe), dann innerhalb des Teils die Kette (Achse nach x, Beine und Arme nach Abstand)."""
    _, G = feld.werte(V, gruppen=True)
    gruppen = ["rumpf", "kiefer", "bein_l", "bein_r", "arm_l", "arm_r"]
    tau = np.array([0.06, 0.02, 0.07, 0.07, 0.035, 0.035])
    D = np.stack([G.get(g, np.full(len(V), 10.0)) for g in gruppen], 1)
    c = np.exp(-(D - D.min(1, keepdims=True)) / tau)
    c /= c.sum(1, keepdims=True)
    W = {}
    def dazu(wd, faktor):
        for n, w in wd.items():
            W[n] = W.get(n, 0) + w * faktor
    dazu(achs_gewichte(V[:, 0]), c[:, 0])
    dazu({"jaw": np.ones(len(V))}, c[:, 1])
    for i, (sg, s) in enumerate(((1, "l"), (-1, "r"))):
        B = {k: np.array(spiegel(v, sg)) for k, v in BEIN.items()}
        dazu(ketten_gewichte(V, [(f"thigh_{s}", B["huefte"], B["knie"]), (f"calf_{s}", B["knie"], B["knoechel"]),
                                 (f"foot_{s}", B["knoechel"], B["ballen"]), (f"toe_{s}", B["ballen"], B["zehe"])],
                             0.05), c[:, 2 + i])
        A = {k: np.array(spiegel(v, sg)) for k, v in ARM.items()}
        dazu(ketten_gewichte(V, [(f"upperarm_{s}", A["schulter"], A["ellbogen"]),
                                 (f"lowerarm_{s}", A["ellbogen"], A["handgelenk"]),
                                 (f"hand_{s}", A["handgelenk"], A["hand"] + (A["hand"] - A["handgelenk"]))], 0.025),
             c[:, 4 + i])
    namen = list(W)
    M = np.stack([W[n] for n in namen], 1)
    M[M < 0.01] = 0
    if M.shape[1] > 4:
        schwelle = -np.sort(-M, axis=1)[:, 3:4]
        M[M < schwelle] = 0
    M /= np.maximum(M.sum(1, keepdims=True), 1e-9)
    return namen, M

def gewichte_setzen(ob, namen, M):
    for j, n in enumerate(namen):
        idx = np.nonzero(M[:, j] > 0)[0]
        if len(idx) == 0:
            continue
        vg = ob.vertex_groups.get(n) or ob.vertex_groups.new(name=n)
        for i, w in zip(idx.tolist(), M[idx, j].tolist()):
            vg.add([i], w, "REPLACE")

def starr(ob, knochen):
    vg = ob.vertex_groups.new(name=knochen)
    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")

# ---------------- Animationen: Stehen, Laufen, Bruellen (berechnet, 30 Bilder je Sekunde, auf der Stelle) ----------------
# Jede Pose entsteht als absolute Drehung je Knochen gegenueber der Bindepose (Vorwaertskinematik fuer Wirbelsaeule,
# Hals, Schwanz und Arme, analytische Zwei-Knochen-IK fuer die Beine). Daraus werden die lokalen Knochenmatrizen.
def rot(achse, grad):
    return Matrix.Rotation(math.radians(grad), 3, achse)

def glatt(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)

class Poser:
    def __init__(self, arm):
        knochen = arm.data.bones
        self.namen = [b.name for b in knochen]
        self.eltern = {b.name: (b.parent.name if b.parent else None) for b in knochen}
        self.R = {b.name: b.matrix_local.copy() for b in knochen}
        self.kopf = {b.name: b.head_local.copy() for b in knochen}
        self.ende = {b.name: b.tail_local.copy() for b in knochen}

    def laenge(self, n):
        return (self.ende[n] - self.kopf[n]).length

    def loesen(self, D, becken=(0, 0, 0)):
        """D: Knochen -> absolute Drehung (Welt) gegenueber der Bindepose; fehlende Knochen drehen mit den Eltern.
        Liefert die lokalen Matrizen (matrix_basis) und die Lage der Gelenke."""
        kopf, Deff, P = {}, {}, {}
        for n in self.namen:
            p = self.eltern[n]
            Deff[n] = D.get(n, Deff[p] if p else Matrix.Identity(3))
            kopf[n] = self.kopf[n].copy() if p is None else kopf[p] + Deff[p] @ (self.kopf[n] - self.kopf[p])
            if n == "pelvis":
                kopf[n] = kopf[n] + Vector(becken)
            P[n] = Matrix.Translation(kopf[n]) @ (Deff[n] @ self.R[n].to_3x3()).to_4x4()
        B = {}
        for n in self.namen:
            p = self.eltern[n]
            B[n] = (self.R[n].inverted() @ P[n] if p is None
                    else (self.R[p].inverted() @ self.R[n]).inverted() @ P[p].inverted() @ P[n])
        return B, kopf

    def huefte(self, s, Dp, becken):
        return self.kopf["pelvis"] + Vector(becken) + Dp @ (self.kopf[f"thigh_{s}"] - self.kopf["pelvis"])

def frame_drehung(d0, n0, d1, n1):
    """Drehung, die die Richtung d0 (mit Ebenennormale n0) auf d1 (mit n1) bringt."""
    def basis(d, n):
        d = d.normalized()
        n = (n - d * n.dot(d)).normalized()
        return Matrix((d, n, d.cross(n))).transposed()
    return basis(d1, n1) @ basis(d0, n0).transposed()

def bein_ik(po, s, H, ballen, alpha, zehe):
    """Bein mit festem Ziel fuer das Zehengrundgelenk (ballen). alpha: Neigung des Mittelfusses gegen die Senkrechte,
    zehe: Neigung der Zehen gegen die Waagrechte (positiv = Spitze unten), beides in Grad. Das Knie beugt nach vorn.
    Liefert die absoluten Drehungen der vier Beinknochen."""
    L1, L2, L3, L4 = (po.laenge(f"{k}_{s}") for k in ("thigh", "calf", "foot", "toe"))
    f, up = Vector((1, 0, 0)), Vector((0, 0, 1))
    a = math.radians(alpha)
    oben = (-f * math.sin(a) + up * math.cos(a))
    A = ballen + oben * L3
    d = A - H
    if d.length > L1 + L2 - 0.01:
        A = H + d.normalized() * (L1 + L2 - 0.01)
        ballen = A - oben * L3
        d = A - H
    dl = d.length
    u = d / dl
    hint = (f - u * f.dot(u)).normalized()
    aa = (L1 * L1 - L2 * L2 + dl * dl) / (2 * dl)
    K = H + u * aa + hint * math.sqrt(max(L1 * L1 - aa * aa, 0.0))
    z = math.radians(zehe)
    T = ballen + (f * math.cos(z) - up * math.sin(z)) * L4
    R = {k: po.kopf[f"{k}_{s}"] for k in ("thigh", "calf", "foot", "toe")}
    R_T = po.ende[f"toe_{s}"]
    n0 = (R["calf"] - R["thigh"]).cross(R["foot"] - R["calf"])
    n1 = (K - H).cross(A - K)
    return {f"thigh_{s}": frame_drehung(R["calf"] - R["thigh"], n0, K - H, n1),
            f"calf_{s}": frame_drehung(R["foot"] - R["calf"], n0, A - K, n1),
            f"foot_{s}": frame_drehung(R["toe"] - R["foot"], n0, ballen - A, n1),
            f"toe_{s}": frame_drehung(R_T - R["toe"], n0, T - ballen, n1)}

def ruhe_fuss(sg):
    b = BEIN["ballen"]
    return Vector((b[0], sg * b[1], b[2]))

ALPHA_RUHE, ZEHE_RUHE = 18.7, 9.5

def pose(po, becken, Dp, wirbel, hals, kopf_abs, kiefer, schwanz, arme, fuesse):
    """Eine ganze Pose. wirbel/hals/schwanz: Listen (gier, nick) je Knochen in Grad, relativ zum Vorgaenger;
    kopf_abs: (gier, nick) des Kopfs in Welt; kiefer: Oeffnung in Grad (0 = geschlossen);
    arme: {Seite: (nick_oben, nick_unten)}; fuesse: {Seite: (ballen, alpha, zehe)}."""
    D = {"pelvis": Dp}
    acc = Dp
    for n, (g, k) in zip(("spine_01", "spine_02", "spine_03"), wirbel):
        acc = acc @ rot("Z", g) @ rot("Y", k)
        D[n] = acc
    for n, (g, k) in zip(("neck_01", "neck_02", "neck_03"), hals):
        acc = acc @ rot("Z", g) @ rot("Y", k)
        D[n] = acc
    D["head"] = rot("Z", kopf_abs[0]) @ rot("Y", kopf_abs[1])
    D["jaw"] = D["head"] @ rot("Y", kiefer - KIEFER_AUF)
    acc = Dp
    for i, (g, k) in enumerate(schwanz):
        acc = acc @ rot("Z", g) @ rot("Y", k)
        D[f"tail_{i + 1:02d}"] = acc
    for s, (o, u) in arme.items():
        D[f"upperarm_{s}"] = D["spine_03"] @ rot("Y", o)
        D[f"lowerarm_{s}"] = D[f"upperarm_{s}"] @ rot("Y", u)
    for s, (ballen, alpha, zehe) in fuesse.items():
        D.update(bein_ik(po, s, po.huefte(s, Dp, becken), ballen, alpha, zehe))
    return po.loesen(D, becken)[0]

def anim_stehen(po, n=120):
    """Stehen (4 s, Schleife): Atmen, langsames Umsehen, Schwanz pendelt leicht, Kiefer atmet mit."""
    bilder = []
    for i in range(n + 1):
        p = 2 * math.pi * i / n
        becken = (0, 0.02 * math.sin(p), -0.03 + 0.012 * math.sin(2 * p))
        Dp = rot("Z", 1.2 * math.sin(p)) @ rot("Y", 0.6 * math.sin(2 * p + 0.5))
        wirbel = [(-0.4 * math.sin(p), 0.5 * math.sin(2 * p))] * 3
        hals = [(2.5 * math.sin(p - 0.4), -0.8 * math.sin(2 * p)), (3.0 * math.sin(p - 0.5), 0.0),
                (3.0 * math.sin(p - 0.6), 0.5 * math.sin(2 * p + 1))]
        kopf_abs = (12 * math.sin(p - 0.7), -3 + 4 * math.sin(2 * p + 1.2))
        kiefer = 1.5 + 1.5 * math.sin(2 * p)
        schwanz = [(0.9 * math.sin(p - 0.15 * k), 0.15 * math.sin(2 * p - 0.2 * k)) for k in range(12)]
        arme = {"l": (4 * math.sin(2 * p), 3 * math.sin(2 * p + 0.5)), "r": (4 * math.sin(2 * p + 0.3), 3 * math.sin(2 * p + 0.8))}
        fuesse = {s: (ruhe_fuss(sg), ALPHA_RUHE, ZEHE_RUHE) for s, sg in (("l", 1), ("r", -1))}
        bilder.append(pose(po, becken, Dp, wirbel, hals, kopf_abs, kiefer, schwanz, arme, fuesse))
    return bilder

LAUF_SCHRITT, LAUF_DAUER = 2.0, 1.8         # Meter je Standphase, Sekunden je Doppelschritt (etwa 1,8 m/s)

def fuss_lauf(psi, sg):
    beta, hub = 0.62, 0.40
    x0 = ruhe_fuss(sg).x + 0.10
    if psi < beta:
        t = psi / beta
        x = x0 + LAUF_SCHRITT / 2 - LAUF_SCHRITT * t
        z = ruhe_fuss(sg).z
        alpha = ALPHA_RUHE + 26 * max(0.0, (t - 0.55) / 0.45) ** 2
        zehe = ZEHE_RUHE
    else:
        t = (psi - beta) / (1 - beta)
        x = x0 - LAUF_SCHRITT / 2 + LAUF_SCHRITT * glatt(t)
        z = ruhe_fuss(sg).z + hub * math.sin(math.pi * t) ** 1.3
        alpha = ALPHA_RUHE + 26 * (1 - t) ** 2 + 8 * math.sin(math.pi * t)
        zehe = ZEHE_RUHE + 28 * math.sin(math.pi * t)
    return Vector((x, ruhe_fuss(sg).y, z)), alpha, zehe

def anim_laufen(po, n=54):
    """Laufen auf der Stelle (1,8 s je Doppelschritt, Schleife): Fuesse rollen ab, Becken wippt und pendelt,
    Wirbelsaeule und Schwanz drehen gegen, der Kopf bleibt ruhig nach vorn gerichtet."""
    bilder = []
    for i in range(n + 1):
        phi = i / n
        p = 2 * math.pi * phi
        becken = (0.0, 0.05 * math.cos(p - 2 * math.pi * 0.31), -0.17 + 0.04 * math.cos(2 * p))
        Dp = rot("Z", 3.0 * math.sin(p)) @ rot("X", 2.5 * math.cos(p - 2 * math.pi * 0.31)) @ rot("Y", 1.0 * math.cos(2 * p))
        wirbel = [(-1.0 * math.sin(p), 0.3 * math.cos(2 * p))] * 3
        hals = [(-0.3 * math.sin(p), -0.6 * math.cos(2 * p - 0.5))] * 3
        kopf_abs = (0.0, -2.0 + 1.5 * math.cos(2 * p - 0.8))
        schwanz = [((0.35 + 0.12 * k) * math.sin(p - 0.45 - 0.09 * k), 0.4 * math.cos(2 * p - 0.6 - 0.15 * k))
                   for k in range(12)]
        arme = {"l": (6 * math.sin(p + 0.5), 5 * math.sin(p + 0.2)), "r": (6 * math.sin(p + 0.5 + math.pi), 5 * math.sin(p + 0.2 + math.pi))}
        fuesse = {"l": fuss_lauf(phi % 1.0, 1), "r": fuss_lauf((phi + 0.5) % 1.0, -1)}
        bilder.append(pose(po, becken, Dp, wirbel, hals, kopf_abs, 1.0, schwanz, arme, fuesse))
    return bilder

def anim_bruellen(po, n=100):
    """Bruellen (3,3 s, einmal): ausholen, Kopf nach vorn-oben stossen, Maul weit auf, Zittern, zurueck."""
    bilder = []
    for i in range(n + 1):
        t = i / 30.0
        aus = glatt(t / 0.6) * (1 - glatt((t - 0.6) / 0.35))          # ausholen
        stoss = glatt((t - 0.55) / 0.4) * (1 - glatt((t - 2.35) / 0.8))  # bruellen
        zit = math.sin(t * 2 * math.pi * 9) * glatt((t - 0.9) / 0.2) * (1 - glatt((t - 2.2) / 0.3))
        becken = (-0.05 * aus + 0.06 * stoss, 0.0, -0.05 * aus - 0.10 * stoss)
        Dp = rot("Y", -3 * aus + 4 * stoss)
        wirbel = [(0.0, -1.0 * aus + 1.5 * stoss)] * 3
        hals = [(2 * stoss, 6 * aus - 7 * stoss), (2 * stoss, 5 * aus - 6 * stoss), (1 * stoss, 3 * aus - 3 * stoss)]
        kopf_abs = (10 * stoss + 1.2 * zit, 8 * aus - 22 * stoss + 1.0 * zit)
        kiefer = 1.0 + 42 * glatt((t - 0.62) / 0.3) * (1 - glatt((t - 2.25) / 0.5)) + 2.0 * zit
        schwanz = [(0.4 * zit, -0.8 * stoss + 0.3 * aus) for k in range(12)]
        arme = {"l": (-8 * stoss, -10 * stoss), "r": (-8 * stoss, -10 * stoss)}
        fuesse = {s: (ruhe_fuss(sg), ALPHA_RUHE, ZEHE_RUHE) for s, sg in (("l", 1), ("r", -1))}
        bilder.append(pose(po, becken, Dp, wirbel, hals, kopf_abs, kiefer, schwanz, arme, fuesse))
    return bilder

def aufnehmen(arm, name, bilder):
    """Posen als Aktion mit Schluesseln auf jedem Bild (Quaternionen ohne Vorzeichensprung)."""
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data_create()
    arm.animation_data.action = act
    vorher = {}
    for i, B in enumerate(bilder):
        for n, M in B.items():
            pb = arm.pose.bones[n]
            pb.rotation_mode = "QUATERNION"
            loc, q, _ = M.decompose()
            if n in vorher and vorher[n].dot(q) < 0:
                q = -q
            vorher[n] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=i, group=n)
            if n == "pelvis":
                pb.location = loc
                pb.keyframe_insert("location", frame=i, group=n)
    spur = arm.animation_data.nla_tracks.new()
    spur.name = name
    spur.strips.new(name, 0, act)
    spur.mute = True
    return act

# ---------------- Zusammenbauen: Netz, Kleinteile, Skelett, Gewichte, Animationen ----------------
GITTER_LO, GITTER_HI = (-7.45, -1.30, -0.08), (5.30, 1.30, 4.02)

def koerper_netz(feld, h, glaetten=2):
    f, lo = feld.gitter(GITTER_LO, GITTER_HI, h)
    V, Q = surface_nets(f, lo, h)
    del f
    V = feld.auf_flaeche(V)
    if glaetten:
        V = netz_glaetten(V, Q, feld, glaetten)
    return V, Q

log("Form ...")
FELD = t_rex_feld()
V_KOERPER, Q_KOERPER = koerper_netz(FELD, NETZ)
log("Spielnetz:", len(V_KOERPER), "Ecken,", len(Q_KOERPER), "Vierecke")
M_HAUT = material("Haut", hexf("#6b5f4c"), rauheit=0.6)
KOERPER = netz_objekt("Koerper", V_KOERPER, Q_KOERPER, [M_HAUT])
log("Zaehne, Augen, Krallen ...")
KLEINTEILE = kleinteile(FELD)
log("Skelett und Gewichte ...")
RIG = skelett()
namen, GEW = gewichte(V_KOERPER, FELD)
gewichte_setzen(KOERPER, namen, GEW)
for ob, knochen in KLEINTEILE:
    starr(ob, knochen)
bpy.ops.object.select_all(action="DESELECT")
for ob in [KOERPER] + [o for o, _ in KLEINTEILE]:
    ob.select_set(True)
bpy.context.view_layer.objects.active = KOERPER
bpy.ops.object.join()
TREX = bpy.context.view_layer.objects.active
TREX.name = TREX.data.name = "SK_" + NAME
TREX.parent = RIG
mod = TREX.modifiers.new("Skelett", "ARMATURE")
mod.object = RIG
log("Animationen ...")
POSER = Poser(RIG)
AKTIONEN = {"Idle": aufnehmen(RIG, NAME + "_Idle", anim_stehen(POSER)),
            "Walk": aufnehmen(RIG, NAME + "_Walk", anim_laufen(POSER)),
            "Roar": aufnehmen(RIG, NAME + "_Roar", anim_bruellen(POSER))}
RIG.animation_data.action = AKTIONEN["Idle"]

def zeige(aktion, bild):
    """Pose fuer ein Bild: Aktion aktiv setzen und zum Bild springen."""
    RIG.animation_data.action = AKTIONEN[aktion]
    scene.frame_set(bild)

# ---------------- Haut: Regionen, Schuppen, Farbe; gebacken in einen UV-Atlas ----------------
# Das Hautmuster ist prozedural (Abstand zur Kante von Voronoi-Zellen = Schuppen, Rauschen = Flecken und Baender)
# und wird in der Bindepose gebacken: Farbe, Rauheit, Umgebungsverdeckung und die Normalen aus einem feinen Netz
# (zweimal unterteilt, mit Hautfalten) samt Schuppenrelief. Bilder und Export verwenden dieselben Texturen.
def glatt_np(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)

def masken(V, N, feld):
    """Hautregionen je Ecke (0..1)."""
    rumpf = feld.bausteine[0]
    kiefer = next(b for b in feld.bausteine if b.gruppe == "kiefer" and isinstance(b, Profil))
    zunge = next(b for b in feld.bausteine if b.gruppe == "kiefer" and isinstance(b, Ellipsoid))
    _, G = feld.werte(V, gruppen=True)
    gruppen = ["rumpf", "kiefer", "bein_l", "bein_r", "arm_l", "arm_r"]
    tau = np.array([0.06, 0.02, 0.07, 0.07, 0.035, 0.035])
    D = np.stack([G.get(g, np.full(len(V), 10.0)) for g in gruppen], 1)
    c = np.exp(-(D - D.min(1, keepdims=True)) / tau)
    c = dict(zip(gruppen, (c / c.sum(1, keepdims=True)).T))
    x, y, z = V[:, 0], V[:, 1], V[:, 2]
    zt, zb = np.interp(x, rumpf.xs, rumpf.zt), np.interp(x, rumpf.xs, rumpf.zb)
    v = (z - 0.5 * (zt + zb)) / np.maximum(0.5 * (zt - zb), 1e-3)
    u = np.abs(y) / np.maximum(np.interp(x, rumpf.xs, rumpf.w), 1e-3)
    L = (V - kiefer.p0) @ kiefer.M + kiefer.p0                 # im geschlossenen Unterkiefer
    NL = N @ kiefer.M
    jt, jb = np.interp(L[:, 0], kiefer.xs, kiefer.zt), np.interp(L[:, 0], kiefer.xs, kiefer.zb)
    vj = (L[:, 2] - 0.5 * (jt + jb)) / np.maximum(0.5 * (jt - jb), 1e-3)
    glieder = c["bein_l"] + c["bein_r"] + c["arm_l"] + c["arm_r"]
    m = {}
    m["kopf"] = (c["rumpf"] + c["kiefer"]) * glatt_np(x, 3.5, 3.85)
    m["ruecken"] = c["rumpf"] * glatt_np(v, 0.05, 0.75) + glieder * glatt_np(N[:, 2], 0.2, 0.9) * 0.5
    m["bauch"] = c["rumpf"] * glatt_np(-v, 0.15, 0.7) + c["kiefer"] * glatt_np(-vj, 0.1, 0.6) \
        + glieder * (0.35 * glatt_np(-N[:, 2], 0.0, 0.8) + 0.3 * glatt_np(-np.sign(y) * N[:, 1], 0.2, 0.9))
    m["mitte"] = c["rumpf"] * glatt_np(v, 0.3, 0.8) * glatt_np(u, 0.42, 0.15) * (1 - m["kopf"])
    # Maul: alles, was ohne die Mundhoehle tief im Koerper laege, dazu Gaumen- und Kieferraender innerhalb der Lippen
    ohne = Feld([b for b in feld.bausteine if b.gruppe != "mund"]).werte(V)
    hoehle = glatt_np(-ohne, 0.002, 0.012)
    xm = np.linspace(3.8, 5.12, 133)
    rand_o = np.interp(x, xm, [aussen_y(rumpf, xx, float(np.interp(xx, rumpf.xs, rumpf.zb)) + 0.02) for xx in xm])
    xjm = np.linspace(3.7, 5.05, 136)
    rand_u = np.interp(L[:, 0], xjm, [aussen_y(kiefer, xx, float(np.interp(xx, kiefer.xs, kiefer.zt)) - 0.02,
                                               lokal=True) for xx in xjm])
    oben = (c["rumpf"] * glatt_np(x, 3.80, 3.88) * glatt_np(np.abs(y), rand_o - 0.004, rand_o - 0.03)
            * glatt_np(z, zb + 0.10, zb + 0.05) * glatt_np(N[:, 2], -0.1, -0.5))
    unten = (c["kiefer"] * glatt_np(L[:, 0], 3.78, 3.86) * glatt_np(np.abs(L[:, 1]), rand_u - 0.004, rand_u - 0.03)
             * glatt_np(L[:, 2], jt - 0.14, jt - 0.09) * glatt_np(NL[:, 2], 0.05, 0.45))
    m["mund"] = np.maximum(np.maximum(oben, unten), hoehle)
    m["rachen"] = m["mund"] * glatt_np(x, 4.05, 3.75)
    m["zunge"] = m["mund"] * glatt_np(zunge.d(V), 0.012, 0.0)
    lip_o = (c["rumpf"] * glatt_np(x, 3.85, 3.95) * glatt_np(np.abs(np.abs(y) - rand_o - 0.005), 0.035, 0.01)
             * glatt_np(z, zb + 0.09, zb + 0.04))
    lip_u = (c["kiefer"] * glatt_np(L[:, 0], 3.85, 3.95) * glatt_np(np.abs(np.abs(L[:, 1]) - rand_u - 0.005), 0.035, 0.01)
             * glatt_np(L[:, 2], jt - 0.09, jt - 0.04))
    m["lippe"] = np.maximum(lip_o, lip_u) * (1 - m["mund"])
    m["fuss"] = glieder * glatt_np(z, 0.50, 0.25)
    aug = np.minimum(np.linalg.norm(V - AUGE_MITTE, axis=1), np.linalg.norm(V - AUGE_MITTE * np.array((1, -1, 1)), axis=1))
    m["auge"] = glatt_np(aug, 0.13, 0.06)
    return {k: np.clip(w, 0, 1).astype(np.float32) for k, w in m.items()}

def attribute_setzen(ob, werte):
    for name, w in werte.items():
        a = ob.data.attributes.get(name) or ob.data.attributes.new(name, "FLOAT", "POINT")
        a.data.foreach_set("value", np.asarray(w, np.float32))

def ecken(ob, was="co"):
    a = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get(was, a)
    return a.reshape(-1, 3)

def teile_vereinen(ob):
    """Zaehne und Krallen bekommen das Hautmaterial (ein gemeinsamer Atlas); welches Teil es war, steht danach in
    der Ecken-Eigenschaft 'teil' (0 Haut, 1 Zahn, 2 Kralle, 3 Auge)."""
    me = ob.data
    nummer = {"Zahn": 1, "Kralle": 2, "Auge": 3}
    mi = np.empty(len(me.polygons), int)
    me.polygons.foreach_get("material_index", mi)
    namen = [m.name for m in me.materials]
    teil = np.zeros(len(me.vertices), np.float32)
    for p in me.polygons:
        t = nummer.get(namen[p.material_index], 0)
        if t:
            teil[list(p.vertices)] = t
    attribute_setzen(ob, {"teil": teil})
    haut, auge = namen.index("Haut"), namen.index("Auge")
    neu = np.where(mi == auge, 1, 0)
    m_haut, m_auge = me.materials[haut], me.materials[auge]
    me.materials.clear()
    me.materials.append(m_haut)
    me.materials.append(m_auge)
    me.polygons.foreach_set("material_index", neu)
    for n in ("Zahn", "Kralle"):
        if n in bpy.data.materials:
            bpy.data.materials.remove(bpy.data.materials[n])

def unterteilen(V, Q):
    """Jedes Viereck in vier (Kantenmitten und Flaechenmitte als neue Ecken), Umlaufsinn bleibt."""
    F, nV = len(Q), len(V)
    kanten = np.concatenate([Q[:, [0, 1]], Q[:, [1, 2]], Q[:, [2, 3]], Q[:, [3, 0]]])
    s = np.sort(kanten, 1).astype(np.int64)
    eind, inv = np.unique(s[:, 0] * nV + s[:, 1], return_inverse=True)
    inv = inv.reshape(-1)
    a0, a1 = eind // nV, eind % nV
    Vn = np.concatenate([V, 0.5 * (V[a0] + V[a1]), V[Q].mean(1)])
    e = inv.reshape(4, F).T + nV
    f = np.arange(F) + nV + len(eind)
    a, b, cc, d = Q.T
    Qn = np.concatenate([np.stack([a, e[:, 0], f, e[:, 3]], 1), np.stack([b, e[:, 1], f, e[:, 0]], 1),
                         np.stack([cc, e[:, 2], f, e[:, 1]], 1), np.stack([d, e[:, 3], f, e[:, 2]], 1)])
    return Vn, Qn

# ---------- Shader-Bausteine ----------
def farb_knoten(K, h):
    n = K.nt.nodes.new("ShaderNodeRGB")
    n.outputs[0].default_value = (*hexf(h), 1.0)
    return n.outputs[0]

def mischen(K, a, b, t, art="MIX"):
    n = K.nt.nodes.new("ShaderNodeMix")
    n.data_type = "RGBA"
    n.blend_type = art
    n.clamp_factor = True
    K.ein(n.inputs[0], t)
    K.ein(n.inputs[6], a)
    K.ein(n.inputs[7], b)
    return n.outputs[2]

def grau(K, w):
    return K.vektor(w, w, w)

def zellen_kante(K, P, groesse, zufall=1.0):
    """Schuppen: (Abstand zur Zellkante in Zellgroessen, Zufallswert der Zelle)."""
    a = K.nt.nodes.new("ShaderNodeTexVoronoi")
    a.voronoi_dimensions, a.feature = "3D", "DISTANCE_TO_EDGE"
    b = K.nt.nodes.new("ShaderNodeTexVoronoi")
    b.voronoi_dimensions, b.feature = "3D", "F1"
    for n in (a, b):
        K.ein(n.inputs["Vector"], P)
        n.inputs["Scale"].default_value = 1.0 / groesse
        n.inputs["Randomness"].default_value = zufall
    return a.outputs["Distance"], K.trenne(b.outputs["Color"])[0]

HAUT_ATTR = ("ruecken", "bauch", "mitte", "kopf", "lippe", "mund", "rachen", "zunge", "fuss", "auge", "teil", "spitze")

def haut_felder(K):
    """Gemeinsame Felder fuer Farbe, Rauheit und Relief."""
    P, N = K.geometrie()
    x, y, z = K.trenne(P)
    A = {n: K.attribut(n) for n in HAUT_ATTR}
    rn = K.nt.nodes.new("ShaderNodeTexNoise")               # leichte Verzerrung gegen zu gleichmaessige Zellen
    K.ein(rn.inputs["Vector"], P)
    rn.inputs["Scale"].default_value = 2.5
    rn.inputs["Detail"].default_value = 2.0
    P2 = K.v("ADD", P, K.v("SCALE", K.v("SUBTRACT", rn.outputs["Color"], (0.5, 0.5, 0.5)), 0.03))
    fein = zellen_kante(K, P2, 0.014)
    mittel = zellen_kante(K, P2, 0.026)
    gross = zellen_kante(K, P2, 0.055)
    feinanteil = K.max(A["bauch"], A["fuss"], K.mul(A["kopf"], 0.7), A["lippe"])
    return dict(P=P, N=N, x=x, y=y, z=z, A=A, fein=fein, mittel=mittel, gross=gross, feinanteil=feinanteil)

def kanten_mix(K, F):
    """Abstand zur Schuppenkante je Region (fein am Bauch/Kopf, mittel an den Flanken, gross am Rueckgrat)."""
    k = K.add(K.mul(F["mittel"][0], K.m("SUBTRACT", 1.0, F["feinanteil"])), K.mul(F["fein"][0], F["feinanteil"]))
    return K.add(K.mul(k, K.m("SUBTRACT", 1.0, F["A"]["mitte"])), K.mul(F["gross"][0], F["A"]["mitte"]))

def schuppen_hoehe(K, F):
    """Relief 0..1: gewoelbte Schuppen mit Fugen; am Rueckgrat grosse Schilde, am Kopf Hoecker, im Maul glatt."""
    fein = K.glatt(F["fein"][0], 0.0, 0.25)
    mittel = K.glatt(F["mittel"][0], 0.0, 0.2)
    gross = K.glatt(F["gross"][0], 0.0, 0.16)
    h = K.add(K.mul(mittel, K.m("SUBTRACT", 1.0, F["feinanteil"])), K.mul(fein, F["feinanteil"], 0.7))
    h = K.add(K.mul(h, K.m("SUBTRACT", 1.0, F["A"]["mitte"])), K.mul(gross, F["A"]["mitte"], 1.6))
    hoecker = K.mul(K.glatt(K.rauschen(F["P"], 9.0, detail=2), 0.56, 0.72), F["A"]["kopf"], 1.4)
    h = K.add(h, hoecker, K.mul(K.rauschen(F["P"], 5.0, detail=4), 0.5))
    return K.mul(h, K.m("SUBTRACT", 1.0, F["A"]["mund"]))

def haut_farbe(K, F):
    A = F["A"]
    c = mischen(K, farb_knoten(K, "#4a3922"), farb_knoten(K, "#261c11"), A["ruecken"])
    c = mischen(K, c, farb_knoten(K, "#8a7450"), A["bauch"])
    # Querbaender ueber Ruecken und Schwanz, Flecken an den Flanken
    welle = K.m("SINE", K.add(K.mul(F["x"], 2 * math.pi / 0.85), K.mul(K.rauschen(F["P"], 0.8, detail=3), 5.0)))
    band = K.mul(K.glatt(welle, 0.1, 0.6), K.glatt(F["x"], 3.4, 3.0), K.max(A["ruecken"], 0.35),
                 K.m("SUBTRACT", 1.0, A["bauch"]), 0.65)
    c = mischen(K, c, farb_knoten(K, "#1f190f"), band)
    flecken = K.mul(K.glatt(K.rauschen(F["P"], 4.5, detail=3), 0.58, 0.66), K.m("SUBTRACT", 1.0, A["bauch"]), 0.45)
    c = mischen(K, c, farb_knoten(K, "#2c251b"), flecken)
    # Kopf: Schnauzenruecken roetlich, um die Augen dunkel, Lippen dunkel; Fuesse dunkler
    c = mischen(K, c, farb_knoten(K, "#5a3523"), K.mul(A["kopf"], A["ruecken"], 0.6))
    c = mischen(K, c, farb_knoten(K, "#231b14"), K.mul(A["auge"], 0.75))
    c = mischen(K, c, farb_knoten(K, "#3e342a"), A["lippe"])
    c = mischen(K, c, farb_knoten(K, "#353027"), K.mul(A["fuss"], 0.8))
    # Schuppen: jede Zelle etwas anders, Fugen dunkler, grosse Flaechen leicht wolkig
    zelle = K.add(K.mul(F["mittel"][1], 0.5), K.mul(F["fein"][1], 0.3), K.mul(F["gross"][1], 0.2))
    c = mischen(K, c, grau(K, K.add(0.86, K.mul(zelle, 0.28))), 1.0, art="MULTIPLY")
    fuge = K.add(0.66, K.mul(0.34, K.glatt(kanten_mix(K, F), 0.0, 0.2)))
    fuge = K.add(fuge, K.mul(A["mund"], K.m("SUBTRACT", 1.0, fuge)))
    c = mischen(K, c, grau(K, fuge), 1.0, art="MULTIPLY")
    c = mischen(K, c, grau(K, K.add(0.88, K.mul(K.rauschen(F["P"], 0.7, detail=4), 0.24))), 1.0, art="MULTIPLY")
    # Maul: Zahnfleisch, Zunge, dunkler Rachen
    maul = mischen(K, farb_knoten(K, "#7a3a33"), farb_knoten(K, "#8f4b42"), A["zunge"])
    maul = mischen(K, maul, farb_knoten(K, "#2a1412"), A["rachen"])
    c = mischen(K, c, maul, A["mund"])
    # Zaehne (teil 1) und Krallen (teil 2)
    zahn = mischen(K, farb_knoten(K, "#6f5a3d"), farb_knoten(K, "#cdbf9f"), K.glatt(A["spitze"], 0.15, 0.75))
    kralle = mischen(K, farb_knoten(K, "#25201b"), farb_knoten(K, "#6a604f"), K.glatt(A["spitze"], 0.55, 1.0))
    c = mischen(K, c, zahn, K.glatt(A["teil"], 0.5, 0.6))
    c = mischen(K, c, kralle, K.glatt(A["teil"], 1.5, 1.6))
    return c

def haut_rauheit(K, F):
    A = F["A"]
    r = K.add(0.6, K.mul(0.24, K.m("SUBTRACT", 1.0, K.glatt(kanten_mix(K, F), 0.0, 0.2))),
              K.mul(K.rauschen(F["P"], 2.0, detail=3), 0.1))
    r = K.add(K.mul(r, K.m("SUBTRACT", 1.0, A["mund"])), K.mul(A["mund"], 0.26))
    hart = K.glatt(A["teil"], 0.5, 0.6)
    return K.add(K.mul(r, K.m("SUBTRACT", 1.0, hart)), K.mul(hart, K.add(0.3, K.mul(K.m("SUBTRACT", 1.0, A["spitze"]), 0.2))))

# ---------- Backen ----------
def back_mat(name, farbe_von, ziel):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    aus = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(em.outputs[0], aus.inputs["Surface"])
    K = Knoten(nt)
    wert = farbe_von(K)
    if wert.type == "VALUE":
        wert = grau(K, wert)
    nt.links.new(wert, em.inputs["Color"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = ziel
    nt.nodes.active = tex
    return m

def backen(ob, name, farbe_von, proben, aufl, typ="EMIT", quelle=None):
    """Backt in ein neues Bild (Float, linear) und gibt die Pixel (Zeile von unten, Spalte, RGB) zurueck.
    Die Augen haben eigene Texturen und landen in einem Wegwerfbild."""
    ziel = bpy.data.images.new("_bake_" + name, aufl, aufl, alpha=False, float_buffer=True)
    ziel.colorspace_settings.name = "Non-Color"
    leer = bpy.data.images.new("_bake_leer", 64, 64, alpha=False, float_buffer=True)
    alt = list(ob.data.materials)
    neu = []
    if typ == "EMIT":
        m_haupt = back_mat("_Bake_" + name, farbe_von, ziel)
        m_leer = back_mat("_Bake_leer", lambda K: grau(K, 0.0), leer)
        neu = [m_haupt, m_leer]
        for i, m in enumerate(alt):
            ob.data.materials[i] = m_leer if "Auge" in m.name else m_haupt
    else:                                                    # Normalen: Zielbild in den echten Materialien
        for m in alt:
            t = m.node_tree.nodes.new("ShaderNodeTexImage")
            t.image = leer if "Auge" in m.name else ziel
            m.node_tree.nodes.active = t
    scene.render.engine = "CYCLES"
    scene.cycles.samples = proben
    scene.render.bake.margin = 8
    scene.render.bake.margin_type = "EXTEND"
    bpy.ops.object.select_all(action="DESELECT")
    if quelle is not None:
        quelle.select_set(True)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    t0 = time.time()
    if typ == "EMIT":
        bpy.ops.object.bake(type="EMIT", uv_layer="UVMap", margin=8, use_clear=True)
        for i, m in enumerate(alt):
            ob.data.materials[i] = m
    else:
        bpy.ops.object.bake(type="NORMAL", uv_layer="UVMap", margin=8, use_clear=True, use_selected_to_active=True,
                            cage_extrusion=0.012, max_ray_distance=0.03, normal_space="TANGENT")
        for m in alt:
            m.node_tree.nodes.remove(m.node_tree.nodes.active)
    for m in neu:
        bpy.data.materials.remove(m)
    px = np.empty(aufl * aufl * 4, dtype=np.float32)
    ziel.pixels.foreach_get(px)
    bpy.data.images.remove(ziel)
    bpy.data.images.remove(leer)
    log(f"  gebacken: {name} ({time.time() - t0:.0f} s)")
    return px.reshape(aufl, aufl, 4)[..., :3]

def flaechen(me):
    """Je Flaeche: Mittelpunkt, erste Ecke; je Kante die beiden anliegenden Flaechen (nur Kanten mit genau zwei)."""
    F = len(me.polygons)
    Z = np.empty(F * 3)
    me.polygons.foreach_get("center", Z)
    ls = np.empty(F, int)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(F, int)
    me.polygons.foreach_get("loop_total", lt)
    lv = np.empty(len(me.loops), int)
    me.loops.foreach_get("vertex_index", lv)
    le = np.empty(len(me.loops), int)
    me.loops.foreach_get("edge_index", le)
    lf = np.repeat(np.arange(F), lt)
    o = np.argsort(le, kind="stable")
    e_s, f_s = le[o], lf[o]
    paar = np.nonzero(e_s[1:] == e_s[:-1])[0]
    nur_zwei = np.ones(len(paar), bool)
    if len(paar) > 1:
        doppelt = np.nonzero(paar[1:] == paar[:-1] + 1)[0]
        nur_zwei[doppelt] = nur_zwei[doppelt + 1] = False
    paar = paar[nur_zwei]
    return Z.reshape(-1, 3), lv[ls], e_s[paar], f_s[paar], f_s[paar + 1], lf

def glied_aussen(P, kegel, sg):
    """Fuer Bein und Arm: liegt der Punkt auf der aeusseren Haelfte des naechsten Glieds? (Ebene durch die
    Gliedachse, senkrecht zum Boden; so laufen die Naehte vorn und hinten bzw. oben und unten.)"""
    best = np.full(len(P), np.inf)
    aussen = np.zeros(len(P), bool)
    for k in kegel:
        ab = k.b - k.a
        t = np.clip(((P - k.a) @ ab) / (ab @ ab), 0, 1)
        q = k.a + t[:, None] * ab
        d = np.linalg.norm(P - q, axis=1) - (k.r1 + (k.r2 - k.r1) * t)
        s = np.array((ab[1], -ab[0], 0.0))
        if np.hypot(s[0], s[1]) < 0.35 * np.linalg.norm(ab):
            s = s + np.array((0.0, sg * np.linalg.norm(ab), 0.0))
        if s[1] * sg < 0:
            s = -s
        s /= np.linalg.norm(s)
        neu = d < best
        best[neu] = d[neu]
        aussen[neu] = ((P[neu] - q[neu]) @ s) > 0
    return aussen

def uv_inseln(ob):
    """Flaechen der Haut in Inseln einteilen: Rumpf links/rechts (Naht auf der Mittellinie), quer geteilt am
    Schwanzansatz, vor dem Hals und hinter dem Kopf; Unterkiefer links/rechts; Beine und Arme je in eine aeussere
    und eine innere Haelfte. Liefert die Nummer je Flaeche (-1: Zaehne, Krallen, Augen)."""
    me = ob.data
    Z, erste, kanten, f1, f2, _ = flaechen(me)
    mi = np.empty(len(me.polygons), int)
    me.polygons.foreach_get("material_index", mi)
    teil = np.empty(len(me.vertices))
    me.attributes["teil"].data.foreach_get("value", teil)
    haut = (teil[erste] < 0.5) & (mi == 0)
    nr = np.full(len(Z), -1)
    P = Z[haut]
    _, G = FELD.werte(P, gruppen=True)
    gruppen = ["rumpf", "kiefer", "bein_l", "bein_r", "arm_l", "arm_r"]
    g = np.stack([G.get(n, np.full(len(P), 10.0)) for n in gruppen], 1).argmin(1)
    lab = np.zeros(len(P), int)
    r = g == 0
    lab[r] = (P[r, 1] > 0) * 4 + np.digitize(P[r, 0], [-3.3, 2.5, 3.5])
    k = g == 1
    lab[k] = 8 + (P[k, 1] > 0)
    for i, (n, sg) in enumerate((("bein_l", 1), ("bein_r", -1), ("arm_l", 1), ("arm_r", -1))):
        w = g == 2 + i
        kegel = [b for b in FELD.bausteine if b.gruppe == n and isinstance(b, Kegel)]
        lab[w] = 10 + 2 * i + glied_aussen(P[w], kegel, sg)
    nr[haut] = lab
    # Einzelne abweichende Flaechen an den Grenzen glaetten (Mehrheit der Nachbarn)
    beide = (nr[f1] >= 0) & (nr[f2] >= 0)
    a1, a2 = f1[beide], f2[beide]
    for _ in range(3):
        stimmen = np.zeros((len(nr), 18))
        np.add.at(stimmen, (a1, nr[a2]), 1)
        np.add.at(stimmen, (a2, nr[a1]), 1)
        beste = stimmen.argmax(1)
        wechsel = (nr >= 0) & (stimmen.max(1) >= 3) & (beste != nr)
        nr[wechsel] = beste[wechsel]
    naht = kanten[beide][nr[a1] != nr[a2]]
    return nr, naht

def uv_atlas(ob):
    """Abwicklung: Haut mit Naehten zwischen den Inseln (winkeltreu abgewickelt), Zaehne und Krallen per Smart
    Project, Augen behalten ihre Kugel-Abwicklung. Gleiche Texeldichte, der Kopf doppelt so dicht, dann gepackt."""
    me = ob.data
    if "UVMap" not in me.uv_layers:
        me.uv_layers.new(name="UVMap")
    me.uv_layers.active = me.uv_layers["UVMap"]
    nr, naht = uv_inseln(ob)
    mi = np.empty(len(me.polygons), int)
    me.polygons.foreach_get("material_index", mi)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    scene.tool_settings.use_uv_select_sync = False
    bm = bmesh.from_edit_mesh(me)
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    for e in bm.edges:
        e.seam = False
    for i in naht.tolist():
        bm.edges[i].seam = True
    def waehle(bed):
        for f in bm.faces:
            f.select_set(bool(bed[f.index]))
        bm.select_flush_mode()
        bmesh.update_edit_mesh(me)
    waehle(nr >= 0)
    bpy.ops.uv.unwrap(method="ANGLE_BASED", fill_holes=True, correct_aspect=True, margin=0.0)
    waehle((nr < 0) & (mi == 0))
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0, scale_to_bounds=False)
    waehle(mi == 0)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    # Kopf und Unterkiefer doppelte Flaeche, Zaehne und Krallen 1,5-fach (je Insel um ihre Mitte skaliert)
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers["UVMap"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    lt = np.empty(len(me.polygons), int)
    me.polygons.foreach_get("loop_total", lt)
    lnr = np.repeat(nr, lt)
    lmi = np.repeat(mi, lt)
    for gruppe, faktor in (([3, 7, 8, 9], 2.0), ([-1], 1.5)):
        for n in gruppe:
            sel = (lnr == n) & (lmi == 0)
            if sel.any():
                c = uv[sel].mean(0)
                uv[sel] = c + (uv[sel] - c) * math.sqrt(faktor)
    me.uv_layers["UVMap"].data.foreach_set("uv", uv.ravel())
    bpy.ops.object.mode_set(mode="EDIT")
    bm = bmesh.from_edit_mesh(me)
    bm.faces.ensure_lookup_table()
    for f in bm.faces:
        f.select_set(f.material_index == 0)
    bm.select_flush_mode()
    bmesh.update_edit_mesh(me)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, scale=True, margin_method="FRACTION", margin=0.002, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")
    uv = np.empty(len(me.loops) * 2)
    me.uv_layers["UVMap"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    ls = np.empty(len(me.polygons), int)
    me.polygons.foreach_get("loop_start", ls)
    naechste = np.arange(len(uv)) + 1
    naechste[ls + lt - 1] = ls
    kreuz = uv[:, 0] * uv[naechste, 1] - uv[naechste, 0] * uv[:, 1]
    flaeche = np.abs(np.add.reduceat(kreuz, ls)) / 2
    log(f"  UV: {len(set(nr.tolist())) - 1} Hautinseln, {len(naht)} Nahtkanten, "
        f"Atlas zu {100 * flaeche[mi == 0].sum():.0f} % belegt")

def unscharf(a, n=1):
    for _ in range(n):
        a = (a + np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 5
    return a

def haut_backen(ob):
    """Texturen der Haut backen und das Hautmaterial darauf umstellen."""
    log("Haut backen ...")
    uv_atlas(ob)
    RIG.data.pose_position = "REST"
    bpy.context.view_layer.update()
    farbe = backen(ob, "farbe", lambda K: haut_farbe(K, haut_felder(K)), 4, ATLAS)
    daten = backen(ob, "daten", lambda K: (lambda F: K.vektor(haut_rauheit(K, F), K.m("DIVIDE", F["A"]["teil"], 3.0),
                                                                0.0))(haut_felder(K)), 2, ATLAS)
    rau, teil = daten[..., 0], daten[..., 1] * 3
    def ao(K):
        n = K.nt.nodes.new("ShaderNodeAmbientOcclusion")
        n.samples, n.only_local = 16, True
        n.inputs["Distance"].default_value = 0.4
        return n.outputs["AO"]
    verd = unscharf(backen(ob, "ao", ao, 4, ATLAS)[..., 0], 2)
    log("Feines Netz fuer die Normalen ...")
    stufen = max(1, int(round(math.log2(NETZ / FEIN))))
    V, Q = V_KOERPER, Q_KOERPER
    for _ in range(stufen):
        V, Q = unterteilen(V, Q)
    feld_fein = t_rex_feld(fein=True)
    V = feld_fein.auf_flaeche(V, schritte=2)
    fein = netz_objekt("Feinhaut", V, Q, [bpy.data.materials.new("Feinhaut")])
    attribute_setzen(fein, masken(V, ecken(fein, "normal"), FELD))
    m = fein.data.materials[0]
    m.use_nodes = True
    K = Knoten(m.node_tree)
    bump = m.node_tree.nodes.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 0.003
    K.ein(bump.inputs["Height"], schuppen_hoehe(K, haut_felder(K)))
    m.node_tree.links.new(bump.outputs["Normal"], m.node_tree.nodes["Principled BSDF"].inputs["Normal"])
    log("  feines Netz:", len(V), "Ecken")
    nrm = backen(ob, "normal", None, 1, ATLAS, typ="NORMAL", quelle=fein)
    me = fein.data
    bpy.data.objects.remove(fein)
    bpy.data.meshes.remove(me)
    bpy.data.materials.remove(m)
    RIG.data.pose_position = "POSE"
    # Zaehne und Krallen: glatte Normalen (die Strahlen treffen dort nur das Zahnfleisch)
    nrm[teil > 0.5] = (0.5, 0.5, 1.0)
    farbe = farbe * (0.8 + 0.2 * verd[..., None])
    bc = bild_hw("T_" + NAME + "_BaseColor", np.clip(farbe, 0, 1) ** (1 / 2.2), farbe=True)
    orm = bild_hw("T_" + NAME + "_ORM", np.stack([verd, np.clip(rau, 0.05, 1), np.zeros_like(rau)], -1), farbe=False)
    nb = bild_hw("T_" + NAME + "_Normal", nrm, farbe=False)
    dx = nrm.copy()
    dx[..., 1] = 1 - dx[..., 1]
    bpy.data.images.remove(bild_hw("T_" + NAME + "_Normal_DirectX", dx, farbe=False))   # nur Datei (Unreal)
    gltf = bpy.data.node_groups.get("glTF Material Output")
    if gltf is None:
        gltf = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
        gltf.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        gltf.interface.new_socket("Thickness", in_out="INPUT", socket_type="NodeSocketFloat")
        gltf.nodes.new("NodeGroupInput")
        gltf.nodes.new("NodeGroupOutput")
    m = ob.data.materials[0]
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
    nt.links.new(tex(orm).outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    g = nt.nodes.new("ShaderNodeGroup")
    g.node_tree = gltf
    nt.links.new(sep.outputs["Red"], g.inputs["Occlusion"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    nt.links.new(tex(nb).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Coat Weight"].default_value = 0.0
    b.inputs["Subsurface Weight"].default_value = 0.05
    b.inputs["Subsurface Radius"].default_value = (1.0, 0.45, 0.3)
    b.inputs["Subsurface Scale"].default_value = 0.02
    m.name = "M_" + NAME + "_Haut"
    ob.data.materials[1].name = "M_" + NAME + "_Auge"
    log("  Texturen gespeichert")

log("Haut ...")
teile_vereinen(TREX)
attribute_setzen(TREX, masken(ecken(TREX), ecken(TREX, "normal"), FELD))
if os.environ.get("HAUT", "1") == "1":
    haut_backen(TREX)

# ---------------- Export: FBX fuer Unreal (Zentimeter, alle Animationen) und glTF (Meter, alle Animationen) ----------------
for name in HAUT_ATTR:                                  # Hilfswerte des Backens gehoeren nicht in den Export
    if name in TREX.data.attributes:
        TREX.data.attributes.remove(TREX.data.attributes[name])

# Vielecke mit mehr als vier Ecken (Zahn- und Krallenboeden) triangulieren; erst dann schreibt FBX Tangenten
bm = bmesh.new()
bm.from_mesh(TREX.data)
bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4], quad_method="BEAUTY", ngon_method="BEAUTY")
bm.to_mesh(TREX.data)
bm.free()
TREX.data.calc_loop_triangles()
DREIECKE = len(TREX.data.loop_triangles)
log(f"fuer den Export: {DREIECKE} Dreiecke, {len(TREX.data.vertices)} Ecken, {len(RIG.data.bones)} Knochen, "
    f"{len(TREX.data.materials)} Materialien")

def auswahl():
    bpy.ops.object.select_all(action="DESELECT")
    RIG.select_set(True)
    TREX.select_set(True)
    bpy.context.view_layer.objects.active = RIG

def skalieren(f):
    """Netz, Knochen und die Verschiebungs-Schluessel des Beckens um f skalieren (fuer die FBX in Zentimetern)."""
    TREX.data.transform(Matrix.Scale(f, 4))
    auswahl()
    bpy.ops.object.mode_set(mode="EDIT")
    neu = {b.name: (b.head * f, b.tail * f) for b in RIG.data.edit_bones}   # erst alle berechnen: verbundene
    for b in RIG.data.edit_bones:                                            # Knochen teilen Kopf und Ende
        b.head, b.tail = neu[b.name]
    bpy.ops.object.mode_set(mode="OBJECT")
    for act in AKTIONEN.values():
        for fc in act.fcurves:
            if fc.data_path.endswith(".location"):
                for k in fc.keyframe_points:
                    k.co.y *= f
                    k.handle_left.y *= f
                    k.handle_right.y *= f
                fc.update()

RIG.animation_data.action = AKTIONEN["Idle"]
scene.frame_set(0)
# glTF in Metern, jede Aktion als eigene Animation
auswahl()
bpy.ops.export_scene.gltf(filepath=os.path.join(EXPORT, "SK_" + NAME + ".glb"), export_format="GLB", use_selection=True,
                          export_yup=True, export_apply=False, export_skins=True, export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_range=False,
                          export_cameras=False, export_lights=False, export_image_format="AUTO")
# FBX fuer Unreal: Zentimeter, ueberall Skalierung 1. Netz, Knochen und Becken-Verschiebungen werden dafuer kurz x100
# gesetzt und die Szeneneinheit auf 0,01. Die Normal-Textur geht in der DirectX-Richtung (Gruen umgedreht) hinein,
# wie Unreal sie erwartet.
nt_haut = TREX.data.materials[0].node_tree
nm_tex = next((n for n in nt_haut.nodes if n.type == "TEX_IMAGE" and n.image and n.image.name.endswith("_Normal")), None)
dx_bild = None
if nm_tex is not None:
    dx_bild = bpy.data.images.load(os.path.join(TEXDIR, "T_" + NAME + "_Normal_DirectX.png"))
    dx_bild.colorspace_settings.name = "Non-Color"
    gl_bild, nm_tex.image = nm_tex.image, dx_bild
RIG.animation_data.action = None
scene.unit_settings.scale_length = 0.01
skalieren(100.0)
auswahl()
bpy.ops.export_scene.fbx(filepath=os.path.join(EXPORT, "SK_" + NAME + ".fbx"), use_selection=True,
                         object_types={"ARMATURE", "MESH"}, apply_unit_scale=True, global_scale=1.0,
                         apply_scale_options="FBX_SCALE_NONE", add_leaf_bones=False, primary_bone_axis="Y",
                         secondary_bone_axis="X", use_armature_deform_only=True, bake_anim=True,
                         bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False, bake_anim_use_all_actions=True,
                         bake_anim_force_startend_keying=True, bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
                         mesh_smooth_type="FACE", use_mesh_modifiers=False, use_tspace=True,
                         path_mode="COPY", embed_textures=True)
skalieren(0.01)
scene.unit_settings.scale_length = 1.0
if nm_tex is not None:
    nm_tex.image = gl_bild
    bpy.data.images.remove(dx_bild)
RIG.animation_data.action = AKTIONEN["Idle"]
scene.frame_set(0)
log("exportiert:", sorted(f for f in os.listdir(EXPORT) if f != "Texturen"), sorted(os.listdir(TEXDIR)))

# ---------------- Szenen fuer die Vorschaubilder: Lichtung im Kreidezeit-Wald und Fotostudio ----------------
# Die Lichtung ist frei erfunden: Farne, Palmfarne, Baumfarne, Schachtelhalme und hohe Nadelbaeume, wie sie in
# der spaeten Kreidezeit wuchsen, dazu Felsen, ein umgestuerzter Stamm, Bodennebel und Sonnenstrahlen durch das
# Blaetterdach. Alles wird per Skript erzeugt; die Szene dient nur den Bildern und ist nicht Teil des Exports.
def sammlung(name):
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    return c

def in_sammlung(ob, c):
    for alt in list(ob.users_collection):
        alt.objects.unlink(ob)
    c.objects.link(ob)
    return ob

def welt(farbe, staerke=1.0):
    w = bpy.data.worlds.new("Welt")
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*farbe, 1)
    bg.inputs["Strength"].default_value = staerke
    return w

def flaechenlicht(name, ort, ziel, sx, sy, energie, c, farbe=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA")
    d.shape = "RECTANGLE"
    d.size, d.size_y = sx, sy
    d.energy = energie
    d.color = farbe
    ob = bpy.data.objects.new(name, d)
    c.objects.link(ob)
    ob.location = ort
    ob.rotation_euler = (Vector(ziel) - Vector(ort)).to_track_quat("-Z", "Y").to_euler()
    ob.visible_camera = False
    return ob

def netz_aus(name, V, F, mats, attr=None, glatt=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], [tuple(f) for f in F])
    me.validate(clean_customdata=False)
    for m in mats:
        me.materials.append(m)
    if glatt:
        me.shade_smooth()
    for n, w in (attr or {}).items():
        a = me.attributes.new(n, "FLOAT", "POINT")
        a.data.foreach_set("value", np.asarray(w, np.float32))
    return me

# ---------- Materialien ----------
def mat_knoten(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree, m.node_tree.nodes["Principled BSDF"], Knoten(m.node_tree)

def blatt_material(name, a, b, spitze="#8c8a3c", rau=0.42, durch=0.3):
    """Blaetter: Farbe je Pflanze zufaellig zwischen a und b, zur Wedelspitze heller; zweiseitig durchscheinend."""
    m, nt, bs, K = mat_knoten(name)
    info = nt.nodes.new("ShaderNodeObjectInfo")
    c = mischen(K, farb_knoten(K, a), farb_knoten(K, b), info.outputs["Random"])
    c = mischen(K, c, farb_knoten(K, spitze), K.mul(K.glatt(K.attribut("t"), 0.55, 1.0), 0.35))
    c = mischen(K, c, grau(K, K.add(0.8, K.mul(K.rauschen(K.geometrie()[0], 30.0, detail=2), 0.4))), 1.0,
                art="MULTIPLY")
    K.ein(bs.inputs["Base Color"], c)
    bs.inputs["Roughness"].default_value = rau
    bs.inputs["Specular IOR Level"].default_value = 0.4
    tl = nt.nodes.new("ShaderNodeBsdfTranslucent")
    K.ein(tl.inputs["Color"], mischen(K, c, farb_knoten(K, "#9fb04a"), 0.3))
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = durch
    nt.links.new(bs.outputs["BSDF"], mix.inputs[1])
    nt.links.new(tl.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])
    return m

def laub_material(name, a, b, loch_skala=7.0):
    """Laubbueschel: Huelle mit Luecken (Rauschen), dahinter weitere Huellen; durchscheinend, je Baum andere Farbe."""
    m, nt, bs, K = mat_knoten(name)
    P = K.geometrie()[0]
    info = nt.nodes.new("ShaderNodeObjectInfo")
    c = mischen(K, farb_knoten(K, a), farb_knoten(K, b), info.outputs["Random"])
    c = mischen(K, c, grau(K, K.add(0.7, K.mul(K.rauschen(P, 3.0, detail=3), 0.6))), 1.0, art="MULTIPLY")
    K.ein(bs.inputs["Base Color"], c)
    bs.inputs["Roughness"].default_value = 0.55
    bu = nt.nodes.new("ShaderNodeBump")
    bu.inputs["Distance"].default_value = 0.05
    K.ein(bu.inputs["Height"], K.rauschen(P, loch_skala * 2.5, detail=2))
    nt.links.new(bu.outputs["Normal"], bs.inputs["Normal"])
    tl = nt.nodes.new("ShaderNodeBsdfTranslucent")
    K.ein(tl.inputs["Color"], mischen(K, c, farb_knoten(K, "#7f9a3a"), 0.35))
    blatt = nt.nodes.new("ShaderNodeMixShader")
    blatt.inputs[0].default_value = 0.3
    nt.links.new(bs.outputs["BSDF"], blatt.inputs[1])
    nt.links.new(tl.outputs["BSDF"], blatt.inputs[2])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    K.ein(mix.inputs[0], K.glatt(K.rauschen(P, loch_skala, detail=4, rau=0.6), 0.47, 0.5))
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(blatt.outputs["Shader"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])
    return m

def bueschel(bm, mitte, r, platt=0.6, mi=1, rng=None):
    """Laubbueschel aus zwei ineinander liegenden, verbeulten Kugeln."""
    for f in (1.0, 0.68):
        k = bmesh.new()
        bmesh.ops.create_icosphere(k, subdivisions=2, radius=r * f)
        off = (rng.uniform(0, 50, 3) if rng is not None else np.zeros(3))
        for v in k.verts:
            p = np.array(v.co) / max(r * f, 1e-6)
            d = 1 + 0.22 * math.sin(3.1 * p[0] + off[0]) * math.sin(2.7 * p[1] + off[1]) + 0.12 * math.sin(4 * p[2] + off[2])
            v.co = Vector((p[0] * r * f * d, p[1] * r * f * d, p[2] * r * f * d * platt)) + Vector(mitte)
        for fc in k.faces:
            fc.material_index = mi
        einfuegen(bm, k)

def rinde_material(name, a, b, streck=(5.0, 5.0, 0.6), skala=3.0, bump=0.6):
    """Rinde: laengs gestreckte Fasern (Rauschen in gestauchten Koordinaten), dazu Moos an der Wetterseite."""
    m, nt, bs, K = mat_knoten(name)
    P = K.geometrie()[0]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    Q = K.v("MULTIPLY", tc.outputs["Object"], streck)
    fas = K.rauschen(Q, skala, detail=8, rau=0.65, verzerrung=0.4)
    c = mischen(K, farb_knoten(K, a), farb_knoten(K, b), K.glatt(fas, 0.35, 0.7))
    moos = K.mul(K.glatt(K.rauschen(P, 1.5, detail=4), 0.5, 0.7), K.glatt(K.trenne(P)[2], 2.5, 0.3))
    c = mischen(K, c, farb_knoten(K, "#3d4a22"), K.mul(moos, 0.8))
    K.ein(bs.inputs["Base Color"], c)
    bs.inputs["Roughness"].default_value = 0.85
    bu = nt.nodes.new("ShaderNodeBump")
    bu.inputs["Strength"].default_value = bump
    bu.inputs["Distance"].default_value = 0.02
    K.ein(bu.inputs["Height"], fas)
    nt.links.new(bu.outputs["Normal"], bs.inputs["Normal"])
    return m

def fels_material():
    m, nt, bs, K = mat_knoten("Fels")
    P, N = K.geometrie()
    r = K.rauschen(P, 2.0, detail=10, rau=0.6)
    c = mischen(K, farb_knoten(K, "#4a4740"), farb_knoten(K, "#77736a"), K.glatt(r, 0.35, 0.7))
    oben = K.glatt(K.trenne(N)[2], 0.35, 0.85)
    moos = K.mul(oben, K.glatt(K.rauschen(P, 3.0, detail=5), 0.38, 0.55))
    c = mischen(K, c, farb_knoten(K, "#3c4b1f"), moos)
    K.ein(bs.inputs["Base Color"], c)
    K.ein(bs.inputs["Roughness"], K.add(0.7, K.mul(moos, 0.2)))
    bu = nt.nodes.new("ShaderNodeBump")
    bu.inputs["Distance"].default_value = 0.03
    K.ein(bu.inputs["Height"], K.rauschen(P, 6.0, detail=10, rau=0.6))
    nt.links.new(bu.outputs["Normal"], bs.inputs["Normal"])
    return m

def boden_material():
    """Waldboden: dunkler feuchter Lehm, Laubstreu, Moospolster; Fusspfad in der Lichtung etwas heller und kahl."""
    m, nt, bs, K = mat_knoten("Waldboden")
    P = K.geometrie()[0]
    x, y, z = K.trenne(P)
    lehm = mischen(K, farb_knoten(K, "#2e2418"), farb_knoten(K, "#4a3a28"), K.rauschen(P, 0.8, detail=6))
    streu_z, streu_r = zellen_kante(K, P, 0.045)
    streu = mischen(K, farb_knoten(K, "#5a3f22"), farb_knoten(K, "#7a5a32"), streu_r)
    s_maske = K.glatt(K.rauschen(P, 1.6, detail=4), 0.42, 0.55)
    c = mischen(K, lehm, streu, K.mul(s_maske, K.glatt(streu_z, 0.02, 0.08)))
    moos_m = K.glatt(K.rauschen(P, 0.35, detail=5), 0.52, 0.62)
    c = mischen(K, c, mischen(K, farb_knoten(K, "#2f3d18"), farb_knoten(K, "#4a5a22"), K.rauschen(P, 9.0)), moos_m)
    r = K.m("SQRT", K.add(K.mul(K.add(x, 0.5), K.add(x, 0.5), 0.012), K.mul(y, y, 0.03)))
    pfad = K.glatt(r, 1.0, 0.6)
    c = mischen(K, c, farb_knoten(K, "#4f4030"), K.mul(pfad, 0.6))
    K.ein(bs.inputs["Base Color"], c)
    K.ein(bs.inputs["Roughness"], K.add(0.62, K.mul(moos_m, 0.25)))
    bu = nt.nodes.new("ShaderNodeBump")
    bu.inputs["Distance"].default_value = 0.04
    K.ein(bu.inputs["Height"], K.add(K.mul(K.rauschen(P, 3.0, detail=8), 0.6), K.mul(streu_z, s_maske, 2.0)))
    nt.links.new(bu.outputs["Normal"], bs.inputs["Normal"])
    return m

# ---------- Pflanzen ----------
def wedel(rng, L, B, auf, bogen, fiedern=24, schmal=0.2, haengen=0.25, winkel=58, n=22):
    """Ein Wedel in lokalen Koordinaten: Spindel ab dem Ursprung Richtung +x, steigt mit 'auf' Grad an und biegt
    sich um 'bogen' Grad nach unten. Fiedern beidseitig (in der Mitte am laengsten), leicht haengend.
    Rueckgabe: Ecken, Vierecke, Lage entlang des Wedels (0..1) je Ecke."""
    ts = np.linspace(0, 1, n)
    th = np.radians(auf - bogen * ts ** 1.6)
    P = np.zeros((n, 3))
    for i in range(1, n):
        P[i] = P[i - 1] + L / (n - 1) * np.array((math.cos(th[i - 1]), 0.0, math.sin(th[i - 1])))
    V, F, T = [], [], []
    def streifen(mitten, quer, t):
        i0 = len(V)
        for c, q, tt in zip(mitten, quer, t):
            V.extend((c - q, c + q))
            T.extend((tt, tt))
        for k in range(len(mitten) - 1):
            a = i0 + 2 * k
            F.append((a, a + 1, a + 3, a + 2))
    seitlich = np.array((0.0, 1.0, 0.0))
    streifen(P, [seitlich * 0.008 * (1 - 0.7 * t) for t in ts], ts)          # Spindel
    for k in range(fiedern):
        t = 0.1 + 0.88 * k / (fiedern - 1)
        p = np.array([np.interp(t, ts, P[:, j]) for j in range(3)])
        w = np.radians(np.interp(t, ts, np.degrees(th)))
        d = np.array((math.cos(w), 0.0, math.sin(w)))
        laenge = B * math.sin(math.pi * min(1.0, 0.15 + 0.95 * t)) ** 0.6 * (1.15 - 0.45 * t) * rng.uniform(0.9, 1.1)
        for s in (1, -1):
            a = math.radians(winkel + rng.uniform(-6, 6))
            r = d * math.cos(a) + seitlich * s * math.sin(a)
            us = np.linspace(0, 1, 4)
            mitten = [p + r * laenge * u + np.array((0, 0, -haengen * laenge * u * u)) for u in us]
            quer = [d * max(0.002, laenge * schmal * 0.5 * (1 - u) ** 0.7) for u in us]
            streifen(mitten, quer, [t] * 4)
    return np.array(V), np.array(F), np.array(T)

def rosette(rng, anzahl, kopf, L, B, auf, bogen, **kw):
    """Wedel rundherum um den Punkt 'kopf' (Krone)."""
    V, F, T = [], [], []
    for i in range(anzahl):
        phi = 2 * math.pi * i / anzahl + rng.uniform(-0.25, 0.25)
        v, f, t = wedel(rng, L * rng.uniform(0.75, 1.1), B, auf + rng.uniform(-12, 12), bogen * rng.uniform(0.8, 1.2), **kw)
        R = np.array(Matrix.Rotation(phi, 3, "Z"))
        F.append(f + sum(len(x) for x in V))
        V.append(v @ R.T + np.array(kopf) + np.array((math.cos(phi), math.sin(phi), 0)) * 0.03)
        T.append(t)
    return np.concatenate(V), np.concatenate(F), np.concatenate(T)

def stamm(punkte, r0, r1, segs=12):
    """Stamm als Rohr mit linear abnehmendem Radius (Ecken je Ring nach aussen geschoben)."""
    pts = [Vector(p) for p in punkte]
    bm = rohr(pts, 1.0, segs=segs, deckel=False)
    n = len(pts)
    for i, v in enumerate(bm.verts):
        ring = i // segs
        t = ring / max(n - 1, 1)
        mitte = pts[ring]
        v.co = mitte + (v.co - mitte) * (r0 + (r1 - r0) * t)
    return bm

def bm_netz(name, bm, mats):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    me.shade_smooth()
    return me

def krone_anhaengen(me, v, f, t):
    """Wedel (Ecken, Vierecke, Lage t) an ein vorhandenes Stamm-Mesh haengen, mit Materialindex 1."""
    bm = bmesh.new()
    bm.from_mesh(me)
    lay = bm.verts.layers.float.get("t") or bm.verts.layers.float.new("t")     # Ebene vor den neuen Ecken anlegen
    vs = [bm.verts.new(p) for p in v]
    for vv, tt in zip(vs, t):
        vv[lay] = tt
    for q in f:
        fc = bm.faces.new([vs[j] for j in q])
        fc.material_index = 1
        fc.smooth = True
    bm.to_mesh(me)
    bm.free()

def pflanzen_vorlagen():
    """Einige Varianten je Pflanzenart als Mesh-Daten (werden in der Szene vielfach verlinkt)."""
    rng = np.random.default_rng(21)
    m_farn = blatt_material("Farn", "#2f4a1a", "#4d6a22")
    m_palm = blatt_material("Palmfarn", "#2a4220", "#3e5a26", spitze="#6b7a3a", rau=0.35, durch=0.2)
    m_baumfarn = blatt_material("Baumfarn", "#2c4a1c", "#466b25")
    m_halm = blatt_material("Schachtelhalm", "#3a5222", "#58702c", spitze="#5a5a2a", durch=0.15)
    m_rinde = rinde_material("Rinde_Nadelbaum", "#3a2a1e", "#6a4b34")
    m_rinde_f = rinde_material("Rinde_Baumfarn", "#241b14", "#3e3022", streck=(8, 8, 2.5), skala=4.0, bump=0.9)
    m_rinde_p = rinde_material("Rinde_Palmfarn", "#3a3226", "#5d5240", streck=(6, 6, 6), skala=2.5, bump=1.0)
    m_rinde_l = rinde_material("Rinde_Laubbaum", "#4a4236", "#6e6452", streck=(4, 4, 1.5), skala=2.0, bump=0.4)
    m_nadel = laub_material("Nadeln", "#1f3118", "#2f4520", loch_skala=12.0)
    m_laub = blatt_material("Palmwedel", "#2c4418", "#4b6626", spitze="#7a7a36", rau=0.38, durch=0.25)
    V = {}
    for i in range(3):                                           # Farne
        v, f, t = rosette(rng, int(rng.integers(10, 15)), (0, 0, 0.02), 1.25, 0.30, 62, 115)
        V.setdefault("farn", []).append(netz_aus(f"Farn_{i}", v, f, [m_farn], {"t": t}))
    for i in range(2):                                           # Palmfarne: kurzer Stamm, steife Wedel
        h = 0.7 + 0.4 * i
        bm = stamm([(0, 0, -0.1), (0, 0, h * 0.5), (0, 0, h)], 0.28, 0.22, segs=14)
        v, f, t = rosette(rng, 20, (0, 0, h), 1.5, 0.22, 48, 38, schmal=0.09, haengen=0.05, winkel=62)
        me = bm_netz(f"Palmfarn_{i}", bm, [m_rinde_p, m_palm])
        krone_anhaengen(me, v, f, t)
        V.setdefault("palmfarn", []).append(me)
    for i in range(2):                                           # Baumfarne: schlanker Stamm, grosse Krone
        h = 3.6 + 1.2 * i
        bieg = rng.uniform(-0.3, 0.3, 2)
        pts = [(bieg[0] * (k / 6) ** 2, bieg[1] * (k / 6) ** 2, h * k / 6) for k in range(7)]
        bm = stamm(pts, 0.2, 0.13, segs=12)
        v, f, t = rosette(rng, 13, pts[-1], 2.6, 0.55, 40, 95, fiedern=30)
        me = bm_netz(f"Baumfarn_{i}", bm, [m_rinde_f, m_baumfarn])
        krone_anhaengen(me, v, f, t)
        V.setdefault("baumfarn", []).append(me)
    for i in range(3):                                           # Nadelbaeume: hohe Staemme, Brettwurzeln, Aeste oben
        h = 30 + 6 * i
        bm = bmesh.new()
        r = 0.55 + 0.2 * i
        pts = [(0, 0, -0.5)] + [(0.15 * math.sin(k * 0.7 + i), 0.15 * math.cos(k * 0.5 + i), h * k / 10) for k in range(1, 11)]
        einfuegen(bm, stamm(pts, r * 1.15, r * 0.35, segs=16))
        for k in range(5):                                       # Brettwurzeln
            w = 2 * math.pi * k / 5 + i
            d = np.array((math.cos(w), math.sin(w), 0))
            einfuegen(bm, stamm([tuple(d * r * 0.4 + (0, 0, 1.6)), tuple(d * r * 1.6 + (0, 0, 0.2)), tuple(d * r * 2.6 + (0, 0, -0.3))],
                                0.22 * r / 0.55, 0.06, segs=8))
        for k in range(14):                                      # Aeste im oberen Drittel
            z0 = h * (0.62 + 0.36 * k / 14)
            w = k * 2.4 + i
            d = np.array((math.cos(w), math.sin(w), 0.25))
            l = 4.5 * (1 - 0.6 * k / 14)
            einfuegen(bm, stamm([(0, 0, z0), tuple(d * l * 0.5 + (0, 0, z0)), tuple(d * l + (0, 0, z0 - 0.6))], 0.16, 0.04, segs=6))
            for j in range(4):
                p = d * l * rng.uniform(0.45, 1.05) + rng.normal(0, 0.5, 3) * (1, 1, 0.4) + (0, 0, z0 - 0.3)
                bueschel(bm, tuple(p), rng.uniform(0.8, 1.4), 0.55, rng=rng)
        bueschel(bm, (0, 0, h + 0.5), 2.2, 0.8, rng=rng)
        V.setdefault("baum", []).append(bm_netz(f"Nadelbaum_{i}", bm, [m_rinde, m_nadel]))
    for i in range(3):                                           # Palmen im Unterholz: schlank, leicht gebogen
        h = 6.5 + 1.6 * i
        bieg = rng.uniform(-0.8, 0.8, 2)
        pts = [(bieg[0] * (k / 8) ** 2, bieg[1] * (k / 8) ** 2, h * k / 8) for k in range(9)]
        bm = stamm(pts, 0.2, 0.15, segs=12)
        me = bm_netz(f"Palme_{i}", bm, [m_rinde_l, m_laub])
        v, f, t = rosette(rng, 15, pts[-1], 3.4, 0.62, 34, 105, fiedern=34, schmal=0.13, haengen=0.35, winkel=70)
        krone_anhaengen(me, v, f, t)
        V.setdefault("laubbaum", []).append(me)
    for i in range(2):                                           # Schachtelhalm-Buesche
        bm = bmesh.new()
        lay = None
        for k in range(int(rng.integers(14, 22))):
            w = rng.uniform(0, 2 * math.pi)
            r0 = rng.uniform(0, 0.25)
            h = rng.uniform(0.6, 1.4)
            neig = rng.uniform(0.05, 0.25)
            b = np.array((r0 * math.cos(w), r0 * math.sin(w), 0))
            e = b + np.array((neig * math.cos(w), neig * math.sin(w), h))
            einfuegen(bm, stamm([tuple(b), tuple((b + e) / 2), tuple(e)], 0.012, 0.004, segs=5))
        V.setdefault("halm", []).append(bm_netz(f"Schachtelhalm_{i}", bm, [m_halm]))
    return V

def fels(rng, name, m):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
    s = rng.uniform(0.7, 1.3, 3) * np.array((1.3, 1.0, 0.65))
    off = rng.uniform(0, 100, 3)
    for v in bm.verts:
        p = np.array(v.co)
        d = 1 + 0.18 * math.sin(3 * p[0] + off[0]) * math.cos(2.5 * p[1] + off[1]) + 0.1 * math.sin(5 * p[2] + off[2])
        v.co = Vector(p * s * d)
    return bm_netz(name, bm, [m])

# ---------- Gelaende und Verteilung ----------
LICHTUNG = (-0.8, 0.0, 10.5, 6.8)          # Mitte x, y und Halbachsen der flachen Lichtung
SICHTACHSEN = [((11.0, -6.2), (1.2, 0.0)), ((8.7, -5.0), (3.4, 0.2))]   # Kamera und Ziel der Dschungelbilder
SONNE_HOEHE, SONNE_RICHTUNG = math.radians(48), math.radians(14)        # Gegenlicht von hinten links
DACH_H = 21.0                                                          # Hoehe des (unsichtbaren) Blaetterdachs

def sonnen_licht():
    """Richtung, in die das Sonnenlicht laeuft (nach unten)."""
    return Vector((math.cos(SONNE_HOEHE) * math.cos(SONNE_RICHTUNG), math.cos(SONNE_HOEHE) * math.sin(SONNE_RICHTUNG),
                   -math.sin(SONNE_HOEHE)))

def gelaende_hoehe(x, y):
    cx, cy, ax, ay = LICHTUNG
    r = np.sqrt(((x - cx) / ax) ** 2 + ((y - cy) / ay) ** 2)
    h = 0.35 * np.sin(0.21 * x + 1.3) * np.cos(0.17 * y + 0.4) + 0.18 * np.sin(0.53 * x - 0.7 * y) \
        + 0.08 * np.sin(1.3 * x + 0.9 * y)
    h = h + 0.03 * np.maximum(r - 1.6, 0) ** 2 * (1 + 0.5 * np.sin(0.1 * x))       # Gelaende steigt nach aussen an
    return h * np.clip((r - 0.85) / 0.6, 0, 1)

def gelaende(m):
    n, gr = 260, 130.0
    u = np.linspace(-gr / 2, gr / 2, n)
    X, Y = np.meshgrid(u, u, indexing="ij")
    Z = gelaende_hoehe(X, Y)
    V = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
    i = np.arange(n - 1)
    I, J = np.meshgrid(i, i, indexing="ij")
    a = (I * n + J).ravel()
    F = np.stack([a, a + n, a + n + 1, a + 1], 1)
    return netz_aus("Waldboden", V, F, [m])

def strecken_abstand(x, y, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    t = max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / max(dx * dx + dy * dy, 1e-9)))
    return math.hypot(x - x0 - t * dx, y - y0 - t * dy)

def verteilen(rng, anzahl, r_min, r_max, abstand, belegt, meiden=()):
    """Zufaellige Orte im Ring um die Lichtung (elliptischer Abstand r_min..r_max), mit Mindestabstand."""
    cx, cy, ax, ay = LICHTUNG
    orte = []
    versuche = 0
    while len(orte) < anzahl and versuche < anzahl * 60:
        versuche += 1
        w = rng.uniform(0, 2 * math.pi)
        r = math.sqrt(rng.uniform(r_min ** 2, r_max ** 2))
        x, y = cx + ax * r * math.cos(w), cy + ay * r * math.sin(w)
        if any(strecken_abstand(x, y, *m[:4]) < m[4] for m in meiden):
            continue
        if any(math.hypot(x - bx, y - by) < 0.5 * (abstand + ba) for bx, by, ba in belegt):
            continue
        belegt.append((x, y, abstand))
        orte.append((x, y))
    return orte

def setzen(c, me, x, y, rng, skala=(0.8, 1.2), neigung=0.08):
    ob = bpy.data.objects.new(me.name, me)
    c.objects.link(ob)
    z = float(gelaende_hoehe(np.array(x), np.array(y)))
    ob.location = (x, y, z)
    ob.rotation_euler = (rng.normal(0, neigung), rng.normal(0, neigung), rng.uniform(0, 2 * math.pi))
    ob.scale = (rng.uniform(*skala),) * 3
    return ob

def dschungel_bauen():
    """Die Lichtung: Gelaende, Pflanzen, Felsen, Nebel, Sonne mit Blaetterdach-Schatten und Himmel."""
    log("Dschungel ...")
    c = sammlung("Dschungel")
    rng = np.random.default_rng(7)
    in_sammlung(bpy.data.objects.new("Waldboden", gelaende(boden_material())), c)
    V = pflanzen_vorlagen()
    belegt = []
    hoch = [(k[0], k[1], z[0], z[1], 2.6) for k, z in SICHTACHSEN]          # Sichtachsen der Kameras frei halten
    L = sonnen_licht()
    weit = 44.0 / math.tan(SONNE_HOEHE)                                       # Lichtschneise bis ueber die Kronen
    hoch.append((0.5, 0.3, 0.5 - L.x / L.xy.length * weit, 0.3 - L.y / L.xy.length * weit, 6.5))
    flach = [(k[0], k[1], k[0], k[1], 1.6) for k, z in SICHTACHSEN]          # niedrige Pflanzen nur nicht direkt davor
    for x, y in verteilen(rng, 46, 1.9, 4.6, 3.2, belegt, hoch):
        setzen(c, V["baum"][int(rng.integers(3))], x, y, rng, (0.85, 1.15), 0.02)
    for x, y in verteilen(rng, 34, 1.5, 4.2, 4.0, belegt, hoch):
        setzen(c, V["laubbaum"][int(rng.integers(3))], x, y, rng, (0.8, 1.2), 0.06)
    for x, y in verteilen(rng, 60, 1.2, 3.6, 1.6, belegt, hoch):
        setzen(c, V["baumfarn"][int(rng.integers(2))], x, y, rng, (0.8, 1.3), 0.12)
    for x, y in verteilen(rng, 70, 1.0, 3.4, 1.2, belegt, hoch):
        setzen(c, V["palmfarn"][int(rng.integers(2))], x, y, rng, (0.75, 1.25), 0.06)
    m_fels = fels_material()
    for i, (x, y) in enumerate(verteilen(rng, 22, 1.0, 2.6, 2.0, belegt, hoch)):
        ob = in_sammlung(bpy.data.objects.new(f"Fels_{i}", fels(rng, f"Fels_{i}", m_fels)), c)
        ob.location = (x, y, float(gelaende_hoehe(np.array(x), np.array(y))) - 0.2)
        ob.rotation_euler = (0, 0, rng.uniform(0, 6.3))
        ob.scale = (rng.uniform(0.4, 1.3),) * 3
    for x, y in verteilen(rng, 1100, 0.92, 3.6, 0.75, belegt, flach):
        setzen(c, V["farn"][int(rng.integers(3))], x, y, rng, (0.7, 1.45), 0.1)
    for x, y in verteilen(rng, 260, 0.85, 3.2, 0.6, belegt, flach):
        setzen(c, V["halm"][int(rng.integers(2))], x, y, rng, (0.7, 1.3), 0.05)
    # Ein paar kleine Farne und Schachtelhalme auch in der Lichtung (nicht unter den Fuessen)
    for x, y in verteilen(rng, 26, 0.55, 0.95, 0.9, belegt, flach + [(0.6, 0.0, 0.6, 0.0, 3.0), (-3.5, 0, -3.5, 0, 3.0)]):
        setzen(c, V["farn"][int(rng.integers(3))], x, y, rng, (0.5, 0.9), 0.1)
    # Umgestuerzter Stamm am Rand der Lichtung
    m_rinde = bpy.data.materials["Rinde_Nadelbaum"]
    for i, (a, b, r) in enumerate((((-9.5, 6.5, 0.4), (2.5, 10.5, 0.7), 0.55), ((-13, -6, 0.3), (-6, -11, 0.5), 0.4))):
        bm = stamm([a, tuple((np.array(a) + np.array(b)) / 2 + (0, 0, 0.1)), b], r, r * 0.8, segs=14)
        ob = in_sammlung(bpy.data.objects.new(f"Stamm_{i}", bm_netz(f"Stamm_{i}", bm, [m_rinde])), c)
    # Ferner Waldrand: innen bemalter Zylinder hinter dem Nebel (nur fuer die Kamera)
    bm = bmesh.new()
    ring_u = [bm.verts.new((58 * math.cos(w), 58 * math.sin(w), -1)) for w in np.linspace(0, 2 * math.pi, 97)[:-1]]
    ring_o = [bm.verts.new((58 * math.cos(w), 58 * math.sin(w), 90)) for w in np.linspace(0, 2 * math.pi, 97)[:-1]]
    for k in range(96):
        bm.faces.new((ring_u[(k + 1) % 96], ring_u[k], ring_o[k], ring_o[(k + 1) % 96]))
    m, nt, bs, K = mat_knoten("Waldrand")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    Q = K.v("MULTIPLY", tc.outputs["Object"], (1.0, 1.0, 0.12))
    stamm_m = K.glatt(K.rauschen(Q, 0.9, detail=3), 0.55, 0.62)
    laub = K.rauschen(K.geometrie()[0], 0.3, detail=6)
    farbe = mischen(K, farb_knoten(K, "#121a0d"), farb_knoten(K, "#1f2a14"), laub)
    farbe = mischen(K, farbe, farb_knoten(K, "#1c1610"), K.mul(stamm_m, 0.7))
    nt.nodes.remove(bs)                       # selbstleuchtend: ferner Wald im Dunst, unabhaengig von der Sonne
    em = nt.nodes.new("ShaderNodeEmission")
    K.ein(em.inputs["Color"], farbe)
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    wand = in_sammlung(bpy.data.objects.new("Waldrand", bm_netz("Waldrand", bm, [m])), c)
    wand.visible_diffuse = wand.visible_glossy = wand.visible_shadow = False
    # Nebel: duenner Dunst im ganzen Wald, dichter am Boden
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    nebel = in_sammlung(bpy.data.objects.new("Nebel", bm_netz("Nebel", bm, [])), c)
    nebel.scale = (112, 112, DACH_H - 0.3)
    nebel.location = (0, 0, (DACH_H - 0.3) / 2 - 0.5)
    m, nt, bs, K = mat_knoten("Nebel")
    nt.nodes.remove(bs)
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    P = K.geometrie()[0]
    z = K.trenne(P)[2]
    dichte = K.add(0.0042, K.mul(0.016, K.m("EXPONENT", K.mul(z, -0.5))),
                   K.mul(0.006, K.glatt(K.rauschen(P, 0.08, detail=2), 0.4, 0.7), K.m("EXPONENT", K.mul(z, -0.25))))
    K.ein(vol.inputs["Density"], dichte)
    vol.inputs["Color"].default_value = (*hexf("#d9d6c8"), 1)
    vol.inputs["Anisotropy"].default_value = 0.7
    nt.links.new(vol.outputs["Volume"], nt.nodes["Material Output"].inputs["Volume"])
    nebel.data.materials.append(m)
    # Sonne von links hinten (aus Sicht der Hauptkamera) und ein unsichtbares Blaetterdach mit Luecken
    hoehe, richtung = SONNE_HOEHE, SONNE_RICHTUNG
    d = bpy.data.lights.new("Sonne", "SUN")
    d.energy = 6.0
    d.angle = math.radians(0.6)
    d.color = (1.0, 0.93, 0.82)
    sonne = in_sammlung(bpy.data.objects.new("Sonne", d), c)
    sonne.rotation_euler = L.to_track_quat("-Z", "Y").to_euler()
    d = bpy.data.lights.new("Aufheller", "AREA")
    d.shape, d.size, d.size_y, d.energy, d.color = "RECTANGLE", 12, 9, 650, (0.85, 0.92, 1.0)
    auf = in_sammlung(bpy.data.objects.new("Aufheller", d), c)
    auf.location = (18, -12, 8)
    auf.rotation_euler = (Vector((1, 0, 2.5)) - Vector((18, -12, 8))).to_track_quat("-Z", "Y").to_euler()
    auf.visible_camera = False
    auf.visible_volume_scatter = False
    H = DACH_H
    loch = Vector((0.5, 0.3, 2.5)) - L * ((H - 2.5) / -L.z)          # Luecke, durch die die Sonne auf das Tier faellt
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=80)
    dach = in_sammlung(bpy.data.objects.new("Blaetterdach", bm_netz("Blaetterdach", bm, [])), c)
    dach.location = (0, 0, H)
    dach.visible_camera = False
    dach.visible_glossy = False
    m, nt, bs, K = mat_knoten("Blaetterdach")
    P = K.geometrie()[0]
    x, y, _ = K.trenne(P)
    offen = K.glatt(K.rauschen(P, 0.22, detail=6, rau=0.6), 0.52, 0.56)
    r = K.m("SQRT", K.add(K.mul(K.add(x, -loch.x), K.add(x, -loch.x)), K.mul(K.add(y, -loch.y), K.add(y, -loch.y))))
    offen = K.max(offen, K.glatt(r, 9.0, 6.0))
    cx, cy, ax, ay = LICHTUNG                                         # ueber der Lichtung offen
    r2 = K.m("SQRT", K.add(K.mul(K.add(x, -cx), K.add(x, -cx), 1 / ax ** 2), K.mul(K.add(y, -cy), K.add(y, -cy), 1 / ay ** 2)))
    offen = K.max(offen, K.glatt(r2, 1.0, 0.7))
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    bs.inputs["Base Color"].default_value = (*hexf("#1d2a12"), 1)
    bs.inputs["Roughness"].default_value = 0.9
    mix = nt.nodes.new("ShaderNodeMixShader")
    K.ein(mix.inputs[0], offen)
    nt.links.new(bs.outputs["BSDF"], mix.inputs[1])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], nt.nodes["Material Output"].inputs["Surface"])
    dach.data.materials.append(m)
    # Himmel (ohne eigene Sonnenscheibe, die Sonne ist die Lampe)
    w = bpy.data.worlds.new("Himmel")
    w.use_nodes = True
    sky = w.node_tree.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_disc = False
    sky.sun_elevation = hoehe
    sky.sun_rotation = richtung + math.pi
    sky.air_density, sky.dust_density = 1.0, 2.5
    bg = w.node_tree.nodes["Background"]
    w.node_tree.links.new(sky.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.8
    log(f"  Dschungel: {len(c.objects)} Objekte")
    return c, w

def studio_bauen():
    """Fotostudio: runde Hohlkehle (Boden geht ohne Kante in die Wand ueber), grosse Softboxen."""
    c = sammlung("Studio")
    bm = bmesh.new()
    prof = [(0.0, 0.0), (20.0, 0.0), (32.0, 0.0)] + [(32.0 + 7.0 * math.sin(w), 7.0 - 7.0 * math.cos(w))
                                                  for w in np.linspace(0.15, math.pi / 2, 9)] + [(39.0, 40.0)]
    ringe = []
    for w in np.linspace(0, 2 * math.pi, 129)[:-1]:
        ringe.append([bm.verts.new((r * math.cos(w), r * math.sin(w), z)) for r, z in prof])
    for i in range(len(ringe)):
        r0, r1 = ringe[i], ringe[(i + 1) % len(ringe)]
        for k in range(len(prof) - 1):
            bm.faces.new((r0[k], r1[k], r1[k + 1], r0[k + 1]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    m, nt, bs, K = mat_knoten("Studioboden")
    bs.inputs["Base Color"].default_value = (*hexf("#63666a"), 1)
    bs.inputs["Roughness"].default_value = 0.6
    kehle = in_sammlung(bpy.data.objects.new("Hohlkehle", bm_netz("Hohlkehle", bm, [m])), c)
    for n in ("Hohlkehle",):
        for p in bpy.data.meshes[n].polygons:
            p.use_smooth = True
    flaechenlicht("Hauptlicht", (9, 13, 12), (0.5, 0, 2.4), 8, 6, 7000, c, (1.0, 0.96, 0.9))
    flaechenlicht("Fuelllicht", (12, -11, 5), (0.5, 0, 2.2), 10, 7, 2200, c, (0.9, 0.95, 1.0))
    flaechenlicht("Kante", (-12, -7, 10), (0, 0, 2.8), 7, 5, 3200, c)
    flaechenlicht("Oben", (0, 0, 18), (0, 0, 0), 16, 8, 900, c)
    w = welt(hexf("#5d6066"), 0.3)
    return c, w

# ---------------- Vorschaubilder ----------------
# dschungel: das Tier kommt durch die Lichtung auf die Kamera zu (Laufen); bruellen: Nahaufnahme beim Bruellen;
# seite, vorne, kopf: Fotostudio. Jedes Bild t_rex_<name>.png neben dem Skript.
BILDER = {   # Name: (Szene, Aktion, Bild, Kamera, Ziel, Brennweite, Blende)
    "dschungel": ("dschungel", "Walk", 8, (11.0, -6.2, 1.35), (1.2, 0.0, 2.8), 28, 8.0),
    "bruellen": ("dschungel", "Roar", 46, (8.7, -5.0, 1.9), (3.4, 0.2, 3.3), 30, 5.6),
    "seite": ("studio", "Idle", 0, (-1.0, 27.0, 2.4), (-1.0, 0.0, 1.95), 58, None),
    "vorne": ("studio", "Idle", 0, (13.0, -8.5, 4.2), (0.4, 0.0, 2.1), 42, None),
    "kopf": ("studio", "Idle", 0, (7.6, -3.6, 4.0), (4.3, 0.0, 3.3), 55, None),
}

VIDEOS = [v for v in os.environ.get("VIDEOS", "laufen,bruellen").split(",") if v]
VIDEO_AKTION = {"laufen": ("Walk", 2), "bruellen": ("Roar", 1), "stehen": ("Idle", 1)}   # Aktion, Durchlaeufe

def videos_rendern(teile, cam, cd):
    """Kurze Videos der Animationen im Studio (800 x 450, H.264): t_rex_laufen.mp4 (zwei Doppelschritte),
    t_rex_bruellen.mp4."""
    for n, (c, w) in teile.items():
        c.hide_render = n != "studio"
    scene.world = teile["studio"][1]
    scene.view_settings.look = "AgX - Medium High Contrast"
    ort, ziel = Vector((14.5, -9.5, 4.0)), Vector((0.2, 0.0, 2.0))
    cam.location = ort
    cam.rotation_euler = (ziel - ort).to_track_quat("-Z", "Y").to_euler()
    cd.lens, cd.dof.use_dof = 40, False
    alt = (scene.render.resolution_x, scene.render.resolution_y, scene.cycles.samples)
    scene.render.resolution_x, scene.render.resolution_y = 800, 450
    scene.cycles.samples = int(os.environ.get("VIDEO_SAMPLES", "8"))
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    for name in VIDEOS:
        if name not in VIDEO_AKTION:
            continue
        aktion, runden = VIDEO_AKTION[name]
        act = AKTIONEN[aktion]
        mods = [(fc, fc.modifiers.new("CYCLES")) for fc in act.fcurves] if runden > 1 else []
        RIG.animation_data.action = act
        f0, f1 = (int(round(v)) for v in act.frame_range)
        scene.frame_start = f0
        scene.frame_end = f0 + (f1 - f0) * runden - (1 if aktion != "Roar" else 0)   # Schleifen ohne doppeltes Endbild
        scene.render.filepath = os.path.join(OUT, f"{DATEI}_{name}.mp4")
        t0 = time.time()
        bpy.ops.render.render(animation=True)
        log(f"Video {name}: {scene.frame_end - scene.frame_start + 1} Bilder ({time.time() - t0:.0f} s)")
        for fc, m in mods:
            fc.modifiers.remove(m)
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_x, scene.render.resolution_y, scene.cycles.samples = alt
    scene.frame_start, scene.frame_end = 0, 120

def bilder_rendern():
    teile = {}
    if any(BILDER[s][0] == "dschungel" for s in SHOTS if s in BILDER):
        teile["dschungel"] = dschungel_bauen()
    if any(BILDER[s][0] == "studio" for s in SHOTS if s in BILDER) or VIDEOS:
        teile["studio"] = studio_bauen()
    cd = bpy.data.cameras.new("Kamera")
    cd.clip_start, cd.clip_end = 0.1, 400
    cam = bpy.data.objects.new("Kamera", cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.engine = "CYCLES"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces, scene.cycles.glossy_bounces = 3, 2
    scene.cycles.transmission_bounces, scene.cycles.transparent_max_bounces = 4, 12
    scene.cycles.volume_bounces = 0
    scene.cycles.volume_step_rate = 3.0
    scene.cycles.sample_clamp_indirect = 6.0
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.image_settings.file_format = "PNG"
    for name in SHOTS:
        if name not in BILDER:
            log("unbekanntes Bild:", name)
            continue
        art, aktion, bild_nr, ort, ziel, lens, blende = BILDER[name]
        for n, (c, w) in teile.items():
            c.hide_render = n != art
        scene.world = teile[art][1]
        ort, ziel = Vector(ort), Vector(ziel)
        if art == "dschungel":                    # Kamerahoehe ueber dem Gelaende
            ort.z += float(gelaende_hoehe(np.array(ort.x), np.array(ort.y)))
        cam.location = ort
        cam.rotation_euler = (ziel - ort).to_track_quat("-Z", "Y").to_euler()
        cd.lens = lens
        cd.dof.use_dof = blende is not None
        if blende is not None:
            cd.dof.aperture_fstop = blende
            cd.dof.focus_distance = (ziel - ort).length
        scene.view_settings.look = "AgX - Punchy" if art == "dschungel" else "AgX - Medium High Contrast"
        zeige(aktion, bild_nr)
        scene.render.filepath = os.path.join(OUT, f"{DATEI}_{name}.png")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        log(f"Bild {name} ({time.time() - t0:.0f} s)")
    if VIDEOS and "studio" in teile:
        videos_rendern(teile, cam, cd)
    if "dschungel" in teile:                      # die .blend oeffnet mit der Lichtung
        teile["dschungel"][0].hide_render = False
        scene.world = teile["dschungel"][1]
        if "studio" in teile:
            teile["studio"][0].hide_render = True
            teile["studio"][0].hide_viewport = True

if SHOTS or VIDEOS:
    bilder_rendern()
zeige("Idle", 0)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, DATEI + ".blend"))
bpy.ops.file.make_paths_relative()                # Texturen relativ (export/Texturen), dann noch einmal speichern
bpy.ops.wm.save_mainfile()
log("gespeichert:", DATEI + ".blend")

