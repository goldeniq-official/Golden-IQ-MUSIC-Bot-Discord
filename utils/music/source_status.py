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
        # A fresh Pterodactyl server has no application.yml — it is generated
        # from the bundled template the first time Lavalink starts
        # (utils/music/local_lavalink.py). The Music cog is constructed before
        # that happens, so fall back to the template; otherwise the very first
        # boot would offer sources it cannot serve.
        template = Path(f"{app_yml_path}.example")
        if not template.exists():
            return set()
        path = template

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


_YT_URL_RE = re.compile(
    r"https?://(www\.|music\.|m\.)?(youtube\.com|youtu\.be)/", re.IGNORECASE
)

# Lavalink's youtube-source reports blocking as a generic FriendlyException.
# These are the phrases it uses when YouTube refuses the request rather than
# when the video genuinely does not exist.
_YT_BLOCK_PHRASES = (
    "something went wrong while looking up the track",
    "sign in to confirm",
    "not a bot",
    "please sign in",
    "this video is not available",
)


def is_youtube_query(query: str) -> bool:
    if not query:
        return False
    stripped = query.strip().lstrip("<").rstrip(">")
    return bool(_YT_URL_RE.search(stripped)) or stripped.lower().startswith(
        ("ytsearch:", "ytmsearch:")
    )


def youtube_block_hint(query: str, error_text: str) -> Optional[str]:
    """Explain an opaque YouTube failure, or return None if it is not one.

    "Something went wrong while looking up the track" is what youtube-source
    returns when YouTube refuses the request — overwhelmingly because the
    host IP is flagged, which is normal for datacenter and VPS ranges and
    does not happen on a home connection. The raw message sends people
    hunting for a bug in the bot instead.
    """
    if not is_youtube_query(query):
        return None
    lowered = (error_text or "").lower()
    if not any(phrase in lowered for phrase in _YT_BLOCK_PHRASES):
        return None
    return (
        "   ↳ YouTube កំពុងបដិសេធ server នេះ (IP ត្រូវបានទប់ស្កាត់)។ / "
        "YouTube is refusing this host — its IP is flagged, which is common "
        "for VPS and datacenter ranges.\n"
        "     ដំណោះស្រាយ / Fix: run the bot owner command to link a YouTube "
        "account (OAuth), which authenticates the requests. See "
        "modules/ll_yt_oauth.py. SoundCloud keeps working meanwhile."
    )


def unavailable_message(source: str, alternatives: str = "YouTube / SoundCloud") -> str:
    """Bilingual, actionable message for a source that cannot serve requests."""
    name = _DISPLAY.get(source, source.title())
    return (
        f"**ប្រភព {name} មិនអាចប្រើបានទេនៅពេលនេះ។ / "
        f"{name} is currently unavailable.**\n"
        f"សូមប្រើ {alternatives} ជំនួស — ស្វែងរកតាមឈ្មោះបទ ឬឈ្មោះសិល្បករ។ / "
        f"Please use {alternatives} instead — search by track or artist name."
    )
