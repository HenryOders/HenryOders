# ABANDONED · Wand-Baukasten HD fuer Unreal Engine 5 (Nanite)
# Alles wird hier erzeugt: echte Fliesen mit Fasen und Fugen, Rasterdecke mit Platten,
# Linoleum-Boden aus einzelnen Platten, kaputte Wand mit Bewehrung, 4K-Texturen.
# Laeuft mit Blender 4.x (Scripting-Tab) oder headless mit dem bpy-Modul.
import bpy, bmesh, math, random, os, time
import numpy as np
import addon_utils
from mathutils import Vector, Matrix, noise, geometry

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
DDOOR = (1.1, 2.9, 2.3)                      # Doppeltuer
FLOOR2 = 3.85                                # Geschosshoehe fuer die Treppe

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

def tex_terrazzo():
    n = 2048 // TEXDIV
    c1 = fractal(n, 0.0, 1001, sigma=2.2 * n / 2048)
    c2 = fractal(n, 0.0, 1002, sigma=1.2 * n / 2048)
    base = hexc("#b9b3a7") * (0.95 + 0.04 * fractal(n, 1.2, 1003)[..., None])
    alb = mix(base, hexc("#6c6860"), sm(1.3, 1.6, c1))
    alb = mix(alb, hexc("#ebe5d7"), sm(1.4, 1.7, c2))
    alb = mix(alb, hexc("#8a5a40"), sm(1.9, 2.2, -c1))
    dirt = sm(0.2, 2.0, fractal(n, 1.3, 1004))
    alb *= (1 - 0.35 * dirt)[..., None]
    height = 0.05 * c1 + 0.02 * fractal(n, 1.0, 1005)
    rough = 0.32 + 0.3 * dirt
    return texture_set("Terrazzo", alb, rough, height, 2.0)

def tex_matratze():
    # Kunstleder-Bezug mit Flecken und Rissen
    n = 2048 // TEXDIV
    grain = fractal(n, 0.2, 1102, sigma=0.7)
    st = fractal(n, 1.5, 1103)
    stain = sm(0.8, 1.8, st)
    tide = sm(0.7, 0.78, st) * (1 - stain)
    crack = sm(0.04, 0.0, np.abs(fractal(n, 0.9, 1104))) * sm(0.5, 1.3, fractal(n, 1.3, 1105))
    alb = hexc("#5f7f86") * (0.93 + 0.05 * fractal(n, 1.0, 1101)[..., None] + 0.03 * grain[..., None])
    alb = mix(alb, alb * hexc("#a07a48") * 1.3, 0.6 * stain)
    alb *= (1 - 0.3 * tide - 0.5 * crack)[..., None]
    height = 0.05 * grain - 0.4 * crack
    rough = 0.45 + 0.2 * stain + 0.2 * crack
    return texture_set("Matratze", alb, rough, height, 2.5)

def tex_vorhang():
    n = 2048 // TEXDIV
    xx, yy = coords(n)
    weave = 0.5 + 0.25 * np.sin(xx * 2 * np.pi * 400) + 0.25 * np.sin(yy * 2 * np.pi * 400)
    stain = sm(0.9, 1.9, fractal(n, 1.4, 1202))
    mold = sm(2.2, 2.8, fractal(n, 0.3, 1203, sigma=1.5)) * sm(0.4, 1.2, fractal(n, 1.2, 1204))
    alb = hexc("#9fb8a8") * (0.92 + 0.06 * fractal(n, 1.2, 1201)[..., None]) * (0.92 + 0.08 * weave)[..., None]
    alb = mix(alb, alb * hexc("#9a7a50") * 1.3, 0.6 * stain)
    alb = mix(alb, hexc("#2f3326"), 0.7 * mold)
    return texture_set("Vorhang", alb, 0.86 + 0.0 * weave, 0.3 * weave, 1.0)

