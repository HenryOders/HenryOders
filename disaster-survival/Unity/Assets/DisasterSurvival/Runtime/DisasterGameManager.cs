using System;
using System.Collections.Generic;
using System.Linq;
using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>
    /// Runs the match: countdown, rounds, events, recap, progression.
    /// The world components (zones, radios, hazards) report to this manager,
    /// the manager reports to the rules in DisasterSurvival.Core.
    /// For online play run this on the host/server only and replicate the results.
    /// </summary>
    public class DisasterGameManager : MonoBehaviour
    {
        public static DisasterGameManager Instance { get; private set; }

        public enum Stage { Waiting, Countdown, Playing, Recap, MatchOver }

        [Header("Match")]
        public int roundsPerMatch = 4;
        public float countdownSeconds = 5f;
        public float recapSeconds = 12f;
        public bool autoStart = true;
        [Tooltip("0 = random every match")]
        public int seed = 0;

        [Header("Round rules")]
        public int sharedMissions = 3;
        public bool secretMissions = true;
        public float minEventGap = 30f;
        public float maxEventGap = 60f;
        public bool injuredDieIfNotRescued = true;

        [Header("World")]
        public Transform[] spawnPoints;
        [Tooltip("Where rescued players are placed when they are dropped at the rescue station.")]
        public Transform rescueDropPoint;
        [Tooltip("A healthy player who was this close to an injured player and then runs to the rescue station alone has left them behind.")]
        public float abandonRadius = 8f;
        public float abandonMemorySeconds = 20f;

        public MatchSession Session { get; private set; }
        public RoundController Round => Session?.Current;
        public Stage CurrentStage { get; private set; } = Stage.Waiting;
        public float StageTimeLeft { get; private set; }
        public List<string> LastRecap { get; private set; } = new List<string>();
        public Dictionary<string, ProgressionUpdate> LastProgress { get; } = new Dictionary<string, ProgressionUpdate>();

        // Hooks for world components and UI
        public static event Action<RoundController> RoundStarted;
        public static event Action<RoundResult> RoundFinished;
        public static event Action<ActiveEvent> EventStarted;
        public static event Action<ActiveEvent> EventEnded;
        public static event Action<string> Announcement;
        public static event Action<PlayerAgent, MissionDef> MissionCompleted;

        readonly Dictionary<string, float> _lastNear = new Dictionary<string, float>();

        void Awake()
        {
            if (Instance != null && Instance != this) { Destroy(gameObject); return; }
            Instance = this;
        }

        void OnDestroy() { if (Instance == this) Instance = null; }

        void Start() { if (autoStart) StartMatch(); }

        public PlayerAgent Agent(string id) => PlayerAgent.Players.FirstOrDefault(p => p.playerId == id);
        public PlayerAgent LocalPlayer => PlayerAgent.Players.FirstOrDefault(p => p.isLocalPlayer);
        public PlayerState StateOf(PlayerAgent a) => a == null ? null : Round?.Find(a.playerId);

        public void StartMatch()
        {
            var roster = PlayerAgent.Players.Select(p => new KeyValuePair<string, string>(p.playerId, p.displayName)).ToList();
            var rules = new RoundRules
            {
                SharedMissionCount = sharedMissions,
                SecretMissions = secretMissions,
                MinEventGap = minEventGap,
                MaxEventGap = maxEventGap,
                InjuredDieIfNotRescued = injuredDieIfNotRescued,
            };
            Session = new MatchSession(roster, roundsPerMatch, rules, seed == 0 ? (int?)null : seed);
            Session.RoundStarted += OnRoundStarted;
            Session.RoundFinished += OnRoundFinished;
            SetStage(Stage.Countdown, countdownSeconds);
        }

        void SetStage(Stage s, float seconds)
        {
            CurrentStage = s;
            StageTimeLeft = seconds;
        }

        void Update()
        {
            switch (CurrentStage)
            {
                case Stage.Countdown:
                    StageTimeLeft -= Time.deltaTime;
                    if (StageTimeLeft <= 0f) StartRound();
                    break;
                case Stage.Playing:
                    TrackProximity();
                    Round.Tick(Time.deltaTime);
                    break;
                case Stage.Recap:
                    StageTimeLeft -= Time.deltaTime;
                    if (StageTimeLeft <= 0f)
                    {
                        if (Session.Finished) SetStage(Stage.MatchOver, 0f);
                        else SetStage(Stage.Countdown, countdownSeconds);
                    }
                    break;
            }
        }

        void StartRound()
        {
            _lastNear.Clear();
            var spawns = spawnPoints != null && spawnPoints.Length > 0 ? spawnPoints : new[] { transform };
            int i = 0;
            foreach (var p in PlayerAgent.Players.ToList())
            {
                var sp = spawns[i++ % spawns.Length];
                p.Respawn(sp.position + Vector3.up * 0.1f, sp.rotation);
            }
            Session.StartNextRound();   // fires OnRoundStarted
            SetStage(Stage.Playing, 0f);
        }

        void OnRoundStarted(RoundController round)
        {
            round.Announced += t => Announcement?.Invoke(t);
            round.EventStarted += e => EventStarted?.Invoke(e);
            round.EventEnded += e => EventEnded?.Invoke(e);
            round.PlayerInjured += s => Agent(s.Id)?.SetInjured(true);
            round.PlayerDied += s => Agent(s.Id)?.Kill();
            round.MissionCompleted += (s, m) => MissionCompleted?.Invoke(Agent(s.Id), m);

            foreach (var d in FindObjectsByType<DisasterSpecific>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                d.Apply(round.Disaster.Type);

            Announcement?.Invoke(round.Disaster.Intro);
            RoundStarted?.Invoke(round);
        }

        void OnRoundFinished(RoundResult result)
        {
            LastRecap = Session.RoundRecap(result);
            LastProgress.Clear();
            foreach (var agent in PlayerAgent.Players.Where(p => p.isLocalPlayer))
            {
                var profile = ProfileStore.Load(agent.playerId);
                LastProgress[agent.playerId] = Progression.ApplyRound(profile, result);
                ProfileStore.Save(profile);
            }
            foreach (var d in FindObjectsByType<DisasterSpecific>(FindObjectsInactive.Include, FindObjectsSortMode.None))
                d.Apply(null);

            SetStage(Stage.Recap, recapSeconds);
            RoundFinished?.Invoke(result);
        }

        // ------------------------------------------------------------ reports from the world

        public void ReportZoneEnter(PlayerAgent p, string zoneId)
        {
            if (!Playing(p)) return;
            Round.PlayerReachedZone(p.playerId, zoneId);
            if (zoneId == ContentLibrary.RescueStation) CheckLeftBehind(p);
        }

        public void ReportZoneStay(PlayerAgent p, string zoneId, float dt)
        {
            if (Playing(p)) Round.PlayerInZone(p.playerId, zoneId, dt);
        }

        public void ReportActivated(PlayerAgent p, string groupId)
        {
            if (Playing(p)) Round.ObjectActivated(p.playerId, groupId);
        }

        public void ReportDelivered(PlayerAgent p, string itemId)
        {
            if (Playing(p)) Round.ItemDelivered(p.playerId, itemId);
        }

        public void ReportRescue(PlayerAgent rescuer, PlayerAgent injured)
        {
            if (!Playing(rescuer) || injured == null) return;
            Round.PlayerRescued(rescuer.playerId, injured.playerId);
            var drop = rescueDropPoint != null ? rescueDropPoint.position : rescuer.transform.position + rescuer.transform.forward * 1.5f;
            injured.ReleaseFromCarrier(drop);
            injured.SetInjured(false);
        }

        public void ReportBonus(PlayerAgent p, int sp, string reason)
        {
            if (Playing(p)) Round.AwardBonus(p.playerId, sp, reason);
        }

        public void ReportDeath(PlayerAgent p, string cause)
        {
            if (CurrentStage != Stage.Playing || p == null || !p.Alive) return;
            Round.PlayerEliminated(p.playerId, cause);
        }

        public bool IsActive(EventEffect effect) => CurrentStage == Stage.Playing && Round != null && Round.IsActive(effect);

        bool Playing(PlayerAgent p) => CurrentStage == Stage.Playing && p != null && p.Alive && !p.Injured;

        // ------------------------------------------------------------ left behind

        void TrackProximity()
        {
            float now = Time.time;
            foreach (var injured in PlayerAgent.Players)
            {
                if (!injured.Alive || !injured.Injured || injured.CarriedBy != null) continue;
                foreach (var other in PlayerAgent.Players)
                {
                    if (other == injured || !other.Alive || other.Injured) continue;
                    if (Vector3.Distance(other.transform.position, injured.transform.position) <= abandonRadius)
                        _lastNear[other.playerId + "|" + injured.playerId] = now;
                }
            }
        }

        // Reaching safety alone while someone you just passed is still lying there
        void CheckLeftBehind(PlayerAgent p)
        {
            if (p.CarriedPlayer != null) return;
            foreach (var injured in PlayerAgent.Players)
            {
                if (injured == p || !injured.Alive || !injured.Injured) continue;
                if (_lastNear.TryGetValue(p.playerId + "|" + injured.playerId, out var t) && Time.time - t <= abandonMemorySeconds)
                    Round.PlayerLeftBehind(p.playerId, injured.playerId);
            }
        }
    }
}
