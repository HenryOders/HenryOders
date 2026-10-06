using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>Shows this object only during certain disasters (e.g. the tornado, the lava).</summary>
    public class DisasterSpecific : MonoBehaviour
    {
        public DisasterType[] activeDuring = { DisasterType.Tornado };
        [Tooltip("Visible between rounds as well.")]
        public bool showBetweenRounds = false;

        public void Apply(DisasterType? current)
        {
            bool on = current.HasValue ? System.Array.IndexOf(activeDuring, current.Value) >= 0 : showBetweenRounds;
            gameObject.SetActive(on);
        }
    }
}
