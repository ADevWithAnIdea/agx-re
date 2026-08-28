# PROGRESS — EXP-0105 M4 encoding/registers (ENC-* cluster)

Timestamped milestones, written incrementally so a kill costs at most one
milestone (per SUBAGENT_BRIEF.md).

## Milestone 1 — scoping (2026-08-27)

Read CLAUDE.md, CODEX.md, SUBAGENT_BRIEF.md, docs/isa/register-move-and-
liveness.md, EXP-0099/RESULTS.md + PRE_REGISTRATION.md (the direct
predecessor: refuted both candidate models of falu2's register field,
leaving the top bit HW-tested INERT and r64-95 addressing UNKNOWN again).
Enumerated the 16 ENC-* items from APPLE9_RE_IMPLEMENTATION_GAPS.md.
Surveyed `tools/agx-isa/db.json` for every family with a register-typed
field: falu2/falu2_ext/falu2_ext8b/falu2_srcmod10/falu2_uni/falu2i,
falu3/falu3_ext/falu3_srcmod12/falu_srcmod12b, iadd2/imad/iminmax/ibfe,
reg_move_c*, uniform_mov, get_sr, device_load/device_store. Cross-checked
EXP-0092 (get_sr/device_store GLIO-A02 register-address round trip,
HW-VALIDATED 0-95) as a candidate model for a "separate bank-select field"
mechanism (get_sr's `dst_hi`), distinct from falu2's already-refuted
packed-top-bit model.

## Milestone 2 — pilot: iminmax dead end (2026-08-27)

Compiled OWN MSL (`int a=mem[tid]; int b=mem[tid+1]; out[tid]=max(a,b);`)
to get a REAL, working `iminmax` instance (own-MSL, OWN-SHADER) and
confirmed it computes `max()` correctly unspliced (mem=[23,71] -> 71).
Extracted its field values (`fmt=3`, `selhi=0`, `sel=6=imax`, `srcA=5`
matching the register a device_load wrote "a" into) as a "known-good
default" template, since db.json flags this family's own `fmt`/`selhi` as
"INFERRED... NOT HW-dispatch validated."

Two independent attempts to use `iminmax` as a SECOND, structurally
different register-addressing test both failed in ways this experiment
could not interpret safely, and were ABANDONED (not shipped as gated
cases):

1. **Anchor-splice attempt** (EXP-0092's own `_splice_bytes` technique):
   spliced ONLY the working compiled instance's `srcA` byte (offset 0x2d
   in `_agc.main`, verified single-byte diff via `isadb.assemble`) to (a)
   `1` (a genuinely different, IN-RANGE low register, holding a known `0`
   from `get_sr(thread_position_in_grid.x)`) and (b) `67` (the r64-95
   candidate). **Neither splice changed the output at all** -- `out[0]`
   stayed at the ORIGINAL "a" operand's value (12345) in both cases, with
   splice (b) additionally showing GPUTIME_NS ~30x normal (88124 vs the
   usual ~2700-3900) while still reporting `STATUS OK`. The splice
   mechanism itself was independently re-confirmed sound (`SPLICE
   _agc.main@0x2d: 05 -> 43` printed correctly, matching the file's actual
   changed byte), so this is not a tooling bug in the obvious place.
2. **Hand-built (isadb.assemble from scratch) attempt**: built a
   `mov_imm(3,99)` + `iminmax(dst=5,srcA=3,srcB=3,sel=imax)` +
   `device_store` program (using the SAME `fmt=3`/`selhi=0` values
   extracted from the working compiled instance). Result: `0`, not `99`.
   A PARALLEL control -- `mov_imm(5,77)` + the SAME `device_store` call,
   skipping `iminmax` entirely -- correctly stored `77`, proving the
   store mechanism, splice mechanism, and `mov_imm` seeding are all fine
   in this exact harness; the defect is specific to something about
   `iminmax`'s own operand-read behavior in a hand-built context. Adding
   4 padding instructions between seed and read (ruling out a pipeline-
   timing/hazard explanation) made no difference. Redirecting the SAME
   construction's source to a register written by `device_load` instead
   of `mov_imm` also read back `0`, not the loaded value -- but a
   PARALLEL, decoupled test (`device_load` -> `device_store` directly,
   no `iminmax`) ALSO read back `0` instead of the loaded value, which
   is CONSISTENT with EXP-0099's own already-documented finding that
   `device_load`'s result cannot be reliably forwarded to a later,
   non-adjacent consumer via the `addr_mode=0x54`/`extmode=2*data_reg`
   convention -- i.e. THAT specific negative result is not new, but it
   confounds isolating whether `iminmax` itself has a separate defect
   when fed a `mov_imm`-sourced register (which is NOT explained by the
   known load-forwarding blocker).

**Decision (disclosed, not hidden):** neither failure mode matches any
previously-documented hardware behavior (not the "silent zero" pattern
from register-move-and-liveness.md section 2.5/2.6, not a fault, not
simply the known load-to-ALU blocker -- the anchor-splice attempt's total
insensitivity to a splice on a REGISTER FIELD, for a REAL working
instruction, with the store mechanism independently proven sound, is a
genuinely new and unexplained observation). Per CODEX's "when the source
of a fact is unclear, treat it as forbidden and stop" spirit applied to
methodology (not clean-room boundary here, but the same caution
principle) and the standing "do not guess" discipline: `iminmax` is
DROPPED from this experiment's gated case matrix. A `get_sr`-based seeded
positive-value confirmation (planned as a second leg of the SEEDED group)
was also dropped without independent hardware verification, since
stacking it on top of an already-not-understood mechanism would not have
produced an interpretable result even if built, and this experiment did
not have time to independently re-verify `get_sr` on its own before the
capture deadline (EXP-0092's own `get_sr`/`device_store` round trip is
cited as PUBLIC-to-this-experiment evidence, not re-derived here).

This is reported as a first-class, if inconclusive, finding (RESULTS.md),
and a concrete lead for a successor experiment: characterize why
`iminmax`'s operand fields do not behave as a plain, splicable 8-bit
register index even at LOW, in-range values, before attempting to reuse
it for anything else.

## Milestone 3 — pivot to falu2/falu2i-only design, pilot success (2026-08-27)

Redesigned the case matrix around ONLY EXP-0090/EXP-0099's own proven
falu2/falu2i construction: (a) `falu2i`'s `srcA_reg` field (EXP-0099's own
disclosed gap -- "the analogous position in falu2i was not [tested]"),
tested via the IDENTICAL aliasing design EXP-0099 used for falu2 itself;
(b) a candidate "separate bank-select bit" sweep (`opflags` bits22/23,
`mod_hi` bit44, a `ctrl` bit walk) crossed against BOTH reg=3 (low,
baseline) and reg=67 (high field value) on `falu2`'s register-register
form. Ran an UN-GATED pilot execution of all 16 cases (single-shot, not
part of the formal two-run capture, `work/pilot_run/` -- scratch, not
committed) to sanity-check the construction before freezing
PRE_REGISTRATION.md. All 16 cases returned `STATUS OK`, clean, internally
consistent, interpretable results (see RESULTS.md for the full table);
no faults, no anomalous timing, matches EXP-0099's baseline case exactly
(`control_r3_falu2i`: 30.0, matches). Captured case 0's real record as
`harness/recorded_fixture_case0.json` (CODEX gate (e), a REAL hardware
record, not synthesized). `verify.py --selftest` (47 checks) and
`--seqtest` both PASS in `PRE_GPU` state.

