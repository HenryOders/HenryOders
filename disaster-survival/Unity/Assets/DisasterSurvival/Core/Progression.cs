// Disaster Survival - long-term progression: survival rank and cosmetic unlocks.
// PlayerProfile only uses public fields, lists and arrays, so Unity's JsonUtility can save it.
using System;
using System.Collections.Generic;
using System.Linq;

namespace DisasterSurvival.Core
{
    [Serializable]
    public sealed class PlayerProfile
    {
        public string PlayerId = "";
        public string Rank = "Rookie";
        public int TotalSp;
        public int RoundsPlayed;
        public int RoundsSurvived;
        public int Rescues;
        public int LastSurvivorWins;
        public int SecretMissionsDone;
        public int MissionsCompleted;
        public int TimesLeftSomeoneBehind;
        public int[] SurvivedByType = new int[6];
        public List<string> Unlocked = new List<string>();

        public int SurvivedCount(DisasterType t)
        {
            Normalize();
            return SurvivedByType[(int)t];
        }

        public int DisasterTypesSurvived
        {
            get { Normalize(); return SurvivedByType.Count(n => n > 0); }
        }

        // Older saves may have a shorter array if new disasters were added
        public void Normalize()
        {
            int n = Enum.GetValues(typeof(DisasterType)).Length;
            if (SurvivedByType == null) SurvivedByType = new int[n];
            if (SurvivedByType.Length < n)
            {
                var a = new int[n];
                Array.Copy(SurvivedByType, a, SurvivedByType.Length);
                SurvivedByType = a;
            }
            if (Unlocked == null) Unlocked = new List<string>();
        }
    }

    public sealed class ProgressionUpdate
    {
        public int SpGained;
        public string OldRank;
        public string NewRank;
        public bool RankUp => OldRank != NewRank;
        public List<UnlockDef> NewUnlocks = new List<UnlockDef>();
        public List<string> NextRankMissing = new List<string>();
    }

    public static class Progression
    {
        static readonly List<RankDef> DefaultRanks = ContentLibrary.Ranks();
        static readonly List<UnlockDef> DefaultUnlocks = ContentLibrary.Unlocks();

        /// <summary>Adds one finished round to the profile and returns rank-ups and new unlocks.</summary>
        public static ProgressionUpdate ApplyRound(PlayerProfile profile, RoundResult round,
                                                   List<RankDef> ranks = null, List<UnlockDef> unlocks = null)
        {
            ranks = ranks ?? DefaultRanks;
            unlocks = unlocks ?? DefaultUnlocks;
            profile.Normalize();

            var me = round.Players.FirstOrDefault(p => p.Id == profile.PlayerId);
            var update = new ProgressionUpdate { OldRank = profile.Rank };
            if (me == null) { update.NewRank = profile.Rank; return update; }

            profile.RoundsPlayed++;
            profile.TotalSp += me.Sp;
            profile.Rescues += me.Rescues;
            profile.TimesLeftSomeoneBehind += me.LeftBehind;
            profile.MissionsCompleted += me.Completed.Count;
            if (me.Alive)
            {
                profile.RoundsSurvived++;
                profile.SurvivedByType[(int)round.Disaster.Type]++;
            }
            if (round.LastSurvivorId == me.Id) profile.LastSurvivorWins++;
            if (me.Secret != null && me.Secret.Done) profile.SecretMissionsDone++;

            update.SpGained = me.Sp;
            profile.Rank = RankFor(profile, ranks).Name;
            update.NewRank = profile.Rank;

            int rankIndex = ranks.FindIndex(r => r.Name == profile.Rank);
            foreach (var u in unlocks)
            {
                if (profile.Unlocked.Contains(u.Id)) continue;
                bool byRank = u.RequiredRank != null && ranks.FindIndex(r => r.Name == u.RequiredRank) <= rankIndex;
                bool byMilestone = u.Milestone != null && u.Milestone(profile);
                if (byRank || byMilestone)
                {
                    profile.Unlocked.Add(u.Id);
                    update.NewUnlocks.Add(u);
                }
            }

            update.NextRankMissing = MissingForNextRank(profile, ranks);
            return update;
        }

        public static RankDef RankFor(PlayerProfile p, List<RankDef> ranks = null)
        {
            ranks = ranks ?? DefaultRanks;
            var best = ranks[0];
            foreach (var r in ranks)
                if (Meets(p, r)) best = r; else break;
            return best;
        }

        public static bool Meets(PlayerProfile p, RankDef r) =>
            p.TotalSp >= r.MinSp && p.Rescues >= r.MinRescues && p.LastSurvivorWins >= r.MinLastSurvivor &&
            p.SecretMissionsDone >= r.MinSecretMissions && p.DisasterTypesSurvived >= r.MinDisasterTypes;

        /// <summary>What is still missing for the next rank, as short readable lines.</summary>
        public static List<string> MissingForNextRank(PlayerProfile p, List<RankDef> ranks = null)
        {
            ranks = ranks ?? DefaultRanks;
            int i = ranks.FindIndex(r => r.Name == RankFor(p, ranks).Name);
            var lines = new List<string>();
            if (i < 0 || i + 1 >= ranks.Count) return lines;
            var next = ranks[i + 1];
            lines.Add($"Next rank: {next.Name}");
            if (p.TotalSp < next.MinSp) lines.Add($"{next.MinSp - p.TotalSp} more SP");
            if (p.Rescues < next.MinRescues) lines.Add($"{next.MinRescues - p.Rescues} more rescues");
            if (p.LastSurvivorWins < next.MinLastSurvivor) lines.Add($"{next.MinLastSurvivor - p.LastSurvivorWins} more times last survivor");
            if (p.SecretMissionsDone < next.MinSecretMissions) lines.Add($"{next.MinSecretMissions - p.SecretMissionsDone} more secret missions");
            if (p.DisasterTypesSurvived < next.MinDisasterTypes) lines.Add($"survive {next.MinDisasterTypes - p.DisasterTypesSurvived} more kinds of disaster");
            return lines;
        }
    }
}
