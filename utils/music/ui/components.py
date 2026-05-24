# -*- coding: utf-8 -*-
"""Reusable disnake View / Modal / component classes.

This module exists so that ten different code paths don't each invent their
own "view that disables on timeout" or "paginator with prev/next buttons".

Public surface:

- :class:`BaseTimeoutView` — drop-in ``disnake.ui.View`` replacement that
  always disables its components and calls ``stop()`` on timeout. Subclasses
  override ``on_timeout_extra`` if they need to cancel background tasks etc.
- :class:`Paginator` — generic embed paginator. Replaces the trio of
  ``EmbedPaginatorInteraction``, ``ViewHelp``'s pagination, and the inline
  paginator scattered through views.
- :class:`Wizard` — multi-step view that swaps components per step while
  keeping the same message. Used by the rewritten ``SkinEditorMenu``.
- :class:`ButtonRowFactory` — produces the standard "transport" button row
  used by every player skin. Honors the ``EmojiSet`` so custom-emoji configs
  flow through automatically.

Backwards compatibility note: when a class here replaces an existing one,
the custom_id of any persistent component is preserved so saved messages
keep working.
"""
from __future__ import annotations

import asyncio
import traceback
from typing import Callable, List, Optional, Sequence, TYPE_CHECKING, Union

import disnake
from disnake.ext import commands

from utils.music.ui.emoji_set import e as emoji
from utils.music.ui.theme import resolve_color, status_for_player

if TYPE_CHECKING:
    from utils.music.models import LavalinkPlayer
    from utils.others import CustomContext


# ---------------------------------------------------------------------------
# Base view: always behaves correctly on timeout.
# ---------------------------------------------------------------------------


