# EXP-0172 — RESULTS

**Target:** Apple A18 Pro / **G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 cores, macOS 26.6,
Metal family Apple9). Nothing ran on the M4.
**Clean-room:** OWN-SHADER + HW-PROBE. Every byte spliced, decoded or inspected is the compiled form
of our own MSL in `kernels/`. **No Apple binary was disassembled or introspected.**
**Gate applied:** `PRE_REGISTRATION.md` §6, implemented by `analysis/verdicts.py` and nothing else.
Verdicts are recomputed from `raw/`, never from a run manifest.

## 0. Headline

**Six fields promoted to `hardware-run`. Five instructions move across the emittable line:
`tex_sample`, `tex_deriv`, `vary_slot`, `irotate`, `frame_marker_compact`.**
A sixth field, `imageblock_store.src`, is promoted but does **not** close its instruction (`b4`
still blocks it). Two fields are proven inert on carriers that span the dimension they control and
are therefore **not** promoted (rule 8). Two are reported `untested` because the method had no
power, and one was declined in advance and stays declined. Four more were declined before any
device time, each with a measured reason.

Against the `validation.json` state measured at analysis time (42 emittable, 600 emitter-grade
fields of 1062), this is **+6 emitter-grade fields and +5 emittable instructions → 47**. The
per-field rows in `analysis/field_verdicts.json` all carry `values_dispatched`, `distinct_bytes`,
`encodable_range`, `start` and `width`; **12 of 12 rows are covered and every span matches the live
`db.json`.**

## 1. Verdicts

| field | verdict | label | coverage (dispatched / distinct bytes / encodable) | cross-run |
|---|---|---|---|---|
| `tex_sample.coord` | **LIVE** | `hardware-run` | 256 / 1024 / 256 | 100 %, 4 arms |
| `tex_deriv.dstsrc` | **LIVE** | `hardware-run` | 65 / 214 / 64 | 100 %, 4 arms |
| `vary_slot.slot` | **LIVE** | `hardware-run` | 256 / 256 / 256 | 100 %, 1 of 4 arms |
| `irotate.b2` | **LIVE** | `hardware-run` | 256 / 1280 / **2** | 100 %, 5 arms |
| `frame_marker_compact.b1` | **LIVE** | `hardware-run` | 256 / 256 / 256 | 100 %, 1 of 5 arms |
| `imageblock_store.src` | **LIVE** | `hardware-run` | 256 / 512 / 256 | 100 %, 2 arms |
| `falu2i.imm_flag` | INERT-ROBUST | `single-template-inference` | 2 / 16 / 2 | 100 %, 8 arms |
| `get_sr.form` | INERT-ROBUST | `single-template-inference` | 2 / 16 / 2 | 100 %, 8 arms |
| `simd_ballot.cache` | INERT-ROBUST | `single-template-inference` | 256 / 1536 / 256 | 100 %, 6 arms |
| `simd_shuffle.cache` | INERT-ROBUST | `single-template-inference` | 2 / 32 / 2 | 100 %, 16 arms |
| `n4_cf_word.b3` | STILL-UNDERPOWERED | `untested` | 256 / 256 / 256 | **no arm had power** |
| `ret.scoreboard` | DECLINED in advance | unchanged | 41 / 41 / 41 | 1 run only |

`distinct_bytes` is counted from **distinct `bytes` strings in `raw/`**, never from the dispatched
value count.

## 2. Observations, separated from interpretation

### 2.1 `tex_sample.coord` — the EXP-0155 irreproducibility is resolved, and the operand form falls out

**Observed.** 256 values on each of four arms, two gated runs. **Per-value cross-run agreement:
100 %** (EXP-0155 got 73–93 %). One arm moves — `texmix` occurrence #3, an integer `read` bundle
(`variant = 23`, `mode = 0`, baseline `coord = 2`) — at exactly 32 of 256 values. The other three
arms, including two derivative-free integer reads on `texread`, move at **zero** of 256.

The 32 moving values are reproduced with **zero exceptions**, in both runs, by

> `moved ⟺ (v & 1) == 1 AND ((v >> 1) mod 16) ∈ {6, 8, 10, 14}`

