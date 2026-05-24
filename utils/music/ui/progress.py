# -*- coding: utf-8 -*-
"""Progress bar rendering for player skins.

Extracted from the per-skin implementations in ``default_progressbar.py``
and ``default_progressbar_static.py`` so a single function is the source of
truth.

Two output styles:

- ``render_unicode_bar`` — pure Unicode characters (``█`` and ``░`` or
  similar). Renders identically on every device and never needs a code
  block.
- ``render_ansi_bar`` — wraps the bar in an ANSI code block to colorize the
  filled portion. Looks great on desktop but renders as a monospace block
  on mobile, taking more vertical space.

Default skins should call ``render_unicode_bar`` unless they specifically
opt into the ANSI variant for the "premium" feel.
"""
from __future__ import annotations

FILLED_CHAR = "█"
EMPTY_CHAR = "░"
KNOB_CHAR = "🔘"


def _ratio(position: float, duration: float) -> float:
    if duration <= 0:
        return 0.0
    if position <= 0:
        return 0.0
    return min(1.0, position / duration)


def render_unicode_bar(position: float, duration: float, width: int = 14) -> str:
    """Render a Unicode-only progress bar safe for mobile.

    ``width`` characters wide; ``position`` and ``duration`` in the same
    units (typically milliseconds). Stream tracks (``duration == 0``) render
    as a fully-filled bar.
    """
    width = max(4, width)
    if duration <= 0:
        return FILLED_CHAR * width

    filled = round(_ratio(position, duration) * width)
    filled = max(0, min(width, filled))

    return FILLED_CHAR * filled + EMPTY_CHAR * (width - filled)


def render_knob_bar(position: float, duration: float, width: int = 14) -> str:
    """Progress bar with a knob marker — like a Spotify scrubber.

    Renders ``▬▬▬🔘▬▬▬`` style; works on mobile but the knob emoji adds a
    tiny vertical bump. Use for "fancy" skins; default to ``render_unicode_bar``
    for the most universal look.
    """
    width = max(4, width)
    if duration <= 0:
        return "▬" * width

    pos = round(_ratio(position, duration) * (width - 1))
    pos = max(0, min(width - 1, pos))

    return "▬" * pos + KNOB_CHAR + "▬" * (width - 1 - pos)


def render_ansi_bar(position: float, duration: float, width: int = 14) -> str:
    """ANSI-colored progress bar wrapped in a code block.

    Caller is expected to embed the returned string as-is (it includes the
    triple-backtick fence). Use sparingly — code blocks render as a fixed
    monospace block on mobile.
    """
    width = max(4, width)
    if duration <= 0:
        return f"```ansi\n[31;1m{FILLED_CHAR * width}[0m```"

    filled = round(_ratio(position, duration) * width)
    filled = max(0, min(width, filled))
    return (
        "```ansi\n"
        f"[32;1m{FILLED_CHAR * filled}[0m{EMPTY_CHAR * (width - filled)}"
        "```"
    )


def percent(position: float, duration: float) -> int:
    """Return the integer percent (0–100) of ``position`` through ``duration``."""
    return int(_ratio(position, duration) * 100)
