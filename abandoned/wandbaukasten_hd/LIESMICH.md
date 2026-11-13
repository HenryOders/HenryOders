# ABANDONED · Baukasten HD (verlassenes Krankenhaus)

Hochaufgelöste Version für Unreal Engine 5 mit Nanite. Alles ist per Skript in Blender erzeugt, Modelle und Texturen. Es stecken keine fremden Assets drin, du darfst alles frei in deinem Spiel verwenden.

## Inhalt

Im Repository liegt nur das Skript. Die Modelle, Texturen und die Blender-Datei entstehen, wenn du es ausführst: in Blender 4.x im Tab „Scripting“ öffnen und starten (dauert einige Minuten). Danach liegt alles im Ordner `ABANDONED_Wandbaukasten_HD` neben dem Skript.

| Ordner oder Datei | Was drin ist |
|---|---|
| `Modelle_FBX/` | 21 Teile als FBX, mit Kollision |
| `Texturen/` | 13 Materialien, bis 4096 × 4096, kachelbar |
| `ABANDONED_Wandbaukasten_HD.blend` | alles zum Weiterbearbeiten in Blender |
| `abandoned_hd.py` | das Skript, das alles erzeugt |
| `Vorschau/` | gerenderte Bilder |

Entpacke das Modelle-Zip und die Textur-Zips in denselben Ordner, dann findet die Blender-Datei ihre Texturen.

## Was „HD“ hier heißt

- **Echte Fliesen:** Jede Fliese ist ein eigenes Modell mit abgerundeten Kanten, 3-mm-Fugen und winzigen Versätzen. Manche fehlen, manche sind gesprungen.
- **Echte Rasterdecke:** T-Profile, durchhängende Platten, fehlende Platten mit Rohren dahinter, eine Platte hängt herunter.
- **Echter Linoleum-Boden:** 100 einzelne Platten pro Modul, einige fehlen oder stehen an einer Ecke hoch.
- **Kaputte Wand:** unregelmäßige, glatte Bruchkante mit zerklüfteter Bruchfläche, Betonbrocken, abgerissenen Bewehrungseisen und abgefallenen Fliesen.
- **Texturen bis 4K:** abblätternde Farbschichten, Risse, Wasserränder, Schimmel, Glasur mit feinen Haarrissen, Lack mit Rost.

## Die Teile

| Teil | Was es ist | Dreiecke |
|---|---|---|
| SM_Wand_4m | Wand 4 × 3,2 m, 20 cm dick (mit Fliesen 22,4 cm) | ca. 31.000 |
| SM_Wand_2m | Wand 2 × 3,2 m | ca. 16.000 |
| SM_Wand_Tuer_4m | Türöffnung 1,4 × 2,3 m | ca. 21.000 |
| SM_Wand_Doppeltuer_4m | Öffnung 1,8 × 2,3 m für Stationstüren | ca. 19.000 |
| SM_Wand_Fenster_4m | Fenster 1,6 × 1,2 m, Brüstung 1 m | ca. 28.000 |
| SM_Wand_Kaputt_4m | Loch mit Bruchkante und Bewehrung | ca. 28.000 |
| SM_Boden_4x4m | 10 × 10 Linoleum-Platten auf Beton | ca. 4.000 |
| SM_Decke_4x4m | Rasterdecke 6 × 6 Platten, Rohre, Betondecke | ca. 7.000 |
| SM_Saeule | 30 × 30 cm, gefliest | ca. 6.000 |
| SM_Tuerrahmen | Stahlzarge für die 1,4-m-Tür | ca. 700 |
| SM_Doppeltuerrahmen | Stahlzarge für die Doppeltür, Bänder auf beiden Seiten | ca. 800 |
| SM_Tuerblatt_140 | Tür mit Sichtfenster, Trittschutz und Drücker | ca. 1.200 |
| SM_Tuerblatt_90 | Flügel der Doppeltür (zwei Stück einsetzen) | ca. 1.200 |
| SM_Fensterrahmen | Rahmen mit Sprossen und Glasresten | ca. 800 |
| SM_Deckenlampe | Leuchte mit zwei Röhren | ca. 200 |
| SM_Schutt | Betonbrocken, Fliesenscherben, Putzplatten | ca. 6.000 |
| SM_Treppe_Podest | Treppe über ein Geschoss (3,85 m) mit Podest und Geländer, 8 × 4 m | ca. 1.400 |
| SM_Krankenbett | Bett mit Matratze, Kissen, Seitengittern und Rollen | ca. 3.300 |
| SM_Nachttisch | Nachttisch mit Schublade und Tür | ca. 900 |
| SM_Infusionsstaender | Ständer mit Rollen, Haken und Beutel | ca. 900 |
| SM_Vorhang | Vorhang an Deckenschiene, unten zerrissen | ca. 26.000 |

