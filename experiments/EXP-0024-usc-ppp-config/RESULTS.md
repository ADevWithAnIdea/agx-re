# EXP-0024 Results — USC shader-entry, PPP header grammar, CDM config + threadgroup memory

> **SUPERSEDED IN PART (2026-08-17, EXP-0042):** the claims that graphics uses an
> unselected positional code-block walk and that `0x58000+0x08` is an FS byte size are
> falsified by live M4 multi-pipeline/equal-size-FS probes. The retained A18 captures remain
> historical DATA-TRACE evidence; use EXP-0042 for the current selector/container verdict.

**TL;DR.** On A18 Pro / G17P / macOS 26.6, change-one-Metal-parameter byte-diffing (36 captures,
all `status=4`, zero reboots) closes the three acceptance-gate gaps:

* **G-3 (graphics shader-entry).** There is **no `shaderVA>>N` pointer in the userspace command
  stream** — graphics binds shaders fundamentally differently from compute. Proven by exhaustive
  search: growing the fragment shader shifts the vertex-shader code entry by +0x80, yet **no word
  in any registered BO tracks it** (only code-internal *size* headers move), no 8-byte pointer to
  the USC or code BO exists anywhere, and the VDM + firmware-context BOs are byte-identical across
  shader changes. Instead, the **code BO `0x10000000000` is a walk of `[size-header][machine-code]`
  blocks** (stage order `[helpers][FS][VS]…`), and the **USC `0x10000130000` holds per-stage
  uniform-preamble programs** (block0/1 = vertex, block2 = fragment; config word `0x008800XX`).
  The code-BO base is conveyed to firmware via the kernel submit, not a client descriptor.
* **G-7 (PPP header).** **No present-bit mask.** The bind-pair template and pool layout are fixed;
  presence/order is a **monotonic length word** (VDM `0x18000+0x0c` and pool `0x58000+0x14`, which
  grow +0x400 when an optional depth/stencil block is appended) over a fixed layout, with **per-group
  enable bits** inside each packet.
* **G-8 (compute config + tg-mem).** The CDM `+0x00` config word is `0x00080000` (bit19 always set)
  with **bit23 = register/occupancy tier** as the only variable (atomics/barriers/simd/tg-mem do not
  touch it). The **threadgroup-memory size lives in BO `0x10000090000`**, not the CDM, encoded as
  **`(tgmem_bytes << 2) | 0x80`** (HW-validated over 256…32768 B, static and dynamic).

Every field tagged **HW-clean** is a single-word (or clean multi-word) diff from changing exactly
one Metal parameter against a byte-identical baseline (USC determinism: base vs base2 = 0 words).
All raw tables in `raw/FINDINGS_TABLES.txt`.

---

## G-3 — Graphics USC shader-entry word (CRITICAL)

### Method that finally isolated it
Prior work ("big shader", EXP-0014/0019) entangled *code growth* + *uniform-region growth* and never
isolated the entry. Two clean levers here:
* `--pad N` keeps the real shaders **byte-identical** and tries to relocate them (dummy pipelines).
* `--fsz K` grows the **first** shader (fragment) by K FMA blocks, which pushes the **second** shader
  (vertex) entry by a measured +0x80 — a true code-entry move.

### Finding 1 — the USC does NOT encode a code address (HW-clean, exhaustive)
Under `--fsz4` the fragment shader grew 0x80 and the **vertex entry moved +0x80**. An exhaustive
search over *every* registered BO for any word changing by the shift (`+0x80`, or `+0x80>>6 = +0x2`)
returns only:

| BO + off | change | meaning |
|---|---|---|
| `0x58000 +0x08` | `0x4c0 → 0x540` (+0x80) | **fragment-shader code size (bytes)** |
| `0x10000000000 +0x340` | `0x140 → 0x1c0` (+0x80) | code-BO **FS block size** header |

Both are **sizes**, not pointers. Corroborating negatives (all HW-clean):
* **No 8-byte pointer** to the USC BO (`0x10000130000`) or into the code BO (`0x10000000000`)
  exists in any registered BO (pointer scan).
* **VDM `0x18000` and context BOs `0x28000/0x38000/0x48000` = 0 diffs** under any shader change.
* `0x58000+0x08` = FS code size, confirmed: base `0x4c0`; `vsz4` (VS grew) **unchanged** `0x4c0`;
  `fsz4` `0x540` (+0x80); `fsz8` `0x5c0` (+0xc0).

**Conclusion: graphics has no `shaderVA>>N` word.** This is the opposite of compute (CDM `+0x08 =
shaderVA>>6`, EXP-0011). A first-class negative result — it tells the implementer the graphics
shader entry is **not** a userspace descriptor field.

