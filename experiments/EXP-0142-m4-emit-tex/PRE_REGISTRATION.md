# EXP-0142 — PRE-REGISTRATION (FROZEN)

**Frozen:** 2026-08-28. Nothing below may be edited after the first gated run starts.
**Repo revision at freeze:** `7faf0db77813ca4416d10b60e3424ee177215273` (working tree dirty:
48 paths, all owned by *sibling* experiments plus this experiment's own pre-freeze
calibration; per `SUBAGENT_BRIEF.md` a capture is valid if the **authored blob hashes**
below match, and sibling commits moving `HEAD` are **not** contamination).
**Target:** local Apple M4 / G16G, 10 GPU cores, macOS 26.6.2 (25G82), Metal 4. No other
target is touched. The A18 Pro is hands-off; M5 is out of scope.

---

## 1. Question

`DOC-02` names texture sampling's coordinate and result registers among the top untested
blockers in the whole ISA. **46 fields across six texture/imageblock instructions are
below the emitter bar**, so a driver cannot today choose where a sample's coordinates come
from or where its result lands. This experiment moves as many of those 46 to
`hardware-run` as the fault budget allows, `tex_sample` first.

Blocking fields at freeze (from `tools/agx-isa/validation.json`), 46 total:

| instruction | blocking fields |
|---|---|
| `tex_sample` (9) | `kind` `chain` `comp_flags` `result_sel` `coord` `extra_coord` `lod_present` `tex_type` `samp_extra` |
| `tex_coord_setup` (10) | `dst_lo` `b1` `subop` `srcA` `form` `b5` `b6` `idx` `b8` `b9` |
| `tex_write` (13) | `coord_pack` `amode` `seq_idx` `layer_reg` `coord_regs` `rsv8` `coord_dim` `rsv10` `rsv11` `wop` `data_desc` `data_desc_hi` `rsv15` |
| `tex_deriv` (4) | `b1` `dstsrc` `src_comp` `tail` |
| `imageblock_load` (5) | `dst` `b4` `b6` `fmt` `tail` |
| `imageblock_store` (5) | `src` `b4` `b6` `fmt` `tail` |

## 2. Falsifiable hypotheses

**H1 (tex_sample operand fields are real and emitter-choosable).** Each of `coord`,
`result_sel`, `extra_coord`, `comp_flags`, `chain`, `kind`, `lod_present`, `tex_type`,
`samp_extra` occupies the byte `db.json` assigns it, and splicing an arbitrary value into
that byte changes **only** the sampled result of the bundle spliced — either to another
determinable texel value, or to the Apple9 silent zero.
*Refuter:* a byte sweep that leaves all eight sampled quads bit-identical to baseline for
all 256 values (the field is inert / not where `db.json` says), **or** one that perturbs a
quad other than the spliced bundle's while the spliced bundle is unchanged (the field is
not a per-bundle operand). Either outcome is recorded as a `db_defect`.

**H2 (tex_write operand fields address a specific texel and a specific colour).** Splicing
`coord_pack` / `coord_regs` / `coord_dim` / `layer_reg` relocates or suppresses **exactly
one** of the three writes; `data_desc` / `data_desc_hi` change **which colour** lands;
`rsv8` / `rsv10` / `rsv11` / `rsv15` are inert for every value 0x00..0xff.
*Refuter for the rsv claim:* any value of an `rsv*` byte that changes any texel.

**H3 (tex_deriv `axis` is the only live selector at byte+6, and `src_comp`/`dstsrc` choose
the source varying and destination register).** With four derivatives whose host-known
values are `(A,B,C,D) = (1,2,4,8)`, splicing `axis` on derivative 0 from `0x92` to `0x90`
must change the **red** channel from `A = 1.0` to `B = 2.0`; splicing `src_comp` from
`0x04` to `0x08` must change red from `A = 1.0` to `C = 4.0`.
*Refuter:* red stays `1.0` in both cases → the fragment derivative arm is **not live** and
is reported dead exactly as EXP-0129 reported its dead arm, not assumed.

