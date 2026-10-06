// Simulates whole matches with random player behaviour and checks the core rules.
// Build and run without Unity:  mcs -out:sim.exe ../Unity/Assets/DisasterSurvival/Core/*.cs Simulation.cs && mono sim.exe
using System;
using System.Collections.Generic;
using System.Linq;
using DisasterSurvival.Core;

static class Simulation
{
    static int failures;

    static void Check(bool ok, string what)
    {
        if (!ok) { failures++; Console.WriteLine("FAIL: " + what); }
    }

    static void Main()
    {
        var roster = new List<KeyValuePair<string, string>>
        {
            new KeyValuePair<string, string>("a", "Alex"),
            new KeyValuePair<string, string>("b", "Ben"),
            new KeyValuePair<string, string>("c", "Cleo"),
            new KeyValuePair<string, string>("d", "Dana"),
        };

        // ---- One full match, printed as an example
        var match = new MatchSession(roster, 4, seed: 7);
        var rng = new Random(11);
        var profiles = roster.ToDictionary(p => p.Key, p => new PlayerProfile { PlayerId = p.Key });

        while (!match.Finished)
        {
            var round = match.StartNextRound();
            var eventTimes = new List<float>();
            bool finaleSeen = false;
            round.EventStarted += e => { eventTimes.Add(round.Elapsed); if (e.Def.IsFinale) finaleSeen = true; };
            round.Announced += t => Console.WriteLine($"   [{round.Elapsed,5:0}s] {t}");

            Console.WriteLine($"\n=== Round {round.RoundNumber}: {round.Disaster.Name} ({round.Disaster.Duration}s) ===");
            Console.WriteLine("   Missions: " + string.Join(" | ", round.Missions.Select(m => $"{m.Title} +{m.Reward}")));
            foreach (var p in round.Players) Console.WriteLine($"   Secret for {p.Name}: {p.Secret.Text}");

            Check(round.Missions.Count == 3, "three shared missions");
            Check(round.Missions[0].Kind == MissionKind.Survive, "survive is always a mission");

            PlayRandomly(round, rng);

            // events: first after ~20 s, then 30-60 s apart, plus one finale
            Check(finaleSeen, "finale event happened in round " + round.RoundNumber);
            var normal = eventTimes.Take(eventTimes.Count - 1).ToList();
            for (int i = 1; i < normal.Count; i++)
                Check(normal[i] - normal[i - 1] >= 29.5f && normal[i] - normal[i - 1] <= 60.5f, $"event gap {normal[i] - normal[i - 1]:0.0}s");

            var result = match.History.Last();
            Console.WriteLine();
            foreach (var line in match.RoundRecap(result)) Console.WriteLine("   " + line);
            foreach (var pr in profiles.Values)
            {
                var up = Progression.ApplyRound(pr, result);
                if (up.RankUp) Console.WriteLine($"   RANK UP: {match.NameOf(pr.PlayerId)} is now {up.NewRank}");
                foreach (var u in up.NewUnlocks) Console.WriteLine($"   Unlocked for {match.NameOf(pr.PlayerId)}: {u.Name}");
            }
        }

        Console.WriteLine("\n=== Match story ===");
        foreach (var line in match.MatchStory()) Console.WriteLine("   " + line);
        Console.WriteLine("\n=== Leaderboard ===");
        foreach (var kv in match.Leaderboard()) Console.WriteLine($"   {match.NameOf(kv.Key),-6} {kv.Value} SP");
        Check(match.History.Select(h => h.Disaster.Type).Distinct().Count() == 4, "four different disasters in four rounds");

        // ---- Deterministic rule checks
        RuleChecks(roster);

        // ---- Many matches: long-term progression reaches the top rank
        var veteran = new PlayerProfile { PlayerId = "a" };
        int matches = 0;
        string lastRank = veteran.Rank;
        while (veteran.Rank != "Disaster Master" && matches < 2000)
        {
            var m = new MatchSession(roster, 4, seed: 100 + matches);
            var r = new Random(matches);
            while (!m.Finished) { PlayRandomly(m.StartNextRound(), r); Progression.ApplyRound(veteran, m.History.Last()); }
            matches++;
            if (veteran.Rank != lastRank) { Console.WriteLine($"   {veteran.Rank} after {matches} matches ({veteran.TotalSp} SP, {veteran.Rescues} rescues, {veteran.LastSurvivorWins}x last survivor)"); lastRank = veteran.Rank; }
        }
        Console.WriteLine($"\nDisaster Master after {matches} matches ({matches * 4} rounds), {veteran.Unlocked.Count} unlocks.");
        Check(veteran.Rank == "Disaster Master", "top rank reachable");

        Console.WriteLine(failures == 0 ? "\nALL CHECKS PASSED" : $"\n{failures} CHECKS FAILED");
        Environment.Exit(failures == 0 ? 0 : 1);
    }

