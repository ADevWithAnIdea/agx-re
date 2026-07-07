# EXP-0019 Results — Graphics fixed-function state packets + USC bind grammar

**TL;DR.** On A18 Pro / G17P / macOS 26.6, byte-diffing ~100 one-Metal-state-parameter
draws (`svar.m` + `iotrace` read-only) bit-decodes the `0x58000` 3D fixed-function state
pool and the `0x10000130000` USC program:

* **Depth/stencil** is a clean bit-packed packet (per-face front/back blocks) — the depth
  and stencil **compare-function** and the three **stencil-op** fields are fully mapped,
  with code tables that match the Metal enum ordering *as the actual HW packet bytes*.
* **Blend is programmable, not fixed-function**: blend **factors and ops are compiled into
  the fragment/blend microprogram in the shader-code BO `0x10000000000`**, so there is
  **no factor/op LUT** in `0x58000`. Only coarse blend-class + write-mask bits are
  fixed-function. Dual-source blend works; framebuffer logic ops are emulatable in that
  same shader path.
* **Rasterizer** cull/winding/depth-clip is a bit-packed word at `0x58000+0x70`; **depth
  clamp is a native 2-bit field** (HW supports it); depth-bias values are 3 floats in the
  tiler-param region.
* **Shaders bind through the USC program `0x10000130000`** (3 stage sub-blocks), **not** a
  compute-style `shaderVA>>6` in the VDM. The shader-entry word is located; its exact
  pointer bit-encoding is inferred/opaque.

Every field tagged **HW-clean** is a single-word diff from changing exactly one Metal
parameter against a byte-identical baseline (noise floor = 0 words across 38 paired
control BOs, `raw/analysis/diff_base2.txt`). Tables map the *packet bytes we captured*.

---

## 0. Method & determinism
`svar.m` = the state analogue of EXP-0014's `dvar.m` (own MSL VS+FS; depth/stencil, blend,
raster params are CLI flags). `run.sh` captures the matrix under the `iotrace` interposer;
`bodiff.py` pairs BOs by deterministic `gpu_va` and word-diffs; `summarize.py` extracts
per-BO single-word diffs. **Build must be `-arch arm64e`** (§Procedure in README).
Determinism: base vs re-run = 0 differing words in all 38 control BOs (only the
`gpu_va=0x0` alias artifact and the `0x10000130000+0x534` per-run counter appear; excluded
everywhere).

---

## 1. Depth / stencil packet — BO `0x58000` (HW-clean)

Layout is **two per-face blocks** — FRONT at `+0x38`/`+0x3c`, BACK at `+0x40`/`+0x44` —
plus a shared flags word at `+0x34`. Depth state (face-independent) is **replicated into
both** depth slots (`+0x38` and `+0x40`); stencil is per-face. Reference config
(`sa_ref`: depth less+write, stencil less/replace, masks 0xff, ref 0),
`raw/hex2/sa_ref_58000.hex`:
```
+0x34: 0x000c0200   flags (stencil enabled)
+0x38: 0x01000f00   FRONT depth word
+0x3c: 0x0202ffff   FRONT stencil word
+0x40: 0x01000f00   BACK  depth word  (mirror of +0x38)
+0x44: 0x0202ffff   BACK  stencil word
```

### Flags word `+0x34` (base `0x00000200`)
| bit(s) | field | evidence |
|---|---|---|
| 9 `0x200` | constant (always set) | baseline |
| 17 `0x00020000` | **depth-bias enable** | `dbias_c`/`dbias_s` set it; clamp-only does not |
| 19:18 `0x000c0000` | **stencil test enable** | set whenever stencil is active |
| 26 `0x04000000` | **polygon line-fill mode** | `fill_lines` |

### Depth word — FRONT `+0x38`, BACK `+0x40` (baseline `0x0X000f00`)
| bits | byte | field | evidence |
|---|---|---|---|
| [7:0] | +0x38 | **stencil reference value** | `sref 5`→`..05`; `sref 0x5a` |
| [15:8] | +0x39 | constant `0x0f` (opaque; fixed plane/sample mask?) | always `0x0f` |
| 21 `0x200000` | +0x3a b5 | **depth WRITE DISABLE** (1 = read-only) | `dwr_off`: `0x07000f00→0x07200f00` |
| [26:24] | +0x3b | **depth compare function** (table below) | `dcmp` sweep, all 8 |

