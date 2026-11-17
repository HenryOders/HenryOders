# Streifenwagen fuer Spiele: eigenes Kombi-Design (keine echte Automarke), blau-silberne POLIZEI-Beklebung.
# Erzeugt die Karosserie mit echten Spaltmassen, versenkten Scheiben und Leuchten mit Innenleben, Raeder mit
# Reifenprofil, einen Innenraum, Texturen, ein Skelett fuer Unreal Engine 5 (root + vier Radknochen),
# den Export als FBX und glTF sowie Vorschaubilder (Fotostudio und Strasse bei Nacht).
# Start: blender -b -P polizeiauto.py   (oder mit dem bpy-Modul: python polizeiauto.py)
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

OUT = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(OUT, "export")
TEXDIR = os.path.join(EXPORT, "Texturen")
os.makedirs(TEXDIR, exist_ok=True)
SHOTS = [s for s in os.environ.get("SHOTS", "vorne,hinten,seite,oben,detail,nacht").split(",") if s]
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
LAENGE, BREITE = 4.80, 1.89
RADSTAND, SPUR = 2.84, 1.60
XV, XH = RADSTAND / 2, -RADSTAND / 2          # Vorder- und Hinterachse
RAD_R, RAD_B = 0.335, 0.235                   # Reifenradius, Reifenbreite (245/45 R18)
FELGE_R = 0.229                               # 18 Zoll
BOGEN_R = 0.372                               # Radlauf
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

# Reifen-UV: u = 1/8 Umfang je Kachel, v = Profil von innen (0) nach aussen (1)
REIFEN_V = {"lauf0": 0.34, "lauf1": 0.66}
def textur_reifen(w=1024, h=512, seed=11):
    rng = np.random.default_rng(seed)
    U, V = np.meshgrid((np.arange(w) + 0.5) / w, (np.arange(h) + 0.5) / h, indexing="ij")
    hoehe = np.zeros((w, h))
    kante = lambda d, breite, weich: np.clip((breite / 2 - np.abs(d)) / weich + 0.5, 0, 1)
    teilung = 1 / 9                                       # 9 Bloecke je Kachel (ca. 2,9 cm)
    # Querrillen in den Schulterrippen, leicht schraeg, laufen zur Flanke aus
    for v0, v1, sg in ((0.27, 0.405, -1), (0.595, 0.73, 1)):
        zone = np.clip((V - v0) / 0.01, 0, 1) * np.clip((v1 - V) / 0.01, 0, 1)
        auslauf = np.clip((0.5 - np.abs(V - 0.5) - 0.23) / 0.04, 0, 1)
        ph = (U / teilung + sg * 1.6 * (V - 0.5)) % 1.0
        hoehe -= 0.006 * kante(ph - 0.5, 0.16, 0.03) * zone * (0.35 + 0.65 * auslauf)
    # Lamellen (feine Schlitze) in den Mittelrippen
    for v0, v1 in ((0.412, 0.458), (0.474, 0.526), (0.542, 0.588)):
        zone = np.clip((V - v0) / 0.004, 0, 1) * np.clip((v1 - V) / 0.004, 0, 1)
        ph = (U / (teilung / 2) + 2.2 * (V - 0.5)) % 1.0
        hoehe -= 0.003 * kante(ph - 0.5, 0.06, 0.02) * zone
    # Flanke: feine Ringe am Felgenhorn, Riffelband, erhabene Schriftbloecke (ohne lesbaren Text)
    for vr in (0.0, 1.0):
        nah = np.clip(1 - np.abs(V - vr) / 0.07, 0, 1)
        hoehe += 0.0005 * np.sin(2 * np.pi * V * h / 5) * nah
    for v0, v1 in ((0.17, 0.205), (0.795, 0.83)):
        zone = np.clip((V - v0) / 0.004, 0, 1) * np.clip((v1 - V) / 0.004, 0, 1)
        hoehe += 0.0004 * (np.sin(2 * np.pi * U * w / 6) > 0.3) * zone
    for v0, v1 in ((0.10, 0.15), (0.85, 0.90)):
        for _ in range(26):
            u0, bu = rng.random(), 0.004 + 0.012 * rng.random()
            du = (U - u0 + 0.5) % 1.0 - 0.5
            hoehe += 0.0008 * (np.abs(du) < bu) * (V > v0) * (V < v1)
    meter_u = 2 * np.pi * RAD_R / 8 / w
    meter_v = 0.43 / h
    nrm = normal_aus_hoehe(hoehe, meter_u, meter_v)
    # Grundfarbe: Gummi, in Rillen dunkler, Flanke minimal heller und leicht fleckig
    tief = np.clip(-hoehe / 0.006, 0, 1)
    flanke = np.clip((np.abs(V - 0.5) * 2 - 0.42) / 0.58, 0, 1)
    wolke = np.zeros((w, h))
    for k in range(1, 5):
        wolke += np.sin(2 * np.pi * (k * 3 * U + rng.random())) * np.sin(2 * np.pi * (k * 2 * V + rng.random())) / k
    lin = 0.0105 * (1 - 0.5 * tief) * (1 + 0.15 * flanke) * (1 + 0.06 * wolke)
    srgb = np.clip(lin, 0, 1) ** (1 / 2.2)
    return bild("T_Reifen_N", nrm, farbe=False), bild("T_Reifen_BC", np.repeat(srgb[..., None], 3, -1), farbe=True)

# ---------------- Materialien ----------------
MATS = {}
def material(name, farbe, metall=0.0, rauheit=0.5, lack=0.0, lack_rau=0.03, durch=0.0, ior=1.45, leuchten=0.0,
             leucht_farbe=None, normal=None, normal_uv="UVMap", normal_skala=1.0, normal_staerke=1.0,
             farb_bild=None, farb_uv="UVMap", farb_skala=1.0):
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
    bm.normal_update()
    for f in bm.faces:
        if f.normal.dot(d) > 0:
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
REIFEN_N, REIFEN_BC = textur_reifen()
FLAKE_SKALA = 25.0            # Flake-Kacheln je Meter auf der UV-Karte "UV_Flakes" (Wuerfelprojektion, 1 UV = 1 m)

def lack(name, farbe, metall):
    return material(name, farbe, metall=metall, rauheit=0.34, lack=1.0, lack_rau=0.015, normal=FLAKES,
                    normal_uv="UV_Flakes", normal_skala=FLAKE_SKALA, normal_staerke=0.3)

