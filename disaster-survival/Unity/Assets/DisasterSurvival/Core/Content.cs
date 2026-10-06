// Disaster Survival - content definitions and the default content library.
// Pure C#, no UnityEngine dependency, so the rules can be tested outside Unity
// and ported to other engines (for example Verse in UEFN).
using System;
using System.Collections.Generic;

namespace DisasterSurvival.Core
{
    public enum DisasterType { Tornado, Flood, Earthquake, Wildfire, Blizzard, Volcano }

    public enum MissionKind
    {
        Survive,          // be alive when the timer runs out
        ActivateObjects,  // activate N objects of a group (e.g. emergency radios)
        RescuePlayer,     // carry an injured player to the rescue station
        DeliverItem,      // bring an item (e.g. the emergency kit) to a drop zone
        HoldZone,         // stay N seconds inside a zone (e.g. the bunker)
        ReachZone,        // reach a zone at least once (e.g. the rooftop)
        LastSurvivor,     // be the only one alive at the end
    }

    public enum SecretKind
    {
        ReachBefore,             // reach the rescue station before your target does
        RescueTarget,            // rescue one specific player
        KeepTargetFromStation,   // your target must not reach the rescue station
        MostActivations,         // activate more objects than anyone else
    }

    public enum ArcPhase { Opening, Midgame, Finale }

    [Flags]
    public enum ArcMask { None = 0, Opening = 1, Midgame = 2, Finale = 4, Any = 7 }

    [Flags]
    public enum EventEffect
    {
        None = 0,
        BunkerDoorsDisabled = 1,   // power failure: bunker doors stop working
        WaterRising = 2,           // flood wave: low areas become deadly
        PlayerInjured = 4,         // rescue call: one player is injured and needs help
        HazardMoves = 8,           // the disaster changes direction / spreads
        SupplyDrop = 16,           // a supply crate appears
        LowVisibility = 32,        // smoke, snow or dust
        GroundShaking = 64,        // aftershock: buildings may collapse
    }

    public enum UnlockCategory { Equipment, Character, Animation, Outfit, Emote, Title, Banner, Vehicle, SpawnEffect }

    public sealed class MissionDef
    {
        public string Id;
        public string Title;
        public MissionKind Kind;
        public int Target = 1;          // count, or seconds for HoldZone
        public string TargetId = "";    // object group, item or zone id
        public int Reward;
    }

    public sealed class EventDef
    {
        public string Id;
        public string Title;
        public string Description;
        public EventEffect Effects;
        public ArcMask Phases = ArcMask.Any;
        public float Duration = 25f;
        public int Weight = 10;
        public DisasterType[] OnlyFor;  // null = every disaster
        public bool IsFinale;           // the big moment near the end of the round

        public bool AllowedFor(DisasterType d)
        {
            if (OnlyFor == null) return true;
            return Array.IndexOf(OnlyFor, d) >= 0;
        }
    }

    public sealed class DisasterDef
    {
        public DisasterType Type;
        public string Name;
        public string Intro;
        public float Duration = 240f;
        public List<MissionDef> MissionPool = new List<MissionDef>();
    }

    public sealed class RankDef
    {
        public string Name;
        public int MinSp;
        public int MinRescues;
        public int MinLastSurvivor;
        public int MinSecretMissions;
        public int MinDisasterTypes;   // number of different disasters survived
    }

    public sealed class UnlockDef
    {
        public string Id;
        public string Name;
        public UnlockCategory Category;
        public string RequiredRank;          // unlocked when this rank is reached (or null)
        public Func<PlayerProfile, bool> Milestone;  // or when this milestone is met
        public string MilestoneText;
    }

    /// <summary>All default content. Change numbers and texts here.</summary>
    public static class ContentLibrary
    {
        public const string RescueStation = "rescue_station";
        public const string Bunker = "bunker";
        public const string Radios = "radio";
        public const string EmergencyKit = "emergency_kit";
        public const string Rooftop = "rooftop";

        public static readonly int SecretReward = 700;

