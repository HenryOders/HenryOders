# Streifenwagen für Spiele

Ein fahrbarer Streifenwagen für Unreal Engine 5 (Chaos Vehicles), als glTF auch für Godot, Unity oder three.js. Das Auto ist ein eigenes Kombi-Design und keiner echten Marke nachgebaut. Die Beklebung folgt dem deutschen blau-silbernen Stil mit POLIZEI-Schriftzügen, das Kennzeichen ist ausgedacht. Modell, Skelett, Materialien und Texturen entstehen komplett per Skript in Blender. Es stecken keine fremden Assets drin.

## Dateien

| Datei | Zweck |
|---|---|
| `polizeiauto.py` | erzeugt das Auto, die Texturen, das Skelett, FBX und GLB, die `.blend` und sechs Vorschaubilder |
| `pruefe_export.py` | prüft die beiden Exporte unabhängig: Einheit und Skalierung der FBX, Knochen, Gewichte, Maße |

## Erzeugen und prüfen

```
blender -b -P polizeiauto.py
blender -b -P pruefe_export.py -- export
```

- Getestet mit Blender 4.5 LTS. Das Skript setzt Blender auf Werkseinstellungen zurück. Starte es deshalb nicht in einem offenen Projekt.
- Neben dem Skript entstehen:
  - `export/SK_Polizeiauto.fbx` für Unreal, in Zentimetern, Texturen eingebettet
  - `export/SK_Polizeiauto.glb` für alle anderen Engines, in Metern, Texturen eingebettet
  - `export/Texturen/` mit den drei Texturen als PNG
  - `polizeiauto.blend` mit Auto und Skelett in Metern, dazu die Nachtszene
  - `polizeiauto_vorne.png`, `_hinten`, `_seite`, `_oben`, `_detail` und `_nacht`
- `pruefe_export.py` schreibt am Ende „ALLES OK“ oder eine Liste der Fehler.
- Modell, Texturen und Export brauchen etwa 20 Sekunden. Die sechs Bilder in 1920 × 1080 mit Cycles auf der CPU dauern auf einem Rechner mit vier Kernen etwa 20 Minuten. Mit `SHOTS=` fallen sie weg.

Schalter für schnelle Läufe (Umgebungsvariablen):

| Schalter | Wirkung |
|---|---|
| `SHOTS=` (leer) | keine Bilder. `SHOTS=vorne,nacht` rendert nur diese beiden |
| `SAMPLES=16`, `RES=960x540` | schnellere Bilder zum Testen (Standard sind 64 Samples mit Entrauschen) |

## Das Auto

| | |
|---|---|
| Länge | 4,80 m, mit Kennzeichen 4,90 m |
| Breite | 1,89 m über den Kotflügeln, mit Spiegeln 2,22 m |
| Höhe | Dach 1,48 m, Lichtbalken 1,61 m |
| Radstand und Spur | 2,84 m und 1,60 m |
| Räder | 245/45 R18: Radius 33,5 cm, Breite 23,5 cm, Felge 18 Zoll |
| Bodenfreiheit | 17 cm |
| Dreiecke | 133 357 |
| Materialien | 28 |
| Texturen | 3: Lack-Flakes (Normal), Reifen (Normal und Farbe) |
| UV-Karten | `UVMap` für alles, `UV_Flakes` für die Lack-Flakes (Würfelprojektion, 1 UV-Einheit = 1 m) |

Was alles dran ist:

