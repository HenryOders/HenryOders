# ABANDONED · Wand-Baukasten (verlassenes Krankenhaus)

Alle Teile sind per Skript in Blender erzeugt. Es stecken keine fremden Assets drin, du darfst alles frei in deinem Spiel verwenden.

## Inhalt

Im Repository liegt nur das Skript. Die Modelle, Texturen und die Blender-Datei entstehen, wenn du es ausführst: in Blender 4.x im Tab „Scripting“ öffnen und starten. Danach liegt alles im Ordner `ABANDONED_Wandbaukasten` neben dem Skript.

| Ordner oder Datei | Was drin ist |
|---|---|
| `Modelle_FBX/` | 12 Teile als FBX für Unreal |
| `Texturen/` | 5 Materialien mit je 4 Karten, 1024 × 1024, kachelbar |
| `ABANDONED_Wandbaukasten.blend` | alles zum Weiterbearbeiten in Blender |
| `abandoned_wandbaukasten.py` | das Skript, das alles erzeugt |

## Die Teile

| Teil | Größe | Dreiecke |
|---|---|---|
| SM_Wand_4m | 4 × 3,2 m, 20 cm dick | 36 |
| SM_Wand_2m | 2 × 3,2 m | 36 |
| SM_Wand_Tuer_4m | Türöffnung 1,4 × 2,3 m | 84 |
| SM_Wand_Fenster_4m | Fenster 1,6 × 1,2 m, Brüstung 1 m | 96 |
| SM_Wand_Kaputt_4m | Wand mit ausgebrochenem Loch | 256 |
| SM_Boden_4x4m | Bodenplatte | 12 |
| SM_Decke_4x4m | Deckenplatte | 12 |
| SM_Saeule | 30 × 30 cm, für Ecken | 24 |
| SM_Tuerrahmen | passt in SM_Wand_Tuer_4m | 36 |
| SM_Fensterrahmen | passt in SM_Wand_Fenster_4m | 72 |
| SM_Deckenlampe | Neonröhre, Drehpunkt oben | 24 |
| SM_Schutt | Brocken vor der kaputten Wand | 320 |

Die Wände sind unten gefliest (1,4 m) und oben verputzt, mit einer Leiste dazwischen.

## Raster

- Der Drehpunkt jeder Wand liegt unten am Wandanfang, in der Mitte der Wanddicke. Die Wand läuft 4 m in X-Richtung.
- Boden und Decke haben den Drehpunkt in der Ecke. Die Decke gehört auf 320 cm Höhe.
- Tür- und Fensterrahmen haben denselben Drehpunkt wie ihre Wand. Setz sie einfach an dieselbe Stelle.
- In Unreal das Einrasten auf 400 stellen, für die 2-m-Wand auf 200.

## Import in Unreal Engine 5

1. Den Ordner `Modelle_FBX` in den Content Browser ziehen.
2. Die Kollision ist schon eingebaut (UCX-Boxen). Ausnahmen sind `SM_Wand_Kaputt_4m` und `SM_Schutt`: Dort im Static Mesh unter Collision die Einstellung „Collision Complexity“ auf „Use Complex Collision As Simple“ stellen.
3. Den Ordner `Texturen` importieren. Nimm die Normal-Karten mit `DirectX_Unreal` im Namen, die OpenGL-Karten sind für Blender. Bei Roughness und Normal muss „sRGB“ aus sein, bei Normal steht die Komprimierung auf „Normalmap“.
4. Unreal legt beim Import Materialien an, zum Beispiel `M_Fliesen` und `M_Putz`. Darin BaseColor an Base Color, Roughness an Roughness und Normal an Normal anschließen.
5. Für die Leiste, die Rahmen und die Lampe reichen einfache Farben. `M_Leuchte` bekommt Emissive.

## Tipps

- Die Texturen wiederholen sich alle 1 bis 2,4 m. Mit Decals (Dreck, Risse, Wasserflecken) und Vertex Painting fällt das nicht mehr auf.
- Die Texturen sind ein guter Start. Später kannst du sie gegen gescannte Texturen tauschen, die UVs passen weiter.
- Einzelne Gegenstände wie Betten, Rollstühle oder Aktenschränke kannst du in Meshy erzeugen und dann in Blender sauber machen lassen.
