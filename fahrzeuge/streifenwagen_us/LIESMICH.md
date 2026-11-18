# Amerikanischer Streifenwagen für Spiele

Ein fahrbarer US-Streifenwagen (Patrol Car) für Unreal Engine 5 (Chaos Vehicles), als glTF auch für Godot, Unity oder three.js. Das Auto ist ein eigenes Limousinen-Design und keiner echten Marke nachgebaut. Die Lackierung folgt dem klassischen amerikanischen Schwarz-Weiß-Schema. Abzeichen, Einheitsnummer und Kennzeichen sind ausgedacht, es gibt kein echtes Department. Modell, Skelett, Materialien und Texturen entstehen komplett per Skript in Blender. Es stecken keine fremden Assets drin.

## Dateien

| Datei | Zweck |
|---|---|
| `streifenwagen_us.py` | erzeugt das Auto, die Texturen, das Skelett, FBX und GLB, die `.blend` und acht Vorschaubilder |
| `pruefe_export.py` | prüft die beiden Exporte unabhängig: Einheit und Skalierung der FBX, Knochen, Gewichte, Maße |

## Erzeugen und prüfen

```
blender -b -P streifenwagen_us.py
blender -b -P pruefe_export.py -- export SK_Streifenwagen_US 2.96 1.64 0.364 0.245
```

- Getestet mit Blender 4.5 LTS. Das Skript setzt Blender auf Werkseinstellungen zurück. Starte es deshalb nicht in einem offenen Projekt.
- Die Zahlen hinter dem Prüfer sind Radstand, Spur, Radradius und Reifenbreite in Metern.
- Neben dem Skript entstehen:
  - `export/SK_Streifenwagen_US.fbx` für Unreal, in Zentimetern, Texturen eingebettet
  - `export/SK_Streifenwagen_US.glb` für alle anderen Engines, in Metern, Texturen eingebettet
  - `export/Texturen/` mit den drei Texturen als PNG
  - `streifenwagen_us.blend` mit Auto und Skelett in Metern, dazu die Nachtszene
  - `streifenwagen_us_vorne.png`, `_hinten`, `_seite`, `_oben`, `_detail`, `_verfolger`, `_strasse` und `_nacht`
- `pruefe_export.py` schreibt am Ende „ALLES OK“ oder eine Liste der Fehler.
- Modell, Texturen und Export brauchen etwa 20 Sekunden. Die acht Bilder in 1920 × 1080 mit Cycles auf der CPU dauern auf einem Rechner mit vier Kernen etwa 28 Minuten. Mit `SHOTS=` fallen sie weg.

Schalter für schnelle Läufe (Umgebungsvariablen):

| Schalter | Wirkung |
|---|---|
| `SHOTS=` (leer) | keine Bilder. `SHOTS=vorne,nacht` rendert nur diese beiden |
| `SAMPLES=16`, `RES=960x540` | schnellere Bilder zum Testen (Standard sind 64 Samples mit Entrauschen) |

## Vorschaubilder

| Bild | Szene |
|---|---|
| `_vorne`, `_hinten`, `_seite`, `_oben` | Fotostudio mit großen Softboxen, die sich im Lack spiegeln |
| `_detail` | Nahaufnahme von Rammschutzbügel, Grill und Scheinwerfer |
| `_verfolger` | Tagesszene aus der Verfolgerkamera, wie in einem Fahr- oder Polizeispiel |
| `_strasse` | dieselbe Tagesszene auf Straßenhöhe |
| `_nacht` | nasse Straße bei Nacht, Rot- und Blaulicht an |

Die Tagesszene ist eine eigene amerikanische Innenstadtstraße und kein Nachbau eines bestimmten Spiels. Dazu gehören:

- zwei Fahrspuren mit gelber Doppellinie, Parkstreifen, Zebrastreifen und Haltelinie
- Bordsteine und Gehwege mit Fugen
- Häuserzeilen aus Ziegel, Putz und Beton mit Läden, Markisen und Schildern
- Laternen, eine Ampel mit Straßenschild, ein Hydrant, Parkuhren und Kanaldeckel
- drei geparkte Zivilautos aus derselben Karosserie, einfarbig und ohne Polizeiausstattung

