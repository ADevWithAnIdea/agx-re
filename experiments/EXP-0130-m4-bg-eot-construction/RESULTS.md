# RESULTS -- EXP-0130: M4 BG/EOT construction (P0.4 / DRV-UAPI-04)

**Target:** local Apple M4 / G16G, this host only. macOS 26.6.2 (25G82), Metal 4.
M4-only; no A18 Pro evidence exists or is claimed here (A18 Pro is hands-off).

**Gated evidence:** `raw/m4_20260828_run01/`, `raw/m4_20260828_run02/`, 23/23
records each (3 structural + 20 behavioral), 0 fail, 0 timeout in both.
`analysis/verify.py --selftest` **PASS 14/14**, `--seqtest` **PASS 6/6**,
`--captured --run01 m4_20260828_run01 --run02 m4_20260828_run02` **PASS
10/10** -- byte-exact cross-run reproduction of every non-timing field, every
behavioral case matches its float32 oracle exactly in both runs
independently, the structural op-presence claim holds identically in both
runs, and the paired-control invariant holds in both runs.

## Verdict

**PARTIAL. P0.4 is not closed** (per its own closure rules, closing requires
all four programs' full field/ABI spec with adversarial validation, plus
partial-render trigger characterization this experiment does not attempt).
This experiment **advances construction concretely**: (1) the exact UAPI
field shape of all four programs, cited to the pinned `mesa/` reference with
file/line; (2) a fresh, HW-validated-on-M4 construction of a program that
performs the core EOT operation -- read the tilebuffer, write an attachment
-- via the same ISA instructions (`tile_read`, `frag_color_store`) Mesa's
own from-scratch EOT program uses, together with a decisive structural
finding about which authored shapes actually reach those instructions and
which the compiler silently elides; (3) a rigorous, checked (not assumed)
bounded negative on why the literal `drm_asahi_bg_eot.usc`/`rsrc_spec`
fields cannot be registered through any path reachable from this host; and
(4) a precisely cited answer for what `partial_bg`/`partial_eot`
additionally require beyond `bg`/`eot`.

---

## 1. OBSERVED vs INTERPRETED

### 1.1 H1 -- an EOT-shaped read+write program is constructible and executes correctly

**OBSERVED** (`raw/m4_20260828_run0{1,2}/records.jsonl`, both runs
byte-identical): for all 8 `dst` boundary/asymmetric cases (zero, small
integers, large mixed-sign fractional, `+-2^126`/`+-2^-120`, tiny
power-of-two fractions, an asymmetric mix with a large negative, a
signed-zero probe), `f_eot_evict`'s measured output equals `dst` exactly
(float32-exact, `struct.pack('f',...)`-round-tripped comparison, zero
tolerance). For the same 8 cases, `f_eot_ctrl`'s measured output equals its
fixed `konst=(111.0,-222.0,333.5,-444.25)` sentinel exactly, **invariant**
across every one of the 8 different `dst` clear colors used for that
render pass (`analysis/verify.py`'s `*_ctrl_result_constant_across_dst_sweep`
check: exactly 1 distinct result value across the 8-case sweep, both runs).
For all 4 `(dst, src)` pairs in `combine` mode (spanning zero, negative, and
`+-1.0e6`-magnitude operands), `f_eot_combine`'s measured output equals
`dst*2.0+src` exactly, componentwise, in both runs.

