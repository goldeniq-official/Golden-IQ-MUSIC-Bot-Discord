# -*- coding: utf-8 -*-
"""Lite skin: a single small embed with no controls — display-only."""
from __future__ import annotations

from os.path import basename

import disnake

from utils.music.converters import fix_characters, time_format
from utils.music.models import LavalinkPlayer
from utils.music.ui import theme
from utils.music.ui.emoji_set import e as emoji


class LiteSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3]
        self.preview = "https://i.ibb.co/h2r9Y5p/lite.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = False
        player.controller_mode = False
        player.auto_update = 0
        player.hint_rate = 9
        player.static = False

    def load(self, player: LavalinkPlayer) -> dict:
        data: dict = {"content": None, "embeds": []}

        status = theme.status_for_player(player)
        color = theme.resolve_color(player.bot, player.guild, status)

        duration = "🔴 `LIVE STREAM`" if player.current.is_stream else f"`{time_format(player.position)} / {time_format(player.current.duration)}`"

        lines = [
            f"> ▶ **│**[`{fix_characters(player.current.title, 45)}`]({player.current.uri or player.current.search_uri})",
            f"> 👤 **│**`{fix_characters(player.current.author, 18)}`",
            f"> ⏳ **│**{duration}",
        ]

        if not player.current.autoplay:
            lines.append(f"> 🎧 **│**<@{player.current.requester}>")
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            if related_url:
                lines.append(f"> ✨ **│**[`[Recommended]`]({related_url})")
            else:
                lines.append(f"> ✨ **│**`[Recommended]`")

        if player.current.playlist_name:
            lines.append(
                f"> 📀 **│**[`{player.current.playlist_name}`]({player.current.playlist_url})"
            )

        embed = disnake.Embed(color=color, description="\n".join(lines))
        embed.set_thumbnail(player.current.thumb)
        data["embeds"].append(embed)

        if player.current_hint:
            hint = disnake.Embed(color=color)
            hint.set_footer(text=f"{emoji('tip')} Tip: {player.current_hint}")
            data["embeds"].append(hint)

        return data


def load():
    return LiteSkin()
