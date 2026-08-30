# EXP-0204 — RESULTS

**Target: Apple A18 Pro / G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6, Metal
family Apple9). Nothing ran on the M4. **Clean-room: OWN-SHADER + HW-PROBE — no Apple binary was
disassembled, decompiled, symbol-dumped, strings-scanned or introspected.**

`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` is normative for everything below and **wins where it
conflicts** with the gates this experiment originally froze. Section 15 of `PRE_REGISTRATION.md` is
the Amendment-2 restatement, frozen before its first dispatch.

---

## 0. Headline, on the six axes

Exact numerators and denominators throughout. **No percentage appears without its fraction.**

| field | geometry | liveness | semantics | recipe | target | reproducibility | legacy label |
|---|---|---|---|---|---|---|---|
| `tex_sample.mode` | **ledger-verified** 5119/5119 | **live** on 10/10 arms | **hypothesis** — the pre-registered model is **REFUTED** (1/30) and replaced by an exact bit rule | not-generated | G17P-direct | auditable (6/10 arms at 256/256; Gate E not met) | `untested` |
| `tex_write.amode` | **ledger-verified** 6144/6144 | **accepted-inert in the tested envelope**, 0/3072 moved | **bounded-map** 3072/3072 (the store still landed where and with what the host predicted, at every value) | not-generated | G17P-direct | auditable (12/12 arms ≥ 99 %; Gate E not met) | `untested` |
| `tex_write.rsv11` | **ledger-verified** 6144/6144 | **accepted-inert in the tested envelope**, 0/3072 moved | **bounded-map** 3072/3072 | not-generated | G17P-direct | auditable (12/12 arms ≥ 99 %; Gate E not met) | `untested` |
| `tex_deriv.dstsrc` | ledger-verified on the A2 runs | **live** | **unknown** — *no semantic model was pre-registered*, so Gate C caps this field at `live; role unknown` **by design, stated in advance** | not-generated | G17P-direct | see §4 | `untested` |
| `cubearray_coord_const.b3` | — | — | — | — | — | — | **UNRESOLVED** (§5) |

**`untested` here is not "no evidence".** Under `RE_EXPERIMENT_PROCESS_CORRECTIONS.md` §2,
`hardware-run` requires semantic checks against an independent predictor and `isolated-byte-diff`
requires a *predicted* semantic effect at the tested point. Reproducible liveness with a refuted or
absent semantic model maps to the legacy `untested` — and the real content is in the axes, the
counts, and §§1–5 below. Liveness must not be rounded up into the legacy label.

**Nothing here is claimed emittable.** Gate D (a generated compiler recipe) was not attempted.

---

## 1. `tex_sample.mode` — the documented enum is WRONG, and the field is a 3-bit bitfield

### 1.1 The carrier dimension, and that it was actually spanned

`mode`'s dimension is the **sample-operation class**. Six carriers were authored, one per class,
and the **pre-freeze census settles that they span it — by the compiler's own choice**:

| carrier | operation | compiler's own `mode` |
|---|---|---|
| `msfilt` | implicit-LOD linear filtered sample | **0x10** |
| `msfixl` | explicit-`level()` linear filtered sample | **0x10** |
| `msgath` | `gather` | **0x00** |
| `msread` | integer `read` (3 explicit levels) | **0x00** |
| `mscmp` | depth `sample_compare` (linear PCF + nearest) | **0x00** |
| `mslodq` | `calculate_clamped_lod` / `calculate_unclamped_lod` | **0x20** |

**All three values `db.json` documents appear as compiler-chosen baselines.** No carrier in this
corpus had ever emitted an LOD query at all; it needs a **mipmapped** sampled texture, which the
harness gained for this experiment (`--tex-mip`).

Every one of the ten arms passed Gate B: detection power **10/10**, and a moved control **in
`mode`'s own dimension** (`variant` / `result_desc` / `lod_present`) **10/10**.

### 1.2 The host oracle validated the whole chain before anything was spliced

`harness/oracle.py` predicts each carrier's baseline exactly, from the triangle our own vertex
shaders draw and the texture content `gfrun4.m` itself writes. On the baseline of every arm:

- `msfilt`, `msfixl`, `msgath`, `msread`, `mslodq`: **28/28 channels agree**
- `mscmp`: **16/16** (its nearest-filter channel is deliberately not predicted)
- the five write carriers: **52/52** (constant destinations) and **28/28** (dynamic ones)
- `deriv`: **28/28**; `deriv2`: **22/28** — the six mismatches are all channel 3, the
  **half-precision** derivative, where the host arithmetic is `float` (observed 333.98438 vs
  predicted 333.33333). **No verdict rests on that channel**, and it is reported rather than
  absorbed by a wider tolerance.

