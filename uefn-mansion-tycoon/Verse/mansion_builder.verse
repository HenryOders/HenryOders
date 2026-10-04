# Mansion Tycoon - Automatischer Mansion-Bau.
# Die Mansion wird komplett aus Wuerfel-Props mit verschiedenen Materialien gebaut (moderner Stil:
# Flachdaecher, Glasfronten, Marmor und Gold). Jeder Kauf erzeugt eine Liste von Bloecken (build_box),
# die das Device als Props spawnt. Masse in Zentimetern relativ zum Device. Vorderseite = -Y.
# Ein Raster-Feld (Cell) ist standardmaessig 10 x 10 m, eine Etage 4,5 m hoch.

using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }

block_mat := enum{Wall, Floor, Marble, Glass, Roof, Wood, Fabric, Dark, Gold, Water, Grass, Court, Line, Stone, Glow}

build_box := struct:
    X : float = 0.0
    Y : float = 0.0
    Z : float = 0.0
    SX : float = 100.0
    SY : float = 100.0
    SZ : float = 100.0
    Mat : block_mat = block_mat.Wall

build_ctx := struct:
    C : float = 1000.0
    FH : float = 450.0
    Detail : logic = true

room_slot := struct:
    Id : string = ""
    GX : float = 0.0
    GY : float = 0.0
    F : int = 0

# Block mit Mittelpunkt (PX, PY, PZ) und Groesse (W, D, H).
Bx(PX:float, PY:float, PZ:float, W:float, D:float, H:float, M:block_mat)<transacts>:build_box =
    build_box{X := PX, Y := PY, Z := PZ, SX := W, SY := D, SZ := H, Mat := M}

# Moebel-Qualitaet: Basic = Holz, Premium = Stoff, Luxury = Dunkel, Elite = Gold
QMat(Level:int)<transacts>:block_mat =
    if (Level >= 4) then block_mat.Gold
    else if (Level = 3) then block_mat.Dark
    else if (Level = 2) then block_mat.Fabric
    else block_mat.Wood

# ---------- Grundriss ----------
# GX: links (-) / rechts (+), GY: vorne (0) / hinten (+), F: Etage.

RoomLayout()<transacts>:[]room_slot = array{
    room_slot{Id := "entrance", GX := 0.0, GY := 0.0, F := 0},
    room_slot{Id := "living", GX := 1.0, GY := 0.0, F := 0},
    room_slot{Id := "office", GX := -1.0, GY := 0.0, F := 0},
    room_slot{Id := "dining", GX := 0.0, GY := 1.0, F := 0},
    room_slot{Id := "kitchen", GX := 1.0, GY := 1.0, F := 0},
    room_slot{Id := "bath_ground", GX := -1.0, GY := 1.0, F := 0},
    room_slot{Id := "master_bed", GX := 0.0, GY := 0.0, F := 1},
    room_slot{Id := "bed2", GX := 1.0, GY := 0.0, F := 1},
    room_slot{Id := "closet", GX := -1.0, GY := 0.0, F := 1},
    room_slot{Id := "bath_upper", GX := 0.0, GY := 1.0, F := 1},
    room_slot{Id := "bed3", GX := 1.0, GY := 1.0, F := 1},
    room_slot{Id := "gaming", GX := -1.0, GY := 1.0, F := 1},
    room_slot{Id := "gym", GX := 2.0, GY := 0.0, F := 0},
    room_slot{Id := "cinema", GX := 2.0, GY := 1.0, F := 0},
    room_slot{Id := "library", GX := 2.0, GY := 0.0, F := 1},
    room_slot{Id := "music_room", GX := 2.0, GY := 1.0, F := 1},
    room_slot{Id := "wine_cellar", GX := -1.0, GY := 2.0, F := 0},
    room_slot{Id := "game_room", GX := 0.0, GY := 2.0, F := 0},
    room_slot{Id := "indoor_pool", GX := 1.0, GY := 2.0, F := 0},
    room_slot{Id := "spa", GX := 2.0, GY := 2.0, F := 0}
}

FindRoomSlot(Id:string)<decides><transacts>:room_slot =
    var Found : ?room_slot = false
    for (S : RoomLayout(), S.Id = Id):
        set Found = option{S}
    Found?

FurnitureHost(Id:string)<transacts>:string =
    if (Id = "sofa" or Id = "tv" or Id = "aquarium") then "living"
    else if (Id = "plants" or Id = "artwork" or Id = "luxury_lights") then "entrance"
    else if (Id = "table") then "dining"
    else if (Id = "desk" or Id = "computer") then "office"
    else if (Id = "bed") then "master_bed"
    else if (Id = "kitchen_island") then "kitchen"
    else if (Id = "gym_equipment") then "gym"
    else if (Id = "pool_table") then "game_room"
    else if (Id = "cinema_screen") then "cinema"
    else ""

