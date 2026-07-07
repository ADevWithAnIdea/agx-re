# RT-5 RESULTS — falsification of the texture / subgroup / matrix / RT / fragment ISA

All results are **HW-validated** (spliced bytes run on the real A18 Pro GPU, macOS 26.6).
Values are verbatim runtime read-backs; raw logs in `raw/`. Compiles used `--no-fast-math`.

## Verdict summary

| Family | Field under test | Verdict |
|---|---|---|
| **Matrix** `0xcf` | A=+5, B=+6, C=+7, dst=+8, accum=+11 bit0 | **CONFIRMED** (all splice-validated) |
| **SIMD reduce** `0xbf/0x3f` | byte0 bit7 add/xor; byte+1 op | **CONFIRMED** (op-select); byte+1 doc values are the LOW NIBBLE only |
| **SIMD reduce** dtype byte+7 | int-reduce=0x03, int-excl-scan=0x0b | **DISCREPANCY** — real reduce=**0x01**, excl-scan=**0x09** (=incl) |
| **SIMD shuffle** `0x47/0xc7` | byte+6 lane<<1; byte0 dir; byte+1 simd/quad | **CONFIRMED** (semantics) |
| **SIMD shuffle** decode | DB match `byte+2==0x56` | **DISCREPANCY (decode gap)** — real op has byte+2=**0x54** ⇒ does NOT decode |
| **SIMD ballot** `0x17` | DB match `byte+1==0x07` | **DISCREPANCY (mis-decode)** — real op byte+1=**0x17** ⇒ decodes as `unpack_convert` |
| **Texture** sampler-slot op+5 | plain index | **CONFIRMED** (0x00=s0, 0x01=s1) |
| **Texture** variant op+2 | 0x17 = read | **CONFIRMED** |
| **Texture** gather comp+3 | 0xa4/ac/b4/bc = R/G/B/A | **CONFIRMED** (exact texel channels) |
| **Texture** write `0xd7` | writes land where claimed; byte+3=data reg | **CONFIRMED** |
| **Texture** slot op+4 | "texture-slot = op+4 (bit0x80=index)" | **DISCREPANCY** — low bits inert; only bit7 (2-way); can't reach a 3rd texture |
| **Texture** filtered op+6 | "0x10 filtered / 0x00 read" | **DISCREPANCY** — splice 0x10↔0x00 is a no-op (filter is sampler-controlled) |
| **Fragment** `iter` byte+5 | varying slot (slot<<1) | **CONFIRMED** (walked pixel.r through vc.x/y/z/w) |
| **Fragment** `frag_color_store` | byte+3 src reg; byte+5 RT index | **CONFIRMED** (src); byte+5 consistent (single-RT) |
| **RT** `rt_intersect` `0xea` | op is dedicated & load-bearing | **CONFIRMED** (0xea sub-op corrupt → GPU hang) |
| **RT** traverse sub-fields | byte+4 AS-select 0x8b/0x1b/0xbb; byte0 result-reg; byte+2 mode | **DISCREPANCY / UNVERIFIED** — all splice-**inert** (identical hit); doc's "0x8b→0x1b flips primitive→instance" not reproduced |
| **Census** (large shaders) | big-frag 100%; big-compute gaps | fragment tokenizes clean; compute has real 0x47/0xc7 (shuffle) + 0x1b/0x3b gaps |

---

