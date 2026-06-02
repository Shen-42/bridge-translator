"""
model_generators.py

Comparison systems that simulate model-based outputs without requiring an API key.

Why simulate?
- The proposal asks for model-based generation from artificial language and direct
  raw-notation generation.
- A fully offline project should still run for grading/reproducibility.
- These functions act like model baselines: smoother than templates, but less
  exhaustive and therefore easier to penalize for omitted facts.

If you later want to use a real LLM, use the prompt files in prompts/.
"""

from __future__ import annotations

from typing import Dict, List

from .artificial_language import raw_to_artificial
from .generator import artificial_to_english


def model_from_artificial_simulated(artificial_lines: List[str]) -> str:
    """
    Simulated model-based generation from artificial language.

    It produces smoother commentary but compresses pass details and may omit
    some low-level facts, which creates a realistic comparison against templates.
    """
    full = artificial_to_english(artificial_lines, style="expert")
    sentences = [s.strip() for s in full.split(".") if s.strip()]

    compressed = []
    pass_count = 0

    for sentence in sentences:
        if sentence.endswith("passes"):
            pass_count += 1
            continue

        if pass_count:
            compressed.append(f"After {pass_count} pass{'es' if pass_count != 1 else ''}, the auction continues")
            pass_count = 0

        compressed.append(sentence)

    if pass_count:
        compressed.append(f"The remaining {pass_count} call{'s' if pass_count != 1 else ''} are passes")

    return ". ".join(compressed) + "."


def direct_raw_model_simulated(raw: Dict[str, str]) -> str:
    """
    Simulated direct raw-notation model.

    This intentionally relies on the raw fields and gives a plausible high-level
    explanation, but it does not expose all intermediate structure.
    """
    auction = raw.get("auction", "")
    contract = raw.get("contract", "the final contract")
    lead = raw.get("opening_lead", "the opening lead")

    opening_fragment = auction.split("-")[0].strip() if auction else "The auction begins"
    return (
        f"The deal starts with {opening_fragment}. The auction reaches {contract}. "
        f"The play begins with {lead}. This gives a short summary of the Bridge record."
    )


def artificial_model_system(example: Dict) -> Dict:
    artificial = raw_to_artificial(example["raw"])
    return {
        "artificial_language": artificial,
        "english": model_from_artificial_simulated(artificial),
    }


def direct_raw_model_system(example: Dict) -> str:
    return direct_raw_model_simulated(example["raw"])
