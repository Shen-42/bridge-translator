# Bridge Translator

Bridge Translator turns short Bridge game records into plain English that a beginner can follow.

Bridge players write down games in a compact shorthand. A line like `North 1NT - East Pass - South 3NT` tells an experienced player a lot about each hand, but a newcomer sees only letters and numbers. This project reads that shorthand and explains it in full sentences.

## Why I built this

Bridge notation is short because experienced players already know what each bid implies. A beginner doesn't, so reading a game record means looking up every bid. I wanted to see whether a program could fill in that missing knowledge.

The project also tests an idea from language processing: whether translation gets more accurate when you first convert the input into a simple, structured in-between format instead of going straight from shorthand to English. In this project, that in-between format is a small "artificial language" I designed for Bridge.

## How it works

The program works in three steps:

1. **Read** the Bridge record and pick out each event (who bid what, the final contract, the first card played).
2. **Rewrite** each event in the artificial language, adding what the bid usually means. For example, `1NT` becomes `OPEN(North, 1NT, balanced, 15-17_HCP)`.
3. **Write** English sentences from the artificial language.

Because each step is separate, a wrong output can be traced back to the step that caused it.

## Example

Running the demo translates a Bridge record like this:

```text
Input:
  Auction: North 1NT - East Pass - South 3NT - West Pass - North Pass - East Pass
  Contract: 3NT by North
  Opening lead: West S4

Artificial language:
  OPEN(North, 1NT, balanced, 15-17_HCP)
  PASS(East)
  RAISE_TO_GAME(South, 3NT)
  PASS(West)
  PASS(North)
  PASS(East)
  CONTRACT(3NT, declarer=North)
  LEAD(West, S4)

English:
  North opens 1NT, showing a balanced hand with about 15-17 high-card points.
  East passes. South raises directly to 3NT, which is a game-level no-trump
  contract. West passes. North passes. East passes. The final contract is 3NT
  by North. West leads the four of spades to begin the play.
```

## Results

I compared seven approaches on 15 held-out test examples. The main comparison is between writing English straight from the shorthand and writing it from the artificial language:

| Approach | Facts kept | Bridge meaning (out of 5) | Readability (out of 5) |
|---|---:|---:|---:|
| Straight from shorthand | 74% | 2.86 | 5.00 |
| From artificial language (template) | 89% | 4.77 | 4.95 |

Going through the artificial language kept more of the original facts and explained more of what the bids mean, with almost no loss in readability. Full results for all seven approaches are in the paper (`paper/Translating_Bridge.pdf`).

## Requirements

- Python 3.9 or newer
- Git

No API keys or environment variables are needed. The "model" approaches are simulated, so everything runs offline.

## Clone and run

1. Clone the repository and move into it:

   ```bash
   git clone https://github.com/Shen-42/bridge-translator.git
   cd bridge-translator
   ```

2. (Optional) Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # macOS / Linux
   .venv\Scripts\activate           # Windows
   ```

3. Run the demo from the repository root:

   ```bash
   python scripts/demo.py
   ```

   This prints the input record, its artificial-language version, and the English translation.

All paths in the scripts are relative to the repository root, so run the commands from the `bridge-translator/` folder.

## Run the tests

The evaluation scripts score every approach against the hand-written reference answers.

Run on the test set (the numbers reported above):

```bash
python scripts/run_test.py
```

Run on the development set (used for debugging during development):

```bash
python scripts/run_dev.py
```

Each script prints a score table for all seven approaches. Saved outputs and summaries from earlier runs are in `reports/`.

## Repository layout

```text
bridge-translator/
├── data/                  # train/dev/test examples (JSON)
├── src/bridge_translator/ # parser, artificial language, generators, evaluation
├── scripts/               # demo and evaluation scripts
├── reports/               # saved dev/test outputs
├── paper/                 # final paper (PDF) and LaTeX source
└── examples/              # sample input and output
```

## Known issues

- **The "model" approaches are simulated.** They imitate how a language model might write, but no real model is called. The results say nothing yet about how GPT-style models would perform.
- **The dataset is small and hand-built.** It has 90 examples (60 train, 15 dev, 15 test), all written by me. Real game records are messier.
- **Scores are automatic estimates.** Readability and Bridge meaning are measured with simple rules, not by people.
- **Awkward phrasing in the simulated model.** It writes "After 1 pass, the auction continues" after single passes, and "After 3 passes, the auction continues" even when three passes end the auction.
- **The shorthand-only model drops details.** For example, it can write "West J" and leave out the suit of the opening lead.
- **Parsing is imperfect on harder records.** Records with doubles, redoubles, card play, or finesses don't always match the reference artificial language exactly.
- **Bridge knowledge is basic.** The program gives the most common meaning of each bid and ignores partnership agreements, vulnerability, and scoring.

## To do

- [ ] Compare real language models on shorthand input versus artificial-language input
- [ ] Add real game records to the dataset
- [ ] Run a study where Bridge players score accuracy and beginners score readability
- [ ] Write a formal grammar for the artificial language so badly formed output is caught automatically
- [ ] Add a reverse task: rebuild the original record from the English explanation
- [ ] Add unit tests for the parser and generators
