using System.Collections.Generic;
using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>
    /// A trigger area: rescue station, bunker, rooftop ... Needs a Collider with "Is Trigger".
    /// The rescue station also accepts carried items and injured players.
    /// </summary>
    [RequireComponent(typeof(Collider))]
    public class MissionZone : MonoBehaviour
    {
        [Tooltip("rescue_station, bunker, rooftop or your own id")]
        public string zoneId = ContentLibrary.RescueStation;
        [Tooltip("Carried items with one of these ids are delivered here.")]
        public string[] acceptsItems = { ContentLibrary.EmergencyKit };
        [Tooltip("Injured players carried in here count as rescued.")]
        public bool acceptsInjured = true;

        readonly HashSet<PlayerAgent> _inside = new HashSet<PlayerAgent>();

        void Reset()
        {
            GetComponent<Collider>().isTrigger = true;
        }

        void OnTriggerEnter(Collider other)
        {
            var p = other.GetComponentInParent<PlayerAgent>();
            if (p == null || p.CarriedBy != null || !_inside.Add(p)) return;
            var gm = DisasterGameManager.Instance;
            if (gm == null) return;

            if (p.CarriedItem != null && System.Array.IndexOf(acceptsItems, p.CarriedItem.itemId) >= 0)
            {
                var item = p.TakeCarriedItem();
                gm.ReportDelivered(p, item.itemId);
                item.Deliver();
            }
            if (acceptsInjured && p.CarriedPlayer != null)
                gm.ReportRescue(p, p.TakeCarriedPlayer());

            gm.ReportZoneEnter(p, zoneId);
        }

        void OnTriggerStay(Collider other)
        {
            var p = other.GetComponentInParent<PlayerAgent>();
            if (p != null && _inside.Contains(p)) DisasterGameManager.Instance?.ReportZoneStay(p, zoneId, Time.fixedDeltaTime);
        }

        void OnTriggerExit(Collider other)
        {
            var p = other.GetComponentInParent<PlayerAgent>();
            if (p != null) _inside.Remove(p);
        }

        void OnDisable() { _inside.Clear(); }
    }
}
