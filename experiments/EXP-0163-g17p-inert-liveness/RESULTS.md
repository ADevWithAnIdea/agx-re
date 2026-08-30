# EXP-0163 — RESULTS

**Target: Apple A18 Pro / G17P** (`applegpu_g17p`, `AGXAcceleratorG17P`, 5 GPU
cores, macOS 26.6, Metal family Apple9). Every result below is
**`target: G17P`, direct evidence**, not `INFERRED`.

```
Clean-room provenance: OWN-SHADER + HW-PROBE
Inputs inspected: kernels/*.metal (ours) and the machine code the public
                  newLibraryWithSource: / MTLBinaryArchive API produced from them
Apple binary introspection: NONE
Reproduction:  see README.md sec.0
Evidence:      raw/g17p_20260830_run01/sweep.jsonl (+ run02),
               raw/prefreeze/census_run{1,2,3}.json (calibration only)
```

> **STATUS: PROVISIONAL — one gated run.** `run01` is complete and analysed.
> `run02`, the pre-registered confirmation run, is deferred behind a coordinated
> quiet window for `EXP-0167` and every verdict here is subject to cross-run
> agreement. Sections marked **[1-RUN]** will be re-derived, not rewritten:
> `analysis/verdicts.py`, `analysis/rules.py`, `analysis/emit_verdicts.py` and
> `analysis/report.py` regenerate everything from the raw.

---

## 1. The question, and the answer

`EXP-0155` swept 109 fields over two gated runs; **22 moved nothing, on any
carrier, in either run.** This experiment asked whether any of them is genuinely
a don't-care, or whether "inert" only meant the carrier never exercised it.

**The answer is that the don't-care reading does not survive contact with better
carriers.** Of the 20 db.json fields on the list **[1-RUN]**:

| bucket | count | fields |
|---|---|---|
| **LIVE** — a carrier was found where the field moves an observable | **7** | `iter_at.loc`, `vary_store.hint6`, `tex_coord_setup.b5` `.b6` `.b8` `.idx`, `simd_shuffle.rsv9` |
| **INERT-ROBUST** — inert across ≥3 structurally different carriers that each passed the strict detection profile | **11** | `frag_color_store.store_mode`, `frag_tile_setup.access` `.sel` `.b5`, `imageblock_store.b4`, `iter.b9`, `simd_ballot.cache`, `simd_shuffle.cache`, `tex_coord_setup.b9`, `vary_store.hint2` `.b7` |
| **STILL-UNDERPOWERED** — could not be reached to the pre-registered bar | **2** | `tex_write.amode`, `tex_write.rsv11` |

**Labels, and why the eleven negatives are deliberately labelled weaker than
their evidence.** LIVE → `hardware-run`; STILL-UNDERPOWERED → `untested`;
**INERT-ROBUST → `single-template-inference`, not `hardware-run`.** The eleven
rest on a full dense hardware sweep, so by observation strength they are
`HW-VALIDATED` — but `hardware-run` is one of the two labels
`validate_labels.py` counts as **emitter-grade**, and emitter-grade asserts that
an implementer may *choose* the value. Our own `emitter_guidance` for these
eleven says the opposite: *emit the compiler-observed value*, which is a
dependency on a captured template and is what Definition-of-Done rule 1 forbids.
A negative result must not be able to inflate the emittable count.
`single-template-inference` states the emitter's real position — we know the
value that works because the compiler used it, we have hardware evidence the
field is inert across a stated envelope, and we cannot say what it controls.
**The measurement is not downgraded, only the claim about what an emitter may do
with it**: the full strength of each negative is carried in `note`, `range`,
`inert_arms.proven_live_controls` and the `hardware_evidence` block of
`analysis/field_verdicts_flat.json`.

A separate, first-class finding fell out of the pre-freeze census rather than
the sweep: **`db.json` does not decode a fragment colour-store variant
(`byte+1 == 0x86`) and mis-reads it as a 14-byte compute `device_store`**, which
silently omits that form from every occurrence census ever run on the
descriptor. Full example, argument and a proposed match fix in **§4b**.

Seven of twenty is not a rounding error, and the seven were not found by luck:
each was found by asking what the field would have to be *doing* for the program
to notice, and then writing that program. The clearest case is a controlled
experiment, not a search — see §2.

**None of the seven is a small effect.** `vary_store.hint6` bit 4 zeroes the
entire fragment output. `tex_coord_setup.b6` bits 2–5 must all be clear or the
addressed varying is lost. `simd_shuffle.rsv9`, a byte db.json names "reserved",
turns out to be an operand of the rotate/fill form that changes the result
value. These are not don't-cares that happened to twitch.

## 2. The controlled test: `iter_at.loc`

This is the experiment's cleanest result and it was pre-registered as H2.

`kernels/k_cent.metal` is built **twice**, as carrier `cent1` and carrier
`cent4`. Same MSL, same bound resources, same probe pixels; **the only thing
changed is `rasterSampleCount`, 1 versus 4.**

**Precisely what is and is not identical, since it matters.** An earlier draft
of this section said "same MSL, same compiled bytes"; that was an overclaim and
is corrected here.

