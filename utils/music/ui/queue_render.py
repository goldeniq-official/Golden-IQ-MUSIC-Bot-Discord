# -*- coding: utf-8 -*-
"""Queue display — single source of truth across all skins and views.

Before this module, every skin re-implemented its own queue listing with
slightly different formats, character truncation limits, and emoji choices.
That duplication caused mobile users to see inconsistent layouts depending
on which skin they were on.

Two output modes:

- ``compact`` — one line per track, designed for the mobile-friendly inline
  preview (3–5 entries). Format: ``[NN] [DURATION] Title — Author`` where
  long titles truncate to fit a phone screen width.
- ``detailed`` — two-line per track, includes "starts in" relative time for
  the desktop ``static_player`` skins that have the screen real estate.

Both honor ``itertools.islice`` semantics — pass any iterable.
"""
from __future__ import annotations

import datetime
import itertools
from typing import TYPE_CHECKING, Iterable

import disnake

from utils.music.converters import fix_characters, time_format

if TYPE_CHECKING:
    from utils.music.models import LavalinkPlayer, LavalinkTrack


_RECOMMENDATION_PREFIX = "✨"

def _format_duration(track) -> str:
    if track.is_stream:
        return "🔴 LIVE"
    return time_format(track.duration)

def render_compact_line(track, index: int, *, title_limit: int = 28, is_recommendation: bool = False) -> str:
    """Render a single track as one compact line."""
    prefix = f"{_RECOMMENDATION_PREFIX} " if is_recommendation else ""
    duration = _format_duration(track)
    title = fix_characters(track.title, title_limit)
    return f"`{prefix}{index:02} ⬩` [`{title}`]({track.uri}) `{duration}`"


def render_compact_lines(
    tracks: Iterable,
    *,
    max_items: int = 5,
    title_limit: int = 28,
    is_recommendation: bool = False,
) -> str:
    """Render up to ``max_items`` compact lines, joined with newlines."""
    return "\n".join(
        render_compact_line(
            t,
            n + 1,
            title_limit=title_limit,
            is_recommendation=is_recommendation,
        )
        for n, t in enumerate(itertools.islice(tracks, max_items))
    )


def render_detailed_line(track, index: int, *, title_limit: int = 42, is_recommendation: bool = False) -> str:
    """Two-line entry with author on the second line."""
    prefix = f"{_RECOMMENDATION_PREFIX} " if is_recommendation else ""
    duration = _format_duration(track)
    title = fix_characters(track.title, title_limit)
    author = fix_characters(track.author, title_limit)
    return (
        f"`{prefix}{index:02} ⬩` [`{title}`]({track.uri})\n"
        f"> 👤 `{author}` ⬩ ⏳ `{duration}`"
    )


def render_detailed_lines(
    tracks: Iterable,
    *,
    max_items: int = 8,
    title_limit: int = 42,
    is_recommendation: bool = False,
) -> str:
    """Render up to ``max_items`` detailed two-line entries."""
    return "\n".join(
        render_detailed_line(
            t,
            n + 1,
            title_limit=title_limit,
            is_recommendation=is_recommendation,
        )
        for n, t in enumerate(itertools.islice(tracks, max_items))
    )


def render_queue_lines(
    player: "LavalinkPlayer",
    *,
    max_items: int = 5,
    format: str = "compact",
) -> tuple[str, bool]:
    """Render the active queue (or autoplay queue) using the chosen format.

    Returns ``(text, is_recommendation)``. The boolean lets the caller decide
    whether to label the section "Songs in queue" vs "Next recommended".

    If there are no upcoming tracks at all, returns ``("", False)`` so the
    caller can skip rendering the queue section entirely.
    """
    tracks = player.queue or []
    is_recommendation = False

    if not tracks and getattr(player, "queue_autoplay", None):
        tracks = player.queue_autoplay
        is_recommendation = True

    if not tracks:
        return "", False

    if format == "detailed":
        return (
            render_detailed_lines(tracks, max_items=max_items, is_recommendation=is_recommendation),
            is_recommendation,
        )

    return (
        render_compact_lines(tracks, max_items=max_items, is_recommendation=is_recommendation),
        is_recommendation,
    )


def render_queue_footer_eta(player: "LavalinkPlayer") -> str:
    """Return a "queue ends ~<t:relative>" string, or empty if not applicable.

    Skipped when the player has no current track, when loop mode is enabled
    (the queue technically never ends), when 24/7 mode is on, or when the
    player is paused.
    """
    current = getattr(player, "current", None)
    if not current:
        return ""
    if player.loop or player.keep_connected or player.paused:
        return ""
    if not player.queue:
        return ""

    queue_duration = sum(t.duration for t in player.queue if not t.is_stream)

    current_remaining = 0
    if not current.is_stream:
        current_remaining = current.duration - player.position

    eta_ms = queue_duration + current_remaining
    if eta_ms <= 0:
        return ""

    ends_at = disnake.utils.utcnow() + datetime.timedelta(milliseconds=eta_ms)
    return f"> ⏳ **Songs end:** <t:{int(ends_at.timestamp())}:R>"


def remaining_time_marker(track, *, position_ms: int = 0) -> str:
    """Discord relative timestamp for when ``track`` will finish playing.

    ``position_ms`` is how far into the track we already are. Returns an
    empty string for streams.
    """
    if track.is_stream:
        return ""
    remaining_ms = max(0, track.duration - position_ms)
    finish_at = disnake.utils.utcnow() + datetime.timedelta(milliseconds=remaining_ms)
    return f"<t:{int(finish_at.timestamp())}:R>"
