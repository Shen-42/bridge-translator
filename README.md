# Bridge Translator

Bridge Translator is an NLP system that translates compact Bridge game records into beginner-readable English through a controlled artificial Bridge language.

The project treats Bridge notation as a formal source language. Raw Bridge records are parsed into structured events, converted into a predicate-style artificial language, and then verbalized into English explanations.

## Pipeline

```text
Raw Bridge notation
→ Bridge parser
→ Controlled artificial Bridge language
→ English generator
→ Evaluation
```

## Example

Input:

```text
North 1NT - East Pass - South 3NT - West Pass - North Pass - East Pass
Contract: 3NT by North
Opening lead: West S4
```

Artificial language:

```text
OPEN(North, 1NT, balanced, 15-17_HCP)
PASS(East)
RAISE_TO_GAME(South, 3NT)
PASS(West)
PASS(North)
PASS(East)
CONTRACT(3NT, declarer=North)
LEAD(West, S4)
```

English:

```text
North opens 1NT, showing a balanced hand with about 15–17 high-card points. East passes. South raises directly to 3NT, which is a game-level no-trump contract. West passes. North passes. East passes. The final contract is 3NT by North. West leads the four of spades to begin the play.
```

## Systems Compared

The project compares seven systems:

1. Generic baseline
2. Literal baseline
3. Raw-copy baseline
4. Direct raw model
5. Model + artificial language
6. Template + artificial language
7. Expert template + artificial language

## Dataset

The dataset contains 90 aligned examples:

| Split | Examples | Purpose |
|---|---:|---|
| Train | 60 | Rule/template design |
| Development | 15 | Debugging/error analysis |
| Test | 15 | Final evaluation |

Each example contains raw notation, gold artificial language, gold English, a fact dictionary, and metadata.

## Main Results

Test-set results:

| System | Fact | Meaning | Readability | Reconstructability |
|---|---:|---:|---:|---:|
| Direct raw model | 0.743 | 2.858 | 5.000 | 0.743 |
| Model + artificial language | 0.887 | 4.459 | 4.973 | 0.887 |
| Template + artificial language | 0.887 | 4.766 | 4.947 | 0.887 |

The template system using the artificial language gives the best overall balance of factual preservation, Bridge meaning, beginner readability, and reconstructability.

## Repository Structure

```text
bridge-translator/
├── data/                  # train/dev/test JSON data
├── src/bridge_translator/ # implementation
├── scripts/               # runnable scripts
├── reports/               # dev/test outputs and summaries
├── paper/                 # final PDF and ACL LaTeX source
├── prompts/               # prompt templates for future model experiments
└── examples/              # sample input and output
```

## Run

Clone the repo and run:

```bash
python scripts/demo.py
```

Run evaluation on the test set:

```bash
python scripts/run_test.py
```

Run evaluation on the development set:

```bash
python scripts/run_dev.py
```

## Paper

The final paper is available at:

```text
paper/Translating_Bridge.pdf
```

The ACL LaTeX source is also included in `paper/`.

## Notes

The model-based systems are simulated so the project is fully reproducible without external APIs. The prompt templates in `prompts/` can be used later to compare real language-model generation from raw notation versus the controlled artificial language.