## 4. Matrix `0xcf` — CONFIRMED (`raw/matrix_test.log`)
Op `cf 02 56 02 00 04 08 09 d4 43 24 01` at `_agc.main+0xba`. Baseline D=A·B+C=8ij+1000:
```
1000 1008 1016 ...    (row i, col j = 1000 + 8ij)  ✓
```
- **byte+5 (A/left) → 0x08 (=B's reg):** D = B·B+C = 28j+1000 (every row `1000 1028 1056 …`). ✓
- **byte+6 (B/right) → 0x04 (=A's reg):** D = A·A+C = 28i+1000 (every col constant by row). ✓
- **swap +5↔+6:** D = B·A+C = **140+1000 = 1140 everywhere** (matmul non-commutative). ✓
- **byte+11 bit0 (accum) 0x01→0x00:** D = A·B only = 8ij, **the +1000 drops**. ✓
- **byte+7 (C-src) 0x09→0x04, byte+8 (dst) 0xd4→0xd6:** both load-bearing (result changes/garbles).
→ operand map **exactly as documented**. Matrix is the strongest CONFIRMED family.

## 3. Subgroup / quad (`raw/subgroup_test.log`, `raw/scan_test.log`, `raw/decode_gaps.log`)

**simd_reduce** op `bf 11 54 00 02 04 14 01` (simd_sum, lanes 0..31 → 496):
- **byte0 0xbf→0x3f (bit7):** 496 → **0** = simd_xor(0..31). ✓ add/xor select confirmed.
- **byte+1 0x11→0x10:** → 31 = OR;  **→0x12:** 31 = max;  **→0x13:** 31 = umax. ✓
  ⇒ the op is the **low nibble** of byte+1 (0=and/or, 1=xor/add, 2=max/min, 3=umax). The doc's
  `op` enum lists `0x00/0x01/0x02…`; the real byte for a 32-bit int reduce is **0x1X** — the high
  nibble is a width/type field the doc omits. (Not a decode break; `op` field just shows raw.)
- **byte+7 dtype:** real int-reduce = **0x01** (doc claims 0x03); splicing to 0x03/0x07 breaks the
  broadcast (only lane 0 keeps 496). **DISCREPANCY.**

**Scan** (`raw/scan_test.log`): inclusive `bf…14 09` → 0,1,3,6,10,… ✓ (byte+7=0x09 matches doc).
Exclusive `simd_prefix_exclusive_sum` compiles to `bf 11 54 00 02 04 14 **09**` (byte+7=0x09, same
as inclusive; differs only at byte+3=0x02 vs 0x03 + surrounding ALU). The doc's **byte+7=0x0b for
int exclusive-scan is wrong** — real excl-scan = 0x09. **DISCREPANCY.**

**simd_shuffle** broadcast `47 04 54 00 02 00 06 2c 04 00` (broadcast lane 3 of v=lane·10+5 → 35):
- **byte+6 (lane<<1):** 0x06→0x00 = lane0 (5); 0x0a = lane5 (55); 0x0e = lane7 (75). ✓ lane<<1.
- **byte0 0x47→0xc7:** broadcast → **shuffle_xor(v,3)**: `35 25 15 5 75 …` = (lane^3)·10+5. ✓ dir bit.
- **byte+1 0x04→0x00:** simd → **quad** broadcast (lane 3 within each 4-lane quad). ✓
- **simd_shuffle_xor** `c7 …`, byte+6 = mask<<1 (0x02→0x04→0x08 = xor 1/2/4). ✓
- **DECODE GAP:** the real broadcast/xor ops carry **byte+2 = 0x54**, but the DB `simd_shuffle`
  descriptor matches on `byte+2 == 0x56`, so `disasm(47 04 54 …)` → **`ValueError: no descriptor
  matches`** (and `c7 04 54 …` likewise). The EXP-0038 "cache-bit" relaxation was applied to the
  reduce family but **not** to shuffle; it needs the same `{0x54,0x56}` widening. Corroborated by
  the census (0x47/0xc7 appear undecoded in `big_compute`).

**simd_ballot** `17 17 54 00 02 04 14 18 22 0c` — `simd_ballot(lane<5)` → **0x1F** (correct). But
byte+1 = **0x17**, whereas the DB `simd_ballot` matches `byte+1==0x07`; so `disasm(17 17 54 …)`
→ **`unpack_convert`** (which only gates on byte+2). A real, HW-correct ballot **mis-decodes**.
**DISCREPANCY (silent mis-decode).**

## 1–2. Texture (`raw/tex_map.log`, `tex_slotmap.log`, `tex_samp_test.log`, `tex_variant_test.log`, `tex_write_test.log`)

**Sampler slot op+5 — CONFIRMED.** t0 = 2×1 [red|blue], sample at (0.5,0.5). Baseline (s0=nearest)
→ (0,0,1,1) blue; splice sample#0 **op+5 0x00→0x01** → **(0.5,0,0.5,1)** = linear avg of red+blue
(=s1). 0x02/0x03 → zeros (unbound). op+5 is a clean plain index.

**Variant op+2 — CONFIRMED.** On a 2×2 [R,G/B,W] linear-sampled to (0.5,0.5,0.5,1):
**op+2 0x09→0x17** → **(1,0,0,1)** = read of texel(0,0) (unfiltered). Read variant works.

**Gather comp+3 — CONFIRMED (exact).** Splicing companion+3:
`0xa4`→(0,1,0,1)=gather.R, `0xac`→(0,1,1,0)=gather.G, `0xb4`→(1,1,0,0)=gather.B, `0xbc`→(1,1,1,1)=gather.A —
each is the single channel of the 4 texels in Metal gather order. Matches the documented enum exactly.

**Texture WRITE `0xd7` — CONFIRMED.** `img.write(v0,(0,0)); img.write(v1,(1,0))` with
v0=(.1,.2,.3,.4), v1=(.9,.8,.7,.6). Read-back = **(.1,.2,.3,.4)** @ texel(0,0), **(.9,.8,.7,.6)** @
texel(1,0) — writes land exactly where claimed. Splicing the first op **byte+3 0x00→0x02** makes it
emit **(.9,.8,.7,.6)** (v1's register) ⇒ **byte+3 = data source register** confirmed.

**Texture slot op+4 — DISCREPANCY.** 3 solid textures (t0=red, t1=green, t2=blue), read (no sampler).
Splicing sample#0's **op+4**:
```
0x00,0x01,0x02,0x03 -> RED   (t0)   <- low bits INERT
0x80,0x81,0x82,0x83 -> GREEN (t1)   <- only bit7 matters, and only 2-way
```
The low bits do **not** index the texture, and **t2 is unreachable via op+4** (t2 differs from t0
in companion+3=0xb8 + op+1, not op+4). The three bound textures differ across op+4-bit7 / companion+3 /
op+1 — the texture selection is **not a clean single-byte immediate index at op+4** as documented.
(The doc's "splice tex1→tex0 changed the pixel" reproduces only as the op+4-bit7 2-texture flip.)
*Caveat: this used **direct** `setTexture:atIndex:` binding; the doc's claim is nominally about the
Tier-2 argument-buffer path, which this test did not exercise. Under direct binding op+4 is not an index.*

**Filtered op+6 — DISCREPANCY.** Splicing op+6 **0x10↔0x00↔0x20** on a linear sample was a **no-op**
(still (0.5,0.5,0.5,1)). Filtering is controlled by the **sampler** (proven via op+5), not op+6.
The doc's "filtered = op+6 (0x10 sample / 0x00 gather-read)" is not supported by a splice.

## 6. Fragment (`raw/render_test.log`)
`render_vary`: varying vc=(0.20,0.40,0.60,0.80) → 4 `iter` ops (slots 0x2/0x4/0x6/0x8) + a
W-denominator iter (mode=0x04). Baseline pixel = (0.2,0.4,0.6,0.8).
- **`iter` byte+5 (varying slot):** splicing the red-channel iter 0x02→0x04→0x06→0x08 walks the
  pixel red channel **0.2 → 0.4 → 0.6 → 0.8** (reads vc.y/z/w). **CONFIRMED — byte+5 = slot<<1.**
- **`iter` byte+6 (mode):** splice 0x00→0x04/0x02 was a no-op here (varying is near-constant ⇒ mode
  invisible). Not contradicted, not confirmed.
- **`frag_color_store` byte+3 (src reg):** 0x00→0x02/0x06 → pixel **(0,0,0,0)** (wrong reg). CONFIRMED load-bearing.
- **`frag_color_store` byte+5 (RT index):** 0x00→0x02 → RT0 stays clear (0,0,0,0), i.e. the store was
  **diverted off RT0** — consistent with byte+5 = RT index (single-RT setup; positive MRT confirmation
  would need a multi-target runner).

## 5. Ray tracing (`raw/rt_test.log`, `raw/rt_controls.log`)
Built a primitive AS (triangle at z=3). Baseline ray (0.2,0.2,0)+z → **hit dist=3, prim=0, bary=0.2**;
apex ray (0.8,0.8,0) → **miss (inf)**. Two `rt_intersect` ops: traverse `e4 ea 90 a6 8b …` @+0x54
(byte+4=0x8b primitive AS), result-read `04 ea 10 26 63 80 26 9f` @+0x58c.

**Controls prove splicing is effective** (`raw/rt_controls.log`):
- traverse **byte+1 0xea→0x00** → **GPU hang** (the intersect sub-op is load-bearing);
- result-read **byte+1 0xea→0x00** → distance **3 → 2.984** (the result-read op is load-bearing);
- output store byte+8→0x00 → all-zero output.

**But every documented traverse *sub-field* was splice-INERT** — identical correct hit `[1 3 0 0.2]` for:
- **byte+4 AS-select 0x8b → 0x1b (instance) / 0xbb (motion) / 0x00** — no change. The doc's specific
  claim *"byte+4 0x8b→0x1b flips primitive→instance AS (HW-validated end-to-end)"* is **not reproduced**.
- **byte0 result-reg 0xe4 → 0x04 / 0x14** — no change.
- **byte+2 mode 0x90 → 0x10 (dyn) / 0xd0 (+fn-table)** — no change.
- **byte+3 ray/param reg 0xa6 → 0x00** — no change.

⇒ `rt_intersect` **is** a dedicated, load-bearing op, but its operand SUB-FIELDS (marked "byte-diff-
inferred" in the doc) do **not** survive an adversarial splice on the single-primitive
`intersection_query` path: they are byte-diff correlations, not splice-validated semantics.
**DISCREPANCY / UNVERIFIED.** *(Caveat: only a primitive AS was built; the instance/motion paths that
would exercise 0x1b/0xbb were not constructed, so this falsifies the splice-effect claim, not the
existence of an instance-AS encoding somewhere.)*

## 7. Large-shader census (`raw/census.log`)
- **`big_frag` fragment: 214 B → 100% tokenized, 0 undecoded.** MRT (3 RTs), 3 textures, 2 samplers,
  flat+smooth varyings all decode.
- **`big_compute`: ~78%** (figure inflated by 2-byte resync noise). Genuine undecoded leaders include
  **0x47/0xc7** (the simd_shuffle gap above), **0x1b** (ray/reg-marshalling-family, ×4), **0x3b**
  (shift-prep, ×3), 0x5b, 0x73, 0xf0. The **simd_ballot mis-decode is silent** — it counts as
  "decoded" but resolves to `unpack_convert`, so coverage % understates the DB error rate.
- `big_frag` vertex ~80% with 0x40/0x82/0xa2/0x23/0x26 coordinate-math leaders (known follow-ups).

## Bottom line for the docs
Strongly upheld: **matrix operand map, simd reduce/shuffle op-select semantics, sampler-slot, texture
read/gather/write, fragment iter varying-slot.** Needs correction: **(a)** simd_shuffle decode gate
(0x54 vs 0x56) and simd_ballot match byte (0x17 vs 0x07) — both cause real compiled ops to
mis-/non-decode; **(b)** simd_reduce byte+7 dtype values (reduce 0x01 not 0x03; excl-scan 0x09 not
0x0b); **(c)** texture-slot op+4 is not a plain index and op+6 is not the filter selector (under
direct binding); **(d)** the `rt_intersect` traverse sub-fields are inferred, not splice-load-bearing.
