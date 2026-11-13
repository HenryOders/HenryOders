# ABANDONED · Wand-Baukasten fuer ein verlassenes Krankenhaus
# Erzeugt passgenaue Module (4-m-Raster), kachelbare Texturen, Kollision fuer Unreal,
# exportiert alles als FBX und rendert zwei Vorschaubilder.
# Laeuft mit Blender 4.x: im Scripting-Tab oeffnen und ausfuehren, oder headless mit bpy.
import bpy, bmesh, math, random, os
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, noise

OUT = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(OUT, "ABANDONED_Wandbaukasten")
TEX = os.path.join(KIT, "Texturen")
MESH = os.path.join(KIT, "Modelle_FBX")
for d in (KIT, TEX, MESH):
    os.makedirs(d, exist_ok=True)
SAMPLES = int(os.environ.get("SAMPLES", "64"))
RES = [int(v) for v in os.environ.get("RES", "1600x900").split("x")]
TEXRES = int(os.environ.get("TEXRES", "1024"))

random.seed(4)
bpy.ops.wm.read_factory_settings(use_empty=True)
for mod in ("io_scene_fbx",):
    addon_utils.enable(mod, default_set=True)
scene = bpy.context.scene

# Rastermasse in Metern (Unreal: 1 m = 100 cm)
H = 3.2        # Raumhoehe
T = 0.2        # Wandstaerke
SOCKEL = 1.4   # Hoehe der Fliesen
DOOR = (1.3, 2.7, 2.3)          # Tuer: von x, bis x, Hoehe
WIN = (1.2, 2.8, 1.0, 2.2)      # Fenster: von x, bis x, Bruestung, Sturz

# ---------------- Kachelbare Texturen ----------------
def lin(hexcol):
    h = hexcol.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])

def fractal(n, beta, seed, lo=0):
    rng = np.random.default_rng(seed)
    F = np.fft.fft2(rng.standard_normal((n, n)))
    fx = np.fft.fftfreq(n)[:, None]
    fy = np.fft.fftfreq(n)[None, :]
    f = np.sqrt(fx * fx + fy * fy)
    f[0, 0] = 1.0
    F = F / f ** beta
    if lo:
        F[f < lo / n] = 0
    F[0, 0] = 0
    r = np.real(np.fft.ifft2(F))
    return (r - r.mean()) / r.std()

def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)