M_SILBER = lack("Lack_Silber", hexf("#c3c8cd"), 0.75)
M_BLAU = lack("Lack_Blau", hexf("#0e3172"), 0.55)
M_WEISS = material("Reflexfolie_Weiss", hexf("#eef0f0"), rauheit=0.36, lack=0.5, lack_rau=0.04)
M_SCHWARZ = material("Kunststoff_Schwarz", hexf("#151617"), rauheit=0.62)
M_GLAS = glas("Glas", hexf("#c4d2d0"))
M_GLAS_DUNKEL = glas("Glas_Getoent", hexf("#5f6867"))
M_TRIM = material("Hochglanz_Schwarz", hexf("#0b0c0d"), rauheit=0.1, lack=0.8, lack_rau=0.02)
M_SPALT = material("Spalt", hexf("#050505"), rauheit=0.9)
M_CHROM = material("Chrom", hexf("#dcdee0"), metall=1.0, rauheit=0.05)
M_SW_INNEN = material("Scheinwerfer_Innen", hexf("#7d838a"), metall=0.9, rauheit=0.25)
M_SW_GLAS = glas("Scheinwerfer_Glas", hexf("#f1f4f6"))
M_REFLEKTOR = material("Reflektor", hexf("#e6e8ea"), metall=1.0, rauheit=0.07)
M_LED = material("Tagfahrlicht", hexf("#ffffff"), rauheit=0.2, leuchten=2.5)
M_RL_GLAS = glas("Ruecklicht_Glas", hexf("#d0121a"))
M_RL_LED = material("Ruecklicht_LED", hexf("#b0141a"), rauheit=0.3, leuchten=0.8, leucht_farbe=hexf("#ff2020"))
M_BLAULICHT = material("Blaulicht", hexf("#1a4cff"), rauheit=0.25, leuchten=0.0, leucht_farbe=hexf("#2a5bff"))
M_BL_KAPPE = glas("Blaulicht_Kappe", hexf("#5b86ff"))
M_FOLIE = material("Folie_Blau", hexf("#0e3172"), rauheit=0.4)
M_GUMMI = material("Reifen", hexf("#1c1d1e"), rauheit=0.88, normal=REIFEN_N, farb_bild=REIFEN_BC)
M_FELGE = material("Felge", hexf("#c3c7cb"), metall=1.0, rauheit=0.2)
M_FELGE_DUNKEL = material("Felge_Innen", hexf("#3b3e41"), metall=0.85, rauheit=0.45)
M_BREMSE = material("Bremse", hexf("#5a5c5e"), metall=0.85, rauheit=0.38)
M_INNEN = material("Innenraum", hexf("#1e1f21"), rauheit=0.78)
M_INNEN_HELL = material("Innenraum_Stoff", hexf("#34363a"), rauheit=0.95)
M_SCHILD = material("Kennzeichen", hexf("#f2f2f0"), rauheit=0.35)
M_SCHILD_BLAU = material("Kennzeichen_Band", hexf("#1c3fa0"), rauheit=0.35)
M_ALU = material("Dachreling", hexf("#9097a0"), metall=0.85, rauheit=0.3)
M_BLINKER = material("Blinker", hexf("#b88a55"), rauheit=0.3, leuchten=0.0, leucht_farbe=hexf("#ff8a10"))

# ---------------- Karosserie: Querschnitte entlang X ----------------
Z_TOP = pchip([(2.40, 0.665), (2.37, 0.745), (2.32, 0.790), (2.20, 0.828), (1.80, 0.880), (1.40, 0.920), (1.20, 0.945),
               (0.95, 1.10), (0.65, 1.26), (0.40, 1.37), (0.20, 1.44), (-0.10, 1.475), (-1.00, 1.465), (-1.70, 1.43),
               (-1.98, 1.39), (-2.10, 1.27), (-2.22, 1.10), (-2.30, 0.98), (-2.36, 0.86), (-2.40, 0.70)])
Z_GURT = pchip([(2.40, 0.645), (2.30, 0.760), (2.00, 0.810), (1.40, 0.880), (1.20, 0.900), (0.00, 0.960), (-1.20, 0.995),
                (-1.90, 1.01), (-2.20, 0.98), (-2.32, 0.88), (-2.40, 0.68)])
Z_BODEN = pchip([(2.40, 0.27), (2.30, 0.235), (2.10, 0.21), (1.80, 0.20), (-1.80, 0.20), (-2.10, 0.22), (-2.30, 0.27),
                 (-2.40, 0.33)])
W = pchip([(2.40, 0.745), (2.36, 0.830), (2.28, 0.885), (2.10, 0.915), (1.80, 0.925), (1.40, 0.922), (0.00, 0.915),
           (-1.40, 0.922), (-1.90, 0.920), (-2.20, 0.905), (-2.33, 0.86), (-2.40, 0.78)])
W_TOP = pchip([(2.40, 0.63), (2.30, 0.73), (2.00, 0.785), (1.50, 0.80), (1.20, 0.79), (0.90, 0.765), (0.50, 0.73),
               (0.20, 0.715), (-1.00, 0.71), (-1.80, 0.70), (-2.00, 0.69), (-2.20, 0.72), (-2.32, 0.74), (-2.40, 0.68)])
WOELB = pchip([(2.40, 0.010), (2.20, 0.020), (1.25, 0.022), (0.25, 0.022), (0.0, 0.026), (-1.95, 0.024), (-2.10, 0.012),
               (-2.40, 0.008)])
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
    beule = math.exp(-((x - XV) / 0.46) ** 2) + math.exp(-((x - XH) / 0.46) ** 2)
    return 0.022 * beule * glatt01((t - 0.04) / 0.30) * glatt01((0.97 - t) / 0.25)

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

# Abschnitte (x von - bis) fuer Fenster, Saeulen und Wasserkasten
FENSTER_SEITE = [(-0.08, 1.12), (-1.06, -0.16), (-1.90, -1.16)]
B_SAEULE = (-0.16, -0.08)
FRONTSCHEIBE = (0.26, 1.16)
WASSERKASTEN = (1.16, 1.25)
HECKSCHEIBE = (-2.28, -2.00)

def stationen():
    xs = set(round(v, 4) for v in np.arange(-2.40, 2.4001, 0.06))
    for a, b in FENSTER_SEITE + [B_SAEULE, FRONTSCHEIBE, WASSERKASTEN, HECKSCHEIBE]:
        xs |= {round(a, 4), round(b, 4)}
    xs |= {-2.385, -2.37, -2.355, -2.335, 2.385, 2.37, 2.355, 2.335, -2.12, -2.06, 2.30, 2.25, 1.22, 1.10, 0.30, 0.18}
    out = []
    for x in sorted(xs):
        if not out or x - out[-1] > 0.012:
            out.append(x)
    if out[-1] != 2.40:
        out[-1] = 2.40
    return out

def bereich(x, ranges):
    return any(a <= x <= b for a, b in ranges)

# Materialindizes der Karosserie
K_SILBER, K_BLAU, K_WEISS, K_SCHWARZ, K_GLAS, K_TRIM, K_GLAS_D = range(7)

