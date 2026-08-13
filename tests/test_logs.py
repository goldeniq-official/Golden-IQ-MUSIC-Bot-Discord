# -*- coding: utf-8 -*-
"""Error IDs make failures reportable.

The bot swallowed errors in 320 bare handlers and showed users a generic red
embed carrying nothing actionable, so the owner could not report what broke.
Every recorded error now gets a short ID, shown to the user and resolvable
here to a full traceback.
"""
import re

import pytest

from utils.logs import record_error, lookup_error, setup_logging

ID_RE = re.compile(r"^[A-Z0-9]{8}$")


@pytest.fixture(autouse=True)
def _logging(tmp_path):
    setup_logging(log_dir=str(tmp_path))


def _boom():
    raise ValueError("សាកល្បង / test failure")


def test_record_error_returns_short_id():
    try:
        _boom()
    except ValueError as exc:
        eid = record_error(exc, guild=3003, control="musicplayer_skip")
    assert ID_RE.match(eid), f"{eid!r} is not an 8-char uppercase ID"


def test_recorded_traceback_is_retrievable():
    try:
        _boom()
    except ValueError as exc:
        eid = record_error(exc, guild=3003)
    stored = lookup_error(eid)
    assert stored is not None
    assert "ValueError" in stored
    assert "សាកល្បង" in stored, "Khmer text must survive the round trip"


def test_ids_are_unique_per_occurrence():
    ids = []
    for _ in range(5):
        try:
            _boom()
        except ValueError as exc:
            ids.append(record_error(exc))
    assert len(set(ids)) == 5


def test_context_is_stored_with_the_traceback():
    try:
        _boom()
    except ValueError as exc:
        eid = record_error(exc, guild=3003, control="musicplayer_skip", user=1001)
    stored = lookup_error(eid)
    assert "musicplayer_skip" in stored
    assert "3003" in stored


def test_unknown_id_returns_none():
    assert lookup_error("ZZZZZZZZ") is None


def test_ids_avoid_lookalike_characters():
    """Users read these off a screen and type them back."""
    ids = []
    for _ in range(40):
        try:
            _boom()
        except ValueError as exc:
            ids.append(record_error(exc))
    joined = "".join(ids)
    for ch in "IO01":
        assert ch not in joined, f"{ch!r} is easily misread when reporting an ID"


def test_error_is_written_to_the_log_file(tmp_path):
    setup_logging(log_dir=str(tmp_path))
    try:
        _boom()
    except ValueError as exc:
        eid = record_error(exc, guild=3003)

    log_file = tmp_path / "bot.log"
    assert log_file.exists(), "no log file was created"
    content = log_file.read_text(encoding="utf-8")
    assert eid in content
    assert "ValueError" in content


def test_cache_is_bounded():
    """A long-running bot must not accumulate tracebacks forever."""
    from utils.logs import _MAX_CACHE, _errors

    for _ in range(_MAX_CACHE + 50):
        try:
            _boom()
        except ValueError as exc:
            record_error(exc)
    assert len(_errors) <= _MAX_CACHE
