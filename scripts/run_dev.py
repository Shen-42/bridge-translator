#!/usr/bin/env python3
"""Run all Bridge Translator systems on the synthetic and real development sets.

Pass --llm to generate missing Qwen outputs through a local Ollama server; without it,
LLM systems are scored from the cached outputs in reports/llm_outputs/ when complete.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bridge_translator.main_runner import run_all

if __name__ == "__main__":
    for split in ["dev", "real_dev"]:
        run_all(split=split, save_reports=True, generate_llm="--llm" in sys.argv)