# ---------- Verteiler ----------

ItemBoxes(Item:catalog_item, Level:int, Ctx:build_ctx)<transacts>:[]build_box =
    if (Level <= 0):
        array{}
    else if (Item.Id = "garage"):
        GarageBoxes(Level, Ctx)
    else if (Item.Id = "land"):
        LandBoxes(Level, Ctx)
    else if (Item.Cat = item_cat.Furniture):
        FurnitureBoxes(Item.Id, Level, Ctx)
    else if (Item.Cat = item_cat.Staff):
        StaffBoxes(Item.Id, Ctx)
    else if (Item.Cat = item_cat.Vehicle):
        array{}
    else if (Slot := FindRoomSlot[Item.Id]):
        RoomBoxes(Slot, Level, Ctx)
    else:
        OutdoorBoxes(Item.Id, Level, Ctx)

# ---------- Raeume ----------

RoomBoxes(S:room_slot, Level:int, Ctx:build_ctx)<transacts>:[]build_box =
    C := Ctx.C
    FH := Ctx.FH
    CX := S.GX * C
    CY := S.GY * C
    Z0 := (S.F * 1.0) * FH
    Zf := Z0 + 30.0
    WallH := FH - 60.0
    MidZ := Zf + WallH / 2.0
    FloorMat := if (Level >= 3) then block_mat.Marble else if (S.F = 0) then block_mat.Stone else block_mat.Floor
    var Boxes : []build_box = array{
        Bx(CX, CY, Z0 + 15.0, C, C, 30.0, FloorMat),
        Bx(CX, CY + C / 2.0 - 15.0, MidZ, C, 30.0, WallH, block_mat.Wall),
        Bx(CX, CY, Z0 + FH - 15.0, C + 80.0, C + 80.0, 30.0, block_mat.Roof)}
    if (Ctx.Detail?):
        set Boxes += array{
            Bx(CX, CY - C / 2.0 + 10.0, MidZ, C - 60.0, 20.0, WallH, block_mat.Glass),
            Bx(CX + C / 2.0 - 15.0, CY, MidZ, 30.0, C - 60.0, WallH, block_mat.Wall)}
    if (Level >= 2):
        TrimMat := if (Level >= 4) then block_mat.Gold else block_mat.Dark
        set Boxes += array{Bx(CX, CY - C / 2.0 - 46.0, Z0 + FH - 15.0, C + 80.0, 12.0, 44.0, TrimMat)}
    if (Level >= 3):
        set Boxes += array{Bx(CX, CY + C / 2.0 - 36.0, Z0 + FH * 0.6, C * 0.6, 10.0, 40.0, block_mat.Glow)}
    if (Level >= 5):
        set Boxes += array{
            Bx(CX - C / 2.0 + 40.0, CY - C / 2.0 - 30.0, MidZ, 50.0, 50.0, WallH, block_mat.Gold),
            Bx(CX + C / 2.0 - 40.0, CY - C / 2.0 - 30.0, MidZ, 50.0, 50.0, WallH, block_mat.Gold)}
    Boxes + RoomSignature(S.Id, CX, CY, Zf, C, Level)

