# G17P vs G16G — the seven load-bearing findings, side by side

**EXP-0153.** Every G17P column is a **direct observation on the Apple A18 Pro**
(`Mac17,5`, `AGXAcceleratorG17P`, `applegpu_g17p`, 5 GPU cores, macOS 26.6
build 25G5043d). Every G16G column is the committed M4 result being
revalidated, quoted from that experiment's own `RESULTS.md` or raw records.
Nothing here promotes an M4 label to G17P or a G17P label to M4.

Evidence: `raw/g17p-20260830-run01/` and `raw/g17p-20260830-run03/` — two
independent gated runs, **1958/1958 cases in exact case-for-case agreement, 0
disagreements**, 52/52 unmutated-carrier health checks `ok`, 0 cascades; plus
`raw/g17p-20260830-reval02/`, which re-ran every fault-class case **five times
each under the GPU lease** (75 cases, 375 measurements, 14/14 health checks
`ok`). Scored by `analysis/verdicts.py` → `analysis/verdicts.json`.

The revalidation changed one reading and is reported in §6: 69 of the 75
re-run cases are reproducible faults 5/5, and **4 are not faults at all** —
they were victims of sibling GPU load that survived *both* gated runs.

---

## Headline

**Six of the seven reproduce. One (arm G) reproduces with a measured caveat.
Zero refutations.** Every accepted-set mask rule, every fault boundary, every
model fit count and every competing-model fit count came out **numerically
identical** to the M4 result — in several arms including details the M4
write-ups did not put in their headline.

The one genuinely new fact is in arm F: `mov_imm`'s `imm7 == 12` is a **decoder
defect only**. The hardware writes 12 correctly. EXP-0140 explicitly left that
untested.

---

## 1. `device_load` destination rule — REPRODUCED (EXP-0141)

| quantity | G16G (EXP-0141) | **G17P (EXP-0153)** |
|---|---|---|
| `dst_lo` accepted, target r7 | 1 of 4, `v & 3 == 1` | **1 of 4, `v & 3 == 1`** |
| `dst_lo` accepted, target r20 | 1 of 4, `v & 3 == 1` | **1 of 4, `v & 3 == 1`** |
| `dst_ext9` accepted, r7 | 64 of 128, `v & 1 == 1` | **64 of 128, `v & 1 == 1`** |
| `dst_ext9` accepted, r20 | 64 of 128, `v & 1 == 1` | **64 of 128, `v & 1 == 1`** |
| the (`dst_lo`,`dst_ext9`) pair | 64 of 512, `v & 0x181 == 0x81` | **64 of 512, `v & 0x181 == 0x81`** |
| `extmode` accepted | 128 of 256, `v & 0x80 == 0` | **128 of 256, `v & 0x80 == 0`** |
| bit 0 of `extmode` | don't-care (both parities work) | **don't-care — 64 of the 128 accepted values are odd** |
| **R reachable** | **0..63 only; R ≥ 64 silently zeroes** | **0..63 only; 0 of 128 values ≥ 128 accepted, 124 wrong_value** |
| `extmode` 252..255 | reproducible fault, `Caused GPU Hang Error` (raw run11/run12) | **reproducible fault ×3, `kIOGPUCommandBufferCallbackErrorHang`** |
| falsifier `(dst_lo,dst_ext9) = (0,0)` | silent zero → `out0 == 1.5` | **`out0 == 1.5`** |
| falsifier `extmode = 0` vs consumer r7 | fails | **fails** |

Every mask rule is machine-derived and **exactness-checked** (`verdicts.py ::
mask_rule` reports a rule only when it admits exactly the accepted set and
excludes every other value), the same standard EXP-0141 used.

**The emitter rule is now directly established on the documentation target:**

```
device_load destination register R (0 <= R <= 63):
    extmode  = 2*R          (bit 0 free; 2*R+1 works identically)
    dst_lo   = 1
    dst_ext9 = 1
  R >= 64 is NOT REACHABLE through this field: it silently zeroes.
  extmode 252..255 (R = 126, 127) FAULTS -- do not emit.
```

## 2. `falu2` source-class model + the inline float immediate — REPRODUCED (EXP-0138)