## Milestone 4 — PRE_REGISTRATION.md frozen, formal captures (2026-08-27)

`PRE_REGISTRATION.md`/`CAPTURE_CONTRACT.json` frozen (pinned revision
`0f1af7fa1d3e21a9996c3b49d7d91f6377427225`). `harness/
recorded_fixture_case0.json` captured from a real pilot-phase hardware run
(case 0). `verify.py --preflight`: PASS. `run.py --execute --run-id
m4-20260827-run01`: 16/16 cases, `STATUS OK` throughout, no `STOP.json`.
`verify.py --between-runs`: PASS. `run.py --execute --run-id
m4-20260827-run02`: 16/16 cases, `STATUS OK` throughout, no `STOP.json`.
`verify.py --captured`: PASS — `01_results.jsonl` byte-identical across
both runs (sha256 `b19327a48bc2857f36b7771202f1287fec2ab104a0dc12d518301517fca14453`).
`analysis.py --write` and `make_manifest.py --write` run. `RESULTS.md`
written with full per-ENC-item response blocks, the finite-resource
table, proposed `db.json` corrections, and the `iminmax` post-mortem.
Scratch (`work/`, `__pycache__`, an unused empty `analysis/` directory
left over from initial scaffolding) cleaned before final gate re-check.
**Experiment complete.**