**H4 (tex_coord_setup feeds one sample's coordinate).** Splicing a `tex_coord_setup`'s
`dst_lo` / `srcA` / `idx` changes the sampled value of exactly one of the eight samples,
to another host-determinable texel value or to zero.

**H5 (imageblock_load/store), CONDITIONAL — see §7.**

## 3. Carriers, and how each field is proven live on the observed path

All three carriers were compiled and **executed before the freeze**; the calibration
transcript is `raw/prefreeze/carrier_calibration_smoke.txt`. Each reproduced its
host-computed oracle **exactly**, which is what makes them admissible as liveness proofs.

### Carrier A — `kernels/tex_sample8.metal` → `work/frozen/cA_sample8.bin`
Eight independent `t.sample(...)` calls, results in `out[4j..4j+3]`, sentinel in `out[32]`.
Input `work/frozen/inA.bin`: sample *j* reads pixel coordinate `(j+1.5, j+0.5)` of an
R32Float 16x16 texture whose texel is `x + 100*y`, so
**oracle `out[4j] = 101j + 1` = 1, 102, 203, 304, 405, 506, 607, 708**, `out[4j+1..2] = 0`,
`out[4j+3] = 1`, `out[32] = 12345`. Observed at freeze: **exactly that, all 33 words.**
*Liveness:* the eight oracle values are mutually distinct and distinct from 0, so
"this bundle's result changed", "it silently zeroed", "it picked up **another** sample's
coordinates" (the value becomes another member of the known set) and "a different bundle
moved" are four separately identifiable observations at fixed buffer addresses.

Eight `tex_sample` bundles at `_agc.main +0x0102 +0x0110 +0x011e +0x012c +0x013a +0x0148
+0x0156 +0x0164`; fourteen `tex_coord_setup` at `+0x006e +0x0078 +0x0082 +0x008c +0x009e
+0x00a8 +0x00b2 +0x00bc +0x00c6 +0x00d0 +0x00da +0x00e4 +0x00ee +0x00f8`.

### Carrier B — `kernels/tex_write3.metal` → `work/frozen/cB_write3.bin`
Three `w.write(colour, coord)` to an RGBA32Float 8x8 target that `texpersist` **resets to
`(-1,-2,-3,-4)` in every texel before every dispatch**. Input `work/frozen/inB.bin` gives
colours `11,22,33,44` / `55,66,77,88` / `99,110,121,132` at texels `(1,0)` / `(3,2)` /
`(5,4)`. Observed at freeze: exactly that, with every other texel still at the reset value.
*Liveness:* "the write happened", "the write moved to another texel", "the write changed
colour" and "the write did not happen at all" (texel still `(-1,-2,-3,-4)`) are four
distinct observations. Sentinel `out[0] = in[63] = 12345` on a path that never touches the
texture unit. Three `tex_write` at `+0x0114 +0x0124 +0x0134`.

### Carrier C — `kernels/frag_deriv.metal` → `work/frozen/cC_deriv.bin` (render)
Two varyings that are exact affine functions of the **screen pixel coordinate**, so all
four partials are host-known, distinct and non-zero: `dfdx(u)=A=1`, `dfdy(u)=B=2`,
`dfdx(v)=C=4`, `dfdy(v)=D=8`, and the alpha channel carries `D + S` where `S = in[7]*in[8]
= 3` is computed on the plain float ALU. **Oracle pixel = `(1, 2, 4, 11)`.** Observed at
freeze: exactly `(1.0, 2.0, 4.0, 11.0)` on all 16 pixels of the 4x4 RGBA32Float target.
*Liveness:* this is the EXP-0129 guard. A derivative that does not reach the rasterised
pixel changes a named float; an axis or source swap makes one **known** value appear in
another **known** channel; alpha reports three ways — `11` both paths ran, `8` the sentinel
ALU died, `3` the derivative died, `0` nothing ran. Four `tex_deriv` at `+0x0038 +0x0042
+0x004c +0x0056`.

## 4. Independent / controlled variables, and the sweep matrix

Independent variable: **one byte of one instruction instance**, one case at a time.
Controlled: everything else — same archive bytes, same input file, same runner process,
same texture contents, same grid.

| arm | instruction | instances spliced | bytes swept | values | cases |
|---|---|---|---|---|---|
| A1 | `tex_sample` | `+0x0164` (bundle 7) and `+0x0102` (bundle 0) | `1..13` full 256; byte `0` restricted (see below) | 3359 | 6718 |
| A2 | `tex_coord_setup` | two instances, chosen in run01 by the "which setup feeds which sample" probe | `1..9` full 256; byte `0` = 16 high-nibble values | 2320 | 4640 |
| B  | `tex_write` | `+0x0124` (write 1) and `+0x0134` (write 2) | `1..15` full 256 | 3840 | 7680 |
| C  | `tex_deriv` | `+0x0038` (dfdx u) and `+0x004c` (dfdx v) | `1..9` full 256 | 2304 | 4608 |

**Total pre-registered: 23,646 cases**, plus fault-confirmation re-runs and periodic
baseline re-validations.

**Byte-0 restriction (a deliberate, pre-registered safety deviation).** Byte 0 carries the
opcode nibble that the length rule reads; an arbitrary byte 0 desynchronises the whole
instruction stream and EXP-0128 got two real GPU hangs exactly this way. For `tex_sample`
byte 0 the sweep is therefore the **31-value set** `{0x?5 : all 16 high nibbles} ∪ {0x0? :
all 16 low nibbles}`, which still covers **both** four-bit fields (`chain`, `kind`)
densely. For `tex_coord_setup` byte 0 it is the 16 values `{0x?b}`, covering `dst_lo`
densely. `tex_write` and `tex_deriv` byte 0 carry **no** modelled field and are **not**
swept at all.

Every field of width ≤ 8 in the matrix therefore gets **all 2^w values**, satisfying
FIELD-SWEEP-PROTOCOL §3.3. `tex_write.coord_regs` (24 bits) and `tex_deriv.dstsrc`
(24 bits) are swept **byte-wise, all 256 values per constituent byte**; their verdicts
state that range honestly and do **not** claim the full 24-bit space.

## 5. Oracle

The primary oracle is **host-computed, GPU-independent**: the exact float vector each
carrier must produce, derived above from the MSL and the runner's known texture contents,
and confirmed against hardware before the freeze. Every case's `oracle` field is that
baseline vector; `match` is bit-exact equality.

For fields where a *model* predicts a specific non-baseline value (a coordinate register
redirected to another sample's pair must yield another member of `{1,102,...,708}`; an
`axis` flip must yield another member of `{1,2,4,8}`), the analysis records the model
prediction and whether the observation met it. Those model oracles are **also** host
computed; no GPU value is used to predict another GPU value.

## 6. Outcome classification (the `outcome` key)

- `ok` — output bit-identical to the baseline oracle (the value is inert here).
- `silent_zero` — the spliced instance's own observable collapsed to zero (`tex_sample`
  quad `(0,0,0,0)`; `tex_write` texel still at the reset value `(-1,-2,-3,-4)`;
  `tex_deriv` channel `0.0`) and nothing else moved.
