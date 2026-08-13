# Golden IQ MUSIC Bot Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a regression safety net for a 30,701-line Discord music bot, then use it to fix confirmed breakages, surface swallowed errors, remove event-loop stalls, and decompose the 7,929-line music module.

**Architecture:** Tests come first and act as the acceptance gate for every later phase. An offline harness fabricates player and interaction objects, renders all 15 skins, and drives all 30 button/select handlers without a live Discord gateway — because clicking in Discord cannot be automated. Live boots against a local Lavalink node verify integration at each phase boundary.

**Tech Stack:** Python 3.14.6, disnake (pinned fork commit `96ed4459`), wavelink (vendored), Lavalink v4 + lavasrc/youtube plugins, MongoDB Atlas (motor), pytest + pytest-asyncio.

**Spec:** [docs/superpowers/specs/2026-08-13-bot-hardening-design.md](../specs/2026-08-13-bot-hardening-design.md)

## Global Constraints

- **Python version:** 3.14.6. The `venv/` holds cp314 wheels; any other minor version breaks them.
- **UI language:** Khmer + English side by side, Khmer first, separated by ` / `. Applies to every user-facing string.
- **Slash command description limit:** 100 characters total including `desc_prefix`. Current worst cases: `Music` cog 89/100 (prefix `[🎶 Music] | ` = 12 chars), `Settings` cog 88/100 (prefix `[🔧 Settings] | ` = 15 chars). **~11 characters of headroom** — any added text must be measured.
- **No new runtime dependencies.** Test-only dependencies go in `requirements-dev.txt`, never `requirements.txt`.
- **Behavior preservation:** Phases 3–5 must not change user-visible behavior. The Phase 1 suite passing identically before and after is the acceptance criterion.
- **Windows console:** stdio must be UTF-8 or emoji logging raises `UnicodeEncodeError` (default codepage here is cp1252).
- **Never commit secrets.** `.env` and `application.yml` are gitignored and contain live credentials. Tests must read them without printing values.
- **Commit style:** conventional commits, trailer `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

## Verified Baseline (2026-08-13)

Facts established by measurement. Do not re-derive; do re-verify if something contradicts them.

- Bot boots, loads 10 cogs, syncs commands, connects local Lavalink v4 — **working**.
- `ytsearch:` 20 hits, `scsearch:` 10 hits, YouTube URL loads — **working**.
- `spsearch:` → `loadType: error` (`FriendlyException`) — **broken**.
- `dzsearch:` → `loadType: empty` — **broken**.
- `https://cdn.discordapp.com/attachments/554468640942981147/1082887587770937455/rainbow_bar2.gif` → **HTTP 404**, used in 4 places.
- 320 bare `except:`; 370 `except`→`pass`; 0 test files.
- 15 skins: normal = `classic default default_progressbar embed_link lite micro_controller micro_nc mini minimalist miniplayer`; static = `classic default default_progressbar embed_link mini`.
- 30 `PlayerControls` constants in `utils/others.py:199-229`.

## File Structure

| Path | Responsibility |
| --- | --- |
| `requirements-dev.txt` | Test-only dependencies (create) |
| `pytest.ini` | pytest + asyncio configuration (create) |
| `tests/conftest.py` | Shared fixtures: `FakeBot`, `FakeGuild`, `FakeTrack`, `FakePlayer`, `FakeInteraction` (create) |
| `tests/discord_limits.py` | Discord API limit constants + `assert_payload_valid()` validator (create) |
| `tests/test_skin_render.py` | Renders all 15 skins across all player states (create) |
| `tests/test_emoji_validity.py` | Every component emoji is a real emoji (create) |
| `tests/test_player_controller.py` | All 30 controls dispatch without escaping exceptions (create) |
| `tests/test_command_metadata.py` | Command name/description limits (create) |
| `tests/test_config_coherence.py` | `application.yml` ↔ `.env` agreement (create) |
| `utils/logs.py` | Rotating file logging + Error ID registry (create, Phase 3) |
| `application.yml` | Lavalink source credentials and region (modify, Phase 2) |
| `utils/music/ui/theme.py` | Decorative bar URL, `STATUS_ICONS` glyphs (modify, Phase 2) |
| `modules/error_handler.py` | Error ID display in red embed (modify, Phase 3) |
| `utils/client.py`, `utils/music/local_lavalink.py`, `utils/music/remote_lavalink_serverlist.py` | Blocking→async I/O (modify, Phase 4) |
| `modules/music/` package | Decomposition target for `modules/music.py` (create, Phase 5) |

---

# Phase 0 — Foundation

### Task 1: Reproducible environment and pytest bootstrap

**Files:**
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/test_environment.py`
- Modify: `app.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: a working `pytest` invocation; `tests/` package importable with the repo root on `sys.path`.

- [ ] **Step 1: Write the failing test**

Create `tests/__init__.py` as an empty file, then `tests/test_environment.py`:

```python
# -*- coding: utf-8 -*-
"""Guards the environment assumptions the rest of the suite relies on."""
import sys


def test_python_version_is_3_14():
    assert sys.version_info[:2] == (3, 14), (
        f"venv holds cp314 wheels; got {sys.version_info[:3]}"
    )


def test_stdout_is_utf8():
    # Windows consoles default to cp1252, which raises UnicodeEncodeError
    # the first time the bot logs an emoji.
    assert (sys.stdout.encoding or "").lower().replace("-", "") == "utf8", (
        f"stdout encoding is {sys.stdout.encoding!r}, expected utf-8"
    )


def test_core_modules_import():
    import config_loader  # noqa: F401
    import utils.client  # noqa: F401
    import utils.music.models  # noqa: F401
    import utils.music.ui  # noqa: F401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_environment.py -v`
Expected: FAIL — `No module named pytest`.

- [ ] **Step 3: Add dev dependencies and config**

Create `requirements-dev.txt`:

```
# Test-only dependencies. Never add these to requirements.txt.
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

Create `pytest.ini`:

```ini
[pytest]
testpaths = tests
asyncio_mode = auto
filterwarnings =
    ignore::DeprecationWarning
```

Install: `./venv/Scripts/python.exe -m pip install -r requirements-dev.txt`

- [ ] **Step 4: Force UTF-8 stdio at process start**

In `app.py`, insert before the `from utils.client import BotPool` line:

```python
# Windows consoles default to cp1252; emoji in logs raise UnicodeEncodeError.
import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
```

Add the same block at the top of `tests/conftest.py` when Task 2 creates it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `./venv/Scripts/python.exe -m pytest tests/test_environment.py -v`
Expected: 3 passed.

If `test_stdout_is_utf8` still fails under pytest, run with `PYTHONIOENCODING=utf-8` and record that in the README step below rather than weakening the assertion.

- [ ] **Step 6: Document setup in README.md**

Add a section documenting: required Python 3.14.6; that `venv/pyvenv.cfg` must point at a local 3.14 interpreter (it shipped pointing at `C:\Python314` from a different machine — a backup of the original is at `venv/pyvenv.cfg.bak`); `pip install -r requirements.txt -r requirements-dev.txt`; and `pytest` as the test command.

- [ ] **Step 7: Commit**

```bash
git add requirements-dev.txt pytest.ini tests/ app.py README.md
git commit -m "test: bootstrap pytest and guard environment assumptions"
```

---

# Phase 1 — Test harness

### Task 2: Fixtures and the Discord limit validator

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/discord_limits.py`
- Test: `tests/test_discord_limits.py`

**Interfaces:**
- Consumes: Task 1's pytest setup.
- Produces:
  - `tests/discord_limits.py`: `assert_payload_valid(payload: dict, context: str) -> None`, raising `AssertionError` on violation.
  - `tests/conftest.py` pytest fixtures: `fake_bot`, `fake_guild`, `player_states` (a `dict[str, FakePlayer]`), and factory `make_player(**overrides) -> FakePlayer`.
  - Classes `FakeBot`, `FakeGuild`, `FakeMember`, `FakeTrack`, `FakeNode`, `FakePlayer`, `FakeInteraction` importable from `tests.conftest`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_discord_limits.py`:

```python
# -*- coding: utf-8 -*-
import pytest

from tests.discord_limits import assert_payload_valid


def _embed(**over):
    base = {"description": "hello"}
    base.update(over)
    return base


def test_accepts_a_valid_payload():
    assert_payload_valid({"embeds": [_embed()], "components": []}, "ok-case")


def test_rejects_overlong_description():
    with pytest.raises(AssertionError, match="description"):
        assert_payload_valid({"embeds": [_embed(description="x" * 4097)]}, "bad")


def test_rejects_too_many_action_rows():
    rows = [{"type": 1, "components": [{"type": 2, "custom_id": f"c{i}", "style": 2}]}
            for i in range(6)]
    with pytest.raises(AssertionError, match="action row"):
        assert_payload_valid({"components": rows}, "bad")


def test_rejects_overlong_custom_id():
    rows = [{"type": 1, "components": [{"type": 2, "custom_id": "x" * 101, "style": 2}]}]
    with pytest.raises(AssertionError, match="custom_id"):
        assert_payload_valid({"components": rows}, "bad")


def test_rejects_embed_total_over_6000():
    embeds = [_embed(description="x" * 3500), _embed(description="y" * 3500)]
    with pytest.raises(AssertionError, match="6000"):
        assert_payload_valid({"embeds": embeds}, "bad")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_discord_limits.py -v`
Expected: FAIL — `No module named 'tests.discord_limits'`.

- [ ] **Step 3: Implement the validator**

Create `tests/discord_limits.py`:

```python
# -*- coding: utf-8 -*-
"""Discord API payload limits, expressed as executable assertions.

Every limit here comes from Discord's documented maximums. A skin that
violates one produces an API rejection, which the user sees as the red
"interaction failed" text.
"""
from __future__ import annotations

