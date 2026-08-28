# PROGRESS -- EXP-0126

All timestamps local (2026-08-28), single session, no host wedge, no kill,
no partial/quarantined capture at any point.

1. **Reading phase.** Read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md,
   `docs/isa/register-move-and-liveness.md`, and RESULTS.md for
   EXP-0086/0089/0099/0113/0119 in full. Confirmed the exact established
   scope (six families/contexts for H1's bit15/31 inertness, EXP-0119's
   three-signature H3 verdict, the disclosed-not-resolved A18-vs-M4
   ibitcount contradiction) before designing anything new.
2. **Tooling survey.** Read `tools/agxtest/README.md`, EXP-0119's
   `isa_helpers.py`/`casematrix.py`/`run.py`/`verify.py`/`case_exec.py` in
   full (the direct architectural template), EXP-0112's `cf.py`/
   `generator.py`/kernels (source of the CF skeleton and the 1536-byte
   `carrier_dag.metal`), EXP-0101's `device_load_fixed`/`mods=0xC0`
   findings, and EXP-M4-14's own `iunary.metal`/`splice_results.json`
   (source of the H3 anchor bytes and the k_popcount dispatch shape).
3. **Fragment-stage pilot (H1, ultimately NOT REACHED).** Compiled
   `kernels/fs_adjacent.metal` via `shdump --render`, located
   `_agc.main`/`_agc.main.constant_program` for the fragment stage
   (discovered these are TWO separate regions, unlike compute's single
   `_agc.main`), found a genuine compiler-emitted `falu2` instruction with
   a naturally top-bit-set `srcA_reg` field. Two independent positive
   controls (a saturated-output pilot, then a properly [1/64]-scaled one)
   both failed to detect a deliberate LOW-bit register change at that
   exact splice point -- concluded the located instruction is not
   demonstrably live on the rendered-pixel path within budget. Patched
   `harness/fsrun.m` (copied from EXP-0111/EXP-0091) to remove its
   `NSTemporaryDirectory()`/system-`/tmp` scratch-archive write (clean-room
   fix, own copy only) before this pilot even ran, per the standing
   never-write-outside-the-repo rule.
4. **CF-boundary pilot (H1).** Wrote `isa_helpers.build_cf_topbit_program`,
   a hand-transcription of EXP-0112/EXP-0090's own `cf.py::build_cf_program`
   parameterized on the "arm_true" instruction's `srcA_reg` field. First
   transcription had a wrong opflags nibble (1 instead of 2) -- caught by a
   byte-exact diff against the original BEFORE any hardware run. Fixed,
   re-diffed clean, then ran 5 real dispatches (true/false arm x
   base/bit15-cleared, plus a positive control) -- all matched their
   host-computed oracle, including the positive control correctly reading
   0.0 (proving the harness detects a genuine addressing change here).
5. **Register-pressure pilot (H1).** Confirmed `carrier_dag.metal` (reused
   from EXP-0112) compiles to 1590 bytes (>=1536 budget), built 40
   `device_load_fixed` instructions into registers r16..r55, ran the
   standard H1 field={3,67}/opflags={0,1} probe on top -- all 4 combinations
   matched the established pattern exactly (own=50.0 always, later=50/20
   per opflags bit).
6. **Load-sourced-operand pilot (H1).** First attempt used
   `falu2i_raw(..., mods=0)` (the naive default) and silently read zero
   for every case. Diagnosed via a standalone `device_load`-then-
   `device_store` (bypassing the ALU entirely) which ALSO read zero,
   isolating the bug to the load/consume path rather than a real
   corruption; found EXP-0101's own `mods=0xC0` requirement in its
   casematrix.py, applied it, re-ran -- all 4 combinations then matched
   (own=62.0 always [LOADVAL 42+K2 20], later=62/20 per opflags bit).
