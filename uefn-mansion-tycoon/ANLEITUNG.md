# Mansion Tycoon für UEFN

Ein Tycoon-Spiel für Fortnite (Unreal Editor for Fortnite). Der Spieler startet mit einem kleinen Haus und $10.000 und baut daraus Schritt für Schritt einen **Billionaire Estate**.

Alles steckt im Verse-Code: Geld, Einkommen, Räume, Möbel, Fahrzeuge, Personal, Upgrades, Mansion-Stufen, XP, Level, Quests, Rangliste, Benachrichtigungen, Speicherstand und der Bau der Mansion selbst. Du platzierst nur ein Device und gibst ihm Würfel-Props als Bausteine.

## Dateien

| Datei | Inhalt |
|---|---|
| `Verse/mansion_catalog.verse` | Alle Spieldaten: 28 Räume, Grundstück, 14 Möbel, 7 Fahrzeuge, 6 Mitarbeiter, 7 Mansion-Stufen, 23 Quests, Balancing |
| `Verse/mansion_builder.verse` | Der automatische Bau: Grundriss, Räume, Möbel, Autos, Personal, Pool, Courts, Helipad und die Architektur jeder Mansion-Stufe |
| `Verse/mansion_hud.verse` | HUD oben und rechts, Benachrichtigungen, Estate-Tablet (Menü mit 7 Reitern) |
| `Verse/mansion_plot_device.verse` | Das Device `mansion_plot_device`: Einkommen, Kaufen, Quests, Speichern, Bauen |

## Die Mansion baut sich selbst

Du musst die Mansion nicht von Hand bauen. Das Device setzt sie aus Würfeln mit verschiedenen Materialien zusammen, im Stil einer modernen Luxus-Villa: Flachdächer, Glasfronten, Marmor und Gold. Jeder Kauf baut sofort etwas dazu, und neue Teile fahren animiert aus dem Boden.

**Was du siehst:**
- **Start (Small House):** Rasenstück, Eingangshalle, leeres Wohnzimmer und ein Gartenweg.
- **Jeder Raum** ist ein Feld von 10 × 10 m mit Boden, Rückwand, Glasfront, Flachdach und typischer Einrichtung. Die Küche hat eine Arbeitsplatte, das Bad eine Wanne, die Bibliothek Regale, der Indoor-Pool Wasser usw.
- **Raum-Upgrades:** ab Stufe 2 eine Dachkante, ab Stufe 3 Marmorboden und Lichtleiste, ab Stufe 4 goldene Kante, ab Stufe 5 goldene Säulen.
- **Obergeschoss** über dem Erdgeschoss, **Luxusflügel** rechts und hinten.
- **Möbel** stehen im passenden Raum. Ihre Qualität sieht man am Material: Basic = Holz, Premium = Stoff, Luxury = Dunkel, Elite = Gold.
- **Garage:** wächst von 1 auf 4 Felder. Die Autos parken darin, der Golden Hypercar ist aus Gold.
- **Personal:** als Figuren an ihrem Arbeitsplatz, der Butler mit goldener Fliege.
- **Außen:** Garten mit Hecken, Bäumen und Blumenbeeten, Brunnen, Pool mit Infinity-Kante, Lounge, Tennis- und Basketballplatz, Helipad.
- **Grundstück:** Die Rasenfläche wächst mit jeder Stufe, ab Stufe 2 mit Mauer.
- **Mansion-Stufen:**
  - **Modern House:** Vordach am Eingang.
  - **Luxury Villa:** Marmorsäulen über zwei Etagen und eine Auffahrt.
  - **Mansion:** Einfahrtstor und Laternen.
  - **Luxury Mansion:** Glas-Atrium und goldenes Fassadenband.
  - **Mega Mansion:** Penthouse-Etage und Lichtsäulen.
  - **Billionaire Estate:** goldene Krone, goldenes Tor, Statue und vier Lichtstrahlen in den Himmel.

**Ausrichtung:** Die Vorderseite zeigt in Richtung −Y des Devices. Drehst du das Device, dreht sich die ganze Mansion mit. Das Grundstück braucht im Endausbau etwa 180 × 120 m freie, ebene Fläche um das Device herum.

## Einbau in 6 Schritten

