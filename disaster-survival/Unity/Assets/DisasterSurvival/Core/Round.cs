// Disaster Survival - one round: missions, secret missions, the event director and the story log.
// The game world reports what happens (radio activated, player rescued, ...) and ticks the round.
// The round decides which events fire, which missions are completed and how many points are earned.
using System;
using System.Collections.Generic;
using System.Linq;

namespace DisasterSurvival.Core
{
    public sealed class RoundRules
    {
        public int SharedMissionCount = 3;        // missions everyone can complete, "Survive" is always one of them
        public bool SecretMissions = true;
        public float MinEventGap = 30f;
        public float MaxEventGap = 60f;
        public float FirstEventAfter = 20f;
        public float FinaleAt = 0.78f;            // share of the round when the finale event starts
        public bool InjuredDieIfNotRescued = true;
        public int RepeatRescueBonus = 150;       // every rescue after the mission is done
    }

    public sealed class SecretMission
    {
        public SecretKind Kind;
        public string TargetId;
        public string Text;
        public bool Done;
    }

    public sealed class PlayerState
    {
        public readonly string Id;
        public readonly string Name;
        public bool Alive = true;
        public bool Injured;
        public int Sp;
        public int Rescues;
        public int LeftBehind;
        public float ReachedStationAt = -1f;
        public SecretMission Secret;
        public readonly HashSet<string> Completed = new HashSet<string>();
        public readonly Dictionary<string, int> Activations = new Dictionary<string, int>();
        public readonly Dictionary<string, float> ZoneSeconds = new Dictionary<string, float>();
        public readonly HashSet<string> ZonesReached = new HashSet<string>();

        public PlayerState(string id, string name) { Id = id; Name = name; }

        public int TotalActivations => Activations.Values.Sum();
    }

    public enum StoryKind { Injured, Rescued, LeftBehind, Eliminated, MissionDone, SecretDone, SecretFailed, Survived, LastSurvivor, EventStarted }

    public sealed class StoryEntry
    {
        public float Time;
        public StoryKind Kind;
        public string Actor;   // player id
        public string Other;   // second player id, if any
        public string Text;
    }

    public sealed class ActiveEvent
    {
        public EventDef Def;
        public float StartedAt;
        public float EndsAt;
        public string InjuredPlayerId;
    }

    public sealed class RoundResult
    {
        public int RoundNumber;
        public DisasterDef Disaster;
        public List<MissionDef> Missions;
        public List<PlayerState> Players;
        public List<StoryEntry> Story;
        public string LastSurvivorId;
    }

    public sealed class RoundController
    {
        public readonly DisasterDef Disaster;
        public readonly RoundRules Rules;
        public readonly int RoundNumber;
        public readonly List<MissionDef> Missions = new List<MissionDef>();
        public readonly List<PlayerState> Players = new List<PlayerState>();
        public readonly List<StoryEntry> Story = new List<StoryEntry>();
        public readonly List<ActiveEvent> ActiveEvents = new List<ActiveEvent>();

        public float Elapsed { get; private set; }
        public bool Finished { get; private set; }
        public float TimeLeft => Math.Max(0f, Disaster.Duration - Elapsed);
        public ArcPhase Phase => PhaseAt(Elapsed / Disaster.Duration);

        /// <summary>Short text for the HUD banner ("Power failure - the bunker doors ...").</summary>
        public event Action<string> Announced;
        public event Action<ActiveEvent> EventStarted;
        public event Action<ActiveEvent> EventEnded;
        public event Action<PlayerState, MissionDef> MissionCompleted;
        public event Action<PlayerState> PlayerInjured;
        public event Action<PlayerState> PlayerDied;
        public event Action<RoundResult> RoundEnded;

        readonly Random _rng;
        readonly List<EventDef> _eventPool;
        float _nextEventAt;
        bool _finaleStarted;
        string _lastEventId;

        public RoundController(int roundNumber, DisasterDef disaster, IEnumerable<KeyValuePair<string, string>> roster,
                               List<EventDef> eventPool, RoundRules rules = null, Random rng = null)
        {
            RoundNumber = roundNumber;
            Disaster = disaster;
            Rules = rules ?? new RoundRules();
            _rng = rng ?? new Random();
            _eventPool = eventPool ?? ContentLibrary.Events();
            foreach (var p in roster) Players.Add(new PlayerState(p.Key, p.Value));

            PickMissions();
            if (Rules.SecretMissions && Players.Count >= 2) AssignSecretMissions();
            _nextEventAt = Rules.FirstEventAfter;
        }

        // ------------------------------------------------------------ setup

