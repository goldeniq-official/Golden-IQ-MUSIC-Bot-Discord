# -*- coding: utf-8 -*-
"""Fabricated disnake-shaped objects for offline rendering and dispatch tests.

Button clicks in a live Discord client cannot be automated, so the suite
drives the same code paths by handing the skins and handlers objects that
expose the attributes they actually read. Attribute coverage is derived from
what the skins touch — check utils/music/models.py before assuming a missing
attribute is a fixture gap rather than a real defect.
"""
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
        self.bot_ready = True
        self.dispatched: list[tuple] = []
        # No active player. This is a real, common scenario: a user clicks a
        # stale player message after the bot has left the voice channel. The
        # control must tell them something, not die silently.
        self.music = SimpleNamespace(players={})

    def get_color(self, _me=None):
        return disnake.Color(0xD4AF37)

    def is_ready(self):
        return True

    def dispatch(self, event, *args, **kwargs):
        # Records instead of firing. The dispatcher uses this to hand errors
        # to the error handler cog, so swallowing it here would hide the very
        # failures these tests exist to surface.
        self.dispatched.append((event, args, kwargs))

    def get_channel(self, cid):
        return SimpleNamespace(id=cid, guild=FakeGuild())


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
        self._track_loops = over.get("track_loops", 0)

    @property
    def authors_string(self) -> str:
        # Mirrors LavalinkTrack.authors_string (utils/music/models.py:191).
        return self.author

    @property
    def authors_md(self) -> str:
        return f"`{self.author}`"

    @property
    def authors(self) -> list:
        return [self.author]

    @property
    def track_loops(self) -> int:
        # Real tracks read this out of info["extra"] (models.py:231).
        return self.info.get("extra", {}).get("track_loops", self._track_loops)


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
        # Real values are False | "current" | "queue" (models.py:3632-3640).
        # Several skins branch on the exact string, so a bool would silently
        # exercise neither branch.
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
        "loop_current": make_player(loop="current",
                                    current=FakeTrack(info={"sourceName": "youtube",
                                                            "extra": {"track_loops": 3}})),
        "loop_queue": make_player(loop="queue",
                                  queue=[FakeTrack(title=f"Track {i}") for i in range(3)]),
        "all_toggles_on": make_player(loop="queue", autoplay=True, nightcore=True,
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