| stage | `cent1` (1 sample) | `cent4` (4 samples) | identical? |
|---|---|---|---|
| vertex | 166 B, `sha256 9f5c0d0cc9e216a2678f58f8…` | 166 B, `sha256 9f5c0d0cc9e216a2678f58f8…` | **yes, byte-for-byte** |
| fragment | 174 B, `sha256 28c22e96eb7bf0eb44d4f227…` | 482 B, `sha256 a4bbec1f7f1c85ccda1bc63e…` | **no** |

Metal lowers the multisampled fragment build differently — 174 bytes at one
sample, 482 at four — so this is a **controlled comparison of the same source
and the same instruction under one changed pipeline parameter, not a
byte-for-byte splice pair.** A reviewer should read it that way.

What *is* held constant is the thing the claim rests on: the `iter_at` opcodes
match in shape and carry the same two `loc` values on both sides. `cent1` has
`af 14 54 0a 03 00 0a 01` (`loc = 1`) and `af 04 54 08 03 04 0a 03` (`loc = 3`);
`cent4` has `af 14 54 08 03 08 0a 01` (`loc = 1`) plus three `loc = 3` siblings.
Both values the compiler itself chooses are present on each side, so the
comparison is not between a program that uses the field and one that does not.

| arm | sample count | values that moved the observation |
|---|---|---|
| `iter_at@cent1/fragment#0` | 1 | **0 / 256** |
| `iter_at@cent1/fragment#1` | 1 | **0 / 256** |
| `iter_at@cent4/fragment#0` | 4 | **128 / 256** |
| `iter_at@cent4/fragment#1` | 4 | **128 / 256** |
| `iter_at@cent4/fragment#2` | 4 | **128 / 256** |
| `iter_at@ms4cent/fragment#0` | 4 | 128 / 256 |
| `iter_at@ms4out/fragment#0` | 4 | 128 / 256 |
| `iter_at@atoff4/fragment#0` | 4 (pull model) | 128 / 256 |
| `iter_at@atoff4/fragment#1` | 4 (pull model) | 128 / 256 |
| `iter_at@atoff1/fragment#0` | 1 (pull model) | 0 / 256 |

EXP-0155 swept this field on `c_cent1` only — a **1-sample** build. At one
sample the centroid, the sample point and the pixel centre are *the same point*,
so no location selector can move anything. The field was structurally
unreachable, not inert.

**The rule, exactly.** Two equivalence classes of exactly 128 values each, and
the partition is `bit1`:

```
iter_at.loc bit1 = 0  ->  centroid
iter_at.loc bit1 = 1  ->  per-sample
bit0 and bits 2..7    ->  don't-care (0x81 behaves exactly as 0x01,
                                      0x83 exactly as 0x03)
```

Read back at probe pixel (8,8) of the 4-sample resolved `cent4` arm, channel 0
(a `centroid_perspective` varying) is `3249.99976` for `loc & 2 == 0` and
`3312.49976` for `loc & 2 != 0`, with the other channels untouched.

This **refines** db.json's enum `{1: "centroid", 3: "sample"}`: the enum lists
two legal values, the hardware has one selector bit and seven free bits. That is
strictly more useful to an emitter, which now knows what it may leave alone.

## 3. What made the difference, field by field

Each row is the structural gap in EXP-0155's carrier set, and the carrier that
closed it.

| field | what EXP-0155's carrier could not do | the carrier that moved it |
|---|---|---|
| `iter_at.loc` | swept only at `rasterSampleCount == 1` | `cent4` — the identical program at 4 samples |
| `tex_coord_setup.idx` `.b8` | one occurrence, on the byte+4 == `0x00` float-modifier form | `vsrc` / `vhalf` / `ms4out` — the byte+4 == `0x42` vertex attribute / varying-destination-address form, which db.json's own note says is where `idx` carries `dst<<2` |
| `tex_coord_setup.b5` `.b6` | as above | live on **both** forms once a second form existed to compare against |
| `vary_store.hint6` | four 32-bit scalar varyings, one data source, slots 0–7 | `vmany` (16 varyings, slots past 7), `vhalf` (half/vector), `vflat` (flat int / no-perspective), `vsrc` (memory / immediate / computed sources) |
| `simd_shuffle.rsv9` | two arms, both plain 32-bit `uint` shuffles | `stype` — the `mode == 0x06` rotate / shuffle-and-fill form, whose `rsv9` the census already showed carrying `0xa1` / `0x91` rather than `0` |

The census alone (`raw/prefreeze/census_run3.json`, calibration) already showed
the premise was right before a single value was swept: across the new carriers
`vary_store.hint2` takes **0x54 / 0x55 / 0x56** where EXP-0155's single carrier
had one value; `hint6` takes 0x48–0x4d; `tex_write.amode` takes 0x55 as well as
0x54; `tex_coord_setup` appears in **three** distinct `form` values with `idx` up
to 0x94; `frag_tile_setup.sel` takes eight distinct values. **The compiler was
already using encoding space EXP-0155's carrier set never showed it using.**

## 4. Semantics established

Written only where the observation supports them; the machine-readable form with
per-arm counts is `analysis/field_verdicts_flat.json`.

