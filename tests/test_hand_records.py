import unittest

from bridge_translator.hand_records import parse_lin, parse_pbn
from bridge_translator.validate import validate_record

HANDS = {
    "North": "KT62..AJ953.AQ76",
    "East": "AQ987.AJ5.8.J543",
    "South": "J4.QT63.KT7642.K",
    "West": "53.K98742.Q.T982",
}
AUCTION = (
    "South Pass - West 2H - North Double - East 2NT{alert} - South 3D - West Pass - North 3H - "
    "East Pass - South 3NT - West Pass - North Pass - East Pass"
)
EXPECTED = {
    "dealer": "South",
    "hands": HANDS,
    "contract": "3NT by South",
    "opening_lead": "West ♣T",
    "play": "Trick 1: West ♣T - North ♣6 - East ♣5 - South ♣K; Winner: South ♣K",
    "result": "9",
}

# East's hand is left out, as LIN files often do; the reader rebuilds it.
LIN = (
    "qx|o1|md|1SJ4HQT63DKT7642CK,S53HK98742DQCT982,SKT62HDAJ953CAQ76,|sv|o|"
    "mb|p|mb|2H|mb|d|mb|2N!|an|lebensohl|mb|3D|mb|p|mb|3H|mb|p|mb|3N|mb|p|mb|p|mb|p|"
    "pc|CT|pc|C6|pc|C5|pc|CK|pg||mc|9|"
)

PBN = """[Event "test"]
[Board "1"]
[Dealer "S"]
[Deal "S:J4.QT63.KT7642.K 53.K98742.Q.T982 KT62..AJ953.AQ76 AQ987.AJ5.8.J543"]
[Contract "3NT"]
[Declarer "S"]
[Result "9"]
[Auction "S"]
Pass 2H X 2NT
3D Pass 3H Pass
3NT AP
[Play "W"]
CT C6 C5 CK
"""


class LinTest(unittest.TestCase):
    def test_board(self):
        (board,) = parse_lin(LIN)
        self.assertEqual(board["board"], "o1")
        self.assertEqual(board["auction"], AUCTION.format(alert="!"))
        for key, value in EXPECTED.items():
            self.assertEqual(board[key], value, key)
        self.assertEqual(validate_record(board), [])

    def test_passed_out_board_is_skipped(self):
        lin = "qx|o2|md|1SJ4HQT63DKT7642CK,S53HK98742DQCT982,SKT62HDAJ953CAQ76,|mb|p|mb|p|mb|p|mb|p|"
        self.assertEqual(parse_lin(lin), [])


class PbnTest(unittest.TestCase):
    def test_board(self):
        (board,) = parse_pbn(PBN)
        self.assertEqual(board["auction"], AUCTION.format(alert=""))
        for key, value in EXPECTED.items():
            self.assertEqual(board[key], value, key)


if __name__ == "__main__":
    unittest.main()