- **Karosserie:** Kombi mit hoher, moderner Front, ausgestellten Kotflügeln und einer scharfen Charakterlinie an der Seite. Die Radläufe sitzen eng um die Räder.
- **Spaltmaße:** Sie sind echte Geometrie, 4,5 mm breit und 9 mm tief: vier Türen, Türunterkanten, Motorhaube, vordere und hintere Stoßfänger, Heckklappe und Tankdeckel.
- **Scheiben:** Sie sitzen 12 mm vertieft in einer schwarzen Hochglanz-Einfassung. Die hinteren Scheiben sind getönt. Durch alle Scheiben sieht man den Innenraum.
- **Beklebung:** unten Blau, darüber ein weißer Reflexstreifen mit geraden Kanten rund ums Auto, oben Silber. POLIZEI steht weiß auf den Vordertüren und blau auf Haube und Heckklappe.
- **Front:** Scheinwerfer mit Glasabdeckung, zwei Projektionslinsen, LED-Tagfahrlicht mit Haken und Blinkerleiste. Dazu ein Wabengrill mit Chromrahmen und zwei blauen Frontblitzern, ein unterer Lufteinlass mit Wabengitter und Nebelscheinwerfer.
- **Heck:** Rückleuchten mit rotem Glas, LED-Lichtleitern und Rückfahrlicht, Dachspoiler mit dritter Bremsleuchte, blaue Heckblitzer neben dem Kennzeichen, Reflektoren und Heckwischer.
- **Dach:** Dachreling, darauf ein Lichtbalken mit blauen Kappen über LED-Modulen und der Anzeige POLIZEI nach vorn und hinten. Dazu eine Haifischflossen-Antenne.
- **Anbauteile:** Spiegel mit Blinker, Türgriffe in Griffmulden, Scheibenwischer und Kennzeichen mit Halter und blauem Band (Fantasiekennzeichen „PL 2340“).
- **Innenraum:** Armaturenbrett mit Bildschirm, Lenkrad, Vordersitze mit Seitenwangen, Rückbank, Türverkleidungen und Dachhimmel.
- **Räder:** Reifen 245/45 R18. Vier Längsrillen sind Geometrie, Querrillen, Lamellen und die Flankenriffelung kommen aus der Normal-Karte. Die 18-Zoll-Felge hat fünf Doppelspeichen, eine tiefer liegende Nabe, ein Felgenhorn, Radmuttern und einen Nabendeckel. Dahinter sitzt die Bremsscheibe. Einen Bremssattel gibt es absichtlich nicht: Er hinge am Radknochen und würde sich im Spiel mitdrehen.

## Skelett

| Knochen | Kopf in Blender (m, X vorn, Y links) | Kopf in Unreal (cm, X vorn, Y rechts) | Daran hängt |
|---|---|---|---|
| `root` | 0 / 0 / 0 | 0 / 0 / 0 | Karosserie, Anbauteile, Lichtbalken, Innenraum |
| `wheel_fl` | 1,42 / 0,80 / 0,335 | 142 / −80 / 33,5 | Rad vorn links |
| `wheel_fr` | 1,42 / −0,80 / 0,335 | 142 / 80 / 33,5 | Rad vorn rechts |
| `wheel_rl` | −1,42 / 0,80 / 0,335 | −142 / −80 / 33,5 | Rad hinten links |
| `wheel_rr` | −1,42 / −0,80 / 0,335 | −142 / 80 / 33,5 | Rad hinten rechts |

- `root` liegt am Boden mittig zwischen den Achsen, die Radknochen sitzen genau in der Radmitte. Jede Ecke hängt an genau einem Knochen mit Gewicht 1. Die Räder drehen sich also starr mit ihrem Knochen.
- Das Auto schaut in Blender und in Unreal nach +X. Beim Import muss nichts gedreht werden.
- Der Armature-Knoten heißt `Armature`. Unreal macht aus einem Knoten mit diesem Namen normalerweise keinen eigenen Knochen. Falls doch ein Knochen `Armature` über `root` auftaucht, stört er nicht: Er hat keine Drehung und die Skalierung 1.

## Export

- **FBX für Unreal:**
  - Die Einheit ist Zentimeter, jeder Knoten hat die Skalierung 1. So entsteht nicht der bekannte Fehler mit Faktor 100 am Wurzelknochen, der Physik und Räder durcheinanderbringt.
  - Vielecke mit mehr als vier Ecken sind trianguliert. Normalen (mit harten Kanten) und Tangenten sind enthalten, die Texturen eingebettet, Animationen nicht.
- **GLB für alle anderen:**
  - glTF 2.0 in Metern mit +Y oben, das Skelett steckt als Skin drin.
  - Die Materialien kommen vollständig an: Metallic, Rauheit, Klarlack, Glas, Leuchten und die Texturen. Für die Flakes gilt die zweite UV-Karte mit der Kachelung 25.
- **Glas:** Alle Scheiben und Abdeckungen sind einfache Flächen ohne Dicke. Im Material stehen deshalb volle Durchlässigkeit, IOR 1,0 (keine Brechung) und eine Klarlackschicht für die Spiegelung. In Unreal nimmst du dafür ein Translucent-Material.
- Das Blaulicht leuchtet in beiden Dateien nicht. Es wird in der Engine geschaltet (siehe unten).

## In Unreal Engine 5 einrichten (Chaos Vehicles)

1. **Plugin:** Unter Plugins „Chaos Vehicles“ einschalten und den Editor neu starten. Am schnellsten testest du im Projekt-Template „Vehicle“: Dort ist alles schon verdrahtet, du tauschst nur Mesh, Anim Blueprint und Räder.
2. **Import:** `SK_Polizeiauto.fbx` in den Content Browser ziehen. Als Skeletal Mesh importieren, ein Physics Asset erstellen lassen, keine Animationen. Die Transformation bleibt unverändert: Drehung 0, Skalierung 1,0, keine Umrechnung der Einheiten.
3. **Physics Asset:** öffnen und die Körper der vier Radknochen löschen. Die Räder fragt Chaos selbst ab. Am Knochen `root` bleibt ein Körper. Gut funktionieren zwei Boxen:
   - Unterbau: Mitte (0, 0, 56) cm, Größe 480 × 189 × 78 cm
   - Aufbau: Mitte (−55, 0, 120) cm, Größe 350 × 150 × 55 cm
