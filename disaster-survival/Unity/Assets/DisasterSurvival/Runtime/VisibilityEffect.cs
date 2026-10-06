using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>Thick fog during "LowVisibility" events (smoke, snow, ash). Uses the scene fog.</summary>
    public class VisibilityEffect : MonoBehaviour
    {
        public Color fogColor = new Color(0.55f, 0.55f, 0.58f);
        public float normalDensity = 0.002f;
        public float lowVisibilityDensity = 0.06f;
        [Tooltip("Base fog for a blizzard round.")]
        public float blizzardDensity = 0.02f;
        public float fadeSpeed = 0.03f;

        float _base;

        void OnEnable() { DisasterGameManager.RoundStarted += OnRoundStarted; }
        void OnDisable() { DisasterGameManager.RoundStarted -= OnRoundStarted; }

        void Start()
        {
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogColor = fogColor;
            RenderSettings.fogDensity = normalDensity;
            _base = normalDensity;
        }

        void OnRoundStarted(RoundController r)
        {
            _base = r.Disaster.Type == DisasterType.Blizzard ? blizzardDensity : normalDensity;
        }

        void Update()
        {
            var gm = DisasterGameManager.Instance;
            float target = gm != null && gm.IsActive(EventEffect.LowVisibility) ? lowVisibilityDensity : _base;
            RenderSettings.fogDensity = Mathf.MoveTowards(RenderSettings.fogDensity, target, fadeSpeed * Time.deltaTime);
        }
    }
}
