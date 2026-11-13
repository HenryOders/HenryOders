"""Unabhaengige Pruefung der exportierten Bodenplatten (liest nur die .gltf/.bin- und die Texturdateien).

Aufruf: python pruefe_boden.py <PolyHaven-Ordner> <Gebaeude>
Prueft: Aufbau der Dateien (ein Objekt, keine Kamera/Lichter, kein Versatz), Materialien und Texturpfade,
Masse und Ursprung, exakt flache Raender (aeussere 5 cm auf Z = 0), Hoehen (+-1,5 cm; lose Teile bis 6 cm und
mindestens 30 cm vom Rand), Dreiecke, Pixeldichte, weltbezogene UV der Oberseite, Normalen und die Texturen
(4096 x 4096, kachelbar, Rauheit gepackt mit Rot = 255 und Blau = 0). Beim Detail-Atlas kacheln die
durchgehenden Baender (V 0 .. 2,8 m) in U; darueber liegen Einzelflaechen (Mitte der OP-Platte, Schutt, Papier).
"""
import json, os, sys, math, struct, zlib
import numpy as np

ROOT, GEB = sys.argv[1], sys.argv[2]
TEXRES = 4096
NAMES = ["boden_01", "boden_02", "boden_03", "boden_04", "boden_schwelle"]
MAXTRI = 12000
DICHTE = (1024 * 0.95, 1024 * 1.05)      # erlaubt je Dreieck (px/m)
RAND, LOSE, HUB, LOSE_H = 0.05, 0.30, 0.015, 0.06
COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
TEXDIR = os.path.join(ROOT, "Texturen", GEB)
SAETZE = {f"M_{GEB}_Boden": f"T_{GEB}_Boden", f"M_{GEB}_BodenDetail": f"T_{GEB}_BodenDetail"}


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