| field | rule | effect |
|---|---|---|
| `iter_at.loc` | **bit1 alone**, 2 classes × 128 | 0 = centroid, 1 = per-sample. Bits 0, 2–7 free. |
| `vary_store.hint6` | **bit4 alone**, 2 classes × 128, on 7 arms / 5 carriers | bit4 set → **all four fragment output channels read back 0.0**: the whole varying block is lost, not just this component. The compiler-chosen 0x48–0x4d all have it clear. |
| `tex_coord_setup.b6` | **bits 2,3,4,5**; exactly the 16 values with `(v & 0x3c) == 0` reproduce the baseline | any of those bits set → the addressed varying reads 0.0 |
| `tex_coord_setup.b8` | **bit3** (plus bit4 on two arms) | same signature: zeroes exactly the one varying this occurrence addresses. Live only on the `0x42` form. |
| `tex_coord_setup.idx` | **bit7 alone**, on the `0x42` form | bit7 clear → that one varying reads 0.0, the other three untouched — i.e. the byte really is that store's destination selector, as db.json's `dst<<2` note implies. Inert over all 256 values on the `0x00` form. |
| `tex_coord_setup.b5` | bits 0,1,2,4 (+3 on the `0x42` form); 4–5 classes | bit0 set → the varying reads 0.0; bit3 with `b6` clear shifts the varying's **value** slightly (6.08333 → 6.0918 / 6.10946), an address/offset perturbation rather than a kill |
| `simd_shuffle.rsv9` | bits **1, 2, 6, 7**; 8–10 classes; 240–248 of 256 move | **not reserved.** On the `mode == 0x06` rotate / shuffle-and-fill form, bits 6 and 7 change the fill **result value** (31 → 116 → 256 across the combinations, bit2 giving a further distinct value); bit1 suppresses the stores that follow. Inert on the `0x00` / `0x04` / `0x05` forms. |

---

## 4b. FIRST-CLASS FINDING (independent of the sweep): a fragment colour-store variant `db.json` does not decode

This was found by the pre-freeze census, not by any swept field, and it is
reported here as a finding in its own right because it **silently corrupts every
occurrence census ever run against the current `frag_color_store` descriptor** —
EXP-0155's, this experiment's, and any other.

### The observation

Carrier `texcube` (`kernels/k_texcube.metal`: four texture samples of a 2D, a
3D, a cube and a 2D-array texture, then a `float4` return into an RGBA32Float
attachment) compiles to a fragment program whose only store is:

```
offset 188, 14 bytes as db.json currently consumes them:

    e7 86 54 00 00 00 01 2e 00 00 00 00 07 02
    ^^ ^^ ^^                ^^
    |  |  |                 └─ 0x2e = the RGBA32Float attachment format descriptor
    |  |  └──────────────────── 0x54 = store_mode, the value in 130/130 of the corpus
    |  └─────────────────────── 0x86  ← THE VARIANT BYTE
    └────────────────────────── 0xe7 = the memory-family store opcode
```

Compare a plain single-RT RGBA32Float colour store from carrier `bits`, which
`db.json` decodes correctly:

```
    e7 06 54 00 00 00 01 2e 00 00 00 00        (12 bytes, frag_color_store)
       ^^
       └─ 0x06 = the FRAGMENT tile-store variant
```

**The first twelve bytes are identical except byte+1.** Same `store_mode`
(`0x54`), same `src` (`0x00`), same `rt_index` (`0x00`), same `mask` (`0x01`),
same `fmt` (`0x2e`), same zero `slice_addr`. It is preceded by the ordinary
`0x87` `frag_tile_setup` store bracket at offset 182 (`87 02 54 0c 08 00`),
exactly as every other colour store in this experiment is.

### Why the current decode is impossible

`db.json` matches `frag_color_store` on `byte+1 == 0x06` **exactly**, and
`imageblock_store` on `byte+1 == 0x16`. `0x86` matches neither, so the decoder
falls through to `device_store`, whose only match constraint is
`byte0 == 0xe7`, and consumes **14** bytes.

That decode cannot be right:

1. `device_store` is the **compute** device-buffer store. `texcube`'s fragment
   stage has no writable device buffer at all — its only buffer is
   `device const float *u [[buffer(0)]]`, read-only.
2. The fragment returns a `float4` into an RGBA32Float attachment. That store
   has to exist, and this is the only 0xe7 in the program.
3. Its `fmt` byte is `0x2e`, the documented RGBA32Float **attachment** format
   descriptor — a colour-store field, not a device-store field.
4. Consuming 14 bytes rather than 12 means the two bytes after it (`07 02`) are
   swallowed, so anything that followed is mis-framed.

### The structural reading

`db.json` already documents `0x16 = 0x06 | 0x10` as "the `0x10` bit marking the
FIRST store after a `0x87` tile-access setup". `0x86 = 0x06 | 0x80` is therefore
a **third variant bit in the same byte**, and its role is **unknown**. The one
correlate available from this carrier set is that `texcube` is the only carrier
whose fragment stage performs four texture samples before its store; whether
`0x80` marks a texture-dependency wait, a different tile path, or something
else is **not established here**.

### Consequence for existing results

Any statement of the form "`frag_color_store` always has X", derived by
enumerating `frag_color_store` occurrences, is **unquantified over the `0x86`
form**, because that form is not in any such enumeration — it was counted as a
`device_store`. This experiment's own `frag_color_store` arms are unaffected
(all eight are `0x06` forms located and verified against frozen bytes), but the
*population* they were drawn from was incomplete.