        // ---------------- Missions ----------------
        static MissionDef Survive() => new MissionDef { Id = "survive", Title = "Survive", Kind = MissionKind.Survive, Reward = 500 };
        static MissionDef Radios3() => new MissionDef { Id = "radios", Title = "Activate 3 emergency radios", Kind = MissionKind.ActivateObjects, Target = 3, TargetId = Radios, Reward = 400 };
        static MissionDef Rescue() => new MissionDef { Id = "rescue", Title = "Rescue another player", Kind = MissionKind.RescuePlayer, Reward = 600 };
        static MissionDef Kit() => new MissionDef { Id = "kit", Title = "Bring the emergency kit to the rescue station", Kind = MissionKind.DeliverItem, TargetId = EmergencyKit, Reward = 300 };
        static MissionDef Bunker60() => new MissionDef { Id = "bunker", Title = "Hold the bunker for 60 seconds", Kind = MissionKind.HoldZone, Target = 60, TargetId = Bunker, Reward = 800 };
        static MissionDef Roof() => new MissionDef { Id = "roof", Title = "Reach the rooftop", Kind = MissionKind.ReachZone, TargetId = Rooftop, Reward = 250 };
        static MissionDef Last() => new MissionDef { Id = "last", Title = "Be the last survivor", Kind = MissionKind.LastSurvivor, Reward = 400 };

        public static List<DisasterDef> Disasters()
        {
            return new List<DisasterDef>
            {
                new DisasterDef { Type = DisasterType.Tornado, Name = "Tornado", Intro = "A tornado is touching down. Find cover.", Duration = 240f,
                    MissionPool = { Survive(), Radios3(), Rescue(), Kit(), Bunker60(), Last() } },
                new DisasterDef { Type = DisasterType.Flood, Name = "Flood", Intro = "The dam broke. Get to high ground.", Duration = 240f,
                    MissionPool = { Survive(), Rescue(), Kit(), Roof(), Radios3(), Last() } },
                new DisasterDef { Type = DisasterType.Earthquake, Name = "Earthquake", Intro = "The ground is shaking. Stay away from buildings.", Duration = 210f,
                    MissionPool = { Survive(), Rescue(), Radios3(), Bunker60(), Kit(), Last() } },
                new DisasterDef { Type = DisasterType.Wildfire, Name = "Wildfire", Intro = "The forest is on fire. The wind is turning.", Duration = 240f,
                    MissionPool = { Survive(), Rescue(), Kit(), Bunker60(), Roof(), Last() } },
                new DisasterDef { Type = DisasterType.Blizzard, Name = "Blizzard", Intro = "A whiteout is coming. Keep moving or freeze.", Duration = 240f,
                    MissionPool = { Survive(), Radios3(), Rescue(), Bunker60(), Kit(), Last() } },
                new DisasterDef { Type = DisasterType.Volcano, Name = "Volcano", Intro = "The volcano erupts. Lava is on its way.", Duration = 210f,
                    MissionPool = { Survive(), Rescue(), Roof(), Kit(), Radios3(), Last() } },
            };
        }

