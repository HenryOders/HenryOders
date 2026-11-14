# ABANDONED · Bodenplatten „gefaengnis“

Fünf modulare Bodenstücke für das verlassene Gefängnis: vier Betonplatten mit 4 × 4 m und eine Türschwelle aus Stahl. Modelle und Texturen sind komplett per Skript in Blender erzeugt. Es stecken keine fremden Assets drin.

## Dateien

| Datei | Zweck |
|---|---|
| `kit_boden_gefaengnis.py` | erzeugt die zwei Texturen, alle fünf Stücke, den glTF-Export und Vorschaubilder |
| `pruefe_boden.py` | prüft die exportierten Dateien unabhängig gegen die Regeln für Bodenplatten (dieselbe Datei wie beim Krankenhaus) |

## Erzeugen und prüfen

```
blender -b -P kit_boden_gefaengnis.py
python pruefe_boden.py PolyHaven gefaengnis
```

- Das Skript setzt Blender auf Werkseinstellungen zurück. Starte es deshalb nicht in einem offenen Projekt.
- Es legt neben sich den Ordner `PolyHaven/` an. Dessen Inhalt gehört nach `C:\Users\Henry\Abandoned\SourceArt\PolyHaven\`. Die Texturen landen in `Texturen/gefaengnis/` neben den Wandtexturen. Die Namen überschneiden sich nicht: `T_gefaengnis_Wand_*` und `T_gefaengnis_Detail_*` gehören den Wänden, `T_gefaengnis_Boden_*` und `T_gefaengnis_BodenDetail_*` dem Boden.
- `pruefe_boden.py` braucht nur Python mit numpy. Am Ende steht „ALLES OK“ oder eine Liste der Fehler.
- Jeder Lauf liefert byteweise dieselben Modell- und Texturdateien. Alle Zufallswerte hängen an festen Startwerten.
- Ein voller Lauf dauert auf einem Rechner mit vier Kernen etwa 10 Minuten. Die Texturen brauchen knapp 1,5 Minuten, den Rest die zehn Vorschaubilder. Mit `SHOTS=` ist der Lauf nach gut 1,5 Minuten fertig.

Schalter für schnelle Tests (Umgebungsvariablen):

| Schalter | Wirkung |
|---|---|
| `TEXDIV=4` | Texturen nur 1024 statt 4096 px groß, nur zum Testen (die Prüfung meldet dann die falsche Größe; das Rauschen und damit das Bild sehen anders aus) |
| `SHOTS=` (leer) | keine Vorschaubilder; `SHOTS=nah1,lampe2` rendert nur diese |
| `SAMPLES=24`, `RES=960x540` | schnellere Vorschaubilder |
| `DIAG=1` | listet Dreiecke, deren Pixeldichte außerhalb von 990–1060 px/m liegt |

## Die Stücke

| Stück | Was es ist | Dreiecke | Pixeldichte px/m (min–max) | Lauffläche | lose Teile |
|---|---|---|---|---|---|
| `gefaengnis_boden_01` | Anstrich weitgehend erhalten. Er ist vor allem an den Dehnfugen abgeplatzt, dazu kommen dunkle Schmutzränder eingetrockneter Pfützen. Vier Fugenkanten sind abgeplatzt (echte Geometrie) | 1450 | 1018–1024 | −0,65 … +0,03 cm | keine |
| `gefaengnis_boden_02` | Der Anstrich ist zur Hälfte abgelaufen: Die mittlere Reihe (y −1 … +1 m) ist blanker, glatt getretener Beton mit Farbresten. Mitten darin läuft eine verblasste, durchgetretene gelbe Wegmarkierung (10 cm) quer über die Platte. Dazu kommen drei feine Risse (Spalt bis 1,6 mm, 3 bis 4 mm tief) und fünf abgeplatzte Fugenkanten | 2580 | 1018–1024 | −0,65 … +0,05 cm | keine |
| `gefaengnis_boden_03` | Der Beton ist in einer flachen Mulde ausgebrochen (0,92 × 0,59 m, bis 1,43 cm tief, Bruchkante 3 bis 6 mm). Der Boden ist rau mit freiliegenden Kieseln. Zwei Bewehrungsstäbe (12 mm) liegen frei, ein Querstab (9 mm) schaut an der tiefsten Stelle heraus. Alles ist rostig, mit Rostwasser im Beton. Um die Mulde ist der Anstrich abgeplatzt. Dazu 25 Betonkrümel, ein feiner Riss und drei abgeplatzte Fugenkanten | 4124 | 1018–1033 | −1,40 … +0,09 cm | Krümel bis 0,67 cm |
| `gefaengnis_boden_04` | Zellentrakt: Gussrinne 20 cm breit quer über die Platte (y −0,1 … +0,1 m). Rahmen und Gitter liegen bündig auf Z = 0. Jedes Gitterstück ist 50 cm lang und hat 16 Schlitze von 1 × 13 cm als echte Öffnungen, darunter ein 10 cm tiefer Trog mit Schlamm. Rundherum ist der Anstrich bis 22 bis 30 cm von der Rinnenmitte abgeplatzt, dort liegen Rostläufer und Nässe. Dazu drei abgeplatzte Fugenkanten | 4058 | 1018–1024 | −0,64 … +0,05 cm | keine |
| `gefaengnis_boden_schwelle` | Stahlschwelle 1,00 × 0,20 m, 20 cm dick: Riffelblech mit Tränenmuster, bündig auf Z = 0 und durchgehend verrostet, mit vier leicht eingesunkenen Senkschrauben | 268 | 1024–1024 | −0,07 … 0 cm | keine |

- **Lauffläche** heißt: alle nach oben zeigenden Flächen ohne lose Teile, gemessen an den exportierten Dateien. Sie schließt die Fugenmasse (6 mm unter der Oberseite), die Rissgründe und den Muldenboden ein.
- Tiefer liegt nur der Trog der Rinne: bis 10 cm, nur durch die 1 cm breiten Schlitze zu sehen.
- Die Pixeldichte ist an den exportierten Dateien gemessen. Flache Teile liegen genau bei 1024 px/m. Die kleinen Abweichungen stammen von geneigten Flächen in Abplatzungen und Mulde, von den Krümeln und von der Rundung auf 32-Bit-Zahlen in der Datei.

## Stil

- **Anstrich:** stumpfes Grau auf Beton, leicht ungleichmäßig, stellenweise dünn gelaufen. Er ist großflächig abgeplatzt, auf 21 % der Fläche, vor allem in breiten Streifen entlang der Dehnfugen. Am Rand der Abplatzungen sitzt ein heller Saum im Anstrich, auf dem Beton davor sammelt sich Schmutz.
- **Roher Beton:** warmgraue Zementhaut mit feinem Zuschlag und Poren, dazu Kellenspuren.
- **Dehnfugen:** alle 2 m in beiden Richtungen (bei x und y = −1 und +1 m jeder Platte), 8 mm breit und als echte Rillen modelliert. Die Fugenmasse aus Bitumen liegt 6 mm tief und ist stellenweise ausgebrochen. Entlang der Fugen hat sich Schmutz gesammelt.
- **Gebrauchsspuren:** sieben Schmutzränder eingetrockneter Pfützen, feuchte Stellen, Gummistriemen von Schuhen, zwei Spuren eines Essenswagens, Kratzer im Anstrich, Ölflecken, Rostpunkte und zwei alte Dübellöcher einer Bettverankerung. Darüber liegt ein Staubschleier.
- **Abgeplatzte Fugenkanten:** flache Ausbrüche bis 3 cm tief ins Feld, an der Fuge bis 4 mm abgesenkt. Darin liegt roher Beton mit Kieseln frei.
- **Laufweg (02):** blanker Beton, glatt getreten, mit feinem Zuschlag, Gummiabrieb in Gehrichtung und Inseln aus Farbresten. Die gelbe Linie ist ausgeblichen, verschmutzt und an vielen Stellen bis auf den Beton durchgetreten.
- **Mulde (03):** gebrochene Oberfläche mit Kieseln, dunkel und feucht. Bewehrung mit Rippen, durchgerostet, mit Rostfahnen im Beton und einem eingetrockneten Rostwasserrand an der tiefsten Stelle. Um die Mulde liegt freier Beton mit Rostwasserspuren.
- **Rinne (04):** Rahmen aus Stahlwinkeln, Gussgitter dunkel und rostig, abgetretene Stege, Stöße der Gitterstücke alle 50 cm. Im Trog liegen Schlamm, Rostschuppen und Steinchen.
- **Schwelle:** Riffelblech mit Tränenmuster, durchgerostet, Lochfraß, Schmutz zwischen den Rippen. In der Mitte sind die Rippen abgetreten und dunkler.
- **Stimmung:** gedeckte, entsättigte Farben, nichts ist sauber oder glänzt. Die kleinste Rauheit in beiden Sätzen ist 0,42 (nasse Stellen und Schlamm im Trog), der Anstrich liegt bei etwa 0,7, roher Beton bei 0,85 bis 0,95.

## Regeln und wie sie eingehalten sind

- **Maße und Ursprung:** Platten X und Y −2 … +2 m, Oberseite auf Z = 0, Unterseite auf Z = −0,2 m. Die Schwelle reicht X −0,5 … +0,5 und Y −0,1 … +0,1 m, ebenfalls 20 cm dick. Der Ursprung liegt oben in der Mitte. Im glTF hat jeder Knoten keine Transformation (Maßstab 1, Meter).
- **Begehbar:** Die Lauffläche bleibt bei allen Stücken zwischen −1,40 und +0,09 cm. Es gibt keine Stufen: Die höchsten Kanten sind die 6 mm der Fugen und die Bruchkante der Mulde mit höchstens 6,4 mm. Löcher, in die man treten kann, gibt es nicht. Die Rinne ist vom Gitter abgedeckt, die Schlitze sind 1 cm breit.
- **Rand:** In den äußeren 5 cm liegt jeder Punkt genau auf Z = 0 (oder auf der Unterseite). Die Fugen werden auf den letzten 20 cm vor dem Rand flacher und enden dort auf Z = 0. Im Randstreifen sind sie nur gemalt. Die Prüfung kontrolliert das Punkt für Punkt.
- **Lose Teile:** Nur Platte 03 hat welche: Betonkrümel bis 0,67 cm hoch, alle nahe der Plattenmitte und weit mehr als 30 cm vom Rand.
- **Echte Geometrie:** Fugen, abgeplatzte Fugenkanten, Risse, Mulde mit Bruchkante, Bewehrung, Rinne mit Rahmen, Gitter, Schlitzen und Trog sowie die Senkschrauben der Schwelle sind modelliert. Die Normal-Karte ergänzt nur feine Details (Poren, Kiesel, Riffelmuster, Farbkanten).
- **Dreiecke:** höchstens 12 000 je Platte. Am meisten hat Platte 03 mit 4124, die schlichte Platte 01 kommt mit 1450 aus.
- **Materialien:** genau zwei je Stück, `M_gefaengnis_Boden` und `M_gefaengnis_BodenDetail`. Beide sind ein Principled BSDF, angeschlossen sind nur Base Color, Normal und Roughness (Grünkanal). Metallic ist nicht angeschlossen und steht auf 0, es gibt keine Transparenz und kein Displacement. Die Materialien sind einseitig (`doubleSided` aus), alle Teile sind geschlossen oder liegen auf.
- **Export:** glTF 2.0 getrennt (`.gltf` + `.bin`), +Y oben, unter `Modelle/<name>/<name>.gltf`. Es gibt einen Knoten pro Datei, benannt wie die Datei, und keine Lichter, Kameras oder Empties. Die Bilder sind nicht eingebettet, sondern relativ verknüpft: `../../Texturen/gefaengnis/T_gefaengnis_Boden_Grundfarbe.jpg` usw.
- **Normalen:** keine gekippten oder entarteten Dreiecke, alle Normalen haben die Länge 1.

## Texturen

Zwei Sätze mit je 4096 × 4096 px und 1024 px/m (UV 0,25 je Meter). Alle fünf Stücke nutzen dieselben zwei Materialien und dieselben Bilddateien.

Je Satz gibt es drei Dateien:

- `_Grundfarbe.jpg`: Farbe (sRGB).
- `_Normale.png`: Normal-Karte im OpenGL-Format, wie glTF es vorschreibt. Falls deine Engine DirectX erwartet und die Beulen falsch herum wirken, beim Import den Grünkanal umdrehen.
- `_Rauheit.png`: gepackt, Rot = 255, Grün = Rauheit, Blau = 0.

### `T_gefaengnis_Boden`: gestrichener Beton

4 × 4 m gestrichener Beton mit den Dehnfugen, in beide Richtungen nahtlos kachelbar. Die Oberseite aller Platten ist weltbezogen gemappt: U = (X + 2) / 4, V = (Y + 2) / 4. Die Prüfung rechnet das für jede Fläche mit diesem Material nach.

### `T_gefaengnis_BodenDetail`: Streifen-Atlas

Wie das Detail-Set der Wände ist BodenDetail ein Streifen-Atlas. Die Bänder über die volle Breite kacheln waagerecht nahtlos und laufen mit U = (X + 2) / 4 über die Plattengrenzen weiter. Die Blöcke oben sind Einzelflächen. Angaben in Metern von der Unterkante des Bildes:

| Bereich | Inhalt |
|---|---|
| 0 … 1,02 | abgelaufener Laufweg: blanker Beton mit Farbresten (Platte 02) |
| 1,02 … 1,14 | gelbe Wegmarkierung, 10 cm |
| 1,14 … 1,64 | roher Beton mit Kieseln: Abplatzungen, Rissflanken, Bruchkante der Mulde, Krümel, Unterseiten |
| 1,64 … 2,44 | Rinne mit Rahmen, Gitter und Schlitzen, beidseitig freiliegender Beton mit Rostläufern |
| 2,44 … 2,69 | Inneres des Troges: Wände und Boden mit Schlamm |
| 2,69 … 2,89 | Schnitt durch die Platte: Beton, Estrich, Anstrich (Seitenflächen) |
| 2,89 … 2,92 | Fugenflanken und Fugenmasse |
| 2,92 … 4,0, links 1,5 m | Mulde der Platte 03 mit dem Ring aus freiliegendem Beton (Einzelfläche) |
| 2,92 … 3,48, rechts 2,5 m | Riffelblech der Schwelle, Stahlkante, Bewehrung, Gusseisen, Seiten der Schwelle |

### Warum Laufweg, Rinne und Mulde im BodenDetail liegen

Der Satz `Boden` ist weltbezogen und auf allen Platten gleich. Was eine einzelne Platte anders aussehen lässt, liegt deshalb im BodenDetail. Damit die Grenze zwischen den beiden Materialien nicht auffällt, liegt sie dort, wo auch in Wirklichkeit eine Kante ist:

- **Laufweg (02):** Er reicht genau von Fuge zu Fuge (y = −1 bis +1 m). Die untere und die obere Hälfte nutzen verschiedene Stellen des Bands. Die Naht zwischen ihnen liegt unter der gelben Linie.
- **Rostzone (04) und Ring um die Mulde (03):** Ihr Rand ist eine zerfranste Abplatzkante. Innen liegt roher Beton, außen der Anstrich, so wie bei den Abplatzungen im Boden-Satz.

## Aneinanderlegen

- Die Platten passen ins 4-m-Raster. Die Fugen liegen bei x und y = −1 und +1 m jeder Platte, so entstehen Felder von 2 × 2 m, die über die Plattengrenzen reichen. Der Rand ist auf allen Platten gleich flach, deshalb ist jede Kombination begehbar.
- Ohne Drehung kachelt das Bild des Anstrichs nahtlos. Um 90° oder 180° gedreht passen die Fugen weiterhin, aber das Bild springt an der Plattengrenze.
- An der Plattengrenze sind die Fugen auf 10 cm nur gemalt (je 5 cm Randstreifen), davor werden sie auf 20 cm flacher.
- Mehrere 02 hintereinander (entlang X) ergeben einen durchgehenden Laufweg mit gelber Linie. Mehrere 04 hintereinander ergeben eine durchgehende Rinne. Im Randstreifen ist das Gitter flach gemalt, der Trog endet 5 cm vor der Kante. Neben anderen Platten enden Laufweg und Rinne an der Plattengrenze.
- Die Schwelle ist so breit wie die Wände (20 cm) und gehört in die Türöffnung.

## Vorschaubilder

`gefaengnis_boden_uebersicht.png` zeigt alle Stücke bei flachem Licht. `gefaengnis_boden_kacheln.png` zeigt zwei Laufweg-Platten hintereinander mit 01 und 03 daneben und zwei Rinnen-Platten hintereinander. `lampe1` bis `lampe4` zeigen die Platten 01 bis 04 aus Augenhöhe im Taschenlampenlicht (02 entlang des Laufwegs). `nah1` bis `nah4` sind Nahaufnahmen von Rinne, Schwelle, Mulde und der gelben Linie an einer Fuge.