7. **Half-width pilot (H1).** A seed-then-immediate-store diagnostic (b16,
   zero intervening instructions) correctly read back 30.0; the actual
   two-instruction H1 construction (seed, then a second b16 read) read 0.0
   in all 4 (field, opflags-bit) combinations -- recorded as an
   OBSERVED/UNINTERPRETED anomaly, oracle set to EXPLORATORY (None) rather
   than chased further or silently absorbed into an "inert" claim.
8. **H3 MODE B pilot (the session's most consequential bug).** First
   attempt used the ABSOLUTE archive file offset (from `agxparse.py
   --locate`) as `agxtest.py --splice`'s offset argument; every dispatch
   (any grid size, any cache value) read back all-zero. Diagnosed by
   dumping `MAIN_ORIG` and manually locating the anchor bytes' RELATIVE
   position (0x12, not the absolute 0x1a-looking value from a prior
   mis-transcription) within the 44-byte `_agc.main` -- `agxtest.py`'s own
   `--splice SYM@OFF=HEX` is relative to the symbol region. Fixed, re-ran:
   baseline (unspliced) kernel correctly gave [4,1,16,2]; the RIGHT-offset
   splice at grid=1/grid=4 x fresh/stale cache reproduced EXP-M4-14's own
   "stale breaks it" signature at BOTH grid sizes -- the decisive H3
   dispatch-shape-independence result.
9. **H3 MODE A pilot.** Built the operand-provenance x dispatch-shape 2x2
   directly (ALU-seeded matching EXP-0119's own construction; device_load-
   sourced via EXP-0101's formula, reusing lesson from step 6). Confirmed:
   ALU-seeded NEVER breaks (any grid, any cache); device_load-sourced
   breaks at cache=0 AT GRID=1 already -- the clean, single-axis-isolated
   confirmation that operand provenance (not dispatch shape) is the
   deciding factor.
10. **H2 byte-sweep pilot.** Read `ibitcount`'s full db.json field/match
    table to identify exactly which bits are genuinely free (not
    match-forced, not the already-characterized compute-enable/GPR-read-
    enable bits): `op_enable` bits{0,2-7}, `srcdesc` bits{0-5,7}, `tail`
    bits{0-7}, 22 total. Ran all 22 -- found `srcdesc` bit4 gives a CLEAN
    dissociated signature (own-result stays correct at popcount=6, later-
    read flips from corrupted [20.0] to RETAINED [50.0]), distinct from
    `srcdesc` bits0/3 and `tail` bit2 which break OWN-result too (a
    confounded "degraded GPR read" pattern). Added H2_INTERACTION on the
    spot to check whether `cache` regains a role once `srcdesc` bit4 is at
    its "retains" setting -- it does not (both cache values give 50.0
    retained once srcdesc bit4 is cleared).
11. **Full 58-case smoke pass** (informal, not the gated capture): every
    case STATUS OK, zero faults/hangs/timeouts, across the whole matrix.
12. **Froze PRE_REGISTRATION.md + CAPTURE_CONTRACT.json** (pinned revision
    `633cd06b0c9890bc641128ca7b49ff66eee41cb1`), generated
    `harness/recorded_fixture_case0.json` from a real hardware run,
    `verify.py --selftest` (192 checks) / `--seqtest` / `--preflight` all
    PASS, `baseline.py` PASS (every carrier kernel's compiled facts
    re-derived fresh, matching casematrix.py's assumptions exactly).
13. **run01 (m4-20260828-run01): 58/58 STATUS OK, 56/58 matched** (the 2
    designed-to-mismatch H3_MODEB "stale" cases). `--between-runs` PASS.
14. **run02 (m4-20260828-run02): 58/58 STATUS OK, 56/58 matched**,
    identical status/mismatch pattern to run01.
15. **`verify.py --captured`: PASS** -- `01_results.jsonl` byte-identical
    across both runs (sha256
    `9bcdb378fe47a019abd1a3f228ca94c034788ffedc06baa2c836933bd48e1b1e`).
    `analysis.py --write` and `make_manifest.py --write` run. RESULTS.md
    written from the gated data. No STOP.json in either run. No fault, no
    hang, no timeout, anywhere in this experiment.