def read_png(path):
    """8-Bit-PNG ohne Bildbibliothek lesen (Filter 0-4; 0, 1 und 2 schnell). Zeile 0 = oben."""
    d = open(path, "rb").read()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("keine PNG-Datei")
    pos, idat = 8, b""
    while pos < len(d):
        L = struct.unpack(">I", d[pos:pos + 4])[0]
        t, body = d[pos + 4:pos + 8], d[pos + 8:pos + 8 + L]
        pos += 12 + L
        if t == b"IHDR":
            w, h, bd, ct, _, _, il = struct.unpack(">IIBBBBB", body)
        elif t == b"IDAT":
            idat += body
        elif t == b"IEND":
            break
    if bd != 8 or il != 0:
        raise ValueError("nur 8 Bit ohne Interlace")
    bpp = {0: 1, 2: 3, 4: 2, 6: 4}[ct]
    raw = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, 1 + w * bpp)
    ft, px = raw[:, 0], raw[:, 1:]
    if np.all(ft == 2):
        out = np.cumsum(px, axis=0, dtype=np.uint8)
    else:
        out = np.empty_like(px)
        prev = np.zeros(w * bpp, np.uint8)
        for r in range(h):
            f, line = ft[r], px[r]
            if f == 0:
                cur = line.copy()
            elif f == 1:
                cur = np.cumsum(line.reshape(w, bpp), axis=0, dtype=np.uint8).reshape(-1)
            elif f == 2:
                cur = (line + prev).astype(np.uint8)
            else:
                cur = np.zeros_like(line)
                for i in range(w * bpp):
                    a = int(cur[i - bpp]) if i >= bpp else 0
                    b = int(prev[i])
                    c = int(prev[i - bpp]) if i >= bpp else 0
                    if f == 3:
                        cur[i] = (int(line[i]) + (a + b) // 2) & 255
                    else:
                        p = a + b - c
                        pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                        pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                        cur[i] = (int(line[i]) + pr) & 255
            out[r] = cur
            prev = cur
    return out.reshape(h, w, bpp)


def jpg_size(path):
    d = open(path, "rb").read()
    i = 2
    while i < len(d) - 9:
        if d[i] != 0xFF:
            i += 1
            continue
        m = d[i + 1]
        if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", d[i + 5:i + 9])
            return w, h
        if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
            i += 2
            continue
        i += 2 + struct.unpack(">H", d[i + 2:i + 4])[0]
    return None


def kachelt(img, achsen):
    """Vergleicht gegenueberliegende Bildraender mit dem Unterschied benachbarter Pixelreihen im Inneren."""
    a = img.astype(np.float64)
    out = {}
    for ax in achsen:
        rand = np.abs(np.take(a, 0, axis=ax) - np.take(a, -1, axis=ax)).mean()
        innen = np.abs(np.diff(a, axis=ax)).mean()
        out[("U", "V")[1 - ax]] = (round(float(rand), 2), round(float(innen), 2), bool(rand <= 2.5 * innen + 1.0))
    return out


report, fehler = {"texturen": {}}, []
# ---------- Texturen ----------
for mname, prefix in SAETZE.items():
    info = {}
    jpg = os.path.join(TEXDIR, prefix + "_Grundfarbe.jpg")
    if not os.path.exists(jpg):
        fehler.append(f"{prefix}: Grundfarbe fehlt")
    else:
        info["Grundfarbe"] = jpg_size(jpg)
        if info["Grundfarbe"] != (TEXRES, TEXRES):
            fehler.append(f"{prefix}_Grundfarbe: Groesse {info['Grundfarbe']}")
    for teil in ("Normale", "Rauheit"):
        path = os.path.join(TEXDIR, f"{prefix}_{teil}.png")
        if not os.path.exists(path):
            fehler.append(f"{prefix}: {teil} fehlt")
            continue
        img = read_png(path)
        d = {"groesse": img.shape[1::-1]}
        if img.shape[:2] != (TEXRES, TEXRES) or img.shape[2] < 3:
            fehler.append(f"{prefix}_{teil}: Groesse/Kanaele {img.shape}")
        if teil == "Rauheit":
            d["rot_min"], d["blau_max"] = int(img[..., 0].min()), int(img[..., 2].max())
            d["rauheit"] = (round(img[..., 1].min() / 255, 3), round(img[..., 1].max() / 255, 3))
            if d["rot_min"] != 255 or d["blau_max"] != 0:
                fehler.append(f"{prefix}_Rauheit: Rot muss 255, Blau 0 sein (Rot min {d['rot_min']}, Blau max {d['blau_max']})")
            k = kachelt(img[..., 1] if prefix.endswith("_Boden") else img[-int(img.shape[0] * 0.7):, :, 1],
                        (1, 0) if prefix.endswith("_Boden") else (1,))
        else:
            m = img[..., :3].reshape(-1, 3).mean(0)
            d["mittel"] = [round(float(v), 1) for v in m]
            if not (115 < m[0] < 141 and 115 < m[1] < 141 and m[2] > 230):
                fehler.append(f"{prefix}_Normale: Mittelwert {d['mittel']} passt nicht zu einer OpenGL-Normalkarte")
            k = kachelt(img[..., 1] if prefix.endswith("_Boden") else img[-int(img.shape[0] * 0.7):, :, 1],
                        (1, 0) if prefix.endswith("_Boden") else (1,))
        d["kachelt"] = k
        for achse, (r_, i_, ok) in k.items():
            if not ok:
                fehler.append(f"{prefix}_{teil}: Raender passen in {achse} nicht zusammen ({r_} gegen {i_})")
        info[teil] = d
    report["texturen"][prefix] = info

# ---------- Stuecke ----------
for short in NAMES:
    name = f"{GEB}_{short}"
    path = os.path.join(ROOT, "Modelle", name, name + ".gltf")
    if not os.path.exists(path):
        fehler.append(f"{name}: Datei fehlt")
        continue
    g, prims = load(path)
    r = {}
    # Aufbau: genau ein Objekt mit dem Dateinamen, ohne Versatz; keine Kamera, keine Lichter
    nodes = g.get("nodes", [])
    if len(nodes) != 1 or nodes[0].get("name") != name or "mesh" not in nodes[0]:
        fehler.append(f"{name}: erwartet genau ein Objekt '{name}', gefunden {[n.get('name') for n in nodes]}")
    for key in ("translation", "rotation", "scale", "matrix"):
        if nodes and key in nodes[0]:
            fehler.append(f"{name}: Objekt hat {key} (Transformationen nicht angewendet)")
    if g.get("cameras") or "KHR_lights_punctual" in g.get("extensionsUsed", []):
        fehler.append(f"{name}: Kamera oder Licht exportiert")
    # Materialien
    mats = g.get("materials", [])
    names = sorted(m.get("name") for m in mats)
    if names != sorted(SAETZE):
        fehler.append(f"{name}: Materialien {names}, erwartet {sorted(SAETZE)}")
    for m in mats:
        pbr = m.get("pbrMetallicRoughness", {})
        if pbr.get("metallicFactor", 1.0) != 0:
            fehler.append(f"{name}/{m.get('name')}: metallicFactor {pbr.get('metallicFactor', 1.0)} (kein Metallic erlaubt)")
        if m.get("alphaMode", "OPAQUE") != "OPAQUE" or m.get("extensions") or m.get("emissiveTexture") or m.get("occlusionTexture"):
            fehler.append(f"{name}/{m.get('name')}: nur Grundfarbe, Normale und Rauheit erlaubt")
        prefix = SAETZE.get(m.get("name"), "?")
        for teil, ref, ext in (("Grundfarbe", pbr.get("baseColorTexture"), "jpg"), ("Rauheit", pbr.get("metallicRoughnessTexture"), "png"),
                               ("Normale", m.get("normalTexture"), "png")):
            if ref is None:
                fehler.append(f"{name}/{m.get('name')}: {teil} nicht angeschlossen")
                continue
            img = g["images"][g["textures"][ref["index"]]["source"]]
            soll = f"../../Texturen/{GEB}/{prefix}_{teil}.{ext}"
            if img.get("uri") != soll or "bufferView" in img:
                fehler.append(f"{name}/{m.get('name')}: {teil} verweist auf {img.get('uri')}, erwartet {soll}")
            elif not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(path), img["uri"]))):
                fehler.append(f"{name}: Textur {img['uri']} nicht gefunden")
    matname = {i: m.get("name") for i, m in enumerate(mats)}
    P = np.concatenate([p["P"] for p in prims])
    tris = sum(len(p["I"]) for p in prims)
    r["dreiecke"] = tris
    if tris > MAXTRI:
        fehler.append(f"{name}: {tris} Dreiecke (hoechstens {MAXTRI})")
    # Masse und Ursprung
    schwelle = short == "boden_schwelle"
    xh, yh = (0.5, 0.1) if schwelle else (2.0, 2.0)
    mn, mx = P.min(0), P.max(0)
    r["masse"] = [[round(v, 4) for v in mn], [round(v, 4) for v in mx]]
    for i, (lo, hi) in enumerate(((-xh, xh), (-yh, yh))):
        if abs(mn[i] - lo) > 1e-5 or abs(mx[i] - hi) > 1e-5:
            fehler.append(f"{name}: {'xy'[i]} reicht von {mn[i]:.4f} bis {mx[i]:.4f}, erwartet {lo} bis {hi}")
    if abs(mn[2] + 0.2) > 1e-5:
        fehler.append(f"{name}: Unterseite bei z = {mn[2]:.4f}, erwartet -0,2")
    if mx[2] > (HUB if schwelle else LOSE_H) + 1e-6:
        fehler.append(f"{name}: hoechster Punkt z = {mx[2]:.4f}")
    # Rand: aeussere 5 cm exakt auf Z = 0 (nur Seitenflaechen reichen nach unten)
    if schwelle:
        zone = (np.abs(P[:, 0]) > xh - RAND + 1e-6) | (np.abs(P[:, 1]) > yh - RAND + 1e-6)
    else:
        zone = np.maximum(np.abs(P[:, 0]), np.abs(P[:, 1])) > 2.0 - RAND + 1e-6
    zz = P[zone][:, 2]
    bad = zone.sum() - ((np.abs(zz) < 1e-6) | (np.abs(zz + 0.2) < 1e-6)).sum()
    r["rand_flach"] = int(zone.sum()) - int(bad)
    if bad:
        fehler.append(f"{name}: {bad} Punkte in den aeusseren 5 cm nicht auf Z = 0")
    # Hoehen: Oberflaeche +-1,5 cm; was hoeher als 7 mm ist, gilt als loses Teil (30 cm Abstand vom Rand)
    m_ = np.maximum(np.abs(P[:, 0]) / xh, np.abs(P[:, 1]) / yh)
    hoch = P[:, 2] > 0.007
    if not schwelle and np.any(hoch & (np.maximum(np.abs(P[:, 0]), np.abs(P[:, 1])) > 2.0 - LOSE + 1e-6)):
        fehler.append(f"{name}: Teile hoeher als 7 mm naeher als 30 cm am Rand")
    if schwelle and np.any(P[:, 2] > HUB):
        fehler.append(f"{name}: Schwelle hoeher als 1,5 cm")
    tief = P[:, 2] < -HUB
    erlaubt = (np.abs(np.abs(P[:, 0]) - xh) < 1e-6) | (np.abs(np.abs(P[:, 1]) - yh) < 1e-6) | (np.abs(P[:, 2] + 0.2) < 1e-6)
    if short == "boden_04":
        erlaubt |= np.hypot(P[:, 0], P[:, 1]) <= 0.1001          # Topf des Bodenablaufs unter dem Rost
    if np.any(tief & ~erlaubt):
        fehler.append(f"{name}: {int((tief & ~erlaubt).sum())} Punkte tiefer als 1,5 cm (Loch in der Oberflaeche)")
    r["hoehe_cm"] = [round(float(P[~erlaubt][:, 2].min()) * 100, 2) if np.any(~erlaubt) else 0.0, round(float(mx[2]) * 100, 2)]
    # Pixeldichte, weltbezogene UV der Oberseite, Normalen
    dens, area = [], []
    welt_fehl, kipp, entartet, nlen = 0, 0, 0, []
    for p in prims:
        I, Pp, UV, N = p["I"], p["P"], p["UV"], p["N"]
        a, b, c = Pp[I[:, 0]], Pp[I[:, 1]], Pp[I[:, 2]]
        cr = np.cross(b - a, c - a)
        A3 = 0.5 * np.linalg.norm(cr, axis=1)
        ua, ub, uc = UV[I[:, 0]], UV[I[:, 1]], UV[I[:, 2]]
        A2 = 0.5 * np.abs((ub[:, 0] - ua[:, 0]) * (uc[:, 1] - ua[:, 1]) - (uc[:, 0] - ua[:, 0]) * (ub[:, 1] - ua[:, 1]))
        ok = A3 > 1e-10
        entartet += int((~ok).sum())
        dens.append(np.sqrt(A2[ok] / A3[ok]) * TEXRES)
        area.append(A3[ok])
        fn = cr[ok] / np.linalg.norm(cr[ok], axis=1, keepdims=True)
        vn = (N[I[ok, 0]] + N[I[ok, 1]] + N[I[ok, 2]])
        kipp += int((np.einsum("ij,ij->i", fn, vn) <= 0).sum())
        nlen.append(np.linalg.norm(N, axis=1))
        if matname.get(p["mat"]) == f"M_{GEB}_Boden":
            nz = fn[:, 2]
            ii = I[ok]
            oben = (nz > 0.9) & np.all(np.abs(Pp[ii][:, :, 2]) < 0.012, axis=1)
            unten = (nz < -0.9) & np.all(np.abs(Pp[ii][:, :, 2] + 0.2) < 1e-6, axis=1)
            sel = oben | unten
            v = ii[sel].reshape(-1)
            du = np.abs(UV[v, 0] - (Pp[v, 0] + 2.0) / 4.0)
            dv = np.abs((1.0 - UV[v, 1]) - (Pp[v, 1] + 2.0) / 4.0)
            welt_fehl += int(((du > 2e-4) | (dv > 2e-4)).sum())
    d = np.concatenate(dens)
    w = np.concatenate(area)
    r["dichte"] = {"min": round(float(d.min())), "max": round(float(d.max())), "mittel": round(float((d * w).sum() / w.sum()))}
    if d.min() < DICHTE[0] or d.max() > DICHTE[1]:
        fehler.append(f"{name}: Pixeldichte {d.min():.0f}..{d.max():.0f} px/m (erlaubt {DICHTE[0]:.0f}..{DICHTE[1]:.0f})")
    nl = np.concatenate(nlen)
    r["normalen"] = {"gekippt": kipp, "entartet": entartet, "laenge": [round(float(nl.min()), 3), round(float(nl.max()), 3)]}
    if kipp or entartet or abs(nl.min() - 1) > 1e-3 or abs(nl.max() - 1) > 1e-3:
        fehler.append(f"{name}: Normalen {r['normalen']}")
    r["uv_weltbezogen_fehler"] = welt_fehl
    if welt_fehl:
        fehler.append(f"{name}: {welt_fehl} Punkte der Oberseite nicht weltbezogen abgebildet (U = (X+2)/4, V = (Y+2)/4)")
    report[short] = r

print(json.dumps(report, ensure_ascii=False, indent=1))
print("FEHLER:\n - " + "\n - ".join(fehler) if fehler else "ALLES OK")