**INTERPRETED:** a fragment-shaped program authored entirely from our own
MSL, declaring an explicit `[[color(0)]]` input and writing attachment 0,
reads the tile's pre-existing resident value (established via
`MTLLoadActionClear` with an exact float clear color -- i.e. exactly the
"already-loaded/cleared tilebuffer content" an EOT program's input state
represents) and writes a value derived from it to the real backing texture
(`MTLStoreActionStore`, verified via CPU-side `getBytes:` readback) -- the
two operations the task specifies ("reads the tilebuffer and writes an
attachment"). The paired control (`f_eot_ctrl`) demonstrates this is not
coincidental: removing the `[[color(n)]]` declaration from an otherwise
identical output-writing shader makes the output provably independent of
`dst`, which is exactly the behavior `f_eot_evict`/`f_eot_combine` do NOT
show. This is HW-validated in the CODEX sense of "independently generated
encoding executed successfully on hardware" for the *behavioral* claim; see
1.2 for which shapes reach it via the actual hardware instructions.

### 1.2 H2 -- structural: which authored shapes reach the hardware ops, and which don't

**OBSERVED** (structural records, byte-identical both runs; extracted via a
locally-rebuilt, pinned-hash `tools/shdump`+`agxparse.py`, read-only tool
use):

| function | source shape | compiled length | contains `tile_read` (`67 0e 54`) | contains `frag_color_store` (`e7 06 54`) |
|---|---|---:|---|---|
| `f_eot_evict` | `return dst;` (pure identity, `[[color(0)]]` read, unmodified write) | 16 B | **NO** | **NO** |
| `f_eot_ctrl` | `return konst;` (no `[[color(n)]]` parameter at all) | 54 B | NO (expected -- never declared) | **YES** |
| `f_eot_combine` | `return dst*2.0+src;` (genuinely non-constant-foldable ALU) | 120 B | **YES** | **YES** |

Full hex dumps in `raw/m4_20260828_run01/records.jsonl` (`kind:"structural"`
records). `f_eot_combine`'s bytes contain the literal substring
`670e5404000001ce...` at internal offset 12 and `...e70654040000014e...`
near the end -- matching EXP-0029's established byte-for-byte encoding for
`tile_read` (byte0 `0x67`, byte+1 `0x0e`, byte+2 `0x54`) and
`frag_color_store` (byte0 `0xe7`, byte+1 `0x06`, byte+2 `0x54`) exactly,
freshly reproduced on M4 (EXP-0029 was A18-only) from an independently
authored kernel (not a copy of EXP-0029's `blend_read`/EXP-0117's logic-op
kernels).

**INTERPRETED:** `f_eot_evict`'s pure-identity shape is a **compiler-level
no-op elimination**, not a genuine tilebuffer read+write -- Metal's
compiler proves that "read attachment-0's current value, then write the
identical value back to attachment 0" has no observable effect and removes
both the read and the store from the compiled program entirely, deferring
correctness (which the H1 behavioral check confirms holds) entirely to the
render pass's own fixed-function load (`MTLLoadActionClear`) and store
(`MTLStoreActionStore`) actions. This independently reproduces, from an
entirely different code path, the elision EXP-0117 found for its
`blendstruct_on_dstonly` case (a *pipeline-descriptor*-level
`MTLBlendFactor` reduction, `dst=One, src=Zero`) -- confirming the same
class of no-op elimination applies even to a hand-authored `[[color(n)]]`
identity with no blend descriptor involved at all, i.e. this is a general
property of the compiler's dead-code elimination on this construct, not an
artifact specific to the blend-factor mechanism. **A driver author cannot
rely on a pure-passthrough authored shape to exercise/validate the
`tile_read`/`frag_color_store` hardware path** -- exactly the reason this
experiment's *primary* validated construction is `f_eot_combine`, not
`f_eot_evict`. Both are reported: the negative (elision) result is a
first-class finding per `CODEX.md`, not a discarded pilot detail.

### 1.3 H3 -- registering the literal `drm_asahi_bg_eot` fields is unreachable from this host

**OBSERVED** (`raw/host_check.json`): `uname -a` reports a Darwin/macOS
kernel (`Darwin ... RELEASE_ARM64_T8132`), not Linux; `/dev/dri` does not
exist on this host; no `asahi`- or `drm`-named entry appears in `kextstat`.
Cross-referencing this repository's own `docs/P0-P1-CLOSURE.md` (read, not
modified): the P0.5 row (`DRV-CMD-01`, "Complete relocatable VDM/CDM/PPP/USC
command and state packing") is **`OPEN`**, explicitly listing "independent
packer" among what is still needed.

**INTERPRETED:** `struct drm_asahi_bg_eot` and `struct drm_asahi_cmd_render`
(`mesa/include/drm-uapi/asahi_drm.h`) are Linux DRM UAPI structures,
consumed by `DRM_IOCTL_ASAHI_SUBMIT` on a `drm_asahi`-backed kernel driver.
This host runs macOS, which has no such device node, kernel driver, or
ioctl -- there is categorically no way, from any userspace program on this
machine, to populate a real `drm_asahi_bg_eot.usc`/`rsrc_spec` pair and have
a real kernel/firmware consume it, independent of anything about this
project's own tooling. Separately (and this would matter even on a
hypothetical Linux host with different tooling gaps): this project's own
command-stream capability is not yet at the point of independently
synthesizing and submitting a VDM/CDM control stream outside Metal's own
render-pass construction (P0.5 `OPEN`) -- so even the "same effect via a
different, same-OS path" alternative does not exist here either. **This is
the rigorous bounded negative the task anticipates**: not "we didn't find
it," but "here is exactly what blocks it, checked directly, on two
independent grounds." What *is* constructible and hardware-executable on
this host is the program *content* (Section 1.1/1.2) that a driver would
point `bg.usc`/`eot.usc` at, once a Linux target with a working command-
stream submission path exists to carry it.

