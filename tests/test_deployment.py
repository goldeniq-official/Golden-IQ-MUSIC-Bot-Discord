# -*- coding: utf-8 -*-
"""Pterodactyl deployment must be correct for fresh servers.

application.yml is gitignored, so a Pterodactyl install never has one — the
bot generates it from application.yml.example on first run
(utils/music/local_lavalink.py:228). That makes the example file, not the
local application.yml, the thing every deployed server actually gets. Fixes
applied only to the local copy never reach production.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = PROJECT_ROOT / "application.yml.example"
EGG = PROJECT_ROOT / "deploy_handlers" / "egg-golden-iq-music-bot.json"
START_SH = PROJECT_ROOT / "deploy_handlers" / "start.sh"
LOCAL_LAVALINK = PROJECT_ROOT / "utils" / "music" / "local_lavalink.py"


@pytest.fixture(scope="module")
def example_lavasrc():
    data = YAML(typ="safe").load(EXAMPLE.read_text(encoding="utf-8"))
    return ((data or {}).get("plugins") or {}).get("lavasrc") or {}


@pytest.fixture(scope="module")
def egg():
    return json.loads(EGG.read_text(encoding="utf-8"))


def test_example_config_exists():
    """Without it, first boot raises FileNotFoundError and Lavalink never starts."""
    assert EXAMPLE.is_file(), "application.yml.example is what fresh servers get"


@pytest.mark.parametrize("section", ["spotify", "applemusic"])
def test_example_region_is_not_the_fork_default(example_lavasrc, section):
    code = (example_lavasrc.get(section) or {}).get("countryCode")
    if code is None:
        pytest.skip(f"lavasrc.{section} has no countryCode")
    assert code != "BR", (
        f"application.yml.example still ships countryCode 'BR' for {section}. "
        f"Every fresh Pterodactyl deploy would be configured for Brazil."
    )


def test_example_does_not_enable_sources_without_credentials(example_lavasrc):
    required = {"spotify": ("clientId", "clientSecret"),
                "deezer": ("masterDecryptionKey",)}
    enabled = example_lavasrc.get("sources") or {}
    offenders = []
    for source, keys in required.items():
        if not enabled.get(source):
            continue
        conf = example_lavasrc.get(source) or {}
        missing = [k for k in keys if not conf.get(k)]
        if missing:
            offenders.append((source, missing))
    assert not offenders, (
        f"application.yml.example enables sources with blank credentials, so "
        f"fresh deploys hit the same opaque failures: {offenders}"
    )


def test_lavalink_initial_ram_is_actually_used():
    """-Xms must use the initial-RAM setting, not the limit.

    The egg exposes LAVALINK_INITIAL_RAM (default 60) and LAVALINK_RAM_LIMIT
    (default 200). Passing the limit to -Xms makes the JVM reserve the whole
    heap at startup, which can push a small Pterodactyl plan into OOM and
    makes LAVALINK_INITIAL_RAM meaningless.
    """
    source = LOCAL_LAVALINK.read_text(encoding="utf-8-sig")
    match = re.search(r'-Xms\{(\w+)\}m', source)
    assert match, "could not find the -Xms flag construction"
    assert match.group(1) == "lavalink_initial_ram", (
        f"-Xms is built from {match.group(1)!r}; it must use "
        f"lavalink_initial_ram or the panel setting has no effect"
    )


def test_egg_startup_runs_the_real_entrypoint(egg):
    assert "start.sh" in egg["startup"]
    assert "python3 -u main.py" in START_SH.read_text(encoding="utf-8"), (
        "start.sh must launch main.py — app.py is only 'from main import *'"
    )


def test_egg_declares_required_runtime_variables(egg):
    names = {v["env_variable"] for v in egg["variables"]}
    for required in ("TOKEN", "GIT_ADDRESS", "BRANCH", "AUTO_UPDATE",
                     "RUN_LOCAL_LAVALINK", "LAVALINK_INITIAL_RAM",
                     "LAVALINK_RAM_LIMIT"):
        assert required in names, f"egg is missing the {required} variable"


def test_egg_does_not_install_dev_dependencies(egg):
    """requirements-dev.txt is test-only and must never reach a server."""
    install = egg["scripts"]["installation"]["script"]
    assert "requirements-dev" not in install
    assert "requirements-dev" not in START_SH.read_text(encoding="utf-8")


def test_start_script_launches_with_unbuffered_output(egg):
    """Pterodactyl consoles need unbuffered output or logs appear frozen."""
    assert "python3 -u" in START_SH.read_text(encoding="utf-8")


def test_source_status_falls_back_to_the_template(tmp_path, monkeypatch):
    """A fresh server has no application.yml until Lavalink first runs.

    The Music cog is constructed before that, so without a template fallback
    the very first boot would advertise Spotify and Deezer as working.
    """
    from utils.music.source_status import compute_unavailable_sources

    monkeypatch.chdir(tmp_path)
    template = tmp_path / "application.yml.example"
    template.write_text(
        "plugins:\n"
        "  lavasrc:\n"
        "    sources:\n"
        "      spotify: false\n"
        "      deezer: false\n",
        encoding="utf-8",
    )

    unavailable = compute_unavailable_sources("application.yml")
    assert "spotify" in unavailable
    assert "deezer" in unavailable


def test_source_status_tolerates_a_server_with_neither_file(tmp_path, monkeypatch):
    from utils.music.source_status import compute_unavailable_sources

    monkeypatch.chdir(tmp_path)
    assert compute_unavailable_sources("application.yml") == set()
