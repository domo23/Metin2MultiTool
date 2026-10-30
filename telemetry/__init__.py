# -*- coding: utf-8 -*-
"""Legacy leaderboard helpers retained for compatibility.

The desktop application no longer sends telemetry or fetches an online
leaderboard. Importing this package performs no network or thread activity.
"""

from telemetry import anon_name, payload

__all__ = ['anon_name', 'payload', 'client']


def __getattr__(name):
    if name == 'client':
        import importlib
        return importlib.import_module('telemetry.client')
    raise AttributeError(
        '{!r} has no attribute {!r}'.format(__name__, name))
