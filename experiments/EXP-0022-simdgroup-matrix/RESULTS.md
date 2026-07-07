# EXP-0022 Results — `simdgroup_matrix` cooperative matrix (A18 Pro / G17P)

**Verdict: DEDICATED matrix hardware.** `simdgroup_matrix` lowers to a **new AGX
instruction group `0xcf`** — a 12-byte SIMD-group cooperative-matrix
multiply-accumulate. It is **not** an FMA/shuffle expansion. All core findings are
**HW-validated** (a real GPU dispatch produced the expected matrix result);
sub-field bit layouts marked *inferred* are byte-diff only.

SIMD width = 32 (one full simdgroup = the cooperative scope). Device: macOS 26.6
(25G5043d), 5 GPU cores, Metal 4 / Apple9.

---

## 1. Dedicated vs emulated — the opcode diff (deciding question)

Compiled our own `simdgroup_multiply_accumulate` (`kernels/mat.metal`) and a
hand-written FMA matmul of the **same 8×8 shape** (`kernels/hand.metal`), carved
`_agc.main`, tokenized both (`analyze.py`, `raw/tokenize.txt`):

| kernel | what it is | contains `0xcf`? | body |
|---|---|---|---|
| `mad_f32` | `simdgroup_multiply_accumulate(r,a,b,c)` | **YES ×1** | 3×`0x67` load → **1×`0xcf`** → 1×`0xe7` store |
| `mul_f32` | `simdgroup_multiply(r,a,b)` | **YES ×1** | 2×load → 1×`0xcf` → store |
| `mad_f16` | half MAC | **YES ×1** | 3×load → 1×`0xcf` → store |
| `hand_mm_f32` | scalar `fma()` matmul (control) | **NO (×0)** | `device_load` + `fma`(0x09) + `device_store` only |
| `hand_mm_shuffle` | lane-cooperative `simd_shuffle`+`fma` (control) | **NO (×0)** | 596 B of `0x47/0xc7` shuffle + `0x09` fma |

The simdgroup kernels carry a single **novel opcode group `0xcf`** that our ISA DB
did not know; both hand-written controls — the exact thing an *emulated* cooperative
matrix would compile to — contain **zero** `0xcf`. A full 8×8×8 tile MAC (512
scalar MACs) is **one** `0xcf` instruction, versus 596 bytes of fma+shuffle for the
lane-cooperative emulation. ⟹ **dedicated matrix/MAC-array unit, not lane-cooperative FMA.**

## 2. The matrix MAC instruction (`matrix_mac`, byte0 `0xcf`, 12 bytes)

Exact bytes (single standalone MAC, HW-validated):

```
        +0  +1  +2  +3  +4  +5  +6  +7  +8  +9  +10 +11
f32 MAC cf  02  56  02  00  04  08  09  d4  43  24  01     r = a*b + c   (float)
f32 MUL cf  02  56  02  00  04  08  00  d4  41  24  00     r = a*b       (float)
f16 MAC cf  00  56  04  02  0c  08  04  10  62  8c  00     r = a*b + c   (half)
MPP MAC cf  02  54  05  01  b4  6f  00  4a  42  24  01     tiled (matmul2d)
```

| byte | field | meaning | status |
|---|---|---|---|
| +0 | opcode | `0xcf` = cooperative-matrix MAC | ✅ HW |
| +1 | **dtype** | `0x00` = 16-bit (half); `0x02` = 32-bit (float; bfloat shares the 32-bit datapath) | inferred (per-type diff) |
| +2 | **mode** | `0x56` = standalone op; `0x54` = tiled (MPP `matmul2d` context) | inferred |
| +3..+4 | A operand + dst high bits | fragment register selectors (packed) | *partially decoded* |
| +5..+6 | B operand | fragment register selector (packed) | *partially decoded* |
| **+7** | **C source register** | accumulator fragment source reg (`0x09` in MAC, `0x00` in MUL) | ✅ **HW** (corrupting it breaks the accumulate) |
| +8..+9 | **dst** | result fragment register + width | inferred |
| +10 | marker | `0x24` (constant in all observed) | inferred |
| **+11 bit0** | **accumulate-enable** | `1` → `a*b + c`; `0` → `a*b` | ✅ **HW** (splice `01`→`00` turns MAC into pure multiply) |

