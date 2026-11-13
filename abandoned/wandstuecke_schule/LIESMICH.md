# ABANDONED · Wandstücke „schule“

Sieben modulare Wandstücke für die alte Schule, gebaut nach den Grundregeln für alle Gebäude. Modelle und Texturen sind komplett per Skript in Blender erzeugt. Es stecken keine fremden Assets drin.

## Dateien

| Datei | Zweck |
|---|---|
| `kit_schule.py` | erzeugt die zwei Texturen, alle sieben Stücke, den glTF-Export und Vorschaubilder |
| `pruefe_gltf.py` | prüft die exportierten Dateien unabhängig gegen die Regeln (gleiche Datei wie bei den anderen Gebäuden) |

## Erzeugen und prüfen

```
blender -b -P kit_schule.py
python pruefe_gltf.py PolyHaven schule
```

- Das Skript setzt Blender auf Werkseinstellungen zurück. Starte es deshalb nicht in einem offenen Projekt.
- Es legt neben sich den Ordner `PolyHaven/` an. Dessen Inhalt gehört nach `C:\Users\Henry\Abandoned\SourceArt\PolyHaven\`.
- `pruefe_gltf.py` braucht nur Python mit numpy. Am Ende steht „ALLES OK“ oder eine Liste der Fehler.

Schalter für schnelle Tests: `TEXDIV=4` (Texturen 1024 statt 4096 px), `SHOTS=` (keine Vorschaubilder), `DIAG=1` (listet Dreiecke außerhalb von 950–1100 px/m).

## Die Stücke

| Stück | Was es ist | Dreiecke | Pixeldichte px/m (min–max) | Vorstand |
|---|---|---|---|---|
| `schule_wand_01` | intakte Wand; eingeritzt: MAJA, ein Herz und 1973 auf −Y, UWE und 7C auf +Y | 1366 | 1022–1026 | 2,8 cm (Holzleiste) |
| `schule_wand_02` | stark beschädigt: tiefer Riss durch den Putz bis in den Ziegel (beide Seiten), vier Putzabplatzungen bis auf den Ziegel, zwei davon mit Holzlatten als Putzträger, je Seite fehlende, lose und abgebrochene Bretter; Putzbrocken, Schuppen, Ziegelbröckchen und Splitter am Boden | 2542 | 1024–1024 | lose Bretter 8,9 cm, Brocken am Boden 11,5 cm |
| `schule_wand_03` | auf +Y Heizungsrohre in Kniehöhe und unter der Decke, Feuermelder mit eingeschlagener Scheibe; auf −Y ein loses Brett, eine kleine Abplatzung, eingeritzt OLE | 2696 | 1024–1024 | Rohre 7,0 cm, Brocken am Boden 11,0 cm |
| `schule_wand_tuer` | Öffnung 1,30 × 2,20 m, Zarge aus dunklem Holz; ein fehlendes Brett, eingeritzt KLO, auf +Y eine Abplatzung mit Latten | 1448 | 1024–1024 | Zarge 2,0 cm, Brocken am Boden 9,9 cm |
| `schule_wand_fenster` | Öffnung 1,50 × 1,40 m ab 0,95 m, Putzlaibung, Blendrahmen und Bänke aus Holz; ein loses Brett, eingeritzt JA, eine Abplatzung über dem Fenster | 1690 | 1024–1024 | Bänke 4,0 cm, loses Brett 8,3 cm, Brocken am Boden 10,1 cm |
| `schule_wand_durchbruch` | Loch 1,44 × 1,32 m ab 0,96 m, darunter zersplitterte Bretter, Leiste unterbrochen, je Seite eine Abplatzung, Schuttkegel auf beiden Seiten | 4526 | 1024–1024 | Schutt 48,6 cm, über 45 cm Höhe 5,6 cm |
| `schule_wand_ecke` | Pfosten 21 × 21 cm, unten Vertäfelung mit V-Fugen, oben Putz, Sockel- und Holzleiste rundum | 202 | 1024–1024 | 2,8 cm (Holzleiste) |

Die Pixeldichte ist an den exportierten Dateien gemessen. Flache Teile liegen genau bei 1024 px/m. Die kleinen Abweichungen stammen von schrägen Kerben und Splittern und von der Rundung auf 32-Bit-Zahlen in der Datei.

## Stil

- **Vertäfelung bis 1,2 m:** je Seite 38 senkrechte Bretter, 10 cm breit, als echte Geometrie mit V-Fugen (6 mm breit, 3 mm tief). Dunkel gebeizt, Maserung mit Fladern und stehenden Jahresringen, einzelne Äste. In Hand- und Stuhllehnenhöhe ist die Beize abgegriffen. Die Brettflächen liegen bündig mit dem Putz auf |y| = 0,1 m, dahinter sind Lattung und Grundputz.
- **Kratzer und eingeritzte Buchstaben:** viele Schrammen und schwach eingeritzte Wörter stecken in der Textur. Dazu kommen an einzelnen Stücken echte Kerben in hellem Holz: MAJA, ein Herz und 1973 sowie UWE und 7C (wand_01), TOM (wand_02), OLE (wand_03), KLO (wand_tuer), JA (wand_fenster).
- **Lose und fehlende Bretter:** lose Bretter sind oben abgebrochen und kippen nach vorn, unten stecken sie hinter der Sockelleiste. Hinter fehlenden Brettern sieht man die Lattung und den dunklen Grundputz. Abgebrochene Bretter enden in gezackten Bruchkanten mit Splittern.
- **Holzleiste und Sockelleiste:** die Holzleiste liegt auf 1,17–1,235 m über der Trennlinie 1,2 m und steht 2,8 cm vor. Ihre Unterseite schließt die Fugen oben ab. Die hölzerne Sockelleiste ist 11,6 cm hoch und steht 2,5 cm vor.
- **Putz darüber:** vergilbtes Creme, nach oben dunkler. Darauf sind verblasste Rechtecke abgehängter Bilder und Plakate und der runde Fleck einer Schuluhr zu sehen. Dazu kommen Nagel- und Dübellöcher, Klebestreifenreste (teils mit Papierfetzen), Kreidestaub und Kreidekritzeleien. Von der Decke ziehen Wasserflecken mit Rändern, stellenweise blättert die Farbe ab. Direkt über der Leiste sitzen Schrammen.
- **Untergrund unter abgefallenem Putz:** Ziegel im Läuferverband, 2,5 cm hinter der Putzfläche. Einzelne Ziegel fehlen, die Löcher liegen genau auf den Ziegeln der Textur. An manchen Stellen liegen Holzlatten als Putzträger auf dem Ziegel, einige sind gebrochen oder hängen herab.
- **Zarge und Fensterrahmen:** dunkles Holz. Die Bekleidung ist 9 cm breit und steht 2 cm vor der Wand, die Kanten sind gefast und heller abgegriffen. Die Tür hat Futter, Anschlag und zwei Bänder. Das Fenster hat eine Putzlaibung, einen Blendrahmen in der Wandmitte und Holzbänke auf beiden Seiten. Es hat kein Glas, keine Flügel und kein Gitter.
- **Leitungen (wand_03, +Y):** Vor- und Rücklauf der Heizung laufen in Kniehöhe (0,40 und 0,50 m), zwei weitere Rohre unter der Decke (3,13 und 3,24 m). Die Schellen sind mitgestrichen, alle Rohre enden bündig an beiden Kanten.
- **Feuermelder (wand_03, +Y):** ein Druckknopfmelder auf 1,52 m mit der Aufschrift FEUERMELDER. Die Scheibe ist eingeschlagen: Scherben stecken noch im Rahmen und liegen am Boden, dahinter sitzt der Knopf. Daneben hängt ein Nothammer an einer Kette, ein Leerrohr führt nach oben zu einer Abzweigdose.
- **Durchbruch:** ein Loch durch das Mauerwerk. Darunter sind die Bretter zersplittert: gezackte Bruchkanten, abstehende Splitter, zwei fehlen, eins hängt lose. Die Holzleiste ist unterbrochen. Auf beiden Seiten liegt ein Schuttkegel aus Ziegel- und Putzbrocken, Putzschuppen, Brettstücken, Splittern und Latten.

## Regeln und wie sie eingehalten sind

- **Maße:** Grundkörper X −1,9 … +1,9, Z 0 … 3,4, Y −0,1 … +0,1 m. Drehpunkt unten mittig, im glTF ohne Transformation.
- **Kanten:** Die Randbretter sind bei allen Stücken heil. Links und rechts ist das Kantenbild bei allen Wänden gleich, auch bei den UVs. An jeder Kante endet die Vertäfelung mit einer halben V-Fuge. Bei wand_03 kommen auf +Y die Heizungsrohre in Kniehöhe und unter der Decke dazu, die bündig an den Kanten enden.
- **Randzone:** Schäden halten mindestens 40 cm Abstand zu den Kanten. Die Prüfung vergleicht die Randzonen jedes Stücks Punkt für Punkt mit dem intakten wand_01.
- **Vorstand:** Nichts ragt mehr als 12 cm vor die Wandfläche. Die Zarge steht 2 cm vor, die losen Bretter oben höchstens 9 cm. Nur der Schutt am Durchbruch reicht weiter, höchstens 60 cm.
- **Dreiecke:** höchstens 3000 je Stück, beim Durchbruch höchstens 6000, beim Pfosten höchstens 800.
- **Normalen:** keine gekippten oder entarteten Dreiecke, alle Normalen haben die Länge 1.

## Texturen

Zwei kachelbare Sätze mit je 4096 × 4096 px. Alle sieben Stücke nutzen dieselben zwei Materialien und dieselben Bilddateien in `Texturen/schule/`.

| Satz | Inhalt |
|---|---|
| `T_schule_Wand_*` | unter 1,2 m die gebeizten Bretter (40 je 4 m), darüber der vergilbte Putz mit Bilderflecken, Klebestreifen, Kreide und Wasserflecken |
| `T_schule_Detail_*` | Streifen-Atlas: Ziegel, Bruchfläche, Rissflanken, Holzlatten, frisch angeritztes Holz, Brettkanten, Holzleiste, Sockelleiste, dunkles Rahmenholz (fünf Breiten), Grundputz, Heizungslack, Feuermelder mit Vorderseite, Glas, Stahl (drei Breiten) |

Je Satz gibt es drei Dateien:

- `_Grundfarbe.jpg`: Farbe (sRGB).
- `_Normale.png`: Normal-Karte im OpenGL-Format, wie glTF es vorschreibt. Falls deine Engine DirectX erwartet und die Beulen falsch herum wirken, beim Import den Grünkanal umdrehen.
- `_Rauheit.png`: Rauheit im Grünkanal, Metall im Blaukanal (glTF-Packing, Rotkanal = 1).

**Maßstab:** UV 0,25 je Meter, also 1024 px/m. Eine Texturbreite sind 4 m und kachelt waagerecht nahtlos.

## Raster und Wandbild

- Das Wandbild hängt wie beim Krankenhaus und Gefängnis am 4-m-Weltraster. Die Brettfugen der Geometrie liegen bei x = 0,1 k, auf beiden Seiten und an allen vier Pfostenseiten genau auf den Fugen der Textur.
- Die Wände passen ins 4-m-Raster mit einem Pfosten an jeder Stoßstelle. Sie können auch direkt aneinanderstoßen (3,8 m Abstand), dann ergeben die beiden halben Fugen an der Stoßstelle eine normale V-Fuge.
- Die Fensterlaibung zeigt Putz aus einer ruhigen Stelle des Wandbilds, damit unter 1,2 m kein Holz in der Laibung erscheint.
