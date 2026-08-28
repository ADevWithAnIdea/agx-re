# PRE-REGISTRATION — EXP-0141 M4 memory/atomic/fence family: emission, not decoding

**Frozen:** 2026-08-28, before either gated run.
**Target:** local Apple M4 / G16G only (`Mac16,10`, macOS 26.6.2). A18 Pro is
hands-off; M5 is out of scope. Every claim below is an M4 claim.
**Repository revision pinned at pre-registration:** `f17938ee0105c8f1fb1e1c25be3aa22fa4a77a5c`
(dirty: sibling experiments EXP-0133/0139/0140 untracked). Per `SUBAGENT_BRIEF.md`
this revision is **recorded, not gated**: a capture is valid if the authored blob
hashes in `CAPTURE_CONTRACT.json` match, regardless of where `HEAD` moves.

---

## 1. Question

`APPLE9_RE_IMPLEMENTATION_GAPS.md` DOC-02 / `docs/evidence-classification.md`:
58 of the 81 fields of the ten memory/atomic/fence instructions
(`atomic_mem atomic_rmw atomic_tg dev_scoreboard_fence device_load device_store
mem_fence mem_fence8 tg_addr_compute threadgroup_barrier`) are below
emitter grade, and the family gates every load, store and atomic a compiler emits.

The single named blocker is `device_load.dst_lo` / `dst_ext9`
(`single-template-inference`): `EXP-0112`'s generator produces 100 correct random
DAGs only by copying these two fields **verbatim** from a compiled shader.
`EXP-0101` established that the ALU-visible destination register is
`device_load.extmode / 2` and that `EXP-M4-13`'s `dst = dst_lo | (dst_ext9 << 2)`
is **refuted**, but it never swept `dst_lo`/`dst_ext9` — it only showed that
`(1,1)` works and that four derived alternatives break the load.

**This experiment asks: as a function of the target register, what must
`dst_lo`/`dst_ext9` contain — or are they derived / inert / a descriptor of
something else entirely?** And, for the remaining 56 fields: can an emitter
choose arbitrary values, and what happens when it does?

## 2. Hypotheses, each with its pre-registered refuter

**H1a — `extmode` is a register selector with a don't-care low bit.**
The ALU-visible destination is `extmode >> 1`; `extmode` bit 0 is a don't-care.
*Predicted observation:* over `extmode` = 0..255 DENSE, each paired with a
consumer reading `r(extmode >> 1)`, the program yields `-7.0` for every value
except where the target register is itself unusable (`EXP-0112`: `r126/r127`
fault; `R in [64,112]` aliases `r(R mod 64)`, which this program tolerates
because the consumer's own register field aliases identically).
*Refuter:* an even `extmode` whose paired consumer silently zeroes, or an odd
value behaving differently from its even neighbour.

**H1b — `dst_lo`/`dst_ext9` do NOT encode the target register.**
The SET of `(dst_lo, dst_ext9)` pairs that keep the load working is **identical**
at target registers 3, 7, 20 and 33.
*Refuter:* the working set differs between any two of those target registers —
which would mean the pair IS (part of) a register field and `EXP-0101`'s
"copy it verbatim" advice is target-dependent.

**H1c — the working set is larger than the single verbatim token `(1,1)`.**
`dst_ext9` was originally named `dst_width`; we predict the pair is a
destination *descriptor* (width/count/valid), so a structured subset of the 512
encodable combinations will work, and that subset will be describable as a rule
an emitter can apply.
*Refuter (explicitly registered as the live alternative):* exactly one of the
512 combinations works at each target register, i.e. the field really is an
opaque per-shape token and the family stays "decodable, not yet emittable".

**H2 — `device_store.addr_mode` bit 1 is a live DATA-SOURCE selector, not inert.**
`0x54` selects the ALU-computed source, `0x56` the direct live load-result. This
CONTRADICTS `validation.json`'s current `device_store.addr_mode` range text
("bit1 ... INERT here", `EXP-0119`), which was measured only with an
ALU-computed source.
*Predicted observation:* in the ALU program `0x54` works and `0x56` fails (or
vice-versa); in the load-forward program the opposite. *Refuter:* both values
work in both programs (genuine inertness).

**H3 — exactly one byte of `atomic_mem` selects the RMW operand register.**
`db.json`'s own semantics say the operand register "is implicit (supplied by the
preceding op / amode)" and `DOC-02` ranks this a **missing field**. The carrier
keeps `a[1] = 1007`, `a[2] = 2007`, `a[3] = 3007` live across the atomic while
`a[0] = 7` is the operand.
*Predicted observation:* some value of some byte in `+1..+13` makes the counter
read 1007 / 2007 / 3007 (or their sum/AND with 0), identifying the selector.
*Refuter:* no byte value in the whole 13 x 256 dense sweep ever produces a
counter equal to any of the other live registers — the operand really is not
encoded in the instruction.

