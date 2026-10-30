# -*- coding: utf-8 -*-
"""Local-only placeholder for the removed online leaderboard."""

import customtkinter as ctk

from i18n import t
from interface.widgets import PANEL, TEXT_FAINT


def build_ranking_view(app, parent):
    """Build the former ranking tab without making network requests."""
    parent.grid_columnconfigure(0, weight=1)
    card = ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=10)
    card.grid(row=0, column=0, sticky='ew')
    ctk.CTkLabel(
        card, text=t('ui.leaderboard_title'), anchor='w',
        text_color=TEXT_FAINT, font=ctk.CTkFont(size=11, weight='bold')
    ).grid(row=0, column=0, sticky='w', padx=12, pady=(6, 1))
    app._rank_notice = ctk.CTkLabel(
        card, text=t('ui.ranking_removed'), anchor='w', justify='left',
        text_color=TEXT_FAINT, wraplength=430,
        font=ctk.CTkFont(size=10))
    app._rank_notice.grid(row=1, column=0, sticky='w', padx=12, pady=(2, 8))
    app._rank_board_body = None
    app._rank_refresh_btn = None
    return parent


def refresh_leaderboard(app, force=False):
    """Compatibility entry point; online leaderboard traffic is disabled."""
    return None
