# Disaster Survival (UEFN) - content: disasters, missions, events, ranks, unlocks and helpers.
# Same rules and numbers as the Unity version (disaster-survival/Unity/.../Core/Content.cs).

using { /Verse.org/Simulation }

ds_disaster := enum{Tornado, Flood, Earthquake, Wildfire, Blizzard, Volcano}
ds_mission_kind := enum{Survive, ActivateRadios, Rescue, DeliverKit, HoldBunker, ReachRooftop, LastSurvivor}
ds_secret_kind := enum{ReachBefore, RescueTarget, KeepTargetFromStation, MostActivations}
ds_effect := enum{PowerFailure, InjurePlayer, HazardMoves, WaterRising, GroundShaking, LowVisibility, SupplyDrop, Finale}
ds_zone := enum{Station, Bunker, Rooftop}
ds_story_kind := enum{Injured, Rescued, LeftBehind, Eliminated, MissionDone, SecretDone, SecretFailed, Survived, LastSurvivor}
ds_milestone := enum{None, Rescues, LastSurvivor, LeftBehind, SecretMissions, SurvivedDisaster}

ds_mission := struct:
    Id : string = ""
    Title : string = ""
    Kind : ds_mission_kind = ds_mission_kind.Survive
    Target : int = 1
    Reward : int = 0

ds_event := struct:
    Id : string = ""
    Title : string = ""
    Description : string = ""
    InOpening : logic = true
    InMidgame : logic = true
    InFinale : logic = false
    IsFinale : logic = false
    Duration : float = 25.0
    Weight : int = 10
    # Empty = every disaster
    Disasters : []ds_disaster = array{}
    PowerFailure : logic = false
    InjurePlayer : logic = false
    HazardMoves : logic = false
    WaterRising : logic = false
    GroundShaking : logic = false
    LowVisibility : logic = false
    SupplyDrop : logic = false

ds_disaster_def := struct:
    Kind : ds_disaster = ds_disaster.Tornado
    Name : string = ""
    Intro : string = ""
    Cause : string = "did not make it"
    Duration : float = 240.0
    Missions : []ds_mission = array{}

ds_rank := struct:
    Name : string = ""
    MinSp : int = 0
    MinRescues : int = 0
    MinLastSurvivor : int = 0
    MinSecrets : int = 0
    MinDisasterTypes : int = 0

ds_unlock := struct:
    Id : string = ""
    Name : string = ""
    Category : string = ""
    # Unlocked when this rank is reached ...
    Rank : string = ""
    # ... or when this milestone is met
    Milestone : ds_milestone = ds_milestone.None
    MilestoneValue : int = 0
    MilestoneDisaster : ds_disaster = ds_disaster.Tornado

ds_story := struct:
    Round : int = 0
    Kind : ds_story_kind = ds_story_kind.Survived
    Actor : int = -1
    Other : int = -1
    Text : string = ""

DsSecretReward : int = 700
DsRepeatRescueBonus : int = 150
DsCallsigns : []string = array{"Red", "Blue", "Green", "Yellow", "Orange", "Purple", "Pink", "Teal", "Gold", "Silver", "White", "Black", "Lime", "Navy", "Coral", "Mint"}

# ---------- helpers ----------

DsToInt(F:float)<transacts>:int =
    if (I := Floor[F]) then I else 0

DsPad2(N:int)<transacts>:string =
    if (N < 10) then "0{N}" else "{N}"

DsPad3(N:int)<transacts>:string =
    if (N < 10) then "00{N}" else if (N < 100) then "0{N}" else "{N}"

# 12450 -> "12,450"
DsNumber(Amount:int)<transacts>:string =
    var Rest : int = Amount
    var Out : string = ""
    loop:
        if (Rest < 1000):
            set Out = "{Rest}{Out}"
            break
        else:
            Q := DsToInt((Rest * 1.0) / 1000.0)
            set Out = ",{DsPad3(Rest - Q * 1000)}{Out}"
            set Rest = Q
    Out

# A mod B for non-negative A and positive B
DsMod(A:int, B:int)<transacts>:int =
    if (B <= 0) then 0 else A - B * DsToInt((A * 1.0) / (B * 1.0))

