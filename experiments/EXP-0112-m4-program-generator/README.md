# EXP-0112 -- M4 program generator (DRV-ISA-01 / P0.6 generation proof)

## Question

Can a compiler backend for this ISA be built from the documented per-family
field rules alone, i.e. does a GENERATOR (not more hand-built programs) that
composes those rules over randomly-shaped dataflow DAGs produce correct
programs at scale, and if not everywhere, exactly where does it fail?

## Method

`generator.py` builds a dataflow DAG from a seeded RNG (structure pass),
allocates a 14-register pool with reuse (linear-scan allocator, provably
bounded live-count), then emits real AGX9 bytes via `isa_helpers.py`
(itself a thin wrapper over `tools/agx-isa`'s own `isadb.assemble()`) while
computing an independent host-side oracle. `families.py` adds three
narrower, systematically-swept single-field families (REGBOUNDARY,
IADD_ANCHOR) plus deliberate rule-violation ADVERSARIAL cases. `cf.py`
reuses EXP-0090's own validated loop+if/else control-flow skeleton,
parameterized by data. `casematrix.py` assembles the full, deterministic,
161-program corpus. Every program is spliced over a real compiled carrier
kernel and run on real M4 hardware (`tools/agxtest`), compared bit-exactly
against the host oracle.

Full method, frozen seed/recurrence, and pass criterion: `PRE_REGISTRATION.md`.
Results, failure taxonomy, and the DRV-ISA-01 generation-envelope statement:
`RESULTS.md`.

## Reproduce

```sh
python3 -B verify.py --selftest       # no GPU
python3 -B verify.py --seqtest        # no GPU
python3 -B verify.py --preflight      # no GPU (before run01)
python3 -B baseline.py                # GPU-adjacent: compile-only carrier re-derivation
python3 -B run.py --run-id m4-20260828-run01 --execute
python3 -B verify.py --between-runs   # no GPU (before run02)
python3 -B run.py --run-id m4-20260828-run02 --execute
python3 -B verify.py --captured       # no GPU
```

## Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: this experiment's own authored generator/harness code and
  carrier MSL, plus tools/agx-isa's read-only isadb (no edits).
Apple binary introspection: NONE.
Reproduction: see above.
Evidence: raw/m4-20260828-run01/, raw/m4-20260828-run02/
```

## Deliverable conventions

Do NOT `git commit` (orchestrator owns commits). `tools/*` read-only. All
files live inside this experiment directory (including `work/` scratch).
