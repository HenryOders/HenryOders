# Disaster Survival (UEFN) - the game manager. Place ONE of these on the island.
# Runs matches of several rounds: a new disaster each round, shared missions, one secret mission per
# player, an event every 30-60 seconds with a finale, first aid for injured players, a story recap
# that remembers earlier rounds, and long-term ranks and unlocks saved per player.

using { /Fortnite.com/Devices }
using { /Fortnite.com/Characters }
using { /Fortnite.com/UI }
using { /Verse.org/Simulation }
using { /Verse.org/Random }
using { /UnrealEngine.com/Temporary/SpatialMath }

ds_active := struct:
    Def : ds_event = ds_event{}
    EndsAt : float = 0.0
    Injured : int = -1

# One player in the match (round values are reset every round)
ds_player := class:
    Player : player
    Hud : ds_hud
    Progress : ds_progress
    var Index : int = 0
    var Callsign : string = ""
    var InMatch : logic = false
    var Left : logic = false
    var MatchSp : int = 0

    var Alive : logic = true
    var Injured : logic = false
    var Sp : int = 0
    var Rescues : int = 0
    var LeftBehind : int = 0
    var Completed : []string = array{}
    var UsedRadios : []int = array{}
    var BunkerSeconds : float = 0.0
    var InBunker : logic = false
    var CarryingKit : logic = false
    var ReachedStationAt : float = -1.0
    var Secret : ds_secret_kind = ds_secret_kind.MostActivations
    var SecretTarget : int = -1
    var SecretText : string = ""
    var SecretDone : logic = false
    var FirstAid : float = 0.0
    var FirstAidBy : int = -1
    var NearSince : [int]float = map{}

    ResetForRound():void =
        set Alive = InMatch
        set Injured = false
        set Sp = 0
        set Rescues = 0
        set LeftBehind = 0
        set Completed = array{}
        set UsedRadios = array{}
        set BunkerSeconds = 0.0
        set InBunker = false
        set CarryingKit = false
        set ReachedStationAt = -1.0
        set SecretTarget = -1
        set SecretText = ""
        set SecretDone = false
        set FirstAid = 0.0
        set FirstAidBy = -1
        set NearSince = map{}

    HasCompleted(Id:string)<transacts>:logic =
        var Found : logic = false
        for (C : Completed, C = Id):
            set Found = true
        Found

# Small handler classes, because Verse has no lambdas
ds_radio_handler := class:
    Manager : ds_game_manager
    RadioIndex : int
    OnInteract(Agent:agent):void = Manager.OnRadio(Agent, RadioIndex)

ds_zone_handler := class:
    Manager : ds_game_manager
    Zone : ds_zone
    OnEnter(Agent:agent):void = Manager.OnZoneEnter(Agent, Zone)
    OnExit(Agent:agent):void = Manager.OnZoneExit(Agent, Zone)

ds_elim_handler := class:
    Manager : ds_game_manager
    PlayerRef : player
    OnEliminated(Result:elimination_result):void = Manager.OnEliminated(PlayerRef)

