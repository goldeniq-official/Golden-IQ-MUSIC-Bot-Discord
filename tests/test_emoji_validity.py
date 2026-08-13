# -*- coding: utf-8 -*-
"""Component emoji must be real emoji or well-formed custom emoji.

Discord rejects non-emoji glyphs (math symbols, dingbats, bare arrows) used
as Button.emoji or SelectOption.emoji. The rejection surfaces to users as the
red "interaction failed" text. utils/music/ui/emoji_set.py documents this
rule in its module docstring; this module enforces it.
"""
from __future__ import annotations

import re
from importlib import import_module

import emoji as emoji_lib
import pytest
from disnake.ui.action_row import normalize_components_to_dict

from tests.conftest import all_player_states
from tests.test_skin_render import SKIN_PARAMS

CUSTOM_EMOJI_RE = re.compile(r"^<a?:[A-Za-z0-9_]{2,32}:\d{15,25}>$")
_SELECT_TYPES = (3, 5, 6, 7, 8)


def is_valid_component_emoji(value: str) -> bool:
    if not value:
        return False
    if CUSTOM_EMOJI_RE.match(value):
        return True
    return emoji_lib.purely_emoji(value)


def _collect_component_emoji(payload_rows) -> list:
    found = []
    for row in payload_rows:
        for child in row.get("components") or []:
            if (em := child.get("emoji")) and em.get("name") and not em.get("id"):
                found.append((child.get("custom_id"), em["name"]))
            for opt in child.get("options") or []:
                if (em := opt.get("emoji")) and em.get("name") and not em.get("id"):
                    found.append((opt.get("value"), em["name"]))
    return found


def test_validator_accepts_real_emoji():
    assert is_valid_component_emoji("⏯️")
    assert is_valid_component_emoji("🎧")
    assert is_valid_component_emoji("<:custom:123456789012345678>")


def test_validator_rejects_non_emoji_glyphs():
    # These are the exact glyphs currently present in theme.STATUS_ICONS.
    assert not is_valid_component_emoji("∞")   # U+221E math infinity
    assert not is_valid_component_emoji("✓")   # U+2713 check mark, not emoji
    assert not is_valid_component_emoji("↻")   # U+21BB clockwise open circle arrow
    assert not is_valid_component_emoji("")


def test_emoji_set_defaults_are_all_valid():
    """Verified clean 2026-08-13 — this is a guard against regression."""
    from utils.music.ui.emoji_set import _DEFAULTS

    bad = {n: v for n, v in _DEFAULTS.items() if not is_valid_component_emoji(v)}
    assert not bad, f"emoji_set._DEFAULTS contains non-emoji values: {bad}"


@pytest.mark.xfail(reason="Phase 2 Task 10 fixes the 3 invalid STATUS_ICONS glyphs")
def test_status_icons_are_component_safe():
    """STATUS_ICONS values are text-only today, so these are latent traps.

    Measured 2026-08-13: 'loading' (↻ U+21BB), 'autoplay' (∞ U+221E), and
    'ok' (✓ U+2713) are not emoji. They render fine inside an embed
    description, but would be rejected the moment one is passed as a
    component emoji. This is a trap to close, not a live user-visible bug.
    """
    from utils.music.ui.theme import STATUS_ICONS

    bad = {n: v for n, v in STATUS_ICONS.items() if not is_valid_component_emoji(v)}
    assert not bad, f"theme.STATUS_ICONS contains non-emoji values: {bad}"


@pytest.mark.parametrize("kind,name", SKIN_PARAMS)
def test_skin_component_emoji_are_valid(kind, name):
    module = import_module(f"utils.music.skins.{kind}.{name}")
    skin = module.load()
    player = all_player_states()["playing"]
    skin.setup_features(player)
    data = skin.load(player)
    components = data.get("components") or []
    if not components:
        pytest.skip(f"{kind}/{name} renders no components")
    rows = normalize_components_to_dict(components)[0]
    bad = [(cid, val) for cid, val in _collect_component_emoji(rows)
           if not is_valid_component_emoji(val)]
    assert not bad, f"{kind}/{name} uses invalid component emoji: {bad}"
