# -*- coding: utf-8 -*-
"""Default skin with a live Unicode progress bar (Spotify-card premium)."""
from __future__ import annotations

from os.path import basename

import disnake

from utils.music.converters import fix_characters, music_source_image, time_format
from utils.music.models import LavalinkPlayer
from utils.music.ui import progress, queue_render, theme
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
    return {"playing": "Now Playing", "paused": "Paused", "stopped": "Idle"}.get(status, status.title())


def _footer_text(player: LavalinkPlayer) -> str:
    parts = [f"🔊  {player.volume}%"]
    if player.loop: parts.append("🔁 Loop on")
    if player.autoplay: parts.append("🔄 Autoplay")
    if player.nightcore: parts.append("🎚 Nightcore")
    if player.keep_connected: parts.append("♾ 24/7")
    if player.restrict_mode: parts.append("🔐 DJ-only")
    return "   •   ".join(parts)


class DefaultProgressbarSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3]
        self.preview = "https://i.ibb.co/2yhVZRJ/default-progressbar.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = True
        player.controller_mode = True
        player.auto_update = 15
        player.hint_rate = player.bot.config["HINT_RATE"]
        player.static = False

    def load(self, player: LavalinkPlayer) -> dict:
        data: dict = {"content": None, "embeds": []}

        status = theme.status_for_player(player)
        color = theme.resolve_color(player.bot, player.guild, status)
        source = player.current.info.get("sourceName", "")

        embed = disnake.Embed(color=color)
        embed.set_author(
            name=f"{_status_header(status)}   •   {_source_label(source)}",
            icon_url=music_source_image(source),
        )

        embed.title = fix_characters(player.current.single_title, 90)
        embed.url = player.current.uri or player.current.search_uri

        lines: list[str] = [f"# {player.current.author}"]

        if player.current.album_name:
            album_text = fix_characters(player.current.album_name, 60)
            if player.current.album_url:
                lines.append(f"-# from [{album_text}]({player.current.album_url})")
            else:
                lines.append(f"-# from {album_text}")

        lines.append("")

        if player.current.is_stream:
            lines.append(f"{emoji('live')}   `{progress.FILLED_CHAR * 22}`   `LIVE`")
        else:
            bar = progress.render_unicode_bar(player.position, player.current.duration, width=22)
            lines.append(
                f"`{bar}`   `{time_format(player.position)} / {time_format(player.current.duration)}`"
            )

        meta_parts: list[str] = []
        if not player.current.autoplay:
            meta_parts.append(f"{emoji('request')} <@{player.current.requester}>")
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            meta_parts.append(
                f"{emoji('recommendation')} [Recommended]({related_url})" if related_url else f"{emoji('recommendation')} Recommended"
            )

        qsize = len(player.queue)
        if qsize and not player.mini_queue_enabled:
            meta_parts.append(f"{emoji('queue')} {qsize} in queue")
        if player.current.playlist_name:
            pl_text = fix_characters(player.current.playlist_name, 26)
            if player.current.playlist_url:
                meta_parts.append(f"{emoji('playlist')} [{pl_text}]({player.current.playlist_url})")
            else:
                meta_parts.append(f"{emoji('playlist')} {pl_text}")

        if meta_parts:
            lines.append("")
            lines.append("   •   ".join(meta_parts))

        if player.command_log:
            lines.append("")
            lines.append(f"{player.command_log_emoji}   *{player.command_log}*")

        embed.description = "\n".join(lines)
        embed.set_image(url=player.current.thumb)

        if player.current_hint:
            embed.set_footer(text=f"{emoji('tip')}   {player.current_hint}")
        else:
            embed.set_footer(text=_footer_text(player))

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
    return DefaultProgressbarSkin()