def flaechen_material(j, xm):
    """Materialindex fuer das Flaechenband j (zwischen Punkt j und j+1 der rechten Haelfte) bei x = xm."""
    if j <= 2:
        return K_SCHWARZ                           # Unterboden
    if j <= 6:
        return K_BLAU
    if j == 7:
        return K_WEISS                             # Reflexstreifen
    if j <= 11:
        return K_SILBER
    fenster = bereich(xm, FENSTER_SEITE)
    if j in (12, 13, 14, 15):
        if bereich(xm, [B_SAEULE]):
            return K_TRIM
        if fenster:
            if j in (13, 14):
                return K_GLAS if bereich(xm, [FENSTER_SEITE[0]]) else K_GLAS_D
            return K_TRIM
        return K_SILBER
    if bereich(xm, [WASSERKASTEN]):
        return K_SCHWARZ
    if bereich(xm, [FRONTSCHEIBE]):
        return K_TRIM if j == 16 else K_GLAS
    if bereich(xm, [HECKSCHEIBE]):
        return K_TRIM if j == 16 else K_GLAS_D
    return K_SILBER

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
    # Stirnflaechen vorn und hinten: eingerueckte Ringe (leicht gewoelbt) und ein Faecher zur Mitte,
    # Farbgrenzen wie an der Seite als waagrechte Schnitte
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
        zb, zg = Z_BODEN(x0), min(Z_GURT(x0), Z_TOP(x0) - WOELB(x0) - 0.004)
        grenzen = (zb, zb + (zg - zb) * 0.585)
        for zc in grenzen:
            fl = [f for f in bm.faces if f[kap] == k + 1]
            geom = fl + list({e for f in fl for e in f.edges}) + list({v for f in fl for v in f.verts})
            bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0, 0, zc), plane_no=(0, 0, 1))
        for f in bm.faces:
            if f[kap] == k + 1:
                z = f.calc_center_median().z
                f.material_index = K_SCHWARZ if z < grenzen[0] else K_BLAU if z < grenzen[1] else K_SILBER
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
        if len(mats) == 2 and K_TRIM in mats and (mats & {K_GLAS, K_GLAS_D, K_SILBER}):
            e[cl] = max(e[cl], 0.85)
    ob = objekt("Karosserie", bm, [M_SILBER, M_BLAU, M_WEISS, M_SCHWARZ, M_GLAS, M_TRIM, M_GLAS_DUNKEL], glatt=True)
    sub = ob.modifiers.new("Glaetten", "SUBSURF")
    sub.levels = sub.render_levels = 1
    sub.subdivision_type = "CATMULL_CLARK"
    anwenden(ob, sub)
    return ob

# ---------------- Ausschnitte: Radlaeufe, Leuchten, Grill, Lufteinlaesse, Griffmulden ----------------
VORN = dict(ursprung=(2.75, 0, 0), achse=(-1, 0, 0), e1=(0, 1, 0), e2=(0, 0, 1))
HINTEN = dict(ursprung=(-2.75, 0, 0), achse=(1, 0, 0), e1=(0, 1, 0), e2=(0, 0, 1))
def SEITE(sg):
    return dict(ursprung=(0, sg * 1.4, 0), achse=(0, -sg, 0), e1=(1, 0, 0), e2=(0, 0, 1))

def gespiegelt(umriss, sg):
    """Umriss (y, z) der linken Seite fuer sg = -1 spiegeln (Umlaufsinn bleibt gueltig)."""
    pts = [(sg * a, b) for (a, b) in umriss]
    return pts if sg > 0 else pts[::-1]

U_SCHEINWERFER = chaikin([(0.365, 0.592), (0.42, 0.578), (0.60, 0.574), (0.75, 0.588), (0.835, 0.612), (0.868, 0.645),
                          (0.852, 0.671), (0.76, 0.676), (0.58, 0.661), (0.40, 0.633)], 2)
U_GRILL = chaikin([(-0.30, 0.505), (0.30, 0.505), (0.335, 0.53), (0.345, 0.612), (0.32, 0.632), (-0.32, 0.632),
                   (-0.345, 0.612), (-0.335, 0.53)], 3)
U_EINLASS = chaikin([(-0.50, 0.278), (0.50, 0.278), (0.535, 0.31), (0.505, 0.352), (-0.505, 0.352), (-0.535, 0.31)], 3)
U_NEBEL = chaikin([(0.575, 0.300), (0.680, 0.305), (0.705, 0.395), (0.625, 0.420), (0.570, 0.385)], 3)
U_RUECKLICHT = chaikin([(0.50, 0.805), (0.68, 0.795), (0.82, 0.802), (0.872, 0.85), (0.865, 0.93), (0.80, 0.958),
                        (0.64, 0.935), (0.52, 0.885)], 3)
U_HECKBLITZER = chaikin([(0.30, 0.588), (0.42, 0.588), (0.42, 0.622), (0.30, 0.622)], 2)
GRIFFE = (0.55, -0.62)
def u_griffmulde(xg):
    return chaikin([(xg - 0.085, 0.855), (xg + 0.085, 0.855), (xg + 0.085, 0.897), (xg - 0.085, 0.897)], 3)