Mit Nanite sind diese Polygonzahlen kein Problem.

## Raster und Drehpunkte

- **Wände:** Drehpunkt unten am Wandanfang, in der Mitte der Wanddicke. Die Wand läuft 4 m in X-Richtung.
- **Boden und Decke:** Drehpunkt in der Ecke. Die Decke gehört auf 320 cm Höhe, der Drehpunkt sitzt an der Unterkante des Rasters.
- **Rahmen:** Tür- und Fensterrahmen haben denselben Drehpunkt wie ihre Wand. Setz sie an dieselbe Stelle.
- **Türblätter:** Drehpunkt unten an der Bandseite, damit die Tür in Unreal richtig aufschwingt. In SM_Wand_Tuer_4m sitzt das Blatt bei X = 132,3 cm, Y = −2 cm, Z = 1 cm. In der Doppeltür sitzt der linke Flügel bei X = 112,3 cm, Y = −2 cm, der rechte um 180° gedreht bei X = 287,7 cm, Y = −6,5 cm.
- **Treppe:** Drehpunkt in der unteren Ecke. Lauf 1 beginnt bei X = 150 cm, das Podest liegt auf 192,5 cm, die obere Platte auf 385 cm. Das nächste Geschoss beginnt also auf 385 cm.
- **Möbel:** Drehpunkt unten. Das Bett läuft vom Kopfende 2,1 m in X-Richtung.
- In Unreal das Einrasten auf 400 stellen, für die 2-m-Wand auf 200.

## Import in Unreal Engine 5

1. Den Ordner `Modelle_FBX` in den Content Browser ziehen. Im Import-Fenster **„Build Nanite“** einschalten.
2. Die Kollision ist schon eingebaut (UCX-Boxen). Ausnahmen sind `SM_Wand_Kaputt_4m`, `SM_Schutt`, `SM_Treppe_Podest`, `SM_Vorhang` und `SM_Infusionsstaender`: Dort im Static Mesh unter Collision die Einstellung „Collision Complexity“ auf „Use Complex Collision As Simple“ stellen. Beim Vorhang kannst du die Kollision auch ganz weglassen.
3. Den Ordner `Texturen` importieren. Die Normal-Karten sind schon im DirectX-Format für Unreal. Bei Roughness, Normal und Height muss „sRGB“ aus sein, bei Normal steht die Komprimierung auf „Normalmap“.
4. Unreal legt beim Import Materialien an, zum Beispiel `M_Putz` und `M_Fliesenglasur`. Darin BaseColor an Base Color, Roughness an Roughness und Normal an Normal anschließen.
5. `M_Glas` und `M_Infusionsbeutel` werden durchsichtig (Blend Mode „Translucent“), `M_Leuchte` bekommt Emissive. Für `M_Deckenraster`, `M_Kunststoff`, `M_Edelstahl` und `M_Gummi` reichen einfache Farben, beim Edelstahl mit Metallic 1.
6. Für noch mehr Tiefe beim Putz: `T_Putz_Height` für Nanite-Tessellation (Displacement) nutzen.

## Texturen

| Material | Auflösung | deckt ab |
|---|---|---|
| Putz (mit Height) | 4096 | 4 × 4 m |
| Fliesenglasur | 4096 | 4 × 4 m, jede Fliese hat ihren eigenen Ton |
| Linoleum | 4096 | 4 × 4 m, passend zum Boden-Modul |
| Deckenplatte | 2048 | 4 × 4 m, passend zur Rasterdecke |
| Mörtel, Beton, Metall_lackiert, Terrazzo, Matratze, Vorhang, Türlack | 2048 | 1 × 1 m |
| Rost | 1024 | 0,5 × 0,5 m |
| Leiste | 1024 | 1 × 1 m |

## Tipps

- Decals für Blut, Graffiti, Dreck und Wasserflecken machen jeden Flur einzigartig.
- Licht macht den größten Unterschied: Lumen anschalten, wenig Licht, etwas Staub (Exponential Height Fog mit Volumetric Fog) und eine Taschenlampe.
- Die Türblätter kannst du als eigene Actors mit einer Timeline aufschwingen lassen, zum Beispiel wenn ein Monster dagegen schlägt.
- Den Vorhang kannst du in Unreal auch als Cloth simulieren lassen.
- Einzelne Gegenstände wie Rollstühle oder Aktenschränke kannst du in Meshy erzeugen und dann in Blender spielfertig machen lassen.
