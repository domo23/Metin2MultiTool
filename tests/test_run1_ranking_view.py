"""The former online ranking view stays local-only."""

import threading
import unittest
from unittest import mock
from urllib import request

from interface import ranking_view


class TestRankingViewOffline(unittest.TestCase):
    def test_refresh_makes_no_request_or_worker_thread(self):
        app = object()
        with mock.patch.object(
                request, 'urlopen',
                side_effect=AssertionError('network access is disabled')) as urlopen, \
             mock.patch.object(
                threading, 'Thread',
                side_effect=AssertionError('no ranking worker should start')) as thread:
            self.assertIsNone(ranking_view.refresh_leaderboard(app, force=True))
        urlopen.assert_not_called()
        thread.assert_not_called()