# Typische Einrichtung, an der man den Raum erkennt.
RoomSignature(Id:string, CX:float, CY:float, Zf:float, C:float, Level:int)<transacts>:[]build_box =
    Accent := if (Level >= 3) then block_mat.Marble else block_mat.Wood
    if (Id = "kitchen"):
        array{
            Bx(CX, CY + C / 2.0 - 90.0, Zf + 45.0, C * 0.7, 100.0, 90.0, Accent),
            Bx(CX, CY + C / 2.0 - 40.0, Zf + 230.0, C * 0.7, 50.0, 90.0, block_mat.Wood)}
    else if (Id = "bath_ground" or Id = "bath_upper"):
        array{
            Bx(CX - C * 0.22, CY + C * 0.25, Zf + 30.0, 250.0, 130.0, 60.0, block_mat.Wall),
            Bx(CX - C * 0.22, CY + C * 0.25, Zf + 61.0, 220.0, 100.0, 4.0, block_mat.Water)}
    else if (Id = "bed2" or Id = "bed3"):
        array{
            Bx(CX, CY + C * 0.2, Zf + 30.0, 220.0, 260.0, 60.0, block_mat.Fabric),
            Bx(CX, CY + C * 0.2 + 140.0, Zf + 80.0, 240.0, 20.0, 160.0, Accent)}
    else if (Id = "closet"):
        array{
            Bx(CX - C * 0.35, CY, Zf + 110.0, 80.0, C * 0.7, 220.0, Accent),
            Bx(CX + C * 0.3, CY, Zf + 110.0, 80.0, C * 0.7, 220.0, Accent)}
    else if (Id = "gaming"):
        array{
            Bx(CX, CY + C * 0.3, Zf + 40.0, 300.0, 100.0, 80.0, block_mat.Dark),
            Bx(CX, CY + C * 0.36, Zf + 140.0, 260.0, 10.0, 90.0, block_mat.Glow)}
    else if (Id = "gym"):
        array{Bx(CX, CY, Zf + 2.0, C * 0.8, C * 0.8, 4.0, block_mat.Dark)}
    else if (Id = "cinema"):
        array{
            Bx(CX, CY + C * 0.1, Zf + 40.0, C * 0.7, 120.0, 80.0, block_mat.Dark),
            Bx(CX, CY + C * 0.3, Zf + 60.0, C * 0.7, 120.0, 120.0, block_mat.Dark)}
    else if (Id = "library"):
        array{
            Bx(CX, CY + C / 2.0 - 70.0, Zf + 170.0, C * 0.8, 80.0, 340.0, block_mat.Wood),
            Bx(CX - C / 2.0 + 70.0, CY, Zf + 170.0, 80.0, C * 0.6, 340.0, block_mat.Wood)}
    else if (Id = "music_room"):
        array{
            Bx(CX, CY, Zf + 50.0, 220.0, 160.0, 100.0, block_mat.Dark),
            Bx(CX, CY + 60.0, Zf + 130.0, 220.0, 30.0, 60.0, block_mat.Wall)}
    else if (Id = "wine_cellar"):
        array{
            Bx(CX - C * 0.3, CY, Zf + 120.0, 80.0, C * 0.7, 240.0, block_mat.Wood),
            Bx(CX, CY + C * 0.35, Zf + 120.0, C * 0.5, 80.0, 240.0, block_mat.Wood),
            Bx(CX + C * 0.3, CY, Zf + 120.0, 80.0, C * 0.7, 240.0, block_mat.Wood)}
    else if (Id = "game_room"):
        array{Bx(CX - C * 0.3, CY + C * 0.3, Zf + 55.0, 300.0, 90.0, 110.0, block_mat.Dark)}
    else if (Id = "indoor_pool"):
        array{
            Bx(CX, CY, Zf + 6.0, C * 0.78, C * 0.6, 12.0, block_mat.Water),
            Bx(CX, CY - C * 0.33, Zf + 4.0, C * 0.8, 40.0, 8.0, Accent)}
    else if (Id = "spa"):
        array{
            Bx(CX, CY, Zf + 30.0, 360.0, 360.0, 60.0, block_mat.Stone),
            Bx(CX, CY, Zf + 61.0, 320.0, 320.0, 4.0, block_mat.Water)}
    else:
        array{}

GarageCell(K:int, C:float)<transacts>:vector3 =
    if (K = 0) then vector3{X := -2.0 * C, Y := 0.0, Z := 0.0}
    else if (K = 1) then vector3{X := -2.0 * C, Y := C, Z := 0.0}
    else if (K = 2) then vector3{X := -3.0 * C, Y := 0.0, Z := 0.0}
    else vector3{X := -3.0 * C, Y := C, Z := 0.0}

# Garage waechst mit jeder Stufe um ein Feld. Ab Car Gallery: Glasfront und Marmor.
GarageBoxes(Level:int, Ctx:build_ctx)<transacts>:[]build_box =
    C := Ctx.C
    FH := Ctx.FH
    WallH := FH - 60.0
    var Boxes : []build_box = array{}
    for (K := 0..Level - 1):
        P := GarageCell(K, C)
        FloorMat := if (Level >= 3) then block_mat.Marble else block_mat.Stone
        DoorMat := if (Level >= 3) then block_mat.Glass else block_mat.Dark
        set Boxes += array{
            Bx(P.X, P.Y, 15.0, C, C, 30.0, FloorMat),
            Bx(P.X, P.Y + C / 2.0 - 15.0, 30.0 + WallH / 2.0, C, 30.0, WallH, block_mat.Wall),
            Bx(P.X - C / 2.0 + 15.0, P.Y, 30.0 + WallH / 2.0, 30.0, C, WallH, block_mat.Wall),
            Bx(P.X, P.Y - C / 2.0 + 10.0, 30.0 + WallH / 2.0, C - 60.0, 20.0, WallH, DoorMat),
            Bx(P.X, P.Y, FH - 15.0, C + 80.0, C + 80.0, 30.0, block_mat.Roof)}
        if (Level >= 4):
            set Boxes += array{Bx(P.X, P.Y - C / 2.0 - 46.0, FH - 15.0, C + 80.0, 12.0, 44.0, block_mat.Gold)}
    Boxes

# ---------- Fahrzeuge ----------