PATCHES = {}
BVH_ROH = None
def ausschnitte(kar):
    """Alle Schneidekoerper bauen, mit der unversehrten Karosserie als Projektionsflaeche."""
    global BVH_ROH
    bvh = BVH_ROH = bvh_von(kar)
    bm = bmesh.new()      # Materialien: 0 Radkasten, 1 Scheinwerfer innen, 2 Hochglanz schwarz, 3 Spalt, 4 Silber
    for name, (x, y) in RAEDER.items():
        einfuegen(bm, zylinder((x, math.copysign(0.92, y), RAD_R), BOGEN_R, 0.74, "Y", segs=56, mi=0))
    def aussparung(name, umriss, ansicht, tiefe, mi_wand, mi_boden, raster=0.012):
        pb, fehl = patch(umriss, ansicht["ursprung"], ansicht["achse"], ansicht["e1"], ansicht["e2"], bvh, raster)
        if fehl:
            log("  Warnung:", name, fehl, "Strahlen ohne Treffer")
        PATCHES[name] = pb
        einfuegen(bm, schale(pb, 0.03, tiefe, mi_wand, mi_boden))
    for sg, s in ((1, "l"), (-1, "r")):
        aussparung("scheinwerfer_" + s, gespiegelt(U_SCHEINWERFER, sg), VORN, 0.075, 1, 1, 0.010)
        aussparung("nebel_" + s, gespiegelt(U_NEBEL, sg), VORN, 0.05, 2, 2, 0.010)
        aussparung("ruecklicht_" + s, gespiegelt(U_RUECKLICHT, sg), HINTEN, 0.055, 2, 2, 0.010)
        aussparung("heckblitzer_" + s, gespiegelt(U_HECKBLITZER, sg), HINTEN, 0.02, 2, 2, 0.008)
        for xg in GRIFFE:
            aussparung(f"griff_{s}_{xg}", u_griffmulde(xg) if sg < 0 else u_griffmulde(xg)[::-1], SEITE(sg), 0.014, 4, 4,
                       0.008)
    aussparung("grill", U_GRILL, VORN, 0.06, 2, 3, 0.012)
    aussparung("einlass", U_EINLASS, VORN, 0.06, 2, 3, 0.012)
    schneider = objekt("_Schneider", bm, [M_SCHWARZ, M_SW_INNEN, M_TRIM, M_SPALT, M_SILBER])
    # Fugen: Tueren, Tuerunterkanten, Haube, Stossfaenger, Heckklappe, Tankdeckel
    bm = bmesh.new()
    def seite(x, z, sg):
        return (x, sg * (seiten_y(x, z) + 0.004), z)
    for sg in (-1, 1):
        for x0, x1 in ((1.00, 1.10), (-1.00, -1.11)):
            zg = Z_GURT(x1) - 0.012
            pts = [seite(x0, z, sg) for z in np.linspace(0.258, 0.70, 34)]
            pts += [seite(x0 + (x1 - x0) * t * t, 0.70 + (zg - 0.70) * t, sg) for t in np.linspace(0.05, 1, 16)]
            rille(bm, pts, bvh)
        rille(bm, [seite(-0.12, z, sg) for z in np.linspace(0.258, Z_GURT(-0.12) - 0.012, 50)], bvh)
        rille(bm, [seite(x, Z_BODEN(x) + 0.058, sg) for x in np.linspace(-1.00, 1.00, 120)], bvh)
        # Stossfaenger vorn und hinten: vom Radlauf zur Leuchte
        a = math.radians(58)
        p0 = (XV + (BOGEN_R - 0.012) * math.cos(a), RAD_R + (BOGEN_R - 0.012) * math.sin(a))
        rille(bm, [seite(p0[0] + (2.235 - p0[0]) * t, p0[1] + (0.612 - p0[1]) * t - 0.012 * math.sin(math.pi * t), sg)
                   for t in np.linspace(0, 1, 50)], bvh)
        p0 = (XH - (BOGEN_R - 0.012) * math.cos(a), RAD_R + (BOGEN_R - 0.012) * math.sin(a))
        rille(bm, [seite(p0[0] + (-2.255 - p0[0]) * t, p0[1] + (0.790 - p0[1]) * t - 0.010 * math.sin(math.pi * t), sg)
                   for t in np.linspace(0, 1, 50)], bvh)
        # Heckklappe: senkrecht unter und ueber der Leuchte
        rille(bm, [(-2.6, sg * 0.66, z) for z in np.linspace(0.712, 0.80, 12)], bvh, strahl=(1, 0, 0))
        rille(bm, [(-2.6, sg * 0.66, z) for z in np.linspace(0.935, 1.035, 12)], bvh, strahl=(1, 0, 0))
    # Haube: geschlossene Linie (Seiten, Vorderkante, Wasserkasten)
    def hy(x):
        return W_TOP(x) - 0.065
    xe = 2.335
    haube = [(x, -hy(x), Z_TOP(x) + 0.02) for x in np.linspace(1.25, 2.27, 60)]
    haube += [(2.27 + (xe - 2.27) * math.sin(w), -hy(2.27) * math.cos(w) - 0.0, Z_TOP(2.30) + 0.02)
              for w in np.linspace(0.15, 1.25, 8)]
    haube += [(xe, y, Z_TOP(xe) + 0.02) for y in np.linspace(-hy(2.27) * 0.3, hy(2.27) * 0.3, 30)]
    haube += [(2.27 + (xe - 2.27) * math.sin(w), hy(2.27) * math.cos(w), Z_TOP(2.30) + 0.02)
              for w in np.linspace(1.25, 0.15, 8)]
    haube += [(x, hy(x), Z_TOP(x) + 0.02) for x in np.linspace(2.27, 1.25, 60)]
    haube += [(1.25, y, Z_TOP(1.25) + 0.02) for y in np.linspace(hy(1.25) * 0.97, -hy(1.25) * 0.97, 60)]
    rille(bm, haube, bvh, geschlossen=True)
    rille(bm, [(-2.6, y, 0.712) for y in np.linspace(-0.66, 0.66, 80)], bvh, strahl=(1, 0, 0))
    tank = [(-1.385 + 0.085 * math.copysign(abs(math.cos(w)) ** 0.35, math.cos(w)),
             0.865 + 0.065 * math.copysign(abs(math.sin(w)) ** 0.35, math.sin(w))) for w in np.linspace(0, 2 * math.pi, 48, endpoint=False)]
    rille(bm, [seite(x, z, -1) for (x, z) in tank], bvh, geschlossen=True)
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

