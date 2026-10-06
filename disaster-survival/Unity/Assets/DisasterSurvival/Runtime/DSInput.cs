using UnityEngine;

namespace DisasterSurvival
{
    /// <summary>Works with the new Input System package and with the old Input Manager.</summary>
    public static class DSInput
    {
        public static bool InteractPressed()
        {
#if ENABLE_INPUT_SYSTEM
            var k = UnityEngine.InputSystem.Keyboard.current;
            var g = UnityEngine.InputSystem.Gamepad.current;
            return (k != null && k.eKey.wasPressedThisFrame) || (g != null && g.buttonWest.wasPressedThisFrame);
#else
            return Input.GetKeyDown(KeyCode.E) || Input.GetKeyDown(KeyCode.JoystickButton2);
#endif
        }

        public static bool DropPressed()
        {
#if ENABLE_INPUT_SYSTEM
            var k = UnityEngine.InputSystem.Keyboard.current;
            var g = UnityEngine.InputSystem.Gamepad.current;
            return (k != null && k.gKey.wasPressedThisFrame) || (g != null && g.dpad.down.wasPressedThisFrame);
#else
            return Input.GetKeyDown(KeyCode.G);
#endif
        }

        public static bool JumpPressed()
        {
#if ENABLE_INPUT_SYSTEM
            var k = UnityEngine.InputSystem.Keyboard.current;
            var g = UnityEngine.InputSystem.Gamepad.current;
            return (k != null && k.spaceKey.wasPressedThisFrame) || (g != null && g.buttonSouth.wasPressedThisFrame);
#else
            return Input.GetKeyDown(KeyCode.Space) || Input.GetKeyDown(KeyCode.JoystickButton0);
#endif
        }

        public static bool SprintHeld()
        {
#if ENABLE_INPUT_SYSTEM
            var k = UnityEngine.InputSystem.Keyboard.current;
            var g = UnityEngine.InputSystem.Gamepad.current;
            return (k != null && k.leftShiftKey.isPressed) || (g != null && g.leftStickButton.isPressed);
#else
            return Input.GetKey(KeyCode.LeftShift);
#endif
        }

        public static Vector2 Move()
        {
#if ENABLE_INPUT_SYSTEM
            var k = UnityEngine.InputSystem.Keyboard.current;
            var g = UnityEngine.InputSystem.Gamepad.current;
            Vector2 v = g != null ? g.leftStick.ReadValue() : Vector2.zero;
            if (k != null)
            {
                if (k.wKey.isPressed) v.y += 1f;
                if (k.sKey.isPressed) v.y -= 1f;
                if (k.dKey.isPressed) v.x += 1f;
                if (k.aKey.isPressed) v.x -= 1f;
            }
            return Vector2.ClampMagnitude(v, 1f);
#else
            return Vector2.ClampMagnitude(new Vector2(Input.GetAxisRaw("Horizontal"), Input.GetAxisRaw("Vertical")), 1f);
#endif
        }

        public static Vector2 Look()
        {
#if ENABLE_INPUT_SYSTEM
            var m = UnityEngine.InputSystem.Mouse.current;
            var g = UnityEngine.InputSystem.Gamepad.current;
            Vector2 v = m != null ? m.delta.ReadValue() * 0.1f : Vector2.zero;
            if (g != null) v += g.rightStick.ReadValue() * 2.5f;
            return v;
#else
            return new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y"));
#endif
        }
    }
}
