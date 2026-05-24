# -*- coding: utf-8 -*-
"""Default static-player skin — Spotify-card aesthetic with detailed queue."""
from __future__ import annotations

import itertools
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


class DefaultStaticSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3] + "_static"
        self.preview = "https://i.ibb.co/fDzTqtV/default-static-skin.png"

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
        source = player.current.info.get("sourceName", "")
        source_label = _SOURCE_LABEL.get(source, source.title() if source else "Live")
        status_label = {"playing": "Now Playing", "paused": "Paused"}.get(status, status.title())

        embed = disnake.Embed(color=color)
        embed.set_author(
            name=f"{status_label}   •   {source_label}",
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
            lines.append(f"{emoji('live')}   **Live broadcast**")
        elif player.paused:
            lines.append(f"{emoji('pause')}   `{time_format(player.current.duration)}`")
        else:
            marker = queue_render.remaining_time_marker(player.current, position_ms=player.position)
            lines.append(
                f"{emoji('clock')}   `{time_format(player.current.duration)}`   •   ends {marker}"
            )

        meta_parts: list[str] = []
        if not player.current.autoplay:
            meta_parts.append(f"{emoji('request')} <@{player.current.requester}>")
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            meta_parts.append(f"{emoji('recommendation')} [Recommended]({related_url})" if related_url else f"{emoji('recommendation')} Recommended")
        try:
            meta_parts.append(f"🔊 {player.guild.me.voice.channel.mention}")
        except AttributeError:
            pass
        if player.loop:
            meta_parts.append("🔂 Loop song" if player.loop == "current" else "🔁 Loop queue")
        if player.current.track_loops:
            meta_parts.append(f"🔂 {player.current.track_loops} loop(s) left")
        if player.keep_connected:
            meta_parts.append("♾ 24/7")
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
            parts = [f"🔊  {player.volume}%"]
            if player.autoplay: parts.append("🔄 Autoplay")
            if player.nightcore: parts.append("🎚 Nightcore")
            embed.set_footer(text="   •   ".join(parts))

        # Detailed queue companion card
        queue_text, is_rec = queue_render.render_queue_lines(player, max_items=8, format="detailed")
        embed_queue = None
        if queue_text:
            title = "Up next  •  Recommended" if is_rec else f"Up next  •  {len(player.queue)}"
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
                include_miniqueue=False,
                include_voice_status=isinstance(player.last_channel, disnake.VoiceChannel),
                include_thread=False,
            )
        )

        if (queue := player.queue or player.queue_autoplay):
            data["components"].append(
                disnake.ui.Select(
                    placeholder="Jump to a queued song:",
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
    return DefaultStaticSkin()
