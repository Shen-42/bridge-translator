"""
hand_records.py

Read real Bridge hand records into this project's raw record format.

Supported formats:
- LIN, the format BBO uses for vugraph archives and hand histories.
- PBN (Portable Bridge Notation), the standard interchange format.

Each board becomes a dict with the usual raw fields (auction, contract,
opening_lead, play) plus dealer, hands (PBN order spades.hearts.diamonds.clubs)
and result (tricks taken by declarer) when known. Only trick 1 is kept in
`play`, matching the rest of the dataset. Player names and commentary are
never copied.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .bridge_parser import PLAYERS, parse_auction
from .validate import card_beats, next_player, validate_auction

SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}
FULL_DECK = {s + r for s in "SHDC" for r in "AKQJT98765432"}
LIN_DEALERS = {"1": "South", "2": "West", "3": "North", "4": "East"}
LIN_HAND_ORDER = ["South", "West", "North", "East"]
PBN_SEATS = {"N": "North", "E": "East", "S": "South", "W": "West"}


def _call_text(call: str) -> Optional[str]:
    """Normalise a LIN/PBN call to the auction text used in raw records."""
    alerted = call.endswith("!")
    call = call.rstrip("!").strip().upper()
    if call in {"P", "PASS"}:
        text = "Pass"
    elif call in {"D", "X", "DBL"}:
        text = "Double"
    elif call in {"R", "XX", "RDBL"}:
        text = "Redouble"
    elif re.fullmatch(r"[1-7](N|NT|C|D|H|S)", call):
        text = call[0] + ("NT" if call[1] == "N" else call[1])
    else:
        return None
    return text + ("!" if alerted and text not in {"Pass", "Double", "Redouble"} else "")


def _hand_to_pbn(cards: List[str]) -> str:
    """['SA', 'SK', 'H2', ...] -> 'AK.2..' (spades.hearts.diamonds.clubs, high to low)."""
    order = "AKQJT98765432"
    return ".".join(
        "".join(sorted((c[1] for c in cards if c[0] == suit), key=order.index)) for suit in "SHDC"
    )


def _lin_hand(text: str) -> List[str]:
    cards, suit = [], None
    for ch in text.upper():
        if ch in "SHDC":
            suit = ch
        elif suit and ch in "AKQJT98765432":
            cards.append(suit + ch)
    return cards


def build_raw_record(
    dealer: str,
    hands: Dict[str, List[str]],
    calls: List[str],
    plays: List[str],
    claimed_tricks: Optional[int] = None,
) -> Optional[Dict[str, object]]:
    """
    Turn one board into a raw record. `calls` are auction calls from the dealer,
    `plays` are cards ('SA') in the order played. Returns None for boards
    that are passed out, unfinished, or not a full deal.
    """
    if sorted(c for h in hands.values() for c in h) != sorted(FULL_DECK):
        return None

    player = dealer
    parts = []
    for call in calls:
        text = _call_text(call)
        if text is None:
            return None
        parts.append(f"{player} {text}")
        player = next_player(player)
    auction = " - ".join(parts)

    errors, final = validate_auction(parse_auction(auction))
    if errors or final is None:
        return None

    declarer = final["declarer"]
    strain = final["contract"][1:]
    trump = None if strain == "NT" else SUIT_SYMBOLS[strain]

    raw: Dict[str, object] = {
        "dealer": dealer,
        "hands": {p: _hand_to_pbn(hands[p]) for p in PLAYERS},
        "auction": auction,
        "contract": f"{final['contract']}{final['doubled']} by {declarer}",
    }

    # Replay the cards to find trick winners and declarer's trick count.
    owner = {card: p for p, cards in hands.items() for card in cards}
    leader = next_player(declarer)
    tricks_won = 0
    for t in range(len(plays) // 4):
        trick = plays[4 * t: 4 * t + 4]
        who = [owner[c] for c in trick]
        expected = [leader, next_player(leader), next_player(next_player(leader)), next_player(next_player(next_player(leader)))]
        if who != expected:
            return None
        symbols = [SUIT_SYMBOLS[c[0]] + c[1] for c in trick]
        best = 0
        for i in range(1, 4):
            if card_beats(symbols[i], symbols[best], trump):
                best = i
        winner = who[best]
        if winner in {declarer, next_player(next_player(declarer))}:
            tricks_won += 1
        if t == 0:
            raw["opening_lead"] = f"{who[0]} {symbols[0]}"
            raw["play"] = (
                "Trick 1: " + " - ".join(f"{p} {c}" for p, c in zip(who, symbols)) + f"; Winner: {winner} {symbols[best]}"
            )
        leader = winner

    if claimed_tricks is not None:
        raw["result"] = str(claimed_tricks)
    elif len(plays) == 52:
        raw["result"] = str(tricks_won)
    return raw


def _lin_pairs(text: str) -> List[tuple]:
    tokens = text.replace("\n", "").replace("\r", "").split("|")
    return list(zip(tokens[0::2], tokens[1::2]))


def parse_lin(text: str) -> List[Dict[str, object]]:
    """Parse a LIN file (one or more boards). Each result has a `board` key ('o1', 'c1', ...)."""
    boards: List[Dict[str, object]] = []
    current: Optional[Dict[str, object]] = None

    def finish():
        if current and current.get("hands"):
            raw = build_raw_record(current["dealer"], current["hands"], current["calls"], current["plays"], current["claim"])
            if raw:
                raw["board"] = current["board"]
                boards.append(raw)

    for key, value in _lin_pairs(text):
        key = key.strip().lower()
        if key == "qx":
            finish()
            current = {"board": value.split(",")[0], "hands": None, "calls": [], "plays": [], "claim": None}
        elif current is None:
            continue
        elif key == "md" and value:
            dealer = LIN_DEALERS.get(value[0])
            hand_texts = value[1:].split(",")
            hands = {p: _lin_hand(h) for p, h in zip(LIN_HAND_ORDER, hand_texts)}
            missing = [p for p in LIN_HAND_ORDER if len(hands.get(p, [])) != 13]
            if len(missing) == 1:
                used = {c for p, h in hands.items() if p != missing[0] for c in h}
                hands[missing[0]] = sorted(FULL_DECK - used)
            current["dealer"], current["hands"] = dealer, hands
        elif key == "mb":
            current["calls"].append(value)
        elif key == "pc":
            card = value.strip().upper()
            current["plays"].append(card if len(card) == 2 else card[0] + "T")
        elif key == "mc" and value.strip().isdigit():
            current["claim"] = int(value)
    finish()
    return boards


def parse_pbn(text: str) -> List[Dict[str, object]]:
    """
    Parse a PBN file. Uses the Deal, Dealer, Auction, Play and Result tags.
    Only the first trick of the Play section is replayed; Result gives the trick count.
    """
    boards: List[Dict[str, object]] = []
    for game in re.split(r"\n\s*\n(?=\[)", text.strip()):
        tags = dict(re.findall(r'^\[(\w+)\s+"([^"]*)"\]', game, flags=re.MULTILINE))
        if "Deal" not in tags or "Dealer" not in tags:
            continue

        first, hand_text = tags["Deal"].split(":", 1)
        seat = PBN_SEATS[first.upper()]
        hands: Dict[str, List[str]] = {}
        for hand in hand_text.split():
            hands[seat] = [s + c for s, cards in zip("SHDC", hand.split(".")) for c in cards.upper()]
            seat = next_player(seat)

        def section(name: str) -> List[str]:
            m = re.search(rf'^\[{name}\s+"[^"]*"\]\s*\n(.*?)(?=^\[|\Z)', game, flags=re.MULTILINE | re.DOTALL)
            if not m:
                return []
            body = re.sub(r"\{[^}]*\}|;[^\n]*", " ", m.group(1))
            return [t for t in body.split() if not re.fullmatch(r"=\d+=|\$\d+|\*", t)]

        calls = section("Auction")
        if calls and calls[-1].upper() == "AP":
            calls = calls[:-1] + ["Pass"] * 3

        play_tokens = [t for t in section("Play") if t != "-"]
        result = int(tags["Result"]) if tags.get("Result", "").isdigit() else None
        raw = build_raw_record(PBN_SEATS[tags["Dealer"].upper()], hands, calls, play_tokens[:4], result)
        if raw:
            raw["board"] = tags.get("Board", "")
            boards.append(raw)
    return boards
