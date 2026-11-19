import unittest

from bridge_translator.artificial_language import raw_to_artificial
from bridge_translator.bridge_parser import (
    Event,
    normalize_card,
    parse_auction,
    parse_contract,
    parse_finesse_note,
    parse_opening_lead,
    parse_play,
)
from bridge_translator.generator import artificial_to_english


class ParseAuctionTest(unittest.TestCase):
    def test_bids_passes_doubles(self):
        events = parse_auction("North 1♥ - East X - South XX - West P")
        self.assertEqual(
            events,
            [
                Event("BID", {"player": "North", "bid": "1H"}),
                Event("DOUBLE", {"player": "East"}),
                Event("REDOUBLE", {"player": "South"}),
                Event("PASS", {"player": "West"}),
            ],
        )

    def test_unknown_call(self):
        self.assertEqual(parse_auction("North 8NT")[0].type, "UNKNOWN_CALL")

    def test_empty(self):
        self.assertEqual(parse_auction(""), [])


class ParseOtherFieldsTest(unittest.TestCase):
    def test_contract(self):
        self.assertEqual(parse_contract("3nt by South").args, {"contract": "3NT", "declarer": "South"})
        self.assertIsNone(parse_contract("3NT"))

    def test_card_formats_normalise_to_symbol_first(self):
        for text in ["S4", "4S", "♠4", "4♠"]:
            self.assertEqual(normalize_card(text), "♠4")

    def test_opening_lead(self):
        self.assertEqual(parse_opening_lead("West S4").args, {"player": "West", "card": "♠4"})

    def test_play_and_winner(self):
        events = parse_play("Trick 1: West ♠4 - North ♠A - East ♠7 - South ♠2; Winner: North ♠A")
        self.assertEqual([e.type for e in events], ["PLAY"] * 4 + ["WIN_TRICK"])
        self.assertEqual(events[-1].args, {"player": "North", "card": "♠A", "trick_number": "1"})

    def test_finesse_note(self):
        event = parse_finesse_note("Finesse: North in ♠ against queen; success")
        self.assertEqual(event.args, {"player": "North", "suit": "♠", "target": "queen", "outcome": "success"})


class ArtificialLanguageTest(unittest.TestCase):
    def test_raise_to_game_of_partners_strain(self):
        lines = raw_to_artificial({"auction": "North 1S - East Pass - South 4S - West Pass - North Pass - East Pass"})
        self.assertEqual(lines[2], "RAISE_TO_GAME(South, 4S)")

    def test_openers_game_rebid_is_not_a_raise(self):
        lines = raw_to_artificial(
            {"auction": "South 2C - West Pass - North 2D - East Pass - South 3NT - West Pass - North Pass - East Pass"}
        )
        self.assertEqual(lines[2], "RESPOND(North, 2D, waiting_response)")
        self.assertEqual(lines[4], "BID(South, 3NT)")

    def test_game_in_new_strain_is_not_a_raise(self):
        lines = raw_to_artificial({"auction": "North 1H - East Pass - South 4S"})
        self.assertEqual(lines[2], "BID(South, 4S)")


class GeneratorTest(unittest.TestCase):
    def test_round_trip_sentence(self):
        english = artificial_to_english(["OPEN(North, 1NT, balanced, 15-17_HCP)", "LEAD(East, ♠4)"])
        self.assertEqual(
            english,
            "North opens 1NT, showing a balanced hand with about 15–17 high-card points. "
            "East leads the four of spades to begin the play.",
        )


if __name__ == "__main__":
    unittest.main()
