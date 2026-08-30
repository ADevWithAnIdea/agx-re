# EXP-0168 — RENDER arm design (vertex + fragment)

**Target: Apple A18 Pro / G17P.** Four fields, all withdrawn to `untested` by
EXP-0164's adversarial audit. This document is the pre-registration content for
the render half of EXP-0168; the compute half is the parent's.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected:      kernels/r_*.metal (ours) and the machine code the public
                       newLibraryWithSource: / MTLBinaryArchive API produced from
                       them; plus read-only analysis of our own committed raw
                       from EXP-0147 / EXP-0155 / EXP-0162 / EXP-0163
Apple binary introspection: NONE
Reproduction:          section 9
```

---

## 0. The four fields, and why each was withdrawn

| field | bits | stage | withheld as | prior evidence | why it was withdrawn |
|---|---|---|---|---|---|
| `vtx_out_pos.dst` | byte0 hi nibble, 4 | vertex | INERT-SINGLE | EXP-0147, M4, 16 values | **1 carrier**, 0 moved |
| `vtx_out_pos.slot` | byte+7, 8 | vertex | INERT-SINGLE | EXP-0147, M4, 256 values | **1 carrier**, 0 moved |
| `pixel_order.kind` | byte+1, 8 | fragment | UNVERIFIABLE `no-field-records` | EXP-0093 / EXP-0162 | **zero per-value records** attributable to the field |
| `frag_color_pack.dst` | byte+3, 8 | fragment | UNSTABLE | EXP-0155, G17P, 208 values | failed cross-run agreement; **"2 carriers" is one program** |

`vtx_out_pos.dst` and `.slot` are the **only** withheld fields on
`vtx_out_pos`, so landing both **recovers the whole instruction**. That is this
arm's highest-value target.

### The standard this design is built to

1. **A field withheld as "inert" almost always means the carrier could not
   express what the field controls.** The canonical proof is EXP-0163:
   `iter_at.loc` read inert on every EXP-0155 arm and moves 128/256 at
   `rasterSampleCount = 4`, because at one sample the centroid, the sample point
   and the pixel centre are the same point.
2. **Two carriers identical in the dimension the field controls are one
   carrier.** Carrier count proves nothing. Every carrier here declares a
   `carrier_dim` string naming that dimension, `rendercarriers.selftest()`
   refuses two carriers in a family that share one, and `render_verdicts.py`
   counts **distinct `carrier_dim` values** — never arms, never occurrences.
3. **Detection power is proven before anything is concluded**, per arm, with a
   ladder whose known-live control is cited.
4. **Only the field's own bits are varied**, and where a field is sub-byte the
   complementary bits are also swept as a byte-mate control.
5. **Every arm carries at least one case pre-registered to fail.**

---

## 1. `vtx_out_pos.slot` — the dimension is the number, identity and WIDTH of output slots

**What the field controls.** db.json: *"byte+7 = varying/output slot
(0x04/0x08/0x0c/0x10/0x14)"* — a stride-4 index selecting **which** output slot
the op targets. EXP-0147's carrier had **one** user varying (`VOutA {float4 pos
[[position]]; float4 va;}`), so there was nothing to select: the carrier was
blind by construction, and EXP-0147's own `RESULTS.md` §6 names
*"`vtx_out_pos.slot` in a multi-varying carrier"* as the open follow-up.

**Carriers, and how each differs in that dimension.**

| carrier | slots | how it differs | prio |
|---|---|---|---|
| `r_v1` | **1** float4 varying | **CONTROL** — reproduces EXP-0147's blind shape on purpose. If `slot` moves nothing here and something elsewhere, the prior null is a carrier limitation, not a don't-care. | 1 |
| `r_v8` | **8** scalar varyings, + vertex→device-buffer write | eight slots to select between, and a second **independent observation path** (§1b) | 1 |
| `r_vmix` | **5** varyings of **MIXED WIDTH** (`half`, `half2`, `float`, `float2`, `float4`) | **the discriminator**, §1c | 1 |
| `r_v4v` | **4** float4 varyings (16 components) across 4 RTs | vector slots instead of scalar slots, at a different count | 2 |
| `r_vsrc` | **8** scalars from a serial dependency chain | 8 simultaneously-live **distinct registers** (this is the `dst` dimension, §2) | 2 |
| `r_v8f` | **8** scalars, `[[flat]]`, **no** device write | different interpolation class, and the no-device-write control for §1b | 3 |

Six distinct dimensions, against the prior evidence's one.

**Values.** Each varying carries a **distinct power of two** (`r_v8`: 1,2,4,…,128;
`r_v4v`: 1…32768; `r_vmix`: 1…8192). Powers of two make the observation
*decodable*, not merely different: any subset-sum is unique, so a read-back
channel says exactly which slot(s) reached it — swapped, duplicated, merged or
lost — and `0.0` (lost) is distinguishable from every legal value. Values are
runtime-sourced from a uniform (so they cannot be constant-folded) and
**identical at all three vertices**, so the interpolated value is exact and
host-known at every covered pixel whatever the barycentric weights are (the
EXP-0162 `f_vary` trick). Every carrier draws a full-screen triangle, so all four
probe pixels are inside the primitive by construction.

### 1b. A vertex-stage observable that is DIRECT, not inferred

EXP-0163's `gfrun2.m` already binds the `--out-buf` device buffer to the vertex
stage (`setVertexBuffer:`) and **no carrier it built ever used it.** `r_v8`,
`r_v4v` and `r_vsrc` write their outputs to that buffer as well as emitting them
as varyings, so `vtx_out_pos` gets a **per-vertex** observable that never passes
through rasterization or interpolation, alongside the interpolated pixel:

* buffer → *"the vertex stage ran and computed value X for vertex n"*
* pixel → *"value X was routed to output slot k"*
* both poison → *"the program never ran"*

Those three are otherwise indistinguishable, which is exactly the failure mode
FIELD-SWEEP-PROTOCOL §7 exists for. **Two independent observation paths, both
kept.**

The buffer layout is 32 floats per vertex; only slots 0..15 (`r_v4v`: 0..23) are
ever written, so the remainder is a **tail poison region** — a dispatch that
reports OK and leaves the tail non-poison performed an out-of-bounds
vertex-stage write, recorded as `outbuf_tail_dirty` and reported as a
first-class finding.

> **Declared risk, and the reason `r_v1` / `r_v8f` exist.** A vertex function
> that both returns rasterized output and writes a device buffer draws a real
> Metal warning: `warning: writable resources in non-void vertex function`. It
> compiles and is legal, but it may change how the vertex stage is lowered — in
> the worst case removing `vtx_out_pos` entirely. `r_v1` and `r_v8f` have **no**
> device write, so if the writing carriers behave differently the write itself is
> identified as the confound rather than silently contaminating the result. If
> the census shows `vtx_out_pos` absent from the buffer-writing carriers, that is
> a first-class structural finding about the vertex output path, recorded, not a
> failed build.

### 1c. `r_vmix`, and the one thing no amount of extra carriers could settle

The corpus values 0x04/0x08/0x0c/0x10/0x14 fit **two** readings equally well:

* (a) `slot` is a **slot ordinal** scaled by 4, or
* (b) `slot` is a **byte offset** into the vertex output block.

For **uniform-width** varyings the two are indistinguishable — `ordinal × stride`
and `byte offset` agree up to a constant. Every other carrier here is
uniform-width (`r_v8`/`r_vsrc` = eight 4-byte scalars; `r_v4v` = four 16-byte
vectors). `r_vmix` makes the ordinal→offset map **non-linear** on purpose
(2, 4, 4, 8, 16 bytes), so a dense `slot` sweep there **discriminates** between
(a) and (b). Reporting the discrimination — either way, or that it is still
ambiguous — is a deliverable in its own right.

### 1d. Ladder, oracle, falsifier, coverage, byte-mate

**Liveness ladder.** `vtx_out_pos` declares exactly two fields and **both are
under test**, so there is no value-field control on the instruction itself. The
ladder is therefore layered, weakest-hazard first:

| ladder | control | citation that makes it known-live | hazard |
|---|---|---|---|
| `L_data` | **no splice at all** — re-run the byte-identical program with `@buf0` = the alt uniform | tautological: if changing the input does not move the observation, the observation path is dead | **none** |
| `L_vary_hint6` | `vary_store.hint6` (byte+6), 8 values `{0x00..0x03, 0x10..0x13}` | **EXP-0163 §4, G17P, HW-VALIDATED**: `hint6` **bit4 alone**, 2 classes × 128, on 7 arms across 5 carriers — bit4 set makes all four fragment output channels read 0.0. It is a VALUE field: EXP-0163's fault table attributes its 88 resets to `b5_tag` (18) and `hint1` (8) on this same instruction and **none to `hint6`**. Tried on up to 4 occurrences until one shows power, because EXP-0163 found `hint6` live on specific occurrences, not all. | low |
| `L_vary_slot` | `vary_store.out_slot` (byte+4), 8 values on the stride-4 grid `{0x00..0x1c}` | **the ROUTING-sensitivity control, and this design's own logic demands it.** `L_vary_hint6` proves the observation can see a varying being **killed**; it does not prove the observation can see one being **rerouted**, and those are different sensitivities. `out_slot` is the *other* instruction's slot selector, so if it moves the observation then this carrier **can** see slot routing — exactly the detection power `vtx_out_pos.slot` needs. Without it, an inert `slot` cannot be told apart from an observation blind to routing, which is the whole EXP-0163 lesson. Hazard `medium`: no prior sweep targeted this byte densely, but EXP-0163's detection profile spliced it twice per arm across ~9 `vary_store` arms with **no fault attributed to `out_slot`** in its fault table (which does list `b5_tag` at 18 and `hint1` at 8 on the same instruction), and EXP-0162 hung on `vary_store` byte+1, not byte+4. | medium |
| `L_self_b1` | `vtx_out_pos` byte+1 (a match constant), 8 values `0..7` | **no prior — ladder of last resort.** Run LAST, budget 2 hangs, then stopped and recorded. An inert verdict does **not** depend on it. | **high** |

Pass criterion: **≥ 2 distinct observed surface hashes** among cases that were
status-OK, `validity == "valid"`, accepted, **and still decode as the control's
own mnemonic**. That last clause is EXP-0163's own §7 defect fixed: its in-run
predicate required both statuses to be OK, so **a faulted control scored as a
live control**. Here the gate is enforced at measurement time *and* recomputed
independently from the raw by `analysis/render_verdicts.py`.

**Oracle — host-computed, and how it is derived.** `rendercarriers.py` computes,
in Python, from the MSL we wrote: every varying value, every render-target
channel, and every device-buffer slot including which slots must remain poison.
Every quantity is a dyadic rational chosen to be **exactly** representable in
binary32 (and binary16 for `r_vmix`'s half lanes), so the comparison is exact
rather than tolerant — `rendercarriers.selftest()` asserts the exactness,
including that no value collides with `0.0`, that all values within a carrier are
distinct, and that the ladder's alt values are disjoint from the baseline's. The
baseline of every arm is scored against that oracle and the result recorded as
`baseline_oracle_exact`; a mismatch bounds every claim from that arm and is
visible in the record.

**Falsifiers** (pre-registered to FAIL):

* `F_data_alt` — `@buf0` = alt uniform. Must **not** reproduce the baseline, and
  must match the alt oracle **exactly** on every surface including the
  vertex-stage device buffer.
* `F_hint6_kill` — `vary_store.hint6 |= 0x10`. Predicted signature: **all four
  fragment output channels 0.0** (EXP-0163 §4). If it instead reproduces the
  baseline, this carrier's fragment observation path is not live and every inert
  result on it is void.

Falsifiers resolve to three states — `held` / `partial` / `failed`. A prediction
that is directionally right but not exact is `partial`, never `held`; recording
it as a pass would launder a wrong prediction into a passed control.

**Coverage.** `dst` is 4 bits → **all 16** values. `slot` is 8 bits → **all 256**
values. Dense, per FIELD-SWEEP-PROTOCOL §3.

**Byte-mate.** `dst` occupies byte0 bits[4:8]; its complementary bits are byte0's
**low nibble**, which db.json pins to `0xb` as part of the instruction match. The
control is run — anchor `dst` held, low nibble swept over all 16 values — but it
is a **decode-boundary probe, not an ordinary byte-mate**: 15 of 16 values make
the bytes decode as something else, and movement there is *expected*. It does
**not** create attribution ambiguity for `dst`, because no value of `dst`
changes the mnemonic (the match constrains only bits[0:4]). Its purpose is to
show the byte is reached at all. It is the highest-hazard item in this plan, so
it runs on **one arm only** (`--bytemate-arms 1`) with a hard budget of 2 hangs.
`slot` is a whole byte: **no byte-mate applies**, and that is recorded explicitly
rather than omitted.

---

## 2. `vtx_out_pos.dst` — the dimension is which register feeds the output

`dst` is a 4-bit register selector. Whatever its exact role (destination, or the
source register whose value is emitted), the only dimension a register index can
control is **which register**. EXP-0138's `copysign.operands` is the lesson: it
read inert because its carrier had **two** live float registers, so a register
selector had nothing to select between.

`r_vsrc` is that lesson applied to the vertex stage: a serial dependency chain
`t0 = u.x; t(k+1) = t(k)*1.5 + u.y` forces **eight simultaneously live, mutually
distinct** values (1, 3.5, 7.25, 12.875, 21.3125, 33.96875, 52.953125,
81.4296875 — all dyadic, so exact whether or not the compiler contracts the
multiply-add into an FMA). `r_v8` sources its eight from four uniform lanes and
lets the compiler reuse a small register set; `r_v1` has essentially one. Three
genuinely different register-space pressures.

Being 4 bits, `dst` cannot address a register outside r0..r15, so it cannot
produce the out-of-range-register faults that dominated EXP-0163's reset count —
and EXP-0147 measured **0 faults and 0 hangs** across its 283 `vtx_out_pos`
cases. Ladder, oracle, falsifiers and byte-mate as §1d.

---

## 3. `pixel_order.kind` — the dimension is what an ordering failure LOOKS LIKE

`kind` selects acquire/wait (`0x14`) versus release/signal (`0x04`) — **which
half of an ordering bracket** an instruction is. A carrier can only speak to that
if ordering failure is *visible* in it, and different carriers must make it
visible *differently*.

**The ordering guarantee is the whole design.** `raster_order_group` orders
fragments covering **the same pixel**, by primitive order, and guarantees nothing
between fragments at different pixels. So the only deterministic carrier is a
**1×1** render target drawn **N times**: N primitives, N fragments, one pixel,
one ordered accumulator. A 16×16 target with one instance has 256 fragments at
256 different pixels and would measure noise. This is why `gfrun3.m` gains
`--instances` (§7).

| carrier | accumulation | what an ordering failure looks like | prio |
|---|---|---|---|
| `r_rog8` | `v += src`, **commutative** | a **lost-update count**. Blind to a pure permutation. Replicates EXP-0162's exact parameters. | 1 |
| `r_rogx` | `v = v*2 + src`, **NON-commutative, non-idempotent** | a **wrong value that names how many updates were applied** — `v_k = 2^k·R + (2^k−1)·src`, every k on its own value. Sensitive to reordering, not only to loss. | 2 |
| `r_rog2` | two groups: float `group(0)` and **uint** `group(1)`, group 1's increment derived from group 0's post-value | an **inconsistency between two resources of different type**. Also puts two independent `pixel_order` brackets with different scope in one program. | 3 |

**Oracle — closed form, host-computed.** With accumulator reset `R`, source
`src`, clear `C`, `N = 8`:

```
r_rog8   ordered:  texel = R + N·src            pixel = C + N·R + (N(N+1)/2)·src
         lost(k):  texel = R + k·src            pixel = C + N·(R + k·src)