VehicleBoxes(Ids:[]string, Ctx:build_ctx)<transacts>:[]build_box =
    C := Ctx.C
    var Boxes : []build_box = array{}
    for (I -> Id : Ids):
        Cell := ToInt((I * 1.0) / 2.0)
        Side := I - Cell * 2
        Base := GarageCell(Cell, C)
        PX := Base.X + (if (Side = 0) then -0.22 * C else 0.22 * C)
        set Boxes += CarBoxes(Id, PX, Base.Y)
    Boxes

CarBoxes(Id:string, PX:float, PY:float)<transacts>:[]build_box =
    var BodyMat : block_mat = block_mat.Fabric
    var CabinMat : block_mat = block_mat.Glass
    var Length : float = 460.0
    var Height : float = 70.0
    if (Id = "luxury_suv"):
        set BodyMat = block_mat.Dark
        set Height = 120.0
    else if (Id = "classic_roadster"):
        set BodyMat = block_mat.Wall
        set CabinMat = block_mat.Wood
    else if (Id = "supercar"):
        set CabinMat = block_mat.Dark
        set Height = 60.0
    else if (Id = "limousine"):
        set BodyMat = block_mat.Dark
        set Length = 680.0
    else if (Id = "hypercar"):
        set BodyMat = block_mat.Dark
        set CabinMat = block_mat.Glow
        set Height = 55.0
    else if (Id = "golden_hypercar"):
        set BodyMat = block_mat.Gold
        set Height = 55.0
    array{
        Bx(PX, PY, 50.0 + Height / 2.0, 200.0, Length, Height, BodyMat),
        Bx(PX, PY + 20.0, 50.0 + Height + 25.0, 170.0, Length * 0.45, 50.0, CabinMat),
        Bx(PX, PY, 30.0, 190.0, Length - 60.0, 40.0, block_mat.Dark)}

# ---------- Moebel ----------

FurnitureBoxes(Id:string, Level:int, Ctx:build_ctx)<transacts>:[]build_box =
    if (S := FindRoomSlot[FurnitureHost(Id)]):
        C := Ctx.C
        CX := S.GX * C
        CY := S.GY * C
        Zf := (S.F * 1.0) * Ctx.FH + 30.0
        Q := QMat(Level)
        if (Id = "sofa"):
            array{
                Bx(CX, CY + 250.0, Zf + 30.0, 380.0, 110.0, 60.0, Q),
                Bx(CX, CY + 320.0, Zf + 70.0, 380.0, 30.0, 140.0, Q)}
        else if (Id = "tv"):
            var Tv : []build_box = array{
                Bx(CX, CY - 330.0, Zf + 25.0, 220.0, 60.0, 50.0, Q),
                Bx(CX, CY - 330.0, Zf + 140.0, 300.0, 20.0, 170.0, block_mat.Dark)}
            if (Level >= 3):
                set Tv += array{Bx(CX, CY - 318.0, Zf + 140.0, 280.0, 6.0, 150.0, block_mat.Glow)}
            Tv
        else if (Id = "aquarium"):
            array{
                Bx(CX - 400.0, CY, Zf + 30.0, 80.0, 400.0, 60.0, Q),
                Bx(CX - 400.0, CY, Zf + 140.0, 70.0, 380.0, 160.0, block_mat.Glass),
                Bx(CX - 400.0, CY, Zf + 125.0, 50.0, 360.0, 120.0, block_mat.Water)}
        else if (Id = "plants"):
            var Pots : []build_box = array{
                Bx(CX - 380.0, CY - 330.0, Zf + 30.0, 80.0, 80.0, 60.0, Q),
                Bx(CX - 380.0, CY - 330.0, Zf + 130.0, 130.0, 130.0, 140.0, block_mat.Grass)}
            if (Level >= 2):
                set Pots += array{
                    Bx(CX + 380.0, CY - 330.0, Zf + 30.0, 80.0, 80.0, 60.0, Q),
                    Bx(CX + 380.0, CY - 330.0, Zf + 130.0, 130.0, 130.0, 140.0, block_mat.Grass)}
            Pots
        else if (Id = "artwork"):
            array{
                Bx(CX, CY + C / 2.0 - 40.0, Zf + 200.0, 260.0, 10.0, 180.0, Q),
                Bx(CX, CY + C / 2.0 - 47.0, Zf + 200.0, 220.0, 6.0, 140.0, block_mat.Fabric)}
        else if (Id = "luxury_lights"):
            array{
                Bx(CX, CY, Zf + Ctx.FH - 140.0, 170.0, 170.0, 50.0, Q),
                Bx(CX, CY, Zf + Ctx.FH - 185.0, 120.0, 120.0, 40.0, block_mat.Glow)}
        else if (Id = "table"):
            array{
                Bx(CX, CY, Zf + 78.0, 400.0, 180.0, 14.0, Q),
                Bx(CX, CY, Zf + 36.0, 300.0, 60.0, 72.0, Q)}
        else if (Id = "desk"):
            array{Bx(CX - 150.0, CY + 250.0, Zf + 40.0, 260.0, 120.0, 80.0, Q)}
        else if (Id = "computer"):
            array{
                Bx(CX - 150.0, CY + 290.0, Zf + 125.0, 130.0, 10.0, 70.0, block_mat.Glow),
                Bx(CX - 10.0, CY + 260.0, Zf + 40.0, 40.0, 80.0, 80.0, Q)}
        else if (Id = "bed"):
            array{
                Bx(CX, CY + 150.0, Zf + 25.0, 300.0, 380.0, 50.0, Q),
                Bx(CX, CY + 150.0, Zf + 60.0, 280.0, 360.0, 20.0, block_mat.Wall),
                Bx(CX, CY + 350.0, Zf + 90.0, 320.0, 30.0, 180.0, Q)}
        else if (Id = "kitchen_island"):
            array{
                Bx(CX, CY - 100.0, Zf + 45.0, 350.0, 120.0, 90.0, Q),
                Bx(CX, CY - 100.0, Zf + 95.0, 380.0, 150.0, 10.0, block_mat.Marble)}
        else if (Id = "gym_equipment"):
            array{
                Bx(CX - 250.0, CY, Zf + 60.0, 150.0, 80.0, 120.0, Q),
                Bx(CX, CY, Zf + 60.0, 150.0, 80.0, 120.0, Q),
                Bx(CX + 250.0, CY, Zf + 60.0, 150.0, 80.0, 120.0, Q)}
        else if (Id = "pool_table"):
            array{
                Bx(CX, CY, Zf + 40.0, 280.0, 160.0, 80.0, Q),
                Bx(CX, CY, Zf + 82.0, 250.0, 130.0, 6.0, block_mat.Court)}
        else if (Id = "cinema_screen"):
            array{
                Bx(CX, CY - C / 2.0 + 46.0, Zf + 190.0, C * 0.85, 6.0, 280.0, Q),
                Bx(CX, CY - C / 2.0 + 40.0, Zf + 190.0, C * 0.8, 10.0, 250.0, block_mat.Glow)}
        else:
            array{}
    else:
        array{}

