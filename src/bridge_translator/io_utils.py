"""
io_utils.py

Small input/output helpers.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List


def load_examples(split: str) -> List[Dict]:
    path = Path("data") / f"{split}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(obj, path: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def save_csv(rows: List[Dict], path: str) -> None:
    if not rows:
        return

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    fields = list(rows[0].keys())
    with p.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
