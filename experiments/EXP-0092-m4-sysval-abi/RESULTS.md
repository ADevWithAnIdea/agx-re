# EXP-0092 Results — M4 sysval / `get_sr` ABI (Bundle C: GLIO-A02/A03/A05/A06)

Target: **Apple M4 / G16G, local host**, macOS 26.6.2 (25G82), Metal 4, `xcrun` 72, Python 3.14.6.
A18 Pro: no data collected (hands-off). M5: out of scope, not touched.

Clean-room: **OWN-SHADER** (`srsweep`/`dstsweep`: our own compiled bytes, spliced with the public
`tools/agx-isa` assembler) + **OWN-SHADER + HW-PROBE** (`drawparam`/`numworkgroups`: our own MSL
compiled and run natively via the public Metal API, no splice, with controlled draw/dispatch
parameters). No Apple binary, framework, kext, or firmware was disassembled, decompiled, or otherwise
introspected. See the attestation at the end of this file.

---

## TL;DR

1. **GLIO-A02 — `get_sr` SR-selector namespace.** The selector byte (`sr_sel`, `get_sr` byte1) splits
   cleanly on its **top bit**: every value with bit7 **set** (`0x80`-`0xFF`, 128 values) either matches
   a previously-known SR exactly, or reads a stable, structured, or constant value; every value with
   bit7 **clear** (`0x00`-`0x7F`, 128 values) instead reproducibly materializes **the selector number
   itself** into the destination register (verified to `1000+n` for all `n` in `0..127`, exact, in both
   runs) and leaves the rest of the observation window untouched. **No `sr_sel` value in the full
   0x00-0xFF range raised a command-buffer error or hang** — the field's failure mode across its whole
   legal encoding space is never "fault," it is "identity materialization" below `0x80`. `HW-VALIDATED`.