EMBED_TOTAL = 6000
EMBED_DESCRIPTION = 4096
EMBED_TITLE = 256
EMBED_FIELDS = 25
EMBED_FIELD_NAME = 256
EMBED_FIELD_VALUE = 1024
EMBED_FOOTER = 2048
EMBED_AUTHOR = 256
MAX_ACTION_ROWS = 5
MAX_BUTTONS_PER_ROW = 5
MAX_SELECT_OPTIONS = 25
COMPONENT_LABEL = 80
CUSTOM_ID = 100
SELECT_DESCRIPTION = 100
SELECT_PLACEHOLDER = 150

_BUTTON = 2
_SELECT_TYPES = (3, 5, 6, 7, 8)


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _embed_length(embed: dict) -> int:
    total = 0
    for key in ("title", "description"):
        total += len(embed.get(key) or "")
    total += len(((embed.get("footer") or {}).get("text")) or "")
    total += len(((embed.get("author") or {}).get("name")) or "")
    for field in embed.get("fields") or ():
        total += len(field.get("name") or "") + len(field.get("value") or "")
    return total


def _validate_embeds(embeds: list, ctx: str) -> None:
    running = 0
    for i, embed in enumerate(embeds):
        where = f"{ctx} embed[{i}]"
        _check(len(embed.get("title") or "") <= EMBED_TITLE,
               f"{where}: title over {EMBED_TITLE}")
        _check(len(embed.get("description") or "") <= EMBED_DESCRIPTION,
               f"{where}: description over {EMBED_DESCRIPTION}")
        _check(len(((embed.get("footer") or {}).get("text")) or "") <= EMBED_FOOTER,
               f"{where}: footer over {EMBED_FOOTER}")
        _check(len(((embed.get("author") or {}).get("name")) or "") <= EMBED_AUTHOR,
               f"{where}: author over {EMBED_AUTHOR}")
        fields = embed.get("fields") or []
        _check(len(fields) <= EMBED_FIELDS, f"{where}: over {EMBED_FIELDS} fields")
        for j, field in enumerate(fields):
            _check(len(field.get("name") or "") <= EMBED_FIELD_NAME,
                   f"{where} field[{j}]: name over {EMBED_FIELD_NAME}")
            _check(len(field.get("value") or "") <= EMBED_FIELD_VALUE,
                   f"{where} field[{j}]: value over {EMBED_FIELD_VALUE}")
        running += _embed_length(embed)
    _check(running <= EMBED_TOTAL,
           f"{ctx}: embeds total {running} chars, over {EMBED_TOTAL}")


def _validate_components(rows: list, ctx: str) -> None:
    _check(len(rows) <= MAX_ACTION_ROWS,
           f"{ctx}: {len(rows)} action rows, over {MAX_ACTION_ROWS}")
    for i, row in enumerate(rows):
        children = row.get("components") or []
        buttons = [c for c in children if c.get("type") == _BUTTON]
        selects = [c for c in children if c.get("type") in _SELECT_TYPES]
        where = f"{ctx} row[{i}]"
        _check(len(buttons) <= MAX_BUTTONS_PER_ROW,
               f"{where}: {len(buttons)} buttons, over {MAX_BUTTONS_PER_ROW}")
        _check(not (selects and buttons),
               f"{where}: mixes a select with buttons in one action row")
        _check(len(selects) <= 1, f"{where}: more than one select in a row")
        for c in children:
            cid = c.get("custom_id")
            if cid is not None:
                _check(len(cid) <= CUSTOM_ID,
                       f"{where}: custom_id {len(cid)} chars, over {CUSTOM_ID}")
            label = c.get("label")
            if label:
                _check(len(label) <= COMPONENT_LABEL,
                       f"{where}: label over {COMPONENT_LABEL}")
            if c.get("type") in _SELECT_TYPES:
                opts = c.get("options") or []
                _check(len(opts) <= MAX_SELECT_OPTIONS,
                       f"{where}: {len(opts)} options, over {MAX_SELECT_OPTIONS}")
                _check(len(opts) >= 1, f"{where}: select has no options")
                ph = c.get("placeholder")
                if ph:
                    _check(len(ph) <= SELECT_PLACEHOLDER,
                           f"{where}: placeholder over {SELECT_PLACEHOLDER}")
                for k, opt in enumerate(opts):
                    _check(len(opt.get("label") or "") <= COMPONENT_LABEL,
                           f"{where} option[{k}]: label over {COMPONENT_LABEL}")
                    _check(len(opt.get("description") or "") <= SELECT_DESCRIPTION,
                           f"{where} option[{k}]: description over {SELECT_DESCRIPTION}")
                values = [o.get("value") for o in opts]
                _check(len(values) == len(set(values)),
                       f"{where}: duplicate option values")


def assert_payload_valid(payload: dict, context: str) -> None:
    """Raise AssertionError if ``payload`` would be rejected by Discord."""
    _validate_embeds(payload.get("embeds") or [], context)
    _validate_components(payload.get("components") or [], context)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/Scripts/python.exe -m pytest tests/test_discord_limits.py -v`
Expected: 5 passed.

- [ ] **Step 5: Build the fixtures**

Create `tests/conftest.py`. Attribute coverage is derived from what the skins actually read — verify against `utils/music/skins/normal_player/default.py` before extending.

```python
# -*- coding: utf-8 -*-
"""Fabricated disnake-shaped objects for offline rendering and dispatch tests."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import disnake  # noqa: E402


class FakeAsset:
    def __init__(self, url="https://example.invalid/avatar.png"):
        self.url = url

    def replace(self, **_kw):
        return self


class FakeMember:
    def __init__(self, id=1001, name="Tester"):
        self.id = id
        self.name = name
        self.global_name = name
        self.display_name = name
        self.mention = f"<@{id}>"
        self.display_avatar = FakeAsset()
        self.voice = SimpleNamespace(channel=SimpleNamespace(id=2002, voice_states={}))


class FakeGuild:
    def __init__(self, id=3003):
        self.id = id
        self.name = "Test Guild"
        self.me = FakeMember(id=4004, name="Golden IQ MUSIC")
        self._members = {1001: FakeMember()}

    def get_member(self, mid):
        return self._members.get(mid)


class FakeNode:
    def __init__(self):
        self.identifier = "LOCAL"
        self.lyric_support = True
        self.is_available = True


class FakeBot:
    def __init__(self):
        self.user = FakeMember(id=4004, name="Golden IQ MUSIC")
        self.config = {"HINT_RATE": 4, "EMBED_COLOR": None}
        self.default_prefix = "!!"

    def get_color(self, _me=None):
        return disnake.Color(0xD4AF37)


class FakeTrack:
    def __init__(self, **over):
        self.title = over.get("title", "Never Gonna Give You Up")
        self.single_title = over.get("single_title", self.title)
        self.author = over.get("author", "Rick Astley")
        self.uri = over.get("uri", "https://youtube.com/watch?v=dQw4w9WgXcQ")
        self.search_uri = self.uri
        self.duration = over.get("duration", 213_000)
        self.is_stream = over.get("is_stream", False)
        self.requester = over.get("requester", 1001)
        self.autoplay = over.get("autoplay", False)
        self.album_name = over.get("album_name", "Whenever You Need Somebody")
        self.album_url = over.get("album_url", "https://example.invalid/album")
        self.playlist_name = over.get("playlist_name", "")
        self.playlist_url = over.get("playlist_url", "")
        self.thumb = over.get("thumb", "https://example.invalid/thumb.jpg")
        self.ytid = over.get("ytid", "dQw4w9WgXcQ")
        self.info = over.get("info", {"sourceName": "youtube", "extra": {}})


class FakePlayer:
    def __init__(self, **over):
        self.bot = FakeBot()
        self.guild = FakeGuild()
        self.node = FakeNode()
        self.current = over.get("current", FakeTrack())
        self.queue = over.get("queue", [])
        self.queue_autoplay = over.get("queue_autoplay", [])
        self.played = over.get("played", [])
        self.position = over.get("position", 45_000)
        self.paused = over.get("paused", False)
        self.volume = over.get("volume", 100)
        self.loop = over.get("loop", False)
        self.autoplay = over.get("autoplay", False)
        self.nightcore = over.get("nightcore", False)
        self.keep_connected = over.get("keep_connected", False)
        self.restrict_mode = over.get("restrict_mode", False)
        self.mini_queue_enabled = over.get("mini_queue_enabled", True)
        self.mini_queue_feature = True
        self.command_log = over.get("command_log", "")
        self.command_log_emoji = over.get("command_log_emoji", "🎵")
        self.current_hint = over.get("current_hint", "")
        self.is_closing = False
        self.has_thread = False
        self.static = False
        self.auto_update = 0
        self.hint_rate = 4
        self.controller_link = ""
        self.last_channel = SimpleNamespace(id=2002)
        self.text_channel = SimpleNamespace(id=2002)
        self.controller_mode = True

    def __len__(self):
        return len(self.queue)


def make_player(**overrides) -> FakePlayer:
    return FakePlayer(**overrides)


_LONG_KH = "បទចម្រៀងខ្មែរដែលមានចំណងជើងវែងណាស់សម្រាប់ការសាកល្បង " * 4


def _states() -> dict:
    return {
        "playing": make_player(),
        "paused": make_player(paused=True),
        "live": make_player(current=FakeTrack(is_stream=True, duration=0)),
        "empty_queue": make_player(queue=[], mini_queue_enabled=False),
        "long_queue": make_player(queue=[FakeTrack(title=f"Track {i}") for i in range(50)]),
        "autoplay": make_player(
            autoplay=True,
            current=FakeTrack(autoplay=True, info={"sourceName": "youtube",
                                                   "extra": {"related": {"uri": "https://example.invalid/r"}}}),
        ),
        "no_artwork": make_player(current=FakeTrack(thumb="")),
        "long_title": make_player(current=FakeTrack(title=_LONG_KH, single_title=_LONG_KH)),
        "khmer_log": make_player(command_log="អ្នកប្រើបានរំលងបទចម្រៀង / User skipped the track"),
        "all_toggles_on": make_player(loop=True, autoplay=True, nightcore=True,
                                      keep_connected=True, restrict_mode=True, volume=150),
    }


@pytest.fixture
def fake_bot():
    return FakeBot()


@pytest.fixture
def fake_guild():
    return FakeGuild()


@pytest.fixture
def player_states():
    return _states()


def all_player_states() -> dict:
    """Non-fixture accessor so tests can use it in @pytest.mark.parametrize."""
    return _states()
```

- [ ] **Step 6: Verify fixtures import cleanly**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v`
Expected: 8 passed (3 environment + 5 limits), no collection errors.

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/discord_limits.py tests/test_discord_limits.py
git commit -m "test: add fake player fixtures and Discord payload validator"
```

---

### Task 3: Skin render validation across all 15 skins

**Files:**
- Create: `tests/test_skin_render.py`

**Interfaces:**
- Consumes: `tests.conftest.all_player_states`, `tests.discord_limits.assert_payload_valid`.
- Produces: proof that every skin renders a Discord-valid payload in every player state. Later phases rely on this as the behavior-preservation gate.

- [ ] **Step 1: Write the failing test**

Create `tests/test_skin_render.py`:

```python
# -*- coding: utf-8 -*-
"""Every skin, every player state, must produce a Discord-valid payload."""
from __future__ import annotations

from importlib import import_module

import pytest
from disnake.ui.action_row import normalize_components_to_dict

from tests.conftest import all_player_states
from tests.discord_limits import assert_payload_valid

NORMAL_SKINS = [
    "classic", "default", "default_progressbar", "embed_link", "lite",
    "micro_controller", "micro_nc", "mini", "minimalist", "miniplayer",
]
STATIC_SKINS = ["classic", "default", "default_progressbar", "embed_link", "mini"]

ALL_SKINS = (
    [("normal_player", n) for n in NORMAL_SKINS]
    + [("static_player", n) for n in STATIC_SKINS]
)
STATE_NAMES = sorted(all_player_states().keys())


def _load_skin(kind: str, name: str):
    module = import_module(f"utils.music.skins.{kind}.{name}")
    assert hasattr(module, "load"), f"{kind}.{name} has no load() entrypoint"
    return module.load()


def _serialize(data: dict) -> dict:
    """Convert a skin's raw output into the JSON Discord would receive."""
    payload = {}
    embeds = [e for e in (data.get("embeds") or []) if e is not None]
    payload["embeds"] = [e.to_dict() for e in embeds]
    components = data.get("components") or []
    payload["components"] = normalize_components_to_dict(components) if components else []
    return payload


