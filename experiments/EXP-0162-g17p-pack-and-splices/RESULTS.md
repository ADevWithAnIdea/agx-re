# RESULTS — EXP-0162: the PACK coverage gap closed, and both descriptor defects settled

**Clean-room provenance**

```
Clean-room provenance: OWN-SHADER + HW-PROBE (+ PUBLIC for IEEE-754 / bfloat16 and the MSL
  format-conversion definitions, used only to write the host oracle, never to source an
  Apple9 encoding fact)
Inputs inspected: kernels/carriers.metal (EXP-0144's carriers, verbatim),
  kernels/render_probe.metal (authored here), the machine code compiled from both, this
  repository's own committed own-MSL corpus, and tools/agx-isa/ (read-only)
Apple binary introspection: NONE
Reproduction: README.md -> "Reproduction"
Evidence: raw/g17p_20260829_run01__{cvt_bf16,cvt_f2h_dst,packed_half2_hi}/sweep.jsonl,
  raw/g17p_20260829_run04__rog/sweep.jsonl,
  raw/g17p_20260829_run05__{kill,vary}/sweep.jsonl (append-only, one object per case);
  raw/g17p_20260829_run02__* retained unused; analysis/*.json
```

**Target: Apple A18 Pro / G17P only.** Nothing here is promoted to M4/G16G, and no M4 label
is carried in. Where an M4 result is deliberately re-tested, it is named and the
reproduction outcome stated.

---

## 0. Headline

| | |
|---|---|
| EXP-0144 fields that were blocked by coverage | **18** |
| Now `hardware-run` on G17P | **18 of 18** |
| **bf16 numeric result measured?** | **YES** — 31 semantic vectors; float32→bfloat16 is **round-to-nearest-EVEN**, and f32 input denormals **flush to zero** |
| `cvt_bf16` RNE (EXP-0144 withdrew this) | **re-established, and strengthened**: `TIES_DOWN`, `TRUNC` and `RNA` are each refuted by named tie vectors |
| `packed_half2_hi` high-lane-only (EXP-0144 withdrew this) | **re-established**: 4/4 vectors, high lane = the correct packed product, low lane **written as zero** |
| `pixel_order` defect | **SETTLEABLE and settled** — a match that passes round-trip, moves **zero** corpus firings, and decodes four HW-verified encodings the old one could not |
| `vary_store` defect | **SETTLEABLE and settled** — a byte+1-aware length + match split; **833 clean files (+1), −268 leftover bytes**, round-trip ALL PASS |
| Cases dispatched / genuine hangs | **7 898** sweep cases: compute 4 424 (**0 hangs**) · `rog` 2 048 (**0 hangs**) · `kill` 1 128 (3) · `vary` 298 (7). 369 reproducible faults, all in the compute arms. |
| Fields labelled | 33 `hardware-run`, 2 `isolated-byte-diff`, 2 `untested` |
| `db.json` edited | **No.** Proposals in `analysis/proposed_db_changes.json`, A/B'd against COPIES |

**All five pre-registered detection-power controls passed**, and both render arms' controls
passed *quantitatively* — which is the only reason any "inert" verdict below is a
measurement rather than a blind spot.

---

## 1. Directly observed

### 1.1 bf16 rounding — the questionnaire measurement (Arm A, 31 vectors)

Every vector was run on the **unmutated** `cvt_bf16` in `c_f2bf` with a host oracle
computed in exact integer arithmetic, and scored against **four** competing models.

