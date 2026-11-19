"""
evaluate.py

Automatic evaluation.

Per example:
- fact_accuracy        share of key facts stated in the right role. A fact counts only if its
                       value appears in a sentence with a role cue (the opener's name next to
                       "open", the declarer's next to "contract", ...). The bid sequence fact
                       checks that the auction's bids and doubles are mentioned in order.
- meaning_recall       share of meaning facts explained (e.g. "West's 2H is Michaels"): a
                       sentence names the player and one of the accepted keywords. Real-data
                       meaning facts are annotated; synthetic ones come from the gold artificial
                       language.
- unsupported_bids     number of bids the output mentions that never occur in the record
                       (a hallucination check).
- fk_grade             Flesch-Kincaid grade level (lower is easier to read).
- chrf                 sentence-level chrF against the reference (sacrebleu).
- artificial_exact_match  share of gold artificial-language lines predicted exactly, where gold exists.

Per system, summarize() adds corpus BLEU and corpus chrF (sacrebleu) over examples with references.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

PLAYERS = ["North", "East", "South", "West"]
NUMBER_WORDS = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
                "8": "eight", "9": "nine", "10": "ten", "11": "eleven", "12": "twelve", "13": "thirteen"}
STRAIN_WORDS = {"C": ["club", "clubs"], "D": ["diamond", "diamonds"], "H": ["heart", "hearts"],
                "S": ["spade", "spades"], "NT": ["no-trump", "no trump", "notrump", "nt"]}
RANK_WORDS = {"A": "ace", "K": "king", "Q": "queen", "J": "jack", "T": "ten", "9": "nine", "8": "eight",
              "7": "seven", "6": "six", "5": "five", "4": "four", "3": "three", "2": "two"}
SUIT_LETTER = {"♠": "S", "♥": "H", "♦": "D", "♣": "C"}
SUIT_WORD = {"♠": "spades", "♥": "hearts", "♦": "diamonds", "♣": "clubs"}

# Fact key -> words that must share a sentence with the value. Empty list: value anywhere.
ROLE_CUES = {
    "opener": ["open", "start", "first"], "opening_bid": ["open", "start", "first"],
    "overcaller": ["overcall", "interven", "comes in", "cue"],
    "contract": ["contract"], "contract_doubled": ["contract"],
    "declarer": ["contract", "declarer"],
    "opening_leader": ["lead", "led"], "opening_lead": ["lead", "led"],
    "trick_1_winner": ["win", "won", "trick"], "trick_1_winning_card": ["win", "won", "trick"],
    "declarer_tricks": ["trick"],
    "double": ["doubl"], "redouble": ["redoubl"],
    "finesse_player": ["finesse"], "finesse_outcome": ["finesse"],
}
# A fact also holds when its value shares a sentence with its partner fact's value
# ("South bids 1H" states both the opener and the opening bid).
PAIRED_FACTS = {
    "opener": "opening_bid", "opening_bid": "opener", "overcaller": "overcall", "overcall": "overcaller",
    "responder": "response", "response": "responder", "opening_leader": "opening_lead",
    "opening_lead": "opening_leader", "trick_1_winner": "trick_1_winning_card",
    "trick_1_winning_card": "trick_1_winner",
}
VALUE_VARIANTS = {"success": ["works", "succeeds", "success", "wins"], "failure": ["loses", "fails", "failure"]}


def normalize_text(text: str) -> str:
    """Lower-case, ASCII hyphens, suit symbols after a level as letters (1♥ -> 1h)."""
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"([1-7])\s?([♠♥♦♣])", lambda m: m.group(1) + SUIT_LETTER[m.group(2)], text)
    text = re.sub(r"([♠♥♦♣])\s?([2-9TJQKA]|10)\b", lambda m: f"{RANK_WORDS.get(m.group(2), 'ten')} of {SUIT_WORD[m.group(1)]}", text)
    return re.sub(r"\s+", " ", text.lower()).strip()


def sentences(text: str) -> List[str]:
    return [s for s in re.split(r"(?<=[.!?;])\s+", normalize_text(text)) if s]


def bid_variants(bid: str) -> List[str]:
    level, strain = bid[0], bid[1:]
    out = [bid.lower(), f"{level} {strain.lower()}"]
    for word in STRAIN_WORDS[strain]:
        out += [f"{level} {word}", f"{NUMBER_WORDS[level]} {word}"]
    return out


def value_variants(key: str, value: str) -> List[str]:
    value = str(value)
    if value in VALUE_VARIANTS:
        return VALUE_VARIANTS[value]
    if re.fullmatch(r"[♠♥♦♣][2-9TJQKA]", value):
        rank = "10" if value[1] == "T" else value[1].lower()
        return [f"{RANK_WORDS[value[1]]} of {SUIT_WORD[value[0]]}", f"{rank}{SUIT_LETTER[value[0]].lower()}"]
    if re.fullmatch(r"[1-7](NT|C|D|H|S)", value):
        return bid_variants(value)
    if value.isdigit():
        return [value, NUMBER_WORDS.get(value, value)]
    return [value.lower()]


def contains_variant(sentence: str, variants: Iterable[str]) -> bool:
    return any(re.search(rf"(?<![a-z0-9]){re.escape(v)}(?![a-z0-9])", sentence) for v in variants)


def bid_sequence_in_order(output: str, sequence: str) -> bool:
    """Every bid, double and redouble of the auction is mentioned, in order."""
    text = normalize_text(output)
    position = 0
    for item in sequence.split():
        call = item.split(":")[1]
        if call == "PASS":
            continue
        if call == "DOUBLE":
            patterns = [r"(?<!re)doubl"]
        elif call == "REDOUBLE":
            patterns = [r"redoubl"]
        else:
            patterns = [rf"(?<![a-z0-9]){re.escape(v)}(?![a-z0-9])" for v in bid_variants(call)]
        matches = [m for p in patterns for m in [re.compile(p).search(text, position)] if m]
        if not matches:
            return False
        position = min(m.end() for m in matches)
    return True


def fact_accuracy(output: str, facts: Dict[str, str]) -> Optional[float]:
    if not facts:
        return None
    sents = sentences(output)
    correct = 0
    for key, value in facts.items():
        if key == "bid_sequence":
            correct += bid_sequence_in_order(output, value)
            continue
        variants = value_variants(key, value)
        cues = ROLE_CUES.get(key, [])
        pair = PAIRED_FACTS.get(key)
        pair_variants = value_variants(pair, facts[pair]) if pair in facts else []
        correct += any(
            contains_variant(s, variants)
            and (not cues or any(c in s for c in cues) or (pair_variants and contains_variant(s, pair_variants)))
            for s in sents
        )
    return correct / len(facts)


def meaning_facts_from_gold(gold_artificial: List[str]) -> Dict[str, List[str]]:
    """Meaning facts for the synthetic set, read off the gold artificial language."""
    facts: Dict[str, List[str]] = {}
    for line in gold_artificial:
        head, args = line.split("(", 1)
        args = [a.strip() for a in args[:-1].split(",")]
        if head == "OPEN" and args[1] == "1NT":
            facts[f"{args[0]} 1NT"] = ["15-17", "balanced"]
        elif head == "OPEN" and args[1] == "2NT":
            facts[f"{args[0]} 2NT"] = ["20-21", "balanced"]
        elif head == "OPEN" and args[1] == "2C":
            facts[f"{args[0]} 2C"] = ["strong", "artificial"]
        elif head == "RAISE_TO_GAME" or (head == "REBID" and args[1] in {"3NT", "4H", "4S", "5C", "5D"}):
            facts[f"{args[0]} {args[1]}"] = ["game"]
        elif head == "RESPOND" and args[2] == "waiting_response":
            facts[f"{args[0]} {args[1]}"] = ["waiting", "keeping the auction open", "relay", "negative"]
        elif head == "DOUBLE":
            facts[f"{args[0]} Double"] = [args[1]]
    return facts


def meaning_recall(output: str, meaning: Dict[str, List[str]]) -> Optional[float]:
    if not meaning:
        return None
    sents = sentences(output)
    hits = 0
    for label, keywords in meaning.items():
        player = label.split()[0].lower()
        hits += any(player in s and any(k.lower().replace("–", "-") in s for k in keywords) for s in sents)
    return hits / len(meaning)


def record_bids(raw: Dict[str, object]) -> set:
    found = set(re.findall(r"\b([1-7](?:NT|C|D|H|S))\b", str(raw.get("auction", "")) + " " + str(raw.get("contract", ""))))
    return {b.lower() for b in found}


CALL_CONTEXT = re.compile(
    r"(bid|bids|bidding|open|opens|opened|opening|overcall\w*|raise[sd]?|raising|respond\w*|rebid\w*|"
    r"jump\w*|cue-bid\w*|transfer\w*|correct\w*|contract(?: is| was| of)?|to|in|at|with an?)\s+$"
)


def unsupported_bids(output: str, raw: Dict[str, object]) -> int:
    """
    Bids mentioned in the output ('3H', '3♥', '3 hearts', 'three no-trump') that the record never
    contains. A mention counts only after a calling word ("bids", "opens", "raises to", "the
    contract is", ...), because '6♥' or 'two hearts' may describe a card or a hand instead.
    """
    text = normalize_text(output)
    words = {w: s for s, ws in STRAIN_WORDS.items() for w in ws}
    numbers = {v: k for k, v in NUMBER_WORDS.items() if int(k) <= 7}
    pattern = (
        r"(?<![a-z0-9])([1-7]|one|two|three|four|five|six|seven)"
        r"(?:\s?(nt|c|d|h|s)(?![a-z0-9])|[ -](no-trump|no trump|notrump|clubs?|diamonds?|hearts?|spades?)(?![a-z]))"
    )
    mentioned = set()
    for m in re.finditer(pattern, text):
        if m.group(2) and not m.group(1).isdigit():
            continue
        if CALL_CONTEXT.search(text[max(0, m.start() - 25):m.start()]):
            level = numbers.get(m.group(1), m.group(1))
            mentioned.add(level + (m.group(2) or words[m.group(3)].lower()))
    return len(mentioned - record_bids(raw))


def syllables(word: str) -> int:
    word = word.lower()
    count = len(re.findall(r"[aeiouy]+", word))
    if word.endswith("e") and not word.endswith(("le", "ee")) and count > 1:
        count -= 1
    return max(count, 1)


def fk_grade(text: str) -> Optional[float]:
    words = re.findall(r"[A-Za-z]+", text)
    n_sentences = max(len(re.findall(r"[.!?]+", text)), 1)
    if not words:
        return None
    return 0.39 * len(words) / n_sentences + 11.8 * sum(syllables(w) for w in words) / len(words) - 15.59


def exact_artificial_match(predicted: List[str], gold: List[str]) -> float:
    if not gold:
        return 0.0
    correct = sum(1 for p, g in zip(predicted, gold) if p == g)
    return correct / max(len(gold), 1)


def sentence_chrf(output: str, reference: str) -> Optional[float]:
    if not reference:
        return None
    import sacrebleu

    return sacrebleu.sentence_chrf(normalize_text(output), [normalize_text(reference)]).score


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

        meaning = example.get("meaning_facts") or meaning_facts_from_gold(example.get("gold_artificial", []))
        gold_al = example.get("gold_artificial")
        rows.append({
            "id": example["id"],
            "system": system_name,
            "fact_accuracy": fact_accuracy(english, example.get("facts", {})),
            "meaning_recall": meaning_recall(english, meaning),
            "unsupported_bids": unsupported_bids(english, example["raw"]),
            "fk_grade": fk_grade(english),
            "words": len(english.split()),
            "chrf": sentence_chrf(english, example.get("gold_english", "")),
            "artificial_exact_match": exact_artificial_match(artificial, gold_al) if artificial and gold_al else None,
            "output": english,
            "reference": example.get("gold_english", ""),
        })
    return rows


def average(rows: List[Dict], key: str) -> Optional[float]:
    values = [row[key] for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(values) / len(values)


METRICS = ["fact_accuracy", "meaning_recall", "unsupported_bids", "fk_grade", "words", "artificial_exact_match"]


def summarize(rows: List[Dict]) -> List[Dict]:
    import sacrebleu

    systems = list(dict.fromkeys(row["system"] for row in rows))
    summary = []
    for system in systems:
        system_rows = [row for row in rows if row["system"] == system]
        entry = {"system": system, "n": len(system_rows)}
        entry.update({key: average(system_rows, key) for key in METRICS})
        with_ref = [r for r in system_rows if r["reference"]]
        if with_ref:
            hyps = [normalize_text(r["output"]) for r in with_ref]
            refs = [[normalize_text(r["reference"]) for r in with_ref]]
            entry["bleu"] = sacrebleu.corpus_bleu(hyps, refs).score
            entry["chrf"] = sacrebleu.corpus_chrf(hyps, refs).score
        else:
            entry["bleu"] = entry["chrf"] = None
        summary.append(entry)
    return summary


def load_json(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))
