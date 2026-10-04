# Mansion Tycoon - Haupt-Device. Ein Device = ein Grundstueck (Plot) fuer einen Spieler.
# Fuer mehrere Spieler das Device samt Grundstueck kopieren und die Verweise neu setzen.

using { /Fortnite.com/Devices }
using { /Fortnite.com/UI }
using { /Verse.org/Simulation }
using { /UnrealEngine.com/Temporary/SpatialMath }

# ---------- Speicherstand (Fortnite-Persistenz, bleibt zwischen Sitzungen erhalten) ----------

mansion_save := class<final><persistable>:
    Version : int = 1
    Cash : int = 10000
    Xp : int = 0
    Tier : int = 1
    Levels : [string]int = map{}
    QuestsDone : []int = array{}
    TotalEarned : int = 0

var MansionSaves : weak_map(player, mansion_save) = map{}
# Wer in dieser Sitzung schon ein Grundstueck hat (verhindert zwei Plots pro Spieler).
var PlotOwnership : weak_map(session, [player]logic) = map{}

# ---------- Verknuepfung mit der Welt ----------

# Verbindet einen Katalog-Eintrag (ItemId) mit Kauf-Buttons und Props pro Ausbaustufe.
mansion_world_link := class<concrete>:
    @editable ItemId : string = ""
    @editable BuyButtons : []button_device = array{}
    # true: Props aller gekauften Stufen bleiben sichtbar (Anbauten).
    # false: nur die Props der aktuellen Stufe sind sichtbar (Moebel-Qualitaet, Raum-Upgrade).
    @editable Stacking : logic = false
    @editable Level1Props : []creative_prop = array{}
    @editable Level2Props : []creative_prop = array{}
    @editable Level3Props : []creative_prop = array{}
    @editable Level4Props : []creative_prop = array{}
    @editable Level5Props : []creative_prop = array{}

    PropsFor(Level:int):[]creative_prop =
        if (Level = 1) then Level1Props
        else if (Level = 2) then Level2Props
        else if (Level = 3) then Level3Props
        else if (Level = 4) then Level4Props
        else if (Level = 5) then Level5Props
        else array{}

# Props der Haus-Huelle je Mansion-Stufe (1 = Small House ... 7 = Billionaire Estate).
mansion_tier_link := class<concrete>:
    @editable Tier : int = 1
    @editable Props : []creative_prop = array{}

world_buy_handler := class:
    Plot : mansion_plot_device
    ItemId : string
    OnInteract(Agent:agent):void = Plot.HandleWorldBuy(Agent, ItemId)

# ---------- Device ----------

