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


def opening_sentence(player: str, bid: str, style: str) -> str:
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
    return f"{player} opens {bid}."


def artificial_to_english(artificial_lines: List[str], style: str = "beginner") -> str:
    sentences: List[str] = []
    current_trick_plays: Dict[str, List[str]] = {}

    for line in artificial_lines:
        line = line.strip()

        if line.startswith("OPEN("):
            args = split_args(line, "OPEN")
            sentences.append(opening_sentence(args[0], args[1], style))

        elif line.startswith("PASS("):
            player = split_args(line, "PASS")[0]
            sentences.append(f"{player} passes.")

        elif line.startswith("DOUBLE("):
            player = split_args(line, "DOUBLE")[0]
            if style == "beginner":
                sentences.append(f"{player} doubles, increasing the penalty if the contract fails.")
            else:
                sentences.append(f"{player} doubles.")

        elif line.startswith("REDOUBLE("):
            player = split_args(line, "REDOUBLE")[0]
            if style == "beginner":
                sentences.append(f"{player} redoubles, increasing the stakes after the double.")
            else:
                sentences.append(f"{player} redoubles.")

        elif line.startswith("RAISE_TO_GAME("):
            player, bid = split_args(line, "RAISE_TO_GAME")
            sentences.append(f"{player} raises directly to {bid}, which is {game_description(bid)}.")

        elif line.startswith("RESPOND("):
            args = split_args(line, "RESPOND")
            player, bid = args[0], args[1]
            if bid == "2D":
                sentences.append(f"{player} responds 2D, keeping the auction open after partner's strong opening.")
            else:
                sentences.append(f"{player} responds {bid}, keeping the auction open.")

        elif line.startswith("BID("):
            player, bid = split_args(line, "BID")
            sentences.append(f"{player} bids {bid}.")

        elif line.startswith("CONTRACT("):
            args = split_args(line, "CONTRACT")
            contract = args[0]
            declarer = args[1].split("=")[1].strip()
            sentences.append(f"The final contract is {contract} by {declarer}.")

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

        else:
            sentences.append(f"The system records {line}.")

    return " ".join(sentences)
