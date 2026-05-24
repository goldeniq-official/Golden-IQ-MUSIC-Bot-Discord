# -*- coding: utf-8 -*-
"""Embed-link static skin: content-only (no embed), full controls."""
from __future__ import annotations

import itertools
from os.path import basename

import disnake

from utils.music.converters import fix_characters, time_format
from utils.music.models import LavalinkPlayer
from utils.music.ui import layout, queue_render, theme
from utils.music.ui.components import ButtonRowFactory
from utils.music.ui.emoji_set import e as emoji


class EmbedLinkStaticSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3] + "_static"
        self.preview = "https://media.discordapp.net/attachments/554468640942981147/1101328287466274816/image.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = False
        player.controller_mode = True
        player.auto_update = 0
        player.hint_rate = player.bot.config["HINT_RATE"]
        player.static = True

    def load(self, player: LavalinkPlayer) -> dict:
        parts: list[str] = []

        if player.current_hint:
            parts.append(f"> -# `{emoji('tip')} Tip: {player.current_hint}`")

        # Header
        title = (
            f"[{fix_characters(player.current.title)}]({player.current.uri})"
            if player.current.uri else fix_characters(player.current.title)
        )
        if player.paused:
            parts.append(f"> ### {emoji('pause')} ⠂Paused: {title}")
        else:
            parts.append(f"> ### {emoji('play')} ⠂Now Playing: {title}")

        # Duration row
        if player.current.is_stream:
            parts.append(f"> -# {emoji('live')} **⠂Duration:** `Livestream`")
        else:
            duration_line = f"> -# {emoji('clock')} **⠂Duration:** `{time_format(player.current.duration)}`"
            if not player.paused:
                marker = queue_render.remaining_time_marker(player.current, position_ms=player.position)
                duration_line += f" ⠂ ends {marker}"
            parts.append(duration_line)

        # Attribution + extras
        if not player.current.autoplay:
            parts.append(f"> -# {emoji('request')} **⠂Requested by:** <@{player.current.requester}>")
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            label = f"[`Recommended Song`](<{related_url}>)" if related_url else "`Recommended Song`"
            parts.append(f"> -# {emoji('recommendation')} **⠂Added via:** {label}")

        extras: list[str] = []
        if player.current.playlist_name:
            extras.append(layout.compact_field(
                emoji("playlist"), "Playlist",
                f"[`{fix_characters(player.current.playlist_name) or 'View'}`](<{player.current.playlist_url}>)",
            ))
        if player.current.track_loops:
            extras.append(layout.compact_field(emoji("loop_one"), "Loops left", f"`{player.current.track_loops}`"))
        elif player.loop == "current":
            extras.append(layout.compact_field(emoji("loop_one"), "Loop", "`current song`"))
        elif player.loop == "queue":
            extras.append(layout.compact_field(emoji("loop"), "Loop", "`queue`"))
        try:
            extras.append(layout.compact_field("*️⃣", "Voice channel", player.guild.me.voice.channel.mention))
        except AttributeError:
            pass

        if extras:
            parts.append(layout.accordion_text(extras, visible=3, hidden_label="more"))

        if player.command_log:
            parts.append(f"> -# {player.command_log_emoji} **⠂Last Interaction:** {player.command_log}")

        if qsize := len(player.queue):
            queue_text, _ = queue_render.render_queue_lines(player, max_items=5, format="compact")
            header = f"> -# **Next in queue · {qsize}**" if qsize > 4 else "> -# **Next in queue**"
            parts.append(header)
            parts.append(queue_text)

        data: dict = {"content": "\n".join(parts), "embeds": []}

        data["components"] = ButtonRowFactory.player_controls(player)
        data["components"].append(
            ButtonRowFactory.overflow_select(
                player,
                include_lyrics=bool(player.current.ytid and player.node.lyric_support),
                include_miniqueue=False,
                include_voice_status=isinstance(player.last_channel, disnake.VoiceChannel),
                include_thread=False,
            )
        )

        if (queue := player.queue or player.queue_autoplay):
            data["components"].append(
                disnake.ui.Select(
                    placeholder="Next songs:",
                    custom_id="musicplayer_queue_dropdown",
                    min_values=0,
                    max_values=1,
                    required=False,
                    options=[
                        disnake.SelectOption(
                            label=fix_characters(f"{n + 1}. {t.single_title}", 47),
                            description=fix_characters(
                                f"[{time_format(t.duration) if not t.is_stream else '🔴 Live'}]. {t.authors_string}",
                                47,
                            ),
                            value=f"{n:02d}.{t.title[:96]}",
                        )
                        for n, t in enumerate(itertools.islice(queue, 25))
                    ],
                )
            )

        return data


def load():
    return EmbedLinkStaticSkin()
