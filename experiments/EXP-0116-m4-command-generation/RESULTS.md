# EXP-0116 results: hand-constructed CDM link generation and hardware-
# consumer proof (M4)

## Verdict

**Task 1 (hand-built link followed by hardware): YES, HW-VALIDATED.**
**Task 2 (systematic link-target boundary map): DONE, 17 cases, reproduced
byte-identical across two independently gated runs.**
**Task 3 (code block outside the archive path): PRECISE NEGATIVE.** A
verbatim-copied code/uniform-window-pointer field is not portable across
records; the field's true encoding was not derived. P0.5/P0.7 remain
**OPEN**: this experiment answers exactly the "was a link record ever
independently constructed and hardware-executed" and "was a code block ever
constructed outside the archive path" gaps EXP-0110 named, but each answer
adds a new, narrower open question (see "What P0.5/P0.7 still need" below);
neither row closes here.

All results are M4/G16G only (macOS 26.6.2, Metal 4). No A18 Pro/G17P run
exists (hands-off per `CLAUDE.md`); per repo convention this is the
operational Apple9 evidence via the established A18=M4 byte-identity
finding, not a direct G17P observation.

## Method (summary; full detail in `PRE_REGISTRATION.md`)

Every command-stream byte read is Apple-generated DATA captured by the
unmodified, read-only `tools/iotrace/iotrace.c` interposer from this
process's own registered GPU buffer objects (DATA-TRACE). The new technique
is that this experiment also *writes* a value it computes into that same
CPU-mapped memory, strictly before the owning command buffer is committed --
i.e. before any hardware consumes it (HW-PROBE: "write a known pattern into
hardware-visible state, observe what the hardware does with it," per
`CLAUDE.md`). Calibration proved the BODUMP `cpu=` field iotrace reports for
a BO is literally `MTLBuffer.contents` for that BO -- an ordinary, directly
writable pointer in this process's own address space (see `PROGRESS.md`).

The primary mechanism (`same_cb`, used for the whole boundary matrix): ONE
command buffer, one compute encoder, authored to roll over into the exact
three-segment CDM shape EXP-0110 validated occurs naturally at 1500 authored
dispatches (732/732/36 records): `seg0` (writes `buf_A`), `seg1` (writes
`buf_MID`), `seg2` (writes `buf_A` again). `seg0`'s own natural tail link is
overwritten in place, before commit, with a value this program computes per
test case. Because source and every candidate target live inside the SAME
not-yet-committed command buffer, GPU residency for the target is never
independently in question. The distinguishing observable is always
**content, never mere completion status**: `buf_MID` is stomped to a known
sentinel before encoding and only `seg1`'s own 732 real dispatches can
change it; a sentinel surviving to read-back is proof `seg1` never ran.

## 1. Did the hardware follow a hand-built link? YES.

### Observed

`skip_seg1`: `seg0`'s tail link, computed fresh each run from that run's own
just-discovered `seg2` address (never hand-copied from a prior run), redirect
target = `seg2`'s own GPU VA, tag `0x20` (the established CDM link tag).
Reproduced byte-identical (gated) across `m4_20260828_run05`/`run06`:

| field | value |
|---|---|
| `wrote` | `true` |
| `final_status` | `4` (`MTLCommandBufferStatusCompleted`) |
| `final_error_category` | `None` |
| `buf_MID` readback | `0x5eed1000` == sentinel (unchanged) |
| `buf_A` readback | `0xc0000023` == `seg2`'s own last authored tag |

### Interpreted

`seg1`'s 732 real dispatches never executed (their only possible output,
`buf_MID`, is unchanged from the pre-encode sentinel), while `seg2`'s 36
real, entirely unmodified records executed correctly to completion (`buf_A`
shows exactly `0xc0000000 | 35`, seg2's own last authored tag, computed in
advance from our own fixed dispatch order, never read off a capture). This
is only possible if the hardware fetched the NEXT command-stream segment
from the GPU VA our own process computed and wrote, not from Apple's
originally-encoded value (which pointed at `seg1`). **HW-VALIDATED**: an
independently generated link value, never present in any captured Apple
command stream, was followed by real silicon with the predicted, observable
side effect. This directly answers EXP-0110's own "shortest route to
HW-VALIDATED" note and its DECODED-vs-GENERATABLE table's `Not attempted`
verdict for the CDM segment link.

