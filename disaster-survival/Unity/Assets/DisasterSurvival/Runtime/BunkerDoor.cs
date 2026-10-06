using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>
    /// A door that opens for nearby players. During a power failure it closes and stays shut,
    /// so whoever is inside the bunker is trapped and whoever is outside is locked out.
    /// </summary>
    public class BunkerDoor : MonoBehaviour
    {
        public Vector3 openOffset = new Vector3(0f, 3.2f, 0f);
        public float openRadius = 4f;
        public float speed = 4f;
        [Tooltip("Optional light or sign that turns on while the power is out.")]
        public GameObject powerOutIndicator;

        Vector3 _closed;

        void Awake() { _closed = transform.localPosition; }

        void Update()
        {
            var gm = DisasterGameManager.Instance;
            bool locked = gm != null && gm.IsActive(EventEffect.BunkerDoorsDisabled);
            bool someoneNear = false;
            if (!locked)
                foreach (var p in PlayerAgent.Players)
                    if (p.Alive && Vector3.Distance(p.transform.position, transform.position) <= openRadius) { someoneNear = true; break; }

            var target = someoneNear ? _closed + openOffset : _closed;
            transform.localPosition = Vector3.MoveTowards(transform.localPosition, target, speed * Time.deltaTime);
            if (powerOutIndicator != null) powerOutIndicator.SetActive(locked);
        }
    }
}
