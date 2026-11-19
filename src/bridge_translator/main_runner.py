"""Programmatic runner for the Bridge Translator GitHub repository."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import json
import csv

from bridge_translator import llm
from bridge_translator.artificial_language import raw_to_artificial
from bridge_translator.baselines import generic_baseline, literal_baseline, raw_copy_baseline
from bridge_translator.error_analysis import build_error_rows, save_error_analysis
from bridge_translator.evaluate import evaluate_examples, summarize
from bridge_translator.generator import artificial_to_english


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
}


def llm_systems(examples: List[Dict], generate: bool) -> Dict:
    """LLM systems whose outputs are cached for every example (after generating them if asked)."""
    systems = {}
    for model in llm.MODELS:
        for name in llm.PROMPTS:
            if generate:
                llm.generate(model, name, examples)
            if all(llm.cached_output(model, name, e) is not None for e in examples):
                systems[f"{name}__{model}"] = lambda e, m=model, n=name: llm.cached_output(m, n, e)
    return systems


def fmt(value, digits=3):
    return "-" if value is None else f"{value:.{digits}f}"


def print_summary(split, summary_rows):
    print(f"\nEvaluation summary: {split}")
    header = f"{'system':34} {'facts':>6} {'meaning':>8} {'unsup.':>7} {'FK':>5} {'words':>6} {'BLEU':>6} {'chrF':>6} {'AL em':>6}"
    print(header)
    print("-" * len(header))
    for row in summary_rows:
        print(
            f"{row['system']:34} {fmt(row['fact_accuracy']):>6} {fmt(row['meaning_recall']):>8} "
            f"{fmt(row['unsupported_bids'], 2):>7} {fmt(row['fk_grade'], 1):>5} {fmt(row['words'], 0):>6} "
            f"{fmt(row['bleu'], 1):>6} {fmt(row['chrf'], 1):>6} {fmt(row['artificial_exact_match']):>6}"
        )


def run_all(split: str = "test", save_reports: bool = True, show_examples: bool = False, generate_llm: bool = False):
    examples = load_examples(split)
    systems = {**SYSTEMS, **llm_systems(examples, generate_llm)}

    all_rows = []
    for name, system in systems.items():
        all_rows.extend(evaluate_examples(examples, name, system))

    summary_rows = summarize(all_rows)
    print_summary(split, summary_rows)

    if save_reports:
        reports_dir = ROOT / "reports"
        save_json(summary_rows, reports_dir / f"{split}_summary.json")
        save_csv(all_rows, reports_dir / f"{split}_outputs.csv")
        error_rows = build_error_rows(all_rows)
        save_error_analysis(error_rows, str(reports_dir / f"{split}_error_analysis.csv"))

    return summary_rows
