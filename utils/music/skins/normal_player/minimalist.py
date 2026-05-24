# -*- coding: utf-8 -*-
"""Minimalist skin: single content line, no embed, no controls."""
from __future__ import annotations

from os.path import basename

from utils.music.converters import fix_characters, time_format
from utils.music.models import LavalinkPlayer
from utils.music.ui.emoji_set import e as emoji


class Minimalist:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3]
        self.preview = "https://i.ibb.co/ynN9F4V/minimalist.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = False
        player.controller_mode = False
        player.auto_update = 0
        player.hint_rate = 9
        player.static = False

    def load(self, player: LavalinkPlayer) -> dict:
        duration = "🔴 Livestream" if player.current.is_stream else time_format(player.current.duration)
        title = fix_characters(player.current.title, 42)
        author = fix_characters(player.current.author, 20)
        url = player.current.uri or player.current.search_uri

        content = (
            f"-# {emoji('play')}`⠂Playing:` [`{title}`](<{url}>) "
            f"`[{author}] {duration}`"
        )

        if player.current_hint:
            content += f"\n-# {emoji('tip')}`⠂Tip: {player.current_hint}`"

        return {"content": content, "embeds": []}


def load():
    return Minimalist()