def tex_tuerlack():
    n = 2048 // TEXDIV
    chip = fractal(n, 1.1, 1301) + 0.5 * fractal(n, 0.6, 1302)
    under = sm(1.5, 1.58, chip)
    scratch = np.clip(sm(2.1, 2.9, fractal(n, 0.6, 1303, aniso=0.07)) + sm(2.2, 3.0, fractal(n, 0.6, 1304, aniso=10.0)), 0, 1)
    dirt = sm(0.0, 2.0, fractal(n, 1.3, 1305))
    hand = sm(1.6, 2.6, fractal(n, 1.6, 1306))
    paint = hexc("#c9c3ab") * (0.95 + 0.04 * fractal(n, 1.4, 1307)[..., None])
    alb = mix(paint, hexc("#8a7a60"), under)
    alb *= (1 - 0.3 * dirt - 0.25 * hand)[..., None]
    alb = mix(alb, hexc("#5d564a"), 0.5 * scratch)
    height = -0.3 * under - 0.2 * scratch
    rough = 0.45 + 0.25 * dirt + 0.2 * under
    return texture_set("Tuerlack", alb, rough, height, 2.5)

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
    "terrazzo": tex_material("Terrazzo", tex_terrazzo()),
    "matratze": tex_material("Matratze", tex_matratze()),
    "vorhang": tex_material("Vorhang", tex_vorhang()),
    "tuerlack": tex_material("Tuerlack", tex_tuerlack()),
    "kunststoff": color_material("Kunststoff", "#d6cfbc", 0.5),
    "edelstahl": color_material("Edelstahl", "#c4c5c1", 0.32, 1.0),
    "gummi": color_material("Gummi", "#232323", 0.85),
    "beutel": color_material("Infusionsbeutel", "#e6eef0", 0.2, 0.0, 0.0, 0.85),
}
UVS = {"putz": 0.25, "glasur": 0.25, "moertel": 1.0, "linoleum": 0.25, "platte": 0.25, "beton": 1.0,
       "metall": 1.0, "rost": 2.0, "leiste": 1.0, "raster": 1.0, "glas": 1.0, "leuchte": 1.0,
       "terrazzo": 1.0, "matratze": 1.0, "vorhang": 1.0, "tuerlack": 1.0, "kunststoff": 1.0,
       "edelstahl": 1.0, "gummi": 1.0, "beutel": 1.0}

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
def finish(name, bm, mats, colliders=(), export=True):
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
    if export:
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
    """Wand mit ausgebrochenem Loch. Der Umriss ist ein Polygon mit 240 Punkten, die Bruchflaeche wird
    in der Wanddicke unterteilt und verformt, Brocken und Bewehrungseisen sitzen an der Kante."""
    rng = random.Random(seed)
    random.seed(seed)
    cx, cz, rad = 2.15, 1.3, 0.95
    def hole_r(ang):
        c, s_ = math.cos(ang), math.sin(ang)
        return rad * (1 + 0.3 * noise.noise(Vector((c * 1.2, s_ * 1.2, 4.2)))
                      + 0.12 * noise.noise(Vector((c * 4.0, s_ * 4.0, 7.0)))
                      + 0.045 * noise.noise(Vector((c * 14.0, s_ * 14.0, 2.0)))
                      + 0.02 * noise.noise(Vector((c * 40.0, s_ * 40.0, 5.0))))
    def hole_dist(x, z):
        return math.hypot((x - cx) * 0.85, z - cz) - hole_r(math.atan2(z - cz, (x - cx) * 0.85))
    N = 240
    inner = []
    for k in range(N):
        ang = 2 * math.pi * k / N
        r = hole_r(ang)
        z = max(cz + math.sin(ang) * r, 0.12 + 0.012 * noise.noise(Vector((k * 0.37, 1.3, 2.1))))
        inner.append(Vector((cx + math.cos(ang) * r / 0.85, 0.0, z)))
    outer = [Vector((0, 0, 0)), Vector((length, 0, 0)), Vector((length, 0, H)), Vector((0, 0, H))]
    tris = geometry.tessellate_polygon([outer, inner])
    pts = outer + inner
    bm = bmesh.new()
    vs = [bm.verts.new((p.x, -T / 2, p.z)) for p in pts]
    for (a, b, c) in tris:
        try:
            bm.faces.new((vs[a], vs[b], vs[c]))
        except ValueError:
            pass
    bm.normal_update()
    for f in bm.faces:
        if f.normal.y > 0:
            f.normal_flip()
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6,
                           plane_co=Vector((0, 0, SOCKEL)), plane_no=Vector((0, 0, 1)))
    for f in bm.faces:
        f.material_index = I_MOERTEL if f.calc_center_median().z < SOCKEL else I_PUTZ
    bm.normal_update()
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=T)
    ys = [vv.co.y for vv in bm.verts]
    sh = -(min(ys) + max(ys)) / 2
    for vv in bm.verts:
        vv.co.y += sh
    bm.normal_update()
    def outer_face(c):
        return c.x < 0.01 or c.x > length - 0.01 or c.z < 0.01 or c.z > H - 0.01
    for f in bm.faces:
        if abs(f.normal.y) < 0.9 and not outer_face(f.calc_center_median()):
            f.material_index = I_BETON
    # Bruchflaeche in der Dicke unterteilen und verformen
    rim_faces = [f for f in bm.faces if f.material_index == I_BETON]
    span = list({e for f in rim_faces for e in f.edges if abs(e.verts[0].co.y - e.verts[1].co.y) > T * 0.8})
    bmesh.ops.subdivide_edges(bm, edges=span, cuts=3, use_grid_fill=True)
    rim_v = {v for f in bm.faces if f.material_index == I_BETON for v in f.verts}
    for v in rim_v:
        if v.co.x < 0.02 or v.co.x > length - 0.02 or v.co.z < 0.02 or v.co.z > H - 0.02:
            continue
        ux, uz = v.co.x - cx, v.co.z - cz
        l = math.hypot(ux, uz) or 1.0
        ux, uz = ux / l, uz / l
        mid = abs(v.co.y) < T / 2 - 0.005
        d = (0.05 if mid else 0.018) * noise.noise(v.co * 9.0) + (0.02 if mid else 0.006) * noise.noise(v.co * 27.0)
        if mid:
            d += 0.025
        v.co.x += ux * d
        v.co.z += uz * d
    # Betonbrocken entlang der Kante
    for k in range(0, N, 3):
        p = inner[k]
        s_ = rng.uniform(0.016, 0.05)
        chunk(bm, (p.x, rng.uniform(-T / 2 + s_, T / 2 - s_), p.z),
              Vector((s_ * rng.uniform(1.0, 1.8), s_, s_ * rng.uniform(0.8, 1.5))), I_BETON, k, flat=1.0)
    # abgerissene Bewehrungseisen
    def rebar(points):
        tube(bm, [Vector(q) for q in points], 0.006, I_ROST, seg=8)
    for yb in (-0.05, 0.05):
        rebar([(cx - 1.45, yb, cz + 0.35), (cx - 0.78, yb, cz + 0.36), (cx - 0.62, yb - 0.03, cz + 0.3)])
        rebar([(cx - 1.45, yb, cz - 0.4), (cx - 0.82, yb, cz - 0.41), (cx - 0.7, yb + 0.02, cz - 0.47)])
        rebar([(cx + 1.45, yb, cz + 0.35), (cx + 0.86, yb, cz + 0.34), (cx + 0.74, yb - 0.04, cz + 0.4)])
    rebar([(cx - 0.12, -0.05, cz + 1.4), (cx - 0.12, -0.05, cz + 0.72), (cx - 0.08, -0.12, cz + 0.55)])
    rebar([(cx + 0.38, 0.05, cz + 1.4), (cx + 0.38, 0.05, cz + 0.8), (cx + 0.45, 0.1, cz + 0.68)])
    rebar([(cx + 0.12, -0.05, cz - 1.25), (cx + 0.12, -0.05, cz - 0.72), (cx + 0.2, -0.1, cz - 0.6)])
    # Fliesen und Leiste
    rects = [(0.0, length, 0.0, SOCKEL)]
    def hd(x, z):
        return hole_dist(x, z) + 0.02
    runs, cur = [], None
    steps = int(round(length / 0.01))
    for i in range(steps + 1):
        x = i * 0.01
        ok = all(hole_dist(x, SOCKEL + dz) > 0.07 for dz in (-0.04, 0.0, 0.04))
        if ok and cur is None:
            cur = x
        if (not ok or i == steps) and cur is not None:
            if x - cur > 0.05:
                runs.append((cur, x))
            cur = None
    for side in (-1, 1):
        tile_area(bm, rects, side, rng, hole=hd)
        for a, b in runs:
            rail(bm, a + 0.002, b - 0.002, side)
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

