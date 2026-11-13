"""Unabhaengige Pruefung der exportierten Wandstuecke (liest nur die .gltf/.bin-Dateien).

Aufruf: python pruefe_gltf.py <PolyHaven-Ordner> <Gebaeude>
Prueft: Dreiecke, Masse/Drehpunkt, Vorstand (12 cm, Schutt 60 cm), 40-cm-Randzone ohne Schaden,
gleiche Kanten bei allen Stuecken, Materialien/Texturpfade, Pixeldichte, Normalen.
"""
import json, os, sys, math
import numpy as np

ROOT, GEB = sys.argv[1], sys.argv[2]
TEXRES = 4096
W2, H, T2 = 1.9, 3.4, 0.1
NAMES = ["wand_01", "wand_02", "wand_03", "wand_tuer", "wand_fenster", "wand_durchbruch", "wand_ecke"]
LIMIT = {"wand_durchbruch": 6000, "wand_ecke": 800}
# Texturraster je Gebaeude: (Periode, Versatz Waende, Versatz Pfosten) in Metern des Wandbilds.
# Krankenhaus/Gefaengnis: am 4-m-Weltraster verankert (Fliesen 4/26 m, Schaltafeln 1 m).
# Labor: am Stueck verankert (Paneelfugen), x = 0 liegt auf beiden Seiten bei 2,0 m, der Pfosten bei 0.
# Schule: am 4-m-Weltraster verankert, Brettfugen alle 10 cm.
RASTER = {"krankenhaus": (4.0 / 26, 0.0, 0.0), "gefaengnis": (1.0, 0.0, 0.0), "labor": (4.0, 2.0, 0.0),
          "schule": (0.1, 0.0, 0.0)}.get(GEB, (1.0, 0.0, 0.0))
# Hoehen (z), in denen bei wand_03 auf +Y Leitungen buendig an den Kanten enden (Ausnahme vom Kantenvergleich)
PIPE_Z = {"schule": [(0.3, 0.75), (2.9, 3.41)]}.get(GEB, [(2.9, 3.41)])
# Gebaeude, deren Randzone Fugen oder Kantungen enthaelt (dort ist wand_01 keine reine Verlaengerung der Kante)
FUGEN_IN_RANDZONE = ("labor", "schule")
COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def load(path):
    g = json.load(open(path, encoding="utf-8"))
    base = os.path.dirname(path)
    bufs = [open(os.path.join(base, b["uri"]), "rb").read() for b in g["buffers"]]

    def acc(i):
        a = g["accessors"][i]
        bv = g["bufferViews"][a["bufferView"]]
        dt, nc = np.dtype(COMP[a["componentType"]]), NC[a["type"]]
        off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = bv.get("byteStride", 0) or dt.itemsize * nc
        raw = np.frombuffer(bufs[bv["buffer"]], dtype=np.uint8, count=stride * (a["count"] - 1) + dt.itemsize * nc, offset=off)
        idx = (np.arange(a["count"])[:, None] * stride + np.arange(dt.itemsize * nc)[None, :])
        return raw[idx].copy().view(dt).reshape(a["count"], nc)

    prims = []
    for m in g["meshes"]:
        for p in m["primitives"]:
            P = acc(p["attributes"]["POSITION"]).astype(np.float64)
            N = acc(p["attributes"]["NORMAL"]).astype(np.float64)
            UV = acc(p["attributes"]["TEXCOORD_0"]).astype(np.float64)
            I = acc(p["indices"]).astype(np.int64).reshape(-1, 3)
            # glTF (+Y oben) zurueck nach Blender (Z oben): x = X, y = -Z, z = Y
            P = np.stack([P[:, 0], -P[:, 2], P[:, 1]], 1)
            N = np.stack([N[:, 0], -N[:, 2], N[:, 1]], 1)
            prims.append({"P": P, "N": N, "UV": UV, "I": I, "mat": p.get("material")})
    return g, prims


