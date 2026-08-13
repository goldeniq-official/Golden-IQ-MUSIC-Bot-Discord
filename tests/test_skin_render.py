# -*- coding: utf-8 -*-
"""Every skin, every player state, must produce a Discord-valid payload."""
from __future__ import annotations

from importlib import import_module

import pytest
from disnake.ui.action_row import normalize_components_to_dict

from tests.conftest import all_player_states
from tests.discord_limits import assert_payload_valid

NORMAL_SKINS = [
    "classic", "default", "default_progressbar", "embed_link", "lite",
    "micro_controller", "micro_nc", "mini", "minimalist", "miniplayer",
]
STATIC_SKINS = ["classic", "default", "default_progressbar", "embed_link", "mini"]

ALL_SKINS = (
    [("normal_player", n) for n in NORMAL_SKINS]
    + [("static_player", n) for n in STATIC_SKINS]
)
STATE_NAMES = sorted(all_player_states().keys())

# Confirmed defects awaiting a Phase 2 fix. Keyed by (kind, name).
# Non-strict: the 'live' state takes a different branch and passes, and an
# xpass there must not be reported as a failure.
KNOWN_BROKEN = {
    ("static_player", "classic"): (
        "Phase 2: classic.py:43 calls queue_render.remaining_time_marker() but "
        "utils/music/ui/queue_render is never imported (only layout, theme are) "
        "-> NameError on every render except live streams. Introduced by adae264."
    ),
}


def _skin_params():
    params = []
    for kind, name in ALL_SKINS:
        reason = KNOWN_BROKEN.get((kind, name))
        marks = [pytest.mark.xfail(reason=reason, strict=False)] if reason else []
        params.append(pytest.param(kind, name, marks=marks, id=f"{kind}/{name}"))
    return params


SKIN_PARAMS = _skin_params()


def _load_skin(kind: str, name: str):
    module = import_module(f"utils.music.skins.{kind}.{name}")
    assert hasattr(module, "load"), f"{kind}.{name} has no load() entrypoint"
    return module.load()


def _serialize(data: dict) -> dict:
    """Convert a skin's raw output into the JSON Discord would receive.

    normalize_components_to_dict returns a ``(payloads, has_v2_component)``
    tuple, not a bare list — unpack it or every row reads as a bool.
    """
    payload = {}
    embeds = [e for e in (data.get("embeds") or []) if e is not None]
    payload["embeds"] = [e.to_dict() for e in embeds]
    components = data.get("components") or []
    payload["components"] = normalize_components_to_dict(components)[0] if components else []
    return payload


def test_all_fifteen_skins_are_covered():
    assert len(ALL_SKINS) == 15, f"expected 15 skins, found {len(ALL_SKINS)}"


@pytest.mark.parametrize("kind,name", SKIN_PARAMS)
@pytest.mark.parametrize("state", STATE_NAMES)
def test_skin_renders_valid_payload(kind, name, state):
    skin = _load_skin(kind, name)
    player = all_player_states()[state]
    skin.setup_features(player)
    data = skin.load(player)
    assert_payload_valid(_serialize(data), f"{kind}/{name} [{state}]")


@pytest.mark.parametrize("kind,name", ALL_SKINS, ids=[f"{k}/{n}" for k, n in ALL_SKINS])
def test_skin_declares_name_and_preview(kind, name):
    """Static skins deliberately append '_static' to distinguish themselves.

    Both skin families are keyed by ``skin.name`` in separate registries
    (utils/client.py:512 and :534), and the suffix is what keeps
    'default' and 'default_static' from colliding in the /change_skin list.
    """
    skin = _load_skin(kind, name)
    expected = f"{name}_static" if kind == "static_player" else name
    assert skin.name == expected, (
        f"{kind}/{name}: self-reported name is {skin.name!r}, expected {expected!r}"
    )
    assert isinstance(skin.preview, str) and skin.preview.startswith("http")
