"""The legacy leaderboard client must remain offline."""

import threading
import unittest
from unittest import mock
from urllib import request

from telemetry import client


class TestTelemetryClientDisabled(unittest.TestCase):
    def test_api_calls_never_open_network_connections(self):
        with mock.patch.object(
                request, 'urlopen',
                side_effect=AssertionError('network access is disabled')) as urlopen:
            self.assertEqual(
                client.check_name('https://example.invalid/leaderboard',
                                  'player', 'install-id')['available'],
                True)
            self.assertEqual(
                client.post_submit('https://example.invalid/submit', {}),
                ('error', None))
            self.assertIsNone(
                client.fetch_leaderboard('https://example.invalid/leaderboard'))
        urlopen.assert_not_called()

    def test_sender_does_not_start_a_thread(self):
        with mock.patch.object(
                threading, 'Thread',
                side_effect=AssertionError('sender thread must not start')):
            self.assertIsNone(client.start_sender(lambda: {}))
        self.assertIsNone(client.stop_sender())
