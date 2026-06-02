"""
error_analysis.py

Qualitative error analysis support.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List


ERROR_TYPES = [
    "player_role_error",
    "bid_sequence_error",
    "card_error",
    "overgeneralization_error",
    "hallucinated_strategy_error",
    "readability_error",
    "artificial_language_parsing_error",
    "template_coverage_error",
]


def classify_error(row: Dict) -> str:
    """
    Simple automatic helper. Final paper should still inspect examples manually.
    """
    output = row.get("output", "").lower()

    if row.get("fact_preservation", 1.0) < 0.4:
        return "overgeneralization_error"

    if row.get("artificial_exact_match") is not None and row.get("artificial_exact_match") < 0.8:
        return "artificial_language_parsing_error"

    if row.get("beginner_readability", 5.0) < 3.5:
        return "readability_error"

    if "unknown" in output:
        return "template_coverage_error"

    return ""


def build_error_rows(evaluation_rows: List[Dict]) -> List[Dict]:
    rows = []
    for row in evaluation_rows:
        error_type = classify_error(row)
        if not error_type:
            continue
        rows.append({
            "example_id": row["id"],
            "system": row["system"],
            "error_type": error_type,
            "explanation": f"Automatic flag based on scores. Output: {row['output'][:200]}",
        })
    return rows


def save_error_analysis(rows: List[Dict], path: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["example_id", "system", "error_type", "explanation"])
        writer.writeheader()
        writer.writerows(rows)
