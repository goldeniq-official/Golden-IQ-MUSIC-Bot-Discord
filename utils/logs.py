# -*- coding: utf-8 -*-
"""Rotating file logging and short Error IDs.

The bot's bare ``except:`` handlers made failures unreportable: users saw a
generic red embed carrying nothing actionable, so "it broke" was all the
owner could relay. Every recorded error now gets a short ID that is shown to
the user and resolves here to a full traceback with context.

IDs deliberately avoid I, O, 0 and 1 — people read them off a screen and
type them back.
"""
from __future__ import annotations

import logging
import os
import secrets
import traceback
from logging.handlers import RotatingFileHandler
from typing import Optional

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no look-alikes (I/O/0/1)
_MAX_CACHE = 500

_logger = logging.getLogger("goldeniq")
_errors: dict[str, str] = {}
_order: list[str] = []


def _new_id() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(8))


def setup_logging(log_dir: str = ".logs") -> None:
    """Install a rotating file handler. Safe to call more than once."""
    os.makedirs(log_dir, exist_ok=True)

    for handler in list(_logger.handlers):
        _logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    handler = RotatingFileHandler(
        os.path.join(log_dir, "bot.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False

    _errors.clear()
    _order.clear()


def record_error(exc: BaseException, **context) -> str:
    """Store ``exc`` with context and return a short ID to show the user."""
    error_id = _new_id()
    while error_id in _errors:
        error_id = _new_id()

    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    ctx = "\n".join(f"  {k}: {v}" for k, v in context.items())
    entry = f"Error ID: {error_id}\nContext:\n{ctx or '  (none)'}\n\n{tb}"

    _errors[error_id] = entry
    _order.append(error_id)
    while len(_order) > _MAX_CACHE:
        _errors.pop(_order.pop(0), None)

    _logger.error(entry)
    return error_id


def lookup_error(error_id: str) -> Optional[str]:
    """Return the stored traceback for ``error_id``, or None if unknown."""
    if not error_id:
        return None
    return _errors.get(error_id.strip().upper())