`mslodq` returning exactly `(2.0, 1.0, 0.0, −1.0)` — the host-computed LODs for gradients of 4, 2
and 0.5 texels per pixel, clamped and unclamped — is the single most load-bearing calibration here:
it proves the LOD-query class really executes and is measured correctly.

### 1.3 The pre-registered model is REFUTED

Refuter **R1c/R1d** fired. Splicing the three documented values across classes:

| arm (baseline) | `mode := 0x00` | `mode := 0x10` | `mode := 0x20` |
|---|---|---|---|
| `msfilt/0` (0x10) | **unchanged** | unchanged (own baseline) | silent_zero |
| `msfixl/0`, `msfixl/1` (0x10) | **unchanged** | unchanged | **unchanged** |
| `msgath/0` (0x00) | unchanged | **unchanged** | **unchanged** |
| `msread/0`, `msread/1` (0x00) | unchanged | **unchanged** | **unchanged** |
| `mscmp/0` (0x00) | unchanged | **unchanged** | silent_zero |
| `mscmp/1` (0x00) | unchanged | **unchanged** | correct (compare/lod) |
| `mslodq/0`, `mslodq/1` (0x20) | unmodelled / coherent_other | unmodelled / coherent_other | unchanged |

The semantic predictor's hit rate on the class model is **1 / 30**. **`mode` does not select the
operation class.** The class is fixed elsewhere (`variant` / `result_desc`), and this reproduces
RT-5's older negative — "op+6 spliced 0x00/0x10 on a linear sample: filtering does NOT change" —
from a different direction, with per-value records, on six carriers instead of one.

### 1.4 What the field actually is: an exact bit rule, zero exceptions

`analysis/mode_bits.py` uses **only values whose observation agrees across the two gated runs**,
which were dispatched in **opposite case order**. On the six arms whose agreement is 256/256 the
moved set is described **exactly** by a mask rule:

| arm | cross-run agreement | moved | exact rule | live bits |
|---|---|---|---|---|
| `mscmp/0` | 256/256 | 224/256 | `moved ⟺ (mode & 0x2C) ≠ 0` | 2, 3, 5 |
| `mscmp/1` | 256/256 | 224/256 | `moved ⟺ (mode & 0x2C) ≠ 0` | 2, 3, 5 |
| `msfilt/0` | 256/256 | 224/256 | `moved ⟺ (mode & 0x2C) ≠ 0` | 2, 3, 5 |
| `msfixl/0` | 256/256 | 192/256 | `moved ⟺ (mode & 0x0C) ≠ 0` | 2, 3 |
| `msfixl/1` | 256/256 | 192/256 | `moved ⟺ (mode & 0x0C) ≠ 0` | 2, 3 |
| `msgath/0` | 255/256 (1 `InnocentVictim`) | 127/255 | `moved ⟺ (mode & 0x08) ≠ 0` | 3 |
| `mslodq/0` | 220/256 | 196/220 | none | — |
| `mslodq/1` | 242/256 | 217/242 | none | — |
| `msread/0` | 103/256 | 60/103 | `(mode & 0x0A) ≠ 0` (over the agreeing subset only) | — |
| `msread/1` | 146/256 | 107/146 | none | — |

**Bits 0, 1, 4, 6 and 7 (mask 0xD3) are inert on every stable arm** — identical moved-rate whether
set or clear (112/128 both ways on `mscmp/0`). That includes **bit 4 = 0x10, which `db.json` names
"filtered sample" and which is the compiler's own baseline on `msfilt` and `msfixl`.**

**Bit 5 (0x20) is context-dependent:** live on the three implicit-LOD arms, **inert on the two
explicit-`level()` arms**, reproduced at 256/256 on all five. That is a field-dependency edge
(`RE_EXPERIMENT_PROCESS_CORRECTIONS` §5 Phase 4) between `mode` bit 5 and whether the occurrence
carries an explicit LOD — which is exactly what one would expect if 0x20 selects an LOD-query path
that an explicit level makes vacuous.

**Status of this rule.** It was derived *after* the sweep, so it is a **hypothesis**, not a
`bounded-map`: it survived a cross-run reproducibility test in opposite case order but was never
predicted in advance. §4 of the corrections document forbids editing a hypothesis to match captured
data, so it is recorded as the successor's pre-registration target, not promoted here.

### 1.5 What is NOT shown

- Four of ten arms (`msread` ×2, `mslodq` ×2) are **not reproducible** (103/256 … 242/256) and
  support nothing. Those arms have 10–13 distinct valid payloads, consistent with a corrupted
  sample descriptor reading undefined data; that is a conjecture, not a measurement.