| model | vectors fitted (of 31) | refuted by |
|---|---|---|
| **`RNE`** (round half to even) | **30** | only vector 20, the largest f32 subnormal — see §1.2 |
| `RNA` (ties away from zero) | 24 | `1.00390625`→`0x3f80`, `2.0078125`→`0x4000`, `-1.00390625`→`0xbf80`, `3.3828852e38`→`0x7f7e`, and two subnormals |
| `TIES_DOWN` (ties toward zero — **EXP-0133's `unorm16` store rule**) | 24 | `1.01171875`→**`0x3f82`**, `2.0234375`→`0x4002`, `-1.01171875`→`0xbf82`, `0.998046875`→`0x3f80`, `3.3961775e38`→**`0x7f80` = +inf**, `-3.3961775e38`→`0xff80` |
| `TRUNC` (drop the low 16 bits) | 20 | all of `TIES_DOWN`'s, plus `0.1`→`0x3dcd`, `1/3`→`0x3eab`, `2/3`→`0x3f2b` |

The load-bearing rows are the **odd-mantissa-lsb ties**, because they are the only inputs
on which `RNE` and `TIES_DOWN` differ at all. `1.01171875` is the exact bf16 tie whose
truncation `0x3f81` is odd: `RNE` must round **up** to `0x3f82`, ties-toward-zero must keep
`0x3f81`. **The hardware returns `0x3f82`.** The even-lsb tie `1.00390625` returns `0x3f80`,
i.e. down — so the rule is genuinely *to even*, not "always up" and not "always down".

Two boundary rows are worth quoting on their own:

* `0.998046875` (bits `0x3F7F8000`) → **`0x3f80`**: the tie carries **into the exponent**.
* `3.39617752923046e38` (bits `0x7F7F8000`, the tie above the largest finite bf16) →
  **`0x7f80` = `+inf`**. RNE overflows to infinity here; every truncating model would have
  produced the largest finite value. The negative mirror gives `0xff80` = `-inf`.

`±0` are preserved with sign (`0x0000` / `0x8000`); `±inf` pass through; both a signalling
and a quiet NaN come back **`0x7fc0`**, i.e. quieted.

**This closes the "no committed experiment has ever measured a single bf16 numeric result"
gap** (Part-II P2-01/02), on G17P, with a host-computed oracle and three refuted alternatives.

### 1.2 A first-class negative: f32 input denormals FLUSH TO ZERO

The one vector `RNE` does not fit is the largest f32 subnormal, `0x007FFFFF`
(`1.1754942e-38`). Correct RNE rounds it **up into the smallest normal bfloat**, `0x0080`;
the hardware returns **`0x0000`**. The two other subnormal inputs tested (`0x00000001` and
the subnormal exact tie `0x00008000`) also return `0x0000`, which RNE alone would also
predict — so `0x007FFFFF` is the discriminating case, and it says the subnormal never
reaches the rounder.

bfloat16 shares float32's exponent range, so a *normal* f32 can never produce a subnormal
bf16; the only subnormal question for this instruction is on the **input** side, and the
answer is flush-to-zero. **Alternative not excluded:** the flush may happen in the load /
register path rather than inside the converter. This carrier cannot separate those, and the
verdict says so.

**Driver consequence:** an implementer must not assume IEEE subnormal handling for
`float → bfloat`; it is RNE **with input FTZ**.

### 1.3 `packed_half2_hi` — the withdrawn finding, re-established (Arm B)

The instruction cannot be provoked from any MSL shape EXP-0144 tried, so it is reachable
only as an encoding assembled from `db.json` and spliced over the carrier's own 6-byte
`half_alu` (`90 04 05 00 00 20` → `98 04 24 00 00 20`, MODE A).

**It executes, and it computes the packed-half2 product for the HIGH lane only.** All four
semantic vectors, against a poisoned read-back:

| vector | high lane expected | high lane observed | low lane if BOTH computed | low lane observed |
|---|---|---|---|---|
| `(1.5,2.5)·(3.0,4.0)` | `0x4900` (10.0) | **`0x4900`** | `0x4480` (4.5) | **`0x0000`** |
| `(0.5,-0.5)·(2.0,-2.0)` | `0x3c00` | **`0x3c00`** | `0x3c00` | **`0x0000`** |
| `(65504,1)·(2,1)` | `0x3c00` | **`0x3c00`** | `0x7c00` (inf) | **`0x0000`** |
| `(6e-8,1)·(1,1)` | `0x3c00` | **`0x3c00`** | `0x0001` | **`0x0000`** |

The poison **refines** EXP-0144's withdrawn wording. It reported the low lane "untouched";
the low half of the read-back word is **`0x0000`, not the poison**, so the instruction
writes the whole 32-bit destination and puts zero in the low lane. That is a different
statement, and only a poisoned buffer can tell them apart.

Corroborating: sweeping byte0's high nibble, value `8` leaves the read-back word at
**`0xDEADBEEF` intact** — the destination moved to a register nothing stores, which is a
strictly stronger observation than a zero and further proof the instruction is live.

### 1.4 The 18 fields (Arms A/B/C)

`analysis/field_verdicts.json` carries every rule with its outcome histogram. Highlights,
all dense 0..255 unless stated:

| field | measured rule (G17P) |
|---|---|
| `cvt_bf16.dst` / `cvt_f2h_dst.dst` / `packed_half2_hi.dst` | **byte0's HIGH NIBBLE is the destination selector.** Swept dense 0..15 with the low nibble held, so the length cannot change — the coverage EXP-0144's bounded 24-value byte0 probe could not give. `cvt_f2h_dst` shows 16 distinct read-back patterns |
| `cvt_bf16.srcw` (+1) | `(v & 0x7f) == 0x01` — exactly `{0x01, 0x81}` |
| `cvt_bf16.opsel` (+2) | 40/256; **every value with `(v & 0x07) == 0x07` FAULTS** (32 cases) |
| `cvt_bf16.fmt` (+4) | 52/256, **and `0x01` — `db.json`'s own match constant — is NOT among them** (see §3) |
| `cvt_bf16.dir` (+6) | `(v & 0xc2) == 0x40` exact — 32 values |
| `cvt_bf16.b7` (+7) | `(v & 0x02) == 0x00` exact — 128 values |
| `cvt_f2h_dst.srcfmt` (+1) | `(v & 0x7f) == 0x01` — identical rule to `cvt_bf16` |
| `cvt_f2h_dst.opsel` (+2) | `(v & 0xc7) == 0x04` exact — 8 values; same `(v & 0x07) == 0x07` fault family |
| `cvt_f2h_dst.dhalf` (+4) | `(v & 0xf7) == 0x04` exact — exactly `{0x04, 0x0c}` |
| `packed_half2_hi.srcA` (+1), `.srcB` (+3), `.mods_hi` (+5) | **fully INERT, 256/256 each** — see §3 |
| `packed_half2_hi.opsel` (+2) | 96/256 reproduce; 144 fault |

`cvt_f2h_dst`'s five semantic vectors match IEEE fp16 round-to-nearest-even exactly,
including the `65520.0` overflow tie that must carry to `+inf`.

### 1.5 `pixel_order` — the G17P legal sets, and what the family actually is (Arm D)

**Detection power first, in numbers.** The carrier draws 8 instances over one texel under a
texture-tagged `raster_order_group`; with ordering intact the texel ends at exactly `8·src`
and the programmable-blend pixel at `clear + 36·src`. Corrupting the acquire member's
byte+4 to `0x01` drops the texel to exactly `1·src` and the pixel to `clear + 8·src` — **7
of 8 serialised read-modify-writes lost**. Reproduced for the release member and for the
opcode byte. 22/22 baselines byte-exact. **The spliced value is live on the rendered-pixel
path, and the litmus counts lost updates.**

Dense 0..255 on both members, all four bytes:

| field | acquire (`07 14 54 50 06 00`) | release (`07 04 54 d0 06 00`) |
|---|---|---|
| `kind` (+1) — **not swept by EXP-0147** | `(v & 0x16) == 0x14` exact, **32** values | `(v & 0x06) == 0x04` exact, **64** values |
| `scope` (+3) | `bit4 == 1 and (bit6 XOR bit7) == 1`, **64** | `(v & 0x90) == 0x90`, **64** |
| `flags` (+4) | `(v & 0x01) == 0 and (v & 0x0e) != 0`, **112** | `(v & 0x0e) != 0`, **224** |
| `b5` (+5) | **fully inert**, 256/256 | **fully inert**, 256/256 |

The `scope` and `flags` rows **reproduce EXP-0147's M4 measurement exactly**, including the
counts 64 / 64 / 112 / 224. That is a G16G↔G17P agreement, stated as such. `kind` is new:
bit1 must be clear and bit2 set in both members, and **bit4 is the acquire/wait bit**.

**The cross-form probes — the evidence the corpus cannot supply.** Whole six-byte
encodings from the same `0x07` family were substituted for one or both members:

| substituted encoding | at acquire | at release | both |
|---|---|---|---|
| `07 14 54 51 0e 00` / `07 04 54 d1 0e 00` — the `threadgroup_barrier(mem_texture)` pair our **own MSL** compiles to | **ok** | **ok** | **ok** |
| `07 14 54 50 0e 00` / `07 04 54 d0 0e 00` — byte+4 = the texture memory class | **ok** | **ok** | — |
| `07 14 54 51 06 00` / `07 04 54 d1 06 00` — byte+3 bit0 (execution-convergence) set | **ok** | **ok** | — |
| `07 04 54 61 09 00` — the corpus **compute** threadgroup barrier | 7 of 8 lost | 7 of 8 lost | — |
| `07 04 54 84 0a 00` — the device `mem_fence` | 7 of 8 lost | 7 of 8 lost | — |
| `07 02 54 0c 02 00` — the corpus **fragment tile-ordering** barrier | wrong pixel | wrong pixel | — |
| each member's own encoding at the **other** site | 7 of 8 lost | 7 of 8 lost | — |

Two things follow, and they are the whole answer to the defect:

1. **`threadgroup_barrier(mem_texture)`'s acquire/release pair IS the `pixel_order` pair.**
   Not "similar": byte-for-byte substitutable, in both directions, at both sites, with the
   ordering litmus at full power.
2. **The corpus barriers are NOT raster-order markers.** They lose the same 7 of 8 updates
   the neutered marker loses. So candidate C1b — which moved 186 real corpus
   `threadgroup_barrier`s into `pixel_order` — was not merely over-fitted, it was
   *contradicted by hardware*. That failure is now a measurement.

### 1.6 The `0x57` group — byte+2 is not the discriminator (Arm E)

**Desk, over the committed own-MSL corpus (1080 files), before any dispatch:**

| population | count | byte+1 low nibble | byte+5 | byte+2 |
|---|---|---|---|---|
| vertex varying stores | **615** | always **6** (bit1 SET) | `0x40`/`0x41` | `0x54`×554, `0x55`×31, `0x56`×40 |
| fragment kill/mask ops | **10** | always **4** (bit1 CLEAR) | `0x01` | `0x54`×4, `0x55`×1, `0x56`×3+2 |

`0x54`, `0x55` and `0x56` occur in **both** populations. **The dispatch's premise — and
`db.json`'s own `emit_unsafe` note — that "byte0=0x57 with byte+2=0x54" identifies the
fragment op is therefore wrong.** Hardware agrees: byte+2 is **fully inert**, 256/256, on
the fragment op *and* 256/256 on a vertex store.

**Detection power (fragment).** Splicing the op's byte+4 from `0x00` to `0x01` turns the
surviving pixel `(0.75, 0.5, 0.25, 1)` into the clear colour; the unspliced `mask = 0`
control does the same. 12/12 baselines exact.

| probe | result |
|---|---|
| byte+1 `0x14 → 0x16` (**bit1 SET**, the vertex tag) | **fragment KILLED** — the op stops working |
| byte+1 `0x14 → 0x1c` (bit1 still clear) | **unchanged** — reproducing EXP-0091's M4 null result on G17P |
| byte+1 dense 0..0x5b | `(v & 0x06) == 0x04` **exact** over all 92 values dispatched: bit2 set **and bit1 clear** |
| byte+5 `→ 0x40 / 0x41 / 0x03`, and dense 0..255 | **fully inert** — byte+5 separates the corpus but is *not* the hardware selector |
| byte+4 `src_sel` dense | `(v & 0x1f) == 0x00` exact — only `{00,20,40,60,80,a0,c0,e0}` survive; bits[4:0] are a register select, bits[7:5] don't-care (sharpens EXP-0091's partial probe) |
| byte+3 dense | `(v & 0xfe) == 0x00` — only `{0x00, 0x01}` |

