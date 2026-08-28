# EXP-0126 Results — M4 UAPI field-by-field mapping (P0.3 / DRV-UAPI-03)

## Verdict

**PARTIAL. P0.3 remains OPEN**, but every one of the 65 leaves in `EXP-0045`'s field
matrix now carries an explicit chain (`userspace derivation -> UAPI value -> kernel/
firmware marshaling -> observed Apple9 behavior`), a citation, an evidence label, and a
status, replacing several `OPEN` rows with `A18-PARTIAL`/`M4`-level detail or `MAPPED`
closure-relevant content. Counts (of 65 leaves):

| status | count |
|---|---:|
| **MAPPED** | 7 |
| **PARTIAL** | 58 |
| **UNDETERMINABLE-FROM-USERSPACE** | 0 (see note below — the one genuinely undeterminable item is a supplementary, non-leaf parameter) |

Two new M4 hardware probes were run (pre-registered, two independent captures, all five
standing gates green) and materially advanced the row's two explicitly named priorities:

1. **`render.ppp_multisamplectl` / sample positions — settled.** The captured
   sample-position BO does **not** map to the UAPI as an additional submit parameter or
   pointer at all. `ppp_multisamplectl` **is** the packed value itself (Mesa
   `hk_pack_ppp_multisamplectrl`, PUBLIC source): up to 4 samples, one byte each
   `(y<<4)|x`, each axis a 4-bit `[0,15]` code on a 1/16 grid, zero-extended into the
   64-bit UAPI field. New M4 evidence (this experiment) **exhaustively confirms the full
   1/16 grid** (16/16 tested X points and 8/8 tested Y points reproduce exactly), **locates
   the exact rounding rule** (round-half-up, both tested tie points 1/32 and 3/32 round
   up — RT-4 had shown only 4 arbitrary off-grid points snap to *a* grid point, on A18,
   pre-hands-off; this is the first M4-native confirmation and the first exact
   tie-boundary bisection anywhere in this project), and characterizes **boundary/past-limit
   behavior**: requests in `[0.9375,1.0)` are *not* clamped to 15/16 the way Mesa's software
   formula clamps its input — `0.99` was captured as the literal float `1.0`, outside the
   nominal 4-bit `0..15` range, while `0.94` rounds to `0.9375`. Metal's own hard API range
   is `[0.0,1.0)`, enforced by a **process-terminating assertion** (not a catchable
   `NSError`) for values at/past that limit.
2. **`render.samples` valid range — boundary-tested both ways.** `supportsTextureSampleCount:`
   reports `true` only for `{1,2,4}` out of the full swept set `{0,1,2,3,4,5,6,7,8,16}` on
   this M4; texture/pipeline construction at every unsupported count aborts via a
   process-terminating assertion citing the exact rejected count. Matches the header's "must
   be 1, 2, or 4" exactly, now with an explicit tested negative boundary on both sides.

**High-risk fields named in the dispatch, closed or advanced this experiment:**
- `ppp_multisamplectl` / sample positions — **settled/MAPPED** (above).
- `render.samples` — **MAPPED**, boundary-tested.
- `isp_scissor_base` / `isp_dbias_base` — **not closed**, but the exact per-draw ENABLE bit
  behind `EXP-0055`'s `0x58000+0x36` candidate is now identified by cross-reference against
  Mesa's PUBLIC "Fragment control" bit layout (bit17 = "Depth bias enable"), and the array
  RECORD FORMAT (16-byte Scissor / 12-byte Depth-bias structs) is now known from PUBLIC
  source even though the array's Apple9 address is still unlocated (§ below).
- `zls_ctrl`, `ppp_ctrl` — full PUBLIC bit layouts now documented (Mesa `cmdbuf.xml`); still
  **no macOS observation point exists** for either (both are submit-parameter-only,
  firmware-marshaled registers absent from every userspace BO — this is a structural fact,
  not a gap in probing effort, per `docs/kernel-interface.md` §6).
- `isp_bgobjvals` — clarified beyond the header's one-line comment: Mesa ORs the raw stencil
  clear byte into a **fixed `0x300` baseline**, not "bottom 8 bits" alone.
- `isp_merge_upper_x/y` — **a real discrepancy found**: the UAPI header's doc comment says
  `tan(60°) * width`; Mesa's actual code computes `fui(tan_60 / cs->cr.width)` — **division**,
  not multiplication. Neither formula is independently Apple9-validated in this repository;
  flagged precisely rather than silently resolved.
- `compute.cdm_ctrl_stream_end` — Mesa's own reference driver uses a **hardcoded placeholder
  (`65536 /* XXX */`)** for the linked/chained-stream case; this project's own `EXP-0043`
  segment-capacity finding (732 CDM records/segment, `EXP-0049`/`EXP-0110`/`EXP-0116`
  reproduce it) is better-grounded than Mesa's current placeholder for that case.
- stage timestamp frequency/units — **the genuinely undeterminable item** (see next
  section): not one of the 65 leaves, but the parameter needed to interpret every
  `ts_*.offset`-written value.