---

## 2. `drm_asahi_bg_eot` field requirements (cited)

`struct drm_asahi_bg_eot` (`mesa/include/drm-uapi/asahi_drm.h:925-941`):

```c
struct drm_asahi_bg_eot {
	__u32 usc;        /* :933 -- tagged USC program address */
	__u32 rsrc_spec;  /* :940 -- packed resource specifier */
};
```

Four unconditional instances in `struct drm_asahi_cmd_render`
(`asahi_drm.h:1075,1078,1084,1090`): `bg`, `eot`, `partial_bg`,
`partial_eot`. The doc comment (`asahi_drm.h:914-924`) states the division
of labor precisely: "The fragment-like background program is responsible
for loading either the clear colour or the existing render target
contents, while the compute-like end-of-tile program stores the tilebuffer
contents to memory," and `usc` "is a tagged pointer with additional
configuration in the bottom bits."

**What a driver must actually construct for each `usc`/`rsrc_spec` pair**,
per Mesa's own from-scratch implementation (gallium:
`agx_build_bg_eot`, `mesa/src/gallium/drivers/asahi/agx_state.c:3052-3242`;
Vulkan: `hk_build_bg_eot`, `mesa/src/asahi/vulkan/hk_cmd_draw.c:268-462`;
both call into the shared `agx_get_bg_eot_shader`/`agx_compile_bg_eot_shader`,
`mesa/src/asahi/lib/agx_bg_eot.c:34-63,183-206`):

1. **`usc`** is not a raw 64-bit GPU VA. It is `agx_usc_addr(dev, addr)`
   (`mesa/src/asahi/lib/agx_device.h:226-232`): `addr - dev->shader_base`,
   asserted to fit in 32 bits -- i.e. an **offset relative to a fixed,
   per-device/VM `shader_base` register**, not an absolute pointer. The
   pointed-to memory is a **USC word blob** built with `agx_usc_builder`
   (gallium: `agx_state.c:3099-3250`; Vulkan: `hk_cmd_draw.c:359-466`): an ordered sequence
   of `TEXTURE` (0 or more, one per bound attachment being loaded/stored;
   `USC Texture`, `cmdbuf.xml:667-673`), optionally `SAMPLER` (one shared
   sampler when any attachment is loaded via `txf`; `USC Sampler`,
   `cmdbuf.xml:675-681`), `SHARED` (tilebuffer layout word, `USC Shared`,
   `cmdbuf.xml:690-697`), `SHADER` (the program's code address + flags,
   `USC Shader`, `cmdbuf.xml:699-706`), `REGISTERS` (GPR count + spill
   size, `USC Registers`, `cmdbuf.xml:708-714`), and either `PRESHADER`
   (preamble code address, `cmdbuf.xml:720-724`) or `NO_PRESHADER`
   (`cmdbuf.xml:716-718`) depending on whether the compiled program has a
   preamble. The low bits OR'd onto the final address (`| 4` for
   eot/partial_bg/partial_eot, `| 4` or `| 8` for bg depending on
   `nr_cbufs >= 4`; `agx_pipe.c:1374-1377`, `hk_queue.c:174-177`) are the
   "additional configuration in the bottom bits" the UAPI doc comment
   names; their exact bit-level meaning is **not decoded by this
   experiment** (Mesa's own field name for the low bits is not given in
   the genxml either -- flagged as an open item below, not asserted).