### Stencil word — FRONT `+0x3c`, BACK `+0x44` (active baseline `0x0202ffff`)
| bits | field | evidence |
|---|---|---|
| [7:0] | **write mask** | `swrite 0x0f`→`..ff0f`, `0x55`→`..ff55` |
| [15:8] | **read mask** | `sread 0x0f`→`..0fff`, `0x33`→`..33ff` |
| [18:16] | **depthStencilPass op** (table) | `spass` sweep, all 8 |
| [21:19] | **depthFail op** (table) | `szfail_replace/invert` |
| [24:22] | **stencilFail op** (table) | `sfail_replace/invert` |
| [27:25] | **stencil compare function** (table) | `scmp` sweep, all 8 |

Full back-face reconstruction (HW-clean, `sback` capture, back = equal / zero / invert /
replace, read 0x0f, write 0x3c): captured `+0x44 = 0x046a0f3c` decodes **exactly** as
`cmp(equal=2)<<25 | sfail(zero=1)<<22 | zfail(invert=5)<<19 | pass(replace=2)<<16 |
read(0x0f)<<8 | write(0x3c)` — validating the whole word.

**Metal optimization note:** a stencil that is `always` + all-`keep` is emitted *disabled*
(`+0x3c = 0x0e000000`, masks 0) — so masks/ops only appear once the compare or an op is
non-trivial.

### Compare-function codes (depth `+0x3b` bits[2:0]; stencil word bits[27:25]) — HW packet bytes
| code | function |
|---|---|
| 0 | never |
| 1 | less |
| 2 | equal |
| 3 | lessEqual |
| 4 | greater |
| 5 | notEqual |
| 6 | greaterEqual |
| 7 | always |

### Stencil-operation codes (all 3 op fields, 3 bits each) — HW packet bytes
| code | operation |
|---|---|
| 0 | keep |
| 1 | zero |
| 2 | replace |
| 3 | incrementClamp |
| 4 | decrementClamp |
| 5 | invert |
| 6 | incrementWrap |
| 7 | decrementWrap |

Both tables coincide with the `MTLCompareFunction` / `MTLStencilOperation` enum ordering,
but these are the **bytes emitted into the hardware packet** (diff-confirmed), not merely
the API enum.

---

## 2. Blend — factors/ops are IN THE SHADER, not a fixed-function packet (HW-clean)

Changing a blend **factor** (`--srgb`/`--drgb`/`--salpha`/`--dalpha`) or **op**
(`--brgbop`/`--balphaop`) leaves `0x58000` and the VDM essentially unchanged and instead
rewrites the **fragment/blend microprogram in the shader-code BO `0x10000000000`**
(`raw/analysis/diff_srgb_*`, `diff_brgbop_*`): e.g. `srgb dstcolor` → 44 changed words in
`0x10000000000`; `brgbop sub` → 51; `balphaop min` → 13; the `0x58000` FF-state pool does
not carry the factor. **Consequence for the implementer: there is no blend factor/op code
table to emit — blend must be lowered into fragment-shader code** (Apple TBDR programmable
blend). *(We only located this program; we did not disassemble it — clean-room rule 5.)*

Fixed-function blend/write state that DOES live in `0x58000`:
| field | offset | evidence |
|---|---|---|
| **color write mask** (per-channel) | near `+0x5c` (+ coarse bit at `+0x08`) | `wmask` sweep: red=bit0, green=bit1, blue=bit2, alpha=bit3 — **reverse of Metal's mask bit order** |
| blend/write "class" hint | `+0x08` (base `0x500`) | zero-src→`0x4c0`, 1-srccolor→`0x540`, wmask→`0x480` |
| constant-blend-color present | `+0x10` (`+0x40`) | any `blendcolor`/`blendalpha` factor |
| dual/independent flag | `+0x18` (→1) | `1-dstalpha`, `srcalphasat` |
| blend-enable-ish | `+0x50` (→`0x20000200`) | `--blend` (EXP-0014) |

Full write-mask bit isolation is partially entangled because Metal also recompiles the
fragment store when the mask changes (wmask 0 takes a store-disable fast path).

**Blend enable** flag also at `0x10000120000+0x45` bit `0x80` (EXP-0014, corroborated).

### Capability: dual-source & logic ops
* **Dual-source blend — HW-supported (validated).** A pipeline whose FS emits
  `[[color(0),index(0)]]` + `[[color(0),index(1)]]` with `Source1Color/Source1Alpha`
  factors compiles and runs (`status=4`). Because blend is in-shader, the 2nd source is
  just another shader output.
