# Disaster Survival für UEFN (Fortnite)

Dieselben Regeln wie die Unity-Fassung:
- jede Runde eine neue Katastrophe,
- 3 gemeinsame Missionen und eine geheime Mission pro Spieler,
- alle 30 bis 60 Sekunden ein Ereignis, dazu ein Finale,
- eine Geschichte, die sich an frühere Runden erinnert,
- 5 Ränge und 21 Freischaltungen, gespeichert pro Spieler.

## Dateien

| Datei | Inhalt |
|---|---|
| `Verse/ds_content.verse` | Katastrophen, Missionen, Ereignisse, Ränge, Freischaltungen, Hilfsfunktionen |
| `Verse/ds_progression.verse` | Speicherstand (Fortnite-Persistenz), Rang und Freischaltungen |
| `Verse/ds_hud.verse` | HUD: Timer, Missionen, geheime Mission, Ereignis-Banner, Statuszeile, Rückblick |
| `Verse/ds_world.verse` | Verknüpfung mit Fortnite-Devices, wandernde Gefahren, steigendes Wasser und Lava |
| `Verse/ds_game_manager.verse` | Das Device `ds_game_manager`: der komplette Spielablauf |

## Unterschiede zur Unity-Fassung

| Unity | UEFN | Grund |
|---|---|---|
| Verletzte zur Station tragen | **Erste Hilfe:** 3 Sekunden neben dem Verletzten stehen | Fortnite kann Spieler nicht per Verse tragen lassen |
| Spielernamen | **Farbe als Rufname** pro Match (Red, Blue, Green …) | Verse bietet keinen verlässlichen Zugriff auf Anzeigenamen |
| Eigene Gefahren-Komponenten | Tornado und Flut steuert der Code, alles andere über Fortnite-Devices | So nutzt du vorhandene Devices |

Verletzte Spieler werden eingefroren (sie können sich drehen und emoten). Hilft niemand bis zum Ende des Ereignisses, sind sie raus.

## Einbau

### 1. Verse-Dateien
Die fünf `.verse`-Dateien in den Verse-Ordner deines Projekts legen und **Verse → Build Verse Code** ausführen.

### 2. Insel-Einstellungen
- **Spieler respawnen:** an. Ausgeschiedene Spieler werden automatisch zum Zuschauerbereich teleportiert.
- **Schaden:** an. Tornado, Flut und Schadenszonen müssen Spieler treffen können.
- **Teams:** alle in einem Team oder „Jeder gegen jeden“. Die Spieler sollen sich nicht gegenseitig beschießen. Schaden durch andere Spieler am besten ausschalten.

### 3. Devices platzieren und im `ds_game_manager` eintragen

| Feld | Device | Wofür |
|---|---|---|
| **SpawnTeleporters** | Teleporter | Startpunkte zu Beginn jeder Runde (Zielpunkte setzen) |
| **SpectatorTeleporters** | Teleporter | Zuschauerbereich für Ausgeschiedene (optional, nur der erste zählt) |
| **RescueStationZones** | Mutator Zone | Rettungsstation |
| **BunkerZones** | Mutator Zone | Bunker innen (für „Bunker 60 Sekunden halten“) |
| **RooftopZones** | Mutator Zone | Dach (für „Aufs Dach kommen“) |
| **RadioButtons** | Button | Notfunkgeräte, z. B. 5 Stück. Jeder Spieler kann jedes einmal pro Runde nutzen |
| **KitButtons** | Button | Notfallkoffer aufheben |
| **KitProps** | Prop | Das Koffer-Modell, wird beim Aufheben ausgeblendet |
| **BunkerBarriers** | Barrier | Sperrt den Bunkereingang beim Stromausfall |

### 4. Katastrophen einrichten

**MovingHazards** (Tornado, Feuerwalze, Lavabombe) – ein Prop, das herumwandert und Spieler in der Nähe verletzt:
- **Prop:** z. B. ein Tornado-Prop oder eine große Rauchsäule
- **Disasters:** bei welchen Katastrophen er auftaucht
- **Radius / DamagePerSecond / Speed / AreaRadius:** Wirkradius, Schaden, Tempo und Bewegungsgebiet in cm
- Bei „Tornado changes direction“ oder „The wind turns“ steuert er mit 60 % Wahrscheinlichkeit auf die größte Spielergruppe zu.

**Floods** (Wasser oder Lava) – eine große flache Platte, die steigt:
- **Surface:** z. B. eine große blaue oder orangefarbene Platte, knapp unter dem Boden platziert
- **FloodRise:** wie hoch sie bei einer Flutwelle steigt (cm). Nach jeder Welle bleibt etwas Wasser stehen.
- **ConstantRisePerMinute:** für Lava, die ständig langsam steigt
- **DepthToHurt / DamagePerSecond:** ab welcher Tiefe Spieler Schaden nehmen

**DisasterKits** – Devices, die die ganze Runde einer Katastrophe laufen. Beispiele:
- Waldbrand: Rauch-VFX und Schadenszonen am Waldrand
- Blizzard: Schnee-VFX und Wind-Sound

**EffectHooks** – Devices, die nur während eines Ereignisses laufen. Beispiele:
- **GroundShaking:** Schadenszonen in den Häusern (Einsturz) und Wackel-Sound
- **LowVisibility:** Nebel- oder Rauch-VFX
- **SupplyDrop:** Item Spawner, die Ausrüstung abwerfen
- **WaterRising:** Wellen-Sound
- **Finale:** große Effekte für das Finale

Jeder Eintrag schaltet Damage Volumes, Barrieren, VFX, Prop Mover, Sounds, Item Spawner und Props ein und danach wieder aus. Mit **OnlyDuring** begrenzt du ihn auf bestimmte Katastrophen.

### 5. Testen
Mit **IgnoreSaves = true** startest du beim Testen ohne gespeicherten Fortschritt. Vor dem Veröffentlichen wieder auf `false` stellen.

## Einstellungen am Device

| Feld | Standard | Bedeutung |
|---|---|---|
| RoundsPerMatch | 4 | Runden pro Match |
| MinPlayers | 1 | Ab wie vielen Spielern ein Match startet |
| SharedMissions | 3 | Gemeinsame Missionen pro Runde, „Überleben“ inklusive |
| CountdownSeconds / RecapSeconds / MatchOverSeconds | 8 / 14 / 20 | Pausen zwischen den Runden |
| MinEventGap / MaxEventGap / FirstEventAfter | 30 / 60 / 20 | Abstand der Ereignisse in Sekunden |
| FinaleAt | 0.78 | Bei welchem Anteil der Runde das Finale startet |
| FirstAidRadius / FirstAidSeconds | 350 cm / 3 s | Erste Hilfe |
| AbandonRadius / AbandonMemory | 800 cm / 20 s | Ab wann „zurückgelassen“ zählt |

## Wichtig

Ich konnte den Verse-Code hier nicht kompilieren und nicht in UEFN testen. Er folgt der aktuellen Verse-API, aber ein paar Stellen kann ich nicht sicher prüfen:
- das Einfrieren Verletzter (`PutInStasis`),
- die Prop-Mover-Methoden (`Begin` und `Reverse`),
- die Fortnite-Persistenz.

Wenn **Build Verse Code** Fehler meldet, kopiere mir die Meldungen. Ich behebe sie dann. Mit dem UEFN-MCP auf deinem PC kann eine lokale Claude-Sitzung den Code auch direkt kompilieren und reparieren.
