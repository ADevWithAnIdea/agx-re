# PROGRESS — EXP-0099

All timestamps local (host clock), 2026-08-28/29 session.

## Milestone 1 — reading & static analysis (no GPU)

Read `apple9_isa_explainer.md`, `work/COMPILER-EXPLAINER-INTERACTION-20260828.md`,
`docs/isa/register-move-and-liveness.md`, `EXP-0086/EXP-0089/EXP-0090`
RESULTS.md. Decoded the explainer's own example bytes against
`tools/agx-isa/db.json`:

- His compact-float retain/release example (`falu2`, fmul) decodes exactly
  as the background doc reports: `srcA_reg` delta of 64 (68 vs 4) =
  bit15 (top bit of the 7-bit field, bits9-15); `srcB_reg` delta of 64
  (66 vs 2) = bit31; `opflags` 4 (retain) vs 7 (release) = bit19/bit20
  toggling as his tables predict.
- His 10-byte "XOR, retain source 0" example (byte0=`0x4b`) does **NOT
  decode under any `db.json` family** — `isadb.disassemble` reports
  `unknown instruction length at offset 0`. His "release both" example
  (same byte0) DOES decode, but as `b_alu10_loe` (a weakly-validated,
  byte-diff-only family — NOT `ilogic`, whose match condition requires the
  WHOLE of byte0 == `0x0B`, not merely its low nibble). This is a genuine,
  static, decoding-dispatch defect, independent of any hardware result —
  recorded for RESULTS.md.

## Milestone 2 — harness build, first smoke test (GPU)

Built `tools/shdump`/`tools/agxtest` locally. Wrote an initial
`kernels/carrier.metal` (20 live output expressions, moderate register
pressure) and a first case matrix seeding `r67` via `device_load` +
verifying via `device_store`.

**First smoke test FAILED**: `seed_r3_readback` (pure ALU, no load)
initially failed too, but for an UNRELATED reason — `V_LOW=42.5` exceeds
`falu2i`'s packed-minifloat immediate range (`+-{0,1/32..30}`), silently
clamping to 30.0. Fixed by using `H.imm_value(K)` (a fixed point of
`isadb.imm_encode/imm_decode`) as both the assembled K and the recorded
oracle throughout, instead of a raw literal.

## Milestone 3 — INCIDENT: device_load splices silently returned 0.0

