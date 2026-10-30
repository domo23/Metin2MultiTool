# -*- coding: utf-8 -*-
"""LifecycleMixin -- extracted from interface/app (behaviour-preserving).

Mixin for :class:`interface.app.App`. Holds only methods (no
``__init__``, no class-level mutable state) so MRO is unaffected and every
``self`` reference resolves exactly as in the original module.
"""

from interface.app._common import *  # noqa: F401,F403


class LifecycleMixin:
    def _flush_stats(self):
        """Run the registered final-stats-save hook (if any). Never raises.

        Called on every exit path so accrued runtime/counters reach stats.json
        even when no catch/solve triggered the debounced save before exit."""
        try:
            hook = getattr(self, '_stats_save_hook', None)
            if callable(hook):
                hook()
        except Exception:
            pass

    def _on_close(self):
        self._flush_stats()
        try:
            cfgmod.save(self.controller.current_config())
        except Exception:
            pass
        try:
            if self._tray_icon is not None:
                self._tray_icon.stop()
        except Exception:
            pass
        try:
            self.log_panel.detach()
        except Exception:
            pass
        self.destroy()

    # -- UI-Synchronisierung ---------------------------------------------

    def _maybe_onboard(self):
        """Zeigt beim ersten Start den Dialog fuer den lokalen Anzeigenamen.

        Nur wenn noch kein Name gewaehlt UND das Onboarding noch nie entschieden
        wurde. Streng defensiv -- ein Fehler hier darf den Start nie kippen."""
        try:
            from interface import onboarding
            if onboarding.needs_onboarding(self.controller.current_config()):
                onboarding.open_onboarding(self, on_done=self._on_onboarded)
        except Exception:
            pass

    def _on_onboarded(self, _result):
        """Aktualisiert die Konfiguration nach dem lokalen Onboarding."""
        try:
            self._cfg = self.controller.current_config()
        except Exception:
            pass

    # -- Status-/Detection-Note (unten rechts) ---------------------------
