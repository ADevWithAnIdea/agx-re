# PRE_REGISTRATION -- EXP-0090 (M4 hand-built program suite, DRV-ISA-01)

Frozen before any GATED hardware capture (informal pilot probes, `work/pilot*/`
and `work/informal_full/`, already ran and are cited below as the process that
SHAPED this design -- per CODEX.md step 3 and EXP-0087's own precedent; no
GATED run has occurred yet at the time this file is written).

## Question

Can this repository's own tools (`tools/agx-isa`) independently CONSTRUCT --
not merely decode, not merely splice a single field into an Apple-observed
template -- four non-trivial, multi-instruction-family AGX programs, whose
whole-program behavior is checked against an independently computed exact
oracle, on real M4 hardware? This is the acceptance test for DRV-ISA-01:
"can an implementer generate code from our docs."

## Hypothesis

H1 (primary): programs built purely from `isa_helpers.py` wrappers over
`isadb.assemble()` -- using ONLY the specific instruction-family combinations
this experiment's own pilot diagnostics (see below) found reliable -- will
match their independent Python oracle exactly, reproducibly, across two
independent hardware captures.

Refuter: any case where `observed != oracle` on a STATUS-OK dispatch, on
EITHER run, is a direct falsification of H1 for that case/family.

## What pilot diagnostics established (frozen facts this design relies on)