**Detection power (vertex), per output slot.** Zeroing the source register of each of the
eight `vary_store`s changes exactly that channel, or kills the draw for the position slots —
8 of 8 respond. 5/5 baselines exact. Then, reproduced at three different stores:

| probe | result |
|---|---|
| byte+1 **bit1 CLEARED** (`0x06 → 0x04`) | the store's own channel **and downstream channels** return garbage floats (`5.06e32`, `-1.55e19`) — the signature of a stream desync |
| control: byte+1 bit3 set, **bit1 left set** | **unchanged**, all three stores |
| byte+6 `→ 0xFF` | **NO DRAW**, all three stores — byte+6 is **live**, so the vertex form really is ≥ 7 bytes |
| byte+7 `→ 0xFF` | **unchanged**, all three stores — byte+7 inert, matching `db.json`'s `const 0x00` |

So the same bit governs both forms, in opposite senses, on hardware: **byte+1 bit1 set → the
8-byte vertex store; clear → the 6-byte fragment op.**

---

## 2. The two defects, settled (`analysis/proposed_db_changes.json`)

`db.json` was **not** edited. Both changes were applied to COPIES by
`analysis/make_variant.py` and measured by `analysis/ab_run.py`.

| | baseline (live tree, measured here) | `pixel_order` | `vary_store` | both |
|---|---|---|---|---|
| `roundtrip_test.py` | 302 OK / 0 FAIL | **302 / 0** | **302 / 0** | **302 / 0** |
| corpus clean files (of 1080) | 832 | **832** | **833** | **833** |
| corpus strict leftover bytes | 388 872 | **388 872** | **388 604** | **388 604** |
| descriptor firings moved | — | **none** | `frag_sample_submit` 0→10, `vary_store` 621→611, +37 tokens net | same |

