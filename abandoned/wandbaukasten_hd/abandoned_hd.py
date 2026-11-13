# ABANDONED · Wand-Baukasten HD fuer Unreal Engine 5 (Nanite)
# Alles wird hier erzeugt: echte Fliesen mit Fasen und Fugen, Rasterdecke mit Platten,
# Linoleum-Boden aus einzelnen Platten, kaputte Wand mit Bewehrung, 4K-Texturen.
# Laeuft mit Blender 4.x (Scripting-Tab) oder headless mit dem bpy-Modul.
import bpy, bmesh, math, random, os, time
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, noise

T0 = time.time()
OUT = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(OUT, "ABANDONED_Wandbaukasten_HD")
TEX = os.path.join(KIT, "Texturen")
MESH = os.path.join(KIT, "Modelle_FBX")
for d in (KIT, TEX, MESH):
    os.makedirs(d, exist_ok=True)
SAMPLES = int(os.environ.get("SAMPLES", "96"))
RES = [int(v) for v in os.environ.get("RES", "1920x1080").split("x")]
TEXDIV = int(os.environ.get("TEXDIV", "1"))      # 4 = schnelle Tests mit kleinen Texturen
SHOTS = os.environ.get("SHOTS", "flur,nah").split(",")

random.seed(5)
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("io_scene_fbx", default_set=True)
scene = bpy.context.scene

H, T, SOCKEL = 3.2, 0.2, 1.4
TILE, GAP, TT, BED = 0.2, 0.003, 0.008, 0.004
FACE = T / 2 + BED + TT                      # Abstand Fliesenoberflaeche zur Wandmitte
DOOR = (1.3, 2.7, 2.3)
WIN = (1.2, 2.8, 1.0, 2.2)

def log(*a):
    print(f"[{time.time() - T0:6.1f}s]", *a, flush=True)

# ======================= Texturen =======================
def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)

def fractal(n, beta, seed, aniso=1.0, sigma=0.0):
    """Kachelbares Rauschen: 1/f^beta-Spektrum, optional gestreckt (aniso) oder weichgezeichnet (sigma in Pixeln)."""
    rng = np.random.default_rng(seed)
    F = np.fft.rfft2(rng.standard_normal((n, n)).astype(np.float32))
    fy = np.fft.fftfreq(n)[:, None]
    fx = np.fft.rfftfreq(n)[None, :]
    f = np.sqrt(fx * fx + (fy * aniso) ** 2)
    f[0, 0] = 1.0
    F *= (1.0 / f ** beta).astype(np.float32)
    if sigma:
        F *= np.exp(-2 * (math.pi * sigma) ** 2 * (fx * fx + fy * fy)).astype(np.float32)
    F[0, 0] = 0
    r = np.fft.irfft2(F, s=(n, n)).astype(np.float32)
    return (r - r.mean()) / (r.std() + 1e-9)

def sm(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)

def mix(a, b, t):
    return a * (1 - t[..., None]) + b * t[..., None]

def save_image(name, arr, color=True):
    hgt, wid = arr.shape[:2]
    img = bpy.data.images.new(name, wid, hgt, alpha=False)
    rgba = np.ones((hgt, wid, 4), dtype=np.float32)
    if arr.ndim == 2:
        rgba[..., :3] = np.clip(arr, 0, 1)[..., None]
    else:
        rgba[..., :3] = np.clip(arr, 0, 1)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = os.path.join(TEX, name + ".jpg")
    img.file_format = "JPEG"
    img.save()
    if not color:
        img.colorspace_settings.name = "Non-Color"
    return img

def texture_set(name, albedo, rough, height, strength, keep_height=False):
    n = albedo.shape[0]
    s = strength * n / 1024.0
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * s
    dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * s
    nrm = np.dstack([-dx, -dy, np.ones_like(height)])
    nrm /= np.linalg.norm(nrm, axis=2, keepdims=True)
    enc = nrm * 0.5 + 0.5
    enc[..., 1] = 1.0 - enc[..., 1]          # DirectX-Normalen fuer Unreal (Blender dreht im Material zurueck)
    imgs = {"base": save_image(f"T_{name}_BaseColor", albedo),
            "rough": save_image(f"T_{name}_Roughness", rough, color=False),
            "normal": save_image(f"T_{name}_Normal", enc, color=False)}
    if keep_height:
        hmin, hmax = height.min(), height.max()
        save_image(f"T_{name}_Height", (height - hmin) / (hmax - hmin + 1e-9), color=False)
    log("Textur", name, n)
    return imgs

def coords(n):
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / n
    return xx, yy

def tex_putz():
    # 4096 px = 4 m: mehrere Farbschichten blaettern ab, Risse, Wasserraender, Schimmelpunkte
    n = 4096 // TEXDIV
    big = fractal(n, 1.7, 101)
    peel = fractal(n, 1.25, 102) + 0.45 * fractal(n, 0.75, 103)
    top_gone = sm(1.15, 1.22, peel)
    deep = sm(1.55, 1.62, peel + 0.3 * fractal(n, 0.9, 104))
    lip = sm(0.98, 1.15, peel) * (1 - top_gone)
    crack = sm(0.045, 0.0, np.abs(fractal(n, 1.0, 105))) * sm(0.3, 1.1, fractal(n, 1.4, 106))
    hair = sm(0.02, 0.0, np.abs(fractal(n, 0.85, 107))) * sm(0.6, 1.4, fractal(n, 1.2, 108))
    st = fractal(n, 1.5, 109)
    stain = sm(0.9, 1.9, st)
    tide = sm(0.75, 0.82, st) * sm(0.92, 0.84, st)
    streak = sm(0.8, 2.2, fractal(n, 1.1, 110, aniso=5.0))
    mold = sm(2.2, 2.8, fractal(n, 0.2, 111, sigma=2.5 * n / 4096)) * sm(0.2, 1.0, fractal(n, 1.3, 112))
    grain = fractal(n, 0.35, 113, sigma=0.8)
    paint = hexc("#9cb3a1") * (0.95 + 0.04 * big[..., None] + 0.015 * grain[..., None])
    under = hexc("#d7cfb7") * (0.93 + 0.05 * fractal(n, 1.0, 114)[..., None])
    plaster = hexc("#ada28b") * (0.86 + 0.08 * fractal(n, 0.9, 115)[..., None] + 0.04 * grain[..., None])
    alb = mix(paint, under, top_gone)
    alb = mix(alb, plaster, deep)
    alb *= (1 - 0.22 * lip)[..., None]
    alb = mix(alb, alb * hexc("#8a6a3e") * 1.25, 0.55 * stain)
    alb *= (1 - 0.35 * tide)[..., None]
    alb *= (1 - 0.18 * streak)[..., None]
    alb = mix(alb, hexc("#2b2d22"), 0.75 * mold)
    alb *= (1 - 0.55 * crack - 0.25 * hair)[..., None]
    height = 1.0 - 0.18 * top_gone - 0.2 * deep + 0.07 * lip - 0.3 * crack - 0.1 * hair + 0.03 * grain + 0.05 * deep * fractal(n, 0.7, 116)
    rough = 0.52 + 0.06 * big + 0.18 * top_gone + 0.15 * deep + 0.08 * stain + 0.1 * mold
    return texture_set("Putz", alb, rough, height, 9.0, keep_height=True)