def images_of(g, path):
    out = {}
    for mi, m in enumerate(g.get("materials", [])):
        pbr = m.get("pbrMetallicRoughness", {})
        refs = {"Grundfarbe": pbr.get("baseColorTexture"), "Rauheit": pbr.get("metallicRoughnessTexture"),
                "Normale": m.get("normalTexture")}
        d = {}
        for k, r in refs.items():
            if r is None:
                d[k] = None
                continue
            img = g["images"][g["textures"][r["index"]]["source"]]
            uri = img["uri"]
            d[k] = (uri, os.path.exists(os.path.normpath(os.path.join(os.path.dirname(path), uri))))
        out[m["name"]] = d
    return out


report, fehler = {}, []
edges = {}
zones = {}
for short in NAMES:
    name = f"{GEB}_{short}"
    path = os.path.join(ROOT, "Modelle", name, name + ".gltf")
    g, prims = load(path)
    P = np.concatenate([p["P"] for p in prims])
    tris = sum(len(p["I"]) for p in prims)
    lim = LIMIT.get(short, 3000)
    r = {"dreiecke": tris, "grenze": lim}
    if tris > lim:
        fehler.append(f"{short}: {tris} Dreiecke > {lim}")
    # Knoten ohne Verschiebung, Drehung, Skalierung (Drehpunkt = Ursprung)
    for nd in g.get("nodes", []):
        tr = {k: nd[k] for k in ("translation", "rotation", "scale", "matrix") if k in nd}
        ident = {"translation": [0, 0, 0], "rotation": [0, 0, 0, 1], "scale": [1, 1, 1]}
        if any(k == "matrix" or max(abs(a - b) for a, b in zip(v, ident[k])) > 1e-6 for k, v in tr.items()):
            fehler.append(f"{short}: Knoten {nd.get('name')} hat Transformation {tr}")
    r["knoten"] = len(g.get("nodes", []))
    # Masse und Drehpunkt
    lo, hi = P.min(0), P.max(0)
    r["bbox"] = [[round(v, 4) for v in lo], [round(v, 4) for v in hi]]
    if lo[2] < -1e-4 or hi[2] > H + 1e-4:
        fehler.append(f"{short}: Hoehe {lo[2]:.4f}..{hi[2]:.4f}")
    if short == "wand_ecke":
        # Pfosten 21 x 21 cm; Sockel darf so weit vorstehen wie an den Waenden
        lim = 0.105 + SOCKEL_VOR + 0.0005
        r["pfosten_halbe_breite_cm"] = round(max(abs(lo[0]), abs(hi[0]), abs(lo[1]), abs(hi[1])) * 100, 2)
        if max(abs(lo[0]), abs(hi[0]), abs(lo[1]), abs(hi[1])) > lim:
            fehler.append(f"{short}: Pfosten zu breit")
    else:
        if abs(lo[0] + W2) > 1e-4 or abs(hi[0] - W2) > 1e-4:
            fehler.append(f"{short}: Breite {lo[0]:.4f}..{hi[0]:.4f}")
    # Vorstand
    ay = np.abs(P[:, 1])
    r["vorstand_cm"] = round((ay.max() - T2) * 100, 1)
    if short == "wand_durchbruch":
        wall = P[:, 2] > 0.45
        r["vorstand_ohne_schutt_cm"] = round((ay[wall].max() - T2) * 100, 1)
        if ay[wall].max() > T2 + 0.12 + 1e-4:
            fehler.append(f"{short}: Teile ueber 45 cm Hoehe ragen {r['vorstand_ohne_schutt_cm']} cm vor")
        if ay.max() > T2 + 0.60 + 1e-4:
            fehler.append(f"{short}: Schutt ragt {r['vorstand_cm']} cm vor")
    elif ay.max() > T2 + 0.12 + 1e-4:
        fehler.append(f"{short}: ragt {r['vorstand_cm']} cm vor")
    if short == "wand_01":
        SOCKEL_VOR = float(np.abs(P[np.abs(np.abs(P[:, 0]) - W2) < 1e-4][:, 1]).max()) - T2
    # Randzone und Kanten
    if short != "wand_ecke":
        rz = {}
        for s in (-1, 1):
            at_edge = np.abs(P[:, 0] - s * W2) < 1e-4
            E = {(round(y, 4), round(z, 4)) for y, z in P[at_edge][:, 1:]}
            zone = (s * P[:, 0] > W2 - 0.4) & ~at_edge
            zones[(short, s)] = {tuple(round(float(c), 4) for c in p) for p in P[zone]}
            # wand_01 ist das intakte Bezugsstueck: dort muss die Randzone eine Verlaengerung des Kantenbilds sein
            # (beim Labor liegen dort zusaetzlich die Kanten der Randpaneele und die Tragschienen, bei der Schule die Brettfugen)
            bad = []
            if short == "wand_01" and GEB not in FUGEN_IN_RANDZONE:
                bad = [tuple(np.round(p, 3)) for p in P[zone] if (round(p[1], 4), round(p[2], 4)) not in E]
            rz[s] = len(bad)
            if bad:
                fehler.append(f"{short}: {len(bad)} Punkte in der 40-cm-Randzone {'rechts' if s > 0 else 'links'} weichen ab, z. B. {bad[:3]}")
            # Kantenbild mit UVs
            EU = set()
            for p in prims:
                m = np.abs(p["P"][:, 0] - s * W2) < 1e-4
                for (x, y, z), (u, v) in zip(p["P"][m], p["UV"][m]):
                    EU.add((round(y, 4), round(z, 4), round(u % 1.0, 4) % 1.0, round(v, 4), p["mat"]))
            edges[(short, s)] = (E, EU)
        r["randzone_abweichungen"] = rz
    # Materialien und Bilder
    r["materialien"] = images_of(g, path)
    # Pixeldichte und Normalen
    dens, area, flipped, degen, nlen = [], [], 0, 0, []
    for p in prims:
        A, B, C = (p["P"][p["I"][:, k]] for k in range(3))
        cr = np.cross(B - A, C - A)
        a3 = np.linalg.norm(cr, axis=1) / 2
        ua, ub, uc = (p["UV"][p["I"][:, k]] for k in range(3))
        a2 = np.abs((ub[:, 0] - ua[:, 0]) * (uc[:, 1] - ua[:, 1]) - (uc[:, 0] - ua[:, 0]) * (ub[:, 1] - ua[:, 1])) / 2
        ok = a3 > 2e-7
        degen += int((a3 < 1e-10).sum())
        d = np.sqrt(a2[ok] * TEXRES * TEXRES / a3[ok])
        dens.append(d)
        area.append(a3[ok])
        nv = (p["N"][p["I"][:, 0]] + p["N"][p["I"][:, 1]] + p["N"][p["I"][:, 2]])
        fn = cr / np.maximum(np.linalg.norm(cr, axis=1, keepdims=True), 1e-12)
        flipped += int(((np.einsum("ij,ij->i", fn, nv) <= 0) & ok).sum())
        nlen.append(np.linalg.norm(p["N"], axis=1))
    dens, area, nlen = np.concatenate(dens), np.concatenate(area), np.concatenate(nlen)
    r["dichte"] = {"min": round(float(dens.min())), "max": round(float(dens.max())),
                   "mittel": round(float((dens * area).sum() / area.sum()))}
    if dens.min() < 950 or dens.max() > 1100:
        fehler.append(f"{short}: Pixeldichte {dens.min():.0f}..{dens.max():.0f}")
    # Raster der Wandtextur (Fliesen 4/26 m, Schaltafeln 1 m, Brettfugen 0,1 m): auf Wandflaechen und allen vier Pfostenseiten
    # muessen die Fugen auf Vielfachen davon liegen, sonst springen sie an den Stoessen
    TS, OFF = RASTER[0], (RASTER[2] if short == "wand_ecke" else RASTER[1])
    worst = 0.0
    for p in prims:
        if p["mat"] is None or "Wand" not in g["materials"][p["mat"]]["name"]:
            continue
        n, P_, U = p["N"], p["P"], p["UV"][:, 0] * 4.0
        sel = [(n[:, 1] < -0.9999, U - P_[:, 0]), (n[:, 1] > 0.9999, U + P_[:, 0])]
        if short == "wand_ecke":
            sel += [(n[:, 0] > 0.9999, U - P_[:, 1]), (n[:, 0] < -0.9999, U + P_[:, 1])]
        for m, val in sel:
            if m.any():
                ph = np.mod(val[m] - OFF, TS)
                worst = max(worst, float(np.minimum(ph, TS - ph).max()))
    r["raster_abweichung_mm"] = round(worst * 1000, 2)
    if worst > 0.0005:
        fehler.append(f"{short}: Texturraster um {worst * 1000:.1f} mm verschoben")
    r["normalen"] = {"gekippt": flipped, "entartet": degen, "laenge_min": round(float(nlen.min()), 4),
                     "laenge_max": round(float(nlen.max()), 4)}
    if flipped or degen or abs(nlen.min() - 1) > 1e-3 or abs(nlen.max() - 1) > 1e-3 or np.isnan(nlen).any():
        fehler.append(f"{short}: Normalen {r['normalen']}")
    report[short] = r

