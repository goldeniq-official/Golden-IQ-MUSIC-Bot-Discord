# -*- coding: utf-8 -*-
"""Everything imported at module level must be declared in requirements.txt.

Caught in production, not by this suite: utils/db.py imports
tinydb_serialization, which was never declared. It happened to be installed
in the development venv, so every test passed, while a fresh Pterodactyl
server crashed on boot with ModuleNotFoundError. tinymongo lists it
transitively, but transitive availability is not a guarantee — and a module
we import directly is a direct dependency regardless.

Imports guarded by try/except ImportError are optional by design (nodriver,
the private dev package) and are excluded.
"""
from __future__ import annotations

import ast
import sys
from importlib.metadata import packages_distributions
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"

SCAN_DIRS = ("modules", "utils", "wavelink")
SCAN_FILES = ("main.py", "app.py", "web_app.py", "config_loader.py")

# Packages shipped with this repo or provided by the interpreter.
LOCAL_MODULES = {
    "utils", "modules", "wavelink", "config_loader", "web_app",
    "main", "app", "tests",
}


def _normalize(name: str) -> str:
    return name.lower().replace("_", "-").strip()


def _declared_distributions() -> set:
    """Distribution names named in requirements.txt, normalized."""
    declared = set()
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("git+"):
            # e.g. git+https://github.com/DisnakeDev/disnake.git@<sha>
            tail = line.split("/")[-1]
            declared.add(_normalize(tail.split(".git")[0].split("@")[0]))
            continue
        # Strip extras, markers, and version specifiers.
        name = line.split(";")[0].split("[")[0]
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            name = name.split(sep)[0]
        if name.strip():
            declared.add(_normalize(name))
    return declared


def _guarded_line_ranges(tree: ast.AST) -> list:
    """Line spans of try blocks that swallow ImportError."""
    spans = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        catches_import = any(
            handler.type is None
            or (isinstance(handler.type, ast.Name)
                and handler.type.id in {"ImportError", "ModuleNotFoundError", "Exception"})
            or (isinstance(handler.type, ast.Tuple)
                and any(isinstance(e, ast.Name)
                        and e.id in {"ImportError", "ModuleNotFoundError", "Exception"}
                        for e in handler.type.elts))
            for handler in node.handlers
        )
        if catches_import:
            for stmt in node.body:
                spans.append((stmt.lineno, getattr(stmt, "end_lineno", stmt.lineno)))
    return spans


def _iter_sources():
    for d in SCAN_DIRS:
        base = PROJECT_ROOT / d
        if base.exists():
            yield from base.rglob("*.py")
    for f in SCAN_FILES:
        p = PROJECT_ROOT / f
        if p.exists():
            yield p


def _unguarded_third_party_imports() -> dict:
    stdlib = set(sys.stdlib_module_names)
    found: dict[str, set] = {}

    for path in _iter_sources():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError:
            continue

        guarded = _guarded_line_ranges(tree)

        def is_guarded(lineno: int) -> bool:
            return any(start <= lineno <= end for start, end in guarded)

        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            if not names or is_guarded(node.lineno):
                continue
            for name in names:
                if name in stdlib or name in LOCAL_MODULES:
                    continue
                rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
                found.setdefault(name, set()).add(f"{rel}:{node.lineno}")

    return found


def test_requirements_file_exists():
    assert REQUIREMENTS.is_file()


def test_every_unguarded_import_is_declared():
    declared = _declared_distributions()
    module_to_dist = packages_distributions()

    undeclared = {}
    for module, sites in sorted(_unguarded_third_party_imports().items()):
        dists = module_to_dist.get(module)
        if dists is None:
            # Not installed here; fall back to comparing the module name.
            if _normalize(module) in declared:
                continue
            undeclared[module] = sorted(sites)
            continue
        if any(_normalize(d) in declared for d in dists):
            continue
        undeclared[module] = sorted(sites)

    assert not undeclared, (
        "modules imported without a try/except guard but missing from "
        f"requirements.txt — these crash a fresh server on boot: {undeclared}"
    )


@pytest.mark.parametrize("module", ["tinydb_serialization", "aiohttp", "pymongo"])
def test_specific_direct_imports_are_declared(module):
    """Regression guards for the ones that were relied on transitively.

    tinydb_serialization is the one that actually took production down.
    """
    declared = _declared_distributions()
    dists = packages_distributions().get(module, [module])
    assert any(_normalize(d) in declared for d in dists), (
        f"{module} is imported directly but only available transitively; "
        f"declare it in requirements.txt"
    )