def build_door_frame(name, x0=DOOR[0], x1=DOOR[1], z1=DOOR[2], hinges="links"):
    bm = bmesh.new()
    d, w, e = 0.15, 0.065, 0.02
    for a, b in ((x0 - w, x0 + e), (x1 - e, x1 + w)):
        box(bm, (a, -d, 0), (b, d, z1 - e), 0, bevel=0.004)
    box(bm, (x0 - w, -d, z1 - e), (x1 + w, d, z1 + w), 0, bevel=0.004)
    stop = 0.016
    box(bm, (x0 + e - 0.001, -0.02, 0), (x0 + e + stop, 0.03, z1 - e + 0.001), 0, bevel=0.002)
    box(bm, (x1 - e - stop, -0.02, 0), (x1 - e + 0.001, 0.03, z1 - e + 0.001), 0, bevel=0.002)
    box(bm, (x0 + e, -0.02, z1 - e - stop), (x1 - e, 0.03, z1 - e + 0.001), 0, bevel=0.002)
    posts = [x0 + e + 0.012] + ([x1 - e - 0.012] if hinges == "beide" else [])
    for hx in posts:
        for zh in (0.25, 1.9):
            tube(bm, [Vector((hx, -0.035, zh)), Vector((hx, -0.035, zh + 0.12))], 0.009, 1, seg=10)
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

def hexa(bm, v8, mi):
    """Quader aus 8 Punkten: unten 0-3, oben 4-7 (jeweils gegen den Uhrzeigersinn)."""
    vs = [bm.verts.new(p) for p in v8]
    for idx in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        bm.faces.new([vs[i] for i in idx]).material_index = mi
    return vs