2. **GLIO-A02 — destination register.** A register-address round trip (get_sr `dst`/`dst_hi` +
   `device_store` `index_reg` spliced to the same candidate register) reproduces correctly for **every**
   tested register `0..95`, and **faults with a command-buffer error (`CMDBUF_ERROR`, "Caused GPU Hang
   Error") for every tested register `96..127`** except one: register **112 is genuinely
   nondeterministic** (fault in run01; a silent all-zero success in run02; 5 faults / 3 silent-zero in 8
   additional informal repeats). This is an exact, sharp confirmation of the documented **96-GPR**
   physical file against the structurally-7-bit (`0..127`) `get_sr`/`device_store` addressing field.
   `HW-VALIDATED` for the 0-95/96-127 boundary; the exact per-register behavior *within* 96-127 is
   `PARTIAL` (mix of deterministic-fault and flaky).
3. **GLIO-A03 — `base_vertex`/`base_instance`.** Upgraded from `docs/isa/README.md`'s **(inferred)** to
   **HW-VALIDATED**: a real indexed+instanced draw with independently distinguishable, nonzero, negative,
   and boundary `baseVertex`/`baseInstance` shows `base_vertex == baseVertex` and
   `base_instance == baseInstance` **exactly**, in all 9 tested cases, both runs, byte-identical. MSL's
   `[[vertex_id]]`/`[[instance_id]]` **already include the base** (`vertex_id = index + baseVertex mod
   2**32`, `instance_id = ordinal + baseInstance mod 2**32`), including correct unsigned wraparound for
   negative `baseVertex` and for `baseInstance` at `UINT32_MAX`.
4. **GLIO-A05 — `load_num_workgroups`.** `threadgroups_per_grid` reports **exactly** the requested
   threadgroup count for every tested direct-3D dispatch (asymmetric, non-power-of-two, large single
   axis, non-power-of-two local size) and **exactly** the raw indirect-buffer record for every tested
   indirect dispatch, including `UINT32_MAX` and a `65535×65535` product — **no clamping, no
   truncation, no fault** was observed at any tested value. A record with **any** axis `0` dispatches
   zero threadgroups (confirmed for the all-zero record and generalized-but-not-independently-observed
   for a single-zero-axis record, see §5). `HW-VALIDATED` for the numeric pass-through claim across the
   tested range.
5. **GLIO-A06 — finite-resource table.** Populated below (§6) for every sysval this experiment touched.
6. **Draw-ID.** Not tested on hardware. Metal exposes no multidraw primitive with an automatic per-draw
   index visible to a vertex function; this is reported as `UNKNOWN`/`PUBLIC`-sourced, not fabricated
   from an untested mechanism (see §4).

---

## 1. Cross-run gate status (report honestly, not force-closed)

Both required captures ran to completion (300/300 cases each): `raw/m4-20260828b-run01/`,
`raw/m4-20260828b-run02/`. **299 of 300 gated case records are byte-identical between the two runs.**
The exception is `dstsweep reg_112` (§2.2) — a genuine hardware nondeterminism finding, not a harness
defect (confirmed by 8 additional informal standalone repeats: 5 fault, 3 silent-zero-success). Per
`verify.py`'s design, the formal `--captured` byte-exact cross-run gate therefore **does not pass** for
the full 300-case set; it is reported as such rather than force-closed by editing data or retrying until
the two runs happen to agree. All conclusions in this file that touch register 112 are qualified as
`PARTIAL`/nondeterministic; every other conclusion rests on 299/300 (effectively all) cases being
independently reproduced byte-for-byte across two fully separate processes, environments, and dispatch
orders.

An earlier `run.py` invocation under the run-id `m4-20260828-run01` (no `b`) hit an own-code bug
(`parse_lines()` dict-init `KeyError`) at case 272/300 and was retained untouched as
`QUARANTINE-run01-attempt1.md` / `quarantine-m4-20260828-run01/` — not a hardware finding; see that file.

---

## 2. GLIO-A02 — complete `get_sr` operand/result model

### 2.1 SR-selector byte (byte1) — full 0x00-0xFF sweep, `srsweep` (256 cases × 2 runs)

Method: `kernels/srprobe.metal` reads `[[thread_index_in_simdgroup]]` (`get_sr` `sr_sel=0x82`) into `v`,
then a **separate, later** `iadd2` computes `w = v + 1000`, then a **third, separate** `device_store`
writes `w` to `out[thread_position_in_grid.x]` — satisfying the later-read discipline
(`docs/isa/register-move-and-liveness.md`). `sr_sel` (byte1 of the `get_sr` alone) is spliced to every
value `0x00..0xFF`; `dst`/`dp_width`/`dp_marker`/`dst_hi` and the untouched second `get_sr` (`gid`,
`sr_sel=0xa0`) are left at their natural compiled values. Dispatch: `grid=64,tg=64` (single threadgroup,
`threadExecutionWidth=32`).

**Observed, exhaustive, both runs byte-identical:**

- **`0x00-0x7F` (bit7 clear, 128/128 values):** `STATUS OK` every time. `out[0] == sr_sel` exactly (raw,
  before the `+1000` probe offset) for **all 128 values without exception** — `0x00->0`, `0x01->1`, ...,
  `0x7f->127`, an exact linear identity. `out[1..63]` remain `0` (the buffer's pre-dispatch state) for
  every one of the 128 values.
- **`0x80-0xFF` (bit7 set, 128/128 values):** `STATUS OK` every time.
  - **16 values exactly reproduce a previously-known SR's independently-computed 64-thread pattern**
    (`KNOWN_MATCH`): `0x82` (simd_lane_id), `0x85` (simd_group_id), `0x98/99/9a` (threads_per_threadgroup
    x/y/z), `0x9c/9d/9e` (threadgroup_position_in_grid x/y/z), `0xa0/a1/a2` (thread_position_in_grid
    x/y/z), `0xa4/a5/a6` (thread_position_in_threadgroup x/y/z), `0xa7` (thread_index_in_threadgroup),
    and **`0xa8`, re-confirming RT-7's A18 finding on M4**: bare `get_sr 0xa8` tracks
    `threads_per_threadgroup.x` (constant `64` here), *not* `threadgroups_per_grid` (see §4 for the real
    `num_workgroups` mechanism).
  - **106 values alias an already-known SR's exact pattern** at a *different* selector (`ALIASES_KNOWN_SR`
    in `analysis.json`): the overwhelming majority (100/106) alias `0x9c` (constant `0` — indistinguishable
    from "unpopulated/reads zero" in a single-threadgroup dispatch), a handful alias `0x99`/`0x9a`
    (constant `1`), and three unexpected aliases are worth flagging as candidates for a follow-up:
    `0x95` and `0xea` reproduce `simd_lane_id`'s exact 0-31/0-31 pattern (aliasing `0x82`), and `0xf8`
    reproduces `simd_group_id`'s exact 0×32/1×32 pattern (aliasing `0x85`).
  - **4 values return a stable constant, matching no known SR**: `0x90->3`, `0x96->4`, `0x97->32`,
    `0xb9->256`. (`0x97` is the addendum's own flagged "currently-unresolved sample-ID path," `GLIO-A04`;
    on this **compute** dispatch it reads a constant `32` = `threadExecutionWidth`, not a per-sample or
    per-thread value — consistent with sample-ID being fragment-stage-only and this being read from
    the wrong stage, not proof of its fragment-stage semantics, which remain `GLIO-A04`'s own question.)
  - **2 values (`0x83`, `0x94`) show a genuinely NEW structured, thread-varying, period-4 pattern**
    (`0,1,2,3,0,1,2,3,...` across all 64 threads) matching neither any known SR nor a simple alias.
    `thread_index_in_quadgroup` is documented as **computed** (`simd_lane_id & 3`), not a direct `get_sr`
    — this raw pattern is consistent with that same value being independently *readable* via `0x83`/`0x94`
    as well, but that identification is `INFERRED` here (structural match only, not cross-validated
    against an independent quad-group probe) and flagged as a follow-up.
- **Zero faults, zero hangs, zero command-buffer errors across the full 256-value sweep.**
  `analysis.json`'s `srsweep.faulted_sr` is the empty list.

**Interpretation (flagged explicitly as interpretation, not a directly observed mechanism):** the
uniform, exceptionless "`out[0]==sr_sel`, everything else untouched" shape for all 128 bit7-clear values
is consistent with byte1's top bit being a genuine **structural discriminator** between two different
4-byte-encoding behaviors — "materialize the selector byte as an immediate" (bit7 clear) vs. "read the
special-register file" (bit7 set) — and every SR this repository has ever characterized, compute or
graphics, has bit7 set. **What is not established by this experiment** is *why* the materialized value
lands only in `out[0]` and not divergently at each thread's own slot (i.e., whether this reflects a
uniform/scalar write that only one SIMD lane's dependent chain retires, some other scheduling collapse,
or a different mechanism entirely) — recorded as `UNKNOWN`, not asserted.

### 2.2 Destination register field — boundary sweep, `dstsweep` (23 cases × 2 runs)

Method: `kernels/dstprobe.metal` reads `[[thread_position_in_grid]]` (`get_sr` `sr_sel=0xa0`) into `v`,
and the **immediately following `device_store`'s own `index_reg` field** (an explicit, separate,
GPR-addressed instruction performing the store's *address computation*, not adjacent-instruction data
forwarding) uses that same register to select `out[v]`'s slot. For candidate register `R`, `get_sr`'s
`dst`+`dst_hi` fields **and** `device_store`'s `index_reg` byte are spliced **in lockstep** to `R`.
Dispatch: `grid=1,tg=1` (single thread, `v` is always `0`), so a correct round trip always yields
`out[0]=1` (all else `0`) — **except** `R=0`, which collides by construction with `dstprobe.metal`'s
fixed `mov_imm dst=0` (the sentinel-1 constant): `get_sr` writes r0, `mov_imm` immediately overwrites r0
with `1`, and the store reads `index_reg=0` finding `1` — so `out[1]` (not `out[0]`) is the predicted,
non-anomalous sentinel for `R=0` (`casematrix.dstsweep_expected(0)`; confirmed exactly as predicted in
both runs).