def test_all_fifteen_skins_are_covered():
    assert len(ALL_SKINS) == 15, f"expected 15 skins, found {len(ALL_SKINS)}"


@pytest.mark.parametrize("kind,name", ALL_SKINS, ids=[f"{k}/{n}" for k, n in ALL_SKINS])
@pytest.mark.parametrize("state", STATE_NAMES)
def test_skin_renders_valid_payload(kind, name, state):
    skin = _load_skin(kind, name)
    player = all_player_states()[state]
    skin.setup_features(player)
    data = skin.load(player)
    assert_payload_valid(_serialize(data), f"{kind}/{name} [{state}]")


@pytest.mark.parametrize("kind,name", ALL_SKINS, ids=[f"{k}/{n}" for k, n in ALL_SKINS])
def test_skin_declares_name_and_preview(kind, name):
    skin = _load_skin(kind, name)
    assert skin.name == name, f"{kind}/{name}: self-reported name is {skin.name!r}"
    assert isinstance(skin.preview, str) and skin.preview.startswith("http")
```

- [ ] **Step 2: Run test to discover the real failures**

Run: `./venv/Scripts/python.exe -m pytest tests/test_skin_render.py -v --tb=short`
Expected: a mix of PASS and FAIL. This is the first real measurement of skin health — **160 render cases** (15 skins × 10 states, plus 16 metadata cases).

- [ ] **Step 3: Triage every failure**

Record each failure in a triage list, classifying it as either:
- **(a) fixture gap** — the fixture lacks an attribute a skin legitimately reads. Fix `tests/conftest.py` and re-run.
- **(b) real skin bug** — the skin produces an invalid payload. Do *not* fix the skin here. Mark it `xfail` with a reason naming the defect, and add it to the Phase 2 fix list.

Distinguish them by asking: would a real `LavalinkPlayer` have this attribute? Check `utils/music/models.py` to confirm before assuming a fixture gap.

- [ ] **Step 4: Re-run until every case either passes or is a documented xfail**

Run: `./venv/Scripts/python.exe -m pytest tests/test_skin_render.py -v`
Expected: 0 failures; some `xfail`, each carrying a reason string.

- [ ] **Step 5: Commit**

```bash
git add tests/test_skin_render.py tests/conftest.py
git commit -m "test: validate all 15 skins render Discord-valid payloads"
```

---

### Task 4: Component emoji validity

**Files:**
- Create: `tests/test_emoji_validity.py`

**Interfaces:**
- Consumes: `tests.conftest.all_player_states`; the `emoji` package (already a runtime dependency).
- Produces: `is_valid_component_emoji(value: str) -> bool`, importable by later tasks.

- [ ] **Step 1: Write the failing test**

Create `tests/test_emoji_validity.py`:

```python
# -*- coding: utf-8 -*-
"""Component emoji must be real emoji or well-formed custom emoji.

Discord rejects non-emoji glyphs (math symbols, dingbats, bare arrows) used
as Button.emoji or SelectOption.emoji. The rejection surfaces to users as the
red "interaction failed" text. utils/music/ui/emoji_set.py documents this
rule; this module enforces it.
"""
from __future__ import annotations

import re
from importlib import import_module

import emoji as emoji_lib
import pytest
from disnake.ui.action_row import normalize_components_to_dict

from tests.conftest import all_player_states
from tests.test_skin_render import ALL_SKINS

CUSTOM_EMOJI_RE = re.compile(r"^<a?:[A-Za-z0-9_]{2,32}:\d{15,25}>$")
_SELECT_TYPES = (3, 5, 6, 7, 8)


def is_valid_component_emoji(value: str) -> bool:
    if not value:
        return False
    if CUSTOM_EMOJI_RE.match(value):
        return True
    return emoji_lib.purely_emoji(value)


def _collect_component_emoji(payload_rows) -> list:
    found = []
    for row in payload_rows:
        for child in row.get("components") or []:
            if (em := child.get("emoji")) and em.get("name") and not em.get("id"):
                found.append((child.get("custom_id"), em["name"]))
            for opt in child.get("options") or []:
                if (em := opt.get("emoji")) and em.get("name") and not em.get("id"):
                    found.append((opt.get("value"), em["name"]))
    return found


def test_validator_accepts_real_emoji():
    assert is_valid_component_emoji("⏯️")
    assert is_valid_component_emoji("🎧")
    assert is_valid_component_emoji("<:custom:123456789012345678>")


def test_validator_rejects_non_emoji_glyphs():
    # These are the exact glyphs currently present in theme.STATUS_ICONS.
    assert not is_valid_component_emoji("∞")   # U+221E math infinity
    assert not is_valid_component_emoji("✓")   # U+2713 check mark, not emoji
    assert not is_valid_component_emoji("")


def test_emoji_set_defaults_are_all_valid():
    """Verified clean 2026-08-13 — this is a guard against regression."""
    from utils.music.ui.emoji_set import _DEFAULTS

    bad = {n: v for n, v in _DEFAULTS.items() if not is_valid_component_emoji(v)}
    assert not bad, f"emoji_set._DEFAULTS contains non-emoji values: {bad}"


@pytest.mark.xfail(reason="Phase 2 Task 10 fixes the 3 invalid STATUS_ICONS glyphs")
def test_status_icons_are_component_safe():
    """STATUS_ICONS values are text-only today, so these are latent traps.

    Measured 2026-08-13: 'loading' (↻ U+21BB), 'autoplay' (∞ U+221E), and
    'ok' (✓ U+2713) are not emoji. They render fine in an embed description
    but would be rejected the moment one is used as a component emoji.
    """
    from utils.music.ui.theme import STATUS_ICONS

    bad = {n: v for n, v in STATUS_ICONS.items() if not is_valid_component_emoji(v)}
    assert not bad, f"theme.STATUS_ICONS contains non-emoji values: {bad}"


@pytest.mark.parametrize("kind,name", ALL_SKINS, ids=[f"{k}/{n}" for k, n in ALL_SKINS])
def test_skin_component_emoji_are_valid(kind, name):
    module = import_module(f"utils.music.skins.{kind}.{name}")
    skin = module.load()
    player = all_player_states()["playing"]
    skin.setup_features(player)
    data = skin.load(player)
    components = data.get("components") or []
    if not components:
        pytest.skip(f"{kind}/{name} renders no components")
    rows = normalize_components_to_dict(components)
    bad = [(cid, val) for cid, val in _collect_component_emoji(rows)
           if not is_valid_component_emoji(val)]
    assert not bad, f"{kind}/{name} uses invalid component emoji: {bad}"