# ---------- Personal ----------

StaffBoxes(Id:string, Ctx:build_ctx)<transacts>:[]build_box =
    C := Ctx.C
    var PX : float = 0.0
    var PY : float = 0.0
    var BodyMat : block_mat = block_mat.Dark
    if (Id = "cleaner"):
        set PX = C - 300.0
        set PY = -200.0
        set BodyMat = block_mat.Wall
    else if (Id = "chef"):
        set PX = C + 300.0
        set PY = C - 200.0
        set BodyMat = block_mat.Wall
    else if (Id = "gardener"):
        set PX = -1.4 * C
        set PY = -1.6 * C
        set BodyMat = block_mat.Grass
    else if (Id = "driver"):
        set PX = -2.0 * C
        set PY = -0.8 * C
    else if (Id = "security"):
        set PX = 0.6 * C
        set PY = -3.0 * C
    else if (Id = "butler"):
        set PX = 250.0
        set PY = -200.0
    var Figure : []build_box = array{
        Bx(PX, PY, 30.0 + 80.0, 60.0, 40.0, 160.0, BodyMat),
        Bx(PX, PY, 30.0 + 185.0, 40.0, 40.0, 40.0, block_mat.Stone)}
    if (Id = "butler"):
        set Figure += array{Bx(PX, PY - 22.0, 30.0 + 150.0, 30.0, 6.0, 14.0, block_mat.Gold)}
    Figure

# ---------- Aussenbereich ----------

