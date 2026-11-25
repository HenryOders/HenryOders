"""Prueft die Exporte des T. rex.

Start:  blender -b -P pruefe_export.py -- export
        (oder mit dem bpy-Modul: python pruefe_export.py -- export)

1. FBX roh gelesen: Einheit Zentimeter, an jedem Knoten Skalierung 1, die 36 Knochen, drei Animationen.
2. FBX und GLB in Blender neu importiert: genau ein Mesh "SK_TRex" und ein Skelett, Knochen an der richtigen Stelle,
   jede Ecke an 1 bis 4 Knochen mit Gewichtssumme 1, Groesse und Bodenkontakt, UV-Karte, Texturen,
   die Animationen Idle, Walk und Roar mit der richtigen Laenge; beim Laufen bleiben die Zehen ueber dem Boden.
Am Ende steht "ALLES OK" oder eine Liste der Fehler.
"""
import sys, os
import bpy
from mathutils import Vector
from io_scene_fbx import parse_fbx

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
EXP = ARGS[0] if ARGS else "export"
NAME = "SK_TRex"
FBX = os.path.join(EXP, NAME + ".fbx")
GLB = os.path.join(EXP, NAME + ".glb")
KNOCHEN = (["root", "pelvis", "spine_01", "spine_02", "spine_03", "neck_01", "neck_02", "neck_03", "head", "jaw"]
           + [f"tail_{i:02d}" for i in range(1, 13)]
           + [f"{n}_{s}" for s in "lr" for n in ("thigh", "calf", "foot", "toe", "upperarm", "lowerarm", "hand")])
ORTE = {"root": (0, 0, 0), "pelvis": (0, 0, 3.05), "head": (3.72, 0, 3.36), "jaw": (3.80, 0, 3.02),
        "thigh_l": (0, 0.40, 3.00), "foot_l": (-0.08, 0.47, 0.78), "toe_r": (0.14, -0.45, 0.13),
        "tail_12": (-6.55, 0, 2.00), "upperarm_r": (2.20, -0.40, 2.56)}
AKTIONEN = {"Idle": 121, "Walk": 55, "Roar": 101}       # Bilder je Aktion (Schleifen mit Endbild = Anfangsbild)
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
limbs, skalen = [], 0
objekte = kinder(root, b"Objects")[0]
for m in kinder(objekte, b"Model"):
    name = m.props[1].split(b"\x00")[0].decode()
    art = m.props[2].decode()
    s = props70(m).get("Lcl Scaling", (1.0, 1.0, 1.0))
    if any(abs(v - 1.0) > 1e-4 for v in s):
        fehler(f"Knoten {name} hat Skalierung {tuple(s)} statt 1")
        skalen += 1
    if art == "LimbNode":
        limbs.append(name)
    elif art != "LimbNode":
        print(f"  {art:9s} {name}")
print(f"  {len(limbs)} Knochen")
if sorted(limbs) != sorted(KNOCHEN):
    fehler(f"Knochen in der FBX: fehlen {sorted(set(KNOCHEN) - set(limbs))}, zu viel {sorted(set(limbs) - set(KNOCHEN))}")
stapel = [s.props[1].split(b"\x00")[0].decode() for s in kinder(objekte, b"AnimationStack")]
print("  Animationen:", stapel)
for a in AKTIONEN:
    if not any(a in s for s in stapel):
        fehler(f"FBX: Animation {a} fehlt")

