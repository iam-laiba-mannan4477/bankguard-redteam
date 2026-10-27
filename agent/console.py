"""Console helpers for scripts that print model output."""
import sys


def use_utf8_stdout():
    """Windows consoles default to cp1252; model text (e.g. U+2011) would crash print()."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
