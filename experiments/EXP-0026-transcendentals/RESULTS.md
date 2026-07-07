# EXP-0026 Results — transcendental / special-function lowering (HW-validated)

Clean-room category: **OWN-SHADER + HW-PROBE** (+ PUBLIC for the applegpu *shape*). Every byte
inspected / spliced / executed is the compiled form of MSL we wrote. No Apple binary was
disassembled. Device: Apple A18 Pro / G17P, macOS 26.6 (25G5043d), Metal 4 / Apple9.

## TL;DR
- **~60 kernels; ~700 HW dispatches; 0 reboots, 0 faults.**
- Two distinct hardware mechanisms:
  1. A **special-function unit (SFU)** — the EXP-0013 `fspecial` group (byte0 `0x2f/0xaf`, 10 B) —
     that computes **rcp, rsqrt, sqrt, exp2, log2, round** as *single ops* (~0–1 ULP). Fast-math
     emits these directly. exp/log/pow/div compose them.
  2. A low-precision **estimate seed op** (byte0 `0x29`, 6 B) — **~7.5–8.0 mantissa bits** — that
     seeds the software **Newton-Raphson** refinement used for *correctly-rounded* (precise) `1/x`,
     `rsqrt`, `sqrt`, `a/b`.
- `tools/agx-isa`: `fspecial` descriptor **expanded** (full 2×3 SFU function table) + **new
  `fspecial_est`** descriptor; `db.json` regenerated; `roundtrip_test.py` +9 real instrs, +5 whole
  programs, +4 synth → **ALL PASS**.

---

## 1. The estimate op(s) — `0x29`, and its precision (task 1)
The precise (non-fast-math) `1/x`, `rsqrt`, `sqrt` lowerings **begin** with a single low-precision
hardware estimate, then refine it. The estimate is a **distinct opcode**:

```
byte0 0x29 | byte+1 0x81 | byte+2 0x25 | byte+3 SUBOP | byte+4 0x00 | byte+5 0xc2     (6 bytes)
```
- byte0 `0x29` (low nibble 9 → shares the 6-byte float-ALU length; high nibble = falu2-style dst).
- byte+2 == `0x25` is the **estimate discriminator** (real `fmul` has byte+2 `0x1d`; this bit-5-set
  value is what tells the estimate apart from an ordinary float ALU op).
- **byte+3 = function (the only "sibling" selector — one opcode, a sub-field, not several opcodes):**

  | byte+3 | estimate | seen in |
  |---|---|---|
  | `0x09` | **reciprocal** (~1/x)      | precise `1.0/x` |
  | `0x0b` | **reciprocal-sqrt** (~1/√x) | precise `rsqrt` |
  | `0x0d` | **sqrt** (~√x)             | precise `sqrt`  |

**Precision (HW-measured, `raw/estimate_precision.txt`).** We redirected the precise kernel's final
`device_store` to read the register that (under multi-lane dispatch) holds the pre-refinement
estimate and swept `x` densely over one mantissa period, reading the raw seed and comparing to the
true function:

| estimate | worst-case relative error | good mantissa bits |
|---|---|---|
| reciprocal (0x09) | 3.83e-3 (≈ 2⁻⁸·⁰) | **~8.0** |
| rsqrt (0x0b)      | 4.28e-3 (≈ 2⁻⁷·⁹) | **~7.9** |
| sqrt (0x0d)       | 5.44e-3 (≈ 2⁻⁷·⁵) | **~7.5** |

So all three are **≈ 8-bit seeds** (worst-case rel-err ~2⁻⁷·⁵…2⁻⁸). This is the classic
single-table hardware reciprocal seed; 2 Newton-Raphson iterations (8 → 16 → ≥24 correct bits) then
reach full fp32. (Raw per-register evidence in `raw/estimate_regsweep.txt`: in precise `1/x`, reg7
holds the coarse `1/x` seed — e.g. est(2)=0.5026, est(3)=0.3320, est(4)=0.2516 — while ~30 other
registers hold the fully-refined result.)

