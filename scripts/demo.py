#!/usr/bin/env python3
"""Run the Bridge Translator pipeline on examples/sample_input.json."""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bridge_translator.artificial_language import raw_to_artificial
from bridge_translator.generator import artificial_to_english

if __name__ == "__main__":
    raw = json.loads((ROOT / "examples" / "sample_input.json").read_text(encoding="utf-8"))
    artificial = raw_to_artificial(raw)
    english = artificial_to_english(artificial, style="beginner")

    print("Artificial language:")
    for line in artificial:
        print(line)

    print("\nEnglish:")
    print(english)
