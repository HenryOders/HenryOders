# Streifenwagen fuer Spiele: eigenes Kombi-Design (keine echte Automarke), blau-silberne POLIZEI-Beklebung.
# Erzeugt Karosserie, Raeder, Details und Innenraum, ein Skelett fuer Unreal Engine 5 (root + vier Radknochen),
# den Export als FBX und glTF sowie Vorschaubilder.
# Start: blender -b -P polizeiauto.py   (oder mit dem bpy-Modul: python polizeiauto.py)
# Das Skript setzt Blender auf Werkseinstellungen zurueck, also nicht in einem offenen Projekt ausfuehren.
# Koordinaten: X nach vorn, Y nach links, Z nach oben, Ursprung am Boden mittig zwischen den Achsen. Meter.
import bpy, bmesh, math, os, time, random
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, noise

T0 = time.time()
def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)

OUT = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(OUT, "export")
os.makedirs(EXPORT, exist_ok=True)
SHOTS = [s for s in os.environ.get("SHOTS", "vorne,hinten,seite,oben,nacht").split(",") if s]
SAMPLES = int(os.environ.get("SAMPLES", "128"))
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
LAENGE, BREITE = 4.80, 1.86
RADSTAND, SPUR = 2.84, 1.60
XV, XH = RADSTAND / 2, -RADSTAND / 2          # Vorder- und Hinterachse
RAD_R, RAD_B = 0.335, 0.225                   # Reifenradius, Reifenbreite
FELGE_R = 0.218
BOGEN_R = 0.405                               # Radlauf
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

MATS = {}
def material(name, farbe, metall=0.0, rauheit=0.5, lack=0.0, durch=0.0, ior=1.45, leuchten=0.0, leucht_farbe=None, alpha=1.0):
    """Principled BSDF mit festen Werten (exportiert sauber nach glTF und FBX)."""
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*farbe, 1.0)
    b.inputs["Metallic"].default_value = metall
    b.inputs["Roughness"].default_value = rauheit
    b.inputs["Coat Weight"].default_value = lack
    b.inputs["Coat Roughness"].default_value = 0.03
    b.inputs["Transmission Weight"].default_value = durch
    b.inputs["IOR"].default_value = ior
    if leuchten:
        b.inputs["Emission Color"].default_value = (*(leucht_farbe or farbe), 1.0)
        b.inputs["Emission Strength"].default_value = leuchten
    if alpha < 1.0:
        b.inputs["Alpha"].default_value = alpha
    m.diffuse_color = (*farbe, 1.0)
    MATS[name] = m
    return m

def hexf(h):
    h = h.lstrip("#")
    return tuple((int(h[i:i + 2], 16) / 255) ** 2.2 for i in (0, 2, 4))     # sRGB -> linear

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

def einfuegen(ziel, teil):
    """bmesh 'teil' an bmesh 'ziel' anhaengen (Materialindizes bleiben)."""
    me = bpy.data.meshes.new("_tmp")
    teil.to_mesh(me)
    teil.free()
    ziel.from_mesh(me)
    bpy.data.meshes.remove(me)

# ---------------- Materialien ----------------
M_SILBER = material("Lack_Silber", hexf("#c9cdd1"), metall=0.55, rauheit=0.32, lack=1.0)
M_BLAU = material("Lack_Blau", hexf("#123a7a"), metall=0.45, rauheit=0.32, lack=1.0)
M_WEISS = material("Reflexfolie_Weiss", hexf("#eceeee"), rauheit=0.45, lack=0.3)
M_SCHWARZ = material("Kunststoff_Schwarz", hexf("#151618"), rauheit=0.55)
M_GLAS = material("Glas", hexf("#1a2026"), rauheit=0.02, durch=1.0, ior=1.5)
M_CHROM = material("Chrom", hexf("#d8dadc"), metall=1.0, rauheit=0.08)
M_LINSE = material("Scheinwerfer_Glas", hexf("#e8eef4"), rauheit=0.02, durch=1.0, ior=1.5)
M_ROT = material("Ruecklicht_Rot", hexf("#8a0c10"), rauheit=0.05, durch=0.6, ior=1.5, leuchten=0.4)
M_BLAULICHT = material("Blaulicht", hexf("#1747ff"), rauheit=0.1, durch=0.4, ior=1.5, leuchten=0.0, leucht_farbe=hexf("#2a5bff"))
M_FOLIE = material("Folie_Blau", hexf("#123a7a"), rauheit=0.4)
M_LED = material("Tagfahrlicht", hexf("#ffffff"), rauheit=0.2, leuchten=2.0)
M_GUMMI = material("Gummi", hexf("#141414"), rauheit=0.85)
M_FELGE = material("Felge", hexf("#b4b8bc"), metall=1.0, rauheit=0.28)
M_BREMSE = material("Bremse", hexf("#4a4a4a"), metall=0.8, rauheit=0.45)
M_INNEN = material("Innenraum", hexf("#2b2c2e"), rauheit=0.9)
M_SCHILD = material("Kennzeichen", hexf("#f2f2f0"), rauheit=0.4)

# ---------------- Karosserie: Querschnitte entlang X ----------------
Z_TOP = pchip([(2.40, 0.58), (2.33, 0.70), (2.18, 0.79), (1.80, 0.86), (1.40, 0.91), (1.20, 0.94), (0.95, 1.10),
               (0.65, 1.26), (0.40, 1.37), (0.20, 1.44), (-0.10, 1.475), (-1.00, 1.465), (-1.70, 1.43), (-1.98, 1.39),
               (-2.10, 1.27), (-2.22, 1.10), (-2.30, 0.98), (-2.36, 0.86), (-2.40, 0.70)])
