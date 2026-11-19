"""
generator.py

Template-based English generation from artificial Bridge language.

Supports beginner and expert-ish styles. Beginner mode explains more terms.
Expert mode is more compact.
"""

from __future__ import annotations

import re
from typing import Dict, List


SUIT_NAMES = {
    "♣": "clubs", "♦": "diamonds", "♥": "hearts", "♠": "spades",
    "C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades",
}
BID_SUIT_NAMES = {"C": "club", "D": "diamond", "H": "heart", "S": "spade", "NT": "no-trump"}
RANK_NAMES = {
    "A": "ace", "K": "king", "Q": "queen", "J": "jack", "T": "ten",
    "9": "nine", "8": "eight", "7": "seven", "6": "six",
    "5": "five", "4": "four", "3": "three", "2": "two",
}


def split_args(line: str, predicate: str) -> List[str]:
    inside = line[len(predicate) + 1:-1]
    return [part.strip() for part in inside.split(",")]


def card_to_english(card: str) -> str:
    card = card.strip()
    if len(card) != 2:
        return card
    return f"{RANK_NAMES.get(card[1], card[1])} of {SUIT_NAMES.get(card[0], card[0])}"


def game_description(bid: str) -> str:
    if bid == "3NT":
        return "a game-level no-trump contract"
    if len(bid) == 2:
        return f"a game-level {BID_SUIT_NAMES.get(bid[1], bid[1])} contract"
    return "a game contract"


def opening_sentence(player: str, bid: str, style: str, interpretation: str = "") -> str:
    if "artificial" in interpretation and "strong_artificial" not in interpretation:
        return (
            f"{player} opens {bid}, an alerted artificial bid whose meaning depends on the partnership's system."
            if style == "beginner"
            else f"{player} opens an artificial {bid}."
        )
    if bid == "1NT":
        return (
            f"{player} opens 1NT, showing a balanced hand with about 15–17 high-card points."
            if style == "beginner"
            else f"{player} opens a standard 15–17 1NT."
        )
    if bid == "2NT":
        return (
            f"{player} opens 2NT, showing a balanced hand with about 20–21 high-card points."
            if style == "beginner"
            else f"{player} opens a strong 20–21 2NT."
        )
    if bid == "2C":
        return (
            f"{player} opens 2C, a strong artificial opening that usually shows a very powerful hand."
            if style == "beginner"
            else f"{player} opens a strong artificial 2C."
        )
    if len(bid) == 2 and bid[0] == "1":
        suit = BID_SUIT_NAMES.get(bid[1], bid[1])
        return (
            f"{player} opens {bid}, showing an opening bid in {suit}s."
            if style == "beginner"
            else f"{player} opens {bid}."
        )
    if style == "beginner" and "weak_two" in interpretation:
        suit = BID_SUIT_NAMES[bid[1]]
        return f"{player} opens {bid}, a weak two-bid showing a six-card {suit} suit and about 5–10 high-card points."
    if style == "beginner" and "preempt" in interpretation:
        suit = BID_SUIT_NAMES[bid_strain(bid)]
        return (
            f"{player} opens {bid}, a preemptive bid showing a long {suit} suit and a weak hand; "
            "it takes bidding space away from the opponents."
        )
    if "weak_two" in interpretation:
        return f"{player} opens a weak {bid}."
    if "preempt" in interpretation:
        return f"{player} opens {bid}, preemptive."
    return f"{player} opens {bid}."


NUMBER_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
                "eleven", "twelve", "thirteen"]
TAG_PHRASES = {
    "stayman": "Stayman", "transfer": "a transfer", "raise": "a raise", "notrump": "no-trump",
    "new_suit": "a new suit", "own_suit": "rebidding the suit", "cue_bid": "a cue-bid",
    "simple_overcall": "an overcall", "jump_overcall": "a weak jump overcall",
    "notrump_overcall": "15–18 balanced", "unusual_2nt": "unusual no-trump", "artificial": "artificial",
    "waiting_response": "waiting", "agreed_suit": "the agreed suit", "second_suit": "a second suit",
}


def bid_strain(bid: str) -> str:
    return bid[1:]


def level_note(bid: str) -> str:
    """', which is ...' for bids that reach game or slam, else ''."""
    level, strain = int(bid[0]), bid_strain(bid)
    if level == 6:
        return ", which is a small slam needing 12 of the 13 tricks"
    if level == 7:
        return ", which is a grand slam needing all 13 tricks"
    if (strain == "NT" and level >= 3) or (strain in {"H", "S"} and level >= 4) or (strain in {"C", "D"} and level >= 5):
        if bid in {"3NT", "4H", "4S", "5C", "5D"}:
            return f", which is {game_description(bid)}"
        return ", which is above game level"
    return ""