**Semantics (HW-proven):** `d = a·b (+ c)`, row-major 8×8, `d[i][j] = C[i][j] + Σ_k A[i][k]·B[k][j]`.
`simdgroup_multiply` is the same op with the accumulate bit cleared and no C operand
(byte-identical to a spliced MAC — see §5).

**Matrix dimensions:** only **8×8** is exposed by MSL. `simdgroup_matrix<float,{16×16,8×16,16×8,4×4,32×32}>`
all fail `_valid_simdgroup_matrix_size()` at compile time. The HW primitive is a fixed
**8×8×8** tile; larger matmuls tile in software over it (see §6).

**Data types** (`raw/dtype_envelope.txt`, each probed in isolation):

| element type | accepted? | lowers to |
|---|---|---|
| `half` (fp16) | ✅ | 1× `0xcf` (dtype byte+1 = `0x00`) |
| `float` (fp32) | ✅ | 1× `0xcf` (dtype byte+1 = `0x02`) |
| `bfloat` (bf16) | ✅ | 1× `0xcf` (dtype = `0x02`; +16 B of input conversion) |
| `char/uchar/short/ushort/int/uint` | ❌ **REJECTED** | `is_simdgroup_matrix_element<T>` == false — **no integer/int8 cooperative matrix** |
| mixed `half*half → float` accum | ✅ | 1× `0xcf` (the ML-relevant fp16→fp32 path) |
| mixed `bfloat*bfloat → float` accum | ✅ | 1× `0xcf` |
| mixed `float*float → half` accum | ✅ | 1× `0xcf` |

## 3. `simdgroup_load` / `simdgroup_store` + 8×8 → 32-lane mapping

**Not dedicated instructions.** `simdgroup_load`/`store` lower to the **ordinary
memory family** (`0x67` load / `0xe7` store, EXP-0012) with a per-lane computed
address — there is no matrix-load opcode.

- The fp32 load uses a **64-bit data width** (byte+8 = `0x59`, the EXP-0012 64-bit
  code) ⟹ **each lane loads a 64-bit register pair = 2 fp32 tile elements.**
  32 lanes × 2 = 64 = the whole 8×8 tile. (half: 2 half elements = 32-bit/lane.)
- **HW-validated round-trip identity:** `ls_f32` (load tile → store tile) reproduces
  the input 8×8 exactly (`raw/hwval.txt` T0), so the load and store lane mappings are
  mutually consistent. `make_filled_simdgroup_matrix` is **not** a matrix op either —
  it is two `0x2c`/`0x3c` constant-splat moves (8 B each) writing the fragment's 2
  per-lane registers.