def details(kar):
    teile = []
    bm = bmesh.new()
    # Materialindizes der Anbauteile
    (A_SCHWARZ, A_CHROM, A_TRIM, A_BLAU, A_SCHILD, A_BAND, A_SILBER, A_ALU, A_KAPPE, A_RL, A_LED, A_BLINK, A_REFL,
     A_SWGLAS, A_RLGLAS, A_WEISS) = range(16)
    MATS_ANB = [M_SCHWARZ, M_CHROM, M_TRIM, M_BLAULICHT, M_SCHILD, M_SCHILD_BLAU, M_SILBER, M_ALU, M_BL_KAPPE, M_RL_LED,
                M_LED, M_BLINKER, M_REFLEKTOR, M_SW_GLAS, M_RL_GLAS, M_WEISS]
    for sg, s in ((1, "l"), (-1, "r")):
        # --- Scheinwerfer: Glas, zwei Projektionslinsen, LED-Tagfahrlicht mit Haken, Blinkerleiste ---
        einfuegen(bm, von_patch("scheinwerfer_" + s, A_SWGLAS))
        for a, b, r in ((0.505, 0.616, 0.025), (0.625, 0.624, 0.023)):
            einfuegen(bm, linse(VORN, sg * a, b, r, 0.032, A_REFL, A_SWGLAS, A_TRIM))
        drl = [(0.41, 0.624), (0.50, 0.637), (0.60, 0.649), (0.70, 0.659), (0.78, 0.663), (0.828, 0.657), (0.846, 0.643),
               (0.838, 0.627)]
        einfuegen(bm, rohr(pfad(VORN, [(sg * a, b) for a, b in drl], 0.013), 0.0045, segs=8, mi=A_LED))
        einfuegen(bm, rohr(pfad(VORN, [(sg * a, b) for a, b in ((0.45, 0.592), (0.58, 0.588), (0.70, 0.597), (0.78, 0.610))],
                                0.02), 0.0032, segs=6, mi=A_BLINK))
        # --- Nebelscheinwerfer im seitlichen Lufteinlass ---
        einfuegen(bm, linse(VORN, sg * 0.637, 0.357, 0.029, 0.02, A_CHROM, A_SWGLAS, A_TRIM))
        # --- Rueckleuchten: rotes Glas, LED-Lichtleiter als C und innerer Balken ---
        einfuegen(bm, von_patch("ruecklicht_" + s, A_RLGLAS))
        c = [(0.56, 0.868), (0.62, 0.838), (0.70, 0.826), (0.79, 0.829), (0.838, 0.856), (0.842, 0.905), (0.80, 0.932),
             (0.70, 0.922), (0.62, 0.902)]
        einfuegen(bm, rohr(pfad(HINTEN, [(sg * a, b) for a, b in c], 0.016), 0.0048, segs=8, mi=A_RL))
        einfuegen(bm, rohr(pfad(HINTEN, [(sg * a, b) for a, b in ((0.60, 0.873), (0.70, 0.876), (0.79, 0.88))], 0.022),
                           0.0038, segs=6, mi=A_RL))
        einfuegen(bm, linse(HINTEN, sg * 0.66, 0.852, 0.014, 0.024, A_REFL, A_SWGLAS, A_TRIM))      # Rueckfahrlicht
        # --- Heckblitzer neben dem Kennzeichen ---
        einfuegen(bm, von_patch("heckblitzer_" + s, A_SWGLAS))
        loc, n = auf(HINTEN, sg * 0.36, 0.605)
        einfuegen(bm, ausrichten(kasten((0, 0, 0), (0.008, 0.105, 0.026), fase=0.003, mi=A_BLAU), loc - n * 0.009, n))
        # --- Reflektoren im Stossfaenger ---
        pb, _ = patch(chaikin([(0.56, 0.44), (0.72, 0.44), (0.72, 0.462), (0.56, 0.462)], 2) if sg > 0 else
                      chaikin([(-0.56, 0.462), (-0.72, 0.462), (-0.72, 0.44), (-0.56, 0.44)], 2),
                      HINTEN["ursprung"], HINTEN["achse"], HINTEN["e1"], HINTEN["e2"], BVH_ROH, 0.008)
        for v in pb.verts:
            v.co += v.normal * 0.0012
        for f in pb.faces:
            f.material_index = A_RLGLAS
        einfuegen(bm, pb)
    # --- Grill: Wabengitter, Chromrahmen, zwei blaue Frontblitzer ---
    einfuegen(bm, waben(U_GRILL, VORN, 0.0155, 0.0035, 0.006, 0.024, A_TRIM))
    rahmen = [auf(VORN, a, b) for a, b in U_GRILL]
    einfuegen(bm, rohr([p + n * 0.002 for p, n in rahmen] + [rahmen[0][0] + rahmen[0][1] * 0.002], 0.0035, segs=8,
                       mi=A_CHROM, deckel=False))
    for sg in (-1, 1):
        loc, n = auf(VORN, sg * 0.235, 0.568)
        einfuegen(bm, ausrichten(kasten((0, 0, 0), (0.012, 0.078, 0.024), fase=0.004, mi=A_BLAU), loc - n * 0.013, n))
    einfuegen(bm, waben(U_EINLASS, VORN, 0.017, 0.004, 0.006, 0.026, A_TRIM))
    # --- Reflexstreifen ueber die Stirnflaechen (gerade Kanten) ---
    for ansicht, x0 in ((VORN, 2.40), (HINTEN, -2.40)):
        zb, zg = Z_BODEN(x0), min(Z_GURT(x0), Z_TOP(x0) - WOELB(x0) - 0.004)
        z0, z1 = zb + (zg - zb) * 0.55, zb + (zg - zb) * 0.62
        yw = min(seiten_y(x0, z0), seiten_y(x0, z1)) - 0.002
        pb, _ = patch([(-yw, z0), (yw, z0), (yw, z1), (-yw, z1)], ansicht["ursprung"], ansicht["achse"], ansicht["e1"],
                      ansicht["e2"], BVH_ROH, 0.01)
        for v in pb.verts:
            v.co += v.normal * 0.0007
        for f in pb.faces:
            f.material_index = A_WEISS
        einfuegen(bm, pb)
    # --- Kennzeichen mit Halter, blauem Band und Text ---
    for x, s, yb in ((2.433, 1, -0.235), (-2.437, -1, 0.235)):
        z = 0.432 if s > 0 else 0.56
        einfuegen(bm, kasten((x, 0.0, z), (0.02, 0.545, 0.128), fase=0.004, mi=A_SCHWARZ))
        einfuegen(bm, kasten((x + s * 0.009, 0.0, z), (0.012, 0.52, 0.11), fase=0.004, mi=A_SCHILD))
        einfuegen(bm, kasten((x + s * 0.0152, yb, z), (0.0012, 0.044, 0.104), mi=A_BAND))
        rot = R_FRONT if s > 0 else R_HECK
        teile.append(schrift("PL 2340", 0.07, M_SCHWARZ, rot, (x + s * 0.0156, -yb * 0.09, z - 0.003), "Kennzeichen"))
        teile.append(schrift("D", 0.03, M_WEISS, rot, (x + s * 0.0162, yb, z - 0.03), "Kennzeichen_D"))
    # --- Spiegel: Gehaeuse in Wagenfarbe, Spiegelglas, Arm, Blinker ---
    for sg in (-1, 1):
        g = kugel((0, 0, 0), 1.0, segs=32, ringe=16, mi=A_SILBER)
        for v in g.verts:
            x, y, z = v.co
            x = math.copysign(abs(x) ** 0.75, x) * (0.18 if x < 0 else 1.0)
            y = math.copysign(abs(y) ** 0.5, y)
            z = math.copysign(abs(z) ** 0.55, z) * (0.78 + 0.22 * (sg * y + 1) / 2)
            v.co = (x, y, z)
        bmesh.ops.scale(g, vec=(0.075, 0.108, 0.062), verts=g.verts)
        bmesh.ops.translate(g, vec=(0.985, sg * 1.0, 0.99), verts=g.verts)
        einfuegen(bm, g)
        einfuegen(bm, kugel((0.9705, sg * 1.003, 0.99), 1.0, segs=24, ringe=12, skala=(0.0025, 0.093, 0.054), mi=A_CHROM))
        einfuegen(bm, kasten((1.015, sg * 0.915, 0.958), (0.075, 0.07, 0.034), fase=0.012, mi=A_SCHWARZ))
        einfuegen(bm, rohr([(1.035, sg * 0.985, 0.952), (1.034, sg * 1.04, 0.95), (1.022, sg * 1.085, 0.955),
                            (1.0, sg * 1.098, 0.962)], 0.0035, segs=6, mi=A_BLINK))
        # --- Tuergriffe in den Griffmulden ---
        for xg in GRIFFE:
            loc, n = auf(SEITE(sg), xg, 0.876)
            einfuegen(bm, ausrichten(kasten((0, 0, 0), (0.016, 0.15, 0.022), fase=0.007, mi=A_CHROM), loc + n * 0.002, n))
    # --- Dachreling links und rechts ---
    def dach(x, y):
        return BVH_ROH.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)))[0].z
    for sg in (-1, 1):
        yr = sg * 0.665
        xs = np.linspace(0.50, -1.80, 46)
        pts = [(0.53, yr, dach(0.53, yr) + 0.004)] + [(x, yr, dach(x, yr) + 0.040) for x in xs] + \
              [(-1.83, yr, dach(-1.83, yr) + 0.004)]
        einfuegen(bm, rohr(pts, 0.011, 0.014, segs=12, mi=A_ALU, eckig=3.5))
        for xf in (0.49, -0.65, -1.79):
            einfuegen(bm, kasten((xf, yr, dach(xf, yr) + 0.022), (0.09, 0.032, 0.04), fase=0.01, mi=A_SCHWARZ))
    # --- Lichtbalken quer auf dem Dach: Grundkoerper, Halter auf der Reling, blaue Kappen mit LED-Modulen ---
    xb = -0.20
    zr = dach(xb, 0.0)
    einfuegen(bm, kasten((xb, 0.0, zr + 0.06), (0.30, 1.20, 0.035), fase=0.014, mi=A_TRIM))
    for sg in (-1, 1):
        einfuegen(bm, kasten((xb, sg * 0.64, zr + 0.042), (0.08, 0.07, 0.035), fase=0.008, mi=A_SCHWARZ))
        einfuegen(bm, kasten((xb, sg * 0.385, zr + 0.105), (0.285, 0.43, 0.055), fase=0.022, mi=A_KAPPE))
        for k in range(3):
            yk = sg * (0.24 + 0.095 * k)
            for xs_ in (0.105, -0.105):
                einfuegen(bm, kasten((xb + xs_, yk, zr + 0.103), (0.012, 0.072, 0.024), fase=0.003, mi=A_BLAU))
        einfuegen(bm, kasten((xb, sg * 0.575, zr + 0.103), (0.20, 0.012, 0.024), fase=0.003, mi=A_BLAU))
    einfuegen(bm, kasten((xb, 0.0, zr + 0.10), (0.262, 0.34, 0.05), fase=0.012, mi=A_TRIM))
    for x, rot in ((xb + 0.1315, R_FRONT), (xb - 0.1315, R_HECK)):
        teile.append(schrift("POLIZEI", 0.036, M_LED, rot, (x, 0.0, zr + 0.10), "Schrift_Lichtbalken"))
    # --- Dachspoiler, dritte Bremsleuchte, Haifischflossen-Antenne ---
    zs = Z_TOP(-1.97) + 0.006
    einfuegen(bm, rohr([(-2.0, y, zs) for y in np.linspace(-0.61, 0.61, 30)], 0.058, 0.012, segs=14, mi=A_SILBER, eckig=2.6))
    einfuegen(bm, kasten((-2.052, 0.0, zs - 0.009), (0.008, 0.36, 0.009), fase=0.002, mi=A_RL))
    f = kugel((0, 0, 0), 1.0, segs=20, ringe=12, mi=A_TRIM)
    for v in f.verts:
        v.co.z = max(v.co.z, 0.0)
    bmesh.ops.scale(f, vec=(0.085, 0.022, 0.062), verts=f.verts)
    for v in f.verts:
        v.co.x -= v.co.z * 0.9
    bmesh.ops.translate(f, vec=(-1.56, 0.0, dach(-1.56, 0.0) - 0.002), verts=f.verts)
    einfuegen(bm, f)
    # --- Scheibenwischer vorn und hinten ---
    def auf_glas(x, y, ab):
        loc, nor = BVH_ROH.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)))[:2]
        return loc + nor * ab
    for y0, y1 in ((0.10, 0.64), (-0.44, 0.05)):
        einfuegen(bm, rohr([auf_glas(1.115 - 0.02 * t, y0 + (y1 - y0) * t, 0.012) for t in np.linspace(0, 1, 16)],
                           0.010, 0.006, segs=8, mi=A_SCHWARZ, eckig=3))
    hz = [Vector(BVH_ROH.ray_cast(Vector((-2.8, 0.03 + 0.25 * t, 1.04 + 0.24 * t)), Vector((1, 0, 0)))[0]) +
          Vector((-0.012, 0, 0)) for t in np.linspace(0, 1, 12)]
    einfuegen(bm, rohr(hz, 0.008, 0.006, segs=8, mi=A_SCHWARZ, eckig=3))
    anb = objekt("Anbauteile", bm, MATS_ANB, glatt=True, auto_glatt=35)
    teile.append(anb)
    # --- Schriftzuege (Folie) ---
    for sg, rot in ((-1, R_RECHTS), (1, R_LINKS)):
        teile.append(schrift("POLIZEI", 0.16, M_WEISS, rot, (0.47, sg * 1.2, 0.47), "Schrift_Seite", kar))
    teile.append(schrift("POLIZEI", 0.15, M_FOLIE, R_HAUBE, (1.86, 0.0, 1.2), "Schrift_Haube", kar))
    teile.append(schrift("POLIZEI", 0.085, M_FOLIE, R_HECK, (-2.6, 0.0, 0.872), "Schrift_Heck", kar))
    teile.append(innenraum())
    return teile