```

- [ ] **Step 2: Run test to verify it fails where expected**

Run: `./venv/Scripts/python.exe -m pytest tests/test_emoji_validity.py -v --tb=short`
Expected: the two validator tests PASS; `test_emoji_set_defaults_are_all_valid` and per-skin tests reveal the true state. Record which fail.

- [ ] **Step 3: Mark real defects as xfail, not fixed**

Any genuine invalid emoji is a Phase 2 fix. Mark with `pytest.mark.xfail(reason=...)` naming the offending glyph and file. Do not edit `theme.py` or `emoji_set.py` in this task.

- [ ] **Step 4: Run to confirm clean**

Run: `./venv/Scripts/python.exe -m pytest tests/test_emoji_validity.py -v`
Expected: 0 failures; documented xfails only.

- [ ] **Step 5: Commit**

```bash
git add tests/test_emoji_validity.py
git commit -m "test: enforce component emoji validity across skins"
```

---

### Task 5: Player controller dispatch across all 30 controls

**Files:**
- Create: `tests/test_player_controller.py`
- Modify: `tests/conftest.py` (add `FakeInteraction`)

**Interfaces:**
- Consumes: `tests.conftest.FakePlayer`.
- Produces: `FakeInteraction` in `tests/conftest.py` with `.responded` (bool), `.response_calls` (list[str]), `.sent` (list[dict]).

This is the automated equivalent of clicking every button.

- [ ] **Step 1: Add `FakeInteraction` to `tests/conftest.py`**

Append to `tests/conftest.py`:

```python
class _FakeResponse:
    def __init__(self, owner):
        self._owner = owner

    def is_done(self):
        return self._owner.responded

    async def defer(self, *a, **kw):
        self._owner.responded = True
        self._owner.response_calls.append("defer")

    async def edit_message(self, *a, **kw):
        self._owner.responded = True
        self._owner.response_calls.append("edit_message")

    async def send_message(self, *a, **kw):
        self._owner.responded = True
        self._owner.response_calls.append("send_message")


class FakeInteraction:
    """Implements the disnake.MessageInteraction surface the handlers touch."""

    def __init__(self, custom_id: str, *, values=None, player=None):
        self.responded = False
        self.response_calls: list[str] = []
        self.sent: list[dict] = []
        self.data = SimpleNamespace(custom_id=custom_id)
        self.values = values or []
        self.guild_id = 3003
        self.channel_id = 2002
        self.author = FakeMember()
        self.guild = player.guild if player else FakeGuild()
        self.channel = SimpleNamespace(id=2002, guild=self.guild)
        self.message = SimpleNamespace(id=5005, embeds=[], author=self.author,
                                       channel=self.channel)
        self.response = _FakeResponse(self)
        self.application_command = None

    async def send(self, content=None, **kw):
        self.responded = True
        self.response_calls.append("send")
        self.sent.append({"content": content, **kw})

    async def edit_original_message(self, **kw):
        self.response_calls.append("edit_original_message")
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_player_controller.py`:

```python
# -*- coding: utf-8 -*-
"""Drive every PlayerControls value through the dispatcher.

A control that raises an unhandled exception, or that returns without ever
acknowledging the interaction, is what users experience as a dead button or
the red error text.
"""
from __future__ import annotations

import inspect

import pytest

from utils.others import PlayerControls


def all_control_values() -> dict:
    return {
        name: value
        for name, value in vars(PlayerControls).items()
        if not name.startswith("_") and isinstance(value, str)
    }


CONTROLS = sorted(all_control_values().items())


def test_thirty_controls_are_defined():
    assert len(CONTROLS) == 30, f"expected 30 controls, found {len(CONTROLS)}"


@pytest.mark.parametrize("name,value", CONTROLS, ids=[n for n, _ in CONTROLS])
def test_control_id_is_well_formed(name, value):
    assert value.startswith("musicplayer_"), (
        f"{name}={value!r} does not start with the musicplayer_ prefix the "
        f"on_button_click listener filters on — this button is silently ignored"
    )
    assert len(value) <= 100, f"{name}: custom_id over Discord's 100-char limit"


