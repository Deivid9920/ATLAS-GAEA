"""build_ladder: FASE 2 — construye y congela la escalera n=100.

T1 = the 50 existing ATLAS tasks (seed 42), imported verbatim through
the read-only hook. T2 = 30 mutation-composition tasks (10 families x
3) authored here. T3 = 20 adversarial tasks (10 debug + 5 inverse
spec + 5 invariants). Every canonical solution is proven in ATLAS's
sandbox BEFORE freezing, and every T3 debug bug is proven REAL (its
buggy code must fail its own tests). Freezing emits the suite digest
and chains it: after this event the suite is immutable.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gv.audit.chain import AuditChain  # noqa: E402
from gv.bridge.atlas_hook import AtlasHook, BridgeError  # noqa: E402
from gv.canon import canonical, config_sha256, sha256_canonical  # noqa: E402
from gv.harness.task_ladder import suite_digest  # noqa: E402

# base-family facts, cited honestly where the composition really is a
# member of that family (the graph grounds these atoms)
F_SUM = {"subject": "sum_list", "predicate": "computes",
         "object": "total_of_integers"}
F_MAX = {"subject": "max_in_list", "predicate": "computes",
         "object": "maximum_value"}
F_REV = {"subject": "reverse_string", "predicate": "produces",
         "object": "reversed_string"}
F_VOW = {"subject": "count_vowels", "predicate": "counts",
         "object": "vowel_characters"}
F_PAL = {"subject": "is_palindrome", "predicate": "checks",
         "object": "symmetric_string"}
F_MRG = {"subject": "merge_two_sorted_lists", "predicate": "produces",
         "object": "sorted_union_preserving_order"}
F_DDP = {"subject": "dedupe_preserve_order", "predicate": "preserves",
         "object": "first_occurrences"}
F_SEC = {"subject": "second_largest", "predicate": "computes",
         "object": "second_maximum"}
F_BSR = {"subject": "bsearch", "predicate": "requires",
         "object": "inputs_sorted_ascending"}
F_WRD = {"subject": "count_words", "predicate": "counts",
         "object": "whitespace_tokens"}

# ---------------------------------------------------------------- T2 ----
T2_FAMILIES = ("sum_nested", "merge3", "dedupe_by", "bsearch_insert",
               "count_vowels_acc", "second_smallest", "palindrome_clean",
               "longest_word", "reverse_words", "count_tokens")


def _t2_payload(family: str, variant: int) -> tuple[str, str, str, list]:
    """Returns (prompt, canonical_solution, tests, triplets)."""
    if family == "sum_nested":
        items = [{"v": v} for v in
                 ([3, 1, 4, 1], [2, 7, 1], [5, 5, 5, 5])[variant]]
        flat = [d["v"] for d in items]
        return (f"Write sum_nested(items): total of the 'v' field "
                f"over items={items} (dicts shaped {{'v': x}}).",
                "def sum_nested(items):\n"
                "    return sum(it['v'] for it in items)\n",
                f"assert sum_nested({items}) == {sum(flat)}\n"
                "assert sum_nested([]) == 0\n", [F_SUM])
    if family == "merge3":
        a, b, c = [([1, 4], [2, 6, 9], [3, 5]),
                   ([0, 2, 7], [1], [3, 8]),
                   ([5], [1, 8], [2, 6])][variant]
        merged = sorted(a + b + c)
        return (f"Write merge3(a, b, c) merging three sorted lists. "
                f"a={a} b={b} c={c}",
                "def merge3(a, b, c):\n    import heapq\n"
                "    return list(heapq.merge(a, b, c))\n",
                f"assert merge3({a}, {b}, {c}) == {merged}\n"
                "assert merge3([], [], []) == []\n", [F_MRG])
    if family == "dedupe_by":
        xs = (["A", "b", "a", "C", "B"], ["x", "X", "y"],
              ["k", "K", "K", "k", "m"])[variant]
        expected = _dedupe_by_expected(xs)
        return (f"Write dedupe_by(xs) keeping the first occurrence of "
                f"each word ignoring case. xs={xs}",
                "def dedupe_by(xs):\n    seen = set()\n    out = []\n"
                "    for x in xs:\n        k = x.lower()\n"
                "        if k not in seen:\n            seen.add(k)\n"
                "            out.append(x)\n    return out\n",
                f"assert dedupe_by({xs}) == {expected}\n"
                "assert dedupe_by([]) == []\n", [F_DDP])
    if family == "bsearch_insert":
        xs, t = ([([1, 3, 5, 7], 4), ([2, 4], 1), ([1, 2, 3], 9)]
                 [variant])
        return (f"Write insert_pos(xs, t): the index where t should be "
                f"inserted to keep sorted xs ascending. xs={xs} t={t}",
                "def insert_pos(xs, t):\n    lo, hi = 0, len(xs)\n"
                "    while lo < hi:\n        mid = (lo + hi) // 2\n"
                "        if xs[mid] < t:\n            lo = mid + 1\n"
                "        else:\n            hi = mid\n    return lo\n",
                f"assert insert_pos({xs}, {t}) == "
                f"{_bisect_left(xs, t)}\n"
                f"assert insert_pos([], {t}) == 0\n", [F_BSR])
    if family == "count_vowels_acc":
        s = ("canción", "raíz azul", "murciélago")[variant]
        n = sum(1 for ch in s.lower() if ch in "aeiouáéíóú")
        return (f"Write count_vowels_u(s) counting vowels including "
                f"accented ones (aeiouáéíóú) in s='{s}'.",
                "def count_vowels_u(s):\n    return sum("
                "1 for c in s.lower() if c in 'aeiouáéíóú')\n",
                f"assert count_vowels_u('{s}') == {n}\n"
                "assert count_vowels_u('xyz') == 0\n", [F_VOW])
    if family == "second_smallest":
        xs = ([4, 1, 3, 1], [9, 7], [2, 2, 3, 1])[variant]
        uniq = sorted(set(xs))
        return (f"Write second_smallest(xs): second smallest distinct "
                f"value in xs={xs}.",
                "def second_smallest(xs):\n"
                "    return sorted(set(xs))[1]\n",
                f"assert second_smallest({xs}) == {uniq[1]}\n"
                "assert second_smallest([5, 5, 6]) == 6\n", [F_SEC])
    if family == "palindrome_clean":
        s = ("A man, a plan!", "Ab; ba", "No x in Nixon")[variant]
        clean = "".join(c.lower() for c in s if c.isalnum())
        return (f"Write is_palindrome_clean(s): True iff s='{s}' reads "
                f"the same ignoring punctuation, spaces and case.",
                "def is_palindrome_clean(s):\n"
                "    t = ''.join(c.lower() for c in s if c.isalnum())\n"
                "    return t == t[::-1]\n",
                f"assert is_palindrome_clean('{s}') is "
                f"{'True' if clean == clean[::-1] else 'False'}\n"
                "assert is_palindrome_clean('!!') is True\n", [F_PAL])
    if family == "longest_word":
        ws = (["alpha", "beta", "gamma"], ["a", "bb"],
              ["uno", "dos", "cuatro"])[variant]
        longest = max(ws, key=len)
        return (f"Write longest_word(words) returning the longest word "
                f"(first on ties). words={ws}",
                "def longest_word(words):\n"
                "    return max(words, key=len)\n",
                f"assert longest_word({ws}) == '{longest}'\n"
                "assert longest_word(['hi']) == 'hi'\n", [F_MAX])
    if family == "reverse_words":
        s = ("alpha beta gamma", "hola mundo", "a bb ccc")[variant]
        return (f"Write reverse_words(s): the words of s='{s}' in "
                f"reverse order, single spaces.",
                "def reverse_words(s):\n"
                "    return ' '.join(s.split()[::-1])\n",
                f"assert reverse_words('{s}') == "
                f"'{' '.join(s.split()[::-1])}'\n"
                "assert reverse_words('') == ''\n", [F_REV])
    if family == "count_tokens":
        s = ("hola, mundo!", "uno... dos", "a-b c")[variant]
        n = sum(1 for w in s.split()
                if any(ch.isalnum() for ch in w))
        return (f"Write count_tokens(s): number of words in s='{s}' "
                f"that contain at least one letter or digit.",
                "def count_tokens(s):\n    return sum("
                "1 for w in s.split()\n"
                "                 if any(c.isalnum() for c in w))\n",
                f"assert count_tokens('{s}') == {n}\n"
                "assert count_tokens('---') == 0\n", [F_WRD])
    raise ValueError(f"unknown T2 family {family}")


def _dedupe_by_expected(xs):
    seen, out = set(), []
    for w in xs:
        k = w.lower()
        if k not in seen:
            seen.add(k)
            out.append(w)
    return out


def _bisect_left(xs, t):
    lo, hi = 0, len(xs)
    while lo < hi:
        mid = (lo + hi) // 2
        if xs[mid] < t:
            lo = mid + 1
        else:
            hi = mid
    return lo


def build_t2() -> list[dict]:
    tasks = []
    idx = 0
    for family in T2_FAMILIES:
        for variant in range(3):
            prompt, solution, tests, triplets = _t2_payload(family,
                                                            variant)
            tasks.append({"id": f"T2-{idx:04d}", "tier": "t2",
                          "family": family, "prompt": prompt,
                          "tests": tests,
                          "canonical_solution": solution,
                          "triplets": triplets, "seed": 42})
            idx += 1
    return tasks


# ---------------------------------------------------------------- T3 ----
_DEBUG_BUGS = (
    ("sum_upto", "def sum_upto(xs):\n    total = 0\n"
     "    for i in range(len(xs) - 1):\n        total += xs[i]\n"
     "    return total\n",
     "def sum_upto(xs):\n    total = 0\n"
     "    for i in range(len(xs)):\n        total += xs[i]\n"
     "    return total\n",
     "assert sum_upto([1, 2, 3]) == 6\nassert sum_upto([]) == 0\n"),
    ("append_to", "def append_to(item, acc=[]):\n    acc.append(item)"
     "\n    return acc\n",
     "def append_to(item, acc=None):\n    if acc is None:\n"
     "        acc = []\n    acc.append(item)\n    return acc\n",
     "assert append_to(1) == [1]\n"
     "assert append_to(2) == [2]\n"),
    ("normalize", "def normalize(xs):\n    xs.sort()\n"
     "    return xs\n",
     "def normalize(xs):\n    return sorted(xs)\n",
     "src = [3, 1, 2]\nassert normalize(src) == [1, 2, 3]\n"
     "assert src == [3, 1, 2]\n"),
    ("clamp", "def clamp(x, lo, hi):\n    return min(lo, max(x, hi))"
     "\n",
     "def clamp(x, lo, hi):\n    return max(lo, min(x, hi))\n",
     "assert clamp(5, 0, 3) == 3\nassert clamp(-2, 0, 3) == 0\n"
     "assert clamp(1, 0, 3) == 1\n"),
    ("last_index", "def last_index(xs, t):\n    for i in "
     "range(len(xs)):\n        if xs[i] == t:\n            return i\n"
     "    return -1\n",
     "def last_index(xs, t):\n    for i in range(len(xs) - 1, -1, "
     "-1):\n        if xs[i] == t:\n            return i\n"
     "    return -1\n",
     "assert last_index([1, 2, 1], 1) == 2\n"
     "assert last_index([1, 2], 9) == -1\n"),
    ("average", "def average(xs):\n    return sum(xs) // len(xs)\n",
     "def average(xs):\n    return sum(xs) / len(xs)\n",
     "assert average([1, 2]) == 1.5\nassert average([2, 2]) == 2.0\n"),
    ("total_orders", "def total_orders(prices):\n    for p in "
     "prices:\n        total = 0\n        total += p\n"
     "    return total\n",
     "def total_orders(prices):\n    total = 0\n    for p in "
     "prices:\n        total += p\n    return total\n",
     "assert total_orders([2, 3]) == 5\n"
     "assert total_orders([]) == 0\n"),
    ("double_all", "def double_all(xs):\n    for x in xs:\n"
     "        x = x * 2\n    return xs\n",
     "def double_all(xs):\n    return [x * 2 for x in xs]\n",
     "assert double_all([1, 2]) == [2, 4]\n"
     "assert double_all([]) == []\n"),
    ("any_negative", "def any_negative(xs):\n    for x in xs:\n"
     "        if x < 0:\n            return True\n"
     "        else:\n            return False\n",
     "def any_negative(xs):\n    return any(x < 0 for x in xs)\n",
     "assert any_negative([1, -2]) is True\n"
     "assert any_negative([1, 2]) is False\n"
     "assert any_negative([]) is False\n"),
    ("merge_counts", "def merge_counts(a, b):\n    return {**a, **b}"
     "\n",
     "def merge_counts(a, b):\n    out = dict(a)\n"
     "    for k, v in b.items():\n        out[k] = out.get(k, 0) + v\n"
     "    return out\n",
     "assert merge_counts({'a': 1}, {'a': 2, 'b': 1}) == "
     "{'a': 3, 'b': 1}\nassert merge_counts({}, {}) == {}\n"),
)

_INVERSE_SPECS = (
    ("running_max", "Write running_max(xs): the list of running "
     "maxima of xs=[1, 3, 2, 5, 4].",
     "def running_max(xs):\n    out = []\n    best = None\n"
     "    for x in xs:\n        best = x if best is None else "
     "max(best, x)\n        out.append(best)\n    return out\n",
     "assert running_max([1, 3, 2, 5, 4]) == [1, 3, 3, 5, 5]\n"
     "assert running_max([]) == []\n"),
    ("title_words", "Write title_words(s): every word of s='hola "
     "mundo' starts uppercase.",
     "def title_words(s):\n    return ' '.join(w.capitalize() for w "
     "in s.split())\n",
     "assert title_words('hola mundo') == 'Hola Mundo'\n"
     "assert title_words('') == ''\n"),
    ("first_unique", "Write first_unique(xs, k): the first k distinct "
     "elements of xs=[1, 2, 1, 3, 2] in order, k=3.",
     "def first_unique(xs, k):\n    out = list(dict.fromkeys(xs))\n"
     "    return out[:k]\n",
     "assert first_unique([1, 2, 1, 3, 2], 3) == [1, 2, 3]\n"
     "assert first_unique([1], 5) == [1]\n"),
    ("group_pairs", "Write group_pairs(pairs) grouping second "
     "elements by the first: pairs=[('a', 1), ('b', 2), ('a', 3)].",
     "def group_pairs(pairs):\n    out = {}\n"
     "    for k, v in pairs:\n        out.setdefault(k, []).append(v)"
     "\n    return out\n",
     "assert group_pairs([('a', 1), ('b', 2), ('a', 3)]) == "
     "{'a': [1, 3], 'b': [2]}\n"
     "assert group_pairs([]) == {}\n"),
    ("run_length", "Write run_length(s): compress runs of s='aaabb' "
     "as letter followed by count.",
     "def run_length(s):\n    out = []\n    i = 0\n"
     "    while i < len(s):\n        j = i\n"
     "        while j < len(s) and s[j] == s[i]:\n            j += 1\n"
     "        out.append(s[i] + str(j - i))\n        i = j\n"
     "    return ''.join(out)\n",
     "assert run_length('aaabb') == 'a3b2'\n"
     "assert run_length('') == ''\n"),
)

_INVARIANTS = (
    ("involution", "Complete the body marked ____ so that "
     "revprop(revprop(s)) == s for every string, including ''.",
     "def revprop(s):\n    return ____\n",
     "def revprop(s):\n    return s[::-1]\n",
     "for s in ('', 'a', 'ab', 'abc', 'abba'):\n"
     "    assert revprop(revprop(s)) == s\n"),
    ("is_sorted", "Complete the body marked ____ so is_sorted(xs) is "
     "True iff xs never decreases.",
     "def is_sorted(xs):\n    return ____\n",
     "def is_sorted(xs):\n    return all(xs[i] <= xs[i + 1] for i in "
     "range(len(xs) - 1))\n",
     "assert is_sorted([1, 2, 2, 3]) is True\n"
     "assert is_sorted([2, 1]) is False\n"
     "assert is_sorted([]) is True\n"),
    ("stable_dedupe", "Complete the body marked ____ so "
     "stable_dedupe keeps first occurrences in order.",
     "def stable_dedupe(xs):\n    return ____\n",
     "def stable_dedupe(xs):\n    return list(dict.fromkeys(xs))\n",
     "assert stable_dedupe([3, 1, 3, 2]) == [3, 1, 2]\n"
     "assert stable_dedupe([]) == []\n"),
    ("sum_seconds", "Complete the body marked ____ so sum_seconds "
     "adds the second element of every pair.",
     "def sum_seconds(pairs):\n    return ____\n",
     "def sum_seconds(pairs):\n    return sum(b for _, b in pairs)\n",
     "assert sum_seconds([('a', 1), ('b', 2)]) == 3\n"
     "assert sum_seconds([]) == 0\n"),
    ("flatten_once", "Complete the body marked ____ so flatten_once "
     "removes exactly one level of nesting.",
     "def flatten_once(nested):\n    return ____\n",
     "def flatten_once(nested):\n    return [x for row in nested for "
     "x in row]\n",
     "assert flatten_once([[1, 2], [3], []]) == [1, 2, 3]\n"
     "assert flatten_once([]) == []\n"),
)


def build_t3() -> list[dict]:
    tasks = []
    idx = 0
    for family, buggy, fixed, tests in _DEBUG_BUGS:
        prompt = (f"The function below has a subtle bug. Fix it so "
                  f"the asserts pass.\n{buggy.strip()}")
        tasks.append({"id": f"T3-{idx:04d}", "tier": "t3",
                      "family": f"debug_{family}", "prompt": prompt,
                      "tests": tests, "canonical_solution": fixed,
                      "triplets": [], "seed": 42,
                      "buggy_code": buggy.strip()})
        idx += 1
    for family, prompt, fixed, tests in _INVERSE_SPECS:
        tasks.append({"id": f"T3-{idx:04d}", "tier": "t3",
                      "family": f"spec_{family}", "prompt": prompt,
                      "tests": tests, "canonical_solution": fixed,
                      "triplets": [], "seed": 42})
        idx += 1
    for family, prompt, skeleton, fixed, tests in _INVARIANTS:
        full_prompt = f"{prompt}\n{skeleton.strip()}"
        tasks.append({"id": f"T3-{idx:04d}", "tier": "t3",
                      "family": f"inv_{family}", "prompt": full_prompt,
                      "tests": tests, "canonical_solution": fixed,
                      "triplets": [], "seed": 42})
        idx += 1
    return tasks


def main() -> int:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    hook = AtlasHook(config, ROOT)
    chain_path = ROOT / "logs" / "audit.jsonl"
    chain = AuditChain.load(chain_path) if chain_path.exists() \
        else AuditChain()

    try:
        ident = hook.verify_identity(config)
        print(json.dumps({"step": "identity", "git_head":
                          ident["git_head"]}))

        # T1 verbatim from ATLAS
        t1_raw = hook.build_t1(n=50, seed=42)
        t1 = [{"id": t["id"], "tier": "t1", "family": t["family"],
               "prompt": t["prompt"], "tests": t["tests"],
               "canonical_solution": t["canonical_solution"],
               "triplets": t["triplets"], "seed": t["seed"]}
              for t in t1_raw]
        assert len(t1) == 50

        t2 = build_t2()
        t3 = build_t3()
        assert len(t2) == 30 and len(t3) == 20

        # every canonical solution must pass in ATLAS's sandbox, and
        # every T3 debug bug must be REAL (its buggy code fails)
        for tier, tasks in (("t2", t2), ("t3", t3)):
            for task in tasks:
                res = hook.run_tests(task["canonical_solution"],
                                     task["tests"])
                if not res["passed"]:
                    raise RuntimeError(
                        f"{task['id']} canonical fails its own tests: "
                        f"{res['stderr_tail'][:200]}")
        for task in t3:
            if "buggy_code" in task:
                res = hook.run_tests(task["buggy_code"], task["tests"])
                if res["passed"]:
                    raise RuntimeError(
                        f"{task['id']} bug is NOT real: buggy code "
                        f"passed its tests")
        print(json.dumps({"step": "canonical_validation", "t2": 30,
                          "t3": 20, "bugs_real": 10}))

        profile = ROOT / "profiles" / "code_qa"
        frozen_utc = datetime.now(timezone.utc).isoformat(
            timespec="seconds")
        tiers = {"t1": t1, "t2": t2, "t3": t3}
        digests = {}
        for tier, tasks in tiers.items():
            for task in tasks:
                task["task_sha256"] = sha256_canonical(
                    {k: task[k] for k in ("id", "family", "prompt",
                                          "tests",
                                          "canonical_solution")})
            digests[tier] = suite_digest(tasks)
            doc = {"tier": tier, "n": len(tasks),
                   "digest": digests[tier], "frozen_utc": frozen_utc,
                   "tasks": tasks}
            (profile / f"tasks_{tier}.json").write_text(
                json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8")

        all_tasks = t1 + t2 + t3
        manifest = {"version": 1, "n_total": 100,
                    "counts": {"t1": 50, "t2": 30, "t3": 20},
                    "t1_digest": digests["t1"],
                    "t2_digest": digests["t2"],
                    "t3_digest": digests["t3"],
                    "suite_digest": suite_digest(all_tasks),
                    "frozen_utc": frozen_utc,
                    "atlas_git_head": config["identities"][
                        "atlas_git_head"]}
        (profile / "suite_manifest.json").write_text(
            canonical(manifest) + "\n", encoding="utf-8")

        chain.append({"action": "t1_imported",
                      "digest": digests["t1"], "n": 50,
                      "source_head": ident["git_head"]})
        chain.append({"action": "suite_frozen",
                      "suite_digest": manifest["suite_digest"],
                      "t1_digest": digests["t1"],
                      "t2_digest": digests["t2"],
                      "t3_digest": digests["t3"], "n_total": 100,
                      "canonical_solutions_verified": 50,
                      "bugs_proven_real": 10})
        chain.save(chain_path)
        print(json.dumps({"step": "frozen",
                          "suite_digest": manifest["suite_digest"]}))
        return 0
    finally:
        hook.close()


if __name__ == "__main__":
    raise SystemExit(main())
