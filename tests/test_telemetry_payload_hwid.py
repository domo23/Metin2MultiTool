# -*- coding: utf-8 -*-
"""Pure tests for the retired, offline leaderboard payload helper."""

import unittest
from datetime import datetime, timezone

from telemetry import payload


class TestBuildSubmit(unittest.TestCase):
    def _stats(self, **over):
        base = {'fishing_catches': 5, 'puzzles_solved': 2,
                'fishing_runtime_s': 12.5, 'puzzler_runtime_s': 3.0}
        base.update(over)
        return base

    def test_schema_keys_exact(self):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        p = payload.build_submit('bob', 'abc123', self._stats(), '1.0.5', now)
        self.assertEqual(set(p), {
            'username', 'hwid', 'fishing_catches', 'puzzles_solved',
            'fishing_runtime_s', 'puzzler_runtime_s', 'app_version', 'ts'})

    def test_values_carried(self):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        p = payload.build_submit('bob', 'abc', self._stats(), '1.0.5', now)
        self.assertEqual(p['username'], 'bob')
        self.assertEqual(p['fishing_catches'], 5)
        self.assertEqual(p['app_version'], '1.0.5')

    def test_deterministic_ts_from_aware_now(self):
        now = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        p = payload.build_submit('bob', 'abc', self._stats(), '1.0.5', now)
        self.assertEqual(p['ts'], int(now.timestamp()))

    def test_ts_from_epoch_number(self):
        p = payload.build_submit('bob', 'abc', self._stats(), '1.0.5', 1700000000)
        self.assertEqual(p['ts'], 1700000000)

    def test_username_capped(self):
        long = 'x' * 200
        p = payload.build_submit(long, 'abc', self._stats(), '1.0.5', 0)
        self.assertEqual(len(p['username']), payload.USERNAME_MAXLEN)

    def test_negative_counts_clamped(self):
        p = payload.build_submit('bob', 'abc',
                                 self._stats(fishing_catches=-9,
                                             fishing_runtime_s=-1.0),
                                 '1.0.5', 0)
        self.assertEqual(p['fishing_catches'], 0)
        self.assertEqual(p['fishing_runtime_s'], 0.0)

    def test_garbage_stats_safe(self):
        p = payload.build_submit('bob', 'abc',
                                 {'fishing_catches': 'NaN',
                                  'fishing_runtime_s': 'oops'}, '1.0.5', 0)
        self.assertEqual(p['fishing_catches'], 0)
        self.assertEqual(p['fishing_runtime_s'], 0.0)

    def test_build_from_non_dict_stats(self):
        p = payload.build_submit('bob', 'abc', None, '1.0.5', 0)
        self.assertEqual(p['fishing_catches'], 0)
        self.assertEqual(p['puzzles_solved'], 0)

    def test_never_raises(self):
        # totally hostile inputs
        p = payload.build_submit(object(), object(), object(), object(),
                                 object())
        self.assertIn('username', p)
        self.assertEqual(p['ts'], 0)


class TestClampPayload(unittest.TestCase):
    def test_idempotent(self):
        p = payload.build_submit('bob', 'abc',
                                 {'fishing_catches': 3}, '1.0.5', 100)
        self.assertEqual(payload.clamp_payload(p), p)

    def test_huge_count_clamped(self):
        p = payload.clamp_payload({'fishing_catches': 10 ** 12})
        self.assertEqual(p['fishing_catches'], 100_000_000)

    def test_non_dict_returns_defaults(self):
        p = payload.clamp_payload('not a dict')
        self.assertEqual(p['fishing_catches'], 0)
        self.assertEqual(p['username'], '')


if __name__ == '__main__':
    unittest.main()
