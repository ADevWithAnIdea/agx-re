# RESULTS — EXP-0157 (G17P): the MISC family

**Headline: the acceleration-structure testbed gap is CLOSED — the whole ray-query cluster is
sweepable for the first time — and `op04_len8`'s declared length is wrong on hardware.**

| | |
|---|---|
| Target | **Apple A18 Pro / G17P** (`Mac17,5`, `AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores, macOS 26.6 build 25G5043d). Every record is `target: G17P`. |
| Gated captures | **RSH gate:** `raw/g17p_run01` (complete) + `raw/g17p_run02` (RETAINED PARTIAL, stopped at 11 830 records) + `raw/g17p_run03` (targeted second capture of the four carriers run02 never reached) — all replaying the SAME resolved case list. **B2 gate:** `raw/g17p_raymove01` + `raw/g17p_raymove02` |
| Fault confirmation | `raw/g17p_reval03` — every `fault`/`hang` of all three gated captures re-run 5× **under `~/agxre/gpulease.sh`** (FIELD-SWEEP-PROTOCOL §7A). The first attempt (`g17p_reval01`) never executed because the shared lease script was mid-rewrite by another agent; see §10.8. **Whether the retry is on disk is stated in §11's capture table, and §9.1 explains why its absence cannot invalidate an ok-set.** |
| Post-freeze controls | `raw/g17p_reach01` (reachability) · `raw/g17p_bbox01` (custom-intersection carriers) · `raw/g17p_lenmap01`, `g17p_qlen01`, `g17p_qlen02` (hardware length probe) · `g17p_fence01/02` (fence litmus) |
| Retained, not reused | `raw/smoke01..04`, `raw/lm_smoke`, `raw/lm_smoke2` |
| Concurrency | **unlocked and concurrent** with the rest of the wave throughout; quantified in §9 |

**Clean-room:** `OWN-SHADER + HW-PROBE`. Every byte inspected or spliced is the compiled form of
MSL we wrote, or bytes emitted by `tools/agx-isa`'s assembler from our own field values. The
acceleration structures are built from triangle vertices and bounding boxes **we authored**. No
Apple binary was introspected. `db.json`, `validation.json`, `docs/**`, `PROVENANCE.md` and
`tools/agxtest/agxrun_persist.m` were **not modified**.

---

## 1. The testbed gap is closed (hypothesis H0 — CONFIRMED)

EXP-0146 could not sweep a single field of `sr_read_wide`, `rtq_*` or `ray_move*` for one reason:

> "`agxrun_persist` binds `MTLBuffer`s only and cannot bind an `MTLAccelerationStructure`:
> `q.next()` never enters the loop, so the getters never reach the output." (EXP-0146 §3.7)

`harness/agxrun_persist_as.m` adds a `setAccelerationStructure:` path — a build-and-bind of a
primitive (or instance, or bounding-box) acceleration structure from **our own** geometry. The
shared `tools/agxtest/agxrun_persist.m` is deliberately **not** edited: four sibling G17P
experiments rebuild it from `tools/` concurrently and a mid-wave edit would break their builds.
The addition is fenced by `EXP-0157 ADDITION` comments so it can be upstreamed verbatim.

**Directly observed.** With the structure bound, our own `intersection_query` kernel returns every
host-computed oracle exactly:

| carrier (own MSL) | quantity | host oracle | read back |
|---|---|---|---|
| `k_rq_prim` | candidates / Σ prim / Σ geom / Σ dist / committed prim, geom, dist, type | 4, 3, 1, 10, 2, 0, 1, 1 | **all 8 exact** |
| `k_cand_prim` | Σ candidate primitive ids | 3 | 3.0 |
| `k_cand_geom` | Σ candidate geometry ids | 1 | 1.0 |
| `k_cand_dist` | Σ candidate distances | 10 | 10.0 |
| `k_cand_count` | number of candidates | 4 | 4.0 |
| `k_comm_prim` | committed (closest) primitive id | 2 | 2.0 |
| `k_comm_dist` | committed distance | 1 | 1.0 |
| `k_comm_type` | committed type == triangle | 1 | 1.0 |
| `k_bb_count/prim/commit/geom` | bounding-box path | 3, 6, 1, 6 | all exact |

Two implementation facts a re-user needs:

1. **`opaque = NO` on the geometry descriptor is load-bearing.** An opaque triangle hit is
   committed by the hardware without ever surfacing as a candidate, so with `opaque = YES`
   `q.next()` returns false immediately and every CANDIDATE getter stays dead — the exact failure
   mode being fixed. Non-opaque geometry forces every hit through the candidate path.
2. **The acceleration-structure BUILD is itself a frequent innocent victim.** On a busy device the
   build command buffer is repeatedly discarded
   (`kIOGPUCommandBufferCallbackErrorInnocentVictim`); the first attempt in this experiment failed
   eight times in a row. The runner now retries the build up to 30× with backoff, and `run.py`
   retries the whole process start four times on top. Without that, a contamination storm voids
   the run rather than delaying it.

**Consequence.** The cluster is now sweepable, and this experiment sweeps it. What it found is in
§2 and §3 — including a negative that only became visible *because* the carrier finally runs.

## 2. Anchors: which of them are actually executed

The ray-query carriers are 8–25 kB of `_agc.main` and do not tokenize end-to-end, so anchors come
from a resync walk (`analysis/resync.py`) and are then subjected to **two liveness controls**
(`byte0 ^= 1`; erase-to-zero) before any field is swept. Run01, over 12 candidate anchors per
(carrier, instruction):

| instruction | LIVE anchors | inert-or-unreached |
|---|---:|---:|
| `n2_op6` | 15 | 0 |
| `ray_move_copy6` | 10 | 2 |
| `ray_move_zero6` | 4 | 3 |
| `sfu_marker` | 4 | 0 |
| `sr_read_wide` | 4 | 32 |
| `rtq_state_move` | 3 | 13 |
| `h_coord_hi` | 2 | 0 |
| `op04_len8` | 2 | 3 |
| `h_coord_hi_ext` | 1 | 0 |
| `n3_mov` | 1 | 0 |
| `scoreboard_fence` | 1 | 0 |
| **`rtq_dualsrc`** | **0** | **11** |
| **`rtq_pred`** | **0** | **8** |
| | **47** | **72** |

### 2.1 `rtq_pred` and `rtq_dualsrc` are UNREACHED, not inert — proved

`inert_or_unreached` is ambiguous by construction, so a reachability control was run
(`harness/reachprobe.py`, `raw/g17p_reach01`): erase a **window** of 4, 16, 64 and 256 contiguous
bytes at the anchor and see whether the oracle survives.

| offset | 4 B | 16 B | 64 B | 256 B |
|---|---|---|---|---|
| `sr_read_wide` @328 (**live control**) | breaks | breaks | breaks | breaks |
| `rtq_dualsrc` @3788 / @4276 / @4402 | ok | ok | ok | **ok** |
| `rtq_pred` @1994 / @2092 / @3486 | ok | ok | ok | **ok** |

A 256-byte hole through those regions leaves the ray-query result **exactly correct**. They are
not executed. Suspecting the missing path was the custom-intersection one, we authored a
bounding-box acceleration structure and four bbox carriers (`kernels/k_rq_bbox.metal`, all four
oracles verified) — and `rtq_pred` is inert at **10 of 10** anchors there and `rtq_dualsrc` at
**12 of 12** (`raw/g17p_bbox01`).

**Verdict: both descriptors remain `untested` on G17P, with a named cause.** They are not
reachable from any own-MSL ray-query program we can currently build, under either triangle or
bounding-box geometry. This is a carrier problem, not a hardware or DB one — and it is *not* the
same problem EXP-0146 had, which is now fixed.

## 3. Per-field results at LIVE anchors

Every number below is a dense sweep (all 2^w values for `w ≤ 8`) at an anchor that passed the
liveness controls, in a carrier whose unmutated oracle is non-zero.

### 3.1 `sr_read_wide` — two of six fields are load-bearing, four are inert here

Anchor `24 a1 06 00 00 00 00 00` in `k_cand_dist`, independently in `14 a1 46 …` in `k_cand_prim`:

| field | width | outcome | exact rule |
|---|---:|---|---|
| `dst` | 4 | 15/15 **silent zero** | only the compiler's own value works |
| `sel` | 7 | 15 ok, 112 silent zero | **`(v & 0x87) == 0x01`** (identical in both carriers) |
| `width` | 8 | 7 ok, 216 silent zero, **32 fault** | `(v & 0xce) == 0x06` (cdist) / `== 0x46` (cprim) → the shared constraint is `(v & 0x8e) == 0x06`, bit 6 being a per-instance operand bit |
| `operand` | 8 | 255/255 ok | **HW-tested inert in these carriers** |
| `phase` | 8 | 255/255 ok | **HW-tested inert in these carriers** |
| `marshal` | 16 | 82/82 ok, and 255/255 on each of its two bytes | **HW-tested inert in these carriers** |

**H2 is REFUTED as stated.** No swept value produced *another property's* value — every failure
is a silent zero. `sel` does not select the property in a way these carriers can observe: 16
different `sel` values all return the correct distance. That is consistent with the independent
differential-compilation finding below.

**Differential compilation (independent second method).** Three `intersection_query<triangle_data>`
kernels that differ only in the getter they read (`barycentric.x`, `barycentric.y`,
`triangle_distance`) compile to programs that are **byte-identical except at 14 offsets**, each a
single byte taking `0xc4` / `0xc6` / `0xc8`. That byte is at `+10` inside a 14-byte `rt_ray_mem`
token — **not** inside `sr_read_wide`. So on G17P the ray-query *property selector* lives in
`rt_ray_mem`, which is why sweeping `sr_read_wide.sel` never yields another property.

### 3.2 The `0x?b` ray-marshalling moves

| instruction | carrier | `dst` | `src` | `form` (byte+2) | byte+3 |
|---|---|---|---|---|---|
| `ray_move_copy6` | `rq_cdist` | 15/15 ok | 255/255 ok | 191 ok, **64 fault** | 191 ok, **64 fault** |
| `ray_move_zero6` | `rq_cdist` | 15/15 ok | 255/255 ok | 191 ok, **64 fault** | 255/255 ok |
| `rtq_state_move` | `rq_cdist` | 13 ok, 1 silent zero, 1 wrong | 39 ok, 212 wrong, 4 silent zero | 175 ok, 64 silent zero, 16 wrong | 207 ok, 48 wrong |
| `rtq_state_move` | `rq_mtype` | 14 ok, 1 silent zero | 251 ok, 4 silent zero | 191 ok, 32 fault, 32 silent zero | 255/255 ok |
| `rtq_state_move` | `bb_commit` | 14 ok, 1 wrong | 251 ok, 4 wrong | 255/255 ok | 255/255 ok |

`ray_move` produced **no resync token at all** in `rq_cdist`, so a post-freeze arm (`B2`) scanned
the 25 kB `k_rq_prim` carrier instead, which contains 46 of them. It found four live anchors, and
the sweep at the first (`2b 26 81 08` @72) is the cleanest in the whole cluster — **gated across
two independent captures of its own** (`raw/g17p_raymove01` + `raw/g17p_raymove02`, 3 058 of 3 059
common cases agreeing, one disagreement):

| `ray_move` field | outcome |
|---|---|
| `dst` | **15/15 ok** — every destination nibble reproduces the oracle |
| `src` | **255/255 ok** |
| `b3` | **255/255 ok** |
| `form` (byte+2) | 223 ok, **32 fault** |

The same arm re-measured `sr_read_wide.sel` in a **third** carrier and got
`(v & 0x87) == 0x01` again — three independent carriers, one rule.

`ray_move_zinit` had no live anchor in any of the four carriers scanned (`rq_cdist`, `rq_ccount`,
`bb_count`, `rq_all`), so it stays `untested`.

**Interpretation.** `rtq_state_move` is the only member of the cluster whose `src` field is
demonstrably a per-instance operand: in `rq_cdist` only 39 of 256 source values reproduce the
oracle and 212 return a *different* value — the signature of a real register read. In `rq_mtype`
and `bb_commit` the same field is almost entirely inert, which bounds the claim to the carrier.
`ray_move_copy6`/`ray_move_zero6` are inert in `dst` and `src` at every live anchor: their
destinations are not observable at register granularity on this output path, so an emitter gains
no licence from that.

### 3.3 `n2_op6` — four independent carriers agree on the shape, not on the constants

`n2_op6` was swept densely at a live anchor in **four** independent carriers.

| field | `sfusin` | `sfucos` | `sfumix` | `u64eq` |
|---|---|---|---|---|
| `dst` | 15/15 silent zero | 14 silent zero, 1 not-written | 13 wrong, 1 silent zero, 1 not-written | 15/15 silent zero |
| `src_desc` | 3 ok, `(v & 0x7e) == 0x04` | 3 ok, `== 0x04` | 3 ok, `== 0x08` | 3 ok, `== 0x00` |
| `opsel` | 3 ok, `(v & 0xd7) == 0x03` | 3 ok, `(v & 0xcf) == 0x03`, **128 fault** | 3 ok, same, **128 fault** | 7 ok, `(v & 0xd5) == 0x05` |
| `opA` | 1 ok | 17 ok | 17 ok | 117 ok, 138 silent zero |
| `opB` | 5 ok, 113 fault | 1 ok, 17 fault | 0 ok, 64 fault | 15 ok, `(v & 0xa6) == 0x26` |
| `imm_sel` | 3 ok, `(v & 0x7e) == 0x06` | 3 ok, `== 0x06` | 3 ok, `== 0x10` | 3 ok |

The **shape** reproduces across carriers — `dst` is not observable, `src_desc`/`imm_sel` accept a
6-bit-masked family, `opsel` is strongly constrained and faults on half its range — but the
accepted **constants** differ per carrier, because each carrier's baseline instance differs. An
emitter therefore gets a per-instance mask, not a global one. That is the honest reading and it is
what `analysis/field_verdicts.json` records (keyed `n2_op6.<field>@<carrier>`).

### 3.3b The same shape analysis on `n2_op6` — the SFU quadrant machinery again

`analysis/shapes.py` generalises the classification used in §3.4: instead of recording
"wrong_value", it classifies each swept value by the *shape* of the eight-row output. Applied to
`n2_op6` in the `fast::sin` carrier:

| field | shape | n | rule | reading |
|---|---|---:|---|---|
| `opsel` | `........` | 3 | `(v & 0xd7) == 0x03` | correct |
| `opsel` | `......-.` | 4 | `(v & 0xd7) == 0x13` | one row (x = −4.25) sign-flipped |
| `opsel` | `....-...` | 122 | — | the x = 3.0 row sign-flipped |
| `opsel` | `.xx.-...` | 62 | `(v & 0x02) == 0x00` | two rows wrong **and** the quadrant flip |
| `opsel` | `.0000000` | 60 | `(v & 0x02) == 0x02` | the SFU produces nothing |
| `imm_sel` | `........` | 3 | `(v & 0x7e) == 0x06` | correct |
| `imm_sel` | `....0...` | 240 | — | the range-reduced row is **zeroed**, others correct |
| `imm_sel` | `.0000000` | 4 | `(v & 0x7e) == 0x00` | all rows zero |

So `n2_op6` in this lowering is part of the same argument-reduction machinery as `sfu_marker`:
`opsel` bit 1 gates whether the SFU emits a result at all, and `imm_sel` selects which reduced
row survives. That matches `db.json`'s own reading of the family ("in the transcendental family
the tail is an SFU coefficient/select") and gives it hardware backing.

**Clean-room note (rule 5).** What is documented here is a per-field *accept/reject envelope* and
the observable effect of a field VALUE on the output — hardware behaviour. The SFU's
range-reduction coefficient sequence itself is deliberately not reconstructed, exactly as
EXP-0146 constrained itself.

### 3.4 `sfu_marker` — db.json is wrong, and EXP-0146's M4 rule reproduces EXACTLY on G17P

`db.json` describes `06 02` as a *"byte-INVARIANT 2-byte token … fixed control token with no
operand bits"*, and gives it **zero fields**. In three independent carriers:

| byte | accepted set | rule |
|---|---|---|
| byte+0 | 2 of 256 | **`(v & 0xf7) == 0x06`** |
| byte+1 | 32 of 256 | **`(v & 0x13) == 0x02`** |

Both rules are **identical in `sfusin`, `sfucos` and `sfumix`**, and both are **byte-for-byte the
rules EXP-0146 measured on M4/G16G**. This is a clean G16G→G17P revalidation of an unmerged M4
result, and a confirmed `db.json` defect: the descriptor needs two 8-bit fields.

**And the failures are not noise — they are a quadrant map.** The `sfusin` carrier computes
`fast::sin` over eight authored inputs, four of which need range reduction. Classifying every
swept value by the *shape* of its eight-row output (`.` = matches `sin`, `-` = sign-flipped,
`0` = zero) partitions both bytes exactly:

| byte | output shape (rows 0..7) | n | value rule | reading |
|---|---|---:|---|---|
| byte+0 | `........` | 1 | `v == 0x0e` | correct (plus the baseline `0x06`) |
| byte+0 | `....-...` | 44 | `(v & 0x60) == 0x00` | the quadrant correction for x = 3.0 (in π/2..π) is **dropped** |
| byte+0 | `.---.---` | 16 | `(v & 0x64) == 0x00` | a *different* quadrant map — six rows inverted |
| byte+0 | `..--..-.` | 2 | `v ∈ {0x16, 0x1e}` | a third map |
| byte+0 | `.0000000` | 192 | bit 5 set | the SFU produces **nothing** |
| byte+1 | `........` | 31 | `(v & 0x13) == 0x02` | correct |
| byte+1 | `....-...` | 80 | `(v & 0x10) == 0x00` | same single-quadrant drop |
| byte+1 | `...----.` | 16 | `(v & 0x17) == 0x00` | four rows inverted |
| byte+1 | `.0000000` | 128 | bit 4 set | the SFU produces nothing |

The `....-...` row is **exactly EXP-0146's M4 observation** — *"setting byte+0 to `0x00` flips the
sign of `fast::sin` on exactly the rows whose argument needs range reduction"* — reproduced on
G17P, and now with three further behaviours mapped either side of it. So `06 02` is not a marker:
**both of its bytes carry live quadrant/sign control for the SFU's argument reduction**, and a
wrong value either inverts a quadrant or silences the unit entirely.

### 3.5 `n3_mov` — G17P reproduces M4

In `u64eq`: `dst` 15/15 ok, `srcA_reg` 127/127 ok, `srcA_uni` 2/2 ok, `companion` 223 ok / 32
silent zero, `subform` 89 ok / 86 silent zero / 33 fault / 31 not-written. EXP-0146 measured
224 ok for `companion` and 90 ok / 118 silent / 32 fault for `subform` on M4 in the same carrier.
**The load-bearing byte is `subform`, and the M4 result reproduces.** `srcA_reg`'s inertness — the
contradiction EXP-0146 flagged and could not resolve — reproduces too, so it is a property of the
instruction in this lowering, not an M4 artefact.

### 3.6 `h_coord_hi` / `h_coord_hi_ext` — carriers exist on G17P, and the operands are real

Neither appears in any carrier reused from EXP-0145/0146 when recompiled on G17P; both had to be
provoked (`kernels/k_provoke.metal`: `k_h4_fma`, a `half4` fma with a reversed second operand, and
`k_h3_mix`, a `half3` `mix`+`fma`). `h_coord_hi` then had a live anchor in **both**.

**`h_coord_hi`** (anchors `08 07 2e 84 80 08` in `h4fma` and `18 06 2e 82 00 81` in `h3mix`):

| field | carrier | outcomes over the dense sweep | exact rule |
|---|---|---|---|
| `ctrl` | `h3mix` | 128 not written, 90 wrong value, 36 silent zero, 1 ok | `(v & 0xff) == 0x04` |
| `ctrl` | `h4fma` | 97 fault, 84 wrong value, 40 silent zero, 31 not written, 3 ok | `(v & 0x7b) == 0x00` |
| `dst` | `h3mix` | 14 silent zero, 1 not written | — |
| `dst` | `h4fma` | 14 silent zero, 1 not written | — |
| `mods` | `h3mix` | 254 wrong value, 1 ok | `(v & 0xff) == 0x01` |
| `mods` | `h4fma` | 242 wrong value, 12 silent zero, 1 ok | `(v & 0xff) == 0x88` |
| `opsel` | `h3mix` | 160 not written, 80 silent zero, 12 wrong value, 3 ok | `(v & 0xd7) == 0x06` |
| `opsel` | `h4fma` | 88 silent zero, 80 fault, 80 not written, 4 wrong value, 3 ok | `(v & 0xd7) == 0x06` |
| `srcA` | `h3mix` | 250 wrong value, 4 silent zero, 1 ok | `(v & 0xff) == 0x86` |
| `srcA` | `h4fma` | 240 wrong value, 14 silent zero, 1 ok | `(v & 0xff) == 0x87` |
| `srcB` | `h3mix` | 254 wrong value, 1 ok | `(v & 0xff) == 0x02` |
| `srcB` | `h4fma` | 254 wrong value, 1 ok | `(v & 0xff) == 0x04` |

**`h_coord_hi_ext`** (anchor `58 80 26 90 81 03 00 22` in `h3mix`):

| field | carrier | outcomes over the dense sweep | exact rule |
|---|---|---|---|
| `dst` | `h3mix` | 14 silent zero, 1 not written | — |
| `ext` | `h3mix` | 128 fault, 64 not written, 60 wrong value, 3 ok | `(v & 0x7b) == 0x01` |
| `opsel` | `h3mix` | 236 silent zero, 18 wrong value, 1 ok | `(v & 0xff) == 0x06` |
| `srcA` | `h3mix` | 254 wrong value, 1 ok | `(v & 0xff) == 0x00` |
| `srcB` | `h3mix` | 254 wrong value, 1 silent zero | — |
| `srcC` | `h3mix` | 254 wrong value, 1 ok | `(v & 0xff) == 0x83` |
| `tail` | `h3mix` | 66 silent zero, 15 wrong value, 2 ok | — |

Three things are worth naming. **`opsel` gives the same rule `(v & 0xd7) == 0x06` in both
`h_coord_hi` carriers** — the one cross-carrier constant in this instruction, and the pre-registered
falsifier H-F1 (`opsel = 0x00` must mismatch) passed in both. **`srcA`, `srcB`, `mods` and `srcC`
each accept exactly one value while 240-254 of the others return a *different, non-zero* result** —
the signature of a real source-operand field, not an inert byte; those fields are `hardware-run`
with an exact rule, but the rule pins them, so an emitter cannot yet choose those operands (§11).
And `h_coord_hi_ext`'s `tail`, which `db.json` carries as one opaque 16-bit `raw` field, splits
into two bytes with different behaviour: `tail.byte+6` accepts `(v & 0xec) == 0x00` and
`tail.byte+7` accepts `(v & 0x1b) == 0x02`.

### 3.7 `op04_len8` fields

At its live anchors (`04 00 00 00 60 00 0f 05` in `rq_mprim` and `rq_mdist`, and one in
`bb_commit`): `dst` 15/15 ok, `mode` 255/255 ok, `body.byte+2` and `body.byte+3` 255/255 ok, while
the 48-bit `body` sampled at 147 points gives 26 ok / 118 not-written / 3 fault. So the leading
bytes are inert and the tail is load-bearing — **which is exactly what §4 predicts**, because
`db.json` splices only 8 of the instruction's real 12 bytes.

## 4. `op04_len8`'s length is wrong — measured on hardware, not inferred

EXP-0148 left `op04_len8` OPEN after scoring six *static* length rules on corpus tokenization and
finding all six worse than the status quo. Round-trip is blind to over-consumption by
construction, so that method could not settle it. **This experiment asks the silicon instead.**

`harness/run_lm.py` synthesises a program whose registers witness where instruction decoding
resumed: a sentinel store, five (or eight) witness registers zeroed, the probe bytes, then a run
of distinct 2-byte `mov_imm` markers, then a store of every witness. The number of *leading*
markers that did not run is half the number of bytes the probe consumed beyond its own length.

**Both pre-registered controls pass** (`raw/g17p_lenmap01`, arm L):

* `CTRL_INERT` — eight bytes of known 2-byte `mov_imm`: every witness set, `r5 = 0`. ✔
* `CTRL_LEN6` — a known **six**-byte instruction followed by `mov_imm(r5,5)`: `r5 = 5`. ✔
  (Without this, a "length 6" reading would be unfalsifiable.)

### 4.1 The findings

1. **All six `op04_len8` patterns taken from our own G17P compiles consume TWELVE bytes**, not the
   eight `db.json` declares. Witness pattern `r1 = r2 = 0, r3 = 3, r4 = 4` in every case.
2. **The length is a joint function of `byte+1` bit 7 and `byte+2`** (and, in the bit-7-clear
   family, `byte+3` bit 7) — not of `byte+1` alone:
   * sweeping `byte+1` over all 256 values on three independent candidates: **length 8 iff bit 7
     is SET, 12 iff CLEAR** — a clean 128/128 split, reproduced three times
     (`analysis/length_rule.json`);
   * with `byte+2 = byte+3 = 0x00` the same bit gives **4** (set) / **8** (clear);
   * with `byte+1` bit 7 SET the family is `{4, 8, 10}` selected by `byte+2 & 3` (`0 → 4`,
     `1,2 → 8`, `3 → 10`);
   * with `byte+1` bit 7 CLEAR the family is much wider — measured lengths of 4, 6, 8, 10, 12, 14,
     16 and 18 occur, selected mainly by `byte+2 & 7`;
   * `byte+3`, `byte+5` and `byte+7` are length-irrelevant for the candidates tested (all 256
     values → the same length).
   The complete measured map is committed as `analysis/length_map_q.json` (2 304 measurements)
   and `analysis/length_rule.json`.
3. **`sr_read_wide`'s own match requires `byte+1` bit 7 = 1** — and the measurement says that is
   exactly the 8-byte case. The 8-byte model is right for `sr_read_wide` and wrong for the
   bit-7-clear half that `op04_len8` also matches.

### 4.2 `mesh_out_src` — its 2-byte length is confirmed for half the space and refuted for the other

Arm M splices `04 XX` into a compute program ahead of four 2-byte markers and sweeps `XX` over all
256 values:

* **all 128 values with bit 7 CLEAR consume exactly 2 bytes** (every marker runs) — the declared
  length, confirmed on hardware;
* **all 128 values with bit 7 SET consume 4** (the first marker is swallowed);
* **no value changed the stored result.** `sel` has no observable effect in a compute program, so
  it stays `untested`; H5 is confirmed for the semantic half and refuted for the length half.

`mesh_out_src`'s match is `byte0 == 0x04` with no constraint on `byte+1`, so as written it claims
2 bytes for the 4-byte form as well, and it collides with `op04_len8`, whose match is only the
byte0 low nibble.

**Internal consistency check (arm M vs arm Q2).** Arm M's probe is `04 XX` followed by
`mov_imm(r1,1)` = `1c 01`, so the byte stream the decoder actually sees is
`04 XX 1c 01 …` — i.e. arm M is one column of arm Q2's map, at `byte+2 = 0x1c`. Q2, which
synthesised `04 b1 1c b3` independently and measured it with eight witnesses instead of four,
reports length **4** for `b1` bit 7 set. Arm M reports the first marker swallowed for exactly the
128 values with bit 7 set — the same 4 bytes. Two probes of different shape agree.

## 5. The fences — the litmus now WORKS, and promotion is still declined

EXP-0141 and EXP-0147 both declined to promote `scoreboard_fence`/`compute_fence_scoped` because
their carriers could not detect a spliced-out barrier at all. **That is no longer true here.**

In `u64eq` the `scoreboard_fence` anchor `07 02 20 80` passes both liveness controls, and a
dedicated litmus (`raw/g17p_fence01/02`) replaces its four bytes with **two `mov_imm(r13,0)` —
a filler whose inertness was verified on hardware by arm L's `CTRL_INERT`, not merely assumed**:

| filler | result |
|---|---|
| `mov_imm(r13,0) × 2` (HW-verified no-op) | **silent zero** — the carrier's oracle breaks |
| `00 00 00 00` | **wrong value** — also breaks |

So this carrier genuinely detects the fence's *removal*. The sweep at that anchor gives `kind`
71/255 ok, `scope` 63/127 ok, `mask` 119/255 ok — and the **shape** of the failures is
data-aligned, which is the first ordering-specific signal anyone has obtained for these fields.
`u64eq` computes `a[i] == b[i] ? 1 : 0` over eight authored rows, four of which compare EQUAL, so
the oracle is `1,0,1,0,0,1,1,0`:

| field | shape | n | rule | reading |
|---|---|---:|---|---|
| `kind` | `........` | 71 | `(v & 0x10) == 0x00` | correct |
| `kind` | `0.0..00.` | 64 | `(v & 0x11) == 0x10` | **exactly the rows whose result should be 1 read back 0** |
| `kind` | `.x.xx..x` | 48 | `(v & 0x11) == 0x01` | **exactly the rows whose result should be 0 read back garbage** |
| `kind` | `0x0xx00x` | 64 | `(v & 0x11) == 0x11` | both of the above at once |
| `scope` | `........` / `.x.xx..x` | 63 / 64 | — | same false-row corruption |
| `mask` | `........` / `.x.xx..x` | 119 / 136 | — | same false-row corruption |

A wrong *instruction* would corrupt rows indiscriminately. A corruption that partitions the rows
**by their own comparison result** is what a missing register/scoreboard dependency looks like:
the consumer reads the compare's destination before the producer has written it, so what it sees
depends on the data. That is an ordering signature, and it is considerably more than EXP-0141 or
EXP-0147 had.

**We still do not promote.** Detecting *removal* is not the same as detecting *ordering
specifically*: an accepted `kind` value may preserve the required ordering, or may simply be one
the carrier cannot distinguish. Nothing here shows two different fence values producing two
different, predictable orderings, which is what the dispatch requires. The three fields stay `untested`, and what a successor needs is now much more precisely named:
a carrier in which **two ACCEPTED fence values give two different, host-predictable results**.
The shape table above is the strongest available hint at where to look — `kind` bit 4 and bit 0
partition the failures along the data, so a litmus that makes those two bits produce two
*different correct* answers (rather than one correct and one corrupt) would close it. `compute_fence_scoped` appears in our carriers only after a
resync gap and was not in the frozen arm table; it is not swept here.

## 6. What has NO carrier on G17P — two first-class negatives

`n2_op8` and `coord_madf` are emitted by **nothing we can compile on this target**.

The census over **all 59 own-MSL programs this experiment compiled on G17P** is committed as
`raw/g17p_census01/provocation_census.json` (per-program byte count, hex digest, strict-tokenizer
leftover, resync token count, and the count of every dispatched descriptor). Its
`never_observed_on_G17P` list is exactly `["coord_madf", "mesh_out_src", "n2_op8"]`.

* **`n2_op8`** — **20 SFU-family programs** across two independent provocation rounds:
  `fast`/`precise` `sin`, `cos`, `tan`, `sinpi`/`cospi`/`tanpi`, `exp`/`log`/`pow`,
  `atan2`/`asin`/`acos`, `sinh`/`cosh`/`tanh`, `rsqrt`/`sqrt`/`divide`, `modf`/`fract`/`fmod`,
  `rint`/`floor`/`ceil`/`trunc`/`round`, half-precision transcendentals and large-argument forms,
  **with and without fast-math** — plus 14 texture programs, 5 half programs and every ray-query
  carrier. **Zero occurrences in any of the 59.** EXP-0146 found it in `fast::sin` on
  **M4/G16G**; on G17P that lowering does not produce it. All 4 fields stay `untested` on G17P.
* **`coord_madf`** — **14 texture programs** (cube, cube-array, 3D, 2D-array, `sample_compare`,
  `gather`, explicit `level`, `gradientcube`, `read_write` 3D), with and without fast-math. Zero
  occurrences. All 5 fields stay `untested` on G17P.
* **`mesh_out_src`** — likewise never emitted, which is expected: it is a MESH-stage op and our
  testbed has no mesh pipeline. Its *length* was nevertheless measured (§4.2) by synthesising the
  encoding ourselves, which needs no carrier.

This is a statement about what **G17P's compiler emits**, not about the silicon; the M4 evidence
stands on its own target. It is also exactly the kind of G16G↔G17P divergence the target rule
exists to surface.

## 7. Pre-registered falsifiers

| id | prediction | outcome |
|---|---|---|
| **L-F1** | a known 6-byte instruction + `mov_imm(r5,5)` must set r5, or the length probe is blind | **passed** — r5 = 5 |
| **L-CTRL** | 8 bytes of known 2-byte `mov_imm` must leave every witness set and r5 = 0 | **passed** |
| **H-F1** | `h_coord_hi.opsel = 0x00` must mismatch | **passed** (silent zero) |
| **S-F1** | `sfu_marker.byte+0 = 0x00` must mismatch (EXP-0146's M4 sign flip) | **passed** (wrong value); the accepted set is exactly EXP-0146's |
| **M-F1** | `mesh_out_src` spliced over a live instruction must mismatch | **passed** for every value that changes the consumed length |
| **R-F1** | `sr_read_wide.sel` set to another getter's value should return that other property | **FAILED — refuted.** Every non-accepted value silently zeroes. §3.1 explains why: the property selector is in `rt_ray_mem`, not here. |
| **R-liveness** | erasing a live instruction must break the oracle | **passed** — `sr_read_wide` @328 breaks at a 4-byte erase |
| **P-reach** | erasing 256 bytes at a *reached* offset must break the oracle | **passed** at the live control, **survived** at every `rtq_pred`/`rtq_dualsrc` offset |

One falsifier failed and it changed a conclusion rather than being explained away. That is the
point of having them.

## 8. Limitations — what a reader must not over-read

1. **Every verdict is carrier-scoped.** An "ok" value can mean the field is inert *or* that this
   carrier cannot observe the difference. `n2_op6`'s four carriers agree on shape and disagree on
   constants; that disagreement is the evidence for this caveat, not an inconsistency.
2. **Anchors come from a resync walk.** They are trusted only after passing a liveness control,
   and every record carries its `after_gap` flag. An anchor that failed both controls promotes
   nothing.
3. **The length map is a MAP, not a fitted formula.** `analysis/length_map_q.json` is what was
   measured. The regularities in §4.1 are described but deliberately not smoothed into a closed
   form, and 4–12 % of the swept values produced witness patterns that do not classify (recorded
   as `null`).
4. **The length measurement is compute-stage.** Instruction length is a property of the decoder,
   not the stage, but `mesh_out_src` was measured in a compute program because no mesh carrier
   exists in our testbed.
5. **`rtq_pred` / `rtq_dualsrc` are bounded, not characterized.** Everything §2.1 says is about
   *reachability from our carriers*.
6. **`sr_read_wide`'s rules come from three carriers** — `k_cand_dist`, `k_cand_prim` and
   `k_rq_prim` (which runs both a candidate pass and a committed pass) — and all three give
   `sel` = `(v & 0x87) == 0x01`. But every `sr_read_wide` anchor in the three purely-COMMITTED
   carriers (`k_comm_prim`, `k_comm_dist`, `k_comm_type`) failed both liveness controls, so the
   `phase` field — which `db.json` reads as the CANDIDATE-vs-COMMITTED selector — was never swept
   at an anchor where a committed read is the observed quantity. Its inertness is bounded
   accordingly.
7. **Nine oversized `00_cases.json` files were replaced by manifests** (CODEX §6). They are
   DERIVED INPUTS — `harness/cases.py` regenerates them exactly, and every case's spliced bytes
   are also in that run's own `sweep.jsonl` — so what was traded away is 108 MB of redundancy,
   not evidence. Each manifest carries the file's size, sha256, generation command, retention
   location on the target, its resolved anchors, and a first-record excerpt. **No `sweep.jsonl`
   was touched.**
8. **run02 is a RETAINED PARTIAL** (11 830 of ~21 000 records) and is not reused or topped up.
   It completed all of arm R and the `sfusin` groups; the targeted second capture of the four
   carriers it never reached is `raw/g17p_run03`, under a new run id. Where a field is gated by
   only one capture, it is reported at the weaker label, not rounded up.
9. **No M4 result is relabelled G17P.** Where an M4 rule reproduced (`sfu_marker`, `n3_mov`) it is
   stated as a reproduction with both targets named.

## 9. Concurrency, contamination, and how much of it there was

**This experiment ran unlocked and concurrent with the rest of the wave throughout**, as
`NEO-TARGET-BRIEF.md` prescribes; the GPU lease was taken only for the fault-confirmation pass.
`raw/<run>/00_env.json` records the other GPU runner processes seen at each run's start (2 at
run01's start, more later), and `02_neighbours_end.json` at its end.

| | run01 | run02 (partial) |
|---|---:|---:|
| records | 20962 | 10631 |
| `ok` | 7789 | 6684 |
| `wrong_value` | 6937 | 1554 |
| `silent_zero` | 3944 | 1515 |
| `not_written` | 1064 | 246 |
| `fault` (pre-confirmation) | 1107 | 533 |
| `hang` | 0 | 0 |
| baseline health checks | 190, **188 passed** | 95, **95 passed** |
| `...ErrorInnocentVictim` retries absorbed | 1551 | 369 |
| `...ErrorHang` classifications seen | 1791 | 1153 |
| `...ErrorPageFault` classifications seen | 1375 | 420 |

Every failed health check triggered a fresh runner process and the following check passed;
neither capture is a cascade. **Zero hangs in either run**, so no arm hit the two-hang stop
rule.

### 9.1 Which way contamination biases this experiment

Worth stating, because it bounds the damage if a lease pass is starved by the queue (five agents
were waiting on `gpulease.sh` while this ran). **Contamination can only turn an `ok` into a
failure, never a failure into an `ok`.** A discarded or hung command buffer returns no output at
all, and a poisoned read-back plus a query-independent sentinel means a dispatch that did not run
is recorded `not_written`, not `ok`.

Every claim in §3 has the form *"these values reproduce the host oracle"*, and every exact rule
`(v & M) == V` is computed from the **ok-set**. So contamination shrinks the ok-set and makes the
rules **conservative**, not wrong: the failure mode is under-claiming an accepted value, not
inventing one. What contamination *can* corrupt is the distinction between `fault` and
`wrong_value` among the REJECTED values — which is exactly what the lease pass is for, and
exactly what does not move a rule.

**Cross-run disagreement.** Over the RSH gate's ~15 000 common cases, **170 disagree (1.1 %)**,
and they are concentrated rather than spread: the `h4fma`/`h_coord_hi` arm — the fault-heaviest
in the experiment, a quarter of whose values fault — accounts for most of them. Disagreeing cases
are excluded from every verdict, never averaged.

**Every `fault` and `hang` verdict is re-run 5× under `~/agxre/gpulease.sh`**
(`raw/g17p_reval01`), per FIELD-SWEEP-PROTOCOL §7A — which exists because EXP-0153 showed that
majority-of-3 *plus* cross-run agreement still let four contaminated cases through, and only
isolation caught them. A `fault` that does not reproduce under the lease is re-classified and
excluded from the gate.

## 10. Deviations from the frozen contract

All recorded here rather than by editing `PRE_REGISTRATION.md`.

1. **Arms L/M were extended and arms N, Q, Q2 added** (`harness/run_lm.py`). §5.5 pre-registered
   the register-witness length probe; N/Q/Q2 are *sweeps of that same probe* added after the first
   capture showed the six real `op04_len8` patterns consuming 12 bytes rather than 8, which the
   five-witness form could only bound. Both pre-registered controls run in every one of them.
2. **`harness/reachprobe.py` (arm P) was added** after arm R found `rtq_pred`/`rtq_dualsrc` inert
   at every anchor. It is a control, not a sweep: it distinguishes `inert` from `unreached`, and
   without it §2's twelve zero-live rows would have been silently mis-read as "inert".
3. **Bounding-box carriers were added** (`kernels/k_rq_bbox.metal`, `harness/carriers_bbox.py`,
   `--accel-kind bbox`), reported under their own arm letter `B`. `carriers.py` is untouched and
   the pre-registered arms R/S/H are byte-identical to what was captured before those files
   existed.
4. **A second provocation round was added** (`kernels/k_provoke2.metal`) so that §6's two
   negatives rest on two independent rounds rather than one.
5. **`harness/run.py` gained `--repeats` and `--revalidate-outcomes`** in response to the
   coordinator's mid-run relay of FIELD-SWEEP-PROTOCOL §7A. The gated captures are unaffected.
6. **run02 was started concurrently with run01 rather than after it** (`harness/chain2.sh`).
   The two gated runs are independent captures of the same frozen case list; nothing required
   them to be sequential, and run01's fault-heavy `h_coord_hi` arm would otherwise have cost
   hours of wall time for no evidentiary gain. Both runs' `00_env.json` records the concurrency.
7. **`persistrun.py`**: the coordinator relayed a fix for an EOF spin. The neo's copy was verified
   byte-identical to the fixed repo copy (`cc53d8ef…`), so no re-copy was needed.
8. **The §7A fault-confirmation pass had to be retried** (`harness/chain4.sh`). The first attempt
   never executed: at the moment it invoked the shared `~/agxre/gpulease.sh`, that script was
   mid-rewrite by another agent and bash could not parse it (`unexpected EOF while looking for
   matching '` at line 48). `bash -n` passes on it now, so it was a transient half-written file.
   **Operational note for the wave: editing a shell wrapper in place while eight agents invoke
   it is a race whose failure mode is silent — the wrapper exits non-zero and the payload simply
   never runs.** chain4 `bash -n`s it before invoking it.
9. **The gate is `run01` vs the UNION of the later runs, not their intersection**, because run02
   (partial) and run03 (targeted) cover complementary carriers. Intersecting all three briefly
   under-reported this experiment as 3 emittable descriptors instead of 6, purely because run03
   was still mid-capture.

## 11. Verdict

<!-- BEGIN GENERATED: python3 analysis/summary.py -->
### Captures actually on disk

| run | records | role |
|---|---:|---|
| `g17p_run01` | 20962 | gated capture 1 (arms R, S, H) — complete |
| `g17p_run02` | 11854 | gated capture 2 — RETAINED PARTIAL, stopped, not reused |
| `g17p_run03` | 3648 | targeted gated capture 2 for the carriers run02 never reached |
| `g17p_reval01` | — | **NOT PRESENT** — fault/hang confirmation, ATTEMPT 1 -- never ran, the shared gpulease.sh was mid-rewrite (section 10.8) |
| `g17p_reval03` | — | **NOT PRESENT** — fault/hang confirmation RETRY over all three gated captures, 5x per case, UNDER THE GPU LEASE |
| `g17p_raymove01` | 3258 | arm B2 capture 1 (ray_move in the 25 kB carrier) |
| `g17p_raymove02` | 3258 | arm B2 capture 2 |
| `g17p_bbox01` | 1948 | bounding-box carriers (single capture, reported not promoted) |
| `g17p_reach01` | 29 | reachability control |
| `g17p_fence01` | 2 | fence litmus, inert filler |
| `g17p_fence02` | 2 | fence litmus, zero filler |
| `g17p_lenmap01` | 6421 | arms L/M/N — hardware length probe |
| `g17p_qlen01` | 1793 | arm Q — length vs byte+1 x byte+2 |
| `g17p_qlen02` | 2048 | arm Q2 — length vs byte+2 |
| `g17p_census01` | 0 | own-MSL compile census (no dispatches) |

> ⚠ **`g17p_reval03` not on disk at the time this table was generated.** Those captures were queued behind other agents on `~/agxre/gpulease.sh`. Any claim in this report that depends on them is marked as such; nothing was promoted on their assumed content.

### Gate
* **B2** — g17p_raymove01 + g17p_raymove02: 3059 common cases, **3058 agree**, 1 disagree; 8 of 57 scanned anchors live.
* **RSH** — g17p_run01 + g17p_run02 + g17p_run03: 15033 common cases, **14863 agree**, 170 disagree; 47 of 119 scanned anchors live.

### Per-descriptor verdict

| descriptor | fields | status | operand fields an emitter can still not choose | blocking |
|---|---:|---|---|---|
| `sr_read_wide` | 6 | **EMITTABLE** | `dst` | — |
| `ray_move` | 4 | **EMITTABLE** | — | — |
| `ray_move_copy6` | 4 | **EMITTABLE** | — | — |
| `ray_move_zero6` | 4 | **EMITTABLE** | — | — |
| `rtq_state_move` | 4 | **EMITTABLE** | — | — |
| `n2_op6` | 6 | **EMITTABLE** | `dst` | — |
| `n3_mov` | 5 | **EMITTABLE** | — | — |
| `sfu_marker` | 0 | no fields in db.json | — | — |
| `h_coord_hi` | 6 | not yet | `dst`, `srcA`, `srcB` | `mods` |
| `h_coord_hi_ext` | 7 | not yet | — | `dst`, `ext`, `opsel`, `srcA`, `srcB`, `srcC`, `tail` |
| `scoreboard_fence` | 3 | not yet | — | `kind`, `mask`, `scope` |
| `op04_len8` | 3 | not yet | — | `body`, `dst`, `mode` |
| `mesh_out_src` | 1 | not yet | — | `sel` |
| `n2_op10` | 5 | not yet | — | `dst`, `immword`, `opdesc`, `opsel`, `src` |
| `compute_fence_scoped` | 3 | not yet | — | `kind`, `mask`, `scope` |
| `ray_move_zinit` | 4 | not yet | — | `b3`, `dst`, `form`, `src` |
| `rtq_dualsrc` | 3 | not yet | — | `b3`, `opA`, `opB` |
| `rtq_pred` | 0 | no fields in db.json | — | — |
| `n2_op8` | 4 | not yet | — | `body`, `dst`, `opsel`, `srcA_desc` |
| `coord_madf` | 5 | not yet | — | `b1`, `body`, `mark`, `op`, `srcA` |

**7 of 20 dispatched descriptors are EMITTABLE** under the DOC-02 rule (5 of them with full operand choice). 81 per-carrier field entries reached emitter grade, which reduce to **39 merge-ready `<mnemonic>.<field>` entries** in `analysis/field_verdicts.json` (the form `work/merge_verdicts.py` accepts); the per-carrier detail stays in `analysis/field_verdicts_by_carrier.json`.
<!-- END GENERATED -->

### What this does to `validation.json`

`analysis/field_verdicts.json` is emitted in the exact form `work/merge_verdicts.py` accepts —
plain `<mnemonic>.<field>` keys, with the exact rule, outcome counts, carrier, anchor and
semantics folded into `note`. A dry run of the orchestrator's merger against it:

```
applied 39 field verdicts, skipped 6
emitter-grade: 552 -> 590 fields
emittable instructions: 53 -> 60
  now emittable: ... n2_op6, n3_mov, ray_move, ray_move_copy6, ray_move_zero6,
                     rtq_state_move, sr_read_wide ...
```

**Seven instructions newly emittable, +38 fields to emitter grade.** The six skips are this
experiment's deliberate declines — `op04_len8` ×3 (§4: its length is refuted) and
`scoreboard_fence` ×3 (§5: a removal litmus is not an ordering litmus). The merger refuses to
weaken a label without a human decision, which is exactly the right behaviour for a refutation,
and both reasons are recorded per field in `analysis/field_verdicts.json`.

**A convention warning worth passing on.** The merger requires `<mnemonic>.<field>`; a
`<mnemonic>.<field>@<carrier>` key is rejected outright. EXP-0146's verdict file uses the
`@carrier` convention, which is very likely why its dense M4 sweeps of `n2_op6`, `n2_op8`,
`n2_op10`, `n3_mov` and `sfu_marker` never reached `validation.json` — those instructions still
read `untested` there while a committed `field_verdicts.json` says `hardware-run`. This
experiment therefore emits **both** files: the merge-ready one and
`analysis/field_verdicts_by_carrier.json` with the per-carrier and per-byte detail. Two of this
experiment's own strongest results — `sfu_marker.byte+0` and `.byte+1` — are in the second file
only, because `db.json` gives `sfu_marker` **no fields at all** for them to merge into (§3.4).

Read the two right-hand columns together. A descriptor marked **EMITTABLE** has every
`db.json` field at `hardware-run` under a two-run gate — but where the fourth column names a
field, the accepted set for that field is the compiler's own value up to don't-care bits, so an
emitter still cannot *choose* that operand from this evidence. Reporting only the first number
would overstate the result, which is why `analysis/emittability.py` computes both.

Three descriptors are deliberately **not** promoted despite mechanically qualifying, each with
its reason recorded per field in `analysis/field_verdicts.json`:

* `scoreboard_fence` and `compute_fence_scoped` — §5: a removal litmus is not an ordering litmus;
* `op04_len8` — §4: its **length is refuted on hardware**, so every field offset in the descriptor
  is measured against a model that is wrong. No field of a descriptor whose length is refuted may
  be promoted.

## 12. Recommended next work, in value order

1. **Upstream the acceleration-structure path.** `harness/agxrun_persist_as.m` is
   `tools/agxtest/agxrun_persist.m` plus one fenced block. Merging it makes the whole ray-query
   surface sweepable for every future experiment, and it is the single change that unblocked this
   one. (Kept out of `tools/` here only because four sibling experiments were rebuilding that file
   concurrently.)
2. **Fix `op04_len8`'s length in `db.json`** from the measured map
   (`analysis/length_rule.json`, `analysis/length_map_q.json`): the `04` leader's length is a joint
   function of `byte+1` bit 7 and `byte+2`, not a constant 8. Same for `mesh_out_src`, whose
   2-byte claim holds only for `byte+1` bit 7 clear. Re-tokenizing the corpus under the corrected
   rule is then a much better-posed version of the question EXP-0148 left open.
3. **Give `sfu_marker` and `rtq_pred` fields.** `sfu_marker` has two demonstrably load-bearing
   bytes (§3.4, three carriers, matching EXP-0146's M4 rules exactly) and zero fields in
   `db.json`; it is currently counted against emittability while modelling nothing.
4. **Reach `rtq_pred` / `rtq_dualsrc`.** Neither triangle nor bounding-box geometry executes their
   region. The remaining untried paths are motion-blur (`intersection_query<motion>`), instance
   queries with a non-identity transform, and a query that *terminates* early
   (`q.abort()` / `accept_any_intersection`) — the last is the best bet, since a traversal
   predicate is most plausibly on the early-out path.
5. **Make `sr_read_wide.dst` choosable.** Its destination is pinned in all three carriers because
   the following code reads exactly that register. A synthesised program (rather than a spliced
   compiled one) would free it, using EXP-0154's technique of seeding all 16 GPRs distinctly and
   dumping all 16 afterwards.
6. **`n2_op8` and `coord_madf` need a carrier, not a sweep** — 59 own-MSL programs compiled on
   G17P contain neither (`raw/g17p_census01/provocation_census.json`).

## 13. Reproduction

On the neo (`~/agxre/EXP-0157`), `AGX_TOOLS=$HOME/agxre/tools`:

```sh
bash harness/build.sh
python3 -B harness/run.py --run-id g17p_run01 --bin-dir bin --work work/w_run01 \
        --raw raw/g17p_run01 --arms R,S,H --max-anchors 12 --sweep-anchors 1
python3 -B harness/run.py --run-id g17p_run02 --bin-dir bin --work work/w_run02 \
        --raw raw/g17p_run02 --arms R,S,H --replay raw/g17p_run01/00_cases.json
~/agxre/gpulease.sh EXP-0157 2700 -- python3 -B harness/run.py --run-id g17p_reval01 \
        --bin-dir bin --work work/w_reval --raw raw/g17p_reval01 --arms R,S,H \
        --replay raw/g17p_run01/00_cases.json --revalidate work/gated_all.jsonl \
        --revalidate-outcomes fault,hang,nondeterministic --repeats 5
LENMAP_CANDS=3 LENMAP_BYTES=0,1,2,3,4,5,6,7 python3 -B harness/run_lm.py \
        --run-id g17p_lenmap01 --bin-dir bin --work work/wl --raw raw/g17p_lenmap01 \
        --candidates work/op04_candidates.json --arms N,L,M
python3 -B harness/run_lm.py --run-id g17p_qlen01 --bin-dir bin --work work/wq \
        --raw raw/g17p_qlen01 --candidates work/op04_candidates.json --arms Q
python3 -B harness/run_lm.py --run-id g17p_qlen02 --bin-dir bin --work work/wq2 \
        --raw raw/g17p_qlen02 --candidates work/op04_candidates.json --arms Q2
python3 -B harness/reachprobe.py --run-id g17p_reach01 --bin-dir bin --work work/wr \
        --raw raw/g17p_reach01 --carrier rq_cdist --anchors work/reach_anchors.json
EXTRA_CARRIERS=bbox EXTRA_ARMS="B:bb_commit:rtq_pred:10,..." \
python3 -B harness/run.py --run-id g17p_bbox01 --bin-dir bin --work work/wb \
        --raw raw/g17p_bbox01 --arms B --max-anchors 12 --sweep-anchors 1
```

In this repository:

```sh
python3 analysis/verdicts.py raw/g17p_run01 raw/g17p_run02 \
        --out analysis/field_verdicts_RSH.json --report analysis/gate_report_RSH.json
python3 analysis/verdicts.py raw/g17p_raymove01 raw/g17p_raymove02 \
        --out analysis/field_verdicts_B2.json --report analysis/gate_report_B2.json
python3 analysis/merge.py            # -> analysis/field_verdicts.json
python3 analysis/emittability.py     # -> analysis/emittability.json
python3 analysis/lenrule.py raw      # -> analysis/length_rule.json, length_map_q.json
python3 analysis/summary.py          # the tables in section 11
python3 analysis/shapes.py raw/g17p_run01 sfu_marker byte+0 sfusin   # section 3.4
python3 analysis/shapes.py raw/g17p_run01 n2_op6 opsel sfusin        # section 3.3b
python3 analysis/shapes.py raw/g17p_run01 scoreboard_fence kind u64eq # section 5
bash analysis/finalize.sh            # all of the above, in order
```

`work/pull.sh` copies `raw/` back from the test target; `work/sync.sh` pushes the authored
sources to it. Neither is part of `finalize.sh`, which is pure analysis over what is already in
`raw/`.