4. **Räder:** zwei Blueprints mit der Elternklasse `ChaosVehicleWheel` anlegen. Bei beiden gilt `Wheel Radius` 33,5 und `Wheel Width` 23,5.
   - `BP_Rad_Vorn`: Axle Type Front, `Affected By Steering` an, `Max Steer Angle` 40, `Affected By Handbrake` aus.
   - `BP_Rad_Hinten`: Axle Type Rear, `Affected By Steering` aus, `Affected By Handbrake` an.
   - `Affected By Engine` bei Heckantrieb hinten an und vorn aus, bei Allrad überall an.
5. **Anim Blueprint:** für das Skelett ein Anim Blueprint mit der Elternklasse `VehicleAnimationInstance` anlegen. Im AnimGraph so verbinden: `Mesh Space Ref Pose` → `Wheel Controller` (in älteren Versionen „Wheel Handler“) → `Component To Local` → `Output Pose`.
6. **Fahrzeug:** ein Blueprint mit der Elternklasse `WheeledVehiclePawn` anlegen.
   - Am Vehicle Mesh: `SK_Polizeiauto` als Mesh, das Anim Blueprint als Anim Class, Collision Preset `Vehicle`, `Simulate Physics` an.
   - An der Chaos Vehicle Movement Component unter `Wheel Setups` vier Einträge anlegen: `BP_Rad_Vorn` mit `wheel_fl` und `wheel_fr`, `BP_Rad_Hinten` mit `wheel_rl` und `wheel_rr`.
   - `Mass` auf etwa 1600 kg stellen. Wenn das Auto zum Kippen neigt: `Enable Center Of Mass Override` an und den Schwerpunkt auf etwa (0, 0, 50) cm legen. Der Ursprung liegt am Boden, das sind also 50 cm über der Straße.
   - Dazu Spring Arm und Kamera. Gas, Bremse, Lenkung und Handbremse gehen über `Set Throttle Input`, `Set Brake Input`, `Set Steering Input` und `Set Handbrake Input`.

### Materialien in Unreal

Über FBX kommen meist nur Grundfarbe, Leuchten, Transparenz und die Texturen an. Metallic, Rauheit und Klarlack stellst du am besten von Hand ein. Die Farben sind sRGB-Hexwerte, so wie sie der Farbwähler von Unreal annimmt.

| Material (Slot) | Wo | Farbe | Metallic | Rauheit | Sonst |
|---|---|---|---|---|---|
| `Lack_Silber` | Karosserie oben, Spiegel, Spoiler | `#C3C8CD` | 0,75 | 0,34 | Clear Coat 1, Clear Coat Roughness 0,015, Flakes (siehe unten) |
| `Lack_Blau` | Karosserie unten | `#0E3172` | 0,55 | 0,34 | wie Silber |
| `Reflexfolie_Weiss` | Streifen, Seitenschrift | `#EEF0F0` | 0 | 0,36 | Clear Coat 0,5 |
| `Folie_Blau` | Schrift auf Haube und Heck | `#0E3172` | 0 | 0,40 | |
| `Kunststoff_Schwarz` | Stoßfänger unten, Radkästen, Halter, Wischer | `#151617` | 0 | 0,62 | |
| `Hochglanz_Schwarz` | Scheibeneinfassungen, Grill, Lichtbalken | `#0B0C0D` | 0 | 0,10 | Clear Coat 0,8 |
| `Spalt` | Innenseite der Fugen | `#050505` | 0 | 0,90 | |
| `Glas` | vordere Scheiben | `#C4D2D0` | 0 | 0 | Translucent, Farbe als Tönung |
| `Glas_Getoent` | hintere Scheiben | `#5F6867` | 0 | 0 | Translucent, dunkler |
| `Chrom` | Grillrahmen, Griffe, Spiegelglas, Radmuttern | `#DCDEE0` | 1 | 0,05 | |
| `Scheinwerfer_Innen` | Gehäuse der Scheinwerfer | `#7D838A` | 0,9 | 0,25 | |
| `Scheinwerfer_Glas` | Abdeckungen, Linsen | `#F1F4F6` | 0 | 0 | Translucent |
| `Reflektor` | Ringe um die Linsen | `#E6E8EA` | 1 | 0,07 | |
| `Tagfahrlicht` | LED-Leisten, Anzeige im Lichtbalken | `#FFFFFF` | 0 | 0,2 | leuchtet weiß |
| `Ruecklicht_Glas` | Rückleuchten, Reflektoren | `#D0121A` | 0 | 0 | Translucent rot |
| `Ruecklicht_LED` | Lichtleiter, dritte Bremsleuchte | `#B0141A` | 0 | 0,3 | leuchtet rot, beim Bremsen heller |
| `Blaulicht` | LED-Module im Lichtbalken, Front- und Heckblitzer | `#1A4CFF` | 0 | 0,25 | blinkt, siehe unten |
| `Blaulicht_Kappe` | Kappen des Lichtbalkens | `#5B86FF` | 0 | 0 | Translucent blau |
| `Blinker` | Blinkerleisten in Scheinwerfern und Spiegeln | `#B88A55` | 0 | 0,3 | leuchtet orange beim Blinken |
| `Reifen` | Reifen | Textur | 0 | 0,88 | Normal-Textur |
| `Felge` | Felgen | `#C3C7CB` | 1 | 0,20 | |
| `Felge_Innen` | Felgenbett, Nabe | `#3B3E41` | 0,85 | 0,45 | |
| `Bremse` | Bremsscheiben | `#5A5C5E` | 0,85 | 0,38 | |
| `Dachreling` | Reling | `#9097A0` | 0,85 | 0,30 | |
| `Innenraum` | Armaturen, Verkleidungen | `#1E1F21` | 0 | 0,78 | |
| `Innenraum_Stoff` | Sitze, Dachhimmel | `#34363A` | 0 | 0,95 | |
| `Kennzeichen` | Kennzeichen | `#F2F2F0` | 0 | 0,35 | |
| `Kennzeichen_Band` | blaues Band | `#1C3FA0` | 0 | 0,35 | |