> **A note on the frozen numbers.** The dispatch quotes EXP-0148's endpoint as 832 clean /
> 389 368 leftover. The live tree measures 832 / **388 872**: the clean-file count is
> unchanged and the leftover count has moved by 496 bytes because `db.json` itself has moved
> since (the `work/DB-DEFECT-TRIAGE.md` (a)/(b) pass landed in between). The gate applied
> here is **no regression against the live baseline measured in the same run**, not against
> a quoted historical constant.

### 2.1 `pixel_order` — drop the byte+4 pin, constrain byte+3 instead

```
match:  [[0,8,7], [16,8,84], [32,8,6]]      ->  [[0,8,7], [16,8,84], [28,1,1], [30,1,1]]
        (byte+4 == 0x06)                        (byte+3 bit4 == 1 AND byte+3 bit6 == 1)
```

`flags` (byte+4) becomes the genuine field the descriptor already declared, covering the
full measured 112 / 224 legal sets.

**Functional check — does the tree decode what the hardware accepted?**

| encoding | HW | baseline decodes as | variant decodes as |
|---|---|---|---|
| `07 14 54 50 06 00` | ok | `pixel_order` | `pixel_order` |
| `07 04 54 d0 06 00` | ok | `pixel_order` | `pixel_order` |
| `07 14 54 51 0e 00` | **ok** | `threadgroup_barrier` | **`pixel_order`** |
| `07 04 54 d1 0e 00` | **ok** | `threadgroup_barrier` | **`pixel_order`** |
| `07 14 54 50 0e 00` | **ok** | `threadgroup_barrier` | **`pixel_order`** |
| `07 04 54 d0 0a 00` | **ok** | `threadgroup_barrier` | **`pixel_order`** |
| `07 04 54 61 09 00` | **ordering LOST** | `threadgroup_barrier` | `threadgroup_barrier` |
| `07 02 54 0c 02 00` | **ordering LOST** | `threadgroup_barrier` | `threadgroup_barrier` |
| `07 04 54 84 0a 00` | **ordering LOST** | `mem_fence` | `mem_fence` |

