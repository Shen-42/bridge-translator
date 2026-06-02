"""
baselines.py

Baseline systems for comparison.
"""

from __future__ import annotations

from typing import Dict

from .bridge_parser import parse_auction


def literal_baseline(raw: Dict[str, str]) -> str:
    events = parse_auction(raw.get("auction", ""))
    sentences = []

    for event in events:
        if event.type == "PASS":
            sentences.append(f"{event.args['player']} passes.")
        elif event.type == "DOUBLE":
            sentences.append(f"{event.args['player']} doubles.")
        elif event.type == "REDOUBLE":
            sentences.append(f"{event.args['player']} redoubles.")
        elif event.type == "BID":
            sentences.append(f"{event.args['player']} bids {event.args['bid']}.")
        else:
            sentences.append(f"{event.args.get('player', 'A player')} makes an unknown call.")

    if raw.get("contract"):
        sentences.append(f"The contract is {raw['contract']}.")

    if raw.get("opening_lead"):
        sentences.append(f"The opening lead is {raw['opening_lead']}.")

    if raw.get("play"):
        sentences.append(f"The play record is {raw['play']}.")

    return " ".join(sentences)


def generic_baseline(raw: Dict[str, str]) -> str:
    return "The players complete the auction and reach a final contract."


def raw_copy_baseline(raw: Dict[str, str]) -> str:
    parts = []
    for key in ["auction", "contract", "opening_lead", "play", "note"]:
        if raw.get(key):
            parts.append(f"{key}: {raw[key]}")
    return " ".join(parts)