def bid_sentence(role: str, player: str, bid: str, tag: str, style: str) -> str:
    strain = bid_strain(bid)
    suit = BID_SUIT_NAMES.get(strain, strain)
    note = level_note(bid)

    if style != "beginner":
        verb = {"RESPOND": "responds", "OVERCALL": "overcalls", "ADVANCE": "advances", "REBID": "rebids"}[role]
        return f"{player} {verb} {bid} ({TAG_PHRASES.get(tag, tag)})."

    if tag == "artificial":
        return f"{player} bids {bid}, an alerted artificial bid whose meaning depends on the partnership's system{note}."
    if tag == "waiting_response":
        return f"{player} responds {bid}, keeping the auction open after partner's strong opening."
    if tag == "stayman":
        return f"{player} responds {bid}, the Stayman convention, asking whether partner holds a four-card major suit."
    if tag == "transfer":
        target = {"D": "hearts", "H": "spades"}[strain]
        return f"{player} responds {bid}, a transfer asking partner to bid {target}; it shows at least five {target}."
    if tag == "raise":
        return f"{player} raises partner's {suit}{'' if strain == 'NT' else 's'} to {bid}{note}."
    if tag == "simple_overcall":
        return f"{player} overcalls {bid}, showing a good {suit} suit, usually five or more cards{note}."
    if tag == "jump_overcall":
        return f"{player} makes a jump overcall of {bid}, a preemptive bid showing a long {suit} suit and a weak hand{note}."
    if tag == "notrump_overcall":
        return (
            f"{player} overcalls {bid}, showing a balanced hand with about 15–18 high-card points "
            "and a stopper in the opponents' suit."
        )
    if tag == "unusual_2nt":
        return f"{player} jumps to {bid}, the unusual no-trump, showing at least five cards in each of the two lowest unbid suits."
    if tag == "cue_bid" and role == "OVERCALL":
        return f"{player} cue-bids {bid} in the opponents' suit, usually showing a two-suited hand{note}."
    if tag == "cue_bid":
        return f"{player} cue-bids {bid} in the opponents' suit, an artificial bid showing a strong hand{note}."
    if tag == "agreed_suit":
        return f"{player} bids {bid} in the suit the partnership has agreed on{note}."
    if tag == "own_suit":
        return f"{player} rebids {bid}, showing extra length in {suit}s{note}."
    if role == "REBID" and tag == "notrump":
        return f"{player} rebids {bid}{note}."
    if tag == "second_suit":
        return f"{player} bids {bid}, showing a second suit{note}."
    if role == "REBID":
        return f"{player} bids {bid}, naming a {suit} suit{note}."
    if tag == "notrump":
        return f"{player} bids {bid}, suggesting a no-trump contract{note}."
    if role == "ADVANCE":
        return f"{player} bids {bid}, showing {suit}s in reply to partner's overcall or double{note}."
    if int(bid[0]) == 1:
        return f"{player} responds {bid}, showing at least four {suit}s{note}."
    return f"{player} responds {bid}, naming a new {suit} suit with enough strength to bid at a higher level{note}."


DOUBLE_SENTENCES = {
    "penalty": "{p} doubles, increasing the penalty if the contract fails.",
    "takeout": "{p} doubles for takeout, showing opening values and support for the unbid suits, and asking partner to choose one.",
    "negative": "{p} makes a negative double, showing some values and length in the unbid suits rather than a wish to defend.",
    "lead_directing": "{p} doubles the artificial bid, asking partner to lead that suit.",
    "responsive": "{p} makes a responsive double, showing values and length in the unbid suits after partner's takeout double.",
}
DOUBLE_EXPERT = {"takeout": "{p} doubles for takeout.", "negative": "{p} makes a negative double.",
                 "lead_directing": "{p} makes a lead-directing double.",
                 "responsive": "{p} makes a responsive double."}


def hand_sentence(player: str, hcp: str, shape: str, style: str) -> str:
    if style != "beginner":
        return f"{player}: {hcp} HCP, {shape}."
    counts = [NUMBER_WORDS[int(n)] for n in shape.split("-")]
    names = ["spades", "hearts", "diamonds", "clubs"]
    parts = [f"{c} {name[:-1] if c == 'one' else name}" for c, name in zip(counts, names)]
    return f"{player} holds {hcp} high-card points with {', '.join(parts[:3])} and {parts[3]}."


def result_sentence(declarer: str, contract: str, tricks: int) -> str:
    diff = tricks - (int(contract[0]) + 6)
    if diff == 0:
        outcome = "making the contract exactly"
    elif diff > 0:
        outcome = f"making the contract with {NUMBER_WORDS[diff]} overtrick{'s' if diff > 1 else ''}"
    else:
        outcome = f"going down {NUMBER_WORDS[-diff]}"
    return f"{declarer} takes {tricks} trick{'s' if tricks != 1 else ''}, {outcome}."


