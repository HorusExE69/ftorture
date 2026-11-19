#!/usr/bin/env python3
"""Run ftorture directly from a checkout, without installation."""
import sys

if sys.version_info < (3, 10):
    raise SystemExit("ftorture requires Python 3.10 or newer")

from ftorture.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
