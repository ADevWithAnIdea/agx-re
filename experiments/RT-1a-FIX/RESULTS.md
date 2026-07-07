# RT-1a-FIX RESULTS — the RT-1a corrections, each independently HW-re-validated then applied

All five items were **independently splice-and-observe re-validated on the real A18 Pro GPU**
(values below are verbatim runtime outputs; raw logs in `raw/`). **RT-1a reproduced on all five** —
no finding was wrong. Each fix was then applied to `tools/agx-isa/isadb.py` (→ `db.json`) and the
`docs/isa/` prose/tables.

## Verdict summary

| # | RT-1a claim | Independent re-validation | Fix applied |
|---|---|---|---|
| 1 | mem-op index register = **byte+5** (not +1/+6); +6 inert; +1 = space; immediate offset ~+9bit7/+10/+11 | **REPRODUCED (all parts)** | `device_load`/`device_store`: `count`→`index_reg`, `+6`→`inert6`, added `idx_off` |
| 2 | iadd2 HW `0x9f`=ADD, `0x1f`=SUBTRACT (DB inverted) | **REPRODUCED** | `iadd2` field `srcA_neg`→`addsub` {1:iadd,0:isub}; semantics fixed |
| 3 | `a+uniform` reads a REAL uniform; DB mis-decodes it as a `falu2i` tiny immediate | **REPRODUCED** | added `falu2_uni` descriptor; disambiguation = byte+1 exp-nibble under bit39 |
| 4 | byte0 `0x60` + byte+2=`0x18` undecoded → tokenizer halts | **REPRODUCED (both halt)** | added `spill_frame_marker` (0x60, len 4) + widened `falu_acc` to byte+2∈{0x18,0x38} |
| 5 | `imm_decode()` unguarded for out-of-domain input | (code review) | guarded to e≥8 + byte range (raises for the uniform overload) |

---

## Item 1 — memory-op index register = byte+5 (RE-VALIDATED)

`bank.metal` loads `out=a[i0]`, i0..i3 from `idxbuf`. Filled `a[j]=100·j+3`, `idxbuf={40,3,77,12}`
(so r0=i0=40, r1=i1=3, r2=i2=77, r3=i3=12). Swept one byte of the `a[i0]` load (main+0x1c):

- **byte+5 = index register (CONFIRMED).** `0x00→a[40]=4003, 0x01→a[3]=303, 0x02→a[77]=7703,
  0x03→a[12]=1203, 0x04→a[0], 0x05→a[0]` — reads the *contents* of r0/r1/r2/r3 as the index.
  `0x80→a[40], 0x81→a[3], 0x82→a[77]` — bit7 (`0x80`, the compiler's scalar flag) is a don't-care
  for the register selection; the low bits are the register number. **Not** `(reg<<1)|size` (0x01→r1,
  not r0). → byte+5 selects the index GPR. (RT-1a's "byte+5 is mislabeled count" confirmed: the
  N-vector confound is real; true width lives at +8/+12.)
- **byte+6 = INERT (CONFIRMED).** `0x00..0xff` → out constant `a[40]=4003`. Not an address byte.
- **byte+1 = address space (CONFIRMED).** `0x00→a[40]` (device), `0x01/0x02/0x03→0` (threadgroup/
  uninitialized), `0x04→a[40]`. It toggles the space; it is **not** the index register.
- **Immediate index-offset field (CONFIRMED).** `byte+9 bit7`: `0x01→a[40]`, `0x81→a[41]` (+1).
  `byte+10`: `0x00→a[40], 0x01→a[42] (+2), 0x02→a[44] (+4), 0x08→a[56] (+16)` (= +2·v). `byte+11`
  (with a 2048-entry a[]): `0x40→a[40], 0x41→a[552] (+512), 0x42→a[1064] (+1024)` (= +512·v). So an
  additive **11-bit element offset** starting at byte+9 bit7 exists (the compiler leaves it 0).

**Fix:** `device_load`/`device_store` descriptors — `count`→`index_reg` (+5), `addr_lo`→`inert6`
(+6), split the tail into `tail9lo`/`idx_off`(+9bit7/+10/+11)/`tail11hi`. README memory table +
addressing-model prose updated (index = byte+5, +6 inert, immediate offset exists). Raw: `raw/mem_index.log`.

## Item 2 — iadd2 add/sub polarity (RE-VALIDATED)

`rt1a_iaddbank.metal` exposes a clean `out=p.x+p.y` iadd2 at main+0x34 (byte0 `0x9f`). Fed
p.x=10, p.y=20. Spliced byte0:

```
byte0=0x9f -> out=30    => ADD (10+20)
byte0=0x1f -> out=-10   => SUBTRACT (10-20)
```

Confirms **`0x9f`=ADD, `0x1f`=SUBTRACT** — the DB previously matched the canonical iadd on `0x1f`
with `srcA_neg=0` and semantics `d=srcA+srcB` although `0x1f` subtracts. **Fix:** iadd2 field
`srcA_neg`→`addsub` (opcode-select enum `1`=iadd/`0`=isub), semantics corrected; imad's bit7 renamed
`b0bit7` (multiply polarity not separately characterized). Raw: `raw/iadd_polarity.log`.

## Item 3 — float uniform-register source (RE-VALIDATED)

- **A) reads a real uniform:** `rt1a_uni.metal` `a[gid]+p.k` (a=10): `p.k=7→17, 100→110, 0.5→10.5,
  2→12` — tracks the *runtime* uniform (an immediate cannot change with the bound buffer).
