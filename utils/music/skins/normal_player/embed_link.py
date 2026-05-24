# -*- coding: utf-8 -*-
"""Embed-link skin: content-only (no embed), keeps full controls.

Useful in channels where embeds are not allowed but the player should still
be controllable from the message.
"""
from __future__ import annotations

import re
from os.path import basename

import disnake

from utils.music.converters import fix_characters, time_format
from utils.music.models import LavalinkPlayer
from utils.music.ui import queue_render
from utils.music.ui.components import ButtonRowFactory
from utils.music.ui.emoji_set import e as emoji


_COMMAND_LOG_LINK_RE = re.compile(r"\[(.+)]\(.+\)")


class EmbedLinkSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3]
        self.preview = "https://media.discordapp.net/attachments/554468640942981147/1101330475164893244/Discord_N1QhBDXtar.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = False
        player.controller_mode = True
        player.auto_update = 0
        player.hint_rate = player.bot.config["HINT_RATE"]
        player.static = False

    def load(self, player: LavalinkPlayer) -> dict:
        data: dict = {"content": None, "embeds": []}

        parts: list[str] = []

        if player.current_hint:
            parts.append(f"> -# `{emoji('tip')}` **⠂Tip:** `{player.current_hint}`")

        if player.current.uri:
            title = f"[`{fix_characters(player.current.title, 40)}`]({player.current.uri})"
        else:
            title = f"`{fix_characters(player.current.title)}`"

        if player.paused:
            header = f"> -# {emoji('pause')} **⠂Paused:** {title}"
        else:
            header = f"> -# {emoji('play')} **⠂Now Playing:** {title}"
        parts.append(header)

        # Duration / ends-at marker
        if player.current.is_stream:
            parts.append(f"> -# `{emoji('live')}` **⠂Duration:** `Livestream`")
        else:
            duration_line = f"> -# `{emoji('clock')}` **⠂Duration:** `{time_format(player.current.duration)}`"
            if not player.paused:
                marker = queue_render.remaining_time_marker(player.current, position_ms=player.position)
                duration_line += f" ⠂ ends {marker}"
            parts.append(duration_line)

        # Queue / requester / autoplay attribution
        extras: list[str] = []
        if (q := len(player.queue)):
            extras.append(f"`In queue: {q}`")
        if not player.current.autoplay:
            extras.append(f"<@{player.current.requester}>")
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            extras.append(f"[`[Recommended Song]`](<{related_url}>)" if related_url else "`[Recommended Song]`")
        if extras:
            parts.append("> -# " + " ⠂ ".join(extras))

        if player.command_log:
            # Strip nested markdown links — otherwise Discord renders multiple
            # link previews for the same message.
            log = _COMMAND_LOG_LINK_RE.sub(r"\1", player.command_log.replace("`", ""))
            parts.append(f"> -# {player.command_log_emoji} **⠂Last Interaction:** {log}")

        data["content"] = "\n".join(parts)

        data["components"] = ButtonRowFactory.player_controls(player)
        data["components"].append(
            ButtonRowFactory.overflow_select(
                player,
                include_lyrics=bool(player.current.ytid and player.node.lyric_support),
                include_voice_status=isinstance(player.last_channel, disnake.VoiceChannel),
                include_thread=not player.has_thread,
                # No mini-queue option — this skin disables the feature.
                include_miniqueue=False,
            )
        )

        return data


def load():
    return EmbedLinkSkin()
