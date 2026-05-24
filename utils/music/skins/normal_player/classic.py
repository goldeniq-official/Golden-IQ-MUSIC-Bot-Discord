# -*- coding: utf-8 -*-
"""Classic skin: two-embed layout with a title-led header embed."""
from __future__ import annotations

from os.path import basename

import disnake

from utils.music.converters import music_source_image, time_format
from utils.music.models import LavalinkPlayer
from utils.music.ui import layout, queue_render, theme
from utils.music.ui.components import ButtonRowFactory
from utils.music.ui.emoji_set import e as emoji


DECORATIVE_BAR = "https://cdn.discordapp.com/attachments/554468640942981147/1127294696025227367/rainbow_bar3.gif"


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

        embed_top = disnake.Embed(
            color=color,
            description=f"## [{player.current.title}]({player.current.uri or player.current.search_uri})",
        )
        embed_top.set_author(
            name=theme.author_for_status(status)[0],
            icon_url=music_source_image(player.current.info["sourceName"]),
        )
        embed_top.set_thumbnail(url=player.current.thumb)
        embed_top.set_image(url=DECORATIVE_BAR)

        # ---- Body embed ---------------------------------------------------
        rows: list[tuple[str, str]] = []
        if player.current.is_stream:
            rows.append((emoji("live"), "`Live broadcast`"))
        else:
            rows.append((emoji("clock"), f"`{time_format(player.current.duration)}`"))

        rows.append((emoji("person"), f"`{player.current.author}`"))

        if not player.current.autoplay:
            rows.append(("🎧", f"<@{player.current.requester}>"))
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            rows.append((emoji("recommendation"), f"[`Recommended`]({related_url})" if related_url else "`Recommended`"))

        if player.current.playlist_name:
            rows.append((
                emoji("playlist"),
                layout.link(f"`{layout.truncate(player.current.playlist_name, 36)}`", player.current.playlist_url),
            ))

        if (qsize := len(player.queue)) and not player.mini_queue_enabled:
            rows.append((emoji("queue"), f"`{qsize} song{'s'[:qsize ^ 1]} in queue`"))

        body = layout.vertical_stack(rows)

        if player.command_log:
            body += f"\n> -# {player.command_log_emoji} **Last action ⠂** {player.command_log}"

        # ---- Optional mini-queue inline -----------------------------------
        queue_text, _ = queue_render.render_queue_lines(player, max_items=5, format="compact")
        if queue_text and player.mini_queue_enabled:
            body += f"\n\n**Next up:**\n{queue_text}"

        embed = disnake.Embed(color=color, description=body)
        embed.set_image(url=DECORATIVE_BAR)

        if player.current_hint:
            embed.set_footer(text=f"{emoji('tip')} Tip: {player.current_hint}")
        else:
            embed.set_footer(text=str(player), icon_url="https://i.ibb.co/QXtk5VB/neon-circle.gif")

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
