# EXP-0131 pre-registration: M4 shader container field map + live splice-and-
# execute hardware-consumer proof, boundary/extent construction

## Question

`docs/P0-P1-CLOSURE.md` P0.7 (`DRV-SHADER-01`) requires more than decoding: a
container record must be independently CONSTRUCTED (header, entry point,
authoritative extent, resource specifiers), and closure rule 6 requires "the
relevant userspace object ... independently generated and consumed without a
captured Apple template." EXP-0042 mapped the 0x40-header-aligned graphics
code-record framing on M4 (header/constant_program/main/pad) but left
unresolved whether hardware or firmware (vs. only macOS userspace) consumes
the live per-record bytes, and reported the record immediately following an
FS record as "opaque DATA-TRACE structure ... UNKNOWN". EXP-0110 extended the
field survey (compute-side `__GPU_METADATA`) and proved two more fields are
archive/compile-time bookkeeping, not hardware-visible. EXP-0116 proved a
hand-built CDM (compute) LINK record is followed by real hardware
(HW-VALIDATED) but that a verbatim CDM code-pointer swap across two captured
records faults (a precise negative -- the field's encoding is unknown).

This experiment asks, for the GRAPHICS shader container specifically (the
0x10000000000-family code BO EXP-0042 located, distinct from EXP-0110/0116's
CDM/compute work):

1. Can the container's fields (header, constant_program, main, and the
   record immediately following it) be mapped completely enough to classify
   each as FIRMWARE-CONSUMED (hardware reads it to execute/select code) vs.
   ARCHIVE/CREATION-TIME BOOKKEEPING (macOS userspace only)?
2. Can we DIRECTLY prove hardware -- not merely a macOS cache -- executes
   from the live, POST-CREATION container, by mutating it in place (using
   our own tools/agx-isa-derived field edit, not a copied value) and
   observing the predicted output on a FRESH draw that reuses the
   already-created pipeline object?
3. What happens at documented extent/alignment boundaries: a corrupted
   record-size header, a truncated main program, a corrupted adjacent
   record?

Per the dispatch's explicit coordination instruction, this experiment does
NOT attempt to derive or construct the live FS/VS SELECTOR mechanism itself
(the field(s) that tell the draw path which code record to fetch) -- that is
`EXP-0127-m4-shader-selection`'s assigned angle ("graphics-selection side").
This experiment reuses whatever selector Metal itself already established at
pipeline creation (i.e. every case here draws with an UNCHANGED,
already-working selector) and only mutates the CODE/HEADER bytes the
selector points at or past. See PROGRESS.md Milestone 1 step 6 for the
informal calibration that confirmed this experiment's own memory of "pool+
0x08" did not hold in a simpler two-pipeline case, and the decision to defer
selector work entirely rather than guess.

## Falsifiable hypotheses

- **H1 (live container framing generalizes).** A fresh, independently
  compiled render pipeline (not EXP-0042's stage-matrix shaders) will show
  the SAME record framing EXP-0042 documented: `u32 record_size` header,
  zero-pad to header+0x40, `constant_program` (64 or 128 B), `main`, zero-pad
  to `header+record_size`. Falsifier: a differently shaped/ordered layout.
- **H2 (live-container hardware-consumer proof).** Writing our own
  tools/agx-isa-decoded-and-modified single byte (the `frag_color_pack`
  `val` field at live `main+0x06`, `0x80`->`0x40`) directly into the
  CPU-mapped live code BO, strictly before a FRESH command buffer commits
  (reusing the SAME already-created `MTLRenderPipelineState`), changes the
  rendered pixel exactly as EXP-0008 already validated at the ARCHIVE level
  (green channel `0.502`->`0.251`, i.e. `bgra` `4080ffff`->`4040ffff`).
  Falsifier: the pixel is unchanged (macOS/hardware executes from a
  different, cached copy) or the command buffer faults/hangs.
- **H3 (record_size header is not re-consulted per draw for code fetch).**
  Corrupting the record's own leading `record_size` u32 to `0x00000000` or
  `0xFFFFFFFF` (two separate cases/processes) after creation, then drawing
  again with the SAME pipeline object, does NOT change the rendered pixel
  (main is still fetched/executed as before). Falsifier: a changed pixel, a
  fault, or a hang in either direction.
- **H4 (truncation halts cleanly, does not fault).** Overwriting the main
  program starting right after its first instruction (byte offset `+0x0a`)
  with `stop` (`0e000000`) and zeroing the remainder produces a
  syntactically valid, early-terminating program that renders the render
  pass's OWN clear color (`0,0,0,0`, since `frag_tile_setup`/
  `frag_color_store` are never reached) rather than faulting.