ds_game_manager := class(creative_device):
    @editable RoundsPerMatch : int = 4
    @editable MinPlayers : int = 1
    @editable SharedMissions : int = 3
    @editable CountdownSeconds : float = 8.0
    @editable RecapSeconds : float = 14.0
    @editable MatchOverSeconds : float = 20.0
    @editable MinEventGap : float = 30.0
    @editable MaxEventGap : float = 60.0
    @editable FirstEventAfter : float = 20.0
    @editable FinaleAt : float = 0.78

    @editable SpawnTeleporters : []teleporter_device = array{}
    @editable SpectatorTeleporters : []teleporter_device = array{}
    @editable RescueStationZones : []mutator_zone_device = array{}
    @editable BunkerZones : []mutator_zone_device = array{}
    @editable RooftopZones : []mutator_zone_device = array{}
    @editable RadioButtons : []button_device = array{}
    @editable KitButtons : []button_device = array{}
    @editable KitProps : []creative_prop = array{}
    # Closed during a power failure
    @editable BunkerBarriers : []barrier_device = array{}

    @editable DisasterKits : []ds_disaster_kit = array{}
    @editable EffectHooks : []ds_effect_hook = array{}
    @editable MovingHazards : []ds_moving_hazard = array{}
    @editable Floods : []ds_flood = array{}

    # First aid: stand this close (cm) to an injured player for this long
    @editable FirstAidRadius : float = 350.0
    @editable FirstAidSeconds : float = 3.0
    # Being this close to an injured player and then running to the rescue station alone counts as leaving them behind
    @editable AbandonRadius : float = 800.0
    @editable AbandonMemory : float = 20.0
    @editable IgnoreSaves : logic = false

    TickSeconds : float = 0.25

    var Disasters : []ds_disaster_def = array{}
    var Events : []ds_event = array{}
    var Ranks : []ds_rank = array{}
    var Unlocks : []ds_unlock = array{}

    var Players : []ds_player = array{}
    var Subscribed : [player]logic = map{}

    var RoundNumber : int = 0
    var Disaster : ds_disaster_def = ds_disaster_def{}
    var Missions : []ds_mission = array{}
    var Played : []ds_disaster = array{}
    var Story : []ds_story = array{}
    var Active : []ds_active = array{}
    var Elapsed : float = 0.0
    var NextEventAt : float = 0.0
    var FinaleStarted : logic = false
    var LastEventId : string = ""
    var RoundRunning : logic = false
    var KitAvailable : logic = true
    var LastSurvivor : int = -1
    var RecapLines : []string = array{}

    # ================================================================ setup

    OnBegin<override>()<suspends>:void =
        set Disasters = DsDisasters()
        set Events = DsEvents()
        set Ranks = DsRanks()
        set Unlocks = DsUnlocks()

        for (Kit : DisasterKits) { Kit.Devices.ForceOff() }
        for (Hook : EffectHooks) { Hook.Devices.ForceOff() }
        for (H : MovingHazards) { H.Capture() }
        for (F : Floods) { F.Capture() }
        for (B : BunkerBarriers) { B.Disable() }

        for (I -> B : RadioButtons):
            H := ds_radio_handler{Manager := Self, RadioIndex := I}
            B.InteractedWithEvent.Subscribe(H.OnInteract)
        for (B : KitButtons) { B.InteractedWithEvent.Subscribe(OnKitPickup) }
        SubscribeZones(RescueStationZones, ds_zone.Station)
        SubscribeZones(BunkerZones, ds_zone.Bunker)
        SubscribeZones(RooftopZones, ds_zone.Rooftop)

        GetPlayspace().PlayerAddedEvent().Subscribe(OnPlayerAdded)
        GetPlayspace().PlayerRemovedEvent().Subscribe(OnPlayerRemoved)
        for (P : GetPlayspace().GetPlayers()) { OnPlayerAdded(P) }

        loop:
            Here := CountPresent()
            if (Here >= MinPlayers):
                RunMatch()
            else:
                for (P : Players) { P.Hud.ShowCenter("DISASTER SURVIVAL", "Waiting for players ({Here}/{MinPlayers})", "") }
                Sleep(1.0)

    SubscribeZones(Zones:[]mutator_zone_device, Zone:ds_zone):void =
        for (Z : Zones):
            H := ds_zone_handler{Manager := Self, Zone := Zone}
            Z.AgentEntersEvent.Subscribe(H.OnEnter)
            Z.AgentExitsEvent.Subscribe(H.OnExit)

    OnPlayerAdded(P:player):void =
        var Known : logic = false
        for (X : Players, X.Player = P, not X.Left?):
            set Known = true
        if (not Known?):
            Hud := ds_hud{PlayerRef := P}
            NewPlayer := ds_player{Player := P, Hud := Hud, Progress := DsLoadProgress(P, IgnoreSaves)}
            set NewPlayer.Index = Players.Length
            set NewPlayer.Callsign = CallsignFor(Players.Length)
            set Players += array{NewPlayer}
            Hud.Show()
            Hud.Banner("Welcome! You join at the next match.")
        if (not Subscribed[P], FC := P.GetFortCharacter[]):
            H := ds_elim_handler{Manager := Self, PlayerRef := P}
            FC.EliminatedEvent().Subscribe(H.OnEliminated)
            set Subscribed = ConcatenateMaps(Subscribed, map{P => true})

    OnPlayerRemoved(P:player):void =
        if (Me := Find[P]):
            if (Me.Alive?) then Eliminate(Me, "left the game")
            set Me.InMatch = false
            set Me.Left = true
            Me.Hud.Hide()
            DsSaveProgress(P, Me.Progress)

    CallsignFor(I:int)<transacts>:string =
        if (Name := DsCallsigns[I]) then Name else "Player {I + 1}"

    Find(P:player)<decides><transacts>:ds_player =
        var Found : ?ds_player = false
        for (X : Players, X.Player = P):
            set Found = option{X}
        Found?

    FindAgent(Agent:agent)<decides><transacts>:ds_player =
        P := player[Agent]
        Find[P]

    At(I:int)<decides><transacts>:ds_player = Players[I]

    NameOf(I:int)<transacts>:string =
        if (P := Players[I]) then P.Callsign else "Someone"

    # ================================================================ match flow

    RunMatch()<suspends>:void =
        # Everyone present takes part; callsigns are handed out again in join order
        var Present : []ds_player = array{}
        for (P : Players, not P.Left?):
            set Present += array{P}
        set Players = Present
        for (I -> P : Players):
            set P.Index = I
            set P.Callsign = CallsignFor(I)
            set P.InMatch = true
            set P.MatchSp = 0
        set Played = array{}
        set Story = array{}
        set RoundNumber = 0

        loop:
            if (RoundNumber >= RoundsPerMatch):
                break
            set RoundNumber += 1
            Countdown()
            RunRound()
            ShowRecap()
            Sleep(RecapSeconds)

        ShowMatchOver()
        Sleep(MatchOverSeconds)

    Countdown()<suspends>:void =
        var Left : float = CountdownSeconds
        loop:
            if (Left <= 0.0):
                break
            for (P : Players):
                Who := if (P.InMatch?) then "You are {P.Callsign}" else "You join at the next match"
                P.Hud.ShowCenter("ROUND {RoundNumber} OF {RoundsPerMatch}", "Next disaster in {DsToInt(Left + 0.99)}", Who)
            Sleep(0.5)
            set Left -= 0.5

    RunRound()<suspends>:void =
        SetupRound()
        loop:
            Sleep(TickSeconds)
            Tick(TickSeconds)
            if (not RoundRunning?):
                break

    SetupRound():void =
        # A disaster not played yet in this match
        var Pool : []ds_disaster_def = array{}
        for (D : Disasters):
            var Seen : logic = false
            for (X : Played, X = D.Kind):
                set Seen = true
            if (not Seen?) then set Pool += array{D}
        if (Pool.Length = 0) then set Pool = Disasters
        if (Pick := Pool[GetRandomInt(0, Pool.Length - 1)]):
            set Disaster = Pick
        set Played += array{Disaster.Kind}

        for (P : Players) { P.ResetForRound() }
        PickMissions()
        AssignSecrets()

        set Active = array{}
        set Elapsed = 0.0
        set NextEventAt = FirstEventAfter
        set FinaleStarted = false
        set LastEventId = ""
        set LastSurvivor = -1
        ResetKit()
        for (B : BunkerBarriers) { B.Disable() }

        # Everyone to the start, nobody frozen
        var Slot : int = 0
        for (P : Players):
            if (FC := P.Player.GetFortCharacter[]) then FC.ReleaseFromStasis()
            if (P.InMatch?, SpawnTeleporters.Length > 0, T := SpawnTeleporters[DsMod(Slot, SpawnTeleporters.Length)]):
                T.Teleport(P.Player)
                set Slot += 1

        for (Kit : DisasterKits, Kit.Disaster = Disaster.Kind) { Kit.Devices.TurnOn() }
        for (H : MovingHazards):
            On := H.ActiveFor(Disaster.Kind)
            if (On?) then H.Start()
        for (F : Floods):
            On := F.ActiveFor(Disaster.Kind)
            if (On?) then F.Start()

        set RoundRunning = true
        Announce("{Disaster.Name}! {Disaster.Intro}")

    PickMissions():void =
        set Missions = array{}
        var Rest : []ds_mission = array{}
        # Last survivor and rescue need company
        Solo := if (CountInMatch() < 2) then true else false
        for (M : Disaster.Missions):
            NeedsCompany := if (M.Kind = ds_mission_kind.LastSurvivor or M.Kind = ds_mission_kind.Rescue) then true else false
            if (M.Kind = ds_mission_kind.Survive):
                set Missions += array{M}
            else if ((not Solo?) or (not NeedsCompany?)):
                set Rest += array{M}
        Shuffled := Shuffle(Rest)
        for (M : Shuffled, Missions.Length < SharedMissions):
            set Missions += array{M}

    AssignSecrets():void =
        if (CountInMatch() >= 2):
            for (P : Players, P.InMatch?):
                var Others : []int = array{}
                for (O : Players, O.InMatch?, O.Index <> P.Index):
                    set Others += array{O.Index}
                if (TargetIndex := Others[GetRandomInt(0, Others.Length - 1)]):
                    TargetName := NameOf(TargetIndex)
                    set P.SecretTarget = TargetIndex
                    Roll := GetRandomInt(0, 3)
                    if (Roll = 0):
                        set P.Secret = ds_secret_kind.ReachBefore
                        set P.SecretText = "Reach the rescue station before {TargetName}."
                    else if (Roll = 1):
                        set P.Secret = ds_secret_kind.RescueTarget
                        set P.SecretText = "If {TargetName} gets injured, you must be the one who helps."
                    else if (Roll = 2):
                        set P.Secret = ds_secret_kind.KeepTargetFromStation
                        set P.SecretText = "Keep {TargetName} away from the rescue station."
                    else:
                        set P.Secret = ds_secret_kind.MostActivations
                        set P.SecretText = "Activate more radios than anyone else."

    CountPresent()<transacts>:int =
        var N : int = 0
        for (P : Players, not P.Left?):
            set N += 1
        N

    CountInMatch()<transacts>:int =
        var N : int = 0
        for (P : Players, P.InMatch?):
            set N += 1
        N

    CountAlive()<transacts>:int =
        var N : int = 0
        for (P : Players, P.Alive?):
            set N += 1
        N

    # ================================================================ the round tick

    Tick(Dt:float):void =
        if (RoundRunning?):
            set Elapsed += Dt

            # Events that ran out
            var Still : []ds_active = array{}
            for (A : Active):
                if (A.EndsAt <= Elapsed) then EndEvent(A) else set Still += array{A}
            set Active = Still

            # Finale, then the next regular event
            if (not FinaleStarted?, Elapsed >= Disaster.Duration * FinaleAt):
                set FinaleStarted = true
                if (E := PickEvent[true]) then StartEvent(E)
            else if (Elapsed >= NextEventAt, Elapsed < Disaster.Duration * FinaleAt - 10.0):
                if (E := PickEvent[false]) then StartEvent(E)
                set NextEventAt = Elapsed + GetRandomFloat(MinEventGap, MaxEventGap)

            UpdateEffects()
            FirstAidAndProximity(Dt)
            BunkerTime(Dt)
            HazardDamage(Dt)
            Spectators()
            RefreshHuds()

            if (Elapsed >= Disaster.Duration or CountAlive() = 0):
                EndRound()

    Phase()<transacts>:int =
        Share := Elapsed / Disaster.Duration
        if (Share < 0.34) then 0 else if (Share < 0.75) then 1 else 2

    PickEvent(Finale:logic)<decides><transacts>:ds_event =
        Ph := Phase()
        Healthy := CountHealthy()
        var Candidates : []ds_event = array{}
        var Total : int = 0
        for (E : Events):
            Allowed := DsEventAllowed(E, Disaster.Kind)
            InPhase := if (Ph = 0) then E.InOpening else if (Ph = 1) then E.InMidgame else E.InFinale
            var Running : logic = false
            for (A : Active, A.Def.Id = E.Id):
                set Running = true
            if (E.IsFinale = Finale, Allowed?, (Finale? or InPhase?), E.Id <> LastEventId, not Running?,
                (not E.InjurePlayer? or Healthy >= 2)):
                set Candidates += array{E}
                set Total += E.Weight
        Total > 0
        var Roll : int = GetRandomInt(0, Total - 1)
        var Chosen : ?ds_event = false
        for (E : Candidates, not Chosen?):
            set Roll -= E.Weight
            if (Roll < 0) then set Chosen = option{E}
        Chosen?

    CountHealthy()<transacts>:int =
        var N : int = 0
        for (P : Players, P.Alive?, not P.Injured?):
            set N += 1
        N

    StartEvent(E:ds_event):void =
        set LastEventId = E.Id
        var Injured : int = -1
        var Text : string = "{E.Title}! {E.Description}"
        if (E.InjurePlayer?):
            if (Victim := PickVictim[]):
                set Injured = Victim.Index
                Injure(Victim)
                set Text = "{E.Title}! {Victim.Callsign} is injured. Stand next to them for {DsToInt(FirstAidSeconds)} seconds to help."
        set Active += array{ds_active{Def := E, EndsAt := Elapsed + E.Duration, Injured := Injured}}
        if (E.HazardMoves?):
            Center := PlayerCenter()
            for (H : MovingHazards) { H.Retarget(Center) }
        Announce(Text)

    EndEvent(A:ds_active):void =
        if (A.Def.WaterRising?):
            for (F : Floods) { F.WaveEnded() }
        if (A.Injured >= 0, Victim := At[A.Injured], Victim.Alive?, Victim.Injured?):
            Eliminate(Victim, "was not helped in time")
            if (FC := Victim.Player.GetFortCharacter[]):
                FC.ReleaseFromStasis()
                FC.Damage(500.0)

    # Rescue events prefer players that someone's secret mission is about: that is where the drama is
    PickVictim()<decides><transacts>:ds_player =
        var Healthy : []ds_player = array{}
        var Targeted : []ds_player = array{}
        for (P : Players, P.Alive?, not P.Injured?):
            set Healthy += array{P}
            var IsTarget : logic = false
            for (O : Players, O.SecretTarget = P.Index, O.Secret = ds_secret_kind.RescueTarget or O.Secret = ds_secret_kind.KeepTargetFromStation):
                set IsTarget = true
            if (IsTarget?) then set Targeted += array{P}
        Pool := if (Targeted.Length > 0, GetRandomFloat(0.0, 1.0) < 0.6) then Targeted else Healthy
        Pool[GetRandomInt(0, Pool.Length - 1)]

    IsActive(Effect:ds_effect)<transacts>:logic =
        var Found : logic = false
        for (A : Active):
            Has := DsEventHas(A.Def, Effect)
            if (Has?) then set Found = true
        Found

    UpdateEffects():void =
        PowerOut := IsActive(ds_effect.PowerFailure)
        for (B : BunkerBarriers):
            if (PowerOut?) then B.Enable() else B.Disable()
        for (Hook : EffectHooks):
            Applies := Hook.AppliesTo(Disaster.Kind)
            On := IsActive(Hook.Effect)
            if (Applies?, On?) then Hook.Devices.TurnOn() else Hook.Devices.TurnOff()
        Boost := IsActive(ds_effect.HazardMoves)
        for (H : MovingHazards) { set H.Boost = Boost }

    # ================================================================ players in the world

    PosOf(P:ds_player)<decides><transacts>:vector3 =
        FC := P.Player.GetFortCharacter[]
        FC.GetTransform().Translation

    PlayerCenter()<transacts>:?vector3 =
        var Sum : vector3 = vector3{X := 0.0, Y := 0.0, Z := 0.0}
        var N : int = 0
        for (P : Players, P.Alive?, Pos := PosOf[P]):
            set Sum = Sum + Pos
            set N += 1
        if (N > 0) then option{Sum * (1.0 / (N * 1.0))} else false

    FirstAidAndProximity(Dt:float):void =
        for (Hurt : Players, Hurt.Alive?, Hurt.Injured?, HurtPos := PosOf[Hurt]):
            var Closest : int = -1
            var Best : float = FirstAidRadius
            for (Helper : Players, Helper.Alive?, not Helper.Injured?, Helper.Index <> Hurt.Index, HelperPos := PosOf[Helper]):
                D := Distance(HurtPos, HelperPos)
                if (D <= AbandonRadius):
                    set Helper.NearSince = ConcatenateMaps(Helper.NearSince, map{Hurt.Index => Elapsed})
                if (D <= Best):
                    set Best = D
                    set Closest = Helper.Index
            if (Closest < 0):
                set Hurt.FirstAid = 0.0
                set Hurt.FirstAidBy = -1
            else:
                if (Hurt.FirstAidBy = Closest):
                    set Hurt.FirstAid += Dt
                else:
                    set Hurt.FirstAidBy = Closest
                    set Hurt.FirstAid = Dt
                if (Hurt.FirstAid >= FirstAidSeconds, Helper := At[Closest]):
                    Rescue(Helper, Hurt)

    BunkerTime(Dt:float):void =
        for (P : Players, P.Alive?, not P.Injured?, P.InBunker?):
            set P.BunkerSeconds += Dt
            for (M : Missions, M.Kind = ds_mission_kind.HoldBunker, P.BunkerSeconds >= M.Target * 1.0):
                Complete(P, M)

    HazardDamage(Dt:float):void =
        for (P : Players, P.Alive?, Pos := PosOf[P], FC := P.Player.GetFortCharacter[]):
            for (H : MovingHazards):
                Hit := H.Hits(Pos)
                if (Hit?) then FC.Damage(H.DamagePerSecond * Dt)
            for (F : Floods):
                Hurt := F.Hurts(Pos)
                if (Hurt?) then FC.Damage(F.DamagePerSecond * Dt)
        Rising := IsActive(ds_effect.WaterRising)
        for (F : Floods) { F.Update(Dt, Rising) }

    # Players who are out are sent to the spectator area once they respawn
    Spectators():void =
        if (T := SpectatorTeleporters[0], DsMod(DsToInt(Elapsed * 4.0), 8) = 0):
            SpectatorPos := T.GetTransform().Translation
            for (P : Players, not P.Alive?, Pos := PosOf[P], Distance(Pos, SpectatorPos) > 1500.0):
                T.Teleport(P.Player)

    # ================================================================ reports from devices

    OnZoneEnter(Agent:agent, Zone:ds_zone):void =
        if (RoundRunning?, P := FindAgent[Agent], P.Alive?, not P.Injured?):
            if (Zone = ds_zone.Station):
                if (P.CarryingKit?):
                    set P.CarryingKit = false
                    for (M : Missions, M.Kind = ds_mission_kind.DeliverKit) { Complete(P, M) }
                    Announce("{P.Callsign} brought the emergency kit to the rescue station.")
                if (P.ReachedStationAt < 0.0) then set P.ReachedStationAt = Elapsed
                CheckLeftBehind(P)
            else if (Zone = ds_zone.Bunker):
                set P.InBunker = true
            else:
                for (M : Missions, M.Kind = ds_mission_kind.ReachRooftop) { Complete(P, M) }

    OnZoneExit(Agent:agent, Zone:ds_zone):void =
        if (P := FindAgent[Agent], Zone = ds_zone.Bunker):
            set P.InBunker = false

    OnRadio(Agent:agent, RadioIndex:int):void =
        if (RoundRunning?, P := FindAgent[Agent], P.Alive?, not P.Injured?):
            var Used : logic = false
            for (R : P.UsedRadios, R = RadioIndex):
                set Used = true
            if (Used?):
                P.Hud.Banner("You already used this radio.")
            else:
                set P.UsedRadios += array{RadioIndex}
                P.Hud.Banner("Radio activated ({P.UsedRadios.Length}).")
                for (M : Missions, M.Kind = ds_mission_kind.ActivateRadios, P.UsedRadios.Length >= M.Target) { Complete(P, M) }

    OnKitPickup(Agent:agent):void =
        if (RoundRunning?, KitAvailable?, P := FindAgent[Agent], P.Alive?, not P.Injured?):
            set KitAvailable = false
            set P.CarryingKit = true
            for (K : KitProps) { K.Hide() }
            for (B : KitButtons) { B.Disable() }
            P.Hud.Banner("You carry the emergency kit. Bring it to the rescue station.")

    ResetKit():void =
        set KitAvailable = true
        for (K : KitProps) { K.Show() }
        for (B : KitButtons) { B.Enable() }

    DropKit(P:ds_player):void =
        if (P.CarryingKit?):
            set P.CarryingKit = false
            ResetKit()
            Announce("The emergency kit is back at its spot.")

    OnEliminated(PlayerRef:player):void =
        if (RoundRunning?, P := Find[PlayerRef], P.Alive?):
            Eliminate(P, Disaster.Cause)

    # ================================================================ rules

    Injure(P:ds_player):void =
        set P.Injured = true
        DropKit(P)
        if (FC := P.Player.GetFortCharacter[]):
            FC.PutInStasis(stasis_args{AllowTurning := true, AllowFalling := true, AllowEmotes := true})
        Log(ds_story_kind.Injured, P.Index, -1, "{P.Callsign} got injured.")

    Rescue(Helper:ds_player, Hurt:ds_player):void =
        set Hurt.Injured = false
        set Hurt.FirstAid = 0.0
        set Hurt.FirstAidBy = -1
        if (FC := Hurt.Player.GetFortCharacter[]) then FC.ReleaseFromStasis()
        var Still : []ds_active = array{}
        for (A : Active):
            if (A.Injured = Hurt.Index) then set Still += array{ds_active{Def := A.Def, EndsAt := A.EndsAt, Injured := -1}}
            else set Still += array{A}
        set Active = Still

        set Helper.Rescues += 1
        Log(ds_story_kind.Rescued, Helper.Index, Hurt.Index, "{Helper.Callsign} rescued {Hurt.Callsign}.")
        Announce("{Helper.Callsign} rescued {Hurt.Callsign}!")
        var MissionPaid : logic = false
        for (M : Missions, M.Kind = ds_mission_kind.Rescue):
            Done := Helper.HasCompleted(M.Id)
            if (not Done?):
                Complete(Helper, M)
                set MissionPaid = true
        if (not MissionPaid?) then set Helper.Sp += DsRepeatRescueBonus
        if (Helper.Secret = ds_secret_kind.RescueTarget, Helper.SecretTarget = Hurt.Index):
            set Helper.SecretDone = true

    CheckLeftBehind(P:ds_player):void =
        for (Hurt : Players, Hurt.Alive?, Hurt.Injured?, Hurt.Index <> P.Index, Since := P.NearSince[Hurt.Index], Elapsed - Since <= AbandonMemory):
            var Already : logic = false
            for (S : Story, S.Round = RoundNumber, S.Kind = ds_story_kind.LeftBehind, S.Actor = P.Index, S.Other = Hurt.Index):
                set Already = true
            if (not Already?):
                set P.LeftBehind += 1
                Log(ds_story_kind.LeftBehind, P.Index, Hurt.Index, "{P.Callsign} left {Hurt.Callsign} behind.")

    Eliminate(P:ds_player, Cause:string):void =
        if (P.Alive?):
            set P.Alive = false
            set P.Injured = false
            set P.InBunker = false
            DropKit(P)
            Log(ds_story_kind.Eliminated, P.Index, -1, "{P.Callsign} {Cause}.")
            Announce("{P.Callsign} {Cause}.")

    Complete(P:ds_player, M:ds_mission):void =
        Done := P.HasCompleted(M.Id)
        if (not Done?):
            set P.Completed += array{M.Id}
            set P.Sp += M.Reward
            Log(ds_story_kind.MissionDone, P.Index, -1, "{P.Callsign}: {M.Title} (+{M.Reward} SP)")
            if (M.Kind <> ds_mission_kind.Survive, M.Kind <> ds_mission_kind.LastSurvivor):
                P.Hud.Banner("Mission complete: {M.Title}  +{M.Reward} SP")

    Log(Kind:ds_story_kind, Actor:int, Other:int, Text:string):void =
        set Story += array{ds_story{Round := RoundNumber, Kind := Kind, Actor := Actor, Other := Other, Text := Text}}

    Announce(Text:string):void =
        for (P : Players) { P.Hud.Banner(Text) }

    # ================================================================ end of round

    EndRound():void =
        set RoundRunning = false
        for (A : Active) { EndEvent(A) }
        set Active = array{}
        UpdateEffects()
        for (Kit : DisasterKits) { Kit.Devices.TurnOff() }
        for (H : MovingHazards) { H.Stop() }
        for (F : Floods) { F.Stop() }
        for (B : BunkerBarriers) { B.Disable() }

        AliveCount := CountAlive()
        for (P : Players, P.Alive?):
            for (M : Missions, M.Kind = ds_mission_kind.Survive) { Complete(P, M) }
            Log(ds_story_kind.Survived, P.Index, -1, "{P.Callsign} survived.")
        if (CountInMatch() >= 2, AliveCount = 1):
            for (P : Players, P.Alive?):
                set LastSurvivor = P.Index
                for (M : Missions, M.Kind = ds_mission_kind.LastSurvivor) { Complete(P, M) }
                Log(ds_story_kind.LastSurvivor, P.Index, -1, "{P.Callsign} was the last survivor.")

        ResolveSecrets()
        for (P : Players, P.InMatch?):
            set P.MatchSp += P.Sp
            if (FC := P.Player.GetFortCharacter[]) then FC.ReleaseFromStasis()

    ResolveSecrets():void =
        for (P : Players, P.InMatch?, P.SecretTarget >= 0, Target := At[P.SecretTarget]):
            if (P.Secret = ds_secret_kind.ReachBefore):
                Mine := P.ReachedStationAt
                Theirs := Target.ReachedStationAt
                if (Mine >= 0.0, Theirs < 0.0 or Mine < Theirs) then set P.SecretDone = true
            else if (P.Secret = ds_secret_kind.KeepTargetFromStation):
                if (Target.ReachedStationAt < 0.0) then set P.SecretDone = true
            else if (P.Secret = ds_secret_kind.MostActivations):
                Mine := P.UsedRadios.Length
                var Beaten : logic = true
                for (O : Players, O.Index <> P.Index, O.UsedRadios.Length >= Mine):
                    set Beaten = false
                if (Mine > 0, Beaten?) then set P.SecretDone = true
            if (P.SecretDone?):
                set P.Sp += DsSecretReward
                Log(ds_story_kind.SecretDone, P.Index, P.SecretTarget, "{P.Callsign} had a secret mission: \"{P.SecretText}\" - and did it.")
            else:
                Log(ds_story_kind.SecretFailed, P.Index, P.SecretTarget, "{P.Callsign} had a secret mission: \"{P.SecretText}\" - and failed.")

    # ================================================================ HUD texts

    RefreshHuds():void =
        Top := "{Disaster.Name}   {DsClock(Disaster.Duration - Elapsed)}   |   Round {RoundNumber}/{RoundsPerMatch}"
        PhaseName := if (Phase() = 0) then "IT BEGINS" else if (Phase() = 1) then "GETTING WORSE" else "FINAL STAGE"
        var Sub : string = PhaseName
        for (A : Active):
            set Sub = Sub + "   |   {A.Def.Title} {DsToInt(A.EndsAt - Elapsed + 0.99)}s"
        for (P : Players):
            P.Hud.ShowPlaying(Top, Sub, MissionLines(P), SecretLine(P), StatusLine(P))

    MissionLines(P:ds_player)<transacts>:string =
        var Text : string = ""
        for (M : Missions):
            Done := P.HasCompleted(M.Id)
            var Progress : string = ""
            if (not Done?, M.Kind = ds_mission_kind.ActivateRadios):
                set Progress = "  ({Min(P.UsedRadios.Length, M.Target)}/{M.Target})"
            if (not Done?, M.Kind = ds_mission_kind.HoldBunker):
                set Progress = "  ({Min(DsToInt(P.BunkerSeconds), M.Target)}/{M.Target}s)"
            Line := if (Done?) then "DONE   {M.Title}" else "+{M.Reward}   {M.Title}{Progress}"
            set Text = if (Text = "") then Line else Text + "\n" + Line
        Text + "\n\n{P.Sp} SP this round"

    SecretLine(P:ds_player)<transacts>:string =
        if (P.SecretText = "") then "-" else "{P.SecretText}   +{DsSecretReward}"

    StatusLine(P:ds_player)<transacts>:string =
        if (not P.InMatch?):
            "You join at the next match."
        else if (not P.Alive?):
            "You are out. Watch the others until the round ends."
        else if (P.Injured?, P.FirstAidBy >= 0):
            "{NameOf(P.FirstAidBy)} is helping you... {DsToInt(P.FirstAid)}/{DsToInt(FirstAidSeconds)}s"
        else if (P.Injured?):
            "You are injured! Someone has to stand next to you for {DsToInt(FirstAidSeconds)} seconds."
        else if (P.CarryingKit?):
            "You are {P.Callsign}  |  Bring the emergency kit to the rescue station."
        else:
            "You are {P.Callsign}"

    # ================================================================ recap and story

    ShowRecap():void =
        Lines := RoundRecap(RoundNumber)
        for (P : Players):
            var Body : string = ""
            for (L : Lines):
                set Body = Body + L + "\n"
            if (P.InMatch?):
                G := P.Progress
                set G.RoundsPlayed += 1
                set G.TotalSp += P.Sp
                set G.Rescues += P.Rescues
                set G.LeftBehind += P.LeftBehind
                if (P.Alive?):
                    set G.RoundsSurvived += 1
                    Idx := DsDisasterIndex(Disaster.Kind)
                    if (Old := G.SurvivedByType[Idx], set G.SurvivedByType[Idx] = Old + 1) {}
                if (LastSurvivor = P.Index) then set G.LastSurvivorWins += 1
                if (P.SecretDone?) then set G.SecretMissions += 1
                OldRank := G.Rank
                NewUnlocks := DsRefreshRankAndUnlocks(G, Ranks, Unlocks)
                DsSaveProgress(P.Player, G)
                set Body = Body + "\n+{DsNumber(P.Sp)} SP   |   Rank: {G.Rank}"
                if (OldRank <> G.Rank) then set Body = Body + "   RANK UP!"
                for (U : NewUnlocks):
                    set Body = Body + "\nUnlocked: {U}"
                set Body = Body + "\n{DsMissingForNext(G, Ranks)}"
            P.Hud.ShowPanel("ROUND OVER", "Round {RoundNumber}: {Disaster.Name}", Body)

    RoundRecap(R:int):[]string =
        var Lines : []string = array{}
        for (S : Story, S.Round = R):
            if (S.Kind = ds_story_kind.Rescued or S.Kind = ds_story_kind.LeftBehind):
                set Lines += array{WithHistory(S)}
            else if (S.Kind = ds_story_kind.Eliminated or S.Kind = ds_story_kind.LastSurvivor or S.Kind = ds_story_kind.SecretDone):
                set Lines += array{S.Text}
        Alive := CountAlive()
        InMatch := CountInMatch()
        Summary := if (Alive = 0) then "Nobody survived." else if (Alive = InMatch) then "Everyone made it out." else "{Alive} of {InMatch} survived."
        set Lines += array{Summary}
        var Best : int = -1
        var BestSp : int = -1
        for (P : Players, P.InMatch?, P.Sp > BestSp):
            set Best = P.Index
            set BestSp = P.Sp
        if (Best >= 0) then set Lines += array{"Most points: {NameOf(Best)} with {DsNumber(BestSp)} SP."}
        Lines

    # Adds what happened between the same two players in earlier rounds
    WithHistory(S:ds_story)<transacts>:string =
        A := NameOf(S.Actor)
        B := NameOf(S.Other)
        var SavedBy : int = 0
        var Payback : int = 0
        var Betrayed : int = 0
        var Favor : int = 0
        var Again : int = 0
        for (E : Story, E.Round < S.Round):
            if (E.Kind = ds_story_kind.Rescued, E.Actor = S.Other, E.Other = S.Actor):
                set SavedBy = E.Round
                set Favor = E.Round
            if (E.Kind = ds_story_kind.LeftBehind, E.Actor = S.Other, E.Other = S.Actor):
                set Payback = E.Round
                set Betrayed = E.Round
            if (E.Kind = ds_story_kind.Rescued, E.Actor = S.Actor, E.Other = S.Other):
                set Again = E.Round
        if (S.Kind = ds_story_kind.LeftBehind, SavedBy > 0):
            "{A} leaves {B} behind - even though {B} saved {A} in round {SavedBy}."
        else if (S.Kind = ds_story_kind.LeftBehind, Payback > 0):
            "{A} leaves {B} behind. Payback for round {Payback}."
        else if (S.Kind = ds_story_kind.LeftBehind):
            "{A} leaves {B} behind."
        else if (Betrayed > 0):
            "{A} rescues {B} anyway - although {B} left {A} behind in round {Betrayed}."
        else if (Favor > 0):
            "{A} rescues {B} and returns the favor from round {Favor}."
        else if (Again > 0):
            "{A} rescues {B} again, just like in round {Again}."
        else:
            "{A} rescues {B}."

    Headline(R:int)<transacts>:string =
        var Line : string = ""
        for (S : Story, S.Round = R, Line = "", S.Kind = ds_story_kind.LeftBehind):
            set Line = WithHistory(S)
        for (S : Story, S.Round = R, Line = "", S.Kind = ds_story_kind.Rescued):
            set Line = WithHistory(S)
        for (S : Story, S.Round = R, Line = "", S.Kind = ds_story_kind.SecretDone):
            set Line = "{NameOf(S.Actor)} pulled off a secret mission."
        for (S : Story, S.Round = R, Line = "", S.Kind = ds_story_kind.LastSurvivor):
            set Line = "{NameOf(S.Actor)} was the last one standing."
        if (Line = "") then "a hard round for everyone." else Line

    ShowMatchOver():void =
        var Body : string = ""
        for (I -> D : Played):
            Name := if (Def := Disasters[DsDisasterIndex(D)]) then Def.Name else "Disaster"
            set Body = Body + "Round {I + 1}: {Name} - {Headline(I + 1)}\n"
        set Body = Body + "\nLEADERBOARD\n"
        # Simple selection: highest score first
        var Listed : []int = array{}
        var Place : int = 1
        loop:
            var Best : int = -1
            var BestSp : int = -1
            for (P : Players, P.InMatch?, P.MatchSp > BestSp):
                var Taken : logic = false
                for (L : Listed, L = P.Index):
                    set Taken = true
                if (not Taken?):
                    set Best = P.Index
                    set BestSp = P.MatchSp
            if (Best < 0):
                break
            set Listed += array{Best}
            set Body = Body + "{Place}.  {NameOf(Best)}   {DsNumber(BestSp)} SP\n"
            set Place += 1
        for (P : Players):
            P.Hud.ShowPanel("MATCH OVER", "The story of this match", Body)
