# -*- coding: utf-8 -*-
"""Visual identity for the music bot UI.

Owns:
    - Color resolution (guild role color → bot config override → neutral default)
    - Status accents (green=playing, amber=paused, red=stopped/error/disconnect)
    - Spacing constants (zero-width characters used as visual separators)

Callers never hardcode a hex value — they go through ``resolve_color`` so the
end-user's chosen ``EMBED_COLOR`` always wins, and views that want to signal
state pull a single status accent rather than inventing their own.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

import disnake

if TYPE_CHECKING:
    from utils.music.models import LavalinkPlayer
    from utils.client import BotCore

# Zero-width space used to add breathing room between sections without
# inflating the line height the way blank lines do.
ZW = "​"

# Modern minimal dividers. 
DIVIDER_THIN = "⏤" * 8
DIVIDER_DOT = " ⬩ "

# A sleeker accent bar for Next-Gen aesthetic
PREMIUM_ACCENT_BAR = "━" * 20

# Golden IQ specific modern animated bar, or sleek gradient
PREMIUM_DECORATIVE_BAR = "https://cdn.discordapp.com/attachments/554468640942981147/1082887587770937455/rainbow_bar2.gif"

# "Golden IQ" brand palette — warm gold tones used by help/about/info surfaces
# that want to express bot identity rather than guild role color.
BRAND_GOLD = 0xD4AF37          # primary brand (Anniversary Gold)
BRAND_GOLD_BRIGHT = 0xFFD700   # accent / highlight
BRAND_GOLD_DEEP = 0xB8860B     # subdued (footer dividers, secondary text)

# Status accent colors tailored for modern dark/light contrast
STATUS_COLORS = {
    "playing": None,                 # use the guild/bot color (brand wins)
    "paused": 0xF5A623,              # amber
    "stopped": 0x4F545C,             # deep neutral grey
    "error": 0xED4245,               # discord red
    "disconnect": 0xED4245,          # discord red
    "loading": 0x5865F2,             # discord blurple
    "brand": BRAND_GOLD,             # Golden IQ brand surfaces (help/about)
    "success": 0x57F287,             # discord green
    "info": 0x5865F2,                # discord blurple
}

# Status icons using refined sleek symbols where possible
STATUS_ICONS = {
    "playing": "▶",
    "paused": "⏸",
    "stopped": "⏹",
    "loading": "↻",
    "live": "🔴",
    "loop_track": "🔂",
    "loop_queue": "🔁",
    "autoplay": "∞",
    "recommendation": "✨",
    "favorite": "🤍",
    "voice": "🔊",
    "info": "ℹ️",
    "warn": "⚠️",
    "error": "🛑",
    "ok": "✓",
}


def resolve_color(
    bot: "BotCore",
    guild: Optional[disnake.Guild] = None,
    status: Optional[str] = None,
) -> int:
    """Pick the embed color for a UI surface.

    Order: explicit status accent → bot.get_color(guild.me) (which already
    honors EMBED_COLOR config and guild role color) → neutral fallback.
    """
    if status and (accent := STATUS_COLORS.get(status)) is not None:
        return accent

    if guild is not None:
        color = bot.get_color(guild.me)
        if isinstance(color, disnake.Color):
            return color.value
        return color

    # Last resort — neutral dark grey that works on both Discord themes.
    return 0x2B2D31


def status_for_player(player: "LavalinkPlayer") -> str:
    """Map a player's runtime state to a status key understood by this module."""
    try:
        if player.is_closing:
            return "disconnect"
    except AttributeError:
        pass

    if not getattr(player, "current", None):
        return "stopped"
    if player.paused:
        return "paused"
    return "playing"


def status_accent_line(player: "LavalinkPlayer") -> str:
    """One-line status banner suitable for the top of an embed description."""
    status = status_for_player(player)
    icon = STATUS_ICONS.get(status, "▶️")

    label = {
        "playing": "Now playing",
        "paused": "Paused",
        "stopped": "Idle",
        "loading": "Loading",
        "disconnect": "Disconnected",
    }.get(status, status.title())

    return f"-# {icon} **{label}**"


def author_for_status(status: str) -> tuple[str, Optional[str]]:
    """Return (author_name, icon_url) for ``embed.set_author``.

    Icon URLs are intentionally omitted — the skin-level author icon (album
    art, source platform icon) remains the more informative choice. Callers
    that want a status icon should use ``STATUS_ICONS[status]`` inline.
    """
    label = {
        "playing": "Now Playing",
        "paused": "Paused",
        "stopped": "Idle",
        "loading": "Loading",
        "disconnect": "Disconnected",
        "error": "Error",
    }.get(status, status.title())
    return label, None