def test_dispatcher_signature_is_stable():
    from modules.music import Music

    sig = inspect.signature(Music.player_controller)
    assert list(sig.parameters)[:3] == ["self", "interaction", "control"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_player_controller.py -v --tb=short`
Expected: `test_control_id_is_well_formed` and the count test reveal the truth about prefixes; `test_dispatcher_signature_is_stable` confirms the entrypoint. Record failures.

- [ ] **Step 4: Add the dispatch smoke test**

Append to `tests/test_player_controller.py`:

```python
@pytest.mark.parametrize("name,value", CONTROLS, ids=[n for n, _ in CONTROLS])
async def test_control_dispatch_always_acknowledges(name, value, monkeypatch):
    """Every control must acknowledge the interaction or raise a handled error.

    An interaction left unacknowledged for 3 seconds shows the user
    "This interaction failed" — the reported red text.
    """
    from modules.music import Music
    from tests.conftest import FakeInteraction, FakePlayer
    from utils.music.errors import GenericError

    player = FakePlayer()
    inter = FakeInteraction(value, player=player)

    cog = Music.__new__(Music)  # bypass __init__; we only exercise dispatch
    cog.bot = player.bot
    cog.bot.bot_ready = True
    cog.bot.is_ready = lambda: True

    try:
        await Music.player_controller(cog, inter, value)
    except GenericError:
        pass  # a handled, user-facing error is an acceptable outcome
    except (AttributeError, KeyError) as exc:
        pytest.xfail(f"{name}: dispatch needs deeper fixtures — {type(exc).__name__}: {exc}")

    assert inter.responded, (
        f"{name}: dispatcher returned without acknowledging the interaction"
    )
```

- [ ] **Step 5: Run and triage**

Run: `./venv/Scripts/python.exe -m pytest tests/test_player_controller.py -v --tb=short`

Expect many `xfail`s initially — `player_controller` reaches deep into bot state. Deepen the fixtures for controls that are close to working; leave genuinely deep ones as documented xfails. **The goal is maximum honest coverage, not a green bar.** Record the passing count; it is the metric Phase 5 must not regress.

- [ ] **Step 6: Commit**

```bash
git add tests/test_player_controller.py tests/conftest.py
git commit -m "test: drive all 30 player controls through the dispatcher"
```

---

### Task 6: Command metadata limits

**Files:**
- Create: `tests/test_command_metadata.py`

**Interfaces:**
- Consumes: the cog classes in `modules/`.
- Produces: a regression guard on the ~11 characters of description headroom.

- [ ] **Step 1: Write the failing test**

Create `tests/test_command_metadata.py`:

```python
# -*- coding: utf-8 -*-
"""Slash command metadata must fit Discord's limits.

Descriptions are built as f"{desc_prefix}{text}". Measured 2026-08-13:
Music 89/100, Settings 88/100 — about 11 characters of headroom. Khmer text
added carelessly overflows this, and a single overflow fails command sync
for the entire bot.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

DESCRIPTION_LIMIT = 100
NAME_LIMIT = 32
NAME_RE = re.compile(r"^[-_\w]{1,32}$")

COG_FILES = ["modules/music.py", "modules/music_settings.py",
             "modules/misc.py", "modules/lastfm.py"]

PREFIX_RE = re.compile(r'^\s{4}emoji\s*=\s*"(.+?)"\s*$\n\s{4}name\s*=\s*"(.+?)"\s*$',
                       re.MULTILINE)
DESC_RE = re.compile(r'description=f"\{desc_prefix\}([^"]*)"')
PLAIN_DESC_RE = re.compile(r'description="([^"]*)"')


def _prefix_lengths(source: str) -> list[int]:
    return [len(f"[{em} {nm}] | ") for em, nm in PREFIX_RE.findall(source)]


@pytest.mark.parametrize("path", COG_FILES)
def test_prefixed_descriptions_fit(path):
    source = Path(path).read_text(encoding="utf-8")
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
    source = Path(path).read_text(encoding="utf-8")
    offenders = [(len(d), d) for d in PLAIN_DESC_RE.findall(source)
                 if len(d) > DESCRIPTION_LIMIT]
    assert not offenders, f"{path}: descriptions over {DESCRIPTION_LIMIT}: {offenders}"


@pytest.mark.parametrize("path", COG_FILES)
def test_headroom_is_reported(path):
    """Not a pass/fail gate — prints remaining headroom for reviewers."""
    source = Path(path).read_text(encoding="utf-8")
    prefixes = _prefix_lengths(source)
    if not prefixes:
        pytest.skip(f"{path} declares no desc_prefix")
    bodies = DESC_RE.findall(source)
    if not bodies:
        pytest.skip(f"{path} has no prefixed descriptions")
    worst = max(len(b) for b in bodies) + max(prefixes)
    print(f"\n{path}: worst description {worst}/{DESCRIPTION_LIMIT} "
          f"({DESCRIPTION_LIMIT - worst} chars headroom)")
    assert worst <= DESCRIPTION_LIMIT
```

- [ ] **Step 2: Run test**

Run: `./venv/Scripts/python.exe -m pytest tests/test_command_metadata.py -v -s`
Expected: PASS, with headroom printed. If any fails, that description must be shortened in Phase 2.

- [ ] **Step 3: Add a locale-leftover guard**

Append:

```python
def test_no_portuguese_locale_leftovers():
    """The fork's pt_BR localizations are dead weight; Khmer is the target."""
    offenders = []
    for path in COG_FILES:
        source = Path(path).read_text(encoding="utf-8")
        if "Locale.pt_BR" in source:
            offenders.append((path, source.count("Locale.pt_BR")))
    assert not offenders, f"pt_BR locale leftovers from the upstream fork: {offenders}"
```

- [ ] **Step 4: Run and mark xfail**

Run: `./venv/Scripts/python.exe -m pytest tests/test_command_metadata.py -v`
Expected: the locale test FAILS (13 `Localized` uses with `pt_BR` in `modules/music.py`). Mark it `xfail(reason="Phase 2 removes pt_BR leftovers")`.

- [ ] **Step 5: Commit**

```bash
git add tests/test_command_metadata.py
git commit -m "test: guard slash command description limits and locale leftovers"
```

---

### Task 7: Configuration coherence

**Files:**
- Create: `tests/test_config_coherence.py`

**Interfaces:**
- Consumes: `application.yml`, `.env` (read-only; values never printed).
- Produces: executable encoding of the Spotify and Deezer defects.

- [ ] **Step 1: Write the failing test**

Create `tests/test_config_coherence.py`:

```python
# -*- coding: utf-8 -*-
"""application.yml and .env must agree about which audio sources work.

Reproduced 2026-08-13: spsearch -> loadType "error", dzsearch -> "empty",
because application.yml enables Spotify with empty credentials and disables
Deezer while the Python layer still offers it.

These tests never print credential values.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

APP_YML = Path("application.yml")
ENV = Path(".env")


@pytest.fixture(scope="module")
def lavasrc():
    if not APP_YML.exists():
        pytest.skip("application.yml not present")
    data = YAML(typ="safe").load(APP_YML.read_text(encoding="utf-8"))
    plugins = (data or {}).get("plugins") or {}
    src = plugins.get("lavasrc")
    if not src:
        pytest.skip("lavasrc plugin not configured")
    return src


def _env_has(key: str) -> bool:
    if not ENV.exists():
        return False
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            value = line.split("=", 1)[1].strip().strip("'\"")
            return bool(value)
    return False


def test_spotify_enabled_implies_credentials(lavasrc):
    enabled = (lavasrc.get("sources") or {}).get("spotify", False)
    if not enabled:
        pytest.skip("Spotify source disabled")
    conf = lavasrc.get("spotify") or {}
    assert conf.get("clientId"), (
        "application.yml enables Spotify but clientId is empty — "
        "this is why spsearch returns loadType 'error'"
    )
    assert conf.get("clientSecret"), (
        "application.yml enables Spotify but clientSecret is empty"
    )


def test_env_spotify_credentials_are_present():
    assert _env_has("SPOTIFY_CLIENT_ID"), ".env is missing SPOTIFY_CLIENT_ID"
    assert _env_has("SPOTIFY_CLIENT_SECRET"), ".env is missing SPOTIFY_CLIENT_SECRET"


def test_deezer_enabled_implies_decryption_key(lavasrc):
    enabled = (lavasrc.get("sources") or {}).get("deezer", False)
    if not enabled:
        pytest.skip("Deezer source disabled — the coherent state when no key exists")
    conf = lavasrc.get("deezer") or {}
    assert conf.get("masterDecryptionKey"), (
        "Deezer enabled without masterDecryptionKey — dzsearch returns empty"
    )


def test_region_is_not_the_upstream_fork_default(lavasrc):
    for section in ("spotify", "applemusic"):
        code = (lavasrc.get(section) or {}).get("countryCode")
        if code is None:
            continue
        assert code != "BR", (
            f"lavasrc.{section}.countryCode is still 'BR' from the upstream "
            f"Brazilian fork; should be 'KH'"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_config_coherence.py -v`
Expected: `test_spotify_enabled_implies_credentials` FAILS (empty clientId) and both `test_region_*` cases FAIL (`BR`). These are the confirmed defects.

- [ ] **Step 3: Mark the confirmed defects xfail**

Mark each failing test `xfail(reason="Phase 2 Task N fixes this")` referencing the fixing task. They flip to `xpass` in Phase 2, which is the completion signal.

- [ ] **Step 4: Run whole suite and record the baseline**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v --tb=short > docs/superpowers/plans/phase1-baseline.txt 2>&1`

Commit this baseline. Phases 2–5 are measured against it.

- [ ] **Step 5: Commit**

```bash
git add tests/test_config_coherence.py docs/superpowers/plans/phase1-baseline.txt
git commit -m "test: assert application.yml and .env agree on audio sources"
```

---

# Phase 2 — Fix confirmed breakages

Every task flips a Phase 1 `xfail` to a pass.

### Task 8: Restore Spotify

**Files:**
- Modify: `application.yml:72-75`
- Modify: `utils/music/audio_sources/spotify.py` (demote or remove the second path)
- Test: `tests/test_config_coherence.py` (remove xfail markers)

**Interfaces:**
- Consumes: `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` from `.env`.
- Produces: `spsearch:` returning `loadType: search`.

- [ ] **Step 1: Confirm the test currently xfails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_config_coherence.py::test_spotify_enabled_implies_credentials -v`
Expected: XFAIL.

- [ ] **Step 2: Populate lavasrc Spotify credentials**

In `application.yml`, set `plugins.lavasrc.spotify.clientId` and `clientSecret` to the values already in `.env` (read them; do not print or commit them — `application.yml` is gitignored). Set `countryCode: "KH"` in both the `spotify` and `applemusic` sections.

- [ ] **Step 3: Remove the xfail markers**

Delete the `xfail` decorators from `test_spotify_enabled_implies_credentials` and `test_region_is_not_the_upstream_fork_default`.

- [ ] **Step 4: Run the config tests**

Run: `./venv/Scripts/python.exe -m pytest tests/test_config_coherence.py -v`
Expected: PASS.

- [ ] **Step 5: Verify against live Lavalink**

```bash
# terminal 1
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe app.py
# wait for "Music server: [LOCAL / v4] is ready for use!"
# terminal 2
curl -s -H "Authorization: youshallnotpass" \
  "http://127.0.0.1:8090/v4/loadtracks?identifier=spsearch%3Aadele%20hello" \
  | head -c 300
```

Expected: `"loadType":"search"` with a non-empty `data` array. Stop the bot afterward.

- [ ] **Step 6: Resolve the duplicate Spotify path**

The Python `SpotifyClient` in `utils/music/audio_sources/spotify.py` also fails at boot (`Failed to get client`). With lavasrc authoritative for track resolution, either fix its credential loading or disable it so boot emits no misleading warning. Whichever is chosen, exactly one path must be the documented source of truth. Record the choice in a comment at the top of the file.

- [ ] **Step 7: Commit**

```bash
git add tests/test_config_coherence.py utils/music/audio_sources/spotify.py
git commit -m "fix: restore Spotify playback via lavasrc credentials"
```

Note: `application.yml` is gitignored, so the config change is not committed. Document the required keys in `application.yml.example` and commit that instead.

---

### Task 9: Make Deezer coherent

**Files:**
- Modify: `application.yml:87-88`
- Modify: `application.yml.example`
- Modify: `utils/music/audio_sources/deezer.py` or its call site
- Test: `tests/test_config_coherence.py`

**Interfaces:**
- Produces: a Deezer query that returns an explicit Khmer + English "source unavailable" message rather than an empty result.

**Assumption (owner-confirmed 2026-08-13):** no `masterDecryptionKey` is available, so Deezer is disabled coherently rather than enabled.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config_coherence.py`:

```python
def test_deezer_is_coherently_disabled(lavasrc):
    """If Deezer has no key it must be off everywhere, not half-on.

    Half-on is what produced dzsearch -> loadType "empty": a silent nothing
    instead of a message the user can act on.
    """
    conf = lavasrc.get("deezer") or {}
    enabled = (lavasrc.get("sources") or {}).get("deezer", False)
    if conf.get("masterDecryptionKey"):
        assert enabled, "Deezer key present but source disabled"
    else:
        assert not enabled, "Deezer enabled without a key — queries return empty"
```

- [ ] **Step 2: Run to verify current state**

Run: `./venv/Scripts/python.exe -m pytest tests/test_config_coherence.py::test_deezer_is_coherently_disabled -v`
Expected: PASS already (`deezer: false`, key empty) — the config side is coherent; the user-facing side is not.

- [ ] **Step 3: Add the user-facing message**

Find where a Deezer query reaches an empty result (trace from `get_tracks` in `modules/music.py`). Ensure an empty result from a Deezer identifier raises a `GenericError` with:

```
"ប្រភព Deezer មិនអាចប្រើបានទេ សូមប្រើ YouTube ឬ SoundCloud ជំនួស។ / "
"Deezer is unavailable — please use YouTube or SoundCloud instead."
```

Measure the string: it is a runtime error message, not a command description, so the 100-character limit does not apply.

- [ ] **Step 4: Test the message path**

Add a test asserting a Deezer identifier produces that `GenericError` rather than an empty result. Run it; expect PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_config_coherence.py modules/music.py application.yml.example
git commit -m "fix: report Deezer unavailability instead of returning empty results"
```

---

### Task 10: Replace the dead decorative bar and invalid emoji

**Files:**
- Modify: `utils/music/ui/theme.py`
- Modify: `utils/music/skins/normal_player/classic.py:62,109`
- Modify: `utils/music/skins/normal_player/default.py:157`
- Modify: `utils/music/skins/static_player/default.py:115`
- Test: `tests/test_emoji_validity.py`, `tests/test_skin_render.py`

**Interfaces:**
- Produces: no embed references a 404 URL; `STATUS_ICONS` values pass `is_valid_component_emoji` where used as component emoji.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_skin_render.py`:

```python
def test_no_skin_references_the_dead_cdn_attachment():
    """The 2023 attachment URL returns HTTP 404 (verified 2026-08-13).

    Discord CDN attachment links now require signed ex/is/hm parameters;
    unsigned legacy links are dead, so every player embed using it renders
    a broken image.
    """
    from pathlib import Path

    dead = "attachments/554468640942981147/1082887587770937455"
    offenders = []
    for path in Path("utils/music").rglob("*.py"):
        if dead in path.read_text(encoding="utf-8"):
            offenders.append(str(path))
    assert not offenders, f"dead CDN attachment URL still referenced in: {offenders}"
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_skin_render.py::test_no_skin_references_the_dead_cdn_attachment -v`
Expected: FAIL, listing `theme.py` (and any skin with an inlined copy).

- [ ] **Step 3: Remove the dead image**

In `utils/music/ui/theme.py`, delete `PREMIUM_DECORATIVE_BAR`. In each of the 4 call sites, remove the `embed.set_image(url=theme.PREMIUM_DECORATIVE_BAR)` line.

Prefer removal over substitution: the artwork thumbnail is already the visual anchor (stated in `default.py`'s own module docstring), and a decorative bar adds a network fetch per render for no information.

- [ ] **Step 4: Fix the invalid `STATUS_ICONS` glyphs**

Measured 2026-08-13 with `emoji.purely_emoji`: exactly **three** values in `utils/music/ui/theme.py` are not emoji.

```python
"loading": "↻",   # U+21BB  -> "🔄"
"autoplay": "∞",  # U+221E  -> "♾️"
"ok": "✓",        # U+2713  -> "✅"
```

Be precise about the stakes: these three are currently used only as **text inside embed descriptions** (via `status_accent_line`), where Discord accepts any glyph. They are a **latent trap**, not the current cause of the red error text — the moment anyone passes one to `Button.emoji` or `SelectOption.emoji`, that component is rejected. Fixing them now closes the trap; do not claim it fixes a live user-visible bug.

Leave `"playing": "▶"`, `"paused": "⏸"`, and `"stopped": "⏹"` alone — they are bare codepoints without the U+FE0F variation selector, but `emoji.purely_emoji` accepts them and Discord does too. Changing them is cosmetic churn with a real risk of typos.

`utils/music/ui/emoji_set.py` `_DEFAULTS` was checked in full and every value is already valid — no change needed there.

- [ ] **Step 5: Remove the emoji xfail markers and run**

Run: `./venv/Scripts/python.exe -m pytest tests/test_emoji_validity.py tests/test_skin_render.py -v`
Expected: PASS, including previously-xfailed cases.

- [ ] **Step 6: Commit**

```bash
git add utils/music/ui/theme.py utils/music/skins/ tests/
git commit -m "fix: drop dead CDN image and replace non-emoji component glyphs"
```

---

### Task 11: Remove Portuguese and pt_BR leftovers

**Files:**
- Modify: `utils/music/audio_sources/spotify.py` (the `Ocorreu um erro ao obter token` string)
- Modify: `modules/music.py` (13 `Locale.pt_BR` uses)
- Test: `tests/test_command_metadata.py`

**Interfaces:**
- Produces: no Portuguese strings in user-facing paths.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_command_metadata.py`:

```python
PORTUGUESE_MARKERS = ["Ocorreu um erro", "Não foi", "está", "música", "Sim"]


def test_no_portuguese_user_facing_strings():
    from pathlib import Path

    offenders = []
    for path in list(Path("modules").rglob("*.py")) + list(Path("utils").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for marker in PORTUGUESE_MARKERS:
            if marker in text:
                offenders.append((str(path), marker))
    assert not offenders, f"Portuguese leftovers from the upstream fork: {offenders}"
```

- [ ] **Step 2: Run to see the true extent**

Run: `./venv/Scripts/python.exe -m pytest tests/test_command_metadata.py::test_no_portuguese_user_facing_strings -v`
Expected: FAIL with a list. If the list is large, narrow `PORTUGUESE_MARKERS` to unambiguous phrases (`"Ocorreu um erro"`) — `"está"` and `"Sim"` may appear inside unrelated identifiers. Adjust the marker list before mass-editing.

- [ ] **Step 3: Translate the strings**

Replace each with Khmer + English, Khmer first, separated by ` / `. For the Spotify one:

```python
"⚠️ - Spotify: មិនអាចទាញយក token បានទេ / Failed to obtain token: {error}"
```

- [ ] **Step 4: Replace pt_BR localizations**

Replace `disnake.Locale.pt_BR` with the Khmer locale if disnake exposes one; otherwise remove the `Localized` wrapper and keep the bilingual literal, since a locale the bot does not target adds sync payload for no benefit. Verify with:

```bash
./venv/Scripts/python.exe -c "import disnake; print([l for l in dir(disnake.Locale) if not l.startswith('_')])"
```

- [ ] **Step 5: Run tests**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v`
Expected: PASS, including the previously-xfailed locale test.

- [ ] **Step 6: Verify command sync against live Discord**

Boot the bot; confirm the log shows commands synchronized with no length error. Stop it.

- [ ] **Step 7: Commit**

```bash
git add modules/ utils/ tests/
git commit -m "fix: replace Portuguese fork leftovers with Khmer + English"
```

---

# Phase 3 — Error visibility

### Task 12: Error ID registry and rotating file logs

**Files:**
- Create: `utils/logs.py`
- Create: `tests/test_logs.py`
- Modify: `app.py`

**Interfaces:**
- Produces:
  - `utils.logs.setup_logging(log_dir: str = ".logs") -> None`
  - `utils.logs.record_error(exc: BaseException, **context) -> str` returning an 8-character uppercase Error ID.
  - `utils.logs.lookup_error(error_id: str) -> str | None` returning the stored traceback.

- [ ] **Step 1: Write the failing test**

Create `tests/test_logs.py`:

```python
# -*- coding: utf-8 -*-
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
    assert "សាកល្បង" in stored


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_logs.py -v`
Expected: FAIL — `No module named 'utils.logs'`.

- [ ] **Step 3: Implement the module**

Create `utils/logs.py`:

```python
# -*- coding: utf-8 -*-
"""Rotating file logging and short Error IDs.

The bot's 320 bare ``except:`` handlers made failures unreportable: users saw
a generic red embed carrying nothing actionable. Every recorded error now gets
a short ID shown to the user and resolvable to a full traceback here.
"""
from __future__ import annotations

import logging
import os
import secrets
import traceback
from logging.handlers import RotatingFileHandler
from typing import Optional

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alikes (I/O/0/1)
_MAX_CACHE = 500

_logger = logging.getLogger("goldeniq")
_errors: dict[str, str] = {}
_order: list[str] = []


def _new_id() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(8))


def setup_logging(log_dir: str = ".logs") -> None:
    """Install a rotating file handler. Safe to call more than once."""
    os.makedirs(log_dir, exist_ok=True)
    for handler in list(_logger.handlers):
        _logger.removeHandler(handler)
    handler = RotatingFileHandler(
        os.path.join(log_dir, "bot.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s"
    ))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
    _errors.clear()
    _order.clear()


def record_error(exc: BaseException, **context) -> str:
    """Store ``exc`` with context and return a short ID to show the user."""
    error_id = _new_id()
    while error_id in _errors:
        error_id = _new_id()

    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    ctx = "\n".join(f"  {k}: {v}" for k, v in context.items())
    entry = f"Error ID: {error_id}\nContext:\n{ctx or '  (none)'}\n\n{tb}"

    _errors[error_id] = entry
    _order.append(error_id)
    while len(_order) > _MAX_CACHE:
        _errors.pop(_order.pop(0), None)

    _logger.error(entry)
    return error_id


def lookup_error(error_id: str) -> Optional[str]:
    """Return the stored traceback for ``error_id``, or None if unknown."""
    return _errors.get(error_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/Scripts/python.exe -m pytest tests/test_logs.py -v`
Expected: 5 passed.

- [ ] **Step 5: Call `setup_logging` at startup**

In `app.py`, after the UTF-8 block from Task 1:

```python
from utils.logs import setup_logging
setup_logging()
```

- [ ] **Step 6: Commit**

```bash
git add utils/logs.py tests/test_logs.py app.py
git commit -m "feat: add rotating logs and short Error IDs for reportable failures"
```

---

### Task 13: Show the Error ID in the red embed

**Files:**
- Modify: `modules/error_handler.py:99-125`
- Test: `tests/test_error_handler.py` (create)

**Interfaces:**
- Consumes: `utils.logs.record_error`.
- Produces: every generic error embed contains an Error ID.

- [ ] **Step 1: Write the failing test**

Create `tests/test_error_handler.py`:

```python
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
    assert any("\u1780" <= ch <= "\u17ff" for ch in text), "missing Khmer text"
    assert re.search(r"[A-Za-z]{4,}", text), "missing English text"
```

- [ ] **Step 2: Run to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_error_handler.py -v`
Expected: FAIL — `build_generic_error_embed` does not exist.

- [ ] **Step 3: Extract the embed builder**

In `modules/error_handler.py`, extract the generic-embed construction (currently inline around lines 108–125) into a module-level function:

```python
def build_generic_error_embed(error: BaseException, **context):
    """Build the red fallback embed and register a reportable Error ID."""
    from utils.logs import record_error

    error_id = record_error(error, **context)
    embed = disnake.Embed(
        color=disnake.Color.red(),
        title="⚠️ មានបញ្ហាបច្ចេកទេស / Something went wrong",
        description=(
            "មានកំហុសមួយកើតឡើងពេលដំណើរការពាក្យបញ្ជានេះ។\n"
            "An unexpected error occurred while running this command.\n\n"
            f"-# `{type(error).__name__}` ⬩ លេខកូដកំហុស / Error ID: `{error_id}`"
        ),
    )
    return embed, error_id
```

Then call it from `process_interaction_error` in place of the inline construction, passing available context (`guild`, `user`, `command`).

- [ ] **Step 4: Run tests**

Run: `./venv/Scripts/python.exe -m pytest tests/test_error_handler.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add modules/error_handler.py tests/test_error_handler.py
git commit -m "feat: show reportable Error ID in the generic error embed"
```

---

### Task 14: Triage bare exception handlers on the interaction and playback paths

**Files:**
- Modify: `modules/music.py`, `utils/music/models.py`, `utils/music/interactions.py`
- Test: `tests/test_exception_hygiene.py` (create)

**Interfaces:**
- Produces: a ratcheting budget test that prevents new bare handlers.

**Approach:** do not convert all 320 at once. Ratchet the count downward, highest-risk files first.

- [ ] **Step 1: Write the budget test**

Create `tests/test_exception_hygiene.py`:

```python
# -*- coding: utf-8 -*-
"""Ratchet down bare exception handlers.

Baseline 2026-08-13: 320 bare `except:` across modules/ and utils/. Each one
converts a real fault into silent misbehavior, which is why failures could not
be reported. Lower the budgets as handlers are converted; never raise them.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Per-file budgets. Lower these as work proceeds; a rise fails the build.
BUDGETS = {
    "modules/music.py": 999,
    "utils/music/models.py": 999,
    "utils/music/interactions.py": 999,
}


def _count_bare_handlers(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.ExceptHandler) and node.type is None
    )