# 192.4 -> "3:12"
DsClock(Seconds:float)<transacts>:string =
    Total := DsToInt(Seconds + 0.99)
    Minutes := DsToInt((Total * 1.0) / 60.0)
    "{Minutes}:{DsPad2(Total - Minutes * 60)}"

DsDisasterIndex(D:ds_disaster)<transacts>:int =
    case (D):
        ds_disaster.Tornado => 0
        ds_disaster.Flood => 1
        ds_disaster.Earthquake => 2
        ds_disaster.Wildfire => 3
        ds_disaster.Blizzard => 4
        ds_disaster.Volcano => 5

DsEventHas(E:ds_event, Effect:ds_effect)<transacts>:logic =
    case (Effect):
        ds_effect.PowerFailure => E.PowerFailure
        ds_effect.InjurePlayer => E.InjurePlayer
        ds_effect.HazardMoves => E.HazardMoves
        ds_effect.WaterRising => E.WaterRising
        ds_effect.GroundShaking => E.GroundShaking
        ds_effect.LowVisibility => E.LowVisibility
        ds_effect.SupplyDrop => E.SupplyDrop
        ds_effect.Finale => E.IsFinale

DsEventAllowed(E:ds_event, D:ds_disaster)<transacts>:logic =
    var Found : logic = false
    if (E.Disasters.Length = 0):
        set Found = true
    for (X : E.Disasters, X = D):
        set Found = true
    Found

# ---------- missions ----------

DsSurvive()<transacts>:ds_mission = ds_mission{Id := "survive", Title := "Survive", Kind := ds_mission_kind.Survive, Reward := 500}
DsRadios()<transacts>:ds_mission = ds_mission{Id := "radios", Title := "Activate 3 emergency radios", Kind := ds_mission_kind.ActivateRadios, Target := 3, Reward := 400}
DsRescue()<transacts>:ds_mission = ds_mission{Id := "rescue", Title := "Help an injured player", Kind := ds_mission_kind.Rescue, Reward := 600}
DsKit()<transacts>:ds_mission = ds_mission{Id := "kit", Title := "Bring the emergency kit to the rescue station", Kind := ds_mission_kind.DeliverKit, Reward := 300}
DsBunker()<transacts>:ds_mission = ds_mission{Id := "bunker", Title := "Hold the bunker for 60 seconds", Kind := ds_mission_kind.HoldBunker, Target := 60, Reward := 800}
DsRoof()<transacts>:ds_mission = ds_mission{Id := "roof", Title := "Reach the rooftop", Kind := ds_mission_kind.ReachRooftop, Reward := 250}
DsLast()<transacts>:ds_mission = ds_mission{Id := "last", Title := "Be the last survivor", Kind := ds_mission_kind.LastSurvivor, Reward := 400}

DsDisasters()<transacts>:[]ds_disaster_def = array{
    ds_disaster_def{Kind := ds_disaster.Tornado, Name := "Tornado", Intro := "A tornado is touching down. Find cover.", Cause := "was swept away by the tornado", Duration := 240.0,
        Missions := array{DsSurvive(), DsRadios(), DsRescue(), DsKit(), DsBunker(), DsLast()}},
    ds_disaster_def{Kind := ds_disaster.Flood, Name := "Flood", Intro := "The dam broke. Get to high ground.", Cause := "drowned", Duration := 240.0,
        Missions := array{DsSurvive(), DsRescue(), DsKit(), DsRoof(), DsRadios(), DsLast()}},
    ds_disaster_def{Kind := ds_disaster.Earthquake, Name := "Earthquake", Intro := "The ground is shaking. Stay away from buildings.", Cause := "was buried by debris", Duration := 210.0,
        Missions := array{DsSurvive(), DsRescue(), DsRadios(), DsBunker(), DsKit(), DsLast()}},
    ds_disaster_def{Kind := ds_disaster.Wildfire, Name := "Wildfire", Intro := "The forest is on fire. The wind is turning.", Cause := "was caught by the fire", Duration := 240.0,
        Missions := array{DsSurvive(), DsRescue(), DsKit(), DsBunker(), DsRoof(), DsLast()}},
    ds_disaster_def{Kind := ds_disaster.Blizzard, Name := "Blizzard", Intro := "A whiteout is coming. Keep moving or freeze.", Cause := "froze", Duration := 240.0,
        Missions := array{DsSurvive(), DsRadios(), DsRescue(), DsBunker(), DsKit(), DsLast()}},
    ds_disaster_def{Kind := ds_disaster.Volcano, Name := "Volcano", Intro := "The volcano erupts. Lava is on its way.", Cause := "was caught by the lava", Duration := 210.0,
        Missions := array{DsSurvive(), DsRescue(), DsRoof(), DsKit(), DsRadios(), DsLast()}}
}