def tex_glasur():
    # 4096 px = 4 m x 4 m, Fliesenraster 20 cm ist eingebacken (jede Fliese hat ihren eigenen Ton)
    n = 4096 // TEXDIV
    xx, yy = coords(n)
    k = 20
    iu, iv = np.floor(xx * k).astype(int), np.floor(yy * k).astype(int)
    rng = np.random.default_rng(201)
    tint = rng.normal(0, 0.03, (k, k)).astype(np.float32)
    warm = (rng.uniform(0, 1, (k, k)) > 0.82).astype(np.float32)
    crazed = (rng.uniform(0, 1, (k, k)) > 0.6).astype(np.float32)
    base = hexc("#d6e0d6") * (1 + tint[iv, iu][..., None])
    base = mix(base, base * hexc("#f0dfb8"), 0.5 * warm[iv, iu])
    craze = sm(0.03, 0.0, np.abs(fractal(n, 0.9, 202))) * crazed[iv, iu]
    dirt = sm(0.0, 2.0, fractal(n, 1.35, 203))
    run = sm(0.6, 2.4, fractal(n, 1.0, 204, aniso=7.0))
    rust = sm(2.0, 2.6, fractal(n, 1.2, 205)) * sm(0.5, 1.5, fractal(n, 1.0, 206, aniso=6.0))
    alb = base * (1 - 0.3 * dirt - 0.2 * run)[..., None]
    alb = mix(alb, hexc("#8b5a2b"), 0.6 * rust)
    alb *= (1 - 0.35 * craze)[..., None]
    height = -0.2 * craze + 0.02 * fractal(n, 1.6, 207)
    rough = 0.1 + 0.4 * dirt + 0.25 * run + 0.3 * rust + 0.3 * craze
    return texture_set("Fliesenglasur", alb, rough, height, 4.0)

def tex_moertel():
    n = 2048 // TEXDIV
    sand = fractal(n, 0.25, 301, sigma=0.7)
    alb = hexc("#7d786d") * (0.85 + 0.08 * fractal(n, 1.2, 302)[..., None] + 0.06 * sand[..., None])
    xx, yy = coords(n)
    groove = 0.5 + 0.5 * np.sin(yy * 2 * math.pi * 80)
    alb *= (1 - 0.08 * groove)[..., None]
    height = 0.4 * groove + 0.2 * sand
    rough = 0.93 + 0.0 * sand
    return texture_set("Moertel", alb, rough, height, 2.0)

def tex_linoleum():
    # 4096 px = 4 m x 4 m, Schachbrett aus 40-cm-Platten passend zum Boden-Modell
    n = 4096 // TEXDIV
    xx, yy = coords(n)
    k = 10
    iu, iv = np.floor(xx * k).astype(int), np.floor(yy * k).astype(int)
    rng = np.random.default_rng(401)
    tint = rng.normal(0, 0.03, (k, k)).astype(np.float32)
    checker = ((iu + iv) % 2 == 0).astype(np.float32)
    base = mix(hexc("#6a7a70"), hexc("#bdb5a0"), checker) * (1 + tint[iv, iu])[..., None]
    chips = fractal(n, 0.0, 402, sigma=1.4 * n / 4096)
    light = sm(1.6, 2.0, chips)
    dark = sm(-1.6, -2.0, chips)
    alb = mix(base, base * 1.25, 0.6 * light)
    alb = mix(alb, base * 0.55, 0.6 * dark)
    dirt = sm(0.0, 2.1, fractal(n, 1.3, 403))
    scuff = sm(1.9, 2.7, fractal(n, 0.7, 404, aniso=0.25)) + sm(2.0, 2.8, fractal(n, 0.7, 405, aniso=4.0))
    water = sm(1.2, 2.2, fractal(n, 1.6, 406))
    alb *= (1 - 0.45 * dirt)[..., None]
    alb = mix(alb, hexc("#2c2a26"), 0.5 * np.clip(scuff, 0, 1))
    alb = mix(alb, alb * hexc("#a08a60"), 0.5 * water)
    height = 0.03 * chips - 0.1 * np.clip(scuff, 0, 1) + 0.02 * fractal(n, 1.4, 407)
    rough = 0.38 + 0.35 * dirt + 0.15 * np.clip(scuff, 0, 1) + 0.1 * water
    return texture_set("Linoleum", alb, rough, height, 3.0)

def tex_deckenplatte():
    # 2048 px = 4 m x 4 m, 6 x 6 Platten mit Fissuren, Wasserflecken und Schimmel
    n = 2048 // TEXDIV
    xx, yy = coords(n)
    k = 6
    iu, iv = np.floor(xx * k).astype(int), np.floor(yy * k).astype(int)
    rng = np.random.default_rng(501)
    stained = (rng.uniform(0, 1, (k, k)) < 0.35).astype(np.float32)
    fiss = sm(0.06, 0.0, np.abs(fractal(n, 0.6, 502, sigma=0.6)))
    pores = fractal(n, 0.1, 503, sigma=0.6)
    base = hexc("#dedbd1") * (0.94 + 0.03 * pores[..., None])
    base *= (1 - 0.25 * fiss)[..., None]
    st = fractal(n, 1.4, 504)
    stain = sm(0.4, 1.4, st) * stained[iv, iu]
    tide = sm(0.3, 0.4, st) * sm(0.55, 0.45, st) * stained[iv, iu]
    alb = mix(base, base * hexc("#b08a52"), 0.7 * stain)
    alb *= (1 - 0.35 * tide)[..., None]
    mold = sm(2.1, 2.7, fractal(n, 0.3, 505, sigma=1.5)) * stained[iv, iu]
    alb = mix(alb, hexc("#3a3a2c"), 0.7 * mold)
    height = -0.4 * fiss + 0.05 * pores
    rough = 0.88 + 0.05 * stain
    return texture_set("Deckenplatte", alb, rough, height, 3.5)