# Kanten aller Stuecke gegen wand_01 (wand_03: die Leitungen auf +Y enden laut Vorgabe buendig an den Kanten)
def pipe_zone(short, e):
    return short == "wand_03" and e[0] >= T2 - 1e-4 and any(a < e[1] < b for a, b in PIPE_Z)
for s in (-1, 1):
    E0, EU0 = edges[("wand_01", s)]
    for short in NAMES:
        if short in ("wand_01", "wand_ecke"):
            continue
        E, EU = edges[(short, s)]
        extra = {e for e in E - E0 if not pipe_zone(short, e)}
        miss = E0 - E
        extra_uv = {e for e in EU - EU0 if not pipe_zone(short, e)}
        miss_uv = EU0 - EU
        key = "rechts" if s > 0 else "links"
        report[short].setdefault("kante_wie_wand_01", {})[key] = not (extra or miss or extra_uv or miss_uv)
        if extra or miss:
            fehler.append(f"{short}: Kante {key} anders als wand_01 (+{len(extra)} / -{len(miss)} Punkte)")
        elif extra_uv or miss_uv:
            fehler.append(f"{short}: Kante {key}: UVs anders als wand_01 (+{len(extra_uv)} / -{len(miss_uv)})")

# Randzonen aller Stuecke gegen das intakte wand_01: gleiche Punkte, nur bei wand_03 die Leitungen dazu
for s in (-1, 1):
    Z0 = zones[("wand_01", s)]
    for short in NAMES:
        if short in ("wand_01", "wand_ecke"):
            continue
        Zs = zones[(short, s)]
        extra = {p for p in Zs - Z0 if not (short == "wand_03" and p[1] >= T2 - 1e-4 and any(a < p[2] < b for a, b in PIPE_Z))}
        miss = Z0 - Zs
        report[short].setdefault("randzone_wie_wand_01", {})["rechts" if s > 0 else "links"] = not (extra or miss)
        if extra or miss:
            fehler.append(f"{short}: Randzone {'rechts' if s > 0 else 'links'} anders als beim intakten Stueck "
                          f"(+{len(extra)} / -{len(miss)} Punkte), z. B. {sorted(extra)[:2]}")

# gleiche Materialien und Bilder ueberall
mats = {short: json.dumps(report[short]["materialien"], sort_keys=True) for short in NAMES}
if len(set(mats.values())) != 1:
    fehler.append("Materialien oder Bildpfade unterscheiden sich zwischen den Stuecken")
for mname, d in report["wand_01"]["materialien"].items():
    for k, v in d.items():
        if v is None or not v[1]:
            fehler.append(f"Material {mname}: {k} fehlt oder Datei nicht gefunden ({v})")
texdir = os.path.join(ROOT, "Texturen", GEB)
report["_texturen"] = sorted(os.listdir(texdir))
print(json.dumps(report, indent=1, ensure_ascii=False))
print("FEHLER:" if fehler else "ALLES OK")
for f in fehler:
    print(" -", f)
