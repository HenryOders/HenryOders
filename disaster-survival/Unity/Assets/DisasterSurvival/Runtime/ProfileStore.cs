using System.IO;
using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>Saves player profiles as JSON files in Application.persistentDataPath.</summary>
    public static class ProfileStore
    {
        static string PathFor(string playerId) =>
            Path.Combine(Application.persistentDataPath, $"disaster_profile_{playerId}.json");

        public static PlayerProfile Load(string playerId)
        {
            try
            {
                var path = PathFor(playerId);
                if (File.Exists(path))
                {
                    var p = JsonUtility.FromJson<PlayerProfile>(File.ReadAllText(path));
                    if (p != null) { p.PlayerId = playerId; p.Normalize(); return p; }
                }
            }
            catch (System.Exception e) { Debug.LogWarning("Could not read profile: " + e.Message); }
            return new PlayerProfile { PlayerId = playerId };
        }

        public static void Save(PlayerProfile profile)
        {
            try { File.WriteAllText(PathFor(profile.PlayerId), JsonUtility.ToJson(profile, true)); }
            catch (System.Exception e) { Debug.LogWarning("Could not save profile: " + e.Message); }
        }
    }
}