Z_GURT = pchip([(2.40, 0.56), (2.30, 0.68), (2.00, 0.80), (1.40, 0.88), (1.20, 0.90), (0.00, 0.96), (-1.20, 0.995),
                (-1.90, 1.01), (-2.20, 0.98), (-2.32, 0.88), (-2.40, 0.68)])
Z_BODEN = pchip([(2.40, 0.30), (2.30, 0.24), (2.10, 0.21), (1.80, 0.20), (-1.80, 0.20), (-2.10, 0.22), (-2.30, 0.27), (-2.40, 0.33)])
W = pchip([(2.40, 0.70), (2.36, 0.80), (2.28, 0.865), (2.10, 0.905), (1.80, 0.92), (1.40, 0.925), (0.00, 0.93), (-1.40, 0.93),
           (-1.90, 0.925), (-2.20, 0.905), (-2.33, 0.86), (-2.40, 0.78)])
W_TOP = pchip([(2.40, 0.58), (2.30, 0.70), (2.00, 0.78), (1.50, 0.80), (1.20, 0.79), (0.90, 0.765), (0.50, 0.73), (0.20, 0.715),
               (-1.00, 0.71), (-1.80, 0.70), (-2.00, 0.69), (-2.20, 0.72), (-2.32, 0.74), (-2.40, 0.68)])
WOELB = pchip([(2.40, 0.008), (2.20, 0.018), (1.25, 0.022), (0.25, 0.022), (0.0, 0.026), (-1.95, 0.024), (-2.10, 0.012), (-2.40, 0.008)])
T_SEITE = (0.07, 0.22, 0.40, 0.55, 0.62, 0.72, 0.86, 0.96)
U_OBEN = (0.12, 0.45, 0.80, 1.0)
F_DACH = (0.8, 0.55, 0.28, 0.0)

def einzug(t):
    """Seitenwand: unten eingezogen (Schweller), zur Schulter hin leicht nach innen."""
    return 0.03 * max(0.0, 1 - t / 0.25) ** 2 + 0.022 * max(0.0, (t - 0.6) / 0.4) ** 2

def schnitt(x):
    """Rechte Haelfte eines Querschnitts von der Bodenmitte bis zur Dachmitte: Liste (y, z)."""
    zt, zg, zb, w, wt, cr = Z_TOP(x), Z_GURT(x), Z_BODEN(x), W(x), W_TOP(x), WOELB(x)
    zg = min(zg, zt - cr - 0.004)
    zu = zb - 0.03
    pts = [(0.0, zu), (0.45 * w, zu), (w - 0.13, zu + 0.004), (w - 0.045, zb)]
    for t in T_SEITE:
        pts.append((w - einzug(t), zb + (zg - zb) * t))
    ws = w - 0.035
    pts.append((ws, zg))
    ze = zt - cr * 0.95
    for u in U_OBEN:
        pts.append((ws + (wt - ws) * u, zg + (ze - zg) * (1 - (1 - u) ** 1.2)))
    for f in F_DACH:
        pts.append((wt * f, zt - cr * f * f))
    return pts

# Abschnitte (x von - bis) fuer Fenster und Saeulen
FENSTER_SEITE = [(-0.08, 1.12), (-1.06, -0.16), (-1.90, -1.16)]
B_SAEULE = (-0.16, -0.08)
FRONTSCHEIBE = (0.26, 1.16)
HECKSCHEIBE = (-2.28, -2.00)

def stationen():
    xs = set(round(v, 4) for v in np.arange(-2.40, 2.4001, 0.06))
    for a, b in FENSTER_SEITE + [B_SAEULE, FRONTSCHEIBE, HECKSCHEIBE]:
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

def flaechen_material(j, xm):
    """Materialindex fuer das Flaechenband j (zwischen Punkt j und j+1 der rechten Haelfte) bei x = xm."""
    if j <= 2:
        return 3                                   # Unterboden, Schweller unten
    if j <= 6:
        return 1                                   # blau
    if j == 7:
        return 2                                   # weisser Reflexstreifen
    if j <= 11:
        return 0                                   # silber
    fenster = bereich(xm, FENSTER_SEITE)
    if j in (12, 13, 14, 15):
        if bereich(xm, [B_SAEULE]):
            return 3
        if fenster:
            return 4 if j in (13, 14) else 3
        return 0
    if bereich(xm, [FRONTSCHEIBE, HECKSCHEIBE]):
        return 3 if j == 16 else 4
    return 0