Roughly 30 authored, single-purpose diagnostic probes were run on real M4
hardware before this file was written (`work/pilot1`..`work/pilot33`, no
raw/ artifacts created -- purely informal shaping, exactly the "pilot probes
... shaped the frozen matrix" pattern EXP-0087's own PROGRESS.md documents).
Each finding below is HW-PROBE evidence, reproduced at least twice, and is
treated as an established building block for this design -- NOT re-tested
inside the formal gate (falsifying them further is future work, not this
experiment's residual risk):

1. **falu2i chains are reliable.** `srcA` reading a value a PRIOR `falu2i`/
   `falu2` instruction genuinely computed, combined with a compile-time
   packed-minifloat immediate (`srcB`), works for any `last_use_srcA` value.
2. **falu2 (register form) combining two real prior values requires
   opflags=3, not opflags=1.** `opflags` bit1 (in ADDITION to bit0, the
   already-documented EXP-0086 last-use flag) must be set when `srcB` reads
   a value a prior instruction actually computed; bit0-only (opflags=1)
   silently zeroes that `srcB` read. Falsified 4 independent ways
   (`pilot25/26/28/31`); confirmed working with opflags=3 (`pilot30`,
   reproduced by every P1 case since). This is a NEW field-semantics
   finding, not previously documented (`db.json` currently types `falu2`'s
   `opflags` as an untyped 5-bit `mod`).
3. **device_load's result could NOT be reliably read by a freshly
   constructed falu2/falu2i.** 5+ independently varied attempts (address
   mode, `extmode`, `dst_lo`/`dst_ext9`, index source, added latency) all
   produced a silent zero. One byte-verbatim copy of a real compiled
   load-then-ALU pair worked (`pilot18`) but the specific combination of
   fields responsible could not be isolated in the time available. This
   experiment does NOT attempt this bridge in any GATED case; `db.json`'s
   `device_load` destination-register model (`dst_lo|dst_ext9<<2`,
   EXP-M4-13 R8) should be treated as validated ONLY for the load's own
   destination bookkeeping and for feeding a directly-following
   `device_store`/`iadd2` per items 4-5 below, not as a general "read this
   GPR from any instruction" guarantee.
4. **device_load reliably forwards to device_store directly**
   (`addr_mode=0x56`, structural fields copied verbatim from a real
   compile) -- confirmed 3x.
5. **device_load reliably feeds iadd2 via ONE specific verbatim anchor**
   (`kernels/pilot_immadd.metal`'s own compiled `a[i]+K` triplet: load
   `space=0x10,addr_mode=0x44,extmode=0,dst_lo=1,dst_ext9=1`; iadd2
   `srcA=0x88,opc_tail=0x15,opc_tail2=4,dst=0`) with ONLY `srcB_imm`
   (the EXP-0007-validated immediate field) varied on top of the
   EXP-0082/0083-validated load fields (`index_reg`,`idx_off`,`elem_size`
   code,`base_slot`) -- confirmed 3x (`pilot22`, `pilot32`, integrated use).
6. **reg_move (the EXP-0087-proven encoding) FAILED to read a GPR a
   falu2/falu2i instruction had just written** -- falsified 3x
   (`pilot25/26/29`). EXP-0087's own validated cases all sourced from
   UNIFORM slots (its whole carrier was `uniform_mov`-based); this
   experiment's attempt to move a genuinely `_agc.main`-computed value
   between families is a materially different, NOT-currently-synthesizable
   case. Consequently **P4 (register-pressure/move program) is EXCLUDED
   from this capture** -- see "P4 negative result" below.
7. **device_store's `extmode` byte = 2*(source GPR)** when
   `addr_mode=0x54` (ALU-forwarded store) -- confirmed independently 3x
   (`carrier_p2.metal`'s own compile, `pilot_extmode.metal`'s own compile,
   `carrier_p3.metal`'s own compile). Refines `db.json`'s current "value
   register supplied implicitly" note (EXP-0082) into a concrete formula.
   `isa_helpers.device_store(data_reg=...)` implements this.
8. **A second load+iadd2+store ("echo") sequence appended after a first,
   reusing the same index-setup pattern, landed its store at an unexpected
   byte offset** (P2's original two-store design) -- falsified, mechanism
   not isolated in time available. P2's GATED design uses a single
   load-transform-store only. Reported as a negative finding, not hidden.

## Programs under test (frozen; see `casematrix.py::build_cases()`)

- **P1** (`item=P1`, 7 cases): arithmetic dataflow chain. 6 `falu2`/`falu2i`
  ops (fadd/fmul mixed), 3 immediates (boundary-tested at 0/mid/±30 -- the
  representable range of the packed minifloat, `isadb.imm_encode`), one
  register (`R1`) read twice at different points (the liveness pair), one
  INDEPENDENT integer op (verbatim `iadd2` anchor, item 5 above) writing its
  own `out[word4]` slot.
- **P2** (`item=P2`, 10 cases): memory round trip. A computed index
  (`mov_imm`), `device_load` with `idx_off` swept {0, 1000(mid), 2047(max),
  2048(first field-encoding-invalid value, masks to 0)}, `elem_size` code
  swept {0,1,2,3,4}, `base_slot` including the EXP-0083 mirror (`slot+128`),
  an integer transform (`iadd2`, item 5), store to a DIFFERENT computed
  offset (`idx_st`≠`idx_ld`).
- **P3** (`item=P3`, 7 cases): control flow. A real compiled loop (carried
  accumulator, `acc += 1.5` per iteration) + if/else lowered to a
  compare-then-select (`isel10`) join, byte-for-byte reproduced via
  `isadb.decode_one`+`assemble()` from our own compile
  (`kernels/carrier_p3.metal`) -- 0 residual byte diffs after reconstruction
  (verified). Trip count swept {0,1,3(baseline),20}; both select outcomes
  (data-driven, natural threshold 100.0); `icmp_pred`'s loop-guard `cond`
  field flipped 6(s_gt)->7(s_lt) (found by pilot testing to control loop
  ENTRY, not arm-selection as first assumed -- corrected before freezing);
  one deliberate liveness-bit violation.
- **P4**: EXCLUDED, see item 6. Its own diagnostic evidence
  (`work/pilotP4/`) is retained and reported in RESULTS.md as a first-class
  negative result, per this project's standing rule that a failed
  construction is a success for the experiment, not a gap to hide.

## Predictions (frozen, exact -- see `casematrix.py` for every value)

Every case's `oracle` field in `casematrix.build_cases()` IS the frozen
prediction; it was computed by `programs.py`'s pure-Python model BEFORE this
file was written, driven by the pilot findings above (never by observing a
GATED run -- no GATED run exists yet). The corrections listed as "found by
pilot testing" above were incorporated during the SAME informal pre-
registration phase (sanctioned) and are the final, frozen values below --
they will NOT be further adjusted after the gated captures below run.

Two specific liveness-corruption predictions are notable because they
generalize EXP-0086's "later reader sees zero" finding to a WHOLE-PROGRAM
context with MULTIPLE later readers of the same corrupted register:

- P1 `p1_liveness_violate`: flipping R1's FIRST (non-last) read's opflags
  bit0 does NOT corrupt that read itself; it corrupts the SECOND (later)
  read only. Predicted `out0=11.5` (vs `7.5` baseline).
- P3 `p3_liveness_violate`: flipping `acc`'s FIRST reader's bit corrupts
  BOTH the arm computation AND the arm-SELECTION decision (both read the
  same physical register) -- predicted `out0=-3.0` (the false-arm value,
  because the corrupted `acc==0` is also what the select's own comparison
  sees), not merely a corrupted true-arm value.

## Environment / tooling (frozen)

- Target: local Apple M4 (G16G), 10 GPU cores, macOS 26.6.2 build 25G82,
  Metal 4, `clang -fobjc-arc`, `--no-fast-math` throughout.
- Tools: `tools/shdump` (compile our carrier MSL), `tools/agxtest/agxtest.py`
  (splice + run + raw hex readback), `tools/agx-isa` (assemble/disassemble),
  all read-only, invoked as subprocesses.
- Timeouts: 45s per case (`run.py::CASE_TIMEOUT`), 120s host build, 300s per
  gate subprocess.
- 24 cases total (`casematrix.build_cases()`), one fresh process each.

## Confounders considered

- Register-file zero-initialization: an unwritten GPR reads exactly 0.0
  (EXP-0087 MOVE-04, independently re-confirmed by every P1 case's seed
  step) -- used deliberately as the "immediate seed" mechanism for P1's
  inputs; this is a DESIGN CHOICE (avoiding item 3's unresolved bridge), not
  an oversight, and is documented as such in `programs.py::build_p1`'s
  docstring.
- Carrier buffer-slot assignment is NOT literally `buffer(N)->base_slot=N`
  in general (P3's own carrier maps buffer(1)->base_slot=2 and
  buffer(2)->base_slot=1); every carrier's true mapping was independently
  re-derived by forcing a `tid`-indexed reference to each buffer and
  disassembling the result BEFORE being relied upon (see PROGRESS.md).
- `device_store`'s address-formula unit for `idx_off` is 16 bytes (not 4) --
  EXP-0082's own finding, re-confirmed here (P1's second output landed at
  word 4, not word 1, when `idx_off=1`); every oracle byte offset in
  `casematrix.py` is computed via `isa_helpers.store_byte_offset`, never a
  naive `idx_off*4` guess.

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own carrier MSL (kernels/*.metal), our own
  hand-assembled instruction bytes (isa_helpers.py/programs.py via
  tools/agx-isa's read-only assemble()), our own splice+run harness
  (harness/case_exec.py over tools/agxtest/agxtest.py).
Apple binary introspection: NONE.
```
