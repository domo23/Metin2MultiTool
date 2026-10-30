# -*- coding: utf-8 -*-
"""Pytest-wide setup for safe, headless application tests."""

import sys
import types

# Windows-only Eingabe-/Fenster-Module stubben, damit puzzle.py & Co. headless
# (Linux/WSL/CI ohne pydirectinput/win32) importierbar sind. Einzelne Testmodule
# (z.B. test_puzzle_hardening) installieren denselben Stub lokal vor ihrem
# puzzle-Import; hier session-weit, damit JEDES Modul (auch test_puzzle_glue /
# test_puzzle_box_refill / die neuen v1.3-Tests) den echten puzzle-Code laden
# kann. No-op-Funktionen -> kein realer Tastatur-/Mausklick im Test.
if 'pydirectinput' not in sys.modules:
    _pdi = types.ModuleType('pydirectinput')
    _pdi.PAUSE = 0
    for _fn in ('click', 'moveTo', 'press', 'keyDown', 'keyUp'):
        setattr(_pdi, _fn, lambda *a, **k: None)
    sys.modules['pydirectinput'] = _pdi
for _name in ('win32gui', 'win32ui', 'win32con', 'win32api'):
    sys.modules.setdefault(_name, types.ModuleType(_name))
