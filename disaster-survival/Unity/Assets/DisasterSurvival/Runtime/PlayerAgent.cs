using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Events;

namespace DisasterSurvival
{
    /// <summary>
    /// Connects a character to the round: alive, injured, carrying an item or another player.
    /// Put it on every player (human or bot). Movement stays in your own controller;
    /// list it in "Disable When Down" so injured or dead players cannot walk.
    /// </summary>
    [DisallowMultipleComponent]
    public class PlayerAgent : DSInteractable
    {
        public static readonly List<PlayerAgent> Players = new List<PlayerAgent>();

        [Header("Identity")]
        public string playerId = "";
        public string displayName = "Player";
        [Tooltip("Reads keyboard / gamepad input. Turn off for bots and remote players.")]
        public bool isLocalPlayer = true;

        [Header("Interaction")]
        public float interactRadius = 2.5f;
        [Tooltip("Where carried items and players are held. Defaults to above the head.")]
        public Transform carryPoint;
        [Tooltip("Scripts that are switched off while injured, carried or dead (e.g. your movement controller).")]
        public Behaviour[] disableWhenDown;
        [Tooltip("Renderers hidden while dead (spectating).")]
        public Renderer[] hideWhenDead;

        [Header("Events")]
        public UnityEvent onInjured;
        public UnityEvent onRescued;
        public UnityEvent onDied;
        public UnityEvent onRespawned;

        public bool Alive { get; private set; } = true;
        public bool Injured { get; private set; }
        public DeliveryItem CarriedItem { get; private set; }
        public PlayerAgent CarriedPlayer { get; private set; }
        public PlayerAgent CarriedBy { get; private set; }
        public bool IsBusy => CarriedItem != null || CarriedPlayer != null;

        CharacterController _cc;

        void Awake()
        {
            if (string.IsNullOrEmpty(playerId)) playerId = System.Guid.NewGuid().ToString("N").Substring(0, 8);
            _cc = GetComponent<CharacterController>();
            if (carryPoint == null)
            {
                var cp = new GameObject("CarryPoint").transform;
                cp.SetParent(transform, false);
                cp.localPosition = new Vector3(0f, 2.3f, 0f);
                carryPoint = cp;
            }
        }

        protected override void OnEnable() { base.OnEnable(); if (!Players.Contains(this)) Players.Add(this); }
        protected override void OnDisable() { base.OnDisable(); Players.Remove(this); }

        void Update()
        {
            if (!isLocalPlayer || !Alive || Injured) return;
            if (DSInput.InteractPressed()) TryInteract();
            if (DSInput.DropPressed()) DropCarried();
        }

        // ------------------------------------------------------------ interaction

        public DSInteractable FindInteractable()
        {
            DSInteractable best = null;
            float bestDist = interactRadius;
            foreach (var i in DSInteractable.All)
            {
                if (i == this || i == null || !i.isActiveAndEnabled) continue;
                float d = Vector3.Distance(transform.position, i.InteractPoint);
                if (d <= bestDist && i.CanInteract(this)) { best = i; bestDist = d; }
            }
            return best;
        }

        public bool TryInteract()
        {
            if (!Alive || Injured) return false;
            var target = FindInteractable();
            if (target == null) return false;
            target.Interact(this);
            return true;
        }

        public void PickUp(DeliveryItem item)
        {
            if (IsBusy || item == null) return;
            CarriedItem = item;
            item.AttachTo(carryPoint);
        }

        public void DropCarried()
        {
            if (CarriedItem != null)
            {
                CarriedItem.Detach(transform.position + transform.forward * 1.2f);
                CarriedItem = null;
            }
            if (CarriedPlayer != null)
            {
                var p = CarriedPlayer;
                CarriedPlayer = null;
                p.ReleaseFromCarrier(transform.position + transform.forward * 1.5f);
            }
        }

        /// <summary>Hands the carried item over to a drop zone. Returns the item that was carried.</summary>
        public DeliveryItem TakeCarriedItem()
        {
            var item = CarriedItem;
            CarriedItem = null;
            return item;
        }

        public PlayerAgent TakeCarriedPlayer()
        {
            var p = CarriedPlayer;
            CarriedPlayer = null;
            return p;
        }

        // An injured player is itself something you can interact with: pick them up
        public override bool CanInteract(PlayerAgent by) =>
            Alive && Injured && CarriedBy == null && by != this && by.Alive && !by.Injured && !by.IsBusy;

        public override void Interact(PlayerAgent by)
        {
            if (!CanInteract(by)) return;
            by.CarriedPlayer = this;
            CarriedBy = by;
            if (_cc != null) _cc.enabled = false;
            transform.SetParent(by.carryPoint, true);
            transform.localPosition = Vector3.zero;
            transform.localRotation = Quaternion.Euler(0f, 0f, 90f);
        }

        public override string Prompt(PlayerAgent by) => $"Carry {displayName}";

        internal void ReleaseFromCarrier(Vector3 position)
        {
            if (CarriedBy != null && CarriedBy.CarriedPlayer == this) CarriedBy.CarriedPlayer = null;
            CarriedBy = null;
            transform.SetParent(null, true);
            transform.SetPositionAndRotation(position, Quaternion.Euler(0f, transform.eulerAngles.y, 0f));
            if (_cc != null) _cc.enabled = true;
        }

        // ------------------------------------------------------------ state, set by the game manager

        internal void SetInjured(bool injured)
        {
            if (Injured == injured) return;
            Injured = injured;
            if (injured) { DropCarried(); onInjured?.Invoke(); }
            else onRescued?.Invoke();
            ApplyDownState();
        }

        internal void Kill()
        {
            if (!Alive) return;
            DropCarried();
            if (CarriedBy != null) ReleaseFromCarrier(transform.position);
            Alive = false;
            Injured = false;
            foreach (var r in hideWhenDead) if (r != null) r.enabled = false;
            ApplyDownState();
            onDied?.Invoke();
        }

        internal void Respawn(Vector3 position, Quaternion rotation)
        {
            DropCarried();
            if (CarriedBy != null) ReleaseFromCarrier(position);
            Alive = true;
            Injured = false;
            if (_cc != null) _cc.enabled = false;
            transform.SetParent(null, true);
            transform.SetPositionAndRotation(position, rotation);
            if (_cc != null) _cc.enabled = true;
            foreach (var r in hideWhenDead) if (r != null) r.enabled = true;
            ApplyDownState();
            onRespawned?.Invoke();
        }

        void ApplyDownState()
        {
            bool canMove = Alive && !Injured;
            foreach (var b in disableWhenDown) if (b != null) b.enabled = canMove;
        }
    }
}