2. **`rsrc_spec`** is a packed 32-bit `Counts` word (`cmdbuf.xml:406-416`):
   `Unknown 0` (1 bit), `Uniform register count` (3 bits, `groups(64)`),
   `Texture state register count` (5 bits, `groups(8)`), `Sampler state
   register count` (3 bits), `Preshader register count` (4 bits,
   `groups(16)`), then either `CF binding count` (7 bits, vertex/compute)
   or, "only for fragment shaders," a 16-bit `Unknown` -- i.e. **BG/EOT
   programs use the fragment-shaped interpretation of this word** (all
   four `drm_asahi_bg_eot` instances are built via the fragment-family
   `COUNTS` pack in Mesa: `agx_state.c:3238-3248`, `hk_cmd_draw.c:455-465`).
   Concretely: `uniform_register_count = shader->info.push_count`,
   `preshader_register_count = shader->info.nr_preamble_gprs`,
   `texture_state_register_count` = the highest texture slot used + 1
   (computed per-RT during USC-word construction), `sampler_state_register_count`
   via `agx_translate_sampler_state_count(uses_txf?1:0, false)`; the
   gallium path additionally sets an `unknown=0xFFFF` field specifically
   for **non-store** (i.e. `bg`) pipelines only (`agx_state.c:3245-3247`)
   -- a field this experiment does not further decode (flagged open).
3. **What the program itself must DO** (source-level, `agx_bg_eot.c`):
   - **`AGX_BG_CLEAR`** (`build_background_op`, `:100-104`): output the
     per-RT clear color, sourced from a **preamble uniform** at a fixed
     offset (`4 + 8*rt`, 8 32-bit words = 1 RGBA32 clear value per RT).
   - **`AGX_BG_LOAD`** (`:69-99`): output `nir_txf` (an ordinary texture
     fetch, NOT a `tile_read`) against a **bindless image built from the
     destination attachment's own memory** (`nir_load_texture_handle_agx`
     lowered to `nir_bindless_image_agx` via a fixed `u0`/`u1` register
     pair, `:20-32`), with pixel coordinate (+layer if layered, +sample id
     if MSAA) as the fetch address -- i.e. BG_LOAD reads the attachment's
     **backing DRAM**, not the tile's current on-chip content (see
     Section 3).
   - **`AGX_EOT_STORE`** (`agx_build_end_of_tile_shader`, `:142-181`):
     `nir_image_store_block_agx` per RT, `.format =
     agx_tilebuffer_physical_format(tib, rt)`, at
     `agx_tilebuffer_offset_B(tib, rt)`, with an explicit 16-bit layer
     index if layered -- a single fused "read local tile memory at this
     byte offset, write to bound image `rt`" hardware operation (see
     Section 3) with **no separate value SSA source** in the NIR call
     signature -- distinct from any ordinary per-fragment ALU-computed
     store.
   - Every BG/EOT program is compiled as a genuinely separate NIR shader
     per unique `agx_bg_eot_key` (tilebuffer layout x per-RT op) and
     cached (`agx_get_bg_eot_shader`, `:183-206`); nothing here is a
     single canonical fixed routine on the Linux driver's design -- in
     sharp contrast to what EXP-0108 observed on Apple's own macOS path
     (Section 3).

---

## 3. Tilebuffer load/store ABI

Two textually distinct mechanisms exist in Mesa's own from-scratch design,
and this experiment's own HW-validated construction (Section 1) exercises
the second one:

1. **BG_LOAD (attachment memory -> tile)**: an ordinary `txf` texture
   fetch against a bindless descriptor that happens to point at the
   destination attachment's own backing memory (`agx_bg_eot.c:69-99`,
   Section 2 above). This is memory-to-tile; it is **not** the
   `tile_read`/`local_pixel_agx` mechanism EXP-0029 decoded, and this
   experiment does not construct or validate it directly (ordinary texture
   sampling is already independently well-characterized elsewhere in this
   project's ISA work, so no new HW-validation was needed here; see
   "Deferred" below for the honest scope statement).
2. **In-tile read (tile -> register)**: `load_local_pixel_agx`
   (`mesa/src/compiler/nir/nir_intrinsics.py:2539,2542`, comment
   `:2520-2536`): "Logically loads a single sample... All calculations are
   relative to an immediate byte offset into local memory... `((((y *
   tile_width) + x) * nr_samples) + sample) * sample_stride) + offset`."
   This is the mechanism an ordinary app fragment shader's `[[color(n)]]`
   **input** compiles to (EXP-0029: `tile_read`, byte0 `0x67` byte+1
   `0x0e`), and it is what this experiment's `f_eot_combine` construction
   (Section 1.1/1.2) exercises and HW-validates on M4: sample selection is
   a bitmask source, addressing is (x,y,sample)-explicit via the formula
   above, layer selection for the render-pass-level case is handled by the
   render pass's own per-layer tile assignment (not an operand of this
   specific intrinsic).