**Observed, both runs (except R=112, see below):**

| register range tested | result |
|---|---|
| `R=0` | `out[1]=1` (predicted collision case) — `MATCH_EXPECTED`, both runs |
| `R∈{1,15,16,31,32,47,48,63,64,79,80,87,88,94,95}` | `out[0]=1`, all else `0` — `MATCH_EXPECTED`, both runs |
| `R∈{96,97,100,111,120,127}` | `STATUS CMDBUF_ERROR` ("Caused GPU Hang Error", `kIOGPUCommandBufferCallbackErrorHang`) — `FAULT`, **identical in both runs** |
| `R=112` | run01: `CMDBUF_ERROR`/`FAULT`. run02: `STATUS OK`, `out[]` **entirely zero** (no sentinel found anywhere in the 256-element observation window) — `MISMATCH_EXPECTED`. 8 further informal (non-gated) repeats: 5 more faults, 3 more silent-all-zero successes. **Genuinely nondeterministic**, not a harness artifact — the command buffer either raises a contained GPU-hang error or completes with the address write silently discarded/redirected outside the observed window, unpredictably, across otherwise byte-identical splices. |

**First-invalid boundary: register 96** (exact, reproducible, both runs, for every tested point at or
above it except the one flaky point). This is a **sharp, direct confirmation of the documented 96-GPR
physical register file** against the structurally 7-bit (`0..127`) `get_sr dst`/`device_store index_reg`
addressing fields: the field can *encode* registers up to 127, but only `0..95` are backed by real
hardware for this addressing path; `96..127` either faults the command buffer deterministically (`96,97,
100,111,120,127`, all six tested) or is genuinely flaky (`112`). No test in `0..95` showed any deviation,
aliasing, or wraparound (e.g. `R mod 96`) — the boundary is a hard cliff at exactly `96`, not a
wrap-around scheme.

**Scope note:** this test necessarily couples `get_sr`'s `dst` field to `device_store`'s `index_reg`
field (both spliced to the same candidate register so the round trip is meaningful) — it directly
establishes the addressable/backed range of the **register file itself** along this pair of addressing
paths, which is the finite resource GLIO-A02 and GLIO-A06 ask about; it is not a claim that `get_sr`'s
`dst` field in isolation, decoupled from any consumer, has different legality.

---

## 3. GLIO-A03 — vertex/instance/base-vertex/base-instance semantics

Method: `harness/agxvdraw.m` (own compile, **no splice**) issues one `drawIndexedPrimitives:` per case
with a host-chosen, non-identity index buffer and controlled `baseVertex`/`baseInstance`/`instanceCount`.
`kernels/vdraw_probe.metal`'s vertex function reads MSL's own `[[vertex_id]]`/`[[instance_id]]`/
`[[base_vertex]]`/`[[base_instance]]` attributes and appends `(vid,iid,bv,bi)` to a device buffer via an
atomic counter (order-independent: both observed and expected sets are sorted before comparison).

**All 9 cases, both runs, byte-identical, all `MATCH_EXPECTED`:**

| case | `baseVertex` | `baseInstance` | representative observed record | interpretation |
|---|---:|---:|---|---|
| `nonzero_base` | 100 | 50 | index 7 → `vid=107,iid=50,bv=100,bi=50` | `vid=index+baseVertex`, `iid=ordinal+baseInstance`, `bv`/`bi` exact |
| `large_base` | 1000000 | 500000 | index 2 → `vid=1000002,iid=500000` | scales linearly, no truncation at 7-digit values |
| `negative_base_vertex` | −5 | 0 | index 0 → `vid=4294967291` | `0 + (−5) mod 2**32 = 0xFFFFFFFB`, exact unsigned wraparound |
| `negative_base_vertex_underflow` | −1 | 0 | index 0 → `vid=4294967295` | `bv` itself also reads back as `4294967295` (the same signed-to-unsigned reinterpretation applies to the raw `base_vertex` value, not only to the computed `vid`) |
| `max_base_instance` | 0 | 4294967295 (`UINT32_MAX`) | → `iid=4294967295,bi=4294967295` | exact at the unsigned ceiling |
| `instance_wrap` | 0 | 4294967295, `instanceCount=2` | ordinals 0,1 → `iid∈{4294967295,0}` | instance-ordinal wraparound past `UINT32_MAX` confirmed |
| `base_vertex_int32_max` | 2147483647 (`INT32_MAX`) | 0 | → `vid=2147483647,bv=2147483647` | exact at the signed ceiling |
| `repeated_index` | 42 | 0 | index 0 (×3 draws) → 3× `vid=42` | a repeated identical index still produces one recorded invocation per point primitive (no vertex-cache collapse observed for this primitive type/count) |