Four HW-verified raster-order encodings become decodable; the three the hardware refuses keep
their old mnemonics; **zero corpus firings move.** This is exactly what C1 and C1b failed to
do, and the reason it works is a byte the corpus fitting never reached: **byte+3**, whose
`0x50`/`0xd0`/`0x51`/`0xd1` values occur nowhere in 1080 own-MSL files while `0x06` at byte+4
and `0x04`/`0x14` at byte+1 both collide.

**Stated residue, not hidden:** the full hardware-legal byte+3 set is
`bit4 AND (bit6 OR bit7)`. An **OR of two bits is inexpressible** in the
`(start, width, value)` match language — the same blocker as db defects 25 and 50 — so this
proposal takes the largest expressible **subset**, `bit4 AND bit6`. The `bit6 == 0, bit7 == 1`
half (`0x9x`, `0xbx`) stays undecodable. Closing that needs the match language to grow an OR term.

### 2.2 `vary_store` — a byte+1-aware length and a split match

```
isadb.py:  if b0 == 0x57: return 8      ->  if b0 == 0x57: return 8 if (_b1 & 0x02) else 6
vary_store.match:  [[0,8,87]]           ->  [[0,8,87], [9,1,1]]     ; emit_unsafe removed
new: frag_sample_submit, length 6, match [[0,8,87], [9,1,0]]
```