Himmel und Sonne sind physikalisch berechnet. Die Szene dient nur den Bildern und ist nicht Teil des Exports.

## Das Auto

| | |
|---|---|
| Länge | 5,10 m, mit Rammschutzbügel und Endrohren 5,40 m |
| Breite | 1,93 m über den Kotflügeln, mit Spiegeln 2,34 m |
| Höhe | Dach 1,48 m, Lichtbalken 1,63 m, Antennen 1,80 m |
| Radstand und Spur | 2,96 m und 1,64 m |
| Räder | 245/55 R18: Radius 36,4 cm, Breite 24,5 cm, schwarze 18-Zoll-Stahlfelge |
| Bodenfreiheit | 18 cm |
| Dreiecke | rund 148 000 |
| Materialien | 35 |
| Texturen | 3: Lack-Flakes (Normal), Reifen (Normal und Farbe) |
| UV-Karten | `UVMap` für alles, `UV_Flakes` für die Lack-Flakes (Würfelprojektion, 1 UV-Einheit = 1 m) |

Was alles dran ist:

- **Karosserie:** viertürige Limousine mit langer Haube, Stufenheck, ausgestellten Kotflügeln und Charakterlinie. Spaltmaße sind echte Geometrie: vier Türen, Türunterkanten, Motorhaube, Kofferraumdeckel, Stoßfänger und Tankdeckel. Die Scheiben sitzen vertieft in einer schwarzen Einfassung, die hinteren sind getönt.
- **Lackierung:** klassisch Schwarz-Weiß. Türen, Säulen und Dach sind weiß, Kotflügel, Haube, Kofferraum und Stoßfänger schwarz.
- **Beschriftung:**
  - ein eigenes Stern-Abzeichen auf den Vordertüren: goldener Ring, blaue Scheibe, sechszackiger Stern
  - POLICE auf den hinteren Türen und am Heck
  - die Einheitsnummer 27 groß auf dem Dach, von hinten lesbar (so wie für Hubschrauber), und klein an den hinteren Kotflügeln
  - ein US-Kennzeichen „EXEMPT / PD 2740“
- **Sondersignal:**
  - Lichtbalken: links (Fahrerseite) rot, rechts (Beifahrerseite) blau. In der Mitte sitzen weiße Arbeitslichter nach vorn und ein gelbes Warnlicht nach hinten, an den Enden weiße Seitenlichter.
  - Dazu rot-blaue Blitzer im Grill, auf dem Rammschutzbügel, im hinteren Stoßfänger und hinter der Heckscheibe.
- **Front:**
  - Rammschutzbügel (Push Bar) mit Gummiauflagen, dahinter der Sirenenlautsprecher
  - Scheinwerfer mit Projektionslinsen und LED-Tagfahrlicht, Wabengrill, Nebelscheinwerfer
- **Suchscheinwerfer** an der A-Säule auf der Fahrerseite.
- **Heck:** Rückleuchten mit LED-Lichtleitern und Rückfahrlicht, Kennzeichen in einer Mulde, Reflektoren und zwei Endrohre.
- **Dach:** drei Antennen.
- **Innenraum:**
  - vorn: Armaturenbrett mit Bildschirm, Lenkrad, Laptop auf einer Halterung und Vordersitze
  - dahinter ein Trenngitter: unten Stahl, oben eine Scheibe
  - hinten: Rückbank, Türverkleidungen, Dachhimmel und Hutablage
- **Räder:**
  - Reifen 245/55 R18 mit Profil: Längsrillen als Geometrie, Querrillen und Flanke aus der Normal-Karte
  - schwarze Stahlfelge mit sechs Lüftungslöchern, verchromter Mittelkappe und sechs Radmuttern, dahinter die Bremsscheibe
  - Einen Bremssattel gibt es absichtlich nicht: Er hinge am Radknochen und würde sich im Spiel mitdrehen.

## Skelett

