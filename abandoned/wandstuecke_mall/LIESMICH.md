# ABANDONED · Wandstücke „mall“

Sieben modulare Wandstücke für das verlassene Einkaufszentrum, gebaut nach den Grundregeln für alle Gebäude. Modelle und Texturen sind komplett per Skript in Blender erzeugt. Es stecken keine fremden Assets drin.

## Dateien

| Datei | Zweck |
|---|---|
| `kit_mall.py` | erzeugt die zwei Texturen, alle sieben Stücke, den glTF-Export und Vorschaubilder |
| `pruefe_gltf.py` | prüft die exportierten Dateien unabhängig gegen die Regeln (gleiche Datei wie bei den anderen Gebäuden) |

## Erzeugen und prüfen

```
blender -b -P kit_mall.py
python pruefe_gltf.py PolyHaven mall
```

- Das Skript setzt Blender auf Werkseinstellungen zurück. Starte es deshalb nicht in einem offenen Projekt.
- Es legt neben sich den Ordner `PolyHaven/` an. Dessen Inhalt gehört nach `C:\Users\Henry\Abandoned\SourceArt\PolyHaven\`.
- `pruefe_gltf.py` braucht nur Python mit numpy. Am Ende steht „ALLES OK“ oder eine Liste der Fehler.
- Jeder Lauf liefert byteweise dieselben Modell- und Texturdateien. Alle Zufallswerte hängen an festen Startwerten oder an der Lage der Fläche.

Schalter für schnelle Tests: `TEXDIV=4` (Texturen 1024 statt 4096 px), `SHOTS=` (keine Vorschaubilder), `DIAG=1` (listet Dreiecke außerhalb von 950–1100 px/m).

## Die Stücke

| Stück | Was es ist | Dreiecke | Pixeldichte px/m (min–max) | Vorstand |
|---|---|---|---|---|
| `mall_wand_01` | intakte Wand; je Seite eine gesprungene Steinplatte | 394 | 1022–1024 | 1,5 cm (Sockel) |
| `mall_wand_02` | stark beschädigt: tiefer Riss durch die Beplankung (beide Seiten). Auf −Y ein großes Loch im Gipskarton mit Ständer und eingerissener Dämmung und ein kleineres Loch. Auf +Y ein Loch oben. Je Seite eine abgefallene Platte (Kleberbett sichtbar) und eine abgebrochene Ecke, dazu drei gesprungene Platten. Gipsbröckchen, Gipskartonstücke, Dämmflocken und Steinscherben am Boden | 2702 | 1021–1025 | Brocken am Boden 11,4 cm |
| `mall_wand_03` | auf +Y Kabelkanal und Sprinklerrohr unter der Decke und ein Feuerlöscherkasten in Brusthöhe mit offener Tür; auf −Y ein kleines Loch im Gipskarton und eine gesprungene Platte | 1728 | 1023–1024 | Sprinklerrohr 8,0 cm, Brocken am Boden 10,0 cm |
| `mall_wand_tuer` | Öffnung 1,30 × 2,20 m, Umfassungszarge aus eloxiertem Aluminium mit Gummidichtung und drei Bändern; auf +Y ein kleines Loch, auf −Y eine gesprungene Platte | 1042 | 1023–1027 | Zarge 2,0 cm, Brocken am Boden 10,3 cm |
| `mall_wand_fenster` | Schaufenster 1,50 × 1,40 m ab 0,95 m: Aluminiumrahmen mit leerem Glasfalz, auf −Y eine Bank aus dunklem Stein und eine abgebrochene Plattenecke, auf +Y ein Alublech, ein kleines Loch oben und eine gesprungene Platte | 1193 | 1023–1029 | Bänke 3,0 cm, Brocken am Boden 9,3 cm |
| `mall_wand_durchbruch` | Loch durch die ganze Ständerwand, 1,44 × 1,32 m ab 0,96 m: zerbröselter Gipskarton, eingerissene Dämmung, durchtrennte und verbogene Ständer; die vom Loch angeschnittenen Platten sind abgefallen; Schuttkegel auf beiden Seiten | 4432 | 1023–1032 | Schutt 51,7 cm, über 45 cm Höhe 1,3 cm |
| `mall_wand_ecke` | Pfosten 21 × 21 cm: zwei Reihen Steinplatten mit Eckschutzwinkeln aus Aluminium, Schattenfuge, darüber Gipskarton; Sockel aus dunklem Stein rundum | 210 | 1024–1024 | 1,5 cm (Sockel) |

Die Pixeldichte ist an den exportierten Dateien gemessen. Flache Teile liegen genau bei 1024 px/m. Die kleinen Abweichungen stammen von der gewellten Dämmung, den gebogenen Profilen und Schuttstücken und von der Rundung auf 32-Bit-Zahlen in der Datei.

## Stil

- **Steinplatten bis 1,2 m:** beiger Kalkstein, 60 × 60 cm und 15 mm dick, als echte Geometrie mit 3-mm-Fugen und kleinen Fasen. Je Seite zwei Reihen, die Randplatten sind 40 cm breit. Jede Platte hat einen eigenen Ton, mit Fossilien, Muschelresten und Stylolithen. Dazu kommen Schmutz, eine Wischkante, Schuhschrammen, dunkle Fugen, Laufspuren und feine Haarrisse.
- **Schäden an den Platten:** gesprungene Platten haben einen echten Riss mit Flanken. Wo Platten abgefallen sind, sieht man das Kleberbett mit Kammspuren und Steinresten. Abgebrochene Ecken enden in einer rauen Bruchkante.
- **Sockel:** dunkler, polierter Granit, 10 cm hoch und 1,5 cm vor den Platten, oben mit kleiner Fase.
- **Gipskarton darüber:** über den Platten eine Schattenfuge (8 mm hoch, 12 mm tief), darüber zwei Lagen Gipskarton bis zur Decke. Die Farbe ist ein helles Grauweiß, nach oben hin vergilbt. Plattenstöße sind mit Spachtelstreifen geschlossen, über den Ständern sitzen Schraubenreihen, manche rostig. Es gibt Schmutz und Griffspuren, einen Wasserlauf von der Decke und Stockflecken über dem Steinbereich, unter der Decke, am Wasserfleck und entlang der Plattenstöße.
- **Plakatreste:** drei abgerissene Plakate mit Kleisterflächen, Papierfetzen mit verblichenem Druck, weißen Rissrändern und Heftklammern.
- **Graffiti:** eine übermalte Fläche mit Rollenspuren, unter der ein altes NOVA durchscheint, daneben ein kleiner schwarzer Tag NOVA. Dazu ein silbernes OK mit schwarzer Kontur, REX in Schwarz und KAZ in Rot, beide mit Läufern, und ZERO in Filzstift auf einem Plakatrest.
- **Untergrund hinter beschädigtem Gipskarton:** verzinkte Metallständer alle 62,5 cm mit 5 cm breiten Flanschen, dazwischen gelbe Glaswolle, gewellt und stellenweise ausgerissen. Dahinter liegt die graue Kartonrückseite der Gegenplatte mit Stempel. Der Lochrand ist zerbröselt, an der Bruchkante sieht man den Gipskern beider Lagen zwischen den Kartonschichten.
- **Zarge:** Umfassungszarge aus eloxiertem Aluminium. Der Spiegel ist 6 cm breit und steht 2 cm vor der Wand, in der Laibung liegt das Futter. Der Anschlag hat eine Gummidichtung, dazu kommen drei Bänder.
- **Schaufenster:** die Laibung zeigt den gestrichenen Gipskarton. Der Blendrahmen aus eloxiertem Aluminium hat 5 cm Ansicht und ist 10 cm tief. Der Glasfalz ist leer, Glasleisten und Dichtungen sind noch da, es gibt kein Glas und kein Gitter. Auf −Y liegt eine Bank aus dunklem Stein, auf +Y ein Alublech.
- **Leitungen (wand_03, +Y):** direkt unter der Decke ein Kabelkanal (6 × 10 cm), darunter das rote Sprinklerrohr (Ø 6 cm) mit drei Schellen und zwei hängenden Sprinklern aus Messing mit Glasfass. Beide enden bündig an beiden Kanten.
- **Feuerlöscherkasten (wand_03, +Y):** ein rot lackierter Kasten (38 × 62 cm, 13 cm tief), in die Ständerwand eingelassen, Mitte auf 1,58 m, mit 2,5 cm breiter Blende. Die Tür ist um 180° aufgeklappt und liegt flach neben dem Kasten, die Innenseite mit Prüfplakette und Schloss zeigt nach vorn. Innen sitzen oben das Schild FEUERLÖSCHER und das Rettungszeichen, darunter hängt ein Feuerlöscher mit Schlauch an seiner Halterung.
- **Durchbruch:** das Loch geht durch die ganze Ständerwand. Der Gipskarton ist am Rand zerbröselt, dahinter sieht man die Kartonrückseite und die eingerissene Dämmung. Die durchtrennten Ständer ragen verbogen in die Öffnung, vor allem zur Seite gebogen. In der oberen Plattenreihe sind die Platten abgefallen, die das Loch anschneidet, darunter ist eine Platte gesprungen. Auf beiden Seiten liegt ein Schuttkegel aus Gipsbrocken und Gipsstaub mit Gipskartonstücken, Steinscherben, Dämmflocken und einem verbogenen Profilstück.

## Regeln und wie sie eingehalten sind

- **Maße:** Grundkörper X −1,9 … +1,9, Z 0 … 3,4, Y −0,1 … +0,1 m. Drehpunkt unten mittig, im glTF ohne Transformation.
- **Kanten:** Die Randplatten sind bei allen Stücken heil. Links und rechts ist das Kantenbild bei allen Wänden gleich, auch bei den UVs. An jeder Kante endet die Plattenreihe mit einer halben Fuge. Bei wand_03 kommen auf +Y Kabelkanal und Sprinklerrohr dazu, die bündig an den Kanten enden.
- **Randzone:** Schäden halten mindestens 40 cm Abstand zu den Kanten. Die Prüfung vergleicht die Randzonen jedes Stücks Punkt für Punkt mit dem intakten wand_01.
- **Vorstand:** Nichts ragt mehr als 12 cm vor die Wandfläche. Die Zarge steht 2 cm vor, die Fensterbänke 3 cm, das Sprinklerrohr mit seinen Schellen 8 cm. Nur der Schutt am Durchbruch reicht weiter, höchstens 60 cm.
- **Dreiecke:** höchstens 3000 je Stück, beim Durchbruch höchstens 6000, beim Pfosten höchstens 800.
- **Normalen:** keine gekippten oder entarteten Dreiecke, alle Normalen haben die Länge 1.

## Texturen

Zwei kachelbare Sätze mit je 4096 × 4096 px. Alle sieben Stücke nutzen dieselben zwei Materialien und dieselben Bilddateien in `Texturen/mall/`.

| Satz | Inhalt |
|---|---|
| `T_mall_Wand_*` | unter 1,2 m die beigen Kalksteinplatten mit Fugen, darüber der gestrichene Gipskarton mit Stockflecken, Plakatresten und Graffiti |
| `T_mall_Detail_*` | Streifen-Atlas: Kleberbett, Bruchfläche und Kanten des Steins, Rissflanken, Gipskern, Kartonrückseite, gelbe Glaswolle, verzinktes Ständerprofil, Granitsockel, eloxiertes Aluminium (fünf Breiten), Gummi, Kabelkanal, roter Lack, Feuerlöscherkasten (Rückwand und Türinnenseite), Feuerlöscher, schwarzer Kunststoff, Messing, Stahl (zwei Breiten) |

Je Satz gibt es drei Dateien:

- `_Grundfarbe.jpg`: Farbe (sRGB).
- `_Normale.png`: Normal-Karte im OpenGL-Format, wie glTF es vorschreibt. Falls deine Engine DirectX erwartet und die Beulen falsch herum wirken, beim Import den Grünkanal umdrehen.
- `_Rauheit.png`: Rauheit im Grünkanal, Metall im Blaukanal (glTF-Packing, Rotkanal = 1).

**Maßstab:** UV 0,25 je Meter, also 1024 px/m. Eine Texturbreite sind 4 m und kachelt waagerecht nahtlos.

## Raster und Wandbild

- Wie beim Labor hängt das Wandbild am Stück, nicht am 4-m-Weltraster. Die Plattenfugen x = −1,9 / −1,5 / −0,9 / −0,3 / 0,3 / 0,9 / 1,5 / 1,9 liegen auf beiden Seiten bei 0,1 / 0,5 / 1,1 / 1,7 / 2,3 / 2,9 / 3,5 / 3,9 m im Bild. So passt jede Platte in jeder Drehung genau auf ihre Fläche im Bild, auch die abgefallenen, gesprungenen und abgebrochenen.
- Der Bereich 3,9 … 4,1 m im Bild gehört dem Pfosten. Seine Plattenfugen liegen unter den Eckschutzwinkeln.
- Die Wände passen ins 4-m-Raster mit einem Pfosten an jeder Stoßstelle. Sie können auch direkt aneinanderstoßen (3,8 m Abstand), dann ergeben die beiden halben Fugen an der Stoßstelle eine normale 3-mm-Fuge.
- Das Wandbild wiederholt sich auf jedem Stück. Wer mehr Abwechslung will, legt Decals mit weiteren Plakaten oder Tags darüber.
- Die Fensterlaibung zeigt Gipskarton aus einer ruhigen Stelle des Wandbilds, zwischen zwei Schraubenreihen und ohne Plattenstoß. So erscheinen in der Laibung weder Steinplatten noch Fugen.