def innenraum():
    """Innenraum, durch die Scheiben sichtbar: Armaturen, Lenkrad, Sitze, Verkleidungen, Himmel."""
    bm = bmesh.new()       # 0 dunkler Kunststoff, 1 Stoff, 2 Hochglanz (Bildschirm)
    einfuegen(bm, kasten((0.99, 0.0, 0.86), (0.36, 1.64, 0.17), fase=0.05, mi=0))                 # Armaturentafel
    einfuegen(bm, kasten((0.83, 0.37, 0.935), (0.13, 0.34, 0.06), fase=0.025, mi=0))              # Instrumente
    einfuegen(bm, kasten((0.80, 0.0, 0.93), (0.012, 0.25, 0.15), fase=0.004, mi=2,
                         rot=Matrix.Rotation(math.radians(-12), 3, "Y")))                       # Mittelbildschirm
    einfuegen(bm, kasten((0.32, 0.0, 0.43), (0.84, 0.22, 0.20), fase=0.03, mi=0))                 # Mittelkonsole
    lr = rohr([(0.0, 0.185 * math.cos(w), 0.185 * math.sin(w)) for w in np.linspace(0, 2 * math.pi, 33)], 0.016,
              segs=10, mi=0, deckel=False)
    for w in (math.pi / 2, math.pi * 7 / 6, math.pi * 11 / 6):
        einfuegen(lr, kasten((0.0, 0.09 * math.cos(w), 0.09 * math.sin(w)), (0.012, 0.17, 0.035),
                             rot=Matrix.Rotation(w, 3, "X"), fase=0.005, mi=0))
    einfuegen(lr, zylinder((0.0, 0, 0), 0.05, 0.03, "X", segs=16, mi=0))
    bmesh.ops.transform(lr, matrix=Matrix.Translation((0.73, 0.37, 0.93)) @ Matrix.Rotation(math.radians(-22), 4, "Y"),
                        verts=lr.verts)
    einfuegen(bm, lr)
    for yy in (0.40, -0.40):
        einfuegen(bm, kasten((0.16, yy, 0.47), (0.50, 0.40, 0.12), fase=0.05, mi=1))              # Sitzflaeche
        for ys in (-0.21, 0.21):
            einfuegen(bm, kasten((0.16, yy + ys, 0.50), (0.48, 0.07, 0.15), fase=0.03, mi=1))     # Seitenwangen
        lehne = Matrix.Rotation(math.radians(-14), 3, "Y")
        einfuegen(bm, kasten((-0.09, yy, 0.82), (0.13, 0.40, 0.60), fase=0.05, rot=lehne, mi=1))
        for ys in (-0.21, 0.21):
            einfuegen(bm, kasten((-0.07, yy + ys, 0.80), (0.16, 0.07, 0.55), fase=0.03, rot=lehne, mi=1))
        einfuegen(bm, kasten((-0.15, yy, 1.18), (0.09, 0.26, 0.17), fase=0.04, mi=1))             # Kopfstuetze
    einfuegen(bm, kasten((-0.80, 0.0, 0.47), (0.50, 1.40, 0.14), fase=0.05, mi=1))               # Ruecksitzbank
    einfuegen(bm, kasten((-1.04, 0.0, 0.84), (0.13, 1.40, 0.62), fase=0.05,
                         rot=Matrix.Rotation(math.radians(-12), 3, "Y"), mi=1))
    for yy in (-0.48, 0.0, 0.48):
        einfuegen(bm, kasten((-1.12, yy, 1.20), (0.08, 0.24, 0.14), fase=0.035, mi=1))
    einfuegen(bm, kasten((-0.10, 0.0, 0.19), (3.9, 1.64, 0.04), mi=0))                           # Boden
    einfuegen(bm, kasten((-1.60, 0.0, 0.52), (0.80, 1.50, 0.03), mi=0))                          # Kofferraumboden
    for sg in (-1, 1):
        einfuegen(bm, kasten((-0.20, sg * 0.83, 0.70), (2.60, 0.05, 0.42), fase=0.02, mi=0))     # Tuerverkleidungen
    einfuegen(bm, kasten((-0.79, 0.0, 1.378), (2.12, 1.28, 0.02), fase=0.01, mi=1))              # Dachhimmel
    return objekt("Innenraum", bm, [M_INNEN, M_INNEN_HELL, M_TRIM], glatt=True, auto_glatt=40)

