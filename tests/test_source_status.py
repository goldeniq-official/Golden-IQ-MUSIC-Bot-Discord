# -*- coding: utf-8 -*-
"""Unavailable sources must say so, in Khmer and English.

Reproduced 2026-08-13 against live Lavalink: spsearch returned loadType
"error" and dzsearch returned "empty". Neither told the user anything
actionable.
"""
from __future__ import annotations

import pytest

from utils.music.source_status import detect_source, unavailable_message


@pytest.mark.parametrize("query,expected", [
    ("spsearch:adele hello", "spotify"),
    ("https://open.spotify.com/track/4iV5W9uYEdYUVa79Axb7Rh", "spotify"),
    ("<https://open.spotify.com/playlist/abc>", "spotify"),
    ("dzsearch:coldplay yellow", "deezer"),
    ("https://www.deezer.com/track/123", "deezer"),
    ("amsearch:test", "applemusic"),
    ("https://music.apple.com/us/album/x/1", "applemusic"),
])
def test_detects_source_from_query(query, expected):
    assert detect_source(query) == expected


@pytest.mark.parametrize("query", [
    "ytsearch:never gonna give you up",
    "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "scsearch:daft punk",
    "https://soundcloud.com/artist/track",
    "just some words",
    "",
])
def test_working_sources_are_not_flagged(query):
    assert detect_source(query) is None


def test_message_is_bilingual_and_actionable():
    msg = unavailable_message("spotify")
    assert "Spotify" in msg
    assert any("ក" <= ch <= "៿" for ch in msg), "missing Khmer text"
    assert "YouTube" in msg, "must name a source that actually works"


def test_message_names_the_right_source():
    assert "Deezer" in unavailable_message("deezer")
    assert "Apple Music" in unavailable_message("applemusic")


def test_disabled_source_is_computed_from_config():
    """Reads the real application.yml; skips if the host has no config."""
    from utils.music.source_status import compute_unavailable_sources

    unavailable = compute_unavailable_sources()
    if not unavailable:
        pytest.skip("no application.yml, or every source is configured")
    # Spotify credentials were rejected by Spotify (HTTP 400 invalid_client)
    # on 2026-08-13, so the source is switched off in application.yml.
    assert "spotify" in unavailable
    assert "deezer" in unavailable


@pytest.mark.parametrize("query,source", [
    ("spsearch:adele hello", "spotify"),
    ("https://open.spotify.com/track/abc", "spotify"),
    ("dzsearch:coldplay", "deezer"),
])
async def test_get_tracks_rejects_unavailable_source(query, source):
    """The guard must fire inside get_tracks, not just in isolation."""
    from modules.music import Music
    from utils.music.errors import GenericError
    from tests.conftest import FakePlayer

    cog = Music.__new__(Music)
    cog.bot = FakePlayer().bot
    cog.unavailable_sources = {source}

    with pytest.raises(GenericError) as excinfo:
        await Music.get_tracks(cog, query=query, ctx=None, user=None)

    message = str(excinfo.value)
    assert any("ក" <= ch <= "៿" for ch in message), "message must include Khmer"
    assert "YouTube" in message, "must point the user at a working source"


async def test_get_tracks_allows_working_sources():
    """A YouTube query must not be blocked by the guard.

    It will fail later for lack of a real node; the point is that it gets
    past the availability check rather than being rejected up front.
    """
    from modules.music import Music
    from utils.music.errors import GenericError
    from tests.conftest import FakePlayer

    cog = Music.__new__(Music)
    cog.bot = FakePlayer().bot
    cog.unavailable_sources = {"spotify", "deezer"}

    with pytest.raises(Exception) as excinfo:
        await Music.get_tracks(cog, query="ytsearch:test", ctx=None, user=None)

    if isinstance(excinfo.value, GenericError):
        assert "unavailable" not in str(excinfo.value).lower(), (
            "a working source was wrongly rejected by the availability guard"
        )
