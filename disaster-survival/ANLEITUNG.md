# Disaster Survival für Unity

Ein Katastrophen-Survival-Spiel mit dem Survival-Missions-System: Jede Runde bringt eine neue Katastrophe, eigene Missionen, eine geheime Mission pro Spieler, Ereignisse alle 30 bis 60 Sekunden und ein großes Finale. Über viele Matches steigt man im Rang auf und schaltet kosmetische Belohnungen frei. Jedes Match erzählt am Ende seine eigene Geschichte.

## Was drin ist

| Teil | Ordner | Inhalt |
|---|---|---|
| **Spielregeln** | `Unity/Assets/DisasterSurvival/Core/` | Reines C# ohne Unity-Abhängigkeit: Missionen, geheime Missionen, Ereignis-Regie, Punkte, Story, Ränge, Freischaltungen |
| **Unity-Teil** | `Unity/Assets/DisasterSurvival/Runtime/` | Spieler, Zonen, Funkgeräte, Notfallkoffer, Bunkertür, Tornado, Flut, Lava, Feuer, Einsturzzonen, Nebel, Versorgungskisten, HUD, Speichern, Bots |
| **Testarena** | `Unity/Assets/DisasterSurvival/Editor/` | Ein Menüpunkt baut eine spielbare Arena mit dir und 3 Bots |
| **Tests** | `Tests/Simulation.cs` | Simuliert ganze Matches und prüft die Regeln |

## In 3 Minuten spielen

1. Unity **2022.3 LTS oder Unity 6** öffnen (mindestens 2021.3.18), ein neues **3D-Projekt** anlegen (Built-in oder URP).
2. Den Ordner `Unity/Assets/DisasterSurvival` in den `Assets`-Ordner deines Projekts kopieren.
3. Im Menü **Tools → Disaster Survival → Build Demo Scene** klicken.
4. **Play** drücken.

**Steuerung:** WASD laufen, Maus umsehen, Shift rennen, Leertaste springen, **E** benutzen (Funkgerät, Koffer, Verletzte tragen, Kiste öffnen), **G** ablegen. Controller geht auch.

Die Testarena ist ein Graubox-Level aus einfachen Formen: Rettungsstation auf einer Plattform, Bunker mit automatischer Tür, Turm mit Rampe zum Dach, 5 Notfunkgeräte, Notfallkoffer, 3 Häuser, die bei Nachbeben einstürzen. Dazu kommen je nach Katastrophe Tornado, Flutwasser, Lava, Feuerwalze oder Eisfeld.

## So läuft eine Runde

**Missionen:** Jede Runde zieht 3 Missionen aus dem Pool der Katastrophe. „Überleben“ ist immer dabei.

| Mission | SP |
|---|---|
| Überleben | 500 |
| 3 Notfunkgeräte aktivieren | 400 |
| Einen anderen Spieler retten | 600 |
| Notfallkoffer zur Rettungsstation bringen | 300 |
| Bunker 60 Sekunden halten | 800 |
| Aufs Dach kommen | 250 |
| Letzter Überlebender | 400 |

„Letzter Überlebender“ ist bewusst kleiner als von dir vorgeschlagen, damit Verstecken sich nicht lohnt.

**Geheime Mission (+700 SP):** Jeder Spieler bekommt eine, die nur er sieht. Zum Beispiel:
- „Erreiche die Rettungsstation vor Ben.“
- „Halte Ben von der Rettungsstation fern.“
- „Wenn Ben verletzt wird, musst du ihn retten.“
- „Aktiviere mehr Geräte als alle anderen.“

Rettungsereignisse treffen bevorzugt Spieler, um die sich eine geheime Mission dreht. Dort entsteht das Drama. Nach der Runde werden die geheimen Missionen aufgedeckt.

**Ereignisse:** Das erste nach 20 Sekunden, dann alle 30 bis 60 Sekunden, passend zur Katastrophe. Die Runde hat einen Spannungsbogen: Anfang, Verschärfung, Finale. Bei 78 % der Zeit kommt immer ein großes Finale, etwa „Supercell“ beim Tornado oder „Second dam breaks“ bei der Flut.

| Ereignis | Wirkung |
|---|---|
| Tornado changes direction / The wind turns | Gefahr dreht ab, oft auf die größte Spielergruppe zu |
| Power failure | Bunkertüren schließen und bleiben zu |
| Rescue event | Ein Spieler wird verletzt. Wird er nicht rechtzeitig zur Station getragen, ist er raus |
| Flood wave | Wasser steigt schnell an |
| Aftershock | Häuser stürzen ein |
| Thick smoke | Sicht fast null |
| Supply drop | Kiste fällt vom Himmel, wer zuerst kommt, bekommt Bonuspunkte |

