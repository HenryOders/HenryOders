using System.Collections.Generic;
using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>Drops a supply crate from the sky during a "SupplyDrop" event.</summary>
    public class SupplyDrop : MonoBehaviour
    {
        [Tooltip("A crate with a SupplyCrate component (and ideally a Rigidbody).")]
        public SupplyCrate cratePrefab;
        public Transform areaCenter;
        public float areaRadius = 40f;
        public float dropHeight = 40f;

        readonly List<GameObject> _spawned = new List<GameObject>();

        void OnEnable()
        {
            DisasterGameManager.EventStarted += OnEvent;
            DisasterGameManager.RoundStarted += OnRoundStarted;
        }

        void OnDisable()
        {
            DisasterGameManager.EventStarted -= OnEvent;
            DisasterGameManager.RoundStarted -= OnRoundStarted;
        }

        void OnRoundStarted(RoundController r)
        {
            foreach (var g in _spawned) if (g != null) Destroy(g);
            _spawned.Clear();
        }

        void OnEvent(ActiveEvent e)
        {
            if ((e.Def.Effects & EventEffect.SupplyDrop) == 0 || cratePrefab == null) return;
            var c = areaCenter != null ? areaCenter.position : transform.position;
            var r = Random.insideUnitCircle * areaRadius;
            var crate = Instantiate(cratePrefab, c + new Vector3(r.x, dropHeight, r.y), Quaternion.Euler(0f, Random.Range(0f, 360f), 0f));
            crate.gameObject.SetActive(true);
            _spawned.Add(crate.gameObject);
        }
    }
}