@pytest.mark.parametrize("path,budget", sorted(BUDGETS.items()))
def test_bare_handler_budget(path, budget):
    actual = _count_bare_handlers(Path(path))
    assert actual <= budget, (
        f"{path} has {actual} bare `except:` handlers, budget is {budget}. "
        f"Bare handlers hide faults — add a specific exception type."
    )


def test_budgets_are_calibrated():
    """Fails if a budget drifts far above reality — keeps the ratchet honest."""
    loose = {
        path: (budget, _count_bare_handlers(Path(path)))
        for path, budget in BUDGETS.items()
        if budget > _count_bare_handlers(Path(path)) + 5
    }
    assert not loose, f"budgets far above actual (tighten them): {loose}"
```

- [ ] **Step 2: Run to get real per-file counts**

Run: `./venv/Scripts/python.exe -m pytest tests/test_exception_hygiene.py -v`
Expected: budget tests PASS; `test_budgets_are_calibrated` FAILS and reports the true counts.

- [ ] **Step 3: Set budgets to the measured values**

Replace each `999` with the actual count from Step 2. Re-run; expect all PASS.

- [ ] **Step 4: Convert handlers on the interaction path**

Starting with `modules/music.py`'s `player_controller` and its helpers, replace each bare `except:` with either a specific exception type, or — where a broad catch is genuinely correct — `except Exception as exc:` followed by `record_error(exc, ...)`. Never leave a bare `pass`.

Work in reviewable batches. After each batch, lower that file's budget to the new count and run the full suite:

Run: `./venv/Scripts/python.exe -m pytest tests/ -v`
Expected: no regression against `phase1-baseline.txt`.

- [ ] **Step 5: Treat newly surfaced faults as findings**

Converting handlers will surface real faults that were previously hidden. Each is a **finding, not a regression** — record it, and fix or file it explicitly. Do not restore the bare handler to make a symptom disappear.

- [ ] **Step 6: Commit each batch**

```bash
git add modules/music.py tests/test_exception_hygiene.py
git commit -m "refactor: replace bare exception handlers on the interaction path"
```

---

# Phase 4 — Performance

### Task 15: Remove blocking I/O from async paths

**Files:**
- Modify: `utils/client.py:614`
- Modify: `utils/music/remote_lavalink_serverlist.py:51`
- Modify: `utils/music/local_lavalink.py:19`
- Test: `tests/test_async_hygiene.py` (create)

**Interfaces:**
- Produces: no `requests.*` call reachable from an `async def` in these files.

- [ ] **Step 1: Write the failing test**

Create `tests/test_async_hygiene.py`:

```python
# -*- coding: utf-8 -*-
"""Blocking I/O inside a coroutine stalls the whole bot.

Baseline 2026-08-13: three `requests.get()` calls sit on async paths. While
one runs, no other command, button, or voice event is processed — the
reported slowness.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

WATCHED = [
    "utils/client.py",
    "utils/music/remote_lavalink_serverlist.py",
    "utils/music/local_lavalink.py",
]
BLOCKING = {"requests"}


def _blocking_calls_in_coroutines(path: Path) -> list:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for func in ast.walk(tree):
        if not isinstance(func, ast.AsyncFunctionDef):
            continue
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if (isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id in BLOCKING):
                found.append(f"{func.name}:{node.lineno} -> "
                             f"{target.value.id}.{target.attr}()")
    return found


@pytest.mark.parametrize("path", WATCHED)
def test_no_blocking_http_inside_coroutines(path):
    found = _blocking_calls_in_coroutines(Path(path))
    assert not found, (
        f"{path}: blocking HTTP inside async functions stalls the event loop: {found}"
    )
```

- [ ] **Step 2: Run to see which are truly on async paths**

Run: `./venv/Scripts/python.exe -m pytest tests/test_async_hygiene.py -v`
Expected: failures listing the offending coroutines. A `requests.get` inside a plain `def` called only at startup is *not* a defect — the test correctly ignores those. Record which of the three are genuinely async-reachable.

- [ ] **Step 3: Convert the async-reachable ones to aiohttp**

For each, replace with the `aiohttp` session already available on the bot. Pattern:

```python
async with self.session.get(url, allow_redirects=False) as resp:
    body = await resp.text()
```

For a module-level helper without a session, accept one as a parameter rather than creating a session per call — session creation per request is itself a performance defect.

- [ ] **Step 4: Run tests**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v`
Expected: `test_async_hygiene.py` passes; no regression elsewhere.

- [ ] **Step 5: Verify with a live boot**

Boot the bot; confirm it reaches "Music server: [LOCAL / v4] is ready for use!" and that Lavalink server-list fetching still works. Stop it.

- [ ] **Step 6: Commit**

```bash
git add utils/ tests/test_async_hygiene.py
git commit -m "perf: replace blocking HTTP with aiohttp on async paths"
```

---

### Task 16: Cache guild data reads

**Files:**
- Modify: `utils/db.py`
- Test: `tests/test_db_cache.py` (create)

**Interfaces:**
- Produces: `guild_data` served from cache on repeat reads, invalidated on write.

- [ ] **Step 1: Measure the current read volume**

Instrument `get_data` in `utils/db.py` with a counter, boot the bot, exercise a few interactions, and record how many MongoDB round-trips occur per interaction. **Write the number down** — Step 6 compares against it.

- [ ] **Step 2: Write the failing test**

Create `tests/test_db_cache.py`:

```python
# -*- coding: utf-8 -*-
"""Repeated guild-data reads must not hit the database every time."""
import pytest


class _CountingBackend:
    def __init__(self):
        self.reads = 0
        self.store = {"3003": {"player_controller": {"skin": "default"}}}

    async def get_data(self, guild_id, *, db_name=None, collection=None, default_model=None):
        self.reads += 1
        return self.store.get(str(guild_id))

    async def update_data(self, guild_id, data, *, db_name=None, collection=None):
        self.store[str(guild_id)] = data


async def test_repeat_reads_hit_the_backend_once():
    from utils.db import CachedDatabase

    backend = _CountingBackend()
    db = CachedDatabase(backend)

    for _ in range(5):
        await db.get_data(3003)

    assert backend.reads == 1, f"expected 1 backend read, got {backend.reads}"


async def test_write_invalidates_the_cache():
    from utils.db import CachedDatabase

    backend = _CountingBackend()
    db = CachedDatabase(backend)

    await db.get_data(3003)
    await db.update_data(3003, {"player_controller": {"skin": "mini"}})
    result = await db.get_data(3003)

    assert backend.reads == 2, "write must invalidate the cached entry"
    assert result["player_controller"]["skin"] == "mini"


async def test_distinct_guilds_are_cached_separately():
    from utils.db import CachedDatabase

    backend = _CountingBackend()
    backend.store["4004"] = {"player_controller": {"skin": "lite"}}
    db = CachedDatabase(backend)

    a = await db.get_data(3003)
    b = await db.get_data(4004)

    assert a != b
    assert backend.reads == 2
```

- [ ] **Step 3: Run to verify it fails**

Run: `./venv/Scripts/python.exe -m pytest tests/test_db_cache.py -v`
Expected: FAIL — `CachedDatabase` does not exist.

- [ ] **Step 4: Implement `CachedDatabase`**

Add to `utils/db.py`:

```python
class CachedDatabase:
    """Read-through cache over a database backend, keyed by guild ID.

    Guild data was re-read from MongoDB on essentially every interaction.
    The 60-second TTL is short enough that edits made outside this process
    (a second shard, a manual DB change) converge quickly, while still
    collapsing the burst of reads a single button press triggers.
    """

    def __init__(self, backend, ttl: int = 60, maxsize: int = 1000):
        self._backend = backend
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)

    async def get_data(self, guild_id, **kwargs):
        key = str(guild_id)
        try:
            return self._cache[key]
        except KeyError:
            pass
        data = await self._backend.get_data(guild_id, **kwargs)
        if data is not None:
            self._cache[key] = data
        return data

    async def update_data(self, guild_id, data, **kwargs):
        self._cache.pop(str(guild_id), None)
        return await self._backend.update_data(guild_id, data, **kwargs)

    def invalidate(self, guild_id) -> None:
        self._cache.pop(str(guild_id), None)

    def __getattr__(self, name):
        # Anything not cached delegates straight through to the backend.
        return getattr(self._backend, name)
```

`TTLCache` comes from `cachetools`, already imported in `utils/client.py` and present in `requirements.txt`. Add `from cachetools import TTLCache` to `utils/db.py` if absent.

- [ ] **Step 5: Run tests**

Run: `./venv/Scripts/python.exe -m pytest tests/test_db_cache.py -v`
Expected: 3 passed.

- [ ] **Step 6: Re-measure and report real numbers**

Repeat Step 1's measurement. Report the before/after round-trip counts. **If there is no measurable improvement, say so** rather than asserting one.

- [ ] **Step 7: Commit**

```bash
git add utils/db.py tests/test_db_cache.py
git commit -m "perf: cache guild data reads with write-through invalidation"
```

---

### Task 17: Reduce redundant player message edits

**Files:**
- Modify: `utils/music/models.py` (the player update path)
- Test: `tests/test_render_rate.py` (create)

**Interfaces:**
- Produces: no message edit when the rendered payload is unchanged.

- [ ] **Step 1: Write the failing test**

Create `tests/test_render_rate.py`:

```python
# -*- coding: utf-8 -*-
"""Identical renders must not produce a Discord edit.