- The rule is bounded to these six carriers and this envelope. `inert in the tested envelope;
  global role unknown` is the correct wording for bits 0,1,4,6,7.

---

## 2. `tex_write.amode` and `tex_write.rsv11` — the third carrier the refusal asked for, and what it found

### 2.1 The refusal, and why the prior carriers were one carrier

The recorded refusal, identical for both fields: *"STILL-UNDERPOWERED: swept densely on 6 arms but
only 2 distinct carriers with proven detection power (the pre-registered bar is 3), so NOT
promoted. Reported as unreached, not as inert."* Those two were EXP-0163's `twdim` and `twtype`. In
`amode`'s **own** dimension they are one carrier: every write in both is
`write(colour, uint2(LITERAL, LITERAL))` at implicit level 0, and every arm's baseline is `0x54`.

### 2.2 Five carriers, five address forms, five observation paths

`RE_EXPERIMENT_PROCESS_CORRECTIONS` §5 Phase 5: *two carriers with the same leaf callee, state
shape, or observation path count as one method.* These five differ in all three:

| carrier | address form / provenance that is new | destination resource observed |
|---|---|---|
| `twmip` | **explicit mip-level operand** in the write address | `TEXWM0/1/2` (per-level read-back) |
| `twbuf` | **`texture_buffer`** — linear 1-D texel index | `TEXWB` |
| `twcube` | **cube face** operand (`coord_dim` 0x0C, never emitted before in this corpus) | `TEXWC0…5` |
| `twcomp` | **1-component `R32Float` and 2-component `RG32Float`** destinations | `TEXWR`, `TEXWG` |
| `twdyn` | **register-formed (per-fragment) coordinate**, and a contiguous `float4` store with **no ALU between the load and the write** | `TEXW`, `TEXWA0…3` |

The census also broke the `0x54`-only monoculture: the compiler itself emits **`amode = 0x55`** on
the last write of `twbuf` and of `twcube`, so two of the twelve arms have a **different baseline
value** — something no prior experiment's arms had.

### 2.3 The measurement

12 arms × 256 values × 2 gated runs (forward and reverse case order), for each field:

| quantity | `amode` | `rsv11` |
|---|---|---|
| encodable values | 256 | 256 |
| distinct requested values dispatched | 256 | 256 |
| **distinct ACTUAL encodings dispatched** (Gate A) | **256** | **256** |
| **ledger cases OK / checked** | **6144 / 6144** | **6144 / 6144** |
| arms with detection power (Gate B) | 12 / 12 | 12 / 12 |
| arms with a moved control **in the field's own dimension** | 12 / 12 | 11 / 12 |
| values that moved the observation | **0 / 3072** | **0 / 3072** |
| cross-run agreement (worst arm) | 255/256 | 255/256 |
| cross-run disagreements, all arms | 1 / 3072 | 1 / 3072 |
| hard outcomes (fault/hang/undecodable/malformed) | 0 | 0 |
| **semantic checks: the store landed where and with what the host predicted** | **3072 / 3072** | **3072 / 3072** |
| distinct valid observed payloads | 1 | 1 |

### 2.4 Verdict, worded as §7 requires

**`inert in the tested envelope; global role unknown`** — *not* "unused", "reserved" or "may be
chosen arbitrarily", and **not** a withdrawal of the prior "unreached" wording.

§7's bar, item by item:

| §7 requirement | status |
|---|---|
| ≥3 structurally different carrier/context classes | **met** — 5 carriers, 4 address forms, 5 observation paths, plus an operand-provenance variant |
| a positive detection-power control in every carrier | **met** — 12/12 arms, controls in the addressing dimension (`coord_pack`, `coord_regs`, `coord_dim`, `layer_reg`) and the format dimension (`data_desc`, `data_desc_hi`, `rsv8`) |
| interactions with every plausible selector | **NOT met** — no pairwise interaction array was run. Address form, destination resource, component count and data provenance were varied; opcode/sub-op, stage (compute), mask/order state and register lifecycle were **not** |
| two clean isolated repetitions | **NOT met** — see §6; both gated runs were on a measurably busy machine |
| an independent compiler-differential method | **partially met** — the 13-carrier census is a compiler differential: it shows the compiler choosing `0x54` and `0x55` for `amode` and **`0` for `rsv11` on every occurrence, including the 1- and 2-component destinations** |

**The surviving explanations, kept separate as §7 demands:**

