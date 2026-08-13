# -*- coding: utf-8 -*-
"""Blocking I/O inside a coroutine stalls the whole bot.

asyncio runs one coroutine at a time. A synchronous requests.get() inside an
`async def` blocks the event loop for the full round trip, during which no
other command, button press, or voice event is processed — the reported
sluggishness.

This scans the whole tree rather than a fixed list, so a new blocking call
anywhere fails the build.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Modules whose synchronous APIs block the calling thread.
BLOCKING_MODULES = {"requests", "urllib"}
# Synchronous callables from otherwise-fine modules.
BLOCKING_CALLS = {("time", "sleep"), ("subprocess", "run"), ("subprocess", "call")}

SCAN_DIRS = ("modules", "utils")

# Known-blocking calls that run at startup or in a thread executor, where
# stalling the loop is not a concern. Each entry must say why.
ALLOWED = {
    # run_lavalink downloads the jar during startup, before the loop serves
    # traffic; it is called via a thread in utils/client.py.
    ("utils/music/local_lavalink.py", "requests"),
}


def _iter_python_files():
    for d in SCAN_DIRS:
        for path in (PROJECT_ROOT / d).rglob("*.py"):
            yield path


def _blocking_calls_in_coroutines(path: Path) -> list:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except SyntaxError:
        return []

    found = []
    for func in ast.walk(tree):
        if not isinstance(func, ast.AsyncFunctionDef):
            continue
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if not isinstance(target, ast.Attribute):
                continue
            if not isinstance(target.value, ast.Name):
                continue
            mod, attr = target.value.id, target.attr
            if mod in BLOCKING_MODULES or (mod, attr) in BLOCKING_CALLS:
                found.append(f"{func.name}():{node.lineno} -> {mod}.{attr}()")
    return found


ALL_FILES = sorted(_iter_python_files())


@pytest.mark.parametrize(
    "path", ALL_FILES, ids=[str(p.relative_to(PROJECT_ROOT)).replace("\\", "/") for p in ALL_FILES]
)
def test_no_blocking_io_inside_coroutines(path):
    rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    found = _blocking_calls_in_coroutines(path)
    found = [f for f in found
             if not any(rel == a_path and a_mod in f for a_path, a_mod in ALLOWED)]
    assert not found, (
        f"{rel}: blocking I/O inside async functions stalls the event loop, "
        f"freezing every other command and button while it runs: {found}"
    )


def _sync_functions_doing_blocking_io(tree) -> set:
    """Names of plain `def` functions in this module that block."""
    names = set()
    for func in ast.walk(tree):
        if not isinstance(func, ast.FunctionDef):
            continue
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                v = node.func.value
                if isinstance(v, ast.Name) and (
                    v.id in BLOCKING_MODULES or (v.id, node.func.attr) in BLOCKING_CALLS
                ):
                    names.add(func.name)
    return names


def _calls_awaiting_executor(func) -> set:
    """Call names that are handed to run_in_executor inside ``func``.

    run_in_executor(None, lambda: helper(...)) moves the blocking work to a
    thread, so the coroutine no longer stalls the loop. Those are fine.
    """
    offloaded = set()
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.attr if isinstance(node.func, ast.Attribute) else None
        if name != "run_in_executor":
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
                offloaded.add(inner.func.id)
    return offloaded


@pytest.mark.parametrize(
    "path", ALL_FILES, ids=[str(p.relative_to(PROJECT_ROOT)).replace("\\", "/") for p in ALL_FILES]
)
def test_blocking_helpers_are_not_called_bare_from_coroutines(path):
    """Catch the indirect case: coroutine -> plain helper -> requests.get().

    Checking only for `requests.get` written literally inside an `async def`
    misses this, and it stalls the loop just the same. Verified 2026-08-13:
    run_lavalink() blocks but is invoked through run_in_executor, so it is
    correctly excluded here.
    """
    rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except SyntaxError:
        pytest.skip(f"{rel} does not parse")

    blocking = _sync_functions_doing_blocking_io(tree)
    if not blocking:
        pytest.skip(f"{rel} defines no blocking sync helpers")

    offenders = []
    for func in ast.walk(tree):
        if not isinstance(func, ast.AsyncFunctionDef):
            continue
        offloaded = _calls_awaiting_executor(func)
        for node in ast.walk(func):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in blocking and node.func.id not in offloaded):
                offenders.append(f"{func.name}():{node.lineno} -> {node.func.id}()")

    assert not offenders, (
        f"{rel}: coroutine calls a blocking helper directly (use "
        f"loop.run_in_executor): {offenders}"
    )
