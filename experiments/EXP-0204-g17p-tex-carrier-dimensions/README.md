# EXP-0204 — texture: four fields, and the carrier dimension each one needed (G17P)

**Question.** Four fields block four texture instructions from being emittable. For each:
*can an emitter choose this field's value and get documented hardware behaviour?*

| instruction | field | prior status |
|---|---|---|
| `tex_sample` | `mode` | `untested` — never swept; 2 values spliced in RT-5, no per-value records |
| `tex_deriv` | `dstsrc` | `untested` — EXP-0189 withheld **UNSTABLE**: 198 observations moved, but the cross-run partition did not reproduce |
| `tex_write` | `amode` | `untested` — EXP-0163: "swept densely on 6 arms but only **2 distinct carriers** with proven detection power (the bar is 3)" |
| `tex_write` | `rsv11` | `untested` — identical refusal |

**Hypotheses, variables, refuters, confounders, oracles and the promotion gate:**
`PRE_REGISTRATION.md`, frozen before any build or device run (§14 is the amendment log — five
amendments, all during pre-freeze calibration, none touching a hypothesis or the gate).
**Frozen contract, pinned ISA-DB hash, timeouts, raw schema:** `CAPTURE_CONTRACT.json`.
**Observations vs interpretation:** `RESULTS.md`. **Machine-readable verdicts:**
`analysis/field_verdicts.json`.

**Clean-room category: OWN-SHADER + HW-PROBE.** Every byte spliced, decoded or inspected is the
compiled form of MSL in `kernels/`, produced by the public Metal API from source we wrote. **No
Apple binary was disassembled, decompiled, symbol-dumped, strings-scanned or introspected at any
point.**

**Target: Apple A18 Pro / G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6, Metal
family Apple9), host `users-MacBook-Neo.local`. Nothing was run on the M4.

## The one idea this experiment is built on

`docs/isa/emit-worklist.md` line 7: *a field that never moves is promotable only if the carriers
differ **in the dimension the field controls**; two carriers identical in that dimension are ONE
carrier.* This corpus has been burned by it twice, both times on texture — `tex_sample.samp_extra`
(256/256 inert on nine arms, moved on 128/256 on the tenth) and `iter_at.loc` (inert on every arm
until `rasterSampleCount` was varied).

So the work here is mostly **carrier design**, and each carrier states the dimension it moves in:

| field | dimension it controls | what the prior carriers all shared | what EXP-0204 varies |
|---|---|---|---|
| `tex_sample.mode` | the **sample-operation class** (`0x10` filtered / `0x00` gather-read-compare / `0x20` LOD query) | no carrier had ever emitted an **LOD query** at all | six carriers, one per class: filtered implicit-LOD, filtered explicit-level, gather, integer read, depth-compare, `calculate_clamped_lod` — needing a **mipmapped** sampled texture, which the harness gained |
| `tex_deriv.dstsrc` | the derivative's **destination and source registers** | one program (EXP-0172's `k_deriv`) | that same program **unchanged** (this is a re-measurement, not a new experiment) plus a second with a different allocation: derivatives of ALU temporaries and half-precision derivatives |
| `tex_write.amode` | the **address form / operand sourcing** — the same byte position and the same `0x44/0x54/0x56/0x64` vocabulary as `device_load.addr_mode` / `device_store.addr_mode` | every write ever swept was `write(colour, uint2(LITERAL, LITERAL))` at implicit level 0, and every arm's baseline was `0x54` | explicit mip level, `texture_buffer` (linear 1-D), cube face, register-formed coordinate, and a contiguous vec4 store with no ALU between load and write |
| `tex_write.rsv11` | the **write-data format descriptor tail** (positional sibling of `device_store.st_desc_hi`, whose neighbour is set only for a non-4-component store) | every destination ever swept was **4-component** | 1-component `R32Float` and 2-component `RG32Float` destinations |

## What makes a null mean anything here

- **Per-arm detection profile** before any sweep: every field of the instruction, complemented and
  zeroed, recorded with whether the observation moved and whether the bytes still decode as the
  same mnemonic *in context*. An arm with no status-OK same-mnemonic control that moves is barred
  from supporting any verdict, inert or live.
- **A dimension-specific positive control** (`FIELD-SWEEP-PROTOCOL.md` §9 rule 1) on top of that:
  the arm must show a control **in the field's own dimension** moving.
- **A host-computed oracle that can fail.** `harness/oracle.py` predicts each carrier's baseline
  exactly, from the triangle our own vertex shaders draw (all three vertices have `w == 1`, so
  every varying is affine in screen space) and the texture content `gfrun4.m` itself writes. It is
  checked on every baseline and every baseline re-validation.
- **Faults and `undecodable` are counted separately from movement** — a GPU fault is not movement,
  and neither is our own disassembler failing to decode.
- **The width-1 gate is written literally** as `moved >= 2*disagree AND moved > 0`, and
  `analysis/verdicts.py::selftest()` proves it promotes a 1-bit field with 0 disagreements and
  refuses a field with 0 moved, before any verdict is computed.
- **No verdict cites a round trip, `rt_ok`, or tokenization.**

## Layout

| path | what |
|---|---|
| `PRE_REGISTRATION.md`, `CAPTURE_CONTRACT.json` | the frozen contract (hypotheses, oracles, gate, hashes, amendment log) |
| `kernels/*.metal` | **our own MSL**, one file per carrier |
| `harness/carriers.py` | carrier table + the authored `DIMENSION` and `DECLINED` tables |
| `harness/arms.py` | the FROZEN arm list (generated by `analysis/gen_arms.py`, asserted byte-exact at run time) |
| `harness/oracle.py` | the host-computed oracles |
| `harness/gfrun4.m` | render/splice/read-back runner (fork of our own EXP-0172 `gfrun2.m` + five new surfaces) |
| `harness/runner4.py` | persistent-runner driver with the §3(d) per-child reader-thread fix |
| `pinned/` | the ISA DB snapshot every decode in this experiment used |
| `run.py` | the capture driver |
| `analysis/census.py` | pre-freeze calibration (no verdict may cite it) |
| `analysis/verdicts.py` | verdicts, recomputed from `raw/` only |
| `analysis/cube_probe.py` | the tier-3 `cubearray_coord_const` synthesis probe (no promotion possible) |
| `raw/prefreeze/` | **calibration only** |
| `raw/g17p_*` | append-only gated evidence, one JSON object per case, plus `procs.jsonl` — the machine-quiet **measurement** |

## Commands (as run)

```sh
# on the neo, under this experiment's OWN pinned tool tree
sh harness/sync.sh push && sh harness/sync.sh build
python3 analysis/census.py run2            # calibration -> raw/prefreeze/
python3 analysis/gen_arms.py               # -> harness/arms.py, then frozen
python3 run.py --run-id smoke01 --smoke-only   # baselines + detection profiles
python3 run.py --run-id g17p_20260830_runNN --deadline-s ...
python3 analysis/cube_probe.py
# on the repo host
python3 analysis/verdicts.py               # -> analysis/field_verdicts.json
python3 ../../tools/agx-isa/wave_audit.py .   # the arrival gate, run before reporting
```