**Zurücklassen:** Wer neben einem Verletzten stand und dann allein zur Rettungsstation läuft, hat ihn „zurückgelassen“. Das merkt sich das Spiel.

**Geschichte:** Nach jeder Runde gibt es einen Rückblick, am Ende des Matches eine Geschichte über alle Runden. Das Spiel erinnert sich an frühere Runden, zum Beispiel:
- „Ben lässt Alex zurück – obwohl Alex Ben in Runde 1 gerettet hat.“
- „Alex lässt Cleo zurück. Rache für Runde 2.“
- „Dana rettet Cleo und revanchiert sich für Runde 3.“

## Ränge und Freischaltungen

| Rang | Voraussetzung | Laut Simulation nach |
|---|---|---|
| Rookie | Start | – |
| Survivor | 6.000 SP | ~2 Matches |
| Veteran | 35.000 SP, 10 Rettungen, 3 Katastrophen überlebt | ~10 Matches |
| Elite | 120.000 SP, 30 Rettungen, 2× letzter Überlebender, 8 geheime Missionen, 5 Katastrophen | ~40 Matches |
| Disaster Master | 350.000 SP, 80 Rettungen, 5× letzter Überlebender, 25 geheime Missionen, alle 6 Katastrophen | ~110 Matches |

Es gibt 21 Freischaltungen, alle kosmetisch: Ausrüstung, Charaktere, Animationen, Outfits, Emotes, Titel, Banner, Fahrzeuge und Spawn-Effekte. Ein Teil kommt über den Rang. Ein anderer Teil kommt über das, was man tut: „Lifesaver“ für 10 Rettungen, „Storm Chaser“ für 10 überlebte Tornados, das Emote „Not My Problem“ für 5 zurückgelassene Verletzte.

Der Fortschritt wird als JSON-Datei in `Application.persistentDataPath` gespeichert. Die Freischaltungen sind bisher nur Einträge im Profil. Die echten Modelle, Outfits und Effekte musst du noch bauen und mit den IDs verknüpfen.

## Eigene Map bauen

Die Testarena ist nur zum Ausprobieren. Für deine eigene Map setzt du die Komponenten auf eigene Objekte:

| Komponente | Wofür |
|---|---|
| `DisasterGameManager` | Einmal pro Szene. Spawnpunkte, Rundenzahl, Ereignis-Abstände |
| `DisasterHud` | Fertiges HUD, auf den Manager legen. Später durch eigene UI ersetzen |
| `PlayerAgent` | Auf jeden Spieler. Deinen Bewegungs-Controller bei **Disable When Down** eintragen |
| `MissionZone` | Trigger für `rescue_station`, `bunker`, `rooftop` |
| `EmergencyRadio` | Notfunkgerät |
| `DeliveryItem` | Notfallkoffer |
| `BunkerDoor` | Tür, die beim Stromausfall zugeht |
| `HazardVolume` | Tödlicher Bereich, immer oder nur bei einem Ereignis (z. B. Einsturz bei GroundShaking) |
| `HazardMover` | Bewegt Tornado, Feuer oder Lavastrom und dreht bei Ereignissen ab |
| `FloodWater` | Wasser oder Lava, steigt bei Flutwellen |
| `VisibilityEffect` | Nebel bei Rauch, Schnee, Asche |
| `SupplyDrop` / `SupplyCrate` | Versorgungskisten |
| `DisasterSpecific` | Objekt nur bei bestimmten Katastrophen zeigen |
| `SimpleBot` | Testgegner |

Alle Zahlen und Texte (Missionen, Punkte, Ereignisse, Ränge, Freischaltungen) stehen in `Core/Content.cs`. Die Spieltexte sind auf Englisch und lassen sich dort übersetzen.

## Wichtig zu wissen

- **Getestet:** Die Spielregeln laufen in einer Simulation über hunderte Matches, alle Prüfungen bestehen. Die Unity-Skripte kompilieren fehlerfrei gegen Unity 2021.3.
- **Nicht getestet:** Den Editor-Knopf für die Testarena konnte ich nicht kompilieren, und ich konnte das Spiel nicht in Unity starten. Meldet Unity Fehler, schick sie mir.
- **Online-Mehrspieler ist nicht enthalten.** Das Spiel läuft lokal mit Bots. Für echtes Online-Spiel brauchst du z. B. Netcode for GameObjects. Der `DisasterGameManager` läuft dann nur auf dem Host, die Spielregeln sind dafür schon getrennt gebaut.

## Tests selbst ausführen

Ohne Unity, mit Mono:

```
cd Tests
mcs -out:sim.exe ../Unity/Assets/DisasterSurvival/Core/*.cs Simulation.cs
mono sim.exe
```

Zeigt ein komplettes Beispiel-Match mit Ereignissen, Rückblick und Geschichte, prüft alle Regeln und misst, wie lange der Weg bis Disaster Master dauert.
