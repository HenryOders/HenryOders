# Tyrannosaurus rex für Spiele

Ein ausgewachsener T. rex als spielfertiges Skeletal Mesh für Unreal Engine 5, als glTF auch für Godot, Unity oder three.js. Das Tier ist ein eigenes Design nach heutigem Wissensstand und kein Nachbau eines Film-Dinos: schuppige Haut mit kleinen Schuppen, größere Schuppen entlang des Rückens, schuppige Lippen am Kieferrand, kleine zweifingrige Arme, drei tragende Zehen und eine kleine erste Zehe. Form, Skelett, Gewichte, Animationen, Texturen und Szenen entstehen komplett per Skript in Blender. Es stecken keine fremden Assets drin.

## Dateien

| Datei | Zweck |
|---|---|
| `t_rex.py` | erzeugt das Tier, die Texturen, das Skelett, drei Animationen, FBX und GLB, die `.blend`, fünf Vorschaubilder und zwei kurze Videos |
| `pruefe_export.py` | prüft die beiden Exporte unabhängig: Einheit und Skalierung der FBX, Knochen, Gewichte, Maße, Texturen, Animationen |

## Erzeugen und prüfen

```
blender -b -P t_rex.py
blender -b -P pruefe_export.py -- export
```

- Getestet mit Blender 4.5 LTS. Das Skript setzt Blender auf Werkseinstellungen zurück. Starte es deshalb nicht in einem offenen Projekt.
- Neben dem Skript entstehen:
  - `export/SK_TRex.fbx` für Unreal, in Zentimetern, mit den drei Animationen, Texturen eingebettet
  - `export/SK_TRex.glb` für alle anderen Engines, in Metern, mit den drei Animationen, Texturen eingebettet
  - `export/Texturen/` mit den fünf Texturen als PNG (siehe „Texturen“)
  - `t_rex.blend` mit Tier, Skelett, Animationen und beiden Szenen
  - `t_rex_dschungel.png`, `_bruellen`, `_seite`, `_vorne` und `_kopf`
  - `t_rex_laufen.mp4` und `t_rex_bruellen.mp4`
- `pruefe_export.py` schreibt am Ende „ALLES OK“ oder eine Liste der Fehler.
- Laufzeit auf einem Rechner mit vier Kernen (nur CPU): Modell, Skelett, Animationen, Texturen und Export etwa ZEIT_MODELL. Die fünf Bilder in 1920 × 1080 mit Cycles dauern etwa ZEIT_BILDER, die beiden Videos etwa ZEIT_VIDEOS.

Schalter für schnelle Läufe (Umgebungsvariablen):

| Schalter | Wirkung |
|---|---|
| `SHOTS=` (leer) | keine Bilder. `SHOTS=dschungel,kopf` rendert nur diese beiden |
| `VIDEOS=` (leer) | keine Videos. `VIDEOS=laufen` nur das Laufen |
| `SAMPLES=16`, `RES=960x540` | schnellere Bilder zum Testen (Standard sind 64 Samples mit Entrauschen) |
| `ATLAS=2048` | Texturen in halber Auflösung backen (Standard 4096) |
| `FEIN=0.02` | feines Netz für die Normal-Textur nur einmal statt zweimal unterteilen |
| `HAUT=0` | gar nicht backen: einfarbiges Tier, sehr schnell (zum Testen von Form und Animation) |

## Vorschaubilder und Videos

| Datei | Szene |
|---|---|
| `_dschungel` | Das Tier kommt durch eine Waldlichtung auf die Kamera zu (Laufen), Gegenlicht mit Sonnenstrahlen im Dunst |
| `_bruellen` | Nahaufnahme beim Brüllen in derselben Lichtung |
| `_seite`, `_vorne`, `_kopf` | Fotostudio mit runder Hohlkehle und großen Softboxen |
| `t_rex_laufen.mp4` | zwei Doppelschritte im Studio (800 × 450, 30 Bilder/s) |
| `t_rex_bruellen.mp4` | das Brüllen im Studio |

Die Lichtung ist frei erfunden und zeigt einen Wald der späten Kreidezeit:

- Farne, Palmfarne, Baumfarne, Schachtelhalme und Palmen im Unterholz
- hohe Nadelbäume mit Brettwurzeln, die Kronen über dem Bildrand
- moosbewachsene Felsen, zwei umgestürzte Stämme, Waldboden aus Lehm, Laubstreu und Moos
- Bodennebel, Sonne durch Lücken im Blätterdach, eine Lichtschneise auf das Tier