def build_door_leaf(name, width, height, seed=51):
    """Tuerblatt mit Sichtfenster. Drehpunkt unten an der Bandseite (x=0), Blatt laeuft in +x, Dicke 0 bis -4,5 cm in y."""
    bm = bmesh.new()
    t = 0.045
    wx0, wx1, wz0, wz1 = width * 0.3, width * 0.7, 1.2, 1.85
    outer = [Vector((0, 0, 0)), Vector((width, 0, 0)), Vector((width, 0, height)), Vector((0, 0, height))]
    win = [Vector((wx0, 0, wz0)), Vector((wx1, 0, wz0)), Vector((wx1, 0, wz1)), Vector((wx0, 0, wz1))]
    tris = geometry.tessellate_polygon([outer, win])
    vs = [bm.verts.new(p) for p in outer + win]
    for (a, b, c) in tris:
        bm.faces.new((vs[a], vs[b], vs[c])).material_index = 0
    bm.normal_update()
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=t)
    ys = [v.co.y for v in bm.verts]
    for v in bm.verts:
        v.co.y -= max(ys)
    bw = 0.025
    for y0, y1 in ((-t - 0.012, -t + 0.002), (-0.002, 0.012)):
        box(bm, (wx0 - bw, y0, wz0 - bw), (wx1 + bw, y1, wz0), 1, bevel=0.002)
        box(bm, (wx0 - bw, y0, wz1), (wx1 + bw, y1, wz1 + bw), 1, bevel=0.002)
        box(bm, (wx0 - bw, y0, wz0), (wx0, y1, wz1), 1, bevel=0.002)
        box(bm, (wx1, y0, wz0), (wx1 + bw, y1, wz1), 1, bevel=0.002)
    box(bm, (wx0, -t / 2 - 0.003, wz0), (wx1, -t / 2 + 0.003, wz1), 2)
    for y0, y1 in ((-t - 0.0015, -t + 0.0005), (-0.0005, 0.0015)):
        box(bm, (0.03, y0, 0.02), (width - 0.03, y1, 0.3), 1)
    box(bm, (width - 0.22, -t - 0.0015, 1.0), (width - 0.08, -t + 0.0005, 1.35), 1)
    for sgn, yf in ((-1, -t), (1, 0.0)):
        hx = width - 0.07
        tube(bm, [Vector((hx, yf, 1.05)), Vector((hx, yf + sgn * 0.055, 1.05))], 0.01, 1, seg=10)
        tube(bm, [Vector((hx, yf + sgn * 0.05, 1.05)), Vector((hx - 0.13, yf + sgn * 0.058, 1.05))], 0.009, 1, seg=10)
        tube(bm, [Vector((hx, yf, 1.05)), Vector((hx, yf + sgn * 0.008, 1.05))], 0.028, 1, seg=16)
    return finish(name, bm, ["tuerlack", "edelstahl", "glas", "rost"], [((0, -t, 0), (width, 0, height))])

def build_stairs(name):
    """Podesttreppe ueber ein Geschoss (3,85 m) auf 8 x 4 m. Drehpunkt in der Ecke unten.
    Lauf 1 steigt in +x, Podest bei halber Hoehe, Lauf 2 fuehrt zurueck auf die obere Platte."""
    bm = bmesh.new()
    M = ["terrazzo", "beton", "metall", "edelstahl"]
    R = FLOOR2 / 22
    land = 11 * R
    y0, y1, y2, y3 = 0.15, 1.95, 2.05, 3.85
    def nosing(xf, top, ya, yb, direction):
        a, b = (xf - 0.005, xf + 0.035) if direction > 0 else (xf - 0.035, xf + 0.005)
        box(bm, (a, ya + 0.02, top - 0.008), (b, yb - 0.02, top + 0.002), 3)
    for k in range(10):
        xa = 1.5 + k * 0.3
        top = (k + 1) * R
        box(bm, (xa, y0, 0), (xa + 0.32, y1, top), 0)
        nosing(xa, top, y0, y1, 1)
    box(bm, (4.5, y0, 0), (8.0, y3, land), 0)
    nosing(4.5, land, y0, y1, 1)
    for k in range(10):
        xb = 4.5 - (k + 1) * 0.3
        top = land + (k + 1) * R
        box(bm, (xb - 0.02, y2, land + k * R - 0.06), (xb + 0.3, y3, top), 0)
        nosing(xb + 0.3, top, y2, y3, -1)
    def line(x):
        return land + (4.5 - x) / 0.3 * R - 0.04
    pts = []
    for zoff in (0.0, -0.2):
        for (x, y) in ((4.5, y2), (1.5, y2), (1.5, y3), (4.5, y3)):
            pts.append((x, y, line(x) + zoff))
    hexa(bm, pts[4:] + pts[:4], 1)
    box(bm, (0, 0, FLOOR2 - 0.25), (1.5, 4.0, FLOOR2), 0)
    nosing(1.5, FLOOR2, y2, y3, -1)
    # Gelaender zwischen den Laeufen und an der oberen Kante
    def zn1(x):
        return R + (x - 1.5) / 0.3 * R
    def zn2(x):
        return land + R + (4.5 - x) / 0.3 * R
    rail_pts = [(1.5, 1.91, zn1(1.5) + 0.9), (4.5, 1.91, land + 0.9), (4.62, 1.91, land + 0.9), (4.62, 2.09, land + 0.9),
                (4.5, 2.09, zn2(4.5) + 0.9), (1.5, 2.09, FLOOR2 + 0.9), (1.45, 2.0, FLOOR2 + 1.0), (1.45, 0.05, FLOOR2 + 1.0)]
    tube(bm, [Vector(q) for q in rail_pts], 0.022, 2, seg=12)
    tube(bm, [Vector((1.5, 1.91, zn1(1.5) + 0.45)), Vector((4.5, 1.91, land + 0.45))], 0.012, 2, seg=8)
    tube(bm, [Vector((4.5, 2.09, zn2(4.5) + 0.45)), Vector((1.5, 2.09, FLOOR2 + 0.45))], 0.012, 2, seg=8)
    tube(bm, [Vector((1.45, 2.0, FLOOR2 + 0.5)), Vector((1.45, 0.05, FLOOR2 + 0.5))], 0.012, 2, seg=8)
    for x in (1.65, 2.55, 3.45, 4.35):
        k = int((x - 1.5) / 0.3)
        tube(bm, [Vector((x, 1.91, (k + 1) * R)), Vector((x, 1.91, zn1(x) + 0.9))], 0.014, 2, seg=8)
        k2 = int((4.5 - x) / 0.3)
        tube(bm, [Vector((x, 2.09, land + (k2 + 1) * R)), Vector((x, 2.09, zn2(x) + 0.9))], 0.014, 2, seg=8)
    tube(bm, [Vector((4.62, 2.0, land)), Vector((4.62, 2.0, land + 0.9))], 0.016, 2, seg=8)
    for y in (1.6, 0.9, 0.2):
        tube(bm, [Vector((1.45, y, FLOOR2)), Vector((1.45, y, FLOOR2 + 1.0))], 0.014, 2, seg=8)
    # Handlaeufe an den Waenden
    for yw, yr, z_of in ((y0 - 0.05, y0 + 0.06, zn1), (y3 + 0.05, y3 - 0.06, None)):
        if z_of is zn1:
            a, b = (1.4, zn1(1.4) + 0.9), (4.6, land + 0.9)
        else:
            a, b = (4.6, zn2(4.6) + 0.9), (1.4, FLOOR2 + 0.9)
        tube(bm, [Vector((a[0], yr, a[1])), Vector((b[0], yr, b[1]))], 0.02, 2, seg=10)
        for t_ in (0.12, 0.5, 0.88):
            x = a[0] + (b[0] - a[0]) * t_
            z = a[1] + (b[1] - a[1]) * t_
            tube(bm, [Vector((x, yw, z - 0.06)), Vector((x, yr, z - 0.06)), Vector((x, yr, z - 0.02))], 0.008, 2, seg=6)
    return finish(name, bm, M, [((4.5, y0, 0), (8.0, y3, land)), ((0, 0, FLOOR2 - 0.25), (1.5, 4.0, FLOOR2))])