### Proposed `db.json` fix (NOT applied — the orchestrator owns the file)

The minimal change is to stop matching `frag_color_store` on the whole of
byte+1 and match only the bits that are actually the opcode, letting the
variant bits be a field:

- change `frag_color_store.match` from `[[0,8,231],[8,8,6]]` to
  `[[0,8,231],[8,4,6]]` — i.e. match the **low nibble** of byte+1 as `0x6`,
  which `0x06`, `0x16` and `0x86` all share;
- add a `store_variant` field at `start 12, width 4` carrying the high nibble
  (`0x0` plain, `0x1` first-after-tile-setup, `0x8` the newly observed form),
  labelled `single-template-inference` until swept;
- keep `imageblock_store`'s more specific match ahead of it so the `0x16` form
  still resolves to `imageblock_store`.

That is a **proposal, not a validated fix**: it is consistent with all three
observed byte+1 values and with the existing 12-byte length, but nothing in this
experiment swept byte+1, so the nibble split is `INFERRED` and a successor
should sweep it before it is relied on.

**Evidence:** `raw/prefreeze/census_run3.json` → `texcube.stages.fragment`
(complete program hex, tokenization status, and every decoded occurrence).
Recorded machine-readably under `db_defects` in
`analysis/field_verdicts_flat.json`.

## 5. Machine-checked verdict tables **[1-RUN]**

Generated by `analysis/report.py` from `analysis/field_verdicts.json`
and `analysis/bit_rules.json`, so the prose above cannot drift from the
data. (With one run the `cross-run` column is trivially `agree`; it
becomes meaningful when run02 lands.)

### Bucket summary

| field | bucket | label | live on | inert on (carriers w/ proven detection power) |
|---|---|---|---|---|
| `frag_color_store.store_mode` | **INERT-ROBUST** | `single-template-inference` | — | cent4, ibhalf, layer, mrt3, tileread, tilerw2, vflat |
| `frag_tile_setup.access` | **INERT-ROBUST** | `single-template-inference` | — | ibmrt, layer, mrt3, tileread, tilerw2 |
| `frag_tile_setup.b5` | **INERT-ROBUST** | `single-template-inference` | — | ibmrt, layer, mrt3, tileread, tilerw2 |
| `frag_tile_setup.sel` | **INERT-ROBUST** | `single-template-inference` | — | ibmrt, layer, mrt3, tileread, tilerw2 |
| `imageblock_store.b4` | **INERT-ROBUST** | `single-template-inference` | — | atoff4, ibms4, ibsamp |
| `iter.b9` | **INERT-ROBUST** | `single-template-inference` | — | atoff1, cent4, mrt3, vflat, vhalf, vmany |
| `iter_at.loc` | **LIVE** | `hardware-run` | cent4/fragment#0, cent4/fragment#1, cent4/fragment#2, atoff4/fragment#0, atoff4/ | atoff1, cent1 |
| `simd_ballot.cache` | **INERT-ROBUST** | `single-template-inference` | — | sball, scache, sdiv |
| `simd_shuffle.cache` | **INERT-ROBUST** | `single-template-inference` | — | sball, scache, sdiv, stype |
| `simd_shuffle.rsv9` | **LIVE** | `hardware-run` | stype/compute#13, stype/compute#15 | sball, scache, sdiv, stype |
| `tex_coord_setup.b5` | **LIVE** | `hardware-run` | bits/fragment#0, bits/fragment#1, fclass/fragment#1, vsrc/vertex#0, vsrc/vertex# | fclass |
| `tex_coord_setup.b6` | **LIVE** | `hardware-run` | vsrc/vertex#0, vsrc/vertex#1, vhalf/vertex#0, ms4out/fragment#0 | bits, fclass, sball |
| `tex_coord_setup.b8` | **LIVE** | `hardware-run` | vsrc/vertex#0, vsrc/vertex#1, vhalf/vertex#0, ms4out/fragment#0 | bits, fclass, sball |
| `tex_coord_setup.b9` | **INERT-ROBUST** | `single-template-inference` | — | bits, fclass, ms4out, sball, vhalf, vsrc |
| `tex_coord_setup.idx` | **LIVE** | `hardware-run` | vsrc/vertex#0 | bits, fclass, ms4out, sball, vhalf, vsrc |
| `tex_write.amode` | **STILL-UNDERPOWERED** | `untested` | — | twdim, twtype |
| `tex_write.rsv11` | **STILL-UNDERPOWERED** | `untested` | — | twdim, twtype |
| `vary_store.b7` | **INERT-ROBUST** | `single-template-inference` | — | vclip, vflat, vhalf, vmany, vsrc |
| `vary_store.hint2` | **INERT-ROBUST** | `single-template-inference` | — | vclip, vflat, vhalf, vmany, vsrc |
| `vary_store.hint6` | **LIVE** | `hardware-run` | vmany/vertex#9, vmany/vertex#16, vhalf/vertex#0, vhalf/vertex#6, vflat/vertex#4, | vclip, vmany |

Totals: **INERT-ROBUST** 11, **LIVE** 7, **STILL-UNDERPOWERED** 2

Runs compared: g17p_20260830_run01


### LIVE fields — exact rules

