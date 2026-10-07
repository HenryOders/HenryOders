# Disaster Survival (UEFN) - links to Fortnite devices: what turns on during which disaster or event,
# moving hazards (tornado, fire front) and rising water / lava.

using { /Fortnite.com/Devices }
using { /Verse.org/Simulation }
using { /Verse.org/Random }
using { /UnrealEngine.com/Temporary/SpatialMath }

# Devices that switch on together. Used for whole disasters and for single events.
ds_device_set := class<concrete>:
    @editable DamageVolumes : []damage_volume_device = array{}
    @editable Barriers : []barrier_device = array{}
    @editable Vfx : []vfx_spawner_device = array{}
    @editable PropMovers : []prop_mover_device = array{}
    @editable Sounds : []audio_player_device = array{}
    @editable ItemSpawners : []item_spawner_device = array{}
    @editable ShowProps : []creative_prop = array{}

    var IsOn : logic = false

    TurnOn():void =
        if (not IsOn?):
            set IsOn = true
            for (D : DamageVolumes) { D.Enable() }
            for (B : Barriers) { B.Enable() }
            for (V : Vfx) { V.Enable() }
            for (M : PropMovers) { M.Begin() }
            for (S : Sounds) { S.Play() }
            for (I : ItemSpawners) { I.SpawnItem() }
            for (P : ShowProps) { P.Show() }

    TurnOff():void =
        if (IsOn?):
            set IsOn = false
            for (D : DamageVolumes) { D.Disable() }
            for (B : Barriers) { B.Disable() }
            for (V : Vfx) { V.Disable() }
            for (M : PropMovers) { M.Reverse() }
            for (S : Sounds) { S.Stop() }
            for (P : ShowProps) { P.Hide() }

    # Used once at game start so everything begins switched off
    ForceOff():void =
        set IsOn = true
        TurnOff()

# Active for the whole round of one disaster (e.g. tornado sound, wildfire smoke, lava glow)
ds_disaster_kit := class<concrete>:
    @editable Disaster : ds_disaster = ds_disaster.Tornado
    @editable Devices : ds_device_set = ds_device_set{}

# Active while an event with this effect runs (e.g. GroundShaking -> collapse damage volumes)
ds_effect_hook := class<concrete>:
    @editable Effect : ds_effect = ds_effect.GroundShaking
    @editable OnlyDuring : []ds_disaster = array{}
    @editable Devices : ds_device_set = ds_device_set{}

    AppliesTo(D:ds_disaster)<transacts>:logic =
        var Found : logic = false
        if (OnlyDuring.Length = 0):
            set Found = true
        for (X : OnlyDuring, X = D):
            set Found = true
        Found

