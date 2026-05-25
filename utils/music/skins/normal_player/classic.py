# -*- coding: utf-8 -*-
"""Classic skin: two-embed premium card (artwork + body)."""
from __future__ import annotations

from os.path import basename

import disnake

from utils.music.converters import fix_characters, music_source_image, time_format
from utils.music.models import LavalinkPlayer
from utils.music.ui import queue_render, theme
from utils.music.ui.components import ButtonRowFactory
from utils.music.ui.emoji_set import e as emoji


_SOURCE_LABEL = {
    "youtube": "YouTube",
    "soundcloud": "SoundCloud",
    "spotify": "Spotify",
    "deezer": "Deezer",
    "applemusic": "Apple Music",
    "bandcamp": "Bandcamp",
    "twitch": "Twitch",
    "http": "Direct stream",
}


class ClassicSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3]
        self.preview = "https://i.ibb.co/893S3dJ/image.png"

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
        source = player.current.info.get("sourceName", "")
        source_label = _SOURCE_LABEL.get(source, source.title() if source else "Live")
        status_label = {"playing": "Now playing", "paused": "Paused"}.get(status, status.title())

        # ── Top embed: artwork-led header ───────────────────────────────
        embed_top = disnake.Embed(color=color)
        embed_top.set_author(
            name=f"{source_label} ⬩ {status_label}",
            icon_url=music_source_image(source),
        )
        embed_top.title = fix_characters(player.current.title, 90)
        embed_top.url = player.current.uri or player.current.search_uri
        embed_top.description = f"👤 **{player.current.author}**"
        embed_top.set_thumbnail(url=player.current.thumb)
        embed_top.set_image(url=theme.PREMIUM_DECORATIVE_BAR)

        # ── Bottom embed: Blockquote styling + optional mini-queue ──────
        body_lines: list[str] = []

        if player.current.is_stream:
            body_lines.append(f"> 🔴 `LIVE STREAM` ⬩ playing")
        elif player.paused:
            body_lines.append(f"> ⏸️ `{time_format(player.position)} / {time_format(player.current.duration)}` ⬩ paused")
        else:
            marker = queue_render.remaining_time_marker(player.current, position_ms=player.position)
            body_lines.append(
                f"> ⏳ `{time_format(player.position)} / {time_format(player.current.duration)}` ⬩ ends {marker}"
            )

        meta_parts: list[str] = []
        if not player.current.autoplay:
            meta_parts.append(f"🎧 Requested by <@{player.current.requester}>")
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            meta_parts.append(f"✨ [Recommended track]({related_url})" if related_url else "✨ Recommended track")
        if (qsize := len(player.queue)) and not player.mini_queue_enabled:
            meta_parts.append(f"📑 {qsize} in queue")
        if player.current.playlist_name:
            pl_text = fix_characters(player.current.playlist_name, 28)
            if player.current.playlist_url:
                meta_parts.append(f"📀 [{pl_text}]({player.current.playlist_url})")
            else:
                meta_parts.append(f"📀 {pl_text}")
        if player.loop:
            meta_parts.append("🔁 Loop")

        if meta_parts:
            body_lines.append(f"> {' ⬩ '.join(meta_parts)}")

        if player.command_log:
            body_lines.append("")
            body_lines.append(f"> {player.command_log_emoji}  *{player.command_log}*")

        if player.mini_queue_enabled:
            queue_text, is_rec = queue_render.render_queue_lines(player, max_items=5, format="compact")
            if queue_text:
                body_lines.append("")
                body_lines.append("## Up next ✨" if is_rec else "## Up next 📑")
                body_lines.append(queue_text)

        embed = disnake.Embed(color=color, description="\n".join(body_lines))
        embed.set_image(url=theme.PREMIUM_DECORATIVE_BAR)

        if player.current_hint:
            embed.set_footer(text=f"{emoji('tip')}  {player.current_hint}")
        else:
            parts = [f"🔊  Volume {player.volume}%"]
            if player.autoplay: parts.append("Autoplay")
            if player.keep_connected: parts.append("24/7")
            embed.set_footer(text="   ·   ".join(parts))

        data["embeds"] = [embed_top, embed]

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
    return ClassicSkin()
