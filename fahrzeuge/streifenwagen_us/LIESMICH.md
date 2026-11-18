# Amerikanischer Streifenwagen für Spiele

Ein fahrbarer US-Streifenwagen (Patrol Car) für Unreal Engine 5 (Chaos Vehicles), als glTF auch für Godot, Unity oder three.js. Das Auto ist ein eigenes Limousinen-Design und keiner echten Marke nachgebaut. Die Lackierung folgt dem klassischen amerikanischen Schwarz-Weiß-Schema. Abzeichen, Einheitsnummer und Kennzeichen sind ausgedacht, es gibt kein echtes Department. Modell, Skelett, Materialien und Texturen entstehen komplett per Skript in Blender. Es stecken keine fremden Assets drin.

Das Auto ist kein Neuwagen, sondern ein Streifenwagen im Dienst: Straßenschmutz an Schwellern und Radläufen, Staub, Regenstreifen, Bremsstaub auf den Felgen, einzelne Steinschläge vorn, abgeschabte Kanten am Rammschutzbügel und feine Waschanlagen-Kratzer im Klarlack. Diese Gebrauchsspuren sind in die Texturen gebacken. Bilder, FBX und GLB zeigen also dasselbe Auto.

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
  - `export/Texturen/` mit den acht Texturen als PNG (siehe „Texturen“)
  - `streifenwagen_us.blend` mit Auto und Skelett in Metern, dazu die Nachtszene
  - `streifenwagen_us_vorne.png`, `_hinten`, `_seite`, `_oben`, `_detail`, `_verfolger`, `_strasse` und `_nacht`
- `pruefe_export.py` schreibt am Ende „ALLES OK“ oder eine Liste der Fehler.
- Modell, Texturen, das Backen der Gebrauchsspuren und der Export brauchen auf einem Rechner mit vier Kernen knapp 4 Minuten. Die acht Bilder in 1920 × 1080 mit Cycles auf der CPU dauern etwa 30 Minuten. Mit `SHOTS=` fallen sie weg.

Schalter für schnelle Läufe (Umgebungsvariablen):

| Schalter | Wirkung |
|---|---|
| `SHOTS=` (leer) | keine Bilder. `SHOTS=vorne,nacht` rendert nur diese beiden |
| `SAMPLES=16`, `RES=960x540` | schnellere Bilder zum Testen (Standard sind 64 Samples mit Entrauschen) |
| `ATLAS=2048` | Gebrauchsspuren in halber Auflösung backen, etwa viermal schneller (Standard 4096) |

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
| Dreiecke | rund 250 000 |
| Materialien | 41 |
| Texturen | 8, siehe unten |
| UV-Karten | `UVMap` als gemeinsamer Atlas (etwa 2 mm je Texel auf der Karosserie), `UV_Flakes` für kachelnde Lacktexturen (Würfelprojektion, 1 UV-Einheit = 1 m) |

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
  - Wie bei echten Lichtbalken stecken unter den Hauben LED-Module: Jede LED sitzt in einem eigenen Reflektorbecher aus Chrom.
  - Dazu rot-blaue Blitzer mit denselben LED-Modulen im Grill, auf dem Rammschutzbügel, im hinteren Stoßfänger und hinter der Heckscheibe.
- **Front:**
  - Rammschutzbügel (Push Bar) mit Gummiauflagen, dahinter der Sirenenlautsprecher
  - Scheinwerfer mit dunklem Gehäuse, zwei Projektionsmodulen in Reflektorschalen aus Chrom, flachem LED-Lichtleiter als Tagfahrlicht und einem Blinker aus Einzel-LEDs vor einem bernsteinfarbenen Reflektor. Die Gläser sind schwarz eingefasst.
  - Wabengrill, Nebelscheinwerfer mit Chromschale
  - gelbe Seitenmarkierungsleuchten vorn und rote hinten, wie in den USA vorgeschrieben
