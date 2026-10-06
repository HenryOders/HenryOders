using System.Collections.Generic;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>Anything a player can use with the interact key (E / gamepad X).</summary>
    public abstract class DSInteractable : MonoBehaviour
    {
        public static readonly List<DSInteractable> All = new List<DSInteractable>();

        protected virtual void OnEnable() { All.Add(this); }
        protected virtual void OnDisable() { All.Remove(this); }

        public abstract bool CanInteract(PlayerAgent by);
        public abstract void Interact(PlayerAgent by);
        public abstract string Prompt(PlayerAgent by);

        public virtual Vector3 InteractPoint => transform.position;
    }
}