        void PickMissions()
        {
            var survive = Disaster.MissionPool.FirstOrDefault(m => m.Kind == MissionKind.Survive);
            if (survive != null) Missions.Add(survive);
            var rest = Disaster.MissionPool.Where(m => m != survive).ToList();
            // LastSurvivor and RescuePlayer only make sense with company
            if (Players.Count < 2) rest.RemoveAll(m => m.Kind == MissionKind.LastSurvivor || m.Kind == MissionKind.RescuePlayer);
            Shuffle(rest);
            Missions.AddRange(rest.Take(Math.Max(0, Rules.SharedMissionCount - Missions.Count)));
        }

        void AssignSecretMissions()
        {
            var kinds = (SecretKind[])Enum.GetValues(typeof(SecretKind));
            foreach (var p in Players)
            {
                var others = Players.Where(o => o != p).ToList();
                var target = others[_rng.Next(others.Count)];
                var kind = kinds[_rng.Next(kinds.Length)];
                string text;
                switch (kind)
                {
                    case SecretKind.ReachBefore: text = $"Reach the rescue station before {target.Name}."; break;
                    case SecretKind.RescueTarget: text = $"If {target.Name} gets injured, you must be the one who rescues them."; break;
                    case SecretKind.KeepTargetFromStation: text = $"Keep {target.Name} away from the rescue station."; break;
                    default: text = "Activate more objects than anyone else."; break;
                }
                p.Secret = new SecretMission { Kind = kind, TargetId = target.Id, Text = text };
            }
        }

        // ------------------------------------------------------------ main loop

        public void Tick(float dt)
        {
            if (Finished || dt <= 0f) return;
            Elapsed += dt;

            for (int i = ActiveEvents.Count - 1; i >= 0; i--)
                if (Elapsed >= ActiveEvents[i].EndsAt) EndEvent(ActiveEvents[i]);

            if (!_finaleStarted && Elapsed >= Disaster.Duration * Rules.FinaleAt)
            {
                _finaleStarted = true;
                var finale = PickEvent(true);
                if (finale != null) StartEvent(finale);
            }
            else if (Elapsed >= _nextEventAt && Elapsed < Disaster.Duration * Rules.FinaleAt - 10f)
            {
                var e = PickEvent(false);
                if (e != null) StartEvent(e);
                _nextEventAt = Elapsed + Rules.MinEventGap + (float)_rng.NextDouble() * (Rules.MaxEventGap - Rules.MinEventGap);
            }

            if (Elapsed >= Disaster.Duration || Players.All(p => !p.Alive)) EndRound();
        }

        public static ArcPhase PhaseAt(float share)
        {
            if (share < 0.34f) return ArcPhase.Opening;
            if (share < 0.75f) return ArcPhase.Midgame;
            return ArcPhase.Finale;
        }

        EventDef PickEvent(bool finale)
        {
            var mask = Phase == ArcPhase.Opening ? ArcMask.Opening : Phase == ArcPhase.Midgame ? ArcMask.Midgame : ArcMask.Finale;
            int healthy = Players.Count(p => p.Alive && !p.Injured);
            var candidates = _eventPool.Where(e =>
                    e.IsFinale == finale &&
                    e.AllowedFor(Disaster.Type) &&
                    (finale || (e.Phases & mask) != 0) &&
                    e.Id != _lastEventId &&
                    ActiveEvents.All(a => a.Def.Id != e.Id) &&
                    // a rescue event needs someone to get hurt and someone to help
                    ((e.Effects & EventEffect.PlayerInjured) == 0 || healthy >= 2))
                .ToList();
            if (candidates.Count == 0) return null;
            int total = candidates.Sum(e => e.Weight);
            int roll = _rng.Next(total);
            foreach (var e in candidates)
            {
                roll -= e.Weight;
                if (roll < 0) return e;
            }
            return candidates[candidates.Count - 1];
        }

        void StartEvent(EventDef def)
        {
            var ev = new ActiveEvent { Def = def, StartedAt = Elapsed, EndsAt = Elapsed + def.Duration };
            _lastEventId = def.Id;
            ActiveEvents.Add(ev);
            Log(StoryKind.EventStarted, null, null, def.Title);

            string text = $"{def.Title}! {def.Description}";
            if ((def.Effects & EventEffect.PlayerInjured) != 0)
            {
                var healthy = Players.Where(p => p.Alive && !p.Injured).ToList();
                // Prefer players that someone's secret mission is about: that is where the drama is
                var targeted = healthy.Where(h => Players.Any(o => o.Secret != null && o.Secret.TargetId == h.Id &&
                    (o.Secret.Kind == SecretKind.RescueTarget || o.Secret.Kind == SecretKind.KeepTargetFromStation))).ToList();
                var pool = targeted.Count > 0 && _rng.NextDouble() < 0.6 ? targeted : healthy;
                var victim = pool[_rng.Next(pool.Count)];
                victim.Injured = true;
                ev.InjuredPlayerId = victim.Id;
                text = $"{def.Title}! {victim.Name} is injured. Bring them to the rescue station.";
                Log(StoryKind.Injured, victim.Id, null, $"{victim.Name} got injured.");
                PlayerInjured?.Invoke(victim);
            }
            Announced?.Invoke(text);
            EventStarted?.Invoke(ev);
        }