**Interpretation.** `coord` is an operand byte of the form `(reg << 1) | is32` — exactly the
source-byte convention `db.json` already documents for `falu2` — where bit 0 selects the 32-bit
operand and the upper 7 bits are a register index. On this fragment stage the index **aliases with
period 16**: the four live registers recur at `reg`, `reg+16`, … `reg+112`. That is a new, smaller
period than the mod-64 ALU aliasing HW-validated in EXP-0112, and it is why the *count* of moving
values is 32 rather than 4. A coordinate pointed at a register the program does not keep live
produces a **silent unchanged result, never a fault** — the Apple9 silent-zero behaviour again.

**What this does not show.** Filtered, implicit-LOD sampling was deliberately excluded; the
hypothesis that its derivative/LOD dependence caused EXP-0155's instability is *supported* (the
derivative-free carriers are 100 % reproducible) but not directly demonstrated on a filtered arm.

### 2.2 `tex_deriv.dstsrc` — the first carrier ever authored for this field

**Observed.** The authored `deriv` carrier emits **nine `tex_deriv` occurrences with nine distinct
`dstsrc` values** across both axis codes (`0x92` dfdx / `0x90` dfdy) and the `fwidth` form. On four
arms × two runs, **37 of the 39 values compared change the derivative result, identically in both
runs**. The two that do not are the all-ones patterns `0x3FFFF` and `0x7FFFF`, which **hang the
device** (reproduced, majority-of-3) and stopped the sweep at 39 of 65 sampled values.

**Interpretation.** `dstsrc` is a live packed destination+source operand, as modelled. Nearly any
change alters the result, which is what a register-pair operand should do.

### 2.3 `vary_slot.slot` — live, but one bit, and not the bit the compiler varies

**Observed.** 256 values × 4 arms × 2 runs. On `vsrc`, **all 128 values with bit 2 set move the
observation and all 128 with bit 2 clear do not**, with no exceptions in either run. On `vmany`,
`vhalf` and `vflat` nothing moves at any of 256 values, and those three arms had no strict detection
power. The compiler's own baselines are `0x00 / 0x20 / 0x40` — the varying index shifted left by 5.

**Interpretation.** The modelled 8-bit `slot` has exactly one observable bit here, and it is *not*
where the compiler puts the index (`DEF-0172-3`). This is direct hardware support for EXP-0155's
conclusion that the emitter-relevant lever is `vary_store.out_slot`. The dispatch asked whether this
was even the right lever; the measured answer is **it is a lever, but not the one an implementer
wants**, and the verdict says so in its `note`.

### 2.4 `irotate.b2` — promoted over a two-value range, and asymmetric

**Observed.** `match` pins bit 16 and bits 18..23, so of the 256 dispatched values exactly **two are
legal** (`byte+2 ∈ {0x54, 0x56}`); the other 254 re-decode as a different instruction and are
recorded `undecodable`. Both legal values ran on all five arms in both runs. The effect is
**asymmetric and exactly reproduced**: on the three arms whose baseline is `0x56`, setting `0x54`
changes the observation; on the two arms whose baseline is `0x54`, setting `0x56` changes nothing.

**Why both directions exist.** The smoke calibration caught that my first arm list tested only one
direction (all six `get_sr` arms happened to have `form = 0`), so `gen_arms.py` was changed to bucket
occurrences by the field's own baseline value. That fix is what makes this asymmetry visible.

**Interpretation.** The full encodable range executed with a reproduced value→behaviour partition,
so `hardware-run` is earned — but on a range of **two**, and the modelled 8-bit width is a fiction
(`DEF-0172-1`). The `range` string says exactly that; a generated "0..255 dense" would have been a
lie.

### 2.5 `frame_marker_compact.b1` — live on the carrier that does not hang

**Observed.** On `rot`, 256 values in run01 and run03: **152 move, identically**. On `scache`,
`srnarrow`, `vhalf` and `vsrc`, `b1 = 3` and `b1 = 7` **hang the device**, stopping those sweeps at
8 of 256. `b1 = 0x00` is the 4-byte `spill_frame_marker` — a different instruction.