- Reserved/tag bits — collected in a dedicated subsection below (bg/eot tag nibble `|4`,
  helper `cfg` bit16, and the UAPI's own MBZ/pad convention).

## The one genuinely undeterminable item (not a leaf, but named in the dispatch)

`drm_asahi_params_global.command_timestamp_frequency_hz`
(`mesa/include/drm-uapi/asahi_drm.h:180-188`, queried via `DRM_IOCTL_ASAHI_GET_PARAMS`, not
part of the 65-leaf render/compute/queue matrix) is the timebase a driver **must** divide
raw `ts_*` tick values by to get seconds. This is **UNDETERMINABLE-FROM-USERSPACE**, and
precisely so: it is a **kernel-supplied, read-only output** — userspace never computes it,
only reads it. No clean-room macOS method can stand in for it: Metal's own GPU timestamps
(`EXP-0027`, `EXP-0052`) are already **software-calibrated nanoseconds** (CPU/GPU anchor
pairs + drift correction, `MTLCounterSampleBuffer`), not the **raw hardware tick count** a
Linux kernel driver would DMA directly into a `drm_asahi_timestamp` handle+offset location.
Even a perfect macOS capture of "GPU timestamps read out as ns, period 1.0" does not
establish what raw-tick frequency the firmware reports to a Linux `GET_PARAMS` caller — that
number literally does not exist anywhere in the macOS userspace-visible surface. This is the
correct, narrow reading of "genuinely undeterminable from userspace": not "hard to find," but
"not a userspace decision or observation at all."

## Method

1. **Synthesis** (all 65 leaves): read `asahi_drm.h`'s doc comment for each field
   (file:line cited in the table); read `mesa/src/asahi/**` (pinned MIT-licensed Mesa,
   `3c4d3e46d19f2f4e951f3ae059543b03592f7944`) as PUBLIC/STRUCTURAL evidence for the
   *shape* of the userspace derivation (this repository's established practice —
   `docs/mesa-userspace-requirements.md` and `docs/kernel-interface.md` already cite
   `cmdbuf.xml`/Mesa source this way; per `CLAUDE.md`, `mesa/` is a read-only reference for
   understanding what a driver must produce, not a source of Apple9 hardware facts); cite
   this repository's own prior M4/A18 experiments for the Apple9-specific evidence.
2. **New M4 hardware probes** (`harness/sampos126.m`, `harness/sampcount.m`, both `OWN-SHADER`
   + public Metal API): described in `PRE_REGISTRATION.md`. Full case matrix, raw evidence,
   and gate results in the sections below.

An earlier, more ambitious probe design (`harness/sampcov.m`, a coverage-mask
hardware-consumer test) was abandoned after an unresolved discrepancy surfaced during pilot
testing; see `PRE_REGISTRATION.md` "Superseded exploratory probe" for the full account. It
contributes no claim here.

## New hardware evidence — full detail

### Exhaustive 1/16-grid coverage (M4, DATA-TRACE, both runs byte-identical)

All 16 X-axis grid points and all 8 tested Y-axis grid points reproduce **exactly**, with no
rounding residue, at both tested sample counts (2 and 4):

| requested (`k`/16) | captured `x0` | requested (`k`/16) | captured `x0` |
|---:|---:|---:|---:|
| 0/16 | 0.0 | 8/16 | 0.5 |
| 1/16 | 0.0625 | 9/16 | 0.5625 |
| 2/16 | 0.125 | 10/16 | 0.625 |
| 3/16 | 0.1875 | 11/16 | 0.6875 |
| 4/16 | 0.25 | 12/16 | 0.75 |
| 5/16 | 0.3125 | 13/16 | 0.8125 |
| 6/16 | 0.375 | 14/16 | 0.875 |
| 7/16 | 0.4375 | 15/16 | 0.9375 |

(Y-axis: 0/2/4/6/8/10/12/14 of 16 all reproduce exactly identically — `raw/*/records.jsonl`
`sp_gridy_*`.)

### Rounding-rule bisection (M4, new — never done before on any target)

```
requested x   0.03124   0.03125   0.03126        0.09374   0.09375   0.09376
captured x0   0.0       0.0625    0.0625         0.0625    0.125     0.125
```

The flip happens **exactly at** the halfway point (`1/32 = 0.03125`, `3/32 = 0.09375`), and
in both cases the tie **rounds up**. This is `round(x*16 + 0.5) rounds ties up` i.e.
round-half-up / round-half-away-from-zero for these positive inputs — consistent with, and
now the first hardware confirmation of, Mesa's public `hk_pack_ppp_multisamplectrl`
comment-level intent (`CLAMP(x,0,0.9375)*16`, implicit C-cast truncation of an
already-integer float after the multiply — the *hardware quantization* observed here,
not Mesa's software packer, is what was tested). Full ladder in
`raw/m4_20260828_run01/records.jsonl` (`sp_ladder_*`, 17 points) and reproduced
byte-identically in `run02`.

### Top-boundary / past-the-grid behavior (new negative result)

| requested x | captured x0 | interpretation |
|---:|---:|---|
| 0.9375 (15/16, in-grid max) | 0.9375 | exact |
| 0.94 | 0.9375 | rounds down into the top grid cell (consistent with round-to-nearest-1/16, `0.94*16=15.04`) |
| 0.99 | **1.0** | `0.99*16=15.84`, rounds to **16**, captured as literal `1.0` — **outside** the nominal 4-bit `0..15` grid; **no ceiling clamp observed** at this (macOS AGX float) representation stage |
| 1.0 | *(rejected)* | Metal `setSamplePositions:` fires a **process-terminating assertion**: `"Provided sample position x-coodinate (1.000000) at index 0 is not within the range [0,1)."` [sic — Metal's own message misspells "coordinate"] |
| -0.001 | *(rejected)* | same assertion family, `"...(-0.001000)... not within the range [0,1)."` |

**Implication for a Linux driver:** Mesa's software packer avoids this hazard entirely by
clamping its input to `[0.0, 0.9375]` *before* multiplying by 16 (`CLAMP(loc.x, 0.0f,
0.9375f) * 16.0`), so it can never hand the hardware/firmware a nibble value of 16. This
experiment shows that clamp is doing real, necessary work: at least at the macOS
representation layer, an *unclamped* value approaching 1.0 does **not** self-limit to 15.
Whether the actual 4-bit hardware field wraps, saturates, or is simply never fed a 16 by any
correctly-clamping driver remains unconfirmed (this observation is upstream of the final
4-bit pack, on the macOS side; no Linux submission of an unclamped value was possible to
test).

### `render.samples` boundary sweep (M4, new)

| count | `supportsTextureSampleCount:` | texture/pipeline construction |
|---:|---|---|
| 0 | *(not queried — count<1 guarded in harness)* | rejected before attempt (`BadCount`) |
| 1 | true | OK (drawn as an ordinary `MTLTextureType2D`, no MSAA) |
| 2 | true | OK |
| 3 | **false** | **ABORT**: `"MTLTextureDescriptor sampleCount (3) is not supported by device."` |
| 4 | true | OK |
| 5,6,7,8,16 | **false** | **ABORT**, same assertion family, each citing its own count |

Every case reproduced identically across both runs (`raw/*/records.jsonl` `sc_count_*`).

### Cross-sample-count check (samples=2, different VA `0x100000e0000`)

`sp_count2_0p375` (on-grid) and `sp_count2_0p1` (off-grid, expect round to `0.125`) both
reproduce the same encoding rule as the 4x-sample case, confirming the grid/rounding
contract is independent of sample count.

## Reserved / tag bits — collected findings

- **`bg`/`eot`/`partial_bg`/`partial_eot`.usc tag nibble.** Mesa: `c->bg.usc =
  cs->cr.bg.main.usc | 4` (and identically for eot/partial_bg/partial_eot) — the low bits of
  this "tagged pointer" carry a **fixed tag value `4`** (binary `100`) in the reference
  driver, PUBLIC-sourced; not independently confirmed against any Apple9 hardware
  observation (`EXP-0048` explicitly did not locate a BG/EOT tagged program address on M4).
- **`helper.cfg` bit 16.** Mesa: `cfg = preamble_uses_scratch ? (1 << 16) : 0` for every
  helper (`vertex_helper`/`fragment_helper`/compute `helper`) — PUBLIC-sourced, no bit below
  16 documented/used in the inspected code path; `EXP-0041` (M4) found no observable
  command-stream/BO correlate of scratch pressure at all, so this bit's Apple9 hardware
  effect is unconfirmed.
- **MBZ/pad fields (general UAPI convention, `asahi_drm.h:16-42`).** "All padding fields
  will be checked by the driver to make sure they are zeroed." Applies to `compute.flags`
  (explicitly `/** @flags: MBZ */`, `asahi_drm.h:1120-1121`) and (outside the 65-leaf render/
  compute matrix but adjacent) `queue_create.flags`, `submit.flags`, `submit.pad`,
  `queue_destroy.pad`. These are **fully specified by the header text itself** — no RE is
  needed or possible for a "value" that is normatively always zero; MAPPED by definition.
- **`DRM_ASAHI_RENDER_DBIAS_IS_INT` "bit 18 of the relevant hardware control register."**
  The header explicitly ties this *submit flag* to a specific hardware register bit but does
  not name the register. This is **not** the same "bit 18" this project's `EXP-0110` observed
  newly at `0x58000+0x34` (that one is the PPP **"Fragment control"** packet's **"Stencil
  test enable"** bit per Mesa's `cmdbuf.xml`, an unrelated command-stream state field, not a
  firmware submit-marshaled register). Flagging this explicitly to prevent the two "bit 18"s
  from being conflated in a future doc pass — this remains a genuinely separate open
  question about an unnamed firmware register.

## Cross-reference finding: EXP-0055's `0x58000+0x36` candidate identified

`EXP-0055` (M4, `DATA-TRACE-VALIDATED`) found that every tested nonzero depth-bias input
changes exactly one byte, `0x58000+0x36`, from `0x00` to `0x02`, and called it a
"nonzero-depth-bias enable candidate." Mesa's public `cmdbuf.xml` defines a 32-bit **"Fragment
control"** struct with `Depth bias enable` at bit 17. If that struct is based at
`0x58000+0x34` (consistent with `EXP-0110`'s independently-and-separately-observed **new**
field at `0x58000+0x34` bit 18, "Stencil test enable" in the same struct), then bit 17 lands
at byte offset `0x34+2 = 0x36`, bit 1 of that byte — i.e. value `0x02` — **exactly** matching
`EXP-0055`'s observation. This is a **convergent, well-supported structural identification**
(PUBLIC bit layout + two independent M4 DATA-TRACE observations agreeing on the byte/bit),
promoting `EXP-0055`'s "candidate" to a named field, but it is **not** independently spliced
(no test toggled bit 17 alone and observed a causal effect isolated from the other bits in
that word), so it stays `DATA-TRACE-VALIDATED`/`STRUCTURAL`, not `HW-VALIDATED`. This is a
command-stream (P0.5) fact, not the `render.zls_ctrl`/`ppp_ctrl` *submit* fields — it explains
a byte in the userspace-authored PPP packet pool, unrelated to the firmware-marshaled
registers those two UAPI leaves represent.

---

## The field table

Columns: **field** — **asahi_drm.h** (file:line) — **userspace derivation** — **Apple9
evidence** (experiment, evidence label) — **status**.

Evidence labels per `CODEX.md`: `HW-VALIDATED` > `DATA-TRACE-VALIDATED` > `OWN-SHADER-DIFF` >
`STRUCTURAL` > `INFERRED` > `UNKNOWN`; `PUBLIC` marks a Mesa/genxml-sourced *shape* fact with
no Apple9-specific numeric confirmation.

### Queue creation (1 leaf)

| field | asahi_drm.h | userspace derivation | Apple9 evidence | status |
|---|---|---|---|---|
| `queue.usc_exec_base` | `:571-584` | Fixed 4 GiB VA carveout base for all USC (vertex/fragment/compute) binaries on the queue; `USC_EXEC_BASE_{TA,ISP,CP}` all set identically (Mesa: `.usc_exec_base = dev->shader_base`, `mesa/src/asahi/lib/agx_device.c:756`, PUBLIC) | `EXP-0042` (M4, `DATA-TRACE-VALIDATED`) observes a stable 4 GiB-aligned code-BO base region on macOS but does not identify it as *this* field, and does not test 32-bit-relative rollover; `docs/kernel-interface.md` §4.5 names this open explicitly | **PARTIAL** |

### `drm_asahi_cmd_render` (52 leaves)

| field | asahi_drm.h | userspace derivation | Apple9 evidence | status |
|---|---|---|---|---|
| `render.flags` | `:973`, enum `:770-804` | OR of 4 documented bits: `VERTEX_SCRATCH`(0), `PROCESS_EMPTY_TILES`(1), `NO_VERTEX_CLUSTERING`(2), `DBIAS_IS_INT`(18, "bit 18 of the relevant hardware control register" — register unnamed). Bit *layout* is the Linux ABI itself, fully specified by the header. | `EXP-0041` (M4): scratch pressure (up to 576 B) produces **no** observable command-stream/BO change → the downstream marshaling of bit 0 is invisible to macOS DATA-TRACE; bits 1/2/18 untested this project | **PARTIAL** (layout MAPPED; Apple9 downstream effect of every bit PARTIAL/untested) |
| `render.isp_zls_pixels` | `:977-981` | `CR_ISP_ZLS_PIXELS` (32-bit, PUBLIC `cmdbuf.xml:1126-1129`): `X[0:14]=width-1`, `Y[15:29]=height-1` (Mesa: `cfg.x=cs->cr.zls_width; cfg.y=cs->cr.zls_height`) | None — submit-parameter-only register, absent from every userspace BO (`docs/kernel-interface.md` §4.3/§6) | **PARTIAL** |
| `render.vdm_ctrl_stream_base` | `:984-987` | GPU VA of the userspace-built VDM stream (`cs->addr`) | `EXP-0014`/`EXP-0024` (A18) + `EXP-0043`/`EXP-0049`/`EXP-0110` (M4, `DATA-TRACE-VALIDATED`) + `EXP-0116` (M4, **`HW-VALIDATED`** — a hand-built link record was followed by real hardware) | **MAPPED** |
| `render.vertex_helper.binary` | `:891-911`, `:990` | Tagged USC address to a helper program (`agx_helper_program(&dev->bg_eot)`, shared across stages) | `EXP-0041` (M4): scratch demand shows **no** separately observable helper record/BO/launch-descriptor/FS change (clean negative) | **PARTIAL** |
| `render.vertex_helper.cfg` | `:898` | `(1<<16)` iff the preamble also needs scratch, else `0` (Mesa `hk_queue.c:100`) | same as above | **PARTIAL** |
| `render.vertex_helper.data` | `:902-909` | GPU VA of the per-stage scratch buffer (`dev->scratch.vs.buf->va->addr`); opaque to kernel/firmware, read by the helper via special registers | same as above | **PARTIAL** |
| `render.fragment_helper.binary` | `:891-911`, `:993` | same shape as vertex_helper.binary | `EXP-0041` FS K112 case: 336 B scratch, same negative result | **PARTIAL** |
| `render.fragment_helper.cfg` | `:898` | same shape | same | **PARTIAL** |
| `render.fragment_helper.data` | `:902-909` | GPU VA of `dev->scratch.fs.buf` | same | **PARTIAL** |
| `render.isp_scissor_base` | `:996-999` | GPU VA of a userspace-uploaded array of 16-byte "Scissor" records (PUBLIC `cmdbuf.xml:380-387`: MaxX/MinX u16, MaxY/MinY u16, MinZ/MaxZ f32); Mesa: `cs->uploaded_scissor`. Per-draw selection is a separate 16-bit index inside a "Depth bias/Scissor" 4-byte pair (`cmdbuf.xml:609-612`) carried in the PPP state pool, not in this field. | `EXP-O2A` (A18): multi-scissor rect array **not found in any client BO** (only the per-draw enable bit and tile-grid bound are visible). `EXP-0054`/`EXP-0055` (M4, `DATA-TRACE-VALIDATED`): independently confirm scissor-coordinate changes are **not** visible in `0x58000`/`0x68000` — a clean, bounded negative, not "not yet tried." | **PARTIAL** |
| `render.isp_dbias_base` | `:1002-1005` | GPU VA of a userspace-uploaded array of 12-byte "Depth bias" records (PUBLIC `cmdbuf.xml:389-393`: bias f32, slope f32, clamp f32 — exactly the 3 inputs `EXP-0054` swept); Mesa: `cs->uploaded_zbias` | `EXP-0054` (M4, `HW-PROBE`) establishes the *behavioral* contract (sign/magnitude/clamp move depth as expected); `EXP-0055` (M4, `DATA-TRACE-VALIDATED`) locates the likely per-draw **enable bit** (`0x58000+0x36`, cross-referenced above) but not the array itself | **PARTIAL** |
| `render.isp_oclqry_base` | `:1008-1011` | GPU VA of a per-device 8-byte-per-slot result table, `AGX_MAX_OCCLUSION_QUERIES=32768` slots = 256 KiB (Mesa: `dev->occlusion_queries.bo->va->addr`, `mesa/src/asahi/lib/agx_helpers.h:16`) | `EXP-0027` (A18, `DATA-TRACE`): a **visibility-result-buffer base pointer** was located at client BO `0x10000100000+0x00` on macOS, with per-draw mode (bit14 of `0x58000+0x8c`) and offset (`0x58000+0xa0 = byteOffset<<14`) — a related but not confirmed-identical addressing scheme to Mesa's flat per-device table | **PARTIAL** |
| `render.depth.base` | `:1014` → `:818-839` | GPU VA of the depth surface (image base + layer/level offset) | `EXP-0019`/`EXP-0021` (A18): depth attachment base address visible/validated in captured descriptors | **PARTIAL** |
| `render.depth.comp_base` | `:823-827` | GPU VA of depth compression metadata, only if compressed (Mesa: `metadata_offset_B + layer*compression_layer_stride_B + level_offsets_compressed_B[level]`) | `EXP-0017` (A18): compression enable/layout studied generally; not independently re-validated against this exact field | **PARTIAL** |
| `render.depth.stride` | `:829-833` | `((stride_pages-1)<<14) \| 1` — pages of `AIL_PAGESIZE=0x4000`(16 KiB), fixed low bit 1 (Mesa `hk_cmd_draw.c:669`, PUBLIC formula) | None Apple9-specific; formula is PUBLIC-only | **PARTIAL** |
| `render.depth.comp_stride` | `:835` | `(stride_lines-1)<<14` — lines of `AIL_CACHELINE=0x80`(128 B) (Mesa `hk_cmd_draw.c:686`, PUBLIC) | None Apple9-specific | **PARTIAL** |
| `render.stencil.base` | `:1017` → `:818-839` | Same shape as depth.base, separate plane/resource (Z/S are separate resources on Apple Silicon, `EXP-0028`) | `EXP-0019`/`EXP-0021` (A18) | **PARTIAL** |
| `render.stencil.comp_base` | same struct | Same shape as depth.comp_base | `EXP-0017` (A18), general | **PARTIAL** |
| `render.stencil.stride` | same struct | `((stride_pages-1)<<14) \| 1`, same convention as depth (Mesa `hk_cmd_draw.c:720`) | None Apple9-specific | **PARTIAL** |
| `render.stencil.comp_stride` | same struct | Same convention as depth.comp_stride | None Apple9-specific | **PARTIAL** |
| `render.zls_ctrl` | `:1019-1020` | 64-bit `ZLS Control` (PUBLIC `cmdbuf.xml:1110-1123`): per-op (Z-Load/S-Load/Z-Store/S-Store) Tiling(bit)+Compress(bit)+enable(bit), Z-Format(2 bits, 32F=0/16=2), Z/S-Resolve(bits 56/58); Mesa `memcpy`s a pre-packed `zls_control` struct directly | **None** — `docs/kernel-interface.md` §4.3/§6: this register is deliberately absent from every userspace BO on macOS; only crosses as a submit parameter | **PARTIAL** |
| `render.ppp_multisamplectl` | `:1023` | 32-bit-in-64 packed sample-position control (PUBLIC `hk_cmd_draw.c:2252-2268`, `hk_pack_ppp_multisamplectrl`): up to 4 samples, 1 byte each `(y<<4)\|x`, 4-bit/4-bit fixed point on a 1/16 grid | **NEW, this experiment** (M4, `DATA-TRACE-VALIDATED` + `HW-PROBE`): exhaustive 16-point grid confirmed exactly; exact round-half-up tie rule located at both tested boundaries; top-boundary/API-range behavior characterized (see above) | **MAPPED** |
| `render.sampler_heap` | `:1026-1030` | GPU VA of a device-wide sampler descriptor table shared VS/FS (Mesa: `dev->samplers.table.bo->va->addr`) | `EXP-G1a`/RT-11 claim 1 (A18): establish an 8-byte texture-descriptor-adjacent, 0x20-byte-stride sampler grammar inside a **per-draw argument buffer**, a related but not confirmed-identical structure to a shared cross-draw "heap" | **PARTIAL** |
| `render.ppp_ctrl` | `:1032-1033` | 32-bit `CR PPP Control` (PUBLIC `cmdbuf.xml:1131-1136`): `OpenGL`(0), `Enable W Clamp`(1), `Default point size`(8), `Fixed point format`(9). Mesa's reference driver always sets a **fixed constant**: `enable_w_clamp=1, fixed_point_format=1` = `0x202` (matches `docs/mesa-userspace-requirements.md`'s independently-noted value) | None — same submit-parameter-only absence as `zls_ctrl` | **PARTIAL** |
| `render.width_px` | `:1035-1036` | Framebuffer width in pixels, direct | `EXP-0021`/`RT-4` (A18, `HW-VALIDATED`): drives the tile-grid formula `0x68000+0x904 = 0x80000000\|(ceil(W/32)-1)` and viewport transform, confirmed across a wide W sweep | **MAPPED** |
| `render.height_px` | `:1038-1039` | Framebuffer height in pixels, direct | `EXP-0021`/`RT-4` (A18, `HW-VALIDATED`): `+0x908 = ceil(H/32)-1`, same sweep | **MAPPED** |
| `render.layers` | `:1041-1042` | Number of framebuffer layers (layered rendering) | Field-matrix's `EXP-0028` citation is a **loose match** — that experiment is texture-array Morton-twiddle layer *stride*, not render-pass layer *count*; no dedicated M4/A18 experiment establishes this field's encoding/limits. Correcting the citation here. | **PARTIAL** |
| `render.sampler_count` | `:1044-1045` | Count of populated slots in `sampler_heap` | `EXP-G1a`/RT-2a (A18): argument-buffer sampler counting (`num_samplers=(term-samp)/0x20`), same heap-model caveat as `sampler_heap` | **PARTIAL** |
| `render.utile_width_px` | `:1047-1048` | Logical tilebuffer utile width, format/sample-size dependent (PUBLIC-ONLY per `EXP-0044` baseline) | `EXP-0021`/`RT-4` (A18): the outer 32×32 **macro-tile** is HW-confirmed constant across formats/bpp/MSAA — whether this *is* "utile" as the UAPI defines it, vs. a distinct microtile concept, is not cross-checked here | **PARTIAL** |
| `render.utile_height_px` | `:1050-1051` | Same as above, height | same | **PARTIAL** |
| `render.samples` | `:1053-1054` | Sample count, "must be 1, 2, or 4" (Mesa: `MAX2(cs->tib.nr_samples,1)`) | **NEW, this experiment** (M4, `HW-PROBE`): `supportsTextureSampleCount:` true only for {1,2,4} of {0,1,2,3,4,5,6,7,8,16} tested; every unsupported count aborts with an exact assertion naming the count | **MAPPED** |
| `render.sample_size_B` | `:1056-1057` | Tilebuffer bytes/sample, attachment-format-dependent (Mesa: `cs->tib.sample_size_B`, PUBLIC-ONLY) | `RT-4`/`RT-11` (A18): per-attachment **tiler-heap record** stride measured for several formats (bgra8/rgba16f=0x1000, rgba32f=0x1800 — not simply area×bpp) — a related but not confirmed-identical structure to the UAPI's per-sample tilebuffer byte count | **PARTIAL** |
| `render.isp_merge_upper_x` | `:1059-1066` | **Discrepancy found**: header comment says `tan(60°) * width`; Mesa code computes `fui(tan_60 / cs->cr.width)` (**division**) | None — PUBLIC-ONLY per `EXP-0044`; neither formula independently validated against Apple9 hardware consumption | **PARTIAL** |
| `render.isp_merge_upper_y` | `:1069-1072` | Same discrepancy, height | None | **PARTIAL** |
| `render.bg.usc` | `:1075` → `:914-941` | Tagged USC program address; Mesa: `cs->cr.bg.main.usc \| 4` (fixed tag nibble `4`) | `EXP-0048` (M4): explicitly did **not** locate a BG/EOT tagged program address | **PARTIAL** |
| `render.bg.rsrc_spec` | `:936-940` | Packed "Counts" struct (PUBLIC `cmdbuf.xml:406-415`: uniform/texture/sampler/preshader register counts, CF-binding count), `memcpy`'d from a compiler-derived struct | `EXP-0048` (M4): explicitly did **not** locate the resource-spec layout | **PARTIAL** |
| `render.eot.usc` | `:1078` | Same shape as bg.usc | `EXP-G1b` (A18): PBE/RT-descriptor study, general; not this exact field | **PARTIAL** |
| `render.eot.rsrc_spec` | same | Same shape as bg.rsrc_spec | `EXP-G1b` (A18), general | **PARTIAL** |
| `render.partial_bg.usc` | `:1084-1090` | Same shape, resume-path program | `EXP-0048`: negative (not located) | **PARTIAL** |
| `render.partial_bg.rsrc_spec` | same | Same shape | `EXP-0048`: negative | **PARTIAL** |
| `render.partial_eot.usc` | same | Same shape, pause-path program | `EXP-0048`: negative | **PARTIAL** |
| `render.partial_eot.rsrc_spec` | same | Same shape | `EXP-0048`: negative | **PARTIAL** |
| `render.isp_bgobjdepth` | `:1093-1097` | Depth clear value: `fui(clear)` (f32 surfaces) or `_mesa_float_to_unorm(clear,16)` (Z16) | `EXP-0019`/`EXP-0021` (A18): depth clear-value packing validated generally, A18-only | **PARTIAL** |
| `render.isp_bgobjvals` | `:1100-1103` | **Clarified beyond the header**: Mesa sets a **fixed `0x300` baseline**, then ORs in the raw 8-bit stencil clear value — not "bottom 8 bits" alone; bits 8-9 carry additional fixed bits the header text doesn't mention | `EXP-0019` (A18): reserved-bit/clear behavior studied generally; the `0x300` constant itself not independently confirmed | **PARTIAL** |
| `render.ts_vtx.start.handle` | `:1106` → `:842-878` | `GEM_BIND_OBJECT` handle of a specially-mapped timestamp BO, 0 to skip | `EXP-0027` (A18, `DATA-TRACE`): stage-boundary-only GPU timestamp sampling confirmed (dispatch/draw-internal boundaries unsupported), matching vtx-start/vtx-end/frag-start/frag-end granularity exactly; `EXP-0052` (M4, `HW-PROBE`) confirms monotonic pairs + per-pass ordering, falsifies strict cross-pass ordering | **PARTIAL** |
| `render.ts_vtx.start.offset` | `:859` | Byte offset within that BO | same | **PARTIAL** |
| `render.ts_vtx.end.handle` | same struct | same shape | same | **PARTIAL** |
| `render.ts_vtx.end.offset` | same | same shape | same | **PARTIAL** |
| `render.ts_frag.start.handle` | `:1109` | same shape (Mesa's inspected `hk_queue.c` snippet only shows `ts_frag.end` wired at this call site; `ts_frag.start`/`ts_vtx.*` are populated elsewhere in Mesa and were not traced this pass — noted so as not to overclaim) | `EXP-0027`/`EXP-0052`, same as above | **PARTIAL** |
| `render.ts_frag.start.offset` | same | same | same | **PARTIAL** |
| `render.ts_frag.end.handle` | same | Mesa: `c->ts_frag.end.handle = cs->timestamp.end.handle` (`hk_queue.c:217`) | same | **PARTIAL** |
| `render.ts_frag.end.offset` | same | Mesa: `c->ts_frag.end.offset = cs->timestamp.end.offset_B` (`hk_queue.c:218`) | same | **PARTIAL** |

*(Every `ts_*` leaf additionally depends on `command_timestamp_frequency_hz` for unit
conversion — see "the one genuinely undeterminable item," above.)*

### `drm_asahi_cmd_compute` (12 leaves)

| field | asahi_drm.h | userspace derivation | Apple9 evidence | status |
|---|---|---|---|---|
| `compute.flags` | `:1120-1121` | **MBZ**, stated verbatim in the header. Nothing to derive or RE — a Linux ABI decision, fully specified by its own text. | n/a (normative) | **MAPPED** |
| `compute.sampler_count` | `:1123-1124` | Same shape/caveat as `render.sampler_count` | `EXP-G1a`/RT-2a (A18), same heap-model caveat | **PARTIAL** |
| `compute.cdm_ctrl_stream_base` | `:1127-1130` | GPU VA of the userspace-built CDM stream (`cs->addr`) | `EXP-0024`/`EXP-0027` (A18) + `EXP-0043`/`EXP-0049`/`EXP-0110` (M4, `DATA-TRACE-VALIDATED`) + `EXP-0116` (M4, **`HW-VALIDATED`**, hand-built link followed by real hardware; also shows CDM segment relocation is **client-heap-relative**, `EXP-0110`) | **MAPPED** |
| `compute.cdm_ctrl_stream_end` | `:1132-1137` | Unlinked: `cs->addr + (cs->current - cs->start)` (exact). **Linked/chained: Mesa's own reference driver uses a hardcoded placeholder, `65536 /* XXX */`** — an acknowledged-incomplete convention even upstream. | `EXP-0043` (M4, `DATA-TRACE-VALIDATED`): locates the exact segment **capacity** (732 CDM records/segment), reproduced by `EXP-0049`/`EXP-0110`/`EXP-0116` — arguably better-grounded than Mesa's placeholder for the chained case, though this project has not derived a replacement `end` formula either | **PARTIAL** |
| `compute.sampler_heap` | `:1139-1140` | Same shape/caveat as `render.sampler_heap` | Same as `render.sampler_heap` | **PARTIAL** |
| `compute.helper.binary` | `:891-911`, `:1143` | Same shape as render helpers | `EXP-0041` (M4): CS K96/K112/K160 (208-576 B scratch) — same negative result | **PARTIAL** |
| `compute.helper.cfg` | `:898` | Same shape | same | **PARTIAL** |
| `compute.helper.data` | `:902-909` | GPU VA of `dev->scratch.cs.buf` | same | **PARTIAL** |
| `compute.ts.start.handle` | `:1146` → `:842-878` | Same shape as render timestamps | `EXP-0027`/`EXP-0052`, general GPU-timestamp findings (not compute-dispatch-specific in those experiments) | **PARTIAL** |
| `compute.ts.start.offset` | same | same | same | **PARTIAL** |
| `compute.ts.end.handle` | same | same | same | **PARTIAL** |
| `compute.ts.end.offset` | same | same | same | **PARTIAL** |

---

## OBSERVED vs INTERPRETED

**Directly OBSERVED this experiment** (raw evidence in `raw/m4_20260828_run0{1,2}/`):
- Exact captured `float` values for every grid/ladder/boundary sample-position case, at the
  documented BO VA and offset, for both runs, byte-identical.
- Exact `supportsTextureSampleCount:` boolean and exact texture/pipeline construction
  outcome (including verbatim assertion text on failure) for every swept `samples` value,
  both runs, byte-identical.
- Exact process termination behavior (signal, no GPU dispatch reached) for every
  out-of-contract input.

**INTERPRETED / synthesized** (not independently re-derived from Apple9 hardware this
experiment): every Mesa-source-derived formula, bit layout, and constant cited in the field
table (marked PUBLIC/STRUCTURAL); the identification of `EXP-0055`'s `0x58000+0x36` byte as
"Fragment control.Depth bias enable bit17" (a convergent, unspliced cross-reference); the
claim that `ppp_multisamplectl`'s 4-bit/4-bit byte packing is exactly what Apple9 hardware
consumes (the packing formula is PUBLIC; the *grid and rounding rule* it depends on is now
M4-hardware-confirmed by this experiment, but the literal 64-bit register write was never
observed — macOS provides no observation point for it).

**Not established, at all, by this experiment or its citations:** the byte layout of the
scissor/depth-bias descriptor arrays on Apple9 (location, not just format); the numeric
value or bit-for-bit correctness of `zls_ctrl`/`ppp_ctrl`/`isp_zls_pixels` on any Apple9
target; whether the BG/EOT `rsrc_spec` "Counts" struct genuinely matches Apple9's ABI;
`command_timestamp_frequency_hz`'s actual value.

## What P0.3 still needs

- A **Linux kernel + firmware environment** (out of scope for this repository per
  `CLAUDE.md`) is the only way to directly observe `zls_ctrl`, `ppp_ctrl`,
  `isp_zls_pixels`, `command_timestamp_frequency_hz`, and the BG/EOT `rsrc_spec` register
  writes — macOS structurally hides these (§6 of `docs/kernel-interface.md`), not merely
  "has not yet exposed" them.
- **Locate the scissor/depth-bias array** on macOS: neither the naive `0x58000`/`0x68000`
  candidates (ruled out, `EXP-0054`/`EXP-0055`) nor any other BO has been searched with the
  16-byte-Scissor/12-byte-Depth-bias record shapes now known from PUBLIC source as a search
  template — a concrete, well-scoped next probe.
- **`isp_merge_upper_x/y`**: resolve the header-vs-Mesa multiply/divide discrepancy with an
  authored M4 splice test (feed a known-wrong value for one formula and observe whether
  hardware triangle-merge behavior changes as that formula predicts).
- **Helper/scratch ABI** (`*_helper.{binary,cfg,data}`, 9 of the 12 remaining `PARTIAL`
  leaves touching this area): `EXP-0041`'s negative result needs a stronger probe — e.g.
  much larger forced-scratch programs, or a `bograph.py`-style full BO census rather than an
  allowlisted comparison, to find where (if anywhere in a macOS-visible location) scratch
  state actually lives.
- **`compute.cdm_ctrl_stream_end`** for the linked/chained case: neither Mesa nor this
  project has a non-placeholder formula; `EXP-0043`'s 732-record segment capacity is a
  starting point for deriving one.
- **`render.layers`**: no dedicated experiment exists; needs an authored layered-rendering
  M4 probe (the field-matrix's `EXP-0028` citation was a mismatch, corrected above).

## Gate results

- `harness/verify.py --selftest`: **PASS** (0 issues) — 10 recorded-reality fixtures (real
  M4 captures from `run.py`'s own output, not hand-typed) validate schema, 10 known-value
  regression checks (grid/rounding/boundary/capability results), the VA-exclusion proof
  (a synthetic VA-only difference does **not** fail the gate; a synthetic `observed.x0`
  difference and a synthetic `status` difference **do** fail it), a synthetic hex-parser
  unit check, and case-matrix sanity (exactly 59 frozen cases, no duplicate ids).
- `harness/verify.py --seqtest`: **PASS** (6/6 checks) — `PRE_GPU -> RUN01_PRESENT ->
  RUN02_PRESENT` state machine, case-count-per-run-dir check, identical-fake-runs-compare-
  equal check, and quarantine-directory exclusion, all in an isolated scratch dir
  independent of the real `raw/`.
- Non-recorded smoke gate: **PASS** both runs — `work/m4_20260828_run0{1,2}_smoke.json`
  written and checked **before** the corresponding `raw/m4_20260828_run0{1,2}/` directory
  was created (`run.py main()`); a failing smoke case would have aborted before any `raw/`
  artifact existed (not exercised as a failure this run — both smoke cases passed).
- `harness/verify.py --captured --run01 m4_20260828_run01 --run02 m4_20260828_run02`:
  **PASS** (0 issues) — all 59 cases present in both runs, every gated field
  (`case_id`/`family`/`kind`/`params`/`status`/`observed`) byte-identical; `va_vtxbuf`/
  `va_resbuf` excluded per the standing gate and proven (above) not to mask a real
  difference.
- No run id was reused; `m4_20260828_run01`/`m4_20260828_run02` are the only two entries in
  `raw/`. No post-capture repair was applied to any file under `raw/`.

## Clean-room provenance

```text
Clean-room provenance: PUBLIC (Mesa/asahi_drm.h, MIT-licensed, this repository's existing
  practice of citing mesa/src/asahi/** for driver-shape reference) + DATA-TRACE (tools/
  iotrace, read-only, unmodified) + HW-PROBE (Metal capability query, texture/pipeline/
  render-pass construction and validation behavior) + OWN-SHADER (inline MSL compiled at
  runtime, our own source) + citation of this repository's prior EXP-0014/0017/0019/0021/
  0024/0027/0028/0041/0042/0043/0044/0045/0048/0049/0052/0054/0055/0110/0116, EXP-G1a/G1b,
  EXP-O2A, RT-4, RT-11, EXP-M4-03.
Inputs inspected: mesa/include/drm-uapi/asahi_drm.h; mesa/src/asahi/vulkan/hk_queue.c,
  hk_cmd_draw.c, hk_device.c, hk_cmd_buffer.h; mesa/src/asahi/genxml/cmdbuf.xml;
  mesa/src/asahi/lib/agx_helpers.h, layout/layout.h (all pinned MIT-licensed Mesa source,
  read-only reference per CLAUDE.md — never edited, never copied into a driver, used only
  to document field shape); this experiment's own authored harness/kernels and their raw
  M4 output.
Apple binary introspection: NONE.
Reproduction: harness/run.py --run <id> --out raw/<id>; harness/verify.py --selftest
  --seqtest; harness/verify.py --captured --run01 m4_20260828_run01 --run02
  m4_20260828_run02.
Evidence: raw/m4_20260828_run01/{records.jsonl,hex/,run_manifest.json},
  raw/m4_20260828_run02/{records.jsonl,hex/,run_manifest.json}, fixtures/
  recorded_reality.json, work/m4_20260828_run0{1,2}_smoke.json, manifest.json.
```

## STOPs / notes for the orchestrator

- **Numbering collision**: `experiments/EXP-0126-m4-lifecycle-boundary-probe/` also exists
  under the `EXP-0126` number (observed mid-session; concurrent orchestrator activity —
  several other `EXP-01xx` directories appeared during this run too). This experiment kept
  the exact dispatched path, `experiments/EXP-0126-m4-uapi-field-mapping/`; needs
  resolution (rename one) before commit.
- This experiment does **not** close P0.3 (which requires all 65 leaves at a closure-grade
  status under the six rules in `docs/P0-P1-CLOSURE.md`, plus A18 replication where the
  matrix demands it). It substantially deepens the synthesis and closes the two named
  highest-value gaps (`ppp_multisamplectl`/sample positions, `render.samples`) with genuine
  new M4 hardware evidence.
- No `git commit` was made; no file outside `experiments/EXP-0126-m4-uapi-field-mapping/`
  was written; `tools/iotrace/iotrace.c` was read and built from, never edited;
  `mesa/` was read-only throughout.
