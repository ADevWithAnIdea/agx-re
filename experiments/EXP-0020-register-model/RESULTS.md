# EXP-0020 Results — the G17P register / uniform machine model (consolidated)

Clean-room: **OWN-SHADER + HW-PROBE** (+ PUBLIC for the applegpu *shape*). Every byte
inspected/spliced/executed and every metadata field read is from a shader **we compiled
from our own MSL**. No Apple binary was disassembled or introspected. The `__GPU_METADATA`
we read is our own compiled archive's own FlatBuffer (a public, self-describing format),
walked with our own parser.

Device: Apple A18 Pro / G17P, macOS 26.6, Metal 4 / Apple9. **Reboots: 0** (all runs
completed; the only "faults" were expected PIPELINE_MISS from an AIR-hash mismatch, fixed).

---

## TL;DR
1. **GPR file = 96 addressable 32-bit registers per thread** (not 64). HW-validated: a
   kernel declaring **93** live regs with **no scratch** computes correctly. The compiler's
   register footprint caps at exactly **96**, then spills. EXP-0006's "64" was an artifact
   of a tiny-footprint test shader.
2. **16-bit halves are independently addressable (packed 2-per-GPR).** 64 `half` values
   compile to **50** GPRs (impossible if each half owned a 32-bit reg). The 32-bit `0x09`
   ALU form's size-bit reaches only the *low* half; independent half access is via the
   native-half `0x10`/`0x11` groups.
3. **There is a uniform register file.** A source operand selects **GPR vs uniform** via a
   per-source mode bit (int `0x9f`: srcB uniform = byte+5 bit4, srcA uniform = byte+6).
   Scalar `constant T&` uniforms + buffer base pointers are preloaded into it; a compact
   4-byte **`uniform_mov`** (`Xb YY 01 08`) copies a uniform reg → GPR. Thread-invariant
   expressions are computed on a **separate uniform/scalar datapath in the
   `constant_program`** (it `device_load`s the uniform buffers and does the uniform ALU).
4. **Footprint declaration:** the exact GPR / scratch / uniform footprint lives in the
   shader binary's **`__GPU_METADATA` FlatBuffer** (travels with the shader BO). The
   launch-descriptor `+0x00` config word is only a **coarse 2-level occupancy *tier* bit**
   (bit 23), set once the shader uses ≥ ~12 GPRs — it does *not* carry the exact count.
5. **Dynamic Caching / spill:** above 96 GPRs the compiler spills to **scratch (stack)
   memory**; the per-thread scratch **byte size** is a `__GPU_METADATA` field (32 → 288 →
   576 → 768 → 1280 B as pressure rises). Spilled kernels compute correctly on HW.

---

## 1. GPR file: 96 addressable 32-bit registers (HW-validated)

**Method.** Cyclic-FMA kernels holding K live 32-bit values (`gen_int_pressure.py`). For
each K we read the compiler's register footprint `f0` from `__GPU_METADATA`, ran the kernel
on the GPU with `n=1` (the loop degenerates to a K-register copy, `out[k]=in[k]`), and
exact-compared the int output. (`raw/int_correctness.txt`, `raw/regfootprint_float.txt`.)

| K (live values) | f0 (reg footprint) | scratch (B) | HW copy |
|---:|---:|---:|:--|
| 8  | 13 | 0 | PASS |
| 32 | 43 | 0 | PASS |
| 48 | 63 | 0 | PASS |
| 64 | 83 | 0 | PASS |
| **72** | **93** | **0** | **PASS** |
| 80 | **96** | 32  | PASS |
| 96 | **96** | 288 | PASS |
| 128 | **96** | 576 | PASS |
| 256 | **96** | 1280 | PASS |

- **`f0` grows ~linearly then caps at exactly 96** and never exceeds it (K = 80…256 all
  report 96). The cap is the compiler's maximum GPR allocation.
- **K=72 declares 93 registers with zero scratch and computes correctly** ⇒ the physical
  file holds **≥ 93 live 32-bit registers with no spill**. Combined with the hard cap, the
  **usable GPR file = 96 × 32-bit** (this is the number a compiler must target).
