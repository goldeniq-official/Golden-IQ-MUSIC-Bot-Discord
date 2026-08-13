# -*- coding: utf-8 -*-
"""Which audio sources actually work, and what to tell users when they don't.

A source can be broken in two ways that both used to fail silently:

    Spotify — enabled in application.yml but the credentials are rejected by
    Spotify's own OAuth endpoint (HTTP 400 invalid_client), so every lookup
    raised a bare FriendlyException the user could not act on.

    Deezer — disabled in lavasrc with no masterDecryptionKey, so lookups
    returned loadType "empty", which the bot rendered as "nothing found"
    rather than "this source is off".

Both cases now produce an explicit, bilingual message naming a source that
does work. A user who is told to use YouTube can finish what they were
doing; a user shown "nothing found" just retries and fails again.
"""
from __future__ import annotations

import re
from typing import Optional

# Search prefixes and URL patterns per source, matched against a raw query.
_SOURCE_PATTERNS: dict[str, tuple[tuple[str, ...], Optional[re.Pattern]]] = {
    "spotify": (
        ("spsearch:", "sprec:"),
        re.compile(r"https?://(open|play)\.spotify\.com/", re.IGNORECASE),
    ),
    "deezer": (
        ("dzsearch:", "dzisrc:"),
        re.compile(r"https?://(www\.)?deezer\.com/", re.IGNORECASE),
    ),
    "applemusic": (
        ("amsearch:",),
        re.compile(r"https?://music\.apple\.com/", re.IGNORECASE),
    ),
    "tidal": (("tdsearch:",), re.compile(r"https?://(www\.)?tidal\.com/", re.IGNORECASE)),
    "jiosaavn": (("jssearch:",), re.compile(r"https?://(www\.)?jiosaavn\.com/", re.IGNORECASE)),
}

# Human-facing source names, Khmer + English.
_DISPLAY = {
    "spotify": "Spotify",
    "deezer": "Deezer",
    "applemusic": "Apple Music",
    "tidal": "Tidal",
    "jiosaavn": "JioSaavn",
}


def detect_source(query: str) -> Optional[str]:
    """Return the source key a raw query targets, or None if unrecognised."""
    if not query:
        return None
    stripped = query.strip().lstrip("<").rstrip(">")
    lowered = stripped.lower()
    for source, (prefixes, url_re) in _SOURCE_PATTERNS.items():
        if lowered.startswith(prefixes):
            return source
        if url_re and url_re.search(stripped):
            return source
    return None


# Credential keys each source needs before it can serve a request.
_REQUIRED_CREDENTIALS = {
    "spotify": ("clientId", "clientSecret"),
    "deezer": ("masterDecryptionKey",),
    "applemusic": ("mediaAPIToken",),
    "tidal": ("token",),
}


def compute_unavailable_sources(app_yml_path="application.yml") -> set:
    """Sources that cannot serve requests, read from the Lavalink config.

    A source is unavailable when lavasrc has it switched off, or has it on
    while a credential it requires is blank. Credentials that are present but
    *rejected* by the provider cannot be detected without a network call — in
    that case switch the source off in application.yml so this returns it.
    """
    from pathlib import Path

    path = Path(app_yml_path)
    if not path.exists():
        return set()

    try:
        from ruamel.yaml import YAML

        data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
        lavasrc = ((data or {}).get("plugins") or {}).get("lavasrc") or {}
    except Exception:
        # A malformed config must not take the bot down; assume nothing is
        # known to be broken and let normal lookups report their own errors.
        return set()

    enabled = lavasrc.get("sources") or {}
    unavailable = set()

    for source in _SOURCE_PATTERNS:
        if source not in enabled:
            continue
        if not enabled.get(source):
            unavailable.add(source)
            continue
        conf = lavasrc.get(source) or {}
        for key in _REQUIRED_CREDENTIALS.get(source, ()):
            if not conf.get(key):
                unavailable.add(source)
                break

    return unavailable


def unavailable_message(source: str, alternatives: str = "YouTube / SoundCloud") -> str:
    """Bilingual, actionable message for a source that cannot serve requests."""
    name = _DISPLAY.get(source, source.title())
    return (
        f"**ប្រភព {name} មិនអាចប្រើបានទេនៅពេលនេះ។ / "
        f"{name} is currently unavailable.**\n"
        f"សូមប្រើ {alternatives} ជំនួស — ស្វែងរកតាមឈ្មោះបទ ឬឈ្មោះសិល្បករ។ / "
        f"Please use {alternatives} instead — search by track or artist name."
    )
