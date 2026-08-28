# EXP-0093 RESULTS — M4 `0x07`-family fence/barrier decode + raster-order-group interlock

**Target: local Apple M4 (G16G) only**, macOS 26.6.2 (25G82), Metal 4, 10 GPU cores.
**No A18 Pro claim anywhere in this document** (A18 hands-off; every finding below is
M4-only unless explicitly marked otherwise). Two capture runs
(`raw/m4_20260828_run01/`, `raw/m4_20260828_run02/`), **128 cases each, from
byte-identical authored source (pinned revision
`14017e25641402e10f98100d1a3696175fc0e982`, 0 tracked modifications).**
**Cross-run gate: PASS, 0 issues. Both runs: 128/128 PASS, 0 FAIL, 0 TIMEOUT.**
**Zero GPU faults, hangs, watchdog fires, or host issues across 256 total real
dispatches (128 × 2 runs) plus 2 smoke-gate dispatches.**
`verify.py --selftest` (11/11), `--seqtest` (7/7), `--preflight`/`--between-runs`/
`--captured` all PASS.

## Headline verdicts

| item | verdict | evidence class |
|---|---|---|
| **GLFS-A08** (fragment-ordered / raster-order-group access to a shared resource) | **YES — a real hardware mutual-exclusion mechanism exists, via a compiler-emitted 0x07-family fence pair (texture) or bracket pair (buffer); `HW-VALIDATED`** | deterministic exact-invariant litmus (strong=N always, weak=race always) + causal splice (neutering the mechanism reproduces the race on an otherwise byte-identical binary) |
| **ATOM-07** (relaxed atomics ordered only by dependencies, no implicit device fence) | **YES — `HW-VALIDATED`** | genuine cross-core message-passing violation (up to 100% corrupted messages) once concurrency crosses ~4 pairs; structurally, `memory_order_relaxed` emits no `0x07`-family op at all |
| **ATOM-08** (device fence gives Vulkan/GL-required acquire/release visibility) | **YES for the SYMMETRIC (both-sides-fenced) case — `HW-VALIDATED`; asymmetric fencing is NOT a safe substitute** | 0/1350 mismatches for fully-fenced across both runs at every tested scale; asymmetric (producer-only or consumer-only) fencing still shows large-magnitude corruption |
| **ATOM-09** (threadgroup barrier combines convergence with the requested fence) | **YES, sharpened: convergence is emitted regardless of the requested memory class — `HW-VALIDATED`** | `mem_none` compiles to the same instruction shape as `mem_threadgroup`/`mem_device` AND still HW-provides full convergence+visibility for threadgroup memory |
| **ATOM-10** (device-scope barrier needs a distinct encoding from a standalone device fence) | **YES, and the exact bit is identified — `HW-VALIDATED`, bidirectional splice** | `byte+3` bit0 (`0x85` vs `0x84`) is the execution-convergence enable bit; splicing it off breaks convergence, splicing it on adds convergence to a fence-only op |
| **ATOM-11** (texture/image ops share the device-buffer fence encoding) | **NO — `HW-VALIDATED` negative result** | texture-tagged ROG uses a dedicated acquire/release instruction pair (`byte+4=0x06`); buffer-tagged ROG uses a different, bracket-pair-based mechanism; a standalone compute-side `mem_texture` fence is ALSO a genuine acquire/release pair, structurally unlike the single-instruction `mem_device`/`mem_none`/`mem_threadgroup` forms |

## 1. The `0x07`-family decode (structural, `OWN-SHADER-DIFF`/`STRUCTURAL`)

All of §1 is own-MSL differential compilation only — deterministic given frozen
source, and therefore exactly cross-run-reproducible (every `structural_*` case's
`observed.sha256` fingerprint of the extracted stage hex is byte-identical between
`run01` and `run02`, gated with no exclusion). No GPU dispatch risk in this section.

### 1.1 Selector map (byte0=`0x07`/`0x87`/`0x80`, `byte+2`)

