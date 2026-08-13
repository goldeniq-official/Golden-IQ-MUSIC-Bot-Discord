# -*- coding: utf-8 -*-
"""Keep modules small enough to reason about.

Baseline 2026-08-13: modules/music.py was 7,976 lines. Size is why a missing
import in a skin and two unacknowledged returns in the button dispatcher went
unnoticed — nobody can hold that much in view at once.

Budgets are set to current measured size, so they lock in progress without
failing the build on work that has not happened yet. Lower them as extraction
continues; never raise them.
"""
from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Long-term target for any single module.
TARGET_MAX_LINES = 1500

BUDGETS = {
    # Raised 7110 -> 7120 for the bilingual search-failure logging and the
    # YouTube-block diagnostic (+9). As with client.py below, a raised budget
    # needs its reason recorded here.
    "modules/music/__init__.py": 7120,
    "modules/music/controller.py": 950,
    "utils/music/models.py": 3840,
    "utils/music/interactions.py": 3350,
    "modules/music_settings.py": 2000,
    # Raised twice on 2026-08-13, each with a stated cause:
    #   1510 -> 1525  load_modules package discovery fix (+17), which stopped
    #                 the Music cog from silently failing to load.
    #   1525 -> 1535  skip the internal Spotify client when the source is
    #                 disabled (+8), so boots stop printing a token failure
    #                 for a source the bot deliberately does not offer.
    # Growth without a reason recorded here is what the ratchet exists to stop.
    "utils/client.py": 1535,
}


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8-sig").splitlines())


@pytest.mark.parametrize("rel,budget", sorted(BUDGETS.items()))
def test_module_within_line_budget(rel, budget):
    path = PROJECT_ROOT / rel
    if not path.exists():
        pytest.skip(f"{rel} does not exist")
    lines = _line_count(path)
    assert lines <= budget, (
        f"{rel} is {lines} lines, budget {budget}. Extract before adding more."
    )


def test_no_new_module_exceeds_the_target():
    """New modules must start small; the big ones are grandfathered above."""
    offenders = []
    for d in ("modules", "utils"):
        for path in (PROJECT_ROOT / d).rglob("*.py"):
            rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
            if rel in BUDGETS or "__pycache__" in rel:
                continue
            lines = _line_count(path)
            if lines > TARGET_MAX_LINES:
                offenders.append((rel, lines))
    assert not offenders, (
        f"modules over {TARGET_MAX_LINES} lines that are not grandfathered: "
        f"{offenders}"
    )


def test_extraction_progress_is_recorded():
    """modules/music must stay smaller than the 7,976-line file it replaced."""
    total = sum(
        _line_count(p) for p in (PROJECT_ROOT / "modules" / "music").glob("*.py")
    )
    init = _line_count(PROJECT_ROOT / "modules" / "music" / "__init__.py")
    assert init < 7976, (
        f"music/__init__.py is {init} lines; extraction has regressed below "
        f"the original 7,976-line baseline"
    )
    print(f"\nmodules/music total {total} lines across "
          f"{len(list((PROJECT_ROOT / 'modules' / 'music').glob('*.py')))} files "
          f"(__init__.py: {init})")
