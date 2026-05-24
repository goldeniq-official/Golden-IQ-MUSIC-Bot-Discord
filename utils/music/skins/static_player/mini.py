# -*- coding: utf-8 -*-
"""Mini static skin: compact single-column layout for the request channel."""
from __future__ import annotations

import itertools
from os.path import basename

import disnake

from utils.music.converters import fix_characters, music_source_image, time_format
from utils.music.models import LavalinkPlayer
from utils.music.ui import layout, queue_render, theme
from utils.music.ui.components import ButtonRowFactory
from utils.music.ui.emoji_set import e as emoji


_FALLBACK_BG = "https://media.discordapp.net/attachments/480195401543188483/987830071815471114/musicequalizer.gif"


class MiniStaticSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3] + "_static"
        self.preview = "https://i.ibb.co/F3NTnPc/mini-static-skin.png"

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

        title_line = f"## [`{player.current.single_title}`]({player.current.uri or player.current.search_uri})"

        badges: list[str] = []
        if player.current.track_loops:
            badges.append(f"`{emoji('loop_one')} {player.current.track_loops}`")
        elif player.loop == "current":
            badges.append(f"`{emoji('loop_one')} current`")
        elif player.loop == "queue":
            badges.append(f"`{emoji('loop')} queue`")

        if not player.current.autoplay:
            badges.append(f"`[`<@{player.current.requester}>`]`")
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            badges.append(layout.link("`[Recommended]`", related_url) if related_url else "`[Recommended]`")

        duration = "🔴 Livestream" if player.current.is_stream else time_format(player.current.duration)

        rows = [
            (emoji("clock"), f"**⠂Duration:** `{duration}`"),
            (emoji("person"), f"**⠂Uploader:** `{fix_characters(player.current.author, 28)}`"),
        ]

        sections = [
            theme.status_accent_line(player),
            f"{title_line} {' '.join(badges)}",
            layout.vertical_stack(rows),
        ]

        if player.command_log:
            sections.append(f"> -# {player.command_log_emoji} **Last action ⠂** {player.command_log}")

        embed = disnake.Embed(color=color, description="\n".join(sections))
        embed.set_author(
            name=theme.author_for_status(status)[0],
            icon_url=music_source_image(player.current.info["sourceName"]),
        )
        embed.set_image(url=player.current.thumb or _FALLBACK_BG)

        if player.current_hint:
            embed.set_footer(text=f"{emoji('tip')} Tip: {player.current_hint}")

        # Detailed queue uses a separate embed since static skins have room.
        queue_text, is_rec = queue_render.render_queue_lines(player, max_items=6, format="detailed")
        embed_queue = None
        if queue_text:
            title = "Next recommended songs:" if is_rec else f"Songs in queue: {len(player.queue)}"
            embed_queue = disnake.Embed(title=title, color=color, description=queue_text)

        data["embeds"] = [embed_queue, embed] if embed_queue else [embed]

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
    return MiniStaticSkin()
