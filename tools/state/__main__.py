#!/usr/bin/env python3
"""Allow running as: python3 -m tools.state <command>"""

import sys

from tools.state.indexer import main

sys.exit(main() or 0)
