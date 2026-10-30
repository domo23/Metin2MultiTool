"""Privacy regression tests for local-only names and telemetry removal."""

import unittest

from interface import config
from interface import onboarding
from interface.app.lifecycle import LifecycleMixin
from i18n_data import TRANSLATIONS


class TestLocalDisplayName(unittest.TestCase):
    def test_name_is_only_a_local_config_value(self):
        cfg = config.validate({'username': 'LocalPlayer'})
        self.assertEqual(cfg['username'], 'LocalPlayer')
        self.assertFalse(hasattr(LifecycleMixin, '_telemetry_state'))
        self.assertFalse(hasattr(LifecycleMixin, '_ensure_install_id'))

    def test_old_identity_and_endpoint_fields_are_removed(self):
        cfg = config.validate({'telemetry': {
            'install_id': 'previously-saved-id',
            'submit_url': 'https://example.invalid/submit',
            'leaderboard_url': 'https://example.invalid/leaderboard',
        }})
        self.assertNotIn('install_id', cfg['telemetry'])
        self.assertNotIn('submit_url', cfg['telemetry'])
        self.assertNotIn('leaderboard_url', cfg['telemetry'])

    def test_onboarding_gate_remains_local_and_one_time(self):
        self.assertTrue(onboarding.needs_onboarding(config.validate({})))
        self.assertFalse(onboarding.needs_onboarding(config.validate({
            'telemetry': {'consented': True}})))

    def test_privacy_notice_is_localization_complete(self):
        for key in ('ui.ranking_transparency', 'ui.ranking_removed',
                    'ui.onboarding_transparency'):
            self.assertTrue(TRANSLATIONS[key]['en'])
            self.assertTrue(TRANSLATIONS[key]['de'])
        self.assertIn('does not send',
                      TRANSLATIONS['ui.ranking_transparency']['en'])


if __name__ == '__main__':
    unittest.main()
