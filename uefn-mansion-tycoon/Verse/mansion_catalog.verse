# Mansion Tycoon - Spieldaten, Balancing und Hilfsfunktionen.
# Alle Raeume, Moebel, Fahrzeuge, Mitarbeiter, Stufen und Quests sind hier definiert.
# Preise wachsen pro Ausbaustufe um Faktor 7, jede Ausbaustufe gehoert zu einer Mansion-Stufe.

using { /Verse.org/Simulation }

item_cat := enum{Ground, Upper, Luxury, Outdoor, Land, Furniture, Vehicle, Staff}

quest_kind := enum{RoomsBuilt, RoomsTotal, FurnitureOwned, StaffOwned, VehiclesOwned, CashReached, TierReached, ItemLevel, ValueReached, FurnitureQuality, RankReached}

catalog_item := struct:
    Id : string = ""
    Name : string = ""
    Cat : item_cat = item_cat.Ground
    # Mansion-Stufe, ab der Ausbaustufe 1 kaufbar ist. Stufe k braucht BaseTier + k - 1.
    BaseTier : int = 1
    # Preis von Ausbaustufe 1. Jede weitere Stufe kostet das 7-fache.
    BaseCost : int = 0
    LevelNames : []string = array{}
    RequiresId : string = ""
    ReqLevel : int = 1
    StaffBonus : int = 0
    # Stufen, die der Spieler beim Start schon besitzt (zaehlen zum Wert, nicht zum Einkommen).
    StartLevel : int = 0

tier_def := struct:
    Name : string = ""
    Cost : int = 0
    ReqLevel : int = 1
    ReqRooms : int = 0
    BaseIncome : int = 100
    Value : int = 0

quest_def := struct:
    Title : string = ""
    Kind : quest_kind = quest_kind.RoomsBuilt
    Target : int = 1
    ItemId : string = ""
    RewardCash : int = 0
    RewardXp : int = 0

menu_row := struct:
    Info : string = ""
    ButtonLabel : string = ""
    Action : int = -100
    HasButton : logic = false
    Enabled : logic = true

MaxTier : int = 7
TotalRooms : int = 28
# Einkommen pro Minute in Promille des Kaufpreises, abhaengig von der Mansion-Stufe der Ausbaustufe.
IncomeRates : []int = array{500, 450, 400, 350, 300, 260, 220}
# Fahrzeugplaetze je Garagen-Ausbaustufe 0..4
GarageSlots : []int = array{0, 1, 2, 4, 7}

# ---------- Zahlen ----------

ToInt(F:float)<transacts>:int =
    if (I := Floor[F]) then I else 0

Ratio(A:int, B:int)<transacts>:float =
    if (B > 0) then Min(1.0, (A * 1.0) / (B * 1.0)) else 0.0

Pad2(N:int)<transacts>:string =
    if (N < 10) then "0{N}" else "{N}"

Pad3(N:int)<transacts>:string =
    if (N < 10) then "00{N}" else if (N < 100) then "0{N}" else "{N}"

Fmt2(V:float)<transacts>:string =
    Whole := ToInt(V)
    Frac := ToInt((V - (Whole * 1.0)) * 100.0)
    "{Whole}.{Pad2(Frac)}"

# Kurzform fuer HUD: $950, $9,500, $12.4K, $3.25M, $1.20B
FormatMoney(Amount:int)<transacts>:string =
    F := Amount * 1.0
    if (Amount >= 1000000000):
        "${Fmt2(F / 1000000000.0)}B"
    else if (Amount >= 1000000):
        "${Fmt2(F / 1000000.0)}M"
    else if (Amount >= 10000):
        Whole := ToInt(F / 1000.0)
        Tenth := ToInt((F - (Whole * 1000.0)) / 100.0)
        "${Whole}.{Tenth}K"
    else if (Amount >= 1000):
        Thousands := ToInt(F / 1000.0)
        "${Thousands},{Pad3(Amount - Thousands * 1000)}"
    else:
        "${Amount}"

