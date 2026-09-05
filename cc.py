#!/usr/bin/env python3
"""Ponto de entrada. Use: python cc.py --help"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ccrun.cli import main

if __name__ == "__main__":
    sys.exit(main())
