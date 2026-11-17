"""Prueft die Exporte des Streifenwagens.

Start:  blender -b -P pruefe_export.py -- export      (oder mit dem bpy-Modul: python pruefe_export.py -- export)

1. FBX roh gelesen: Einheit Zentimeter, an jedem Knoten Skalierung 1, die fuenf Knochen.
2. FBX und GLB in Blender neu importiert: genau ein Mesh "SK_Polizeiauto", die fuenf Knochen an der richtigen Stelle,
   jede Ecke haengt an genau einem Knochen mit Gewicht 1, die Radecken liegen im jeweiligen Rad,
   gleiche Zahl an Dreiecken und Materialien in beiden Dateien, UV-Karte vorhanden, Auto steht auf Z = 0.
Am Ende steht "ALLES OK" oder eine Liste der Fehler.
"""
import sys, os, math
import bpy
from mathutils import Vector
from io_scene_fbx import parse_fbx

EXP = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "export"
FBX = os.path.join(EXP, "SK_Polizeiauto.fbx")
GLB = os.path.join(EXP, "SK_Polizeiauto.glb")
KNOCHEN = {"root": (0.0, 0.0, 0.0), "wheel_fl": (1.42, 0.80, 0.335), "wheel_fr": (1.42, -0.80, 0.335),
           "wheel_rl": (-1.42, 0.80, 0.335), "wheel_rr": (-1.42, -0.80, 0.335)}
RAD_R, RAD_HALB = 0.335, 0.125
FEHLER = []

def fehler(text):
    FEHLER.append(text)
    print("  FEHLER:", text)

# ---------- 1. FBX roh ----------
def kinder(e, name):
    return [c for c in e.elems if c.id == name]

def props70(e):
    out = {}
    for p70 in kinder(e, b"Properties70"):
        for p in p70.elems:
            out[p.props[0].decode()] = p.props[4:]
    return out

root, version = parse_fbx.parse(FBX)
einstellungen = props70(kinder(root, b"GlobalSettings")[0])
einheit = einstellungen.get("UnitScaleFactor", [None])[0]
print(f"FBX {version}: UnitScaleFactor {einheit} (1 = Zentimeter)")
if einheit is None or abs(einheit - 1.0) > 1e-9:
    fehler(f"FBX-Einheit ist nicht Zentimeter (UnitScaleFactor {einheit})")
limbs = []
for m in kinder(kinder(root, b"Objects")[0], b"Model"):
    name = m.props[1].split(b"\x00")[0].decode()
    art = m.props[2].decode()
    p = props70(m)
    s = p.get("Lcl Scaling", (1.0, 1.0, 1.0))
    t = p.get("Lcl Translation", (0.0, 0.0, 0.0))
    print(f"  {art:9s} {name:16s} Verschiebung {tuple(round(v, 2) for v in t)}  Skalierung {tuple(round(v, 4) for v in s)}")
    if any(abs(v - 1.0) > 1e-6 for v in s):
        fehler(f"Knoten {name} hat Skalierung {tuple(s)} statt 1")
    if art == "LimbNode":
        limbs.append(name)
if sorted(limbs) != sorted(KNOCHEN):
    fehler(f"Knochen in der FBX: {sorted(limbs)}")

# ---------- 2. Re-Import ----------
def pruefe_import(pfad, importer):
    print(os.path.basename(pfad))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    importer(filepath=pfad)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    autos = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("SK_Polizeiauto")]
    if len(arms) != 1 or len(autos) != 1:
        fehler(f"{os.path.basename(pfad)}: {len(arms)} Armaturen und {len(autos)} Meshes SK_Polizeiauto statt je einer")
        return None
    arm, auto = arms[0], autos[0]
    koepfe = {b.name: arm.matrix_world @ b.head_local for b in arm.data.bones}
    if sorted(koepfe) != sorted(KNOCHEN):
        fehler(f"{os.path.basename(pfad)}: Knochen {sorted(koepfe)}")
        return None
    for name, soll in KNOCHEN.items():
        if (koepfe[name] - Vector(soll)).length > 0.001:
            fehler(f"{os.path.basename(pfad)}: Knochen {name} bei {tuple(round(v, 4) for v in koepfe[name])} statt {soll}")
    me = auto.data
    me.calc_loop_triangles()
    gruppen = {vg.index: vg.name for vg in auto.vertex_groups}
    mw = auto.matrix_world
    falsch_gewicht, ausserhalb = 0, 0
    zmin = min((mw @ v.co).z for v in me.vertices)
    ecken = [mw @ Vector(c) for c in auto.bound_box]
    groesse = [max(e[i] for e in ecken) - min(e[i] for e in ecken) for i in range(3)]
    for v in me.vertices:
        if len(v.groups) != 1 or abs(v.groups[0].weight - 1.0) > 1e-4:
            falsch_gewicht += 1
            continue
        name = gruppen[v.groups[0].group]
        if name.startswith("wheel_"):
            p = mw @ v.co
            k = koepfe[name]
            if math.hypot(p.x - k.x, p.z - k.z) > RAD_R + 0.002 or abs(p.y - k.y) > RAD_HALB:
                ausserhalb += 1
    print(f"  {len(me.loop_triangles)} Dreiecke, {len(me.materials)} Materialien, UV {[u.name for u in me.uv_layers]},"
          f" Groesse {groesse[0]:.3f} x {groesse[1]:.3f} x {groesse[2]:.3f} m, tiefster Punkt Z = {zmin:.4f} m")
    if falsch_gewicht:
        fehler(f"{os.path.basename(pfad)}: {falsch_gewicht} Ecken haengen nicht an genau einem Knochen mit Gewicht 1")
    if ausserhalb:
        fehler(f"{os.path.basename(pfad)}: {ausserhalb} Radecken liegen ausserhalb ihres Rads")
    if not me.uv_layers:
        fehler(f"{os.path.basename(pfad)}: keine UV-Karte")
    if abs(zmin) > 0.002:
        fehler(f"{os.path.basename(pfad)}: tiefster Punkt bei Z = {zmin:.4f} m statt 0")
    return len(me.loop_triangles), len(me.materials)

a = pruefe_import(FBX, bpy.ops.import_scene.fbx)
b = pruefe_import(GLB, bpy.ops.import_scene.gltf)
if a and b and a != b:
    fehler(f"FBX und GLB unterscheiden sich: {a} gegen {b} (Dreiecke, Materialien)")

print("ALLES OK" if not FEHLER else f"{len(FEHLER)} FEHLER")
