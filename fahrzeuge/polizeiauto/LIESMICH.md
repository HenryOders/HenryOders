# Streifenwagen für Spiele

Ein fahrbarer Streifenwagen für Unreal Engine 5 (Chaos Vehicles), als glTF auch für Godot, Unity oder three.js. Das Auto ist ein eigenes Kombi-Design und keiner echten Marke nachgebaut. Die Beklebung folgt dem deutschen blau-silbernen Stil mit POLIZEI-Schriftzügen, das Kennzeichen ist ausgedacht. Modell, Skelett und Materialien entstehen komplett per Skript in Blender. Es stecken keine fremden Assets und keine Texturen drin.

## Dateien

| Datei | Zweck |
|---|---|
| `polizeiauto.py` | erzeugt das Auto, das Skelett, FBX und GLB, die `.blend` und fünf Vorschaubilder |
| `pruefe_export.py` | prüft die beiden Exporte unabhängig: Einheit und Skalierung der FBX, Knochen, Gewichte, Maße |

## Erzeugen und prüfen

```
blender -b -P polizeiauto.py
blender -b -P pruefe_export.py -- export
```

- Getestet mit Blender 4.5 LTS. Das Skript setzt Blender auf Werkseinstellungen zurück. Starte es deshalb nicht in einem offenen Projekt.
- Neben dem Skript entstehen:
  - `export/SK_Polizeiauto.fbx` für Unreal, in Zentimetern
  - `export/SK_Polizeiauto.glb` für alle anderen Engines, in Metern
  - `polizeiauto.blend` mit Auto und Skelett in Metern, dazu die Nachtszene
  - `polizeiauto_vorne.png`, `_hinten`, `_seite`, `_oben` und `_nacht`
- `pruefe_export.py` schreibt am Ende „ALLES OK“ oder eine Liste der Fehler.
- Modell und Export brauchen nur wenige Sekunden. Die fünf Bilder in 1920 × 1080 mit Cycles auf der CPU dauern auf einem Rechner mit vier Kernen etwa 20 Minuten. Mit `SHOTS=` fällt das weg.

Schalter für schnelle Läufe (Umgebungsvariablen):

| Schalter | Wirkung |
|---|---|
| `SHOTS=` (leer) | keine Bilder. `SHOTS=vorne,nacht` rendert nur diese beiden |
| `SAMPLES=24`, `RES=960x540` | schnellere Bilder zum Testen |

## Das Auto

| | |
|---|---|
| Länge | 4,80 m, mit Kennzeichen 4,90 m |
| Breite | 1,86 m, mit Spiegeln 2,1 m |
| Höhe | Dach 1,48 m, Lichtbalken 1,61 m, Antenne 1,78 m |
| Radstand und Spur | 2,84 m und 1,60 m |
| Räder | Radius 33,5 cm (Durchmesser 67 cm), Breite 22,5 cm |
| Bodenfreiheit | 17 cm |
| Dreiecke | 62 588 |
| Materialien | 17, ohne Texturen. Eine UV-Karte ist vorhanden |

Was alles dran ist:

- **Karosserie:** Kombi mit langer Haube, vier Türen und Heckklappe. Die Fugen von Türen, Haube, Heckklappe und Tankklappe sind schmale dunkle Streifen auf dem Lack. Die Radläufe sind ausgeschnitten und innen schwarz.
- **Beklebung:** unten Blau, darüber ein weißer Reflexstreifen rund ums Auto, oben Silber. POLIZEI steht weiß auf beiden Seiten und blau auf Haube und Heckklappe.
- **Sondersignal:** ein Lichtbalken quer auf dem Dach mit zwei blauen Kuppeln und der Anzeige POLIZEI nach vorn und hinten. Dazu kommen zwei blaue Frontblitzer im Grill und zwei Heckblitzer neben dem Kennzeichen.
- **Licht:** Scheinwerfer mit LED-Leiste und zwei Linsen, Rückleuchten über Eck, rote Reflektoren in der Stoßstange.
- **Anbauteile:** Grill mit Lamellen, Lufteinlass, Diffusor, Kennzeichen mit Halter (Fantasiekennzeichen „PL 2340“), Spiegel, Türgriffe, Dachantenne.
- **Innenraum:** schlicht, aber durch die Scheiben sichtbar: Armaturenbrett, Lenkrad, zwei Sitze mit Kopfstützen, Rückbank.
- **Räder:** Reifen mit vier Längsrillen, Felge mit fünf Speichen, Nabe mit fünf Radmuttern, Bremsscheibe. Einen Bremssattel gibt es absichtlich nicht. Er hinge am Radknochen und würde sich im Spiel mitdrehen.

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

- **FBX für Unreal:** Die Einheit ist Zentimeter, jeder Knoten hat die Skalierung 1. So entsteht nicht der bekannte Fehler mit Faktor 100 am Wurzelknochen, der Physik und Räder durcheinanderbringt. Vielecke mit mehr als vier Ecken sind trianguliert. Normalen (mit harten Kanten) und Tangenten sind enthalten, Animationen nicht.
- **GLB für alle anderen:** glTF 2.0 in Metern mit +Y oben, das Skelett steckt als Skin drin. Die Materialien kommen vollständig an: Metallic, Rauheit, Klarlack, Glas und Leuchten.
- Das Blaulicht leuchtet in beiden Dateien nicht. Es wird in der Engine geschaltet (siehe unten).

