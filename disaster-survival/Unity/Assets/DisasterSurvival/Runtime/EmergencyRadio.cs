using System.Collections.Generic;
using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>Emergency radio (or any switch). Every player can use each radio once per round.</summary>
    public class EmergencyRadio : DSInteractable
    {
        public string groupId = ContentLibrary.Radios;
        [Tooltip("Optional: shown while this radio still has a free use for the local player.")]
        public GameObject idleIndicator;
        [Tooltip("Optional: shown once the local player used it.")]
        public GameObject usedIndicator;

        readonly HashSet<string> _usedBy = new HashSet<string>();

        protected override void OnEnable()
        {
            base.OnEnable();
            DisasterGameManager.RoundStarted += OnRoundStarted;
            Refresh();
        }

        protected override void OnDisable()
        {
            base.OnDisable();
            DisasterGameManager.RoundStarted -= OnRoundStarted;
        }

        void OnRoundStarted(RoundController r) { _usedBy.Clear(); Refresh(); }

        public override bool CanInteract(PlayerAgent by) => by.Alive && !by.Injured && !_usedBy.Contains(by.playerId);

        public override void Interact(PlayerAgent by)
        {
            if (!CanInteract(by)) return;
            _usedBy.Add(by.playerId);
            DisasterGameManager.Instance?.ReportActivated(by, groupId);
            Refresh();
        }

        public override string Prompt(PlayerAgent by) => "Activate emergency radio";

        void Refresh()
        {
            var local = DisasterGameManager.Instance != null ? DisasterGameManager.Instance.LocalPlayer : null;
            bool used = local != null && _usedBy.Contains(local.playerId);
            if (idleIndicator != null) idleIndicator.SetActive(!used);
            if (usedIndicator != null) usedIndicator.SetActive(used);
        }
    }
}
