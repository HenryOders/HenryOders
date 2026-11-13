# ABANDONED · Wandstücke „gefaengnis“

Sieben modulare Wandstücke für das alte Gefängnis, gebaut nach den Grundregeln für alle Gebäude. Modelle und Texturen sind komplett per Skript in Blender erzeugt. Es stecken keine fremden Assets drin, und es gibt kein Holz.

## Dateien

| Datei | Zweck |
|---|---|
| `kit_gefaengnis.py` | erzeugt die zwei Texturen, alle sieben Stücke, den glTF-Export und Vorschaubilder |
| `pruefe_gltf.py` | prüft die exportierten Dateien unabhängig gegen die Regeln (gleiche Datei wie beim Krankenhaus) |

## Erzeugen und prüfen

```
blender -b -P kit_gefaengnis.py
python pruefe_gltf.py PolyHaven gefaengnis
```

- Das Skript setzt Blender auf Werkseinstellungen zurück. Starte es deshalb nicht in einem offenen Projekt.
- Es legt neben sich den Ordner `PolyHaven/` an. Dessen Inhalt gehört nach `C:\Users\Henry\Abandoned\SourceArt\PolyHaven\`.
- `pruefe_gltf.py` braucht nur Python mit numpy. Am Ende steht „ALLES OK“ oder eine Liste der Fehler.

Schalter für schnelle Tests: `TEXDIV=4` (Texturen 1024 statt 4096 px), `SHOTS=` (keine Vorschaubilder), `DIAG=1` (listet Dreiecke außerhalb von 950–1100 px/m).

## Die Stücke

| Stück | Was es ist | Dreiecke | Pixeldichte px/m (min–max) | Vorstand |
|---|---|---|---|---|
| `gefaengnis_wand_01` | intakte Wand: Strichliste in der Farbe, Kratzspuren, zwei kleine Abplatzer | 1078 | 1022–1029 | 2,5 cm (Sockel) |
| `gefaengnis_wand_02` | stark beschädigt: vier Abplatzungen bis 5,5 cm tief mit freiliegender Bewehrung, tiefer Riss, Strichliste, Betonbrocken und Farbschuppen am Boden | 2922 | 1022–1038 | 8,7 cm |
| `gefaengnis_wand_03` | auf +Y zwei dicke Stahlrohre in Schellen unter der Decke, bündig an beiden Kanten, und ein verschlossener Schaltkasten auf Brusthöhe; auf −Y lange Strichliste und Kratzer | 2862 | 999–1031 | 10,5 cm |
| `gefaengnis_wand_tuer` | Öffnung 1,30 × 2,20 m, Zarge aus massivem Stahl mit Nieten, Anschlag und Bändern | 2204 | 1018–1030 | Zarge 2,0 cm, Sockel 2,5 cm |
| `gefaengnis_wand_fenster` | Öffnung 1,50 × 1,40 m ab 0,95 m, dicke Betonfasche, Stahlrahmen mit Nieten, Bänke auf beiden Seiten | 1134 | 1019–1027 | 7,0 cm (Bank) |
| `gefaengnis_wand_durchbruch` | Loch ab 0,96 m, zerklüftete Bruchfläche, 26 Eisenstummel (14 davon verbogen), Schuttkegel mit dicken Brocken auf beiden Seiten | 4090 | 1024–1025 | Schutt 50,4 cm, Wand 8,4 cm |
| `gefaengnis_wand_ecke` | Eckpfosten 21 × 21 cm, Sockel rundum (mit Sockel 26 × 26 cm) | 34 | 1024–1024 | 3,0 cm (Sockel) |

Die Pixeldichte ist an den exportierten Dateien gemessen. Die UV-Abbildung selbst ist überall genau 1024 px/m (Mittelwert bei allen Stücken 1024). Die kleine Streuung entsteht beim Speichern als 32-Bit-Zahlen an haarfeinen Dreiecken rund um die Strichlisten.

## Stil

- **Wand:** roher Sichtbeton aus 1 m breiten Schaltafeln mit Fugen, Grat und leichtem Versatz, Poren und runden Ankerlöchern (25 mm). Bis 1,2 m graugrün gestrichen, die Farbe blättert ab (darunter helle Grundierung und Beton). Darüber nackter Beton mit Rostläufern unter den Ankerlöchern, Ausblühungen an der Querfuge und unter der Decke, Wasserläufen.
- **Sockel:** niedriger Betonsockel, 10 cm hoch, 2,5 cm vorstehend, mit Fase.
- **Schäden als Geometrie:** Abplatzungen brechen in zwei Stufen bis 5,5 cm tief aus. Darin liegt die Bewehrung frei (waagerechte Eisen vorne, senkrechte dahinter, manche noch im Beton, manche durchgerostet). Kratzspuren und Strichlisten sind echte, 2–3 mm tiefe Nuten. Der Riss in wand_02 ist 7 cm tief.
- **Stahl:** Zarge aus massivem Stahl mit Futter, Flanschen, Anschlag, schweren Bändern und Nietköpfen. Das Fenster hat eine dicke Betonfasche, einen Stahlrahmen mit Nieten und Bänke auf beiden Seiten, ohne Glas und ohne Gitter.
- **Leitungen:** zwei dicke Stahlrohre (89 und 76 mm) in Schellen mit Ohren, Schrauben und Wandplatten. Dazu ein verschlossener Schaltkasten aus Blech mit Warnschild, Lüftungsschlitzen, Bändern und Vorhängeschloss und ein Leerrohr, das unter den Rohren in der Wand verschwindet.

## Regeln und wie sie eingehalten sind

- **Maße:** Grundkörper X −1,9 … +1,9, Z 0 … 3,4, Y −0,1 … +0,1 m. Drehpunkt unten mittig, Drehung und Skalierung angewendet. Im glTF hat der Knoten keine Transformation.
- **Kanten:** Alle sechs Wände haben links und rechts genau dasselbe Kantenbild, auch bei den UVs (Sockel 10 cm, Farbkante bei 1,2 m). Bei wand_03 enden zusätzlich die Rohre bündig an den Kanten.
- **Randzone:** Schäden, Kratzer und Strichlisten halten mindestens 40 cm Abstand zu den Kanten. Das Skript bricht ab, wenn sich zwei Schäden überschneiden oder einer zu nah an die Kante kommt.
- **Vorstand:** Nichts ragt mehr als 12 cm vor die Wandfläche. Nur der Schutt am Durchbruch reicht weiter, höchstens 60 cm.
- **Durchbruch:** An den Wandflächen 1,44 × 1,32 m, Unterkante bei 0,96 m. In der Wandmitte ist die Bruchfläche so begrenzt, dass das Loch nie breiter als 1,6 m, höher als 1,5 m oder tiefer als 0,9 m wird.
- **Dreiecke:** höchstens 3000 je Stück, beim Durchbruch höchstens 6000, beim Pfosten höchstens 800.
- **Normalen:** keine gekippten oder entarteten Dreiecke, alle Normalen haben die Länge 1.

## Texturen

Zwei kachelbare Sätze mit je 4096 × 4096 px. Alle sieben Stücke nutzen dieselben zwei Materialien und dieselben Bilddateien in `Texturen/gefaengnis/`.

| Satz | Inhalt |
|---|---|
| `T_gefaengnis_Wand_*` | Sichtbeton mit Schaltafeln und Ankerlöchern, bis 1,2 m graugrün gestrichen |
| `T_gefaengnis_Detail_*` | Streifen-Atlas: Betonkern mit Zuschlag und Rostspuren, Rissflanken, Kratzer, massiver Stahl (fünf Breiten), Betonsockel, Stahlrohre, Bewehrungsstahl mit Rippen, Schaltkasten |

Je Satz gibt es drei Dateien:

- `_Grundfarbe.jpg`: Farbe (sRGB).
- `_Normale.png`: Normal-Karte im OpenGL-Format, wie glTF es vorschreibt. Falls deine Engine DirectX erwartet und die Beulen falsch herum wirken, beim Import den Grünkanal umdrehen.
- `_Rauheit.png`: Rauheit im Grünkanal, Metall im Blaukanal (glTF-Packing, Rotkanal = 1).

**Maßstab:** UV 0,25 je Meter, also 1024 px/m. Eine Texturbreite sind 4 m und kachelt waagerecht nahtlos. Senkrecht deckt die Textur 4 m ab, die Wand nutzt 3,4 m.

## Raster

- Wände liegen im 4-m-Raster, ihre Mitte also bei 2 m, 6 m, …, auf jedem Rasterpunkt steht ein Eckpfosten. Er überdeckt die Wandenden um je 5 mm.
- Die Schaltafelfugen liegen bei 0,5 m, 1,5 m, … und die Ankerlöcher auf ganzen Metern. So laufen Fugen und Löcher über Wand und Pfosten weiter, auch wenn eine Wand um 90° oder 180° gedreht ist.
- Die Bewehrung liegt in allen Stücken im selben Raster: senkrecht alle 20 cm ab x = 0, waagerecht alle 20 cm ab z = 0,1 m. Die Rostspuren im Betonkern der Detail-Textur sitzen genau darauf.
