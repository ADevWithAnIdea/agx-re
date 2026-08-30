# Field-sweep protocol — how to move a field to `hardware-run`

**Read with** `../CLAUDE.md`, `../CODEX.md`, `SUBAGENT_BRIEF.md`, and
`../docs/evidence-classification.md` (the label definitions this protocol serves).

**Purpose.** 777 of 1026 ISA fields are not emitter-grade, and the goal is to *emit* every real
instruction, not merely decode it. This protocol defines what a sweep must prove and what it must
record, so eleven agents working in parallel produce evidence that merges mechanically instead of
eleven incompatible harnesses.

---

## 1. The bar you are clearing

From `docs/evidence-classification.md` §2:

> `hardware-run` requires that **arbitrary operands executed**, not that the instruction executed.
> To claim it you must have run values the compiler would not have chosen — boundaries, holes, and
> out-of-range — and recorded what happened, including the silent zeros.

Compiling a shader that happens to use the field is **not** evidence. Round-trip is **not**
evidence. You are proving an emitter can choose a value and get the documented behaviour.

## 2. Use the existing tools — do not rebuild them

- `tools/agxtest/agxrun_persist` + `tools/agxtest/persistrun.py` — the persistent runner. One live
  device for the process lifetime, **logs and continues past contained command-buffer faults**, so a
  256-value sweep is one launch, not 256. It already has the per-request watchdog.
- `tools/agxtest/agxrender.m` — the render/fragment analogue, for FRAG/TEX/varying work.
- `tools/shdump/` — compile our MSL, locate `_agc.main` for in-place splicing.
- `tools/agx-isa/` — `db.json` is now the **single source of truth** (`isadb.py` loads it).
  Use `isadb.py` to assemble/disassemble; do not hand-compute byte offsets.

## 3. Required sweep shape, per field

For field `F` of width `w` in instruction `I`:

1. **Baseline.** Capture the unmutated program's output first. Every later case is a delta against it.
2. **Carrier.** State which carrier shader you spliced into, and why the field is *live* on the
   observed output path. A field whose value cannot reach the output proves nothing —
   EXP-0129 lost its fragment-stage arm exactly this way, and reported it rather than faking it.
3. **Coverage:**
   - `w <= 8` → **sweep all 2^w values**, densely. This is cheap on the persistent runner.
   - `w > 8` → boundaries `{0, 1, 2, max-1, max}`, all power-of-two values, and ≥16 interior
     samples including asymmetric ones. Never only 0/1.
4. **Oracle.** A host-computed expected value per case, independent of the GPU. Say how it was
   derived. "It looked right" is not an oracle.
5. **Falsifier.** At least one case pre-registered to *fail*. If everything passes, the sweep proves
   nothing about your ability to detect a difference. EXP-0136's address-mode code 5 is the model:
   it showed the method could still see a real difference.
6. **Record the silent zeros.** On Apple9 a wrong field value usually yields a **silent zero, not a
   fault**. A value that produces zero is a *result*, not a skipped case.

## 4. Required record, per case — emit exactly these keys

Append one JSON object per case to `raw/<run_id>/sweep.jsonl`, flushed immediately:

```json
{"instr":"falu2","field":"mod_lo","value":3,"bytes":"09051c0100c0",
 "observed":{"out0":7.0},"oracle":{"out0":7.0},"match":true,
 "outcome":"ok","carrier":"carrier_dag","note":""}
```

`outcome` ∈ `ok` | `silent_zero` | `wrong_value` | `fault` | `hang` | `undecodable`.
`fault`/`hang` are results; keep them.

## 5. Verdict per field — write `analysis/field_verdicts.json`

```json
{"falu2.mod_lo": {"label":"hardware-run",
                  "range":"0..7 dense (all 8 values)",
                  "target":"M4",
                  "evidence":["EXP-0140"],
                  "semantics":"...",
                  "note":"values 5..7 silently zero"}}
```

Use the **eight labels from `docs/evidence-classification.md`** and nothing else. If a sweep is
inconclusive, say `corpus-correlation` or `untested` — do not round up. The orchestrator merges
these into `tools/agx-isa/validation.json` and re-runs `validate_labels.py`, so a dishonest label
becomes someone else's silent-zero bug.

## 6. When a field turns out not to be a field