1. **accepted-inert over the tested hardware envelope**;
2. **a contextual field whose effect is unobservable with this instrumentation.** This is the one
   that must not be waved away. `db.json`'s own vocabulary for this byte position
   (`device_load.addr_mode`) distinguishes *"terminal/standalone"* from *"non-terminal of a
   base-sharing group"*, and our own census shows the compiler using `0x55` **only on the last
   write of a program**. A base-sharing-group or ordering marker changes *how* stores are grouped,
   not *what* a post-completion read-back sees — the same argument that made three prior
   experiments decline to promote `ret.scoreboard`. **This harness reads back after
   command-buffer completion, which flushes, so it has no ordering observable.** The `0/3072`
   result therefore bounds the field for a single-store, read-after-completion emitter and says
   nothing about grouping or ordering.
3. For `rsv11`, additionally: **a format-tail bit that no MSL-reachable destination sets.** The
   compiler emits 0 for it on 1-, 2- and 4-component destinations of float, half and integer type.

---

## 3. `tex_deriv.dstsrc` — the hazard region is a family, not two values

### 3.1 What the named debt actually was

EXP-0189 withheld this field as **UNSTABLE**: *"65 values dispatched over 4 arms, 198 observations
moved"* — it failed on cross-run stability, not on liveness. EXP-0172's own account is that all
five disagreeing values were `fault` in one run and `InnocentVictim` in the other, **at exactly the
values that hang**, and that its per-field hang budget of 2 stopped every arm at **39 of 65**.

### 3.2 The mapping pass did what the budget could not

Declared in advance (`PRE_REGISTRATION` §7) as a named hang-tolerant **mapping pass** with a budget
of 8 instead of 2, and announced in `PROGRESS.md` as a courtesy:

- `raw/g17p_20260830_A2run03_derivmapping`: **65/65 values swept on both arms** (`complete: true`),
  54/65 and 53/65 moved, **7 genuine device hangs**, 0 cascade, 156 cases, 310 s.
- The earlier partial `raw/g17p_20260830_run01` also reached **65/65 on `deriv/0`**.

**The hazard is a family, not the two isolated values EXP-0172 could see.** Reproduced fault/hang
values include `0x3FFFF`, `0x7FFFF`, `0xFFFFF`, `0x1FFFFF`, `0x7FFFFF` — the **all-ones prefixes** —
plus `0xFBEEE7`. EXP-0172 stopped after the first two. This is precisely
`FIELD-SWEEP-PROTOCOL` §3(c)'s warning that a per-field budget *"guarantees the region is never
mapped"*, and the device survived every hang with no wedge and no `macvdmtool`.

### 3.3 Gate A caught a real geometry fact

`dstsrc = 0x80` on `deriv2/0` produced bytes that are **on disk exactly as requested**
(`bytes_match: true`) but **decode as no descriptor at all** (`no descriptor matches bytes
3705800000109240 at offset 142`). The case is recorded `ledger_mismatch` and **excluded from every
hardware conclusion** — neither movement nor inertness. Part of `dstsrc`'s nominal 2²⁴ space does
not produce a decodable `tex_deriv`. This is exactly what Gate A exists for, and no earlier
experiment on this field could have seen it.

### 3.4 Ceiling, stated in advance

**No semantic model was pre-registered for `dstsrc`**, and `PRE_REGISTRATION` §15.3 says why: the
`deriv` carriers are deliberately **affine** (which is what makes each derivative constant over the
primitive and exactly host-computable), and §5 Phase 3 of the corrections document warns that an
affine field makes many candidate operations indistinguishable. So `sem_checked = 0`, and by §2
**`hardware-run` is unreachable for this field in this experiment**. Its honest status is
**`live; role unknown`**. The successor needs **non-affine coordinates/channel values** and a
pre-registered bit-split model for the packed destination/source pair.

---

## 4. `cubearray_coord_const.b3` — UNRESOLVED, and the reason is now sharper

Promotion was **declined in advance** (`harness/carriers.py::DECLINED`, `PRE_REGISTRATION` §3 H5):
two experiments had already shown the descriptor cannot be provoked from MSL (EXP-0148: 0 firings
in 1080 corpus files, its signature interior to a `tex_addr_setup` token; EXP-0187: 31 authored
cube/cube-array constructs across 12 shapes, 0 hits). Re-running either would learn nothing.

The different question this experiment asked is **synthesis**: place the four bytes by hand.
`analysis/cube_decode.py` (offline, against the pinned database, no GPU):

- `f0 c0 04 <b3>` decodes as **`cubearray_coord_const`, length 4, for all 256 values, standalone**;
- and also in context at the carrier's **trailing** 4-byte boundary (`@296`, all 256 values);
- but at the **other** proven 4-byte boundary in the same program (`@250`) it decodes as
  **`pad_operand`, length 2, for all 256 values** — a different descriptor claims the leading bytes
  first.