# Langform fuer den Mansion Value: $12,450,000
FormatFull(Amount:int)<transacts>:string =
    var Rest : int = Amount
    var Out : string = ""
    loop:
        if (Rest < 1000):
            set Out = "{Rest}{Out}"
            break
        else:
            Q := ToInt((Rest * 1.0) / 1000.0)
            set Out = ",{Pad3(Rest - Q * 1000)}{Out}"
            set Rest = Q
    "${Out}"

XpToNext(Level:int)<transacts>:int = 80 + 40 * Level

# Fiktive Rangliste der 100 teuersten Anwesen: Platz 1 = $3 Mrd., jeder Platz 11 % weniger.
RankFor(Value:int)<transacts>:int =
    var Rank : int = 1
    var Threshold : float = 3000000000.0
    for (Step := 1..100):
        if (Threshold > Value * 1.0) then set Rank += 1
        set Threshold *= 0.89
    Rank

# ---------- Katalog-Formeln ----------

LevelTier(Item:catalog_item, Level:int)<transacts>:int =
    Min(Item.BaseTier + Level - 1, MaxTier)

ItemCost(Item:catalog_item, Level:int)<transacts>:int =
    var C : int = Item.BaseCost
    for (Step := 2..Level):
        set C = C * 7
    C

CatIncomePermille(Cat:item_cat)<transacts>:int =
    case (Cat):
        item_cat.Vehicle => 500
        item_cat.Land => 600
        item_cat.Staff => 0
        _ => 1000

CatValuePercent(Cat:item_cat)<transacts>:int =
    case (Cat):
        item_cat.Furniture => 130
        item_cat.Vehicle => 250
        item_cat.Land => 250
        item_cat.Staff => 50
        _ => 150

ItemIncome(Item:catalog_item, Level:int)<transacts>:int =
    Rate := if (R := IncomeRates[LevelTier(Item, Level) - 1]) then R else 220
    Cost := ItemCost(Item, Level)
    ToInt((Cost * 1.0) * (Rate * 1.0) * (CatIncomePermille(Item.Cat) * 1.0) / 1000000.0)

ItemValue(Item:catalog_item, Level:int)<transacts>:int =
    ToInt((ItemCost(Item, Level) * 1.0) * (CatValuePercent(Item.Cat) * 1.0) / 100.0)

LevelName(Item:catalog_item, Level:int)<transacts>:string =
    if (N := Item.LevelNames[Level - 1]) then N else Item.Name

IsRoomCat(Cat:item_cat)<transacts>:logic =
    case (Cat):
        item_cat.Ground => true
        item_cat.Upper => true
        item_cat.Luxury => true
        item_cat.Outdoor => true
        _ => false

CatLabel(Cat:item_cat)<transacts>:string =
    case (Cat):
        item_cat.Ground => "Ground Floor"
        item_cat.Upper => "Upper Floor"
        item_cat.Luxury => "Luxury Wing"
        item_cat.Outdoor => "Outdoor"
        item_cat.Land => "Estate Grounds"
        item_cat.Furniture => "Furniture"
        item_cat.Vehicle => "Vehicle"
        item_cat.Staff => "Staff"

Qualities(Name:string)<transacts>:[]string =
    array{"Basic {Name}", "Premium {Name}", "Luxury {Name}", "Elite {Name}"}

GarageCapacity(GarageLevel:int)<transacts>:int =
    if (C := GarageSlots[GarageLevel]) then C else 7

# ---------- Daten ----------

