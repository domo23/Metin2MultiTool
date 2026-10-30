# -*- coding: utf-8 -*-
"""Offline compatibility stubs for the removed online leaderboard client.

These functions deliberately perform no network or background-thread activity.
"""


def check_name(leaderboard_url, username, hwid, timeout=10):
    """Treat a locally chosen display name as available without a server check."""
    return {'available': True, 'owner_is_self': False,
            'name': str(username or '').strip()}


def post_submit(url, payload, timeout=10):
    """Submissions are disabled; return an explicit non-success status."""
    return 'error', None


def fetch_leaderboard(url, timeout=10, force=False):
    """Online leaderboard fetching is disabled."""
    return None


def start_sender(get_state, on_status=None, interval=120, idle_poll=2.0):
    """Automatic telemetry sending is disabled."""
    return None


def stop_sender():
    """Compatibility no-op; no sender thread is started."""
    return None