- **Suchscheinwerfer** an der A-Säule auf der Fahrerseite.
- **Heck:** Rückleuchten mit facettiertem Reflektor hinter dem roten Glas (das typische Funkeln), LED-Lichtleiter als C, eine Reihe Einzel-LEDs und ein Rückfahrlicht mit Chromschale. Dazu das Kennzeichen in einer Mulde, Reflektoren und zwei Endrohre.
- **Dach:** drei Antennen.
- **Innenraum:**
  - Vordersitze mit Seitenwangen: Mitte Stoff, Wangen Kunstleder, Kopfstützen auf Chromstangen, Gurtschlösser und Gurte an der B-Säule
  - Armaturenbrett mit Defroster-Schlitzen, Instrumentenhutze und zwei Rundinstrumenten, Bildschirm, eckigen und runden Lüftungsdüsen, Klimareglern
  - Lenkrad mit Prallpolster, Lenksäule und Hebeln
  - Polizeitechnik auf der Mittelkonsole: Funk-Bedienteil mit Display, Sirenen- und Lichtsteuerung mit farbigen Tasten, Mikrofon mit Spiralkabel, robuster Laptop mit Tastatur auf einem Schwenkhalter
  - Innenspiegel, Sonnenblenden, Innenleuchte, Fußmatten, Türverkleidungen mit Armlehnen, Griffen und Lautsprechern
  - Trenngitter: unten Stahl, oben eine Scheibe mit Schiebefenster
  - hinten eine harte, abwaschbare Rückbank mit zwei Sitzmulden, wie in US-Streifenwagen üblich
- **Räder:**
  - Reifen 245/55 R18 mit Profil: Längsrillen als Geometrie, Querrillen und Lamellen aus der Normal-Karte. Auf der Außenflanke steht erhabene Schrift mit allgemeinen Angaben (Größe „245/55 R18 98V“, „M+S“, „ALL SEASON“, „TUBELESS“, „RADIAL“, keine Marke), auf beiden Seiten des Autos lesbar.
  - gepresste schwarze Stahlfelge mit Versteifungssicke und sechs Lüftungslöchern, verchromter Mittelkappe und sechs Radmuttern mit Kegelsitz, dazu das Ventil
  - innenbelüftete Bremsscheibe mit Kühlrippen
  - Einen Bremssattel gibt es absichtlich nicht: Er hinge am Radknochen und würde sich im Spiel mitdrehen.

## Gebrauchsspuren und Texturen

Das Skript backt mit Cycles Masken in den gemeinsamen UV-Atlas (`UVMap`) und mischt daraus drei Texturen, die sich alle Materialien teilen (außer Glas und Reifen):

- Straßenschmutz: unten am stärksten, um und hinter den Radläufen, am Heck (Sog) und vorn unten
- Staub auf waagrechten Flächen, Regenstreifen unter den Fenstern, Schmutz in Ritzen und Fugen
- Bremsstaub auf den Felgen, zur Mitte und nach innen stärker
- einzelne Steinschläge vorn und hinter den Vorderrädern
- abgeschabte Kanten, vor allem am Rammschutzbügel (blankes Metall)
- Umgebungsverdeckung (Ambient Occlusion) für Engines, die sie nutzen

Wo Schmutz liegt, wird die Oberfläche rauer und der Klarlack verschwindet. Der Innenraum bekommt im Atlas weniger Platz, Glas und Unterboden fast keinen. So bleibt für die sichtbare Karosserie die meiste Auflösung.

| Textur | Größe | Inhalt | UV-Karte |
|---|---|---|---|
| `T_Streifenwagen_US_BaseColor` | 4096² | Farbe mit Schmutz und Abrieb (sRGB) | `UVMap` |
| `T_Streifenwagen_US_ORM` | 4096² | R = Umgebungsverdeckung, G = Rauheit, B = Metall (linear) | `UVMap` |
| `T_Streifenwagen_US_Klarlack` | 2048² | Stärke des Klarlacks (linear) | `UVMap` |
| `T_Lack_Kratzer_N` | 2048², kachelbar | Normalen des Klarlacks: feine Kratzer in allen Richtungen, Kringel aus der Waschanlage, einige längere Kratzer, leichte Orangenhaut | `UV_Flakes`, Kachelung 1,25 |
| `T_Lack_Flakes_N` | 512², kachelbar | Metallic-Flakes im Grundlack | `UV_Flakes`, Kachelung 25 |
| `T_Reflektor_N` | 256², kachelbar | Pyramidenfacetten der Rückleuchten-Reflektoren und Seitenleuchten | `UV_Flakes`, Kachelung 31 bzw. 47 |
| `T_Reifen_N` / `T_Reifen_BC` | 8192 × 1024 | Profil, Flankenschrift, Staub; einmal um den Umfang | `UVMap` (eigene Abwicklung der Reifen) |

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
  - Die Materialien kommen vollständig an: Farbe, Rauheit, Metall und Umgebungsverdeckung aus dem Atlas, Klarlack mit eigener Stärke-Textur und Kratzer-Normalen, Glas, Leuchten. Flakes, Kratzer und Facetten nutzen die zweite UV-Karte mit ihrer Kachelung (KHR_texture_transform).
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