def normal_from_height(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength
    dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    n = np.dstack([-dx, -dy, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n

def save_image(name, arr, color=True):
    """arr: HxWx3 (0..1). Zeile 0 = unten, wie Blender es erwartet."""
    hgt, wid = arr.shape[:2]
    img = bpy.data.images.new(name, wid, hgt, alpha=False, float_buffer=False)
    rgba = np.ones((hgt, wid, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(arr, 0, 1)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = os.path.join(TEX, name + ".jpg")
    img.file_format = "JPEG"
    scene.render.image_settings.quality = 93
    img.save()
    if not color:
        img.colorspace_settings.name = "Non-Color"
    return img

def texture_set(name, albedo, rough, height, strength):
    n = normal_from_height(height, strength)
    gl = n * 0.5 + 0.5
    dx = gl.copy()
    dx[..., 1] = 1.0 - dx[..., 1]
    imgs = {
        "base": save_image(f"T_{name}_BaseColor", albedo),
        "rough": save_image(f"T_{name}_Roughness", np.dstack([rough] * 3), color=False),
        "normal": save_image(f"T_{name}_Normal_OpenGL", gl, color=False),
    }
    save_image(f"T_{name}_Normal_DirectX_Unreal", dx, color=False)
    return imgs

N = TEXRES
yy, xx = np.mgrid[0:N, 0:N] / N   # 0..1, kachelbar

def make_tiles():
    # 1 Textur = 1 m x 1 m, 5 x 5 Fliesen zu 20 cm
    k = 5
    u, v = xx * k, yy * k
    iu, iv = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - iu, v - iv
    edge = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv))
    grout = edge < 0.022
    bevel = smooth(0.022, 0.07, edge)
    rng = np.random.default_rng(7)
    tint = rng.normal(0, 0.035, (k, k))
    yellow = rng.uniform(0, 1, (k, k))
    missing = rng.uniform(0, 1, (k, k)) < 0.06
    base = lin("#cdd8cf")
    alb = np.ones((N, N, 3)) * base
    alb += tint[iv % k, iu % k][..., None]
    alb += (yellow[iv % k, iu % k] > 0.7)[..., None] * np.array([0.03, 0.01, -0.06])
    dirt = smooth(0.3, 1.8, fractal(N, 1.3, 11))
    grime = fractal(N, 0.7, 12)
    alb *= (1 - 0.35 * dirt)[..., None]
    alb *= (1 - 0.05 * np.clip(grime, 0, 3))[..., None]
    alb[grout] = lin("#57544d") * (1 - 0.3 * dirt[grout])[..., None]
    miss = missing[iv % k, iu % k] & ~grout
    conc = lin("#7c7a73") * (0.85 + 0.15 * fractal(N, 1.0, 13))[..., None]
    alb[miss] = conc[miss]
    height = bevel * 1.0
    height = np.where(grout, 0.0, height)
    height = np.where(miss, 0.15 + 0.05 * fractal(N, 1.2, 14), height)
    height += 0.01 * fractal(N, 0.5, 15)
    rough = np.where(grout, 0.92, 0.28 + 0.35 * dirt)
    rough = np.where(miss, 0.95, rough)
    return texture_set("Fliesen", alb, rough, height, 6.0)

def make_plaster():
    # 1 Textur = 2 m x 2 m: alte Farbe, die abblaettert, Wasserflecken
    paint = lin("#9fb29b")
    plaster = lin("#bdb5a5")
    peelmask = fractal(N, 1.15, 21) + 0.35 * fractal(N, 0.6, 22)
    peel = smooth(1.3, 1.42, peelmask)
    rim = smooth(1.18, 1.3, peelmask) * (1 - peel)
    crack = smooth(0.05, 0.0, np.abs(fractal(N, 1.05, 28))) * smooth(0.2, 0.9, fractal(N, 1.2, 29))
    stain = smooth(0.8, 1.6, fractal(N, 1.4, 23))
    ring = smooth(0.7, 0.8, fractal(N, 1.4, 23)) * (1 - stain)
    speck = np.clip(fractal(N, 0.2, 24) - 2.2, 0, 1)
    alb = paint * (0.95 + 0.05 * fractal(N, 0.9, 25))[..., None]
    alb = alb * (1 - peel[..., None]) + plaster * (0.85 + 0.15 * fractal(N, 1.0, 26))[..., None] * peel[..., None]
    alb *= (1 - 0.25 * rim)[..., None]
    alb = alb * (1 - 0.35 * stain[..., None]) + lin("#7a6340") * 0.35 * stain[..., None]
    alb *= (1 - 0.25 * ring)[..., None]
    alb *= (1 - 0.6 * speck)[..., None]
    alb *= (1 - 0.45 * crack)[..., None]
    height = 1.0 - 0.6 * peel + 0.25 * rim - 0.3 * crack + 0.04 * fractal(N, 0.8, 27)
    rough = 0.62 + 0.25 * peel + 0.1 * stain
    return texture_set("Putz", alb, rough, height, 3.0)

def make_linoleum():
    # 1 Textur = 2,4 m x 2,4 m, Schachbrett aus 30-cm-Platten
    k = 8
    u, v = xx * k, yy * k
    iu, iv = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - iu, v - iv
    edge = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv))
    seam = edge < 0.008
    checker = ((iu + iv) % 2 == 0)
    a, b = lin("#b9b29d"), lin("#6c7c72")
    alb = np.where(checker[..., None], a, b) * (0.95 + 0.05 * fractal(N, 0.4, 31))[..., None]
    speck = np.clip(fractal(N, 0.1, 32) - 1.6, 0, 1)
    alb *= (1 - 0.25 * speck)[..., None]
    dirt = smooth(0.2, 1.7, fractal(N, 1.25, 33))
    scuff = smooth(1.8, 2.6, fractal(N, 0.55, 34))
    alb *= (1 - 0.4 * dirt)[..., None]
    alb = alb * (1 - 0.3 * scuff[..., None]) + 0.3 * scuff[..., None] * lin("#3b3934")
    alb[seam] *= 0.6
    height = np.where(seam, 0.2, 1.0) - 0.05 * scuff + 0.01 * fractal(N, 0.6, 35)
    rough = 0.4 + 0.35 * dirt + 0.15 * scuff
    return texture_set("Linoleum", alb, rough, height, 4.0)

def make_ceiling():
    # 1 Textur = 2,4 m x 2,4 m, Rasterdecke mit 60-cm-Platten
    k = 4
    u, v = xx * k, yy * k
    iu, iv = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = u - iu, v - iv
    edge = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv))
    rail = edge < 0.025
    rng = np.random.default_rng(41)
    stained = rng.uniform(0, 1, (k, k)) < 0.3
    missing = rng.uniform(0, 1, (k, k)) < 0.07
    pores = fractal(N, 0.05, 42)
    alb = lin("#d9d6cc") * (0.93 + 0.04 * np.clip(pores, -2, 2))[..., None]
    st = stained[iv % k, iu % k] * smooth(0.4, 1.5, fractal(N, 1.3, 43))
    alb = alb * (1 - 0.45 * st[..., None]) + 0.45 * st[..., None] * lin("#8a6f45")
    alb[rail] = lin("#b8b8b2")
    miss = missing[iv % k, iu % k] & ~rail
    alb[miss] = lin("#1e1c1a")
    height = np.where(rail, 1.0, 0.6) - 0.02 * np.clip(pores, -2, 2)
    height = np.where(miss, 0.0, height)
    rough = np.where(rail, 0.5, 0.9)
    return texture_set("Rasterdecke", alb, rough, height, 3.0)