def tex_beton():
    n = 2048 // TEXDIV
    agg = sm(1.0, 1.5, fractal(n, 0.3, 601, sigma=2.0))
    pores = sm(-2.2, -2.8, fractal(n, 0.05, 602, sigma=0.8))
    alb = hexc("#8f8b83") * (0.8 + 0.1 * fractal(n, 1.2, 603)[..., None])
    alb = mix(alb, hexc("#6f685e"), 0.45 * agg)
    alb *= (1 - 0.5 * pores)[..., None]
    height = 0.5 * fractal(n, 1.3, 604) + 0.35 * agg - 0.6 * pores
    rough = 0.9 + 0.05 * agg
    return texture_set("Beton", alb, rough, height, 2.5)

def tex_metall():
    # Lack mit Abplatzern, Grundierung und Rost
    n = 2048 // TEXDIV
    chip = fractal(n, 1.1, 701) + 0.5 * fractal(n, 0.6, 702)
    primer = sm(1.4, 1.48, chip)
    rust = sm(1.75, 1.85, chip + 0.4 * fractal(n, 0.8, 703))
    scratch = sm(2.2, 3.0, fractal(n, 0.6, 704, aniso=0.08)) + sm(2.3, 3.0, fractal(n, 0.6, 705, aniso=12.0))
    runs = sm(1.0, 2.4, fractal(n, 1.0, 706, aniso=6.0))
    paint = hexc("#8d978f") * (0.95 + 0.04 * fractal(n, 1.5, 707)[..., None])
    alb = mix(paint, hexc("#7c3f2a"), primer)
    alb = mix(alb, hexc("#5a3520") * (0.8 + 0.3 * fractal(n, 0.5, 708)[..., None]), rust)
    alb = mix(alb, alb * hexc("#9a6a40"), 0.35 * runs)
    alb = mix(alb, alb * 1.35, 0.5 * np.clip(scratch, 0, 1))
    height = -0.25 * primer - 0.4 * rust + 0.1 * rust * fractal(n, 0.4, 709) - 0.15 * np.clip(scratch, 0, 1)
    rough = 0.38 + 0.2 * primer + 0.45 * rust + 0.1 * runs
    return texture_set("Metall_lackiert", alb, rough, height, 3.0)

def tex_rost():
    n = 1024 // TEXDIV
    a = fractal(n, 1.0, 801)
    alb = mix(hexc("#5b3420"), hexc("#9a5a2c"), sm(-0.5, 1.5, a)) * (0.85 + 0.2 * fractal(n, 0.3, 802)[..., None])
    height = 0.6 * a + 0.3 * fractal(n, 0.3, 803)
    rough = 0.85 + 0.1 * a
    return texture_set("Rost", alb, rough, height, 2.0)

def tex_leiste():
    n = 1024 // TEXDIV
    scratch = sm(2.0, 2.8, fractal(n, 0.6, 901, aniso=0.07))
    dirt = sm(0.0, 2.0, fractal(n, 1.3, 902))
    alb = hexc("#6d7d73") * (1 - 0.35 * dirt)[..., None]
    alb = mix(alb, hexc("#c9c2b0"), 0.6 * scratch)
    height = -0.3 * scratch
    rough = 0.42 + 0.3 * dirt + 0.2 * scratch
    return texture_set("Leiste", alb, rough, height, 2.0)