OutdoorBoxes(Id:string, Level:int, Ctx:build_ctx)<transacts>:[]build_box =
    C := Ctx.C
    var Boxes : []build_box = array{}
    if (Id = "garden"):
        # Stufe 1: Hecken am Weg, 2: Baeume, 3: Blumenbeete, 4: goldene Pflanzkuebel
        set Boxes += array{
            Bx(-260.0, -1.8 * C, 60.0, 80.0, 2.2 * C, 120.0, block_mat.Grass),
            Bx(260.0, -1.8 * C, 60.0, 80.0, 2.2 * C, 120.0, block_mat.Grass)}
        if (Level >= 2):
            set Boxes += Tree(-1.6 * C, -1.2 * C) + Tree(1.6 * C, -1.2 * C)
        if (Level >= 3):
            set Boxes += array{
                Bx(-1.1 * C, -2.4 * C, 25.0, 420.0, 160.0, 50.0, block_mat.Fabric),
                Bx(1.1 * C, -2.4 * C, 25.0, 420.0, 160.0, 50.0, block_mat.Fabric)}
        if (Level >= 4):
            for (K := 0..3):
                PY := -1.0 * C - (K * 1.0) * 0.6 * C
                set Boxes += array{
                    Bx(-380.0, PY, 50.0, 100.0, 100.0, 100.0, block_mat.Gold),
                    Bx(380.0, PY, 50.0, 100.0, 100.0, 100.0, block_mat.Gold)}
    else if (Id = "fountain"):
        Basin := if (Level >= 2) then block_mat.Marble else block_mat.Stone
        Column := if (Level >= 3) then block_mat.Gold else Basin
        set Boxes += array{
            Bx(0.0, -1.8 * C, 30.0, 440.0, 440.0, 60.0, Basin),
            Bx(0.0, -1.8 * C, 61.0, 400.0, 400.0, 4.0, block_mat.Water),
            Bx(0.0, -1.8 * C, 160.0, 60.0, 60.0, 260.0, Column),
            Bx(0.0, -1.8 * C, 300.0, 160.0, 160.0, 30.0, Column)}
    else if (Id = "swimming_pool"):
        Deck := if (Level >= 2) then block_mat.Marble else block_mat.Stone
        set Boxes += array{
            Bx(2.6 * C, -1.5 * C, 10.0, 1.6 * C, 1.0 * C, 20.0, Deck),
            Bx(2.6 * C, -1.5 * C, 21.0, 1.3 * C, 0.7 * C, 4.0, block_mat.Water)}
        if (Level >= 2):
            set Boxes += array{Bx(2.6 * C, -2.0 * C + 10.0, 70.0, 1.6 * C, 20.0, 120.0, block_mat.Glass)}
        if (Level >= 3):
            set Boxes += array{Bx(3.5 * C, -1.2 * C, 21.0, 0.5 * C, 0.5 * C, 4.0, block_mat.Water)}
            set Boxes += Tree(3.6 * C, -1.8 * C) + Tree(1.7 * C, -1.9 * C)
    else if (Id = "outdoor_lounge"):
        Canopy := if (Level >= 3) then block_mat.Gold else block_mat.Roof
        set Boxes += array{
            Bx(3.6 * C, -0.2 * C, 10.0, 0.9 * C, 0.9 * C, 20.0, block_mat.Wood),
            Bx(3.45 * C, -0.2 * C, 50.0, 200.0, 90.0, 40.0, block_mat.Fabric),
            Bx(3.75 * C, -0.2 * C, 50.0, 200.0, 90.0, 40.0, block_mat.Fabric),
            Bx(3.6 * C + 400.0, -0.2 * C, 160.0, 30.0, 30.0, 300.0, block_mat.Dark),
            Bx(3.6 * C, -0.2 * C, 320.0, 0.9 * C, 0.9 * C, 20.0, Canopy)}
        if (Level >= 2):
            set Boxes += array{Bx(3.6 * C, -0.2 * C - 0.45 * C, 300.0, 0.9 * C, 10.0, 20.0, block_mat.Glow)}
    else if (Id = "tennis"):
        set Boxes += array{
            Bx(5.6 * C, 1.0 * C, 5.0, 1.2 * C, 2.4 * C, 10.0, block_mat.Court),
            Bx(5.6 * C, 1.0 * C, 60.0, 1.2 * C, 10.0, 100.0, block_mat.Line),
            Bx(5.6 * C, 1.0 * C - 1.1 * C, 11.0, 1.1 * C, 10.0, 2.0, block_mat.Line),
            Bx(5.6 * C, 1.0 * C + 1.1 * C, 11.0, 1.1 * C, 10.0, 2.0, block_mat.Line),
            Bx(5.6 * C, 1.0 * C, 11.0, 10.0, 2.2 * C, 2.0, block_mat.Line)}
        if (Level >= 2):
            set Boxes += array{
                Bx(5.6 * C + 0.75 * C, 1.0 * C, 80.0, 160.0, 1.6 * C, 160.0, block_mat.Dark),
                Bx(5.6 * C - 0.65 * C, 1.0 * C - 1.2 * C, 400.0, 40.0, 40.0, 800.0, block_mat.Glow),
                Bx(5.6 * C - 0.65 * C, 1.0 * C + 1.2 * C, 400.0, 40.0, 40.0, 800.0, block_mat.Glow)}
    else if (Id = "basketball"):
        set Boxes += array{
            Bx(-5.2 * C, 1.0 * C, 5.0, 0.9 * C, 1.5 * C, 10.0, block_mat.Wood),
            Bx(-5.2 * C, 1.0 * C, 11.0, 0.9 * C, 10.0, 2.0, block_mat.Line),
            Bx(-5.2 * C, 1.0 * C - 0.7 * C, 200.0, 20.0, 20.0, 400.0, block_mat.Dark),
            Bx(-5.2 * C, 1.0 * C - 0.68 * C, 360.0, 180.0, 10.0, 110.0, block_mat.Glass),
            Bx(-5.2 * C, 1.0 * C + 0.7 * C, 200.0, 20.0, 20.0, 400.0, block_mat.Dark),
            Bx(-5.2 * C, 1.0 * C + 0.68 * C, 360.0, 180.0, 10.0, 110.0, block_mat.Glass)}
        if (Level >= 2):
            set Boxes += array{Bx(-5.2 * C - 0.6 * C, 1.0 * C, 80.0, 160.0, 1.3 * C, 160.0, block_mat.Dark)}
    else if (Id = "helipad"):
        Rim := if (Level >= 2) then block_mat.Gold else block_mat.Line
        set Boxes += array{
            Bx(-5.2 * C, -1.6 * C, 15.0, 1.1 * C, 1.1 * C, 30.0, block_mat.Dark),
            Bx(-5.2 * C - 150.0, -1.6 * C, 31.0, 60.0, 500.0, 2.0, block_mat.Line),
            Bx(-5.2 * C + 150.0, -1.6 * C, 31.0, 60.0, 500.0, 2.0, block_mat.Line),
            Bx(-5.2 * C, -1.6 * C, 31.0, 300.0, 60.0, 2.0, block_mat.Line),
            Bx(-5.2 * C, -1.6 * C - 0.55 * C, 32.0, 1.1 * C, 20.0, 4.0, Rim),
            Bx(-5.2 * C, -1.6 * C + 0.55 * C, 32.0, 1.1 * C, 20.0, 4.0, Rim)}
    Boxes

