# -*- coding: utf-8 -*-
"""Default normal-player skin — Spotify-card premium aesthetic.

Visual decisions:
    1. Artwork as thumbnail, with RGB decorative bar as image — full-width card).
    2. Title is the embed.title (Discord's largest text), linked & blue.
    3. Artist uses `#` markdown for a second tier of prominence.
    4. Body avoids emoji-per-item chip rows; meta info is one prose line.
    5. Footer carries quiet stats only.
    6. RGB Decorative rainbow bar included — the artwork *is* the visual.
"""
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
    "twitch": "Twitch",
    "applemusic": "Apple Music",
    "bandcamp": "Bandcamp",
    "http": "Direct stream",
}


def _source_label(source_name: str) -> str:
    return _SOURCE_LABEL.get(source_name, source_name.title() if source_name else "Live")


def _status_header(status: str) -> str:
    return {
        "playing": "Now Playing",
        "paused": "Paused",
        "stopped": "Idle",
    }.get(status, status.title())


def _footer_text(player: LavalinkPlayer) -> str:
    parts = [f"🔊  {player.volume}%"]
    if player.loop:
        parts.append("🔁 Loop on")
    if player.autoplay:
        parts.append("🔄 Autoplay")
    if player.nightcore:
        parts.append("🎚 Nightcore")
    if player.keep_connected:
        parts.append("♾ 24/7")
    if player.restrict_mode:
        parts.append("🔐 DJ-only")
    return "   •   ".join(parts)


class DefaultSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3]
        self.preview = "https://i.ibb.co/4PkWyqb/image.png"

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

        # ── Header (small text above title) ─────────────────────────────
        embed = disnake.Embed(color=color)
        embed.set_author(
            name=f"{_source_label(source)} ⬩ {_status_header(status)}",
            icon_url=music_source_image(source),
        )

        # ── Title (Discord's largest text, clickable) ───────────────────
        embed.title = fix_characters(player.current.single_title, 90)
        embed.url = player.current.uri or player.current.search_uri

        # ── Body: Blockquote styling for next-gen UI ────────────────────
        lines: list[str] = []

        # Artist
        lines.append(f"> 👤 **{player.current.author}**")

        # Duration & Status
        if player.current.is_stream:
            lines.append(f"> 🔴 `LIVE STREAM` ⬩ playing")
        elif player.paused:
            lines.append(f"> ⏸️ `{time_format(player.position)} / {time_format(player.current.duration)}` ⬩ paused")
        else:
            marker = queue_render.remaining_time_marker(
                player.current, position_ms=player.position
            )
            lines.append(
                f"> ⏳ `{time_format(player.position)} / {time_format(player.current.duration)}` ⬩ ends {marker}"
            )

        # Meta & Requester
        if not player.current.autoplay:
            lines.append(f"> 🎧 Requested by <@{player.current.requester}>")
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            lines.append(
                f"> ✨ [Recommended Track]({related_url})"
                if related_url else f"> ✨ Recommended Track"
            )

        # Optional Album/Playlist info in blockquote
        extra_parts: list[str] = []
        if player.current.album_name:
            album_text = fix_characters(player.current.album_name, 40)
            if player.current.album_url:
                extra_parts.append(f"💿 [{album_text}]({player.current.album_url})")
            else:
                extra_parts.append(f"💿 {album_text}")

        qsize = len(player.queue)
        if qsize and not player.mini_queue_enabled:
            extra_parts.append(f"📑 {qsize} in queue")

        if player.current.playlist_name:
            pl_text = fix_characters(player.current.playlist_name, 26)
            if player.current.playlist_url:
                extra_parts.append(f"📀 [{pl_text}]({player.current.playlist_url})")
            else:
                extra_parts.append(f"📀 {pl_text}")

        if extra_parts:
            lines.append(f"> {' ⬩ '.join(extra_parts)}")

        if player.command_log:
            lines.append("")
            lines.append(f"{player.command_log_emoji}   *{player.command_log}*")

        embed.description = "\n".join(lines)

        # ── Artwork as the hero visual (full-width card) ───────────────
        embed.set_thumbnail(url=player.current.thumb)
        embed.set_image(url=theme.PREMIUM_DECORATIVE_BAR)

        if player.current_hint:
            embed.set_footer(text=f"{emoji('tip')}   {player.current_hint}")
        else:
            embed.set_footer(text=_footer_text(player))

        # ── Optional mini-queue as a quiet companion embed ─────────────
        embed_queue = None
        if player.mini_queue_enabled:
            queue_text, is_rec = queue_render.render_queue_lines(player, max_items=5, format="compact")
            if queue_text:
                title = "Up next  •  Recommended" if is_rec else f"Up next  •  {qsize}"
                embed_queue = disnake.Embed(title=title, color=color, description=queue_text)
                eta = queue_render.render_queue_footer_eta(player)
                if eta:
                    embed_queue.description += f"\n\n{eta}"

        data["embeds"] = [embed_queue, embed] if embed_queue else [embed]

        # ── Controls ────────────────────────────────────────────────────
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
    return DefaultSkin()
