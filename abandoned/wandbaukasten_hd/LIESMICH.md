# ABANDONED · Wand-Baukasten HD (verlassenes Krankenhaus)

Hochaufgelöste Version für Unreal Engine 5 mit Nanite. Alles ist per Skript in Blender erzeugt, Modelle und Texturen. Es stecken keine fremden Assets drin, du darfst alles frei in deinem Spiel verwenden.

## Inhalt

Im Repository liegt nur das Skript. Die Modelle, Texturen und die Blender-Datei entstehen, wenn du es ausführst: in Blender 4.x im Tab „Scripting“ öffnen und starten (dauert einige Minuten). Danach liegt alles im Ordner `ABANDONED_Wandbaukasten_HD` neben dem Skript.

| Ordner oder Datei | Was drin ist |
|---|---|
| `Modelle_FBX/` | 12 Teile als FBX, mit Kollision |
| `Texturen/` | 9 Materialien, bis 4096 × 4096, kachelbar |
| `ABANDONED_Wandbaukasten_HD.blend` | alles zum Weiterbearbeiten in Blender |
| `abandoned_hd.py` | das Skript, das alles erzeugt |
| `Vorschau/` | drei gerenderte Bilder |

## Was „HD“ hier heißt

- **Echte Fliesen:** Jede Fliese ist ein eigenes Modell mit abgerundeten Kanten, 3-mm-Fugen und winzigen Versätzen. Manche fehlen, manche sind gesprungen.
- **Echte Rasterdecke:** T-Profile, durchhängende Platten, fehlende Platten mit Rohren dahinter, eine Platte hängt herunter.
- **Echter Linoleum-Boden:** 100 einzelne Platten pro Modul, einige fehlen oder stehen an einer Ecke hoch.
- **Kaputte Wand:** Bruchkante mit Betonbrocken, abgerissene Bewehrungseisen, Fliesen drumherum abgefallen.
- **Texturen bis 4K:** abblätternde Farbschichten, Risse, Wasserränder, Schimmel, Glasur mit feinen Haarrissen, Lack mit Rost.

## Die Teile

| Teil | Größe | Dreiecke |
|---|---|---|
| SM_Wand_4m | 4 × 3,2 m, 20 cm dick (mit Fliesen 22,4 cm) | ca. 31.000 |
| SM_Wand_2m | 2 × 3,2 m | ca. 16.000 |
| SM_Wand_Tuer_4m | Türöffnung 1,4 × 2,3 m | ca. 21.000 |
| SM_Wand_Fenster_4m | Fenster 1,6 × 1,2 m, Brüstung 1 m | ca. 28.000 |
| SM_Wand_Kaputt_4m | Loch mit Bruchkante und Bewehrung | ca. 25.000 |
| SM_Boden_4x4m | 10 × 10 Linoleum-Platten auf Beton | ca. 4.000 |
| SM_Decke_4x4m | Rasterdecke 6 × 6 Platten, Rohre, Betondecke | ca. 7.000 |
| SM_Saeule | 30 × 30 cm, gefliest | ca. 6.000 |
| SM_Tuerrahmen | Stahlzarge mit Anschlag und Bändern | ca. 700 |
| SM_Fensterrahmen | Rahmen mit Sprossen und Glasresten | ca. 800 |
| SM_Deckenlampe | Leuchte mit zwei Röhren | ca. 200 |
| SM_Schutt | Betonbrocken, Fliesenscherben, Putzplatten | ca. 6.000 |

Mit Nanite sind diese Polygonzahlen kein Problem.

## Raster

- Der Drehpunkt jeder Wand liegt unten am Wandanfang, in der Mitte der Wanddicke. Die Wand läuft 4 m in X-Richtung.
- Boden und Decke haben den Drehpunkt in der Ecke. Die Decke gehört auf 320 cm Höhe, der Drehpunkt sitzt an der Unterkante des Rasters.
- Tür- und Fensterrahmen haben denselben Drehpunkt wie ihre Wand. Setz sie an dieselbe Stelle.
- In Unreal das Einrasten auf 400 stellen, für die 2-m-Wand auf 200.

## Import in Unreal Engine 5

1. Den Ordner `Modelle_FBX` in den Content Browser ziehen. Im Import-Fenster **„Build Nanite“** einschalten.
2. Die Kollision ist schon eingebaut (UCX-Boxen). Ausnahmen sind `SM_Wand_Kaputt_4m` und `SM_Schutt`: Dort im Static Mesh unter Collision die Einstellung „Collision Complexity“ auf „Use Complex Collision As Simple“ stellen.
3. Den Ordner `Texturen` importieren. Die Normal-Karten sind schon im DirectX-Format für Unreal. Bei Roughness, Normal und Height muss „sRGB“ aus sein, bei Normal steht die Komprimierung auf „Normalmap“.
4. Unreal legt beim Import Materialien an, zum Beispiel `M_Putz` und `M_Fliesenglasur`. Darin BaseColor an Base Color, Roughness an Roughness und Normal an Normal anschließen.
5. `M_Glas` wird durchsichtig (Blend Mode „Translucent“), `M_Leuchte` bekommt Emissive. `M_Deckenraster` reicht als helle Farbe.
6. Für noch mehr Tiefe beim Putz: `T_Putz_Height` für Nanite-Tessellation (Displacement) nutzen.

## Texturen

| Material | Auflösung | deckt ab |
|---|---|---|
| Putz (mit Height) | 4096 | 4 × 4 m |
| Fliesenglasur | 4096 | 4 × 4 m, jede Fliese hat ihren eigenen Ton |
| Linoleum | 4096 | 4 × 4 m, passend zum Boden-Modul |
| Deckenplatte | 2048 | 4 × 4 m, passend zur Rasterdecke |
| Mörtel, Beton, Metall_lackiert | 2048 | 1 × 1 m |
| Rost | 1024 | 0,5 × 0,5 m |
| Leiste | 1024 | 1 × 1 m |

## Tipps

- Decals für Blut, Graffiti, Dreck und Wasserflecken machen jeden Flur einzigartig.
- Licht macht den größten Unterschied: Lumen anschalten, wenig Licht, etwas Staub (Exponential Height Fog mit Volumetric Fog) und eine Taschenlampe.
- Einzelne Gegenstände wie Betten, Rollstühle oder Aktenschränke kannst du in Meshy erzeugen und dann in Blender spielfertig machen lassen.