| quantity | G16G (EXP-0138) | **G17P (EXP-0153)** |
|---|---|---|
| source-class model fit | 98/98 per run, 294/294 overall | **64/64, and 8/8 at every one of the 8 `mod_lo` values** |
| bit0 ⇒ srcA reads 0.0 | yes | **yes** |
| bits[2:1]: 0 GPR, 1 non-GPR, 2/3 read 0.0, bit2 dominates bit1 | yes | **yes** |
| refuter (`mod_lo=2`, `srcB_reg=2` unbound) | 5.0, not the GPR answer 8.0 | **fired as pre-registered** |
| inline minifloat, `srcB_reg` 64..127 | 10 HW points | **64/64 DENSE — every k in 0..63 matched `m·2⁻⁵` (e=0) / `(8+m)·2^(e−6)`** |
| the ten M4 points k = 0,2,3,31,32,48,56,61,62,63 | 0, 0.0625, 0.09375, 1.875, 2.0, 8.0, 16.0, 26.0, 28.0, 30.0 | **all ten `ok`** |
| non-GPR file index map | our bound `float4` at indices 6..9 | **indices 6..9, values 101/202/303/404** |
| index 10 | ≈1.0, flagged `CARRIER_SPECIFIC` | **≈1.0 — reproduces, and is the arm's single non-`ok` case** |

The dense 64..127 sweep is **stronger than the M4 evidence it revalidates**:
EXP-0138 confirmed ten points, this run confirms all sixty-four.

> **Field rename.** `db.json` split `falu2.mod_lo` into `srcA_class` (bit 0) and
> `srcB_class` (bits[2:1]) after these captures were taken — which is precisely
> the model this arm measures. The evidence maps straight onto the new names and
> covers both fields over their full ranges; see `RESULTS.md` §10.

## 3. The native single-instruction 64-bit integer ADD — REPRODUCED (EXP-0146)

| quantity | G16G (EXP-0146) | **G17P (EXP-0153)** |
|---|---|---|
| `ulong a - b` compiles to | `get_sr, device_load, device_load, iadd2, device_store, stop` | **identical, 60 B, 0 leftover** |
| the `iadd2` bytes | byte0 `0x1f`, byte+7 `0x50` | **`1f015600020800501705` — byte0 `0x1f`, byte+7 `0x50`, byte-identical** |
| after flipping `addsub` | `0x9f…` | **`9f015600020800501705`** |
| exactness | 8 rows, both gated runs, 5/5 in run05 | **12 rows exact, 5/5 repetitions, both gated runs** |

The four boundary rows the dispatch named, all exact on G17P:

| a | b | observed = oracle |
|---|---|---|
| `0x8000000000000000` | `0x8000000000000000` | `0x0` (carry out of bit 63) |
| `0x7FFFFFFFFFFFFFFF` | `0x1` | `0x8000000000000000` |
| `0xFFFFFFFF00000000` | `0x00000000FFFFFFFF` | `0xFFFFFFFFFFFFFFFF` |
| `0xFFFFFFFFFFFFFFFE` | `0x3` | `0x1` (full 64-bit wrap) |

plus the lo→hi carry witness `0x0123456789ABCDEF + 0xFEDCBA98 =
0x0123456888888887`. **One 10-byte instruction performs a complete 64-bit add
with carry on G17P, and Apple's compiler emits five instructions instead.**

## 4. The register-file model — REPRODUCED, in both of its halves (EXP-0112 + EXP-0139)

The M4 claim has two parts that live in **different fields**, and this run
separates them explicitly.

### 4a. `device_load`'s destination register (where EXP-0112 measured it)

| quantity | G16G (EXP-0112 / EXP-0141) | **G17P (EXP-0153, arm A)** |
|---|---|---|
| R = 0..63 | delivered exactly | **all 128 encodings (both parities) accepted** |
| R = 64..112 | silently aliases `r(R mod 64)` | **not reachable through `extmode`: 0 of the ≥128 values accepted** |
| R = 126, 127 (`extmode` 252..255) | **`CMDBUF_ERROR` fault** | **reproducible fault, `…ErrorHang`** |

### 4b. `falu2.srcB_reg` — a second 7-bit register field, swept 0..127 dense

| quantity | G16G | **G17P (EXP-0153, arm D)** |
|---|---|---|
| 64..112 aliasing | `r(R mod 64)` (EXP-0112, on `device_load`) | **CONFIRMED at 49/49 values, including 13 distinct NON-ZERO discriminators: v = 64..76 returned 10.0, 6.5, 8.0, 5.5, 12.0, 14.0, 16.0, 18.0, 5.25, 23.0, 27.0, 31.0, 35.0 — exactly `5.0 + SEED[v−64]`** |
| top bit | HW-tested inert; field is functionally 6-bit (EXP-0099) | **inert: 128/128 `ok`** |
| 126, 127 | *(never measured in this field on M4)* | **do NOT fault — they read 0.0, i.e. `r62`/`r63` unseeded** |

The 126/127 fault is a property of `device_load`'s destination selector, **not
of every 7-bit register field**; §4a reproduces it where EXP-0112 measured it,
and §4b shows the fault does not generalise. That is consistent with M4's own
EXP-0099 (`falu2` register fields are functionally 6-bit) and with EXP-0138
(126/127 are immediates, not faults, in the non-GPR class).