- The exact element↔lane permutation (which `[i][j]` lands in which lane's reg pair)
  is set by the per-lane load-address arithmetic; structural mapping (2 elems/lane,
  64-bit slot) is HW-confirmed, the exact permutation is a follow-up.

## 4. HW validation — known matmul → correct C (`raw/hwval.txt`)

All PASS, dispatched over one full simdgroup (grid=32, tg=32), read back and
compared against a numpy `A·B + C`:

| test | check | result |
|---|---|---|
| T0 | `ls_f32` load→store round-trip == A | ✅ PASS |
| T1 | `mad_f32` A·I + 0 == A | ✅ PASS |
| T2 | `mad_f32` I·B + 0 == B | ✅ PASS |
| T3 | `mad_f32` full **A·B + C** (distinct known A,B,C) | ✅ PASS |
| T4 | `mul_f32` A·B (multiply-only) | ✅ PASS |
| T5 | `mad_f16` half A·B + C | ✅ PASS |
| T6 | `fill_f32` == 1.0 everywhere | ✅ PASS |

This proves the semantics of the `0xcf` encoding for both fp32 and fp16.

## 5. Splice proofs (`raw/splice_cf.txt`) — the accumulate bit & C operand

Spliced the single `0xcf` in `mad_f32` (main offset 186), ran with known A,B,C:

| splice | R == A·B+C | R == A·B | conclusion |
|---|---|---|---|
| (baseline) | ✅ | ✗ | MAC = `a*b + c` |
| **+11 `01`→`00`** | ✗ | ✅ | **byte+11 bit0 = accumulate-enable** (cleared ⟹ pure multiply) |
| +9 `43`→`41` | ✅ | ✗ | not the accumulate bit |
| **+7 `09`→`00`** | ✗ | ✗ | **byte+7 = C source fragment register** (redirected ⟹ garbage accumulate) |
| +7/+9/+11 → mul form | ✗ | ✅ | matches `simdgroup_multiply` byte-for-byte |

Operand-swap probe (`raw/swap_probe.txt`): swapping byte+3↔+5 did **not** cleanly
produce B·A, and byte+3→0 zeroed the whole result ⟹ the A/B/dst register selectors
are packed across byte+3..+6 / +8..+9 in a non-trivial layout (partially decoded).

## 6. Tensor ops (§B6, MPP `matmul2d`) — available, same HW

`kernels/mpp.metal` (`mpp::tensor_ops::matmul2d`, `execution_simdgroups<1>`,
32×32×32, half×half→float) **compiles on-device** (threadExecutionWidth=32) once the
namespace is `mpp::tensor_ops::matmul2d_descriptor`. Its `_agc.main` is 7332 bytes and
contains **259× `0xcf`** — the **same** `matrix_mac` instruction, in the `0x54` tiled
mode. ⟹ Metal-Performance-Primitives tensor ops and `simdgroup_matrix` share the one
dedicated 8×8 matrix datapath; larger tensor shapes are **software-tiled** over the
8×8×8 HW primitive (32/8 = 4 → 4×4×4 = 64 tile-MACs + edge/convert ⇒ 259 ops).

## 7. Capability notes (for `docs/hypotheses.md` / survey)

- **Dedicated matrix unit confirmed** (Apple9 has matrix HW): one `0xcf` = one full
  8×8×8 MAC; not lane-cooperative FMA. A driver must emit `0xcf`, not a shuffle/fma tree.
- **HW primitive is fixed 8×8×8.** Metal exposes only 8×8 `simdgroup_matrix`; there is
  no larger native tile. Vulkan `VK_KHR_cooperative_matrix` with other MxNxK would need
  software tiling to 8×8 (as MPP already does).
- **Types the HW path accepts (via MSL): fp16, fp32, bf16, and mixed fp16/bf16→fp32.**
  **No integer/int8 cooperative matrix is exposed** — a Vulkan int8 coopmat would have
  to be emulated (or the HW may support it but Metal never emits it; not reachable here).
- `simdgroup_load/store` = ordinary `0x67/0xe7` memory ops (2 elems/lane, 64-bit slot);
  `make_filled` = `0x2c/0x3c` splat. Only the MAC is dedicated silicon.

## 8. Tooling / round-trip / faults

- `tools/agx-isa/`: added the **`matrix_mac`** descriptor (0xcf, 12 B, HW-validated
  fields marked), the `0xcf`→12 length rule + byte0-table note; `db.json` regenerated
  (**36 descriptors**). `roundtrip_test.py` extended with 4 matrix encodings — **ALL PASS**.
- **No faults, no reboots.** Every dispatch returned `STATUS OK`; illegal splices were
  not needed (all splices were semantically valid). Device stable throughout.

## Follow-ups

- Full bit-decode of the A/B/dst fragment-register packing (byte+3..+6, +8..+9).
- Exact element↔lane permutation of the 8×8 tile (from the load-address arithmetic).
- The `0x54` (tiled) vs `0x56` (standalone) mode bit — does it change accumulator
  source/chaining semantics, or is it purely a scheduling/liveness hint?
- Whether the HW datapath supports int8/dims beyond what MSL exposes (needs a
  non-MSL encoding probe; not reachable via the compiler).
- Tokenizer gap: the `0x27`/`f0..` float↔int convert forms in the load-address preamble
  (pre-existing, unrelated to matrices).
