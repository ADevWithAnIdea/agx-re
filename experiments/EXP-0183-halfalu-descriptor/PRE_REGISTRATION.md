# EXP-0183 — PRE-REGISTRATION

**Frozen before any edit to `tools/agx-isa/db.json` and before any analysis script was run.**
Written 2026-08-30. Target of the *evidence* re-read: **A18 Pro / G17P** (EXP-0180's two gated
runs). This experiment itself is **PURE ANALYSIS — no device, no SSH, no GPU.**

## 1. Question

`docs/isa/emit-worklist.md` lists 22 instructions one field away from emittable. Several are
blocked by descriptor defects that EXP-0180 confirmed on hardware (`analysis/db_defects.json`,
DEF-0180-1…8) and that EXP-0181 confirmed by span audit
(`analysis/orphaned_validation_rows.json`). **None has been applied to `db.json`.**

Precise question: **which of those defects survive an independent re-derivation from the
committed raw, and what is the corrected `db.json` descriptor for the `byte0` low-nibble-0
native-half family (`half_alu`, `half_alu_ext8`, `half_alu_fma12`), for `falu2_uni.dst`, and
for `reg_move_cb.dst`?**

## 2. Hypotheses, each with its refuter

Every hypothesis is scored **only** against `experiments/EXP-0180-g17p-halfalu-rerecord/raw/`
(`g17p_run02` = reverse order, `g17p_run03` = forward order) and
`experiments/EXP-0168-*/`, `EXP-0169-*/` raw where the row cites them. **A defect that fails
its re-derivation is reported and NOT applied** (precedent: EXP-0165 found one defect half
wrong; EXP-0175 refused to propagate a fix that would have created a new defect; EXP-0180
withdrew its own DEF-0180-3).

| id | hypothesis | refuter (pre-registered) |
|---|---|---|
| **H1** | DEF-0180-1: for `byte0 & 0x0f == 0`, the destination GPR is `byte0 >> 4`; the write lands in `r[n]`'s LOW 16 bits with the HIGH 16 bits preserved. | Any `DSTNIB` case where `post` differs from `pre` in a register **other than** `r[n]` (excluding the two named harness registers), or where `r[n]`'s high 16 bits change, or where the two runs disagree. |
| **H1b** | The same, structurally: in every gated case the seed program's low-half writes land in `r_j` for `byte0 = (j<<4)`. | Any case whose `pre` vector is not the frozen seed vector for its carrier. Measured as: `pre` is constant per (arm, carrier) across the whole run. |
| **H1c** | The same, arithmetically: `E8_FMA@C_HI` computes `r1.lo = fp16(byte+3) * fp16(byte+1) + fp16(byte+5)`, i.e. db's `dst` (bits 8..15) is a **source**. | The anchor's observed `r1.lo` not equal to the host-computed fp16 fma of the three named source half-registers. |
| **H2** | DEF-0180-2: instruction length for this family is a function of `(opsel = byte+2 & 7, m = byte+4 & 3)` only, with the 32-cell table EXP-0180 published; `db.json`'s stated `byte0_table['0x10']` rule is wrong in 25 of 32 cells. | Any `(opsel, m)` cell with two different observed lengths, or a cell whose observed length differs from the published table, or a cross-run disagreement. |
| **H3** | The six withdrawals: (a) `ext8.rsv6` is LIVE, not inert; (b) the byte+7 nulling bit is instruction bit 60, not 63; (c) `ext8.saturate` is not a clamp; (d) `ext8.srcB_desc`'s encodable range is 64, not 256; (e) `fma12.opsel` has one legal value; (f) `fma12.ext` is 64 bits and not a field. | For each: the opposite count in the raw. (a) `rsv6` moving on <2 values; (b) any `op_valid_marker` case that moves, or any `b7_mid` value in {4,5,6,7} that does **not** null; (c) a `saturate=1` case on the sub-unit carrier that leaves the result unchanged, or that clamps into [0,1]; (d) an 8-byte framing at `m != 1`; (e) more than one `opsel` value at 12 bytes; (f) — structural, cannot be refuted by data, it is a width fact. |
| **H4** | DEF-0180-4/5/6 are citation defects: each row's committed `range` text names a byte the field's own span does not cover. | The byte named by the text falling inside the field's `[start, start+width)`. |
| **H5** | EXP-0181's re-scores hold: `iter_at.grp`'s real range is 2 (dense 2-of-2, 3 runs) and `reg_move_cb.form`'s honest counts are 16/16/16. | The narrowed span not matching the descriptor's own `match`; or the cited raw not containing the claimed dense coverage in every run. |

## 3. Independent variable / controlled variables

