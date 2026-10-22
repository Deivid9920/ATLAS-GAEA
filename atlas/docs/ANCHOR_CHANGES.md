# ANCHOR CHANGES — recorded modifications (anchor-editing policy)

Policy in force: tests are the spec; anchors are never edited to make an
implementation pass; every deviation from the specification package is
recorded here with its justification.

| # | File | Change | Justification | Authorization |
|---|------|--------|---------------|---------------|
| 1 | `config.yaml` | `ceiling_params: 7.0e9` → `7.0e+9` | YAML 1.1 float resolver requires a signed exponent; `7.0e9` loads as **string** under `yaml.safe_load`, and `test_lineage_growth_keys` (`ceiling_params > 285e6`) requires a number. | Defect fix approved by the user in the ATLAS authorization block (fix #1, YAML 1.1 float trap); recorded per policy. |
| 2 | `Makefile` | Whitespace normalized to real recipe tabs | PDF layout extraction flattened tabs to spaces; `make` requires tabs. Target set unchanged (pinned by `test_makefile_targets`). | Reconstruction authorized (ATLAS-0: "5 autorías de reconstrucción autorizables bajo precedente V2.1"). |
| 3 | `README.md` | Quickstart lines un-glued (`make demomake` → `make demo` + `make mcp-serve`) | PDF line-wrap artifact; content otherwise verbatim. | Same reconstruction authorization. |
| 4 | `scripts/scaffold.py` | Missing head reconstructed: `ROOT`, 17 of 28 stub contracts; mangled `main()` indentation restored | PDF source truncated mid-file (Archivo 14). Visible 11 stub contracts kept verbatim; authored stubs follow the same contract style and the FASE 0-6 module map. | Same reconstruction authorization. |
| 5 | `atlas_ns/verify/composite.py` | Missing head reconstructed: module docstring, imports, `APPROVE/REVISE/BLOCK/ABSTAIN`, `Verdict`, `CompositeDecision`, `__init__`, `register`, `signature`, `evaluate` head incl. BLOCK short-circuit | PDF truncated (Archivo 5). Every pinned behavior taken from the complete `tests/test_verify_composite.py` (7 tests). | Same reconstruction authorization. |
| 6 | `atlas_ns/orchestrator/machine.py` | Missing head reconstructed: imports, `Status`, `IllegalTransition`, `Action`, `Task` (+`to_record`/`from_record`), `step` signature & terminal/crash guards | PDF truncated (Archivo 9). Pinned by the complete `tests/test_orchestrator_machine.py` (7 tests). | Same reconstruction authorization. |
| 7 | `atlas_ns/lineage/rules.py` | Missing head reconstructed: imports, `ExpansionMetrics`, `GrowthRules`, `GrowthDecision` | PDF truncated (Archivo 11). Pinned by the complete `tests/test_lineage_rules.py` (7 tests). | Same reconstruction authorization. |
| 8 | `tests/test_structure.py` | Missing head reconstructed: imports, `REPO_ROOT`, `REQUIRED_DIRS`, `REQUIRED_FILES`, `CONFIG_KEYS`, `MAKEFILE_TARGETS`, head of `FORBIDDEN_MARKERS` | PDF truncated (Archivo 13). Dir/file/key lists derived from the scaffold's contracted tree (Archivo 14) and `config.yaml` (Archivo 1); visible `FORBIDDEN_MARKERS` tail kept verbatim; visible test bodies kept verbatim. | Same reconstruction authorization. |

**NOT modified**: the 4 test suites (`test_verify_composite`, `test_audit_chain`,
`test_orchestrator_machine`, `test_lineage_rules`) — complete in the PDF and copied
verbatim; `atlas_ns/audit/chain.py` — complete in the PDF and copied verbatim;
`docs/no_goals.md` — complete, verbatim (list formatting only).

| 9 | `atlas_ns/audit/chain.py` | `verify()` uses `entry.get(...)` for `seq/prev/event/hash` so a **missing** field returns `(False, seq)` instead of raising `KeyError` | Defect fix #2 approved by the user: `test_hash_omission_or_reorder_detected` (`del entries[0]["hash"]` → `assert not ok`) fails with the verbatim PDF anchor because `entry["hash"]` raises `KeyError` before verify can report. Tests are the spec. | Defect fix approved in the ATLAS authorization block (fix #2). |