r_rogx   ordered:  texel = 2^N·R + (2^N−1)·src  pixel = C + (2^(N+1)−2)·R + (2^(N+1)−2−N)·src
r_rog2   as r_rog8, plus texelU = Ureset + Σ uint(16·(R + i·src))
```

`R`, `src` and `C` are dyadic, so every prediction is exact in binary32;
`rendercarriers.selftest()` checks that `r_rog8`'s ordered numbers reproduce
EXP-0162's committed values (`tex = [0.5, 1, 2, 4]`, `pixel = [2.375, 4.75,
9.375, 18.5]`) and its `lost_7_of_8` values, and that `r_rogx`'s nine affine
steps are mutually distinct.

### 3b. This field gets a genuinely PREDICTIVE oracle, not an inert one

**Found while reading the prior raw, and it changes the plan.** EXP-0162
**already swept this exact byte** on G17P: `raw/g17p_20260829_run04__rog/`, 2048
sweep cases, `hangs: 0`, elapsed 11.4 s. Its records are keyed
`instr = acquire|release, field = byte1` — which is *why* EXP-0164 could find no
record attributable to `pixel_order.kind` — but `kind` **is** bits[8:16], i.e.
byte+1. Re-deriving that partition offline gives an exact rule, verified against
**all 256 recorded values on both members**:

```
bit1 set                    ->  ordering LOST (7 of the 8 updates)          128/256
bit1 clear and bit2 set:
    acquire member ALSO needs bit4 set  ->  ok                               32/256
    release member needs only bit2      ->  ok                               64/256