def build_bed(name, seed=31):
    """Krankenbett, Drehpunkt unten am Kopfende (Mitte), Bett laeuft 2,1 m in +x."""
    bm = bmesh.new()
    M = ["metall", "kunststoff", "matratze", "gummi", "edelstahl"]
    L, W, zf = 2.1, 1.0, 0.45
    for y in (-W / 2 + 0.03, W / 2 - 0.03):
        box(bm, (0.04, y - 0.025, zf - 0.06), (L - 0.04, y + 0.025, zf), 0, bevel=0.006)
    for x in (0.1, L * 0.5, L - 0.1):
        box(bm, (x - 0.025, -W / 2 + 0.055, zf - 0.05), (x + 0.025, W / 2 - 0.055, zf - 0.01), 0, bevel=0.005)
    box(bm, (0.08, -W / 2 + 0.06, zf - 0.012), (L - 0.08, W / 2 - 0.06, zf), 4, bevel=0.003)
    for x in (0.12, L - 0.12):
        for y in (-W / 2 + 0.07, W / 2 - 0.07):
            tube(bm, [Vector((x, y, 0.15)), Vector((x, y, zf - 0.05))], 0.022, 0, seg=12)
            box(bm, (x - 0.03, y - 0.028, 0.09), (x + 0.03, y + 0.028, 0.16), 0, bevel=0.006)
            tube(bm, [Vector((x, y - 0.02, 0.06)), Vector((x, y + 0.02, 0.06))], 0.06, 3, seg=18)
    for x0, top in ((0.0, 1.0), (L - 0.05, 0.86)):
        for y in (-W / 2 + 0.02, W / 2 - 0.06):
            box(bm, (x0, y, zf - 0.06), (x0 + 0.05, y + 0.04, top), 0, bevel=0.012)
        box(bm, (x0 - 0.005, -W / 2 + 0.02, top - 0.05), (x0 + 0.055, W / 2 - 0.02, top), 0, bevel=0.015)
        box(bm, (x0 + 0.01, -W / 2 + 0.06, zf + 0.06), (x0 + 0.04, W / 2 - 0.06, top - 0.06), 1, bevel=0.008)
    mv = box(bm, (0.1, -W / 2 + 0.07, zf), (L - 0.1, W / 2 - 0.07, zf + 0.15), 2, bevel=0.04, segs=4)
    pv = box(bm, (0.14, -0.32, zf + 0.13), (0.52, 0.32, zf + 0.24), 2, bevel=0.045, segs=4)
    for v in pv:
        v.co.z += 0.012 * noise.noise(v.co * 8.0)
    for f in faces_of(mv + pv):
        f.smooth = True
    for (y, up) in ((-W / 2 + 0.005, True), (W / 2 - 0.005, False)):
        zt = zf + 0.4 if up else zf + 0.06
        for zz in (zt, zt - 0.14):
            tube(bm, [Vector((0.55, y, zz)), Vector((1.55, y, zz))], 0.011, 4, seg=10)
        for xx in (0.6, 1.5):
            tube(bm, [Vector((xx, y, zf - 0.03)), Vector((xx, y, zt))], 0.011, 4, seg=10)
    return finish(name, bm, M, [((0, -W / 2, 0), (L, W / 2, zf + 0.16))])