**H4 — `threadgroup_barrier.flags` (byte+4) and `b5` (byte+5) do not carry the
fence.** `mem_scope` (byte+3) does. *Predicted observation:* all 512 swept
values of `flags`/`b5` leave the 256-lane tile litmus exact. *Refuter:* some
`flags` value reproduces the stale-read failure with `mem_scope` intact.

**H5 — `tg_addr_compute`'s byte0 high nibble and byte+1 are operand selectors
that `db.json` does not model** (`EXP-M4-14`, A18). *Predicted observation:*
a dense M4 sweep of byte0, byte+1, byte+2 changes the tile dataflow for some
values and not others, and the map is recoverable. *Refuter:* both bytes are
inert on M4 (which would be an A18<->M4 divergence, reported not resolved).

**H6 — `dev_scoreboard_fence.scope_flag` accepts arbitrary values.**
No own-MSL kernel we could compile emits `80 02 00 xx`, so the instruction is
SYNTHESISED into the validated load->ALU->store program. *Predicted
observation:* all 256 `scope_flag` values execute and leave the surrounding
dataflow at `-7.0`. *Refuter:* some value faults or corrupts the dataflow.
**Declared limitation, frozen now:** this carrier has no memory-ordering
observable, so a pass bounds *acceptance and dataflow-inertness only* and will
NOT be labelled `hardware-run` for ordering semantics.

## 3. Independent / controlled variables

Independent: exactly one field (or one byte) per case. Controlled: everything
else in the program, the carrier, the dispatch shape, the input buffers, and the
oracle. Coverage per `FIELD-SWEEP-PROTOCOL.md` 3.3: every field of width <= 8
is swept **densely over all 2^w values**; the one wider field pair
(`dst_lo` x `dst_ext9`, 9 bits) is swept over its **full 512-value product**.

## 4. Oracles

Host-computed in `carriers.py` from the MSL **we wrote**, never read off a GPU
run, and checked against the UNSPLICED carrier before any mutation:

| carrier | oracle |
|---|---|
| `synth` | per case: `-7.0` (load -> falu2i(+1.5) -> store) or `-8.5` (load -> store forward) |
| `atdev` | `o[0] = 7`, `dbg = [1007, 2007, 3007, 0]` |
| `atdevimm` | `o[0] = 5000`, `dbg = [7, 1007, 2007, 3007]` |
| `attg` | `o[0] = sum(a[0..15]) = 120112`, `o[1] = a[8] = 8007` |
| `tgtile` | `o[i] = ((i+1)&255) + ((i+2)&255)` for all 256 lanes |
| `devfence` | `o[i] = 65558 + i`, `c = 65558` |

Silent-zero signatures are pre-declared: `out0 == 1.5` (ALU program, `srcA` read
as 0), `out0 == 0.0` (forward program), all-zero output (splice carriers).

## 5. Falsifiers (arm `CTRL` / `CTRL_SPLICE`, `expect_match = False`)

