# A18 Pro (G17P) Userspace ↔ Kernel/Firmware Interface

The **abstract boundary contract** between the Mesa userspace driver and the kernel/firmware:
what userspace builds and hands down, versus what the kernel/firmware owns. This document
**consolidates** the "firmware-managed" / "route via kernel" findings that are scattered across
the other docs into one authoritative boundary, and **reconciles** the one place the docs
appear to contradict themselves (ZLS / sample positions — see §6, gap **G-11**).

> **Status: synthesis (host-only).** Every fact here is traceable to an already-established
> finding in another `docs/` file — the citation is given inline. This doc introduces **no new
> RE**; it re-organises existing facts around the kernel boundary and settles G-11/G-12 so the
> userspace and kernel teams can agree on a single contract. Per `../CLAUDE.md`, the kernel
> driver itself is **out of scope** — we document only *what userspace must hand it*.

> **Clean-room note.** Sources are our own `docs/` (black-box data traces, hardware probes,
> own-shader disassembly) plus the **open-source** Mesa/Linux UAPI header
> `../mesa/include/drm-uapi/asahi_drm.h` (Mesa is the driver we target — explicitly allowed;
> `mesa-userspace-requirements.md` already summarises it). Register/field *names*
> (`ZLS_CTRL`, `PPP_MULTISAMPLECTL`, `ISP_*`) are used only as bare hardware/UAPI nomenclature
> (`../CLAUDE.md` rule 3). No Apple binary was disassembled.

---

## 1. The boundary in one sentence

On G13/G14 (and, by observation, on G17P) **userspace owns essentially all GPU *programming***
— it compiles shaders, builds the VDM/CDM/PPP control streams word-by-word in BOs, and packs all
descriptors — while the **kernel/firmware owns *submission and a small set of render-pass control
registers*** that the firmware programs on userspace's behalf because the kernel↔firmware ABI is
not stable (`mesa-userspace-requirements.md` §1; `cmdstream/README.md` "Submission model").

Two consequences drive everything below:

