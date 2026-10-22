# FASE 4 — MCTS + self-play: measured verification

- date-run: deterministic protocol, seed 42; engine: heph (weights sha256 499e8c5313f33522...)
- suite: 50 code_qa tasks, integrated tests, sandboxed execution
- total wall time: 204.8s; budget: fast (30s cap), max_iters 3

## 1. Accuracy: nano-solo vs ATLAS (50 tasks)

| mode | accuracy |
|------|----------|
| nano-solo (1 generation, no search, no verifier) | 0.00% |
| ATLAS (retrieval + MCTS + composite verifier) | 100.00% |
| **delta (ATLAS - nano-solo)** | **+100.00%** |
| ATLAS with RANDOM pruning (baseline) | 50.00% |

## 2. Pruning: verifier vs random (nodes explored)

| mode | nodes evaluated | accuracy |
|------|-----------------|----------|
| verifier pruning (score < 0.35) | 200 | 100.00% |
| random pruning (seeded coin, same floor) | 400 | 50.00% |
| **node reduction (verifier vs random)** | **50.0%** | |

## 3. Per-family detail (n / nano / atlas / random)

| family | n | nano-solo | ATLAS | random-prune |
|--------|---|-----------|-------|--------------|
| binary_search_index | 5 | 0 | 5 | 0 |
| count_vowels | 5 | 0 | 5 | 5 |
| count_words | 5 | 0 | 5 | 0 |
| dedupe_preserve_order | 5 | 0 | 5 | 0 |
| is_palindrome | 5 | 0 | 5 | 5 |
| max_in_list | 5 | 0 | 5 | 5 |
| merge_two_sorted | 5 | 0 | 5 | 5 |
| reverse_string | 5 | 0 | 5 | 0 |
| second_largest | 5 | 0 | 5 | 0 |
| sum_list | 5 | 0 | 5 | 5 |

## 4. Provenance & honesty notes

- The champion is the REGENERATED nano (the original was lost in the 5th sandbox reset): 508k training tokens, holdout ppl 3028.7 fp32, holdout digest matches the frozen anchor 62d8992a3add.... The nano is deliberately small — deltas here measure the SYSTEM (search + verification + retrieval), not the nano.
- Expansion uses heph generate (fp32) — this engine build applies int8/ternary at runtime only in bench; the config modes are recorded but generation is fp32 (measured, honest).
- Node evaluation is memoized (#19): identical candidates hit the cache; nodes_evaluated counts cache hits + misses.
- RFT corpus (clean by construction): 50 verified records -> artifacts/selfplay/corpus_rft.jsonl.
- Graph growth: verified families append triplets with explicit causes -> profiles/code_qa/graph_versions.json.