mansion_plot_device := class(creative_device):
    @editable ClaimButtons : []button_device = array{}
    # Spieler bekommen beim Betreten automatisch ein freies Grundstueck.
    @editable AutoClaim : logic = true
    @editable MenuButtons : []button_device = array{}
    @editable MenuInputs : []input_trigger_device = array{}
    @editable TierUpgradeButtons : []button_device = array{}
    @editable WorldLinks : []mansion_world_link = array{}
    @editable TierLinks : []mansion_tier_link = array{}
    # true: Huellen aller erreichten Stufen bleiben sichtbar. false: nur die aktuelle.
    @editable StackTierProps : logic = false
    @editable AnimateNewProps : logic = true
    @editable PurchaseSounds : []audio_player_device = array{}
    @editable LevelUpSounds : []audio_player_device = array{}
    @editable StartCash : int = 10000
    # Zum Testen: ignoriert gespeicherte Spielstaende.
    @editable IgnoreSaves : logic = false

    var Catalog : []catalog_item = array{}
    var TierDefs : []tier_def = array{}
    var Quests : []quest_def = array{}

    var MaybeOwner : ?player = false
    var MaybeHud : ?mansion_hud = false
    var Cash : int = 0
    var Xp : int = 0
    var Tier : int = 1
    var Levels : [string]int = map{}
    var QuestsDone : []int = array{}
    var TotalEarned : int = 0
    var IncomeRemainder : float = 0.0
    var TickCount : int = 0

    OnBegin<override>()<suspends>:void =
        set Catalog = MakeCatalog()
        set TierDefs = MakeTiers()
        set Quests = MakeQuests()
        for (Link : WorldLinks, Button : Link.BuyButtons):
            Handler := world_buy_handler{Plot := Self, ItemId := Link.ItemId}
            Button.InteractedWithEvent.Subscribe(Handler.OnInteract)
        for (Button : ClaimButtons):
            Button.InteractedWithEvent.Subscribe(OnClaimInteract)
        for (Button : MenuButtons):
            Button.InteractedWithEvent.Subscribe(OnMenuInteract)
        for (Input : MenuInputs):
            Input.PressedEvent.Subscribe(OnMenuInteract)
        for (Button : TierUpgradeButtons):
            Button.InteractedWithEvent.Subscribe(OnTierInteract)
        ResetState()
        ApplyAllVisuals()
        GetPlayspace().PlayerAddedEvent().Subscribe(OnPlayerAdded)
        GetPlayspace().PlayerRemovedEvent().Subscribe(OnPlayerRemoved)
        if (AutoClaim?):
            for (P : GetPlayspace().GetPlayers()):
                TryAutoClaim(P)
        IncomeLoop()

    # ---------- Spieler und Grundstueck ----------

    OnPlayerAdded(P:player):void =
        if (AutoClaim?):
            TryAutoClaim(P)

    OnPlayerRemoved(P:player):void =
        if (Owner := MaybeOwner?, Owner = P):
            SaveFor(P)
            SetHasPlot(P, false)
            if (Hud := MaybeHud?):
                Hud.Hide()
            set MaybeHud = false
            set MaybeOwner = false
            ResetState()
            ApplyAllVisuals()

    OnClaimInteract(Agent:agent):void =
        if (P := player[Agent]):
            if (Owner := MaybeOwner?):
                if (Owner = P):
                    Notify("This estate is already yours.")
            else:
                Has := PlayerHasPlot(P)
                if (not Has?):
                    ClaimFor(P)

    TryAutoClaim(P:player):void =
        if (not MaybeOwner?):
            Has := PlayerHasPlot(P)
            if (not Has?):
                ClaimFor(P)

    ClaimFor(P:player):void =
        set MaybeOwner = option{P}
        SetHasPlot(P, true)
        LoadFor(P)
        ApplyAllVisuals()
        Hud := mansion_hud{Plot := Self, PlayerRef := P}
        set MaybeHud = option{Hud}
        Hud.Show()
        if (TotalEarned = 0):
            Notify("Welcome to your new estate! Open the Estate Tablet to build.")
        else:
            Notify("Welcome back! Your {TierName(Tier)} is waiting.")

    PlayerHasPlot(P:player)<transacts>:logic =
        if (Owners := PlotOwnership[GetSession()], Owners[P]?) then true else false

    SetHasPlot(P:player, Value:logic):void =
        var Owners : [player]logic = map{}
        if (Existing := PlotOwnership[GetSession()]):
            set Owners = Existing
        set Owners = ConcatenateMaps(Owners, map{P => Value})
        if (set PlotOwnership[GetSession()] = Owners) {}

    OnMenuInteract(Agent:agent):void =
        if (P := player[Agent], Owner := MaybeOwner?, Owner = P, Hud := MaybeHud?):
            Open := Hud.IsMenuOpen()
            if (Open?):
                Hud.CloseMenu()
            else:
                Hud.OpenMenu()

    OnTierInteract(Agent:agent):void =
        if (P := player[Agent]):
            TryUpgradeTier(P)

    HandleWorldBuy(Agent:agent, ItemId:string):void =
        if (P := player[Agent], Index := FindIndex[ItemId]):
            TryBuy(P, Index)

    # ---------- Speichern und Laden ----------

    ResetState():void =
        set Cash = StartCash
        set Xp = 0
        set Tier = 1
        set QuestsDone = array{}
        set TotalEarned = 0
        set IncomeRemainder = 0.0
        var Start : [string]int = map{}
        for (Item : Catalog, Item.StartLevel > 0):
            set Start = ConcatenateMaps(Start, map{Item.Id => Item.StartLevel})
        set Levels = Start

    LoadFor(P:player):void =
        ResetState()
        if (not IgnoreSaves?, Saved := MansionSaves[P]):
            set Cash = Saved.Cash
            set Xp = Saved.Xp
            set Tier = Saved.Tier
            set QuestsDone = Saved.QuestsDone
            set TotalEarned = Saved.TotalEarned
            set Levels = ConcatenateMaps(Levels, Saved.Levels)

    SaveFor(P:player):void =
        SaveCash := Cash
        SaveXp := Xp
        SaveTier := Tier
        SaveLevels := Levels
        SaveQuests := QuestsDone
        SaveEarned := TotalEarned
        NewSave := mansion_save:
            Version := 1
            Cash := SaveCash
            Xp := SaveXp
            Tier := SaveTier
            Levels := SaveLevels
            QuestsDone := SaveQuests
            TotalEarned := SaveEarned
        if (set MansionSaves[P] = NewSave) {}

    SaveCurrent():void =
        if (Owner := MaybeOwner?):
            SaveFor(Owner)

    # ---------- Einkommen ----------

    IncomeLoop()<suspends>:void =
        loop:
            Sleep(1.0)
            if (MaybeOwner?):
                Tick()

    Tick():void =
        set IncomeRemainder += (IncomePerMinute() * 1.0) / 60.0
        Whole := ToInt(IncomeRemainder)
        if (Whole > 0):
            set IncomeRemainder -= Whole * 1.0
            set Cash += Whole
            set TotalEarned += Whole
        set TickCount += 1
        if (TickCount >= 10):
            set TickCount = 0
            # XP fuers Geldverdienen
            AddXp(3 * Tier)
            SaveCurrent()
        CheckQuests()
        if (Hud := MaybeHud?):
            Hud.Refresh()

    # ---------- Kaufen ----------

    TryBuy(P:player, Index:int):void =
        if (Owner := MaybeOwner?, Owner = P, Item := Catalog[Index]):
            Current := GetLevel(Item.Id)
            Next := Current + 1
            Reason := LockReason(Item, Next)
            Cost := ItemCost(Item, Next)
            if (Reason <> ""):
                Notify(Reason)
            else if (Cash < Cost):
                Notify("Not enough cash - you need {FormatMoney(Cost - Cash)} more")
            else:
                set Cash -= Cost
                set Levels = ConcatenateMaps(Levels, map{Item.Id => Next})
                for (Link : WorldLinks, Link.ItemId = Item.Id):
                    ApplyLink(Link, Next)
                PlaySounds(PurchaseSounds)
                Verb := if (Current = 0) then "NEW" else "UPGRADED"
                Notify("{Verb}: {LevelName(Item, Next)}")
                AddXp(30 * LevelTier(Item, Next))
                AfterChange()

    TryUpgradeTier(P:player):void =
        if (Owner := MaybeOwner?, Owner = P):
            if (Next := TierDefs[Tier]):
                PL := PlayerLevel()
                Rooms := RoomsOwned()
                if (PL < Next.ReqLevel):
                    Notify("{Next.Name} requires Player Level {Next.ReqLevel}")
                else if (Rooms < Next.ReqRooms):
                    Notify("{Next.Name} requires {Next.ReqRooms} rooms - you have {Rooms}")
                else if (Cash < Next.Cost):
                    Notify("Not enough cash - {Next.Name} costs {FormatMoney(Next.Cost)}")
                else:
                    set Cash -= Next.Cost
                    set Tier += 1
                    ApplyTierVisuals(Tier)
                    PlaySounds(LevelUpSounds)
                    Notify("NEW HOME: {Next.Name}!  New rooms and items unlocked")
                    AddXp(200 * Tier)
                    AfterChange()
            else:
                Notify("You already own the Billionaire Estate!")

    AfterChange():void =
        CheckQuests()
        UpdateButtons()
        SaveCurrent()
        if (Hud := MaybeHud?):
            Hud.Refresh()
            Hud.RefreshMenu()

    LockReason(Item:catalog_item, Next:int)<transacts>:string =
        MaxLevel := Item.LevelNames.Length
        NeedTier := LevelTier(Item, Next)
        PL := PlayerLevel()
        HasRequired := if (Item.RequiresId = "") then 1 else GetLevel(Item.RequiresId)
        Cars := VehiclesOwned()
        Slots := GarageCapacity(GetLevel("garage"))
        if (Next > MaxLevel):
            "Already at max level"
        else if (NeedTier > Tier):
            "Requires {TierName(NeedTier)}"
        else if (Next = 1, PL < Item.ReqLevel):
            "Requires Player Level {Item.ReqLevel}"
        else if (HasRequired < 1):
            "Requires {NameOf(Item.RequiresId)}"
        else if (Item.Cat = item_cat.Vehicle, Cars >= Slots):
            "Garage full - expand your garage"
        else:
            ""

    # ---------- Quests und XP ----------

    CheckQuests():void =
        for (Index -> Q : Quests):
            Done := IsQuestDone(Index)
            if (not Done?):
                Progress := QuestProgress(Q)
                if (Progress >= Q.Target):
                    set QuestsDone += array{Index}
                    set Cash += Q.RewardCash
                    Notify("QUEST COMPLETE: {Q.Title}   +{FormatMoney(Q.RewardCash)}  +{Q.RewardXp} XP")
                    AddXp(Q.RewardXp)

    IsQuestDone(Index:int)<transacts>:logic =
        var Result : logic = false
        for (D : QuestsDone, D = Index):
            set Result = true
        Result

    QuestProgress(Q:quest_def)<transacts>:int =
        case (Q.Kind):
            quest_kind.RoomsBuilt => RoomsBuilt()
            quest_kind.RoomsTotal => RoomsOwned()
            quest_kind.FurnitureOwned => FurnitureOwned()
            quest_kind.StaffOwned => StaffOwned()
            quest_kind.VehiclesOwned => VehiclesOwned()
            quest_kind.CashReached => Cash
            quest_kind.TierReached => Tier
            quest_kind.ItemLevel => GetLevel(Q.ItemId)
            quest_kind.ValueReached => MansionValue()
            quest_kind.FurnitureQuality => MaxFurnitureLevel()
            quest_kind.RankReached => (if (RankFor(MansionValue()) <= Q.Target) then Q.Target else 0)

    AddXp(Amount:int):void =
        Before := PlayerLevel()
        set Xp += Amount
        After := PlayerLevel()
        if (After > Before):
            PlaySounds(LevelUpSounds)
            Notify("LEVEL UP!  You are now Player Level {After}")

    PlayerLevel()<transacts>:int =
        var L : int = 1
        var Rest : int = Xp
        loop:
            Need := XpToNext(L)
            if (Rest >= Need):
                set Rest -= Need
                set L += 1
            else:
                break
        L

    XpIntoLevel()<transacts>:int =
        var L : int = 1
        var Rest : int = Xp
        loop:
            Need := XpToNext(L)
            if (Rest >= Need):
                set Rest -= Need
                set L += 1
            else:
                break
        Rest

    # ---------- Werte ----------

    GetLevel(Id:string)<transacts>:int =
        if (L := Levels[Id]) then L else 0

    FindIndex(Id:string)<decides><transacts>:int =
        var Found : int = -1
        for (Index -> Item : Catalog, Item.Id = Id):
            set Found = Index
        Found >= 0
        Found

    NameOf(Id:string)<transacts>:string =
        var Name : string = Id
        for (Item : Catalog, Item.Id = Id):
            set Name = Item.Name
        Name

    TierName(T:int)<transacts>:string =
        if (D := TierDefs[T - 1]) then D.Name else "Estate"

    IncomePerMinute()<transacts>:int =
        var Sum : int = if (T := TierDefs[Tier - 1]) then T.BaseIncome else 100
        for (Item : Catalog):
            L := GetLevel(Item.Id)
            for (K := 1..L):
                if (K > Item.StartLevel):
                    set Sum += ItemIncome(Item, K)
        Percent := 100 + StaffBonusPercent()
        ToInt((Sum * 1.0) * (Percent * 1.0) / 100.0)

    MansionValue()<transacts>:int =
        var Value : int = 0
        for (Index -> T : TierDefs, Index < Tier):
            set Value += T.Value
        for (Item : Catalog):
            L := GetLevel(Item.Id)
            for (K := 1..L):
                set Value += ItemValue(Item, K)
        Value

    StaffBonusPercent()<transacts>:int =
        var Sum : int = 0
        for (Item : Catalog, Item.Cat = item_cat.Staff):
            if (GetLevel(Item.Id) > 0):
                set Sum += Item.StaffBonus
        Sum

    RoomsOwned()<transacts>:int =
        var Count : int = 0
        for (Item : Catalog):
            IsRoom := IsRoomCat(Item.Cat)
            if (IsRoom?, GetLevel(Item.Id) > 0):
                set Count += 1
        Count

    RoomsBuilt()<transacts>:int =
        var Count : int = 0
        for (Item : Catalog):
            IsRoom := IsRoomCat(Item.Cat)
            if (IsRoom?, Item.StartLevel = 0, GetLevel(Item.Id) > 0):
                set Count += 1
        Count

    CountCat(Cat:item_cat)<transacts>:int =
        var Count : int = 0
        for (Item : Catalog, Item.Cat = Cat):
            if (GetLevel(Item.Id) > 0):
                set Count += 1
        Count

    FurnitureOwned()<transacts>:int = CountCat(item_cat.Furniture)
    VehiclesOwned()<transacts>:int = CountCat(item_cat.Vehicle)
    StaffOwned()<transacts>:int = CountCat(item_cat.Staff)

    FurnitureLevelsOwned()<transacts>:int =
        var Sum : int = 0
        for (Item : Catalog, Item.Cat = item_cat.Furniture):
            set Sum += GetLevel(Item.Id)
        Sum

    MaxFurnitureLevel()<transacts>:int =
        var Best : int = 0
        for (Item : Catalog, Item.Cat = item_cat.Furniture):
            set Best = Max(Best, GetLevel(Item.Id))
        Best

    TotalOfCat(Cat:item_cat)<transacts>:int =
        var Count : int = 0
        for (Item : Catalog, Item.Cat = Cat):
            set Count += 1
        Count

    NextTierProgress()<transacts>:float =
        if (Next := TierDefs[Tier]):
            A := Ratio(Cash, Next.Cost)
            B := Ratio(PlayerLevel(), Next.ReqLevel)
            C := Ratio(RoomsOwned(), Next.ReqRooms)
            (A + B + C) / 3.0
        else:
            1.0

    NextTierText()<transacts>:string =
        if (Next := TierDefs[Tier]):
            "{Next.Name}\n{FormatMoney(Next.Cost)}  |  Lvl {Next.ReqLevel}  |  {Next.ReqRooms} rooms"
        else:
            "Maximum reached. You built a Billionaire Estate!"

    CollectionText()<transacts>:string =
        "Rooms {RoomsOwned()}/{TotalRooms}   Furniture {FurnitureLevelsOwned()}/{TotalOfCat(item_cat.Furniture) * 4}\nCars {VehiclesOwned()}/{TotalOfCat(item_cat.Vehicle)}   Staff {StaffOwned()}/{TotalOfCat(item_cat.Staff)}   Quests {QuestsDone.Length}/{Quests.Length}"

    # ---------- Menue-Inhalte ----------

    TabHeader(Tab:int)<transacts>:string =
        if (Tab = 0):
            Value := MansionValue()
            "{TierName(Tier)}  -  Home {Tier} of {MaxTier}\nMansion Value {FormatFull(Value)}   |   Rank #{RankFor(Value)}\nIncome {FormatMoney(IncomePerMinute())}/min   |   Staff bonus +{StaffBonusPercent()}%   |   Earned {FormatMoney(TotalEarned)}"
        else if (Tab = 1):
            "Build new rooms. The upper floor opens with the Modern House,\nthe Luxury Wing with the Luxury Villa."
        else if (Tab = 2):
            "Furnish your rooms. Every piece comes in Basic, Premium, Luxury and Elite."
        else if (Tab = 3):
            "Garage: {GetLevel("garage")} of 4 expansions   |   Parking {VehiclesOwned()} / {GarageCapacity(GetLevel("garage"))}"
        else if (Tab = 4):
            "Staff boost your whole income. Current bonus: +{StaffBonusPercent()}%"
        else if (Tab = 5):
            "Upgrade the rooms you own. Each level needs a bigger home."
        else:
            "Completed {QuestsDone.Length} of {Quests.Length} quests. Rewards are paid out automatically."

    RowsForTab(Tab:int)<transacts>:[]menu_row =
        var Rows : []menu_row = array{}
        if (Tab = 0):
            set Rows += array{TierRow()}
            for (Index -> Item : Catalog, Item.Cat = item_cat.Land):
                set Rows += array{ItemRow(Index, Item)}
        else if (Tab = 6):
            set Rows = QuestRows()
        else:
            for (Index -> Item : Catalog):
                L := GetLevel(Item.Id)
                IsRoom := IsRoomCat(Item.Cat)
                var Show : logic = false
                if (Tab = 1, IsRoom?, L = 0, Item.BaseTier <= Tier + 1):
                    set Show = true
                if (Tab = 2, Item.Cat = item_cat.Furniture, Item.BaseTier <= Tier + 1):
                    set Show = true
                if (Tab = 3, Item.Cat = item_cat.Vehicle, Item.BaseTier <= Tier + 1):
                    set Show = true
                if (Tab = 3, Item.Id = "garage"):
                    set Show = true
                if (Tab = 4, Item.Cat = item_cat.Staff):
                    set Show = true
                if (Tab = 5, L > 0, L < Item.LevelNames.Length, IsRoom?):
                    set Show = true
                if (Tab = 5, L > 0, L < Item.LevelNames.Length, Item.Cat = item_cat.Land):
                    set Show = true
                if (Show?):
                    set Rows += array{ItemRow(Index, Item)}
        Rows

    ItemRow(Index:int, Item:catalog_item)<transacts>:menu_row =
        L := GetLevel(Item.Id)
        MaxLevel := Item.LevelNames.Length
        if (L >= MaxLevel):
            menu_row{
                Info := "{LevelName(Item, L)}      [MAX]\n{CatLabel(Item.Cat)}  |  Fully upgraded  |  Level {L}/{MaxLevel}",
                ButtonLabel := "OWNED", Action := Index, HasButton := true, Enabled := false}
        else:
            Next := L + 1
            Reason := LockReason(Item, Next)
            Cost := ItemCost(Item, Next)
            Gain := if (Item.Cat = item_cat.Staff) then "+{Item.StaffBonus}% total income" else "+{FormatMoney(ItemIncome(Item, Next))}/min"
            var Info : string = "{LevelName(Item, Next)}      {CatLabel(Item.Cat)}  |  Level {Next}/{MaxLevel}\n{Gain}   |   +{FormatMoney(ItemValue(Item, Next))} value   |   +{30 * LevelTier(Item, Next)} XP"
            if (L > 0):
                set Info = Info + "\nNow: {LevelName(Item, L)}"
            if (Reason <> ""):
                set Info = Info + "\nLOCKED: {Reason}"
            Label := if (Reason = "") then "BUY  {FormatMoney(Cost)}" else "LOCKED"
            Unlocked := if (Reason = "") then true else false
            menu_row{Info := Info, ButtonLabel := Label, Action := Index, HasButton := true, Enabled := Unlocked}

    TierRow()<transacts>:menu_row =
        if (Next := TierDefs[Tier]):
            PL := PlayerLevel()
            Rooms := RoomsOwned()
            Ready := if (PL >= Next.ReqLevel, Rooms >= Next.ReqRooms) then true else false
            menu_row{
                Info := "UPGRADE YOUR HOME:  {Next.Name}\nBase income {FormatMoney(Next.BaseIncome)}/min   |   +{FormatMoney(Next.Value)} value   |   unlocks new rooms\nNeeds Player Level {Next.ReqLevel} (you: {PL})  and  {Next.ReqRooms} rooms (you: {Rooms})",
                ButtonLabel := (if (Ready?) then "UPGRADE  {FormatMoney(Next.Cost)}" else "LOCKED"),
                Action := -1, HasButton := true, Enabled := Ready}
        else:
            menu_row{Info := "BILLIONAIRE ESTATE\nYou own the greatest home there is. Keep collecting and climb to Rank #1.", HasButton := false}

    QuestRows()<transacts>:[]menu_row =
        var Open : []menu_row = array{}
        var Finished : []menu_row = array{}
        for (Index -> Q : Quests):
            Done := IsQuestDone(Index)
            Reward := "Reward {FormatMoney(Q.RewardCash)} + {Q.RewardXp} XP"
            if (Done?):
                set Finished += array{menu_row{Info := "[DONE]  {Q.Title}\n{Reward}"}}
            else:
                set Open += array{menu_row{Info := "{Q.Title}\n{Reward}   |   Progress: {QuestProgressText(Q)}"}}
        Open + Finished

    QuestProgressText(Q:quest_def)<transacts>:string =
        P := QuestProgress(Q)
        case (Q.Kind):
            quest_kind.CashReached => "{FormatMoney(Cash)} / {FormatMoney(Q.Target)}"
            quest_kind.ValueReached => "{FormatMoney(P)} / {FormatMoney(Q.Target)}"
            quest_kind.RankReached => "Rank #{RankFor(MansionValue())} / #{Q.Target}"
            quest_kind.TierReached => "{TierName(Tier)} / {TierName(Q.Target)}"
            _ => "{Min(P, Q.Target)} / {Q.Target}"

    # ---------- Darstellung in der Welt ----------

    ApplyAllVisuals():void =
        for (Link : WorldLinks):
            ApplyLink(Link, 0)
        ApplyTierVisuals(0)
        UpdateButtons()

    # AnimateLevel: diese Stufe faehrt animiert aus dem Boden (0 = keine Animation).
    ApplyLink(Link:mansion_world_link, AnimateLevel:int):void =
        Level := GetLevel(Link.ItemId)
        for (L := 1..5):
            var ShowIt : logic = false
            if (Link.Stacking?):
                if (L <= Level) then set ShowIt = true
            else:
                if (L = Level) then set ShowIt = true
            for (Prop : Link.PropsFor(L)):
                if (ShowIt?):
                    if (L = AnimateLevel, AnimateNewProps?):
                        spawn{ RiseIn(Prop) }
                    else:
                        Prop.Show()
                else:
                    Prop.Hide()

    ApplyTierVisuals(AnimateTier:int):void =
        for (TierLink : TierLinks):
            var ShowIt : logic = false
            if (StackTierProps?):
                if (TierLink.Tier <= Tier) then set ShowIt = true
            else:
                if (TierLink.Tier = Tier) then set ShowIt = true
            for (Prop : TierLink.Props):
                if (ShowIt?):
                    if (TierLink.Tier = AnimateTier, AnimateNewProps?):
                        spawn{ RiseIn(Prop) }
                    else:
                        Prop.Show()
                else:
                    Prop.Hide()

    RiseIn(Prop:creative_prop)<suspends>:void =
        Target := Prop.GetTransform()
        Below := Target.Translation - vector3{X := 0.0, Y := 0.0, Z := 350.0}
        if (Prop.TeleportTo[Below, Target.Rotation]) {}
        Prop.Show()
        Prop.MoveTo(Target.Translation, Target.Rotation, 0.8)

    UpdateButtons():void =
        for (Link : WorldLinks, Index := FindIndex[Link.ItemId], Item := Catalog[Index], Button : Link.BuyButtons):
            Level := GetLevel(Item.Id)
            if (Level >= Item.LevelNames.Length):
                Button.SetInteractionText(S2M("{LevelName(Item, Level)} - MAX"))
            else:
                Button.SetInteractionText(S2M("{LevelName(Item, Level + 1)} - {FormatMoney(ItemCost(Item, Level + 1))}"))
        for (Button : TierUpgradeButtons):
            if (Next := TierDefs[Tier]):
                Button.SetInteractionText(S2M("Upgrade to {Next.Name} - {FormatMoney(Next.Cost)}"))
            else:
                Button.SetInteractionText(S2M("Billionaire Estate"))

    PlaySounds(Sounds:[]audio_player_device):void =
        for (Sound : Sounds):
            Sound.Play()

    Notify(Text:string):void =
        if (Hud := MaybeHud?):
            Hud.Toast(Text)
