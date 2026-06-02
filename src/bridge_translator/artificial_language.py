"""
artificial_language.py

Maps parsed Bridge events into the controlled artificial Bridge language.
"""

from __future__ import annotations

from typing import Dict, List

from .bridge_parser import Event, parse_raw_record


GAME_CONTRACTS = {"3NT", "4H", "4S", "5C", "5D"}


def opening_interpretation(bid: str) -> str:
    if bid == "1NT":
        return "balanced, 15-17_HCP"
    if bid == "2NT":
        return "balanced, 20-21_HCP"
    if bid == "2C":
        return "strong_artificial, very_strong_hand"
    if bid in {"1C", "1D", "1H", "1S"}:
        return "suit_opening, opening_strength"
    return "unknown_shape, unknown_strength"


def response_meaning(bid: str) -> str:
    if bid in GAME_CONTRACTS:
        return "game_raise"
    if bid == "2D":
        return "waiting_response"
    if bid.startswith("2"):
        return "constructive_response"
    return "response"


def event_to_artificial(event: Event, auction_call_index: int = 0, bid_index: int = 0) -> str:
    if event.type == "PASS":
        return f"PASS({event.args['player']})"

    if event.type == "DOUBLE":
        return f"DOUBLE({event.args['player']})"

    if event.type == "REDOUBLE":
        return f"REDOUBLE({event.args['player']})"

    if event.type == "BID":
        player = event.args["player"]
        bid = event.args["bid"]

        if bid_index == 0:
            return f"OPEN({player}, {bid}, {opening_interpretation(bid)})"

        if bid in GAME_CONTRACTS:
            return f"RAISE_TO_GAME({player}, {bid})"

        return f"RESPOND({player}, {bid}, {response_meaning(bid)})"

    if event.type == "CONTRACT":
        return f"CONTRACT({event.args['contract']}, declarer={event.args['declarer']})"

    if event.type == "LEAD":
        return f"LEAD({event.args['player']}, {event.args['card']})"

    if event.type == "PLAY":
        return f"PLAY({event.args['player']}, {event.args['card']}, trick_number={event.args['trick_number']})"

    if event.type == "WIN_TRICK":
        return f"WIN_TRICK({event.args['player']}, trick_number={event.args['trick_number']}, card={event.args['card']})"

    if event.type == "FINESSE_ATTEMPT":
        return (
            f"FINESSE_ATTEMPT({event.args['player']}, suit={event.args['suit']}, "
            f"target={event.args['target']}, outcome={event.args['outcome']})"
        )

    if event.type == "UNKNOWN_CALL":
        return f"UNKNOWN_CALL({event.args.get('player')}, {event.args.get('action')})"

    return f"UNKNOWN_EVENT({event.type})"


def events_to_artificial(events: List[Event]) -> List[str]:
    artificial: List[str] = []
    auction_call_index = 0
    bid_index = 0

    for event in events:
        if event.type in {"BID", "PASS", "DOUBLE", "REDOUBLE", "UNKNOWN_CALL"}:
            artificial.append(event_to_artificial(event, auction_call_index, bid_index))
            auction_call_index += 1
            if event.type == "BID":
                bid_index += 1
        else:
            artificial.append(event_to_artificial(event, auction_call_index, bid_index))

    return artificial


def raw_to_artificial(raw: Dict[str, str]) -> List[str]:
    return events_to_artificial(parse_raw_record(raw))