        // ---------------- Round events ----------------
        public static List<EventDef> Events()
        {
            return new List<EventDef>
            {
                new EventDef { Id = "direction", Title = "Tornado changes direction", Description = "The safe side is not safe anymore.",
                    Effects = EventEffect.HazardMoves, Phases = ArcMask.Opening | ArcMask.Midgame, Duration = 20f, Weight = 14, OnlyFor = new[] { DisasterType.Tornado } },
                new EventDef { Id = "wind", Title = "The wind turns", Description = "The fire is spreading toward the village.",
                    Effects = EventEffect.HazardMoves, Phases = ArcMask.Opening | ArcMask.Midgame, Duration = 20f, Weight = 14, OnlyFor = new[] { DisasterType.Wildfire, DisasterType.Volcano } },
                new EventDef { Id = "power", Title = "Power failure", Description = "The bunker doors do not work anymore.",
                    Effects = EventEffect.BunkerDoorsDisabled, Phases = ArcMask.Midgame, Duration = 30f, Weight = 12 },
                new EventDef { Id = "rescue_call", Title = "Rescue event", Description = "A player was injured. Bring them to the rescue station.",
                    Effects = EventEffect.PlayerInjured, Phases = ArcMask.Opening | ArcMask.Midgame, Duration = 35f, Weight = 12 },
                new EventDef { Id = "flood_wave", Title = "Flood wave", Description = "The water is rising fast. Get up high.",
                    Effects = EventEffect.WaterRising, Phases = ArcMask.Midgame | ArcMask.Finale, Duration = 25f, Weight = 10,
                    OnlyFor = new[] { DisasterType.Flood, DisasterType.Tornado, DisasterType.Earthquake } },
                new EventDef { Id = "aftershock", Title = "Aftershock", Description = "Buildings are collapsing. Get out into the open.",
                    Effects = EventEffect.GroundShaking, Phases = ArcMask.Midgame | ArcMask.Finale, Duration = 15f, Weight = 12,
                    OnlyFor = new[] { DisasterType.Earthquake, DisasterType.Volcano } },
                new EventDef { Id = "smoke", Title = "Thick smoke", Description = "You can barely see anything.",
                    Effects = EventEffect.LowVisibility, Phases = ArcMask.Opening | ArcMask.Midgame, Duration = 25f, Weight = 8,
                    OnlyFor = new[] { DisasterType.Wildfire, DisasterType.Volcano, DisasterType.Blizzard } },
                new EventDef { Id = "supply", Title = "Supply drop", Description = "A crate with gear is landing. First come, first served.",
                    Effects = EventEffect.SupplyDrop, Phases = ArcMask.Opening | ArcMask.Midgame, Duration = 20f, Weight = 8 },
                // Finale: one of these happens near the end of every round
                new EventDef { Id = "finale_supercell", Title = "Supercell", Description = "The tornado reaches full strength. Only the bunker is safe.",
                    Effects = EventEffect.HazardMoves | EventEffect.LowVisibility, Phases = ArcMask.Finale, Duration = 40f, Weight = 10, IsFinale = true,
                    OnlyFor = new[] { DisasterType.Tornado } },
                new EventDef { Id = "finale_dam", Title = "Second dam breaks", Description = "Everything below the rooftops will be underwater.",
                    Effects = EventEffect.WaterRising, Phases = ArcMask.Finale, Duration = 40f, Weight = 10, IsFinale = true,
                    OnlyFor = new[] { DisasterType.Flood } },
                new EventDef { Id = "finale_mainshock", Title = "The main shock", Description = "The big one. Nothing stays standing.",
                    Effects = EventEffect.GroundShaking | EventEffect.BunkerDoorsDisabled, Phases = ArcMask.Finale, Duration = 35f, Weight = 10, IsFinale = true,
                    OnlyFor = new[] { DisasterType.Earthquake } },
                new EventDef { Id = "finale_firestorm", Title = "Firestorm", Description = "The fire closes in from all sides.",
                    Effects = EventEffect.HazardMoves | EventEffect.LowVisibility, Phases = ArcMask.Finale, Duration = 40f, Weight = 10, IsFinale = true,
                    OnlyFor = new[] { DisasterType.Wildfire } },
                new EventDef { Id = "finale_whiteout", Title = "Total whiteout", Description = "Zero visibility. Follow the radios home.",
                    Effects = EventEffect.LowVisibility | EventEffect.BunkerDoorsDisabled, Phases = ArcMask.Finale, Duration = 40f, Weight = 10, IsFinale = true,
                    OnlyFor = new[] { DisasterType.Blizzard } },
                new EventDef { Id = "finale_eruption", Title = "Main eruption", Description = "Lava floods the valley. Climb.",
                    Effects = EventEffect.HazardMoves | EventEffect.GroundShaking, Phases = ArcMask.Finale, Duration = 40f, Weight = 10, IsFinale = true,
                    OnlyFor = new[] { DisasterType.Volcano } },
            };
        }

        // ---------------- Ranks ----------------
        public static List<RankDef> Ranks()
        {
            return new List<RankDef>
            {
                new RankDef { Name = "Rookie" },
                new RankDef { Name = "Survivor", MinSp = 6000 },
                new RankDef { Name = "Veteran", MinSp = 35000, MinRescues = 10, MinDisasterTypes = 3 },
                new RankDef { Name = "Elite", MinSp = 120000, MinRescues = 30, MinLastSurvivor = 2, MinSecretMissions = 8, MinDisasterTypes = 5 },
                new RankDef { Name = "Disaster Master", MinSp = 350000, MinRescues = 80, MinLastSurvivor = 5, MinSecretMissions = 25, MinDisasterTypes = 6 },
            };
        }