MakeTiers()<transacts>:[]tier_def = array{
    tier_def{Name := "Small House", Cost := 0, ReqLevel := 1, ReqRooms := 0, BaseIncome := 100, Value := 50000},
    tier_def{Name := "Modern House", Cost := 15000, ReqLevel := 3, ReqRooms := 4, BaseIncome := 500, Value := 25000},
    tier_def{Name := "Luxury Villa", Cost := 200000, ReqLevel := 6, ReqRooms := 8, BaseIncome := 2500, Value := 300000},
    tier_def{Name := "Mansion", Cost := 1500000, ReqLevel := 9, ReqRooms := 13, BaseIncome := 10000, Value := 2250000},
    tier_def{Name := "Luxury Mansion", Cost := 12000000, ReqLevel := 12, ReqRooms := 18, BaseIncome := 30000, Value := 18000000},
    tier_def{Name := "Mega Mansion", Cost := 90000000, ReqLevel := 15, ReqRooms := 23, BaseIncome := 100000, Value := 135000000},
    tier_def{Name := "Billionaire Estate", Cost := 750000000, ReqLevel := 18, ReqRooms := 28, BaseIncome := 500000, Value := 1125000000}
}

MakeCatalog()<transacts>:[]catalog_item = array{
    # Erdgeschoss
    catalog_item{Id := "entrance", Name := "Entrance", Cat := item_cat.Ground, BaseTier := 1, BaseCost := 1000, StartLevel := 1,
        LevelNames := array{"Small Entrance Hall", "Grand Foyer", "Marble Hall", "Palace Hall", "Golden Atrium"}},
    catalog_item{Id := "living", Name := "Living Room", Cat := item_cat.Ground, BaseTier := 1, BaseCost := 1200, StartLevel := 1,
        LevelNames := array{"Empty Living Room", "Cozy Living Room", "Designer Lounge", "Penthouse Lounge", "Royal Salon"}},
    catalog_item{Id := "kitchen", Name := "Kitchen", Cat := item_cat.Ground, BaseTier := 1, BaseCost := 1500,
        LevelNames := array{"Basic Kitchen", "Modern Kitchen", "Luxury Kitchen", "Professional Kitchen", "Billionaire Kitchen"}},
    catalog_item{Id := "bath_ground", Name := "Bathroom", Cat := item_cat.Ground, BaseTier := 1, BaseCost := 1000,
        LevelNames := array{"Guest Bathroom", "Marble Bathroom", "Gold Bathroom"}},
    catalog_item{Id := "dining", Name := "Dining Room", Cat := item_cat.Ground, BaseTier := 1, BaseCost := 2000, ReqLevel := 2,
        LevelNames := array{"Dining Room", "Elegant Dining Room", "Banquet Hall"}},
    catalog_item{Id := "office", Name := "Office", Cat := item_cat.Ground, BaseTier := 2, BaseCost := 10000, ReqLevel := 3,
        LevelNames := array{"Home Office", "Executive Office", "CEO Suite"}},
    catalog_item{Id := "garage", Name := "Garage", Cat := item_cat.Ground, BaseTier := 2, BaseCost := 12000, ReqLevel := 3,
        LevelNames := array{"Single Garage", "Double Garage", "Car Gallery", "Supercar Showroom"}},

    # Obergeschoss (ab Modern House)
    catalog_item{Id := "master_bed", Name := "Master Bedroom", Cat := item_cat.Upper, BaseTier := 2, BaseCost := 15000, ReqLevel := 4,
        LevelNames := array{"Master Bedroom", "Luxury Suite", "Presidential Suite", "Royal Suite"}},
    catalog_item{Id := "bed2", Name := "Bedroom 2", Cat := item_cat.Upper, BaseTier := 2, BaseCost := 9000, ReqLevel := 3,
        LevelNames := array{"Bedroom 2", "Guest Suite 2"}},
    catalog_item{Id := "bath_upper", Name := "Upstairs Bathroom", Cat := item_cat.Upper, BaseTier := 2, BaseCost := 11000, ReqLevel := 4,
        LevelNames := array{"Upstairs Bathroom", "Spa Bathroom", "Marble Spa Bath"}},
    catalog_item{Id := "bed3", Name := "Bedroom 3", Cat := item_cat.Upper, BaseTier := 3, BaseCost := 60000, ReqLevel := 6,
        LevelNames := array{"Bedroom 3", "Guest Suite 3"}},
    catalog_item{Id := "closet", Name := "Walk-in Closet", Cat := item_cat.Upper, BaseTier := 3, BaseCost := 80000, ReqLevel := 7,
        LevelNames := array{"Walk-in Closet", "Designer Closet", "Couture Gallery"}},
    catalog_item{Id := "gaming", Name := "Gaming Room", Cat := item_cat.Upper, BaseTier := 3, BaseCost := 100000, ReqLevel := 7,
        LevelNames := array{"Gaming Room", "Streaming Studio", "E-Sports Arena"}},

    # Luxusbereiche (ab Luxury Villa)
    catalog_item{Id := "gym", Name := "Gym", Cat := item_cat.Luxury, BaseTier := 3, BaseCost := 90000, ReqLevel := 6,
        LevelNames := array{"Home Gym", "Fitness Studio", "Pro Training Center"}},
    catalog_item{Id := "cinema", Name := "Home Cinema", Cat := item_cat.Luxury, BaseTier := 4, BaseCost := 600000, ReqLevel := 9,
        LevelNames := array{"Home Cinema", "IMAX Cinema", "Premiere Theater"}},
    catalog_item{Id := "library", Name := "Library", Cat := item_cat.Luxury, BaseTier := 4, BaseCost := 500000, ReqLevel := 9,
        LevelNames := array{"Library", "Grand Library", "Rare Book Vault"}},
    catalog_item{Id := "wine_cellar", Name := "Wine Cellar", Cat := item_cat.Luxury, BaseTier := 4, BaseCost := 700000, ReqLevel := 10,
        LevelNames := array{"Wine Cellar", "Vintage Cellar", "Grand Cru Vault"}},
    catalog_item{Id := "game_room", Name := "Game Room", Cat := item_cat.Luxury, BaseTier := 4, BaseCost := 650000, ReqLevel := 10,
        LevelNames := array{"Game Room", "Billiard Lounge", "Private Casino"}},
    catalog_item{Id := "indoor_pool", Name := "Indoor Pool", Cat := item_cat.Luxury, BaseTier := 5, BaseCost := 4000000, ReqLevel := 12,
        LevelNames := array{"Indoor Pool", "Lagoon Pool", "Infinity Grotto"}},
    catalog_item{Id := "spa", Name := "Spa", Cat := item_cat.Luxury, BaseTier := 5, BaseCost := 4500000, ReqLevel := 13,
        LevelNames := array{"Spa", "Wellness Temple"}},
    catalog_item{Id := "music_room", Name := "Music Room", Cat := item_cat.Luxury, BaseTier := 5, BaseCost := 3500000, ReqLevel := 12,
        LevelNames := array{"Music Room", "Recording Studio", "Concert Hall"}},

    # Aussenbereich
    catalog_item{Id := "garden", Name := "Garden", Cat := item_cat.Outdoor, BaseTier := 1, BaseCost := 2500, ReqLevel := 2,
        LevelNames := array{"Garden", "Landscaped Garden", "Botanical Garden", "Royal Gardens"}},
    catalog_item{Id := "fountain", Name := "Fountain", Cat := item_cat.Outdoor, BaseTier := 3, BaseCost := 70000, ReqLevel := 5,
        LevelNames := array{"Fountain", "Marble Fountain", "Golden Fountain"}},
    catalog_item{Id := "swimming_pool", Name := "Swimming Pool", Cat := item_cat.Outdoor, BaseTier := 3, BaseCost := 120000, ReqLevel := 6,
        LevelNames := array{"Swimming Pool", "Infinity Pool", "Lagoon Pool Deck"}},
    catalog_item{Id := "outdoor_lounge", Name := "Outdoor Lounge", Cat := item_cat.Outdoor, BaseTier := 4, BaseCost := 550000, ReqLevel := 9,
        LevelNames := array{"Outdoor Lounge", "Sunset Terrace", "Sky Lounge"}},
    catalog_item{Id := "basketball", Name := "Basketball Court", Cat := item_cat.Outdoor, BaseTier := 4, BaseCost := 600000, ReqLevel := 9,
        LevelNames := array{"Basketball Court", "Pro Basketball Arena"}},
    catalog_item{Id := "tennis", Name := "Tennis Court", Cat := item_cat.Outdoor, BaseTier := 4, BaseCost := 800000, ReqLevel := 10,
        LevelNames := array{"Tennis Court", "Pro Tennis Arena"}},
    catalog_item{Id := "helipad", Name := "Helipad", Cat := item_cat.Outdoor, BaseTier := 6, BaseCost := 30000000, ReqLevel := 15,
        LevelNames := array{"Helipad", "Private Heliport"}},

    # Grundstueck
    catalog_item{Id := "land", Name := "Estate Grounds", Cat := item_cat.Land, BaseTier := 1, BaseCost := 2000, StartLevel := 1,
        LevelNames := array{"Small Plot", "Extended Plot", "Park Estate", "Hillside Estate", "Private Peninsula"}},

    # Moebel (4 Qualitaeten: Basic, Premium, Luxury, Elite)
    catalog_item{Id := "sofa", Name := "Sofa", Cat := item_cat.Furniture, BaseTier := 1, BaseCost := 500, RequiresId := "living", LevelNames := Qualities("Sofa")},
    catalog_item{Id := "tv", Name := "TV", Cat := item_cat.Furniture, BaseTier := 1, BaseCost := 700, RequiresId := "living", LevelNames := Qualities("TV")},
    catalog_item{Id := "plants", Name := "Plants", Cat := item_cat.Furniture, BaseTier := 1, BaseCost := 300, RequiresId := "entrance", LevelNames := Qualities("Plants")},
    catalog_item{Id := "table", Name := "Dining Table", Cat := item_cat.Furniture, BaseTier := 1, BaseCost := 600, RequiresId := "dining", ReqLevel := 2, LevelNames := Qualities("Dining Table")},
    catalog_item{Id := "desk", Name := "Desk", Cat := item_cat.Furniture, BaseTier := 2, BaseCost := 4000, RequiresId := "office", ReqLevel := 3, LevelNames := Qualities("Desk")},
    catalog_item{Id := "computer", Name := "Computer", Cat := item_cat.Furniture, BaseTier := 2, BaseCost := 7000, RequiresId := "office", ReqLevel := 3, LevelNames := Qualities("Computer")},
    catalog_item{Id := "bed", Name := "Bed", Cat := item_cat.Furniture, BaseTier := 2, BaseCost := 6000, RequiresId := "master_bed", ReqLevel := 4, LevelNames := Qualities("Bed")},
    catalog_item{Id := "kitchen_island", Name := "Kitchen Island", Cat := item_cat.Furniture, BaseTier := 2, BaseCost := 8000, RequiresId := "kitchen", ReqLevel := 3, LevelNames := Qualities("Kitchen Island")},
    catalog_item{Id := "artwork", Name := "Artwork", Cat := item_cat.Furniture, BaseTier := 2, BaseCost := 9000, RequiresId := "entrance", ReqLevel := 4, LevelNames := Qualities("Artwork")},
    catalog_item{Id := "aquarium", Name := "Aquarium", Cat := item_cat.Furniture, BaseTier := 3, BaseCost := 50000, RequiresId := "living", ReqLevel := 6, LevelNames := Qualities("Aquarium")},
    catalog_item{Id := "gym_equipment", Name := "Gym Equipment", Cat := item_cat.Furniture, BaseTier := 3, BaseCost := 55000, RequiresId := "gym", ReqLevel := 6, LevelNames := Qualities("Gym Equipment")},
    catalog_item{Id := "luxury_lights", Name := "Luxury Lights", Cat := item_cat.Furniture, BaseTier := 3, BaseCost := 60000, RequiresId := "entrance", ReqLevel := 7, LevelNames := Qualities("Luxury Lights")},
    catalog_item{Id := "pool_table", Name := "Pool Table", Cat := item_cat.Furniture, BaseTier := 4, BaseCost := 350000, RequiresId := "game_room", ReqLevel := 10, LevelNames := Qualities("Pool Table")},
    catalog_item{Id := "cinema_screen", Name := "Cinema Screen", Cat := item_cat.Furniture, BaseTier := 4, BaseCost := 400000, RequiresId := "cinema", ReqLevel := 9, LevelNames := Qualities("Cinema Screen")},

    # Fahrzeuge (brauchen einen freien Garagenplatz)
    catalog_item{Id := "sports_car", Name := "Sports Car", Cat := item_cat.Vehicle, BaseTier := 2, BaseCost := 25000, RequiresId := "garage", ReqLevel := 4, LevelNames := array{"Sports Car"}},
    catalog_item{Id := "luxury_suv", Name := "Luxury SUV", Cat := item_cat.Vehicle, BaseTier := 3, BaseCost := 150000, RequiresId := "garage", ReqLevel := 6, LevelNames := array{"Luxury SUV"}},
    catalog_item{Id := "classic_roadster", Name := "Classic Roadster", Cat := item_cat.Vehicle, BaseTier := 3, BaseCost := 200000, RequiresId := "garage", ReqLevel := 7, LevelNames := array{"Classic Roadster"}},
    catalog_item{Id := "supercar", Name := "Supercar", Cat := item_cat.Vehicle, BaseTier := 4, BaseCost := 1200000, RequiresId := "garage", ReqLevel := 10, LevelNames := array{"Supercar"}},
    catalog_item{Id := "limousine", Name := "Limousine", Cat := item_cat.Vehicle, BaseTier := 5, BaseCost := 6000000, RequiresId := "garage", ReqLevel := 12, LevelNames := array{"Limousine"}},
    catalog_item{Id := "hypercar", Name := "Hypercar", Cat := item_cat.Vehicle, BaseTier := 6, BaseCost := 40000000, RequiresId := "garage", ReqLevel := 15, LevelNames := array{"Hypercar"}},
    catalog_item{Id := "golden_hypercar", Name := "Golden Hypercar", Cat := item_cat.Vehicle, BaseTier := 7, BaseCost := 300000000, RequiresId := "garage", ReqLevel := 18, LevelNames := array{"Golden Hypercar"}},

    # Personal (Prozent-Bonus auf das gesamte Einkommen)
    catalog_item{Id := "cleaner", Name := "Cleaner", Cat := item_cat.Staff, BaseTier := 1, BaseCost := 3000, StaffBonus := 5, ReqLevel := 2, LevelNames := array{"Cleaner"}},
    catalog_item{Id := "gardener", Name := "Gardener", Cat := item_cat.Staff, BaseTier := 2, BaseCost := 15000, StaffBonus := 5, RequiresId := "garden", ReqLevel := 3, LevelNames := array{"Gardener"}},
    catalog_item{Id := "chef", Name := "Chef", Cat := item_cat.Staff, BaseTier := 2, BaseCost := 25000, StaffBonus := 10, RequiresId := "kitchen", ReqLevel := 4, LevelNames := array{"Chef"}},
    catalog_item{Id := "driver", Name := "Driver", Cat := item_cat.Staff, BaseTier := 3, BaseCost := 150000, StaffBonus := 10, RequiresId := "garage", ReqLevel := 6, LevelNames := array{"Driver"}},
    catalog_item{Id := "security", Name := "Security", Cat := item_cat.Staff, BaseTier := 4, BaseCost := 1000000, StaffBonus := 15, ReqLevel := 9, LevelNames := array{"Security Team"}},
    catalog_item{Id := "butler", Name := "Butler", Cat := item_cat.Staff, BaseTier := 5, BaseCost := 8000000, StaffBonus := 25, ReqLevel := 12, LevelNames := array{"Butler"}}
}

