# EXP-0182 — PROGRESS

Append-only. Timestamped after every milestone (SUBAGENT_BRIEF: assume the host dies).

## M0 — 2026-08-30 — orientation complete, baseline gate reproduced

Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md` §3, `tools/agx-isa/isadb.py:instr_length`,
EXP-0180 `analysis/{db_defects,length_rule}.json`, EXP-0181 `RESULTS.md` §3.3 +
`analysis/anchor_reachability.py`, EXP-0175 `analysis/ab_gate.py`.

* **Baseline corpus gate reproduced EXACTLY**: `clean=833/1080 leftover=388604 tokens=25419`.
* **DEF-0181-2 reproduced exactly** against the live `tools/agx-isa` (before any edit):

| descriptor | anchor | declared len | `instr_length` | `decode_one` |
|---|---|---:|---|---|
| `bf_add_dst`  | `21001c001100c081`     | 8  | **2**    | `operand_word` |
| `bf_fma_dst`  | `21001e0086041000c081` | 10 | **2**    | `operand_word` |
| `hminmax`     | `22001c0010c0`         | 6  | **10**   | truncated (need 10, have 6) |
| `cvt_bf16`    | `0101148105024000`     | 8  | **None** | unknown length (byte0=0x01) |
| `cvt_f2h_dst` | `c10114810402`         | 6  | **None** | unknown length (byte0=0xc1) |
| `cvt_f2h` (control) | `110114810402`   | 6  | 6        | `cvt_f2h` ✅ |

* **EXP-0180 is COMPLETE, not still running** (its `PROGRESS.md` M11 + `RESULTS.md` +
  `analysis/length_rule.json` are on disk). Its DEF-0180-2 hardware verdict has LANDED:
  the measured half-ALU length rule is keyed on `(byte+2 & 7, byte+4 & 3)` and BOTH
  `db.json`'s stated rule (wrong in 25/32 cells) and `isadb.py`'s implemented rule
  (wrong in 18/32) disagree with it. Coordination point, not a pre-emption.

Next: M1 = re-derive each defect from committed `raw/` before touching `isadb.py`.

## M1 — 2026-08-30 — every defect RE-DERIVED from committed raw, before any edit

* **DEF-0181-2 survives re-derivation, all five.** Each anchor was located in committed
  append-only raw with `outcome: ok, match: true` and a **host-computed semantic oracle**,
  not a hash comparison:
  `bf_add_dst` / `bf_fma_dst` / `hminmax` in `EXP-0156/raw/g17p-20260830-bf03/sweep.jsonl`
  (G17P; notes "host oracle = exact bf16 of a+b" / "of a*b+c" / "exact fp16 of max(a,b)"),
  and `cvt_bf16` / `cvt_f2h_dst` in
  `EXP-0162/raw/g17p_20260829_run01__{cvt_bf16,cvt_f2h_dst}/sweep.jsonl` (G17P, "unmutated
  carrier"; `cvt_bf16` also `ok` on M4 in EXP-0144). The same three EXP-0156 anchors appear
  in that run's `00_inputs.json` `raw_sites` as the lifted instruction at a named offset.
* **The desync is visible in our own compiled carrier.** `00_inputs.json`'s
  `carrier_tokens.bfadd` is the tokenizer's own walk of the 80-byte `bf_add.metal` main: it
  splits the 8-byte bfloat add at off 32 into `operand_word`(2) + `mov_imm`(2) +
  `cvt_f2h`(6) — the last of which runs past the instruction — and every token after it is
  garbage. `carrier_tokens.hmax` shows the same for `hminmax`: `n2_op10`, length 10, eating
  the following two ops.
* **DEF-0180-7 confirmed independently.** `100d0411891500c0` (dst r1) decodes as
  `half_alu_ext8`; `700d0411891500c0` — the SAME instruction at dst r7, which EXP-0180 ran
  on G17P — has no length and no decode. `00021c0300c0` is still called `pad_operand`.
* **DEF-0180-2's contradiction re-derived, and it is worse than "two rules disagree".** Both
  are wrong: `analysis/opsel_length_map.py` and EXP-0180's `length_rule.json` agree the code
  rule is wrong in 18 of 32 cells and `db.json`'s in 25 of 32.

## M2 — 2026-08-30 — general instruments built (before the fix)

* `analysis/collect_anchors.py` → **255 HW anchors over 95 mnemonics**, under a frozen
  selection rule (R-A1..R-A5). `analysis/anchor_decode_test.py` baseline: **245/255 pass,
  10 fail** — the defect is not five accidents.
* `analysis/family_gate_audit.py`: of **74** descriptors whose own `match` leaves byte0's
  high nibble free, **17** decode at only some destination nibbles.
* `analysis/opsel_length_map.py` derives, from `db.json` alone, that in the low-nibble-2
  family **six** op-selects (0x05, 0x06, 0x0e, 0x15, 0x16, 0x1c) have exactly one
  db.json-implied length that `instr_length` gets wrong at most destinations. `hminmax`'s
  0x1c is one of them — 2 of 16 nibbles, as EXP-0181 reported.

## M3 — 2026-08-30 — candidates measured. FIVE PATCHES PASS, ONE FAILS AND IS NOT APPLIED

| candidate | clean | leftover | tokens | roundtrip |
|---|---:|---:|---:|---|
| baseline | 833 | 388604 | 25419 | 302 OK / ALL PASS |
| `n1`+`r9` (low-nibble-1) | **838** | **387924** | 25518 | 302 OK / ALL PASS |
| `n2` (opsel 0x1c) | 833 | 388604 | 25420 | 302 OK / ALL PASS |
| `n2b` (opsel 0x06/0x0e/0x16) | **834** | **388416** | 25453 | 302 OK / ALL PASS |
| `n2c` (opsel 0x05/0x15) | 833 | **388588** | 25421 | 302 OK / ALL PASS |
| `n0c` (DEF-0180-7 gate, agreed cells) | 833 | 388604 | 25419 | 302 OK / ALL PASS |
| **`n0m` (EXP-0180's measured formula verbatim)** | **816** | **391824** | 24965 | 302 OK / ALL PASS |
| **combined** | **840** | **387496** | 25587 | 302 OK / ALL PASS |

* **`n0m` REGRESSES the corpus gate hard** (−17 clean files, +3,220 leftover bytes) and is
  **REPORTED, NOT APPLIED** per the frozen T2 rule. That is a real tension between EXP-0180's
  G17P measurement and the M4 own-MSL corpus, not a defect in either.
* Combined candidate: **4 of the 5 anchors now decode, 0 regressions.**
* `cvt_bf16` is BLOCKED on `db.json`, not on `isadb.py`: its `match` pins byte+4 to `0x01`,
  the anchor carries `0x05`, and EXP-0162 measured on hardware that `0x01` is **not** one of
  the 52 accepted values. `analysis/demo_cvt_bf16_dbfix.py` shows relaxing `[32,8,1]` to
  `[32,1,1]` makes the anchor decode as `cvt_bf16` **with zero corpus change**. Not applied.

## M4 — 2026-08-30 — FIX APPLIED to tools/agx-isa/isadb.py. All gates pass. isadb.py is STABLE.

Applied: `n1 r9 n2 n2b n2c n0c` (`python3 analysis/apply_fix.py --inplace ../../tools/agx-isa
n1 r9 n2 n2b n2c n0c`). `work/tree_before/` holds the pristine pre-fix tree so every
candidate is still reproducible; `work/cand_check` rebuilt from it is byte-identical to the
applied file.

| gate | frozen threshold | before | after | verdict |
|---|---|---:|---:|---|
| T2 corpus clean | ≥ 833 | 833 | **840** | PASS (+7) |
| T2 corpus leftover | ≤ 388604 | 388604 | **387496** | PASS (−1108) |
| T2 tokens | reported | 25419 | 25587 | +168 |
| T3 round trip (subprocess) | 0 FAIL, ALL PASS, OK ≥ 302 | 302/0/ALL PASS | **302/0/ALL PASS** | PASS |
| T4 HW-anchor regression corpus | 0 regressions | 245/255 | **249/255** | PASS (4 fixed, 0 regressed) |
| T5 `validate_labels.py` | exit 0 | exit 0 | **exit 0** | PASS |
| T1 the five anchors | 5, or blocked by a db.json match | 0/5 | **4/5** | 4 PASS, `cvt_bf16` BLOCKED on db.json |
| T6 emittability | must not change | 55 (HEAD moved) | **55** | PASS — `emit_worklist.py` never imports isadb |

Also: op-selects where db.json is unambiguous and `instr_length` disagrees **6 → 0**;
descriptors decoding at all 16 destination nibbles **54 → 57**, family-gated **17 → 15**;
decode→assemble re-emit is **byte-identical for all five** now-decoding anchors;
`gen_encoding_tables.py`, `gen_agx3_xml.py`, `match_overlap_report.py`, `emit_worklist.py`
all still exit 0.

**Two candidates MEASURED AND REFUSED (T2), both reported rather than forced:**
* `n0m` — EXP-0180's HW-measured half-ALU length rule applied verbatim: **816 clean
  (−17), 391824 leftover (+3220)**.
* `r9g` / `r9s` — enforcing the R9 trailing-word closure's own documented contract
  generally (`r9g`: 759 clean, −81; +39,878 bytes) or scoped to byte0 low-nibble 2
  (`r9s`: 838 clean, −2; +11,630 bytes). The narrow low-nibble-1 guard that IS applied
  is the "narrower guard" EXP-0165 asked for, and it improves the gate.

**`tools/agx-isa/isadb.py` IS STABLE — no further edits planned.**

## M5 — 2026-08-30 — deliverables written; two housekeeping facts recorded; DONE

`README.md`, `RESULTS.md`, `manifest.json` written; `analysis/` re-run end to end and
`analysis/apply_fix.py` verified to rebuild the applied `tools/agx-isa/isadb.py` byte for byte.

* **`docs/isa/agx3.xml` and `docs/isa/encoding-tables.md` are stale relative to `db.json`,
  and were already stale before this experiment.** A smoke test of the committed generators
  rewrote them; reverted immediately (`docs/` is the orchestrator's) and then measured:
  regenerating from the pre-fix and post-fix trees gives **byte-identical** output, so this
  change does not affect them. Diff kept at `work/docs_regen_effect.diff`. `docs/` is clean.
* **Commit `20613a44 exp(0178)` swept this in-progress experiment directory into the repo**,
  including eight ~1.3 MB candidate tool copies under `work/`. Pruned to
  `work/candidate_isadb/*.py` plus a rebuild command; the deletions in the working tree are
  intentional.
* Two more experiments appeared alongside mine (`EXP-0183-halfalu-descriptor`,
  `EXP-0184-g17p-onefield-b`). Untouched.

**`tools/agx-isa/isadb.py` IS STABLE.** Final state: `500db91a6077cd1968570dd1f7c08ae2…`,
patches `n1 r9 n2 n2b n2c n0c`, corpus **840/1080 clean, 387496 leftover**, round trip
**302 OK / ALL PASS**, HW-anchor corpus **249/255 (4 fixed, 0 regressed)**,
`validate_labels.py` exit 0.