| field | arm (carrier) | moved / swept | equivalence classes | live bits | exact rule | cross-run |
|---|---|---|---|---|---|---|
| `iter_at.loc` | `atoff4/fragment#0` | 128/256 | 2 | 1 | exactly the values with bit1 clear | agree |
| `iter_at.loc` | `atoff4/fragment#1` | 128/256 | 2 | 1 | exactly the values with bit1 set | agree |
| `iter_at.loc` | `cent4/fragment#0` | 128/256 | 2 | 1 | exactly the values with bit1 set | agree |
| `iter_at.loc` | `cent4/fragment#1` | 128/256 | 2 | 1 | exactly the values with bit1 clear | agree |
| `iter_at.loc` | `cent4/fragment#2` | 128/256 | 2 | 1 | exactly the values with bit1 clear | agree |
| `iter_at.loc` | `ms4cent/fragment#0` | 128/256 | 2 | 1 | exactly the values with bit1 set | agree |
| `iter_at.loc` | `ms4out/fragment#0` | 128/256 | 2 | 1 | exactly the values with bit1 set | agree |
| `simd_shuffle.rsv9` | `stype/compute#13` | 240/256 | 10 | 1,2,6,7 | 240 values, set = 0x0,0x1,0x2,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc, | agree |
| `simd_shuffle.rsv9` | `stype/compute#15` | 248/256 | 8 | 1,2,5,6,7 | 248 values, set = 0x0,0x1,0x2,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc, | agree |
| `tex_coord_setup.b5` | `bits/fragment#0` | 240/256 | 2 | 0,1,2,4 | 240 values, set = 0x0,0x1,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xb,0xc,0xd,0xe, | agree |
| `tex_coord_setup.b5` | `bits/fragment#1` | 240/256 | 3 | 0,1,2,4 | 240 values, set = 0x0,0x1,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xb,0xc,0xd,0xe, | agree |
| `tex_coord_setup.b5` | `fclass/fragment#1` | 240/256 | 3 | 0,1,2,4 | 240 values, set = 0x0,0x1,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xb,0xc,0xd,0xe, | agree |
| `tex_coord_setup.b5` | `ms4out/fragment#0` | 192/256 | 3 | 0,1,2,3,4 | 192 values, set = 0x1,0x3,0x5,0x7,0x9,0xb,0xd,0xf,0x10,0x11,0x12,0x13, | agree |
| `tex_coord_setup.b5` | `sball/compute#0` | 208/256 | 2 | 0,1,2,4 | 208 values, set = 0x1,0x3,0x4,0x5,0x7,0x9,0xb,0xc,0xd,0xf,0x10,0x11,0x | agree |
| `tex_coord_setup.b5` | `vhalf/vertex#0` | 208/256 | 5 | 0,1,2,3,4 | 208 values, set = 0x1,0x3,0x5,0x7,0x8,0x9,0xa,0xb,0xd,0xf,0x10,0x11,0x | agree |
| `tex_coord_setup.b5` | `vsrc/vertex#0` | 208/256 | 4 | 0,1,2,3,4 | 208 values, set = 0x1,0x3,0x5,0x7,0x8,0x9,0xa,0xb,0xd,0xf,0x10,0x11,0x | agree |
| `tex_coord_setup.b5` | `vsrc/vertex#1` | 200/256 | 3 | 0,1,2,3,4 | 200 values, set = 0x1,0x3,0x5,0x7,0x9,0xa,0xb,0xd,0xf,0x10,0x11,0x12,0 | agree |
| `tex_coord_setup.b6` | `ms4out/fragment#0` | 240/256 | 2 | 2,3,4,5 | 240 values, set = 0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc,0xd,0xe,0xf,0x10 | agree |
| `tex_coord_setup.b6` | `vhalf/vertex#0` | 240/256 | 2 | 2,3,4,5 | 240 values, set = 0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc,0xd,0xe,0xf,0x10 | agree |
| `tex_coord_setup.b6` | `vsrc/vertex#0` | 240/256 | 2 | 2,3,4,5 | 240 values, set = 0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc,0xd,0xe,0xf,0x10 | agree |
| `tex_coord_setup.b6` | `vsrc/vertex#1` | 240/256 | 2 | 2,3,4,5 | 240 values, set = 0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc,0xd,0xe,0xf,0x10 | agree |
| `tex_coord_setup.b8` | `ms4out/fragment#0` | 192/256 | 3 | 3,4 | 192 values, set = 0x0,0x1,0x2,0x3,0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb,0xc, | agree |
| `tex_coord_setup.b8` | `vhalf/vertex#0` | 128/256 | 2 | 3 | exactly the values with bit3 set | agree |
| `tex_coord_setup.b8` | `vsrc/vertex#0` | 128/256 | 2 | 3 | exactly the values with bit3 set | agree |
| `tex_coord_setup.b8` | `vsrc/vertex#1` | 192/256 | 2 | 3,4 | 192 values, set = 0x8,0x9,0xa,0xb,0xc,0xd,0xe,0xf,0x10,0x11,0x12,0x13, | agree |
| `tex_coord_setup.idx` | `vsrc/vertex#0` | 128/256 | 2 | 7 | exactly the values with bit7 clear | agree |
| `vary_store.hint6` | `vflat/vertex#4` | 128/256 | 2 | 4 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vhalf/vertex#0` | 128/256 | 4 | 0,1,2,3,4,5,6,7 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vhalf/vertex#6` | 128/256 | 2 | 4 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vmany/vertex#16` | 128/256 | 65 | 0,1,2,3,4,5,6,7 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vmany/vertex#9` | 128/256 | 2 | 4 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vsrc/vertex#5` | 128/256 | 2 | 4 | exactly the values with bit4 set | agree |
| `vary_store.hint6` | `vsrc/vertex#6` | 128/256 | 2 | 4 | exactly the values with bit4 set | agree |


