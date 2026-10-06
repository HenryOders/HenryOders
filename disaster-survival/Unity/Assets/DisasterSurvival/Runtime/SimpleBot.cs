using System.Linq;
using DisasterSurvival.Core;
using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>
    /// A simple bot for solo testing. Walks straight to goals with a CharacterController (no NavMesh needed):
    /// radios, the emergency kit, the bunker, the rooftop - and injured players, whom it either rescues or ignores.
    /// </summary>
    [RequireComponent(typeof(CharacterController), typeof(PlayerAgent))]
    public class SimpleBot : MonoBehaviour
    {
        [Range(0f, 1f)] public float helpfulness = 0.6f;
        public float speed = 5f;
        public float rethinkSeconds = 6f;
        public float gravity = -20f;

        CharacterController _cc;
        PlayerAgent _me;
        Vector3 _goal;
        Component _goalThing;
        float _rethink, _vy, _stuck;
        Vector3 _lastPos;
        PlayerAgent _ignoring;

        void Awake()
        {
            _cc = GetComponent<CharacterController>();
            _me = GetComponent<PlayerAgent>();
            _me.isLocalPlayer = false;
        }

        void Update()
        {
            if (!_cc.enabled) return;
            var gm = DisasterGameManager.Instance;
            bool playing = gm != null && gm.CurrentStage == DisasterGameManager.Stage.Playing && _me.Alive && !_me.Injured;

            _rethink -= Time.deltaTime;
            if (playing && (_rethink <= 0f || _goalThing == null || ReachedGoal())) Think(gm);

            Vector3 move = Vector3.zero;
            if (playing)
            {
                var to = _goal - transform.position;
                to.y = 0f;
                if (to.magnitude > 1.2f)
                {
                    move = to.normalized * speed;
                    transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(to), 8f * Time.deltaTime);
                }
                else _me.TryInteract();
            }

            // Hop over small obstacles when stuck
            _stuck = (transform.position - _lastPos).sqrMagnitude < 0.0004f && move != Vector3.zero ? _stuck + Time.deltaTime : 0f;
            _lastPos = transform.position;
            if (_cc.isGrounded)
            {
                _vy = -2f;
                if (_stuck > 0.6f) { _vy = 7f; _stuck = 0f; _rethink = 0f; }
            }
            _vy += gravity * Time.deltaTime;
            move.y = _vy;
            _cc.Move(move * Time.deltaTime);
        }

        bool ReachedGoal() => Vector3.Distance(new Vector3(_goal.x, transform.position.y, _goal.z), transform.position) < 1.3f;

        void Think(DisasterGameManager gm)
        {
            _rethink = rethinkSeconds * Random.Range(0.7f, 1.3f);
            var station = FindObjectsByType<MissionZone>(FindObjectsSortMode.None).FirstOrDefault(z => z.zoneId == ContentLibrary.RescueStation);

            // Carrying something: bring it home
            if ((_me.CarriedPlayer != null || _me.CarriedItem != null) && station != null) { SetGoal(station); return; }

            // Someone is hurt: help - or decide not to
            var injured = PlayerAgent.Players.FirstOrDefault(p => p != _me && p.Alive && p.Injured && p.CarriedBy == null);
            if (injured != null && injured != _ignoring)
            {
                if (Random.value < helpfulness) { SetGoal(injured); return; }
                _ignoring = injured;   // walks past them; may count as leaving them behind
            }

            // Otherwise pick something useful to do
            var me = gm.StateOf(_me);
            var options = DSInteractable.All
                .Where(i => i != null && i.isActiveAndEnabled && !(i is PlayerAgent) && i.CanInteract(_me))
                .Cast<Component>().ToList();
            var zones = FindObjectsByType<MissionZone>(FindObjectsSortMode.None)
                .Where(z => me == null || !me.ZonesReached.Contains(z.zoneId) || z.zoneId == ContentLibrary.Bunker).Cast<Component>();
            options.AddRange(zones);
            if (options.Count > 0) SetGoal(options[Random.Range(0, options.Count)]);
        }

        void SetGoal(Component thing)
        {
            _goalThing = thing;
            var c = thing.GetComponent<Collider>();
            _goal = c != null ? c.bounds.center : thing.transform.position;
        }
    }
}