DsEvents()<transacts>:[]ds_event = array{
    ds_event{Id := "direction", Title := "Tornado changes direction", Description := "The safe side is not safe anymore.",
        InMidgame := true, Duration := 20.0, Weight := 14, HazardMoves := true, Disasters := array{ds_disaster.Tornado}},
    ds_event{Id := "wind", Title := "The wind turns", Description := "The fire is spreading toward the village.",
        Duration := 20.0, Weight := 14, HazardMoves := true, Disasters := array{ds_disaster.Wildfire, ds_disaster.Volcano}},
    ds_event{Id := "power", Title := "Power failure", Description := "The bunker doors do not work anymore.",
        InOpening := false, Duration := 30.0, Weight := 12, PowerFailure := true},
    ds_event{Id := "rescue_call", Title := "Rescue event", Description := "A player was injured.",
        Duration := 35.0, Weight := 12, InjurePlayer := true},
    ds_event{Id := "flood_wave", Title := "Flood wave", Description := "The water is rising fast. Get up high.",
        InOpening := false, InFinale := true, Duration := 25.0, Weight := 10, WaterRising := true,
        Disasters := array{ds_disaster.Flood, ds_disaster.Tornado, ds_disaster.Earthquake}},
    ds_event{Id := "aftershock", Title := "Aftershock", Description := "Buildings are collapsing. Get out into the open.",
        InOpening := false, InFinale := true, Duration := 15.0, Weight := 12, GroundShaking := true,
        Disasters := array{ds_disaster.Earthquake, ds_disaster.Volcano}},
    ds_event{Id := "smoke", Title := "Thick smoke", Description := "You can barely see anything.",
        Duration := 25.0, Weight := 8, LowVisibility := true,
        Disasters := array{ds_disaster.Wildfire, ds_disaster.Volcano, ds_disaster.Blizzard}},
    ds_event{Id := "supply", Title := "Supply drop", Description := "Gear is landing. First come, first served.",
        Duration := 20.0, Weight := 8, SupplyDrop := true},
    # Finale: one of these near the end of every round
    ds_event{Id := "finale_supercell", Title := "Supercell", Description := "The tornado reaches full strength. Only the bunker is safe.",
        InOpening := false, InMidgame := false, InFinale := true, IsFinale := true, Duration := 40.0, HazardMoves := true, LowVisibility := true,
        Disasters := array{ds_disaster.Tornado}},
    ds_event{Id := "finale_dam", Title := "Second dam breaks", Description := "Everything below the rooftops will be underwater.",
        InOpening := false, InMidgame := false, InFinale := true, IsFinale := true, Duration := 40.0, WaterRising := true,
        Disasters := array{ds_disaster.Flood}},
    ds_event{Id := "finale_mainshock", Title := "The main shock", Description := "The big one. Nothing stays standing.",
        InOpening := false, InMidgame := false, InFinale := true, IsFinale := true, Duration := 35.0, GroundShaking := true, PowerFailure := true,
        Disasters := array{ds_disaster.Earthquake}},
    ds_event{Id := "finale_firestorm", Title := "Firestorm", Description := "The fire closes in from all sides.",
        InOpening := false, InMidgame := false, InFinale := true, IsFinale := true, Duration := 40.0, HazardMoves := true, LowVisibility := true,
        Disasters := array{ds_disaster.Wildfire}},
    ds_event{Id := "finale_whiteout", Title := "Total whiteout", Description := "Zero visibility. Follow the radios home.",
        InOpening := false, InMidgame := false, InFinale := true, IsFinale := true, Duration := 40.0, LowVisibility := true, PowerFailure := true,
        Disasters := array{ds_disaster.Blizzard}},
    ds_event{Id := "finale_eruption", Title := "Main eruption", Description := "Lava floods the valley. Climb.",
        InOpening := false, InMidgame := false, InFinale := true, IsFinale := true, Duration := 40.0, HazardMoves := true, GroundShaking := true, WaterRising := true,
        Disasters := array{ds_disaster.Volcano}}
}