### 4c. `iadd2.dst` — the field where M4 REFUTED the aliasing rule

| quantity | G16G (EXP-0139) | **G17P (EXP-0153)** |
|---|---|---|
| the sum reaches the store's r6 at | `dst` = 12/13 and nowhere below reg 96 | **exactly `dst` = 12, 13** |
| `dst` = 140/141 (reg 70) | did NOT alias to r6 | **did NOT alias — r6 kept its sentinel 99** |
| fault boundary | reg ≥ 96 (`dst` ≥ 192) faults reproducibly | **`dst` 192..255 fault, 64 values, boundary reg = 96** |
| `dst` = 30/31 (reg 15) | carrier artefact (r15 is the store index) | **reproduces as a carrier artefact** |

**Capacity does not differ between the 10-core M4 and the 5-core A18 Pro.** The
addressable-GPR fault boundary is reg 96 on both, the `device_load` destination
ceiling is r63 on both, and `r(R mod 64)` aliasing holds on both. GPU **core
count** is a throughput parameter; the per-thread register file the ISA can
address is unchanged.

## 5. `ibfe`'s opposite out-of-range rules — REPRODUCED (EXP-0139)

| model | G16G fit (EXP-0139) | **G17P fit (EXP-0153)** |
|---|---|---|
| `offset` **LITERAL** (0–31 shift; 32–63 shift the field out, result 0) | **64/64** | **64/64** |
| `offset` mod-32 (the NIR model) | 32/64 | **32/64** |
| `width` **TAKEN MOD 32** | **64/64** | **64/64** |
| `width` literal-clamp-at-32 (EXP-0139's own refuted pre-registration) | 37/64 | **37/64** |

Both competing models score **exactly** what they scored on M4, on the same
inputs. The adversarial second lowering (`o = a >> b`, a different compilation
of the same instruction) behaves as a live field there too: only offsets 4 and
5 leave the output unchanged, 2 silently zero and 60 change the value.

## 6. `mov_imm` is 7-bit — REPRODUCED, and one open M4 question ANSWERED (EXP-0140)

| quantity | G16G (EXP-0140) | **G17P (EXP-0153)** |
|---|---|---|
| `imm7` 0..127 | `hardware-run` | **128/128 `ok`, poisoned read-back** |
| `imm_top = 1`, **padded** | destination KEEPS its previous value (7) — a non-write, not a silent zero | **`out0 == 7` at every one of imm 128, 129, 140, 200, 255** |
| `imm_top = 1`, **unpadded** | the following 2-byte instruction is consumed; the read-back store addresses the wrong word | **the read-back stores DO NOT EXECUTE. In isolation under the GPU lease (5 repetitions each) the buffer comes back poison everywhere except `out[12]`, the pre-test sentinel — see below** |
| `imm7 == 12` tokenization | does not tokenize (`byte+1 == 0x0C` looks like the 4-byte `0x?c` preamble) | **still does not tokenize — `rt: false` — a `db.json` property, target-independent** |
| `imm7 == 12` **on hardware** | **NOT TESTED** (EXP-0140 said so explicitly) | **the hardware writes 12 correctly: `out0 == 12`, `outcome: ok`** |

The padded/unpadded pair is the decisive control and it reproduces: the padded
form proves a **non-write**, so the immediate really is 7 bits.

The unpadded arm needed the revalidation pass to read correctly, and it is this
experiment's best illustration of why FIELD-SWEEP-PROTOCOL §7.1 exists. In
**both** unlocked gated runs all five unpadded immediates were recorded as
reproducible `fault`s (majority-of-3 each, and the two runs agreed). Re-run in
isolation **under the GPU lease, 5 repetitions each**, only imm 128 is a
reproducible fault; 140, 200 and 255 are `wrong_value` 5/5 and 129 is 2 fault /
3 `wrong_value`. Cross-run agreement alone did **not** defeat sustained sibling
GPU load — only isolation did.

And the isolated observation is sharper than M4's. The read-back buffer comes
back with **every word still holding its poison except `out[12]`**, proved from
the committed record without re-running: the case's `sha_0` is
`564e3165d8085121`, and re-hashing "all 16 poison words, with `out[12]` replaced
by `0x41D00000` (26.0f)" reproduces it exactly, while all-poison and the other
three candidate words do not. `out[12]` is the **pre-test sentinel**, written
before the `mov_imm` under test through a `falu2i` path that does not involve
it. So on G17P: the program ran, and **neither of the two following
`device_store`s executed at all** — a total instruction-stream desync, where M4
observed a store landing on the wrong word. Same conclusion (`imm_top` changes
the instruction's length, so the immediate is 7 bits, not 8); a cleaner
signature.

**New fact for the ISA database (`db_defects`):** `mov_imm.imm7 = 12` is a pure
**decoder** defect. An emitter may safely emit it; our tokenizer must be fixed.

## 7. Instruction-length rule corrections — REPRODUCED with a measured caveat (EXP-0148)

Both numbers below come from **one tokenizer run of one `db.json`**
(`f5db942f…`, the post-EXP-0148 database), so the comparison is of corpora, not
of tools.

| corpus | files | clean | leftover bytes | of total |
|---|---|---|---|---|
| **M4, full EXP-0148 corpus** (the published reference) | 1080 | **832** | **389 368** | 587 586 |
| M4, the 582-program subset whose MSL source is committed | 582 | 420 (72.2 %) | 211 238 (66.0 %) | 319 894 |
| **G17P, the same 582 sources recompiled on the A18 Pro** | 582 | **412 (70.8 %)** | **224 830 (67.8 %)** | 331 596 |

The M4 full-corpus row **reproduces EXP-0148's post-patch figures exactly**
(832 clean / 389 368 leftover), which validates the tokenizer before it is
pointed at G17P.

The decisive control is the byte-identity split:

| | files | clean | leftover bytes |
|---|---|---|---|
| the 476 programs that compile **byte-identically** on both targets | 476 | **371 on M4 = 371 on G17P** | **124 982 on M4 = 124 982 on G17P** |
| the 106 programs whose **bytes differ** | 106 | 49 on M4 vs 41 on G17P | 86 256 vs 99 848 |

**Every byte of the difference comes from the 106 files whose compiler output
differs — none from the length rule behaving differently.** On identical bytes
the corrected rules tokenize identically. H-G1 reproduces.

### H-G2, the byte-identity question, with its confound stated

**476 of 582 (81.8 %) of the own-MSL corpus compiles byte-identically on M4 and
A18 Pro.** Of the 106 that differ, 42 are the same length (13 differ in only 2
bytes, 11 in 8), and 64 differ in length — sometimes wildly
(`controlflow__call_fptr_table`: 192 B on M4, 4 B on G17P;
`bf16_matrix__bf16_transcend`: 364 B vs 1182 B). By stage: 71 compute, 29
fragment, 6 vertex; concentrated in `half`, `frag_output`, `texture_sample`,
`derivatives_misc`, `raytracing`, `tessellation`.

**This is not evidence of an ISA difference, and must not be read as one.** The
two corpora were compiled by **different toolchains**: the M4 hex was built on
macOS 26.6.2 build **25G82**, the G17P hex on macOS 26.6 build **25G5043d**.
Differences of this shape and size — a whole function inlined away, a
transcendental expanded differently — are what a compiler revision produces.
Separating "compiler revision" from "target" needs the same OS build on both
machines and is out of this experiment's scope; it is recorded as an open
question, not resolved.

---

## Scorecard

| # | finding | M4 source | verdict on G17P |
|---|---|---|---|
| 1 | `device_load` destination rule | EXP-0141 | **REPRODUCED** (6 mask rules identical, incl. the 252–255 fault set) |
| 2 | `falu2` source class + inline minifloat | EXP-0138 | **REPRODUCED**, and strengthened 10 → 64 dense points |
| 3 | native 64-bit integer ADD | EXP-0146 | **REPRODUCED** (byte-identical anchor, 12/12 rows, 5/5) |
| 4 | register-file model | EXP-0112 + EXP-0139 | **REPRODUCED** in all three parts; no capacity difference |
| 5 | `ibfe` offset literal / width mod-32 | EXP-0139 | **REPRODUCED**, competing-model fits identical (32/64, 37/64) |
| 6 | `mov_imm` 7-bit / `imm_top` / `imm7 == 12` | EXP-0140 | **REPRODUCED**, plus one open M4 question answered |
| 7 | instruction-length corrections | EXP-0148 | **REPRODUCED** on byte-identical code; corpus deltas are compiler-revision, not rule |

**Refuted: 0 of 7.** The one live G16G↔G17P divergence in the repository
(`tg_addr_compute`) is **not** in this set and is untouched by these results.

### A methodological result worth carrying forward

Two independent gated runs agreeing **1958/1958** still recorded 4 cases as
reproducible `fault`s that are not faults. Each had passed majority-of-3 inside
its own run, and both runs agreed — yet in isolation under the lease they are
`wrong_value` 5/5. Cross-run agreement is **not** a substitute for isolation
when the contaminating load is sustained rather than bursty. The
FIELD-SWEEP-PROTOCOL §7.1 re-run is what caught it; the poisoned read-back is
what made the corrected reading provable from the committed record alone.