| Knochen | Kopf in Blender (m, X vorn, Y links) | Kopf in Unreal (cm, X vorn, Y rechts) | Daran hängt |
|---|---|---|---|
| `root` | 0 / 0 / 0 | 0 / 0 / 0 | Karosserie, Anbauteile, Lichtbalken, Innenraum |
| `wheel_fl` | 1,48 / 0,82 / 0,364 | 148 / −82 / 36,4 | Rad vorn links |
| `wheel_fr` | 1,48 / −0,82 / 0,364 | 148 / 82 / 36,4 | Rad vorn rechts |
| `wheel_rl` | −1,48 / 0,82 / 0,364 | −148 / −82 / 36,4 | Rad hinten links |
| `wheel_rr` | −1,48 / −0,82 / 0,364 | −148 / 82 / 36,4 | Rad hinten rechts |

- `root` liegt am Boden mittig zwischen den Achsen, die Radknochen sitzen genau in der Radmitte. Jede Ecke hängt an genau einem Knochen mit Gewicht 1. Die Räder drehen sich also starr mit ihrem Knochen.
- Das Auto schaut in Blender und in Unreal nach +X. Beim Import muss nichts gedreht werden.
- Der Armature-Knoten heißt `Armature`. Unreal macht aus einem Knoten mit diesem Namen normalerweise keinen eigenen Knochen. Falls doch ein Knochen `Armature` über `root` auftaucht, stört er nicht: Er hat keine Drehung und die Skalierung 1.

## Export

- **FBX für Unreal:**
  - Die Einheit ist Zentimeter, jeder Knoten hat die Skalierung 1. So entsteht nicht der bekannte Fehler mit Faktor 100 am Wurzelknochen.
  - Vielecke mit mehr als vier Ecken sind trianguliert. Normalen (mit harten Kanten) und Tangenten sind enthalten, die Texturen eingebettet, Animationen nicht.
- **GLB für alle anderen:**
  - glTF 2.0 in Metern mit +Y oben, das Skelett steckt als Skin drin.
  - Die Materialien kommen vollständig an: Metallic, Rauheit, Klarlack, Glas, Leuchten und die Texturen. Für die Flakes gilt die zweite UV-Karte mit der Kachelung 25.
- **Glas:** Alle Scheiben und Abdeckungen sind einfache Flächen ohne Dicke. Im Material stehen deshalb volle Durchlässigkeit, IOR 1,0 (keine Brechung) und eine Klarlackschicht für die Spiegelung. In Unreal nimmst du dafür ein Translucent-Material.
- Rot- und Blaulicht leuchten in beiden Dateien nicht. Sie werden in der Engine geschaltet (siehe unten).

## In Unreal Engine 5 einrichten (Chaos Vehicles)

1. **Plugin:** Unter Plugins „Chaos Vehicles“ einschalten und den Editor neu starten. Am schnellsten testest du im Projekt-Template „Vehicle“: Dort ist alles schon verdrahtet, du tauschst nur Mesh, Anim Blueprint und Räder.
2. **Import:** `SK_Streifenwagen_US.fbx` in den Content Browser ziehen. Als Skeletal Mesh importieren, ein Physics Asset erstellen lassen, keine Animationen. Die Transformation bleibt unverändert: Drehung 0, Skalierung 1,0, keine Umrechnung der Einheiten.
3. **Physics Asset:** öffnen und die Körper der vier Radknochen löschen. Die Räder fragt Chaos selbst ab. Am Knochen `root` bleibt ein Körper. Gut funktionieren zwei Boxen:
   - Unterbau mit Rammschutz: Mitte (8, 0, 59) cm, Größe 532 × 193 × 80 cm
   - Fahrgastzelle: Mitte (−25, 0, 124) cm, Größe 230 × 150 × 48 cm
4. **Räder:** zwei Blueprints mit der Elternklasse `ChaosVehicleWheel` anlegen. Bei beiden gilt `Wheel Radius` 36,4 und `Wheel Width` 24,5.
   - `BP_Rad_Vorn`: Axle Type Front, `Affected By Steering` an, `Max Steer Angle` 40, `Affected By Handbrake` aus, `Affected By Engine` aus.
   - `BP_Rad_Hinten`: Axle Type Rear, `Affected By Steering` aus, `Affected By Handbrake` an, `Affected By Engine` an (Heckantrieb, wie bei den klassischen US-Streifenwagen).