otherwise                   ->  wrong value                          96 / 64 /256
bits 0, 3, 5, 6, 7          ->  DON'T CARE   (bit4 too, on the release member)
```

So bit4 is the acquire/wait selector, bit2 must be set for the op to work at all,
and **bit1 set breaks ordering** on both members. This is pre-registered in
`renderarms.pixel_order_predict()` and every swept value is scored against it
(`predict` / `predict_held` per record). Consequences:

* `r_rog8` becomes a **direct cross-experiment replication**: a disagreement is a
  real result either way, not a re-measurement.
* `r_rogx` and `r_rog2` ask the actual open question — does the same rule hold
  when ordering failure looks different?
* the re-record closes EXP-0164's auditability gap **and** the field acquires a
  predictive oracle, which is stronger than the inert oracle the other three
  fields have.

**Ladder.**

| ladder | control | citation | hazard |
|---|---|---|---|
| `L_data` | `@buf0` = `src` alt | closed-form: texel and pixel are functions of `src` | none |
| `L_po_flags` | `pixel_order.flags` (byte+4), 8 values `0..7` | **EXP-0162, G17P, HW-VALIDATED, quantitative**: corrupting byte+4 loses exactly **7 of 8** updates (texel `8·src → 1·src`; pixel `C+36·src → C+8·src`). **EXP-0147** measured the full accepted set: acquire correct iff bit0=0 and `(v & 0x0e) != 0`; release iff `(v & 0x0f) >= 2`. A VALUE field. Also re-measures EXP-0147's M4 rule on G17P for free. | low |
| `L_po_scope` | `pixel_order.scope` (byte+3), 8 values all keeping bits 4 and 6 set | **EXP-0147**: acquire correct iff bit4=1 and bit6 XOR bit7=1; release iff bit4=1 and bit7=1. All eight chosen values satisfy EXP-0162's corrected match, so none is an opcode splice. | low |

**Falsifiers.** `F_data_alt` (as above), and `F_flags_01` — `flags = 0x01`,
predicted to produce **exactly** `lost_7_of_8`. Not "differs": a named number
from EXP-0162's proof. If ordering does not break there, the carrier cannot see
an ordering failure and its `pixel_order` results are void.

**Coverage.** 8 bits → **all 256** values, on **both** members (the acquire and
release occurrences) of each carrier. Note that sweeping `kind` on the acquire
occurrence includes `0x04`, turning it into a second release — a designed,
informative case that the model predicts as `wrong_value`.

**Byte-mate.** `kind` is a whole byte: **not applicable**, recorded as such.

---

## 4. `frag_color_pack.dst` — the dimension is which GPR feeds the tilebuffer store

**Why the prior evidence was one carrier.** EXP-0155's `fcp@pack0` and
`fcp@pack1` are two occurrences of the same instruction in one program — one
source file, `color_format = 80` (BGRA8Unorm), one render target, `samples = 1`.
Its liveness control was identical on both (`("val", 0x80)`), and `pack1` even
drops `fmt_class` from its field list. Counting that as two carriers is what
produced the UNSTABLE verdict.

| carrier | differs in | prio |
|---|---|---|
| `r_fcp1` | 1 RT, 8-bit unorm, **IMMEDIATE-source** packs (colours are MSL literals, foldable into `val`) — the EXP-0155 replica / **control** | 1 |
| `r_fcp4` | **4 RTs**, 8-bit unorm, **REGISTER-source** packs, **16 live colour values in 16 registers** | 1 |
| `r_fcph` | 1 RT, **RGBA16Float** — a different conversion class (no normalisation, two halves per word) | 2 |
| `r_fcpf` | 4 RTs, **RGBA32Float** — needs no conversion, so the pack **may not exist at all** | 2 |
| `r_fcp1s` | 1 RT, 8-bit unorm, **4× MSAA** tile path | 3 |

`r_fcp4` is the one that matters most: with sixteen distinct live colour values,
redirecting one pack's destination onto another pack's register produces a
**decodable cross-contamination** — the wrong channel shows a value that names
the register it actually came from. With one render target there are two packs
and few live colour registers, so most redirections land somewhere
indistinguishable, which is the likely cause of the unstable 32-of-208.

The immediate-vs-register split is not incidental: db.json documents
`src_present_mask` = `0xd0` (register source) vs `0x50` (immediate source), so the
`r_fcp1`/`r_fcp4` pair spans a distinction the descriptor itself names.
`r_fcp4`/`r_fcpf` and `r_fcp1`/`r_fcp1s` are **controlled pairs** sharing one MSL
file and differing in exactly one pipeline parameter — with EXP-0163's
correction honoured explicitly: Metal lowers a multisampled fragment build
differently, so these are controlled comparisons of the same source under one
changed parameter, **not** byte-for-byte splice pairs.

**Oracle.** BGRA8Unorm colours are supplied as `k/255` for sixteen distinct `k`
(15, 31, …, 255), so each read-back byte equals its own `k` exactly and names its
channel; the read-back order is B,G,R,A and the oracle permutes accordingly.
`rendercarriers.selftest()` asserts every value is ≥ 0.4 of a code away from a
`.5` rounding tie, so **no oracle here depends on a tie rule we have not
established**. `r_fcph`'s four values are exact in binary16 (asserted by
round-trip). `r_fcp1`'s literals 0.2/0.4/0.6/0.8 land on 51/102/153/204.

**Ladder** (all VALUE fields, all on the same instruction):

| ladder | control | citation | hazard |
|---|---|---|---|
| `L_fcp_mode` | `mode` (byte+4), `0..7` | **EXP-0155**: correct iff `mod 4 ∈ {2,3}` — so 0,1,4,5 break and 2,3,6,7 hold. A documented 50 % break rate; the most reliable control on this instruction. | low |
| `L_fcp_val` | `val` (byte+6), 8 values | **HW-VALIDATED, EXP-0008/0029**: splicing byte+6 `0x80 → 0x40` moved read-back green 0.502 → 0.251. Live only for immediate-source packs, so it may legitimately fail on the register-source carriers — which is why it is not the only ladder. | low |
| `L_fcp_mask` | `src_present_mask` (byte+7), 8 values, **0xff excluded** | **HW-VALIDATED, EXP-M4-14**: per-component source-present bitmask (0x10 = comp0, 0x40 = comp1, 0xd0/0x50 = both). | low |
| `L_data` | `@buf0` alt colours | codes disjoint from the baseline by construction. **Unavailable on `r_fcp1`/`r_fcp1s`** (literals) — recorded as `skipped`, never silently omitted. | none |

**Falsifiers.** `F_data_alt`; `F_mode_00` (`mode = 0x00`, predicted **not** to
reproduce the baseline); and `F_mask_ff` (`src_present_mask = 0xff`, predicted to
produce a **contained** command-buffer fault — EXP-M4-14 documents it as an
illegal encoding that hard-faults with the device surviving). `F_mask_ff` doubles
as a cross-target check of an A18 result on G17P.

**Coverage — and a coverage gap nobody recorded.** Extracted offline from
EXP-0155's raw before anything ran here:

> `frag_color_pack.dst` = **192 and 193 fault reproducibly** — 4 of 4
> observations across two gated runs and two occurrences. EXP-0155's per-field
> stop rule fired on those two, so **both runs stopped at value 194**
> (`n=194, max=193` on three of four (arm, run) pairs; 208 on the fourth).
> **Values 194..255 of this field have therefore never been dispatched, on any
> target.** That is exactly the "208 values dispatched" in EXP-0164's withheld
> row.

Two design consequences, both deliberate:

1. **This experiment's stop rule counts only genuine HANGS** — status `HANG`, or
   an `ErrorHang` OS class, confirmed by majority-of-3 — **never contained
   faults.** A contained command-buffer fault is a *result*; it does not reset the
   device and must not truncate coverage. So this run covers 194..255 for the
   first time.
2. **Known-risky values are swept LAST** within their field
   (`renderarms.coverage_for(width, defer=…)`, with `KNOWN_FAULT_VALUES` pinning
   {192, 193} and the citation), so if one does turn out to reset the device the
   rest of the coverage is already banked.

**Byte-mate.** `dst` is a whole byte: **not applicable**, recorded as such.

---

## 5. Validity — the rule, and why it is not optional

Per case, `validity ∈ {valid, invalid_poison, invalid_sentinel, invalid_victim}`:

* `invalid_victim` — `InnocentVictim` / `IgnoredPriorErrors` OS class, or a
  foreign-fault cascade;
* `invalid_sentinel` — the harness's re-read-and-`memcmp` of every spliced window
  failed, so the bytes we chose are not provably the bytes the GPU ran;
* `invalid_poison` — status OK but **every** surface is still `0xDEADBEEF`, or no
  surface at all;
* `valid` — everything else. **A fault or a hang IS valid** (it is a real
  observation of a fault); what is never valid is an observation that cannot be
  attributed to our encoding.

A non-valid case is **re-run** (up to 4 retries), and every attempt is retained
append-only with `accepted: false`. **No non-valid case is ever recorded as an
inert or silent observation.** This is enforced in the driver and re-asserted by
the offline test: EXP-0160 saw 25 dispatches report `STATUS OK` and write nothing
at all with no victim string; against a zero-initialised buffer those become 25
confident false nulls.

Additional integrity surfaces recorded per case: `rt_ok` (every expected render
target present and read back), `outbuf_tail_dirty` (an out-of-bounds vertex-stage
write), `probe_pixels_disagree` (a full-screen triangle with vertex-equal
varyings whose probe pixels differ — i.e. a position-dependent value), and the
`OVR <idx> applied|skipped` acknowledgement, so a data-ladder case can never be
scored as inert because its uniform silently did not change.

---

## 6. Hazard, hang budget, and the expected device-reset count

A GPU hang is a **device-level reset** that discards every other context's
in-flight command buffers. EXP-0163 produced **88 in 50 s (≈1.7/second)** and
attributes essentially all of them to its detection profile splicing the
**bitwise complement of opcode and register-number bytes** — `iter_at.grp`/`.dst`,
`vary_store.b5_tag`/`.hint1`, `simd_shuffle.dst`, `frag_color_store.src`. **None
of those bytes is spliced anywhere in this design.** Every ladder here except one
is a documented VALUE field, and the one exception is budgeted and run last.

**Budgets (hard stops, not warnings).** 2 hangs per (arm, field) → that field
stops and is recorded PARTIAL; 6 per arm → that arm stops; **24 total → the run
stops** and records PARTIAL. Sleep 2 s / 4 s / 8 s after the 1st / 2nd / 3rd+
confirmed hang. Never conclude `fault` from one observation: majority-of-3.

**Expected device resets, with the basis for each number:**

| source | cases | basis | expected resets |
|---|---|---|---|
| `pixel_order.kind` dense sweep | ~1 536 | **EXP-0162 swept this exact byte on G17P** (512 cases) plus bytes 3/4/5 (1 536 more): `hangs: 0` | **0** (bound 2) |
| `pixel_order` ladders (byte+3, byte+4) | ~100 | same run, 0 hangs over all 512 values of each | **0** |
| `vtx_out_pos.dst` + `.slot` dense sweeps | ~3 000 | **EXP-0147**: 283 `vtx_out_pos` cases, **0 faults, 0 hangs**. `dst` is 4 bits and cannot address past r15. Cross-target (M4→G17P) assumption, stated. | **0–4** |
| `frag_color_pack.dst` dense sweeps | ~2 560 | **EXP-0155 on G17P**: 192/193 fault reproducibly but as *contained* faults; ~20 contained faults expected, which are **not** resets | **0–2** |
| `F_mask_ff` falsifier (0xff) | 5 | **EXP-M4-14**: documented contained fault, device survived | **0** (≈5 contained faults) |
| byte-mate, byte0 low nibble, **1 arm** | 16 | no prior; decode-changing splice in the vertex stream, which EXP-0162 measured hanging (`vary_slot_00 byte+1`). Budget 2. | **0–2** |
| `L_vary_slot` (`vary_store.out_slot`, hazard=medium) | ~8/arm | ~18 splices of this byte inside EXP-0163's detection profile with 0 faults attributed to it; values on the corpus stride-4 grid | **0–2** |
| `L_self_b1` (`vtx_out_pos` byte+1, hazard=high) | ~8/arm | no prior; run last, budget 2 | **0–2** |

> **Expected: 2 device resets. Realistic ceiling: 14. Hard ceiling: 24**, at which
> the run stops itself. Against EXP-0163's 88 — roughly a 40× reduction, bought
> by choosing value-field ladders over complement-of-register splices.
>
> **Also expected and NOT resets: ~25 contained command-buffer faults**
> (`CMDBUF_ERROR`), which cost no sibling agent's work.
>
> **Courtesy note (FIELD-SWEEP-PROTOCOL §7):** the deliberately risky regions are
> `frag_color_pack.dst ∈ {192, 193}` (swept last), `frag_color_pack.src_present_mask = 0xff`
> (once per carrier, expected contained), and the two vertex-stream
> decode-boundary controls (`--bytemate-arms 1`, `L_self_b1`). Run
> `--skip-hazard --no-bytemate` to drop the last group entirely; the four fields'
> verdicts do not depend on it.

**Scale.** ~28 arms, **~8 100 cases** in the offline dry run (12 `vtx_out_pos`,
10 `frag_color_pack`, 6 `pixel_order`; the real occurrence counts come from the
census). For reference EXP-0162 did 2 048 render cases in 11.4 s and EXP-0163 did
39 233 in 50.3 s, so the expected GPU time is minutes, not tens of minutes. The
larger cost is building the 14 archives twice (census + run) -- 14 carriers
over 12 MSL files, since two files each serve a controlled pair differing only
in a pipeline parameter.

---

## 7. What changed in the harness, and what did not

`harness/gfrun3.m` is `EXP-0163/harness/gfrun2.m` **verbatim plus exactly four
additions**, each required by a carrier here and by nothing else. Everything
gfrun2.m had is preserved: `--samples`, `--resolve`, MRT, `--rt-array`, depth,
occlusion, the five writable-texture kinds, `--out-buf`, `--buf-u32`,
absolute-offset splicing for the vertex/fragment/compute stages, the `0xDEADBEEF`
read-back poison, the re-read-and-`memcmp` integrity sentinel,
`MTLPipelineOptionFailOnBinaryArchiveMiss`, the per-request fresh `MTLLibrary`
and fresh scratch archive path, the ERRDOM fault-class print, the per-request
watchdog and the child restart. The exact transformation from the parent file is
kept as `work/render_build/patch_gfrun3.py`, so the fork is auditable rather than
a hand retype.

1. **`--instances N`** → `drawPrimitives:...instanceCount:`. **Not optional**:
   `raster_order_group` only orders fragments at the same pixel, so the only
   deterministic ordered carrier is a 1×1 target drawn N times (§3). `gfrun2.m`
   could not express it, which is the sole reason it needed changing at all for
   the `pixel_order` arm.
2. **`--texw-reset` / `--texwu-reset`** → the per-request reset value of the
   RGBA32Float writable texture at `[[texture(1)]]` and the RGBA32Uint one at
   `[[texture(9)]]`. The ordered-RMW carriers accumulate *into* those, so their
   starting value is an experiment parameter that fixes the oracle and keeps
   "wrote nothing" distinguishable from "wrote zero". Defaults reproduce
   gfrun2.m's hard-coded values, so an unparameterized run is byte-identical.
   (The half texture's reset now tracks `--texw-reset` through an IEEE
   round-to-nearest-even `f32→f16` we wrote; with the default it produces
   gfrun2.m's exact `0xBC00/0xC000/0xC200/0xC400`.)
3. **Per-request overrides** `@inst=<n>` and `@buf<idx>=<hexbytes>`, appended to
   the existing request grammar (a request with no `@` token behaves exactly as
   an EXP-0163 request). This buys the **zero-hazard DATA LADDER**, which matters
   precisely because EXP-0163's resets came from control *splices*. Unknown or
   unbound indices report `OVR <idx> skipped` rather than being silently ignored.
4. **`TARGET <name> registryID=… instances=…`** at startup, so a capture records
   the target read from the **live device** and never from a literal in a harness
   (EXP-0138 hard-coded its host string; this does not repeat that).

`harness/runner3.py` forks `EXP-0163/harness/runner2.py`, preserving the
watchdog, the dead-child EOF fix (EXP-0153), the `InnocentVictim` retry policy
and every surface tag; it adds the three new command-line options, the
per-request override plumbing with its acknowledgements, tolerance for the
`TARGET` line, and `restarts_at` (EXP-0163's manifest reported only a count, and
a restart is exactly the event that separates two observations that ought to be
comparable).

`gfrun3.m` and every `kernels/r_*.metal` were compiled offline as a syntax check
(`clang -fsyntax-only`, `xcrun metal -c`) — **no GPU work, no dispatch.** The
whole census → freeze → run → verdict pipeline was exercised offline against a
mocked device (`work/render_build/mocktest.py`) which asserts the record schema,
the role vocabulary, the validity vocabulary, and the rule that a non-valid case
is never accepted as an inert observation.

**Record schema.** One JSON object per case appended to
`raw/<run_id>/sweep.jsonl`, flushed **and `fsync`ed** immediately — never
buffered, on the assumption the run is killed mid-flight. EXP-0163's keys are
kept (`observed{status,sentinel,hh,probe,missing,poison}`, `outcome`, `os_class`)
and extended with `role ∈ {sweep, ladder, bytemate, falsifier, baseline}`, `arm`,
`carrier_dim`, `byte_index`, `fstart`, `fwidth`, `validity`, `rt_ok`, plus
`oracle`, `predict`, `predict_held`, `attempt`, `accepted`, `hazard`, `confirm`,
`target`, `run_id`, `ts`. The full instruction `bytes` are on every record, so
attribution never depends on a db.json label string — EXP-0144 showed those can
move out from under committed raw when a later experiment edits the descriptor.

**Arms are discovered by census, not hand-listed**, because this experiment
cannot compile MSL without the device and so cannot know how many occurrences of
each instruction the compiler emits. What is frozen before the run is the
selection rule (`renderarms.py`), the census it selected from
(`work/render_census_<id>.json`) and the frozen arm table
(`work/render_frozen_arms.json`, sha256-pinned into each run's
`00_inputs.json`); at run time any arm whose located bytes or offset differ from
the frozen census is **REFUSED, never swept at a new address** — EXP-0163's
integrity check, which caught three arms resolving to the wrong offset before a
single value was swept.

---

## 8. STILL-UNDERPOWERED: what this design cannot reach, and the carrier it would need

Reporting this honestly is worth more than a weak promotion.

| not reachable here | why | carrier that would be needed |
|---|---|---|
| `vtx_out_pos.slot` over **system** output slots — `[[point_size]]`, `[[clip_distance]]`, `[[render_target_array_index]]`, `[[viewport_array_index]]` | every carrier here emits `[[position]]` + user varyings only. If `slot` indexes a table that includes system outputs, those slot values are outside every carrier's reach. | a vertex stage emitting point size, clip distance and a render-target array index together, with a layered attachment. `gfrun3.m` **already has `--rt-array`**, so this is cheap — one more kernel. |
| `vtx_out_pos` in a **mesh** or **tessellation** pipeline | the harness builds only `MTLRenderPipelineDescriptor` with a vertex+fragment pair. | a mesh-pipeline harness (`MTLMeshRenderPipelineDescriptor`). EXP-0163 flagged the same gap for `mesh_out_src.sel`. |
| `vtx_out_pos.dst` above r15 | the field is 4 bits; r16+ is not encodable in it. | nothing — this is a property of the field, not a gap. Recorded so it is not mistaken for one. |
| `frag_color_pack` with `fmt_class = 0x56` (**compute pack**) | db.json documents byte+2 = 0x56 as the compute variant, and **no render carrier can emit it**. | a COMPUTE kernel that packs to a texture write or an imageblock — that is the **parent's compute arm**, flagged for it. |
| `frag_color_pack.dst` on **sRGB (81)**, **R8Unorm (10)** and packed (RGB10A2, RG11B10) attachments | three conversion classes are covered (80 / 115 / 125); these are further distinct ones. | more `color_format` values in `rendercarriers.CARRIERS` — cheap, purely additive, no new MSL. |
| `frag_color_pack` under **dual-source / extended blend** | not expressible through the current pipeline descriptor path. | blend-state support in the harness. |
| `pixel_order` on a **buffer-tagged** `raster_order_group` | EXP-0147 records that a buffer-tagged group "uses a different mechanism" and may not emit `pixel_order` at all. | a carrier with `device` buffer + `raster_order_group`, plus a census to check whether the instruction appears. |
| `pixel_order` on a **tile / imageblock compute** shader (`dispatchThreadsPerTile`) | the harness does not build tile pipelines. EXP-0163 named the same gap for `frag_tile_setup.sel`. | a tile-compute harness. |
| `pixel_order` at **rasterSampleCount > 1** | the rog carriers are 1×1, `samples = 1`; a multisampled 1×1 target cannot be read back without a resolve, which averages the per-sample values the experiment would be trying to tell apart. | an ordered carrier whose accumulator is a writable texture (readable without resolve) at `samples = 4`, with a per-sample fragment. Possible with `gfrun3.m` as it stands; not attempted here to keep the arm bounded. |

Also stated as bounds rather than results: the ladder for the `vtx_out_pos` arms
is a **program** ladder, not a same-instruction one (the instruction has no third
field), so it demonstrates that the observation path can see a vertex-side change
— `L_vary_hint6` a kill, `L_vary_slot` a reroute — not that the specific bytes of
`vtx_out_pos` are reachable. `L_self_b1` is the only same-instruction control and
it is hazardous by nature. Any inert
verdict on `vtx_out_pos` must be read with that caveat, and
`render_verdicts.py` records which ladder actually passed per arm.

---

## 9. Reproduction

On the G17P (`users-MacBook-Neo.local`), with the repo tree at `~/agxre/EXP-0168/`
mirroring `harness/ kernels/ analysis/ work/ raw/` and `AGXRE_REPO` pointing at
the pinned per-experiment tools copy (`$AGXRE_REPO/tools/{agx-isa,shdump}`):

```sh
cd ~/agxre/EXP-0168
export AGXRE_REPO=$HOME/agxre/EXP-0168

