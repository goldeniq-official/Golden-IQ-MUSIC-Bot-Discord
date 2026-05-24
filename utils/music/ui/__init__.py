# -*- coding: utf-8 -*-
"""Shared design system for the Golden IQ Music Bot in-Discord UI.

Modules:
    theme        — color resolution, status accents, spacing constants
    emoji_set    — unicode-default + config-override emoji lookup
    layout       — text layout helpers (vertical stacks, accordions, dividers)
    progress     — progress bar rendering
    queue_render — single source of truth for queue display
    components   — BaseTimeoutView, Paginator, Wizard, ButtonRowFactory

Skins and views compose these helpers; no skin should hand-roll its own
button layout, emoji set, or queue formatter.
"""

from utils.music.ui import theme, emoji_set, layout, progress, queue_render, components

__all__ = ("theme", "emoji_set", "layout", "progress", "queue_render", "components")
