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
        self.assertEqual(lines[4], "REBID(South, 3NT, notrump)")

    def test_game_in_new_strain_is_not_a_raise(self):
        lines = raw_to_artificial({"auction": "North 1H - East Pass - South 4S"})
        self.assertEqual(lines[2], "RESPOND(South, 4S, new_suit)")


def auction(text):
    return raw_to_artificial({"auction": text})


class RolesAndSeatsTest(unittest.TestCase):
    def test_overcall_advance_and_rebid(self):
        lines = auction("North 1H - East 1S - South 2H - West 2S - North 3H")
        self.assertEqual(
            lines,
            [
                "OPEN(North, 1H, suit_opening, opening_strength)",
                "OVERCALL(East, 1S, simple_overcall)",
                "RESPOND(South, 2H, raise)",
                "ADVANCE(West, 2S, raise)",
                "REBID(North, 3H, own_suit)",
            ],
        )

    def test_overcall_types(self):
        self.assertEqual(auction("North 1H - East 2S")[1], "OVERCALL(East, 2S, jump_overcall)")
        self.assertEqual(auction("North 1H - East 1NT")[1], "OVERCALL(East, 1NT, notrump_overcall)")
        self.assertEqual(auction("North 1H - East 2H")[1], "OVERCALL(East, 2H, cue_bid)")
        self.assertEqual(auction("North 1H - East 2NT")[1], "OVERCALL(East, 2NT, unusual_2nt)")
        self.assertEqual(auction("North 1S - East 2H")[1], "OVERCALL(East, 2H, simple_overcall)")

    def test_seat(self):
        self.assertEqual(auction("North Pass - East Pass - South 1S")[2], "OPEN(South, 1S, suit_opening, opening_strength, seat=3)")
        self.assertEqual(auction("North Pass - East 1S")[1], "OPEN(East, 1S, suit_opening, opening_strength)")

    def test_opening_types(self):
        self.assertEqual(auction("North 2H")[0], "OPEN(North, 2H, weak_two, six_card_suit, 5-10_HCP)")
        self.assertEqual(auction("North 3C")[0], "OPEN(North, 3C, preempt, long_suit, weak_hand)")
        self.assertEqual(auction("North 1C!")[0], "OPEN(North, 1C, artificial, system_specific)")

    def test_stayman_and_transfers(self):
        self.assertEqual(auction("North 1NT - East Pass - South 2C")[2], "RESPOND(South, 2C, stayman)")
        self.assertEqual(auction("North 1NT - East Pass - South 2H")[2], "RESPOND(South, 2H, transfer)")
        self.assertEqual(auction("North 2NT - East Pass - South 3D")[2], "RESPOND(South, 3D, transfer)")
        # After interference, 2C is natural.
        self.assertEqual(auction("North 1NT - East 2D - South 3C")[2], "RESPOND(South, 3C, new_suit)")


class DoublesTest(unittest.TestCase):
    def test_takeout(self):
        self.assertEqual(auction("North 1H - East Double")[1], "DOUBLE(East, takeout)")

    def test_negative(self):
        self.assertEqual(auction("North 1C - East 1S - South Double")[2], "DOUBLE(South, negative)")

    def test_penalty_of_notrump_and_of_game(self):
        self.assertEqual(auction("North 1NT - East Double")[1], "DOUBLE(East, penalty)")
        self.assertEqual(auction("North 1H - East Pass - South 4H - West Double")[3], "DOUBLE(West, penalty)")

    def test_penalty_when_partner_has_bid(self):
        lines = auction("North 1H - East 1S - South 2C - West 2S - North 3C - East Pass - South Pass - West Double")
        self.assertEqual(lines[-1], "DOUBLE(West, penalty)")

    def test_lead_directing(self):
        self.assertEqual(auction("North 1NT - East Pass - South 2C - West Double")[3], "DOUBLE(West, lead_directing)")
        self.assertEqual(auction("North 1C! - East Double")[1], "DOUBLE(East, lead_directing)")

    def test_redoubles(self):
        self.assertEqual(auction("North 1H - East Double - South Redouble")[2], "REDOUBLE(South, strength)")
        self.assertEqual(
            auction("North 1H - East Pass - South 4H - West Double - North Redouble")[4], "REDOUBLE(North, to_play)"
        )


class HandsAndResultTest(unittest.TestCase):
    def test_hand_line(self):
        lines = raw_to_artificial({"hands": {"North": "AK963.AJ5.32.KT5"}})
        self.assertEqual(lines, ["HAND(North, hcp=15, shape=5-3-2-3)"])

    def test_doubled_contract_and_result(self):
        lines = raw_to_artificial({"contract": "4HX by South", "result": "8"})
        self.assertEqual(lines, ["CONTRACT(4H, declarer=South, doubled=X)", "RESULT(South, contract=4H, tricks=8)"])
        self.assertEqual(
            artificial_to_english(lines),
            "The final contract is 4H doubled by South. South takes 8 tricks, going down two.",
        )


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