    // Random but plausible behaviour: players activate radios, hold the bunker, help or abandon the injured
    static void PlayRandomly(RoundController round, Random rng)
    {
        const float dt = 0.5f;
        while (!round.Finished)
        {
            foreach (var p in round.Players.Where(p => p.Alive && !p.Injured).ToList())
            {
                double r = rng.NextDouble();
                if (r < 0.006) round.ObjectActivated(p.Id, ContentLibrary.Radios);
                else if (r < 0.008) round.ItemDelivered(p.Id, ContentLibrary.EmergencyKit);
                else if (r < 0.010) round.PlayerReachedZone(p.Id, ContentLibrary.Rooftop);
                else if (r < 0.012) round.PlayerReachedZone(p.Id, ContentLibrary.RescueStation);
                else if (r < 0.0123) round.PlayerEliminated(p.Id, "was swept away");
                // dangerous events actually kill people
                if (round.IsActive(EventEffect.HazardMoves | EventEffect.WaterRising | EventEffect.GroundShaking) && rng.NextDouble() < 0.0022)
                    round.PlayerEliminated(p.Id, "did not make it");

                if (!round.IsActive(EventEffect.BunkerDoorsDisabled) && rng.NextDouble() < 0.5)
                    round.PlayerInZone(p.Id, ContentLibrary.Bunker, dt * 0.4f);
            }
            var injured = round.Players.FirstOrDefault(p => p.Alive && p.Injured);
            if (injured != null)
            {
                var helper = round.Players.Where(p => p.Alive && !p.Injured).OrderBy(_ => rng.Next()).FirstOrDefault();
                if (helper != null)
                {
                    double r = rng.NextDouble();
                    if (r < 0.03) round.PlayerRescued(helper.Id, injured.Id);
                    else if (r < 0.04) round.PlayerLeftBehind(helper.Id, injured.Id);
                }
            }
            round.Tick(dt);
        }
    }