`frag_sample_submit` fires **exactly 10** times and `vary_store` drops by **exactly 10** —
the split conserves the population. The remaining deltas (`+14 falu2`, `+9 iter`, `+3
get_sr`, `+3 threadgroup_barrier`, …) are instructions that become reachable once the
fragment mains stop desynchronising: **+1 clean file, −268 leftover bytes, +37 tokens.**

The new descriptor's fields carry this experiment's own measured rules (`src_sel`
`(v & 0x1f) == 0`, `kind` `(v & 0x06) == 0x04`, `amode`/`tag` inert) and cite EXP-0091 for the
MSAA mask-width contract.

### 2.3 `cvt_bf16`'s match — a stronger statement of db defect 26, still blocked

`db.json` pins byte+4 == `0x01`; our own compiler emits `0x05`. **The hardware does not
accept `0x01` either.** Dense 0..255: 52 values reproduce the convert
(`05 0d 21 25 29 2d 31 35 …`) and `0x01` is **not** among them. So the match constant is not
merely narrow — it is wrong.

This still **cannot be fixed**, for the reason `work/DB-DEFECT-TRIAGE.md` already gave and
this experiment re-confirms: `instr_length()` has **no rule at all** for `byte0 == 0x01`, so
`cvt_bf16` cannot be lengthed and no match relaxation can reach it. The locate pilot
tokenizes `c_f2bf` cleanly to offset 156 and then reports `<no-length>` on
`01 01 14 81 05 02 40 00`. **Db defect 28 must land first**, and it needs its own
pre-registration. No variant was built, because none could be measured.

---

## 3. `db.json` defects found (recorded, NOT patched)

Full detail in `analysis/field_verdicts.json` and `analysis/proposed_db_changes.json`.

1. **`pixel_order`'s `flags`/match contradiction** — settled, §2.1.
2. **`vary_store`'s length and match** — settled, §2.2. And the *stated* discriminator
   (byte+2 == 0x54) is refuted twice over: by the corpus and by 256/256 inertness on hardware.