The estimate op appears **only** in the precise path. Under fast-math the compiler uses the accurate
single-op SFU (below) instead of estimate+NR.

## 2. rcp / rsqrt / sqrt lowering (task 2)

### Fast-math (default) — one SFU op each
| function | `_agc.main` op | decode |
|---|---|---|
| `1/x`    | `af 00 56 00 02 00 10 48 20 00` | fspecial, byte0 `0xaf`, byte+1 `0x00` = **rcp** |
| `rsqrt`  | `af 01 56 00 02 00 b0 40 00 00` | fspecial, byte0 `0xaf`, byte+1 `0x01` = **rsqrt** |
| `sqrt`   | `2f 01 56 04 03 00 92 40 00 00` (+ a small fixup op) | fspecial, byte0 `0x2f`, byte+1 `0x01` = **sqrt** |

Sequence: `get_sr ; device_load x ; <SFU op> ; device_store`. HW accuracy: rcp/rsqrt **0 ULP** on
nice inputs, sqrt **~1 ULP** (`raw/accuracy.txt`).

### Precise (`--no-fast-math` / `metal::precise::`) — estimate + Newton-Raphson
Sequence shape (HW-confirmed; the exact scheduled instruction list is the compiler's and is **not**
transcribed here — a backend writes its own NR): `get_sr ; load x ; fspecial_est(x) → y0 ;
{ Newton-Raphson iterations built from fma/fmul } ; final round ; store`. The seed is the `0x29`
estimate above (~8 bits); two NR iterations plus rounding give a correctly-rounded fp32 result
(`raw/disasm_precise.txt`, e.g. precise `1/x` = 130 B). Standard NR recurrences (textbook, not
Apple's code): reciprocal `y ← y·(2 − x·y)`; rsqrt `y ← y·(1.5 − 0.5·x·y²)`; `sqrt(x) = x·rsqrt(x)`
with a final correction. HW accuracy: precise rcp/rsqrt/sqrt = **0 ULP** on our samples.

> Note: `metal::precise::sqrt` forces the correctly-rounded NR path even when the shader is compiled
> with fast-math (0 ULP), whereas plain `sqrt` under fast-math is the ~1-ULP single SFU op.

## 3. sin / cos / exp / log / pow / div lowering (task 3)

- **exp2 / log2** = a **single SFU op**, identical in fast and precise mode (**1 ULP**):
  `af 02 56 …` (exp2, byte0 `0xaf` byte+1 `0x02`) / `2f 02 56 …` (log2, byte0 `0x2f` byte+1 `0x02`).
- **exp(x) / exp10(x)** = `fmul(x, k) ; exp2(…)` → **exp2(x·log2(e))** / **exp2(x·log2(10))** (the
  constant `k` is a preloaded uniform, so the two share byte-identical code). ~1–2 ULP.
- **log(x) / log10(x)** = `log2(x) ; fmul(…, k)` → **log2(x)·ln(2)** / **log2(x)·log10(2)**. ~2 ULP.
- **pow(a,b)** = `log2(a) ; fmul(·,b) ; exp2(·)` = **exp2(b·log2(a))**, plus a special-case fixup op
  (`2f 04 …`) for the corner cases; `powr(a,b)` is the same without the fixup. ~1 ULP precise, ~3
  fast.
- **a / b** = `rcp(b) ; fmul(a, ·)` = **a·rcp(b)** using the SFU reciprocal (`af 00 …`). Fast **1
  ULP**; precise `a/b` is correctly-rounded (**0 ULP**) via the SFU reciprocal seed + NR + remainder
  correction (300-byte IEEE sequence, `raw/disasm_precise.txt`).
- **sin / cos / tan** = **range reduction + polynomial** (a chain of `falu3` fma ops for the Horner
  polynomial, a `0x2b` range-reduction/round op, and iminmax/select quadrant logic), **not** a
  single SFU op. `tan = sin · rcp(cos)` (uses the SFU rcp). **fast and precise are byte-identical** —
  G17P has a single sin/cos lowering. Accuracy: ~1 ULP for moderate arguments, but degrades badly for
  large arguments (sin(2π) ≈ 5·10⁵ ULP — small *absolute* error near a zero; cos(π/2) similar):
  the built-in range reduction is limited, so a Vulkan/GL `sin/cos` needing large-argument accuracy
  must add software extended (Payne-Hanek) reduction.

## 4. Accuracy validation (task 4, `raw/accuracy.txt`)
Known values, read back from the real GPU (fp32 ULP vs a double reference):

| value | HW result | ULP |
|---|---|---|
| 1/3 | 0.333333343 | 0 |
| rsqrt(2) | 0.707106769 | 0 |
| sqrt(2) | 1.41421354 | 0 |
| 2/3 (a/b, precise) | 0.666666687 | 0 |
| sin(π/6) | 0.5 | 0 |
| sin(π/3) | 0.866025448 | 1 |
| cos(π/3) | 0.49999997 | 1 |
| exp(1) | 2.71828198 | 1 |
| log(e) | 0.999999881 | 2 |
| exp2(0.5) | 1.41421366 | 1 |
| log2(10) | 3.32192802 | 0 |
| pow(10,3) precise | 1000 | 0 |
| pow(2,10) | 1024 | 0 |

Per-function worst ULP over the sampled inputs: exp2 1, log2 1, exp 1–2, log 2, sin/cos 1 (moderate
args), div 0 (precise) / 1 (fast), pow 1 (precise) / 3 (fast). All match the lowerings above.

## 5. tools/agx-isa updates + round-trip + faults
- **`fspecial`** (0x2f/0xaf) descriptor expanded: full **(byte0 bit7, byte+1)** function table
  `(0x2f,0/1/2)=round/sqrt/log2`, `(0xaf,0/1/2)=rcp/rsqrt/exp2`; semantics note the compositions.
- **`fspecial_est`** (byte0 `0x29`, byte+2 `0x25`) **new**: subop byte+3 rcp/rsqrt/sqrt estimate,
  precision ~7.5–8 bits.
- `db.json` regenerated; length-rule `byte0_table` gains `0x2f/0xaf` and the `0x29` estimate note.
- `roundtrip_test.py`: +9 real instrs (SFU rcp/rsqrt/sqrt + 3 estimate seeds + exp2/log2), +5 whole
  programs (`fast_rcp`, `fast_rsqrt`, `fdiv_fast`, `expe_fast`, `loge_fast`), +4 synth → **ALL PASS**.
- **Faults/reboots: 0.** No `macvdmtool` needed.

### HW-validated vs inferred
- **HW-validated:** estimate op byte+3 function selector and its ~8-bit precision (raw-seed
  readback); the SFU function table (disassembly of our own fast/precise kernels + ULP readback);
  the exp/log/pow/div/sin/cos/tan compositions; all ULP accuracies.
- **Inferred (byte-diff / analogy):** the estimate op's srcA/dst bit-fields (falu2 analogy); the
  SFU byte+6/+7 secondary-code exact meaning; the `0x2b` range-reduction op internals; the exact NR
  instruction schedule (deliberately not transcribed — clean-room rule 5).

## Clean-room status
Clean. Only our own MSL was compiled and only our own compiled bytes were spliced/executed.
`gen_kernels.py`, `dump_seq.py`, `est_precision.py`, `estimate_probe.py`, `transplant_est.py`,
`validate.py` are ours; reused OWN-SHADER tools `shdump`, `agxparse.py`, `agxrun_persist`,
`persistrun.py`, `agxisa.py`/`isadb.py`. `raw/` holds text logs only; `.bin` archives stay on the
device under `~/cleanroom_work/exp0026/`.
