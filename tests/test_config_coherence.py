# -*- coding: utf-8 -*-
"""application.yml and .env must agree about which audio sources work.

Reproduced 2026-08-13 against a live local Lavalink v4 node:
    spsearch:adele hello   -> loadType "error" (FriendlyException)
    dzsearch:coldplay yellow -> loadType "empty"

because application.yml enables Spotify with empty credentials and leaves
Deezer half-configured while the Python layer still offers it.

These tests read credentials to check presence only. They never print or
assert on a value.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_YML = PROJECT_ROOT / "application.yml"
ENV = PROJECT_ROOT / ".env"


@pytest.fixture(scope="module")
def lavasrc():
    if not APP_YML.exists():
        pytest.skip("application.yml not present (gitignored; host-specific)")
    data = YAML(typ="safe").load(APP_YML.read_text(encoding="utf-8"))
    plugins = (data or {}).get("plugins") or {}
    src = plugins.get("lavasrc")
    if not src:
        pytest.skip("lavasrc plugin not configured")
    return src


def _env_has(key: str) -> bool:
    if not ENV.exists():
        return False
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            value = line.split("=", 1)[1].strip().strip("'\"")
            return bool(value)
    return False


def test_spotify_enabled_implies_credentials(lavasrc):
    enabled = (lavasrc.get("sources") or {}).get("spotify", False)
    if not enabled:
        pytest.skip("Spotify source disabled")
    conf = lavasrc.get("spotify") or {}
    assert conf.get("clientId"), (
        "application.yml enables Spotify but clientId is empty — "
        "this is why spsearch returns loadType 'error'"
    )
    assert conf.get("clientSecret"), (
        "application.yml enables Spotify but clientSecret is empty"
    )


def test_env_spotify_credentials_are_present():
    """The credentials exist in .env — they are simply not wired into lavasrc."""
    assert _env_has("SPOTIFY_CLIENT_ID"), ".env is missing SPOTIFY_CLIENT_ID"
    assert _env_has("SPOTIFY_CLIENT_SECRET"), ".env is missing SPOTIFY_CLIENT_SECRET"


def test_deezer_is_coherently_configured(lavasrc):
    """If Deezer has no key it must be off everywhere, not half-on.

    Half-on is what produced dzsearch -> loadType "empty": a silent nothing
    instead of a message the user can act on.
    """
    conf = lavasrc.get("deezer") or {}
    enabled = (lavasrc.get("sources") or {}).get("deezer", False)
    if conf.get("masterDecryptionKey"):
        assert enabled, "Deezer key present but source disabled"
    else:
        assert not enabled, "Deezer enabled without a key — queries return empty"


@pytest.mark.parametrize("section", ["spotify", "applemusic"])
def test_region_is_not_the_upstream_fork_default(lavasrc, section):
    code = (lavasrc.get(section) or {}).get("countryCode")
    if code is None:
        pytest.skip(f"lavasrc.{section} has no countryCode")
    assert code != "BR", (
        f"lavasrc.{section}.countryCode is still 'BR' from the upstream "
        f"Brazilian fork; should be 'KH'"
    )