### Finding 2 — how the machine code IS addressed: a self-describing block walk (HW-clean)
The code BO `0x10000000000` is a sequence of `[size-header][machine-code]` blocks:

| offset | value (base) | tracks | role |
|---|---|---|---|
| `+0x00` | `0x340` | constant | offset to first shader block (leading helper region) |
| `+0x340` | `0x140` | grows with **FS** (`0x140→0x1c0→0x240`) | **FS (#1) block size** |
| `+0x500` | `0x140` | grows with **VS** (`0x140→0x1c0→0x240`) | **VS (#2) block size** |

Stage order in the BO is `[helpers][FS][VS][more helpers]`; the hardware walks the blocks from the
code-BO base. **A driver emits the compiled machine code as sized blocks and hands the code-BO base
to the firmware** — the per-stage entry is positional, not an emitted pointer.

### Finding 3 — the USC `0x10000130000` structure (HW-clean)
Three `0x240`-byte per-stage **uniform-preamble programs** (the compute `constant_program` analogue,
EXP-0020), NOT code-entry descriptors:
* **block0 `+0x00` and block1 `+0x240` are byte-identical** (vertex preamble, duplicated); **block2
  `+0x480`** is the fragment preamble.
* Each led by config word at `+0x04` = **`0x008800XX`**, `XX = 0x00 / 0x0c / 0x18` = stage index ×
  `0x0c` (same `0x0088` register-config high half as the compute CDM word).
* `+0x10/+0x18/+0x250/+0x490` = **uniform-DATA pointers** (form `0x0042XXXX`): shift `+0x4000` per
  16 KB when **VS** grows, unchanged when FS grows → uniform pointers, not code pointers.
* `--pad` increments per-shader **id/count** fields `+0x14/+0x254/+0x494/+0x644` (form `0x002000XX`,
  +2 per pad = 1 VS + 1 FS) — a shader-slot id, not an address.

**What a driver must emit for shader binding (graphics):** (a) the machine code as sized blocks in
the code BO; (b) the per-stage uniform-preamble programs in the USC BO (config `0x008800XX`, uniform
pointers, slot ids). The **code-BO base → firmware handoff is a userspace↔kernel item** (flag for
the kernel team; it is not a client-writable descriptor we can capture).

---

## G-7 — PPP fixed-function header + emission-order grammar (HIGH)

**There is no present-bit mask.** Toggling state groups shows the bind-pair template and pool
layout are **fixed**; presence is a **length/count word**, not a bitmask:

* **VDM `0x18000`** header = `0x4000002e` (flag | length `0x2e` words) + a **fixed 8 `(control16,
  address)` bind-pair template** into the pool — *invariant* under every depth/stencil/blend/raster
  toggle. The only VDM change is `+0x0c` **state-alloc size** `0x4800 → 0x4c00` (**+0x400**), and
  only when a depth/stencil block is present (blend/cull alone: **0 VDM diffs**).
* **Pool `0x58000`** mirrors it: `+0x14` state size `0x4c19 → 0x5019` (+0x400) for depth/stencil.
  The optional **depth/stencil block adds 0x400 bytes**; everything else is a fixed slot.

Per-group presence is encoded by **enable bits inside each packet** (HW-clean, base→toggle):

| group | field(s) in `0x58000` | enable evidence |
|---|---|---|
| depth | `+0x34` bit18 (`0x00040000`) clears; `+0x38/+0x40` `0x07200f00→0x01000f00` | `--depth` |
| stencil | `+0x34` bits[19:18] `→0x000c0000`; `+0x3c/+0x44` `0x0e000000→0x0202ffff` | `--stencil` |
| blend | `+0x08` (FS size — blend is in-FS), `+0x18 0→1`, `+0x50 0x200→0x20000200` | `--blend` |
| cull | `+0x70` bits[1:0] (`0x480→0x482`) | `--cull back` |

A disabled group takes a canonical "off" encoding (depth word `0x07200f00` = compare-always +
write-off; stencil word `0x0e000000`). **Emission grammar to assemble a valid 3D state block:** emit
the fixed pool layout + the fixed 8 bind-pairs; set each group's enable bits; if depth/stencil is
used, append its 0x400-byte block and add 0x400 to the length word (`0x18000+0x0c` and `0x58000+0x14`).
(Consistent with EXP-0019's per-packet bit decode, now framed as the header/length grammar.)

---

## G-8 — Compute CDM `+0x00` config word + threadgroup-memory size (HIGH)

### Config word `0x100000b0000 +0x00` (HW-clean)
| kernel | config | note |
|---|---|---|
| add3 / atom / barr / simd | `0x00080000` | baseline |
| heavy (reg-heavy) | `0x00880000` | **bit23 set** |
| tgdyn(256…32768) / tgs(256…32768 B) | `0x00080000` | tg-mem does **not** touch it |

* **bit19 (`0x00080000`)** — always set (compute type/enable); constant across all kernels.
* **bit23 (`0x00800000`)** — register/occupancy **tier** (set for the register-heavy kernel; matches
  EXP-0020's ≥~12-GPR boundary).
* **Everything else 0** for atomics, barriers, `simd_sum`, and threadgroup memory (dynamic *and*
  static). So the config word is `bit19 | (tier ? bit23 : 0)` for these workloads; the exact GPR/
  scratch/uniform footprint is in the shader `__GPU_METADATA` (EXP-0020), not this word.

### Threadgroup-memory size → BO `0x10000090000`, **not** the CDM (HW-validated)
The dynamic-size sweep leaves the CDM record byte-identical (confirms EXP-0011). The size is a
16-bit field in the compute preamble/pipeline BO `0x10000090000`:

| tgmem bytes | field value | `(bytes<<2)|0x80` |
|---:|---|---|
| 256 | `0x0480` | `0x0480` |
| 1024 | `0x1080` | `0x1080` |
| 4096 | `0x4080` | `0x4080` |
| 16384 | `0x10080` | `0x10080` |
| 32768 | `0x20080` | `0x20080` |

**Formula (HW-validated): field = `(tgmem_bytes << 2) | 0x80`.** Location:
* **static** (`threadgroup float sh[N]`): `0x10000090000 +0x40` (low 16 bits).
* **dynamic** (`setThreadgroupMemoryLength:`): `0x10000090000 +0x4c` bits[31:16] (carries into `+0x50`
  for ≥ 16 KB).

The offset differs because the field is an **operand inside the per-kernel preamble program**; the
*value encoding* is identical for static and dynamic. (The `<<2` factor / `0x80` low bits are the
observed field granularity+flag; marked HW-validated by the exact 5-point fit, bit-layout inferred.)

---

## Marking: HW-validated vs inferred

**HW-validated (single/clean multi-word diff confirmed):**
G-3 — no `shaderVA>>N` in the client stream (exhaustive delta-search + pointer scan); code-BO
`[size-header]` block layout (+0x340 FS size, +0x500 VS size); `0x58000+0x08` = FS code size; USC
block0≡block1, config `0x008800XX`, uniform-pointer vs id/count fields; VDM/context invariance.
G-7 — VDM/pool length word `+0x400` for depth-block presence; fixed bind-pair template; per-group
enable bits.
G-8 — config word map (add3/heavy/atom/barr/simd/tg sweep); tg-mem field `(bytes<<2)|0x80` at
`0x10000090000` (5-point static + dynamic).

**Inferred / architectural:**
G-3 — the code-BO-base → firmware handoff mechanism (kernel-interface, not client-visible); the
exact main↔preamble linkage inside the compiler-generated preamble (deliberately not disassembled,
clean-room rule 5). G-8 — the `<<2`/`0x80` internal bit-layout (value fit is exact; alignment
inferred). G-3 config low-nibble stage stride `0x0c` semantics.

---

## Opaque / recommended next
1. **G-3 firmware handoff of the code-BO base** — the one piece not in userspace BOs: coordinate with
   the kernel team (what names `0x10000000000` as the shader code region at submit).
2. Bit-layout confirmation of the tg-mem `<<2`/`0x80` field with a **non-power-of-two** size sweep.
3. Config-word bits beyond 19/23: probe printf/indirect-dispatch/ray-query kernels for any new bit.
4. USC uniform-pointer `0x0042XXXX` full decode (which heap it indexes; VS-only 16 KB quantum).

## Established facts → docs
- G-3 graphics shader-binding architecture (no `shaderVA` word; code-BO block walk; USC preamble
  structure), G-7 PPP length-word grammar + per-group enable bits, G-8 config-word map + tg-mem
  `(bytes<<2)|0x80` at `0x10000090000` → `docs/cmdstream/` → `PROVENANCE.md` (DATA-TRACE, EXP-0024).

## Deliverables
`gvar.m`, `cvar2.m`, `magloc.py`, `run.sh`, `raw/FINDINGS_TABLES.txt`, `raw/ana/` (diffs),
`raw/hex/` (trimmed control-BO hexdumps), `README.md`, `RESULTS.md`. Clean-room: DATA-TRACE +
OWN-SHADER; no Apple binary inspected; `.bin`/archives stayed on-device under `~/cleanroom_work/exp0024/`.