So the descriptor is **shadowed in the decode table**, not obviously absent from the silicon. The
hardware arm of the probe overwrote a live `falu_acc` at `@250` and, as pre-registered, its only
detection power is *"we deleted the original instruction"* — power in the wrong dimension. **`b3`
is therefore reported UNRESOLVED and no value semantics are claimed.** What *is* delivered is the
decode evidence the orchestrator's open question needs (delete / re-anchor / tighten the match):
`DEF-0204-3` in `analysis/field_verdicts.json`.

---

## 5. Database defects reported (not applied — `db.json` is the orchestrator's file)

Full text with evidence pointers in `analysis/field_verdicts.json → db_defects`.

- **DEF-0204-1** — `tex_sample.mode` is modelled as an enum `{0x00, 0x10, 0x20}`; it is a
  **bitfield**, and **0x10 is inert** on every arm including the two where it is the compiler's own
  baseline. Live mask is `0x2C` at most.
- **DEF-0204-2** — `tex_sample.mode` bit 5 is **context-dependent** (live under implicit LOD, inert
  under explicit `level()`): a field-dependency edge, so a single-carrier sweep cannot describe it.
- **DEF-0204-3** — `cubearray_coord_const` is **shadowed by `pad_operand`** at an interior 4-byte
  boundary while decoding correctly standalone and at a trailing boundary.
- **DEF-0204-4** — `tex_write.rsv10` (byte+10) is **not reserved**: the census's three
  explicit-level writes differ only there (`0x00`/`0x10`/`0x20` for levels 0/1/2). Reported as a
  three-point compiler differential, not a swept result.

---

## 6. Limitations, and the gates that were NOT met

1. **Gate E (clean confirmation) is NOT MET for any field.** `raw/*/procs.jsonl` is a
   *measurement*, and it says every run was **BUSY**: 0 quiet samples in every run, with EXP-0199,
   EXP-0200, EXP-0205 and EXP-0206 dispatching throughout. Per the corrections document a
   confirmation run may not rely on a busy machine **at all**, so **nothing here is
   `independently-confirmed`**, and the coordinator's earlier "mark it contaminated" allowance is
   superseded. What *is* true, and is reported as such: the two `tex_sample`/`tex_write` runs were
   in **opposite case order**, completed **9276 cases each with 0 hangs, 0 cascades and 0 runner
   restarts**, and produced **exactly 1 disagreement in 3072** on the `tex_write` fields.
2. **Gate D was not attempted.** No instruction is claimed emittable, and no field is
   `canonical-recipe-proven`.
3. **Interaction coverage is absent.** No pairwise covering array was run. `tex_write`'s inertness
   is bounded to fragment stage, single-shader, read-after-completion observation.
4. **Four `tex_sample.mode` arms are irreproducible** and support nothing.
5. **The `deriv2` half-precision channel is not host-validated** (22/28) and carries no verdict.
6. **`raw/g17p_20260830_run01` ran under the original gate** — no ledger, no semantic oracle, busy
   machine, killed by an SSH hang-up at 404 cases. It is **retained, never topped up, never reused**
   and **excluded from every Amendment-2 gate**; it is reported as a discovery sweep only.
7. **Eight of the arms were located by anchored SCAN**, not by a complete forward tokenization,
   because several carriers do not tokenize to the end under the pinned database. Every such arm
   nevertheless passed its detection profile and its bytes and offset were asserted byte-exact
   against the census before any sweep.

## 7. Recommended next experiments

1. **Pre-register the `mode` bit rule and test it.** `moved ⟺ (mode & 0x2C) ≠ 0` under implicit
   LOD and `(mode & 0x0C) ≠ 0` under explicit `level()` is a sharp, falsifiable prediction. A
   successor should pre-register it, add carriers that separate bits 2 and 3 semantically (what
   *does* bit 2 do? bit 3 silently zeroes the sample on `msgath` — is that a disable?), and run it
   on a quiet machine.
2. **`tex_write.amode` needs an ORDERING observable**, not another carrier. Two stores to the same
   texel in one shader, or a store followed by an in-shader read of the same texel, would make a
   base-sharing/terminal marker visible. Until then the `0/3072` result cannot distinguish
   "inert" from "unobservable here".
3. **`tex_deriv.dstsrc` needs non-affine sources** and a pre-registered dst/src bit-split model;
   only that can lift it off `live; role unknown`.
4. **`cubearray_coord_const` is an orchestrator decision**, not a sweep: the descriptor decodes
   correctly standalone but is shadowed by `pad_operand` in context.