    static void RuleChecks(List<KeyValuePair<string, string>> roster)
    {
        var tornado = ContentLibrary.Disasters().First(d => d.Type == DisasterType.Tornado);
        var rules = new RoundRules { SharedMissionCount = 6, SecretMissions = true };
        var round = new RoundController(1, tornado, roster, ContentLibrary.Events(), rules, new Random(1));
        Check(round.Missions.Count == 6, "all six tornado missions when asked for six");

        int completed = 0;
        round.MissionCompleted += (p, m) => completed++;

        // radios: needs three
        round.ObjectActivated("a", ContentLibrary.Radios);
        round.ObjectActivated("a", ContentLibrary.Radios);
        Check(!round.Find("a").Completed.Contains("radios"), "two radios are not enough");
        round.ObjectActivated("a", ContentLibrary.Radios);
        Check(round.Find("a").Completed.Contains("radios"), "three radios complete the mission");
        int spAfterRadios = round.Find("a").Sp;
        round.ObjectActivated("a", ContentLibrary.Radios);
        Check(round.Find("a").Sp == spAfterRadios, "a mission pays only once");

        // bunker: 60 seconds
        for (int i = 0; i < 59; i++) round.PlayerInZone("b", ContentLibrary.Bunker, 1f);
        Check(!round.Find("b").Completed.Contains("bunker"), "59 s in the bunker are not enough");
        round.PlayerInZone("b", ContentLibrary.Bunker, 1f);
        Check(round.Find("b").Completed.Contains("bunker"), "60 s in the bunker complete the mission");

        // the emergency kit
        round.ItemDelivered("c", ContentLibrary.EmergencyKit);
        Check(round.Find("c").Sp == 300, "kit pays 300");

        // rescue: only works on injured players, then pays the mission once and a bonus after
        round.PlayerRescued("a", "b");
        Check(round.Find("a").Rescues == 0, "cannot rescue a healthy player");
        round.Find("b").Injured = true;
        round.PlayerLeftBehind("c", "b");
        Check(round.Find("c").LeftBehind == 1, "leaving someone behind is recorded");
        round.PlayerRescued("a", "b");
        Check(round.Find("a").Rescues == 1 && !round.Find("b").Injured, "rescue heals and counts");
        Check(round.Find("b").ReachedStationAt >= 0, "rescued player reached the station");
        int spBefore = round.Find("a").Sp;
        round.Find("c").Injured = true;
        round.PlayerRescued("a", "c");
        Check(round.Find("a").Sp == spBefore + rules.RepeatRescueBonus, "second rescue pays the bonus");

        // injured players cannot do missions
        round.Find("d").Injured = true;
        round.ItemDelivered("d", ContentLibrary.EmergencyKit);
        Check(!round.Find("d").Completed.Contains("kit"), "injured players cannot deliver");

        // last survivor
        round.PlayerEliminated("b", "was hit");
        round.PlayerEliminated("c", "was hit");
        round.PlayerEliminated("d", "was hit");
        RoundResult result = null;
        round.RoundEnded += r => result = r;
        while (!round.Finished) round.Tick(1f);
        Check(result.LastSurvivorId == "a", "alex is the last survivor");
        Check(round.Find("a").Completed.Contains("survive") && round.Find("a").Completed.Contains("last"), "survive and last survivor paid");
        Check(!round.Find("b").Completed.Contains("survive"), "dead players do not get survive");

        // an injured player dies when nobody helps in time
        var flood = ContentLibrary.Disasters().First(d => d.Type == DisasterType.Flood);
        var rescueOnly = ContentLibrary.Events().Where(e => e.Id == "rescue_call" || e.IsFinale).ToList();
        var r2 = new RoundController(1, flood, roster, rescueOnly, new RoundRules(), new Random(3));
        PlayerState victim = null;
        r2.PlayerInjured += p => victim = p;
        while (victim == null && !r2.Finished) r2.Tick(0.5f);
        Check(victim != null, "rescue event injures someone");
        float deadline = r2.Elapsed + 36f;
        while (r2.Elapsed < deadline && !r2.Finished) r2.Tick(0.5f);
        Check(victim != null && !victim.Alive, "unrescued player is lost when the event ends");

        // power failure flag is visible to the world while active
        var quake = ContentLibrary.Disasters().First(d => d.Type == DisasterType.Earthquake);
        var powerOnly = ContentLibrary.Events().Where(e => e.Id == "power" || e.IsFinale).ToList();
        var r3 = new RoundController(1, quake, roster, powerOnly, new RoundRules(), new Random(5));
        bool sawPower = false;
        while (!r3.Finished) { r3.Tick(0.5f); if (r3.IsActive(EventEffect.BunkerDoorsDisabled)) sawPower = true; }
        Check(sawPower, "power failure disables bunker doors");

        // story remembers earlier rounds
        var sm = new MatchSession(roster.Take(2), 2, seed: 1);
        var first = sm.StartNextRound();
        first.Find("b").Injured = true;
        first.PlayerRescued("a", "b");
        while (!first.Finished) first.Tick(5f);
        var second = sm.StartNextRound();
        second.Find("a").Injured = true;
        second.PlayerLeftBehind("b", "a");
        while (!second.Finished) second.Tick(5f);
        var story = sm.MatchStory();
        Console.WriteLine("\n=== Story check ===");
        foreach (var l in story) Console.WriteLine("   " + l);
        Check(story[1].Contains("even though Alex saved Ben in round 1"), "betrayal references the earlier rescue");
    }
}