def artificial_to_english(artificial_lines: List[str], style: str = "beginner") -> str:
    sentences: List[str] = []
    current_trick_plays: Dict[str, List[str]] = {}

    for line in artificial_lines:
        line = line.strip()

        if line.startswith("OPEN("):
            args = split_args(line, "OPEN")
            seat = next((a.split("=")[1] for a in args if a.startswith("seat=")), None)
            sentences.append(opening_sentence(args[0], args[1], style, ", ".join(args[2:])))
            if seat and style == "beginner":
                sentences.append({
                    "3": "This opening comes in third seat, after two passes, where openings can be a little lighter than usual.",
                    "4": "This opening comes in fourth seat, after three passes; with a weaker hand the deal could have been passed out.",
                }[seat])

        elif line.startswith("HAND("):
            args = split_args(line, "HAND")
            sentences.append(hand_sentence(args[0], args[1].split("=")[1], args[2].split("=")[1], style))

        elif line.startswith("PASS("):
            player = split_args(line, "PASS")[0]
            sentences.append(f"{player} passes.")

        elif line.startswith("DOUBLE("):
            args = split_args(line, "DOUBLE")
            player, kind = args[0], (args[1] if len(args) > 1 else "penalty")
            if style == "beginner":
                sentences.append(DOUBLE_SENTENCES.get(kind, "{p} doubles.").format(p=player))
            else:
                sentences.append(DOUBLE_EXPERT.get(kind, "{p} doubles.").format(p=player))

        elif line.startswith("REDOUBLE("):
            args = split_args(line, "REDOUBLE")
            player, kind = args[0], (args[1] if len(args) > 1 else "to_play")
            if style == "beginner" and kind == "strength":
                sentences.append(f"{player} redoubles, showing about 10 or more high-card points after the opponents' takeout double.")
            elif style == "beginner":
                sentences.append(f"{player} redoubles, increasing the stakes after the double.")
            else:
                sentences.append(f"{player} redoubles.")

        elif line.startswith(("RESPOND(", "OVERCALL(", "ADVANCE(", "REBID(")):
            role = line.split("(", 1)[0]
            player, bid, tag = split_args(line, role)
            sentences.append(bid_sentence(role, player, bid, tag, style))

        elif line.startswith("RAISE_TO_GAME("):
            player, bid = split_args(line, "RAISE_TO_GAME")
            sentences.append(f"{player} raises directly to {bid}, which is {game_description(bid)}.")

        elif line.startswith("BID("):
            player, bid = split_args(line, "BID")
            sentences.append(f"{player} bids {bid}.")

        elif line.startswith("CONTRACT("):
            args = split_args(line, "CONTRACT")
            contract = args[0]
            declarer = args[1].split("=")[1].strip()
            doubled = args[2].split("=")[1].strip() if len(args) > 2 else ""
            marker = {"X": " doubled", "XX": " redoubled"}.get(doubled, "")
            sentences.append(f"The final contract is {contract}{marker} by {declarer}.")

        elif line.startswith("LEAD("):
            player, card = split_args(line, "LEAD")
            sentences.append(f"{player} leads the {card_to_english(card)} to begin the play.")

        elif line.startswith("PLAY("):
            args = split_args(line, "PLAY")
            player, card = args[0], args[1]
            trick_number = args[2].split("=")[1].strip()
            current_trick_plays.setdefault(trick_number, []).append(f"{player} plays the {card_to_english(card)}")

        elif line.startswith("WIN_TRICK("):
            args = split_args(line, "WIN_TRICK")
            winner = args[0]
            trick_number = args[1].split("=")[1].strip()
            card = args[2].split("=")[1].strip()
            plays = current_trick_plays.get(trick_number, [])
            if plays:
                play_text = ", ".join(plays)
                sentences.append(
                    f"On trick {trick_number}, {play_text}, and {winner} wins the trick with the {card_to_english(card)}."
                )
            else:
                sentences.append(f"{winner} wins trick {trick_number} with the {card_to_english(card)}.")

        elif line.startswith("FINESSE_ATTEMPT("):
            args = split_args(line, "FINESSE_ATTEMPT")
            player = args[0]
            suit = args[1].split("=")[1].strip()
            target = args[2].split("=")[1].strip()
            outcome = args[3].split("=")[1].strip()
            result = "works" if outcome == "success" else "loses"
            if style == "beginner":
                sentences.append(
                    f"{player} attempts a finesse in {SUIT_NAMES.get(suit, suit)} against the {target}; the finesse {result}."
                )
            else:
                sentences.append(f"{player}'s {SUIT_NAMES.get(suit, suit)} finesse against the {target} {result}.")

        elif line.startswith("RESULT("):
            args = split_args(line, "RESULT")
            contract = args[1].split("=")[1].strip()
            tricks = int(args[2].split("=")[1].strip())
            sentences.append(result_sentence(args[0], contract, tricks))

        else:
            sentences.append(f"The system records {line}.")

    return " ".join(sentences)