1. **Projekt anlegen:** Neues UEFN-Projekt mit einer leeren, flachen Insel.
2. **Verse-Dateien kopieren:** Die vier `.verse`-Dateien in den Verse-Ordner des Projekts legen. Danach **Verse → Build Verse Code**.
3. **Würfel-Props anlegen:** Du brauchst einen Würfel als Prop, am besten einen pro Material.
   - Kopiere den Engine-Würfel (`/Engine/BasicShapes/Cube`, 100 × 100 × 100 cm) in deinen Content-Ordner.
   - Erstelle daraus ein Prop. In UEFN geht das über **Rechtsklick auf das Mesh → Create Prop** bzw. über eine Blueprint-Klasse vom Typ *Creative Prop*. Je nach UEFN-Version heißt der Menüpunkt etwas anders.
   - Lege für jedes Material eine Kopie des Props an und gib ihr das passende Material: Wall (weiß), Floor (helles Holz), Marble (heller Marmor), Glass (durchsichtig, leicht blau), Roof (dunkelgrau), Wood (Holz), Fabric (Stoff, z. B. Rot), Dark (fast schwarz), Gold (glänzend gold), Water (blau, durchsichtig), Grass (grün), Court (blau oder grün), Line (weiß), Stone (grauer Stein), Glow (leuchtend, Emissive).
   - Zum Ausprobieren reicht **ein einziger Würfel**. Fehlende Materialien ersetzt das Device dann durch den ersten Eintrag.
4. **Device platzieren:** `mansion_plot_device` auf eine freie Fläche ziehen. Das wird die Mitte der Mansion.
5. **Device einstellen:**
   - **BlockAssets:** für jedes Material einen Eintrag mit *Kind* (z. B. Gold) und *Asset* (dein Gold-Würfel-Prop).
   - **MenuButtons:** einen `Button` am Eingang als Estate-Tablet zuweisen. Optional einen `Input Trigger` bei **MenuInputs** für eine Taste.
   - **IgnoreSaves = true** zum Testen.
6. **Testen:** *Launch Session*. Öffne das Tablet, kaufe Räume und sieh zu, wie die Mansion wächst.

## Einstellungen am Device

| Feld | Bedeutung |
|---|---|
| **AutoBuild** | `true`: Das Device baut die Mansion automatisch. |
| **BlockAssets** | Die Würfel-Props pro Material (siehe oben). |
| **CubeSize** | Kantenlänge deines Würfel-Meshes in cm, Standard 100. |
| **CubePivotAtBottom** | `true`, wenn der Pivot deines Würfels unten in der Mitte sitzt statt im Zentrum. |
| **CellSize / FloorHeight** | Größe eines Raum-Feldes (Standard 1000 cm) und Etagenhöhe (Standard 450 cm). |
| **RoomDetail** | `false` spart Props: Räume ohne Glasfront und Seitenwand. |
| **AnimateNewProps** | Neue Teile fahren in 0,8 Sekunden aus dem Boden. |
| **AutoClaim** | Jeder Spieler bekommt beim Betreten automatisch ein freies Grundstück. |
| **ClaimButtons** | Optional: Buttons zum Übernehmen des Grundstücks, wenn AutoClaim aus ist. |
| **MenuButtons / MenuInputs** | Öffnen und schließen das Estate-Tablet. |
| **TierUpgradeButtons** | Optional: Button in der Welt für das nächste Haus-Upgrade. |
| **PurchaseSounds / LevelUpSounds** | `Audio Player`-Devices für Kauf- und Level-up-Sound. |
| **StartCash** | Startgeld, Standard 10.000. |
| **IgnoreSaves** | Ignoriert gespeicherte Spielstände. Vor dem Veröffentlichen auf `false` stellen. |
| **WorldLinks / TierLinks** | Optional: Wenn du zusätzlich eigene, von Hand gebaute Props zeigen willst. Funktioniert wie unten beschrieben. |

### Optional: eigene Props zusätzlich (WorldLinks)

Willst du statt Würfeln echte Möbel, Autos oder Fortnite-Props zeigen, verknüpfe sie über **WorldLinks**:

- **ItemId:** die ID aus der Tabelle unten, zum Beispiel `kitchen`.
- **BuyButtons:** Buttons in der Welt, die diesen Eintrag kaufen.
- **Level1Props … Level5Props:** deine Props pro Ausbaustufe. Bei Möbeln ist 1 = Basic, 2 = Premium, 3 = Luxury, 4 = Elite.
- **Stacking:** `false` zeigt nur die aktuelle Stufe, `true` zeigt alle gekauften Stufen.

Das Device blendet diese Props passend ein und aus. Den automatischen Bau kannst du dann mit **AutoBuild = false** abschalten oder beides kombinieren.

## Alle IDs

**Erdgeschoss:** `entrance` (gehört von Anfang an), `living` (gehört von Anfang an, leer), `kitchen`, `bath_ground`, `dining`, `office`, `garage`

**Obergeschoss** (ab Modern House): `master_bed`, `bed2`, `bath_upper`, `bed3`, `closet`, `gaming`