# ---------- 2. Re-Import ----------
def pruefe_import(pfad, importer):
    print(os.path.basename(pfad))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 30                      # glTF speichert Sekunden; die Animationen laufen mit 30 fps
    importer(filepath=pfad)
    datei = os.path.basename(pfad)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    netze = [o for o in bpy.data.objects if o.type == "MESH" and o.vertex_groups]    # ohne Knochen-Anzeigeformen
    if len(arms) != 1 or len(netze) != 1 or not netze[0].name.startswith(NAME):
        fehler(f"{datei}: {len(arms)} Skelette und Meshes {[o.name for o in netze]} statt je einem ({NAME})")
        return None
    arm, ob = arms[0], netze[0]
    koepfe = {b.name: arm.matrix_world @ b.head_local for b in arm.data.bones}
    if sorted(koepfe) != sorted(KNOCHEN):
        fehler(f"{datei}: Knochen {sorted(koepfe)}")
        return None
    for name, soll in ORTE.items():
        if (koepfe[name] - Vector(soll)).length > 0.002:
            fehler(f"{datei}: Knochen {name} bei {tuple(round(v, 4) for v in koepfe[name])} statt {soll}")
    me = ob.data
    me.calc_loop_triangles()
    gruppen = {vg.index: vg.name for vg in ob.vertex_groups}
    ohne, zu_viele, summe_falsch, fremd = 0, 0, 0, 0
    for v in me.vertices:
        g = [x for x in v.groups if x.weight > 1e-6]
        if not g:
            ohne += 1
            continue
        if len(g) > 4:
            zu_viele += 1
        if abs(sum(x.weight for x in g) - 1.0) > 2e-3:
            summe_falsch += 1
        if any(gruppen.get(x.group) not in koepfe for x in g):
            fremd += 1
    mw = ob.matrix_world
    pts = [mw @ v.co for v in me.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    bilder = sorted({i.name for i in bpy.data.images})
    print(f"  {len(me.loop_triangles)} Dreiecke, {len(me.vertices)} Ecken, {len(me.materials)} Materialien, "
          f"UV {[u.name for u in me.uv_layers]}")
    print(f"  Groesse {hi[0] - lo[0]:.2f} x {hi[1] - lo[1]:.2f} x {hi[2] - lo[2]:.2f} m, tiefster Punkt Z = {lo[2]:.3f} m")
    print(f"  Bilder: {bilder}")
    for n, anz in (("ohne Gewicht", ohne), ("mit mehr als 4 Knochen", zu_viele),
                   ("mit Gewichtssumme ungleich 1", summe_falsch), ("an fremden Gruppen", fremd)):
        if anz:
            fehler(f"{datei}: {anz} Ecken {n}")
    if not me.uv_layers:
        fehler(f"{datei}: keine UV-Karte")
    if not (11.5 < hi[0] - lo[0] < 13.5 and 3.4 < hi[2] - lo[2] < 4.3):
        fehler(f"{datei}: unerwartete Groesse")
    if abs(lo[2]) > 0.05:
        fehler(f"{datei}: tiefster Punkt bei Z = {lo[2]:.3f} m statt etwa 0")
    if not any("BaseColor" in b for b in bilder) or not any("Normal" in b for b in bilder):
        fehler(f"{datei}: Texturen fehlen")
    # Animationen
    gefunden = {}
    for act in bpy.data.actions:
        for a in AKTIONEN:
            if a in act.name:
                gefunden[a] = act
    print("  Aktionen:", {a: (act.name, tuple(round(f) for f in act.frame_range)) for a, act in gefunden.items()})
    for a, anz in AKTIONEN.items():
        if a not in gefunden:
            fehler(f"{datei}: Animation {a} fehlt")
            continue
        f0, f1 = gefunden[a].frame_range
        if round(f1 - f0) + 1 != anz:
            fehler(f"{datei}: {a} hat {round(f1 - f0) + 1} Bilder statt {anz}")
    if "Walk" in gefunden:
        # Blenders FBX-Import haengt pelvis direkt an das Ende von root ("verbunden") und ignoriert dann die
        # Verschiebung des Beckens. Unreal kennt keine verbundenen Knochen; fuer die Pruefung hier loesen.
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        for eb in arm.data.edit_bones:
            eb.use_connect = False
        bpy.ops.object.mode_set(mode="OBJECT")
        arm.animation_data_create()
        arm.animation_data.action = gefunden["Walk"]
        if arm.animation_data.action_slot is None and gefunden["Walk"].slots:
            arm.animation_data.action_slot = gefunden["Walk"].slots[0]
        f0, f1 = (round(f) for f in gefunden["Walk"].frame_range)
        tief, hoch = 9.0, -9.0
        for f in range(f0, f1 + 1):
            bpy.context.scene.frame_set(f)
            for s in "lr":
                z = (arm.matrix_world @ arm.pose.bones["toe_" + s].tail).z
                tief, hoch = min(tief, z), max(hoch, z)
        print(f"  Laufen: Zehenspitzen zwischen Z = {tief:.3f} und {hoch:.3f} m")
        if tief < -0.03 or hoch < 0.08:
            fehler(f"{datei}: Zehen beim Laufen zwischen {tief:.3f} und {hoch:.3f} m")
    return len(me.loop_triangles), len(me.materials)

a = pruefe_import(FBX, bpy.ops.import_scene.fbx)
b = pruefe_import(GLB, bpy.ops.import_scene.gltf)
if a and b and a != b:
    fehler(f"FBX und GLB unterscheiden sich: {a} gegen {b} (Dreiecke, Materialien)")

print("ALLES OK" if not FEHLER else f"{len(FEHLER)} FEHLER")