Alle Pflanzen sind per Skript gebaut und als verknüpfte Kopien verteilt. Die Szenen dienen nur den Bildern und sind nicht Teil des Exports.

## Das Tier

| | |
|---|---|
| Länge | 12,4 m von der Schnauze bis zur Schwanzspitze |
| Höhe | Hüfte 3,05 m, höchster Punkt 3,84 m (Kopf in der Bindepose) |
| Breite | 1,97 m (Oberschenkel) |
| Dreiecke | 112 968 |
| Ecken | 56 622 |
| Knochen | 36 |
| Materialien | 2 (`M_TRex_Haut`, `M_TRex_Auge`) |
| Texturen | 5, siehe unten |

- **Form:** Rumpf, Hals, Kopf und Schwanz sind ein Profilkörper, dazu Muskeln (Oberschenkel, Wade, Hals- und Kiefermuskeln), Schädelhöcker, Augenhöhlen, Nasenlöcher und die Mundhöhle. Alles ist als Abstandsfeld weich verschmolzen und daraus als gleichmäßiges Vierecksnetz (3,5 cm Kantenlänge) erzeugt. Das Körpernetz ist geschlossen, ohne Löcher und doppelte Flächen.
- **Maul:** Unterkiefer, Zunge, Gaumen und Rachen sind echte Geometrie. Im Maul sitzen 58 einzelne, leicht gebogene Zähne, oben 15 und unten 14 je Seite. Sie sind verschieden lang (Ersatzzähne) und stecken 5 cm tief im Zahnfleisch hinter der Lippe.
- **Augen:** eigene Augäpfel mit goldbrauner Iris und runder Pupille, mandelförmige Lidspalte, darüber der Knochenwulst.
- **Krallen:** drei große Zehenkrallen und eine kleine an der ersten Zehe je Fuß, zwei Fingerkrallen je Hand.

## Texturen

Das Hautmuster ist prozedural und wird mit Cycles in einen gemeinsamen UV-Atlas gebacken. Zähne und Krallen liegen im selben Atlas wie die Haut.

- Gegenschattierung: dunkler Rücken, hellerer Bauch und Kehle
- dunkle Querbänder über Rücken und Schwanz, unregelmäßige Flecken an den Flanken
- rotbraune Schnauze, dunkle Haut um die Augen, dunkle Lippen und Füße
- jede Schuppe etwas anders gefärbt, dunklere Fugen dazwischen
- Maul: Zahnfleisch, Zunge und ein dunkler Rachen; Zähne zur Spitze heller, Krallen dunkel mit hellerer Spitze
- Normalen aus einem zweimal unterteilten Netz mit Hautfalten (Kehle, Knie, Knöchel, Zehen, Schwanzunterseite) und Schuppenrelief: kleine Schuppen an Bauch und Kopf, mittlere an den Flanken, große Schilde entlang des Rückgrats, Höcker auf dem Schädel

| Textur | Größe | Inhalt |
|---|---|---|
| `T_TRex_BaseColor` | 4096² | Farbe (sRGB) |
| `T_TRex_ORM` | 4096² | R = Umgebungsverdeckung, G = Rauheit, B = Metall (0) (linear) |
| `T_TRex_Normal` | 4096² | Normalen im Tangentenraum, OpenGL (Grün = +Y): für Blender, glTF, Godot, Unity |
| `T_TRex_Normal_DirectX` | 4096² | dieselben Normalen mit umgedrehtem Grün: für Unreal (steckt so in der FBX) |
| `T_TRex_Auge` | 512² | Iris von vorn (planare Abbildung des Augapfels) |

- Die UV-Karte `UVMap` hat Nähte an unauffälligen Stellen: auf der Mittellinie von Rücken und Bauch, quer am Schwanzansatz, vor dem Hals und hinter dem Kopf, an Unterkiefer, Beinen und Armen innen und außen. Kopf und Unterkiefer bekommen doppelt so viel Platz im Atlas. Die Augen haben ihre eigene Abwicklung.

## Skelett