- `wrong_value` — the spliced instance's observable changed to something else, or another
  instance's observable moved (cross-talk); the delta is recorded verbatim.
- `fault` — the command buffer failed, **reproducibly**, per §7 below.
- `hang` — no response inside the request timeout.
- `undecodable` — reserved; not expected here.

An **integrity-sentinel failure** (`out[32] != 12345`, `out[0] != 12345`, or alpha showing
the ALU path dead) marks the case `invalid` and it is **not attributed to the field**.

## 7. Safety and anti-contamination controls (FIELD-SWEEP-PROTOCOL §7, §8)

1. **Unique splice-archive path per request** — `work/frozen/spl/<arm>_<seq>.bin`, never
   reused, removed after the response (the ~8% phantom `CMDBUF_ERROR` mitigation).
2. **Poisoned readback** — `texpersist` fills every output buffer with `0xDEADBEEF` before
   the dispatch; an untouched word is unmistakable. The write target is independently
   reset to `(-1,-2,-3,-4)` per dispatch.
3. **Integrity sentinel through a path independent of the instruction under test** —
   `out[32]`/`out[0] = in[63]`, a plain device load→store that never reaches the texture
   unit; for the render arm, the alpha channel's `in[7]*in[8]` float-ALU term.
4. **No `fault` from one observation** — every `fault`/`hang` is re-run to a **majority of
   3**; a value is only recorded `fault` if it faults in the majority. Non-reproducing
   faults are recorded with `outcome` set from the majority observation and a note.
