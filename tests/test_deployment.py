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


def test_egg_skin_defaults_name_real_skins(egg):
    """A skin name typo in the panel silently breaks every player."""
    from tests.test_skin_render import NORMAL_SKINS, STATIC_SKINS

    by_name = {v["env_variable"]: v["default_value"] for v in egg["variables"]}
    assert by_name.get("DEFAULT_SKIN") in NORMAL_SKINS, (
        f"DEFAULT_SKIN={by_name.get('DEFAULT_SKIN')!r} is not a real skin; "
        f"valid: {NORMAL_SKINS}"
    )
    assert by_name.get("DEFAULT_STATIC_SKIN") in STATIC_SKINS, (
        f"DEFAULT_STATIC_SKIN={by_name.get('DEFAULT_STATIC_SKIN')!r} is not a "
        f"real static skin; valid: {STATIC_SKINS}"
    )


def test_egg_variable_descriptions_list_valid_skins(egg):
    """The panel help text must match the skins that actually ship."""
    from tests.test_skin_render import NORMAL_SKINS, STATIC_SKINS

    by_name = {v["env_variable"]: v for v in egg["variables"]}
    for env, expected in (("DEFAULT_SKIN", NORMAL_SKINS),
                          ("DEFAULT_STATIC_SKIN", STATIC_SKINS)):
        desc = by_name[env]["description"]
        missing = [s for s in expected if s not in desc]
        assert not missing, f"{env} description omits real skins: {missing}"


def test_egg_variables_are_well_formed(egg):
    required_keys = {"name", "description", "env_variable", "default_value",
                     "user_viewable", "user_editable", "rules", "field_type"}
    for var in egg["variables"]:
        missing = required_keys - set(var)
        assert not missing, f"{var.get('env_variable')} missing keys: {missing}"


def test_egg_has_no_duplicate_variables(egg):
    names = [v["env_variable"] for v in egg["variables"]]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate panel variables would confuse the UI: {dupes}"


def test_start_script_is_valid_bash():
    import shutil
    import subprocess

    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available")
    result = subprocess.run([bash, "-n", str(START_SH)],
                            capture_output=True, text=True)
    assert result.returncode == 0, f"start.sh has a syntax error:\n{result.stderr}"


def test_start_script_aborts_when_dependencies_fail():
    """Without an explicit check the bot started anyway and died on ImportError.

    start.sh does not use `set -e`, so an unchecked pip failure falls through
    to the exec.
    """
    source = START_SH.read_text(encoding="utf-8")
    assert "if ! python3 -m pip install" in source, (
        "pip install result must be checked before starting the bot"
    )
    # Match the directive at the start of a line, not the phrase inside the
    # comment that explains why it is absent.
    has_set_e = any(re.match(r"\s*set\s+-[a-z]*e", line)
                    for line in source.splitlines())
    assert not has_set_e, (
        "if set -e is added, simplify the explicit pip check rather than "
        "leaving both in place"
    )


def test_start_script_guards_the_python_version():
    source = START_SH.read_text(encoding="utf-8")
    assert "sys.version_info[:2] >= (3, 11)" in source, (
        "an old Docker image should fail with a clear message, not an "
        "obscure error deeper in startup"
    )


def test_shell_scripts_are_stored_with_lf_endings():
    """A CRLF shebang makes Linux fail with a misleading "not found" error.

    The repo is developed on Windows; without .gitattributes this depends on
    every contributor having core.autocrlf set the same way.
    """
    import subprocess

    result = subprocess.run(
        ["git", "ls-files", "--eol", "*.sh"],
        cwd=PROJECT_ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip("git not available")

    offenders = []
    for line in result.stdout.splitlines():
        # Format: "i/lf    w/crlf  attr/text=auto  path"
        if line.startswith("i/crlf") or line.startswith("i/mixed"):
            offenders.append(line)
    assert not offenders, f"shell scripts stored with CRLF in git: {offenders}"


def test_gitattributes_pins_shell_script_endings():
    attrs = PROJECT_ROOT / ".gitattributes"
    assert attrs.is_file(), (
        ".gitattributes is what keeps a Windows contributor from committing "
        "a CRLF start.sh that will not run on the server"
    )
    content = attrs.read_text(encoding="utf-8")
    assert "*.sh" in content and "eol=lf" in content