3. **EOT store (tile -> attachment memory)**:
   `nir_intrinsic_image_store_block_agx`
   (`nir_intrinsics.py:2562`, comment `:2549-2561`): "Store a block
   from local memory into a bound image... extra src[] = { logical offset
   within shared memory, coordinates/layer }." Critically, this intrinsic's
   NIR call site (`agx_bg_eot.c:170-173`) passes **no explicit value
   operand at all** -- only an image index, a byte offset, and a
   layer/coordinate source. Cross-referenced against Mesa's own AGX
   compiler backend (M1/M2-class; PUBLIC context only, not an Apple9 fact):
   `agx_emit_block_image_store`
   (`mesa/src/asahi/compiler/agx_compile.c:885-932`) lowers this to
   `agx_block_image_store(b, base, index, offset, coords, format, dim,
   explicit)`, a **distinct AGX IR opcode** (`agx_opcodes.py:401`,
   `op("block_image_store", (0xB1, 10, _), ...)`), separate from the
   ordinary `image_write` opcode (`agx_opcodes.py:395`,
   `op("image_write", (0xF1 | (1 << 23), 6, 8), ...)`) used for
   `nir_intrinsic_image_store`. **This is read here only as PUBLIC
   cross-generation context** (the byte value `0xB1` is Mesa's M1/M2-class
   encoding, not asserted as an Apple9 fact anywhere in this document) --
   it corroborates, from a second, independently-RE'd AGX generation, that
   this GPU family implements tile-to-memory eviction as its own **fused,
   single hardware instruction** distinct from any per-fragment
   programmable store, consistent with what this experiment could and
   could not reach from the public Metal surface (below).

