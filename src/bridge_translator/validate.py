"""
validate.py

Legality checks for Bridge records. Each check returns a list of human-readable
error strings; an empty list means the record is legal.

Checked:
- Auction: calls go clockwise, bids increase, doubles/redoubles are legal,
  the auction ends with three passes (or four passes for a passed-out deal).
- Contract: the stated contract, doubled status and declarer match the auction.
- Dealer: if given, the dealer makes the first call.
- Opening lead: made by the player to the left of declarer.
- Play: each trick goes clockwise from the right leader, no card is played
  twice, and the stated winner actually won the trick.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .bridge_parser import (
    PLAYERS,
    Event,
    parse_auction,
    parse_contract,
    parse_opening_lead,
    parse_play,
)


STRAINS = ["C", "D", "H", "S", "NT"]
RANKS = "23456789TJQKA"


def next_player(player: str) -> str:
    return PLAYERS[(PLAYERS.index(player) + 1) % 4]


def partner(player: str) -> str:
    return PLAYERS[(PLAYERS.index(player) + 2) % 4]


def same_side(a: str, b: str) -> bool:
    return a == b or a == partner(b)


def bid_strain(bid: str) -> str:
    return bid[1:]


def bid_order(bid: str) -> int:
    return int(bid[0]) * 5 + STRAINS.index(bid_strain(bid))


def validate_auction(events: List[Event]) -> Tuple[List[str], Optional[Dict[str, str]]]:
    """
    Check auction legality.

    Returns (errors, final_contract). final_contract is
    {"contract", "declarer", "doubled"} or None if the deal was passed out
    or the auction could not be followed.
    """
    errors: List[str] = []
    calls = [e for e in events if e.type in {"BID", "PASS", "DOUBLE", "REDOUBLE", "UNKNOWN_CALL"}]

    if not calls:
        return ["auction is empty"], None

    last_bid: Optional[str] = None
    last_bidder: Optional[str] = None
    doubled = ""  # "", "X", or "XX"
    first_to_name: Dict[Tuple[str, str], str] = {}  # (side-representative, strain) -> player
    passes_in_row = 0

    expected = calls[0].args["player"]
    for i, call in enumerate(calls, 1):
        player = call.args["player"]

        if passes_in_row >= 3 and last_bid is not None:
            errors.append(f"call {i}: {player} calls after the auction has ended")
            break
        if passes_in_row >= 4:
            errors.append(f"call {i}: {player} calls after the deal was passed out")
            break

        if player != expected:
            errors.append(f"call {i}: {player} calls out of turn (expected {expected})")
        expected = next_player(player)

        if call.type == "UNKNOWN_CALL":
            errors.append(f"call {i}: {player} makes an unrecognised call {call.args.get('action')!r}")
            passes_in_row = 0
        elif call.type == "PASS":
            passes_in_row += 1
        elif call.type == "BID":
            bid = call.args["bid"]
            if last_bid is not None and bid_order(bid) <= bid_order(last_bid):
                errors.append(f"call {i}: {player} bids {bid}, which is not higher than {last_bid}")
            last_bid, last_bidder, doubled = bid, player, ""
            key = (min(player, partner(player)), bid_strain(bid))
            first_to_name.setdefault(key, player)
            passes_in_row = 0
        elif call.type == "DOUBLE":
            if last_bid is None or doubled or same_side(player, last_bidder):
                errors.append(f"call {i}: {player} doubles, but there is no opponent's undoubled bid to double")
            else:
                doubled = "X"
            passes_in_row = 0
        elif call.type == "REDOUBLE":
            if doubled != "X" or not same_side(player, last_bidder):
                errors.append(f"call {i}: {player} redoubles, but partnership's bid has not been doubled")
            else:
                doubled = "XX"
            passes_in_row = 0

    if last_bid is None:
        if passes_in_row < 4:
            errors.append("auction does not end with four passes")
        return errors, None

    if passes_in_row < 3:
        errors.append("auction does not end with three passes")

    key = (min(last_bidder, partner(last_bidder)), bid_strain(last_bid))
    return errors, {"contract": last_bid, "declarer": first_to_name[key], "doubled": doubled}


def card_beats(card: str, best: str, trump: Optional[str]) -> bool:
    """Whether `card` beats the current `best` card of the trick (cards as '♠A')."""
    if card[0] == best[0]:
        return RANKS.index(card[1]) > RANKS.index(best[1])
    return card[0] == trump


def validate_play(
    play_events: List[Event],
    opening_leader: str,
    trump: Optional[str],
) -> List[str]:
    errors: List[str] = []
    seen_cards: Dict[str, str] = {}

    tricks: Dict[str, Dict[str, object]] = {}
    for event in play_events:
        trick = tricks.setdefault(event.args["trick_number"], {"plays": [], "winner": None})
        if event.type == "PLAY":
            trick["plays"].append((event.args["player"], event.args["card"]))
        elif event.type == "WIN_TRICK":
            trick["winner"] = (event.args["player"], event.args["card"])

    leader = opening_leader
    for number in sorted(tricks, key=int):
        plays = tricks[number]["plays"]
        stated_winner = tricks[number]["winner"]

        if len(plays) != 4:
            errors.append(f"trick {number}: has {len(plays)} cards instead of 4")

        expected = leader
        for player, card in plays:
            if player != expected:
                errors.append(f"trick {number}: {player} plays out of turn (expected {expected})")
            expected = next_player(player)
            if card in seen_cards:
                errors.append(f"trick {number}: {card} played by {player} was already played by {seen_cards[card]}")
            else:
                seen_cards[card] = player

        if not plays:
            continue

        best_player, best_card = plays[0]
        for player, card in plays[1:]:
            if card_beats(card, best_card, trump):
                best_player, best_card = player, card
        if stated_winner and stated_winner != (best_player, best_card):
            errors.append(
                f"trick {number}: winner is stated as {stated_winner[0]} {stated_winner[1]}, "
                f"but {best_player} {best_card} wins"
            )
        leader = best_player

    return errors


def validate_record(raw: Dict[str, str]) -> List[str]:
    """Return all legality errors for a raw record (empty list means legal)."""
    auction_events = parse_auction(raw.get("auction", ""))
    errors, final = validate_auction(auction_events)

    contract = parse_contract(raw.get("contract", ""))
    if raw.get("contract") and contract is None:
        errors.append(f"could not parse contract {raw['contract']!r}")

    if final and contract:
        if contract.args["contract"] != final["contract"]:
            errors.append(f"contract is stated as {contract.args['contract']}, but the auction ends in {final['contract']}")
        if contract.args["declarer"] != final["declarer"]:
            errors.append(f"declarer is stated as {contract.args['declarer']}, but the auction makes {final['declarer']} declarer")
        if contract.args.get("doubled", "") != final["doubled"]:
            errors.append(
                f"contract is stated with doubled={contract.args.get('doubled', '') or 'none'}, "
                f"but the auction gives doubled={final['doubled'] or 'none'}"
            )

    if raw.get("dealer") and auction_events and auction_events[0].args["player"] != raw["dealer"]:
        errors.append(f"dealer is {raw['dealer']}, but {auction_events[0].args['player']} makes the first call")

    declarer = final["declarer"] if final else (contract.args["declarer"] if contract else None)
    strain = bid_strain(final["contract"]) if final else (bid_strain(contract.args["contract"]) if contract else None)

    lead = parse_opening_lead(raw.get("opening_lead", ""))
    if raw.get("opening_lead") and lead is None:
        errors.append(f"could not parse opening lead {raw['opening_lead']!r}")
    if lead and declarer and lead.args["player"] != next_player(declarer):
        errors.append(f"opening lead is made by {lead.args['player']}, but {next_player(declarer)} should lead")

    play_events = parse_play(raw.get("play", ""))
    if play_events and declarer:
        first_play = next((e for e in play_events if e.type == "PLAY"), None)
        if lead and first_play and (first_play.args["player"], first_play.args["card"]) != (lead.args["player"], lead.args["card"]):
            errors.append("first card played does not match the opening lead")
        trump = None if strain == "NT" else {"C": "♣", "D": "♦", "H": "♥", "S": "♠"}[strain]
        errors.extend(validate_play(play_events, next_player(declarer), trump))

    return errors
