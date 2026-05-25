# -*- coding: utf-8 -*-
"""Mini player skin: compact card with the original custom-emoji visual identity.

This skin's transport row uses bespoke server emojis rather than the global
EmojiSet defaults; the IDs are kept here so the visual identity survives a
skin refactor. Hosts who want different glyphs can override these names in
``CUSTOM_EMOJIS`` (see ``utils/music/ui/emoji_set.py``).
"""
from __future__ import annotations

from os.path import basename

import disnake

from utils.music.converters import fix_characters, get_button_style, music_source_image
from utils.music.models import LavalinkPlayer
from utils.music.ui import theme
from utils.music.ui.emoji_set import EmojiSet, get_default
from utils.others import PlayerControls


# Per-skin custom-emoji identity. Skin owners can override any of these via
# the bot-wide ``CUSTOM_EMOJIS`` config; otherwise the IDs below ship.
_SKIN_EMOJI_OVERRIDES = {
    "play_pause": "<:playpause:1000648043529519144>",
    "back": "<:backward:938437126532517928>",
    "stop": "<:stop:923282526322184212>",
    "skip": "<:skip:955164528595857488>",
    "favorite": "🤍",
}


class MiniPlayer:

    __slots__ = ("name", "preview")

    def __init__(self):
        self.name = basename(__file__)[:-3]
        self.preview = "https://i.ibb.co/R6668sT/image.png"

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

        # Skin-specific emoji resolver — overrides only apply to this skin.
        es: EmojiSet = get_default().with_overrides(**_SKIN_EMOJI_OVERRIDES)

        lines = [
            theme.status_accent_line(player),
            f"## [{fix_characters(player.current.single_title, 48)}]({player.current.uri or player.current.search_uri})",
            f"> 👤 **{fix_characters(player.current.author, 17)}**",
        ]

        if not player.current.autoplay:
            lines.append(f"> 🎧 Requested by <@{player.current.requester}>")
        else:
            related_url = player.current.info.get("extra", {}).get("related", {}).get("uri")
            if related_url:
                lines.append(f"> ✨ [Recommendation]({related_url})")
            else:
                lines.append("> ✨ Recommendation")

        if player.command_log:
            lines.append(f"> {player.command_log_emoji} {player.command_log}")

        embed = disnake.Embed(color=color, description="\n".join(lines))
        embed.set_author(
            name=theme.author_for_status(status)[0],
            icon_url=music_source_image(player.current.info["sourceName"]),
        )
        if player.current.thumb:
            embed.set_thumbnail(url=player.current.thumb)

        if player.current_hint:
            hint_embed = disnake.Embed(colour=color)
            hint_embed.set_footer(text=f"💡 Tip: {player.current_hint}")
            data["embeds"].append(hint_embed)

        data["embeds"].append(embed)

        # 5-button transport row, no overflow select — this skin is intentionally
        # compact. Custom-emoji identity preserved.
        data["components"] = [
            disnake.ui.Button(emoji=es("play_pause"), custom_id=PlayerControls.pause_resume, style=get_button_style(player.paused)),
            disnake.ui.Button(emoji=es("back"), custom_id=PlayerControls.back),
            disnake.ui.Button(emoji=es("stop"), custom_id=PlayerControls.stop, style=disnake.ButtonStyle.red),
            disnake.ui.Button(emoji=es("skip"), custom_id=PlayerControls.skip),
            disnake.ui.Button(emoji=es("favorite"), custom_id=PlayerControls.add_favorite),
        ]

        return data


def load():
    return MiniPlayer()
