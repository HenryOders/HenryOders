// Disaster Survival - a match of several rounds. Picks a new disaster each round,
// keeps the score and turns what happened into a short story that remembers earlier rounds.
using System;
using System.Collections.Generic;
using System.Linq;

namespace DisasterSurvival.Core
{
    public sealed class MatchSession
    {
        public readonly List<KeyValuePair<string, string>> Roster;
        public readonly int RoundsTotal;
        public readonly RoundRules Rules;
        public readonly List<RoundResult> History = new List<RoundResult>();
        public readonly Dictionary<string, int> TotalSp = new Dictionary<string, int>();

        public RoundController Current { get; private set; }
        public bool Finished => History.Count >= RoundsTotal;

        public event Action<RoundController> RoundStarted;
        public event Action<RoundResult> RoundFinished;
        public event Action<MatchSession> MatchFinished;

        readonly List<DisasterDef> _disasters;
        readonly List<EventDef> _events;
        readonly Random _rng;

        public MatchSession(IEnumerable<KeyValuePair<string, string>> roster, int rounds = 4, RoundRules rules = null,
                            int? seed = null, List<DisasterDef> disasters = null, List<EventDef> events = null)
        {
            Roster = roster.ToList();
            RoundsTotal = Math.Max(1, rounds);
            Rules = rules ?? new RoundRules();
            _rng = seed.HasValue ? new Random(seed.Value) : new Random();
            _disasters = disasters ?? ContentLibrary.Disasters();
            _events = events ?? ContentLibrary.Events();
            foreach (var p in Roster) TotalSp[p.Key] = 0;
        }

        public string NameOf(string id) => Roster.FirstOrDefault(p => p.Key == id).Value ?? id;

        /// <summary>Starts the next round with a disaster that was not played yet in this match, if possible.</summary>
        public RoundController StartNextRound()
        {
            if (Finished) return null;
            var played = History.Select(h => h.Disaster.Type).ToList();
            var fresh = _disasters.Where(d => !played.Contains(d.Type)).ToList();
            var pool = fresh.Count > 0 ? fresh : _disasters.Where(d => played.Count == 0 || d.Type != played.Last()).ToList();
            var disaster = pool[_rng.Next(pool.Count)];

            Current = new RoundController(History.Count + 1, disaster, Roster, _events, Rules, new Random(_rng.Next()));
            Current.RoundEnded += OnRoundEnded;
            RoundStarted?.Invoke(Current);
            return Current;
        }

        void OnRoundEnded(RoundResult result)
        {
            History.Add(result);
            foreach (var p in result.Players) TotalSp[p.Id] = (TotalSp.TryGetValue(p.Id, out var sp) ? sp : 0) + p.Sp;
            RoundFinished?.Invoke(result);
            if (Finished) MatchFinished?.Invoke(this);
        }

        // ------------------------------------------------------------ story

        /// <summary>Recap lines for one round, shown on the results screen.</summary>
        public List<string> RoundRecap(RoundResult r)
        {
            var lines = new List<string> { $"Round {r.RoundNumber}: {r.Disaster.Name}" };

            foreach (var s in r.Story)
            {
                switch (s.Kind)
                {
                    case StoryKind.Rescued:
                    case StoryKind.LeftBehind:
                        lines.Add(WithHistory(s, r.RoundNumber));
                        break;
                    case StoryKind.Eliminated:
                    case StoryKind.LastSurvivor:
                        lines.Add(s.Text);
                        break;
                    case StoryKind.SecretDone:
                        lines.Add($"Revealed: {NameOf(s.Actor)} had a secret mission - {SecretText(r, s.Actor)} And did it.");
                        break;
                }
            }

            var alive = r.Players.Count(p => p.Alive);
            lines.Add(alive == 0 ? "Nobody survived." : alive == r.Players.Count ? "Everyone made it out." : $"{alive} of {r.Players.Count} survived.");

            var best = r.Players.OrderByDescending(p => p.Sp).First();
            lines.Add($"Most points: {best.Name} with {best.Sp} SP.");
            return lines;
        }

        /// <summary>One headline per round, e.g. "Round 2: Flood - B leaves A behind."</summary>
        public List<string> MatchStory()
        {
            var lines = new List<string>();
            foreach (var r in History)
            {
                var pick = Headline(r);
                lines.Add($"Round {r.RoundNumber}: {r.Disaster.Name} - {pick}");
            }
            return lines;
        }

        public List<KeyValuePair<string, int>> Leaderboard() =>
            TotalSp.OrderByDescending(kv => kv.Value).ToList();

        string Headline(RoundResult r)
        {
            // The most dramatic thing that happened, in this order
            var order = new[] { StoryKind.LeftBehind, StoryKind.Rescued, StoryKind.SecretDone, StoryKind.LastSurvivor };
            foreach (var kind in order)
            {
                var s = r.Story.FirstOrDefault(x => x.Kind == kind);
                if (s == null) continue;
                switch (kind)
                {
                    case StoryKind.LeftBehind: return WithHistory(s, r.RoundNumber);
                    case StoryKind.Rescued: return WithHistory(s, r.RoundNumber);
                    case StoryKind.SecretDone: return $"{NameOf(s.Actor)} pulled off a secret mission.";
                    case StoryKind.LastSurvivor: return $"{NameOf(s.Actor)} was the last one standing.";
                }
            }
            int alive = r.Players.Count(p => p.Alive);
            return alive == 0 ? "nobody made it." : $"{alive} survived together.";
        }

        // Adds what happened between the same two players in earlier rounds
        string WithHistory(StoryEntry s, int round)
        {
            string a = NameOf(s.Actor), b = NameOf(s.Other);
            var earlier = History.Where(h => h.RoundNumber < round).SelectMany(h => h.Story.Select(x => new { h.RoundNumber, Entry = x })).ToList();

            if (s.Kind == StoryKind.LeftBehind)
            {
                var savedBy = earlier.LastOrDefault(x => x.Entry.Kind == StoryKind.Rescued && x.Entry.Actor == s.Other && x.Entry.Other == s.Actor);
                if (savedBy != null) return $"{a} leaves {b} behind - even though {b} saved {a} in round {savedBy.RoundNumber}.";
                var revenge = earlier.LastOrDefault(x => x.Entry.Kind == StoryKind.LeftBehind && x.Entry.Actor == s.Other && x.Entry.Other == s.Actor);
                if (revenge != null) return $"{a} leaves {b} behind. Payback for round {revenge.RoundNumber}.";
                return $"{a} leaves {b} behind.";
            }

            var betrayed = earlier.LastOrDefault(x => x.Entry.Kind == StoryKind.LeftBehind && x.Entry.Actor == s.Other && x.Entry.Other == s.Actor);
            if (betrayed != null) return $"{a} rescues {b} anyway - although {b} left {a} behind in round {betrayed.RoundNumber}.";
            var favor = earlier.LastOrDefault(x => x.Entry.Kind == StoryKind.Rescued && x.Entry.Actor == s.Other && x.Entry.Other == s.Actor);
            if (favor != null) return $"{a} rescues {b} and returns the favor from round {favor.RoundNumber}.";
            var again = earlier.LastOrDefault(x => x.Entry.Kind == StoryKind.Rescued && x.Entry.Actor == s.Actor && x.Entry.Other == s.Other);
            if (again != null) return $"{a} rescues {b} again, just like in round {again.RoundNumber}.";
            return $"{a} rescues {b}.";
        }

        static string SecretText(RoundResult r, string playerId)
        {
            var p = r.Players.FirstOrDefault(x => x.Id == playerId);
            return p?.Secret == null ? "" : p.Secret.Text;
        }
    }
}