Every redundant edit consumes rate-limit budget shared with real user
actions, which makes buttons feel slow.
"""
from tests.conftest import make_player
from tests.test_skin_render import _load_skin, _serialize


def test_identical_state_renders_identical_payload():
    skin = _load_skin("normal_player", "default")
    player = make_player()
    skin.setup_features(player)

    first = _serialize(skin.load(player))
    second = _serialize(skin.load(player))

    assert first == second, (
        "the same player state rendered two different payloads; a non-deterministic "
        "render defeats any edit-deduplication and forces a Discord edit every tick"
    )


def test_position_change_does_change_the_payload():
    skin = _load_skin("normal_player", "default_progressbar")
    player = make_player(position=10_000)
    skin.setup_features(player)
    early = _serialize(skin.load(player))

    player.position = 200_000
    late = _serialize(skin.load(player))

    assert early != late, "progress must be reflected in the payload"
```

- [ ] **Step 2: Run**

Run: `./venv/Scripts/python.exe -m pytest tests/test_render_rate.py -v`

If `test_identical_state_renders_identical_payload` FAILS, the render is non-deterministic (likely a timestamp or `remaining_time_marker` computed from wall-clock). That non-determinism is the finding: it forces an edit on every tick regardless of real change. Fix by deriving time displays from `player.position` rather than wall-clock where the state has not advanced.

- [ ] **Step 3: Add payload deduplication**

In `utils/music/models.py`, add a cheap fingerprint to the player and consult it before editing. In `LavalinkPlayer.__init__`:

```python
self._last_render_hash: Optional[int] = None
```

Then in the update path, immediately before the message edit:

```python
# Skip no-op edits: every redundant edit spends rate-limit budget shared
# with real user actions, which is what makes buttons feel slow.
try:
    fingerprint = hash(repr(normalize_components_to_dict(data.get("components") or []))
                       + repr([e.to_dict() for e in (data.get("embeds") or []) if e]))
except TypeError:
    fingerprint = None  # unhashable payload — fall through and edit

if fingerprint is not None and fingerprint == self._last_render_hash and not force:
    return
self._last_render_hash = fingerprint
```

Reset `self._last_render_hash = None` wherever the player message is recreated, so a fresh message always renders. Import `normalize_components_to_dict` from `disnake.ui.action_row`.

- [ ] **Step 4: Run the full suite**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v`
Expected: no regression against `phase1-baseline.txt`.

- [ ] **Step 5: Verify with a live boot**

Boot, play a track, and confirm the player message still updates visibly as the track progresses. A dedup bug that freezes the player is worse than the redundant edits.

- [ ] **Step 6: Commit**

```bash
git add utils/music/models.py tests/test_render_rate.py
git commit -m "perf: skip player message edits when the payload is unchanged"
```

---

# Phase 5 — Decompose `modules/music.py`

### Task 18: Extract the player controller dispatcher

**Files:**
- Create: `modules/music/__init__.py`, `modules/music/controller.py`
- Modify: `modules/music.py`
- Test: existing suite (the acceptance gate)

**Interfaces:**
- Produces: `modules.music.controller.PlayerControllerMixin` with `player_controller`, `player_button_event`, `player_dropdown_event`, preserving current signatures.

**Precondition:** Phases 1–4 complete and the full suite green. Do not start otherwise.

- [ ] **Step 1: Record the pre-extraction baseline**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v > /tmp/pre-extract.txt 2>&1`
Record pass/fail/xfail counts. This exact result must hold after the extraction.

- [ ] **Step 2: Convert `modules/music.py` into a package**

Create `modules/music/` and move `modules/music.py` to `modules/music/__init__.py` unchanged. Cogs are loaded by module path, so `modules.music` must keep resolving.

- [ ] **Step 3: Verify nothing changed**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v`
Expected: identical to Step 1. Also boot the bot and confirm `music.py Loaded.` still appears.

- [ ] **Step 4: Commit the move alone**

```bash
git add modules/
git commit -m "refactor: convert modules/music.py into a package (no behavior change)"
```

Keeping the pure move in its own commit makes the next diff readable.

- [ ] **Step 5: Extract the dispatcher into a mixin**

Move `player_controller`, `player_button_event`, `player_dropdown_event`, and `process_player_interaction` into `modules/music/controller.py` as `PlayerControllerMixin`. Make `Music` inherit from it. Change no logic.

- [ ] **Step 6: Verify equivalence**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v`
Expected: identical counts to Step 1, including the same xfail set. **A changed xfail set means behavior changed** — investigate before proceeding.

- [ ] **Step 7: Commit**

```bash
git add modules/music/
git commit -m "refactor: extract player controller dispatch into a mixin"
```

---

### Task 19: Extract search and track resolution

**Files:**
- Create: `modules/music/resolution.py`
- Modify: `modules/music/__init__.py`

**Interfaces:**
- Produces: `modules.music.resolution.TrackResolutionMixin` with `get_tracks`, `check_player_queue`, and the search helpers, signatures unchanged.

- [ ] **Step 1: Record the baseline**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v > /tmp/pre-extract-19.txt 2>&1`

- [ ] **Step 2: Move the methods**

Move `get_tracks`, `check_player_queue`, and their private helpers into `modules/music/resolution.py` as `TrackResolutionMixin`. Add it to `Music`'s bases. Change no logic.

- [ ] **Step 3: Verify equivalence**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v`
Expected: identical to Step 1.

- [ ] **Step 4: Live verification**

Boot; run a search; confirm playback works. Stop.

- [ ] **Step 5: Commit**

```bash
git add modules/music/
git commit -m "refactor: extract track resolution into a mixin"
```

---

### Task 20: Extract the static player lifecycle and confirm the target

**Files:**
- Create: `modules/music/static_player.py`
- Modify: `modules/music/__init__.py`
- Test: `tests/test_module_size.py` (create)

**Interfaces:**
- Produces: `modules.music.static_player.StaticPlayerMixin`; a size ratchet preventing regrowth.

- [ ] **Step 1: Write the size ratchet test**

Create `tests/test_module_size.py`:

```python
# -*- coding: utf-8 -*-
"""Keep modules small enough to reason about.