def build_nightstand(name):
    """Nachttisch, Drehpunkt unten in der Mitte, Vorderseite zeigt nach -y."""
    bm = bmesh.new()
    M = ["kunststoff", "edelstahl", "gummi"]
    w, d, h = 0.5, 0.45, 0.8
    box(bm, (-w / 2, -d / 2, 0.08), (w / 2, d / 2, h - 0.03), 0, bevel=0.01)
    box(bm, (-w / 2 - 0.02, -d / 2 - 0.02, h - 0.03), (w / 2 + 0.02, d / 2 + 0.01, h), 0, bevel=0.008)
    box(bm, (-w / 2 + 0.02, -d / 2 - 0.012, h - 0.21), (w / 2 - 0.02, -d / 2 + 0.002, h - 0.06), 0, bevel=0.004)
    box(bm, (-w / 2 + 0.02, -d / 2 - 0.012, 0.11), (w / 2 - 0.02, -d / 2 + 0.002, h - 0.23), 0, bevel=0.004)
    tube(bm, [Vector((-0.08, -d / 2 - 0.012, h - 0.135)), Vector((-0.08, -d / 2 - 0.035, h - 0.135)),
              Vector((0.08, -d / 2 - 0.035, h - 0.135)), Vector((0.08, -d / 2 - 0.012, h - 0.135))], 0.006, 1, seg=8)
    tube(bm, [Vector((w / 2 - 0.06, -d / 2 - 0.012, 0.35)), Vector((w / 2 - 0.06, -d / 2 - 0.035, 0.35)),
              Vector((w / 2 - 0.06, -d / 2 - 0.035, 0.5)), Vector((w / 2 - 0.06, -d / 2 - 0.012, 0.5))], 0.006, 1, seg=8)
    for x in (-w / 2 + 0.05, w / 2 - 0.05):
        for y in (-d / 2 + 0.05, d / 2 - 0.05):
            tube(bm, [Vector((x - 0.015, y, 0.035)), Vector((x + 0.015, y, 0.035))], 0.035, 2, seg=14)
            tube(bm, [Vector((x, y, 0.06)), Vector((x, y, 0.085))], 0.012, 1, seg=8)
    return finish(name, bm, M, [((-w / 2, -d / 2, 0), (w / 2, d / 2, h))])

def build_iv(name):
    """Infusionsstaender mit Beutel, Drehpunkt unten in der Mitte."""
    bm = bmesh.new()
    M = ["edelstahl", "gummi", "beutel"]
    tube(bm, [Vector((0, 0, 0.1)), Vector((0, 0, 1.95))], 0.013, 0, seg=12)
    tube(bm, [Vector((0, 0, 0.07)), Vector((0, 0, 0.14))], 0.032, 0, seg=14)
    for k in range(5):
        a = 2 * math.pi * k / 5
        p = Vector((math.cos(a) * 0.3, math.sin(a) * 0.3, 0.08))
        tube(bm, [Vector((0, 0, 0.1)), p], 0.012, 0, seg=8)
        tube(bm, [p, p + Vector((0, 0, -0.03))], 0.006, 0, seg=6)
        side = Vector((-math.sin(a), math.cos(a), 0)) * 0.012
        tube(bm, [p + Vector((0, 0, -0.05)) - side, p + Vector((0, 0, -0.05)) + side], 0.028, 1, seg=12)
    d0 = None
    for k in range(4):
        a = math.pi / 2 * k + math.pi / 4
        d = Vector((math.cos(a), math.sin(a), 0))
        d0 = d0 or d
        tube(bm, [Vector((0, 0, 1.93)), d * 0.1 + Vector((0, 0, 1.93)), d * 0.12 + Vector((0, 0, 1.97))], 0.006, 0, seg=6)
    c = d0 * 0.115
    bv = box(bm, (c.x - 0.06, c.y - 0.018, 1.62), (c.x + 0.06, c.y + 0.018, 1.88), 2, bevel=0.015, segs=3)
    for f in faces_of(bv):
        f.smooth = True
    tube(bm, [c + Vector((0, 0, 1.62)), c + Vector((0.03, 0.02, 1.4)), c + Vector((0.1, 0.06, 1.05)), c + Vector((0.2, 0.1, 0.85))], 0.0025, 2, seg=6)
    return finish(name, bm, M)