### 2.6 `imageblock_store.src` — promoted, but the instruction stays blocked

**Observed.** 244 of the 248 executed values change the stored value on both the 1-sample and the
4-sample carrier, identically in both runs. `src = 246, 247` hang the device (reproduced).
**This does not make `imageblock_store` emittable**: `b4` is EXP-0163's INERT-ROBUST result, capped
at `single-template-inference` by rule 8. Said here so nobody counts it as a sixth closure.

### 2.7 The two proven-inert fields, and why they are *not* promoted

`falu2i.imm_flag` and `get_sr.form` are each 1 bit, so **both values are the full encodable range**,
and both were executed on eight arms across two runs with 100 % agreement and zero movement.

They are labelled `single-template-inference`, not `hardware-run`, under rule 8: emitter-grade
asserts an implementer may **choose** the value, and "emit what the compiler emitted" is a
captured-template dependency. The measurement is not downgraded — its full strength is in the row's
`note`, `range` and per-arm records — only the claim about what an emitter may do with it.

Two things make these nulls worth something rather than nothing:

- **`get_sr.form` was tested in both directions and across the dimension `db.json` names.** Four arms
  at `form = 0` and four at `form = 1`, on a scalar-SR carrier and a `uint3` position-in-grid
  carrier. `db.json` calls the bit "a datapath/width modifier (set for the position-in-grid SR
  family)". This experiment **fails to find any effect for that reading**, in either direction, on
  either width class. That is not the same as confirming it.
- **`falu2i.imm_flag` refuted my own pre-registered hypothesis.** §2.9 below.

`simd_ballot.cache` and `simd_shuffle.cache` were re-swept on `deadsrc`, a carrier in which every
operand is loaded, used **once** and dead immediately after — the last-use dimension in which all
four of EXP-0163's carriers were identical, i.e. one carrier under rule 2. They stay inert. The
negative is stronger; the label is unchanged. **`simd_shuffle.cache` still covers two values of one
bit**, because `db.json` models only bit 17 of a byte that is `0x54` in every occurrence.

### 2.8 `n4_cf_word` — underpowered, and the whole instruction, not just `b3`

The **full detection profile** — every modelled field complemented *and* zeroed — moved nothing on
three carriers with nested data-dependent divergence, reconvergence points and threadgroup barriers,
in the smoke calibration and in both gated runs, alongside 768 dense sweep cases of `b3` with zero
movement. Under the frozen gate an arm with no detection power is **barred from supporting a
verdict, inert or live**, so this is `untested`, not "inert". Either `04 01 00 XX` is a genuine
no-op marker or what it controls is invisible to a readback taken after command-buffer completion. A
successor needs a divergence observable, not a bigger sweep (`DEF-0172-4`).

### 2.9 A hypothesis refuted before it could contaminate the design

`db.json`'s prose lists `flag(bit8)` inside `imm_decode(b1, sign)`, so H1 was drafted as "`imm_flag`
is the LSB of a 4-bit mantissa" with an exact `dK = 2^(exp−11)/16` oracle. Reading
`tools/agx-isa/isadb.py` before building showed the implementation uses `m = (b1 >> 1) & 0x7` — a
**3-bit** mantissa — and **never reads `b1` bit 0**, while `imm_encode` hard-sets it. The drafted
oracle was unsatisfiable *by construction*: the same defect class as rule 3, one level up. H1 was
rewritten to an operand-**size**-bit hypothesis before anything was built, and recorded as an
amendment (`PRE_REGISTRATION.md` §9). **The rewritten hypothesis was then also refuted** — the bit
is inert. Both the prose model and my structural model are wrong; the field's role is UNKNOWN.

The side finding stands on its own: **our own encoder can only ever emit one of this field's two
legal values** (`DEF-0172-2`). An encoder that cannot reach a legal encoding is not an emitter for
that field, whatever a round trip says.

## 3. Declines — each with a named, and where possible *measured*, reason