5. **Anim Blueprint:** für das Skelett ein Anim Blueprint mit der Elternklasse `VehicleAnimationInstance` anlegen. Im AnimGraph so verbinden: `Mesh Space Ref Pose` → `Wheel Controller` (in älteren Versionen „Wheel Handler“) → `Component To Local` → `Output Pose`.
6. **Fahrzeug:** ein Blueprint mit der Elternklasse `WheeledVehiclePawn` anlegen.
   - Am Vehicle Mesh: `SK_Streifenwagen_US` als Mesh, das Anim Blueprint als Anim Class, Collision Preset `Vehicle`, `Simulate Physics` an.
   - An der Chaos Vehicle Movement Component unter `Wheel Setups` vier Einträge anlegen: `BP_Rad_Vorn` mit `wheel_fl` und `wheel_fr`, `BP_Rad_Hinten` mit `wheel_rl` und `wheel_rr`.
   - `Mass` auf etwa 1900 kg stellen. Wenn das Auto zum Kippen neigt: `Enable Center Of Mass Override` an und den Schwerpunkt auf etwa (0, 0, 52) cm legen. Der Ursprung liegt am Boden.
   - Dazu Spring Arm und Kamera. Gas, Bremse, Lenkung und Handbremse gehen über `Set Throttle Input`, `Set Brake Input`, `Set Steering Input` und `Set Handbrake Input`.

### Materialien in Unreal

Über FBX kommen meist nur Grundfarbe, Leuchten, Transparenz und die Texturen an. Metallic, Rauheit und Klarlack stellst du am besten von Hand ein. Die Farben sind sRGB-Hexwerte, so wie sie der Farbwähler von Unreal annimmt.

| Material (Slot) | Wo | Farbe | Metallic | Rauheit | Sonst |
|---|---|---|---|---|---|
| `Lack_Schwarz` | Kotflügel, Haube, Kofferraum, Spiegel | `#0C0D0F` | 0,4 | 0,32 | Clear Coat 1, Clear Coat Roughness 0,012, Flakes (siehe unten) |
| `Lack_Weiss` | Türen, Säulen, Dach | `#EEF0F1` | 0 | 0,32 | Clear Coat wie oben, Flakes schwächer |
| `Kunststoff_Schwarz` | Stoßfänger unten, Radkästen, Halter, Wischer | `#151617` | 0 | 0,62 | |
| `Hochglanz_Schwarz` | Scheibeneinfassungen, Grill, Lichtbalken | `#0B0C0D` | 0 | 0,10 | Clear Coat 0,8 |
| `Spalt` | Innenseite der Fugen | `#050505` | 0 | 0,90 | |
| `Glas` / `Glas_Getoent` | vordere / hintere Scheiben | `#C4D2D0` / `#4F5857` | 0 | 0 | Translucent, Farbe als Tönung |
| `Chrom` | Griffe, Spiegelglas, Suchscheinwerfer, Mittelkappen, Endrohre | `#DCDEE0` | 1 | 0,05 | |
| `Scheinwerfer_Innen`, `Reflektor` | Innenleben der Scheinwerfer | `#7D838A`, `#E6E8EA` | 0,9 / 1 | 0,25 / 0,07 | |
| `Scheinwerfer_Glas` | Abdeckungen, Linsen | `#F1F4F6` | 0 | 0 | Translucent |
| `Tagfahrlicht` | LED-Leisten, Arbeits- und Seitenlichter im Lichtbalken | `#FFFFFF` | 0 | 0,2 | leuchtet weiß |
| `Ruecklicht_Glas` / `Ruecklicht_LED` | Rückleuchten | `#D0121A` / `#B0141A` | 0 | 0 / 0,3 | Glas translucent, LED leuchtet rot |
| `Rotlicht` / `Blaulicht` | LED-Module der Sondersignale | `#D0141C` / `#1A4CFF` | 0 | 0,25 | blinken, siehe unten |
| `Lichtbalken_Rot` / `_Blau` / `_Klar` | Kappen des Lichtbalkens | `#FF6B6B` / `#6A8FFF` / `#EEF2F4` | 0 | 0 | Translucent |
| `Blinker` | Blinkerleisten, gelbes Warnlicht | `#B88A55` | 0 | 0,3 | leuchtet orange beim Blinken |
| `Folie_Schwarz` / `Reflexfolie_Weiss` | Schriften und Nummern | `#0A0A0B` / `#EEF0F0` | 0 | 0,35 | |
| `Abzeichen_Gold` / `Abzeichen_Blau` | Stern-Abzeichen | `#D4A21E` / `#14254F` | 1 / 0 | 0,3 / 0,4 | |
| `Rammschutz` | Rammschutzbügel, Halter | `#111213` | 0,6 | 0,45 | |
| `Reifen` | Reifen | Textur | 0 | 0,88 | Normal-Textur |
| `Felge_Schwarz` / `Felge_Innen` | Stahlfelgen | `#18191A` / `#2A2C2E` | 0,5 / 0,6 | 0,35 / 0,5 | Felge mit Clear Coat 0,6 |
| `Bremse` | Bremsscheiben | `#5A5C5E` | 0,85 | 0,38 | |
| `Innenraum` / `Innenraum_Stoff` | Armaturen, Sitze, Himmel | `#1E1F21` / `#34363A` | 0 | 0,78 / 0,95 | |
| `Trenngitter` | Trenngitter, Laptop-Halter | `#1A1B1C` | 0,7 | 0,4 | |
| `Bildschirm` | Laptop | `#0D1520` | 0 | 0,15 | leuchtet leicht blau, wenn an |
| `Kennzeichen` / `Kennzeichen_Schrift` | Kennzeichen | `#F4F4F0` / `#1C2F7A` | 0 | 0,35 | |