# ---------------- Raeder: Reifen mit Profil, 18-Zoll-Felge mit fuenf Doppelspeichen, Bremsscheibe ----------------
def drehkoerper(bm, profil, segs, mi, uv=None, kacheln=8):
    """Profil [(r, a[, v])] um die Radachse (lokal Y) drehen. Mit uv-Layer: u laeuft um den Umfang
    (kacheln je Umdrehung), v kommt aus dem Profil."""
    ringe = []
    for i in range(segs):
        w = 2 * math.pi * i / segs
        c, s = math.cos(w), math.sin(w)
        ringe.append([bm.verts.new((p[0] * c, p[1], p[0] * s)) for p in profil])
    faces = []
    for i in range(segs):
        r0, r1 = ringe[i], ringe[(i + 1) % segs]
        for j in range(len(profil) - 1):
            f = bm.faces.new((r0[j], r1[j], r1[j + 1], r0[j + 1]))
            f.material_index = mi
            if uv is not None:
                u0, u1 = i / segs * kacheln, (i + 1) / segs * kacheln
                v0, v1 = profil[j][2], profil[j + 1][2]
                for loop, (uu, vv) in zip(f.loops, ((u0, v0), (u1, v0), (u1, v1), (u0, v1))):
                    loop[uv].uv = (uu, vv)
            faces.append(f)
    return faces

def reifen_profil():
    """Querschnitt 245/45 R18 von der inneren zur aeusseren Wulst: (r, a, v); vier Laengsrillen als Geometrie."""
    p = [(0.226, -0.103, 0.00), (0.236, -0.112, 0.03), (0.255, -0.1175, 0.08), (0.280, -0.1185, 0.14),
         (0.302, -0.116, 0.20), (0.318, -0.110, 0.25), (0.328, -0.100, 0.29), (0.333, -0.089, 0.32)]
    lauf = [(RAD_R, -0.080)]
    for c in (-0.050, -0.017, 0.017, 0.050):
        lauf += [(RAD_R, c - 0.0055), (RAD_R - 0.008, c - 0.004), (RAD_R - 0.008, c + 0.004), (RAD_R, c + 0.0055)]
    lauf.append((RAD_R, 0.080))
    p += [(r, a, 0.34 + (a + 0.080) / 0.160 * 0.32) for (r, a) in lauf]
    p += [(0.333, 0.089, 0.68), (0.328, 0.100, 0.71), (0.318, 0.110, 0.75), (0.302, 0.116, 0.80),
          (0.280, 0.1185, 0.86), (0.255, 0.1175, 0.92), (0.236, 0.112, 0.97), (0.226, 0.103, 1.00)]
    return p

def ausrichten_ref(faces, ref_r, ref_a, nach_aussen=True):
    """Offene Drehflaechen ausrichten: Normalen weg vom (bzw. hin zum) Referenzring (Radius ref_r bei a = ref_a)."""
    for f in faces:
        c = f.calc_center_median()
        r = math.hypot(c.x, c.z) or 1.0
        ref = Vector((ref_r * c.x / r, ref_a, ref_r * c.z / r))
        if ((c - ref).dot(f.normal) < 0) == nach_aussen:
            f.normal_flip()

def speiche(bm, phi, r0, r1, mi):
    """Eine Speiche von der Nabe (r0) zum Felgenbett (r1); Aussenseite liegt zur Nabe hin tiefer (konkav)."""
    ringe = []
    stationen = np.linspace(r0, r1, 9)
    for k, r in enumerate(stationen):
        t = (r - r0) / (r1 - r0)
        versatz = (0.0095 + (0.034 - 0.0095) * t) / r
        th = phi + versatz * math.copysign(1, mi[1])
        er = Vector((math.cos(th), 0, math.sin(th)))
        et = Vector((-math.sin(th), 0, math.cos(th)))
        ea = Vector((0, 1, 0))
        breite = 0.019 + 0.006 * t
        dicke = 0.024 - 0.006 * t
        aussen = 0.054 + 0.040 * t + 0.004 * math.sin(math.pi * t)
        c = er * r
        quer = [(-breite / 2, -dicke), (breite / 2, -dicke), (breite / 2, -0.006), (breite / 2 - 0.005, 0.0),
                (-breite / 2 + 0.005, 0.0), (-breite / 2, -0.006)]
        ringe.append([bm.verts.new(c + et * s + ea * (aussen + h)) for s, h in quer])
    for q0, q1 in zip(ringe, ringe[1:]):
        for j in range(6):
            bm.faces.new((q0[j], q0[(j + 1) % 6], q1[(j + 1) % 6], q1[j])).material_index = mi[0]
    for q in (ringe[0], ringe[-1][::-1]):
        bm.faces.new(q).material_index = mi[0]