* **Framebuffer logic ops — not exposed by Metal; emulatable for free (inferred).** Blend
  is fully programmable here and the ISA has an all-16-boolean-function bitwise LUT
  (EXP-0013 hyp #1), so Vulkan/GL logic ops lower into the blend shader — no dedicated ROP
  logic-op hardware is needed. (Not directly diff-confirmed since Metal cannot emit it.)

---

## 3. Rasterizer packet — BO `0x58000` (HW-clean)

### Cull / winding / depth-clip word `+0x70` (base `0x00000480`)
| bits | field | codes | evidence |
|---|---|---|---|
| [1:0] | **cull mode** | 0=none, 1=front, 2=back | `cull_front`→`0x481`, `cull_back`→`0x482` |
| 16 `0x00010000` | **front-face winding** | 0=CW, 1=CCW | `front_ccw`→`0x00010480` |
| [11:10] | **depth clip mode** | clip=`0b01` (`0x400`), clamp=`0b10` (`0x800`) | `clip_clamp`→`0x00000880` |
| 7 `0x80` | constant | — | baseline |

### Polygon fill mode (Lines)
`fill_lines` sets flags `+0x34` bit26 + `+0x50` bit26 and flips the raster point/line word
`+0x54`/`+0x58` top nibble `0x0→0x5` (`0x07e00000→0x57e40000`), also touching the depth
word `+0x3a`. (EXP-0014: **primitive** point→nibble `0x4`, line→`0x1`; here polygon-line
**fill**→`0x5`.)

### Depth bias
| field | location | evidence |
|---|---|---|
| **enable** | flags `+0x34` bit17 (`0x00020000`) | set for non-zero constant OR slope; clamp-only ⇒ **not** enabled |
| **constant / slopeScale / clamp** | 3 consecutive floats @ `0x100002a8000 +0x00/+0x04/+0x08` (tiler-param region) | `dbias_all` (2.0/3.0/0.5) = `0x40000000/0x40400000/0x3f000000` |

---

## 4. USC bind grammar + graphics shader-entry word

### VDM bind-pairs (BO `0x18000`) — a fixed template
`raw/hex/base_18000.hex`; the draw stream carries a run of `(control-word, GPU-address)`
pairs (LE):
```
(0x0500, 0x0040)    immediate
(0x0700, 0x58000)   FF-state pool: depth/stencil block
(0x0500, 0x5801c)   FF-state pool
(0x0700, 0x58030)   FF-state pool
(0x0500, 0x5804c)   FF-state pool
(0x0a00, 0x68900)   VIEWPORT block (0x68000+0x900)
(0x0300, 0x58060)   FF-state pool
(0x0200, 0x5806c)   FF-state pool (raster)
(0x0200, 0x48000)   context block
```
then the draw-primitive command (`0x61c4|prim`, vtx@+0x68, inst@+0x6c) and `0xc0000000`
terminator (EXP-0014). **These pairs are INVARIANT** under every depth/stencil/blend/raster
change tested — only the VDM **state-alloc-size field `+0x0c`** grows (`0x4800→0x4c00` for
depth+stencil; `raw/analysis2/` VDM diff). The control word is `0x0X00`; the middle nibble
`X ∈ {2,3,5,7,a}` selects the size/target of each state-block DMA into the USC (exact
mapping **inferred**, not fully decoded).

### Graphics shader binding = USC program `0x10000130000` (HW-clean location)
Unlike compute (a single `shaderVA>>6` word in the CDM record, EXP-0011), the draw path
binds shaders **indirectly through the USC (Uniform/Shader Control) program**:
* It has **3 stage sub-blocks** at `+0x00`, `+0x240`, `+0x480` (each `0x240` B), each led by
  the **register/uniform-config word `0x00880000`** — the *same* encoding as the compute
  CDM config word (EXP-0011/0014). `raw/hex2/bb2_usc_full.hex`.
* Enlarging the **vertex** shader shifts the shared uniform-pointer words `+0x10`/`+0x250`/
  `+0x490` (form `0x0042XXXX`, quantized by `0x4000`/16 KB) and their counts `+0x14/…`
  (form `0x002000XX`). Enlarging the **fragment** shader shifts the *same* words **and
  additionally appends FS-stage USC instructions from `+0x640` onward** — i.e. the 3rd
  sub-block (`+0x480`) is the fragment stage. `raw/analysis2/shader_entry.txt` (VS-big:
  12532 changed code words; FS-big: 12646).
* Shader machine code lives in BO `0x10000000000`.

So the **graphics analogue of `shaderVA>>6`** is a **USC-instruction operand** inside
`0x10000130000` (located, HW-validated it lives in the `+0x10`/`+0x250`/`+0x490` region and
the FS block from `+0x640`), rather than a bare word in the draw command. Its precise
pointer bit-encoding (the `0x0042XXXX` form) is **inferred/opaque** — full decode needs a
USC-instruction disassembly or a finer shader-VA-shift sweep (follow-up).

---

## 5. Marking: HW-validated vs inferred

**HW-validated (single-word diff confirmed):** depth compare (8 codes) + write-disable
bit; stencil compare (8) + 3 op fields (8 codes each) + read/write masks + reference +
front/back split (full `0x046a0f3c` reconstruction); blend factors/ops located in
`0x10000000000` (not `0x58000`); color-write-mask channel bits; dual-source blend
compiles+runs; cull (3) / winding (2) / depth-clip-vs-clamp (2-bit) at `+0x70`; polygon
line-fill raster nibble; depth-bias enable bit + the 3 float values; VDM bind-pair template
invariance + state-size field; USC 3-stage layout + config word + shader-entry region.

**Inferred (byte-diff / structural, not independently exercised):** VDM control-word nibble
semantics; exact USC shader-entry pointer encoding; depth-word `+0x39=0x0f` meaning; blend
`+0x08/+0x18/+0x50` coarse-bit exact meaning; logic-op emulability.

---

## 6. Capability-probe results (proposed `docs/hypotheses.md` rows)

| Capability | Basis | Test | Outcome |
|---|---|---|---|
| Depth **clamp** (vs clip) | Vulkan `depthClampEnable` | `setDepthClipMode:Clamp` → `0x58000+0x70[11:10]` | **WORKS** — native 2-bit field (clip=01, clamp=10) |
| **Dual-source** blend | Vulkan needs Src1 factors | FS `index(0)`+`index(1)` + `Source1*` | **WORKS** — compiles & runs; 2nd source is a shader output |
| **Programmable blend** (factors/ops in shader) | Apple TBDR | vary factor/op → only `0x10000000000` changes | **WORKS/architecture** — no fixed-function factor LUT; blend = shader code |
| Blend **logic ops** | Vulkan/GL; Metal has none | can't emit via Metal; ISA has 16-fn LUT (EXP-0013) + in-shader blend | **INFERRED emulate-for-free** — lower into blend shader; no ROP HW needed |
| **Polygon line** fill | Vulkan `polygonMode=LINE` | `setTriangleFillMode:Lines` | **WORKS** — distinct raster state (nibble `0x5`) |
| Polygon **point** fill | Vulkan `polygonMode=POINT` | not exposed by Metal; point *primitive* raster exists (nibble `0x4`, EXP-0014) | **PARTIAL/INCONCLUSIVE** — point raster path exists; polygon-point-fill not directly drivable |
| **Provoking vertex** selection | Vulkan `VK_EXT_provoking_vertex` | not probed (Metal fixes convention) | **NOT PROBED** — needs flat-shaded multi-vertex diff |
| Independent per-RT blend / MRT | Vulkan | not probed here | **NOT PROBED** |

---

## 7. Opaque / recommended next
1. **USC shader-entry pointer encoding** (`0x10000130000` `0x0042XXXX` words) + the VDM
   control-word (`0x0X00`) nibble → target/size mapping: needs a USC-instruction
   disassembly or a finer shader-VA-shift sweep (allocate padding to move the code BO by a
   controlled amount and watch the operand track it).
2. **Depth word `+0x39` constant `0x0f`** — fixed stencil plane/sample mask?
3. **Full color-write-mask bit isolation** — decouple from the fragment-store recompile
   (mask sweep with a fixed shader / no-blend fast path held constant).
4. **Provoking-vertex** and **MRT / independent-blend** probes.
5. **Depth-bias float BO** `0x100002a8000` sits in the large tiler-param region; confirm
   its stable offset/sub-block across allocations.
6. Bit-decode the remaining `0x58000` sub-blocks referenced by the other VDM pairs
   (`0x5801c/0x58030/0x5804c/0x58060`) — sample positions, occlusion/visibility, etc.

## Established facts → docs
- Depth/stencil/raster field maps + compare/op tables, blend architecture, USC bind
  grammar → `docs/cmdstream/` (graphics section) → `PROVENANCE.md` (DATA-TRACE, EXP-0019).
- §6 capability rows → `docs/hypotheses.md` (orchestrator to merge).

## Deliverables
`svar.m` (harness), `run.sh` (matrix + on-device diffs), `summarize.py` (diff extractor),
`raw/analysis/` + `raw/analysis2/` (diffs), `raw/hex/` + `raw/hex2/` (trimmed control-BO
hexdumps), `README.md`, `RESULTS.md`.