# 1. build the harness (full Xcode is present on the neo)
clang -fobjc-arc -framework Metal -framework Foundation -O2 \
      -o work/gfrun3 harness/gfrun3.m

# 2. the oracles and the arm spec must self-test clean BEFORE any dispatch
python3 harness/rendercarriers.py     # -> rendercarriers selftest: PASS
python3 harness/renderarms.py         # -> renderarms selftest: PASS

# 3. census (calibration; writes work/, NOT evidence) -- READ THE OUTPUT
python3 harness/renderrun.py --mode census --run-id c01

# 4. freeze the arm table from that census
python3 harness/renderrun.py --mode freeze --census work/render_census_c01.json

# 5. capture. Two gated runs; cross-run agreement is the promotion gate.
python3 harness/renderrun.py --mode run --run-id g17p_20260830_run01 --deadline-s 1200
python3 harness/renderrun.py --mode run --run-id g17p_20260830_run02 --deadline-s 1200
```

Useful restrictions, all recorded in the manifest when used:

```sh
--priority 1                 # the must-run carrier set only
--carriers r_rog8,r_v8       # a single carrier or two
--mnem pixel_order           # one target instruction
--fields slot                # one field
--skip-hazard --no-bytemate  # drop every hazard=high control
--smoke                      # write to work/ instead of raw/ (calibration)
--cross-family               # also sweep a target on carriers that declare no
                             # dimension for it; such arms are labelled
                             # `secondary:` and never count toward the bar