Both `m4_20260828_run05` and `run06`'s gated `02_results.jsonl` records for
this case are byte-identical (`verify.py --captured`, PASS); the underlying
GPU VAs used (visible only in the non-gated `02_results_addrs.jsonl`
siblings) differ between the two runs as expected, confirming the result is
about *content*, not a hand-copied address.

## 2. Link-target boundary map (task 2)

All 17 `same_cb`/`cross_cb` cases below were captured twice
(`m4_20260828_run05`/`run06`), byte-identical (gated) between runs
(`verify.py --captured`, PASS, after two schema corrections -- see
"Nondeterminism discovered by the cross-run gate itself" below). Two
earlier pairs (`run01`/`run02`, `run03`/`run04`) are retained as valid raw
evidence for those discoveries; `run05`/`run06` is the pair the table below
reports (reproduced via `analysis/report.py raw/m4_20260828_run05`).

| case | target (relative to a natural segment VA) | tag | result | `err_cat` |
|---|---|---|---|---|
| `baseline_check` | (unmodified) | -- | natural completion, `seg1`+`seg2` both run | -- |
| `skip_seg1` | `seg2_va` | `0x20` | **completes; seg1 skipped, seg2 reached** | -- |
| `mid_segment_offset` | `seg2_va + 2*0x2c` | `0x20` | **completes; seg1 skipped, seg2 reached** | -- |
| `misaligned_byte1` | `seg2_va + 1` | `0x20` | **completes; seg1 skipped, seg2 reached** | -- |
| `misaligned_word2` | `seg2_va + 2` | `0x20` | **completes; seg1 skipped, seg2 reached** | -- |
| `misaligned_word4` | `seg2_va + 4` | `0x20` | FAULT | `PageFault` |
| `misaligned_word8` | `seg2_va + 8` | `0x20` | FAULT | `PageFault` |
| `at_capacity_boundary` | `seg1_va + 732*0x2c` (seg1's own tail) | `0x20` | **completes** (see interpretation) | -- |
| `one_past_capacity` | `seg1_va + 733*0x2c` (zero padding) | `0x20` | FAULT | `PageFault` |
| `tag_zero` | `seg2_va` (valid target) | `0x00` | FAULT | `PageFault` |
| `tag_vdm` | `seg2_va` (valid target) | `0x80` | FAULT | `PageFault` |
| `out_of_range_beyond_bo` | `seg1_va + size(seg1) + 0x1000` | `0x20` | FAULT | `PageFault` |
| `out_of_range_null` | `0` | `0x20` | FAULT | `PageFault` |
| `out_of_range_bit40` | `seg2_va + 2^40` | `0x20` | FAULT | `PageFault` |
| `out_of_range_bit44` | `seg2_va + 2^44` | `0x20` | **completes** (aliases back) | -- |
| `out_of_range_far` | `seg2_va + 2^46` (masked to 24-bit hi field) | `0x20` | **completes** (aliases back) | -- |
| `encoding_max` | `0x00ffffffffffffff` (field's own ceiling) | `0xff` | **HANG**, not a fault | `GPU_RECOVERY_EVENT` |
| `cross_cb_uncommitted` | independent, never-committed chain's leaf | `0x20` | FAULT | `PageFault` |

### Interpreted, by dimension (finite-resource-mandate table)

| Namespace/resource | Scope | Encoding | Exact usable range/count | Holes/reserved | First invalid value | Observed failure | Correct "need more" fallback | Evidence |
|---|---|---|---:|---|---:|---|---|---|
| CDM link tag byte | per-link (8-byte field, top byte) | `hi32>>24` | Only `0x20` (CDM) observed to work for a CDM continuation | `0x00`, `0x80` (VDM's own tag) both tested and REJECTED | any value != `0x20` in this context | clean, contained `PageFault`, whole command buffer's effect not guaranteed visible (see below) | driver must always emit `0x20` for a CDM->CDM link; never assume the tag is decorative | `raw/m4_20260828_run05,run06/02_results.jsonl` (`tag_zero`,`tag_vdm`) |
| CDM link target address, small misalignment | per-link, byte granularity near a valid segment head | bits [1:0] of the 56-bit target | offsets `+0`,`+1`,`+2` from a valid head succeed; `+4`,`+8` fault | not exhaustively swept beyond `+1,+2,+4,+8` | `+4` (first tested failing offset) | clean `PageFault` | driver should only ever emit exactly `0x2c`-record-aligned targets; do not rely on any masking of low bits | same |
| CDM link target address, record-granular offset within a segment | per-link | full field | at least `+2*0x2c` records into a still-in-range segment succeeds (records skipped, not executed) | not swept beyond one interior offset | not established | -- | a link can start execution mid-segment, not only at a segment's own head | `mid_segment_offset` |
| CDM link target address, high-order bits beyond the real translated width | per-link | bits above the real GPU VA width | `2^44`/`2^46` offsets alias back to the base address (silently WRONG target reached, not a fault); `2^40` offset faults (genuinely out of range, not aliased) | exact alias boundary not pinned down closer than "somewhere in `(2^40, 2^44]`" | -- | `2^40`: `PageFault`. `2^44`/`2^46`: SILENT ALIAS to a different, still-valid segment -- the single most dangerous failure mode found in this experiment (a wrong-but-legal-looking pointer executes without any error) | driver must never construct or tolerate a target with stray high bits set past the real translated width; a masking/aliasing bug in address arithmetic will not surface as a fault | `out_of_range_bit40`,`out_of_range_bit44`,`out_of_range_far` |
| CDM link encoding ceiling | the field's own representable maximum | `tag=0xff`, 56-bit target all-ones | representable, but distinctly WORSE than an ordinary invalid target | -- | `0x00ffffffffffffff` | **GPU HANG** (`kIOGPUCommandBufferCallbackErrorHang`/`InnocentVictim`), not a clean page fault -- a qualitatively different, more severe failure class, though still CONTAINED (no host wedge; GPU responsive again immediately after, confirmed by a follow-on sanity dispatch) | driver must reject/never construct this encoding at all; do not assume all invalid targets fail the same (safe) way | `encoding_max` |
| CDM segment residency (which memory a link may reach) | per-command-buffer submission | -- | a link may reach only memory the SAME command buffer's own encoding referenced/will make resident; an independent, uncommitted command buffer's own valid, correctly-shaped segment is NOT a legal target | -- | -- | `PageFault`, even though the target bytes were byte-correct, GPU-resident-looking, and previously proven followable in the `same_cb` design | a relocatable-command-stream driver must keep every link target within the residency set the SAME submission establishes; cross-submission jumps are not supported by this mechanism (at least not via an uncommitted buffer) | `cross_cb_uncommitted` |
| Faulted-command-buffer memory visibility | whole command buffer | -- | NOT deterministic: the SAME case, same target, same tag, faulted BOTH times but with a DIFFERENT amount of the command buffer's earlier, perfectly legitimate work visible in memory afterward (see next section) | -- | -- | race, not a hole in the field itself | a driver/debugger must never assume "faulted" implies "no earlier work in this command buffer was performed"; partial, order-dependent completion is possible | discovered via the cross-run gate, see below |

### `at_capacity_boundary`'s surprising completion

Pointing the redirect exactly at `seg1`'s OWN tail position
(`seg1_va + 732*0x2c`) -- i.e. at 8 bytes that are themselves a valid,
Apple-authored CDM link (tag `0x20`, target = `seg2_va`) followed by zero
padding -- completes successfully, with `seg2` reached and `seg1`'s own 732
records never executing. The leading interpretation: the hardware's
record-stream walker does not track "record index N of a fixed-capacity
segment" as separate bookkeeping from "is the word at the current position
a link/terminator" -- it just re-evaluates the current 8-byte window at
every stride, so landing exactly on ANOTHER valid link (even one we did not
write, and even at what would ordinarily be "one past the last legal
record") gets that second link followed too. This is not fully excluded by
this experiment (no case here searches for the true "start of undecodable
zero-content" boundary independent of accidentally hitting a real link);
`one_past_capacity` (one record stride further, landing purely in zero
padding beyond the link) is the clean version of that test and DOES fault.

## Nondeterminism discovered by the cross-run gate itself (a first-class
## result, not a bug we hid)

The cross-run gate is not a formality here -- it caught two genuine pieces
of hardware behavior this experiment would otherwise have missed:

1. **Faulted-command-buffer readback content is racy.** The first official
   pair (`m4_20260828_run01`/`run02`, retained, both valid) showed
   `misaligned_word8` reading back PURE sentinel (`0x5eed0000`, meaning zero
   of `seg0`'s 732 legitimate dispatches were memory-visible) in `run01`,
   but `0xc0000002` (partial progress -- INTO `seg2`, past where the fault
   nominally should have stopped it) in `run02`. Every other field was
   identical. `codeswap_task3` showed the same pattern in the opposite
   direction. **Interpretation: how much of a faulted command buffer's
   earlier, entirely legitimate work is visible in memory by the time the
   fault is reported is a genuine race, not deterministic**, and a driver
   or debugger must not treat "the command buffer reported an error" as
   proof that nothing before the fault point actually ran.
2. **Hang-class recovery labels are racy.** The second pair
   (`m4_20260828_run03`/`run04`, retained, both valid) showed `encoding_max`
   -- the sole case that produces a genuine GPU hang, not a page fault --
   reporting `"Caused GPU Hang Error (...ErrorHang)"` in `run03` but
   `"Discarded (victim of GPU error/recovery) (...ErrorInnocentVictim)"` in
   `run04`, with the SAME `final_status` (5) both times. **Interpretation:**
   GPU-level hang/TDR-style recovery can label an affected in-flight command
   buffer as either the hang's own cause or an innocent victim of it,
   depending on timing outside this experiment's control.

Both findings were used to correct `schema.py` (a tooling fix; neither
`run01`/`run02` nor `run03`/`run04`'s raw files were edited, repaired, or
re-derived -- they remain immutable evidence for exactly these findings) so
the gate correctly excludes genuinely racy content while still catching any
OTHER, non-address-related discrepancy. The corrected gate then passed
clean on a THIRD pair (`m4_20260828_run05`/`run06`) with zero mismatches.
See `CAPTURE_CONTRACT.json`'s `post_capture_corrections` for the full,
disclosed chain, and `verify.py --selftest`'s `racy-on-fault`/
`racy-final_error` fixtures (both literal reproductions of these exact
discovered cases) for the proof the correction is real, not vacuous.

## 3. Code block outside the archive path (task 3) -- PRECISE NEGATIVE

### Observed

Two genuinely different compiled kernels (`kernel_x`: fixed constant
`0x11111111`; `kernel_y`: fixed constant `0x22222222`) were dispatched as
`seg2`'s own records 36/37 (never disturbing the validated 732/732/36
boundary). Both real, Metal-authored CDM records were captured verbatim (44
bytes each) and found identical in EVERY field except `+0x08` (the
"code/uniform-window pointer"): `0x00007970` (kernel_x) vs `0x00007973`
(kernel_y) -- a difference of exactly 3. A hybrid record (kernel_x's record
with ONLY that 4-byte field replaced by kernel_y's own captured value) was
written, plus a terminator, into a fresh buffer this process fully owns
(ordinary `.contents` CPU write, no live-pointer poke needed to construct
it), and `seg0`'s already-HW-validated link was redirected into it. Result,
byte-identical (gated) across `m4_20260828_run05`/`run06`:

| field | value |
|---|---|
| `final_status` | `5` (Error) |
| `final_error_category` | `PageFault` |
| `readback_X` | `0x5eed2000` == sentinel (kernel_x's own value never appeared) |
| `readback_Y` | `0x5eed3000` == sentinel (kernel_y's own value never appeared) |

### Interpreted

Neither buffer changed: the hybrid record did not execute AS kernel_x
(disproving "the swap had no effect") nor AS kernel_y (disproving "the field
alone is a portable code selector"); the whole command buffer FAULTED. The
`+0x08` field's difference between two dispatches issued back-to-back
(3) is far too small to be a raw, shifted absolute code pointer for two
DIFFERENT compiled programs (which would need to be placed some non-trivial
distance apart in the code window); it is much more consistent with a small
per-dispatch preamble/uniform-context slot index that is only valid in the
position/sequence it was originally issued in. **This experiment did not
derive that field's true encoding** -- it only tested a verbatim byte copy,
relocated -- so the precise, bounded negative is: *naive field-level code
selection swapping across two captured records, placed at a new physical
location, is not sufficient to construct an executable code reference; the
`+0x08` field's real encoding rule (relative to segment base? a monotonic
per-encoder-lifetime dispatch counter? something else?) remains UNKNOWN* and
is the concrete next step for P0.7.

## GENERATED vs COPIED, per field (the closure-relevant distinction)

| field | status | evidence |
|---|---|---|
| CDM segment link 8-byte value (tag + 56-bit split-address target) | **GENERATED**: computed fresh from this run's own just-discovered segment addresses using the documented transform (`hi=(tag<<24)|(target>>32&0xffffff)`, `lo=target&0xffffffff`); never copied from a captured pair | `skip_seg1` and every boundary-sweep case; `harness/linksplice.m`'s `encode_link()` |
| CDM link tag byte legality | **GENERATED + TESTED**: `0x20` (works), `0x00`/`0x80` (constructed and found to fault) | `tag_zero`,`tag_vdm` |
| CDM link target: valid range, capacity boundary, misalignment, out-of-range, encoding ceiling | **GENERATED + TESTED** at every case in the table above; not merely observed, each value was computed by this program and written into live memory | full case matrix |
| CDM record's own fixed fields (config word, unclassified words, grid, threadgroup) for the hybrid task-3 record | **COPIED VERBATIM** from a real captured `kernel_x` dispatch; not independently synthesized | `codeswap.m`, `record_x_hex` |
| CDM record's `+0x08` code/uniform-window pointer, task 3 | **COPIED VERBATIM** from a real captured `kernel_y` dispatch (not computed from any derived formula) -- and this copy FAILED (faulted) when relocated, which is itself the result | `codeswap.m`, `y_ptr` |
| Fresh, never-before-compiled machine code placed and executed outside any Metal pipeline-creation call | **NOT ACHIEVED** | none |

## What P0.5 still needs

- The exact alias boundary for the link-target field's real translated
  address width (bounded here only to "somewhere in `(2^40, 2^44]`" by two
  data points) -- and, more importantly, this experiment's own strongest
  safety finding: aliasing is SILENT, not a fault, making it the failure
  mode a driver is least likely to notice without deliberate testing like
  this.
- A `cross_cb`-style link that succeeds: this experiment only demonstrated
  ONE-command-buffer-at-a-time relocation; whether/how a link can legally
  reach memory established resident by an EARLIER, separately-committed
  submission (as opposed to an uncommitted one) is untested.
- General capacity/relocation beyond the 732-record constant and the
  specific VA shift already characterized in EXP-0110 (unchanged here).
- VDM link generation (this experiment tested `tag_vdm` only as a negative
  cross-tag probe on a CDM chain; a VDM-native link splice, mirroring this
  experiment's method, was not attempted).
- Barriers, calls, indirect packets, and full PPP/USC schemas (unchanged
  from EXP-0043/49/110's own remaining gaps).
- A18 Pro replication (hands-off; M4 result treated as the operational
  Apple9 evidence per `CLAUDE.md`).

## What P0.7 still needs

- The `+0x08` code/uniform-window pointer's TRUE encoding rule -- this
  experiment's task 3 negative bounds "verbatim copy across records" as
  insufficient but does not replace it with a positive construction rule.
  The concrete next step: a controlled differential test across 3+ kernels
  at KNOWN, systematically varied encode positions (not just two
  back-to-back dispatches) to determine whether the field is a monotonic
  per-encoder counter, a segment-relative byte offset, or something else.
- Independent, from-scratch machine code (this experiment only relocated
  and relabeled already-Metal-compiled bytes; no freshly assembled
  instruction sequence was ever executed via this mechanism).
- Complete writer/replacement mapping for the code window itself (the fixed
  `0x10000000000`-based region EXP-0042 found); this experiment never wrote
  into that region at all, only into buffers this process independently
  allocated.
- Resource-spec derivation and independent launch without EXP-0042's
  archive-based extraction step for the CODE bytes themselves (this
  experiment's hybrid record's `_agc.main`-adjacent bytes are still
  archive-sourced, just relocated).

## Gate results

- `verify.py --selftest`: **20/20 PASS** (schema round-trips address
  normalization for two independently discovered nondeterministic fields --
  readback-on-fault and hang/innocent-victim final_error -- both proven with
  fixtures that are literal reproductions of the real discovered cases, not
  invented shapes; no address-shaped key/value in any gated fixture;
  deliberately injected leaks are caught).
- `verify.py --seqtest`: **7/7 PASS** (PRE_GPU/RUN01_PRESENT/RUN02_PRESENT
  gate applicability).
- Smoke gate: **PASSED** before `raw/` was created, for every one of the six
  runs (`m4_20260828_run01`..`run06`).
- `verify.py --captured`:
  - `run01`/`run02` (original schema): **FAIL**, 3/19 mismatches, precisely
    diagnosed as the fault-readback race above -- retained as evidence for
    that finding, not discarded, not repaired in place.
  - `run03`/`run04` (first-corrected schema): **FAIL**, 1/19 mismatch,
    precisely diagnosed as the hang/innocent-victim race above -- likewise
    retained.
  - `run05`/`run06` (second-corrected schema): **PASS**, 19/19 cases
    byte-identical gated payload, zero mismatches
    (`analysis/cross_run_report.json`).
- All 6 runs x 19 cases = 114 fresh GPU command-buffer submissions: zero
  process-level timeouts, zero host wedges. One case (`encoding_max`)
  produced a genuine GPU hang, CONTAINED both times (system responsiveness
  confirmed immediately after via a follow-on sanity dispatch in
  calibration; the smoke gate of the immediately-following official run
  also served as a live canary and passed every time).

## Clean-room attestation

```text
Clean-room provenance: HW-PROBE / DATA-TRACE / OWN-SHADER
Inputs inspected: harness/linksplice.m and harness/codeswap.m (authored
  ObjC/C, embedded MSL source only); IOKit boundary allocation metadata and
  content for BOs structurally matching our own authored CDM signature
  (grid/threadgroup dwords we chose), chain-followed from a uniquely
  identified head; public command-buffer status/error/readback.
Apple binary introspection: NONE.
New technique this experiment adds: direct CPU-pointer writes into this
  process's own registered command-stream memory, strictly pre-commit (see
  PRE_REGISTRATION.md "Method summary" for the clean-room justification --
  this is HW-PROBE data mutation of our own process's userspace memory, not
  inspection of any Apple binary's code).
Reproduction: PRE_REGISTRATION.md's run plan; CAPTURE_CONTRACT.json pins
  every authored file's hash including the two disclosed post-capture
  schema corrections.
Evidence: raw/m4_20260828_run01..run06/, analysis/cross_run_report.json,
  analysis/summary.json, CAPTURE_CONTRACT.json.
```

Every shader dispatched or compiled was authored in this experiment's own
`harness/`. `tools/iotrace/iotrace.c` was used exactly as committed, never
edited (hash recorded per-run in `00_inputs.json`). No Apple binary,
framework, kernel, firmware, or Apple-authored shader was inspected,
disassembled, decompiled, strings-scanned, debugged, or traced.