**Luxusbereiche** (ab Luxury Villa): `gym`, `cinema`, `library`, `wine_cellar`, `game_room`, `indoor_pool`, `spa`, `music_room`

**Außenbereich:** `garden`, `fountain`, `swimming_pool`, `outdoor_lounge`, `basketball`, `tennis`, `helipad`

**Grundstück:** `land` (5 Stufen von Small Plot bis Private Peninsula, gehört ab Stufe 1)

**Möbel** (je 4 Qualitäten): `sofa`, `tv`, `plants`, `table`, `desk`, `computer`, `bed`, `kitchen_island`, `artwork`, `aquarium`, `gym_equipment`, `luxury_lights`, `pool_table`, `cinema_screen`

**Fahrzeuge:** `sports_car`, `luxury_suv`, `classic_roadster`, `supercar`, `limousine`, `hypercar`, `golden_hypercar`

**Personal:** `cleaner`, `gardener`, `chef`, `driver`, `security`, `butler`

## So funktioniert das Spiel

**Mansion-Stufen**

| Stufe | Kosten | Voraussetzung | Grundeinkommen |
|---|---|---|---|
| 1 Small House | Start | – | $100/min |
| 2 Modern House | $15K | Level 3, 4 Räume | $500/min |
| 3 Luxury Villa | $200K | Level 6, 8 Räume | $2,500/min |
| 4 Mansion | $1.5M | Level 9, 13 Räume | $10,000/min |
| 5 Luxury Mansion | $12M | Level 12, 18 Räume | $30,000/min |
| 6 Mega Mansion | $90M | Level 15, 23 Räume | $100,000/min |
| 7 Billionaire Estate | $750M | Level 18, alle 28 Räume | $500,000/min |

**Preise und Ausbau:** Jede Ausbaustufe kostet das 7-fache der vorherigen und braucht eine Mansion-Stufe höher. Beispiel Küche: Basic Kitchen ($1,500, Small House) → Modern Kitchen ($10.5K, Modern House) → Luxury Kitchen → Professional Kitchen → Billionaire Kitchen ($3.6M, Luxury Mansion).

**Einkommen:** Jeder Kauf erhöht das Einkommen pro Minute. Am Anfang hat sich ein Kauf nach etwa 2 Minuten bezahlt gemacht, am Ende nach etwa 4,5 Minuten. Personal gibt einen Prozent-Bonus auf das gesamte Einkommen (zusammen +70 %). Das Geld kommt jede Sekunde.

**Mansion Value:** Summe aus Haus-Stufen, Räumen, Möbeln, Fahrzeugen, Grundstück und Personal. Fahrzeuge und Grundstück zählen besonders viel. Der **Mansion Rank** vergleicht den Wert mit einer Rangliste der 100 teuersten Anwesen (Platz 1 ab $3 Mrd.).

**XP und Level:** XP gibt es für jeden Kauf (30 × Stufe), jedes Haus-Upgrade, Quests und alle 10 Sekunden fürs Geldverdienen. Neue Level schalten Räume, Möbel, Autos und Personal frei.

**Garage:** Single Garage (1 Platz), Double Garage (2), Car Gallery (4), Supercar Showroom (7). Ein Auto lässt sich nur mit freiem Platz kaufen.

**Quests:** 23 Aufgaben, von „Build your first room“ bis „Reach Mansion Rank #1“. Sie werden automatisch abgeschlossen und belohnen mit Geld und XP.

**Speichern:** Der Fortschritt wird pro Spieler mit der Fortnite-Persistenz gespeichert (alle 10 Sekunden, nach jedem Kauf und beim Verlassen).

**Spielzeit:** etwa 30 bis 40 Minuten bis zum Billionaire Estate, danach noch Ziele für alle Elite-Möbel, alle Autos und Rang 1.

## Mehrere Spieler

Ein `mansion_plot_device` ist ein Grundstück für einen Spieler. Für 4 Spieler platzierst du 4 Devices mit genug Abstand (mindestens 200 m). Weil die Mansion automatisch gebaut wird, kannst du das Device einfach kopieren. Jeder Spieler bekommt höchstens ein Grundstück.

## Prop-Anzahl

Eine voll ausgebaute Mansion besteht aus etwa 300 Würfeln. Falls UEFN beim Spawnen an eine Grenze stößt oder der Speicher knapp wird, stelle **RoomDetail = false** ein. Das spart etwa 60 Props.

## Wichtig

Ich konnte den Code hier nicht in UEFN kompilieren. Wenn **Build Verse Code** Fehler meldet, kopiere mir die Fehlermeldungen. Ich behebe sie dann.