class BaseTimeoutView(disnake.ui.View):
    """Subclass of ``disnake.ui.View`` with sane timeout defaults.

    On timeout:
        1. Disables every interactive child (buttons + selects).
        2. Calls subclass hook ``on_timeout_extra`` for cleanup.
        3. Edits the original message to reflect the disabled state IF a
           ``message`` attribute was attached.
        4. Calls ``stop()``.

    The default is **not** to mutate the original message — many callers rely
    on the message text staying intact. Subclasses that want a "disabled"
    visual must set ``edit_on_timeout = True``.
    """

    edit_on_timeout: bool = False

    def __init__(self, *, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.message: Optional[disnake.Message] = None

    async def on_timeout_extra(self) -> None:  # pragma: no cover - override hook
        """Hook for subclasses to cancel tasks etc. Defaults to a no-op."""
        return None

    def _disable_children(self) -> None:
        for child in self.children:
            if isinstance(child, (disnake.ui.Button, disnake.ui.Select)):
                child.disabled = True

    async def on_timeout(self) -> None:
        try:
            self._disable_children()
            await self.on_timeout_extra()
            if self.edit_on_timeout and self.message is not None:
                try:
                    await self.message.edit(view=self)
                except disnake.HTTPException:
                    # Message deleted or thread archived — nothing to update.
                    pass
        finally:
            self.stop()


# ---------------------------------------------------------------------------
# Paginator: one class replaces three.
# ---------------------------------------------------------------------------


class Paginator(BaseTimeoutView):
    """Embed paginator with first / prev / next / last / close buttons.

    Construction options:
        embeds       — list of pre-built embeds (one per page); OR
        source       — callable ``(page_index, total) -> disnake.Embed`` for
                       lazy-built pages; in this mode ``total_pages`` must be
                       provided.
        author_only  — only the originating user can interact; default True.

    Custom IDs are stable so a long-running paginator survives a process
    restart if the parent stores ``message_id``.
    """

    edit_on_timeout = True

    def __init__(
        self,
        author: Union[disnake.User, disnake.Member],
        *,
        embeds: Optional[Sequence[disnake.Embed]] = None,
        source: Optional[Callable[[int, int], disnake.Embed]] = None,
        total_pages: Optional[int] = None,
        timeout: float = 180.0,
        author_only: bool = True,
        show_first_last: bool = True,
        close_label: str = "Close",
    ):
        super().__init__(timeout=timeout)
        self.author = author
        self.author_only = author_only

        if embeds is not None:
            self._embeds = list(embeds)
            self._source = None
            self.total = max(1, len(self._embeds))
        elif source is not None and total_pages is not None:
            self._embeds = None
            self._source = source
            self.total = max(1, total_pages)
        else:
            raise ValueError("Paginator needs either embeds or (source + total_pages)")

        self.current = 0

        if show_first_last and self.total > 2:
            self.add_item(_PaginatorBtn(self, "first", emoji("first"), 1))
        self.add_item(_PaginatorBtn(self, "prev", emoji("prev"), 1))
        self.add_item(_PaginatorBtn(self, "next", emoji("next"), 1))
        if show_first_last and self.total > 2:
            self.add_item(_PaginatorBtn(self, "last", emoji("last"), 1))
        self.add_item(_PaginatorBtn(self, "close", emoji("close"), 1, style=disnake.ButtonStyle.red, label=close_label))

        self._sync_disabled()

    def _sync_disabled(self) -> None:
        for child in self.children:
            if not isinstance(child, _PaginatorBtn):
                continue
            if child.kind in ("first", "prev"):
                child.disabled = self.current == 0
            elif child.kind in ("next", "last"):
                child.disabled = self.current >= self.total - 1

    def current_embed(self) -> disnake.Embed:
        if self._embeds is not None:
            return self._embeds[self.current]
        return self._source(self.current, self.total)

    async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
        if not self.author_only:
            return True
        if inter.author.id == self.author.id:
            return True
        await inter.send("Only the user who opened this menu can navigate.", ephemeral=True)
        return False

    async def _advance(self, inter: disnake.MessageInteraction, kind: str) -> None:
        if kind == "first":
            self.current = 0
        elif kind == "prev":
            self.current = max(0, self.current - 1)
        elif kind == "next":
            self.current = min(self.total - 1, self.current + 1)
        elif kind == "last":
            self.current = self.total - 1
        elif kind == "close":
            self._disable_children()
            try:
                await inter.response.edit_message(view=self)
            except disnake.HTTPException:
                pass
            self.stop()
            return

        self._sync_disabled()
        await inter.response.edit_message(embed=self.current_embed(), view=self)


class _PaginatorBtn(disnake.ui.Button):
    def __init__(self, paginator: Paginator, kind: str, em: str, row: int, *, style=disnake.ButtonStyle.secondary, label: Optional[str] = None):
        super().__init__(emoji=em, style=style, row=row, label=label)
        self._paginator = paginator
        self.kind = kind

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        await self._paginator._advance(inter, self.kind)


# ---------------------------------------------------------------------------
# Wizard: multi-step single-message flow.
# ---------------------------------------------------------------------------


class WizardStep:
    """A single step in a :class:`Wizard`.

    Subclasses or instances supply:
        title       — section title shown in the embed header
        description — long-form text for the step
        components  — list of ``disnake.ui.Item`` to attach to the view

    A step may declare ``can_advance`` to gate the Next button.
    """

    title: str = "Step"
    description: str = ""

    def __init__(self, *, title: str = "Step", description: str = "", components: Optional[List[disnake.ui.Item]] = None, can_advance: bool = True):
        self.title = title
        self.description = description
        self.components: List[disnake.ui.Item] = components or []
        self.can_advance = can_advance


class Wizard(BaseTimeoutView):
    """A view that swaps components & embed between steps.

    The first step shows ``Next``; intermediate steps show ``Back + Next``;
    the final step shows ``Back + Cancel + Save``. Subclass and override
    ``on_save`` and ``on_cancel``.
    """

    edit_on_timeout = True

    def __init__(
        self,
        author: Union[disnake.User, disnake.Member],
        steps: List[WizardStep],
        *,
        title_prefix: str = "Wizard",
        color: int = 0x5865F2,
        timeout: float = 600.0,
        author_only: bool = True,
    ):
        super().__init__(timeout=timeout)
        if not steps:
            raise ValueError("Wizard needs at least one step")
        self.author = author
        self.steps = steps
        self.title_prefix = title_prefix
        self.color = color
        self.author_only = author_only
        self.current = 0
        self._rebuild()

    @property
    def step(self) -> WizardStep:
        return self.steps[self.current]

    def build_embed(self) -> disnake.Embed:
        step = self.step
        embed = disnake.Embed(
            title=f"{self.title_prefix} — {step.title}",
            description=step.description,
            color=self.color,
        )
        embed.set_footer(text=f"Step {self.current + 1} / {len(self.steps)}")
        return embed

    def _rebuild(self) -> None:
        self.clear_items()
        for item in self.step.components:
            self.add_item(item)

        if self.current > 0:
            self.add_item(_WizardNav(self, "back", emoji("prev"), label="Back", style=disnake.ButtonStyle.secondary))

        if self.current < len(self.steps) - 1:
            btn = _WizardNav(self, "next", emoji("next"), label="Next", style=disnake.ButtonStyle.primary)
            btn.disabled = not self.step.can_advance
            self.add_item(btn)
        else:
            self.add_item(_WizardNav(self, "cancel", emoji("close"), label="Cancel", style=disnake.ButtonStyle.danger))
            self.add_item(_WizardNav(self, "save", emoji("ok"), label="Save", style=disnake.ButtonStyle.success))

    async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
        if not self.author_only:
            return True
        if inter.author.id == self.author.id:
            return True
        await inter.send("Only the user who opened the wizard can interact.", ephemeral=True)
        return False

    async def _advance(self, inter: disnake.MessageInteraction, direction: str) -> None:
        if direction == "back":
            self.current = max(0, self.current - 1)
        elif direction == "next":
            self.current = min(len(self.steps) - 1, self.current + 1)
        elif direction == "cancel":
            await self.on_cancel(inter)
            self._disable_children()
            await inter.response.edit_message(view=self)
            self.stop()
            return
        elif direction == "save":
            await self.on_save(inter)
            self._disable_children()
            try:
                await inter.response.edit_message(view=self)
            except disnake.InteractionResponded:
                pass
            self.stop()
            return

        self._rebuild()
        await inter.response.edit_message(embed=self.build_embed(), view=self)

    # Hooks — subclasses override.
    async def on_save(self, inter: disnake.MessageInteraction) -> None:  # pragma: no cover - override hook
        await inter.response.defer()

    async def on_cancel(self, inter: disnake.MessageInteraction) -> None:  # pragma: no cover - override hook
        await inter.response.defer()


class _WizardNav(disnake.ui.Button):
    def __init__(self, wizard: Wizard, direction: str, em: str, *, label: str, style: disnake.ButtonStyle):
        super().__init__(emoji=em, label=label, style=style, row=4)
        self._wizard = wizard
        self.direction = direction

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        await self._wizard._advance(inter, self.direction)


# ---------------------------------------------------------------------------
# Player control button row — the source of truth for skins.
# ---------------------------------------------------------------------------


class ButtonRowFactory:
    """Builds the standard 5-button transport row used by every player skin.

    A skin should call ``ButtonRowFactory.player_controls(player)`` instead
    of hand-rolling ``disnake.ui.Button(emoji="⏯️", custom_id=...)`` calls.
    This keeps the emoji set, button styles, and disabled-when logic
    consistent across all 15 skins.

    Returns ``list[disnake.ui.Button]`` — the caller still composes the
    surrounding select menu(s).
    """

    @staticmethod
    def player_controls(player: "LavalinkPlayer", *, include_queue: bool = True) -> List[disnake.ui.Button]:
        from utils.others import PlayerControls
        from utils.music.converters import get_button_style

        row = [
            disnake.ui.Button(
                emoji=emoji("play_pause"),
                custom_id=PlayerControls.pause_resume,
                style=get_button_style(player.paused),
            ),
            disnake.ui.Button(emoji=emoji("back"), custom_id=PlayerControls.back),
            disnake.ui.Button(emoji=emoji("stop"), custom_id=PlayerControls.stop, style=disnake.ButtonStyle.danger),
            disnake.ui.Button(emoji=emoji("skip"), custom_id=PlayerControls.skip),
        ]

        if include_queue:
            queue_empty = not (player.queue or getattr(player, "queue_autoplay", None))
            row.append(
                disnake.ui.Button(
                    emoji=emoji("queue"),
                    custom_id=PlayerControls.queue,
                    disabled=queue_empty,
                )
            )

        return row

    @staticmethod
    def overflow_select(
        player: "LavalinkPlayer",
        *,
        include_lyrics: bool = False,
        include_miniqueue: bool = False,
        include_voice_status: bool = False,
        include_thread: bool = False,
    ) -> disnake.ui.Select:
        """The "More options" select menu used by full skins.

        Conditional options are added by the caller based on player state.
        Returns a single ``disnake.ui.Select`` ready to attach to the view.
        """
        from utils.others import PlayerControls

        options = [
            disnake.SelectOption(
                label="Add song",
                emoji=emoji("add_music"),
                value=PlayerControls.add_song,
                description="Add a song / playlist to the queue.",
            ),
            disnake.SelectOption(
                label="Add to your favorites",
                emoji=emoji("favorite"),
                value=PlayerControls.add_favorite,
                description="Save the current song to your favorites.",
            ),
            disnake.SelectOption(
                label="Play from start",
                emoji=emoji("seek_start"),
                value=PlayerControls.seek_to_start,
                description="Restart the current song.",
            ),
            disnake.SelectOption(
                label=f"Volume: {player.volume}%",
                emoji="🔊",
                value=PlayerControls.volume,
                description="Adjust the playback volume.",
            ),
            disnake.SelectOption(
                label="Shuffle",
                emoji=emoji("shuffle"),
                value=PlayerControls.shuffle,
                description="Randomize the song order.",
            ),
            disnake.SelectOption(
                label="Re-add played songs",
                emoji=emoji("readd"),
                value=PlayerControls.readd,
                description="Bring already-played songs back to the queue.",
            ),
            disnake.SelectOption(
                label="Loop mode",
                emoji=emoji("loop"),
                value=PlayerControls.loop_mode,
                description="Cycle between off / current song / full queue.",
            ),
            disnake.SelectOption(
                label=("Disable" if player.nightcore else "Enable") + " nightcore",
                emoji=emoji("nightcore"),
                value=PlayerControls.nightcore,
                description="Speed up + pitch shift effect.",
            ),
            disnake.SelectOption(
                label=("Disable" if player.autoplay else "Enable") + " autoplay",
                emoji=emoji("autoplay"),
                value=PlayerControls.autoplay,
                description="Auto-queue recommended songs when empty.",
            ),
            disnake.SelectOption(
                label="Last.fm scrobble",
                emoji=emoji("lastfm"),
                value=PlayerControls.lastfm_scrobble,
                description="Toggle scrobbling to your Last.fm account.",
            ),
            disnake.SelectOption(
                label=("Disable" if player.restrict_mode else "Enable") + " restricted mode",
                emoji=emoji("restrict"),
                value=PlayerControls.restrict_mode,
                description="Limit advanced controls to DJ / staff.",
            ),
        ]

        if include_lyrics:
            options.append(
                disnake.SelectOption(
                    label="View lyrics",
                    emoji=emoji("lyrics"),
                    value=PlayerControls.lyrics,
                    description="Show the lyrics for the current song.",
                )
            )
        if include_miniqueue:
            options.append(
                disnake.SelectOption(
                    label="Player mini-queue",
                    emoji=emoji("miniqueue"),
                    value=PlayerControls.miniqueue,
                    description="Toggle the inline mini-queue preview.",
                )
            )
        if include_voice_status:
            options.append(
                disnake.SelectOption(
                    label="Automatic voice status",
                    emoji=emoji("voice_status"),
                    value=PlayerControls.set_voice_status,
                    description="Configure auto-updating voice channel status.",
                )
            )
        if include_thread:
            options.append(
                disnake.SelectOption(
                    label="Song-request thread",
                    emoji=emoji("thread"),
                    value=PlayerControls.song_request_thread,
                    description="Create a thread to request songs by name.",
                )
            )

        return disnake.ui.Select(
            placeholder="More options:",
            custom_id="musicplayer_dropdown_inter",
            min_values=0,
            max_values=1,
            required=False,
            options=options,
        )


# ---------------------------------------------------------------------------
# Helpers for views that need to safely cancel updater tasks on timeout.
# ---------------------------------------------------------------------------


def cancel_task(task: Optional[asyncio.Task]) -> None:
    """Cancel an asyncio task without raising if it's already done."""
    if task is None or task.done():
        return
    try:
        task.cancel()
    except Exception:
        traceback.print_exc()
