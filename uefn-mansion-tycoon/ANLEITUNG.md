# Mansion Tycoon für UEFN

Ein Tycoon-Spiel für Fortnite (Unreal Editor for Fortnite). Der Spieler startet mit einem kleinen Haus und $10.000 und baut daraus Schritt für Schritt einen **Billionaire Estate**.

Der komplette Spielablauf steckt im Verse-Code: Geld, Einkommen, Räume, Möbel, Fahrzeuge, Personal, Upgrades, Mansion-Stufen, XP, Level, Quests, Rangliste, Benachrichtigungen und Speicherstand. Du baust in UEFN nur noch die Mansion aus Props und verknüpfst sie mit dem Device.

## Dateien

| Datei | Inhalt |
|---|---|
| `Verse/mansion_catalog.verse` | Alle Spieldaten: 28 Räume, Grundstück, 14 Möbel, 7 Fahrzeuge, 6 Mitarbeiter, 7 Mansion-Stufen, 23 Quests, Balancing und Zahlenformatierung |
| `Verse/mansion_hud.verse` | HUD oben und rechts, Benachrichtigungen, Estate-Tablet (Menü mit 7 Reitern) |
| `Verse/mansion_plot_device.verse` | Das Device `mansion_plot_device`: Einkommen, Kaufen, Quests, Speichern, Props ein- und ausblenden |

## Einbau in 8 Schritten

1. **Projekt anlegen:** Neues UEFN-Projekt, am besten mit einer leeren Insel.
2. **Verse-Dateien kopieren:** Die drei `.verse`-Dateien in den Verse-Ordner deines Projekts legen (Verse Explorer → Rechtsklick auf den Projektordner → *Add existing file* oder per Datei-Explorer). Danach **Verse → Build Verse Code**.
3. **Device platzieren:** Im Content Browser unter *Creative Devices* das neue `mansion_plot_device` auf die Insel ziehen.
4. **Mansion bauen:** Baue das Haus aus Props in allen Ausbaustufen, zum Beispiel:
   - Für jede Mansion-Stufe eine eigene Außenhülle (Small House, Modern House, …, Billionaire Estate).
   - Für jeden Raum die Wände, Böden und die Einrichtung.
   - Für jedes Möbelstück eine Version pro Qualität (Basic, Premium, Luxury, Elite).
   - Für Garage, Grundstück und Außenanlagen die Anbauten.

   Alles darf am Anfang sichtbar sein. Das Device blendet beim Start alles aus, was der Spieler noch nicht besitzt.
5. **Kauf-Buttons:** Stelle `Button`-Devices an die Stellen, an denen gekauft wird (zum Beispiel vor jedem Raum). Der Text auf dem Button wird automatisch gesetzt, etwa „Basic Kitchen - $1,500“.
6. **Estate-Tablet:** Stelle ein `Button`-Device an den Eingang (zum Beispiel auf einen Laptop-Prop) und trage es bei **MenuButtons** ein. Optional zusätzlich ein `Input Trigger`-Device bei **MenuInputs**, damit sich das Menü per Taste öffnen lässt.
7. **Device einstellen:** siehe nächster Abschnitt.
8. **Testen:** *Launch Session*. Mit **IgnoreSaves = true** startest du bei jedem Test von vorn.

## Einstellungen am Device

| Feld | Bedeutung |
|---|---|
| **AutoClaim** | `true`: Jeder Spieler bekommt beim Betreten automatisch ein freies Grundstück. |
| **ClaimButtons** | Optional: Buttons, mit denen ein Spieler das Grundstück übernimmt (wenn AutoClaim aus ist). |
| **MenuButtons / MenuInputs** | Öffnen und schließen das Estate-Tablet. |
| **TierUpgradeButtons** | Optional: Button in der Welt für „Upgrade to Modern House“ usw. Das geht auch im Tablet unter MANSION. |
| **WorldLinks** | Die Verknüpfung von Katalog-Einträgen mit Props und Buttons, siehe unten. |
| **TierLinks** | Pro Mansion-Stufe (1–7) die Props der Außenhülle. |
| **StackTierProps** | `false`: Nur die Hülle der aktuellen Stufe ist sichtbar. `true`: Alle erreichten Hüllen bleiben stehen (für Anbauten). |
| **AnimateNewProps** | Neu gekaufte Props fahren in 0,8 Sekunden aus dem Boden. |
| **PurchaseSounds / LevelUpSounds** | `Audio Player`-Devices für Kauf- und Level-up-Sound. |
| **StartCash** | Startgeld, Standard 10.000. |
| **IgnoreSaves** | Zum Testen: ignoriert gespeicherte Spielstände. Vor dem Veröffentlichen auf `false` stellen. |

### WorldLinks

Für jeden Eintrag im Katalog, der in der Welt sichtbar sein soll, legst du einen WorldLink an:

- **ItemId:** die ID aus der Tabelle unten, zum Beispiel `kitchen`.
- **BuyButtons:** ein oder mehrere Buttons, die diesen Eintrag kaufen oder verbessern.
- **Level1Props … Level5Props:** die Props jeder Ausbaustufe. Bei Möbeln ist Level 1 = Basic, 2 = Premium, 3 = Luxury, 4 = Elite.
- **Stacking:**
  - `false` (Standard): Nur die Props der aktuellen Stufe sind zu sehen. Passt für Möbel und Raum-Upgrades, bei denen die alte Version ersetzt wird.
  - `true`: Props aller gekauften Stufen bleiben sichtbar. Passt für Garage und Grundstück, die wachsen.

Du musst nicht alles verknüpfen. Alles lässt sich auch ohne Props über das Estate-Tablet kaufen. Für den Spaß sollte aber jeder Kauf in der Welt sichtbar sein.

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

Ein `mansion_plot_device` ist ein Grundstück für einen Spieler. Für 4 Spieler baust du 4 Grundstücke mit je einem eigenen Device. Wenn du ein fertiges Grundstück kopierst, zeigen die Verweise im kopierten Device noch auf die alten Props. Du musst sie deshalb im neuen Device auf die kopierten Props umstellen. Jeder Spieler bekommt höchstens ein Grundstück.

## Wichtig

Ich konnte den Code hier nicht in UEFN kompilieren. Wenn **Build Verse Code** Fehler meldet, kopiere mir die Fehlermeldungen. Ich behebe sie dann.