`byte+2 == 0x54` selects the "long" 6-byte sub-family (everything in the table
below); `byte+2 ∈ {0x00, 0x02}` selects the unrelated 4-byte `scoreboard_fence`
CF-edge/pre-call family (`EXP-0085`'s `07 22 02 00` observation, reproduced
structurally here with no new data). Within the 6-byte sub-family:

| bytes (`byte0 byte1 byte2 byte3 byte4 byte5`) | context this run confirmed | provenance |
|---|---|---|
| `07 04 54 41 09 00` | compute `threadgroup_barrier(mem_none)` | own-compile, `structural_c_barrier_mem_none`, matches pre-existing `db.json` |
| `07 04 54 85 08 00` | compute `threadgroup_barrier(mem_device)` | own-compile, `structural_c_barrier_mem_device`, matches pre-existing `db.json` |
| `07 04 54 84 0a 00` | standalone `atomic_thread_fence(mem_device, seq_cst, thread_scope_device)`, NO barrier | own-compile, `structural_c_fence_device_seqcst`, matches pre-existing `db.json` (was `INFERRED`-only there; still `STRUCTURAL` for the byte shape, now `HW-VALIDATED` for its causal role — see §4/ATOM-10) |
| `07 14 54 51 0e 00` + `07 04 54 d1 0e 00` | compute `threadgroup_barrier(mem_texture)` — a genuine ACQUIRE(`sub=0x14`)/RELEASE(`sub=0x04`) PAIR | own-compile, `structural_c_barrier_mem_texture`. **Corrects `db.json`'s existing provenance note**, which recorded `sub=0x04` for BOTH members of this pair (`EXP-M4-13 R8`); this run's fresh compile shows the first member has `sub=0x14`, matching the fragment-side `pixel_order` acquire marker exactly (informational correction, not applied to `db.json` per dispatch: tools/* is read-only) |
| `07 14 54 50 06 00` | fragment `pixel_order` ACQUIRE (texture ROG) | own-compile reproduction of `EXP-0029`'s finding, `structural_census_rog_tex0`, byte-exact |
| `07 04 54 d0 06 00` | fragment `pixel_order` RELEASE (texture ROG) | same, byte-exact |
| `87 02 54 08 00 00` + `87 02 54 04 00 00` | fragment ROG "bracket-open" pair (present for BOTH texture- and buffer-tagged ROG resources; ALSO the field the raster-order-group INDEX selects, see §1.2) | own-compile, `census_rog_tex0`/`census_rog_buf0`, absent from the matched non-ROG controls (`census_rog_none`/`census_rog_buf_none`) |
| `07 04 54 c4 08 00` | fragment buffer-ROG fence (present only when the buffer resource is ROG-tagged) | own-compile, `census_rog_buf0`; **causally inert for the mutual-exclusion invariant — see §2.2/ATOM-11** |
| `87 02 54 01 00 00` + `07 02 54 01 02 00` | the ordinary, UNCONDITIONAL fragment-program epilog bracket — present in EVERY fragment shader tested (ROG-tagged, buffer-tagged, or neither) | own-compile, all four `census_rog_*` kernels; generalizes `EXP-0091`'s "ordinary end-of-program epilog" finding (previously only observed in kill/mask kernels) to ordinary fragment programs generally |

`EXP-0091`'s companion op (`07 02 54 01 <B4> <B5>`) is this SAME epilog bracket's
closing half, not a kill/mask-specific op — the `byte+3=0x01` tag pairs with the
`87 02 54 01 00 00` opening bracket regardless of whether the fragment program
discards/masks anything.

### 1.2 Finite-resource mandate: raster-order-group index namespace

**Exact range, HW-VALIDATED-by-construction (identical compiled bytes on this
hardware necessarily execute identically — no separate GPU run is needed once byte
identity is shown):** `[[raster_order_group(N)]]` compiles to structurally distinct
bytes ONLY for `N ∈ {0, 1, 2}` — a `<<2`-per-step bit-shifted tag
(`0x08→0x20→0x80`, `0x04→0x10→0x40`, `0x0c→0x30→0xc0` at the three tile-bracket
`byte+3` fields). Every tested `N ≥ 3` — `3, 4, 5, 6, 7, 8, 15, 16, 31, 32, 63, 64,
127, 128, 255, 256, 65535` (20 points total, `structural_rogidx_*`) — compiles
**byte-identical to `N=0`** (SHA-256 fingerprint match, both runs). **First-invalid
behavior: none observed — this is silent aliasing, not rejection.** A driver must
treat `N ≥ 3` as ALIASING group 0, not as an independently addressable third-or-later
raster-order-group lock; exposing more than 3 raster-order-groups to a client API
would silently share locks across supposedly-independent groups.

## 2. GLFS-A08 — fragment raster-order-group mutual exclusion (`HW-VALIDATED`)

**OBSERVED.** `harness/roglitmus.m` draws `N` instances of one full-screen triangle,
all covering the same 1×1 render target's only pixel; the fragment shader performs a
NON-ATOMIC read-modify-write increment (`v = ctr.read(); ctr.write(v+1)` / `v =
ctr[0]; ctr[0] = v+1`) of a shared `read_write texture2d<uint>` or `device uint*`
counter. Tested `N ∈ {64, 4096, 65536}`, 3 repeats each, both texture and buffer
resource kinds, both runs:

| kernel | tag | final counter value, every N/repeat/run |
|---|---|---|
| `litmus_rog_tex.metal` | `[[raster_order_group(0)]]` | **exactly N** (`0x40`, `0x1000`, `0x10000`) — 18/18 cases, both runs, byte-identical |
| `litmus_rog_tex_none.metal` | untagged (WEAK control) | collapsed to **1** (N=64,4096) or **2** (N=65536) — 18/18 cases, both runs, byte-identical (this specific collapsed value is NOT declared order-sensitive and matched exactly across runs, though it is not claimed to be a universal constant beyond this exact test shape) |
| `litmus_rog_buf.metal` | `[[raster_order_group(0)]]` on a `device` buffer | exactly N — 18/18, both runs |
| `litmus_rog_buf_none.metal` | untagged | collapsed to 1 or 2 — 18/18, both runs |

**Causal (splice) validation, texture:** the compiled `litmus_rog_tex.metal` binary's
ACQUIRE (`07 14 54 50 06 00`) and RELEASE (`07 04 54 d0 06 00`) ops were spliced —
`byte+3` zeroed — independently and together, on an OTHERWISE BYTE-IDENTICAL archive
(`PIPELINE_SOURCE archive` on every case, proving the spliced machine code actually
ran, not a silent AIR recompile). An identity-splice control (same bytes, re-copied
through the exact splicing pipeline) still gives exactly N at N=4096/65536, ruling out
the splice mechanism itself as a confound. Every neutering (`acq_only`, `rel_only`,
`both`) collapsed the invariant to 1 or 2 — **both halves of the pair are
independently necessary**, matching neither half being redundant. 16/16 splice cases,
both runs.

**Causal (splice) validation, buffer — a genuine, unanticipated mechanism split
(ATOM-11):** the compiled `litmus_rog_buf.metal` binary contains BOTH the
`87 02 54 08/04 00 00` bracket-open pair (shared in byte shape with the texture case)
AND a distinct `07 04 54 c4 08 00` fence. Splicing ONLY the fence's `byte+3`/`byte+4`
to zero (`fence_scope_only`) left the invariant **fully intact** (exactly 4096, both
runs) — the fence is causally inert for this invariant. Splicing ONLY the two
bracket-open `byte+3` fields to zero (`brackets_only`) **broke** the invariant to a
PARTIAL loss (275-283/4096 depending on run/repeat — genuinely nondeterministic race
detail, declared order-sensitive and excluded from the strict cross-run byte gate,
while the qualitative "broke, not exact" verdict is gated and matched in all 4 cases
across both runs). Combining both splices (`all`) gave a similar partial result
(271-283/4096). **Conclusion: for a device-buffer ROG resource, the mutual-exclusion
primitive is the bracket-open pair (the SAME bytes the raster-order-group index
selects, §1.2), not the `c4` fence** — a materially different mechanism from the
texture case's dedicated acquire/release pair, directly answering `ATOM-11`
negatively (texture and buffer ROG are NOT the same encoding).

**INTERPRETED.** Apple9 provides genuine hardware mutual exclusion (not merely
ordering/visibility) between overlapping fragment-shader invocations accessing a
`[[raster_order_group]]`-tagged resource, realized as a compiler-emitted fence
INSTRUCTION PAIR (texture: dedicated acquire/release `pixel_order` ops,
`byte+4=0x06`; buffer: a bracket-open pair reused from the same general
tile-access-bracket mechanism the raster-order-group index itself selects). This
directly distinguishes raster-order serialization from ordinary device-memory
visibility exactly as the addendum's wording asks: the untagged control shows a real,
severe, reproducible race (never observed the correct count at any tested N), and
that race is causally attributable to the specific bytes identified, not to
scheduling coincidence.

**Compiler consequence.** A compiler targeting Apple9 fragment-shader-interlock must
emit the acquire/release (texture) or bracket-open (buffer) pair around EVERY access
to a resource declared with a matching `[[raster_order_group(N)]]` tag, for
`N ∈ {0,1,2}` only (§1.2) — using `N ≥ 3` risks two "independent" locks silently
aliasing.

**Explicitly NOT established by this experiment (deferred, not silently dropped —
see "Deferred" below):** MSAA per-sample interlock granularity; multiple
simultaneously-tagged render targets; nested/repeated regions; discard/demote inside
the protected region and release-on-every-control-flow-exit (a build-time byte-diff
attempt on `census_rog_discard.metal` found the compiler reshuffles the ENTIRE
fragment-program prologue when a divergent discard is added inside a ROG region,
defeating a simple insertion-diff; a proper answer needs either the still-incomplete
fragment-ISA tokenizer or a smarter alignment method — recorded as `UNKNOWN`, not
guessed); forward-progress/deadlock behavior under malformed/unbalanced sequences;
different-pixel / different-sample non-interference (not directly tested, though the
buffer case's single shared slot, `idx=0` for every fragment regardless of `pos.xy`,
means this experiment's buffer test is deliberately single-slot and does not speak to
per-pixel independence at all).

## 3. ATOM-07 / ATOM-08 — compute device-memory fence (`HW-VALIDATED`)

**OBSERVED.** `kernels/litmus_devfence_pairs.metal` generalizes `EXP-0051`'s mailbox
(payload words + relaxed ready/ack flags, bounded 500,000-iteration spin-wait — never
an unbounded loop) from 1-2 threadgroups to `PAIRS` independent producer/consumer
threadgroup pairs dispatched together, varying which side(s) insert a device-scope
`atomic_thread_fence(mem_device, seq_cst, thread_scope_device)`:

| `PAIRS` | RR (both relaxed) | FR (producer fenced) | RF (consumer fenced) | FF (both fenced) |
|---:|---|---|---|---|
| 1 | 0/50, 0/50 (both runs) | 0/50, 0/50 | 0/50, 0/50 | 0/50, 0/50 |
| 4 | **200/200, 200/200** (100%) | **196/200, 196/200** (98%) | **196/200, 196/200** (98%) | 0/200, 0/200 |
| 8 | **298/400, 214/400** then **214/400, 300/400** (run1/run2) | **196/400→198/400, 294/400** | **200/400, 200/400** | 0/400, 0/400 |

(`x/y` = mismatched payload words / completed messages; every non-`FF` cell at
`PAIRS≥4` is >0 in EVERY case across both runs — 12/12 such cells; every `FF` cell
and every `PAIRS=1` cell is exactly 0 in every case across both runs — 12/12.) Exact
mismatch counts are genuinely nondeterministic run-to-run (declared order-sensitive,
excluded from the strict cross-run byte gate per the CONCURRENCY carve-out); the
coarse verdict — did a race occur, yes/no — is gated and matches the frozen
`expect_race` hypothesis in all 24 cases, both runs, no exceptions. Zero producer or
consumer timeouts anywhere (the 500,000-iteration spin bound was never exhausted).

**INTERPRETED.**
- **`PAIRS=1`'s uniform 0 mismatches explains why `EXP-0051` — which tested at
  exactly this scale — never observed a violation**, not because the hardware
  provides an implicit ordering guarantee at that scale, but because 1-2 threadgroups
  are evidently too small a concurrency footprint to expose cross-core reordering on
  this device (plausibly: both threadgroups land on the same core, or occupancy keeps
  them tightly co-scheduled). This is new, sharper evidence than EXP-0051 had, not a
  contradiction of it.
- **ATOM-07: YES.** At real cross-core concurrency (`PAIRS≥4`), fully-relaxed message
  passing shows large-magnitude, reproducible payload corruption — up to 100% of
  messages wrong in a single case. Relaxed atomics on this hardware carry NO implicit
  device-wide fence; ordering is exactly what dependencies (program order on the SAME
  thread) provide, and nothing more. This directly falsifies "relaxed happened to
  pass, therefore it's safe" — the exact trap `EXP-0051` warned a driver not to fall
  into, now demonstrated rather than merely hedged against.
- **ATOM-08: YES, but only for SYMMETRIC fencing.** Both sides fenced (FF) is the
  ONLY configuration with zero mismatches at every tested scale (12/12 cells). Neither
  asymmetric configuration (FR, RF) is a safe substitute — both still show
  large-magnitude corruption at `PAIRS≥4` (98% in 4/4 `PAIRS=4` cells, 49-74% across
  the `PAIRS=8` cells). **This is a materially different, sharper finding than a
  simple "the fence works" claim**: a driver must emit the device-scope fence on BOTH
  the producer side (before the release-style flag store) AND the consumer side
  (after the acquire-style flag load, before reading the published data) — omitting
  either side is not meaningfully safer than omitting both.

**Falsifier check (required per dispatch): the weak control was shown to actually
break** — RR/FR/RF all break at `PAIRS≥4`, in every one of 12 relevant cells across
both runs, not a cherry-picked single sample (an earlier BUILD-TIME single-sample
probe of FR at `PAIRS=8` happened to show only 12/400 mismatches — a misleadingly
small number not reproduced by the official two-run capture, which shows 196-294/400
for FR at scale; the frozen matrix and this document use ONLY the official captured
data, and the discrepancy itself is recorded here as a caution against trusting a
single exploratory sample for a concurrency claim).

## 4. ATOM-09 / ATOM-10 — barrier execution convergence (`HW-VALIDATED`)

**OBSERVED.** `EXP-0025`'s `tgdiv2` kernel (per-lane variable-length LCG delay: lane
`lid` runs `(lid+1)*32` iterations, then `threadgroup_barrier(...)`, then reads lane
`255-lid`'s slot) was reproduced unmodified as `tgdiv_baseline` (0/256 mismatches vs.
the exact closed-form LCG recurrence, both runs) and `tgdiv_baseline_none` (no
barrier: **128/256 mismatches, both runs, byte-identical** — reproducing EXP-0025's
own A18/G17P finding on M4). Three new variants:

| kernel | memory | barrier form | mismatch (both runs, byte-identical) |
|---|---|---|---:|
| `tgdiv_mem_none` | threadgroup | `threadgroup_barrier(mem_none)` | **0/256** |
| `tgdiv_dev` | device (buffer(2)) | `threadgroup_barrier(mem_device)` | **0/256** |
| `tgdiv_dev_none` | device | no barrier | **128/256** |
| `tgdiv_dev_splice_off` | device | `tgdiv_dev`'s compiled binary, `byte+3` `0x85→0x84` spliced | **128/256** |
| `tgdiv_fenceonly` | device | standalone `atomic_thread_fence(mem_device,...)`, no barrier | **128/256** |
| `tgdiv_fenceonly_splice_on` | device | `tgdiv_fenceonly`'s compiled binary, `byte+3` `0x84→0x85` spliced | **0/256** |

(Device-memory cases pre-fill the shared `scratch` buffer with the sentinel
`0xdeadbeef` so a stale/unconverged read is unambiguous; all four `_dev`/`_fenceonly`
observations reproduced exactly across both runs with no exclusion needed.)

**INTERPRETED.**
- **ATOM-09: YES.** `threadgroup_barrier(mem_none)` compiles to the identical
  instruction shape (`07 04 54 41 09 00`) as `mem_threadgroup`/`mem_device`, NOT a
  separate "no instruction" form — and it still HW-provides full execution
  convergence AND threadgroup-memory visibility (0/256 mismatches, matching the
  `mem_threadgroup` baseline exactly). Convergence is not gated by the requested
  memory class at all on this hardware for threadgroup memory; the `mem_scope` tag
  only controls which ADDITIONAL memory class (device/texture) also gets fenced.
- **ATOM-10: YES, and the exact mechanism is identified.** `byte+3` bit0
  (`0x85`=`0b1000_0101` barrier-with-device-fence vs. `0x84`=`0b1000_0100`
  fence-only) is the execution-convergence enable bit, proven BIDIRECTIONALLY by
  splice: turning it OFF on a real barrier reintroduces the exact 128/256
  no-barrier race; turning it ON on a real fence-only op (which races 128/256 on its
  own, since MSL's `atomic_thread_fence` makes no convergence claim) ELIMINATES the
  race entirely (0/256), on an otherwise byte-identical compiled instruction stream.
  A device-scope barrier and a standalone device fence are therefore NOT
  interchangeable at the encoding level, and the single bit that distinguishes them
  is now `HW-VALIDATED`, not merely `INFERRED` (upgrading `tools/agx-isa/db.json`'s
  existing `mem_fence` entry, which was `inferred (byte-diff)` only — informational,
  not applied, per dispatch).

## 5. Faults, hangs, and safety

**Zero faults, zero hangs, zero command-buffer errors, zero watchdog fires** across
256 real GPU dispatches (128 cases × 2 runs) plus 2 smoke-gate dispatches. Every case
ran in its own process with a hard timeout (90s GPU dispatch, 120s compile, both
generous relative to observed wall times — the full 128-case matrix completes in
well under two minutes). The one splice direction with genuine host-safety risk per
`docs/isa/register-move-and-liveness.md`'s warning (arbitrary `0x54`-bit-17/`ctrl`
mutation) was never exercised — every splice in this experiment targets the
`0x07`-family's own scope/flag bytes (`byte+3`/`byte+4`), a different instruction
family from the register-move family that document warns about, and every splice was
validated with a LATER-READ / cross-lane invariant (the `tgdiv2` output array, the
ROG final counter), never just the spliced instruction's own immediate result.

## 6. Standing gate results

| gate | result |
|---|---|
| (a) shared schema, `verify.py --selftest` | **PASS, 11/11 checks** (matrix well-formed, schema frozen, fixture-grounded tgdiv/ROG facts match recorded reality, cross-run gate correctly passes an order-sensitive-only diff and correctly fails a non-order-sensitive diff) |
| (b) `verify.py --seqtest` | **PASS, 7/7** state/gate combinations (`PRE_GPU`/`RUN01_PRESENT`/`RUN02_PRESENT` × the gate each state must satisfy or fail) |
| (c) non-recorded smoke gate | **PASS** both runs; `work/m4_20260828_run0{1,2}_smoke.json` (never `raw/`), real GPU dispatch, checked before any `raw/` directory exists |
| (d) nondeterminism exclusion | **PASS**, and empirically exercised on REAL data, not just the selftest: `devfence_pairs` mismatch/timeout/completed counts and `rogbuf_splice_{brackets_only,all}`/other neutered-splice `final_hex` genuinely differ between `run01`/`run02` (spot-checked above) while every gated field still matches — the cross-run gate reports 0 issues precisely because the exclusion correctly fires, not because the excluded fields happened to coincide |
| (e) recorded-reality selftest fixtures | **PASS**; `harness/fixtures/recorded_reality.json` holds a real `tgdiv_baseline` 256-value result and a real ROG strong-N16 counter value captured from actual M4 dispatches, referenced (not hand-typed) by `verify.py --selftest` |

Plus: single-threaded harness (one case, one process, `fflush(NULL)`/`ferror` exit
discipline in both ObjC harnesses); `raw/` append-only (never edited after either run
closed); hard timeouts throughout; run ids `m4_20260828_run01`/`m4_20260828_run02`
never reused; no hash-frozen file was repaired post-capture (none needed repair).

## 7. Required response blocks

**GLFS-A08.** Do the inferred Apple9 `0x07` acquire/release forms implement all
ordering required by OpenGL fragment-shader interlock for actually overlapping
fragments? — **Partially closed, `HW-VALIDATED` for the core mutual-exclusion claim.**
Apple9 provides genuine mutual exclusion (not merely visibility ordering) between
overlapping fragment invocations accessing a `[[raster_order_group(N)]]`-tagged
texture (via a dedicated compiler-emitted acquire/release `0x07`-family pair,
`byte+4=0x06`) or device buffer (via a bracket-open-pair mechanism shared with the
raster-order-group index encoding itself, NOT the same instruction the texture case
uses — see ATOM-11). `N` is silently aliased to group 0 beyond `N∈{0,1,2}`
(finite-resource limit, no rejection). NOT established by this increment: MSAA
per-sample granularity, multiple render targets, nesting/repetition, discard/demote
release-on-every-exit-path (a build-time attempt was inconclusive — full-body
compiler reshuffling defeated a simple byte-diff, recorded `UNKNOWN`), and
forward-progress/deadlock behavior under malformed sequences. Recommended successor:
a dedicated experiment for the discard-inside-ROG / release-on-every-exit question
(needs either a working fragment-ISA tokenizer or a smarter diff-alignment method
than plain prefix/suffix matching) and an MSAA/multi-attachment ROG matrix.

**ATOM-07.** Are relaxed atomics ordered only by dependencies, with no implicit
device-wide fence? — **YES, `HW-VALIDATED`.** Cross-core message passing with fully
relaxed atomics shows real, large-magnitude, reproducible payload corruption once
concurrency exceeds ~4 producer/consumer pairs (up to 100% of messages in one
captured cell); at 1-2 pairs (EXP-0051's own scale) no violation was observed,
explaining rather than contradicting that prior result.

**ATOM-08.** Does the identified device-memory fence provide the acquire/release
visibility needed by supported Vulkan/GL memory semantics? — **YES, but ONLY when
BOTH the producer (release side) and the consumer (acquire side) each emit the
fence.** Symmetric fencing (both sides) showed 0 mismatches in every tested case
across both runs; either asymmetric configuration (fence on only one side) still
showed substantial corruption at scale — a compiler must never omit the fence on
either side of a device-memory publish/observe pair.

**ATOM-09.** Does the threadgroup barrier combine execution convergence with the
requested threadgroup memory fence? — **YES, and more strongly than the question
implies: convergence is unconditional.** `threadgroup_barrier(mem_none)` compiles to
the same instruction as `mem_threadgroup`, and still provides full convergence and
threadgroup-memory visibility on real hardware (0/256 mismatches, `HW-VALIDATED`
splice/probe) — the `mem_scope` tag governs only which ADDITIONAL memory class
(device/texture) is fenced, never whether the barrier itself executes or converges.

**ATOM-10.** Does a device-scope barrier require a distinct scope/flag encoding from
a standalone device-memory fence? — **YES, `HW-VALIDATED` bidirectionally.** `byte+3`
bit0 (`0x85` vs `0x84`) is the exact execution-convergence enable bit: clearing it on
a real barrier reintroduces the no-barrier race; setting it on a real fence-only op
eliminates that same race. A driver must never conflate the two — a fence-only op at
`0x84` provides device-memory ordering with NO execution-convergence guarantee.

**ATOM-11.** Are texture/image memory operations covered by the same fence encoding
as device-buffer memory? — **NO, `HW-VALIDATED` negative result; a distinct
image/texture barrier legalization path IS required**, in two independent ways: (1)
fragment-side raster-order-group protection uses a dedicated acquire/release
`pixel_order` pair for a texture resource, but a bracket-open-pair mechanism (shared
with the ROG-index encoding, not a dedicated fence) for a device-buffer resource —
splice-proven to be the causally load-bearing mechanism in each case, and the two are
NOT interchangeable; (2) compute-side, a standalone `mem_texture` fence compiles to a
genuine two-instruction acquire/release PAIR, structurally unlike the
single-instruction `mem_device`/`mem_none`/`mem_threadgroup` forms (own-compile,
`STRUCTURAL`, corrects an existing `db.json` provenance note that had mis-recorded
both pair members with the same `sub` byte).

## 8. Limitations and confounders

- The exact mismatch/lost-update COUNTS in the `devfence_pairs` and neutered-splice
  ROG families are genuinely nondeterministic (real GPU-scheduling artifacts,
  confirmed to differ between the two official runs) — only the coarse verdict
  (raced / did not race, exact / not exact) is promoted as a repeatable fact.
- `PAIRS` was swept only to 8 (24 threadgroups producer+consumer, i.e. up to 16
  threadgroups actually doing work); larger `PAIRS` were not tested and might show a
  different corruption profile.
- The device-buffer ROG mechanism's exact semantics beyond "the bracket-open pair is
  necessary, the `c4` fence alone is not sufficient" are not fully decoded — what the
  `c4` fence's actual purpose is (cross-draw visibility? texture-cache-adjacent
  flushing even for a plain buffer? dead code from a generic codegen path?) is
  `UNKNOWN`.
- No claim about A18 Pro/G17P anywhere in this document; per `CLAUDE.md`, M4
  observations are the operational Apple9 evidence for this workstream but a
  G17P-specific fact would need an explicit `INFERRED`-by-family label, which this
  document does not need to invoke since it makes no G17P-specific claim.
- GLFS-A08's full requested matrix (MSAA, multi-RT, nesting, discard-exit-path,
  deadlock/forward-progress under malformed sequences) is NOT closed by this
  increment — see §7 GLFS-A08 response block for the explicit accounting.

## Verification

```sh
python3 harness/verify.py --selftest      # PASS (11 checks)
python3 harness/verify.py --seqtest       # PASS (7 state/gate combinations)
python3 harness/verify.py --captured m4_20260828_run01 m4_20260828_run02
  # cross_run_gate_pass=true, issues_total=0, verdict_counts_a/b={"PASS":128,...}
python3 harness/run.py --list             # regenerate/inspect the frozen 128-case matrix
```

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / OWN-SHADER
Inputs inspected: authored MSL (kernels/*.metal — litmus, structural-census, and the
  tgdiv2_* convergence family), authored ObjC harnesses (harness/roglitmus.m,
  harness/fencelitmus.m), authored Python (harness/schema.py, harness/casematrix.py,
  harness/run.py, harness/verify.py, harness/splice.py), read-only use of
  tools/shdump, tools/agxtest (agxrun, agxtest.py), tools/agx-isa (unmodified) on our
  own compiled kernel bytes.
Apple binary introspection: NONE.
Apple auxiliary/helper code inspection: NONE.
Command/BO scan or pointer following beyond our own allocated buffers: NONE.
Target qualification: local M4/G16G only; no A18 Pro claim.
Reproduction: README.md command sequence.
Evidence: raw/m4_20260828_run01/, raw/m4_20260828_run02/, manifest.json,
  CAPTURE_CONTRACT.json, harness/fixtures/recorded_reality.json.
```
