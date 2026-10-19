using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace SuruIHA
{
    // Hem yeni Input System hem eski Input Manager ile çalışan küçük giriş katmanı.
    public static class SwarmInput
    {
        public enum K { F, T, C, O, L, G, H, R, J, B, X, N, K, F1, F2, F3, Plus, Minus, Esc, Tab, W, A, S, D, Q, E, Shift, Alpha1 }

        public static Vector2 MouseDelta()
        {
#if ENABLE_INPUT_SYSTEM
            return Mouse.current != null ? Mouse.current.delta.ReadValue() * 0.05f : Vector2.zero;
#else
            return new Vector2(Input.GetAxis("Mouse X"), Input.GetAxis("Mouse Y"));
#endif
        }

        public static float Scroll()
        {
#if ENABLE_INPUT_SYSTEM
            return Mouse.current != null ? Mouse.current.scroll.ReadValue().y / 120f : 0f;
#else
            return Input.mouseScrollDelta.y;
#endif
        }

        public static bool MouseHeld(int button)
        {
#if ENABLE_INPUT_SYSTEM
            if (Mouse.current == null) return false;
            return button == 0 ? Mouse.current.leftButton.isPressed
                 : button == 1 ? Mouse.current.rightButton.isPressed
                 : Mouse.current.middleButton.isPressed;
#else
            return Input.GetMouseButton(button);
#endif
        }

        public static bool Down(K k) => Check(k, true) || (k == K.Plus && NumpadDown(true)) || (k == K.Minus && NumpadDown(false));

        // Sayısal tuş takımındaki + ve - de çalışsın
        static bool NumpadDown(bool plus)
        {
#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            return kb != null && (plus ? kb.numpadPlusKey : kb.numpadMinusKey).wasPressedThisFrame;
#else
            return Input.GetKeyDown(plus ? KeyCode.KeypadPlus : KeyCode.KeypadMinus);
#endif
        }
        public static bool Held(K k) => Check(k, false);

        // Rakam tuşları 1-9: basılan rakamı döndürür, yoksa -1
        public static int DigitDown()
        {
            for (int i = 1; i <= 9; i++)
            {
#if ENABLE_INPUT_SYSTEM
                if (Keyboard.current != null && Keyboard.current[(Key)((int)Key.Digit1 + i - 1)].wasPressedThisFrame) return i;
#else
                if (Input.GetKeyDown(KeyCode.Alpha1 + i - 1)) return i;
#endif
            }
            return -1;
        }

        static bool Check(K k, bool down)
        {
#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            if (kb == null) return false;
            var key = k switch
            {
                K.F => kb.fKey, K.T => kb.tKey, K.C => kb.cKey, K.O => kb.oKey, K.L => kb.lKey,
                K.G => kb.gKey, K.H => kb.hKey, K.R => kb.rKey, K.J => kb.jKey, K.B => kb.bKey, K.Esc => kb.escapeKey, K.X => kb.xKey, K.N => kb.nKey, K.K => kb.kKey,
                K.F1 => kb.f1Key, K.F2 => kb.f2Key, K.F3 => kb.f3Key, K.Plus => kb.equalsKey, K.Minus => kb.minusKey, K.Tab => kb.tabKey,
                K.W => kb.wKey, K.A => kb.aKey, K.S => kb.sKey, K.D => kb.dKey,
                K.Q => kb.qKey, K.E => kb.eKey, K.Shift => kb.leftShiftKey, _ => kb.digit1Key,
            };
            return down ? key.wasPressedThisFrame : key.isPressed;
#else
            var code = k switch
            {
                K.F => KeyCode.F, K.T => KeyCode.T, K.C => KeyCode.C, K.O => KeyCode.O, K.L => KeyCode.L,
                K.G => KeyCode.G, K.H => KeyCode.H, K.R => KeyCode.R, K.J => KeyCode.J, K.B => KeyCode.B, K.Esc => KeyCode.Escape, K.X => KeyCode.X, K.N => KeyCode.N, K.K => KeyCode.K,
                K.F1 => KeyCode.F1, K.F2 => KeyCode.F2, K.F3 => KeyCode.F3, K.Plus => KeyCode.Equals, K.Minus => KeyCode.Minus, K.Tab => KeyCode.Tab,
                K.W => KeyCode.W, K.A => KeyCode.A, K.S => KeyCode.S, K.D => KeyCode.D,
                K.Q => KeyCode.Q, K.E => KeyCode.E, K.Shift => KeyCode.LeftShift, _ => KeyCode.Alpha1,
            };
            return down ? Input.GetKeyDown(code) : Input.GetKey(code);
#endif
        }
    }
}