### INERT-ROBUST fields — the envelope actually tested

| field | carriers (all with proven detection power) | arms | values per arm | total inert observations |
|---|---|---|---|---|
| `frag_color_store.store_mode` | cent4, ibhalf, layer, mrt3, tileread, tilerw2, vflat | 8 | 256 | 2048 |
| `frag_tile_setup.access` | ibmrt, layer, mrt3, tileread, tilerw2 | 8 | 256 | 2048 |
| `frag_tile_setup.b5` | ibmrt, layer, mrt3, tileread, tilerw2 | 8 | 256 | 2048 |
| `frag_tile_setup.sel` | ibmrt, layer, mrt3, tileread, tilerw2 | 8 | 256 | 2048 |
| `imageblock_store.b4` | atoff4, ibms4, ibsamp | 3 | 256 | 768 |
| `iter.b9` | atoff1, cent4, mrt3, vflat, vhalf, vmany | 6 | 256 | 1536 |
| `simd_ballot.cache` | sball, scache, sdiv | 4 | 256 | 1024 |
| `simd_shuffle.cache` | sball, scache, sdiv, stype | 8 | 2 | 16 |
| `tex_coord_setup.b9` | bits, fclass, ms4out, sball, vhalf, vsrc | 9 | 256 | 2304 |
| `vary_store.b7` | vclip, vflat, vhalf, vmany, vsrc | 9 | 256 | 2304 |
| `vary_store.hint2` | vclip, vflat, vhalf, vmany, vsrc | 9 | 256 | 2304 |


### STILL-UNDERPOWERED fields

| field | why | carriers reached |
|---|---|---|
| `tex_write.amode` | only 2 distinct carrier(s) with proven detection power (bar is 3) | twdim, twtype |
| `tex_write.rsv11` | only 2 distinct carrier(s) with proven detection power (bar is 3) | twdim, twtype |


### Detection power, per arm

