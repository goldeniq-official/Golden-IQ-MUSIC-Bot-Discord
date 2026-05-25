# -*- coding: utf-8 -*-
"""Mini skin: a compact single-column layout that drops the two-field grid.

The original used two side-by-side embed fields (Duration / Uploader); those
collapse awkwardly on phones. This version stacks them vertically.
"""
from __future__ import annotations

from os.path import basename

import disnake

from utils.music.converters import fix_characters, music_source_image, time_format
from utils.music.models import LavalinkPlayer
from utils.music.ui import layout, queue_render, theme
from utils.music.ui.components import ButtonRowFactory
from utils.music.ui.emoji_set import e as emoji


DECORATIVE_BAR = "https://cdn.discordapp.com/attachments/554468640942981147/1082887587770937455/rainbow_bar2.gif"


class MiniSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3]
        self.preview = "https://i.ibb.co/ZBTbdvT/mini.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = True
        player.controller_mode = True
        player.auto_update = 0
        player.hint_rate = player.bot.config["HINT_RATE"]
        player.static = False

    def load(self, player: LavalinkPlayer) -> dict:
        data: dict = {"content": None, "embeds": []}

        status = theme.status_for_player(player)
        color = theme.resolve_color(player.bot, player.guild, status)

        # Title with optional loop / autoplay / requester badges trailing.
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

        queue_size = len(player.queue)
        if queue_size:
            badges.append(f"`({queue_size})`")

        duration = "`LIVE STREAM` ⬩ streaming" if player.current.is_stream else f"`{time_format(player.position)} / {time_format(player.current.duration)}`"

        info_block = [
            f"> 👤 **{fix_characters(player.current.author, 28)}**",
            f"> ⏳ {duration}",
        ]

        sections = [
            theme.status_accent_line(player),
            title_line + " " + " ".join(badges) if badges else title_line,
            "\n".join(info_block),
        ]

        if player.command_log:
            sections.append(f"> {player.command_log_emoji} **{player.command_log}**")

        embed = disnake.Embed(color=color, description="\n".join(sections))
        embed.set_author(
            name=theme.author_for_status(status)[0],
            icon_url=music_source_image(player.current.info["sourceName"]),
        )
        embed.set_thumbnail(url=player.current.thumb)
        embed.set_image(url=DECORATIVE_BAR)

        if player.current_hint:
            embed.set_footer(text=f"{emoji('tip')} Tip: {player.current_hint}")

        embed_queue = None
        if player.mini_queue_enabled and queue_size:
            queue_text, _ = queue_render.render_queue_lines(player, max_items=5, format="compact")
            if queue_text:
                embed_queue = disnake.Embed(color=color, description=queue_text)
                embed_queue.set_image(url=DECORATIVE_BAR)

        data["embeds"] = [embed_queue, embed] if embed_queue else [embed]

        data["components"] = ButtonRowFactory.player_controls(player)
        data["components"].append(
            ButtonRowFactory.overflow_select(
                player,
                include_lyrics=bool(player.current.ytid and player.node.lyric_support),
                include_miniqueue=player.mini_queue_feature,
                include_voice_status=isinstance(player.last_channel, disnake.VoiceChannel),
                include_thread=not player.has_thread,
            )
        )

        return data


def load():
    return MiniSkin()
