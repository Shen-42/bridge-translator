"""
llm.py

Real language-model systems, run locally through Ollama (https://ollama.com).

Two inputs are compared with the same instructions and the same model:
- llm_raw: the raw Bridge record (hands, auction, contract, lead, first trick, result)
- llm_al:  the artificial-language lines produced by the parser

Outputs are cached in reports/llm_outputs/<model>__<system>.json together with a
hash of the exact prompt, so evaluation can be re-run without Ollama and a
changed prompt is regenerated rather than silently reused.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from .artificial_language import raw_to_artificial

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "reports" / "llm_outputs"

# Model name -> extra request fields. qwen3:1.7b is a hybrid model, so thinking is switched off;
# qwen3:4b-instruct (Qwen3-4B-Instruct-2507) does not think.
MODELS: Dict[str, Dict[str, object]] = {
    "qwen3:4b-instruct": {},
    "qwen3:1.7b": {"think": False},
}
OPTIONS = {"temperature": 0, "seed": 0, "num_predict": 700, "num_ctx": 4096}

SYSTEM_PROMPT = (
    "You are a bridge teacher. Explain the bridge deal record you are given to a beginner in plain English. "
    "Go through the auction in order and say what each bid, double or redouble means. Then state the final "
    "contract and who is declarer, the opening lead, what happens on the first trick, and how many tricks "
    "declarer took, if the record says. Use only the information in the record and do not invent bids, cards "
    "or results. Write one paragraph of plain prose with no headings, lists or markdown."
)


def raw_prompt(raw: Dict[str, object]) -> str:
    lines = ["Bridge record:"]
    if raw.get("dealer"):
        lines.append(f"Dealer: {raw['dealer']}")
    if raw.get("hands"):
        lines.append("Hands (spades.hearts.diamonds.clubs): " + ", ".join(f"{p} {h}" for p, h in raw["hands"].items()))
    labels = [("auction", "Auction"), ("contract", "Contract"), ("opening_lead", "Opening lead"),
              ("play", "Play"), ("note", "Note"), ("result", "Tricks taken by declarer")]
    lines += [f"{label}: {raw[key]}" for key, label in labels if raw.get(key)]
    return "\n".join(lines)


def al_prompt(raw: Dict[str, object]) -> str:
    return "Bridge record, one event per line in a structured meaning representation:\n" + "\n".join(raw_to_artificial(raw))


PROMPTS = {"llm_raw": raw_prompt, "llm_al": al_prompt}


def chat(model: str, user: str) -> str:
    body = {
        "model": model,
        "stream": False,
        "options": OPTIONS,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        **MODELS[model],
    }
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.load(response)["message"]["content"].strip()


def prompt_hash(model: str, user: str) -> str:
    payload = json.dumps([model, SYSTEM_PROMPT, user, OPTIONS, MODELS[model]], ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def cache_path(model: str, system: str) -> Path:
    return CACHE_DIR / f"{model.replace(':', '_')}__{system}.json"


def load_cache(model: str, system: str) -> Dict[str, Dict[str, str]]:
    path = cache_path(model, system)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def cached_output(model: str, system: str, example: Dict) -> Optional[str]:
    user = PROMPTS[system](example["raw"])
    entry = load_cache(model, system).get(example["id"])
    if entry and entry["prompt_sha"] == prompt_hash(model, user):
        return entry["output"]
    return None


def generate(model: str, system: str, examples: List[Dict]) -> None:
    """Fill the cache for every example that has no up-to-date output."""
    cache = load_cache(model, system)
    path = cache_path(model, system)
    path.parent.mkdir(parents=True, exist_ok=True)
    todo = [e for e in examples if cached_output(model, system, e) is None]
    for i, example in enumerate(todo, 1):
        user = PROMPTS[system](example["raw"])
        try:
            output = chat(model, user)
        except urllib.error.URLError as exc:
            raise SystemExit(f"Could not reach Ollama at {OLLAMA_URL} ({exc}). Is `ollama serve` running?")
        cache[example["id"]] = {"prompt_sha": prompt_hash(model, user), "output": output}
        path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {model} {system}: {i}/{len(todo)} {example['id']}", flush=True)