3. **`cvt_bf16`'s match constant `[32,8,1]` names a value the hardware rejects** — §2.3.
4. **`cvt_bf16.srcw`'s documented enum is wrong for this form.** `db.json` says byte+1 is the
   source width, `0x03` float32 / `0x02` float16. The only values that work are
   `{0x01, 0x81}`, and our own compiler emits `0x01` for a `float → bfloat`. Whatever byte+1
   selects, `0x02`/`0x03` are not it here.
5. **`packed_half2_hi.srcA` (byte+1) and `.srcB` (byte+3) are typed `reg` and are FULLY
   INERT** — 256/256 each, one distinct read-back over the whole sweep — as is `mods`'s
   upper byte (+5). Only byte0's high nibble (`dst`), byte+2 (`opsel`) and `mods`'s lower
   byte (+4) are live. *Alternative not excluded:* the operand registers may be implicit in
   this synthesised form, or inherited from the `half_alu` this splice replaced; a second
   carrier is needed before calling them non-fields in general.
6. **`vary_store.hint2` (byte+2) is inert** in the vertex carrier too (256/256), so
   `db.json`'s "carries the same 0x54/0x55/0x56 data-source mode as the `device_store` amode"
   is at best not load-bearing here.
7. **A cross-instruction fault family:** for both `cvt_bf16` and `cvt_f2h_dst`, every byte+2
   value with `(v & 0x07) == 0x07` faults reproducibly — 32 values each, the identical set.

---

## 4. Interpretation, and what is NOT concluded

1. **"Inert" means inert in the tested carrier.** Every inert verdict here is backed by a
   detection-power control that demonstrably moves the same output, so it is a measurement —
   but a different carrier (more render targets, more varyings, a second source operand) may
   make the same byte live. Each verdict's `range` names its carrier.
2. **The `pixel_order` merge is a behavioural identity at one litmus.** `07 14 54 51 0e 00`
   and `07 14 54 50 06 00` are interchangeable *for raster-order serialisation of a texture
   read-modify-write over 8 instances*. They may still differ in a memory-scope respect this
   litmus cannot see. The proposal therefore changes **decoding**, and the semantics string
   says what was tested.
3. **The `0x57` length claim rests on three independent legs**, none of which is a length
   proof on its own: the corpus split (615/10, zero exceptions), the hardware bit1 behaviour
   in *both* directions with passing controls, and the corpus A/B (+1 clean file, −268
   bytes, exact population conservation). Together they are strong; the honest label on the
   *length rule* is `HW-VALIDATED` for the bit's liveness and `STRUCTURAL` for the length.
4. **The bf16 FTZ finding does not localise the flush.** Input path or converter — this
   carrier cannot tell.
5. **`packed_half2_hi` is still only reachable by synthesis.** No MSL shape emits it. That
   makes every verdict on it conditional on the MODE-A splice being the instruction
   `db.json` describes; the fact that it computes a correct packed-half2 high-lane product
   is the evidence that it is.

---

## 5. Limitations and exact tested range

* **G17P only.** 7 898 sweep cases dispatched: 4 424 compute, 2 048 `rog`, 1 128 of a
  planned 1 280 `kill`, 298 of a planned 1 536 `vary` (the shortfalls are the hang stops below).
* **Byte 0 was swept only in its high nibble** (dense 0..15, the `dst` field), with the low
  nibble held at the anchor's value so the length cannot change. The low nibble got a
  bounded 8-value off-match probe, recorded as match evidence and **never** as `dst` evidence.
* **`frag_sample_submit.kind` reached only 0..0x5b** — two genuine hangs stopped that byte
  (`FIELD-SWEEP-PROTOCOL` §8). The rule `(v & 0x06) == 0x04` is exact over all 92 values
  dispatched; 0x5c..0xff is untested.
* **The vertex-side sweeps are hang-limited.** A vertex-stream desync hangs the GPU. Three
  `(target, byte)` areas were stopped at 2 hangs each and the arm at 12 total; `vary_store`'s
  `hint1[vary_slot_e0]` and `b5_tag[vary_slot_c0]` are therefore reported **`untested`**, not
  rounded up. `hint2[vary_slot_c0]` completed all 256.
