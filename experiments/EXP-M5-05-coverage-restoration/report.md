# EXP-M5-05 — M5 ISA coverage restoration (fork the A18 DB, fix G17g deltas)

**Goal (Phase 1.3, compile-only):** restore ISA tokenization coverage on the M5 by forking the
A18/G17P instruction DB and fixing the G17P→G17g length-rule / leader deltas, validated purely by
re-census + round-trip (no GPU dispatch). Ground truth = the two M5 corpora; a wrong length rule
*increases* desync, so the metric cannot be gamed.

## The fork
`tools/agx-isa-m5/` — the M5 (Apple10/G17g) DB, forked from `tools/agx-isa/` (A18/G17P, left
pristine). 170 descriptors (`db.json`), `isadb.py` 6441→6539 lines. **The win is overwhelmingly
length-rule fixes, not new descriptors** (~+1 descriptor, ~+98 lines of `instr_length` rules) —
confirming the census diagnosis that the G17P→G17g delta is mostly length-rule divergence in a
handful of low-nibble families (`_6 _e _0 _f _7`), plus a few relocated match bits.

## Result — validated on BOTH corpora (hard-timed census, per-file watchdog)
| corpus | before (G17P DB) | after (M5 fork) |
|---|---|---|
| own (842 uniq) | 84.23% byte-cov / 15.77% desync | **96.55% byte-cov** (named 85.14%, desync 3.45%) |
| third-party (708 uniq) | 86.06% / 13.94% | **97.98% byte-cov** (named 90.86%, desync 2.02%) |

- **Round-trip: ALL PASS** — the new/edited encodings are self-consistent (`assemble(disassemble(x))==x`).
- **0 hangs** on either corpus after the recursion fix below.

## Bug found + fixed: `instr_length` infinite recursion
The census hung on 1 of 3095 tp files (SPIRV-Cross `implicit-integer-promotion`, a long repeated-`0x38`
run). Root cause: the EXP-M5-05 generic-closure successor guard `_r9_succ_safe` re-entered
`instr_length` with the **default `_closure=True`** (unlike its siblings `_m5_anchor`/`_m5_chain`,
which correctly pass `_closure=False`), so on a repeated-`0x38` run the closure recursively
re-triggered itself with no depth bound → exponential blowup. **Fix (1 line):** `_r9_succ_safe`
now probes with `_closure=False` (matching the documented design intent). Verified: the bad file
scans fully, both corpora census with 0 hangs, round-trip still green. A hanging disassembler would
have failed OBJ-3, so this was a required correctness fix, not just a perf one.

## Honest scope of "coverage"
This restores **tokenization** (leader + length) — the stream now walks cleanly with ≤3.5% desync.
It does **not** yet prove the **semantics** of the newly-named/relocated ops: new leaders were added
with minimal `raw`/`operand_word` fields and `# SEMANTICS: splice-TODO` markers. Named-% (own 85%,
tp 91%) counts ops with a resolved leader; per-field/enum semantics for the M5-specific ops are the
next wave (splice-and-observe on the M5, now unblocked). Remaining undecoded tail: own 3.45% / tp 2.02%.

## Reproduce
- Census (hard-timed, per-file 3s watchdog, budget/corpus): `census_robust.py` against
  `~/cleanroom_work/EXP-M5-02/hex` (own) and `~/cleanroom_work/EXP-M5-03/tp_hex` (tp), importing the
  fork's `isadb`. Round-trip: `python3 tools/agx-isa-m5/roundtrip_test.py`.
- Base vs final census records: `own_base.json`/`own_final.json`/`tp_base.json`; iteration scripts
  (`analyze_leader.py`, `family_report.py`, `lenvote.py`, `validate.py`, `vet_fillers.py`).

## Clean-room attestation
Own-MSL + committed-permissive corpora, our own tools only; the DB was edited and validated purely
against our own compiled shader bytes. No Apple binary disassembled/introspected; no GPU dispatch.
Every coverage number is from an actual census run.

## Follow-ups
1. Splice-validate semantics of the M5-specific leaders/length families (next wave).
2. Render the M5 DB into `docs/isa/` (encoding tables / XML) for OBJ-1 (driver-from-docs).
3. Close the residual ~2-3.5% undecoded tail.
