# -*- coding: utf-8 -*-
"""Slash command metadata must fit Discord's limits.

Descriptions are built as f"{desc_prefix}{text}". Measured 2026-08-13:
Music 89/100, Settings 88/100 — about 11 characters of headroom. Khmer text
added carelessly overflows this, and a single overflow fails command sync for
the entire bot, not just the offending command.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

DESCRIPTION_LIMIT = 100

PROJECT_ROOT = Path(__file__).resolve().parent.parent

COG_FILES = ["modules/music.py", "modules/music_settings.py",
             "modules/misc.py", "modules/lastfm.py"]

PREFIX_RE = re.compile(r'^\s{4}emoji\s*=\s*"(.+?)"\s*$\n\s{4}name\s*=\s*"(.+?)"\s*$',
                       re.MULTILINE)
DESC_RE = re.compile(r'description=f"\{desc_prefix\}([^"]*)"')
PLAIN_DESC_RE = re.compile(r'description="([^"]*)"')


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _prefix_lengths(source: str) -> list[int]:
    return [len(f"[{em} {nm}] | ") for em, nm in PREFIX_RE.findall(source)]


@pytest.mark.parametrize("path", COG_FILES)
def test_prefixed_descriptions_fit(path):
    source = _read(path)
    prefixes = _prefix_lengths(source)
    if not prefixes:
        pytest.skip(f"{path} declares no desc_prefix")
    worst_prefix = max(prefixes)
    offenders = [
        (len(body) + worst_prefix, body)
        for body in DESC_RE.findall(source)
        if len(body) + worst_prefix > DESCRIPTION_LIMIT
    ]
    assert not offenders, (
        f"{path}: descriptions exceed {DESCRIPTION_LIMIT} chars "
        f"(prefix={worst_prefix}): {offenders}"
    )


@pytest.mark.parametrize("path", COG_FILES)
def test_plain_descriptions_fit(path):
    source = _read(path)
    offenders = [(len(d), d) for d in PLAIN_DESC_RE.findall(source)
                 if len(d) > DESCRIPTION_LIMIT]
    assert not offenders, f"{path}: descriptions over {DESCRIPTION_LIMIT}: {offenders}"


@pytest.mark.parametrize("path", COG_FILES)
def test_headroom_is_reported(path):
    """Prints remaining headroom so reviewers can see how tight this is."""
    source = _read(path)
    prefixes = _prefix_lengths(source)
    bodies = DESC_RE.findall(source)
    if not prefixes or not bodies:
        pytest.skip(f"{path} has no prefixed descriptions")
    worst = max(len(b) for b in bodies) + max(prefixes)
    print(f"\n{path}: worst description {worst}/{DESCRIPTION_LIMIT} "
          f"({DESCRIPTION_LIMIT - worst} chars headroom)")
    assert worst <= DESCRIPTION_LIMIT


@pytest.mark.xfail(reason="Phase 2 Task 11 removes the pt_BR fork leftovers")
def test_no_portuguese_locale_leftovers():
    """The fork's pt_BR localizations are dead weight; Khmer is the target."""
    offenders = []
    for path in COG_FILES:
        source = _read(path)
        count = source.count("Locale.pt_BR")
        if count:
            offenders.append((path, count))
    assert not offenders, f"pt_BR locale leftovers from the upstream fork: {offenders}"
