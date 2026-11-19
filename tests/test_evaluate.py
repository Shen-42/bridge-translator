import unittest

from bridge_translator.evaluate import (
    bid_sequence_in_order,
    fact_accuracy,
    fk_grade,
    meaning_facts_from_gold,
    meaning_recall,
    unsupported_bids,
)

RAW = {"auction": "South 1H - West Double - North 3H - East Double - South Pass - West 3S", "contract": "3S by West"}


class FactAccuracyTest(unittest.TestCase):
    def test_value_must_appear_in_its_role(self):
        facts = {"declarer": "West"}
        self.assertEqual(fact_accuracy("The final contract is 3S by West.", facts), 1.0)
        # West is mentioned, but never as declarer.
        self.assertEqual(fact_accuracy("West doubles. North passes.", facts), 0.0)

    def test_partner_fact_in_same_sentence_counts(self):
        facts = {"opener": "South", "opening_bid": "1H", "opening_leader": "East", "opening_lead": "♣2"}
        output = "South then bid 1 hearts. On the first trick, East led with the two of clubs."
        self.assertEqual(fact_accuracy(output, facts), 1.0)
        self.assertEqual(fact_accuracy("South bids 2H. North bids 1H.", {"opener": "South", "opening_bid": "1H"}), 0.0)

    def test_card_and_number_variants(self):
        facts = {"opening_lead": "♥6", "declarer_tricks": "8"}
        self.assertEqual(fact_accuracy("North leads the 6♥. Declarer takes eight tricks.", facts), 1.0)

    def test_finesse_outcome_words(self):
        self.assertEqual(fact_accuracy("The finesse loses.", {"finesse_outcome": "failure"}), 1.0)

    def test_bid_sequence_order(self):
        sequence = "North:1NT East:PASS South:3NT West:PASS"
        self.assertTrue(bid_sequence_in_order("North opens 1NT and South raises to three no-trump.", sequence))
        self.assertFalse(bid_sequence_in_order("South bids 3NT after North's 1NT.", sequence))


class MeaningTest(unittest.TestCase):
    def test_player_and_keyword_in_one_sentence(self):
        meaning = {"West 2H": ["michaels", "two-suited"], "North Double": ["takeout"]}
        output = "West bids 2H, a Michaels cue-bid. North doubles. Partner should take out the double."
        self.assertEqual(meaning_recall(output, meaning), 0.5)

    def test_from_gold_artificial(self):
        facts = meaning_facts_from_gold(["OPEN(North, 1NT, balanced, 15-17_HCP)", "DOUBLE(East, penalty)"])
        self.assertEqual(facts, {"North 1NT": ["15-17", "balanced"], "East Double": ["penalty"]})


class UnsupportedBidsTest(unittest.TestCase):
    def test_counts_only_invented_calls(self):
        self.assertEqual(unsupported_bids("West bids 3S over North's 3H.", RAW), 0)
        self.assertEqual(unsupported_bids("West bids 4S.", RAW), 1)
        self.assertEqual(unsupported_bids("North raises to three hearts, then East jumps to 4 spades.", RAW), 1)

    def test_cards_and_hand_shapes_are_not_bids(self):
        self.assertEqual(unsupported_bids("North led 6♥ and South holds two spades.", RAW), 0)


class ReadabilityTest(unittest.TestCase):
    def test_longer_words_and_sentences_read_harder(self):
        self.assertLess(fk_grade("North bids. East bids."), fk_grade("The partnership's complicated conventional agreements necessitate considerable memorization."))


if __name__ == "__main__":
    unittest.main()
