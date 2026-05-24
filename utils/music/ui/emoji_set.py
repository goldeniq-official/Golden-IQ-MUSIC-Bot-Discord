# -*- coding: utf-8 -*-
"""Centralized emoji lookup with Unicode defaults and config overrides.

The bot used to scatter raw custom-emoji IDs across every skin file
(``<:music_queue:703761160679194734>``, ``<:add_music:588172015760965654>``,
etc). Hosts who run their own copy of the bot couldn't customize them
without editing every skin.

This module:
    1. Defines a Unicode fallback for every emoji name the UI uses.
    2. Reads ``CUSTOM_EMOJIS`` from the bot config (a dict of name → string)
       and overlays it on top of the defaults.
    3. Exposes ``e(name)`` returning a string that's safe to use anywhere a
       string emoji is accepted (Embed text, Button.emoji, SelectOption.emoji).

A missing name returns the default question mark glyph rather than raising,
so a typo in a skin never crashes the player render path.
"""
from __future__ import annotations

from typing import Optional

# Unicode defaults. Every emoji name used by the UI must be defined here.
# Add new names alongside the skin code that needs them.
_DEFAULTS: dict[str, str] = {
    # Transport controls
    "play_pause": "⏯️",
    "play": "▶️",
    "pause": "⏸️",
    "stop": "⏹️",
    "back": "⏮️",
    "skip": "⏭️",
    "queue": "🎶",
    # Menu / actions
    "more": "⋯",
    "add_music": "➕",
    "favorite": "💗",
    "favorite_full": "💖",
    "seek_start": "⏪",
    "shuffle": "🔀",
    "readd": "🔁",
    "loop": "🔁",
    "loop_one": "🔂",
    "nightcore": "🎚️",
    "autoplay": "🔄",
    "restrict": "🔐",
    "lastfm": "🎵",
    "lyrics": "📃",
    "miniqueue": "📋",
    "voice_status": "📢",
    "thread": "💬",
    # Status / state
    "live": "🔴",
    "clock": "⏰",
    "person": "👤",
    "request": "✋",
    "recommendation": "👍",
    "album": "💽",
    "playlist": "📑",
    "infinity": "♾️",
    "tip": "💡",
    "warn": "⚠️",
    "error": "❌",
    "ok": "✅",
    # Navigation
    "first": "⏮️",
    "prev": "◀️",
    "next": "▶️",
    "last": "⏭️",
    "close": "✖️",
    "refresh": "🔄",
}


def _normalize_override(value) -> Optional[str]:
    """Accept several override shapes:

    - String: used verbatim (``"<:custom:123>"`` or ``"🎵"``).
    - Int: wrapped as ``<:_:ID>`` for animated/static custom emoji ID-only configs.
    - None/empty: ignored, falls back to default.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return f"<:_:{value}>"
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return None


class EmojiSet:
    """Resolves emoji names to display strings."""

    __slots__ = ("_overrides",)

    def __init__(self, overrides: Optional[dict] = None):
        self._overrides: dict[str, str] = {}
        if overrides:
            for name, value in overrides.items():
                normalized = _normalize_override(value)
                if normalized:
                    self._overrides[name] = normalized

    @classmethod
    def from_config(cls, config: Optional[dict]) -> "EmojiSet":
        """Build from the bot config dict (looks for ``CUSTOM_EMOJIS`` key)."""
        if not config:
            return cls()
        return cls(config.get("CUSTOM_EMOJIS"))

    def e(self, name: str) -> str:
        """Return the emoji string for ``name``.

        Resolution: config override → unicode default → ``❓`` (never raises).
        """
        if (override := self._overrides.get(name)) is not None:
            return override
        return _DEFAULTS.get(name, "❓")

    # Aliases that read better in calling code.
    __call__ = e
    get = e

    def with_overrides(self, **kwargs) -> "EmojiSet":
        """Return a copy with additional per-skin overrides applied on top.

        Used by skins that ship their own visual identity (e.g. ``miniplayer``
        has a custom heart icon) so they can preserve their look without
        bypassing the global system.
        """
        merged = dict(self._overrides)
        for name, value in kwargs.items():
            normalized = _normalize_override(value)
            if normalized:
                merged[name] = normalized
        return EmojiSet(merged)


# Module-level default instance used when no config is available (preview
# renders, test runs). The runtime bot replaces this via ``set_default``.
_default = EmojiSet()


def set_default(es: EmojiSet) -> None:
    """Install the bot-wide EmojiSet (called once during bot setup)."""
    global _default
    _default = es


def get_default() -> EmojiSet:
    """Return the currently installed bot-wide EmojiSet."""
    return _default


def e(name: str) -> str:
    """Module-level shortcut equivalent to ``get_default().e(name)``."""
    return _default.e(name)