def karosserie():
    xs = stationen()
    halb = [schnitt(x) for x in xs]
    nh = len(halb[0])                               # Punkte je Haelfte (inkl. beider Mitten)
    bm = bmesh.new()
    ringe = []
    for x, pts in zip(xs, halb):
        rechts = [bm.verts.new((x, -y, z)) for (y, z) in pts]           # rechte Seite = -Y
        links = [bm.verts.new((x, y, z)) for (y, z) in pts[1:-1]]       # linke Seite ohne die beiden Mitten
        ringe.append((rechts, links))
    for k in range(len(xs) - 1):
        xm = (xs[k] + xs[k + 1]) / 2
        (ra, la), (rb, lb) = ringe[k], ringe[k + 1]
        for j in range(nh - 1):
            mi = flaechen_material(j, xm)
            f = bm.faces.new((ra[j], rb[j], rb[j + 1], ra[j + 1]))
            f.material_index = mi
            # linke Seite gespiegelt: Punkt j der Haelfte ist links[j-1] (Mitten aus der rechten Liste)
            def L(lst, rr, i):
                return rr[i] if i in (0, nh - 1) else lst[i - 1]
            f2 = bm.faces.new((L(la, ra, j + 1), L(lb, rb, j + 1), L(lb, rb, j), L(la, ra, j)))
            f2.material_index = mi
    # Stirnflaechen vorn und hinten: eingerueckte Ringe (leicht gewoelbt) und ein Faecher zur Mitte.
    # Farbe nach Hoehe wie an der Seite: unten blau, weisser Streifen, oben silber, ganz unten schwarz.
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
                f = bm.faces.new((prev[i], prev[(i + 1) % n], ring[(i + 1) % n], ring[i]))
                f[kap] = k + 1
            prev = ring
        mitte = bm.verts.new((x0 + sg * 0.032, cy, cz))
        for i in range(len(prev)):
            f = bm.faces.new((prev[i], prev[(i + 1) % len(prev)], mitte))
            f[kap] = k + 1
        # Farbgrenzen wie an der Seite (Unterkante, Blau bis 55 %, Streifen bis 62 %) als waagrechte Schnitte
        zb, zg = Z_BODEN(x0), min(Z_GURT(x0), Z_TOP(x0) - WOELB(x0) - 0.004)
        grenzen = (zb, zb + (zg - zb) * 0.55, zb + (zg - zb) * 0.62)
        for zc in grenzen:
            fl = [f for f in bm.faces if f[kap] == k + 1]
            geom = fl + list({e for f in fl for e in f.edges}) + list({v for f in fl for v in f.verts})
            bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-5, plane_co=(0, 0, zc), plane_no=(0, 0, 1))
        for f in bm.faces:
            if f[kap] == k + 1:
                z = f.calc_center_median().z
                f.material_index = 3 if z < grenzen[0] else 1 if z < grenzen[1] else 2 if z < grenzen[2] else 0
    bm.faces.layers.int.remove(kap)
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # Kantenschaerfe: Schulterlinie (Punkt 12) und Kante zwischen Seite und Dach/Haube (Punkt 16)
    cl = bm.edges.layers.float.get("crease_edge") or bm.edges.layers.float.new("crease_edge")
    for k in range(len(xs) - 1):
        (ra, la), (rb, lb) = ringe[k], ringe[k + 1]
        for idx, wert in ((12, 0.65), (16, 0.45)):
            for va, vb in ((ra[idx], rb[idx]), (la[idx - 1], lb[idx - 1])):
                e = bm.edges.get((va, vb))
                if e is not None:
                    e[cl] = wert
    ob = objekt("Karosserie", bm, [M_SILBER, M_BLAU, M_WEISS, M_SCHWARZ, M_GLAS], glatt=True)
    sub = ob.modifiers.new("Glaetten", "SUBSURF")
    sub.levels = sub.render_levels = 1
    sub.subdivision_type = "CATMULL_CLARK"
    anwenden(ob, sub)
    return ob