| field | decline |
|---|---|
| `dev_scoreboard_fence.scope_flag` | **Measured.** The pre-freeze census tokenized all 24 carriers in both stages and found **zero** occurrences of `dev_scoreboard_fence`. There is no program here to splice it into. |
| `cubearray_coord_const.b3` | **Measured, and it reconfirms EXP-0148.** Zero occurrences across the same 24 carriers, matching EXP-0148's 0 firings in 1080 corpus files — its `f0 c0 04` signature sits interior to the 12-byte `tex_addr_setup` token. Its only exercise is a literal string in `roundtrip_test.py`, and a round trip is not an emitter gate. This is a descriptor-**existence** question for the orchestrator, not a sweep. |
| `half_alu_fma12.ext` | The instruction is flagged `emit_unsafe` in `db.json` for a length that over-consumes the following leader, and `ext` is precisely the 64-bit remainder that defect puts in doubt. Sweeping it would sweep the next instruction. |
| `mesh_out_src.sel` | `mesh_out_src` is mesh-stage-only and `harness/gfrun2.m` has no mesh pipeline. Authoring one is a harness project with its own pre-registration, not a field sweep. |
| `ret.scoreboard` | **Declined in advance, and the data confirms the decline rather than overturning it.** The byte does move the observation — but this harness reads back after command-buffer completion, which flushes, so movement proves general sensitivity, not ordering-specific power. Three prior experiments declined this family for the same reason. Pre-registering the decline is what stops a LIVE result being converted into a promotion after the fact. |

## 4. Threats to validity, and what was done about each

1. **A stale shared `db.json` on the device** (EXP-0169: 1036 fields vs the repo's, `falu2.srcA_class`
   / `srcB_class` replaced by `mod_lo`, reached by a `_find_isadb()` fall-through). This experiment
   pinned its own snapshot — 172 instructions / 1062 fields, sha256 in `CAPTURE_CONTRACT.json` —
   copied into its **own** device tool tree and resolved explicitly via `AGXRE_REPO`. The neo's
   shared `tools/` was neither read nor written. Every verdict row carries `start`/`width` re-read
   from that pin, and all 12 match the live repo `db.json`.
2. **Asynchronous `device_load`** (EXP-0169) — the only known contamination mode that can *fabricate*
   a positive against a diff-based oracle. Designed out: `k_fimm`, `k_srwide`, `k_srnarrow` seed from
   special registers through ALU only, and `k_texread`, `k_texmix`, `k_deriv` declare **no buffer at
   all** and derive everything from the interpolated `[[position]]`. `fimm2` keeps the load-sourced
   `mods == 0xC0` form knowingly. The ≥99 % cross-run gate is the detector everywhere else: an
   intermittently landing load cannot reproduce the same per-value partition twice, and all six LIVE
   fields reproduce at **100 %**.
3. **Rule 3, co-variance.** `run.py` splices only the instruction under test at a frozen absolute
   offset and observes fixed surfaces at probe points chosen before the run. No observed quantity is
   a function of the swept value. The EXP-0140 failure shape cannot occur here.
4. **Rule 4.** No verdict in this experiment cites a round trip, `rt_ok`, or tokenization.
5. **Concurrent siblings.** EXP-0171 swept throughout. All cross-run disagreement in the entire
   experiment — 5 values in `tex_deriv`, 4 in `imageblock_store` — was `fault` in one run and
   `foreign` (`InnocentVictim`) in the other, **at exactly the values that hang the device**. Per
   §7's own definition, `InnocentVictim` is "a sibling's reset, not a property of your encoding", and
   `PRE_REGISTRATION.md` §5.8 froze "InnocentVictim retried and segregated as `foreign`" before any
   run. Those values are therefore excluded from the comparison population and counted separately;
   **both agreement figures are reported on every row** (`cross_run_agreement` and
   `cross_run_agreement_raw_incl_foreign`). No promotion in this experiment depends on the
   difference between a `fault` and a `foreign` at a hang value.
6. **`run01` was stopped by hand** on its last arm (`ret@cfdiv`, tier 3, already declined) while it
   drowned in `InnocentVictim` retries. Every arm before it is complete; the partial `ret` sweep is
   retained as evidence and not reused. `run01`'s manifest was therefore never written, which is why
   `analysis/verdicts.py` recomputes everything from `raw/`.