        // ---------------- Unlocks (cosmetic, no stat boosts) ----------------
        public static List<UnlockDef> Unlocks()
        {
            return new List<UnlockDef>
            {
                new UnlockDef { Id = "title_rookie", Name = "Title: Rookie", Category = UnlockCategory.Title, RequiredRank = "Rookie" },
                new UnlockDef { Id = "outfit_raincoat", Name = "Yellow Raincoat", Category = UnlockCategory.Outfit, RequiredRank = "Survivor" },
                new UnlockDef { Id = "emote_phew", Name = "Emote: Phew!", Category = UnlockCategory.Emote, RequiredRank = "Survivor" },
                new UnlockDef { Id = "equip_flare", Name = "Signal Flare", Category = UnlockCategory.Equipment, RequiredRank = "Veteran" },
                new UnlockDef { Id = "char_ranger", Name = "Character: Park Ranger", Category = UnlockCategory.Character, RequiredRank = "Veteran" },
                new UnlockDef { Id = "banner_storm", Name = "Banner: Eye of the Storm", Category = UnlockCategory.Banner, RequiredRank = "Veteran" },
                new UnlockDef { Id = "vehicle_atv", Name = "Rescue ATV", Category = UnlockCategory.Vehicle, RequiredRank = "Elite" },
                new UnlockDef { Id = "spawn_lightning", Name = "Spawn Effect: Lightning Strike", Category = UnlockCategory.SpawnEffect, RequiredRank = "Elite" },
                new UnlockDef { Id = "anim_hero_landing", Name = "Animation: Hero Landing", Category = UnlockCategory.Animation, RequiredRank = "Elite" },
                new UnlockDef { Id = "title_master", Name = "Title: Disaster Master", Category = UnlockCategory.Title, RequiredRank = "Disaster Master" },
                new UnlockDef { Id = "spawn_meteor", Name = "Spawn Effect: Meteor", Category = UnlockCategory.SpawnEffect, RequiredRank = "Disaster Master" },
                new UnlockDef { Id = "vehicle_heli", Name = "Rescue Helicopter", Category = UnlockCategory.Vehicle, RequiredRank = "Disaster Master" },

                // Milestones: unlocked by what you did, not by grinding points
                new UnlockDef { Id = "title_lifesaver", Name = "Title: Lifesaver", Category = UnlockCategory.Title,
                    Milestone = p => p.Rescues >= 10, MilestoneText = "Rescue 10 players" },
                new UnlockDef { Id = "outfit_paramedic", Name = "Paramedic Outfit", Category = UnlockCategory.Outfit,
                    Milestone = p => p.Rescues >= 25, MilestoneText = "Rescue 25 players" },
                new UnlockDef { Id = "title_lone_wolf", Name = "Title: Lone Wolf", Category = UnlockCategory.Title,
                    Milestone = p => p.LastSurvivorWins >= 5, MilestoneText = "Be the last survivor 5 times" },
                new UnlockDef { Id = "emote_shrug", Name = "Emote: Not My Problem", Category = UnlockCategory.Emote,
                    Milestone = p => p.TimesLeftSomeoneBehind >= 5, MilestoneText = "Leave 5 injured players behind" },
                new UnlockDef { Id = "banner_mastermind", Name = "Banner: Mastermind", Category = UnlockCategory.Banner,
                    Milestone = p => p.SecretMissionsDone >= 10, MilestoneText = "Complete 10 secret missions" },
                new UnlockDef { Id = "char_storm_chaser", Name = "Character: Storm Chaser", Category = UnlockCategory.Character,
                    Milestone = p => p.SurvivedCount(DisasterType.Tornado) >= 10, MilestoneText = "Survive 10 tornadoes" },
                new UnlockDef { Id = "char_lifeguard", Name = "Character: Lifeguard", Category = UnlockCategory.Character,
                    Milestone = p => p.SurvivedCount(DisasterType.Flood) >= 10, MilestoneText = "Survive 10 floods" },
                new UnlockDef { Id = "equip_fire_blanket", Name = "Fire Blanket", Category = UnlockCategory.Equipment,
                    Milestone = p => p.SurvivedCount(DisasterType.Wildfire) >= 10, MilestoneText = "Survive 10 wildfires" },
                new UnlockDef { Id = "anim_dust_off", Name = "Animation: Dust Off", Category = UnlockCategory.Animation,
                    Milestone = p => p.SurvivedCount(DisasterType.Earthquake) >= 10, MilestoneText = "Survive 10 earthquakes" },
            };
        }
    }
}