Baseline 2026-08-13: modules/music.py was 7,929 lines, which is why changes
there caused unrelated breakage. Lower these budgets as extraction proceeds;
never raise them.
"""
from pathlib import Path

import pytest

BUDGETS = {
    "modules/music/__init__.py": 1500,
    "modules/music/controller.py": 1500,
    "modules/music/resolution.py": 1500,
    "modules/music/static_player.py": 1500,
}


@pytest.mark.parametrize("path,budget", sorted(BUDGETS.items()))
def test_module_within_line_budget(path, budget):
    p = Path(path)
    if not p.exists():
        pytest.skip(f"{path} not yet created")
    lines = len(p.read_text(encoding="utf-8").splitlines())
    assert lines <= budget, f"{path} is {lines} lines, budget {budget}"
```

- [ ] **Step 2: Run to see the current state**

Run: `./venv/Scripts/python.exe -m pytest tests/test_module_size.py -v`
Expected: `modules/music/__init__.py` FAILS — still far over budget.

- [ ] **Step 3: Extract the static player lifecycle**

Move `send_idle_embed`, the static-player message handling, and the channel/message-ID persistence into `modules/music/static_player.py` as `StaticPlayerMixin`. Add it to `Music`'s bases.

- [ ] **Step 4: Verify equivalence and size**

Run: `./venv/Scripts/python.exe -m pytest tests/ -v`
Expected: identical pass/fail/xfail to the Phase 4 baseline, and the size test closer to passing.

If `__init__.py` remains over 1,500 lines, continue extracting along the remaining seams — playback commands and queue management — repeating this task's pattern until the budget is met.

- [ ] **Step 4b: Re-rank the remaining risks**

The spec (§4.5) makes `utils/music/models.py` (3,833 lines) and `utils/music/interactions.py` (3,349 lines) conditional targets — they get the same treatment *only if* they are still the largest remaining risks once `modules/music.py` is split. Decide with a measurement, not a guess:

```bash
./venv/Scripts/python.exe -c "
from pathlib import Path
rows=[(len(p.read_text(encoding='utf-8').splitlines()), str(p))
      for p in list(Path('modules').rglob('*.py'))+list(Path('utils').rglob('*.py'))]
for n,p in sorted(rows, reverse=True)[:8]: print(f'{n:6d}  {p}')
"
```

If either file still tops that list, extract it using this task's pattern — baseline the suite, move code without logic changes, verify identical pass/fail/xfail counts, commit — and add it to `BUDGETS`. If `modules/music/` submodules dominate instead, finish those first. Record the decision and its measurement in the commit message.

- [ ] **Step 5: Final full verification**

```bash
./venv/Scripts/python.exe -m pytest tests/ -v
PYTHONIOENCODING=utf-8 ./venv/Scripts/python.exe app.py   # boot, confirm all cogs load and node is ready, then stop
```

Compare against `docs/superpowers/plans/phase1-baseline.txt` and report the delta: tests added, xfails resolved, bugs fixed.

- [ ] **Step 6: Commit**

```bash
git add modules/music/ tests/test_module_size.py
git commit -m "refactor: extract static player lifecycle and add size ratchet"
```

---

## Completion criteria

- `pytest` green; every remaining `xfail` carries a reason naming a real, recorded limitation.
- `spsearch:` returns results; a Deezer query returns a clear bilingual message.
- No embed references the dead CDN attachment; all component emoji validate.
- Every user-visible error carries an Error ID resolvable to a stored traceback.
- No blocking HTTP inside a coroutine on the watched paths.
- No module over ~1,500 lines.
- A live boot loads all cogs, connects Lavalink, and syncs commands.