**Lack-Flakes:** `T_Lack_Flakes_N` ist eine kachelbare Normal-Karte. Nimm dafür den Knoten `TextureCoordinate` mit Coordinate Index 1 (die Karte `UV_Flakes`) und der Kachelung 25. Schwäche die Normalen auf etwa 30 % ab (beim weißen Lack 10 %) und gib sie nur der Lackschicht unter dem Klarlack. In Unreal heißt der Eingang `Clear Coat Bottom Normal`, er muss in den Projekteinstellungen freigeschaltet sein. Ohne diesen Eingang lässt du die Flakes einfach weg.

**Rot und Blau im Wechsel blinken lassen:** Rot und Blau sind eigene Slots. Beide bekommen dasselbe Material, nur mit anderer Farbe und um eine halbe Periode versetzt.

- Parameter anlegen: `Farbe`, `Staerke` (etwa 50), `Takt` (etwa 1,3), `Phase` (Rot 0, Blau 0,5) und `An` (0 oder 1).
- `Time × Takt + Phase` geht in einen `Custom`-Knoten mit dem Eingang `T`, das ergibt einen Doppelblitz:

  ```hlsl
  float t = frac(T);
  return (t < 0.08 || (t > 0.16 && t < 0.24)) ? 1.0 : 0.0;
  ```

- Emissive Color = `Farbe × Staerke × An × Custom`.
- Im Fahrzeug-Blueprint legst du für die Slots `Rotlicht` und `Blaulicht` je eine Dynamic Material Instance an. Mit `Set Scalar Parameter Value` auf `An` schaltest du das Licht ein und aus.
- Rücklicht, Tagfahrlicht, Blinker und Bildschirm gehen genauso, nur ohne Blinken bzw. mit etwa 1,5 Hz beim Blinker. Als Richtwert für Emissive: Tagfahrlicht 20, Rücklicht 4 und beim Bremsen 30, Bildschirm 1. Die passenden Werte hängen von der Belichtung deiner Szene ab.

## Leistung

- Rund 148 000 Dreiecke und 35 Materialslots passen für ein Spielerauto oder eine Zwischensequenz. Jeder Slot kostet einen eigenen Draw Call, die durchsichtigen Slots etwas mehr.
- Für viele Autos gleichzeitig, etwa als Verkehr, im Skeletal-Mesh-Editor LODs erzeugen lassen, zum Beispiel mit 50, 25 und 10 % der Dreiecke. Für weit entfernte Stufen kannst du Innenraum, Leuchten-Innenleben und Antennen weglassen und einfarbige Materialien zusammenfassen.
- Die UV-Karte `UVMap` ist automatisch ausgelegt (Smart UV Project, Inseln ohne Überlappung). Nur die Reifen liegen gekachelt darüber, weil ihre Profiltextur sich um den Umfang wiederholt. Für Schmutz- oder Kratzermasken reicht das. Für eigene Texturen legst du die Karte am besten neu aus.
