# EXP-0116 pre-registration: hand-constructed CDM link generation and
# hardware-consumer proof (M4)

## Question

`docs/P0-P1-CLOSURE.md` P0.5 and P0.7 both require more than decoding: an
implementer must be able to *independently construct* relocatable command/
state records and code blocks and prove hardware consumes them, not merely
tokenize captured Apple-built ones. EXP-0110's own DECODED-vs-GENERATABLE
table states plainly that neither row closes because "no link record was
hand-constructed and executed, no code block was built outside the archive
path." This experiment attempts exactly that, for the CDM (compute) segment
link field EXP-0043/0049/0110 already decoded structurally:

1. Can a link record we compute ourselves (not copied from a capture) be
   spliced into a live, not-yet-submitted command buffer's memory and be
   followed by real hardware, with an observable, unambiguous side effect
   that only a successful redirect could produce?
2. Across the target field's representable range, where is the boundary
   between "hardware follows it" and "hardware faults/hangs"? (capacity
   boundary, misalignment at each relevant granularity, out-of-range, tag
   variation, and the field's own encoding ceiling.)
3. Can a CDM *record* (header + our own captured/recombined machine
   reference) be constructed outside the archive/pipeline-creation path and
   executed?

## Method summary (established by informal calibration; see PROGRESS.md)

Every command-stream byte inspected is either literally authored by us
(dispatch dims, tags, buffer contents) or is Apple-generated DATA (not code)
captured by the unmodified, read-only `tools/iotrace/iotrace.c` interposer
from our own process's registered GPU buffer objects (DATA-TRACE, exactly the
technique EXP-0009/0011/0043/0049/0110 already used to *read* this data). The
new technique here is that this experiment also *writes* a computed 8-byte
value into that same CPU-mapped memory, strictly before the owning command
buffer is committed -- i.e. before any hardware consumes it. Calibration
proved (informally, not evidence, see PROGRESS.md) that the BODUMP `cpu=`
field iotrace reports for a BO is literally `MTLBuffer.contents` for that BO:
an ordinary pointer in this process's own address space, safe to read *and*
write like any other memory this process owns. This is HW-PROBE ("write a
known pattern into hardware-visible state, observe what the hardware does
with it") per `CLAUDE.md`'s sanctioned methods -- not introspection of any
Apple binary.

Two mechanisms, motivated by two calibration negatives (see PROGRESS.md for
full detail):

- **`same_cb`** (primary, used for the whole boundary matrix): ONE command
  buffer, one compute encoder, authored to roll over into the exact
  three-segment CDM shape EXP-0110 already validated occurs naturally at
  1500 authored dispatches (732/732/36 records): `seg0` (732 records, writes
  `buf_A`), `seg1` (732 records, writes `buf_MID`), `seg2` (36 records,
  writes `buf_A` again). `seg0`'s own natural tail link (to `seg1`) is
  overwritten in place, before commit, with a value this program computes
  per test case. Source and every candidate target live inside the SAME
  not-yet-committed command buffer, so GPU residency for the target is never
  independently in question.
- **`cross_cb`** (one documented negative only): an independent, never-
  committed second command buffer (`cbR`, its own valid 732/5-record chain)
  is encoded, and `A0`'s link is redirected into it. This reproducibly
  FAULTED (`kIOGPUCommandBufferCallbackErrorPageFault`) in calibration --
  the leading hypothesis is that residency for a command buffer's referenced
  memory is established at commit time, and an uncommitted command buffer's
  segments are simply never made resident, so a hand-built link reaching
  into them is reaching memory the GPU was never told about. A second
  calibration variant (commit-and-wait `cbR` before encoding `cbM`) was
  tried and discarded: waiting lets Metal reuse (not zero) `cbR`'s 0x8000-
  byte segment storage for `cbM`'s own later allocations, corrupting the
  very memory the test depends on -- a process finding, not a promoted fact.

The distinguishing observable in every case is **content**, never mere
completion status: `buf_A`/`buf_MID` (and, in the task-3 program,
`buf_X`/`buf_Y`) are stomped to a known sentinel pattern via ordinary CPU
writes to our own `MTLBuffer.contents` before the command buffer is built,
and each segment writes a `tag`-derived, deterministic value
(`out[i] = tag + i`) that is fully computable in advance from the encoded
dispatch order alone -- never from a captured address. A sentinel surviving
to read-back is a NEGATIVE (that segment never ran); a tag value is a
POSITIVE (that segment, and only that segment, ran).

## Falsifiable hypotheses

- **H1 (link generation, positive).** Redirecting `seg0`'s tail link to
  `seg2`'s own GPU VA (skipping `seg1`) with the established transform
  (`hi = (tag<<24) | (target>>32 & 0xffffff)`, `lo = target & 0xffffffff`,
  tag `0x20`) makes the command buffer complete with `buf_MID` still at
  sentinel (seg1 never ran) and `buf_A` showing seg2's own last tag (seg2
  ran to completion). Falsifier: `buf_MID` shows seg1's tag (natural link
  still followed, our write had no effect) or the command buffer
  faults/hangs.
