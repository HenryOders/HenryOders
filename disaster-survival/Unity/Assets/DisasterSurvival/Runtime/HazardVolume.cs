using System.Collections.Generic;
using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>
    /// A deadly area: tornado funnel, fire, lava, a building that collapses during an aftershock.
    /// Needs a trigger collider. Players inside for longer than "Seconds To Kill" are out.
    /// </summary>
    [RequireComponent(typeof(Collider))]
    public class HazardVolume : MonoBehaviour
    {
        public string cause = "was caught by the storm";
        public float secondsToKill = 1.5f;
        [Tooltip("None = deadly all round long. Otherwise only while an event with this effect runs (e.g. GroundShaking).")]
        public EventEffect onlyDuring = EventEffect.None;
        [Tooltip("Optional: shown only while the hazard is deadly (warning glow, debris ...).")]
        public GameObject activeVisual;

        readonly Dictionary<PlayerAgent, float> _time = new Dictionary<PlayerAgent, float>();

        void Reset() { GetComponent<Collider>().isTrigger = true; }

        bool Deadly
        {
            get
            {
                var gm = DisasterGameManager.Instance;
                if (gm == null || gm.CurrentStage != DisasterGameManager.Stage.Playing) return false;
                return onlyDuring == EventEffect.None || gm.IsActive(onlyDuring);
            }
        }

        void Update()
        {
            if (activeVisual != null) activeVisual.SetActive(Deadly);
        }

        void OnTriggerStay(Collider other)
        {
            var p = other.GetComponentInParent<PlayerAgent>();
            if (p == null || !p.Alive || p.CarriedBy != null) return;
            if (!Deadly) { _time.Remove(p); return; }
            _time[p] = (_time.TryGetValue(p, out var t) ? t : 0f) + Time.fixedDeltaTime;
            if (_time[p] >= secondsToKill)
            {
                _time.Remove(p);
                DisasterGameManager.Instance.ReportDeath(p, cause);
            }
        }

        void OnTriggerExit(Collider other)
        {
            var p = other.GetComponentInParent<PlayerAgent>();
            if (p != null) _time.Remove(p);
        }
    }
}
