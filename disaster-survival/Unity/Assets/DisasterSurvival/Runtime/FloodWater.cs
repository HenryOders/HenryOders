using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>
    /// Water (or lava) that rises during "WaterRising" events and partly drains afterwards.
    /// Put it on a large flat object; its top surface is the water level.
    /// Players whose head is below the surface for too long drown.
    /// </summary>
    public class FloodWater : MonoBehaviour
    {
        public float baseLevel = -1f;
        public float floodLevel = 2.5f;
        [Tooltip("Level after a flood wave, so every wave leaves the map a bit wetter.")]
        public float afterWaveRise = 0.4f;
        public float riseSpeed = 0.35f;
        public float drainSpeed = 0.15f;
        [Tooltip("Rise slowly all round long (good for lava).")]
        public float constantRisePerMinute = 0f;
        public float headHeight = 1.6f;
        public float secondsToDrown = 4f;
        public string cause = "drowned";

        float _rest;
        readonly System.Collections.Generic.Dictionary<PlayerAgent, float> _under = new System.Collections.Generic.Dictionary<PlayerAgent, float>();

        public float Level => transform.position.y + transform.lossyScale.y * 0.5f;

        void OnEnable()
        {
            DisasterGameManager.RoundStarted += OnRoundStarted;
            DisasterGameManager.EventEnded += OnEventEnded;
            ResetLevel();
        }

        void OnDisable()
        {
            DisasterGameManager.RoundStarted -= OnRoundStarted;
            DisasterGameManager.EventEnded -= OnEventEnded;
        }

        void OnRoundStarted(RoundController r) { ResetLevel(); }

        void OnEventEnded(ActiveEvent e)
        {
            if ((e.Def.Effects & EventEffect.WaterRising) != 0) _rest = Mathf.Min(floodLevel, _rest + afterWaveRise);
        }

        void ResetLevel()
        {
            _rest = baseLevel;
            _under.Clear();
            SetLevel(baseLevel);
        }

        void SetLevel(float level)
        {
            var p = transform.position;
            transform.position = new Vector3(p.x, level - transform.lossyScale.y * 0.5f, p.z);
        }

        void Update()
        {
            var gm = DisasterGameManager.Instance;
            if (gm == null || gm.CurrentStage != DisasterGameManager.Stage.Playing) return;

            _rest = Mathf.Min(floodLevel, _rest + constantRisePerMinute / 60f * Time.deltaTime);
            bool rising = gm.IsActive(EventEffect.WaterRising);
            float target = rising ? floodLevel : _rest;
            float speed = target > Level ? riseSpeed : drainSpeed;
            SetLevel(Mathf.MoveTowards(Level, target, speed * Time.deltaTime));

            foreach (var p in PlayerAgent.Players)
            {
                if (!p.Alive || p.CarriedBy != null) { _under.Remove(p); continue; }
                bool under = p.transform.position.y + headHeight < Level;
                if (!under) { _under.Remove(p); continue; }
                _under[p] = (_under.TryGetValue(p, out var t) ? t : 0f) + Time.deltaTime;
                if (_under[p] >= secondsToDrown) { _under.Remove(p); gm.ReportDeath(p, cause); }
            }
        }
    }
}
