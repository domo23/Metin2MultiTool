"""Regression tests for removal of online leaderboard telemetry."""

import unittest
from unittest import mock
from urllib import request

from interface import config
from interface.app.lifecycle import LifecycleMixin
from telemetry import client


class TestTelemetryRemoved(unittest.TestCase):
    def test_old_network_configuration_is_discarded(self):
        cfg = config.validate({'telemetry': {
            'install_id': 'old-install-id',
            'enabled': True,
            'submit_url': 'https://example.invalid/submit',
            'leaderboard_url': 'https://example.invalid/leaderboard',
            'interval_s': 120,
            'consented': True,
        }})
        self.assertEqual(cfg['telemetry'], {
            'consented': True, 'rating_prompted': False})

    def test_application_has_no_telemetry_sender_hooks(self):
        self.assertFalse(hasattr(LifecycleMixin, '_ensure_install_id'))
        self.assertFalse(hasattr(LifecycleMixin, '_telemetry_state'))
        self.assertFalse(hasattr(LifecycleMixin, '_start_telemetry'))

    def test_legacy_client_apis_make_no_request(self):
        with mock.patch.object(
                request, 'urlopen',
                side_effect=AssertionError('network access is disabled')) as urlopen:
            self.assertEqual(client.post_submit(
                'https://example.invalid/submit', {'data': 'private'}),
                ('error', None))
            self.assertIsNone(client.fetch_leaderboard(
                'https://example.invalid/leaderboard'))
            self.assertTrue(client.check_name(
                'https://example.invalid/leaderboard', 'local-name', 'id')
                ['available'])
            self.assertIsNone(client.start_sender(lambda: {}))
        urlopen.assert_not_called()
