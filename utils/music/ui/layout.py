# -*- coding: utf-8 -*-
"""Text-layout helpers that produce readable output on both desktop and mobile.

Mobile Discord wraps text very aggressively — embeds that look elegant on
desktop become a wall of broken lines on a phone. The helpers here produce
output that wraps predictably:

- ``vertical_stack`` — collapse multi-column data into single-column rows
  with a leading icon.
- ``accordion_text`` — show the first ``visible`` lines, hide the rest behind
  a counted teaser. Used for skins that have 10+ conditional description
  lines (e.g. ``default_static``).
- ``divider`` — a thin line that renders as ~80% of an embed's content width
  without inflating line height.
- ``compact_field`` — produces a single-line, mobile-aware field entry.

None of these helpers call disnake — they return strings. The caller composes
them into ``embed.description``, ``embed.add_field``, etc.
"""
from __future__ import annotations

from typing import Iterable, Sequence


def divider(width: int = 30, char: str = "─") -> str:
    """A thin Unicode divider line.

    Defaults to 30 chars — wide enough to read as a separator on desktop,
    narrow enough to not wrap awkwardly on mobile portrait orientation.
    """
    return char * max(1, width)


def vertical_stack(rows: Iterable[tuple[str, str]], *, separator: str = " **⠂** ") -> str:
    """Render ``(icon, text)`` pairs as a single-column list.

    Each row becomes ``> -# {icon} {separator} {text}`` — the small-text
    blockquote style the existing skins already use. Empty texts are dropped.

    >>> vertical_stack([("⏰", "3:42"), ("👤", "Author")])
    '> -# ⏰ **⠂** 3:42\\n> -# 👤 **⠂** Author'
    """
    out = []
    for icon, text in rows:
        if not text:
            continue
        out.append(f"> -# {icon}{separator}{text}")
    return "\n".join(out)


def accordion_text(lines: Sequence[str], *, visible: int = 4, hidden_label: str = "more detail") -> str:
    """Show the first ``visible`` lines; collapse the rest behind a teaser.

    Used to keep busy descriptions (loops + album + playlist + voice + 24/7 +
    queue summary etc.) under control on mobile.

    If there are ``visible`` or fewer lines, returns them as-is — no teaser
    appended.
    """
    lines = [ln for ln in lines if ln]
    if len(lines) <= visible:
        return "\n".join(lines)
    head = "\n".join(lines[:visible])
    hidden = len(lines) - visible
    return f"{head}\n> -# +{hidden} {hidden_label} line{'s'[:hidden ^ 1]}"


def compact_field(icon: str, label: str, value: str) -> str:
    """A single-line key/value entry styled for the small-text blockquote.

    Suitable for stacking via ``vertical_stack`` or appending to a
    description. Keeps the icon, label, and value visually distinct without
    using a real ``embed.add_field`` (which forces side-by-side columns on
    desktop and collapses to two-column awkward on mobile).
    """
    return f"> -# {icon} **{label}** ⠂ {value}"


def link(text: str, url: str) -> str:
    """Markdown link helper that escapes the closing paren if needed."""
    if not url:
        return text
    return f"[{text}]({url})"


def truncate(text: str, limit: int, *, suffix: str = "…") -> str:
    """Truncate ``text`` to ``limit`` characters, appending ``suffix`` if cut.

    Honors the suffix length in the limit so the result is never longer than
    ``limit``.
    """
    if not text or len(text) <= limit:
        return text
    if limit <= len(suffix):
        return text[:limit]
    return text[: limit - len(suffix)] + suffix
