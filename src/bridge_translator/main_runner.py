
"""Programmatic runner for the Bridge Translator GitHub repository."""

from __future__ import annotations

from pathlib import Path
from typing import Dict
import json
import csv

from bridge_translator.artificial_language import raw_to_artificial
from bridge_translator.baselines import generic_baseline, literal_baseline, raw_copy_baseline
from bridge_translator.error_analysis import build_error_rows, save_error_analysis
from bridge_translator.evaluate import evaluate_examples, summarize
from bridge_translator.generator import artificial_to_english
from bridge_translator.model_generators import artificial_model_system, direct_raw_model_system


ROOT = Path(__file__).resolve().parents[2]


def load_examples(split: str):
    path = ROOT / "data" / f"{split}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def save_csv(rows, path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def template_beginner_system(example: Dict) -> Dict:
    artificial = raw_to_artificial(example["raw"])
    return {
        "artificial_language": artificial,
        "english": artificial_to_english(artificial, style="beginner"),
    }


def template_expert_system(example: Dict) -> Dict:
    artificial = raw_to_artificial(example["raw"])
    return {
        "artificial_language": artificial,
        "english": artificial_to_english(artificial, style="expert"),
    }


def literal_system(example: Dict) -> str:
    return literal_baseline(example["raw"])


def generic_system(example: Dict) -> str:
    return generic_baseline(example["raw"])


def raw_copy_system(example: Dict) -> str:
    return raw_copy_baseline(example["raw"])


SYSTEMS = {
    "generic_baseline": generic_system,
    "literal_baseline": literal_system,
    "raw_copy_baseline": raw_copy_system,
    "template_beginner": template_beginner_system,
    "template_expert": template_expert_system,
    "model_from_artificial_simulated": artificial_model_system,
    "direct_raw_model_simulated": direct_raw_model_system,
}


def print_summary(summary_rows):
    print("Evaluation summary")
    print("==================")
    for row in summary_rows:
        print(f"\nSystem: {row['system']}")
        print(f"  n: {row['n']}")
        print(f"  factual preservation: {row['fact_preservation']:.3f}")
        print(f"  bridge meaning: {row['bridge_meaning']:.3f}")
        print(f"  beginner readability: {row['beginner_readability']:.3f}")
        print(f"  reconstructability: {row['reconstructability']:.3f}")
        print(f"  BLEU-like: {row['bleu_like']:.3f}")
        print(f"  ROUGE-L-like: {row['rouge_l_like']:.3f}")
        if row["artificial_exact_match"] is not None:
            print(f"  artificial exact match: {row['artificial_exact_match']:.3f}")


def run_all(split: str = "test", save_reports: bool = True, show_examples: bool = False):
    examples = load_examples(split)

    all_rows = []
    for name, system in SYSTEMS.items():
        all_rows.extend(evaluate_examples(examples, name, system))

    summary_rows = summarize(all_rows)
    print_summary(summary_rows)

    if save_reports:
        reports_dir = ROOT / "reports"
        save_json(summary_rows, reports_dir / f"{split}_summary.json")
        save_csv(all_rows, reports_dir / f"{split}_outputs.csv")
        error_rows = build_error_rows(all_rows)
        save_error_analysis(error_rows, str(reports_dir / f"{split}_error_analysis.csv"))

    return summary_rows