def make_concrete():
    # 1 Textur = 1 m x 1 m: Bruchkanten, Schutt
    alb = lin("#8e8a82") * (0.8 + 0.12 * fractal(N, 1.1, 51) + 0.06 * fractal(N, 0.3, 52))[..., None]
    pebbles = smooth(1.2, 1.6, fractal(N, 0.15, 53))
    alb = alb * (1 - 0.3 * pebbles[..., None]) + 0.3 * pebbles[..., None] * lin("#6d655b")
    height = 0.6 * fractal(N, 1.2, 54) + 0.3 * pebbles
    rough = 0.9 + 0.05 * fractal(N, 0.8, 55)
    return texture_set("Beton", alb, np.clip(rough, 0, 1), height, 1.2)

# ---------------- Materialien ----------------
def tex_material(name, imgs):
    m = bpy.data.materials.new("M_" + name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    def node(img):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img
        return n
    b, r, n = node(imgs["base"]), node(imgs["rough"]), node(imgs["normal"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(b.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(r.outputs["Color"], bsdf.inputs["Roughness"])
    nt.links.new(n.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m

def color_material(name, hexcol, rough=0.6, metal=0.0, emit=0.0):
    m = bpy.data.materials.new("M_" + name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    c = lin(hexcol) ** 2.2
    b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (1.0, 0.97, 0.9, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m

MAT = {
    "fliesen": tex_material("Fliesen", make_tiles()),
    "putz": tex_material("Putz", make_plaster()),
    "boden": tex_material("Linoleum", make_linoleum()),
    "decke": tex_material("Rasterdecke", make_ceiling()),
    "beton": tex_material("Beton", make_concrete()),
    "leiste": color_material("Leiste", "#6f7a72", 0.5),
    "metall": color_material("Metall_lackiert", "#7d8580", 0.45, 0.6),
    "leuchte": color_material("Leuchte", "#f2efe6", 0.3, 0.0, 6.0),
}
UVSCALE = {"fliesen": 1.0, "putz": 0.5, "boden": 1 / 2.4, "decke": 1 / 2.4, "beton": 1.0,
           "leiste": 1.0, "metall": 1.0, "leuchte": 1.0}

# ---------------- Geometrie-Hilfen ----------------
def faces_of(vs):
    return {f for v in vs for f in v.link_faces}

def box(bm, lo, hi, mi):
    lo, hi = Vector(lo), Vector(hi)
    res = bmesh.ops.create_cube(bm, size=1.0)
    vs = res["verts"]
    bmesh.ops.scale(bm, vec=hi - lo, verts=vs)
    bmesh.ops.translate(bm, vec=(lo + hi) / 2, verts=vs)
    for f in faces_of(vs):
        f.material_index = mi
    return vs

def uv_project(bm, mats):
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        s = UVSCALE[mats[f.material_index]]
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for l in f.loops:
            co = l.vert.co
            if ax == 1:
                l[uv].uv = ((co.x if n.y < 0 else -co.x) * s, co.z * s)
            elif ax == 0:
                l[uv].uv = ((co.y if n.x > 0 else -co.y) * s, co.z * s)
            else:
                l[uv].uv = (co.x * s, co.y * s)

PIECES = []
def finish(name, bm, mats, colliders=()):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    uv_project(bm, mats)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for k in mats:
        me.materials.append(MAT[k])
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    cols = []
    for i, (lo, hi) in enumerate(colliders):
        cb = bmesh.new()
        box(cb, lo, hi, 0)
        cm = bpy.data.meshes.new(f"UCX_{name}_{i:02d}")
        cb.to_mesh(cm)
        cb.free()
        co = bpy.data.objects.new(f"UCX_{name}_{i:02d}", cm)
        co.display_type = "WIRE"
        co.hide_render = True
        scene.collection.objects.link(co)
        cols.append(co)
    PIECES.append((ob, cols))
    return ob

WALL_MATS = ["fliesen", "putz", "leiste"]

def wall_segment(bm, x0, x1, z0, z1):
    """Wandstueck zwischen x0..x1 und z0..z1, unten Fliesen, oben Putz, Leiste an der Grenze."""
    if z0 < SOCKEL:
        box(bm, (x0, -T / 2, z0), (x1, T / 2, min(z1, SOCKEL)), 0)
    if z1 > SOCKEL:
        box(bm, (x0, -T / 2, max(z0, SOCKEL)), (x1, T / 2, z1), 1)

def build_wall(name, length, door=None, window=None):
    bm = bmesh.new()
    cuts = [0.0, length]
    if door: cuts += [door[0], door[1]]
    if window: cuts += [window[0], window[1]]
    cuts = sorted(set(cuts))
    cols = []
    runs = []
    for a, b in zip(cuts, cuts[1:]):
        mid = (a + b) / 2
        if door and door[0] <= mid <= door[1]:
            wall_segment(bm, a, b, door[2], H)
            cols.append(((a, -T / 2, door[2]), (b, T / 2, H)))
        elif window and window[0] <= mid <= window[1]:
            wall_segment(bm, a, b, 0.0, window[2])
            wall_segment(bm, a, b, window[3], H)
            cols.append(((a, -T / 2, 0), (b, T / 2, window[2])))
            cols.append(((a, -T / 2, window[3]), (b, T / 2, H)))
        else:
            wall_segment(bm, a, b, 0.0, H)
            cols.append(((a, -T / 2, 0), (b, T / 2, H)))
            runs.append([a, b])
    merged = []
    for a, b in runs:
        if merged and abs(merged[-1][1] - a) < 1e-6:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    for a, b in merged:
        box(bm, (a + 0.001, -T / 2 - 0.025, SOCKEL - 0.03), (b - 0.001, T / 2 + 0.025, SOCKEL + 0.03), 2)
    return finish(name, bm, WALL_MATS, cols)

def build_broken_wall(name, length):
    """Wand mit ausgebrochenem Loch: Raster aus 10-cm-Zellen, Loch per Rauschen, dann Dicke."""
    cell = 0.1
    nx, nz = int(round(length / cell)), int(round(H / cell))
    cx, cz, rad = 2.2, 1.25, 0.95
    keep = np.ones((nz, nx), dtype=bool)
    for j in range(nz):
        for i in range(nx):
            x, z = (i + 0.5) * cell, (j + 0.5) * cell
            ang = math.atan2(z - cz, x - cx)
            r = rad * (1 + 0.28 * noise.noise(Vector((math.cos(ang) * 1.3, math.sin(ang) * 1.3, 4.2)))
                       + 0.12 * noise.noise(Vector((x * 3.1, z * 3.1, 9.0))))
            if math.hypot((x - cx) * 0.85, z - cz) < r and z > 0.15:
                keep[j, i] = False
    bm = bmesh.new()
    vid = {}
    def v(i, j):
        if (i, j) not in vid:
            vid[(i, j)] = bm.verts.new((i * cell, -T / 2, j * cell))
        return vid[(i, j)]
    for j in range(nz):
        for i in range(nx):
            if keep[j, i]:
                f = bm.faces.new((v(i, j), v(i, j + 1), v(i + 1, j + 1), v(i + 1, j)))
                f.material_index = 0 if (j + 0.5) * cell < SOCKEL else 1
    bm.normal_update()
    front = list(bm.faces)
    bmesh.ops.solidify(bm, geom=front, thickness=T)
    ys = [vv.co.y for vv in bm.verts]
    shift = -(min(ys) + max(ys)) / 2
    for vv in bm.verts:
        vv.co.y += shift
    bm.normal_update()
    # Flaechen der Bruchkante bekommen Beton, Aussenkanten bleiben wie die Wand
    for f in bm.faces:
        n = f.normal
        c = f.calc_center_median()
        if abs(n.y) > 0.9:
            continue
        outer = c.x < 0.01 or c.x > length - 0.01 or c.z < 0.01 or c.z > H - 0.01
        if not outer:
            f.material_index = 3
    # Ebenen zusammenfassen, damit die Wand nicht unnoetig viele Polygone hat
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1), verts=bm.verts, edges=bm.edges,
                             delimit={"MATERIAL", "NORMAL"})
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    # leichte Unebenheit an der Bruchkante
    for vtx in bm.verts:
        if any(f.material_index == 3 for f in vtx.link_faces) and 0.05 < vtx.co.x < length - 0.05 and 0.05 < vtx.co.z < H - 0.05:
            vtx.co.x += 0.03 * noise.noise(vtx.co * 7.0)
            vtx.co.z += 0.03 * noise.noise(vtx.co * 7.0 + Vector((3, 3, 3)))
    # Leiste nur auf den stehenden Teilen
    row = int(SOCKEL / cell)
    i = 0
    while i < nx:
        if keep[row, i] and keep[row - 1, i]:
            s = i
            while i < nx and keep[row, i] and keep[row - 1, i]:
                i += 1
            box(bm, (s * cell + 0.001, -T / 2 - 0.025, SOCKEL - 0.03), (i * cell - 0.001, T / 2 + 0.025, SOCKEL + 0.03), 2)
        i += 1
    return finish(name, bm, WALL_MATS + ["beton"])

def build_floor(name, size=4.0, ceiling=False):
    bm = bmesh.new()
    if ceiling:
        box(bm, (0, 0, 0), (size, size, 0.1), 0)
    else:
        box(bm, (0, 0, -0.1), (size, size, 0), 0)
    lo, hi = ((0, 0, 0), (size, size, 0.1)) if ceiling else ((0, 0, -0.1), (size, size, 0))
    return finish(name, bm, ["decke" if ceiling else "boden"], [(lo, hi)])

def build_pillar(name):
    bm = bmesh.new()
    s = 0.3
    box(bm, (-s / 2, -s / 2, 0), (s / 2, s / 2, SOCKEL), 0)
    box(bm, (-s / 2, -s / 2, SOCKEL), (s / 2, s / 2, H), 1)
    return finish(name, bm, ["fliesen", "putz"], [((-s / 2, -s / 2, 0), (s / 2, s / 2, H))])

def build_frame(name, x0, x1, z0, z1, depth=0.28, w=0.07, sill=False):
    bm = bmesh.new()
    d = depth / 2
    e = 0.02
    box(bm, (x0 - w, -d, z0), (x0 + e, d, z1 + w), 0)
    box(bm, (x1 - e, -d, z0), (x1 + w, d, z1 + w), 0)
    box(bm, (x0 - w, -d, z1 - e), (x1 + w, d, z1 + w), 0)
    if sill:
        box(bm, (x0 - w, -d - 0.05, z0 - w), (x1 + w, d, z0 + e), 0)
        mid = (x0 + x1) / 2
        box(bm, (mid - 0.03, -0.03, z0), (mid + 0.03, 0.03, z1), 0)
        box(bm, (x0, -0.03, (z0 + z1) / 2 - 0.03), (x1, 0.03, (z0 + z1) / 2 + 0.03), 0)
    return finish(name, bm, ["metall"])

def build_lamp(name):
    bm = bmesh.new()
    box(bm, (-0.65, -0.17, -0.09), (0.65, 0.17, 0.0), 0)
    box(bm, (-0.6, -0.13, -0.1), (0.6, 0.13, -0.09), 1)
    return finish(name, bm, ["metall", "leuchte"])

def build_rubble(name):
    bm = bmesh.new()
    rng = random.Random(9)
    for i in range(16):
        res = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
        vs = res["verts"]
        s = rng.uniform(0.05, 0.22)
        for vv in vs:
            vv.co = Vector((vv.co.x * s * rng.uniform(0.8, 1.6), vv.co.y * s * rng.uniform(0.8, 1.4),
                            vv.co.z * s * rng.uniform(0.5, 0.9)))
        ang = rng.uniform(0, math.pi)
        rr = rng.uniform(0, 0.9) ** 0.7
        bmesh.ops.translate(bm, vec=Vector((math.cos(ang) * rr * 1.3, -0.15 - abs(math.sin(ang)) * rr * 0.9, s * 0.35)), verts=vs)
        for f in faces_of(vs):
            f.material_index = 0
    return finish(name, bm, ["beton"])

# ---------------- Baukasten bauen ----------------
w4 = build_wall("SM_Wand_4m", 4.0)
w2 = build_wall("SM_Wand_2m", 2.0)
wd = build_wall("SM_Wand_Tuer_4m", 4.0, door=DOOR)
ww = build_wall("SM_Wand_Fenster_4m", 4.0, window=WIN)
wb = build_broken_wall("SM_Wand_Kaputt_4m", 4.0)
fl = build_floor("SM_Boden_4x4m")
ce = build_floor("SM_Decke_4x4m", ceiling=True)
pi = build_pillar("SM_Saeule")
fd = build_frame("SM_Tuerrahmen", DOOR[0], DOOR[1], 0.0, DOOR[2])
fw = build_frame("SM_Fensterrahmen", WIN[0], WIN[1], WIN[2], WIN[3], sill=True)
la = build_lamp("SM_Deckenlampe")
ru = build_rubble("SM_Schutt")

# ---------------- Export (jedes Teil mit seiner Kollision) ----------------
for ob, cols in PIECES:
    bpy.ops.object.select_all(action="DESELECT")
    for o in [ob] + cols:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=os.path.join(MESH, ob.name + ".fbx"), use_selection=True,
                             apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE",
                             bake_space_transform=False, path_mode="STRIP")
for ob, cols in PIECES:
    for c in cols:
        bpy.data.objects.remove(c, do_unlink=True)

# Teile selbst bleiben als Vorlage unsichtbar; im Bild stehen Kopien
for ob, _ in PIECES:
    ob.hide_render = True
    ob.hide_viewport = True

def put(src, loc, rz=0.0, name=None, sx=1.0):
    o = bpy.data.objects.new(name or src.name, src.data)
    o.location = loc
    o.rotation_euler = (0, 0, rz)
    o.scale = (sx, 1, 1)
    scene.collection.objects.link(o)
    return o

# ---------------- Vorschau 1: Flur im verlassenen Krankenhaus ----------------
left = [wd, w4, wb, wd, w4]
right = [w4, ww, wd, ww, w4]
for i in range(5):
    x = i * 4.0
    put(fl, (x, 0, 0))
    put(ce, (x, 0, H))
    put(left[i], (x, 0, 0))
    if left[i] is wd:
        put(fd, (x, 0, 0))
    if left[i] is wb:
        put(ru, (x + 2.2, T / 2 + 0.05, 0), rz=math.pi)
    put(right[i], (x + 4.0, 4.0, 0), rz=math.pi)
    if right[i] is ww:
        put(fw, (x + 4.0, 4.0, 0), rz=math.pi)
    if right[i] is wd:
        put(fd, (x + 4.0, 4.0, 0), rz=math.pi)
put(wd, (20.0, 0, 0), rz=math.pi / 2)
put(fd, (20.0, 0, 0), rz=math.pi / 2)
for x in (0, 20):
    for y in (0, 4):
        put(pi, (x, y, 0))
# Lampen: eine an, eine haengt schief herunter
l1 = put(la, (10.0, 2.0, H))
l2 = put(la, (14.0, 2.0, H - 0.35))
l2.rotation_euler = (math.radians(14), math.radians(-8), 0.2)

def area_light(name, loc, size, energy, color=(1.0, 0.95, 0.85)):
    d = bpy.data.lights.new(name, "AREA")
    d.shape = "RECTANGLE"
    d.size, d.size_y = size
    d.energy = energy
    d.color = color
    o = bpy.data.objects.new(name, d)
    o.location = loc
    scene.collection.objects.link(o)
    return o

area_light("Lampe 1", (10.0, 2.0, H - 0.11), (1.2, 0.26), 120)
spot_d = bpy.data.lights.new("Taschenlampe", "SPOT")
spot_d.energy = 900
spot_d.spot_size = math.radians(38)
spot_d.spot_blend = 0.6
spot_d.color = (0.85, 0.92, 1.0)
spot = bpy.data.objects.new("Taschenlampe", spot_d)
scene.collection.objects.link(spot)

sun_d = bpy.data.lights.new("Sonne", "SUN")
sun_d.energy = 28.0
sun_d.angle = math.radians(1.0)
sun_d.color = (1.0, 0.86, 0.66)
sun = bpy.data.objects.new("Sonne", sun_d)
sun.rotation_euler = (math.radians(62), 0, math.radians(195))
scene.collection.objects.link(sun)

world = bpy.data.worlds.new("Welt")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.06, 0.08, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6

# leichter Staub in der Luft, damit Licht sichtbar wird
bpy.ops.mesh.primitive_cube_add(size=1, location=(10, 2, H / 2))
fog = bpy.context.active_object
fog.name = "Staub"
fog.scale = (22, 4.2, H)
fm = bpy.data.materials.new("M_Staub")
fm.use_nodes = True
fnt = fm.node_tree
fnt.nodes.remove(fnt.nodes["Principled BSDF"])
vol = fnt.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Density"].default_value = float(os.environ.get("FOG", "0.035"))
fnt.links.new(vol.outputs["Volume"], fnt.nodes["Material Output"].inputs["Volume"])
fog.data.materials.append(fm)

cam_d = bpy.data.cameras.new("Kamera")
cam_d.lens = 18
cam = bpy.data.objects.new("Kamera", cam_d)
cam.location = (0.9, 2.3, 1.62)
look = Vector((12.0, 1.55, 1.25))
cam.rotation_euler = (look - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.collection.objects.link(cam)
scene.camera = cam
spot.location = cam.location + Vector((0.15, -0.25, -0.2))
spot.rotation_euler = (Vector((7.0, 1.2, 0.9)) - spot.location).to_track_quat("-Z", "Y").to_euler()

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.cycles.volume_step_rate = 4.0
scene.cycles.max_bounces = 6
scene.render.resolution_x, scene.render.resolution_y = RES
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.render.filepath = os.path.join(OUT, "abandoned_flur.png")
BLEND = os.path.join(KIT, "ABANDONED_Wandbaukasten.blend")
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
bpy.ops.render.render(write_still=True)

# ---------------- Vorschau 2: alle Teile nebeneinander ----------------
for o in list(scene.objects):
    if o.type in ("MESH", "LIGHT") and o.name not in ("Kamera",):
        o.hide_render = True
bx = 300.0
row = [(w4, 0.0), (w2, 4.8), (wd, 7.6), (ww, 12.4), (wb, 17.2), (pi, 22.2)]
for src, x in row:
    put(src, (bx + x, 0, 0)).hide_render = False
put(fd, (bx + 7.6, 0, 0)).hide_render = False
put(fw, (bx + 12.4, 0, 0)).hide_render = False
put(ru, (bx + 17.2 + 2.2, -T / 2 - 0.05, 0)).hide_render = False
bpy.ops.mesh.primitive_plane_add(size=80, location=(bx + 11, 0, 0))
floor = bpy.context.active_object
floor.data.materials.append(color_material("Hintergrund", "#9a968e", 0.9))
key = bpy.data.lights.new("Licht", "SUN")
key.energy = 3.0
key.angle = math.radians(8)
k = bpy.data.objects.new("Licht", key)
k.rotation_euler = (math.radians(55), 0, math.radians(-30))
scene.collection.objects.link(k)
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.58, 0.62, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
fog.hide_render = True
cam_d.lens = 35
cam.location = (bx + 11.3, -24.0, 5.0)
cam.rotation_euler = (Vector((bx + 11.3, 0, 1.4)) - cam.location).to_track_quat("-Z", "Y").to_euler()
scene.render.resolution_y = int(RES[0] * 0.36)
scene.render.filepath = os.path.join(OUT, "abandoned_baukasten.png")
bpy.ops.render.render(write_still=True)

tris = {ob.name: sum(len(p.vertices) - 2 for p in ob.data.polygons) for ob, _ in PIECES}
print("Dreiecke je Teil:", tris)
print("fertig")
