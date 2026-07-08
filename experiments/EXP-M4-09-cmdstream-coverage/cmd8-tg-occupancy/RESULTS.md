# CMD-8: Threadgroup rounding + CDM occupancy bit23 — RESULTS

**Clean-room category:** OWN-SHADER (our own MSL, compiled at runtime; our own shader's own
`__GPU_METADATA`) + DATA-TRACE (our own command-buffer bytes via the `iotrace` IOKit interposer).
No Apple binary was disassembled or introspected.

> ⚠ **DEVICE = local Apple M4 (10-core GPU, Metal 4), NOT the A18 Pro / G17P.** The CDM BO is at
> the **same** GPU VA `0x100000b0000` and the 0x2c-byte record layout matches the A18 doc field-for-field
> (cfg@+0x00, shptr@+0x08, grid@+0x10, tg@+0x1c), so the structure is shared across the Apple9 family —
> but every **numeric threshold** below is an M4 measurement and **must be cross-confirmed on the A18**.
> The doc's claims being tested are A18 claims; where M4 contradicts them it is either an M4-vs-A18
> hardware/driver difference or a genuine doc error. Both are flagged **A18-CROSS-CONFIRM**.

Tools built here (`-arch arm64e`): `iotrace.dylib`, `cvar` (with a new `--srcfile` option), `shdump`.
Scripts: `run_tg.sh`, `run_tg2.sh`, `run_tg3.sh` (sub-task 1); `gprmeas.py`, `run_gpr.py` (sub-task 2);
`cdmread.py`/`cdmraw.py` (record parsers). Raw evidence: `caps_*/**/bo_*va100000b0000_*.hex` + `*.out`.

---

## Sub-task (1): threadgroup field @ +0x1c/+0x20/+0x24 — rounding rule

### Verdict: the doc's rule is **FALSIFIED / mischaracterized.**
The doc says: *"each axis rounded up to a power of two with product ≥ 32 (1..32→32, 48/64→64, 100→128;
(3,5)→(4,8)); exact rounding is occupancy/shader-dependent."*

**Reality on M4:** `+0x1c/+0x20/+0x24` is the **physical launch threadgroup size**. It is **verbatim =
the requested `threadsPerThreadgroup`** whenever the threadgroup boundaries are semantically meaningful.
The "rounding" the doc saw is a **Metal userspace-driver occupancy optimization** that *merges* the
requested groups into fuller physical groups **only when it is provably invisible** (kernel uses no
threadgroup memory and no barrier), and it is **neither next-pow2 nor next-mult-32**.

