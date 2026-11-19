#!/usr/bin/env python3
"""
Build data/real_dev.json and data/real_test.json from BBO vugraph LIN files.

Usage:
    python scripts/build_real_dataset.py LIN_DIR

LIN_DIR holds files named <vugraph id>.lin, downloaded from
https://www.bridgebase.com/tools/vugraph_linfetch.php?id=<vugraph id>
(the ids used for the committed dataset are listed in data/real_sources.txt).

Steps:
1. Parse every board, keep it only if it is legal and its contract, declarer
   and trick count agree with the file's official result line.
2. Split by deal (both tables of a board go to the same split) with a fixed seed.
3. real_dev: the first 40 boards.
4. real_test: 40 boards whose auction pattern appears neither in the synthetic
   training set nor in real_dev, chosen to cover as many auction features as possible.

Player names, team names and commentary are never copied.
"""

from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bridge_translator.bridge_parser import parse_auction, parse_contract  # noqa: E402
from bridge_translator.hand_records import _lin_pairs, parse_lin  # noqa: E402
from bridge_translator.validate import partner, validate_record  # noqa: E402

DEV_SIZE = 40
TEST_SIZE = 40
SEED = 7


def official_result(pairs, board: str):
    """Look up (contract, declarer initial, tricks) for a board in the LIN `rs` line."""
    rs = next((v for k, v in pairs if k == "rs"), "").split(",")
    vg = next((v for k, v in pairs if k == "vg"), "").split(",")
    first = int(vg[3]) if len(vg) > 3 and vg[3].isdigit() else 1
    idx = (int(board[1:]) - first) * 2 + (0 if board[0] == "o" else 1)
    if not 0 <= idx < len(rs):
        return None
    m = re.fullmatch(r"([1-7])([NSHDC])([NESW])(x{0,2})([=+-]\d*)", rs[idx].strip(), flags=re.IGNORECASE)
    if not m:
        return None
    level, strain, declarer, doubled, outcome = m.groups()
    need = int(level) + 6
    tricks = need if outcome == "=" else need + int(outcome)
    contract = level + ("NT" if strain.upper() == "N" else strain.upper()) + doubled.upper()
    return contract, declarer.upper(), str(tricks)


def auction_pattern(auction: str) -> str:
    """Non-pass calls; the non-opening side's calls in parentheses, e.g. 1H-(1S)-2H-(X)."""
    calls = [e for e in parse_auction(auction) if e.type != "PASS"]
    if not calls:
        return ""
    opener = calls[0].args["player"]
    parts = []
    for e in calls:
        text = e.args.get("bid") or {"DOUBLE": "X", "REDOUBLE": "XX"}[e.type]
        parts.append(text if e.args["player"] in {opener, partner(opener)} else f"({text})")
    return "-".join(parts)


def features(raw) -> set:
    events = parse_auction(raw["auction"])
    bids = [e for e in events if e.type == "BID"]
    opener = bids[0].args["player"]
    opening = bids[0].args["bid"]
    seat = events.index(bids[0]) + 1
    found = set()
    if seat >= 3:
        found.add("seat_3_or_4")
    if opening in {"1NT", "2NT"}:
        found.add("notrump_opening")
    elif opening in {"2D", "2H", "2S"}:
        found.add("two_level_suit_opening")
    elif int(opening[0]) >= 3:
        found.add("high_level_opening")
    if any(e.args.get("alerted") for e in bids):
        found.add("alerted_call")
    if any(e.args["player"] not in {opener, partner(opener)} for e in bids):
        found.add("contested")
    if any(e.type == "DOUBLE" for e in events):
        found.add("double")
    if any(e.type == "REDOUBLE" for e in events):
        found.add("redouble")
    contract = parse_contract(raw["contract"])
    if int(contract.args["contract"][0]) >= 6:
        found.add("slam")
    if contract.args.get("doubled"):
        found.add("doubled_contract")
    if int(raw.get("result", 0)) < int(contract.args["contract"][0]) + 6:
        found.add("contract_failed")
    return found


