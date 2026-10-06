using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>First player to open the crate gets bonus points. Hook "On Opened" up to give real gear.</summary>
    public class SupplyCrate : DSInteractable
    {
        public int bonusSp = 150;
        public UnityEngine.Events.UnityEvent<PlayerAgent> onOpened;

        bool _opened;

        public override bool CanInteract(PlayerAgent by) => !_opened && by.Alive && !by.Injured;

        public override void Interact(PlayerAgent by)
        {
            if (!CanInteract(by)) return;
            _opened = true;
            DisasterGameManager.Instance?.ReportBonus(by, bonusSp, "opened a supply crate");
            onOpened?.Invoke(by);
            Destroy(gameObject, 0.1f);
        }

        public override string Prompt(PlayerAgent by) => "Open supply crate";
    }
}
