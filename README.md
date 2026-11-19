# Bridge Translator

Bridge Translator turns short Bridge game records into plain English that a beginner can follow.

Bridge players write down games in a compact shorthand. A line like `North 1NT - East Pass - South 3NT` tells an experienced player a lot about each hand, but a newcomer sees only letters and numbers. This project reads that shorthand and explains it in full sentences.

## Why I built this

Bridge notation is short because experienced players already know what each bid implies. A beginner doesn't, so reading a game record means looking up every bid. I wanted to see whether a program could fill in that missing knowledge.

The project also tests an idea from language processing: whether translation gets more accurate when you first convert the input into a simple, structured in-between format instead of going straight from shorthand to English. In this project, that in-between format is a small "artificial language" I designed for Bridge.

## How it works

The program works in three steps:

1. **Read** the Bridge record and pick out each event (who bid what, the final contract, the first card played).
2. **Rewrite** each event in the artificial language, adding what the bid usually means. For example, `1NT` becomes `OPEN(North, 1NT, balanced, 15-17_HCP)`. Each bid is labelled by who makes it (opening, response, overcall, advance, rebid), openings note third or fourth seat, and each double is classified from the auction as takeout, negative, responsive, penalty, or lead-directing.
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

The main question is whether a language model explains a Bridge record better when it is given the artificial language instead of the raw shorthand. I tested two local Qwen3 models with the same instructions, plus the template generator and three baselines.

The main test set is **40 real boards** from BBO vugraph broadcasts of national and international team events (`data/real_test.json`). Every board's auction pattern is absent from the training data and from the boards used to write the rules. These are contested auctions with overcalls, doubles, slams, and conventions such as Multi 2D and strong clubs.

| Approach | Facts stated | Meanings explained | Invented bids | Reading grade | chrF |
|---|---:|---:|---:|---:|---:|
| Qwen3 4B, raw shorthand | 0.90 | 0.21 | 0.00 | 7.5 | 40.5 |
| Qwen3 4B, artificial language | 0.90 | **0.63** | 0.00 | 8.1 | 41.7 |
| Qwen3 1.7B, raw shorthand | 0.82 | 0.05 | 0.07 | 5.1 | 41.8 |
| Qwen3 1.7B, artificial language | 0.80 | 0.31 | 0.00 | 5.7 | 42.4 |
| Template from artificial language | 1.00 | 0.64 | 0.00 | 3.5 | 52.1 |
| Literal baseline ("North bids 1NT.") | 0.86 | 0.03 | 0.00 | 0.5 | 36.3 |

With the same model and instructions, the artificial language roughly triples the share of bid meanings explained (0.21 to 0.63 for the 4B model, 0.05 to 0.31 for the 1.7B model) without losing facts. The template generator still explains as much as the best model and states every fact, but even it explains only about two thirds of the meanings on real auctions, because real pairs play conventions the rules do not know.

On the 15-example synthetic test set the same pattern holds (4B: 0.17 to 0.83 meanings explained), but the synthetic references follow the template wording, so template scores there are inflated. Full tables are printed by `python scripts/run_test.py` and saved in `reports/`.

## Requirements

- Python 3.9 or newer
- Git
- For evaluation: `pip install -r requirements.txt` (sacrebleu, for BLEU and chrF)
- Optional, to regenerate language-model outputs: [Ollama](https://ollama.com) with `qwen3:4b-instruct` and `qwen3:1.7b`

The translator itself uses only the Python standard library. No API keys are needed: the language models run locally, and their outputs are saved in `reports/llm_outputs/`, so evaluation works offline.

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

The evaluation scripts score every approach on the synthetic set and on the real BBO set.

Run on the test sets (the numbers reported above):

```bash
python scripts/run_test.py          # scores saved language-model outputs
python scripts/run_test.py --llm    # also generates any missing outputs with Ollama
```

Run on the development sets (used while writing the rules):

```bash
python scripts/run_dev.py
```

Each script prints a score table per split. Saved outputs and summaries are in `reports/`.

Metrics:

| Metric | What it measures |
|---|---|
| facts | Key facts (opener, contract, declarer, lead, tricks, auction order) stated in the right role |
| meaning | Annotated meanings explained, e.g. "West's 2H is a Michaels cue-bid" |
| unsup. | Bids the output mentions that never happened (hallucination check; lower is better) |
| FK | Flesch–Kincaid grade level (lower is easier to read) |
| BLEU, chrF | Similarity to the reference explanation (sacrebleu) |

Run the unit tests (parser, generator, and the legality checker, which also checks every record in `data/`):

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

## Repository layout

```text
bridge-translator/
├── data/                  # synthetic train/dev/test and real BBO real_dev/real_test (JSON)
├── src/bridge_translator/ # parser, artificial language, generators, evaluation
├── scripts/               # demo, evaluation, and real-dataset builder
├── tests/                 # unit tests (unittest)
├── reports/               # saved outputs, summaries, and language-model outputs
├── paper/                 # final paper (PDF) and LaTeX source
└── examples/              # sample input and output
```

## Known issues

- **The real-data references were machine-drafted.** The 40 reference explanations and meaning annotations in `data/real_test.json` were written by Claude from the raw records, before any system was run on that split. I reviewed and approved every one, but a second Bridge player has not checked them.
- **The synthetic dataset is small and hand-built.** It has 90 examples covering seven auction patterns, and its reference English follows the template wording, so template scores on it are inflated.
- **Scores are automatic.** Facts and meanings are checked by matching words in sentences, not by people.
- **Bidding rules are simple Standard American.** Real pairs play other systems: a 2C opening may be natural, 1C may be a strong club, and many alerted calls can only be described as "artificial". Vulnerability and scoring are ignored.
- **Only small local models are tested.** Qwen3 4B and 1.7B run on a laptop; larger models may behave differently.

## To do

- [x] Compare real language models on shorthand input versus artificial-language input
- [x] Add real game records to the dataset
- [x] Review every real-data reference
- [ ] Have a second Bridge player check the references
- [ ] Run a study where Bridge players score accuracy and beginners score readability
- [ ] Write a formal grammar for the artificial language so badly formed output is caught automatically
- [ ] Add a reverse task: rebuild the original record from the English explanation
- [x] Add unit tests for the parser and generators