# A prop that wanders around and hurts players close to it: tornado, fire front, lava bomb ...
# On a "HazardMoves" event it heads for where most players are.
ds_moving_hazard := class<concrete>:
    @editable Prop : creative_prop = creative_prop{}
    @editable Disasters : []ds_disaster = array{ds_disaster.Tornado}
    @editable Radius : float = 700.0
    @editable DamagePerSecond : float = 60.0
    @editable Speed : float = 450.0
    @editable EventSpeedMultiplier : float = 2.0
    @editable AreaRadius : float = 6000.0
    @editable ChasePlayersChance : float = 0.6

    var Home : vector3 = vector3{X := 0.0, Y := 0.0, Z := 0.0}
    var Target : vector3 = vector3{X := 0.0, Y := 0.0, Z := 0.0}
    var Running : logic = false
    var Boost : logic = false

    ActiveFor(D:ds_disaster)<transacts>:logic =
        var Found : logic = false
        for (X : Disasters, X = D):
            set Found = true
        Found

    Capture():void =
        set Home = Prop.GetTransform().Translation
        set Target = Home
        Prop.Hide()

    Start():void =
        if (Prop.TeleportTo[Home, Prop.GetTransform().Rotation]) {}
        Prop.Show()
        set Running = true
        PickRandomTarget()
        spawn{ MoveLoop() }

    Stop():void =
        set Running = false
        Prop.Hide()

    PickRandomTarget():void =
        Angle := GetRandomFloat(0.0, 6.2831)
        Dist := GetRandomFloat(0.0, AreaRadius)
        set Target = vector3{X := Home.X + Cos(Angle) * Dist, Y := Home.Y + Sin(Angle) * Dist, Z := Home.Z}

    Retarget(PlayerCenter:?vector3):void =
        if (C := PlayerCenter?, GetRandomFloat(0.0, 1.0) < ChasePlayersChance):
            set Target = vector3{X := C.X, Y := C.Y, Z := Home.Z}
        else:
            PickRandomTarget()

    MoveLoop()<suspends>:void =
        loop:
            if (not Running?):
                break
            T := Prop.GetTransform()
            Pos := T.Translation
            DX := Target.X - Pos.X
            DY := Target.Y - Pos.Y
            Len := Sqrt(DX * DX + DY * DY)
            Step := Speed * (if (Boost?) then EventSpeedMultiplier else 1.0)
            if (Len < 100.0):
                PickRandomTarget()
                Sleep(0.2)
            else:
                F := Min(1.0, Step / Len)
                Next := vector3{X := Pos.X + DX * F, Y := Pos.Y + DY * F, Z := Pos.Z}
                Prop.MoveTo(Next, T.Rotation, 1.0)

    # Horizontal distance check, so tall funnels hit players on the ground and on roofs
    Hits(At:vector3)<transacts>:logic =
        Pos := Prop.GetTransform().Translation
        DX := At.X - Pos.X
        DY := At.Y - Pos.Y
        if (Running?, DX * DX + DY * DY <= Radius * Radius) then true else false

# Water or lava: a big flat prop that rises during "WaterRising" events and partly drains after.
ds_flood := class<concrete>:
    @editable Surface : creative_prop = creative_prop{}
    @editable Disasters : []ds_disaster = array{ds_disaster.Flood, ds_disaster.Tornado, ds_disaster.Earthquake}
    @editable FloodRise : float = 350.0
    @editable AfterWaveRise : float = 40.0
    @editable RiseSpeed : float = 35.0
    @editable DrainSpeed : float = 15.0
    @editable ConstantRisePerMinute : float = 0.0
    # Damage when a player's position is this far below the surface
    @editable DepthToHurt : float = 120.0
    @editable DamagePerSecond : float = 25.0

    var BaseZ : float = 0.0
    var Rest : float = 0.0
    var Offset : float = 0.0
    var Running : logic = false

    ActiveFor(D:ds_disaster)<transacts>:logic =
        var Found : logic = false
        for (X : Disasters, X = D):
            set Found = true
        Found

    Capture():void =
        set BaseZ = Surface.GetTransform().Translation.Z
        Surface.Hide()

    Start():void =
        set Rest = 0.0
        set Offset = 0.0
        set Running = true
        Place()
        Surface.Show()

    Stop():void =
        set Running = false
        set Offset = 0.0
        Place()
        Surface.Hide()

    WaveEnded():void =
        set Rest = Min(FloodRise, Rest + AfterWaveRise)

    Update(Dt:float, Rising:logic):void =
        if (Running?):
            set Rest = Min(FloodRise, Rest + ConstantRisePerMinute / 60.0 * Dt)
            Goal := if (Rising?) then FloodRise else Rest
            if (Offset < Goal):
                set Offset = Min(Goal, Offset + RiseSpeed * Dt)
            else:
                set Offset = Max(Goal, Offset - DrainSpeed * Dt)
            T := Surface.GetTransform()
            spawn{ Glide(vector3{X := T.Translation.X, Y := T.Translation.Y, Z := BaseZ + Offset}, T.Rotation, Dt) }

    Place():void =
        T := Surface.GetTransform()
        if (Surface.TeleportTo[vector3{X := T.Translation.X, Y := T.Translation.Y, Z := BaseZ + Offset}, T.Rotation]) {}

    Glide(To:vector3, Rot:rotation, Time:float)<suspends>:void =
        Surface.MoveTo(To, Rot, Time)

    Hurts(At:vector3)<transacts>:logic =
        if (Running?, At.Z < BaseZ + Offset - DepthToHurt) then true else false
