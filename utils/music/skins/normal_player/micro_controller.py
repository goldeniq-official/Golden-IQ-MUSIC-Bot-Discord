# -*- coding: utf-8 -*-
"""Micro controller skin: small embed + 6 labeled buttons."""
from __future__ import annotations

from os.path import basename

import disnake

from utils.music.converters import fix_characters, get_button_style, music_source_image
from utils.music.models import LavalinkPlayer
from utils.music.ui import theme
from utils.music.ui.emoji_set import e as emoji
from utils.others import PlayerControls


class MicroController:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3]
        self.preview = "https://i.ibb.co/R0SsBxq/micro-controller.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = False
        player.controller_mode = True
        player.auto_update = 0
        player.hint_rate = player.bot.config["HINT_RATE"]
        player.static = False

    def load(self, player: LavalinkPlayer) -> dict:
        data: dict = {"content": None, "embeds": []}

        status = theme.status_for_player(player)
        color = theme.resolve_color(player.bot, player.guild, status)

        body = (
            f"-# [`{fix_characters(player.current.single_title, 32)}`]({player.current.uri or player.current.search_uri}) "
            f"[`{fix_characters(player.current.author, 12)}`] "
        )

        if not player.current.autoplay:
            body += f"<@{player.current.requester}>"
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            body += f"[`[Recommended]`]({related_url})" if related_url else "`[Recommended]`"

        if player.command_log:
            body += f"\n\n{player.command_log_emoji} ⠂**Last Interaction:** {player.command_log}"

        embed = disnake.Embed(color=color, description=body)
        embed.set_author(
            name=theme.author_for_status(status)[0],
            icon_url=music_source_image(player.current.info["sourceName"]),
        )

        if player.current_hint:
            hint_embed = disnake.Embed(colour=color)
            hint_embed.set_footer(text=f"{emoji('tip')} Tip: {player.current_hint}")
            data["embeds"].append(hint_embed)

        data["embeds"].append(embed)

        # 6 labeled buttons — the Discord layout will wrap to a second row on
        # narrow displays, which is acceptable for this opt-in compact skin.
        queue_empty = not (player.queue or player.queue_autoplay)
        data["components"] = [
            disnake.ui.Button(
                emoji=emoji("play_pause"),
                label="Resume" if player.paused else "Pause",
                custom_id=PlayerControls.pause_resume,
                style=get_button_style(player.paused),
            ),
            disnake.ui.Button(emoji=emoji("back"), label="Back", custom_id=PlayerControls.back),
            disnake.ui.Button(emoji=emoji("stop"), label="Stop", custom_id=PlayerControls.stop, style=disnake.ButtonStyle.red),
            disnake.ui.Button(emoji=emoji("skip"), label="Skip", custom_id=PlayerControls.skip),
            disnake.ui.Button(emoji=emoji("queue"), label="Queue", custom_id=PlayerControls.queue, disabled=queue_empty),
            disnake.ui.Button(emoji=emoji("favorite"), label="Favorite", custom_id=PlayerControls.add_favorite),
        ]

        return data


def load():
    return MicroController()
