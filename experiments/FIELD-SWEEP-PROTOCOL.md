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

## 7. Run everything in parallel. Instrument instead of serializing.

**There is no GPU lease. Run every sweep concurrently and unlocked.** The GPU has many hardware
contexts and they isolate ordinary work correctly. This section replaces three earlier attempts
(a blanket lease, then unlocked-with-majority-of-3, then a lease for fault verdicts only) — each
was wrong in the same direction: they treated a **detectable, recoverable** event as a reason to
serialize, and serializing cost far more than the contamination did. One bulk run once held the
device for 14 minutes with eight agents queued behind it.

### What actually happens

A GPU **hang** triggers a device-level reset. That reset kills in-flight command buffers in *other*
contexts — correct recovery behaviour, not a context-isolation failure. Concurrency is not the
problem; hangs are, and only briefly.

### The three instruments that make it a non-issue

**1. Poison your read-back buffer.** Fill every output with `0xDEADBEEF` before dispatch. This is
the single most important one, because it distinguishes the three outcomes that otherwise look
alike: *wrote the right value* / *wrote a wrong value* / **never ran at all**. On this ISA a wrong
field value usually produces a silent zero, so a zero-initialised buffer cannot tell "wrote 0" from
"did not execute".

EXP-0153 is the proof: five cases passed majority-of-3 **and** agreed across two independent runs,
and were still not faults. Isolation caught it — but so did the buffer, **offline, from data
already captured**: poison everywhere except the pre-test sentinel proved the program ran and that
neither following `device_store` executed. You do not need the device to adjudicate this.

**2. Write an integrity sentinel through a path independent of the instruction under test**, and
put it in a register no descriptor under test can name. A measurement without the sentinel is
`invalid_run` and gets repeated. EXP-0138 lost six sweeps by seeding its sentinel in r11, which the
instruction then read and zeroed.

**3. Record the OS fault-classification string on every non-`ok` case.**
`kIOGPUCommandBufferCallbackErrorInnocentVictim` means "discarded, victim of another context's
error/recovery" — a sibling's reset, not a property of your encoding. Segregate those and re-run.

### The exception, found the hard way: CONFIRMATION runs need a quiet machine

Everything above is right for *sweeps* and stays. It is **not** right for a re-run whose whole
purpose is to confirm an earlier observation, and two experiments established that independently on
2026-08-30:

- **EXP-0160** re-ran cases for confirmation while the machine was busy and the re-run
  **manufactured faults**: `imad` v=186 was `silent_zero` in *both* gated runs and `fault` 3/5 on the
  unlocked re-run. It retracted that path and gated instead on an evidence-validity filter — two
  agreeing clean dumps win outright, since **contamination can destroy an observation but never
  fabricate a coherent one**. That filter is the reusable idea here.
- **EXP-0158** ran its confirmation against 8-12 sibling experiments and got **102 of 174 cases
  giving MIXED outcomes across five runs of byte-identical programs**, with 427 `ErrorHang`
  observations arriving in streaks. Its cross-run gate FAILS and was left failing.

And the instruments are not a complete defence, which is the part to internalise:

- **`InnocentVictim` is not the only contamination signature.** EXP-0158's streaks carried none.
- **A contaminated dispatch can report `STATUS OK` and write nothing.** EXP-0160 saw 25 observations
  with all 16 registers *and both sentinels* still poisoned and no victim string anywhere. Against a
  zero-initialised buffer those would have been 25 confident `silent_zero`s.

**So: sweep unlocked, but do not treat a busy-machine re-run as confirmation.** For a confirmation
or re-validation pass, either (a) get a genuinely quiet machine — coordinate it with the
orchestrator, who owns the window — or (b) adjudicate offline from the poisoned buffer and the
sentinel, per EXP-0160's filter, and say in `RESULTS.md` which of the two you did.

**Do not reinstate a lease to solve this.** `~/agxre/gpulease.sh` is a passthrough shim that takes
no lock; it is deliberate, and a private lock nobody else is pointed at buys exclusivity you would
still have to verify by other means. If you need a quiet window, ask for one and **record concurrent
GPU activity for the duration** (sample the process table into `raw/`) so "the machine was quiet" is
a measurement rather than a claim.

### The one remaining rule

**Never conclude `fault` from a single observation.** Re-run every `fault`/`hang`/victim case,
majority-of-3 minimum, and adjudicate from the poisoned buffer where you can. EXP-0139 would have
labelled **692 legal field values as `fault`** without this; EXP-0144's revalidation reached a
**0.02% hang rate** purely by re-running victims.

### Courtesy, not a rule

If you are about to sweep a region you *know* hangs — `fspecial` byte+3 ≥ 192, control-flow
displacement sweeps, `atomic_tg` byte+5 `0x7E`/`0x7F` — say so in `PROGRESS.md`. A hang resets the
device for everyone, and it is useful for the orchestrator to know which agent caused it. Do not
serialize for it.

## 8. Safety — this host has no out-of-band recovery

`mov_imm.imm7` values 128..255 silently zero, and combined with `iadd2`'s N=0 self-read this
produced **two real GPU hangs** in EXP-0128. Expect more.

- One hypothesis per dispatch; hard timeout on every request; use the persistent runner's watchdog.
- Append + `fflush` every case as it completes. Never buffer to write at the end.
- `PROGRESS.md` entry per milestone.
- **After two genuine hangs in one area, STOP that arm** and report it PARTIAL, as EXP-0128 did.
  A partial sweep honestly bounded is worth more than a wedged host.
- Never `macvdmtool`. Never touch the A18. Never write outside your experiment directory.
