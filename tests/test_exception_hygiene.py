# -*- coding: utf-8 -*-
"""Ratchet down bare exception handlers.

Baseline 2026-08-13: 320 bare ``except:`` across modules/ and utils/. Each
one converts a real fault into silent misbehavior, which is why failures in
this bot could not be reported. Two of the confirmed user-visible bugs found
during this work were hidden behind one.

Lower the budgets as handlers are converted; never raise them.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Per-file budgets, set to the AST-measured count on 2026-08-13.
# A rise fails the build; a drop should be accompanied by tightening these.
#
# Counted with ast, not grep: grep reports 320 project-wide because it also
# matches `except:` inside commented-out triple-quoted blocks. The real
# figure is 303.
BUDGETS = {
    "modules/music/__init__.py": 85,
    "modules/music/controller.py": 14,
    "utils/music/models.py": 91,
    "modules/music_settings.py": 27,
    "utils/music/interactions.py": 11,
    "utils/others.py": 10,
    "modules/misc.py": 10,
    "utils/client.py": 9,
    "utils/music/local_lavalink.py": 9,
    "modules/legacy_cmds.py": 9,
    "modules/player_resume.py": 8,
}


def _count_bare_handlers(path: Path) -> int:
    # utf-8-sig: utils/music/interactions.py carries a UTF-8 BOM. Python's
    # own tokenizer strips it on import, but ast.parse on the decoded string
    # sees U+FEFF and raises SyntaxError.
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler) and node.type is None
    )


@pytest.mark.parametrize("path,budget", sorted(BUDGETS.items()))
def test_bare_handler_budget(path, budget):
    actual = _count_bare_handlers(PROJECT_ROOT / path)
    assert actual <= budget, (
        f"{path} has {actual} bare `except:` handlers, budget is {budget}. "
        f"Bare handlers hide faults — add a specific exception type."
    )


def test_budgets_are_calibrated():
    """Fails if a budget drifts far above reality — keeps the ratchet honest."""
    loose = {
        path: {"budget": budget, "actual": _count_bare_handlers(PROJECT_ROOT / path)}
        for path, budget in BUDGETS.items()
        if budget > _count_bare_handlers(PROJECT_ROOT / path) + 5
    }
    assert not loose, f"budgets far above actual (tighten them): {loose}"


def test_no_bare_handler_in_the_error_reporting_path():
    """The error path itself must never swallow — that hides everything else."""
    for rel in ("modules/error_handler.py", "utils/logs.py"):
        count = _count_bare_handlers(PROJECT_ROOT / rel)
        assert count == 0, (
            f"{rel} has {count} bare `except:` — the module responsible for "
            f"surfacing errors must not hide them"
        )