def rad_bmesh():
    """Ein Rad mit Aussenseite nach +Y (lokal), Mitte im Ursprung. Materialien: 0 Reifen, 1 Felge, 2 Felge innen,
    3 Chrom, 4 Bremse."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    reifen = drehkoerper(bm, reifen_profil(), 72, 0, uv=uv)
    bett = drehkoerper(bm, [(0.240, -0.104), (0.240, -0.097), (0.228, -0.095), (0.226, -0.080), (0.203, -0.072),
                            (0.199, -0.030), (0.199, 0.030), (0.212, 0.045), (0.226, 0.055), (0.228, 0.092)], 72, 2)
    horn = drehkoerper(bm, [(0.228, 0.092), (0.241, 0.096), (0.244, 0.103), (0.240, 0.1085), (0.229, 0.1085),
                            (0.216, 0.101), (0.211, 0.090)], 72, 1)
    for k in range(5):
        phi = 2 * math.pi * k / 5
        for seite in (-1, 1):
            speiche(bm, phi, 0.068, 0.214, (1, seite))
    # Nabe, Radmuttern, Nabendeckel
    einfuegen(bm, zylinder((0, 0.045, 0), 0.082, 0.024, "Y", segs=40, mi=1))
    einfuegen(bm, zylinder((0, 0.0585, 0), 0.074, 0.003, "Y", segs=40, mi=2))
    for k in range(5):
        w = 2 * math.pi * k / 5 + math.pi / 5
        einfuegen(bm, zylinder((0.056 * math.cos(w), 0.064, 0.056 * math.sin(w)), 0.0105, 0.014, "Y", segs=6, mi=3))
    einfuegen(bm, zylinder((0, 0.064, 0), 0.031, 0.012, "Y", segs=28, mi=2))
    einfuegen(bm, zylinder((0, 0.0702, 0), 0.026, 0.002, "Y", segs=28, mi=3))
    # Bremsscheibe mit Topf (rund, darf sich mitdrehen; einen Bremssattel gibt es nicht, er wuerde mitdrehen)
    einfuegen(bm, zylinder((0, -0.028, 0), 0.172, 0.028, "Y", segs=60, mi=4))
    einfuegen(bm, zylinder((0, 0.004, 0), 0.092, 0.036, "Y", segs=40, mi=2))
    bm.normal_update()
    offen = set(reifen) | set(bett) | set(horn)
    bmesh.ops.recalc_face_normals(bm, faces=[f for f in bm.faces if f not in offen])
    ausrichten_ref(reifen, 0.278, 0.0, nach_aussen=True)
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
        bmesh.ops.translate(bm, vec=Vector((x, y, RAD_R)), verts=bm.verts)
        obs[name] = objekt("Rad_" + name, bm, [M_GUMMI, M_FELGE, M_FELGE_DUNKEL, M_CHROM, M_BREMSE], glatt=True,
                           auto_glatt=40)
    return obs

# ---------------- Zusammenbauen, UV-Karten, Skelett, Export ----------------
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

# UV-Karten: "UVMap" per Smart UV Project fuer alles ausser den Reifen (die haben eine eigene Abwicklung fuer die
# Profiltextur), "UV_Flakes" als Wuerfelprojektion in Metern fuer die Lack-Flakes
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
AUTO.name = AUTO.data.name = "SK_Polizeiauto"

# Skelett: root am Boden zwischen den Achsen, je ein Knochen pro Rad (alle gleich ausgerichtet wie root)
arm_data = bpy.data.armatures.new("Polizeiauto_Skelett")
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
log("Polizeiauto:", DREIECKE, "Dreiecke,", len(AUTO.data.materials), "Materialien")

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

# glTF in Metern
auswahl()
bpy.ops.export_scene.gltf(filepath=os.path.join(EXPORT, "SK_Polizeiauto.glb"), export_format="GLB", use_selection=True,
                          export_yup=True, export_apply=False, export_skins=True, export_animations=False,
                          export_cameras=False, export_lights=False, export_image_format="AUTO")
# FBX fuer Unreal: Zentimeter, ueberall Skalierung 1. Mesh und Knochen werden dafuer kurz x100 gesetzt und die
# Szeneneinheit auf 0,01; danach geht alles zurueck. Vielecke mit mehr als vier Ecken werden trianguliert
# (sauber auch bei konkaven Flaechen), erst dann schreibt der Exporter Tangenten.
bm = bmesh.new()
bm.from_mesh(AUTO.data)
bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4], quad_method="BEAUTY", ngon_method="BEAUTY")
bm.to_mesh(AUTO.data)
bm.free()
scene.unit_settings.scale_length = 0.01
skalieren(100.0)
auswahl()
bpy.ops.export_scene.fbx(filepath=os.path.join(EXPORT, "SK_Polizeiauto.fbx"), use_selection=True,
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

def leuchten(blau, rot, weiss, blinker=0.0):
    for m, s in ((M_BLAULICHT, blau), (M_RL_LED, rot), (M_LED, weiss), (M_BLINKER, blinker)):
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

def mathe(nt, op, a, b=None):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, (int, float)):
            n.inputs[i].default_value = x
        else:
            nt.links.new(x, n.inputs[i])
    return n.outputs[0]

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
        "vorne": ((5.9, -4.4, 1.0), (0.25, 0.0, 0.62), 45, None),
        "hinten": ((-5.8, 4.5, 1.2), (-0.3, 0.0, 0.70), 45, None),
        "seite": ((0.0, -8.8, 0.85), (0.0, 0.0, 0.70), 50, None),
        "oben": ((5.0, -6.0, 5.6), (0.0, 0.0, 0.45), 40, None),
        "detail": ((4.0, -2.35, 0.82), (2.3, -0.55, 0.60), 60, 2.8),
    }
    studio_shots = [s for s in SHOTS if s in STUDIO]
    if studio_shots:
        szene = studio()
        leuchten(0.0, 0.8, 2.5)
        for s in studio_shots:
            kamera(*STUDIO[s])
            scene.render.filepath = os.path.join(OUT, f"polizeiauto_{s}.png")
            log("Render", s)
            bpy.ops.render.render(write_still=True)
        for ob in szene:
            bpy.data.objects.remove(ob)
    if "nacht" in SHOTS:
        strasse_nacht()
        welt((0.0025, 0.0035, 0.007))
        leuchten(8.0, 5.0, 12.0)
        blau = (0.12, 0.3, 1.0)
        xb, zk = -0.20, Z_TOP(-0.20) + 0.105
        for sg in (-1, 1):
            for ort, ri in (((xb + 0.165, sg * 0.385, zk), (1, 0, -0.3)), ((xb - 0.165, sg * 0.385, zk), (-1, 0, -0.3)),
                            ((xb, sg * 0.625, zk), (0, sg, -0.3))):
                punktlicht("Blaulicht", ort, 900, blau, radius=0.02, art="SPOT", ziel=tuple(Vector(ort) + Vector(ri)),
                           kegel=165)
            punktlicht("Frontblitzer", (2.48, sg * 0.235, 0.568), 30, blau, radius=0.02)
            punktlicht("Scheinwerfer", (2.42, sg * 0.56, 0.62), 1000, (1.0, 0.95, 0.88), radius=0.03, art="SPOT",
                       ziel=(9.0, sg * 1.2, 0.0), kegel=55)
            punktlicht("Ruecklicht", (-2.48, sg * 0.68, 0.87), 12, (1.0, 0.05, 0.03), radius=0.05)
        kamera((5.6, -3.9, 0.75), (0.3, 0.4, 0.95), 32)
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
        scene.render.filepath = os.path.join(OUT, "polizeiauto_nacht.png")
        log("Render nacht")
        bpy.ops.render.render(write_still=True)
        leuchten(0.0, 0.8, 2.5)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "polizeiauto.blend"), compress=True)
log("fertig")

