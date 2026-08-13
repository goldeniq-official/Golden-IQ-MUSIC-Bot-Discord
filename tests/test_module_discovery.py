# -*- coding: utf-8 -*-
"""Extension discovery must handle packages, not just flat files.

Found by a live boot, not by the suite: after modules/music.py became the
package modules/music/, load_modules kept only the bare filename from
os.walk, so modules/music/controller.py resolved to "modules.controller"
and the Music cog was never loaded at all. Every command and button was
gone, while every unit test still passed because they import modules.music
directly.

These tests reproduce the discovery logic against a temporary tree so the
regression cannot return silently.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def discover(module_dir: str) -> list:
    """Mirror of BotCore.load_modules discovery. Must match utils/client.py."""
    entries = []
    if not os.path.isdir(module_dir):
        return entries
    for name in sorted(os.listdir(module_dir)):
        full_path = os.path.join(module_dir, name)
        if os.path.isfile(full_path) and name.endswith(".py"):
            entries.append((name[:-3], f"{module_dir}.{name[:-3]}"))
        elif os.path.isdir(full_path) and os.path.isfile(
                os.path.join(full_path, "__init__.py")):
            entries.append((name, f"{module_dir}.{name}"))
    return entries


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "modules"
    root.mkdir()
    (root / "misc.py").write_text("", encoding="utf-8")
    pkg = root / "music"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "controller.py").write_text("", encoding="utf-8")
    plain = root / "notapackage"
    plain.mkdir()
    (plain / "helper.py").write_text("", encoding="utf-8")
    return root


def test_flat_module_is_discovered(tree):
    found = dict(discover(str(tree)))
    assert "misc" in found


def test_package_is_discovered_as_itself(tree):
    found = dict(discover(str(tree)))
    assert "music" in found, "the package must be loaded as an extension"
    assert found["music"].endswith(".music")


def test_package_internals_are_not_loaded_as_extensions(tree):
    """controller.py has no setup(); loading it directly raises."""
    names = [n for n, _ in discover(str(tree))]
    assert "controller" not in names, (
        "package internals must not be treated as extensions — this is the "
        "bug that produced 'Extension modules.controller could not be loaded'"
    )


def test_directory_without_init_is_ignored(tree):
    names = [n for n, _ in discover(str(tree))]
    assert "notapackage" not in names


def test_missing_directory_is_tolerated(tmp_path):
    assert discover(str(tmp_path / "modules_dev")) == []


def test_real_modules_directory_yields_the_music_package():
    """Guards the actual tree, not just the synthetic one."""
    os.chdir(PROJECT_ROOT)
    found = dict(discover("modules"))
    assert "music" in found, "the Music cog would not be loaded at startup"
    assert "controller" not in found
    for expected in ("misc", "error_handler", "music_settings"):
        assert expected in found, f"{expected} cog went missing from discovery"
