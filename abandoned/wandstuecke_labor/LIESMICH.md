# ABANDONED · Wandstücke „labor“

Sieben modulare Wandstücke für das unterirdische Forschungslabor, gebaut nach den Grundregeln für alle Gebäude. Modelle und Texturen sind komplett per Skript in Blender erzeugt. Es stecken keine fremden Assets drin.

## Dateien

| Datei | Zweck |
|---|---|
| `kit_labor.py` | erzeugt die zwei Texturen, alle sieben Stücke, den glTF-Export und Vorschaubilder |
| `pruefe_gltf.py` | prüft die exportierten Dateien unabhängig gegen die Regeln (gleiche Datei wie bei den anderen Gebäuden) |

## Erzeugen und prüfen

```
blender -b -P kit_labor.py
python pruefe_gltf.py PolyHaven labor
```

- Das Skript setzt Blender auf Werkseinstellungen zurück. Starte es deshalb nicht in einem offenen Projekt.
- Es legt neben sich den Ordner `PolyHaven/` an. Dessen Inhalt gehört nach `C:\Users\Henry\Abandoned\SourceArt\PolyHaven\`.
- `pruefe_gltf.py` braucht nur Python mit numpy. Am Ende steht „ALLES OK“ oder eine Liste der Fehler.

Schalter für schnelle Tests: `TEXDIV=4` (Texturen 1024 statt 4096 px), `SHOTS=` (keine Vorschaubilder), `DIAG=1` (listet Dreiecke außerhalb von 950–1100 px/m).

## Die Stücke

| Stück | Was es ist | Dreiecke | Pixeldichte px/m (min–max) | Vorstand |
|---|---|---|---|---|
| `labor_wand_01` | intakte Wand mit zwei leichten Dellen | 906 | 1004–1024 | 9,0 cm (Kabeltrog) |
| `labor_wand_02` | stark beschädigt: drei Paneele fehlen (Beton mit tiefem Riss, Dämmwolle, Kabelstränge), eins oben losgerissen, drei verbeult; Splitter, Dämmflocken und Betonbröckchen am Boden | 2528 | 990–1029 | 10,5 cm |
| `labor_wand_03` | auf +Y Kabelbündel, zwei markierte Rohre und ein Bedienfeld mit dunklem Bildschirm; auf −Y eine Delle | 2015 | 1003–1024 | 9,2 cm |
| `labor_wand_tuer` | Öffnung 1,30 × 2,20 m, Zarge aus gebürstetem Stahl mit Gummidichtung | 1156 | 1005–1024 | Zarge 2,0 cm, Kabeltrog 9,0 cm |
| `labor_wand_fenster` | Öffnung 1,50 × 1,40 m ab 0,95 m, Stahlzarge, Rahmen mit Gummidichtung, Bänke beidseitig | 1420 | 1001–1024 | Bänke 5,0 cm, Kabeltrog 9,0 cm |
| `labor_wand_durchbruch` | Loch im Betonkern 1,44 × 1,32 m ab 0,96 m, Dämmung ringsum eingerissen, abgerissene Kabel, Schuttkegel auf beiden Seiten | 5395 | 1024–1024 | Schutt 48,6 cm, Wand 10,5 cm |
| `labor_wand_ecke` | Pfosten 21 × 21 cm; Rammschutz und Kabeltrog laufen rundum, die Trogkabel als Ring | 434 | 1024–1024 | 9,5 cm (Kabeltrog) |

Die Pixeldichte ist an den exportierten Dateien gemessen. Flache Teile liegen genau bei 1024 px/m; Dellen und das losgerissene Paneel weichen leicht ab, weil sie schräg stehen.

## Stil

- **Verkleidung:** hellgraue Metallpaneele, je Stück genau vier Stück à 0,95 m nebeneinander, in zwei Reihen (bis 1,2 m und darüber). Die Fugen sind echte 8-mm-Spalte, dahinter liegen Tragschienen. Die Paneele sind 2 cm tief gekantet. Schraubenköpfe sitzen 2,5 cm neben jeder Fuge, manche rostig.
- **Oberfläche:** Kondenswasser (Tropfen und Laufspuren, glänzend), Rostränder an den Fugen, dunkle Schlieren von oben. Die untere Reihe ist etwas dunkler und verschrammt.
- **Rammschutz:** 30 cm hoch, gelb-schwarz unter 45°, steht 2,5 cm vor, abgestoßen.
- **Kabeltrog:** durchgehend auf 1,2 m, verzinkt mit gelochtem Boden, vier Kabel darin, Konsolen darunter. Er verdeckt die waagerechte Paneelfuge. Am Pfosten läuft er mit seinen Kabeln rundherum.
- **Schäden als Geometrie:** Dellen mit Knickfalte, ein oben losgerissenes, verdrehtes Paneel, fehlende Paneele. Dahinter liegen Beton (mit tiefem Riss in wand_02), eingerissene Dämmwolle und Kabelstränge.
- **Stahl:** Zarge und Fensterrahmen aus gebürstetem Stahl mit schwarzer Gummidichtung. Die Zarge steht 2 cm vor, das Fenster hat Bänke auf beiden Seiten, ohne Glas und ohne Gitter.
- **Leitungen (wand_03):** ein Bündel aus sieben Kabeln mit Kabelbindern, zwei Rohre mit grüner und gelber Kennzeichnung und Pfeilen, Schellen aus Edelstahl. Dazu ein Bedienfeld mit dunklem Bildschirm, Tasten, Ziffernfeld und Not-Aus, dessen Kabel in den Trog führt.
- **Durchbruch:** Die mittleren Paneele fehlen. Das Loch geht durch Dämmung und Betonkern, aus dem Trog und vom Lochrand hängen abgerissene Kabel. Davor liegt ein Schuttkegel mit Betonbrocken, Dämmflocken, Paneelsplittern und Kabelresten.

## Regeln und wie sie eingehalten sind

- **Maße:** Grundkörper X −1,9 … +1,9, Z 0 … 3,4, Y −0,1 … +0,1 m. Die Paneel-Vorderseite liegt auf |y| = 0,1, dahinter 6 cm Hohlraum und 8 cm Betonkern. Drehpunkt unten mittig, im glTF ohne Transformation.
- **Kanten:** Die Randpaneele sind bei allen Stücken heil. Links und rechts ist das Kantenbild bei allen Wänden gleich, auch bei den UVs. Bei wand_03 kommen die Leitungen dazu, die bündig an den Kanten enden.
- **Randzone:** Schäden halten mindestens 40 cm Abstand zu den Kanten. Die Prüfung vergleicht die Randzonen jedes Stücks Punkt für Punkt mit dem intakten wand_01.
- **Vorstand:** Nichts ragt mehr als 12 cm vor die Wandfläche, das losgerissene Paneel steht oben 10 cm vor. Nur der Schutt am Durchbruch reicht weiter, höchstens 60 cm.
- **Dreiecke:** höchstens 3000 je Stück, beim Durchbruch höchstens 6000, beim Pfosten höchstens 800.
- **Normalen:** keine gekippten oder entarteten Dreiecke, alle Normalen haben die Länge 1.

## Texturen

Zwei kachelbare Sätze mit je 4096 × 4096 px. Alle sieben Stücke nutzen dieselben zwei Materialien und dieselben Bilddateien in `Texturen/labor/`.

| Satz | Inhalt |
|---|---|
| `T_labor_Wand_*` | Paneeloberfläche mit Schrauben, Rosträndern an den Fugen, Kondenswasser und Schlieren; unter 1,2 m dunkler und verschrammt |
| `T_labor_Detail_*` | Streifen-Atlas: Beton, Dämmwolle, Kabel in fünf Farben, gebürsteter Stahl (fünf Breiten), Gummi, Rammschutz, Kabeltrog, zwei Rohre mit Kennzeichnung, Bedienfeld, Paneelkanten, Tragschienen, roter Kunststoff, Rissflanken |

Je Satz gibt es drei Dateien:

- `_Grundfarbe.jpg`: Farbe (sRGB).
- `_Normale.png`: Normal-Karte im OpenGL-Format, wie glTF es vorschreibt. Falls deine Engine DirectX erwartet und die Beulen falsch herum wirken, beim Import den Grünkanal umdrehen.
- `_Rauheit.png`: Rauheit im Grünkanal, Metall im Blaukanal (glTF-Packing, Rotkanal = 1).

**Maßstab:** UV 0,25 je Meter, also 1024 px/m. Eine Texturbreite sind 4 m und kachelt waagerecht nahtlos.

## Raster und Wandbild

- **Neu beim Labor:** Das Wandbild hängt am Stück, nicht am 4-m-Weltraster. Die Fugen x = −1,9 / −0,95 / 0 / 0,95 / 1,9 liegen auf beiden Seiten bei 0,1 / 1,05 / 2,0 / 2,95 / 3,9 m im Bild, so treffen Schrauben und Rostränder in jeder Drehung genau die echten Fugen.
- Der Bereich 3,9 … 4,1 m im Bild gehört dem Pfosten: ein schmaler Paneelstreifen mit einer Schraubenreihe in der Mitte.
- Die Wände passen ins 4-m-Raster mit einem Pfosten an jeder Stoßstelle. Sie können aber auch direkt aneinanderstoßen (3,8 m Abstand), dann liegt an der Stoßstelle eine normale 8-mm-Fuge.
- Bei wand_03 liegen die Rohrmarkierungen bei x = −1,5 / −0,5 / 0,5 / 1,5 m.
