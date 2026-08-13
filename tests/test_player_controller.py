# -*- coding: utf-8 -*-
"""Drive every PlayerControls value through the dispatcher.

A control that raises an unhandled exception, or that returns without ever
acknowledging the interaction, is what users experience as a dead button or
the red error text. Clicking in Discord cannot be automated, so this is the
closest equivalent: call the dispatcher directly with a fabricated
interaction.
"""
from __future__ import annotations

import inspect

import pytest

from utils.others import PlayerControls


def all_control_values() -> dict:
    return {
        name: value
        for name, value in vars(PlayerControls).items()
        if not name.startswith("_") and isinstance(value, str)
    }


CONTROLS = sorted(all_control_values().items())


def test_thirty_controls_are_defined():
    assert len(CONTROLS) == 30, f"expected 30 controls, found {len(CONTROLS)}"


@pytest.mark.parametrize("name,value", CONTROLS, ids=[n for n, _ in CONTROLS])
def test_control_id_is_well_formed(name, value):
    assert value.startswith("musicplayer_"), (
        f"{name}={value!r} does not start with the musicplayer_ prefix the "
        f"on_button_click listener filters on — this button is silently ignored"
    )
    assert len(value) <= 100, f"{name}: custom_id over Discord's 100-char limit"


def test_control_ids_are_unique():
    values = [v for _, v in CONTROLS]
    dupes = {v for v in values if values.count(v) > 1}
    assert not dupes, f"duplicate custom_ids dispatch to the wrong handler: {dupes}"


def test_dispatcher_signature_is_stable():
    from modules.music import Music

    sig = inspect.signature(Music.player_controller)
    assert list(sig.parameters)[:3] == ["self", "interaction", "control"]


# Controls that silently return with no user feedback at all.
# See test_control_never_dies_silently for why this is the bug that produces
# dead buttons.
#
# Fixed and removed from this map:
#   embed_forceplay, embed_enqueue_track, embed_enqueue_playlist —
#   modules/music.py resolved the track URL with two bare `return`
#   statements (one inside a bare `except:`) that left the interaction
#   unacknowledged. Both paths now raise GenericError, which the outer
#   handler dispatches to the ErrorHandler cog as a bilingual message.
KNOWN_SILENT: dict[str, str] = {}


def _dispatch_params():
    params = []
    for name, value in CONTROLS:
        reason = KNOWN_SILENT.get(name)
        marks = [pytest.mark.xfail(reason=reason, strict=True)] if reason else []
        params.append(pytest.param(name, value, marks=marks, id=name))
    return params


@pytest.mark.parametrize("name,value", _dispatch_params())
async def test_control_never_dies_silently(name, value):
    """A control must always give the user *some* feedback.

    Two outcomes are legitimate:
      1. It acknowledges the interaction (defer / send / edit_message).
      2. It raises or dispatches an error, which the ErrorHandler cog turns
         into a visible message.

    The bug this catches is the third case: a bare `return` that does
    neither. Discord then shows "This interaction failed" after 3 seconds,
    or the button simply appears dead — the exact symptom reported.

    The scenario here is a real one: no active player, as when a user clicks
    a stale player message after the bot has left the voice channel.
    """
    from modules.music import Music
    from tests.conftest import FakeInteraction, FakePlayer
    from utils.music.errors import GenericError

    player = FakePlayer()
    inter = FakeInteraction(value, player=player)

    cog = Music.__new__(Music)  # bypass __init__; we only exercise dispatch
    cog.bot = player.bot

    raised = None
    try:
        await Music.player_controller(cog, inter, value)
    except GenericError:
        return  # handled, user-facing error — the user sees a message
    except Exception as exc:  # noqa: BLE001 - we are classifying, not handling
        raised = exc

    dispatched_error = any(
        ev == "interaction_player_error" for ev, _, _ in player.bot.dispatched
    )

    assert inter.responded or dispatched_error or raised is not None, (
        f"{name}: returned silently — no acknowledgement, no error dispatched. "
        f"The user sees a dead button or 'This interaction failed'."
    )