def radlaeufe(ob):
    """Radlaeufe als Boolesche Differenz mit Zylindern, dazu dunkle Radkaesten."""
    bm = bmesh.new()
    for name, (x, y) in RAEDER.items():
        einfuegen(bm, zylinder((x, math.copysign(0.92, y), RAD_R), BOGEN_R, 0.74, "Y", segs=48))
    cut = objekt("_Radlauf_Schnitt", bm, [M_SCHWARZ])
    mod = ob.modifiers.new("Radlaeufe", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.material_mode = "TRANSFER"
    mod.object = cut
    anwenden(ob, mod)
    bpy.data.objects.remove(cut)
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    return None

# ---------------- Details: Licht, Grill, Spiegel, Griffe, Fugen, Schrift, Blaulicht, Innenraum ----------------
def auf_flaeche(ob, ziel, abstand=0.0008):
    """Objekt (Linie, Schrift) auf die Karosserie legen."""
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

def seiten_y(x, z):
    """Lage der Seitenwand (|y|) bei x und Hoehe z aus dem Querschnitt."""
    pts = schnitt(x)
    best = None
    for (y0, z0), (y1, z1) in zip(pts[3:13], pts[4:14]):
        if min(z0, z1) - 1e-6 <= z <= max(z0, z1) + 1e-6 and abs(z1 - z0) > 1e-6:
            t = (z - z0) / (z1 - z0)
            best = y0 + (y1 - y0) * t
    return best if best is not None else W(x)

def projiziert(umriss, x_start, richtung, mat, name, ziel, abstand, innen=None):
    """Flaeche mit Umriss (y, z) von x_start aus entlang X (richtung -1 oder +1) auf die Karosserie projizieren."""
    bm = bmesh.new()
    vs = [bm.verts.new((x_start, y, z)) for (y, z) in umriss]
    f = bm.faces.new(vs)
    bmesh.ops.triangulate(bm, faces=[f])
    # feiner unterteilen, damit die Flaeche der Rundung folgt
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
    bm.normal_update()
    for f in bm.faces:
        if f.normal.x * richtung > 0:          # Sichtseite zeigt gegen die Projektionsrichtung
            f.normal_flip()
    ob = objekt(name, bm, [mat], glatt=True)
    sw = ob.modifiers.new("Projektion", "SHRINKWRAP")
    sw.target = ziel
    sw.wrap_method = "PROJECT"
    sw.use_project_x = True
    sw.use_negative_direction = richtung < 0
    sw.use_positive_direction = richtung > 0
    sw.offset = abstand
    anwenden(ob, sw)
    return ob

def rundumriss(y0, y1, z0, z1, z_aussen, r=0.02, n=6):
    """Abgerundetes Viereck im (y, z): innen (y0) von z0..z1, aussen (y1) bis z_aussen angehoben."""
    pts = []
    ecken = [(y0, z0, -1, -1), (y1, z0 + (z_aussen - z1) * 0.6, 1, -1), (y1, z_aussen, 1, 1), (y0, z1, -1, 1)]
    for (cy, cz, sy, sz) in ecken:
        for k in range(n):
            a = math.pi / 2 * k / (n - 1)
            if (sy, sz) == (-1, -1):
                w = math.pi + a
            elif (sy, sz) == (1, -1):
                w = 1.5 * math.pi + a
            elif (sy, sz) == (1, 1):
                w = a
            else:
                w = 0.5 * math.pi + a
            pts.append((cy - sy * r + r * math.cos(w), cz - sz * r + r * math.sin(w)))
    return pts

def linie(punkte, breite, name, ziel, normale):
    """Fuge als schmaler Streifen entlang eines Linienzugs (Punkte in Weltkoordinaten), auf die Karosserie gelegt."""
    bm = bmesh.new()
    n = Vector(normale)
    vs = []
    for i, p in enumerate(punkte):
        p = Vector(p)
        a = Vector(punkte[max(0, i - 1)])
        b = Vector(punkte[min(len(punkte) - 1, i + 1)])
        t = (b - a).normalized()
        q = t.cross(n).normalized() * breite / 2
        vs.append((bm.verts.new(p - q), bm.verts.new(p + q)))
    for (a0, a1), (b0, b1) in zip(vs, vs[1:]):
        f = bm.faces.new((a0, b0, b1, a1))
    bm.normal_update()
    for f in bm.faces:
        if f.normal.dot(n) < 0:
            f.normal_flip()
    ob = objekt(name, bm, [M_SCHWARZ])
    auf_flaeche(ob, ziel, 0.0006)
    return ob

def details(kar):
    teile = []
    # --- Fugen (Tueren, Haube, Heckklappe, Tankklappe) ---
    for sg in (-1, 1):
        for x0 in (1.00, -0.12, -0.98):
            z0 = Z_BODEN(x0) + 0.05
            z1 = Z_GURT(x0) - 0.005
            pts = [(x0, sg * (seiten_y(x0, z) + 0.01), z) for z in np.linspace(z0, z1, 12)]
            teile.append(linie(pts, 0.004, "Fuge_Tuer", kar, (0, sg, 0)))
        zl = lambda x: Z_BODEN(x) + 0.065
        pts = [(x, sg * (seiten_y(x, zl(x)) + 0.01), zl(x)) for x in np.linspace(-0.98, 1.00, 30)]
        teile.append(linie(pts, 0.004, "Fuge_Schweller", kar, (0, sg, 0)))
        # Haube: Laengsfuge auf der Kante zwischen Haube und Kotfluegel
        pts = [(x, sg * (W_TOP(x) - 0.05), Z_TOP(x) - WOELB(x) * ((W_TOP(x) - 0.05) / W_TOP(x)) ** 2 + 0.01)
               for x in np.linspace(1.22, 2.20, 24)]
        teile.append(linie(pts, 0.004, "Fuge_Haube", kar, (0, sg * 0.3, 1)))
        # Heckklappe: senkrechte Fugen
        pts = [(-2.30 - 0.06 * t, sg * 0.67, 1.0 - 0.335 * t) for t in np.linspace(0, 1, 10)]
        teile.append(linie(pts, 0.004, "Fuge_Heck", kar, (-1, 0, 0)))
    pts = [(2.20, y, Z_TOP(2.20) + 0.01) for y in np.linspace(-(W_TOP(2.20) - 0.05), W_TOP(2.20) - 0.05, 30)]
    teile.append(linie(pts, 0.004, "Fuge_Haube_vorn", kar, (0.4, 0, 1)))
    pts = [(-2.40, y, 0.665) for y in np.linspace(-0.67, 0.67, 30)]
    teile.append(linie(pts, 0.004, "Fuge_Heck_unten", kar, (-1, 0, 0)))
    tank = [(-1.47, -0.95, 0.80), (-1.30, -0.95, 0.80), (-1.30, -0.95, 0.93), (-1.47, -0.95, 0.93), (-1.47, -0.95, 0.80)]
    teile.append(linie(tank, 0.003, "Fuge_Tank", kar, (0, -1, 0)))
    # --- Schriftzuege ---
    for sg, rot in ((-1, R_RECHTS), (1, R_LINKS)):
        teile.append(schrift("POLIZEI", 0.17, M_WEISS, rot, (0.02, sg * 1.2, 0.47), "Schrift_Seite", kar))
    teile.append(schrift("POLIZEI", 0.15, M_FOLIE, R_HAUBE, (1.88, 0.0, 1.2), "Schrift_Haube", kar))
    teile.append(schrift("POLIZEI", 0.085, M_FOLIE, R_HECK, (-2.6, 0.0, 0.865), "Schrift_Heck", kar))
    # --- Front: Grill, Lufteinlass, Scheinwerfer, Tagfahrlicht, Frontblitzer, Kennzeichen ---
    bm = bmesh.new()
    einfuegen(bm, kasten((2.415, 0.0, 0.545), (0.05, 0.84, 0.12), fase=0.02, mi=0))       # Grill
    for z in (0.515, 0.545, 0.575):
        einfuegen(bm, kasten((2.442, 0.0, z), (0.01, 0.78, 0.008), mi=1))                 # Lamellen
    einfuegen(bm, kasten((2.405, 0.0, 0.36), (0.05, 1.10, 0.09), fase=0.02, mi=0))        # Lufteinlass
    for sg in (-1, 1):
        einfuegen(bm, kasten((2.432, sg * 0.30, 0.545), (0.02, 0.10, 0.03), fase=0.006, mi=4))             # Frontblitzer
    einfuegen(bm, kasten((2.433, 0.0, 0.445), (0.02, 0.545, 0.128), fase=0.004, mi=0))       # Kennzeichenhalter vorn
    einfuegen(bm, kasten((2.442, 0.0, 0.445), (0.012, 0.52, 0.11), fase=0.004, mi=5))       # Kennzeichen vorn
    # --- Heck: Rueckleuchten, Diffusor, Kennzeichen, Blitzer in der Heckklappe ---
    einfuegen(bm, kasten((-2.42, 0.0, 0.37), (0.04, 1.30, 0.07), fase=0.015, mi=0))         # Diffusor
    einfuegen(bm, kasten((-2.437, 0.0, 0.56), (0.02, 0.545, 0.128), fase=0.004, mi=0))      # Kennzeichenhalter hinten
    einfuegen(bm, kasten((-2.446, 0.0, 0.56), (0.012, 0.52, 0.11), fase=0.004, mi=5))       # Kennzeichen hinten
    # --- Spiegel und Tuergriffe ---
    for sg in (-1, 1):
        einfuegen(bm, kasten((0.97, sg * 0.995, 0.985), (0.15, 0.115, 0.10), fase=0.035, mi=7))
        einfuegen(bm, kasten((0.897, sg * 1.0, 0.985), (0.01, 0.10, 0.08), fase=0.004, mi=1))   # Spiegelglas
        einfuegen(bm, kasten((1.04, sg * 0.93, 0.955), (0.10, 0.06, 0.05), fase=0.012, mi=0))   # Fuss am Fensterdreieck
        for xg in (0.55, -0.62):
            yg = seiten_y(xg, 0.875) + 0.012
            einfuegen(bm, kasten((xg, sg * yg, 0.875), (0.15, 0.022, 0.028), fase=0.009, mi=1))
    # --- Blaulichtbalken quer auf dem Dach, Antenne ---
    xb, zr = -0.20, Z_TOP(-0.20)
    einfuegen(bm, kasten((xb, 0.0, zr + 0.045), (0.30, 1.20, 0.06), fase=0.02, mi=0))
    for sg in (-1, 1):
        einfuegen(bm, kasten((xb, sg * 0.45, zr + 0.095), (0.28, 0.30, 0.075), fase=0.03, mi=4))   # blaue Kuppeln
        einfuegen(bm, kasten((xb, sg * 0.50, zr + 0.012), (0.20, 0.06, 0.04), mi=0))               # Fuesse
    einfuegen(bm, kasten((xb, 0.0, zr + 0.09), (0.26, 0.60, 0.065), fase=0.015, mi=0))             # Anzeige
    einfuegen(bm, zylinder((-1.55, 0.0, Z_TOP(-1.55) + 0.17), 0.004, 0.34, "Z", segs=8, mi=0))   # Antenne
    einfuegen(bm, zylinder((-1.55, 0.0, Z_TOP(-1.55) + 0.01), 0.025, 0.03, "Z", segs=12, mi=0))
    anb = objekt("Anbauteile", bm, [M_SCHWARZ, M_CHROM, M_LINSE, M_LED, M_BLAULICHT, M_SCHILD, M_ROT, M_SILBER],
                 glatt=True, auto_glatt=35)
    teile.append(anb)
    # Scheinwerfer (Gehaeuse hell, darauf LED-Leiste und zwei Linsen) und Rueckleuchten: auf die Ecken projiziert
    M_GEH = material("Scheinwerfer_Gehaeuse", hexf("#9aa0a6"), metall=0.9, rauheit=0.18, lack=1.0)
    for sg in (-1, 1):
        u = [(sg * y, z) for (y, z) in rundumriss(0.40, 0.84, 0.615, 0.700, 0.745, r=0.025)]
        teile.append(projiziert(u, 3.0, -1, M_GEH, "Scheinwerfer", kar, 0.004))
        u = [(sg * y, z) for (y, z) in rundumriss(0.44, 0.80, 0.690, 0.700, 0.742, r=0.005)]
        teile.append(projiziert(u, 3.0, -1, M_LED, "Tagfahrlicht", kar, 0.0055))
        for yl in (0.50, 0.60):
            u = [(sg * (yl + 0.032 * math.cos(2 * math.pi * k / 16)), 0.650 + 0.025 * math.sin(2 * math.pi * k / 16)) for k in range(16)]
            teile.append(projiziert(u, 3.0, -1, M_LINSE, "Linse", kar, 0.0055))
        u = [(sg * y, z) for (y, z) in rundumriss(0.54, 0.86, 0.80, 0.93, 0.95, r=0.03)]
        teile.append(projiziert(u, -3.0, 1, M_ROT, "Rueckleuchte", kar, 0.004))
        u = [(sg * y, z) for (y, z) in rundumriss(0.42, 0.62, 0.43, 0.47, 0.47, r=0.012)]
        teile.append(projiziert(u, -3.0, 1, M_ROT, "Reflektor", kar, 0.003))
        u = [(sg * y, z) for (y, z) in rundumriss(0.32, 0.44, 0.595, 0.625, 0.625, r=0.008)]
        teile.append(projiziert(u, -3.0, 1, M_BLAULICHT, "Heckblitzer", kar, 0.003))
    # Anzeige im Lichtbalken und Kennzeichentext (Geometrie)
    for x, rot in ((xb + 0.131, R_FRONT), (xb - 0.131, R_HECK)):
        teile.append(schrift("POLIZEI", 0.04, M_LED, rot, (x, 0.0, zr + 0.09), "Schrift_Lichtbalken"))
    teile.append(schrift("PL 2340", 0.07, M_SCHWARZ, R_FRONT, (2.4485, 0.0, 0.442), "Kennzeichen_vorn"))
    teile.append(schrift("PL 2340", 0.07, M_SCHWARZ, R_HECK, (-2.4525, 0.0, 0.557), "Kennzeichen_hinten"))
    # --- Innenraum (durch die Scheiben sichtbar) ---
    bm = bmesh.new()
    einfuegen(bm, kasten((1.02, 0.0, 0.86), (0.36, 1.60, 0.16), fase=0.04, mi=0))               # Armaturenbrett
    for yy in (0.40, -0.40):
        einfuegen(bm, kasten((0.18, yy, 0.47), (0.52, 0.50, 0.14), fase=0.05, mi=0))           # Sitzflaeche
        einfuegen(bm, kasten((-0.07, yy, 0.82), (0.14, 0.48, 0.62), fase=0.05,
                             rot=Matrix.Rotation(math.radians(-14), 3, "Y"), mi=0))           # Lehne
        einfuegen(bm, kasten((-0.10, yy, 1.20), (0.10, 0.26, 0.16), fase=0.04, mi=0))          # Kopfstuetze
    einfuegen(bm, kasten((-0.78, 0.0, 0.48), (0.50, 1.40, 0.14), fase=0.05, mi=0))             # Rueckbank
    einfuegen(bm, kasten((-1.02, 0.0, 0.84), (0.13, 1.40, 0.62), fase=0.05,
                         rot=Matrix.Rotation(math.radians(-12), 3, "Y"), mi=0))
    einfuegen(bm, kasten((-0.10, 0.0, 0.18), (3.6, 1.62, 0.06), mi=0))                          # Boden innen
    lr = zylinder((0.74, 0.40, 0.99), 0.19, 0.03, "X", segs=24, mi=1, deckel=False)
    bmesh.ops.rotate(lr, cent=Vector((0.74, 0.40, 0.99)), matrix=Matrix.Rotation(math.radians(-22), 3, "Y"), verts=lr.verts)
    einfuegen(bm, lr)
    innen = objekt("Innenraum", bm, [M_INNEN, M_SCHWARZ], glatt=True, auto_glatt=40)
    teile.append(innen)
    return teile

# ---------------- Raeder: Reifen, 5-Speichen-Felge, Bremsscheibe, Bremssattel ----------------
def drehkoerper(bm, profil, segs, mi):
    """Profil (r, a) um die Achse (lokal Y = a) drehen; liefert Ringe von Vertices."""
    ringe, faces = [], []
    for i in range(segs):
        w = 2 * math.pi * i / segs
        c, s = math.cos(w), math.sin(w)
        ringe.append([bm.verts.new((r * c, a, r * s)) for (r, a) in profil])
    for i in range(segs):
        r0, r1 = ringe[i], ringe[(i + 1) % segs]
        for j in range(len(profil) - 1):
            f = bm.faces.new((r0[j], r1[j], r1[j + 1], r0[j + 1]))
            f.material_index = mi
            faces.append(f)
    return faces

def rad_bmesh():
    """Ein Rad mit Aussenseite nach +Y (lokal), Mitte im Ursprung."""
    bm = bmesh.new()
    # Reifen mit vier Laengsrillen
    lauf = [(0.335, -0.075)]
    for a in (-0.045, -0.015, 0.015, 0.045):
        lauf += [(0.335, a - 0.004), (0.3295, a - 0.003), (0.3295, a + 0.003), (0.335, a + 0.004)]
    lauf.append((0.335, 0.075))
    profil = ([(0.214, -0.100), (0.245, -0.108), (0.290, -0.112), (0.318, -0.106), (0.330, -0.092)] + lauf
              + [(0.330, 0.092), (0.318, 0.106), (0.290, 0.112), (0.245, 0.108), (0.214, 0.100)])
    reifen = drehkoerper(bm, profil, 64, 0)
    # Felgenbett und Felgenhorn
    bett = drehkoerper(bm, [(0.214, 0.098), (0.221, 0.094), (0.219, 0.086), (0.205, 0.080), (0.200, 0.040), (0.200, -0.090),
                     (0.214, -0.097)], 64, 1)
    # Nabe, Nabendeckel, Radmuttern
    einfuegen(bm, zylinder((0, 0.058, 0), 0.072, 0.036, "Y", segs=32, mi=1))
    einfuegen(bm, zylinder((0, 0.080, 0), 0.034, 0.012, "Y", segs=24, mi=2))
    for k in range(5):
        w = 2 * math.pi * k / 5 + math.pi / 5
        einfuegen(bm, zylinder((0.052 * math.cos(w), 0.078, 0.052 * math.sin(w)), 0.009, 0.014, "Y", segs=6, mi=2))
    # 5 Speichen: zur Felge hin breiter, aussen leicht gewoelbt
    for k in range(5):
        w = 2 * math.pi * k / 5
        e_r = Vector((math.cos(w), 0, math.sin(w)))
        e_t = Vector((-math.sin(w), 0, math.cos(w)))
        ringe = []
        for (r, breite, a_aussen) in ((0.066, 0.046, 0.074), (0.11, 0.050, 0.078), (0.16, 0.056, 0.081), (0.203, 0.064, 0.084)):
            c = e_r * r
            dicke = 0.026
            pts = [c + e_t * (-breite / 2) + Vector((0, a_aussen - dicke, 0)), c + e_t * (breite / 2) + Vector((0, a_aussen - dicke, 0)),
                   c + e_t * (breite / 2 - 0.006) + Vector((0, a_aussen, 0)), c + e_t * (-breite / 2 + 0.006) + Vector((0, a_aussen, 0))]
            ringe.append([bm.verts.new(p) for p in pts])
        for r0, r1 in zip(ringe, ringe[1:]):
            for j in range(4):
                f = bm.faces.new((r0[j], r1[j], r1[(j + 1) % 4], r0[(j + 1) % 4]))
                f.material_index = 1
    # Bremsscheibe (rund, darf sich mitdrehen). Keinen Bremssattel: er haengt sonst am Radknochen und dreht im Spiel mit.
    einfuegen(bm, zylinder((0, -0.020, 0), 0.165, 0.026, "Y", segs=40, mi=3))
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # offene Drehflaechen ausrichten: Reifen nach aussen (weg vom Profilmittelpunkt), Felgenbett zur Radmitte aussen
    for f in reifen:
        c = f.calc_center_median()
        r = math.hypot(c.x, c.z) or 1.0
        ref = Vector((0.272 * c.x / r, 0.0, 0.272 * c.z / r))
        if (c - ref).dot(f.normal) < 0:
            f.normal_flip()
    for f in bett:
        c = f.calc_center_median()
        if (Vector((0.0, 0.25, 0.0)) - c).dot(f.normal) < 0:
            f.normal_flip()
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
        obs[name] = objekt("Rad_" + name, bm, [M_GUMMI, M_FELGE, M_CHROM, M_BREMSE], glatt=True, auto_glatt=40)
    return obs

# ---------------- Zusammenbauen, Skelett, Export ----------------
log("Karosserie ...")
KAR = karosserie()
radlaeufe(KAR)
log("Details ...")
TEILE = details(KAR)
log("Raeder ...")
RAEDER_OB = raeder()

def gruppe(ob, name):
    vg = ob.vertex_groups.new(name=name)
    vg.add(list(range(len(ob.data.vertices))), 1.0, "REPLACE")

for ob in [KAR] + TEILE:
    gruppe(ob, "root")
for name, ob in RAEDER_OB.items():
    gruppe(ob, name)

bpy.ops.object.select_all(action="DESELECT")
for ob in [KAR] + TEILE + list(RAEDER_OB.values()):
    ob.select_set(True)
bpy.context.view_layer.objects.active = KAR
bpy.ops.object.join()
AUTO = bpy.context.view_layer.objects.active
AUTO.name = AUTO.data.name = "SK_Polizeiauto"
log("UV-Karte ...")
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.002, scale_to_bounds=False)
bpy.ops.object.mode_set(mode="OBJECT")

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