def build_curtain(name, seed=41):
    """Vorhang an einer Deckenschiene. Drehpunkt am Schienenanfang, Schiene laeuft 2,4 m in +x, Vorhang haengt nach unten."""
    bm = bmesh.new()
    M = ["vorhang", "edelstahl"]
    tube(bm, [Vector((0, 0, -0.03)), Vector((2.4, 0, -0.03))], 0.012, 1, seg=10)
    for x in (0.05, 1.2, 2.35):
        tube(bm, [Vector((x, 0, -0.03)), Vector((x, 0, 0.0))], 0.006, 1, seg=6)
    ns, nz = 150, 50
    s0, s1, top, length = 0.06, 1.8, -0.07, 2.75
    grid = []
    phi = 0.0
    for i in range(ns + 1):
        u = i / ns
        s = s0 + (s1 - s0) * u
        lam = 0.09 + 0.08 * u
        if i:
            phi += 2 * math.pi * ((s1 - s0) / ns) / lam
        col = []
        for j in range(nz + 1):
            t = j / nz
            z = top - t * length
            y = 0.055 * math.sin(phi) * (0.65 + 0.35 * t) + 0.12 * t * t * noise.noise(Vector((0.7, 0.3, 1.0)))
            x = s + 0.012 * noise.noise(Vector((s * 3.0, z * 2.0, 0.5)))
            col.append(bm.verts.new((x, y, z)))
        grid.append(col)
    cut = [int(nz * (0.84 + 0.08 * noise.noise(Vector((i * 0.08, 0.5, 0.2))) + 0.05 * noise.noise(Vector((i * 0.6, 1.5, 0.2))))) for i in range(ns + 1)]
    faces = []
    for i in range(ns):
        for j in range(min(cut[i], cut[i + 1], nz)):
            f = bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
            f.material_index = 0
            f.smooth = True
            faces.append(f)
    loose = [v for col in grid for v in col if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.normal_update()
    res = bmesh.ops.solidify(bm, geom=faces, thickness=0.003)
    for f in bm.faces:
        if f.material_index == 0:
            f.smooth = True
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
wdd = build_wall("SM_Wand_Doppeltuer_4m", 4.0, door=DDOOR, seed=5)
fdd = build_door_frame("SM_Doppeltuerrahmen", DDOOR[0], DDOOR[1], DDOOR[2], hinges="beide")
lf140 = build_door_leaf("SM_Tuerblatt_140", DOOR[1] - DOOR[0] - 0.046, DOOR[2] - 0.033)
lf90 = build_door_leaf("SM_Tuerblatt_90", (DDOOR[1] - DDOOR[0] - 0.049) / 2, DDOOR[2] - 0.033, seed=52)
stairs = build_stairs("SM_Treppe_Podest")
bed = build_bed("SM_Krankenbett")
nst = build_nightstand("SM_Nachttisch")
iv = build_iv("SM_Infusionsstaender")
cu = build_curtain("SM_Vorhang")

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

def fogbox(name, center, size, density):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    f = bpy.context.active_object
    f.name = name
    f.scale = size
    m = fm.copy()
    m.node_tree.nodes["Principled Volume"].inputs["Density"].default_value = density
    f.data.materials.append(m)
    return f

# ======================= Szene: Patientenzimmer =======================
PX = 100.0
for x in (PX, PX + 4.0):
    put(fl, (x, 0, 0))
    put(ce, (x, 0, H))
put(wd, (PX, 0, 0))
put(fd, (PX, 0, 0))
door_leaf = put(lf140, (PX + DOOR[0] + 0.023, -0.02, 0.01))
door_leaf.rotation_euler = (0, 0, math.radians(-75))
put(w4, (PX + 4.0, 0, 0))
for x in (PX + 4.0, PX + 8.0):
    put(ww, (x, 4.0, 0), rz=math.pi)
    put(fw, (x, 4.0, 0), rz=math.pi)
put(w4, (PX, 0, 0), rz=math.pi / 2)
put(w4, (PX + 8.0, 0, 0), rz=math.pi / 2)
put(bed, (PX + 4.4, 3.86, 0), rz=-math.pi / 2)
b2 = put(bed, (PX + 6.95, 3.86, 0), rz=-math.pi / 2 + 0.06)
put(nst, (PX + 3.55, 3.55, 0))
put(nst, (PX + 6.0, 3.55, 0), rz=0.12)
put(iv, (PX + 3.65, 2.65, 0))
put(cu, (PX + 5.65, 3.86, H), rz=-math.pi / 2)
put(la, (PX + 2.0, 2.0, H))
put(la, (PX + 6.0, 2.0, H))
fogbox("Staub Zimmer", (PX + 4.0, 2.0, H / 2), (8.3, 4.3, H), 0.022)
area_light("Lampe Zimmer", (PX + 2.0, 2.0, H - 0.115), (1.15, 0.24), 70)

# ======================= Szene: Treppenhaus =======================
SX = 200.0
put(stairs, (SX, 0, 0))
for x in (SX, SX + 4.0):
    put(fl, (x, 0, 0))
    put(ce, (x, 0, FLOOR2 + H))
for z in (0.0, FLOOR2):
    put(w4, (SX, 0, z))
    put(w4, (SX + 4.0, 0, z))
    put(w4, (SX + 8.0, 0, z), rz=math.pi / 2)
    for x in (SX + 4.0, SX + 8.0):
        if z > 0:
            put(ww, (x, 4.0, z), rz=math.pi)
            put(fw, (x, 4.0, z), rz=math.pi)
        else:
            put(w4, (x, 4.0, z), rz=math.pi)
put(wdd, (SX, 0, 0), rz=math.pi / 2)
put(fdd, (SX, 0, 0), rz=math.pi / 2)
put(wd, (SX, 0, FLOOR2), rz=math.pi / 2)
put(fd, (SX, 0, FLOOR2), rz=math.pi / 2)
# Tuerblaetter: unten die Doppeltuer geschlossen, oben die Tuer einen Spalt offen
put(lf90, (SX + 0.02, DDOOR[0] + 0.023, 0.01), rz=math.pi / 2)
put(lf90, (SX + 0.065, DDOOR[1] - 0.023, 0.01), rz=math.pi * 1.5)
put(lf140, (SX + 0.02, DOOR[0] + 0.023, FLOOR2 + 0.01), rz=math.pi / 2 - 0.55)
rb = bmesh.new()
for lo, hi in (((SX, -T / 2, H), (SX + 8, T / 2, FLOOR2)), ((SX, 4 - T / 2, H), (SX + 8, 4 + T / 2, FLOOR2)),
               ((SX - T / 2, 0, H), (SX + T / 2, 4, FLOOR2)), ((SX + 8 - T / 2, 0, H), (SX + 8 + T / 2, 4, FLOOR2))):
    box(rb, lo, hi, 0)
finish("Ringbalken", rb, ["putz"], export=False)
fogbox("Staub Treppe", (SX + 4.0, 2.0, 3.5), (8.3, 4.3, 7.1), 0.02)
put(la, (SX + 6.2, 2.0, FLOOR2 + H))
area_light("Lampe Treppe", (SX + 6.2, 2.0, FLOOR2 + H - 0.115), (1.15, 0.24), 260)

# ======================= Szene: neue Teile nebeneinander =======================
LX = 300.0
TEILE = []
TEILE.append(put(wdd, (LX, 0, 0)))
TEILE.append(put(fdd, (LX, 0, 0)))
TEILE.append(put(lf90, (LX + DDOOR[0] + 0.023, -0.02, 0.01)))
rl = put(lf90, (LX + DDOOR[1] - 0.023, -0.065, 0.01), rz=math.pi)
rl.rotation_euler = (0, 0, math.pi + math.radians(55))
TEILE.append(rl)
TEILE.append(put(bed, (LX + 4.7, -1.1, 0)))
TEILE.append(put(nst, (LX + 7.35, -0.75, 0)))
TEILE.append(put(iv, (LX + 8.3, -0.9, 0)))
TEILE.append(put(cu, (LX + 9.0, -0.7, 3.05)))

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

if "zimmer" in SHOTS:
    log("Render Patientenzimmer ...")
    cam_d.lens = 20
    cam.location = (PX + 1.95, 0.6, 1.6)
    aim(cam, (PX + 5.3, 3.0, 1.0))
    spot.location = cam.location + Vector((0.12, -0.05, -0.2))
    spot_d.energy = 350
    aim(spot, (PX + 4.4, 2.6, 0.6))
    scene.render.filepath = os.path.join(OUT, "hd_zimmer.png")
    bpy.ops.render.render(write_still=True)

if "treppe" in SHOTS:
    log("Render Treppenhaus ...")
    cam_d.lens = 18
    cam.location = (SX + 7.3, 1.05, FLOOR2 / 2 + 1.65)
    aim(cam, (SX + 2.4, 2.9, FLOOR2 / 2 + 1.05))
    spot.location = cam.location + Vector((-0.1, 0.1, -0.2))
    spot_d.energy = 450
    aim(spot, (SX + 3.6, 2.9, FLOOR2 / 2 + 0.9))
    scene.render.filepath = os.path.join(OUT, "hd_treppe.png")
    bpy.ops.render.render(write_still=True)

if "teile" in SHOTS:
    log("Render neue Teile ...")
    keep = set(TEILE)
    for o in list(scene.objects):
        if o.type in ("MESH", "LIGHT") and o not in keep:
            o.hide_render = True
    bpy.ops.mesh.primitive_plane_add(size=80, location=(LX + 6, 0, 0))
    bpy.context.active_object.data.materials.append(color_material("Hintergrund", "#9a968e", 0.9))
    key = bpy.data.lights.new("Licht", "SUN")
    key.energy = 3.2
    key.angle = math.radians(8)
    kl = bpy.data.objects.new("Licht", key)
    kl.rotation_euler = (math.radians(52), 0, math.radians(-28))
    scene.collection.objects.link(kl)
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.58, 0.62, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    cam_d.lens = 35
    cam.location = (LX + 6.0, -12.0, 2.6)
    aim(cam, (LX + 6.0, -0.5, 1.25))
    scene.render.resolution_y = int(RES[0] * 0.42)
    scene.render.filepath = os.path.join(OUT, "hd_teile.png")
    bpy.ops.render.render(write_still=True)

info = {ob.name: sum(len(p.vertices) - 2 for p in ob.data.polygons) for ob, _ in PIECES}
log("Dreiecke je Teil:", info)
log("fertig")
