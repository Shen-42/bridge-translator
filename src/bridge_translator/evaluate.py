"""
evaluate.py

Automatic evaluation utilities.

These scores are not meant to replace human evaluation. They support the paper's
rubric by producing consistent, inspectable approximations:
- Fact preservation
- Artificial-language exact match
- Reconstructability approximation
- BLEU-like n-gram precision
- ROUGE-L-like longest-common-subsequence recall
- Readability heuristic
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional


def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("–", "-")
    text = text.replace("♠", " spade ")
    text = text.replace("♥", " heart ")
    text = text.replace("♦", " diamond ")
    text = text.replace("♣", " club ")
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> List[str]:
    return normalize_text(text).split()


def fact_value_variants(value: str) -> List[str]:
    value = str(value)
    variants = [value, value.replace("♠", "S").replace("♥", "H").replace("♦", "D").replace("♣", "C")]
    card_match = re.fullmatch(r"([♠♥♦♣])([2-9TJQKA])", value)
    if card_match:
        suit, rank = card_match.groups()
        suits = {"♠": "spades", "♥": "hearts", "♦": "diamonds", "♣": "clubs"}
        ranks = {"A": "ace", "K": "king", "Q": "queen", "J": "jack", "T": "ten",
                 "9": "nine", "8": "eight", "7": "seven", "6": "six", "5": "five",
                 "4": "four", "3": "three", "2": "two"}
        variants.append(f"{ranks.get(rank, rank)} of {suits[suit]}")
        variants.append(f"{suits[suit]} {ranks.get(rank, rank)}")
    return variants


def fact_preservation_score(output_text: str, facts: Dict[str, str]) -> float:
    if not facts:
        return 0.0

    output = normalize_text(output_text)
    correct = 0

    for value in facts.values():
        variants = [normalize_text(v) for v in fact_value_variants(value)]
        if any(v and v in output for v in variants):
            correct += 1

    return correct / len(facts)


def reconstructability_score(output_text: str, facts: Dict[str, str]) -> float:
    """
    Approximation of reconstructability:
    how many key fact values can be recovered by simple matching.
    """
    return fact_preservation_score(output_text, facts)


def exact_artificial_match(predicted: List[str], gold: List[str]) -> float:
    if not gold:
        return 0.0
    correct = sum(1 for p, g in zip(predicted, gold) if p == g)
    return correct / max(len(gold), 1)


def ngrams(tokens: List[str], n: int) -> Counter:
    return Counter(tuple(tokens[i:i+n]) for i in range(0, max(len(tokens)-n+1, 0)))


def bleu_like(candidate: str, reference: str, max_n: int = 4) -> float:
    cand = tokenize(candidate)
    ref = tokenize(reference)
    if not cand or not ref:
        return 0.0

    precisions = []
    for n in range(1, max_n+1):
        cand_ngrams = ngrams(cand, n)
        ref_ngrams = ngrams(ref, n)
        if not cand_ngrams:
            precisions.append(1e-9)
            continue
        overlap = sum(min(count, ref_ngrams[gram]) for gram, count in cand_ngrams.items())
        precisions.append(max(overlap / sum(cand_ngrams.values()), 1e-9))

    brevity = 1.0 if len(cand) > len(ref) else math.exp(1 - len(ref) / max(len(cand), 1))
    return brevity * math.exp(sum(math.log(p) for p in precisions) / max_n)


def lcs_length(a: List[str], b: List[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        curr = [0]
        for j, y in enumerate(b, 1):
            curr.append(prev[j-1] + 1 if x == y else max(prev[j], curr[-1]))
        prev = curr
    return prev[-1]


def rouge_l_like(candidate: str, reference: str) -> float:
    cand = tokenize(candidate)
    ref = tokenize(reference)
    if not cand or not ref:
        return 0.0
    return lcs_length(cand, ref) / len(ref)


def readability_heuristic(output_text: str) -> float:
    """
    1-5 heuristic based on sentence length and unexplained jargon.
    Higher means more beginner-readable.
    """
    sentences = [s.strip() for s in re.split(r"[.!?]+", output_text) if s.strip()]
    if not sentences:
        return 1.0
    words = tokenize(output_text)
    avg_len = len(words) / len(sentences)
    jargon = ["finesse", "redouble", "declarer", "dummy", "strain", "notrump"]
    jargon_count = sum(1 for w in words if w in jargon)
    score = 5.0
    if avg_len > 24:
        score -= 0.75
    if avg_len > 32:
        score -= 0.75
    score -= min(jargon_count * 0.2, 1.0)
    return max(1.0, min(5.0, score))


def bridge_meaning_heuristic(output_text: str, facts: Dict[str, str]) -> float:
    """
    1-5 proxy: rewards factual coverage plus explanatory phrases.
    """
    fact = fact_preservation_score(output_text, facts)
    explanation_terms = ["showing", "balanced", "game-level", "contract", "opens", "raises", "finesse", "penalty"]
    term_hits = sum(1 for term in explanation_terms if term in output_text.lower())
    return max(1.0, min(5.0, 1.0 + 2.5 * fact + 0.3 * term_hits))


def evaluate_examples(examples: List[Dict], system_name: str, generate_function: Callable[[Dict], object]) -> List[Dict]:
    rows = []

    for example in examples:
        result = generate_function(example)
        if isinstance(result, dict):
            english = result["english"]
            artificial = result.get("artificial_language", [])
        else:
            english = str(result)
            artificial = []

        rows.append({
            "id": example["id"],
            "system": system_name,
            "fact_preservation": fact_preservation_score(english, example.get("facts", {})),
            "bridge_meaning": bridge_meaning_heuristic(english, example.get("facts", {})),
            "beginner_readability": readability_heuristic(english),
            "reconstructability": reconstructability_score(english, example.get("facts", {})),
            "bleu_like": bleu_like(english, example.get("gold_english", "")),
            "rouge_l_like": rouge_l_like(english, example.get("gold_english", "")),
            "artificial_exact_match": exact_artificial_match(artificial, example.get("gold_artificial", [])) if artificial else None,
            "output": english,
        })

    return rows


def average(rows: List[Dict], key: str) -> Optional[float]:
    values = [row[key] for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(values) / len(values)


def summarize(rows: List[Dict]) -> List[Dict]:
    systems = sorted(set(row["system"] for row in rows))
    summary = []
    for system in systems:
        system_rows = [row for row in rows if row["system"] == system]
        summary.append({
            "system": system,
            "n": len(system_rows),
            "fact_preservation": average(system_rows, "fact_preservation"),
            "bridge_meaning": average(system_rows, "bridge_meaning"),
            "beginner_readability": average(system_rows, "beginner_readability"),
            "reconstructability": average(system_rows, "reconstructability"),
            "bleu_like": average(system_rows, "bleu_like"),
            "rouge_l_like": average(system_rows, "rouge_l_like"),
            "artificial_exact_match": average(system_rows, "artificial_exact_match"),
        })
    return summary


def load_json(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))
