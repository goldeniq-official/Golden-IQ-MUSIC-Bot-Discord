# -*- coding: utf-8 -*-
"""Micro no-controller skin: one tiny embed, no buttons."""
from __future__ import annotations

from os.path import basename

import disnake

from utils.music.converters import fix_characters
from utils.music.models import LavalinkPlayer
from utils.music.ui import theme
from utils.music.ui.emoji_set import e as emoji


class MicroNC:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3]
        self.preview = "https://media.discordapp.net/attachments/554468640942981147/1050275579766784051/micro_nc.png"

    def setup_features(self, player: LavalinkPlayer):
        player.mini_queue_feature = False
        player.controller_mode = False
        player.auto_update = 0
        player.hint_rate = 9
        player.static = False

    def load(self, player: LavalinkPlayer) -> dict:
        color = theme.resolve_color(player.bot, player.guild, theme.status_for_player(player))
        title = fix_characters(player.current.title, 30)
        author = fix_characters(player.current.author, 12)
        url = player.current.uri or player.current.search_uri

        embed = disnake.Embed(
            color=color,
            description=f"-# {emoji('queue')} **⠂[{title}]({url})** `[{author}]`",
        )

        data: dict = {"content": None, "embeds": [embed]}

        if player.current_hint:
            hint = disnake.Embed(color=color)
            hint.set_footer(text=f"{emoji('tip')} Tip: {player.current_hint}")
            data["embeds"].append(hint)

        return data


def load():
    return MicroNC()
