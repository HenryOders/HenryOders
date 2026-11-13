# ABANDONED · Bodenplatten „krankenhaus“

Fünf modulare Bodenstücke für das verlassene Krankenhaus aus den 1970er-Jahren: vier Platten mit 4 × 4 m und eine Türschwelle. Modelle und Texturen sind komplett per Skript in Blender erzeugt. Es stecken keine fremden Assets drin.

## Dateien

| Datei | Zweck |
|---|---|
| `kit_boden_krankenhaus.py` | erzeugt die zwei Texturen, alle fünf Stücke, den glTF-Export und Vorschaubilder |
| `pruefe_boden.py` | prüft die exportierten Dateien unabhängig gegen die Regeln für Bodenplatten |

## Erzeugen und prüfen

```
blender -b -P kit_boden_krankenhaus.py
python pruefe_boden.py PolyHaven krankenhaus
```

- Das Skript setzt Blender auf Werkseinstellungen zurück. Starte es deshalb nicht in einem offenen Projekt.
- Es legt neben sich den Ordner `PolyHaven/` an. Dessen Inhalt gehört nach `C:\Users\Henry\Abandoned\SourceArt\PolyHaven\`. Die Texturen landen in `Texturen/krankenhaus/` neben den Wandtexturen. Die Namen überschneiden sich nicht (`T_krankenhaus_Wand_*` und `T_krankenhaus_Detail_*` gehören den Wänden, `T_krankenhaus_Boden_*` und `T_krankenhaus_BodenDetail_*` dem Boden).
- `pruefe_boden.py` braucht nur Python mit numpy. Am Ende steht „ALLES OK“ oder eine Liste der Fehler.
- Jeder Lauf liefert byteweise dieselben Modell- und Texturdateien. Alle Zufallswerte hängen an festen Startwerten.
- Ein voller Lauf dauert auf einem Rechner mit vier Kernen etwa 10 Minuten. Die Texturen brauchen gut eine Minute, den Rest die zehn Vorschaubilder. Mit `SHOTS=` ist der Lauf nach gut einer Minute fertig.

Schalter für schnelle Tests (Umgebungsvariablen):

| Schalter | Wirkung |
|---|---|
| `TEXDIV=4` | Texturen nur 1024 statt 4096 px groß, nur zum Testen (die Prüfung meldet dann die falsche Größe) |
| `SHOTS=` (leer) | keine Vorschaubilder; `SHOTS=nah1,lampe2` rendert nur diese |
| `SAMPLES=24`, `RES=960x540` | schnellere Vorschaubilder |
| `DIAG=1` | listet Dreiecke, deren Pixeldichte außerhalb von 990–1060 px/m liegt |

## Die Stücke

| Stück | Was es ist | Dreiecke | Pixeldichte px/m (min–max) | Lauffläche | lose Teile |
|---|---|---|---|---|---|
| `krankenhaus_boden_01` | intakt, gealtert und schmutzig: Linoleum vergilbt und fleckig, mit dunklen Wasserrändern. Die beiden verschweißten Nähte sind leicht aufgewölbt, dazu kommen drei flache Blasen | 1796 | 1021–1024 | −0,05 … +0,29 cm | keine |
| `krankenhaus_boden_02` | abgelaufen: beide Nähte auf 1,45 m und 0,95 m Länge aufgeplatzt (Spalt bis 12 mm, Kanten knapp 8 mm hochgestellt, darunter Estrich mit Kleber). Dazu zwei parallele Schleifrillen eines Bettes über 2,7 m, eine kurze dritte Rille, zwei kurze Risse (33 und 24 cm) mit echter Bruchkante und eine Blase | 6628 | 997–1024 | −0,34 … +0,76 cm | keine |
| `krankenhaus_boden_03` | beschädigt: Linoleum auf 3,9 m² abgerissen (knapp ein Viertel der Platte), an einem 1,3 m breiten Scharnier hängt die aufgerollte Bahn. Im Loch liegt Estrich mit altem Kleber und Juteresten frei, der Rand ist an zwei Stellen hochgestellt. Schutt: 13 Betonbrocken, 14 Glasscherben, zwei Papierblätter, zwei Linoleumfetzen | 4309 | 1007–1029 | −0,35 … +0,44 cm | Rolle 4,8 cm, Brocken bis 4,8 cm |
| `krankenhaus_boden_04` | OP-Bereich: weiße Fliesen 10 × 10 cm mit dunklen Fugen (3 mm breit, 2 mm tief, echte Geometrie), in der Mitte ein runder Edelstahlablauf (Flansch Ø 28 cm, Schlitzrost, Topf) mit rostbrauner Fahne in den Fliesen. Sechs Fliesen sind gesprungen (eine Hälfte leicht abgesackt), vier haben eine abgeplatzte Ecke | 5878 | 1017–1024 | −0,30 … +0,08 cm | keine |
| `krankenhaus_boden_schwelle` | Block 1,00 × 0,20 m, 20 cm dick, oben Linoleum. Darauf eine Aluminiumschiene (90 × 7 cm, 3,5 mm hoch) mit Kratzern und drei Schrauben, am Ende +X ab x = 0,30 m hochgebogen auf genau 1,0 cm | 170 | 1022–1024 | 0 … +1,0 cm | keine |

- **Lauffläche** heißt: alle nach oben zeigenden Flächen von Linoleum, Estrich, Fliesen und Schiene, ohne lose Teile. Gemessen an den exportierten Dateien.
- Die Lauffläche schließt die Fugengründe und den Estrich in Spalten und im Abriss ein (2 bis 3,5 mm unter der Oberseite). Tiefer liegt nur der Ablauftopf unter dem Rost: bis 6 cm, nur durch die 7 mm breiten Schlitze zu sehen.
- Die Pixeldichte ist an den exportierten Dateien gemessen. Flache Teile liegen genau bei 1024 px/m. Die kleinen Abweichungen stammen von angehobenen Rändern, der Rolle, den Schuttstücken und von der Rundung auf 32-Bit-Zahlen in der Datei.

## Stil

- **Linoleum:** grau-grün, in 2 m breiten Bahnen mit verschweißten Nähten bei x = −1 und +1 m. Die Marmorierung läuft längs der Bahnen, benachbarte Bahnen unterscheiden sich leicht im Ton. Das Linoleum ist vergilbt, verschmutzt und stumpf abgelaufen.
- **Gebrauchsspuren im Linoleum:** acht dunkle Wasserränder mit mehreren Trocknungsstufen und feuchte Flecken. Dazu Gummispuren von Betten (Radpaare im Abstand 0,8 m) und Rollstühlen (Bögen), kurze Schuhstriemen und 2600 feine Kratzer. Es gibt sechs Brandlöcher von Zigaretten, den Rostring eines Metallständers und einen Staubschleier über allem.
- **Nähte als Geometrie:** die Schweißschnur ist in der Textur, die Wölbung der Naht (2,5 bis 3,5 mm) ist echte Geometrie. Wo die Naht aufgeplatzt ist, sieht man die Bruchkanten des Linoleums, die Juteunterseite der hochgestellten Ränder und im Spalt den Estrich mit Kleber.
- **Abriss (boden_03):** zerfranster Umriss, vor allem nach innen gerissen. Die Bruchkante zeigt den Schnitt durch Linoleum, Jute und Kleber. Die Bahn ist am Scharnier zu einer Rolle mit gut zwei Windungen aufgerollt, die Oberseite liegt außen und die Jute innen. Im Loch liegt grauer Estrich mit schwarzem Bitumenkleber, Zahnspachtel-Rillen und Juteresten frei.
- **Schutt:** Betonbrocken, dunkle staubige Glasscherben, vergilbte Formularblätter mit hochgebogener Ecke (Rückseite unbedruckt) und abgerissene Linoleumfetzen.
- **OP-Fliesen (boden_04):** grauweiße Glasur mit leichten Tonunterschieden je Fliese. Sie haben Haarrisse, Schmutz in den Kanten und dunkle Fugen. Um den Ablauf liegt eine rostbraune Fahne mit Kalkrand, die in den Fugen dunkler ist. Der Ablauf hat einen Edelstahlflansch mit Drehriefen, einen Rost mit zwölf Schlitzen und einen Topf mit Schlamm und Rost. Die acht Fliesen am Flansch sind rund zugeschnitten.
- **Schwelle:** Aluminium mit Längsschliff, Kratzern, Oxid und Schmutz an den Profilkanten. Die Schrauben sind aus Edelstahl.
- **Stimmung:** gedeckte, entsättigte Farben, nichts ist sauber oder glänzt. Die kleinste Rauheit in beiden Sätzen ist 0,26 (verstaubtes Glas), Fliesenglasur und Edelstahl liegen bei 0,3 und darüber.

## Regeln und wie sie eingehalten sind

- **Maße und Ursprung:** Platten X und Y −2 … +2 m, Oberseite auf Z = 0, Unterseite auf Z = −0,2 m. Die Schwelle reicht X −0,5 … +0,5 und Y −0,1 … +0,1 m, ebenfalls 20 cm dick. Der Ursprung liegt oben in der Mitte. Im glTF hat jeder Knoten keine Transformation (Maßstab 1, Meter).
- **Begehbar:** die Lauffläche bleibt bei allen Stücken zwischen −0,35 und +0,76 cm, nur die hochgebogene Schiene erreicht 1,0 cm. Es gibt keine Stufen, nur die 3 mm hohen Bruchkanten an Abriss, Rissen und Nähten, und keine Löcher, in die man treten kann. Der Ablauf ist vom Rost abgedeckt.
- **Rand:** in den äußeren 5 cm liegt jeder Punkt genau auf Z = 0 (oder auf der Unterseite). Alle Verformungen laufen von 25 cm bis 5 cm vor der Kante sanft aus. Die Prüfung kontrolliert das Punkt für Punkt.
- **Lose Teile:** höchstens 4,8 cm hoch, nur im Inneren. Alles, was höher als 0,7 cm ist, hält mindestens 30 cm Abstand zur Kante, tatsächlich mindestens 63 cm.
- **Echte Geometrie:** Nähte, aufgeplatzte Nähte, Risse, Schleifrillen, Blasen, Abriss, Rolle, Fliesenfugen, gesprungene Fliesen, abgeplatzte Ecken und der Ablauf sind modelliert. Die Normal-Karte ergänzt nur feine Details.
- **Dreiecke:** höchstens 12 000 je Platte. Am meisten hat boden_02 mit 6628, die intakte boden_01 kommt mit 1796 aus.
- **Materialien:** genau zwei je Stück, `M_krankenhaus_Boden` und `M_krankenhaus_BodenDetail`. Beide sind ein Principled BSDF, angeschlossen sind nur Base Color, Normal und Roughness (Grünkanal). Metallic ist nicht angeschlossen und steht auf 0, es gibt keine Transparenz und kein Displacement. Die Materialien sind einseitig (`doubleSided` aus). Dünne Teile wie Papier und Fetzen haben deshalb eine eigene Rückseite.
- **Export:** glTF 2.0 getrennt (`.gltf` + `.bin`), +Y oben, unter `Modelle/<name>/<name>.gltf`. Ein Knoten pro Datei, benannt wie die Datei, ohne Lichter, Kameras oder Empties. Die Bilder sind nicht eingebettet, sondern relativ verknüpft: `../../Texturen/krankenhaus/T_krankenhaus_Boden_Grundfarbe.jpg` usw.
- **Normalen:** keine gekippten oder entarteten Dreiecke, alle Normalen haben die Länge 1.

## Texturen

Zwei Sätze mit je 4096 × 4096 px und 1024 px/m (UV 0,25 je Meter). Alle fünf Stücke nutzen dieselben zwei Materialien und dieselben Bilddateien.

Je Satz gibt es drei Dateien:

- `_Grundfarbe.jpg`: Farbe (sRGB).
- `_Normale.png`: Normal-Karte im OpenGL-Format, wie glTF es vorschreibt. Falls deine Engine DirectX erwartet und die Beulen falsch herum wirken, beim Import den Grünkanal umdrehen.
- `_Rauheit.png`: gepackt, Rot = 255, Grün = Rauheit, Blau = 0.

### `T_krankenhaus_Boden`: Linoleum

4 × 4 m Linoleum, in beide Richtungen nahtlos kachelbar. Die Oberseite aller Linoleumflächen ist weltbezogen gemappt: U = (X + 2) / 4, V = (Y + 2) / 4. Die Prüfung rechnet das für jede Linoleumfläche nach.

### `T_krankenhaus_BodenDetail`: Streifen-Atlas

Wie das Detail-Set der Wände ist BodenDetail ein Streifen-Atlas. Die Bänder über die volle Breite kacheln waagerecht nahtlos, deshalb können lange Kanten darin ohne Sprung durchlaufen. Die beiden Blöcke oben sind Einzelflächen, auf die die Stücke genau gelegt sind. Angaben in Metern von der Unterkante des Bildes:

| Bereich | Inhalt |
|---|---|
| 0 … 1,6 | Estrich mit Bitumenkleber, Zahnspachtel-Rillen und Juteresten (Boden im Abriss und in Spalten, Unterseite der Linoleumplatten) |
| 1,6 … 1,7 | Aluminium der Schwelle |
| 1,7 … 1,9 | Schnitt durch die Linoleumplatte: Beton, Estrich, Kleber, Linoleum (Seitenflächen) |
| 1,9 … 2,1 | Schnitt durch die Fliesenplatte: Beton, Estrich, Mörtelbett, Fliese mit Fugen alle 10 cm |
| 2,1 … 2,7 | sechs Reihen OP-Fliesen 10 × 10 cm |
| 2,7 … 2,8 | Fliesenflanken in den Fugen, Fugengrund, Edelstahl |
| 2,8 … 4,0, links 1,2 m | Mitte der OP-Platte: 12 × 12 Fliesen mit Ablaufflansch, Rost und Rostfahne |
| 2,8 … 4,0, rechts 2,8 m | Juterücken, Schnittkante des Linoleums, Schleifspur, Beton, Glas, drei Formularblätter und eine unbedruckte Rückseite |

### Warum die OP-Fliesen im BodenDetail liegen

Der Satz `Boden` ist schon das Linoleum. Ein zweiter Bodenbelag hat deshalb nur im BodenDetail Platz. Ein weltbezogenes Fliesenbild über 4 × 4 m würde den ganzen zweiten Satz belegen. Die Fliesenfläche von boden_04 nutzt darum das Fliesenband im Atlas:

- Jede Fliesenreihe liegt auf einer der sechs Reihen im Band, versetzt um ganze Fliesen. So passt jede Fliese genau auf eine Fliese im Bild und das Muster wirkt nicht gekachelt.
- Die Mitte (1,2 × 1,2 m) mit dem Ablauf hat ein eigenes Bild.
- Die Pixeldichte bleibt 1024 px/m und das Raster folgt der Welt. Fugen liegen bei x, y = −2,0 / −1,9 / … / +2,0 m.

Damit auch boden_04 genau die zwei Materialien trägt, hat seine Unterseite das Material `M_krankenhaus_Boden`, ebenfalls weltbezogen gemappt. Man sieht sie im Spiel nie.

## Aneinanderlegen

- Die Platten passen ins 4-m-Raster. Die Kanten sind auf allen Platten gleich flach, deshalb ist jede Kombination begehbar.
- Linoleumplatten nebeneinander ergeben eine durchgehende Fläche ohne Textursprung. Die Nähte liegen bei x = −1 und +1 m jeder Platte und laufen über die Plattengrenzen weiter, nur ihre Wölbung läuft zur Kante hin flach aus. Eine Drehung um 180° hält die Nähte in Linie. Bei 90° laufen die Bahnen quer, das passt nur an einer Raumgrenze.
- OP-Platten nebeneinander: an der Kante liegt auf jeder Platte eine halbe Fuge (1,5 mm), zusammen ergibt das eine normale 3-mm-Fuge. In den äußeren 5 cm sind die Fugen nur gemalt, weil der Rand flach bleiben muss.
- Die Schwelle ist so breit wie die Wände (20 cm) und gehört in die Türöffnung. Die Schiene läuft entlang X.

## Vorschaubilder

`krankenhaus_boden_uebersicht.png` zeigt alle Stücke bei flachem Licht. `krankenhaus_boden_kacheln.png` zeigt eine Fläche aus vier Linoleumplatten (01, 02, 03, 01) und zwei OP-Platten nebeneinander. `lampe1` bis `lampe4` zeigen die Platten 01 bis 04 aus Augenhöhe im Taschenlampenlicht. `nah1` bis `nah4` sind Nahaufnahmen von Ablauf, Schwelle, Rolle und aufgeplatzter Naht.