7. **`run03`** re-ran a single frozen arm (`frame_marker_compact@rot/compute#0`) that my own
   hang-avoidance had excluded from `run02` even though it never hung. It was **declared in
   `PROGRESS.md` before its outcome was known**, and there was no prior failing pair for that arm —
   it had never been compared. This is stated plainly because "run a third time until it passes" is
   exactly the thing this project has withdrawn results for.
8. **Single-arm LIVE results.** `vary_slot.slot` and `frame_marker_compact.b1` are carried by one
   powered arm each. Both are promoted on a *structured*, exactly-reproduced partition (a single-bit
   rule for `vary_slot`), not on a movement count, and both rows say so. A reviewer who thinks one
   arm is not enough should downgrade those two; the other four are carried by 2–5 arms.

## 5. Hangs — the hardware facts, and the courtesy record

Genuine, majority-of-3-reproduced `ErrorHang`s. Each is a hardware fact about the encoding, not just
an obstacle:

| field | hang values | consequence |
|---|---|---|
| `frame_marker_compact.b1` | `3`, `7` | hang on `scache`/`srnarrow`/`vhalf`/`vsrc`, **not** on `rot`; stopped those sweeps at 8/256 |
| `tex_deriv.dstsrc` | `0x3FFFF`, `0x7FFFF` (all-ones) | stopped every arm at 39/65 sampled |
| `imageblock_store.src` | `246`, `247` | stopped both arms at 248/256 |

`MAX_HANGS_PER_FIELD = 2` stopped each field as §8 requires. **`frame_marker_compact.b1` hung twice
on the first carrier and I let it repeat on four more** — against the spirit of §8 even though the
per-arm limit held. That was corrected for `run02` by excluding the field, and recorded in
`PROGRESS.md` at 09:40 UTC, before any verdict existed. Sibling experiments seeing `InnocentVictim`
in the 09:33–09:58 UTC window should assume EXP-0172 as a likely cause.

## 6. Database defects reported (not applied — `db.json` is the orchestrator's file)

Full text with evidence pointers in `analysis/field_verdicts.json` → `db_defects`.

- **DEF-0172-1** — `irotate.b2` is modelled 8 bits wide but its own `match` leaves **one** bit free:
  2 legal values, not 256. Instance of DEF-0170-1.
- **DEF-0172-2** — `isadb.imm_encode` **cannot emit `falu2i.imm_flag = 0`**; `imm_decode` never reads
  the bit, while `db.json`'s prose says it is part of the immediate mantissa. Low severity for
  correctness (the bit is HW-proven inert), high for documentation.
- **DEF-0172-3** — `vary_slot.slot` is modelled 8 bits wide; exactly one bit is observable, and it is
  not the bit the compiler varies.
- **DEF-0172-4** — `n4_cf_word` has **no observable effect at all**, not merely `b3`.
- Reconfirmed: `simd_shuffle.cache` covers one bit of eight (EXP-0163); `cubearray_coord_const` fires
  zero times in 24 fresh carriers (EXP-0148).

## 7. Recommended next steps

1. **`imageblock_store.b4`** is now the single field between `imageblock_store` and emittable, and
   EXP-0163 read it INERT-ROBUST. It needs a *different dimension*, not a bigger sweep — the
   explicit multi-field `imageblock<T>` layouts that do not currently compile are the obvious one.
2. **`n4_cf_word`** needs a divergence observable (e.g. a lane-order-dependent threadgroup
   reduction whose result differs if reconvergence is wrong), not more values.
3. **`vary_slot.slot` jointly with `vary_store.out_slot`** — the two must be swept together before
   anyone documents how a varying slot is selected.
4. **`cubearray_coord_const`** — a descriptor-existence decision. While it stands it inflates the
   emitter-relevant denominator with an instruction nobody can emit or observe.
5. **`tex_sample.coord`'s mod-16 aliasing** deserves an adversarial check on another fragment
   program: if the period is a property of the *stage* rather than of this carrier's register
   allocation, it is a documentable hardware fact for the register file section.
