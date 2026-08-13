# -*- coding: utf-8 -*-
"""Classic static skin: ANSI queue block in message content + detail embed."""
from __future__ import annotations

import itertools
from os.path import basename

import disnake

from utils.music.converters import fix_characters, music_source_image, time_format
from utils.music.models import LavalinkPlayer
from utils.music.ui import layout, queue_render, theme
from utils.music.ui.components import ButtonRowFactory
from utils.music.ui.emoji_set import e as emoji


class ClassicStaticSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3] + "_static"
        self.preview = "https://media.discordapp.net/attachments/554468640942981147/1047187412343853146/classic_static_skin.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = False
        player.controller_mode = True
        player.auto_update = 0
        player.hint_rate = player.bot.config["HINT_RATE"]
        player.static = True

    def load(self, player: LavalinkPlayer) -> dict:
        data: dict = {"content": None, "embeds": []}

        status = theme.status_for_player(player)
        color = theme.resolve_color(player.bot, player.guild, status)

        # Header block
        title = f"## [{player.current.title}]({player.current.uri or player.current.search_uri})"
        if player.current.is_stream:
            duration_line = f"> 🔴 `LIVE STREAM` ⬩ playing"
        else:
            marker = queue_render.remaining_time_marker(player.current, position_ms=player.position)
            duration_line = f"> ⏳ `{time_format(player.position)} / {time_format(player.current.duration)}` ⬩ ends {marker}"

        rows: list[str] = [f"> 👤 **{player.current.author}**"]
        if not player.current.autoplay:
            rows.append(f"> 🎧 Requested by <@{player.current.requester}>")
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            label = f"[Recommendation]({related_url})" if related_url else "Recommendation"
            rows.append(f"> ✨ {label}")

        if player.current.playlist_name:
            rows.append(f"> 📀 [{layout.truncate(player.current.playlist_name, 20)}]({player.current.playlist_url})")

        sections = [title, duration_line] + rows
        if player.command_log:
            sections.append(f"> {player.command_log_emoji} {player.command_log}")

        embed = disnake.Embed(color=color, description="\n".join(sections))
        embed.set_author(
            name=theme.author_for_status(status)[0],
            icon_url=music_source_image(player.current.info["sourceName"]),
        )
        embed.set_image(url=player.current.thumb)

        if player.current_hint:
            embed.set_footer(text=f"{emoji('tip')} Tip: {player.current_hint}")
        else:
            embed.set_footer(text=str(player), icon_url="https://i.ibb.co/QXtk5VB/neon-circle.gif")

        data["embeds"] = [embed]

        # ANSI queue block as message content — preserves the classic look.
        if qsize := len(player.queue):
            lines = "\n".join(
                f"[0;33m{(n + 1):02}[0m [0;34m[{time_format(t.duration) if not t.is_stream else '🔴 stream'}][0m [0;36m{fix_characters(t.title, 45)}[0m"
                for n, t in enumerate(itertools.islice(player.queue, 15))
            )
            data["content"] = "**Songs in queue:**\n```ansi\n" + lines
            if qsize > 15:
                data["content"] += f"\n\n[0;37mE mais[0m [0;35m{qsize - 15}[0m [0;37msongs.[0m"
            data["content"] += "```"
        elif len(player.queue_autoplay):
            lines = "\n".join(
                f"[0;33m{(n + 1):02}[0m [0;34m[{time_format(t.duration) if not t.is_stream else '🔴 stream'}][0m [0;36m{fix_characters(t.title, 45)}[0m"
                for n, t in enumerate(itertools.islice(player.queue_autoplay, 15))
            )
            data["content"] = "**Next recommended songs:**\n```ansi\n" + lines + "```"

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

        # Jump-to-track select for the static channel.
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
    return ClassicStaticSkin()
