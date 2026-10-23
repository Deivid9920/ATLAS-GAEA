"""TriviaQA generation for CASSANDRA.

Builds the deterministic subset (seed 42, verifiable answers only)
through cassandra_ns.data.loader and produces greedy continuations
(temperature 0.0, max_new_tokens from config) for every question of a
model. Full transcriptions are appended to
logs/generations_{model}.jsonl keyed by prompt_id, so an interrupted
run resumes without regenerating.

Implementation note (documented deviation): activations and probes run
through TransformerLens hooks, while the free generation uses the same
HF weights through transformers' generate() with KV-cache batching -
on CPU this is an order of magnitude faster than token-by-token
HookedTransformer.generate, and the weights, tokenizer and greedy
decoding are identical.
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
from tqdm import tqdm


def generations_path(cfg: dict, model: str) -> Path:
    return Path("logs") / f"generations_{model}.jsonl"


def _prompt(question: str) -> str:
    return f"Question: {question}\nAnswer:"


def generate_for_model(cfg: dict, model: str, batch_size: int = 16,
                       device: str = "cpu") -> Path:
    from transformers import AutoModelForCausalLM, AutoTokenizer

    from cassandra_ns.data.loader import load_triviaqa_subset

    subset = load_triviaqa_subset(cfg)
    out = generations_path(cfg, model)
    out.parent.mkdir(parents=True, exist_ok=True)

    done: set[str] = set()
    if out.is_file():
        with out.open(encoding="utf-8") as fh:
            for line in fh:
                done.add(json.loads(line)["prompt_id"])
    todo = [r for r in subset if r["question_id"] not in done]

    hf_name = "gpt2" if model == "gpt2" else "EleutherAI/pythia-410m"
    tokenizer = AutoTokenizer.from_pretrained(hf_name)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    hf = AutoModelForCausalLM.from_pretrained(hf_name)
    hf.eval().to(device)

    max_new = int(cfg["generation"]["max_new_tokens"])
    with torch.no_grad():
        for start in tqdm(range(0, len(todo), batch_size),
                          desc=f"generating {model}"):
            batch = todo[start:start + batch_size]
            prompts = [_prompt(r["question"]) for r in batch]
            enc = tokenizer(prompts, return_tensors="pt", padding=True,
                            truncation=True, max_length=128).to(device)
            generated = hf.generate(
                **enc,
                max_new_tokens=max_new,
                do_sample=False,
                num_beams=1,
                temperature=None,
                top_p=None,
                top_k=None,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
            new_tokens = generated[:, enc["input_ids"].shape[1]:]
            texts = tokenizer.batch_decode(new_tokens,
                                           skip_special_tokens=True)
            with out.open("a", encoding="utf-8") as fh:
                for row, text in zip(batch, texts):
                    fh.write(json.dumps({
                        "prompt_id": row["question_id"],
                        "question": row["question"],
                        "answer_value": row["answer_value"],
                        "aliases": row["aliases"],
                        "normalized_aliases": row["normalized_aliases"],
                        "prompt": _prompt(row["question"]),
                        "generation": text,
                    }, ensure_ascii=False) + "\n")

    del hf
    return out


def load_generations(cfg: dict, model: str) -> list[dict]:
    path = generations_path(cfg, model)
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found: run the generation for {model} first "
            "(the notebook guard cell does this automatically)")
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line]