1. **Work crosses the boundary as BOs + a submit, not as an opcode stream copied into a syscall.**
   Userspace assembles command buffers in GPU-visible memory and hands the kernel *the set of BOs
   and a submit request*; the kernel/firmware consumes them (`cmdstream/README.md` "Submission
   model — shared-memory + doorbell").
2. **A handful of firmware *register* values also cross the boundary — as submit *parameters*,
   not as command-stream packets.** These are the ZLS / sample-position / tilebuffer-sizing values
   the firmware writes into its command context (§6).

---

## 2. Submission model — shared-memory ring + doorbell

Established in `cmdstream/README.md` ("Submission model", EXP-0009/EXP-0011):

- Modern macOS 26 Metal does **not** issue one ioctl per submit. The IOKit call count is
  **invariant** under the number of submits (compute: 49 calls for 1/3/5 submits; draw: 58), yet
  every submit runs. Work is encoded into ordinary userspace VM buffers registered into the GPU
  address space; submission is via a **shared-memory ring + doorbell**.
- The **ring** lives in shared memory (`gpu_va ~0x10000050000`): a **producer index increments by
  0x58 bytes per submit**, with fixed-size completion records at the same cadence.
- **The doorbell store is NOT an IOKit / mach-vm call.** It is a store into a **firmware-shared
  page + barrier** — invisible to the userspace interposer (`cmdstream/README.md` "Submission
  ring / doorbell").

**Implication for the Linux/`drm_asahi` port.** Because the doorbell lives in a firmware-shared
page rather than behind an IOKit selector, the natural split on Linux is: **userspace builds the
command buffers in BOs and calls a submit ioctl; the *kernel* advances the ring and rings the
doorbell** on userspace's behalf. Userspace does not touch the doorbell directly. (This matches
Mesa's existing UAPI, where `DRM_IOCTL_ASAHI_SUBMIT` carries the command and the kernel owns the
firmware ring — `mesa-userspace-requirements.md` §2f.)

The macOS IOKit surface that a Linux submit ioctl abstracts (inventory only, from
`cmdstream/README.md` "Userspace↔kernel IOKit interface" and `hardware-overview.md` §4):

| macOS selector | role | Linux/`drm_asahi` analogue |
|---|---|---|
| `0x8` | create queue | `QUEUE_CREATE` |
| `0x7` | one-time setup (1040-byte struct = **executable-path string**, *not* ring config) | (n/a) |
| **`9`** | **map resource → GPU VA** (see §3) | `GEM_CREATE` + `VM_BIND` |
| `0x11` | completion / notify queue | fence / sync object |

There is **no graphics-specific "submit" selector**: a draw uses the same shared-mem + doorbell
path as compute, just registering more BOs (~39 vs ~13) (`cmdstream/README.md` "Graphics (draw)
command stream").

---

## 3. Resource mapping and the GPU VA space

### 3.1 The map primitive (sel-9)

Mapping a BO into the GPU address space is the **`9`** selector (`cmdstream/README.md`
"Userspace↔kernel IOKit interface"), HW-confirmed:

- **in @0x38** = CPU base of the buffer
- **in @0x48** = size
- **out @0x00** = the assigned **GPU VA** (proven: returned `0x10000030000`, matching the
  buffer's Metal `gpuAddress`)

A compute dispatch performs ~30 such maps; a draw ~39 (plus a second IOSurface map). On Linux this
is `GEM_CREATE` + `VM_BIND` (BO alloc + VA bind); the 16 KiB page/alignment constraints from
`mesa-userspace-requirements.md` §2f apply (all bind offsets/addresses/ranges 16 KiB-aligned; the
device uses 16 KiB pages, `hardware-overview.md` §2).

### 3.2 Observed VA-space layout

Consolidated from `cmdstream/README.md` (EXP-0009/0011/0014/0024) and `pipeline/README.md`
(EXP-0021). Two regions are distinguished by VA magnitude; a **second, orthogonal** axis is *who
authors the bytes* (client resource vs submission/firmware machinery).

**Region A — firmware / queue-context (VA `< 0x10000000000`).** Per-queue structures the firmware
reads at *fixed offsets*. Userspace writes the packet *content*, but the region is part of the
firmware-shared queue context and its base is handed to the firmware in the submit (e.g.
`vdm_ctrl_stream_base`, §6.1):

| GPU VA | role | content authored by |
|---|---|---|
| `0x18000` | **VDM / tiler draw stream (TA)** — draw records, USC bind-pairs, primitive words | userspace |
| `0x58000` | **3D fixed-function state pool** — depth/stencil/blend-adjacent/raster packets | userspace |
| `0x68000` | **viewport / tiling context** — tile counts `+0x904/+0x908`, viewport transform `+0x910` | userspace |

**Region B — resource heap (VA `>= 0x10000000000`).** General client resources; base of the heap
observed at `0x10000000000`:

| GPU VA | role | content authored by |
|---|---|---|
| `0x10000000000` | **shader code BO** (self-describing `[size-header][machine-code]` blocks) | userspace (compiled shaders) |
| `0x10000090000` | compute shader-code BO (threadgroup-mem size `@+0x40`) | userspace |
| `0x100000e0000` | **Tier-2 argument buffer** (resource table `@+0x14a0`, 8 B/slot) + appended texture/sampler descriptor blocks | userspace |
| `0x10000100000` | vertex-attribute table | userspace |
| `0x10000110000` | **3D attachment (render-target) descriptor** (relocates into the tiler heap under MSAA) | userspace |
| `0x10000130000` | **USC shader-binding program** (per-stage uniform preambles) | userspace |
| `0x10000018xxx` / `0x10000140000` | **tiler parameter buffer** (TA→3D geometry heap) | allocated by userspace, **written by the tiler HW** during the TA phase |

**Submission machinery (numerically in Region B, but firmware/queue-owned):**

| GPU VA | role | notes |
|---|---|---|
| `~0x10000050000` | **submission ring** (producer index +0x58/submit) | ring managed by firmware/queue; userspace enqueues records |
| `0x100000b0000` | **CDM compute launch descriptor** stream (0x2c-byte records + `0x40000000` terminator) | records authored by userspace; consumed by firmware to launch dispatches |

> **Note on classification.** The submission ring and the CDM launch descriptor are *submission
> machinery* (firmware-consumed), but their **observed VAs are `>= 0x10000000000`** — i.e. they sit
> numerically inside the resource heap, not below `0x10000000000`. A driver should treat "firmware
> vs client" as a **semantic** distinction (who consumes the structure) rather than a strict VA
> cutoff; the only structures observed *below* `0x10000000000` are the three queue-context BOs
> (`0x18000/0x58000/0x68000`).

### 3.3 Who fills what

- **Userspace fills** (both regions): all VDM/CDM control-stream words, all PPP/FF-state packets,
  the viewport/tile-count context, compiled shader code, the argument buffer + descriptor blocks,
  the render-target attachment descriptor, the USC shader-binding program, the vertex-attribute
  table, and the CDM launch-descriptor records.
- **Firmware/kernel sets up** (opaque to userspace): the firmware **command context** (the control
  registers listed in §6), the ring/doorbell mechanics (§2), the **BVH** for ray tracing (§4.1),
  the **partial-render** machinery (§4.4), and the **graphics shader-entry handoff** (§4.5).
- **Written by hardware, not either driver:** the **tiler parameter buffer** content — userspace
  *allocates* it, the tiler (TA) *writes* it during the vertex/tiling phase, and the fragment (3D)
  phase *consumes* it (`pipeline/README.md` "Load/store actions & partial render").

---

## 4. Explicitly firmware/kernel-managed (userspace does NOT emit these in the command stream)

Each item below appears in the other docs as "firmware-managed / route via kernel". For each: what
**userspace provides**, and what the **kernel/firmware must do**.

### 4.1 Acceleration-structure (BVH) build + node format — `isa/README.md` (EXP-0023)
- **Userspace provides:** the geometry **vertices** + a **build descriptor**, and at trace time an
  **8-byte GPU VA to the acceleration structure** in the Tier-2 argument buffer.
- **Kernel/firmware does:** the **BVH build** is GPU/firmware-managed — the GPU writes the BVH; the
  **BVH node format is NOT userspace-visible**. A userspace RT implementation supplies inputs and a
  handle and must treat the built structure as opaque. (The HW *traversal* primitives
  `rt_intersect`/`rt_as_load` **are** userspace ISA — only the *build/format* is firmware-owned.)

### 4.2 Programmable MSAA sample positions — `pipeline/README.md` (EXP-0021), hypothesis #15
- **Userspace provides:** the **packed sample-position value** (Mesa packs 4-bit x/y nibbles into
  `PPP_MULTISAMPLECTL`: 1×=`0x88`, 2×=`0x44cc`, 4×=`0xeaa26e26` — `mesa-userspace-requirements.md`
  §2e).
- **CORRECTED (RT-4): sample positions ARE userspace-emittable** — written to a client BO (`0x100000e8000` 4× /
  `0x100000e0000` 2×) at **+0x40** (N `(x,y)` f32 pairs, 1/16-grid). So this is **NOT** a kernel-managed item; a Mesa
  userspace driver emits them directly into the sample-position BO. (EXP-0021's "byte-identical" diffed the wrong BOs.)

### 4.3 Depth / ZLS store-action — `pipeline/README.md` (EXP-0021)
- **Userspace provides:** the **ZLS control value** and the depth/stencil buffer parameters (see
  §6: `zls_ctrl`, `depth`/`stencil`, `isp_zls_pixels`, clear values).
- **Kernel/firmware does:** programs the ZLS (Z Load/Store) unit registers. The **depth
  store-action / ZLS is not captured in any userspace BO** — it is firmware-managed → route via the
  kernel submit (§6).

### 4.4 Partial-render / tiler-param overflow trigger — `pipeline/README.md` (EXP-0021)
- **Userspace provides:** the tiler parameter buffer allocation and (in the Linux model) the
  `partial_bg`/`partial_eot` programs used when a render is split (§6.2).
- **Kernel/firmware does:** detects tiler-parameter-buffer **overflow** and triggers the
  **partial render** (flush tiles, resume). There is **no userspace knob** for the trigger — it is
  firmware-managed.

### 4.5 Code-BO-base → firmware handoff for graphics shader dispatch — `cmdstream/README.md` (EXP-0024)
- **Userspace provides:** the compiled code as **self-describing sized blocks** in the code BO
  (`0x10000000000`) and the per-stage **USC uniform-preamble programs** (`0x10000130000`).
- **Kernel/firmware does:** binds the shader for dispatch. Unlike compute (which carries an explicit
  `shaderVA>>6` in the CDM launch record), **a draw carries NO shader pointer anywhere in the client
  command stream** (exhaustive delta-search found only *sizes* tracking a growing shader, never an
  8-byte pointer). The base of the code BO reaches the firmware out-of-band. → **flag as a
  userspace↔kernel item**: the Linux submit must convey the code-BO base (analogous to
  `vdm_ctrl_stream_base`, §6.1), and the firmware performs the actual entry bind.

---

## 5. What userspace still owns (for contrast — do NOT route these to the kernel)

To keep the boundary unambiguous, these are **userspace command-stream** content and must **not**
be treated as kernel-populated:

- **Blend / dual-source blend / framebuffer logic ops** — **compiled into the fragment shader**
  (the shader-code BO), *not* a fixed-function packet and *not* a kernel field
  (`cmdstream/README.md` "Blend is programmable", EXP-0019). `0x58000` keeps only color-write-mask +
  blend-class/constant/enable flags.
- **Depth/stencil compare & ops, rasterizer state (cull/winding/depth-clip-vs-clamp/line-fill/depth
  bias)** — PPP packets in `0x58000` that userspace writes (`cmdstream/README.md` "Depth/stencil
  packet", "Rasterizer packet", EXP-0019).
- **Viewport transform + tile counts** — userspace writes into `0x68000` (`pipeline/README.md`
  "Tile size").
- **All descriptors** (texture 32 B, sampler 8 B, buffer inline VA) and the **argument buffer** —
  userspace (`descriptors/README.md`).
- **Texture memory layout** (Morton twiddle, mip tree, compression aux placement) — userspace
  (`tiling/README.md`).

---

## 6. Reconciling the contradiction (G-11): ZLS & sample positions — firmware **or** userspace?

`GAP-ANALYSIS-01.md` ("Contradictions & unexplained magic values") flags an apparent conflict:

- `pipeline/README.md` says depth store-action / ZLS and programmable sample positions are
  **"firmware-managed … route via kernel"** — implying they are *not* a userspace responsibility.
- `mesa-userspace-requirements.md` §1/§2b documents these same values (`ZLS_CTRL`, ISP scissor/merge,
  tilebuffer sizing, sample control) as fields **filled by userspace** in `drm_asahi_cmd_render`.

**Resolution — both are right; they describe different layers, and the boundary is a *submit
parameter*.** At the **hardware level** these are **firmware / control-register state**: the
firmware must set a large number of control registers at render-pass granularity, and the
kernel↔firmware struct ABI is deliberately *not* exposed to userspace
(`../mesa/include/drm-uapi/asahi_drm.h`, `struct drm_asahi_cmd_render` doc comment; summarised in
`mesa-userspace-requirements.md` §1). Therefore, in the **Linux/`drm_asahi` model**:

> These values are **kernel-populated fields of the render-pass command context**, passed by
> userspace as **parameters to the kernel submit ioctl** — they are **NOT emitted inside the Mesa
> userspace VDM/PPP command stream** in the BOs. Userspace *computes the register value*; the
> **kernel/firmware writes it into the firmware command context.**

This is exactly consistent with both docs: `pipeline/README.md` is correct that the values are
**absent from every userspace BO** (nothing to emit in the command stream); `mesa-userspace-
requirements.md` is correct that **userspace still computes and hands them down** (as ioctl args,
not packets). The two are not in conflict once "hand down as a submit parameter" is distinguished
from "emit into the command stream."

### 6.1 The render-pass submit fields (`drm_asahi_cmd_render`) userspace fills

These are the concrete "userspace fills field X, firmware owns register Y" contract. Field set from
`../mesa/include/drm-uapi/asahi_drm.h` (`struct drm_asahi_cmd_render`), cross-referenced to the
findings that make each one a *kernel*-boundary item:

| Submit field (userspace computes → firmware writes) | HW register / role | doc that flags it firmware-owned |
|---|---|---|
| `ppp_multisamplectl` | `PPP_MULTISAMPLECTL` — **sample positions** (packed 4-bit x/y) | `pipeline` MSAA § →§4.2 |
| `zls_ctrl` | `ZLS_CTRL` — **depth/stencil load/store** control | `pipeline` load/store § →§4.3 |
| `depth`, `stencil` (`drm_asahi_zls_buffer`) | Z/S buffer base/stride/tiling/compression | `pipeline` §4.3; note Z/S are **separate resources** (no packed D24S8, `hardware-overview.md` §3) |
| `isp_zls_pixels` | `ISP_ZLS_PIXELS` — depth/stencil width/height | `mesa-req` §2b |
| `isp_bgobjdepth`, `isp_bgobjvals` | depth clear value / stencil clear (low 8 bits) | `cmdstream` attachment clear |
| `isp_scissor_base`, `isp_dbias_base`, `isp_oclqry_base` | scissor / depth-bias / occlusion-query descriptor arrays | `mesa-req` §2b/§2e |
| `samples`, `sample_size_B`, `utile_width_px`, `utile_height_px`, `width_px`, `height_px`, `layers` | tilebuffer sizing + framebuffer dims (kernel also needs these to build tiling data) | `pipeline` tile model; `mesa-req` §1 |
| `isp_merge_upper_x/y` | HW triangle-merge (`tan(60°)·dim`) | `mesa-req` §2b |
| `vdm_ctrl_stream_base` | base of the userspace-built **VDM control stream** (Region A `0x18000`) | `cmdstream` (EXP-0014) |
| `bg`, `eot`, `partial_bg`, `partial_eot` (`drm_asahi_bg_eot`) | background / end-of-tile / partial-render programs | `pipeline` §4.4 |
| `flags`, `ppp_ctrl`, `sampler_heap`, `sampler_count` | render flags, PPP control, sampler-heap base/count | `mesa-req` §2b |

The compute counterpart (`drm_asahi_cmd_compute`) is much thinner — it carries the CDM control
stream base, `sampler_heap`/`sampler_count`, and flags — because compute has no render-pass
register state (no ZLS, no sample positions, no tilebuffer). This asymmetry is itself the tell:
**the kernel-populated fields exist because of the *fragment/render* firmware context, not
compute.**

### 6.2 Boundary summary table (the unambiguous split the two teams agree on)

| Thing | Emitted in userspace command stream? | Handed to kernel as submit param? | Firmware/kernel owns |
|---|---|---|---|
| VDM/CDM/PPP packets, descriptors, shader code | **yes** (in BOs) | base pointers only | consumes BOs |
| Blend / logic-op / dual-source | **yes** (compiled into FS) | no | — |
| Sample positions | **no** | **yes** (`ppp_multisamplectl`) | writes register |
| ZLS / depth store | **no** | **yes** (`zls_ctrl`, `depth`/`stencil`) | writes ZLS regs |
| Tilebuffer sizing / scissor / dbias / occlusion base | **no** | **yes** (`isp_*`, `samples`, `utile_*`) | writes ISP regs |
| RT BVH build + node format | **no** | vertices + build desc | builds BVH (opaque) |
| Partial-render trigger | **no** | `partial_bg`/`partial_eot` programs | detects overflow, triggers |
| Graphics shader-entry bind | **no** (no `shaderVA>>N` in draw stream) | code-BO base (out-of-band) | binds entry |
| Doorbell / ring advance | **no** | submit ioctl | rings doorbell |

---

## 7. What the kernel driver must provide to userspace

The minimal set the userspace driver depends on (for coordination with the kernel team; lower
priority per `../CLAUDE.md`, but in scope as interface notes — `mesa-userspace-requirements.md` §2f,
`GAP-ANALYSIS-01.md` gap #7/#13):

1. **BO allocation + VA bind** — create GPU-visible buffers and map them to GPU VAs (macOS sel-9 →
   Linux `GEM_CREATE` + `VM_BIND`). 16 KiB alignment on all bind offsets/addresses/ranges; BOs
   rounded to 16 KiB (device page size = 16 KiB, `hardware-overview.md` §2).
2. **Submit** with the **command-BO set** and the base pointers of the control streams
   (`vdm_ctrl_stream_base`, the CDM control-stream base, the code-BO base handoff of §4.5). The
   kernel advances the ring and **rings the doorbell** (§2) — userspace never touches the doorbell.
3. **Sync / fences** — completion signalling (macOS sel `0x11` → Linux DRM sync objects) so
   userspace can order and wait on submits.
4. **The kernel-populated render-pass fields of §6.1** — userspace computes the values; the kernel
   marshals them into the firmware command context (this is the ZLS / sample-position / tilebuffer
   contract). The kernel also uses several of them (`width_px`/`height_px`/`utile_*`/`samples`) to
   build tiling data structures itself.
5. **Read-only hardware params** — the driver-facing topology/limits the kernel exposes
   (`drm_asahi_params_global`-shaped: `gpu_generation`/`variant`, `num_clusters_total`,
   `num_cores_per_cluster`, `core_masks[]`, `vm_start`/`vm_end`, timestamp frequency, feature bits).
   For this unit these correspond to G17P, 5 active cores / 1 cluster, `usc_gen=3`
   (`hardware-overview.md` §2). `mesa-userspace-requirements.md` §2f.

---

## 8. Open items (unknowns the kernel team must still close)

Faithfully carried from the source docs — do not treat as decided:

- **The exact CPU→GPU doorbell store** (firmware-shared page + barrier) is not observable from the
  userspace interposer — its precise location/encoding is a **kernel-side** question
  (`cmdstream/README.md` "Submission ring / doorbell").
- **The 3-segment (load/render/store) attachment grammar** and the **store-program id `0x6f`** are
  only partially decoded — where the ZLS/store split lands between the userspace attachment
  descriptor and the kernel `zls_ctrl` field needs the segment grammar finished
  (`cmdstream`/`pipeline` open items; `GAP-ANALYSIS-01.md` magic-value list).
- **BVH node format** and the RT "reorder" stage are firmware-owned and undocumented by design
  (`isa/README.md` EXP-0023 follow-ups).
- **Raw accel-node config values** `num_gps=2`, `num_frags=6`, `is_sksm=1`,
  `kickid_qid_shift=40`/`_mask=127` are read but their submit-side semantics are unconfirmed — they
  may map to queue/submission fields the kernel needs (`hardware-overview.md` §2;
  `mesa-userspace-requirements.md` §5).

---

## Provenance
Synthesis of: `cmdstream/README.md` (EXP-0009/0011/0014/0019/0024 — submission model, VA layout,
sel-9, USC/shader handoff), `pipeline/README.md` (EXP-0021 — sample positions, ZLS, partial
render), `isa/README.md` (EXP-0023 — RT BVH firmware build), `hardware-overview.md` (§2/§4 —
topology, IOKit inventory), `mesa-userspace-requirements.md` (§1/§2b/§2e/§2f — the `drm_asahi`
model and field set), `reviews/GAP-ANALYSIS-01.md` (gap #7/#13 and the G-11 contradiction). UAPI
field names grounded in the open-source `../mesa/include/drm-uapi/asahi_drm.h`. No new experiment;
no Apple binary introspected.

## Scratch / doorbell / uniform-heap (EXP-G1a/G1b, objective-1 gap G1-d → kernel-managed)
Userspace declares the per-thread **scratch (spill) size** in the shader's own `__GPU_METADATA` (EXP-0020); the **scratch
buffer allocation + per-core scratch geometry**, the **`0x0042XXXX` uniform-data heap base**, the **code-BO→firmware
shader handoff**, and the **CPU→GPU doorbell store** are all **kernel/firmware-managed** (not in any client BO). A Mesa
userspace driver emits the scratch-size metadata and buffer/USC contents; the kernel allocates scratch, binds the heaps,
and rings the doorbell. (These correlate with the un-RE'd per-core geometry — a kernel-team RE item, not userspace.)