### Evidence 1 — a single threadgroup is always verbatim (no rounding at all)
`run_tg.sh` swept 40+ combos with `grid == tg` (exactly one group). **Every** requested tg was recorded
verbatim at +0x1c, including the doc's counter-examples: `1→1, 3→3, 48→48, 100→100, (3,5)→(3,5)`.
(→ the doc's rounding only ever appears with **multiple** threadgroups.)

### Evidence 2 — shader-dependence is the decisive control (`run_tg3.sh` part b, numGroups=4)
Same request, three kernels: `add3`/`heavy` (no shared mem, no barrier) vs `tgmem` (shared mem + barrier):

| req tg | add3 eff | heavy eff | **tgmem eff** |
|---|---|---|---|
| 3   | 8   | 8   | **3**   |
| 7   | 16  | 16  | **7**   |
| 16  | 32  | 32  | **16**  |
| 40  | 64  | 64  | **40**  |
| 48  | 64  | 64  | **48**  |
| 80  | 96  | 96  | **80**  |
| 100 | 128 | 128 | **100** |
| 130 | 132 | 132 | **130** |
| 200 | 200 | 200 | **200** |

**`tgmem` (barrier + shared memory) is ALWAYS verbatim.** All 12 tgmem dispatches completed
(`status=4`). A kernel whose threadgroup boundaries carry semantics forces Metal to honor the exact
requested size; a barrier-free kernel lets Metal repack for occupancy. → the field is a **physical
launch size a driver is free to enlarge only when threads don't communicate**; the correct, always-safe
value a Mesa driver emits is the **verbatim requested workgroup size**.

### Evidence 3 — the "rounding" is not pow2 and not mult-32 (`run_tg3.sh` part a, add3, numGroups=8)
Fine 1-D map (requested → effective) for a barrier-free kernel:
`33→33, 34→36, 37→37, 38→64, 39→39, 40→64, 52→52, 61→61, 65→65, 66→68, 80→96, 96→96, 97→98, 99→99,
100→128, 101→102, 102→102, 129→132, 130→132, 160→160, 176→192, 200→200, 224→224, 256→256`.
This is an **opaque Metal occupancy heuristic** (note 34→36, 38→64, 39→39, 80→96, 97→98, 200→200):
- **not** next-power-of-2 (36, 68, 96, 98, 102, 132, 200 are not powers of two);
- **not** next-multiple-of-32 (33, 37, 39, 52, 61, 65, 99, 102, 200 are not multiples of 32, and
  200→200 while mult-32 would force 224).
The doc's specific examples reproduce for barrier-free kernels at the same grid (`48→64, 64→64,
100→128, (3,5)→(4,8)` all confirmed), but they are **instances of this driver heuristic, not a HW rule.**

### Evidence 4 — for small requests the repack also depends on the grid (`run_tg3.sh` part c)
add3 req=3, varying numGroups: `ng1→3, ng2→4, ng4→8, ng8→16, ng16→32, ng32→32`. The physical size grows
with total thread count (≈ largest power-of-two ≤ total, capped at one SIMD/32), confirming this is a
"merge small groups to fill SIMDs" optimization — not a per-axis function of the request. 2-D/3-D behave
the same per axis: `(3,5)→(4,8)` at ng4, `(2,3,5)→(2,4,8)` at ng2.

### Corrected statement for the doc
> `+0x1c/+0x20/+0x24` = **physical threadgroup (workgroup) dimensions, in threads/axis.** `grid` @+0x10
> is verbatim total threads. A conformant driver should emit the **exact requested `threadsPerThreadgroup`**
> here (verbatim) — proven correct: Metal itself emits verbatim for every kernel using threadgroup memory
> or a barrier, and for every single-group dispatch. Metal *additionally* repacks barrier-free /
> shared-mem-free kernels into larger physical groups as an **occupancy optimization** (the values the
> old doc mistook for "round up to power of two"); this repack is Metal-driver-specific, depends on the
> kernel, the request, and the total grid, and is **not** a hardware requirement. **A18-CROSS-CONFIRM**
> the verbatim-when-barrier behavior and the repack heuristic.

---

## Sub-task (2): CDM cfg word @ +0x00 — bit23 occupancy/register tier

### Verdict: doc's "clear ≤11 / set ≥12 GPRs" is **FALSIFIED**; the flip is at a **much lower**
### footprint and is **not a clean function of the field-0 GPR count.**

Method: build a ladder of our own compute kernels with controlled register pressure (independent
`float`/`half` accumulator chains + static live loads); measure each kernel's GPR footprint from **its
own** `__GPU_METADATA` field-0 (`f0`, same method as RT-12 `b2_half.py`, clean-room OWN-SHADER); dispatch
the *same* MSL via `cvar --srcfile` under `iotrace` and read the CDM cfg word +0x00. ~50 kernels.

### Finding A — cfg word takes exactly two values; bit23 is a **single-bit** 2-tier flag
Across the entire corpus (f0 = 2 … 96) the cfg word is **only ever** `0x00080000` (clear) or
`0x00880000` (set). bit19 (`0x00080000`) is always set; **bit23 (`0x00800000`)** is the only variable.
Even f0=96 (`kernel_src_f(90,0)`) stays `0x00880000` — **no bit above 23 ever lights up**, so bit23 is a
**1-bit occupancy/register tier**, *not* the LSB of a GPR-count field. The actual GPR count is **not** in
this word (it lives in the shader BO / USC config, consistent with the doc). Rest of the 0x2c record is
invariant under register pressure.

### Finding B — bit23 == presence of `__GPU_METADATA` **field-32** (perfect correlation)
The compiler emits an extra metadata sub-field (index 32; value `0x0X010001`, high byte X = f0) in our own
shader **iff** bit23 is set in the captured cfg word. Checked kernel-by-kernel: **field-32-present == bit23
for every kernel** (`run_gpr.py`, `caps_pf2` batch: 14/14 OK, plus ~35 earlier all consistent). So the
driver reflects a **compiler-computed occupancy/register-class property** of the shader into cmdstream
bit23. This gives a driver a concrete emit rule (see below).

### Finding C — bit23 is **NOT** a threshold on field-0 GPR count (the doc's model is wrong)
Same f0 lands on **both** sides depending on kernel structure (peak register pressure / loop-carried
liveness), so no `f0 ≥ T` rule can hold:

| f0 | CLEAR examples | SET examples |
|---|---|---|
| 4  | — | `N0H3` (half) |
| 5  | `N1H0`, `N0H4` | `N0H2` (half) |
| 8  | `N0E7`, `N1E3` (1 chain + 3 static) | `N2E0` (2 chains) |
| 9  | `N0E8` (pure static tree) | `N1E4`, `N2E1`, `N3E0` |
| ≥10| — | all (`N0E10` f0=11 set, …) |

- Lowest f0 observed **SET**: **f0 = 4** (a half kernel); pure-float lowest SET: **f0 = 8** (`N2E0`).
- Highest f0 observed **CLEAR**: **f0 = 9** (`N0E8`, a pure-float summation tree that frees registers early).
- Overlap zone f0 ∈ [4,9] is **structure-dependent**, centered around **f0 ≈ 8–10** — **nowhere near 12.**

The true driver is **peak simultaneously-live GPR pressure** (an occupancy class), which field-0 (total
registers touched) only loosely proxies: a kernel with 2 loop-carried chains (`N2E0`, f0=8) flips, while a
kernel with the same f0=8 but only 1 loop-carried chain + static loads (`N1E3`) does not.

### Corrected statement for the doc
> **CDM cfg word (`0x100000b0000`+0x00)** = `0x00080000` (bit19) with a **single occupancy/register-tier
> bit23** (→ `0x00880000`). It is a **2-tier boolean**, not a counter. bit23 is set **iff** the shader's
> compiler assigns it the higher register/occupancy class (materialized as `__GPU_METADATA` field-32).
> This is driven by **peak register pressure**, **not** the total GPR (field-0) count: on M4 the flip
> occurs at a peak footprint of only **~8–10 GPRs** (kernels with f0 as low as 4–8 already set it), and
> the earlier interpolated **"clear ≤11 / set ≥12 GPRs" is FALSE** — f0=8 and f0=9 each occur on **both**
> sides. A Mesa driver must set bit23 from **its own** register allocator's occupancy decision (peak GPR
> class), not a `≥12` test. **A18-CROSS-CONFIRM the exact peak threshold** (the doc's original A18 data
> point of f0=8→clear disagrees with M4's f0=8-can-be-set; this is the sharpest M4-vs-A18 discrepancy).

---

## A18 cross-confirmation items (flagged)
1. **tg field verbatim-vs-repack**: confirm on A18 that `tgmem`(barrier) → verbatim and barrier-free →
   repack, and that the repack heuristic (not pow2/not mult-32) matches. The A18 doc's "1..32→32 / pow2"
   is likely the barrier-free repack at a particular grid, misread as a HW rule.
2. **bit23 peak-GPR threshold**: A18 may flip at a different peak footprint than M4's ~8–10. The doc's
   A18 "f0=8 captured, assumed clear, flip ≥12" directly conflicts with M4 (f0=8 can be SET). Re-run this
   exact ladder on A18.
3. **bit23 is single-bit (2 tiers) on M4** even at f0=96 — verify A18 has no additional tier bits at very
   high register pressure.
