using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>
    /// Moves a hazard (tornado, fire front, lava flow) around an area.
    /// On a "HazardMoves" event it turns toward a new spot and speeds up,
    /// preferably toward where most players are hiding.
    /// </summary>
    public class HazardMover : MonoBehaviour
    {
        public Transform areaCenter;
        public float areaRadius = 60f;
        public float speed = 4f;
        public float eventSpeedMultiplier = 2.2f;
        [Tooltip("Chance that a direction change heads for the biggest group of players.")]
        [Range(0f, 1f)] public float chasePlayers = 0.6f;
        public float spinDegreesPerSecond = 180f;

        Vector3 _target;
        Vector3 _start;

        void Awake() { _start = transform.position; }

        void OnEnable()
        {
            DisasterGameManager.RoundStarted += OnRoundStarted;
            DisasterGameManager.EventStarted += OnEvent;
            PickTarget(false);
        }

        void OnDisable()
        {
            DisasterGameManager.RoundStarted -= OnRoundStarted;
            DisasterGameManager.EventStarted -= OnEvent;
        }

        void OnRoundStarted(RoundController r) { transform.position = _start; PickTarget(false); }

        void OnEvent(ActiveEvent e)
        {
            if ((e.Def.Effects & EventEffect.HazardMoves) != 0) PickTarget(Random.value < chasePlayers);
        }

        void Update()
        {
            var gm = DisasterGameManager.Instance;
            if (gm == null || gm.CurrentStage != DisasterGameManager.Stage.Playing) return;
            float s = speed * (gm.IsActive(EventEffect.HazardMoves) ? eventSpeedMultiplier : 1f);
            var pos = transform.position;
            var flatTarget = new Vector3(_target.x, pos.y, _target.z);
            transform.position = Vector3.MoveTowards(pos, flatTarget, s * Time.deltaTime);
            transform.Rotate(0f, spinDegreesPerSecond * Time.deltaTime, 0f, Space.World);
            if (Vector3.Distance(transform.position, flatTarget) < 1f) PickTarget(false);
        }

        void PickTarget(bool towardPlayers)
        {
            var c = areaCenter != null ? areaCenter.position : _start;
            if (towardPlayers)
            {
                Vector3 sum = Vector3.zero;
                int n = 0;
                foreach (var p in PlayerAgent.Players)
                    if (p.Alive) { sum += p.transform.position; n++; }
                if (n > 0) { _target = sum / n; return; }
            }
            var r = Random.insideUnitCircle * areaRadius;
            _target = c + new Vector3(r.x, 0f, r.y);
        }
    }
}