# ======================= Materialien =======================
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
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    comb = nt.nodes.new("ShaderNodeCombineColor")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(b.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(r.outputs["Color"], bsdf.inputs["Roughness"])
    nt.links.new(n.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Red"], comb.inputs["Red"])
    nt.links.new(sep.outputs["Green"], inv.inputs[1])
    nt.links.new(inv.outputs[0], comb.inputs["Green"])
    nt.links.new(sep.outputs["Blue"], comb.inputs["Blue"])
    nt.links.new(comb.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m

def color_material(name, hexcol, rough=0.6, metal=0.0, emit=0.0, transmission=0.0):
    m = bpy.data.materials.new("M_" + name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    c = hexc(hexcol) ** 2.2
    b.inputs["Base Color"].default_value = (*c, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if transmission:
        b.inputs["Transmission Weight"].default_value = transmission
    if emit:
        b.inputs["Emission Color"].default_value = (1.0, 0.97, 0.9, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m

log("Texturen ...")
MAT = {
    "putz": tex_material("Putz", tex_putz()),
    "glasur": tex_material("Fliesenglasur", tex_glasur()),
    "moertel": tex_material("Moertel", tex_moertel()),
    "linoleum": tex_material("Linoleum", tex_linoleum()),
    "platte": tex_material("Deckenplatte", tex_deckenplatte()),
    "beton": tex_material("Beton", tex_beton()),
    "metall": tex_material("Metall_lackiert", tex_metall()),
    "rost": tex_material("Rost", tex_rost()),
    "leiste": tex_material("Leiste", tex_leiste()),
    "raster": color_material("Deckenraster", "#dcdad2", 0.45, 0.3),
    "glas": color_material("Glas", "#cfe0e4", 0.05, 0.0, 0.0, 1.0),
    "leuchte": color_material("Leuchte", "#f4f2ea", 0.3, 0.0, 5.0),
}
UVS = {"putz": 0.25, "glasur": 0.25, "moertel": 1.0, "linoleum": 0.25, "platte": 0.25, "beton": 1.0,
       "metall": 1.0, "rost": 2.0, "leiste": 1.0, "raster": 1.0, "glas": 1.0, "leuchte": 1.0}

# ======================= Geometrie-Hilfen =======================
def faces_of(vs):
    return {f for v in vs for f in v.link_faces}

def edges_of(vs):
    return list({e for v in vs for e in v.link_edges})

def box(bm, lo, hi, mi, bevel=0.0, segs=2, rot=None, pivot=None):
    lo, hi = Vector(lo), Vector(hi)
    vs = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.scale(bm, vec=hi - lo, verts=vs)
    if rot is not None:
        bmesh.ops.rotate(bm, cent=Vector((0, 0, 0)), matrix=rot, verts=vs)
    bmesh.ops.translate(bm, vec=(lo + hi) / 2, verts=vs)
    for f in faces_of(vs):
        f.material_index = mi
    if bevel > 0:
        res = bmesh.ops.bevel(bm, geom=edges_of(vs) + vs, offset=bevel, offset_type="OFFSET",
                              profile_type="SUPERELLIPSE", segments=segs, profile=0.5, affect="EDGES",
                              clamp_overlap=True, material=mi)
        return list({v for f in res["faces"] for v in f.verts})
    return vs

def connected(seed_verts):
    seen = set(seed_verts)
    stack = list(seed_verts)
    while stack:
        v = stack.pop()
        for e in v.link_edges:
            o = e.other_vert(v)
            if o not in seen:
                seen.add(o)
                stack.append(o)
    return list(seen)

def tube(bm, pts, r, mi, seg=8):
    rings = []
    for k, p in enumerate(pts):
        if k == 0:
            t = pts[1] - pts[0]
        elif k == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = (pts[k + 1] - pts[k]).normalized() + (pts[k] - pts[k - 1]).normalized()
        t = t.normalized()
        ref = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
        b1 = t.cross(ref).normalized()
        b2 = t.cross(b1).normalized()
        ring = [bm.verts.new(p + (b1 * math.cos(2 * math.pi * s / seg) + b2 * math.sin(2 * math.pi * s / seg)) * r)
                for s in range(seg)]
        rings.append(ring)
    for k in range(len(rings) - 1):
        for s in range(seg):
            f = bm.faces.new((rings[k][s], rings[k][(s + 1) % seg], rings[k + 1][(s + 1) % seg], rings[k + 1][s]))
            f.material_index = mi
    for ring in (rings[0][::-1], rings[-1]):
        bm.faces.new(ring).material_index = mi

def chunk(bm, center, size, mi, seed, flat=0.7):
    vs = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)["verts"]
    off = Vector((seed * 1.7, seed * 2.3, seed * 0.9))
    for v in vs:
        d = 1.0 + 0.35 * noise.noise(v.co * 1.6 + off) + 0.12 * noise.noise(v.co * 4.0 + off)
        v.co = Vector((v.co.x * d * size.x, v.co.y * d * size.y, v.co.z * d * size.z * flat))
    rot = Matrix.Rotation(random.uniform(0, math.tau), 3, "Z") @ Matrix.Rotation(random.uniform(-0.4, 0.4), 3, "X")
    bmesh.ops.rotate(bm, cent=Vector((0, 0, 0)), matrix=rot, verts=vs)
    bmesh.ops.translate(bm, vec=Vector(center), verts=vs)
    for f in faces_of(vs):
        f.material_index = mi
    return vs

def uv_project(bm, mats):
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        s = UVS[mats[f.material_index]]
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
        co.hide_render = True
        scene.collection.objects.link(co)
        cols.append(co)
    PIECES.append((ob, cols))
    log("Teil", name, len(me.polygons), "Flaechen")
    return ob

# Materialindizes fuer Waende
WM = ["putz", "moertel", "glasur", "leiste", "beton", "rost"]
I_PUTZ, I_MOERTEL, I_GLASUR, I_LEISTE, I_BETON, I_ROST = range(6)

def tile(bm, x0, x1, z0, z1, side, rng, state="ok"):
    """Eine Fliese auf der Wandseite side (-1 vorne, +1 hinten) im Rechteck x0..x1, z0..z1."""
    g = GAP / 2
    x0, x1, z0, z1 = x0 + g, x1 - g, z0 + g, z1 - g
    if x1 - x0 < 0.01 or z1 - z0 < 0.01:
        return
    y0 = side * (T / 2 + BED)
    y1 = side * (T / 2 + BED + TT)
    lo = (x0, min(y0, y1), z0)
    hi = (x1, max(y0, y1), z1)
    jitter = Vector((rng.uniform(-0.0006, 0.0006), side * rng.uniform(-0.0008, 0.0008), rng.uniform(-0.0006, 0.0006)))
    rot = Matrix.Rotation(rng.uniform(-0.004, 0.004), 3, "Y") @ Matrix.Rotation(rng.uniform(-0.006, 0.006), 3, "Z")
    if state == "crack":
        if rng.random() < 0.5:
            cut = rng.uniform(x0 + 0.3 * (x1 - x0), x0 + 0.7 * (x1 - x0))
            parts = [((x0, lo[1], z0), (cut - 0.0006, hi[1], z1)), ((cut + 0.0006, lo[1], z0), (x1, hi[1], z1))]
        else:
            cut = rng.uniform(z0 + 0.3 * (z1 - z0), z0 + 0.7 * (z1 - z0))
            parts = [((x0, lo[1], z0), (x1, hi[1], cut - 0.0006)), ((x0, lo[1], cut + 0.0006), (x1, hi[1], z1))]
        for k, (a, b) in enumerate(parts):
            r2 = rot @ Matrix.Rotation(rng.uniform(-0.012, 0.012), 3, "Y") if k else rot
            vs = box(bm, a, b, I_GLASUR, bevel=0.0012, segs=2)
            c = (Vector(a) + Vector(b)) / 2
            bmesh.ops.rotate(bm, cent=c, matrix=r2, verts=vs)
            bmesh.ops.translate(bm, vec=jitter + Vector((0, side * 0.0006 * k, 0)), verts=vs)
        return
    vs = box(bm, lo, hi, I_GLASUR, bevel=0.0015, segs=2)
    c = (Vector(lo) + Vector(hi)) / 2
    bmesh.ops.rotate(bm, cent=c, matrix=rot, verts=vs)
    bmesh.ops.translate(bm, vec=jitter, verts=vs)

def tile_area(bm, rects, side, rng, hole=None):
    """Fliesen im 20-cm-Raster auf allen Rechtecken (x0, x1, z0, z1), an Kanten zugeschnitten."""
    nx = int(math.ceil(max(r[1] for r in rects) / TILE))
    nz = int(round(SOCKEL / TILE))
    for j in range(nz):
        for i in range(nx):
            tx0, tx1, tz0, tz1 = i * TILE, (i + 1) * TILE, j * TILE, (j + 1) * TILE
            for (rx0, rx1, rz0, rz1) in rects:
                cx0, cx1, cz0, cz1 = max(tx0, rx0), min(tx1, rx1), max(tz0, rz0), min(tz1, rz1)
                if cx1 - cx0 < 0.012 or cz1 - cz0 < 0.012:
                    continue
                miss, crack = 0.035, 0.05
                if hole is not None:
                    d = hole((cx0 + cx1) / 2, (cz0 + cz1) / 2)
                    if d < 0.05:
                        continue
                    if d < 0.7:
                        miss, crack = 0.45 * (1 - d / 0.7) + 0.05, 0.3
                u = rng.random()
                if u < miss:
                    continue
                tile(bm, cx0, cx1, cz0, cz1, side, rng, "crack" if u < miss + crack else "ok")

def rail(bm, a, b, side):
    """Rammschutzleiste mit gerundetem Profil zwischen x=a und x=b."""
    hgt, dep, r = 0.075, 0.034, 0.012
    prof = [(dep - r + r * math.cos(-math.pi / 2 + math.pi / 2 * k / 4), -hgt / 2 + r + r * math.sin(-math.pi / 2 + math.pi / 2 * k / 4)) for k in range(5)] + \
           [(dep - r + r * math.cos(math.pi / 2 * k / 4), hgt / 2 - r + r * math.sin(math.pi / 2 * k / 4)) for k in range(5)]
    prof = [(0.0, -hgt / 2)] + prof + [(0.0, hgt / 2)]
    vs = [bm.verts.new((a, side * (T / 2 + d), SOCKEL + z)) for d, z in prof]
    f = bm.faces.new(vs if side > 0 else vs[::-1])
    f.material_index = I_LEISTE
    res = bmesh.ops.extrude_face_region(bm, geom=[f])
    nv = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=Vector((b - a, 0, 0)), verts=nv)
    for ff in faces_of(vs + nv):
        ff.material_index = I_LEISTE

def wall_core(bm, x0, x1, z0, z1):
    if z0 < SOCKEL:
        box(bm, (x0, -T / 2, z0), (x1, T / 2, min(z1, SOCKEL)), I_MOERTEL)
    if z1 > SOCKEL:
        box(bm, (x0, -T / 2, max(z0, SOCKEL)), (x1, T / 2, z1), I_PUTZ)

def build_wall(name, length, door=None, window=None, seed=1):
    rng = random.Random(seed)
    bm = bmesh.new()
    cuts = sorted(set([0.0, length] + ([door[0], door[1]] if door else []) + ([window[0], window[1]] if window else [])))
    rects, cols, runs = [], [], []
    for a, b in zip(cuts, cuts[1:]):
        mid = (a + b) / 2
        if door and door[0] <= mid <= door[1]:
            wall_core(bm, a, b, door[2], H)
            cols.append(((a, -FACE, door[2]), (b, FACE, H)))
        elif window and window[0] <= mid <= window[1]:
            wall_core(bm, a, b, 0.0, window[2])
            wall_core(bm, a, b, window[3], H)
            rects.append((a, b, 0.0, window[2]))
            cols.append(((a, -FACE, 0), (b, FACE, window[2])))
            cols.append(((a, -T / 2, window[3]), (b, T / 2, H)))
        else:
            wall_core(bm, a, b, 0.0, H)
            rects.append((a, b, 0.0, SOCKEL))
            cols.append(((a, -FACE, 0), (b, FACE, H)))
            if runs and abs(runs[-1][1] - a) < 1e-6:
                runs[-1][1] = b
            else:
                runs.append([a, b])
    for side in (-1, 1):
        tile_area(bm, rects, side, rng)
        for a, b in runs:
            rail(bm, a + 0.001, b - 0.001, side)
    return finish(name, bm, WM, cols)

def build_broken_wall(name, length, seed=7):
    rng = random.Random(seed)
    cell = 0.025
    nx, nz = int(round(length / cell)), int(round(H / cell))
    cx, cz, rad = 2.15, 1.3, 1.0
    def hole_r(x, z):
        ang = math.atan2(z - cz, x - cx)
        return rad * (1 + 0.3 * noise.noise(Vector((math.cos(ang) * 1.2, math.sin(ang) * 1.2, 4.2)))
                      + 0.12 * noise.noise(Vector((math.cos(ang) * 4.0, math.sin(ang) * 4.0, 7.0)))
                      + 0.05 * noise.noise(Vector((x * 20, z * 20, 1.0))))
    def hole_dist(x, z):
        return math.hypot((x - cx) * 0.85, z - cz) - hole_r(x, z)
    keep = np.ones((nz, nx), dtype=bool)
    for j in range(nz):
        for i in range(nx):
            x, z = (i + 0.5) * cell, (j + 0.5) * cell
            if hole_dist(x, z) < 0 and z > 0.12:
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
                f.material_index = I_MOERTEL if (j + 0.5) * cell < SOCKEL else I_PUTZ
    bm.normal_update()
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=T)
    ys = [vv.co.y for vv in bm.verts]
    sh = -(min(ys) + max(ys)) / 2
    for vv in bm.verts:
        vv.co.y += sh
    bm.normal_update()
    for f in bm.faces:
        n, c = f.normal, f.calc_center_median()
        if abs(n.y) > 0.9:
            continue
        if not (c.x < 0.01 or c.x > length - 0.01 or c.z < 0.01 or c.z > H - 0.01):
            f.material_index = I_BETON
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1), verts=bm.verts, edges=bm.edges, delimit={"MATERIAL", "NORMAL"})
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    rim = [vv for vv in bm.verts if any(f.material_index == I_BETON for f in vv.link_faces)
           and 0.03 < vv.co.x < length - 0.03 and 0.03 < vv.co.z < H - 0.03]
    for vv in rim:
        p = vv.co.copy()
        vv.co.x += 0.022 * noise.noise(p * 9.0)
        vv.co.z += 0.022 * noise.noise(p * 9.0 + Vector((3, 3, 3)))
        vv.co.y *= 1.0 + 0.15 * noise.noise(p * 5.0 + Vector((7, 1, 2)))
    # Betonbrocken entlang der Bruchkante
    edge_cells = [(i, j) for j in range(1, nz - 1) for i in range(1, nx - 1)
                  if keep[j, i] and not (keep[j - 1, i] and keep[j + 1, i] and keep[j, i - 1] and keep[j, i + 1])]
    rng.shuffle(edge_cells)
    for k, (i, j) in enumerate(edge_cells[:70]):
        s = rng.uniform(0.018, 0.05)
        chunk(bm, ((i + 0.5) * cell, rng.uniform(-T / 2 + s, T / 2 - s), (j + 0.5) * cell),
              Vector((s * rng.uniform(1.0, 1.8), s, s * rng.uniform(0.8, 1.5))), I_BETON, k, flat=1.0)
    # Bewehrungseisen: zwei waagerecht, eines senkrecht, teils abgerissen und verbogen
    def rebar(points):
        tube(bm, [Vector(p) for p in points], 0.006, I_ROST, seg=8)
    # abgerissene Stummel, die aus der Bruchkante ragen
    for yb in (-0.05, 0.05):
        rebar([(cx - 1.45, yb, cz + 0.35), (cx - 0.78, yb, cz + 0.36), (cx - 0.62, yb - 0.03, cz + 0.3)])
        rebar([(cx - 1.45, yb, cz - 0.4), (cx - 0.82, yb, cz - 0.41), (cx - 0.7, yb + 0.02, cz - 0.47)])
        rebar([(cx + 1.45, yb, cz + 0.35), (cx + 0.86, yb, cz + 0.34), (cx + 0.74, yb - 0.04, cz + 0.4)])
    rebar([(cx - 0.12, -0.05, cz + 1.4), (cx - 0.12, -0.05, cz + 0.72), (cx - 0.08, -0.12, cz + 0.55)])
    rebar([(cx + 0.38, 0.05, cz + 1.4), (cx + 0.38, 0.05, cz + 0.8), (cx + 0.45, 0.1, cz + 0.68)])
    rebar([(cx + 0.12, -0.05, cz - 1.25), (cx + 0.12, -0.05, cz - 0.72), (cx + 0.2, -0.1, cz - 0.6)])
    # Fliesen um das Loch herum, viele fehlen oder sind gesprungen
    rects = [(0.0, length, 0.0, SOCKEL)]
    def hd(x, z):
        return hole_dist(x, z) + 0.02
    for side in (-1, 1):
        tile_area(bm, rects, side, rng, hole=hd)
        row = int(round(SOCKEL / cell))
        i = 0
        while i < nx:
            ok = keep[row, i] and keep[row - 1, i] and hole_dist((i + 0.5) * cell, SOCKEL) > 0.08
            if ok:
                s0 = i
                while i < nx and keep[row, i] and keep[row - 1, i] and hole_dist((i + 0.5) * cell, SOCKEL) > 0.08:
                    i += 1
                rail(bm, s0 * cell + 0.002, i * cell - 0.002, side)
            i += 1
    return finish(name, bm, WM)

def build_floor(name, seed=3):
    rng = random.Random(seed)
    bm = bmesh.new()
    box(bm, (0, 0, -0.1), (4, 4, -0.004), 1)
    k, s = 10, 0.4
    for j in range(k):
        for i in range(k):
            u = rng.random()
            if u < 0.03:
                continue
            x0, y0 = i * s + 0.0006, j * s + 0.0006
            allv = box(bm, (x0, y0, -0.004), (x0 + s - 0.0012, y0 + s - 0.0012, -0.0005 + rng.uniform(-0.0003, 0.0003)), 0, bevel=0.0006, segs=1)
            if u < 0.06:
                ax = rng.choice(["X", "Y"])
                ang = rng.uniform(0.02, 0.05) * rng.choice([-1, 1])
                piv = Vector((x0 if ang > 0 else x0 + s, y0, -0.004)) if ax == "Y" else Vector((x0, y0 if ang < 0 else y0 + s, -0.004))
                bmesh.ops.rotate(bm, cent=piv, matrix=Matrix.Rotation(ang, 3, ax), verts=allv)
    return finish(name, bm, ["linoleum", "beton"], [((0, 0, -0.1), (4, 4, 0))])

def build_ceiling(name, seed=11):
    """Rasterdecke 4 x 4 m: Drehpunkt auf Hoehe der Unterkante des Rasters."""
    rng = random.Random(seed)
    bm = bmesh.new()
    M = ["platte", "raster", "beton", "metall", "rost"]
    box(bm, (0, 0, 0.55), (4, 4, 0.65), 2)
    k, p = 6, 4 / 6
    for i in range(k + 1):
        c = i * p
        box(bm, (c - 0.012, 0, 0), (c + 0.012, 4, 0.003), 1)
        box(bm, (c - 0.002, 0, 0.003), (c + 0.002, 4, 0.038), 1)
        box(bm, (0, c - 0.012, 0), (4, c + 0.012, 0.003), 1)
        box(bm, (0, c - 0.002, 0.003), (4, c + 0.002, 0.038), 1)
    states = ["ok"] * (k * k)
    idx = list(range(k * k))
    rng.shuffle(idx)
    for q in idx[:3]:
        states[q] = "fehlt"
    states[idx[3]] = "haengt"
    states[idx[4]] = "fehlt"
    for j in range(k):
        for i in range(k):
            st = states[j * k + i]
            if st == "fehlt":
                continue
            x0, y0 = i * p + 0.004, j * p + 0.004
            w = p - 0.008
            grid = bmesh.ops.create_grid(bm, x_segments=6, y_segments=6, size=w / 2)["verts"]
            sag = rng.uniform(0.003, 0.018)
            for v in grid:
                u, vv = v.co.x / (w / 2), v.co.y / (w / 2)
                v.co.z = -sag * (1 - u * u) * (1 - vv * vv)
            fs = list(faces_of(grid))
            for f in fs:
                f.material_index = 0
            bmesh.ops.solidify(bm, geom=fs, thickness=0.015)
            allv = connected(grid)
            cz = min(v.co.z for v in allv if abs(abs(v.co.x) - w / 2) < 1e-4 and abs(abs(v.co.y) - w / 2) < 1e-4)
            bmesh.ops.translate(bm, vec=Vector((x0 + w / 2, y0 + w / 2, 0.004 - cz)), verts=allv)
            if st == "haengt":
                piv = Vector((x0, y0, 0.004))
                bmesh.ops.rotate(bm, cent=piv, matrix=Matrix.Rotation(math.radians(-38), 3, "X") @ Matrix.Rotation(math.radians(6), 3, "Y"), verts=allv)
    tube(bm, [Vector((-0.02, 1.2, 0.36)), Vector((4.02, 1.2, 0.36))], 0.06, 3, seg=16)
    tube(bm, [Vector((-0.02, 1.45, 0.42)), Vector((4.02, 1.45, 0.42))], 0.035, 4, seg=12)
    tube(bm, [Vector((2.3, -0.02, 0.3)), Vector((2.3, 4.02, 0.3))], 0.025, 3, seg=10)
    return finish(name, bm, M, [((0, 0, 0), (4, 4, 0.05))])

def build_pillar(name, seed=13):
    rng = random.Random(seed)
    bm = bmesh.new()
    s = 0.3
    box(bm, (-s / 2, -s / 2, 0), (s / 2, s / 2, SOCKEL), I_MOERTEL)
    box(bm, (-s / 2, -s / 2, SOCKEL), (s / 2, s / 2, H), I_PUTZ)
    off = s / 2 + BED
    for j in range(int(round(SOCKEL / TILE))):
        z0, z1 = j * TILE + GAP / 2, (j + 1) * TILE - GAP / 2
        for a0, a1 in ((-s / 2 - BED - TT, 0.0), (0.0, s / 2 + BED + TT)):
            for sgn in (-1, 1):
                if rng.random() < 0.06:
                    continue
                box(bm, (a0 + GAP / 2, sgn * off if sgn > 0 else -off - TT, z0), (a1 - GAP / 2, sgn * off + TT if sgn > 0 else -off, z1), I_GLASUR, bevel=0.0015)
                if rng.random() < 0.06:
                    continue
                box(bm, (sgn * off if sgn > 0 else -off - TT, a0 + GAP / 2, z0), (sgn * off + TT if sgn > 0 else -off, a1 - GAP / 2, z1), I_GLASUR, bevel=0.0015)
    return finish(name, bm, WM, [((-s / 2 - 0.012, -s / 2 - 0.012, 0), (s / 2 + 0.012, s / 2 + 0.012, H))])

def build_door_frame(name):
    bm = bmesh.new()
    x0, x1, z1 = DOOR
    d, w, e = 0.15, 0.065, 0.02
    for a, b in ((x0 - w, x0 + e), (x1 - e, x1 + w)):
        box(bm, (a, -d, 0), (b, d, z1 - e), 0, bevel=0.004)
    box(bm, (x0 - w, -d, z1 - e), (x1 + w, d, z1 + w), 0, bevel=0.004)
    stop = 0.016
    box(bm, (x0 + e - 0.001, -0.02, 0), (x0 + e + stop, 0.03, z1 - e + 0.001), 0, bevel=0.002)
    box(bm, (x1 - e - stop, -0.02, 0), (x1 - e + 0.001, 0.03, z1 - e + 0.001), 0, bevel=0.002)
    box(bm, (x0 + e, -0.02, z1 - e - stop), (x1 - e, 0.03, z1 - e + 0.001), 0, bevel=0.002)
    for zh in (0.25, 1.9):
        tube(bm, [Vector((x0 + e + 0.012, -0.035, zh)), Vector((x0 + e + 0.012, -0.035, zh + 0.12))], 0.009, 1, seg=10)
    return finish(name, bm, ["metall", "rost"])

def build_window_frame(name, seed=17):
    rng = random.Random(seed)
    bm = bmesh.new()
    x0, x1, z0, z1 = WIN
    d, w, e = 0.15, 0.06, 0.02
    box(bm, (x0 - w, -d, z0 + e), (x0 + e, d, z1 - e), 0, bevel=0.004)
    box(bm, (x1 - e, -d, z0 + e), (x1 + w, d, z1 - e), 0, bevel=0.004)
    box(bm, (x0 - w, -d, z1 - e), (x1 + w, d, z1 + w), 0, bevel=0.004)
    box(bm, (x0 - w, -d - 0.06, z0 - w), (x1 + w, d, z0 + e), 0, bevel=0.004)
    mx, mz = (x0 + x1) / 2, (z0 + z1) / 2
    box(bm, (mx - 0.025, -0.03, z0), (mx + 0.025, 0.03, z1), 0, bevel=0.003)
    box(bm, (x0 + e, -0.03, mz - 0.025), (mx - 0.025, 0.03, mz + 0.025), 0, bevel=0.003)
    box(bm, (mx + 0.025, -0.03, mz - 0.025), (x1 - e, 0.03, mz + 0.025), 0, bevel=0.003)
    # Glasreste in den Ecken der vier Scheiben
    panes = [(x0 + e, mx - 0.025, z0 + e, mz - 0.025), (mx + 0.025, x1 - e, z0 + e, mz - 0.025),
             (x0 + e, mx - 0.025, mz + 0.025, z1 - e), (mx + 0.025, x1 - e, mz + 0.025, z1 - e)]
    for k, (a, b, c, dd) in enumerate(panes):
        if k == 1:
            continue
        corners = [(a, c), (b, c), (a, dd), (b, dd)]
        for (px, pz) in rng.sample(corners, 2):
            sx = 1 if px == a else -1
            sz = 1 if pz == c else -1
            l1, l2 = rng.uniform(0.08, 0.3), rng.uniform(0.08, 0.3)
            pts = [Vector((px, 0, pz)), Vector((px + sx * l1, 0, pz)), Vector((px + sx * l1 * 0.3, 0, pz + sz * l2 * 0.6)), Vector((px, 0, pz + sz * l2))]
            vs = [bm.verts.new(p + Vector((0, -0.003, 0))) for p in pts]
            f = bm.faces.new(vs)
            f.material_index = 1
            res = bmesh.ops.extrude_face_region(bm, geom=[f])
            nv = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
            bmesh.ops.translate(bm, vec=Vector((0, 0.006, 0)), verts=nv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, ["metall", "glas"])

def build_lamp(name):
    bm = bmesh.new()
    box(bm, (-0.64, -0.17, -0.1), (0.64, 0.17, 0.0), 0, bevel=0.006)
    box(bm, (-0.6, -0.13, -0.104), (0.6, 0.13, -0.098), 1)
    for yy in (-0.06, 0.06):
        tube(bm, [Vector((-0.58, yy, -0.06)), Vector((0.58, yy, -0.06))], 0.013, 2, seg=12)
    return finish(name, bm, ["metall", "leuchte", "glas"])

def build_rubble(name, seed=23):
    """Schutt vor der kaputten Wand: Betonbrocken, Fliesenscherben, Putzplatten."""
    rng = random.Random(seed)
    random.seed(seed)
    bm = bmesh.new()
    M = ["beton", "glasur", "putz"]
    for k in range(70):
        ang = rng.uniform(0.15, math.pi - 0.15)
        rr = rng.uniform(0, 1.0) ** 0.6
        x, y = math.cos(ang) * rr * 1.2, -0.12 - math.sin(ang) * rr * 0.9
        s = rng.uniform(0.02, 0.12) * (1.3 - rr * 0.7)
        chunk(bm, (x, y, s * 0.35), Vector((s * rng.uniform(0.9, 1.6), s * rng.uniform(0.8, 1.3), s)), 0, k, flat=0.6)
    for k in range(45):
        ang = rng.uniform(0.1, math.pi - 0.1)
        rr = rng.uniform(0.1, 1.0) ** 0.5
        x, y = math.cos(ang) * rr * 1.5, -0.15 - math.sin(ang) * rr * 1.1
        a, b = rng.uniform(0.03, 0.12), rng.uniform(0.03, 0.1)
        pts = [Vector((0, 0, 0)), Vector((a, rng.uniform(-0.02, 0.02), 0)), Vector((a * rng.uniform(0.4, 1.0), b, 0)), Vector((rng.uniform(-0.03, 0.03), b * rng.uniform(0.5, 1.0), 0))]
        vs = [bm.verts.new(p) for p in pts]
        f = bm.faces.new(vs)
        f.material_index = 1 if k < 32 else 2
        thick = TT if k < 32 else 0.006
        res = bmesh.ops.extrude_face_region(bm, geom=[f])
        nv = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.translate(bm, vec=Vector((0, 0, thick)), verts=nv)
        allv = vs + nv
        rot = Matrix.Rotation(rng.uniform(0, math.tau), 3, "Z") @ Matrix.Rotation(rng.uniform(-0.25, 0.25), 3, "X")
        bmesh.ops.rotate(bm, cent=Vector((0, 0, 0)), matrix=rot, verts=allv)
        bmesh.ops.translate(bm, vec=Vector((x, y, 0.002 + rng.uniform(0, 0.02))), verts=allv)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return finish(name, bm, M)

log("Modelle ...")
w4 = build_wall("SM_Wand_4m", 4.0, seed=1)
w2 = build_wall("SM_Wand_2m", 2.0, seed=2)
wd = build_wall("SM_Wand_Tuer_4m", 4.0, door=DOOR, seed=3)
ww = build_wall("SM_Wand_Fenster_4m", 4.0, window=WIN, seed=4)
wb = build_broken_wall("SM_Wand_Kaputt_4m", 4.0)
fl = build_floor("SM_Boden_4x4m")
ce = build_ceiling("SM_Decke_4x4m")
pi = build_pillar("SM_Saeule")
fd = build_door_frame("SM_Tuerrahmen")
fw = build_window_frame("SM_Fensterrahmen")
la = build_lamp("SM_Deckenlampe")
ru = build_rubble("SM_Schutt")

log("Export ...")
for ob, cols in PIECES:
    bpy.ops.object.select_all(action="DESELECT")
    for o in [ob] + cols:
        o.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.fbx(filepath=os.path.join(MESH, ob.name + ".fbx"), use_selection=True,
                             apply_scale_options="FBX_SCALE_UNITS", mesh_smooth_type="FACE", path_mode="STRIP")
for ob, cols in PIECES:
    for c in cols:
        bpy.data.objects.remove(c, do_unlink=True)
    ob.hide_render = True
    ob.hide_viewport = True

def put(src, loc, rz=0.0):
    o = bpy.data.objects.new(src.name, src.data)
    o.location = loc
    o.rotation_euler = (0, 0, rz)
    scene.collection.objects.link(o)
    return o

# ======================= Szene: Flur =======================
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
        put(ru, (x + 2.15, T / 2 + 0.03, 0), rz=math.pi)
    put(right[i], (x + 4.0, 4.0, 0), rz=math.pi)
    if right[i] is ww:
        put(fw, (x + 4.0, 4.0, 0), rz=math.pi)
    if right[i] is wd:
        put(fd, (x + 4.0, 4.0, 0), rz=math.pi)
put(wd, (20.0, 0, 0), rz=math.pi / 2)
put(fd, (20.0, 0, 0), rz=math.pi / 2)
# Raeume hinter der linken Flurwand und hinter der Tuer am Ende
for i in range(5):
    x = i * 4.0
    put(fl, (x, -4.0, 0))
    put(ce, (x, -4.0, H))
    put(w4, (x, -4.0, 0))
for x in (0.0, 4.0, 8.0, 12.0, 16.0, 20.0):
    put(w4, (x, -4.0, 0), rz=math.pi / 2)
put(fl, (20.0, 0, 0))
put(ce, (20.0, 0, H))
put(w4, (24.0, 0, 0), rz=math.pi / 2)
put(w4, (20.0, 0, 0))
put(w4, (24.0, 4.0, 0), rz=math.pi)
for x in (0, 20):
    for y in (0, 4):
        put(pi, (x, y, 0))
l1 = put(la, (10.0, 2.0, H))
l2 = put(la, (15.0, 2.0, H - 0.4))
l2.rotation_euler = (math.radians(16), math.radians(-10), 0.25)

def area_light(name, loc, size, energy):
    d = bpy.data.lights.new(name, "AREA")
    d.shape = "RECTANGLE"
    d.size, d.size_y = size
    d.energy = energy
    d.color = (1.0, 0.95, 0.85)
    o = bpy.data.objects.new(name, d)
    o.location = loc
    scene.collection.objects.link(o)
    return o

area_light("Lampe", (10.0, 2.0, H - 0.115), (1.15, 0.24), 110)
spot_d = bpy.data.lights.new("Taschenlampe", "SPOT")
spot_d.energy = 900
spot_d.spot_size = math.radians(40)
spot_d.spot_blend = 0.65
spot_d.color = (0.85, 0.92, 1.0)
spot_d.shadow_soft_size = 0.02
spot = bpy.data.objects.new("Taschenlampe", spot_d)
scene.collection.objects.link(spot)
sun_d = bpy.data.lights.new("Sonne", "SUN")
sun_d.energy = 28.0
sun_d.angle = math.radians(0.8)
sun_d.color = (1.0, 0.86, 0.66)
sun = bpy.data.objects.new("Sonne", sun_d)
sun.rotation_euler = (math.radians(62), 0, math.radians(195))
scene.collection.objects.link(sun)
world = bpy.data.worlds.new("Welt")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.06, 0.08, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6

bpy.ops.mesh.primitive_cube_add(size=1, location=(10, 2, H / 2))
fog = bpy.context.active_object
fog.name = "Staub"
fog.scale = (22, 4.3, H)
fm = bpy.data.materials.new("M_Staub")
fm.use_nodes = True
fnt = fm.node_tree
fnt.nodes.remove(fnt.nodes["Principled BSDF"])
vol = fnt.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Density"].default_value = 0.03
fnt.links.new(vol.outputs["Volume"], fnt.nodes["Material Output"].inputs["Volume"])
fog.data.materials.append(fm)

cam_d = bpy.data.cameras.new("Kamera")
cam = bpy.data.objects.new("Kamera", cam_d)
scene.collection.objects.link(cam)
scene.camera = cam

def aim(ob, target):
    ob.rotation_euler = (Vector(target) - ob.location).to_track_quat("-Z", "Y").to_euler()

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

BLEND = os.path.join(KIT, "ABANDONED_Wandbaukasten_HD.blend")
cam_d.lens = 18
cam.location = (0.9, 2.3, 1.62)
aim(cam, (12.0, 1.6, 1.25))
spot.location = cam.location + Vector((0.15, -0.25, -0.2))
aim(spot, (7.0, 1.2, 0.9))
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_as_mainfile(filepath=BLEND)

if "flur" in SHOTS:
    log("Render Flur ...")
    scene.render.filepath = os.path.join(OUT, "hd_flur.png")
    bpy.ops.render.render(write_still=True)

if "nah" in SHOTS:
    log("Render Nahaufnahme ...")
    fog.hide_render = True
    cam_d.lens = 26
    cam.location = (8.55, 2.0, 1.3)
    aim(cam, (10.25, 0.0, 1.0))
    spot.location = cam.location + Vector((0.1, -0.05, 0.25))
    spot_d.energy = 600
    aim(spot, (10.1, -0.4, 1.0))
    scene.render.filepath = os.path.join(OUT, "hd_nah.png")
    bpy.ops.render.render(write_still=True)

if "decke" in SHOTS:
    log("Render Decke ...")
    fog.hide_render = True
    cam_d.lens = 22
    cam.location = (5.0, 2.0, 1.5)
    aim(cam, (9.0, 2.6, 3.2))
    scene.render.filepath = os.path.join(OUT, "hd_decke.png")
    bpy.ops.render.render(write_still=True)

info = {ob.name: sum(len(p.vertices) - 2 for p in ob.data.polygons) for ob, _ in PIECES}
log("Dreiecke je Teil:", info)
log("fertig")
