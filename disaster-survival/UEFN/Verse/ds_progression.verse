# Disaster Survival (UEFN) - saved progress, survival rank and unlocks.
# Saved per player with Fortnite persistence, so it carries over between sessions.

using { /Verse.org/Simulation }

ds_profile := class<final><persistable>:
    Version : int = 1
    Rank : string = "Rookie"
    TotalSp : int = 0
    RoundsPlayed : int = 0
    RoundsSurvived : int = 0
    Rescues : int = 0
    LastSurvivorWins : int = 0
    SecretMissions : int = 0
    LeftBehind : int = 0
    SurvivedByType : []int = array{0, 0, 0, 0, 0, 0}
    Unlocked : []string = array{}

var DsProfiles : weak_map(player, ds_profile) = map{}

# Working copy while the game runs (persistable classes cannot be changed in place)
ds_progress := class:
    var Rank : string = "Rookie"
    var TotalSp : int = 0
    var RoundsPlayed : int = 0
    var RoundsSurvived : int = 0
    var Rescues : int = 0
    var LastSurvivorWins : int = 0
    var SecretMissions : int = 0
    var LeftBehind : int = 0
    var SurvivedByType : []int = array{0, 0, 0, 0, 0, 0}
    var Unlocked : []string = array{}

DsLoadProgress(P:player, IgnoreSaves:logic):ds_progress =
    G := ds_progress{}
    if (not IgnoreSaves?, Saved := DsProfiles[P]):
        set G.Rank = Saved.Rank
        set G.TotalSp = Saved.TotalSp
        set G.RoundsPlayed = Saved.RoundsPlayed
        set G.RoundsSurvived = Saved.RoundsSurvived
        set G.Rescues = Saved.Rescues
        set G.LastSurvivorWins = Saved.LastSurvivorWins
        set G.SecretMissions = Saved.SecretMissions
        set G.LeftBehind = Saved.LeftBehind
        set G.Unlocked = Saved.Unlocked
        # Older saves may know fewer disasters
        var Counts : []int = array{0, 0, 0, 0, 0, 0}
        for (I -> N : Saved.SurvivedByType):
            if (set Counts[I] = N) {}
        set G.SurvivedByType = Counts
    G

DsSaveProgress(P:player, G:ds_progress):void =
    NewProfile := ds_profile:
        Version := 1
        Rank := G.Rank
        TotalSp := G.TotalSp
        RoundsPlayed := G.RoundsPlayed
        RoundsSurvived := G.RoundsSurvived
        Rescues := G.Rescues
        LastSurvivorWins := G.LastSurvivorWins
        SecretMissions := G.SecretMissions
        LeftBehind := G.LeftBehind
        SurvivedByType := G.SurvivedByType
        Unlocked := G.Unlocked
    if (set DsProfiles[P] = NewProfile) {}

DsSurvivedCount(G:ds_progress, D:ds_disaster)<transacts>:int =
    if (N := G.SurvivedByType[DsDisasterIndex(D)]) then N else 0

DsTypesSurvived(G:ds_progress)<transacts>:int =
    var Count : int = 0
    for (N : G.SurvivedByType, N > 0):
        set Count += 1
    Count

DsMeets(G:ds_progress, R:ds_rank)<transacts>:logic =
    Types := DsTypesSurvived(G)
    if (G.TotalSp >= R.MinSp, G.Rescues >= R.MinRescues, G.LastSurvivorWins >= R.MinLastSurvivor,
        G.SecretMissions >= R.MinSecrets, Types >= R.MinDisasterTypes) then true else false

DsRankIndex(G:ds_progress, Ranks:[]ds_rank)<transacts>:int =
    var Best : int = 0
    var Stop : logic = false
    for (I -> R : Ranks):
        if (not Stop?):
            Ok := DsMeets(G, R)
            if (Ok?) then set Best = I else set Stop = true
    Best

DsRankIndexOf(Name:string, Ranks:[]ds_rank)<transacts>:int =
    var Found : int = -1
    for (I -> R : Ranks, R.Name = Name):
        set Found = I
    Found

DsHasUnlock(G:ds_progress, Id:string)<transacts>:logic =
    var Found : logic = false
    for (U : G.Unlocked, U = Id):
        set Found = true
    Found

DsMilestoneMet(G:ds_progress, U:ds_unlock)<transacts>:logic =
    Value := case (U.Milestone):
        ds_milestone.Rescues => G.Rescues
        ds_milestone.LastSurvivor => G.LastSurvivorWins
        ds_milestone.LeftBehind => G.LeftBehind
        ds_milestone.SecretMissions => G.SecretMissions
        ds_milestone.SurvivedDisaster => DsSurvivedCount(G, U.MilestoneDisaster)
        ds_milestone.None => -1
    if (U.Milestone <> ds_milestone.None, Value >= U.MilestoneValue) then true else false

# Updates rank and unlocks, returns the names of new unlocks
DsRefreshRankAndUnlocks(G:ds_progress, Ranks:[]ds_rank, Unlocks:[]ds_unlock):[]string =
    RankIdx := DsRankIndex(G, Ranks)
    if (R := Ranks[RankIdx]) then set G.Rank = R.Name
    var New : []string = array{}
    for (U : Unlocks):
        Has := DsHasUnlock(G, U.Id)
        if (not Has?):
            Needed := if (U.Rank = "") then 999 else DsRankIndexOf(U.Rank, Ranks)
            ByMilestone := DsMilestoneMet(G, U)
            if (Needed >= 0, Needed <= RankIdx):
                set G.Unlocked += array{U.Id}
                set New += array{U.Name}
            else if (ByMilestone?):
                set G.Unlocked += array{U.Id}
                set New += array{U.Name}
    New

DsMissingForNext(G:ds_progress, Ranks:[]ds_rank)<transacts>:string =
    Idx := DsRankIndex(G, Ranks)
    if (Next := Ranks[Idx + 1]):
        var Parts : []string = array{}
        if (G.TotalSp < Next.MinSp) then set Parts += array{"{DsNumber(Next.MinSp - G.TotalSp)} more SP"}
        if (G.Rescues < Next.MinRescues) then set Parts += array{"{Next.MinRescues - G.Rescues} more rescues"}
        if (G.LastSurvivorWins < Next.MinLastSurvivor) then set Parts += array{"{Next.MinLastSurvivor - G.LastSurvivorWins}x last survivor"}
        if (G.SecretMissions < Next.MinSecrets) then set Parts += array{"{Next.MinSecrets - G.SecretMissions} more secret missions"}
        Types := DsTypesSurvived(G)
        if (Types < Next.MinDisasterTypes) then set Parts += array{"survive {Next.MinDisasterTypes - Types} more kinds of disaster"}
        var Text : string = "Next rank: {Next.Name}"
        for (P : Parts):
            set Text = Text + "  |  " + P
        Text
    else:
        "You reached the highest rank."
