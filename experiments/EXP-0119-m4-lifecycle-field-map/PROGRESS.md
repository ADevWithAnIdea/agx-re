# PROGRESS — EXP-0119 M4 lifecycle field map

**Milestone 1 (setup).** Read the four-experiment arc (EXP-0086/89/99),
`docs/isa/register-move-and-liveness.md`, `apple9_isa_explainer.md`,
`work/COMPILER-EXPLAINER-INTERACTION-20260828.md`. Renumbered from EXP-0118
to EXP-0119 mid-dispatch (coordinator directive: another agent had already
claimed EXP-0118 for an unrelated partial-render workload; no capture had
occurred, directory move only).

**Milestone 2 (tooling survey + builder validation, no GPU).** Built
`isa_helpers.py` extending EXP-0099's builders with `falu2_ext_raw`,
`falu3_srcmod12_raw`, `falu_srcmod12b_raw`, `ibitcount_raw`. Found and fixed
a real bug via `assert_round_trip` alone (no hardware needed): constructing
`falu2_ext`/`falu3_srcmod12`/`falu_srcmod12b` with `ctrl=0` silently
re-decoded as a plain 6-byte `falu2i`/`falu2` — `isadb.instr_length`'s rule
for the WHOLE low-nibble-9 float-ALU group is `6+2*(byte4&3)`, i.e. the
`ctrl` field's own low 2 bits are the length selector, not a free bit.
Added `_length_ctrl()` to fix the low 2 bits per intended length and expose
only the upper 5 bits (`ctrl_hi5`). Also found `falu3_srcmod12`'s match
condition forces bit17=1, which overlaps its own `opsel` field (OR-composed
by `assemble()`), making `opsel=4`/`5` unreachable for that family — fixed
by removing the misleading `op` parameter.

**Milestone 3 (hardware pilot, informal, `work/`, not gated).** Built
`shdump`/`agxrun` into `work/pilot_bin`. Confirmed the basic Mode A
pipeline (seed + read via `carrier.metal`, 170B). Ran ~40 exploratory
hardware probes covering every planned group. Found and fixed 4 more real
bugs before freezing the contract (full detail in `PRE_REGISTRATION.md`
section 0): (1) a bad immediate-constant choice (`K3=99.0` silently clamps
to `30.0` in the minifloat immediate codec — collided with the seed value
and made a "rewrite" test look like a no-op); (2) `device_store`'s
`idx_off` unit is 4 words, not 1 — a naive `store(word_index, reg)` helper
wrote out of bounds; (3) `lit17_unpack.metal`/`lit17_cvt.metal`'s buffer
roles are the OPPOSITE of `carrier.metal`'s — every MODE B case silently
read the wrong buffer and returned all-zero; (4) `falu_srcmod12b`'s
`opsel=4` is not a valid encoding for that family and corrupts an entirely
UNRELATED register — found via a positive-control redirect that itself
returned 0 unexpectedly. Also found and directly confirmed with EXP-M4-14's
own literal anchor bytes: `ibitcount`'s `cache` bit has NO observed causal
effect on M4 (own-result and later-read corruption are both unconditional
on it), contradicting EXP-M4-14's A18-recorded finding for the same bytes.

**Milestone 4 (matrix freeze + informal full-matrix smoke, `work/`, not
gated).** Wrote `casematrix.py` (77 cases). `work/full_smoke.py` (informal,
deleted before gated capture) ran every non-hang-probe case once: 76/76
`STATUS OK`, only the 3 by-design mismatches (2 hypothesis refutations, 1
deliberate control) deviated from oracle. The one hang-candidate case
(`..._HANGPROBE`) was independently pre-tested in isolation before freezing
the contract: `STATUS OK`, 115ms, no hang.

**Milestone 5 (frozen contract).** Wrote `PRE_REGISTRATION.md` and
`CAPTURE_CONTRACT.json` at pinned revision `72c2dde8afd896e384afa20050bdd040f657ca78`.
Captured `harness/recorded_fixture_case0.json` (real hardware record, case
0) for `verify.py --selftest`'s CODEX gate (e). `baseline.py` re-derives
`CARRIER_LEN` and both MODE B kernels' anchor bytes fresh — PASS.

**Milestone 6 (gated capture).** All standing gates PASS
(`--selftest` 51 checks, `--seqtest`, `make_manifest.py --check`,
`--preflight`). `run.py --execute --run-id m4-20260828-run01`: 77/77 cases
`STATUS OK` (including the hang-probe — no hang), 74/77 matched (3 by-design
mismatches). `verify.py --between-runs`: PASS. `run.py --execute --run-id
m4-20260828-run02`: 77/77 `STATUS OK` (hang-probe again did not hang),
identical match counts. `verify.py --captured`: PASS — `01_results.jsonl`
byte-identical across both runs
(`sha256 7e5aa5fa6cf83b7295a061a557abccf9a9bd1215314d9b261715464638fb0d87`).
`analysis.py --write`, `make_manifest.py --write`: done.

**No STOP.json anywhere. No fault, no hang, no timeout in either run. Host
did not wedge.**

**Milestone 7.** `RESULTS.md` written from the byte-identical two-run data.