- **H5 (the "following record" is the next record's own header, not
  independent FS metadata).** The 4 bytes at `header + record_size` decode
  as a plausible `record_size` for a DIFFERENT, independently-verifiable
  code record (structural claim, established via calibration inspection,
  not itself re-derived under the gate). A live mutation of ONLY that
  4-byte field (`corrupt_next_record_header`, set to `0xFFFFFFFF`) predicts
  NO visible effect on THIS draw's fragment output (since our own FS record
  and its selector are untouched) -- a null result here is CONSISTENT WITH
  but does not independently PROVE H5; this is disclosed as a limitation up
  front, not discovered after the fact.

## Independent / controlled variables

- Independent: `--case` (one of `casematrix.CASES`, frozen below).
- Controlled/fixed across every case: authored MSL source
  (`kernels/render_min.metal`, byte-identical to
  `experiments/EXP-0008-fragment-extraction/kernels/render_min.metal`,
  sha256 `a3996254101cc3f2d6c138bbf0e278d696409a57a7abe3f449b9dedbca907054`),
  render target shape (4x4 `bgra8Unorm`, shared storage), draw shape
  (one full-screen triangle, 3 vertices, no vertex buffer), watchdog
  (15 s per commit), dump-wait interval (1,000,000 us).
- One case per process (per `SUBAGENT_BRIEF.md`); no case's outcome depends
  on another case having run first in the same process.

## Case matrix (frozen; see `casematrix.py` for the executable copy)

| case | mutation | predicted `post_mutation_bgra` | predicted hang |
|---|---|---|---|
| `baseline_check` | none (control) | `4080ffff` | no |
| `splice_green_field` | `main+0x06`: `0x80`->`0x40` | `4040ffff` | no |
| `splice_wrong_field` | `main+0x07`: `0x50`->`0x40` (adjacent field) | not predicted (boundary probe) | no |
| `header_size_zero` | own header u32 -> `0x00000000` | `4080ffff` (unaffected) | no |
| `header_size_max` | own header u32 -> `0xFFFFFFFF` | `4080ffff` (unaffected) | no |
| `truncate_main_early` | `main+0x0a..0x35` -> `stop`+zero | `00000000` (clear color) | no |
| `corrupt_next_record_header` | next record's header u32 -> `0xFFFFFFFF` | `4080ffff` (unaffected, THIS draw) | no |

`casematrix.py`'s `PREDICTIONS` dict is this table's executable form,
imported by `run.py` (to drive the matrix) and `analysis/report.py` (to
diff predicted vs. observed) -- both therefore cannot silently drift from
what is written here.

## Confounders

- **GPU addresses vary run to run.** Every `addr_*` field (`bo_gpu_va`,
  `bo_cpu`, `main_off`, `header_off`, `write`) is excluded from the
  cross-run gated comparison (`schema.py`, proven by `verify.py --selftest`).
  Allocator movement between runs is expected and is NOT contamination; only
  CONTENT (which byte changed, what color rendered, whether it hung) is
  gate-compared.
- **`header_size_zero` reproducibly crashes the harness PROCESS (SIGBUS)
  during teardown, AFTER the evidentiary `--out` JSON is fully written and
  AFTER the GPU command buffer already completed normally.** This is
  disclosed here, before the official runs, precisely so it is not mistaken
  for an unexpected finding: `run.py` always reads the `--out` file
  regardless of the child process's exit code/signal, and separately logs
  the process outcome (`01_process.jsonl`) so the crash itself is preserved
  as evidence, never silently dropped.
- **A single trivial shader's `constant_program` region (64 B, essentially
  `stop`+filler for `render_min.metal`) is not independently exercised by
  any case here.** This experiment does not claim anything about
  `constant_program` mutation; it is read/observed only. Flagged as
  follow-up scope, not silently omitted.