- Independent: the content of `tools/agx-isa/db.json`.
- Controlled: `tools/agx-isa/isadb.py` (**EXP-0182's file — not touched**), the corpus
  (`experiments/EXP-M4-13-full-corpus/hex`, 1,083 files / 1,080 `.hex`), the round-trip suite.
- **Confounder, declared:** EXP-0182 is editing `isadb.py` concurrently, so the live baseline
  moves. Mitigation: the working tree is snapshotted to `work/base_live/` at pre-registration
  time and **every A/B compares candidate-vs-`base_live`, not candidate-vs-live**. A final
  re-measure against live is reported separately.

## 4. Frozen baseline (measured before any edit)

| tree | clean | leftover | tokens | roundtrip |
|---|---|---|---|---|
| `work/base_head` (git HEAD) | 833/1080 | 388,604 | 25,419 | ALL PASS, 302 OK / 0 FAIL / 0 crash |
| `work/base_live` (HEAD + EXP-0182 dirty `isadb.py`) | **840/1080** | **387,496** | **25,587** | ALL PASS, 302 OK / 0 FAIL / 0 crash |

**Gate: `base_live` must not regress on `clean`, `leftover` or `tokens`, and
`roundtrip_test.py` must stay ALL PASS with 0 crashes.** A length change shifts every
subsequent instruction boundary in the corpus; if a change regresses these counts it is
reported and left unapplied — that is the orchestrator's call, not mine.

## 5. Method (frozen)

1. `analysis/rederive.py` — re-derives H1/H1b/H1c/H2/H3/H4/H5 **from raw only**, writing
   `analysis/defects_rederived.json`. It does not import `db.json`'s conclusions; it recomputes
   register deltas, fp16 arithmetic and marker counts from the committed `pre`/`post`/`hw_markers`.
2. `analysis/ab_gate.py` — the A/B gate. **Both** the corpus half and the round-trip half run in
   a **subprocess** (`analysis/corpus_probe.py`), per DEF-0175-2: EXP-0175's in-process gate let
   the first tree measured win `sys.modules['isadb']`, so every later candidate silently
   re-measured the first tree's database and it reported ALL PASS for a candidate that crashed.
   EXP-0182's gate fixed the round-trip half only; this one fixes both.
3. Candidate trees under `work/cand_*/` (a copy of `work/base_live/` + the edited `db.json`).
   **Nothing lands in `tools/agx-isa/db.json` until its candidate passes the gate.**
4. Surviving defects are applied; **pinned remainders are recorded in `match_notes`** exactly as
   EXP-0175/EXP-0181 did, so no bit silently disappears from the descriptor.
5. `analysis/validation_updates.json` is produced for the orchestrator for **every** row whose
   field moved, folded, or whose `range` text is refuted, carrying corrected
   `start`/`width`/`values_dispatched`/`distinct_bytes`/`encodable_range` — because
   `work/merge_verdicts.py` refuses a verdict whose bits have moved.

## 6. What I will NOT do

- Not edit `tools/agx-isa/isadb.py` (EXP-0182), `tools/agx-isa/validation.json`, `docs/`,
  `PROVENANCE.md`, `CLAUDE.md` or `CODEX.md`.
- Not `git commit`.
- Not touch any device. No SSH. No GPU.
- Not cite `roundtrip_test.py` as an emitter gate (EXP-0170: it passes against an assembler that
  cannot clear a bit). It is used only as a *regression* check.
- Not promote a label. Labels are the orchestrator's; I hand over recommendations.

## 7. Known confounders

- **A length change relocates every following instruction boundary.** The corpus counts are the
  only instrument that sees this; they are checked on every candidate.
- **`db.json`'s `length_rule` is documentation, not code.** `isadb.instr_length` is a Python
  function; editing `byte0_table` changes no decode. This is why the length correction can be
  applied as documentation without a corpus risk, and why the *code* half stays EXP-0182's.
- **Loosening a `match` can steal decodings.** `decode_one` picks the candidate with the most
  matched bits, so a 4-bit match loses to any ≥5-bit competitor at the same length — but it can
  still capture bytes that previously had **no** descriptor. The firing delta per mnemonic and the
  per-file clean/dirty delta are recorded for exactly this.
- The raw I re-read is **G17P**. Rows being corrected are labelled A18 or M4 in places; I do not
  silently promote across targets.

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE (re-read offline; no new run)
Inputs inspected: the committed raw/ trees of EXP-0180 (and the cited raw of EXP-0168/0169),
  which record the behaviour of AGX machine code compiled by the PUBLIC runtime API from MSL
  authored in this project, plus byte splices of that same code; tools/agx-isa/db.json.
Apple binary introspection: NONE. No Apple binary was disassembled, decompiled,
  symbol-dumped, strings-scanned or debugged.
Reproduction: README.md
Evidence: analysis/{defects_rederived,ab_metrics,validation_updates}.json, work/base_*.
```