DsRanks()<transacts>:[]ds_rank = array{
    ds_rank{Name := "Rookie"},
    ds_rank{Name := "Survivor", MinSp := 6000},
    ds_rank{Name := "Veteran", MinSp := 35000, MinRescues := 10, MinDisasterTypes := 3},
    ds_rank{Name := "Elite", MinSp := 120000, MinRescues := 30, MinLastSurvivor := 2, MinSecrets := 8, MinDisasterTypes := 5},
    ds_rank{Name := "Disaster Master", MinSp := 350000, MinRescues := 80, MinLastSurvivor := 5, MinSecrets := 25, MinDisasterTypes := 6}
}

DsUnlocks()<transacts>:[]ds_unlock = array{
    ds_unlock{Id := "title_rookie", Name := "Title: Rookie", Category := "Title", Rank := "Rookie"},
    ds_unlock{Id := "outfit_raincoat", Name := "Yellow Raincoat", Category := "Outfit", Rank := "Survivor"},
    ds_unlock{Id := "emote_phew", Name := "Emote: Phew!", Category := "Emote", Rank := "Survivor"},
    ds_unlock{Id := "equip_flare", Name := "Signal Flare", Category := "Equipment", Rank := "Veteran"},
    ds_unlock{Id := "char_ranger", Name := "Character: Park Ranger", Category := "Character", Rank := "Veteran"},
    ds_unlock{Id := "banner_storm", Name := "Banner: Eye of the Storm", Category := "Banner", Rank := "Veteran"},
    ds_unlock{Id := "vehicle_atv", Name := "Rescue ATV", Category := "Vehicle", Rank := "Elite"},
    ds_unlock{Id := "spawn_lightning", Name := "Spawn Effect: Lightning Strike", Category := "Spawn Effect", Rank := "Elite"},
    ds_unlock{Id := "anim_hero_landing", Name := "Animation: Hero Landing", Category := "Animation", Rank := "Elite"},
    ds_unlock{Id := "title_master", Name := "Title: Disaster Master", Category := "Title", Rank := "Disaster Master"},
    ds_unlock{Id := "spawn_meteor", Name := "Spawn Effect: Meteor", Category := "Spawn Effect", Rank := "Disaster Master"},
    ds_unlock{Id := "vehicle_heli", Name := "Rescue Helicopter", Category := "Vehicle", Rank := "Disaster Master"},
    ds_unlock{Id := "title_lifesaver", Name := "Title: Lifesaver", Category := "Title", Milestone := ds_milestone.Rescues, MilestoneValue := 10},
    ds_unlock{Id := "outfit_paramedic", Name := "Paramedic Outfit", Category := "Outfit", Milestone := ds_milestone.Rescues, MilestoneValue := 25},
    ds_unlock{Id := "title_lone_wolf", Name := "Title: Lone Wolf", Category := "Title", Milestone := ds_milestone.LastSurvivor, MilestoneValue := 5},
    ds_unlock{Id := "emote_shrug", Name := "Emote: Not My Problem", Category := "Emote", Milestone := ds_milestone.LeftBehind, MilestoneValue := 5},
    ds_unlock{Id := "banner_mastermind", Name := "Banner: Mastermind", Category := "Banner", Milestone := ds_milestone.SecretMissions, MilestoneValue := 10},
    ds_unlock{Id := "char_storm_chaser", Name := "Character: Storm Chaser", Category := "Character", Milestone := ds_milestone.SurvivedDisaster, MilestoneValue := 10, MilestoneDisaster := ds_disaster.Tornado},
    ds_unlock{Id := "char_lifeguard", Name := "Character: Lifeguard", Category := "Character", Milestone := ds_milestone.SurvivedDisaster, MilestoneValue := 10, MilestoneDisaster := ds_disaster.Flood},
    ds_unlock{Id := "equip_fire_blanket", Name := "Fire Blanket", Category := "Equipment", Milestone := ds_milestone.SurvivedDisaster, MilestoneValue := 10, MilestoneDisaster := ds_disaster.Wildfire},
    ds_unlock{Id := "anim_dust_off", Name := "Animation: Dust Off", Category := "Animation", Milestone := ds_milestone.SurvivedDisaster, MilestoneValue := 10, MilestoneDisaster := ds_disaster.Earthquake}
}