MakeQuests()<transacts>:[]quest_def = array{
    quest_def{Title := "Build your first room", Kind := quest_kind.RoomsBuilt, Target := 1, RewardCash := 2000, RewardXp := 50},
    quest_def{Title := "Buy your first furniture", Kind := quest_kind.FurnitureOwned, Target := 1, RewardCash := 1000, RewardXp := 40},
    quest_def{Title := "Hire your first staff member", Kind := quest_kind.StaffOwned, Target := 1, RewardCash := 3000, RewardXp := 60},
    quest_def{Title := "Upgrade to a Modern House", Kind := quest_kind.TierReached, Target := 2, RewardCash := 8000, RewardXp := 150},
    quest_def{Title := "Reach $100,000", Kind := quest_kind.CashReached, Target := 100000, RewardCash := 20000, RewardXp := 120},
    quest_def{Title := "Buy your first car", Kind := quest_kind.VehiclesOwned, Target := 1, RewardCash := 30000, RewardXp := 150},
    quest_def{Title := "Build 10 rooms", Kind := quest_kind.RoomsTotal, Target := 10, RewardCash := 60000, RewardXp := 200},
    quest_def{Title := "Build a swimming pool", Kind := quest_kind.ItemLevel, ItemId := "swimming_pool", Target := 1, RewardCash := 100000, RewardXp := 250},
    quest_def{Title := "Reach $1,000,000 Mansion Value", Kind := quest_kind.ValueReached, Target := 1000000, RewardCash := 150000, RewardXp := 300},
    quest_def{Title := "Own a piece of Luxury furniture", Kind := quest_kind.FurnitureQuality, Target := 3, RewardCash := 250000, RewardXp := 300},
    quest_def{Title := "Become a true Mansion owner", Kind := quest_kind.TierReached, Target := 4, RewardCash := 400000, RewardXp := 400},
    quest_def{Title := "Build a Home Cinema", Kind := quest_kind.ItemLevel, ItemId := "cinema", Target := 1, RewardCash := 800000, RewardXp := 400},
    quest_def{Title := "Park 4 cars in your garage", Kind := quest_kind.VehiclesOwned, Target := 4, RewardCash := 1500000, RewardXp := 500},
    quest_def{Title := "Reach Mansion Rank #50", Kind := quest_kind.RankReached, Target := 50, RewardCash := 2000000, RewardXp := 500},
    quest_def{Title := "Hire your full staff", Kind := quest_kind.StaffOwned, Target := 6, RewardCash := 8000000, RewardXp := 600},
    quest_def{Title := "Reach $100,000,000 Mansion Value", Kind := quest_kind.ValueReached, Target := 100000000, RewardCash := 10000000, RewardXp := 700},
    quest_def{Title := "Build your Mega Mansion", Kind := quest_kind.TierReached, Target := 6, RewardCash := 30000000, RewardXp := 1000},
    quest_def{Title := "Build a helipad", Kind := quest_kind.ItemLevel, ItemId := "helipad", Target := 1, RewardCash := 40000000, RewardXp := 800},
    quest_def{Title := "Install a Billionaire Kitchen", Kind := quest_kind.ItemLevel, ItemId := "kitchen", Target := 5, RewardCash := 60000000, RewardXp := 900},
    quest_def{Title := "Own every vehicle", Kind := quest_kind.VehiclesOwned, Target := 7, RewardCash := 150000000, RewardXp := 1200},
    quest_def{Title := "Build the Billionaire Estate", Kind := quest_kind.TierReached, Target := 7, RewardCash := 300000000, RewardXp := 2000},
    quest_def{Title := "Reach $1,000,000,000 Mansion Value", Kind := quest_kind.ValueReached, Target := 1000000000, RewardCash := 500000000, RewardXp := 2000},
    quest_def{Title := "Reach Mansion Rank #1", Kind := quest_kind.RankReached, Target := 1, RewardCash := 1000000000, RewardXp := 3000}
}