Several descriptors are wrong, not merely unlabelled. If a sweep shows the modelled boundaries do
not match the hardware — a "field" that is really two, a live byte `db.json` does not expose, a
length that swallows the next instruction's leader — **that is a first-class result**. Record the
corrected model in `field_verdicts.json` under `"db_defects"` with the evidence. Do **not** edit
`db.json`; the orchestrator owns it and eleven agents editing it concurrently would corrupt it.

Already known and flagged `emit_unsafe` in `db.json` — do not re-derive, but do respect them:
`half_alu_fma12`, `falu2_ext8b`, `op04_len8` (lengths over-consume the following leader),
`vary_store` (0x57/byte+2=0x54 collision), `tg_addr_compute` (over-fitted match, two live operand
bytes unmodelled), `falu_srcmod12b` (`opsel==4` corrupts an unrelated register).

## 7. Concurrent sweeps CONTAMINATE each other — mandatory mitigation

**Found the hard way, 2026-08-28, by two agents independently.** EXP-0143 reported its command
buffers becoming *"innocent victims"* of sibling agents' faults; EXP-0147's smoke run hit a GPU
**error cascade**. Ten agents driving one GPU with deliberately illegal encodings is
self-defeating: another agent's contained fault surfaces in *your* command buffer as a failure,
and a spurious `fault` recorded against a legal field value becomes a confident wrong label in
`validation.json`.

This is the same class as the `...ErrorInnocentVictim` vs `...ErrorHang` distinction EXP-0136 had
to exclude from its cross-run gate.

**Required of every sweep from now on:**

1. **Never treat a single `fault`/`hang` observation as a property of the field.** Re-run any
   faulting case at least once. A value is only `fault` if it faults *reproducibly*, in isolation.
2. **Record the OS fault classification string**, not just the status. An
   `ErrorInnocentVictim`-class failure is evidence about the *machine*, not about your encoding —
   segregate those from your gated comparison the way EXP-0136 did.
3. **Re-validate the baseline periodically mid-run.** If the unmutated carrier starts failing, you
   are in a cascade: stop, note where, and resume in a fresh process rather than recording the
   cascade as data.
4. **Say in `RESULTS.md` how many other GPU experiments were running concurrently.** If you cannot
   tell, say that. A sweep run alone and a sweep run against nine siblings are not the same
   evidence, and the reader must be able to tell which they are holding.

The orchestrator schedules GPU-contending experiments in small batches for this reason. If your
dispatch says you are in a batch, the other members are named; desk-only work (modelling,
classification, corpus analysis) is unaffected and can run alongside anything.

## 7A. ⚠ majority-of-3 is NOT sufficient for a `fault` verdict (EXP-0153, 2026-08-29)

EXP-0153 found the limit of §7's scheme, and it matters. Five `F_imm_top` cases were recorded as
reproducible **faults** in two unlocked gated runs — **each passed majority-of-3, and the two
independent runs agreed with each other.** Re-run under the GPU lease, 5× each, **four of them are
not faults at all** (`wrong_value`, 5/5).

**Cross-run agreement did not defeat sustained sibling load. Only isolation did.** Under continuous
concurrent pressure, contamination can be systematic enough to look reproducible *and* to survive an
independent second run.

**So the rule is:** run bulk sweeps concurrently and unlocked, but **confirm every `fault`/`hang`
verdict under `~/agxre/gpulease.sh` before promoting it.** Faults are the one verdict class where
the cheap mitigations are insufficient.

There is often a cheaper adjudication than re-running. In EXP-0153's case the corrected reading was
provable **offline from the committed digest**: the read-back buffer was poison everywhere except
the pre-test sentinel, which proves the program ran and that neither following `device_store`
executed. **Poison your read-back buffer** (`0xDEADBEEF`) and much of this can be settled from
already-captured data.


## 8. Safety — this host has no out-of-band recovery

`mov_imm.imm7` values 128..255 silently zero, and combined with `iadd2`'s N=0 self-read this
produced **two real GPU hangs** in EXP-0128. Expect more.

- One hypothesis per dispatch; hard timeout on every request; use the persistent runner's watchdog.
- Append + `fflush` every case as it completes. Never buffer to write at the end.
- `PROGRESS.md` entry per milestone.
- **After two genuine hangs in one area, STOP that arm** and report it PARTIAL, as EXP-0128 did.
  A partial sweep honestly bounded is worth more than a wedged host.
- Never `macvdmtool`. Never touch the A18. Never write outside your experiment directory.
