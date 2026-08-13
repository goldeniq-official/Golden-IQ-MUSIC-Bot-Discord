# -*- coding: utf-8 -*-
"""Guards the environment assumptions the rest of the suite relies on.

On the reported Windows host the console codepage is cp1252, so printing an
emoji raises UnicodeEncodeError and kills startup output. ``main.py``
reconfigures stdio to UTF-8 before its first emoji print.

Note on why these tests use a subprocess: under pytest, ``sys.stdout`` is
pytest's own UTF-8 capture object, so asserting on ``sys.stdout.encoding``
in-process passes no matter what the real console does. That assertion would
be vacuous. These tests spawn a child with stdout on a pipe — which uses the
locale encoding, reproducing the real failure — and measure behavior.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SNAKE = "\U0001F40D"

RECONFIGURE_SNIPPET = """
import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
print("\\U0001F40D ok")
"""

NO_RECONFIGURE_SNIPPET = 'print("\\U0001F40D ok")'


def _run(code: str) -> subprocess.CompletedProcess:
    """Run ``code`` in a child with stdio on a pipe and no encoding override."""
    env = dict(os.environ)
    # Strip the override so the child falls back to the locale codepage,
    # which is the condition that breaks the real bot.
    env.pop("PYTHONIOENCODING", None)
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=PROJECT_ROOT,
    )


def test_python_version_is_3_14():
    assert sys.version_info[:2] == (3, 14), (
        f"venv holds cp314 wheels; got {sys.version_info[:3]}"
    )


def test_emoji_output_fails_without_reconfigure():
    """Control case: proves the guard below is testing something real.

    If this ever starts passing, the platform changed and the reconfigure
    block may no longer be load-bearing.
    """
    result = _run(NO_RECONFIGURE_SNIPPET)
    if result.returncode == 0:
        import pytest

        pytest.skip("this platform already defaults to a unicode-safe stdout")
    assert "UnicodeEncodeError" in result.stderr


def test_reconfigure_makes_emoji_output_safe():
    result = _run(RECONFIGURE_SNIPPET)
    assert result.returncode == 0, (
        f"reconfigure did not prevent the encode error:\n{result.stderr}"
    )
    assert SNAKE in result.stdout


def test_main_reconfigures_stdio_before_first_emoji_print():
    """The fix must run before main.py's first emoji output, not after."""
    source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")

    reconfigure_at = source.find("reconfigure(")
    assert reconfigure_at != -1, "main.py no longer reconfigures stdio to UTF-8"

    emoji_print = re.search(r"print\(.*[\U0001F300-\U0001FAFF]", source)
    assert emoji_print, "expected main.py to print an emoji at startup"
    assert reconfigure_at < emoji_print.start(), (
        "main.py prints an emoji before reconfiguring stdio — startup will "
        "crash on a cp1252 console"
    )


def test_core_modules_import():
    import config_loader  # noqa: F401
    import utils.client  # noqa: F401
    import utils.music.models  # noqa: F401
    import utils.music.ui  # noqa: F401