Tree(PX:float, PY:float)<transacts>:[]build_box =
    array{
        Bx(PX, PY, 150.0, 50.0, 50.0, 300.0, block_mat.Wood),
        Bx(PX, PY, 410.0, 280.0, 280.0, 240.0, block_mat.Grass)}

# Grundstueck: Rasenflaeche waechst, ab Stufe 2 mit Mauer (Stufe 4 Marmor, Stufe 5 Gold).
LandBoxes(Level:int, Ctx:build_ctx)<transacts>:[]build_box =
    C := Ctx.C
    W := (if (Level >= 5) then 18.0 else if (Level = 4) then 16.0 else if (Level = 3) then 14.0 else if (Level = 2) then 12.0 else 9.0) * C
    D := (if (Level >= 5) then 12.0 else if (Level = 4) then 10.0 else if (Level = 3) then 9.0 else if (Level = 2) then 8.0 else 7.0) * C
    CY := -0.3 * C
    var Boxes : []build_box = array{Bx(0.0, CY, -10.0, W, D, 20.0, block_mat.Grass)}
    if (Level >= 2):
        WallMat := if (Level >= 5) then block_mat.Gold else if (Level = 4) then block_mat.Marble else block_mat.Stone
        Front := CY - D / 2.0
        Back := CY + D / 2.0
        Half := W / 2.0
        Gap := 0.4 * C
        set Boxes += array{
            Bx(0.0, Back, 60.0, W, 40.0, 120.0, WallMat),
            Bx(-Half, CY, 60.0, 40.0, D, 120.0, WallMat),
            Bx(Half, CY, 60.0, 40.0, D, 120.0, WallMat),
            Bx(-(Half + Gap) / 2.0, Front, 60.0, Half - Gap, 40.0, 120.0, WallMat),
            Bx((Half + Gap) / 2.0, Front, 60.0, Half - Gap, 40.0, 120.0, WallMat)}
    Boxes

# ---------- Haus-Stufen ----------
# Jede Stufe fuegt Architektur hinzu, alle erreichten Stufen bleiben stehen.