Über FBX kommen meist nur Grundfarbe, Leuchten und Transparenz an. Am einfachsten baust du ein Master-Material und machst für jeden Slot eine Material Instance davon:

- Shading Model `Clear Coat`
- `Base Color` = `T_Streifenwagen_US_BaseColor` (Koordinate 0)
- `T_Streifenwagen_US_ORM` (Koordinate 0, Compression „Masks“, sRGB aus): R → `Ambient Occlusion`, G → `Roughness`, B → `Metallic`
- `Clear Coat` = `T_Streifenwagen_US_Klarlack` (Koordinate 0, sRGB aus). Die Textur enthält schon die Stärke je Material und ist dort, wo Schmutz liegt, schwächer.
- `Clear Coat Roughness` = Parameter je Slot (siehe Tabelle, sonst egal)
- `Normal` = `T_Lack_Kratzer_N` mit `TextureCoordinate` Index 1 und Kachelung 1,25, Stärke etwa 0,75. Beim Clear-Coat-Modell wirkt `Normal` auf den Klarlack. Nur für die beiden Lacke, sonst die flache Normale (0, 0, 1).
- Flakes, optional: `T_Lack_Flakes_N` mit Index 1 und Kachelung 25 in `Clear Coat Bottom Normal` (muss in den Projekteinstellungen freigeschaltet sein), Stärke 30 % beim schwarzen und 10 % beim weißen Lack.

Farbe, Rauheit und Metall stehen für alle undurchsichtigen Materialien schon im Atlas. Eigene Werte brauchen nur diese Slots:

| Material (Slot) | Was gilt |
|---|---|
| `Lack_Schwarz`, `Lack_Weiss` | Klarlack-Rauheit 0,012, Kratzer und Flakes wie oben |
| `Hochglanz_Schwarz`, `Reflexfolie_Weiss`, `Felge_Schwarz` | Klarlack-Rauheit 0,02 / 0,04 / 0,05 |
| `Innenraum_Kunstleder` | Klarlack-Rauheit 0,3 |
| `Seitenleuchte_Gelb`, `Seitenleuchte_Rot` | Klarlack-Rauheit 0,01, `T_Reflektor_N` mit Index 1 und Kachelung 47 als Normale (Stärke 0,6) |
| `Ruecklicht_Reflektor` | `T_Reflektor_N` mit Index 1 und Kachelung 31 als Normale |
| `Glas` / `Glas_Getoent` | Translucent, Tönung `#C4D2D0` / `#4F5857`, ohne Brechung |
| `Scheinwerfer_Glas`, `Ruecklicht_Glas`, `Lichtbalken_Rot` / `_Blau` / `_Klar` | Translucent, Tönung `#F1F4F6`, `#D0121A`, `#FF6B6B` / `#6A8FFF` / `#EEF2F4` |
| `Reifen` | Standard-Shading, `T_Reifen_BC` und `T_Reifen_N` (Koordinate 0), Rauheit 0,88 |
| `Tagfahrlicht`, `Ruecklicht_LED`, `Rotlicht`, `Blaulicht`, `Blinker`, `Bildschirm` | Emissive, siehe nächster Abschnitt |

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

- Rund 250 000 Dreiecke und 41 Materialslots passen für ein Spielerauto oder eine Zwischensequenz. Jeder Slot kostet einen eigenen Draw Call, die durchsichtigen Slots etwas mehr. Weil sich fast alle Slots dieselben drei Atlas-Texturen teilen, kosten die vielen Slots kaum zusätzlichen Texturspeicher.
- Für viele Autos gleichzeitig, etwa als Verkehr, im Skeletal-Mesh-Editor LODs erzeugen lassen, zum Beispiel mit 50, 25 und 10 % der Dreiecke. Für weit entfernte Stufen kannst du Innenraum, Leuchten-Innenleben und Antennen weglassen und die Atlas-Materialien zu einem zusammenfassen. Die Texturen kannst du in Unreal mit `Maximum Texture Size` auf 2048 begrenzen.
- Die UV-Karte `UVMap` ist ein automatisch ausgelegter Atlas ohne Überlappung (Smart UV Project, danach nach Wichtigkeit skaliert und neu gepackt). Nur die Reifen liegen mit ihrer eigenen Abwicklung darüber, weil sie eigene Texturen haben.
