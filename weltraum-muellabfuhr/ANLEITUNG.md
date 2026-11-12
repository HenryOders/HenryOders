# Weltraum-Müllabfuhr · Prototyp

Ein spielbarer Einzelspieler-Prototyp: Du arbeitest für die Orbit-Entsorgung GmbH, sammelst Weltraumschrott ein und wirfst ihn in die Schleuse am Heck des Müllschiffs.

## Starten

`index.html` im Browser öffnen (Chrome, Edge oder Firefox). Die Dateien `index.html`, `spiel.js` und der Ordner `lib/` müssen zusammenbleiben. Eine Internetverbindung ist nicht nötig.

## Ziel

- Jede Schicht dauert 7 Minuten und hat ein Ziel in Euro.
- Kleiner Schrott lässt sich greifen und werfen, große Teile ziehst du mit dem Greifhaken.
- An der Station oben auf dem Schiff tankst du Luft und Treibstoff und kannst die Schicht beenden.
- Zerlegst du einen Satelliten, entstehen Trümmer, die weitere Satelliten zerschlagen können. Das kostet 100 € Strafe pro Satellit.
- Wer ohne Luft dasteht, wird selbst zu Weltraumschrott. Der alte Anzug treibt in der nächsten Schicht im Feld und bringt eine Prämie.
- Mit dem verdienten Geld kaufst du in der Werkstatt Upgrades. Drei verfehlte Ziele bedeuten die Kündigung.

## Steuerung

| Taste | Aktion |
|---|---|
| Maus | umsehen (vorher ins Bild klicken) |
| W A S D | Düse vorwärts, links, zurück, rechts |
| Leertaste / C | hoch / runter |
| Shift | Turbo |
| X | bremsen |
| Linksklick oder G | Greifhaken schießen oder lösen, beim Tragen: werfen |
| Rechtsklick oder Q (halten) | Haken einholen |
| E | Schrott greifen oder loslassen |
| T | Scanner: zeigt Schrott und seinen Wert |
| R | Sicherungsseil lösen oder anlegen (am orangen Ring auf dem Schiff) |
| F | an der Station: Schicht beenden |
| Pfeiltasten | umsehen ohne Maus |
| M | Ton an oder aus |
| P oder Esc | Pause |

## Was noch fehlt

- Koop für 2 bis 4 Spieler über Steam-Lobbys, mit Funk statt Sprachchat und Helm-an-Helm-Reden
- mehr Schrottarten, Aufträge und Gebiete (Mond, Asteroidengürtel)
- Sonnenstürme und Mikrometeoriten
- Steam-Anbindung mit Erfolgen

## Technik

- 3D mit [three.js](https://threejs.org) 0.149, MIT-Lizenz (`lib/three-LICENSE.txt`)
- Die Erde, die Wolken und die Stadtlichter werden beim Start aus Rauschen berechnet, es gibt keine Bilddateien.
- Der Spielstand liegt im Browser (`localStorage`).