auswahl()
bpy.ops.export_scene.gltf(filepath=os.path.join(EXPORT, "SK_Polizeiauto.glb"), export_format="GLB", use_selection=True,
                          export_yup=True, export_apply=False, export_skins=True, export_animations=False,
                          export_cameras=False, export_lights=False)

# ---------------- Vorschaubilder ----------------
def welt(farbe, staerke):
    w = bpy.data.worlds.new("Welt")
    scene.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*farbe, 1)
    bg.inputs["Strength"].default_value = staerke
    return bg

def flaechenlicht(name, ort, ziel, groesse, energie, farbe=(1, 1, 1), form="RECTANGLE", groesse_y=None):
    d = bpy.data.lights.new(name, "AREA")
    d.shape = form
    d.size = groesse
    if groesse_y:
        d.size_y = groesse_y
    d.energy = energie
    d.color = farbe
    ob = bpy.data.objects.new(name, d)
    scene.collection.objects.link(ob)
    ob.location = ort
    ob.rotation_euler = (Vector(ziel) - Vector(ort)).to_track_quat("-Z", "Y").to_euler()
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

def boden_studio():
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    b = bpy.context.active_object
    b.name = "Studioboden"
    b.data.materials.append(material("Studioboden", hexf("#2b2c2f"), rauheit=0.38))
    return b