## In Unreal Engine 5 einrichten (Chaos Vehicles)

1. **Plugin:** Unter Plugins „Chaos Vehicles“ einschalten und den Editor neu starten. Am schnellsten testest du im Projekt-Template „Vehicle“: Dort ist alles schon verdrahtet, du tauschst nur Mesh, Anim Blueprint und Räder.
2. **Import:** `SK_Polizeiauto.fbx` in den Content Browser ziehen. Als Skeletal Mesh importieren, ein Physics Asset erstellen lassen, keine Animationen. Die Transformation bleibt unverändert: Drehung 0, Skalierung 1,0, keine Umrechnung der Einheiten.
3. **Physics Asset:** öffnen und die Körper der vier Radknochen löschen. Die Räder fragt Chaos selbst ab. Am Knochen `root` bleibt ein Körper. Gut funktionieren zwei Boxen:
   - Unterbau: Mitte (0, 0, 56) cm, Größe 480 × 186 × 78 cm
   - Aufbau: Mitte (−55, 0, 120) cm, Größe 350 × 150 × 55 cm
4. **Räder:** zwei Blueprints mit der Elternklasse `ChaosVehicleWheel` anlegen. Bei beiden gilt `Wheel Radius` 33,5 und `Wheel Width` 22,5.
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

Über FBX kommen meist nur Grundfarbe, Leuchten und Transparenz an. Metallic, Rauheit und Klarlack stellst du am besten von Hand ein. Die Farben sind sRGB-Hexwerte, so wie sie der Farbwähler von Unreal annimmt.

| Material (Slot) | Wo | Farbe | Metallic | Rauheit | Sonst |
|---|---|---|---|---|---|
| `Lack_Silber` | Karosserie oben, Spiegel | `#C9CDD1` | 0,55 | 0,32 | Shading Model Clear Coat: Clear Coat 1, Clear Coat Roughness 0,03 |
| `Lack_Blau` | Karosserie unten | `#123A7A` | 0,45 | 0,32 | Clear Coat wie oben |
| `Reflexfolie_Weiss` | Streifen, Schrift an der Seite | `#ECEEEE` | 0 | 0,45 | |
| `Folie_Blau` | Schrift auf Haube und Heck | `#123A7A` | 0 | 0,40 | |
| `Kunststoff_Schwarz` | Stoßfänger, Rahmen, Fugen, Lichtbalken | `#151618` | 0 | 0,55 | |
| `Glas` | Scheiben | `#1A2026` | 0 | 0,02 | durchsichtig, z. B. Translucent mit Opacity 0,3 |
| `Chrom` | Lamellen, Griffe, Spiegelglas, Radmuttern | `#D8DADC` | 1 | 0,08 | |
| `Scheinwerfer_Gehaeuse` | Scheinwerfer | `#9AA0A6` | 0,9 | 0,18 | |
| `Scheinwerfer_Glas` | Linsen | `#E8EEF4` | 0 | 0,02 | durchsichtig |
| `Tagfahrlicht` | LED-Leisten, Anzeige im Lichtbalken | `#FFFFFF` | 0 | 0,2 | leuchtet weiß |
| `Ruecklicht_Rot` | Rückleuchten, Reflektoren | `#8A0C10` | 0 | 0,05 | leuchtet rot, beim Bremsen heller |
| `Blaulicht` | Kuppeln, Front- und Heckblitzer | `#1747FF` | 0 | 0,1 | blinkt, siehe unten |
| `Gummi` | Reifen | `#141414` | 0 | 0,85 | |
| `Felge` | Felgen | `#B4B8BC` | 1 | 0,28 | |
| `Bremse` | Bremsscheiben | `#4A4A4A` | 0,8 | 0,45 | |
| `Innenraum` | Armaturen, Sitze | `#2B2C2E` | 0 | 0,9 | |
| `Kennzeichen` | Kennzeichen | `#F2F2F0` | 0 | 0,4 | |

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
- Rücklicht und Tagfahrlicht gehen genauso, nur ohne Blinken. Als Richtwert für Emissive: Tagfahrlicht 20, Rücklicht 4 und beim Bremsen 30. Die passenden Werte hängen von der Belichtung deiner Szene ab.

## Leistung

- 62 588 Dreiecke und 17 Materialslots sind für ein Spielerauto oder ein Auto in Zwischensequenzen gut. Jeder Slot kostet einen eigenen Draw Call.
- Für viele Autos gleichzeitig, etwa als Verkehr, im Skeletal-Mesh-Editor LODs erzeugen lassen, zum Beispiel 4 Stufen. Wenn es noch weniger sein soll, fasse die einfarbigen Materialien zusammen.
- Die UV-Karte ist automatisch ausgelegt (Smart UV Project, Inseln ohne Überlappung). Sie reicht für Schmutz- oder Kratzermasken. Für eigene Texturen legst du sie am besten neu aus.