1. `device_load` `dst_lo=dst_ext9=0` with `extmode` correct -> must silently zero.
2. `device_load` `extmode = 0` with the consumer reading `r7` -> must silently zero.
3. `device_store` forward-source store with `addr_mode = 0x54` -> must store 0.
4. `atomic_mem` op `add(0x20) -> and(0x22)` -> counter must become 0, not 7.
   (`xchg(0x3C)` was **rejected** as a falsifier during harness smoke: with a
   zero-initialised counter both `add` and `xchg` yield 7, so it could not
   detect the change. Recorded here rather than silently swapped.)
5. `atomic_tg` op-selector bit flip -> the threadgroup reduction must change.
6. `threadgroup_barrier` `mem_scope 0x61 -> 0x00` -> the tile litmus must break.

A run in which any `expect_match` case disagrees with its prediction is a STOP,
not a result to be reinterpreted.

## 6. Known confounders, and how each is handled

1. **Innocent-victim transients.** A GPU fault poisons subsequent command
   buffers, which return `kIOGPUCommandBufferCallbackErrorInnocentVictim /
   Discarded (victim of GPU error/recovery)`. Handled by a bounded retry that
   fires ONLY on that error text; every attempt's status is kept in the record.
   Established in this experiment's own pilot (`PROGRESS.md` M3).
2. **Archive-path reuse.** Overwriting one splice archive filename across
   persistent-runner requests produced 28/360 spurious `CMDBUF_ERROR` on
   byte-identical known-good archives; a unique path per request gave 0/360.
   Every request now gets its own inode. (Pilot, `PROGRESS.md` M3.)
3. **Register aliasing.** `EXP-0112`: a register field value R in [64,112]
   aliases `r(R mod 64)`; 126/127 fault. The index register is chosen per case
   to avoid the swept target's alias class (`isa_helpers.pick_idx_reg`).
4. **`mov_imm` width.** `dst` is 4 bits and `imm7` is 7 bits (`EXP-0128`:
   128..255 silently zero), so the index register lives in r0..r15 and only ever
   holds 0.
5. **Re-tokenization.** Sweeping a byte that participates in another
   instruction's `match` (e.g. `device_load` byte+1 == 0x01 is `atomic_mem`'s)
   changes how OUR decoder reads the program. The round-trip result is recorded
   per case (`"rt"`), never asserted, except on controls where a failure is a
   build-time stop.
6. **Buffer initialisation.** The atomic oracles assume zero-initialised output
   buffers; verified 120/120 unmutated runs per carrier in the pilot.
7. **Padding.** Synthesised programs pad with `mov_imm(r13,0)` AFTER `stop`, so
   padding never executes.

## 7. Frozen procedure

Two independent gated runs, `m4-20260828-run01` and `m4-20260828-run02`, each
into its own append-only `raw/<run_id>/`. Run 02 is a full independent repeat,
not a top-up. Per-case record appended and `fflush`+`fsync`ed immediately.
`PROGRESS.md` entry per milestone. Per-request watchdog 8 s; per-arm hang budget
2 (arm ABORTED and reported PARTIAL); per-carrier hang budget 6.
**No `db.json`, `validation.json`, `docs/`, `PROVENANCE.md` edits. No `git commit`.**

## 8. Disclosed pilot

Mechanics-only pilot runs were made into `work/` (never `raw/`) before freezing:
carrier compilation, oracle checks against the UNSPLICED kernels, persistent-runner
throughput, the two harness defects in section 6.1/6.2, and a rerun of
`EXP-0101`'s own known construction. The pilot established that the harness can
see a difference; it did not test any hypothesis in section 2. Pilot artifacts
are retained in `work/` and are not evidence.

## Clean-room provenance

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected: our own MSL (kernels/*.metal), our own hand-assembled AGX
  programs (tools/agx-isa isadb.assemble), our own compiled shader bytes
Apple binary introspection: NONE
Reproduction: python3 -B run.py --run-id <id> --execute
Evidence: raw/<run_id>/sweep.jsonl (append-only), raw/<run_id>/00_manifest.json
```
