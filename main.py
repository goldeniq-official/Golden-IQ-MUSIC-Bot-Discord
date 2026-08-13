# -*- coding: utf-8 -*-
# Windows consoles default to cp1252; emoji in logs raise UnicodeEncodeError.
# This must run before the first emoji print below.
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from platform import python_version

from utils.client import BotPool

print(f"🐍 - Python version: {python_version()}")

pool = BotPool()

pool.setup()
