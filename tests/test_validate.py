import json
import unittest
from pathlib import Path

from bridge_translator.bridge_parser import parse_auction
from bridge_translator.validate import validate_auction, validate_record


ROOT = Path(__file__).resolve().parents[1]

LEGAL = {
    "auction": "South 1NT - West Pass - North 3NT - East Double - South Pass - West Pass - North Pass",
    "contract": "3NTX by South",
    "opening_lead": "West ♦J",
    "play": "Trick 1: West ♦J - North ♦2 - East ♦7 - South ♦A; Winner: South ♦A",
}


class ValidateAuctionTest(unittest.TestCase):
    def errors(self, auction):
        return validate_auction(parse_auction(auction))[0]

    def test_legal_auction_and_final_contract(self):
        errors, final = validate_auction(parse_auction(LEGAL["auction"]))
        self.assertEqual(errors, [])
        self.assertEqual(final, {"contract": "3NT", "declarer": "South", "doubled": "X"})

    def test_declarer_is_first_of_side_to_name_strain(self):
        _, final = validate_auction(
            parse_auction("North 1H - East Pass - South 2H - West Pass - North 4H - East Pass - South Pass - West Pass")
        )
        self.assertEqual(final["declarer"], "North")

    def test_passed_out(self):
        self.assertEqual(validate_auction(parse_auction("North P - East P - South P - West P")), ([], None))

    def test_out_of_turn(self):
        # Original train010: East doubles and then calls again.
        errors = self.errors("South 1H - West Pass - North 4H - East Double - East Pass - South Pass - West Pass")
        self.assertIn("call 5: East calls out of turn (expected South)", errors)

    def test_double_of_a_double(self):
        # Original dev010.
        errors = self.errors("South 1C - West Pass - North 5C - East Double - East Double - South Redouble")
        self.assertTrue(any("no opponent's undoubled bid" in e for e in errors))

    def test_double_partners_bid(self):
        errors = self.errors("North 1C - East Pass - South Double")
        self.assertTrue(any("no opponent's undoubled bid" in e for e in errors))

    def test_redouble_without_double(self):
        errors = self.errors("North 1C - East Redouble")
        self.assertTrue(any("redoubles" in e for e in errors))

    def test_insufficient_bid(self):
        errors = self.errors("North 1S - East 1H - South Pass - West Pass - North Pass")
        self.assertIn("call 2: East bids 1H, which is not higher than 1S", errors)

    def test_missing_final_passes(self):
        self.assertIn("auction does not end with three passes", self.errors("North 1S - East Pass"))

    def test_call_after_auction_ends(self):
        errors = self.errors("North 1S - East Pass - South Pass - West Pass - North 2S")
        self.assertTrue(any("after the auction has ended" in e for e in errors))


class ValidateRecordTest(unittest.TestCase):
    def test_legal_record(self):
        self.assertEqual(validate_record(LEGAL), [])

    def test_doubled_status_must_match(self):
        errors = validate_record({**LEGAL, "contract": "3NT by South"})
        self.assertIn("contract is stated with doubled=none, but the auction gives doubled=X", errors)

    def test_dealer_must_call_first(self):
        errors = validate_record({**LEGAL, "dealer": "North"})
        self.assertIn("dealer is North, but South makes the first call", errors)

    def test_wrong_declarer(self):
        errors = validate_record({**LEGAL, "contract": "3NTX by North"})
        self.assertIn("declarer is stated as North, but the auction makes South declarer", errors)

    def test_wrong_opening_leader(self):
        errors = validate_record({**LEGAL, "opening_lead": "East ♦J", "play": ""})
        self.assertIn("opening lead is made by East, but West should lead", errors)

    def test_counterclockwise_play(self):
        # Original test010 ordering: leader, declarer, leader's partner, dummy.
        errors = validate_record({**LEGAL, "play": "Trick 1: West ♦J - South ♦A - East ♦7 - North ♦2; Winner: South ♦A"})
        self.assertIn("trick 1: South plays out of turn (expected North)", errors)

    def test_duplicate_card_and_wrong_winner(self):
        # Original test004: two aces of spades in one trick.
        record = {
            "auction": "North 2NT - East Pass - South 3NT - West Pass - North Pass - East Pass",
            "contract": "3NT by North",
            "opening_lead": "East ♠A",
            "play": "Trick 1: East ♠A - South ♠2 - West ♠7 - North ♠A; Winner: North ♠A",
        }
        errors = validate_record(record)
        self.assertIn("trick 1: ♠A played by North was already played by East", errors)
        self.assertIn("trick 1: winner is stated as North ♠A, but East ♠A wins", errors)

    def test_ruff_wins_trick(self):
        record = {
            "auction": "North 4S - East Pass - South Pass - West Pass",
            "contract": "4S by North",
            "opening_lead": "East ♥A",
            "play": "Trick 1: East ♥A - South ♥2 - West ♥3 - North ♠2; Winner: North ♠2",
        }
        self.assertEqual(validate_record(record), [])


class DatasetTest(unittest.TestCase):
    def test_every_record_is_legal(self):
        for split in ["train", "dev", "test", "real_dev", "real_test"]:
            for example in json.loads((ROOT / "data" / f"{split}.json").read_text(encoding="utf-8")):
                with self.subTest(id=example["id"]):
                    self.assertEqual(validate_record(example["raw"]), [])


if __name__ == "__main__":
    unittest.main()
