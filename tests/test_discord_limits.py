# -*- coding: utf-8 -*-
import pytest

from tests.discord_limits import assert_payload_valid


def _embed(**over):
    base = {"description": "hello"}
    base.update(over)
    return base


def test_accepts_a_valid_payload():
    assert_payload_valid({"embeds": [_embed()], "components": []}, "ok-case")


def test_rejects_overlong_description():
    with pytest.raises(AssertionError, match="description"):
        assert_payload_valid({"embeds": [_embed(description="x" * 4097)]}, "bad")


def test_rejects_too_many_action_rows():
    rows = [{"type": 1, "components": [{"type": 2, "custom_id": f"c{i}", "style": 2}]}
            for i in range(6)]
    with pytest.raises(AssertionError, match="action row"):
        assert_payload_valid({"components": rows}, "bad")


def test_rejects_overlong_custom_id():
    rows = [{"type": 1, "components": [{"type": 2, "custom_id": "x" * 101, "style": 2}]}]
    with pytest.raises(AssertionError, match="custom_id"):
        assert_payload_valid({"components": rows}, "bad")


def test_rejects_embed_total_over_6000():
    embeds = [_embed(description="x" * 3500), _embed(description="y" * 3500)]
    with pytest.raises(AssertionError, match="6000"):
        assert_payload_valid({"embeds": embeds}, "bad")