| Knochen | Kopf in Blender (m, X vorn, Y links) | Kopf in Unreal (cm, X vorn, Y rechts) |
|---|---|---|
| `root` | 0 / 0 / 0 | 0 / 0 / 0 |
| `pelvis` | 0 / 0 / 3,05 | 0 / 0 / 305 |
| `spine_01` … `spine_03` | 0,62 / 0 / 3,10 bis 2,05 / 0 / 3,00 | 62 / 0 / 310 bis 205 / 0 / 300 |
| `neck_01` … `neck_03` | 2,65 / 0 / 2,94 bis 3,42 / 0 / 3,20 | 265 / 0 / 294 bis 342 / 0 / 320 |
| `head` | 3,72 / 0 / 3,36 | 372 / 0 / 336 |
| `jaw` | 3,80 / 0 / 3,02 (Kiefergelenk) | 380 / 0 / 302 |
| `tail_01` … `tail_12` | 0 / 0 / 3,05 bis −6,55 / 0 / 2,00 | 0 / 0 / 305 bis −655 / 0 / 200 |
| `thigh_l`, `calf_l`, `foot_l`, `toe_l` | Hüfte 0 / 0,40 / 3,00, Knie 0,50 / 0,50 / 1,86, Knöchel −0,08 / 0,47 / 0,78, Ballen 0,14 / 0,45 / 0,13 | 0 / −40 / 300, 50 / −50 / 186, −8 / −47 / 78, 14 / −45 / 13 |
| `upperarm_l`, `lowerarm_l`, `hand_l` | Schulter 2,20 / 0,40 / 2,56, Ellbogen 2,18 / 0,55 / 2,22, Handgelenk 2,40 / 0,52 / 2,08 | 220 / −40 / 256, 218 / −55 / 222, 240 / −52 / 208 |
| `…_r` | gespiegelt (Y negativ) | gespiegelt (Y positiv) |

- `root` liegt am Boden unter den Hüftgelenken, `pelvis` ist das Becken. Rumpf und Schwanz hängen am Becken, die Arme an `spine_03`, der Unterkiefer am Kopf.
- Gewichte: Jede Ecke hängt an höchstens vier Knochen, die Summe ist 1. Die Übergänge sind weich (Schultern, Hüfte, Hals, Schwanz), der Schädel ist starr. Zähne, Augen und Krallen hängen starr an ihrem Knochen.
- In der Bindepose steht das Maul 12 Grad offen. So verformen sich die Lippen beim Öffnen und Schließen sauber. Die Animationen schließen das Maul über den Knochen `jaw`.
- Das Tier schaut in Blender und in Unreal nach +X. Beim Import muss nichts gedreht werden.
- Der Armature-Knoten heißt `Armature`. Unreal macht daraus normalerweise keinen eigenen Knochen.

## Animationen

| Aktion | Bilder (30/s) | Inhalt |
|---|---|---|
| `TRex_Idle` | 121 (4 s, Schleife) | Atmen, langsames Umsehen, Schwanz pendelt, Kiefer bewegt sich leicht |
| `TRex_Walk` | 55 (1,8 s je Doppelschritt, Schleife) | Laufen auf der Stelle, etwa 1,8 m/s (6,4 km/h). Die Füße rollen über Ballen und Zehen ab und rutschen nicht. Das Becken wippt und pendelt, Wirbelsäule und Schwanz schwingen gegen, der Kopf bleibt ruhig |
| `TRex_Roar` | 101 (3,3 s, einmal) | ausholen, Kopf nach vorn oben stoßen, Maul weit auf, Zittern, zurück in die Ruhepose |

- Bei den Schleifen ist das letzte Bild gleich dem ersten.
- Keine Wurzelbewegung (Root Motion): Das Tier läuft auf der Stelle. In der Engine bewegt die Charakter-Komponente den Körper. Damit die Füße nicht rutschen, passt eine Laufgeschwindigkeit von etwa 180 cm/s.
- Die Beine sind mit einer eigenen Zwei-Gelenk-Rechnung gestellt: Fuß und Zehen stehen beim Laufen flach auf dem Boden, beim Stehen und Brüllen bleiben sie an derselben Stelle.

## Export