def boden_nacht():
    bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
    b = bpy.context.active_object
    b.name = "Asphalt"
    m = bpy.data.materials.new("Asphalt_nass")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    n1 = nt.nodes.new("ShaderNodeTexNoise")
    n1.inputs["Scale"].default_value = 0.35
    n1.inputs["Detail"].default_value = 6.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.50, 0.56
    n2 = nt.nodes.new("ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 60.0
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
    nt.links.new(n1.outputs["Fac"], ramp.inputs["Fac"])
    farbe = nt.nodes.new("ShaderNodeMix")
    farbe.data_type = "RGBA"
    farbe.inputs[6].default_value = (0.035, 0.035, 0.037, 1)
    farbe.inputs[7].default_value = (0.012, 0.012, 0.013, 1)
    nt.links.new(ramp.outputs["Color"], farbe.inputs[0])
    nt.links.new(farbe.outputs[2], bsdf.inputs["Base Color"])
    rau = nt.nodes.new("ShaderNodeMapRange")
    rau.inputs["To Min"].default_value, rau.inputs["To Max"].default_value = 0.55, 0.04
    nt.links.new(ramp.outputs["Color"], rau.inputs["Value"])
    nt.links.new(rau.outputs["Result"], bsdf.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    nt.links.new(n2.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    b.data.materials.append(m)
    # Hofecke aus zwei Betonwaenden im Hintergrund, faengt das Blaulicht
    beton = material("Betonwand", hexf("#55554f"), rauheit=0.9)
    for ort, groesse in (((-5.0, 6.0, 3.0), (40, 0.4, 6.0)), ((-7.0, -2.0, 3.0), (0.4, 16, 6.0))):
        bpy.ops.mesh.primitive_cube_add(size=1, location=ort)
        wand = bpy.context.active_object
        wand.scale = groesse
        wand.data.materials.append(beton)
    return b

def kamera(ort, ziel, brennweite):
    cam = scene.camera
    cam.location = ort
    cam.data.lens = brennweite
    cam.rotation_euler = (Vector(ziel) - Vector(ort)).to_track_quat("-Z", "Y").to_euler()

if SHOTS:
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 8
    scene.cycles.transmission_bounces = 8
    scene.cycles.caustics_reflective = scene.cycles.caustics_refractive = False
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    cd = bpy.data.cameras.new("Kamera")
    cd.clip_end = 300
    cam = bpy.data.objects.new("Kamera", cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    STUDIO = {
        "vorne": ((5.4, -4.1, 1.45), (0.15, 0.0, 0.62), 45),
        "hinten": ((-5.3, 4.2, 1.6), (-0.2, 0.0, 0.70), 45),
        "seite": ((0.0, -9.2, 0.95), (0.0, 0.0, 0.72), 50),
        "oben": ((4.6, -5.6, 5.6), (0.0, 0.0, 0.50), 40),
    }
    studio = [s for s in SHOTS if s in STUDIO]
    if studio:
        boden = boden_studio()
        welt((0.045, 0.05, 0.056), 1.0)
        lichter = [flaechenlicht("Haupt", (4.0, -5.0, 5.0), (0, 0, 0.6), 4.0, 900, (1.0, 0.97, 0.93), groesse_y=2.0),
                   flaechenlicht("Fuell", (-3.0, -5.5, 3.0), (0, 0, 0.6), 4.0, 280, (0.85, 0.9, 1.0)),
                   flaechenlicht("Kante", (-4.5, 4.5, 4.0), (0, 0, 0.8), 3.0, 600),
                   flaechenlicht("Oben", (0.0, 0.0, 5.0), (0, 0, 0), 6.0, 500, groesse_y=2.0)]
        for s in studio:
            kamera(*STUDIO[s])
            scene.render.filepath = os.path.join(OUT, f"polizeiauto_{s}.png")
            log("Render", s)
            bpy.ops.render.render(write_still=True)
        for ob in lichter + [boden]:
            bpy.data.objects.remove(ob)
    if "nacht" in SHOTS:
        boden_nacht()
        welt((0.006, 0.008, 0.016), 1.0)
        mond = bpy.data.objects.new("Mond", bpy.data.lights.new("Mond", "SUN"))
        scene.collection.objects.link(mond)
        mond.data.energy = 0.22
        mond.data.color = (0.7, 0.8, 1.0)
        mond.rotation_euler = (math.radians(55), 0, math.radians(-120))
        M_BLAULICHT.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1.8
        M_ROT.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 4.0
        M_LED.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 6.0
        blau = (0.12, 0.3, 1.0)
        zr = Z_TOP(-0.20)
        zk = zr + 0.095
        for sg in (-1, 1):
            # Blaulicht als Spots knapp vor den Kuppeln, von ihnen weg gerichtet: beleuchtet Dach, Boden und
            # Waende, ohne die Kuppeln selbst zu ueberstrahlen
            for ort, ri in (((-0.035, sg * 0.45, zk), (1, 0, -0.3)), ((-0.365, sg * 0.45, zk), (-1, 0, -0.3)),
                            ((-0.20, sg * 0.625, zk), (0, sg, -0.3))):
                punktlicht("Blaulicht", ort, 500, blau, radius=0.02, art="SPOT",
                           ziel=tuple(Vector(ort) + Vector(ri)), kegel=165)
            punktlicht("Frontblitzer", (2.50, sg * 0.30, 0.55), 25, blau, radius=0.03)
            punktlicht("Scheinwerfer", (2.42, sg * 0.63, 0.66), 900, (1.0, 0.93, 0.82), radius=0.04, art="SPOT",
                       ziel=(9.0, sg * 1.5, 0.0), kegel=55)
        punktlicht("Laterne", (-2.5, -4.5, 6.0), 1500, (1.0, 0.75, 0.5), radius=0.25)
        flaechenlicht("Fassade", (8.0, -8.0, 3.5), (0, 0, 0.8), 8.0, 250, (0.55, 0.65, 1.0), groesse_y=3.0)
        kamera((5.0, -3.6, 1.25), (0.1, 0.1, 0.72), 35)
        # leichtes Bloom um Blaulicht, Scheinwerfer und Ruecklichter
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
        M_BLAULICHT.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
        M_ROT.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.4
        M_LED.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 2.0

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "polizeiauto.blend"), compress=True)

# ---------------- FBX fuer Unreal (nach dem Speichern der .blend) ----------------
# Unreal rechnet in Zentimetern. Mesh und Knochen werden dafuer x100 gesetzt und die Szeneneinheit auf 0,01:
# so steht in der FBX ueberall Skalierung 1 und kein Knoten traegt den Faktor 100 (sonst Physik-/Skalierungsfehler).
scene.unit_settings.scale_length = 0.01
AUTO.data.transform(Matrix.Scale(100.0, 4))
bm = bmesh.new()
bm.from_mesh(AUTO.data)
bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4], quad_method="BEAUTY", ngon_method="BEAUTY")
bm.to_mesh(AUTO.data)
bm.free()
auswahl()
bpy.ops.object.mode_set(mode="EDIT")
for b in ARM.data.edit_bones:
    b.head, b.tail = b.head * 100.0, b.tail * 100.0
bpy.ops.object.mode_set(mode="OBJECT")
auswahl()
bpy.ops.export_scene.fbx(filepath=os.path.join(EXPORT, "SK_Polizeiauto.fbx"), use_selection=True,
                         object_types={"ARMATURE", "MESH"}, apply_unit_scale=True, global_scale=1.0,
                         apply_scale_options="FBX_SCALE_NONE", add_leaf_bones=False, primary_bone_axis="Y",
                         secondary_bone_axis="X", use_armature_deform_only=True, bake_anim=False,
                         mesh_smooth_type="FACE", use_mesh_modifiers=False, use_tspace=True)
log("exportiert:", sorted(os.listdir(EXPORT)))
log("fertig")