**What this experiment could and could not reach on M4:** mechanism (2)
(in-tile read) is fully constructible and HW-validated here
(`f_eot_combine`). Mechanism (1) (BG_LOAD's memory-read `txf`) is ordinary
texture sampling, not newly probed here. **Mechanism (3) (the fused
`store_block_agx`-class instruction) was not observed to be reachable from
any public Metal compilation path in this experiment** -- `f_eot_combine`'s
store, and every store this project has ever extracted from a Metal
fragment or compute kernel, compiles to the ordinary `frag_color_store`
(`0xe7`/`0x06`) or `image_write`-class instruction, sourced from an
explicit ALU-computed register value, never a "read local memory and
write to a bound image" single fused op with no intervening register.
This experiment did not attempt the tile-shading/`imageblock<T>` API
(deferred, see below), which is the one remaining public Metal surface
plausibly close to this mechanism (EXP-O2D found `imageblock` writes on
A18 compile to `0xe7`/byte+1 `{0x06,0x16,0x0e}` -- structurally still the
per-fragment/per-thread store family, not a distinct fused op, though
EXP-O2D did not test writing FROM an imageblock read directly TO a bound
DRAM image in one instruction, which is the specific shape that would be
comparable to `store_block_agx`). **This is reported as an open,
UNKNOWN-labeled question, not a negative claim that mechanism (3) is
unreachable** -- only that this experiment's own probing did not reach it.

---

## 4. `partial_bg`/`partial_eot`: what "resume a paused render" adds

Precisely cited from Mesa's own construction (both drivers agree):

- **`partial_eot` is functionally identical in construction to `eot`** in
  the gallium driver: `agx_flush_render` builds `pipeline_store` ONCE
  (`agx_pipe.c:1570`, `agx_build_bg_eot(batch, /*store=*/true,
  /*partial_render=*/false)`) and assigns it to **both**
  `c->eot.usc`/`rsrc_spec` (`agx_pipe.c:1364,1375`) **and**
  `c->partial_eot.usc`/`rsrc_spec` (`agx_pipe.c:1370,1377`) -- i.e. the
  same compiled program and USC words serve both roles on that driver.
  The Vulkan driver builds `eot.partial` as a **separate** call
  (`hk_cmd_draw.c:630,632`) but with the same `store=true` key, and its
  own store-decision logic explicitly forces a store when partial:
  `should_store |= partial_render;` (`hk_cmd_draw.c:299`) -- so even where
  built separately, `partial_eot`'s *behavior* differs from `eot`'s only
  in that a partial pass **always** stores every present attachment,
  overriding whatever `VK_ATTACHMENT_STORE_OP_NONE`/similar the app
  configured for the (still in-progress) render pass.
- **`partial_bg` differs from `bg` in exactly one respect, cited
  precisely**: the per-RT load decision unconditionally forces a load.
  Gallium: `load |= partial_render;` (`agx_state.c:3090`, inside
  `agx_build_bg_eot`). Vulkan: `load |= partial_render;`
  (`hk_cmd_draw.c:310`, inside `hk_build_bg_eot`), with an explanatory
  comment directly above it (`hk_cmd_draw.c:307-309`): "The background
  program used for partial renders must always load whatever was stored
  in the mid-frame end-of-tile program." Concretely: whatever the app's
  own `loadOp`/pipe-clear state says for the FIRST tile pass (Clear, Load,
  or DontCare), a **resumed** tile pass after a partial-render pause must
  use `AGX_BG_LOAD` for every present attachment, unconditionally --
  clearing again on resume would destroy geometry already rendered before
  the pause; DontCare on resume would leave stale/undefined tile content
  where the paused EOT had just written real data. This is the precise,
  minimal, fully-cited answer to "what must `partial_bg` additionally do":
  **override the app's load action with an unconditional load, for every
  attachment present, every time it runs** -- everything else about its
  USC-word/rsrc_spec construction is identical in shape to an ordinary
  `AGX_BG_LOAD`-only `bg` program (Section 2).
- Neither driver's construction path references anything TVB/tiler-
  heap-specific inside `partial_bg`/`partial_eot` -- consistent with
  EXP-0120's finding that the UAPI has no such field at all; "resume" is
  entirely expressed through the ordinary per-RT load/store op selection
  described above, not through any separate resume-specific mechanism.

---

## 5. CONSTRUCTED-vs-COPIED field table

| Field / behavior | Status here | Basis |
|---|---|---|
| `drm_asahi_bg_eot.usc` shape (tagged 32-bit offset from `shader_base`) | **CONSTRUCTED** (spec-level; cited, not itself HW-run since no Linux target is reachable, H3) | `agx_usc_addr` (`agx_device.h:226-232`), doc comment (`asahi_drm.h:927-932`) |
| USC word blob contents (`TEXTURE`/`SAMPLER`/`SHARED`/`SHADER`/`REGISTERS`/`PRESHADER`) | **CONSTRUCTED** (spec-level; the *shape* is Mesa's own from-scratch synthesis, cited; the actual bit layouts in `cmdbuf.xml` are Mesa's own RE work on a **different, M1/M2-class** target, used as PUBLIC hypothesis only, not Apple9-validated by us) | `cmdbuf.xml:660-723` |
| `rsrc_spec` (`Counts`) field meanings | **CONSTRUCTED** (spec-level; same caveat as above -- the top-level shape/field list is corroborated by our own already-established ISA work elsewhere in this project, but the exact bit widths shown are Mesa's M1/M2-generation genxml, not independently HW-validated here) | `cmdbuf.xml:406-416` |
| `AGX_BG_LOAD` = `txf` against attachment memory | **NOT independently HW-validated in this experiment** (ordinary texture sampling; already well-characterized elsewhere in this project's ISA work; ISA claim not re-derived here) | `agx_bg_eot.c:69-99` (PUBLIC only) |
| in-tile read = `tile_read`/`local_pixel_agx` | **CONSTRUCTED + HW-VALIDATED on M4, this experiment** (`f_eot_combine`, Section 1.1/1.2), independently reproducing EXP-0029's A18 encoding fresh on M4 from a new kernel | `raw/m4_20260828_run0{1,2}/records.jsonl` |
| attachment write = `frag_color_store` | **CONSTRUCTED + HW-VALIDATED on M4, this experiment** (`f_eot_combine`/`f_eot_ctrl`), also independently reproducing EXP-0029's encoding | same |
| genuine end-to-end "read tile, combine, write attachment" round trip, pixel-exact vs. host oracle | **CONSTRUCTED + HW-VALIDATED on M4, this experiment**, 4/4 boundary cases exact, both runs | same |
| pure identity ("evict unchanged") shape reaching the hardware ops at all | **REFUTED as a viable construction** -- compiler elides both ops; behaviorally correct via fixed-function load/store only, not via the authored shader body | `f_eot_evict` structural record, both runs |
| fused `store_block_agx`-class instruction (EOT's specific bulk tile-to-memory op) | **NOT REACHED / UNKNOWN** -- no public Metal compilation path in this project's evidence base has been observed to emit it; PUBLIC cross-generation context (Mesa M1/M2 `agx_opcodes.py:401`) suggests it is architecturally a distinct fused op on this GPU family, not itself an Apple9 fact | Section 3 |
| `partial_bg` = `bg` + unconditional load override | **CONSTRUCTED** (spec-level; precisely cited); behavioral consequence (resumed tile recovers exactly what was stored) not independently HW-tested in this experiment (would require actually triggering and observing a partial-render pause, out of scope here -- EXP-0120 already bounds that this is currently unobservable from userspace at any tested scale on M4) | `agx_state.c:3090`, `hk_cmd_draw.c:307-310` |
| `partial_eot` = `eot` (same or near-identical program), store forced | **CONSTRUCTED** (spec-level; precisely cited) | `agx_pipe.c:1364-1377`, `hk_cmd_draw.c:299,624-632` |
| registering any of the above as literal UAPI fields consumed by real firmware | **NOT REACHABLE from this host** (bounded negative, checked directly, H3) | `raw/host_check.json` |

---

## 6. What P0.4 still requires

Not closed by this experiment; still open per `docs/P0-P1-CLOSURE.md`'s
closure rules:

1. **A Linux (or otherwise `drm_asahi`-capable) target** to actually
   populate and submit real `drm_asahi_bg_eot` structs and observe firmware
   consume them -- categorically outside this project's current M4-macOS
   test envelope (H3). Absent that, "generated, not merely decoded" for
   the *literal UAPI fields* can only be argued at the specification level
   (Section 2/5), never HW-run end-to-end from this host.
2. **The low-bits tag meaning** of `usc` (`| 4` / `| 8`) -- not decoded by
   this experiment (flagged, not guessed).
3. **`rsrc_spec`'s exact bit layout for Apple9** -- this experiment cites
   Mesa's M1/M2-class genxml as PUBLIC hypothesis only; independent Apple9
   HW validation of that exact bit layout (versus, say, a shifted or
   reordered Apple9-specific packing) is not attempted here.
4. **The fused `store_block_agx`-class EOT-eviction instruction** --
   whether it exists on Apple9 at all, and if so whether it is reachable
   from any public Metal API (tile shading, or otherwise) or is
   categorically firmware/driver-internal-only -- UNKNOWN (Section 3).
5. **`AGX_BG_LOAD`'s `txf`-against-self mechanism**, independently
   HW-validated as a BG-role construction specifically (not merely cited
   as "ordinary texture sampling already known").
6. **Partial-render's actual trigger and observable behavior on real
   hardware** -- EXP-0120 already bounds this as unobservable from
   userspace up to 20,000,000 tile-concentrated triangles on M4; this
   experiment adds the *what must the program additionally do* half
   (Section 4) but not a hardware-observed partial-render event itself.
7. **Format/resolve/MSAA/layers coverage** for BG/EOT programs specifically
   (already partially covered by P1.1/P1.2's own work; not re-derived
   here).
8. **Adversarial falsification via raw byte-splicing** of the constructed
   `tile_read`/`frag_color_store` sequence (deliberately out of scope
   here, Section "Deferred" -- the paired-control design substitutes for
   it but is a different evidence tier).
9. Any A18 Pro replication (hands-off).

---

## 7. Deferred (explicit, not silently dropped)

- **Tile-shading (`imageblock<T>`, `dispatchThreadsPerTile`) construction
  on M4.** EXP-O2D already HW-validated this general mechanism on A18
  (historical, pre-M4-directive); this experiment's `PRE_REGISTRATION.md`
  explicitly scoped it as "attempted only as time permits." It was not
  attempted here: the core `tile_read`+ALU+`frag_color_store` construction
  (Section 1) already gives decisive, triangulated (behavioral +
  structural + paired-control) evidence for the ABI question this
  experiment targets, and a from-scratch tile-render-pipeline harness on
  M4 (new failure surface: `MTLTileRenderPipelineDescriptor`,
  `dispatchThreadsPerTile:`, imageblock layout) was judged, given the time
  available for this dispatch, to add relatively little beyond what
  Section 3 already states honestly as UNKNOWN. A natural next experiment.
- **Raw byte-splicing** of the working `tile_read`/`frag_color_store`
  sequence as a second, stronger falsifier tier (Section 6 item 8).
- **NaN/Inf clear-color boundary behavior** through `MTLClearColorMake`
  (untested; the 8-case `DST_CASES` sweep uses only finite,
  exact-in-float32 values, per `PRE_REGISTRATION.md` Section 2).

---

## 8. Gate results

- `analysis/verify.py --selftest`: **PASS 14/14** (fixtures copied
  verbatim from the NON-RECORDED smoke run `work/smoke/smoke3`; includes a
  mutator self-check proving a deliberately tampered `result` field is
  correctly caught as a mismatch).
- `--seqtest`: **PASS 6/6** (`PRE_GPU` timestamp in `CAPTURE_CONTRACT.json`
  predates `raw/m4_20260828_run01/`'s mtime, which predates
  `raw/m4_20260828_run02/`'s).
- NON-RECORDED smoke gate: run three times (`smoke1`, `smoke2`, `smoke3`)
  into `work/smoke/`, before either official run id was spent; caught and
  fixed two genuine pre-freeze defects (a non-exact-float32 test value, and
  insufficient stdout precision) -- see `PROGRESS.md` for the full account.
  `smoke1`/`smoke2` are left in place, not deleted, per project convention;
  neither is promoted as evidence.
- `--captured --run01 m4_20260828_run01 --run02 m4_20260828_run02`:
  **PASS 10/10** -- 23/23 records byte-identical across runs (nondeterministic
  `wall_s`/`gputime_ns` excluded per `CAPTURE_CONTRACT.json`), all
  behavioral cases match their float32 oracle in both runs independently,
  the structural op-presence claim holds in both runs, and the
  paired-control invariant holds in both runs.
- No timeouts occurred (20 s per-case cap never approached; all cases
  completed in well under 100 ms wall time per the recorded `wall_s`
  field, itself excluded from the byte-exact gate).
- No faults, no host instability, no reboot. Target surface was
  deliberately minimal (2x2 render target, single triangle, no compute
  dispatch, no atomics, no raw splicing) specifically to keep fault risk
  low for this dispatch (`PRE_REGISTRATION.md` Section 5).

---

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE + PUBLIC (mesa/, read-only,
  cited by exact file/line, pinned revision 3c4d3e46d19f2f4e951f3ae059543b03592f7944;
  no code copied, no Apple code involved anywhere in mesa/)
Inputs inspected: authored MSL (kernels/eot_construct.metal, SHA-256
  2bf4863d0739ef2a7a76dc959c2fcc85aaf93cf7cf2a15c66f5e3525cd778831), our
  own authored ObjC/Python harness (harness/render_eot.m, harness/run.py,
  harness/casematrix.py, hashes in manifest.json), our own compiled shader
  bytes (extracted via a locally-rebuilt, pinned-hash copy of
  tools/shdump/shdump.m + tools/shdump/agxparse.py -- read-only use of
  already-validated tooling, never edited), public Mesa source (mesa/,
  pinned revision, file/line citations and hashes throughout this
  document and PRE_REGISTRATION.md), a trivial host-environment probe
  (uname, /dev/dri listing, kextstat)
Apple binary introspection: NONE
Compiled shader bytes inspected: ONLY our own (f_eot_evict, f_eot_ctrl,
  f_eot_combine), extracted from our own compiled archives
Pointer following: NONE
Reproduction: see README.md "Commands"
Evidence: raw/host_check.json, raw/m4_20260828_run01/,
  raw/m4_20260828_run02/ (append-only, immutable); PRE_REGISTRATION.md,
  CAPTURE_CONTRACT.json (frozen before capture); PROGRESS.md (milestone
  log, including two disclosed pre-freeze bugs); manifest.json (all
  artifact hashes)
```
