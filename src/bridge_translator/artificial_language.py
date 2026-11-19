"""
artificial_language.py

Maps parsed Bridge events into the controlled artificial Bridge language.

Each bid gets a role from who makes it:
- OPEN      first bid of the auction (with seat=3/4 when made after passes)
- RESPOND   opener's partner's first bid
- OVERCALL  first bid by the side that did not open
- ADVANCE   overcaller's partner's first bid
- REBID     any later bid by a player who has already bid
- RAISE_TO_GAME  any of the above that raises partner's strain to game

Doubles and redoubles get a meaning from the auction context. The rules follow
common Standard American agreements and are deliberately simple:
- double of an artificial bid                         -> lead_directing
- double of a no-trump bid                            -> penalty
- responder doubles an overcall at the 1-3 level      -> negative
- doubler's partner has bid                           -> penalty
- otherwise, double of a suit bid at the 1-3 level    -> takeout
- otherwise                                           -> penalty
- redouble after a takeout double of partner's bid    -> strength
- other redoubles                                     -> to_play
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .bridge_parser import Event, parse_raw_record
from .validate import bid_order, bid_strain, partner


GAME_CONTRACTS = {"3NT", "4H", "4S", "5C", "5D"}
AUCTION_TYPES = {"BID", "PASS", "DOUBLE", "REDOUBLE", "UNKNOWN_CALL"}


def opening_interpretation(bid: str, alerted: bool = False) -> str:
    if alerted:
        return "artificial, system_specific"
    if bid == "1NT":
        return "balanced, 15-17_HCP"
    if bid == "2NT":
        return "balanced, 20-21_HCP"
    if bid == "2C":
        return "strong_artificial, very_strong_hand"
    if bid in {"1C", "1D", "1H", "1S"}:
        return "suit_opening, opening_strength"
    if bid in {"2D", "2H", "2S"}:
        return "weak_two, six_card_suit, 5-10_HCP"
    if bid_strain(bid) != "NT" and int(bid[0]) >= 3:
        return "preempt, long_suit, weak_hand"
    return "unknown_shape, unknown_strength"


def is_jump(bid: str, last_bid: Optional[str]) -> bool:
    """Whether `bid` skips at least one level compared with the cheapest legal bid in its strain."""
    if last_bid is None:
        return False
    last_level = int(last_bid[0])
    cheapest = last_level if bid_order(f"{last_level}{bid_strain(bid)}") > bid_order(last_bid) else last_level + 1
    return int(bid[0]) > cheapest


class AuctionState:
    """Running context for labelling calls."""

    def __init__(self) -> None:
        self.calls_before_opening = 0
        self.opener: Optional[str] = None
        self.opening_bid: Optional[str] = None
        self.bids: Dict[str, List[str]] = {}
        self.last_bid: Optional[str] = None
        self.last_bidder: Optional[str] = None
        self.last_bid_artificial = False
        self.last_bid_was_overcall = False
        self.last_double_kind: Optional[str] = None
        self.overcalling_side_has_bid = False
        self.only_passes_since_opening = True

    def strains(self, player: str) -> set:
        return {bid_strain(b) for b in self.bids.get(player, [])}

    def side_has_bid(self, player: str) -> bool:
        return bool(self.bids.get(player) or self.bids.get(partner(player)))


def bid_tag(state: AuctionState, player: str, bid: str, role: str) -> str:
    strain = bid_strain(bid)
    if role == "RESPOND":
        if state.opening_bid == "2C" and bid == "2D" and state.only_passes_since_opening:
            return "waiting_response"
        if state.opening_bid in {"1NT", "2NT"} and state.only_passes_since_opening:
            level = int(state.opening_bid[0]) + 1
            if bid == f"{level}C":
                return "stayman"
            if bid in {f"{level}D", f"{level}H"}:
                return "transfer"
    if role == "OVERCALL":
        if strain == bid_strain(state.opening_bid):
            return "cue_bid"
        if bid == "1NT":
            return "notrump_overcall"
        if bid == "2NT" and is_jump(bid, state.last_bid):
            return "unusual_2nt"
        if is_jump(bid, state.last_bid):
            return "jump_overcall"
        return "simple_overcall"
    if role == "REBID" and strain in state.strains(player):
        return "own_suit"
    if strain in state.strains(partner(player)):
        return "raise"
    if role == "ADVANCE" and strain == bid_strain(state.opening_bid):
        return "cue_bid"
    if strain == "NT":
        return "notrump"
    return "new_suit"


def classify_double(state: AuctionState, player: str) -> str:
    if state.last_bid is None:
        return "unknown"
    if state.last_bid_artificial:
        return "lead_directing"
    if bid_strain(state.last_bid) == "NT":
        return "penalty"
    level = int(state.last_bid[0])
    partner_has_bid = bool(state.bids.get(partner(player)))
    if (
        partner_has_bid
        and partner(player) == state.opener
        and not state.bids.get(player)
        and state.last_bid_was_overcall
        and level <= 3
    ):
        return "negative"
    if partner_has_bid:
        return "penalty"
    if level <= 3:
        return "takeout"
    return "penalty"


def label_bid(state: AuctionState, event: Event) -> str:
    player = event.args["player"]
    bid = event.args["bid"]
    alerted = event.args.get("alerted") == "true"

    if state.opener is None:
        seat = state.calls_before_opening + 1
        line = f"OPEN({player}, {bid}, {opening_interpretation(bid, alerted)}"
        if seat >= 3:
            line += f", seat={seat}"
        return line + ")"

    if state.bids.get(player):
        role = "REBID"
    elif player == partner(state.opener):
        role = "RESPOND"
    elif not state.overcalling_side_has_bid:
        role = "OVERCALL"
    else:
        role = "ADVANCE"

    tag = "artificial" if alerted else bid_tag(state, player, bid, role)
    if tag == "raise" and bid in GAME_CONTRACTS:
        return f"RAISE_TO_GAME({player}, {bid})"
    return f"{role}({player}, {bid}, {tag})"


def update_state_after_bid(state: AuctionState, event: Event, line: str) -> None:
    player = event.args["player"]
    bid = event.args["bid"]
    if state.opener is None:
        state.opener, state.opening_bid = player, bid
    elif state.only_passes_since_opening:
        state.only_passes_since_opening = False
    if line.startswith("OVERCALL("):
        state.overcalling_side_has_bid = True
    state.last_bid_was_overcall = line.startswith("OVERCALL(")
    state.last_bid_artificial = (
        event.args.get("alerted") == "true"
        or (line.startswith("OPEN(") and bid == "2C")
        or any(t in line for t in ("waiting_response", "stayman", "transfer"))
    )
    state.last_bid, state.last_bidder = bid, player
    state.last_double_kind = None
    state.bids.setdefault(player, []).append(bid)


def event_to_artificial(event: Event) -> str:
    """Convert a non-auction event to its artificial-language line."""
    if event.type == "HAND":
        return f"HAND({event.args['player']}, hcp={event.args['hcp']}, shape={event.args['shape']})"

    if event.type == "CONTRACT":
        line = f"CONTRACT({event.args['contract']}, declarer={event.args['declarer']}"
        if event.args.get("doubled"):
            line += f", doubled={event.args['doubled']}"
        return line + ")"

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

    if event.type == "RESULT":
        return f"RESULT({event.args['declarer']}, contract={event.args['contract']}, tricks={event.args['tricks']})"

    return f"UNKNOWN_EVENT({event.type})"


def events_to_artificial(events: List[Event]) -> List[str]:
    artificial: List[str] = []
    state = AuctionState()

    for event in events:
        if event.type not in AUCTION_TYPES:
            artificial.append(event_to_artificial(event))
            continue

        player = event.args["player"]
        if event.type == "PASS":
            line = f"PASS({player})"
        elif event.type == "DOUBLE":
            kind = classify_double(state, player)
            line = f"DOUBLE({player}, {kind})"
            state.last_double_kind = kind
        elif event.type == "REDOUBLE":
            kind = "strength" if state.last_double_kind == "takeout" and state.last_bidder == partner(player) else "to_play"
            line = f"REDOUBLE({player}, {kind})"
        elif event.type == "BID":
            line = label_bid(state, event)
            update_state_after_bid(state, event, line)
        else:
            line = f"UNKNOWN_CALL({player}, {event.args.get('action')})"

        if state.opener is None:
            state.calls_before_opening += 1
        artificial.append(line)

    return artificial


def raw_to_artificial(raw: Dict[str, str]) -> List[str]:
    return events_to_artificial(parse_raw_record(raw))