- **H5 (the "following record" is the next record's own header) is a
  STRUCTURAL claim from calibration inspection, not itself a hypothesis this
  experiment's gated case matrix independently falsifies beyond a
  consistent-with-not-contradicted null result.** A dedicated follow-up
  (deliberately corrupting a byte KNOWN to be inside the next record's own
  `main`, and checking for an effect on THAT stage specifically) is named as
  future work, not attempted here (would require driving the VS to a
  visibly checkable output, e.g. via position corruption, which risks
  conflating this experiment's scope with EXP-0127's).
- **This is a hardware/OS side channel, not a documented API contract**:
  direct CPU-pointer writes into Metal's own internal code-container storage
  are outside any public guarantee. A macOS/Metal update could change
  allocation, caching, or teardown behavior in ways that invalidate specific
  findings here (the exact offsets `0x340`/`0x3c0`/`0xc0`, or the SIGBUS
  teardown behavior) without changing the qualitative method. Findings are
  scoped to macOS 26.6.2 / this M4 (G16G).
- **Selector mechanism is explicitly out of scope** (see "Question" above);
  any apparent correlation with `0x58000`-family fields noticed during
  calibration is disclosed in `PROGRESS.md` but not investigated further or
  promoted as a finding of this experiment.

## Environment / target

Local Apple M4 (G16G), 10 GPU cores, macOS 26.6.2 (25G82), Metal 4. No SSH,
no A18 Pro (hands-off per `CLAUDE.md`); M4 result treated as the operational
Apple9 evidence per repo convention, not a direct G17P observation.

Pinned git revision at pre-registration time: `cf544b4dd1fb37047c7cfee6a70a0d1a87628666`
(dirty tree -- other experiments' untracked/uncommitted files are visible in
`git status`; per `SUBAGENT_BRIEF.md` this is expected and captures are
validated against the AUTHORED-FILE hashes below, not against live `HEAD`).

## Frozen authored-file hashes (sha256)

```
8bb162c4b1d66ce77fa5f3c1938c0eed5d402c756331d9f764c22b1927a2dd7e  harness/codesplice.m
744775abd22135309ff0f49e7ef5538c4e395d8f33b1223288f4698adb4c51bb  schema.py
143553dc0447f65d2558004979bf58db9484bc0bb5aa00e473b88b78ddf0a919  casematrix.py
69a4becfbc4e2ddf19ff90b1deb2083226f241341a012924c5bc2433a6b7e54b  run.py
a7a24d62d02893ac07b3359cf92cf98efc5f8a025da3947a8e8f8402651dc4a9  verify.py
a3996254101cc3f2d6c138bbf0e278d696409a57a7abe3f449b9dedbca907054  kernels/render_min.metal
```

`CAPTURE_CONTRACT.json` mirrors this table in machine-readable form and adds
the read-only `tools/` inputs' hashes as observed at build time (they are
NOT owned by this experiment and are never modified; their hashes are
recorded per-run in `00_inputs.json` for auditability, matching
`SUBAGENT_BRIEF.md`'s convention for read-only tool inputs).

## Raw-record schema (frozen)

Each case's `harness/codesplice.m --out` JSON is split by `schema.py` into:

- a GATED record appended to `raw/<run-id>/02_results.jsonl` (fflush'd
  immediately): case identity, booleans, status codes, the small `record_size`
  header VALUES (content, not addresses), and every byte-string
  (`write_before`/`write_after_intended`/`post_main_hex`/`baseline_bgra`/
  `post_mutation_bgra`) -- see `schema.GATED_KEYS`.
- a NON-GATED sibling `raw/<run-id>/02_results_addrs.jsonl` carrying every
  `addr_*` field, which legitimately differs between runs.
- `raw/<run-id>/01_process.jsonl`: one record per case with the CHILD
  PROCESS's own outcome (exit code, signal, timed-out flag, elapsed time,
  stdout/stderr log paths) -- preserved regardless of whether `--out` JSON
  was written, so a process-level fault (like the disclosed
  `header_size_zero` SIGBUS) is never silently lost.
- `raw/<run-id>/00_inputs.json`: authored-file hashes, case list, timeouts,
  run start time.

`schema.assert_no_address_leak` (exercised by `verify.py --selftest`) proves
the gated file contains no key or value shaped like this experiment's known
GPU-VA/CPU-pointer families.

## Timeouts

- Per-case hardware watchdog: 15 s (`--watchdog-sec 15`), inside the ObjC
  harness itself (completion-handler + timed `dispatch_semaphore_wait`,
  never a bare `waitUntilCompleted`) -- applied to BOTH the baseline draw
  and the post-mutation draw.
- Per-case process-level timeout: 45 s (`run.py`'s `CASE_TIMEOUT_SEC`),
  covering Metal/process startup + two 15 s hardware watchdogs + dump I/O
  with margin.
- One case per process; a hang, fault, or process crash is a recorded
  result, never silently retried or dropped.

## Run plan

`verify.py --selftest` + `--seqtest` (PRE_GPU) -> NON-RECORDED smoke gate
(`run.py --run-id <id> --smoke-only`, writes into `work/smoke_<id>/`, never
`raw/`) -> official run 1 (`run.py --run-id m4_20260828_run01`) ->
`verify.py --seqtest` (RUN01_PRESENT) -> official run 2
(`run.py --run-id m4_20260828_run02`) -> `verify.py --seqtest`
(RUN02_PRESENT) -> `verify.py --captured m4_20260828_run01 m4_20260828_run02`
-> `analysis/report.py` -> `RESULTS.md`.