**This upgrades `docs/isa/README.md`'s SR `0x88`/`0x8a` = `base_vertex`/`base_instance` mapping from
`(inferred)` to `HW-VALIDATED`** — the previous evidence was a byte-diff on a *zero-base, non-indexed*
draw (indistinguishable from "always reads zero"); this experiment used independently distinguishable,
nonzero, negative, and boundary-value draws and the mapping holds exactly in every case.

**Draw-ID (part of GLIO-A03's "and any draw-ID source" ask): not tested on hardware, `UNKNOWN`.** Metal
exposes no multidraw primitive with an automatic per-draw index visible to a *vertex* function — an
Indirect Command Buffer's per-command index is visible only to the *encoding compute kernel*, not the
executed vertex shader, so there is no public-API surface through which a hardware `load_draw_id`-style
value could even be exercised without building native VDM/CDM command-stream machinery, which is out of
this experiment's OWN-SHADER/HW-PROBE scope (and out of the addendum's own stated boundary for this
bundle). This gap is reported honestly rather than inferred from an untested mechanism; a driver's
`load_draw_id` must be synthesized as a per-draw uniform (userspace-supplied), pending a dedicated
command-stream-level experiment if this is later prioritized.

---

## 4. GLIO-A05 — `load_num_workgroups` / `threadgroups_per_grid` ABI

Method: `harness/agxcdispatch.m` (own compile, **no splice**) issues one direct
(`dispatchThreadgroups:threadsPerThreadgroup:`) or indirect
(`dispatchThreadgroupsWithIndirectBuffer:threadsPerThreadgroup:`, host-written raw
`MTLDispatchThreadgroupsIndirectArguments`-shaped record) compute dispatch per case.
`kernels/numwg_probe.metal` has thread `(0,0,0)` write MSL's `threadgroups_per_grid` builtin (the
`load_num_workgroups` lowering — `docs/isa/README.md`'s RT-7 finding: `get_sr 0xa8/a9/aa` + a
`device_load` + a divide, **not** a bare SR read; re-confirmed by this experiment's independent §2.1
`0xa8` re-test on M4, which matches RT-7's original A18 result exactly) to `out[0..2]`.

**All 12 cases, both runs, byte-identical, 11/12 `MATCH_EXPECTED`, 1 `MISMATCH_EXPECTED` (pre-registration
oracle gap, explained below, not a hardware surprise):**