* **`pixel_order` was swept one member at a time**, as EXP-0147 did; joint corruption of both
  members was covered only by the six named cross-form pairs.
* **The `rog` litmus is a single texel with 8 instances.** It counts lost updates; it does
  not test ordering across tiles, across draws, or with more than one raster-order group.

## 6. Concurrency, contamination, and one process deviation

**Other GPU experiments running concurrently: at least six** (EXP-0155, 0156, 0157, 0158,
0159, 0160 were all observed holding or queueing on the GPU lease, plus EXP-0158's case
executor). This is stated because it is the difference between two very different pieces of
evidence.

What it cost, and how it was handled:

* **run02 (render) aborted at its baseline in all three arms** — every attempt came back
  `kIOGPUCommandBufferCallbackErrorInnocentVictim`. It is **retained unused** in `raw/`,
  backs no label, and its id was never reused.
* **`experiments/NEO-TARGET-BRIEF.md` changed on disk mid-experiment: the GPU lease was
  removed** ("Concurrency: unrestricted. There is no lease."). run03 had already been
  launched *under* the lease and was still queued behind six holders; it was killed and
  **never captured a case**, so no run03 directory exists. This is a deliberate deviation
  from the dispatch's instruction to "confirm every fault/hang verdict under
  `~/agxre/gpulease.sh`": that lease no longer exists as policy. What replaces it, per the
  updated brief, is exactly what this experiment already does — **poisoned read-back**, an
  independent integrity sentinel, the recorded OS fault-classification string, and
  majority-of-3. The compute arms' 369 fault verdicts and the render arms' hangs are
  therefore backed by majority-of-3 plus poison adjudication, **not** by lease isolation, and
  a reader should hold them at that strength.
* EXP-0147's recovery rule was adopted after run02: **retry in place first**, restart the
  child only after four consecutive victims. Its earlier restart-first loop produced 138
  consecutive false `invalid_run`s.
* Discarded-and-re-run attempts: **3 121 across all arms** — 471 (`cvt_bf16`), 447
  (`cvt_f2h_dst`), 660 (`packed_half2_hi`), the rest in the render arms. Render-runner
  restarts: 0 (`rog`), 136 (`kill`), 177 (`vary`). The `rog` arm needed **none**, which is
  why its 2 048 cases are the cleanest evidence in this experiment.
* **95 of 97 baseline checks passed.** The two failures are run02's aborted pre-mutation
  baselines — which is exactly why run02 is retained unused and backs no label. Every
  baseline in every arm that produced data, including every mid-run re-validation, passed,
  so no arm recorded a cascade as data.

## 7. Recommended next steps

1. **Db defect 28 — a length rule for `byte0 == 0x01`** (and `0x18`). It is the single
   prerequisite blocking `cvt_bf16`'s match fix (§2.3) *and* the `cvt_f2h`/`cvt_f2h_dst`
   merge (defect 27). It needs its own pre-registration; everything downstream of it is
   already measured.
2. **Extend the match language with an OR term.** Three separate defects now queue behind it:
   `pixel_order`'s `bit4 AND (bit6 OR bit7)` (§2.1), `unpack_convert`'s `(b & 3) != 0`
   (defect 25), and `operand_word_x2_h*`'s cross-field predicate (defect 50).
3. **A second carrier for `packed_half2_hi`**, to decide whether its `srcA`/`srcB` are
   genuinely not register fields or merely unreachable in the MODE-A splice (§3.5).
4. **Localise the bf16 input FTZ** — is it the converter or the load/register path?
   A carrier that keeps a subnormal in a register across an unrelated ALU op would tell.
5. **`pixel_order` with more than one raster-order group**, to test whether `scope`'s
   bit6/bit7 pair selects the group rather than the memory scope.