- `f0` is in **32-bit-register units** (48 32-bit accumulators → 63 regs; if it counted
  16-bit halves, 48 floats would need ≥ 96 — it doesn't).
- **EXP-0006 "64 GPRs" corrected.** That kernel declared a tiny footprint, so the encoding's
  reg index bit-6 read back folded to r0..r63 (only those were live). High-pressure kernels
  use r0..r95 with no aliasing and correct results — 64 was a test artifact, not the file
  size. `MAXREG` here is `> 63` and tracks `f0 − 3` (`raw/pressure_float.txt` analysis).

**Encoding reconciliation (float `dst[4:8]` vs integer `dst=b3`).** All *source* reg fields
and the integer/`falu3` *dst* fields are **7-bit** (`(reg<<1)|size`, r0..r127), covering the
96-reg file. The **6-byte `falu2` dst is a 4-bit nibble (`b0[4:8]`, r0..r15 only)** — a
compaction for low destinations; a float op writing a **high** GPR uses the **8-byte
`falu3` form** (`dst=byte+1`, 7-bit) — HW-observed writing **r64** in a loop-free matmul
kernel (`raw/mm24.hex`). So the two field widths are different *instruction-size* forms, not
a contradiction. (DB updated accordingly.)

## 2. 16-bit half addressing: independently addressable (packed 2/GPR)

Same kernels with `half` accumulators (`fbstats.py half`):

| K | `float` f0 | `half` f0 |
|---:|---:|---:|
| 16 | 23 | 14 |
| 32 | 43 | 26 |
| 48 | 63 | 38 |
| 64 | 83 | **50** |
| 96 | 96(spill) | 74 |

`half` uses **~0.6×** the registers of `float` (slope 0.75 vs 1.25 regs/value). 64 half
values fit in **50** GPRs — **impossible** if a half occupied a full 32-bit reg (that would
need ≥ 64). ⇒ **the compiler packs two independent 16-bit values into one 32-bit GPR**, i.e.
halves are independently addressable. The `0x09` 32-bit form's size-bit only reads the *low*
half (EXP-0006); independent high/low half access is via the native-half `0x10`/`0x11` ALU
groups (their half-select encoding = a follow-up). *(HW-compiled evidence: the compiler,
targeting this silicon, allocates 2 halves/reg. A direct HW splice-read of a high half is a
follow-up.)*

## 3. Uniform register file (selector, datapath, addressing)

**GPR-vs-uniform selector = a per-source mode bit** (`raw/uniform_probes.txt`, byte-diff):
- integer `iadd`/`imad` (`0x9f`): canonical GPR+GPR `…02 08 00 a8 17 05`; **uniform srcB**
  sets **byte+5 bit4** (`0x08→0x18`), consistent across add and mul; **uniform srcA** sets
  **byte+6** (`…02 00 30…`). (Cross-checked with `y−a` / `a−y` to force srcA/srcB roles.)
- float (`0x09`): uniform srcB flips **byte+2 bit4** and **byte+5 bit1** (`…1c 05 00 c0` →
  `…0c 0d 00 c2`).

**Uniform→GPR move** (`uniform_mov`, **4 bytes**, `Xb YY 01 08`): byte0 hi-nibble = dst GPR,
byte1 = uniform source register. `u_each` (`out[i]=u_i`, 6 uniforms) emits six of these with
dst GPR 0..5 and byte1 stepping by 4 (`0x1c,0x20,…,0x30`) — consecutive uniform registers.

**Uniform/scalar datapath (major finding).** A pure-uniform expression (`x+y`, `u0+…+u7`)
emits **no** `0x09`/`0x9f` in `_agc.main` — instead the arithmetic is hoisted into the
**`_agc.main.constant_program`** ("uniform program"), which **`device_load`s the uniform
buffers and runs uniform-datapath ALU** (a chain of `9f` adds for `u0+…+u7`), leaving the
result in a uniform register; `_agc.main` then does one `uniform_mov`. So the
`constant_program` prolog (previously "advisory", EXP-0010) is the **thread-invariant
uniform program**. Buffer **base pointers** likewise land in uniform registers (selected by
`device_load` byte+4, EXP-0010). Uniform footprint is a `__GPU_METADATA` field (grows ~8
per bound uniform: 2→32, 8→80, 16→144 B). Exact uniform-register **count** not pinned — the
byte1 index field is 8-bit (≤128), consistent with a G13-like uniform file (follow-up).

## 4. Footprint declaration (`__GPU_METADATA` + the config word)

**The compiler declares the footprint in the shader binary's `__GPU_METADATA` FlatBuffer**
(nested AppleGPU Mach-O `__TEXT,__compute`; `raw/metadata_float.txt`). Root → field 0 →
stats table:
- **field 0 = GPR footprint** (caps at 96).
- **field 41 / 14 = scratch (spill) byte size** (present only when spilling; §5).
- **field 31 = uniform footprint** (present only when uniforms are used; §3).
- **field 9 = threadgroup-memory** flag (appears for a `threadgroup`-using kernel).
- (`__reflection`/`__descriptor` sections are byte-identical across all K — they carry only
  the Metal API interface, not the register footprint.)

This metadata travels **with the shader BO** (launch descriptor `+0x08` = `shaderVA>>6`,
EXP-0011), so the HW/firmware reads the exact footprint from the shader itself.

**The launch-descriptor `+0x00` config word is a coarse occupancy *tier* bit**, not the
count (`raw/config_correlation.txt`, `raw/config_threshold.txt`, captured via our reused
`iotrace`):

| kernel | f0 | config `+0x00` |
|---|---:|---|
| add3 | 3 | `0x00080000` |
| h5 | 11 | `0x00080000` |
| h6 | 12 | `0x00880000` |
| heavy/h8 | 14 | `0x00880000` |
| h48 | 50 | `0x00880000` |
| h96 (spill) | 96 | `0x00880000` |

Only **bit 23 (byte+2 bit7)** changes: **clear for ≤ 11 GPRs, set for ≥ 12 GPRs**. Every
`f0 ≥ 12` gives the same `0x00880000` (the full 44-byte launch record is otherwise
identical for h8…h160) — so `+0x00` is a **2-level register/occupancy tier flag**, and the
exact count/scratch come from `__GPU_METADATA`. This reconciles EXP-0011 (base `0x08` →
"heavy" `0x88`; "heavy" is our K=16 float kernel, f0=23, which crossed the ~12-reg tier).
Threadgroup size (grid/tg sweeps, EXP-0011) does **not** move `+0x00`.

## 5. Dynamic Caching / register spill (HW-validated)

When the footprint would exceed **96** GPRs, the compiler **spills to scratch (stack)
memory** and records the **per-thread scratch byte size** in `__GPU_METADATA` (field 14/41):

| K | f0 | scratch (B) |
|---:|---:|---:|
| 72 | 93 | 0 (no spill) |
| 80 | 96 | 32 |
| 96 | 96 | 288 |
| 128 | 96 | 576 |
| 256 | 96 | 1280 |

Scratch appears **exactly** when `f0` hits 96, and grows with excess pressure. **All spilled
kernels compute correctly on HW** (`raw/int_correctness.txt`, K=80…256 PASS), so the
spill/fill path works. This is the register-file-as-cache / unified-memory (Dynamic-Caching)
spill mechanism observed from the compiler side.

**What a compiler must know (for `docs/`):**
- **96 addressable 32-bit GPRs** per thread; allocate ≤ 96, spill the rest.
- 16-bit values pack **2 per GPR** (independent halves).
- Spilling to per-thread **scratch** costs memory traffic; scratch size is declared in the
  shader metadata (`field 14/41`), GPR footprint in `field 0`, uniform footprint in
  `field 31`.
- Occupancy has (at least) a **coarse tier boundary at ~12 GPRs** (config bit 23); lower
  register use ⇒ higher occupancy. Exact occupancy curve = follow-up.
- Uniforms/base-pointers live in a **separate uniform register file** fed by the uniform
  program (`constant_program`); a source picks GPR-vs-uniform via a mode bit.

## 6. Round-trip / DB status
`tools/agx-isa/` refined and **`roundtrip_test.py` → ALL PASS**:
- New **`uniform_mov`** descriptor (4-byte `Xb YY 01 08`) + length-rule case for
  low-nibble-`0xB`; tokenizes the uniform kernels cleanly (`uniform_mov dst=.. usrc=..`).
- `falu2`/`iadd2` register-model semantics updated: **64→96 GPRs**, the 6-byte-`falu2`
  4-bit dst vs 8-byte-`falu3`/integer 7-bit dst reconciliation, half-packing, and the
  per-source **uniform-select** bits. `db.json` regenerated.

## 7. Faults / reboots
**Reboots: 0.** ~200 compiles/dispatches (pressure, uniform, config captures) all completed;
no GPU wedge; `macvdmtool` never needed.

## 8. Recommended next
1. Direct HW splice-read of a **high half** + the `0x10`/`0x11` half-select encoding.
2. Pin the **uniform-register count** and its operand bit-layout (uniform-pressure sweep).
3. Locate the **scratch-base** the HW uses for spill (BO-side; ties to EXP-0011 arg buffer).
4. Map the **full occupancy curve** vs GPR count (is 96 hard silicon or an occupancy policy?).

## 9. Clean-room status
Clean. Only our own MSL was compiled; only our own compiled bytes / our own archive's
metadata were inspected. `gen_pressure.py`, `gen_int_pressure.py`, `dump_sections.py`,
`fbstats.py`, `gen_uniform.py`, `analyze_pressure.py`, `make_cvar2.py` are our own tools;
reused OWN-SHADER tools `shdump`/`agxparse.py`/`agxrun`/`agx-isa` and the EXP-0011
`cvar`/`iotrace` (reused verbatim, not edited). The only third-party input is the public MIT
applegpu (design reference / "uniform register" concept, read only). `raw/` holds text logs
only; `.bin` archives stayed on the device under `~/cleanroom_work/exp0020/`.