TierBoxes(T:int, Ctx:build_ctx)<transacts>:[]build_box =
    C := Ctx.C
    FH := Ctx.FH
    if (T = 1):
        # Small House: Gartenweg zur Strasse
        array{Bx(0.0, -1.9 * C, 3.0, 220.0, 2.7 * C, 6.0, block_mat.Stone)}
    else if (T = 2):
        # Modern House: Vordach am Eingang
        array{
            Bx(0.0, -0.8 * C, FH - 15.0, 0.8 * C, 0.6 * C, 30.0, block_mat.Roof),
            Bx(-0.35 * C, -1.05 * C, FH / 2.0, 30.0, 30.0, FH - 30.0, block_mat.Wall),
            Bx(0.35 * C, -1.05 * C, FH / 2.0, 30.0, 30.0, FH - 30.0, block_mat.Wall)}
    else if (T = 3):
        # Luxury Villa: Saeulengang ueber zwei Etagen und Auffahrt zur Garage
        array{
            Bx(-1.5 * C, -0.6 * C, FH, 60.0, 60.0, 2.0 * FH, block_mat.Marble),
            Bx(-0.5 * C, -0.6 * C, FH, 60.0, 60.0, 2.0 * FH, block_mat.Marble),
            Bx(0.5 * C, -0.6 * C, FH, 60.0, 60.0, 2.0 * FH, block_mat.Marble),
            Bx(1.5 * C, -0.6 * C, FH, 60.0, 60.0, 2.0 * FH, block_mat.Marble),
            Bx(-2.0 * C, -1.9 * C, 3.0, 0.6 * C, 2.7 * C, 6.0, block_mat.Stone)}
    else if (T = 4):
        # Mansion: Einfahrtstor und Laternen
        array{
            Bx(-0.35 * C, -3.2 * C, 175.0, 80.0, 80.0, 350.0, block_mat.Stone),
            Bx(0.35 * C, -3.2 * C, 175.0, 80.0, 80.0, 350.0, block_mat.Stone),
            Bx(0.0, -3.2 * C, 370.0, 0.8 * C, 50.0, 40.0, block_mat.Dark),
            Bx(-200.0, -1.2 * C, 110.0, 30.0, 30.0, 220.0, block_mat.Glow),
            Bx(200.0, -1.2 * C, 110.0, 30.0, 30.0, 220.0, block_mat.Glow),
            Bx(-200.0, -2.6 * C, 110.0, 30.0, 30.0, 220.0, block_mat.Glow),
            Bx(200.0, -2.6 * C, 110.0, 30.0, 30.0, 220.0, block_mat.Glow)}
    else if (T = 5):
        # Luxury Mansion: Glas-Atrium vor dem Eingang und goldenes Band an der Fassade
        array{
            Bx(0.0, -0.66 * C, FH, 0.7 * C, 0.25 * C, 2.0 * FH - 40.0, block_mat.Glass),
            Bx(0.0, -0.66 * C, 2.0 * FH + 5.0, 0.8 * C, 0.3 * C, 30.0, block_mat.Gold),
            Bx(0.5 * C, -0.56 * C, 2.0 * FH - 20.0, 3.2 * C, 20.0, 40.0, block_mat.Gold)}
    else if (T = 6):
        # Mega Mansion: Penthouse-Etage mit Glasfront und Lichtsaeulen am Tor
        Z2 := 2.0 * FH
        array{
            Bx(0.5 * C, 0.0, Z2 + 15.0, 2.0 * C, C, 30.0, block_mat.Marble),
            Bx(0.5 * C, -0.5 * C + 10.0, Z2 + FH / 2.0, 2.0 * C - 60.0, 20.0, FH - 60.0, block_mat.Glass),
            Bx(0.5 * C, 0.5 * C - 15.0, Z2 + FH / 2.0, 2.0 * C, 30.0, FH - 60.0, block_mat.Wall),
            Bx(0.5 * C, 0.0, Z2 + FH - 15.0, 2.0 * C + 120.0, C + 120.0, 30.0, block_mat.Roof),
            Bx(0.5 * C, -0.5 * C - 60.0, Z2 + FH - 15.0, 2.0 * C + 120.0, 12.0, 44.0, block_mat.Gold),
            Bx(-0.6 * C, -3.2 * C, 1500.0, 50.0, 50.0, 3000.0, block_mat.Glow),
            Bx(0.6 * C, -3.2 * C, 1500.0, 50.0, 50.0, 3000.0, block_mat.Glow)}
    else if (T = 7):
        # Billionaire Estate: goldene Krone, goldenes Tor, Statue und Himmelsstrahlen
        Z3 := 3.0 * FH
        array{
            Bx(0.5 * C, 0.0, Z3 + 30.0, 2.0 * C + 120.0, C + 120.0, 60.0, block_mat.Gold),
            Bx(0.5 * C, 0.0, Z3 + 120.0, 0.6 * C, 0.6 * C, 120.0, block_mat.Gold),
            Bx(0.0, -3.2 * C, 420.0, 0.9 * C, 60.0, 60.0, block_mat.Gold),
            Bx(-1.2 * C, -1.0 * C, 60.0, 160.0, 160.0, 120.0, block_mat.Marble),
            Bx(-1.2 * C, -1.0 * C, 260.0, 70.0, 70.0, 280.0, block_mat.Gold),
            Bx(-4.0 * C, -3.0 * C, 2500.0, 60.0, 60.0, 5000.0, block_mat.Glow),
            Bx(4.0 * C, -3.0 * C, 2500.0, 60.0, 60.0, 5000.0, block_mat.Glow),
            Bx(-4.0 * C, 3.0 * C, 2500.0, 60.0, 60.0, 5000.0, block_mat.Glow),
            Bx(4.0 * C, 3.0 * C, 2500.0, 60.0, 60.0, 5000.0, block_mat.Glow)}
    else:
        array{}
