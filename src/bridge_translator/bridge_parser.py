"""
bridge_parser.py

Rule-based parser for compact Bridge records.

Supported:
- Auctions with bids, passes, doubles, redoubles
- Final contracts
- Opening leads
- Simple trick-by-trick play records
- Finesse notes

The parser is intentionally transparent because this project studies whether an
explicit controlled representation improves Bridge-to-English generation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional


PLAYERS = ["North", "East", "South", "West"]

SUIT_SYMBOL_TO_LETTER = {"♣": "C", "♦": "D", "♥": "H", "♠": "S"}
SUIT_LETTER_TO_SYMBOL = {"C": "♣", "D": "♦", "H": "♥", "S": "♠"}

BID_PATTERN = r"[1-7](?:NT|C|D|H|S|♣|♦|♥|♠)"
PLAYER_PATTERN = r"(?:North|East|South|West)"
CARD_PATTERN = r"(?:[♣♦♥♠CDHS][2-9TJQKA]|[2-9TJQKA][♣♦♥♠CDHS])"


@dataclass(frozen=True)
class Event:
    type: str
    args: Dict[str, str]


def normalize_bid(bid: str) -> str:
    bid = bid.strip().upper()
    for symbol, letter in SUIT_SYMBOL_TO_LETTER.items():
        bid = bid.replace(symbol, letter)
    return bid


def normalize_card(card: str) -> str:
    card = card.strip().upper()
    if len(card) != 2:
        return card

    a, b = card[0], card[1]

    if a in SUIT_SYMBOL_TO_LETTER:
        return a + b
    if a in SUIT_LETTER_TO_SYMBOL:
        return SUIT_LETTER_TO_SYMBOL[a] + b
    if b in SUIT_SYMBOL_TO_LETTER:
        return b + a
    if b in SUIT_LETTER_TO_SYMBOL:
        return SUIT_LETTER_TO_SYMBOL[b] + a
    return card


def parse_auction(auction_text: str) -> List[Event]:
    if not auction_text:
        return []

    events: List[Event] = []
    parts = [p.strip() for p in auction_text.split("-")]

    for part in parts:
        if not part:
            continue

        tokens = part.split()
        if len(tokens) < 2:
            continue

        player, action = tokens[0], tokens[1]
        if player not in PLAYERS:
            continue

        action_upper = action.upper()

        if action_upper in {"PASS", "P"}:
            events.append(Event("PASS", {"player": player}))
        elif action_upper in {"DOUBLE", "X", "DBL"}:
            events.append(Event("DOUBLE", {"player": player}))
        elif action_upper in {"REDOUBLE", "XX", "RDBL"}:
            events.append(Event("REDOUBLE", {"player": player}))
        elif re.fullmatch(BID_PATTERN, action_upper):
            events.append(Event("BID", {"player": player, "bid": normalize_bid(action_upper)}))
        else:
            events.append(Event("UNKNOWN_CALL", {"player": player, "action": action}))

    return events


def parse_contract(contract_text: str) -> Optional[Event]:
    if not contract_text:
        return None

    pattern = rf"({BID_PATTERN})\s+by\s+({PLAYER_PATTERN})"
    match = re.search(pattern, contract_text, flags=re.IGNORECASE)

    if not match:
        return None

    return Event(
        "CONTRACT",
        {
            "contract": normalize_bid(match.group(1)),
            "declarer": match.group(2),
        },
    )


def parse_opening_lead(lead_text: str) -> Optional[Event]:
    if not lead_text:
        return None

    pattern = rf"({PLAYER_PATTERN})\s+({CARD_PATTERN})"
    match = re.search(pattern, lead_text, flags=re.IGNORECASE)

    if not match:
        return None

    return Event(
        "LEAD",
        {
            "player": match.group(1),
            "card": normalize_card(match.group(2)),
        },
    )


def parse_play(play_text: str) -> List[Event]:
    """
    Parse play records like:
        Trick 1: West ♠4 - North ♠A - East ♠7 - South ♠2; Winner: North ♠A

    Multiple tricks can be separated with "|".
    """
    if not play_text:
        return []

    events: List[Event] = []
    tricks = [t.strip() for t in play_text.split("|") if t.strip()]

    for trick in tricks:
        trick_match = re.search(r"Trick\s+(\d+)\s*:\s*(.*?)(?:;\s*Winner:\s*(.*))?$", trick, flags=re.IGNORECASE)
        if not trick_match:
            continue

        trick_number = trick_match.group(1)
        play_part = trick_match.group(2).strip()
        winner_part = trick_match.group(3)

        play_items = [p.strip() for p in play_part.split("-") if p.strip()]
        for item in play_items:
            m = re.search(rf"({PLAYER_PATTERN})\s+({CARD_PATTERN})", item, flags=re.IGNORECASE)
            if m:
                events.append(
                    Event(
                        "PLAY",
                        {
                            "player": m.group(1),
                            "card": normalize_card(m.group(2)),
                            "trick_number": trick_number,
                        },
                    )
                )

        if winner_part:
            m = re.search(rf"({PLAYER_PATTERN})\s+({CARD_PATTERN})", winner_part, flags=re.IGNORECASE)
            if m:
                events.append(
                    Event(
                        "WIN_TRICK",
                        {
                            "player": m.group(1),
                            "card": normalize_card(m.group(2)),
                            "trick_number": trick_number,
                        },
                    )
                )

    return events


def parse_finesse_note(note_text: str) -> Optional[Event]:
    """
    Parse notes like:
        Finesse: North in ♠ against queen; success
    """
    if not note_text or "finesse" not in note_text.lower():
        return None

    pattern = rf"Finesse:\s*({PLAYER_PATTERN})\s+in\s+([♣♦♥♠CDHS])\s+against\s+([A-Za-z]+);\s*(success|failure)"
    match = re.search(pattern, note_text, flags=re.IGNORECASE)

    if not match:
        return None

    suit = normalize_card(match.group(2) + "2")[0]

    return Event(
        "FINESSE_ATTEMPT",
        {
            "player": match.group(1),
            "suit": suit,
            "target": match.group(3).lower(),
            "outcome": match.group(4).lower(),
        },
    )


def parse_raw_record(raw: Dict[str, str]) -> List[Event]:
    events: List[Event] = []

    events.extend(parse_auction(raw.get("auction", "")))

    contract = parse_contract(raw.get("contract", ""))
    lead = parse_opening_lead(raw.get("opening_lead", ""))
    play_events = parse_play(raw.get("play", ""))
    finesse = parse_finesse_note(raw.get("note", ""))

    if contract:
        events.append(contract)
    if lead:
        events.append(lead)

    events.extend(play_events)

    if finesse:
        events.append(finesse)

    return events