- **H2 (capacity boundary).** A target exactly at a segment's own tail
  position (`seg1_va + 732*0x2c`) and one record further into trailing
  padding (`seg1_va + 733*0x2c`) will behave differently from an ordinary
  in-range target. Falsifier: identical behavior at both offsets.
- **H3 (misalignment).** Targets not aligned to the CDM record stride
  (`0x2c`) at small byte offsets (+1, +2, +4, +8) from a valid segment head
  will not uniformly succeed or uniformly fault. Falsifier: uniform
  behavior across all four offsets.
- **H4 (out-of-range / encoding ceiling).** A target far outside any
  allocated region will fault; a target whose extra high-order bits exceed
  the GPU's actual translated VA width will alias back to a valid mapping
  rather than fault, and the true encoding ceiling (tag `0xff`, target
  `0x00ffffffffffffff`) will not behave identically to an ordinary
  moderate out-of-range target. Falsifier: every out-of-range case behaves
  identically regardless of magnitude.
- **H5 (tag validation).** Changing only the link's tag byte (`0x00`,
  `0x80`) while keeping a valid CDM target address will not be silently
  accepted -- the tag is interpreted, not decorative. Falsifier: identical
  success behavior regardless of tag.
- **H6 (code block, task 3).** A hand-built CDM record combining one real
  captured kernel's record verbatim with a second real captured (different
  compiled kernel's) `+0x08` code/uniform-window-pointer field, placed in a
  buffer we fully own and reached only via our own H1-validated link splice
  (never through `MTLComputePipelineState` creation for that specific
  record), will execute AS the second kernel (falsifying: it executes as
  the first kernel, i.e. the swapped field had no effect) OR will fault
  (a bounded negative: the field is not a portable, location-independent
  absolute selector).

## Independent / controlled variables