- **B) disambiguation:** `cadd` (`a+1.0`, no uniform) byte+1=`0xb1` (exp=11 ≥ 8) → `out=11` (minifloat).
  Splice byte+1→`0x0d` (exp=0 < 8) → `out=10` = a+0 (reads an **unbound uniform register = 0**),
  **NOT** `a+imm_decode(0x0d)≈10.0009`. So byte+1's exponent nibble (= instr bit15) splits the two
  srcB overloads under bit39: **exp≥8 = minifloat immediate, exp<8 = uniform-register source.**
- **C) index:** `uni_multi.metal` (8 uniforms) — byte+1=`0x0d` reads k0; other low-exp values read
  unrelated live uniforms (mostly 0). Uniform index = byte+1 as `(ureg<<1)|size`.

**Fix:** added `falu2_uni` (match `[0:4]==0x9, bit39==1, bit15==0]`); `falu2i` (bit15==1) still decodes
minifloats. `090d140180c0` now → `falu2_uni fadd` (was `falu2i` with bogus imm). Raw: `raw/uniform_src.log`.

## Item 4 — undecoded groups (RE-VALIDATED)

- **byte0 `0x60`** (`60 00 00 00`, right after entry get_sr in the spilling `big` kernel): had no
  length rule → tokenizer halted. Re-validation: with length 4 the following 10-byte iadd2 aligns;
  splicing byte0/+1/+2 is a **no-op** on the output (out=4294966408 unchanged), byte+3→`0xff`
  **faults** (its live last byte). → 4-byte spill/frame-setup marker. **Fix:** `spill_frame_marker`
  descriptor + length rule `0x60→4`.
- **byte0 `0x09` / byte+2=`0x18`** (`19 0b 18 09`, in falubank's `a2+…+a7` reduction): length rule
  gave 4 but no descriptor matched → decode raised, dumping 40 bytes. Re-validation: it is the
  compact float accumulate — splicing byte+2 `0x18↔0x38` leaves the reduction result unchanged
  (out2=33), and redirecting the final 0x18 op's dst zeroes out2 (load-bearing add). **Fix:** widened
  `falu_acc` match to byte+2∈{0x18,0x38} (added a `cache` field for the 0x20 hint bit). falubank now
  tokenizes CLEAN (0 leftover); big's prefix tokenizes CLEAN. Raw: `raw/undecoded.log`.

## Item 5 — guard imm_decode()

`imm_decode(b1, sign)` now raises for `b1` out of `0..255` and for exponent `e<8` (the uniform-source
overload, not an immediate) instead of silently extrapolating the minifloat formula into a bogus tiny
value. The HW-validated e≥8 range is unchanged (round-trip test D still green). `raw/verify_fixes.log`.

---

## Deliverable state

- **Descriptor count:** 75 → **77** (+`falu2_uni`, +`spill_frame_marker`).
- **Round-trip test:** `tools/agx-isa/roundtrip_test.py` → **ALL PASS (282 checks, 0 fail)** — added 6
  REAL_INSTRS vectors (falu2_uni, falu_acc-0x18, spill_frame_marker, device_load-index, iadd/isub) and
  an isub SYNTH vector; renamed the iadd2 SYNTH field.
- **Census** (`experiments/EXP-0036-consolidation-census` corpus, 1247 unique tokens):
  named **926→961 (72.0%→77.1%)**, byte coverage **81.8%→88.0%** (8894/10110). `0x60` and `0x18`
  moved from undecoded to decoded. `raw/census_summary.log`.
- **Regenerated:** `docs/isa/encoding-tables.md` (77 descriptors, 0 in Other), `docs/isa/agx3.xml`
  (77, parses OK). **Prose updated:** `docs/isa/README.md` (status line, memory table, iadd2 polarity,
  uniform source, immediate offset).

## Still uncertain
- **byte0 `0x60`** exact semantics (spill/scratch-frame vs occupancy setup) — only length + "byte+3
  live, rest inert" are HW-pinned; the field meanings are a follow-up.
- **Uniform index bit-layout** within byte+1 (only k0=`0x0d` cleanly mapped; the exact `(ureg<<1)|size`
  split is inferred from convention, not exhaustively swept — the other uniforms were dead in the test
  kernel so read 0).
- iadd2/imad **srcA/srcB register** bit-packing in the tail (unchanged from EXP-0007: located, not fully
  bit-decoded) and imad's byte0 bit7 polarity for multiply.
