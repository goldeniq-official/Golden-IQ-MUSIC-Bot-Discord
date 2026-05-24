# -*- coding: utf-8 -*-
"""Default skin with a Unicode progress bar in place of the "ends in" line."""
from __future__ import annotations

from os.path import basename

import disnake

from utils.music.converters import music_source_image, time_format
from utils.music.models import LavalinkPlayer
from utils.music.ui import layout, progress, queue_render, theme
from utils.music.ui.components import ButtonRowFactory
from utils.music.ui.emoji_set import e as emoji


DECORATIVE_BAR = "https://cdn.discordapp.com/attachments/554468640942981147/1127294696025227367/rainbow_bar3.gif"


class DefaultProgressbarSkin:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3]
        self.preview = "https://i.ibb.co/683gh83/image.png"

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

        embed = disnake.Embed(color=color)
        embed.set_author(
            name=theme.author_for_status(status)[0],
            icon_url=music_source_image(player.current.info["sourceName"]),
        )

        if player.current.is_stream:
            position_line = f"`{progress.FILLED_CHAR * 18}` ⠂ `🔴 LIVE`"
        else:
            bar = progress.render_unicode_bar(player.position, player.current.duration, width=18)
            position_line = (
                f"`{bar}` ⠂ `{time_format(player.position)} / {time_format(player.current.duration)}`"
            )

        rows: list[tuple[str, str]] = [(emoji("person"), player.current.authors_md)]
        if not player.current.autoplay:
            rows.append((emoji("request"), f"<@{player.current.requester}>"))
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            rows.append((emoji("recommendation"), f"[`Recommended`]({related_url})" if related_url else "`Recommended`"))

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
                                     layout.link(f"`{layout.truncate(player.current.album_name, 36)}`", player.current.album_url))
            )
        if player.current.playlist_name:
            extra_lines.append(
                layout.compact_field(emoji("playlist"), "Playlist",
                                     layout.link(f"`{layout.truncate(player.current.playlist_name, 36)}`", player.current.playlist_url))
            )
        if (qlen := len(player.queue)) and not player.mini_queue_enabled:
            extra_lines.append(layout.compact_field(emoji("queue"), "In queue", f"`{qlen} song{'s'[:qlen ^ 1]}`"))
        if player.keep_connected:
            extra_lines.append(layout.compact_field(emoji("infinity"), "24/7 mode", "`Enabled`"))

        title_line = f"## [`{player.current.single_title}`]({player.current.uri or player.current.search_uri})"
        sections = [theme.status_accent_line(player), title_line, position_line, layout.vertical_stack(rows)]
        accordion = layout.accordion_text(extra_lines, visible=3, hidden_label="more")
        if accordion:
            sections.append(accordion)

        if player.command_log:
            sections.append(f"> -# {player.command_log_emoji} **Last action ⠂** {player.command_log}")

        embed.description = "\n".join(sections)
        embed.set_thumbnail(url=player.current.thumb)
        embed.set_image(url=DECORATIVE_BAR)

        if player.current_hint:
            embed.set_footer(text=f"{emoji('tip')} Tip: {player.current_hint}")
        else:
            embed.set_footer(text=str(player), icon_url="https://i.ibb.co/QXtk5VB/neon-circle.gif")

        embed_queue = None
        if player.mini_queue_enabled:
            queue_text, is_rec = queue_render.render_queue_lines(player, max_items=5, format="compact")
            if queue_text:
                title = "Next up — recommended:" if is_rec else f"Next in queue · {len(player.queue)}"
                embed_queue = disnake.Embed(title=title, color=color, description=queue_text)
                eta = queue_render.render_queue_footer_eta(player)
                if eta:
                    embed_queue.description += f"\n{eta}"
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
    return DefaultProgressbarSkin()