        void EndEvent(ActiveEvent ev)
        {
            ActiveEvents.Remove(ev);
            if (ev.InjuredPlayerId != null && Rules.InjuredDieIfNotRescued)
            {
                var victim = Find(ev.InjuredPlayerId);
                if (victim != null && victim.Alive && victim.Injured)
                    PlayerEliminated(victim.Id, "was not rescued in time");
            }
            EventEnded?.Invoke(ev);
        }

        /// <summary>True while an active event has this effect (e.g. bunker doors disabled).</summary>
        public bool IsActive(EventEffect effect) => ActiveEvents.Any(e => (e.Def.Effects & effect) != 0);

        // ------------------------------------------------------------ reports from the game world

        public void ObjectActivated(string playerId, string groupId)
        {
            var p = AliveHealthy(playerId);
            if (p == null) return;
            p.Activations[groupId] = (p.Activations.TryGetValue(groupId, out var n) ? n : 0) + 1;
            foreach (var m in Missions.Where(m => m.Kind == MissionKind.ActivateObjects && m.TargetId == groupId))
                if (p.Activations[groupId] >= m.Target) Complete(p, m);
        }

        public void ItemDelivered(string playerId, string itemId)
        {
            var p = AliveHealthy(playerId);
            if (p == null) return;
            foreach (var m in Missions.Where(m => m.Kind == MissionKind.DeliverItem && m.TargetId == itemId))
                Complete(p, m);
        }

        public void PlayerReachedZone(string playerId, string zoneId)
        {
            var p = Find(playerId);
            if (p == null || !p.Alive) return;
            p.ZonesReached.Add(zoneId);
            if (zoneId == ContentLibrary.RescueStation && p.ReachedStationAt < 0f) p.ReachedStationAt = Elapsed;
            if (p.Injured) return;
            foreach (var m in Missions.Where(m => m.Kind == MissionKind.ReachZone && m.TargetId == zoneId))
                Complete(p, m);
        }

        /// <summary>Call every frame while the player stands inside the zone.</summary>
        public void PlayerInZone(string playerId, string zoneId, float dt)
        {
            var p = AliveHealthy(playerId);
            if (p == null || Finished) return;
            p.ZoneSeconds[zoneId] = (p.ZoneSeconds.TryGetValue(zoneId, out var s) ? s : 0f) + dt;
            foreach (var m in Missions.Where(m => m.Kind == MissionKind.HoldZone && m.TargetId == zoneId))
                if (p.ZoneSeconds[zoneId] >= m.Target) Complete(p, m);
        }

        public void PlayerRescued(string rescuerId, string injuredId)
        {
            var rescuer = AliveHealthy(rescuerId);
            var injured = Find(injuredId);
            if (rescuer == null || injured == null || !injured.Alive || !injured.Injured || rescuer == injured) return;

            injured.Injured = false;
            PlayerReachedZone(injured.Id, ContentLibrary.RescueStation);
            foreach (var ev in ActiveEvents.Where(e => e.InjuredPlayerId == injured.Id)) ev.InjuredPlayerId = null;

            rescuer.Rescues++;
            Log(StoryKind.Rescued, rescuer.Id, injured.Id, $"{rescuer.Name} rescued {injured.Name}.");
            Announced?.Invoke($"{rescuer.Name} rescued {injured.Name}!");

            var mission = Missions.FirstOrDefault(m => m.Kind == MissionKind.RescuePlayer);
            if (mission != null && !rescuer.Completed.Contains(mission.Id)) Complete(rescuer, mission);
            else rescuer.Sp += Rules.RepeatRescueBonus;

            if (rescuer.Secret != null && rescuer.Secret.Kind == SecretKind.RescueTarget && rescuer.Secret.TargetId == injured.Id)
                rescuer.Secret.Done = true;
        }

        /// <summary>The game decides when someone abandoned an injured player (e.g. was close and ran off).</summary>
        public void PlayerLeftBehind(string leaverId, string injuredId)
        {
            var leaver = Find(leaverId);
            var injured = Find(injuredId);
            if (leaver == null || injured == null || leaver == injured || !injured.Injured) return;
            if (Story.Any(s => s.Kind == StoryKind.LeftBehind && s.Actor == leaverId && s.Other == injuredId)) return;
            leaver.LeftBehind++;
            Log(StoryKind.LeftBehind, leaver.Id, injured.Id, $"{leaver.Name} left {injured.Name} behind.");
        }

