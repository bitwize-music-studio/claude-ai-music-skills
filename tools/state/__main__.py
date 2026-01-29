#!/usr/bin/env python3
"""Allow running as: python3 -m tools.state <command>"""

from tools.state.indexer import main
import sys

sys.exit(main() or 0)