def facts(raw) -> dict:
    events = parse_auction(raw["auction"])
    bids = [e for e in events if e.type == "BID"]
    opener = bids[0].args["player"]
    contract = parse_contract(raw["contract"])
    out = {"opener": opener, "opening_bid": bids[0].args["bid"]}
    overcall = next((e for e in bids if e.args["player"] not in {opener, partner(opener)}), None)
    if overcall:
        out["overcaller"] = overcall.args["player"]
        out["overcall"] = overcall.args["bid"]
    out["contract"] = contract.args["contract"]
    if contract.args.get("doubled"):
        out["contract_doubled"] = {"X": "doubled", "XX": "redoubled"}[contract.args["doubled"]]
    out["declarer"] = contract.args["declarer"]
    if raw.get("opening_lead"):
        leader, card = raw["opening_lead"].split()
        out["opening_leader"] = leader
        out["opening_lead"] = card
    if raw.get("result"):
        out["declarer_tricks"] = raw["result"]
    return out


def main(lin_dir: Path) -> None:
    boards = []
    rejected = 0
    for path in sorted(lin_dir.glob("*.lin")):
        text = path.read_text(encoding="latin-1")
        pairs = _lin_pairs(text)
        for raw in parse_lin(text):
            board = raw.pop("board")
            official = official_result(pairs, board)
            contract, declarer = raw["contract"].split(" by ")
            if official != (contract, declarer[0], raw.get("result")) or validate_record(raw):
                rejected += 1
                continue
            boards.append({"source": {"vugraph_id": path.stem, "board": board}, "raw": raw})

    by_deal = defaultdict(list)
    for b in boards:
        by_deal[(b["source"]["vugraph_id"], b["source"]["board"][1:])].append(b)
    deals = sorted(by_deal)
    random.Random(SEED).shuffle(deals)

    dev, rest = [], []
    for deal in deals:
        (dev if len(dev) < DEV_SIZE else rest).append(by_deal[deal])
    dev = [b for group in dev for b in group][:DEV_SIZE]

    train = json.loads((ROOT / "data" / "train.json").read_text(encoding="utf-8"))
    seen = {auction_pattern(e["raw"]["auction"]) for e in train} | {auction_pattern(b["raw"]["auction"]) for b in dev}

    # Greedy selection: one board per deal, prefer boards adding features not yet covered.
    candidates = []
    for group in rest:
        options = [b for b in group if auction_pattern(b["raw"]["auction"]) not in seen]
        if options:
            candidates.append(options)
    test, covered = [], defaultdict(int)
    while len(test) < TEST_SIZE and candidates:
        def gain(b):
            return sum(1.0 / (1 + covered[f]) for f in features(b["raw"]))
        best_group = max(candidates, key=lambda g: max(gain(b) for b in g))
        best = max(best_group, key=gain)
        candidates.remove(best_group)
        test.append(best)
        for f in features(best["raw"]):
            covered[f] += 1

    def to_examples(selected, prefix):
        out = []
        for i, b in enumerate(selected, 1):
            raw = b["raw"]
            out.append({
                "id": f"{prefix}{i:03d}",
                "raw": raw,
                "gold_english": "",
                "facts": facts(raw),
                "metadata": {
                    "source": b["source"],
                    "pattern": auction_pattern(raw["auction"]),
                    "features": sorted(features(raw)),
                },
            })
        return out

    for name, selected, prefix in [("real_dev", dev, "real_dev"), ("real_test", test, "real_test")]:
        path = ROOT / "data" / f"{name}.json"
        path.write_text(json.dumps(to_examples(selected, prefix), indent=2, ensure_ascii=False), encoding="utf-8")

    (ROOT / "data" / "real_sources.txt").write_text(
        "\n".join(sorted({b["source"]["vugraph_id"] for b in boards})) + "\n", encoding="utf-8"
    )
    print(f"kept {len(boards)} boards, rejected {rejected}; dev {len(dev)}, test {len(test)}")
    print("test feature coverage:", dict(sorted(covered.items())))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
