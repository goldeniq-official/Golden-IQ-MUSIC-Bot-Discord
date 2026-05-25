# -*- coding: utf-8 -*-
"""Default static skin with a live progress bar (Spotify-card premium)."""
from __future__ import annotations

import itertools
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
    "applemusic": "Apple Music",
    "bandcamp": "Bandcamp",
    "twitch": "Twitch",
    "http": "Direct stream",
}


class DefaultProgressbarStaticSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3] + "_static"
        self.preview = "https://i.ibb.co/WtyW264/progressbar-static-skin.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = False
        player.controller_mode = True
        player.auto_update = 15
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
            name=f"{source_label} ⬩ {status_label}",
            icon_url=music_source_image(source),
        )
        embed.title = fix_characters(player.current.single_title, 90)
        embed.url = player.current.uri or player.current.search_uri

        # ── Body: Blockquote styling with Progress Bar ────────────────────
        lines: list[str] = [f"> 👤 **{player.current.author}**"]

        if player.current.is_stream:
            lines.append(f"> 🔴 `{progress.FILLED_CHAR * 15}`   `LIVE STREAM` ⬩ playing")
        else:
            bar = progress.render_unicode_bar(player.position, player.current.duration, width=15)
            state_emoji = "⏸️" if player.paused else "⏳"
            lines.append(
                f"> {state_emoji} `{bar}` `{time_format(player.position)} / {time_format(player.current.duration)}`"
            )

        if not player.current.autoplay:
            lines.append(f"> 🎧 Requested by <@{player.current.requester}>")
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            lines.append(
                f"> ✨ [Recommended Track]({related_url})" if related_url else f"> ✨ Recommended Track"
            )

        # Optional Album/Playlist info in blockquote
        extra_parts: list[str] = []
        if player.current.album_name:
            album_text = fix_characters(player.current.album_name, 40)
            if player.current.album_url:
                extra_parts.append(f"💿 [{album_text}]({player.current.album_url})")
            else:
                extra_parts.append(f"💿 {album_text}")

        try:
            extra_parts.append(f"📢 {player.guild.me.voice.channel.mention}")
        except AttributeError:
            pass

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
        embed.set_image(url=player.current.thumb)

        if player.current_hint:
            embed.set_footer(text=f"{emoji('tip')}   {player.current_hint}")
        else:
            parts = [f"🔊  {player.volume}%"]
            if player.autoplay: parts.append("🔄 Autoplay")
            if player.nightcore: parts.append("🎚 Nightcore")
            embed.set_footer(text="   •   ".join(parts))

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
    return DefaultProgressbarStaticSkin()
