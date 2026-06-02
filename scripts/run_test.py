#!/usr/bin/env python3
"""Run all Bridge Translator systems on the test set."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bridge_translator.main_runner import run_all

if __name__ == "__main__":
    run_all(split="test", save_reports=True, show_examples=False)
