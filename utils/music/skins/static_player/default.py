# -*- coding: utf-8 -*-
"""Default static-player skin.

Static skins live in a dedicated song-request channel — they have more
vertical space than the normal player view, so the detailed queue listing
(with relative timestamps) is the right default here.

A second select menu lets users jump directly to a queued track. The
description uses the accordion helper to cap the conditional info section
so even busy players stay readable on mobile.
"""
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

        embed = disnake.Embed(color=color)
        embed.set_author(
            name=theme.author_for_status(status)[0],
            icon_url=music_source_image(player.current.info["sourceName"]),
        )

        # ---- Header ------------------------------------------------------
        title_line = f"## [`{player.current.single_title}`]({player.current.uri or player.current.search_uri})"

        if player.current.is_stream:
            duration_line = f"> -# {emoji('live')} **⠂Streaming**"
        elif player.paused:
            duration_line = f"> -# {emoji('clock')} **⠂Duration:** `{time_format(player.current.duration)}`"
        else:
            marker = queue_render.remaining_time_marker(player.current, position_ms=player.position)
            duration_line = (
                f"> -# {emoji('clock')} **⠂Duration:** `{time_format(player.current.duration)}` ⠂ ends {marker}"
            )

        rows: list[tuple[str, str]] = [(emoji("person"), f"**⠂By:** {player.current.authors_md}")]
        if not player.current.autoplay:
            rows.append((emoji("request"), f"**⠂Requested by:** <@{player.current.requester}>"))
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            label = f"[`Recommendation`]({related_url})" if related_url else "`Recommendation`"
            rows.append((emoji("recommendation"), f"**⠂Added via:** {label}"))

        # ---- Conditional accordion ---------------------------------------
        extra_lines: list[str] = []
        if player.current.track_loops:
            extra_lines.append(layout.compact_field(emoji("loop_one"), "Loops left", f"`{player.current.track_loops}`"))
        if player.loop:
            extra_lines.append(layout.compact_field(
                emoji("loop_one") if player.loop == "current" else emoji("loop"),
                "Loop",
                "`Current song`" if player.loop == "current" else "`Queue`",
            ))
        if player.current.album_name:
            extra_lines.append(
                layout.compact_field(emoji("album"), "Album",
                                     layout.link(f"`{layout.truncate(player.current.album_name, 20)}`", player.current.album_url))
            )
        if player.current.playlist_name:
            extra_lines.append(
                layout.compact_field(emoji("playlist"), "Playlist",
                                     layout.link(f"`{layout.truncate(player.current.playlist_name, 20)}`", player.current.playlist_url))
            )
        if player.keep_connected:
            extra_lines.append(layout.compact_field(emoji("infinity"), "24/7 Mode", "`Enabled`"))
        try:
            vc_mention = player.guild.me.voice.channel.mention
            extra_lines.append(layout.compact_field("*️⃣", "Voice channel", vc_mention))
        except AttributeError:
            pass

        sections = [
            theme.status_accent_line(player),
            title_line,
            duration_line,
            layout.vertical_stack(rows),
        ]
        accordion = layout.accordion_text(extra_lines, visible=4, hidden_label="more")
        if accordion:
            sections.append(accordion)

        if player.command_log:
            sections.append(
                f"```ansi\n[34;1mLast Interaction:[0m```**┕ {player.command_log_emoji} ⠂**{player.command_log}"
            )

        embed.description = "\n".join(sections)
        embed.set_image(url=player.current.thumb or _FALLBACK_BG)

        if player.current_hint:
            embed.set_footer(text=f"{emoji('tip')} Tip: {player.current_hint}")
        else:
            embed.set_footer(text=str(player), icon_url="https://i.ibb.co/QXtk5VB/neon-circle.gif")

        # ---- Queue embed (detailed since static skins have vertical room)
        queue_text, is_rec = queue_render.render_queue_lines(player, max_items=8, format="detailed")
        embed_queue = None
        if queue_text:
            title = "Next recommended songs:" if is_rec else f"Songs in queue: {len(player.queue)}"
            embed_queue = disnake.Embed(title=title, color=color, description=queue_text)
            eta = queue_render.render_queue_footer_eta(player)
            if eta:
                embed_queue.description += f"\n{eta}"

        data["embeds"] = [embed_queue, embed] if embed_queue else [embed]

        # ---- Controls ----------------------------------------------------
        data["components"] = ButtonRowFactory.player_controls(player)
        data["components"].append(
            ButtonRowFactory.overflow_select(
                player,
                include_lyrics=bool(player.current.ytid and player.node.lyric_support),
                # mini_queue toggle not relevant for static skins.
                include_miniqueue=False,
                include_voice_status=isinstance(player.last_channel, disnake.VoiceChannel),
                # static skins live in their own channel — no thread option.
                include_thread=False,
            )
        )

        # Second select: jump-to-queued-track picker.
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
    return DefaultStaticSkin()