71 of 72 arms pass the strict gate (status OK + observation changed + still decodes as the arm's mnemonic) in every run.

Arms WITHOUT strict detection power (excluded from every verdict):

- `iter@vmany/fragment#0` — {"g17p_20260830_run01": {"detect_ok_strict": false, "fault_only_controls": ["grp=0xd0/decode", "grp=0x0/decode"], "in_run_detect_ok": false, "profile_steps": 15, "strict_live_controls": []}}

---

## 6. The negative results, stated honestly

**Eleven fields are `INERT-ROBUST`**, and that is a first-class deliverable: it
tells an implementer which bytes they do not have to understand. But it is a
bounded claim and the bound matters more than the headline.

For each of the eleven, every value of the field was executed on ≥3
structurally different carriers, and **each of those arms had proven detection
power** — a control byte in the *same instruction* that did move the observation,
with status OK and still decoding as the same mnemonic. The proving controls are
recorded per arm in `analysis/field_verdicts_flat.json`
(`proven_live_controls`). For example every `frag_tile_setup` arm is proven by
`b1 = 0x00` / `0xfd`; every `frag_color_store` arm by `src`, `rt_index`, `mask`,
`fmt` and `slice_addr`; every `imageblock_store` arm by `slice_off`, `b6`, `fmt`
and `tail`.

**What the eleven negatives do NOT say.** They do not say the field is a
don't-care. They say it had no observable effect *in the tested envelope*, and
the envelope is written into the record. Three specific limits are worth naming
because they are the most likely places a future experiment overturns one:

1. **`simd_shuffle.cache` is one bit, not a byte.** db.json models byte+2 of
   `simd_shuffle` as a single `cache` bit at bit 17; every observed occurrence
   has byte+2 == `0x54` and **the other seven bits of that byte are not modelled
   at all**. The verdict therefore covers exactly two values of one bit. It must
   not be read as "byte+2 of `simd_shuffle` is inert". Recorded under
   `db_defects` in `analysis/field_verdicts_flat.json`.
2. **`frag_tile_setup.sel` was inert on carriers with up to three render targets
   and real tile reads, but never on a tile/imageblock compute shader**
   (`dispatchThreadsPerTile`), which the harness does not build. If `sel` selects
   among tile resources the explicit-imageblock path exposes, that path was not
   tested.
3. **`frag_color_store.store_mode` was inert including on a layered
   (`texture2d_array`) attachment and on 4-sample stores** — the only stores in
   this repository whose `slice_addr` is non-zero (`0x08000008`) — which is the
   strongest envelope available for it, but still not an exhaustive one.

**Two fields are `STILL-UNDERPOWERED` and are reported as unreached, not as
inert.** `tex_write.amode` and `tex_write.rsv11` were swept densely on six arms
covering 2D, 2D-array-with-non-zero-slice, 3D, half and uint destinations and
contiguous versus scattered data descriptors — and moved nothing. But those six
arms come from only **two source programs**, one short of the pre-registered
≥3-carrier bar, and the two share a property that could itself be the
limitation: **every write in both uses a constant, compile-time coordinate,
loaded straight from a uniform buffer, with no control flow.** Rather than
relax the bar, `ADDENDUM A` (pre-registered, `PRE_REGISTRATION.md`) adds a third
program, `kernels/k_twrt.metal`, that writes with runtime-computed coordinates,
with data of texture-unit provenance, from inside a loop, and to a 3D
destination with a runtime depth. Its paired runs are pending.

**One arm has no detection power and is excluded from every verdict:**
`iter@vmany/fragment#0`. Reported, not hidden.

## 6b. The two secondary byte-probe targets

My re-derivation of EXP-0155's never-moved list found **22** entries, not the 20
db.json fields (`analysis/audit_0155.py`; the extra two are raw byte probes from
EXP-0155's 0x57-collision arms rather than DB fields). Their status here:

- **`op57_vertex.byte2` — COVERED.** EXP-0155's vertex 0x57 probe sweeps byte+2
  of the 8-byte vertex-stage form, which is bit range `[16:24]` — exactly
  `vary_store.hint2`. It is therefore one of this experiment's 20 fields and it
  came back **INERT-ROBUST** over 9 arms on 5 carriers (`vclip`, `vflat`,
  `vhalf`, `vmany`, `vsrc`), each with proven detection power. Note what that
  means for EXP-0155's H3: byte+2 of the *vertex* form was **not** shown to
  encode an instruction length or a discriminator, over a far wider carrier set
  than H3 was originally tested on.
- **`op57_fragment.byte2` — NOT COVERED, and I am saying so rather than
  implying otherwise.** The fragment 0x57 form is the 6-byte kill / target-mask
  op, and **no carrier in this experiment emits it**: none of the 27 uses
  `discard_fragment()` or writes `[[sample_mask]]`, which is what EXP-0155's
  `c_kill` / `c_mask` used to provoke it. A byte-level scan of every fragment
  program here finds no 0x57 opcode byte at all (the only 0x57 bytes in the whole
  carrier set are operand bytes inside `sdiv`'s compute-stage `device_store`s).
  Its EXP-0155 verdict stands unchanged and unimproved. A successor wanting it
  needs a kill/mask carrier, which is cheap to add.

  Worth recording while re-deriving that data: **EXP-0155's own 0x57 arms did
  have detection power on both stages.** Across its two gated runs `byte1` moved
  448/512 on each vertex arm and 384/512 on each fragment arm, while `byte2` was
  512/512 inert on all four. So its H3 — "the discriminator is byte+1 or byte+2
  and it controls the hardware's instruction LENGTH" — is refuted for byte+2 on
  both stages by its own evidence, and this experiment extends only the vertex
  half of that (to 9 arms on 5 carriers, via `vary_store.hint2`).

## 7. Method integrity — what was checked, and one defect found

- **The ISA database used is pinned and the pin is verifiable.** A copy of
  `tools/agx-isa/{db.json,isadb.py}` was placed under `~/agxre/EXP-0163/tools/`
  on the device and its hash frozen into `CAPTURE_CONTRACT.json`
  (`db.json sha256 83b83a350ece33b8…`); the copy on the neo still hashes to
  exactly that. The repo's `db.json` has since moved to
  `07ad894d3e7041ea…` because **EXP-0165 repaired it at commit `4a54e9bb`** —
  which is not contamination (the brief's rule is that a capture is valid if the
  *authored blob hashes* match, not if `HEAD` stands still). Checked explicitly:
  that repair left **all ten** of this experiment's target instructions
  byte-identical in `length`, `match` and field layout, so these verdicts merge
  into the repaired database unchanged.
- **All 156 (arm, field) sweeps completed** in run01: 148 dense 256-value plus 8
  two-value (`simd_shuffle.cache` is 1 bit). 37,904 sweep cases plus 1,329
  baseline / detection-profile records = 39,233.
- **Zero baseline failures.** No `_baseline_recheck` or `_baseline_final`
  mismatch on any of the 72 arms; no cascade; no runner restart.
- **Frozen-occurrence integrity.** `harness/arms.py` carries the census bytes and
  offset of every arm and `run.py` refuses an arm whose located bytes differ. The
  pre-freeze smoke caught exactly this on three `cent4` arms — `run.py` and
  `analysis/census.py` had disagreed about occurrence indices because one
  preferred the forward-tokenization prefix and the other always rescanned. The
  arms were **refused, not swept at the wrong address**, and `run.py` now mirrors
  the census rule.
- **Reproducibility, measured rather than assumed.** The pre-freeze
  detection-profile smoke (`work/smoke_smoke02/sweep.jsonl`, 1,109 cases) and
  run01 are independent processes — separate archives, separate device sessions
  — that share **962** detection-profile cases. **Exactly one disagreed**
  (0.10%).
- **A defect in this harness, found by that one disagreement.** The disagreeing
  case was `tex_write@twdim/fragment#1 amode = 0xab`, and the raw shows the smoke
  scored it `moved` only because that command buffer returned
  `kIOGPUCommandBufferCallbackErrorHang`. `run.py`'s in-run predicate is
  `not same_obs(...)`, and `same_obs` requires *both* statuses OK — so **a
  faulted control scores as a live control.** A fault is an effect, but it is not
  a demonstration that the arm can see a *value* difference, which is what an
  inert verdict rests on. `analysis/verdicts.py` therefore **recomputes the
  detection gate from the raw records** (status OK **and** observation changed
  **and** still decodes as the arm's mnemonic) instead of trusting the in-run
  summary. Recomputed strictly the gate is unchanged at 71/72 arms, so no verdict
  moves — but **`detect_ok` in `05_run_manifest.json` should not be cited;
  `analysis/field_verdicts.json` is the corrected form.** The raw is untouched.
  (Checked against EXP-0155 by the orchestrator: its ladder uses the same
  predicate shape but no control record in either of its gated runs ever faulted,
  so the defect could not have fired there.)

## 8. Faults, hangs, and a by-product measurement of GPU contamination

**88 of run01's 39,233 cases were non-OK: 84 `ErrorHang` and 4
`ErrorPageFault`, with zero `InnocentVictim`.** Every one is inside the
detection profile; **no value of any of the 20 target fields faulted, on any
arm.**

The cause is inherent to the profile: it splices the bitwise complement of every
field, and complementing a register/operand field (`grp`, `dst`, `src`,
`b5_tag`, `hint1`, `form_sig`) points the instruction at an out-of-range
register. The distribution is:

| instruction | control field | `ErrorHang` | `ErrorPageFault` |
|---|---|---|---|
| `vary_store` | `b5_tag` | 18 | — |
| `iter_at` | `grp` | 14 | 2 |
| `iter_at` | `dst` | 10 | — |
| `vary_store` | `hint1` | 8 | — |
| `simd_shuffle` | `dst` | 8 | — |
| `frag_color_store` | `src` | 6 | — |
| `iter` / `simd_ballot` | `dst` | 4 + 4 | — |
| `simd_ballot` | `form_sig` | 4 | — |
| `imageblock_store` | `src` / `b6` | 3 + 2 | — |
| `iter_at` | `lead` | — | 2 |
| `simd_shuffle` | `dsthi` | 2 | — |
| `frag_color_store` | `mask` | 1 | — |

**A GPU hang is a device-level reset, which discards other contexts' command
buffers as `InnocentVictim`.** Run01 produced 88 of them in 50.3 s of wall clock
— **≈1.7 device resets per second of GPU-busy time, from one agent doing
ordinary field-sweep work.** That is an independent, by-product measurement of
exactly the contamination mechanism that made `EXP-0158`'s cross-run gate
unusable with 8–12 experiments sharing the device, and it is why this experiment
went quiet on request rather than running its confirmation concurrently.

Reproducible-hang note for whoever wants it: `iter_at` with `grp = 0x50` (which
re-decodes as no known mnemonic) hung the device on both `cent1` arms, in both
the smoke and run01.

## 9. Limitations

- **[1-RUN]** Everything here rests on one gated run. Cross-run agreement is
  pre-registered as the promotion gate and `run02` has not been executed.
- The oracle is **inert**, not predictive: it detects *that* an observation
  changed, exactly, and the equivalence classes are derived from the data. It
  does not independently predict what the new value should be. For
  `iter_at.loc` the class meanings are pinned by the carrier design
  (centroid versus per-sample varyings in known channels); for the other six LIVE
  fields the partition is exact but the *meaning* of each class is described from
  the observed effect, not proven against a host-computed model.
- Several carriers do not tokenize cleanly, so their occurrences are located by
  anchored decode scan and are **not on a proven instruction boundary**.
  `located_via` is recorded per arm. Such arms are only usable through their
  detection profile — a spurious scan hit cannot move the observation — but a
  reviewer should weigh them accordingly.
- `imageblock_load` is still not emitted by any carrier we can compile
  (EXP-0142 / EXP-0155's pre-registered negative), and this experiment did not
  change that.
- No tile/imageblock compute shader (`dispatchThreadsPerTile`) was built, so the
  explicit-imageblock path is outside every envelope here.

## 10. Bearing on the closure goal

The direct deliverable is `analysis/field_verdicts_flat.json`: 20 fields moved
off "swept, no effect, meaning unknown" onto one of three defensible footings,
on the actual documentation target. Seven gain exact, emitter-usable bit rules —
including one, `iter_at.loc`, that is strictly better than the enum currently in
`db.json`, and one, `simd_shuffle.rsv9`, that db.json calls "reserved" and is not.

The methodological result generalises beyond these 20: **an inert sweep is a
statement about the carrier until the carrier is shown to have detection power,
and even then it is a statement about an envelope.** EXP-0155 found three such
fields by hand; this experiment found seven more by construction, from a
20-field list that had already survived two gated runs. Any field in
`validation.json` whose only evidence is "swept, nothing moved" should be read
with that prior.

## 11. Clean-room statement

Every byte inspected or spliced is the compiled form of MSL in `kernels/`, which
we wrote. The splice-and-reload technique uses only public Metal API
(`newLibraryWithURL:`, `MTLBinaryArchive`,
`MTLPipelineOptionFailOnBinaryArchiveMiss`). **No Apple binary was disassembled,
decompiled, symbol-dumped, strings-scanned, or otherwise introspected.** The
only machine code read is the output of the public compiler API applied to our
own source.