After the immediate-rounding fix, `seed_r3_readback` passed, but
`seed_r67_readback` (device_load then store) read back `0.0` instead of
the seeded `133.75`. Extensive isolation (see Milestone 4) traced this to
the ORIGINAL carrier kernel's higher register pressure / longer natural
compile: the SAME hand-built instruction bytes (byte-for-byte, including
EXP-0090's own `finding_3` verbatim direct-forward construction) worked
perfectly when spliced over `EXP-0090`'s own `carrier_p2.metal`, but
silently failed (all-zero reads, `STATUS OK`, no fault) against the
original, more elaborate carrier — even though the UNSPLICED, natural
compile of that same carrier correctly read/wrote its buffers (confirmed
by a natural, no-splice run matching the compiler's own arithmetic
exactly). Root cause not conclusively isolated in the time available;
`kernels/carrier.metal` was rewritten to closely match `carrier_p2.metal`'s
low-register-pressure shape, which resolved it (`_agc.main` length changed
770/776 bytes, depending on `--no-fast-math`, -> 170 bytes). This is
disclosed as an open, narrow negative finding (kernel complexity affects
splice reliability for `device_load` specifically) rather than swept under
a "just changed the carrier" summary.

Separately, discovered `agxtest.py`'s `--no-fast-math` flag changes the
compiled `_agc.main` LENGTH relative to a manual compile without it (770 vs
776 bytes for the original carrier) — `CARRIER_LEN` must always be
re-measured under the EXACT flags the harness uses, never a manually-run
`shdump` invocation. `baseline.py` was added to re-derive this fresh
(and the buffer-slot assignment) before every capture, never trusting a
hardcoded constant.

## Milestone 4 — isolating the device_load consumption blocker (GPU)

With the fixed carrier, direct isolation tests showed:

- `device_load(dst=5) -> device_store(addr_mode=0x56, direct-forward)`
  (EXP-0090's own `finding_3` construction, byte-for-byte) works.
- The IDENTICAL construction with `dst` = 0, 2, 7, or 67 instead of 5 —
  **fails** (reads 0.0). Varying `idx_off` alone (keeping `dst=5`) does NOT
  break it. So the "direct forward" store path only reliably works for the
  ONE register value EXP-0090's own anchor happened to use, not registers
  in general.
- `device_store extmode=2*data_reg` (addr_mode=0x54, EXP-0090's own
  `finding_5` formula) for `data_reg=67` (`extmode=134`) — **fails**
  (reads 0.0), extending EXP-0090's formula past its previously-tested
  range unsuccessfully.
- `device_load(dst=X) -> falu2(srcA_reg=X, ...)` for X in {5, 7, 67},
  swept across all 8 candidate `mod_hi` "route" values (0-7) AND two
  `opflags` variants (bit19=0, bit21=1) AND with 4 padding instructions
  inserted — **fails uniformly in every combination tried** (reads 0.0).
  This directly, independently replicates EXP-0090's own P4/finding_2/
  finding_4 blocker (their own report: "5+ independently varied
  constructions all produced a silent zero"), now additionally showing the
  explainer's own proposed fix (route) does not resolve it either.
- `db.json`'s own `scoreboard_model` (EXP-0025, HW-VALIDATED) states G17P
  uses hardware register interlock with NO explicit wait needed and
  `>=20` outstanding loads consumed correctly with no wait — so a missing
  software wait/scoreboard instruction is NOT the explanation; the actual
  mechanism remains unidentified.

This is not treated as a plumbing bug to keep fixing — it is EXACTLY H4's
subject matter, and is captured formally as the `ROUTE_LOAD`/`ROUTE_ALU`/
`H4_BIT21` groups in the frozen case matrix.

## Milestone 5 — the H1/H2 test redesign that avoids the load blocker (GPU)

Realized the original H1/H3 design (seed r67 via `device_load`, then read
it via `falu2`) was confounded by Milestone 4's blocker regardless of which
model (his vs. current db.json) was correct. Redesigned: seed ONLY a LOW
register (r3) via the independently-working ALU-only path
(`falu2i(srcA=unwritten, K)`), NEVER write register 67 at all, and encode
the DECISIVE instruction's `srcA_reg`/`srcB_reg` FIELD VALUE as `67` (low6
= 3, weight-64 bit = 1). This is fully decisive without touching the
load-to-ALU path: reading back the seeded value = his/6-bit model; reading
back 0.0 = current db.json 7-bit model (r67 genuinely never written).

Pilot run (informal, no GPU-side gate) of this design, 8 cases (all 4
srcA-pair combos + all 4 srcB-pair combos, immediate read only): field
value 67 read back the LOW register's seeded value (30.0) in EVERY case,
never 0.0 — REFUTING the current db.json 7-bit model decisively. Extended
to include a later, separate reader instruction (EXP-0086's own "adjacent"
methodology) to also test H2: retention (the later reader's result)
depended on `opflags` bit19/bit20 ALONE, identically regardless of the
register-field top bit (bit15/bit31) — i.e. that top bit showed NO
observed effect on EITHER register selection OR retention, in any of the
8 pilot cases. This refines but does not confirm the explainer's specific
complementary-pair mechanism (see RESULTS.md for the full analysis).

## Milestone 6 — GPR_MOVE_RETRY pilot: a specific, non-zero corruption value

Pilot run of the 5 `reg_move` retry variants (baseline replicate, bit21
set, padding, both, load-sourced) all returned NOT 0.0 but the exact
denormalized bit pattern `0x00000100` (float ~3.587e-43) — reproducibly,
identically across all 4 falu2i-sourced variants. Recorded verbatim rather
than rounded to "reads zero"; see RESULTS.md for the exact bytes and the
honest statement that its origin is not identified.

## Milestone 7 — case matrix frozen, gates passing

`casematrix.py` rewritten to the final 35-case design (Milestone 5/6
results folded in). `python3 -B make_manifest.py --check`,
`verify.py --selftest` (13 checks), `verify.py --seqtest` (state=PRE_GPU,
3 checks), `verify.py --preflight` all PASS. `PRE_REGISTRATION.md` and
`CAPTURE_CONTRACT.json` written, pinning revision
`dc61f8c1f99fa72d5a2094fbbcc31269ba4ca89e`. Proceeding to the two formal
gated captures (`m4-20260828-run01`, `m4-20260828-run02`).

## Milestone 8 — both gated captures complete, gate CLOSED

`run.py --execute --run-id m4-20260828-run01`: 35/35 cases, 15 matched /
20 mismatched (all pre-registered as either a positive control or a
hypothesis-testing prediction — none is an unexpected harness failure).
`verify.py --between-runs` PASS. `run.py --execute --run-id
m4-20260828-run02`: 35/35 cases, IDENTICAL 15/20 split.
`verify.py --captured`: **PASS** — `01_results.jsonl` byte-identical
across both runs (sha256
`3285bbe122b0e07b80c61b41e4e73eee9a0587e454ad3eb9b44800eb89c52ce4`), fully
deterministic, no `STOP.json` in either run. `analysis.py --write` and
`make_manifest.py --write` run. `RESULTS.md` written with full
OBSERVED/INTERPRETED analysis, per-hypothesis verdicts, proposed `db.json`
corrections (text only, not applied), and the clean-room attestation.
Headline: H1 (current 7-bit-index model) REFUTED; H2 (his complementary-
pair mechanism) also REFUTED — the register-field top bit is inert for
BOTH addressing and retention in the tested construction, a third outcome
distinct from both competing models. H4 (route hypothesis) REFUTED, load-
to-ALU blocker persists. H5 (three candidate fixes) REFUTED, GPR-move
blocker persists; `reg_move` also cannot read a `device_load`-written GPR
(closes EXP-0090's own open question, negatively). H3 UNKNOWN/OPEN. H6
answered via static structural analysis (bit17 is a distinct mechanism).
A decisive static decoding-dispatch defect found in `db.json`'s coverage
of the 10-byte logic form (one of the explainer's own literal example
byte sequences does not decode under any current family).
