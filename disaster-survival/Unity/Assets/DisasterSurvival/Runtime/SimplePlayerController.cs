using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>
    /// Basic third-person controller for testing (WASD / left stick, mouse / right stick, Space jump, Shift sprint).
    /// Swap it for your own controller or the Unity Starter Assets later.
    /// </summary>
    [RequireComponent(typeof(CharacterController))]
    public class SimplePlayerController : MonoBehaviour
    {
        public Transform cameraPivot;
        public float walkSpeed = 6f;
        public float sprintSpeed = 10f;
        public float jumpHeight = 1.4f;
        public float gravity = -20f;
        public float lookSensitivity = 2f;
        public bool lockCursor = true;

        CharacterController _cc;
        float _yaw, _pitch = 15f, _vy;

        void Awake()
        {
            _cc = GetComponent<CharacterController>();
            _yaw = transform.eulerAngles.y;
        }

        void OnEnable()
        {
            if (lockCursor) { Cursor.lockState = CursorLockMode.Locked; Cursor.visible = false; }
        }

        void Update()
        {
            if (!_cc.enabled) return;
            var look = DSInput.Look() * lookSensitivity;
            _yaw += look.x;
            _pitch = Mathf.Clamp(_pitch - look.y, -30f, 70f);
            if (cameraPivot != null) cameraPivot.rotation = Quaternion.Euler(_pitch, _yaw, 0f);

            var input = DSInput.Move();
            var forward = Quaternion.Euler(0f, _yaw, 0f) * Vector3.forward;
            var right = Quaternion.Euler(0f, _yaw, 0f) * Vector3.right;
            var move = (forward * input.y + right * input.x) * (DSInput.SprintHeld() ? sprintSpeed : walkSpeed);
            if (move.sqrMagnitude > 0.01f)
                transform.rotation = Quaternion.Slerp(transform.rotation, Quaternion.LookRotation(move), 12f * Time.deltaTime);

            if (_cc.isGrounded)
            {
                _vy = -2f;
                if (DSInput.JumpPressed()) _vy = Mathf.Sqrt(jumpHeight * -2f * gravity);
            }
            _vy += gravity * Time.deltaTime;
            move.y = _vy;
            _cc.Move(move * Time.deltaTime);
        }
    }
}