- Independent: `--case` (the link's computed tag/target, or for task 3 the
  hybrid record's swapped field) and `--mechanism` (`same_cb`/`cross_cb`).
- Controlled/fixed across all `same_cb` cases: dispatch shape (grid
  `64,1,1`, threadgroup `32,1,1`), segment sizes (732/732/36), kernel source,
  tag encoding scheme, sentinel values, watchdog timeout, dump-wait interval.
- One case per process (per `SUBAGENT_BRIEF.md`); no case's outcome is
  allowed to depend on another case having run first in the same process.

## Expected observation per case (frozen; computed from calibration, not
## re-derived after the fact -- this table IS the falsifier)

| case | new target (relative to a natural segment VA) | tag | predicted |
|---|---|---|---|
| `baseline_check` | (no write) | -- | natural completion, `seg1` and `seg2` both run |
| `skip_seg1` | `seg2_va` | `0x20` | complete; `buf_MID` sentinel; `buf_A`=seg2 last |
| `mid_segment_offset` | `seg2_va + 2*0x2c` | `0x20` | complete; `buf_MID` sentinel; `buf_A`=seg2 last |
| `at_capacity_boundary` | `seg1_va + 732*0x2c` (seg1's own tail) | `0x20` | complete (predicted: lands on seg1's own valid link to seg2, chains through) |
| `one_past_capacity` | `seg1_va + 733*0x2c` (zero padding) | `0x20` | FAULT |
| `misaligned_word2` | `seg2_va + 2` | `0x20` | complete (predicted: low bits masked) |
| `misaligned_word4` | `seg2_va + 4` | `0x20` | FAULT |
| `misaligned_byte1` | `seg2_va + 1` | `0x20` | complete (predicted: low bits masked) |
| `misaligned_word8` | `seg2_va + 8` | `0x20` | FAULT |
| `out_of_range_beyond_bo` | `seg1_va + size(seg1) + 0x1000` | `0x20` | FAULT |
| `out_of_range_null` | `0` | `0x20` | FAULT |
| `out_of_range_bit40` | `seg2_va + 2^40` | `0x20` | FAULT |
| `out_of_range_bit44` | `seg2_va + 2^44` | `0x20` | complete (predicted: aliases back) |
| `out_of_range_far` | `seg2_va + 2^46` (masked to 24-bit hi field) | `0x20` | complete (predicted: aliases back) |
| `encoding_max` | `0x00ffffffffffffff` | `0xff` | FAULT or HANG, distinct from ordinary out-of-range |
| `tag_zero` | `seg2_va` | `0x00` | FAULT |
| `tag_vdm` | `seg2_va` | `0x80` | FAULT |
| `cross_cb_uncommitted` | independent uncommitted chain's leaf | `0x20` | FAULT (residency) |

This table states our OWN calibration-informed predictions as the
pre-registered expectation; the official runs re-derive every value fresh
from that run's own dump (never hand-copied from calibration), and
`RESULTS.md` reports the actual outcome against this table honestly,
including any case that does not match its prediction (`at_capacity_boundary`
is flagged above as a predicted-but-not-yet-fully-understood chain-through,
not a confident claim).

## Confounders

- **Deferred terminator finalization.** Calibration found `seg2`'s own tail
  word (the true end-of-stream terminator) reads as `0x00000000` in a
  PRE-COMMIT dump and only becomes the real `0x40000000` terminator in a
  POST-COMMIT dump of the identical BO -- i.e. Metal finalizes the very last
  segment's terminator at/after commit, not at `endEncoding`. This does not
  affect the splice itself (which only ever touches `seg0`'s/`seg1`'s own
  forward LINK words, both confirmed reliable pre-commit across 5+ repeated
  calibration runs) but means `natural_chain_ok` in this experiment's schema
  intentionally does NOT require `seg2`'s tail to already read as a
  terminator pre-commit.
- **Chain-head/target disambiguation by content.** `seg0` and `seg1` (and,
  in the discarded `cross_cb` committed-wait variant, `R0`) are
  byte-identical at the level this scanner reads (same authored grid/tg
  signature); a purely content-based "pick the first 732-count linked
  segment found" classifier picked the WRONG segment in one early
  calibration run (filesystem `readdir()` order, not encode order). Fixed by
  finding the unique chain HEAD (a link source that is nobody else's link
  target) and following links forward from there -- a structural, not
  guessed, disambiguation. See PROGRESS.md.
- **GPU addresses vary run to run.** Every `seg*_va`, `hybrid_va`,
  `x_ptr`/`y_ptr`, and the split-address link words themselves are excluded
  from the byte-compared gated payload (`schema.py`); only case identity,
  booleans, status codes, the tag byte, and deterministic tag-derived
  readback content cross the cross-run gate.
- **Allocator movement between runs is expected and is not contamination**;
  only the CONTENT interpretation (which segment ran, sentinel-vs-tag) is
  asserted to be gate-stable.
- **This is a hardware side channel, not a documented API.** Direct
  CPU-pointer writes into Metal's own internal command-stream storage are
  outside any public contract; a macOS/Metal update could change allocation
  timing, residency behavior, or terminator finalization timing in ways that
  invalidate specific numeric findings here (e.g. the exact `732`/`0x2c`
  constants, or which offsets alias) without changing the qualitative
  method. Findings are scoped to macOS 26.6.2 / this M4.

## Environment / target

Local Apple M4 (G16G), 10 GPU cores, macOS 26.6.2 (25G82), Metal 4. No SSH.
A18 Pro hands-off (not run). Pinned git revision at pre-registration time:
`72c2dde8afd896e384afa20050bdd040f657ca78` (dirty tree, per repo norm --
sibling experiments commit continuously; captures are validated against
authored-file hashes below, not live `HEAD`).

## Frozen authored-file hashes (sha256)

```
912db95f0a82f3185d529240fce7f56ab6d036d524edae43dd7620aad5372506  harness/linksplice.m
7ea5c0196eb97fd630bb4805b47dbea8cfff91663c0cf4c3a8bff355d9d04ca7  harness/codeswap.m
```

`schema.py`, `casematrix.py`, `run.py`, `verify.py` are written after this
file and hashed into `CAPTURE_CONTRACT.json` before the first official run.

## Raw-record schema (frozen)

Each case produces one JSON object from the C harness (`--out`), which
`run.py` splits into:

- a GATED record appended to `raw/<run-id>/02_results.jsonl` (fflush'd
  immediately): case name, mechanism, every `found_*`/`*_count` structural
  fact, `natural_chain_ok`/`setup_ok`, `wrote`, `new_link_tag` (the tag byte
  alone, not the address-bearing hi/lo words), `hang`, `final_status`,
  `final_error`, every `readback_*`/`expect_*`/`sentinel_*` value, and (task
  3 only) the full `record_x_hex`/`record_y_hex`/`hybrid_hex` byte strings
  MINUS their `+0x08` field (redacted to `????????` -- see schema.py) since
  that field is itself a location-dependent pointer that varies run to run;
- a NON-GATED sibling `raw/<run-id>/02_results_addrs.jsonl` carrying every
  `*_va`, `pre_link_hi/lo`, `new_link_hi/lo`, `x_ptr`/`y_ptr`, and the
  un-redacted record hex, which legitimately differs between runs and is
  never part of the cross-run gate.

`schema.assert_no_address_leak` (exercised by `verify.py --selftest`) proves
the gated file contains no key or value shaped like a GPU VA.

## Timeouts

- Per-case hardware watchdog: 15s (`--watchdog-sec 15`), inside the C
  harness itself (completion-handler + timed `dispatch_semaphore_wait`,
  never a bare `waitUntilCompleted`).
- Per-case process-level timeout (Python driver): 40s (covers Metal/process
  startup + the 15s hardware watchdog + dump I/O with margin).
- One case per process; a hang or fault is a recorded result, never
  silently retried or dropped.

## Run plan

`verify.py --selftest` + `--seqtest` (PRE_GPU) -> smoke gate (one
`baseline_check` case into `work/`, never `raw/`) -> `run.py --run-id
m4_<date>_run01` -> `verify.py --seqtest` (RUN01_PRESENT) -> `run.py
--run-id m4_<date>_run02` -> `verify.py --seqtest` (RUN02_PRESENT) ->
`verify.py --captured` (cross-run gate). Never reuse a run id; a defective
capture is retained and superseded by a new id, never repaired in place.
