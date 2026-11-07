"""Multiclient stop-button labeling and hotkey behavior."""

import unittest
from unittest import mock

from interface.app.views_multiclient import MulticlientViewMixin


class TestMulticlientStopButton(unittest.TestCase):
    def test_running_label_shows_configured_stop_hotkey(self):
        view = MulticlientViewMixin()
        view.controller = mock.Mock()
        view.controller.current_config.return_value = {
            'controls': {'stop_hotkey': 'f8'}}

        with mock.patch(
                'interface.app.views_multiclient.t',
                side_effect=lambda _key, **values:
                'Stop all [{}]'.format(values['hotkey'])):
            self.assertEqual(view._mc_stop_button_text(),
                             '\u25a0  Stop all [F8]')

    def test_hotkey_stop_only_changes_worker_run_flag(self):
        view = MulticlientViewMixin()
        view._mc_running = True
        view._mc_request_stop_from_hotkey()
        self.assertFalse(view._mc_running)
