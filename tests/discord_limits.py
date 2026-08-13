# -*- coding: utf-8 -*-
"""Discord API payload limits, expressed as executable assertions.

Every limit here comes from Discord's documented maximums. A skin that
violates one produces an API rejection, which the user sees as the red
"interaction failed" text.
"""
from __future__ import annotations

EMBED_TOTAL = 6000
EMBED_DESCRIPTION = 4096
EMBED_TITLE = 256
EMBED_FIELDS = 25
EMBED_FIELD_NAME = 256
EMBED_FIELD_VALUE = 1024
EMBED_FOOTER = 2048
EMBED_AUTHOR = 256
MAX_ACTION_ROWS = 5
MAX_BUTTONS_PER_ROW = 5
MAX_SELECT_OPTIONS = 25
COMPONENT_LABEL = 80
CUSTOM_ID = 100
SELECT_DESCRIPTION = 100
SELECT_PLACEHOLDER = 150

_BUTTON = 2
_SELECT_TYPES = (3, 5, 6, 7, 8)


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _embed_length(embed: dict) -> int:
    total = 0
    for key in ("title", "description"):
        total += len(embed.get(key) or "")
    total += len(((embed.get("footer") or {}).get("text")) or "")
    total += len(((embed.get("author") or {}).get("name")) or "")
    for field in embed.get("fields") or ():
        total += len(field.get("name") or "") + len(field.get("value") or "")
    return total


def _validate_embeds(embeds: list, ctx: str) -> None:
    running = 0
    for i, embed in enumerate(embeds):
        where = f"{ctx} embed[{i}]"
        _check(len(embed.get("title") or "") <= EMBED_TITLE,
               f"{where}: title over {EMBED_TITLE}")
        _check(len(embed.get("description") or "") <= EMBED_DESCRIPTION,
               f"{where}: description over {EMBED_DESCRIPTION}")
        _check(len(((embed.get("footer") or {}).get("text")) or "") <= EMBED_FOOTER,
               f"{where}: footer over {EMBED_FOOTER}")
        _check(len(((embed.get("author") or {}).get("name")) or "") <= EMBED_AUTHOR,
               f"{where}: author over {EMBED_AUTHOR}")
        fields = embed.get("fields") or []
        _check(len(fields) <= EMBED_FIELDS, f"{where}: over {EMBED_FIELDS} fields")
        for j, field in enumerate(fields):
            _check(len(field.get("name") or "") <= EMBED_FIELD_NAME,
                   f"{where} field[{j}]: name over {EMBED_FIELD_NAME}")
            _check(len(field.get("value") or "") <= EMBED_FIELD_VALUE,
                   f"{where} field[{j}]: value over {EMBED_FIELD_VALUE}")
        running += _embed_length(embed)
    _check(running <= EMBED_TOTAL,
           f"{ctx}: embeds total {running} chars, over {EMBED_TOTAL}")


def _validate_components(rows: list, ctx: str) -> None:
    _check(len(rows) <= MAX_ACTION_ROWS,
           f"{ctx}: {len(rows)} action rows, over {MAX_ACTION_ROWS}")
    for i, row in enumerate(rows):
        children = row.get("components") or []
        buttons = [c for c in children if c.get("type") == _BUTTON]
        selects = [c for c in children if c.get("type") in _SELECT_TYPES]
        where = f"{ctx} row[{i}]"
        _check(len(buttons) <= MAX_BUTTONS_PER_ROW,
               f"{where}: {len(buttons)} buttons, over {MAX_BUTTONS_PER_ROW}")
        _check(not (selects and buttons),
               f"{where}: mixes a select with buttons in one action row")
        _check(len(selects) <= 1, f"{where}: more than one select in a row")
        for c in children:
            cid = c.get("custom_id")
            if cid is not None:
                _check(len(cid) <= CUSTOM_ID,
                       f"{where}: custom_id {len(cid)} chars, over {CUSTOM_ID}")
            label = c.get("label")
            if label:
                _check(len(label) <= COMPONENT_LABEL,
                       f"{where}: label over {COMPONENT_LABEL}")
            if c.get("type") in _SELECT_TYPES:
                opts = c.get("options") or []
                _check(len(opts) <= MAX_SELECT_OPTIONS,
                       f"{where}: {len(opts)} options, over {MAX_SELECT_OPTIONS}")
                _check(len(opts) >= 1, f"{where}: select has no options")
                ph = c.get("placeholder")
                if ph:
                    _check(len(ph) <= SELECT_PLACEHOLDER,
                           f"{where}: placeholder over {SELECT_PLACEHOLDER}")
                for k, opt in enumerate(opts):
                    _check(len(opt.get("label") or "") <= COMPONENT_LABEL,
                           f"{where} option[{k}]: label over {COMPONENT_LABEL}")
                    _check(len(opt.get("description") or "") <= SELECT_DESCRIPTION,
                           f"{where} option[{k}]: description over {SELECT_DESCRIPTION}")
                values = [o.get("value") for o in opts]
                _check(len(values) == len(set(values)),
                       f"{where}: duplicate option values")


def assert_payload_valid(payload: dict, context: str) -> None:
    """Raise AssertionError if ``payload`` would be rejected by Discord."""
    _validate_embeds(payload.get("embeds") or [], context)
    _validate_components(payload.get("components") or [], context)