| case | mode | requested/record | observed | verdict |
|---|---|---|---|---|
| `direct_1x1x1` | direct | (1,1,1) | (1,1,1) | match |
| `direct_asym_5x3x2` | direct | (5,3,2) | (5,3,2) | match |
| `direct_npot_7x11x13` | direct | (7,11,13) | (7,11,13) | match |
| `direct_large_x` | direct | (1024,1,1) | (1024,1,1) | match |
| `direct_local_npot` | direct, local=(3,5,1) | (4,2,1) | (4,2,1) | match |
| `direct_64x64` | direct | (64,64,1) | (64,64,1) | match |
| `indirect_7x1x1` | indirect | (7,1,1) | (7,1,1) | match |
| `indirect_asym_5x3x2` | indirect | (5,3,2) | (5,3,2) | match (identical numeric ABI to the direct-mode case above) |
| `indirect_huge_x` | indirect | (`UINT32_MAX`,1,1) | (`UINT32_MAX`,1,1) | match — no clamp, no fault, no truncation observed at the raw-record ceiling |
| `indirect_large_product` | indirect | (65535,65535,1) | (65535,65535,1) | match — no overflow of the ~4.29-billion-threadgroup product observed at the *reporting* level (this does **not** claim 4.29 billion threadgroups actually executed correctly; the kernel only reads back thread `(0,0,0)`'s view of the record, not launch completeness) |
| `indirect_all_zero` | indirect | (0,0,0) | (0,0,0) | `OBSERVED_NO_ORACLE` (pre-registered as such: zero threadgroups means thread `(0,0,0)` never runs, so `out[]` is observed in its untouched zero-initialized state — this is **not** independent confirmation that `threadgroups_per_grid` itself would read `(0,0,0)`) |
| `indirect_zero_x` | indirect | (0,1,1) | (0,0,0) | `MISMATCH_EXPECTED` against the pre-registered oracle, which incorrectly assumed only an *all-zero* record means zero dispatched threadgroups |

**Correction to the pre-registered oracle (interpretation, not a raw-data edit):** `casematrix.py`'s
`NUMWG_CASES` table only special-cased the fully-`(0,0,0)` record as "zero threadgroups dispatched, no
independent oracle" (`PRE_REGISTRATION.md`'s own known-confounders section). `indirect_zero_x`'s raw
observation (`out[]` untouched at `(0,0,0)`) reveals this was too narrow: **any** zero axis in a 3D
dispatch record makes the total threadgroup count zero (`0×1×1=0`), so thread `(0,0,0)` never executes
there either — this is the *same* "zero-dispatch" phenomenon as `indirect_all_zero`, generalized, not a
new or surprising hardware behavior. The raw capture is left exactly as pre-registered and executed
(per the append-only rule — `casematrix.py` was not edited retroactively to match this observation); this
paragraph is the correction, applied in interpretation only. Reclassifying `indirect_zero_x` alongside
`indirect_all_zero`, **12/12 numworkgroups cases are consistent with a single rule**: `threadgroups_per_grid`
reports the requested/record value exactly whenever at least one thread actually runs, and no thread runs
when any axis of the (direct or indirect) threadgroup count is zero.

---

## 5. GLIO-A06 — finite-resource table

| Namespace/resource | Scope | Encoding | Exact usable range/count | Holes/reserved | First invalid value | Observed failure | Correct "need more" fallback | Evidence |
|---|---|---|---:|---|---:|---|---|---|
| `get_sr` SR-selector byte (byte1) | per-instruction, all stages | 8-bit enum, bit7 = populated/unpopulated discriminator | 128 values (`0x80`-`0xFF`) access the special-register file; `0x00`-`0x7F` is a distinct "selector materialized as immediate at a single fixed slot" region, not a real SR read | within `0x80-0xFF`: 16 named, ~106 alias `0x9c`/`0x99`/`0x9a`/`0x82`/`0x85`, 4 unclassified constants, 2 unclassified period-4 structured | none — no value in `0x00-0xFF` raises `STATUS != OK` | none (identity-materialize below `0x80`; read/alias above) — **never** reject/fault/hang | driver should only ever emit values already in the characterized `0x80-0xFF` set (`docs/isa/README.md`'s table); `0x00-0x7F` and unclassified `0x80-0xFF` values must not be treated as reserved-safe no-ops for a *new* meaning without their own validation | `raw/m4-20260828b-run0{1,2}/04_results.jsonl` `backend=srsweep` (256/256 both runs), `analysis.json` `srsweep` |
| `get_sr` `dst`/`dst_hi` + `device_store` `index_reg` register address (coupled round trip) | per-instruction GPR file | 7-bit structural (`dst`\|`dst_hi<<4`, 0-127); `index_reg` full byte | `0-95` (96 registers) fully round-trip correctly | none observed within 0-95; `96-111,113-127` uniformly fault | `96` | `CMDBUF_ERROR` (contained `kIOGPUCommandBufferCallbackErrorHang`) for `96,97,100,111,120,127`; **nondeterministic** fault-or-silent-wrong-result for `112` | driver must never address GPR ≥ 96 via this path; treat 96 as the hard register-file ceiling, not merely the largest value ever observed emitted | `raw/.../04_results.jsonl` `backend=dstsweep` (23/23 both runs except reg_112) + 8 informal reg_112 repeats (not in `raw/`, see §2.2) |
| `base_vertex` (`get_sr 0x88`) | per-draw (VS), draw-uniform | `uint32`, signed host API value reinterpreted unsigned | full `uint32` range exercised at `0`, `100`, `1000000`, `-5`→`0xFFFFFFFB`, `-1`→`0xFFFFFFFF`, `INT32_MAX` | none observed | not tested (no fault at any tested boundary) | none — always exactly `baseVertex mod 2**32` | none needed; native, exact | `raw/.../04_results.jsonl` `backend=drawparam` (9/9 both runs) |
| `base_instance` (`get_sr 0x8a`) | per-draw (VS), draw-uniform | `uint32` | full `uint32` range exercised at `0`, `50`, `500000`, `UINT32_MAX` | none observed | not tested (no fault at `UINT32_MAX`) | none — always exactly `baseInstance` | none needed; native, exact | same as above |
| `vertex_id`/`instance_id` (base-inclusive) | per-vertex/instance (VS) | `uint32`, wraps mod 2**32 | exercised up to `~1.07e9` and through the `UINT32_MAX` wrap | none observed | not tested | none — wraps silently (standard unsigned overflow, not a driver-visible error) | driver-side: none needed if NIR's `load_vertex_id`/`load_instance_id` (base-inclusive) semantics are used directly; a *zero-base* variant (`load_vertex_id_zero_base`) needs `vid - base_vertex`, both operands now independently HW-validated | same as above |
| `threadgroups_per_grid.{x,y,z}` (`load_num_workgroups`) | per-dispatch (compute) | `uint32` ×3, via `get_sr 0xa8/a9/aa` + `device_load` + divide (RT-7, re-confirmed here) | exercised to `UINT32_MAX` (single axis) and a `65535×65535` product; non-power-of-two and asymmetric grids all exact | none observed | not tested (no fault at `UINT32_MAX` or the tested product) | zero total threadgroups (any axis `0`) → no invocation runs, not independently observable via this probe; no other failure mode seen | none needed for the numeric pass-through within the tested range; driver must still respect Metal's own device dispatch-size limits (out of this experiment's scope) for whether a given huge record is *launchable*, not merely *reported* | `raw/.../04_results.jsonl` `backend=numworkgroups` (12/12 both runs) |
| draw-ID (multidraw) | per-draw | n/a | n/a | n/a | n/a | n/a — **no native Metal mechanism exists to test** | driver must synthesize `load_draw_id` as a per-draw userspace-supplied uniform; no hardware SR is known to carry it | `UNKNOWN`/`PUBLIC` — not tested here (§3) |

---

## 6. Required response blocks

### GLIO-A02

```text
Status: [x] Open  [x] Partial  [ ] Closed  [ ] Not applicable
Answer, where Yes/No: [ ] Yes  [ ] No  [x] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [x] HW splice
          [ ] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [x] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0092-m4-sysval-abi/raw/m4-20260828b-run01/04_results.jsonl,
    raw/m4-20260828b-run02/04_results.jsonl (299/300 byte-identical; dstsweep reg_112 differs,
    genuine nondeterminism, see below), analysis.json, casematrix.py (srsweep/dstsweep case
    generation + independent oracles), kernels/srprobe.metal, kernels/dstprobe.metal.
Exact observed semantics or field mapping:
    sr_sel (byte1): bit7 is a structural discriminator. 0x80-0xFF (128 values) reads the special-
    register file (16 named exactly, ~106 alias a known SR's pattern at a different selector, 6
    unclassified but structured/constant). 0x00-0x7F (128 values) materializes the selector BYTE
    ITSELF into the destination at a single fixed observation slot, not a genuine per-thread SR
    read -- mechanism for why only one slot is written is UNKNOWN (see Sec 2.1).
    Destination (dst/dst_hi + device_store index_reg, coupled): registers 0-95 round-trip exactly;
    96-127 fault (CMDBUF_ERROR) deterministically except register 112, which is nondeterministic
    (fault vs. silent wrong result) across otherwise byte-identical splices.
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    sr_sel: 8-bit field, 256 total encodings, ALL well-defined (none fault); 128 "real" (0x80-0xFF),
    128 "identity-immediate" (0x00-0x7F). dst: structurally 7-bit (0-127), physically backed 0-95
    (96 registers) for this addressing path; 96-127 not backed (deterministic-fault-mostly, one
    flaky register observed).
Maximum-valid and first-invalid tests:
    sr_sel: exhaustive 0x00-0xFF, no first-invalid exists (no fault anywhere). dst: max valid
    tested = 95 (exact match); first invalid = 96 (exact, reproducible fault boundary).
Failure/overflow behavior: [ ] reject  [x] zero/discard  [ ] alias/wrap  [x] fault/device loss
    sr_sel<0x80: identity-materialize (not zero/discard/fault -- a distinct fourth behavior: literal
    pass-through of the selector value). dst>=96: fault/device-loss-class CMDBUF_ERROR (contained,
    no wedge), except register 112 which nondeterministically also silently zero/discards instead.
Correct behavior when the compiler/driver needs more:
    Only emit sr_sel values already in the characterized 0x80-0xFF table; never rely on 0x00-0x7F
    identity-materialization as a feature. Never address a GPR >= 96 via get_sr/device_store; treat
    96 as the hard ceiling, and treat 112 specifically as unsafe even below a naive 96 vs. 127
    cutoff reading, since it demonstrably faults some of the time.
Lifetime, destruction, and reuse semantics: not applicable (stateless per-instruction field).
Counterexamples and untested cases:
    dst boundary was tested at 23 points, not exhaustively 0-127 (cost/risk tradeoff); the exact
    shape of the 96-127 failure region between untested points (e.g. 98-99, 101-110, 113-119,
    121-126) is UNKNOWN and could contain more flaky registers like 112. sr_sel's ALIASES_KNOWN_SR
    classification is pattern-equality only for a SINGLE dispatch shape (grid=64,tg=64); a different
    shape could distinguish some of the 106 "alias 0x9c" values as genuinely different unpopulated
    reads that merely happen to read 0 in this configuration.
Driver/compiler consequence:
    A compiler backend can safely treat get_sr as total (no illegal encoding to guard against) for
    sr_sel, but must never synthesize a bare sr_sel<0x80 expecting a real special-register read.
    Register allocation for get_sr destinations (and anything sharing the GPR file) must stay
    strictly within 0-95; the addendum's implied assumption of a 96-register file is now
    HW-VALIDATED, not merely documented from an earlier chapter.
```

### GLIO-A03

```text
Status: [ ] Open  [ ] Partial  [x] Closed  [ ] Not applicable
Answer, where Yes/No: [x] Yes  [ ] No  [ ] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [x] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0092-m4-sysval-abi/raw/m4-20260828b-run0{1,2}/04_results.jsonl
    (backend=drawparam, 9/9 cases, byte-identical both runs), harness/agxvdraw.m,
    kernels/vdraw_probe.metal, casematrix.py (drawparam_expected, independent host oracle).
Exact observed semantics or field mapping:
    vertex_id = index_buffer[slot] + baseVertex (mod 2**32); instance_id = instance_ordinal +
    baseInstance (mod 2**32); base_vertex == baseVertex exactly; base_instance == baseInstance
    exactly. All four hold in every one of 9 independently distinguishable cases (nonzero,
    negative, UINT32_MAX/INT32_MAX boundary, instance-count wraparound).
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    baseVertex: full int32/uint32-reinterpreted range (host API is signed NSInteger, hardware value
    reads back as the unsigned bit pattern). baseInstance: full uint32 range including UINT32_MAX.
Maximum-valid and first-invalid tests:
    baseVertex tested to INT32_MAX (exact) and -1/-5 (exact unsigned wraparound). baseInstance
    tested to UINT32_MAX (exact) including instance-ordinal wraparound past it. No first-invalid
    value found in the tested range.
Failure/overflow behavior: [ ] reject  [ ] zero/discard  [x] alias/wrap  [ ] fault/device loss
    Standard unsigned 32-bit wraparound, not an error condition.
Correct behavior when the compiler/driver needs more:
    None needed -- native, exact, full-range. A zero-base NIR variant (load_vertex_id_zero_base)
    can be synthesized as vertex_id - base_vertex using these two independently-validated values.
Lifetime, destruction, and reuse semantics: per-draw values; not applicable beyond the draw.
Counterexamples and untested cases:
    Draw-ID / multidraw was NOT tested -- Metal exposes no multidraw primitive with a per-draw
    index visible to a vertex function (see Sec 3); reported UNKNOWN/PUBLIC-sourced, not inferred.
    Non-indexed (drawPrimitives) base_vertex/base_instance semantics were not separately re-tested
    here (EXP-0031 already covers the non-indexed zero-base case; combining non-indexed with a
    nonzero base is a candidate follow-up, low priority since Metal's non-indexed vertexStart
    already plays the role baseVertex plays for indexed draws).
Driver/compiler consequence:
    docs/isa/README.md's SR 0x88/0x8a = base_vertex/base_instance mapping upgrades from
    (inferred) to HW-VALIDATED. A Mesa backend can rely on get_sr 0x88/0x8a for NIR
    load_base_vertex/load_base_instance without further validation.
```

### GLIO-A05

```text
Status: [ ] Open  [x] Partial  [ ] Closed  [ ] Not applicable
Answer, where Yes/No: [x] Yes  [ ] No  [ ] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [ ] HW splice
          [x] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [ ] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: experiments/EXP-0092-m4-sysval-abi/raw/m4-20260828b-run0{1,2}/04_results.jsonl
    (backend=numworkgroups, 12/12 cases, byte-identical both runs), harness/agxcdispatch.m,
    kernels/numwg_probe.metal, casematrix.py (NUMWG_CASES, independent host oracle); cites and
    re-confirms docs/isa/README.md's RT-7 finding (get_sr 0xa8/a9/aa + device_load + divide) via
    this experiment's own srsweep 0xa8 re-test (Sec 2.1) on M4 (RT-7 itself ran on A18).
Exact observed semantics or field mapping:
    threadgroups_per_grid (the load_num_workgroups lowering) reports exactly the requested
    threadgroup count for direct dispatch and exactly the raw record for indirect dispatch, for
    every tested value including asymmetric, non-power-of-two, UINT32_MAX (single axis), and a
    65535x65535 product. A bare get_sr(0xa8) (no load+divide) instead returns
    threads_per_threadgroup.x -- it is NOT the workgroup count by itself (RT-7, re-confirmed here).
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    Reporting-level range: at least uint32 per axis (UINT32_MAX tested exact, no clamp). Whether a
    huge record is actually LAUNCHABLE (vs. merely reported back correctly by a probe that only
    checks thread (0,0,0)'s view) is NOT established by this experiment -- see Counterexamples.
Maximum-valid and first-invalid tests:
    Maximum tested and exact: UINT32_MAX on a single axis (indirect); 65535x65535 product
    (indirect). No first-invalid value found -- no fault, clamp, or truncation observed at any
    tested value, direct or indirect.
Failure/overflow behavior: [ ] reject  [x] zero/discard  [ ] alias/wrap  [ ] fault/device loss
    Any zero axis => zero total threadgroups => no invocation runs (not itself observable as a
    "value" -- see Sec 4's oracle-correction paragraph). No other failure mode observed.
Correct behavior when the compiler/driver needs more:
    None needed for the numeric ABI itself within the tested range. A driver must still apply
    Metal's own documented device dispatch-size limits when deciding whether to ACCEPT a given
    huge dispatch request in the first place -- this experiment did not probe that ceiling.
Lifetime, destruction, and reuse semantics: per-dispatch; not applicable beyond the dispatch.
Counterexamples and untested cases:
    Completeness/correctness of a full 65535x65535-threadgroup LAUNCH (all threads actually
    executing correctly) was NOT verified -- only thread (0,0,0)'s reported value was read back;
    the case exercises the REPORTING path, not full-launch correctness at that scale. Variable
    local (threadgroup) size across dispatches within one pipeline, and direct-dispatch huge single
    values beyond 1024 threadgroups (the largest direct case tested), are untested follow-ups.
Driver/compiler consequence:
    A Mesa NIR->Apple9 backend can map load_num_workgroups directly onto the documented
    get_sr(0xa8/a9/aa)+device_load+divide lowering for BOTH direct and indirect dispatch (single
    ABI, no dispatch-mode-dependent special case observed) -- but must still enforce a
    driver-side sanity/advertised limit on dispatch size independent of this reporting-level result.
```

### GLIO-A06

```text
Status: [ ] Open  [ ] Partial  [x] Closed  [ ] Not applicable
Answer, where Yes/No: [x] Yes  [ ] No  [ ] Unknown
Applies to: [ ] A18 Pro/G17P  [x] M4/G16G  [ ] both tested independently
Evidence: [x] independently assembled HW execution  [x] HW splice
          [x] API create/submit/exhaustion test       [ ] Linux end-to-end UAPI test
          [ ] captured userspace/command memory      [x] encode/decode round trip
          [ ] own-MSL byte diff only                 [ ] corpus inference only
Test/artifact: the full table in Sec 5 above, sourced from every backend's raw/ evidence in this
    experiment (srsweep, dstsweep, drawparam, numworkgroups).
Exact observed semantics or field mapping: see Sec 5 table (one row per sysval namespace).
Finite namespace: scope / encoding / exact usable count or range / holes and reservations:
    see Sec 5 table (populated per-row; this item closes as the byproduct of GLIO-A02/A03/A05 as
    the addendum's own triage predicted -- it was not independently closable).
Maximum-valid and first-invalid tests: see Sec 5 table.
Failure/overflow behavior: [ ] reject  [x] zero/discard  [x] alias/wrap  [x] fault/device loss
    Mixed by namespace -- see Sec 5 table for the per-row breakdown (this item spans several
    different resources with different failure classes, not one uniform answer).
Correct behavior when the compiler/driver needs more: see Sec 5 table, "Correct need-more fallback" column.
Lifetime, destruction, and reuse semantics: all rows are per-instruction/per-draw/per-dispatch
    values with no persistent state; not applicable.
Counterexamples and untested cases: see the per-item response blocks above; the draw-ID row is the
    one genuinely UNKNOWN/untested resource in this table.
Driver/compiler consequence: see Sec 5 table.
```

---

## 7. Documentation claims upgraded / not upgraded

**Upgraded (HW-VALIDATED, was `(inferred)`):**
- `docs/isa/README.md`'s SR-number table: `base_vertex` = `0x88` and `base_instance` = `0x8a` — the
  `(inferred)` annotation should be removed; cite this experiment (§3, GLIO-A03 response block).
- `docs/isa/README.md`'s `⚠ threadgroups_per_grid (0xa8/a9/aa) is NOT a direct SR value (RT-7)` note —
  independently re-confirmed on M4 (RT-7 itself was A18); the note's claim stands and now has M4
  evidence, not only A18.

**New facts to add (not previously documented at all):**
- `get_sr`'s `sr_sel` byte7 is a structural populated/unpopulated discriminator (§2.1); the exhaustive
  0x00-0xFF sweep and its per-value classification (`analysis.json`).
- The 96-GPR physical register file's exact boundary, confirmed via a register-address round trip
  through `get_sr`+`device_store` (§2.2), including the register-112 nondeterminism finding.
- The complete `vertex_id`/`instance_id` base-inclusion and wraparound semantics with independently
  distinguishable, nonzero, negative, and boundary draw parameters (§3).
- `threadgroups_per_grid`'s direct-vs-indirect-dispatch numeric ABI equivalence and its zero-axis
  no-invocation behavior (§4).

**Explicitly NOT upgraded / still open:**
- Draw-ID (multidraw): remains `UNKNOWN` — no hardware test was possible through the public Metal API
  surface this bundle's scope allows (§3).
- The exact mechanism behind `sr_sel<0x80`'s single-slot identity materialization: `UNKNOWN` (§2.1).
- The three unexpected SR aliases (`0x95`/`0xea`→simd_lane_id pattern, `0xf8`→simd_group_id pattern) and
  the two period-4-structured values (`0x83`/`0x94`, candidate `thread_index_in_quadgroup`): flagged as
  candidates, not independently cross-validated — do not promote these as confirmed aliases/mappings
  without a dedicated follow-up probe.
- The exact shape of the register-file failure region between 96 and 127 beyond the 23 tested points
  (§2.2 Counterexamples).

---

## 8. Clean-room provenance audit

```text
Clean-room provenance: OWN-SHADER (srsweep/dstsweep: our own MSL compiled via newLibraryWithSource:,
    re-assembled with the public tools/agx-isa DB and spliced with tools/agxtest/agxtest.py) +
    OWN-SHADER + HW-PROBE (drawparam/numworkgroups: our own MSL compiled and run natively via the
    public Metal API, no splice, controlled draw/dispatch parameters, public buffer readback)
Inputs inspected: kernels/srprobe.metal, kernels/dstprobe.metal, kernels/vdraw_probe.metal,
    kernels/numwg_probe.metal (all authored here); tools/agx-isa/db.json (public schema, read-only,
    not edited); tools/shdump, tools/agxtest (read-only, not edited); harness/agxvdraw.m,
    harness/agxcdispatch.m (authored here, own new binaries, no Apple binary inspected)
Apple binary introspection: NONE
Reproduction: cd experiments/EXP-0092-m4-sysval-abi && python3 -B verify.py --selftest &&
    python3 -B verify.py --seqtest && python3 -B run.py --execute --run-id m4-20260828b-run01 &&
    python3 -B run.py --execute --run-id m4-20260828b-run02 && python3 -B analysis.py &&
    python3 -B verify.py --captured   (the last command FAILS as documented in Sec 1 -- this is
    the correct, honest outcome, not a broken reproduction)
Evidence: raw/m4-20260828b-run01/ (300/300 cases), raw/m4-20260828b-run02/ (300/300 cases),
    analysis.json, manifest.json (per-artifact sha256), CAPTURE_CONTRACT.json (frozen schema),
    QUARANTINE-run01-attempt1.md + quarantine-m4-20260828-run01/ (retained non-evidence process
    history from a harness bug, not a hardware finding)
```