5. **OS fault classification recorded** — the `ERRDOM <domain> <code>` line from both
   runners is stored per case. `MTLCommandBufferError` code 4 (`InnocentVictim`) is
   **segregated** from the gated comparison as evidence about the machine.
6. **Periodic baseline re-validation** every 200 cases, 4 attempts with a settle delay.
   All four failing = cascade → the run **stops** and says where.
7. **Hang budget:** 2 genuine hangs in one (instruction, byte) area stops **that area**;
   6 genuine hangs total stops the **run**. Per-request timeout 10 s.
8. Append + `fflush` one JSON object per case to `raw/<run_id>/sweep.jsonl`; a
   `PROGRESS.md` entry per milestone. A kill costs at most one milestone.
9. **Never** `macvdmtool`; never the A18; never a file outside this experiment directory.

## 8. Pre-registered positive controls and falsifiers

These run **first**, in `run01`, and gate the main sweep. If a control fails, its arm is
reported dead rather than swept.

| id | case | pre-registered prediction |
|---|---|---|
| PC1 | carrier A, bundle 7 `tex_slot` (byte 8) `0x00 → 0x10` | `q7` **silently zeroes**, `q0..q6` unchanged (EXP-0114's 4-bit selector, all 14 unused values silently zero) |
| PC2 | carrier A, bundle 7 `variant` (byte 6) `0x09 → 0x17` | `q7` changes (a different sampler operation); `q0..q6` unchanged |
| PC3 | carrier C, deriv 0 `axis` (byte 6) `0x92 → 0x90` | red changes `1.0 → 2.0` (dfdx(u) → dfdy(u)); green/blue unchanged |
| PC4 | carrier C, deriv 0 `src_comp` (byte 5) `0x04 → 0x08` | red changes `1.0 → 4.0` (u → v) |
| PC5 | carrier B, write 1 `wop` (byte 12) `0x89 → 0x00` | texel `(3,2)` stops being written (stays `(-1,-2,-3,-4)`) **or** moves; texels `(1,0)` and `(5,4)` unchanged |
| NC1 | carrier B, write 1 `rsv15` (byte 15), all 256 values | **inert**: every texel identical to baseline for all 256 values |
| NC2 | carrier A, bundle 7, no splice, re-run 8x | identical output all 8 times (the runner is deterministic) |

**A control that does not behave as predicted is a first-class result** and is reported as
such — PC3/PC4 failing means the fragment-derivative arm is not live and `tex_deriv` stays
`untested`, exactly the outcome EXP-0129 reported rather than faking.

## 9. Known confounders

- **Sibling GPU agents.** Another agent's contained fault can surface as a `CMDBUF_ERROR`
  in our command buffer. Mitigated by §7.4/§7.5; the concurrency actually observed is
  reported in `RESULTS.md`.
- **`min_lod_clamp` crashes the AGXMetalG16G compiler service machine-wide** (EXP-0106).
  It appears in **no** carrier here and must not be added to one.
- **Sampler swizzle codes 6/7 hard-fault the command buffer** (EXP-0136). These are
  *descriptor* fields, not instruction bytes, and no carrier sets them.
- **Compiler register allocation** — the register numbering we infer is this carrier's
  allocation; verdicts state the carrier, and the two-instance design (bundle 0 vs bundle
  7, write 1 vs write 2, deriv 0 vs deriv 2) is the check that a finding is not an artefact
  of one instruction's position.
- **Texture unit latency / scoreboard.** `chain` decrements 14,12,…,0 across the eight
  bundles, so it is plausibly a scoreboard countdown rather than an operand; a splice may
  therefore corrupt an *unrelated* bundle. That cross-talk is an expected, recorded
  observation, not a failure.
- **Length desync.** A byte-0 splice may change the decoded instruction length; §4's
  restriction bounds it and §7.7 caps the damage.

## 10. Conditional Arm D — `imageblock_load` / `imageblock_store`

`imageblock<GB, imageblock_layout_explicit>` in a **fragment** function **no longer
compiles** on this host (macOS 26.6.2, GPUCompiler 32023.886) — recorded pre-freeze in
`raw/prefreeze/imageblock_carrier_compile_fail.txt`. The surviving route is the **tile**
pipeline (`imageblock<GB>`, `MTLTileRenderPipelineDescriptor`), which was confirmed
pre-freeze to compile and to emit an `imageblock_load` at `_agc.main+0x000e`.

Arm D is therefore **conditional**: it is attempted only after arms A/B/C have completed,
and only inside a fixed budget. If a *persistent tile runner* with a host-computable
oracle and a demonstrated positive control is not achieved inside that budget, the ten
`imageblock_*` fields are reported **`untested`** with the blocker named. They are **not**
labelled from the compile-only byte-diff evidence that already exists.

## 11. Frozen artefact hashes (sha256)

```
58bf697026cbe1fe0b88f71c98453e37fc49a856256054d7a6d181197979abf6  kernels/frag_deriv.metal
f1e38281026a019f09a6338c7f8f48aa727d6bea3e0807adc690f1049d41708c  kernels/tex_sample8.metal
7c20ab7ef323b51a1c8da1cfcc508e20e434547c7cfc4119164c13ad593efa8e  kernels/tex_write3.metal
60a9503e7b498daaa164c1f01c02b67fc387fc4eb3c56c119d09db3035d48737  harness/renderpersist.m
70dde540869dcff119787593ade741e99f260a1d0f02c1be319b30d8fc9b4b0c  harness/texpersist.m
c0542a0caf30f2fbe954e4074f9670a5dd7091c3e73a86afaba195b5006a1374  harness/texrunner.py
e1ff8f6d67bd397f88cbb1fa10aec9598ec2f7c1fee9770dc8be1817ac1a3257  harness/renderrunner.py
61144cc71306cb7c78dff9dd147eafb3080e58b02cbe4d8095ee8dd16c0661d8  work/frozen/cA_sample8.bin
fb841d5fe3ce88c1c14651493140560b6df11f8f24dc7afd46ea813fc6797527  work/frozen/cB_write3.bin
e048794d8b6671f277375695e4625f00dd8f61a2a7f24c986740001f610d0bc3  work/frozen/cC_deriv.bin
78909c339255682ee8074ee853602c6c894159c6323cbd5bb360f9fada891855  work/frozen/inA.bin
dc9e97b3b3b084a8162924e0fd7f242b36ba183decb0d3f11dd445f60bcc7880  work/frozen/inB.bin
a080857dbc059dfd15465f5769809438fc112090046f012f9e4ec01db6a1c3df  work/frozen/inC.bin
772efb9046452ade0f7640fed156b497c36a3e88f841382b2d0774f671887419  tools/agx-isa/db.json
```

`_agc.main` regions: `cA_sample8.bin` abs 10480 len 524 · `cB_write3.bin` abs 8608 len 356
· `cC_deriv.bin` (stage `fragment`) abs 16048 len 136.

## 12. Runs

- **`run01`** — gate: NC2 determinism, PC1–PC5, NC1, the coord-setup→sample mapping probe,
  and a 512-case rate probe. Gates the main sweep per §8.
- **`run02`** — the full §4 matrix.

Raw evidence: `raw/run01/`, `raw/run02/`. Verdicts: `analysis/field_verdicts.json` in the
FIELD-SWEEP-PROTOCOL §5 schema, using only the eight `docs/evidence-classification.md`
labels. Model corrections go under `"db_defects"`; **`db.json` is not edited.**

## 13. Clean-room provenance

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: our own MSL (kernels/*.metal) and the AGX bytes compiled from it;
                  our own input vectors (work/frozen/in{A,B,C}.bin)
Apple binary introspection: NONE
Reproduction: analysis/sweep.py (see README.md for exact commands)
Evidence: raw/prefreeze/, raw/run01/, raw/run02/
```
