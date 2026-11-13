# ABANDONED · Wandstücke „krankenhaus“

Sieben modulare Wandstücke für das verlassene Krankenhaus, gebaut nach den Grundregeln für alle Gebäude. Modelle und Texturen sind komplett per Skript in Blender erzeugt. Es stecken keine fremden Assets drin.

## Dateien

| Datei | Zweck |
|---|---|
| `kit_krankenhaus.py` | erzeugt die zwei Texturen, alle sieben Stücke, den glTF-Export und Vorschaubilder |
| `pruefe_gltf.py` | prüft die exportierten Dateien unabhängig gegen die Regeln |

## Erzeugen und prüfen

```
blender -b -P kit_krankenhaus.py
python pruefe_gltf.py PolyHaven krankenhaus
```

- Das Skript setzt Blender auf Werkseinstellungen zurück. Starte es deshalb nicht in einem offenen Projekt.
- Es legt neben sich den Ordner `PolyHaven/` an. Dessen Inhalt gehört nach `C:\Users\Henry\Abandoned\SourceArt\PolyHaven\`.
- `pruefe_gltf.py` braucht nur Python mit numpy. Am Ende steht „ALLES OK“ oder eine Liste der Fehler.

Schalter für schnelle Tests (Umgebungsvariablen):

| Schalter | Wirkung |
|---|---|
| `TEXDIV=4` | Texturen nur 1024 statt 4096 px groß, nur zum Testen |
| `SHOTS=` (leer) | keine Vorschaubilder |
| `DIAG=1` | listet Dreiecke, deren Pixeldichte außerhalb von 950–1100 px/m liegt |

## Die Stücke

| Stück | Was es ist | Dreiecke | Pixeldichte px/m (min–max) | Vorstand |
|---|---|---|---|---|
| `krankenhaus_wand_01` | intakte Wand, einzelne fehlende und gesprungene Fliesen | 182 | 1023–1024 | 1,2 cm |
| `krankenhaus_wand_02` | stark beschädigt: Putz großflächig ab mit Ziegeln darunter (einzelne Ziegel fehlen), Fliesenfeld abgefallen (Kleber mit Kammspuren), tiefer Riss, Scherben und Putzbrocken am Boden | 1522 | 1024–1024 | 10,6 cm |
| `krankenhaus_wand_03` | auf +Y zwei Sauerstoffleitungen aus Kupfer und ein Kabelkanal unter der Decke, bündig an beiden Kanten; Notrufkasten auf Brusthöhe mit Leitung zum Kanal | 722 | 1024–1024 | 7,9 cm |
| `krankenhaus_wand_tuer` | Öffnung 1,30 × 2,20 m, weiß lackierte Stahlzarge mit Rost an den Kanten, 2 cm vorstehend | 450 | 1024–1024 | 2,0 cm |
| `krankenhaus_wand_fenster` | Öffnung 1,50 × 1,40 m ab 0,95 m, Laibung, Metallrahmen, Fensterbank innen, Blechbank außen | 436 | 1024–1024 | 5,0 cm |
| `krankenhaus_wand_durchbruch` | Loch ab 0,94 m, zerklüftete Bruchkante, verbogene rostige Eisen, Schuttkegel auf beiden Seiten | 4058 | 1024–1024 | 58,4 cm (Schutt) |
| `krankenhaus_wand_ecke` | Eckpfosten 21 × 21 cm, alle vier Seiten sichtbar | 90 | 1024–1024 | 1,7 cm |

## Regeln und wie sie eingehalten sind

- **Maße:** Grundkörper X −1,9 … +1,9, Z 0 … 3,4, Y −0,1 … +0,1 m. Drehpunkt unten mittig, Drehung und Skalierung angewendet. Im glTF hat der Knoten keine Transformation.
- **Beide Seiten** sind gestaltet und unterscheiden sich.
- **Kanten:** Alle sechs Wände haben links und rechts genau dasselbe Kantenbild, auch bei den UVs: Sockel 12,3 cm, Abschlussleiste bei 1,2 m. Bei wand_03 enden zusätzlich Rohre und Kanal bündig an den Kanten, wie verlangt.
- **Randzone:** Schäden halten mindestens 40 cm Abstand zu den Kanten. Die Prüfung vergleicht jeden Punkt in der Randzone mit dem Kantenbild.
- **Vorstand:** Nichts ragt mehr als 12 cm vor die Wandfläche. Nur der Schutt am Durchbruch reicht bis 58,4 cm.
- **Dreiecke:** höchstens 3000 je Stück, beim Durchbruch höchstens 6000, beim Pfosten höchstens 800.
- **Normalen:** keine gekippten oder entarteten Dreiecke, alle Normalen haben die Länge 1.
- **Schäden** sind Geometrie, keine aufgemalten Flecken: fehlende Fliesen sind 8 mm tief, der Putz ist 2 cm dick, fehlende Ziegel liegen 3 cm tiefer, der Riss ist 7 cm tief.

## Texturen

Zwei kachelbare Sätze mit je 4096 × 4096 px. Alle sieben Stücke nutzen dieselben zwei Materialien und dieselben Bilddateien in `Texturen/krankenhaus/`.

| Satz | Inhalt |
|---|---|
| `T_krankenhaus_Wand_*` | Fliesen bis 1,2 m (Cremeweiß und blasses Türkis, Schmutz, Wasserläufe, Schimmel in den Fugen), darüber blassgrüner Putz mit Rostflecken, Wasserläufen und Schimmel |
| `T_krankenhaus_Detail_*` | Streifen-Atlas: Ziegel, Fliesenkleber mit Kammspuren, Bruchflächen, Riss, weiß lackiertes Metall mit Rost, Sockelfliesen, Abschlussleiste, Kupfer, Rost, Kabelkanal, Front des Notrufkastens |

Je Satz gibt es drei Dateien:

- `_Grundfarbe.jpg`: Farbe (sRGB).
- `_Normale.png`: Normal-Karte im OpenGL-Format, wie glTF es vorschreibt. Falls deine Engine DirectX erwartet und die Beulen falsch herum wirken, beim Import den Grünkanal umdrehen.
- `_Rauheit.png`: Rauheit im Grünkanal, Metall im Blaukanal (glTF-Packing, Rotkanal = 1).

**Maßstab:** UV 0,25 je Meter, also 1024 px/m. Eine Texturbreite sind 4 m und kachelt waagerecht nahtlos. Senkrecht deckt die Textur 4 m ab, die Wand nutzt 3,4 m.

**Abweichung von der Vorgabe:** Die Fliesen sind 15,4 cm statt 15 cm groß. Nur mit genau 26 Fliesen auf 4 m kachelt die Textur nahtlos. Der Sockel ist 12,3 cm hoch, darüber liegen genau 7 Fliesenreihen bis zur Trennlinie bei 1,2 m.

## Raster

- Wände liegen im 4-m-Raster, ihre Mitte also bei 2 m, 6 m, …
- Auf jedem Rasterpunkt (0 m, 4 m, …) steht ein Eckpfosten. Er überdeckt die Wandenden um je 5 mm.
- So laufen Fliesenfugen und Texturen über Wand und Pfosten weiter, auch wenn eine Wand um 90° oder 180° gedreht ist.
