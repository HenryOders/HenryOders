using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>Something you carry to a MissionZone, e.g. the emergency kit. Returns to its start each round.</summary>
    public class DeliveryItem : DSInteractable
    {
        public string itemId = ContentLibrary.EmergencyKit;

        Vector3 _home;
        Quaternion _homeRot;
        Transform _homeParent;
        bool _carried;
        Rigidbody _rb;
        Collider[] _colliders;

        void Awake()
        {
            _home = transform.position;
            _homeRot = transform.rotation;
            _homeParent = transform.parent;
            _rb = GetComponent<Rigidbody>();
            _colliders = GetComponentsInChildren<Collider>();
        }

        // Subscribed for the whole lifetime, because a delivered item is inactive until the next round
        void Start() { DisasterGameManager.RoundStarted += ResetItem; }
        void OnDestroy() { DisasterGameManager.RoundStarted -= ResetItem; }

        void ResetItem(RoundController r)
        {
            gameObject.SetActive(true);
            Detach(_home);
            transform.SetParent(_homeParent, true);
            transform.rotation = _homeRot;
        }

        public override bool CanInteract(PlayerAgent by) => !_carried && by.Alive && !by.Injured && !by.IsBusy;
        public override void Interact(PlayerAgent by) { if (CanInteract(by)) by.PickUp(this); }
        public override string Prompt(PlayerAgent by) => "Pick up emergency kit";

        internal void AttachTo(Transform point)
        {
            _carried = true;
            if (_rb != null) _rb.isKinematic = true;
            foreach (var c in _colliders) c.enabled = false;
            transform.SetParent(point, false);
            transform.localPosition = Vector3.zero;
            transform.localRotation = Quaternion.identity;
        }

        internal void Detach(Vector3 position)
        {
            _carried = false;
            transform.SetParent(null, true);
            transform.position = position;
            foreach (var c in _colliders) c.enabled = true;
            if (_rb != null) _rb.isKinematic = false;
        }

        internal void Deliver()
        {
            Detach(_home);
            gameObject.SetActive(false);   // comes back at the next round
        }
    }
}