**Lack-Flakes:** `T_Lack_Flakes_N` ist eine kachelbare Normal-Karte. Nimm dafür den Knoten `TextureCoordinate` mit Coordinate Index 1 (die Karte `UV_Flakes`) und der Kachelung 25. Schwäche die Normalen auf etwa 30 % ab und gib sie nur der Lackschicht unter dem Klarlack. In Unreal heißt der Eingang `Clear Coat Bottom Normal`, er muss in den Projekteinstellungen freigeschaltet sein. Ohne diesen Eingang lässt du die Flakes einfach weg.

**Blaulicht mit Doppelblitz, links und rechts im Wechsel:**

- Parameter anlegen: `Farbe` (0,02 / 0,1 / 1), `Staerke` (etwa 50), `Takt` (etwa 1,3) und `An` (0 oder 1).
- Die Seite holst du so: `Absolute World Position` → `Transform Position` nach Local Space, davon Kanal G. Die linke Fahrzeugseite liegt in Unreal bei Y < 0. Daraus wird über einen `If`-Knoten eine Phase: 0,5 links, 0 rechts.
- `Time × Takt + Phase` geht in einen `Custom`-Knoten mit dem Eingang `T`:

  ```hlsl
  float t = frac(T);
  return (t < 0.08 || (t > 0.16 && t < 0.24)) ? 1.0 : 0.0;
  ```

- Emissive Color = `Farbe × Staerke × An × Custom`.
- Im Fahrzeug-Blueprint legst du für den Slot `Blaulicht` eine Dynamic Material Instance an. Mit `Set Scalar Parameter Value` auf `An` schaltest du das Licht ein und aus.
- Rücklicht, Tagfahrlicht und Blinker gehen genauso, der Blinker mit etwa 1,5 Hz und ohne Doppelblitz. Als Richtwert für Emissive: Tagfahrlicht 20, Rücklicht 4 und beim Bremsen 30. Die passenden Werte hängen von der Belichtung deiner Szene ab.

## Leistung

- 133 357 Dreiecke und 28 Materialslots passen gut für ein Spielerauto oder eine Zwischensequenz. Jeder Slot kostet einen eigenen Draw Call, die durchsichtigen Slots etwas mehr.
- Für viele Autos gleichzeitig, etwa als Verkehr, im Skeletal-Mesh-Editor LODs erzeugen lassen, zum Beispiel mit 50, 25 und 10 % der Dreiecke. Für weit entfernte Stufen kannst du Innenraum und Leuchten-Innenleben weglassen und einfarbige Materialien zusammenfassen.
- Die UV-Karte `UVMap` ist automatisch ausgelegt (Smart UV Project, Inseln ohne Überlappung). Nur die Reifen liegen gekachelt darüber, weil ihre Profiltextur sich um den Umfang wiederholt. Für Schmutz- oder Kratzermasken reicht das. Für eigene Texturen legst du die Karte am besten neu aus.
