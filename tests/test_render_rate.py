# -*- coding: utf-8 -*-
"""Identical player state must render an identical payload.

LavalinkPlayer.invoke_np already skips the Discord edit when the freshly
rendered payload equals ``self.last_data`` (utils/music/models.py:2561), so
no deduplication needed adding here. That mechanism is only as good as the
renders feeding it: if any skin varied its output for unchanged state — a
wall-clock timestamp, a set iteration order, a random hint — the comparison
would never match and the bot would edit the player message on every single
tick, spending rate-limit budget shared with real button presses.

These tests exist to keep that from happening silently. All 15 skins are
verified deterministic; the converse tests confirm real changes still
produce a new payload, so the dedup cannot freeze a live player.
"""
from __future__ import annotations

import pytest

from tests.conftest import make_player
from tests.test_skin_render import ALL_SKINS, _load_skin, _serialize


@pytest.mark.parametrize("kind,name", ALL_SKINS, ids=[f"{k}/{n}" for k, n in ALL_SKINS])
def test_identical_state_renders_identical_payload(kind, name):
    skin = _load_skin(kind, name)
    player = make_player()
    skin.setup_features(player)

    first = _serialize(skin.load(player))
    second = _serialize(skin.load(player))

    assert first == second, (
        f"{kind}/{name}: the same player state rendered two different payloads. "
        f"A non-deterministic render defeats edit-deduplication and forces a "
        f"Discord edit on every tick."
    )


def test_position_change_does_change_the_payload():
    """The converse: real progress must still produce a new payload."""
    skin = _load_skin("normal_player", "default_progressbar")
    player = make_player(position=10_000)
    skin.setup_features(player)
    early = _serialize(skin.load(player))

    player.position = 200_000
    late = _serialize(skin.load(player))

    assert early != late, "progress must be reflected in the payload"


def test_pause_state_changes_the_payload():
    skin = _load_skin("normal_player", "default")
    player = make_player()
    skin.setup_features(player)
    playing = _serialize(skin.load(player))

    player.paused = True
    paused = _serialize(skin.load(player))

    assert playing != paused, "pausing must be visible to the user"