        /// <summary>Extra points outside the missions, e.g. for opening a supply crate.</summary>
        public void AwardBonus(string playerId, int sp, string reason)
        {
            var p = AliveHealthy(playerId);
            if (p == null || sp <= 0) return;
            p.Sp += sp;
            Announced?.Invoke($"{p.Name}: {reason} (+{sp} SP)");
        }

        public void PlayerEliminated(string playerId, string cause)
        {
            var p = Find(playerId);
            if (p == null || !p.Alive) return;
            p.Alive = false;
            p.Injured = false;
            Log(StoryKind.Eliminated, p.Id, null, $"{p.Name} {cause}.");
            Announced?.Invoke($"{p.Name} {cause}.");
            PlayerDied?.Invoke(p);
        }

        // ------------------------------------------------------------ end of round

        void EndRound()
        {
            if (Finished) return;
            Finished = true;
            foreach (var ev in ActiveEvents.ToList()) EndEvent(ev);

            var alive = Players.Where(p => p.Alive).ToList();
            foreach (var p in alive)
            {
                var survive = Missions.FirstOrDefault(m => m.Kind == MissionKind.Survive);
                if (survive != null) Complete(p, survive);
                Log(StoryKind.Survived, p.Id, null, $"{p.Name} survived.");
            }

            string lastId = null;
            if (Players.Count >= 2 && alive.Count == 1)
            {
                lastId = alive[0].Id;
                var last = Missions.FirstOrDefault(m => m.Kind == MissionKind.LastSurvivor);
                if (last != null) Complete(alive[0], last);
                Log(StoryKind.LastSurvivor, lastId, null, $"{alive[0].Name} was the last survivor.");
            }

            ResolveSecrets();

            RoundEnded?.Invoke(new RoundResult
            {
                RoundNumber = RoundNumber,
                Disaster = Disaster,
                Missions = Missions.ToList(),
                Players = Players.ToList(),
                Story = Story.ToList(),
                LastSurvivorId = lastId,
            });
        }

        void ResolveSecrets()
        {
            foreach (var p in Players.Where(p => p.Secret != null))
            {
                var s = p.Secret;
                var target = Find(s.TargetId);
                switch (s.Kind)
                {
                    case SecretKind.ReachBefore:
                        s.Done = p.ReachedStationAt >= 0f && (target.ReachedStationAt < 0f || p.ReachedStationAt < target.ReachedStationAt);
                        break;
                    case SecretKind.KeepTargetFromStation:
                        s.Done = target.ReachedStationAt < 0f;
                        break;
                    case SecretKind.MostActivations:
                        int mine = p.TotalActivations;
                        s.Done = mine > 0 && Players.Where(o => o != p).All(o => o.TotalActivations < mine);
                        break;
                    case SecretKind.RescueTarget:
                        break; // set when the rescue happens
                }
                if (s.Done)
                {
                    p.Sp += ContentLibrary.SecretReward;
                    Log(StoryKind.SecretDone, p.Id, s.TargetId, $"Secret mission of {p.Name}: \"{s.Text}\" - completed.");
                }
                else
                {
                    Log(StoryKind.SecretFailed, p.Id, s.TargetId, $"Secret mission of {p.Name}: \"{s.Text}\" - failed.");
                }
            }
        }

        // ------------------------------------------------------------ helpers

        void Complete(PlayerState p, MissionDef m)
        {
            if (p.Completed.Contains(m.Id)) return;
            p.Completed.Add(m.Id);
            p.Sp += m.Reward;
            Log(StoryKind.MissionDone, p.Id, null, $"{p.Name}: {m.Title} (+{m.Reward} SP)");
            MissionCompleted?.Invoke(p, m);
        }

        void Log(StoryKind kind, string actor, string other, string text)
        {
            Story.Add(new StoryEntry { Time = Elapsed, Kind = kind, Actor = actor, Other = other, Text = text });
        }

        public PlayerState Find(string id) => Players.FirstOrDefault(p => p.Id == id);

        PlayerState AliveHealthy(string id)
        {
            var p = Find(id);
            return p != null && p.Alive && !p.Injured && !Finished ? p : null;
        }

        void Shuffle<T>(IList<T> list)
        {
            for (int i = list.Count - 1; i > 0; i--)
            {
                int j = _rng.Next(i + 1);
                T tmp = list[i];
                list[i] = list[j];
                list[j] = tmp;
            }
        }
    }
}