- **FBX für Unreal:**
  - Die Einheit ist Zentimeter, jeder Knoten hat die Skalierung 1. So entsteht nicht der bekannte Fehler mit Faktor 100 am Wurzelknochen. Auch die Verschiebungen des Beckens in den Animationen sind in Zentimetern.
  - Die drei Animationen stecken als eigene Takes drin (`Armature|TRex_Idle`, `…_Walk`, `…_Roar`), jedes Bild als Schlüssel.
  - Zahn- und Krallenböden sind trianguliert, sonst Vierecke. Normalen und Tangenten sind enthalten, Farbe und Normalen (DirectX) eingebettet.
- **GLB für alle anderen:**
  - glTF 2.0 in Metern mit +Y oben, das Skelett steckt als Skin drin, die drei Animationen als eigene Animationen (`TRex_Idle`, `TRex_Walk`, `TRex_Roar`).
  - Die Materialien kommen vollständig an: Farbe, Rauheit, Metall, Umgebungsverdeckung und Normalen (OpenGL).
- Wer die FBX wieder in Blender lädt: Blenders FBX-Import verbindet `pelvis` fest mit dem Ende von `root` und ignoriert dann die Verschiebung des Beckens. In Unreal passiert das nicht. Für Blender ist die GLB oder die `.blend` die bessere Wahl.

## In Unreal Engine 5 einrichten

1. **Import:** `SK_TRex.fbx` in den Content Browser ziehen. Als Skeletal Mesh importieren, `Import Animations` an, ein Physics Asset erstellen lassen. Die Transformation bleibt unverändert: Drehung 0, Skalierung 1,0, `Convert Scene Unit` aus.
2. **Texturen:** Farbe und Normalen kommen mit. `export/Texturen/T_TRex_ORM.png` zusätzlich importieren, sRGB aus, Compression „Masks“.
3. **Material `M_TRex_Haut`:** Shading Model `Subsurface` (oder `Default Lit`).
   - `Base Color` = `T_TRex_BaseColor`
   - `T_TRex_ORM`: R → `Ambient Occlusion`, G → `Roughness`, B → `Metallic`
   - `Normal` = `T_TRex_Normal_DirectX` (Compression „Normalmap“). Mit der OpenGL-Variante stattdessen `Flip Green Channel` anhaken.
   - Bei `Subsurface`: `Subsurface Color` dunkles Rotbraun (etwa `#5A2A1E`), `Opacity` 0,3. Das lässt Kehle und dünne Hautstellen im Gegenlicht leicht durchscheinen.
4. **Material `M_TRex_Auge`:** `Base Color` = `T_TRex_Auge`, Roughness 0,05, Specular 0,6 (oder Shading Model `Clear Coat` mit Clear Coat 1).
5. **Charakter:** ein Blueprint mit der Elternklasse `Character` anlegen.
   - Kapsel: Radius etwa 150 cm, Half Height etwa 195 cm. Das Mesh um −195 cm in Z verschieben, weil der Ursprung am Boden liegt.
   - `Max Walk Speed` 180 cm/s, damit die Schritte zur Bewegung passen.
   - Ein Anim Blueprint mit einem Blend Space 1D: `TRex_Idle` bei 0, `TRex_Walk` bei 180 cm/s. `TRex_Roar` als Montage (Slot `DefaultSlot`) abspielen.
6. **Treffer und Physik:** Das erzeugte Physics Asset hat Körper an allen Knochen. Für Treffer reichen Kapseln an Kopf, Hals, Rumpf, Becken, Oberschenkeln, Unterschenkeln und den ersten Schwanzknochen.

## In Godot, Unity und three.js

- `SK_TRex.glb` einfach importieren: Mesh, Skelett, Materialien und die drei Animationen sind dabei. Die Normal-Textur ist im OpenGL-Format, wie glTF es vorschreibt.
- In Godot liegen die Animationen im AnimationPlayer der importierten Szene. `TRex_Idle` und `TRex_Walk` im Import-Dialog auf „Loop“ stellen.

## Leistung

- Rund 113 000 Dreiecke und zwei Materialien passen für einen Hauptgegner oder eine Zwischensequenz.
- Für mehrere Tiere gleichzeitig im Skeletal-Mesh-Editor LODs erzeugen lassen, zum Beispiel mit 50, 25 und 12 % der Dreiecke. Die Texturen kannst du in Unreal mit `Maximum Texture Size` auf 2048 begrenzen.
- Die Zähne kosten zusammen etwa 7 300 Dreiecke. Für weit entfernte LODs kannst du sie weglassen.
