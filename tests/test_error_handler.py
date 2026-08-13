# -*- coding: utf-8 -*-
"""The generic red embed must carry a reportable Error ID."""
import re

import pytest

from utils.logs import setup_logging, lookup_error

ID_IN_TEXT = re.compile(r"[A-Z0-9]{8}")


@pytest.fixture(autouse=True)
def _logging(tmp_path):
    setup_logging(log_dir=str(tmp_path))


def test_generic_embed_includes_a_resolvable_error_id():
    from modules.error_handler import build_generic_error_embed

    try:
        raise RuntimeError("ការសាកល្បង / test")
    except RuntimeError as exc:
        embed, error_id = build_generic_error_embed(exc, guild=3003)

    assert ID_IN_TEXT.search(embed.description or ""), (
        "the red embed must show the Error ID so the owner can report it"
    )
    assert error_id in (embed.description or "")
    assert lookup_error(error_id) is not None


def test_generic_embed_is_bilingual():
    from modules.error_handler import build_generic_error_embed

    try:
        raise RuntimeError("x")
    except RuntimeError as exc:
        embed, _ = build_generic_error_embed(exc)

    text = f"{embed.title or ''}{embed.description or ''}"
    assert any("ក" <= ch <= "៿" for ch in text), "missing Khmer text"
    assert re.search(r"[A-Za-z]{4,}", text), "missing English text"


def test_embed_names_the_exception_type():
    from modules.error_handler import build_generic_error_embed

    try:
        raise KeyError("missing")
    except KeyError as exc:
        embed, _ = build_generic_error_embed(exc)

    assert "KeyError" in (embed.description or "")


def test_context_reaches_the_stored_traceback():
    from modules.error_handler import build_generic_error_embed

    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        _, error_id = build_generic_error_embed(
            exc, guild=3003, user=1001, command="play"
        )

    stored = lookup_error(error_id)
    assert "3003" in stored and "play" in stored