```

Pull `raw/<run-id>/` back into the repo, then on the repo host:

```sh
python3 analysis/render_verdicts.py raw/g17p_20260830_run01 raw/g17p_20260830_run02
```

which recomputes the detection gate from the raw (it does **not** trust the
in-run summary), derives the exact bit rule per (arm, field), scores
`pixel_order.kind` against the pre-registered EXP-0162 partition, computes
cross-run per-value agreement, and writes `analysis/render_verdicts.json`.

**Verdict rules, so they cannot drift:**

```
eligible arm       = baseline OK, ladder PASSED the strict gate, >=1 falsifier
                     HELD, carrier_dim not `secondary:`
LIVE               = >=1 eligible arm moved, in every run that ran it
                     (complete coverage NOT required -- movement is self-proving)
INERT-ROBUST       = 0 movement on >=3 DISTINCT carrier_dim values, each with
                     COMPLETE dense coverage
STILL-UNDERPOWERED = 0 movement, too few distinct dimensions
LADDER-FAILED      = no arm demonstrated detection power
UNSTABLE           = cross-run per-value agreement below 99%
```

Labels use only the eight from `docs/evidence-classification.md`: LIVE →
`hardware-run`; INERT-ROBUST → `single-template-inference` (a negative result must
never inflate the emittable count — EXP-0163's reasoning, adopted); the rest →
`untested`.

## 10. Clean-room statement

Every byte spliced or inspected is the compiled form of MSL in `kernels/r_*.metal`,
which we wrote. The splice-and-reload technique uses only public Metal API
(`newLibraryWithURL:`, `MTLBinaryArchive`,
`MTLPipelineOptionFailOnBinaryArchiveMiss`). The prior-work numbers cited above
come from this repository's own append-only raw captures and from `db.json`, which
is our own. **No Apple binary was disassembled, decompiled, symbol-dumped,
strings-scanned or otherwise introspected.**
