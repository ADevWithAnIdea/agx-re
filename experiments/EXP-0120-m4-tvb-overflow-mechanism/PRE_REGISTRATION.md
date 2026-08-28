# PRE_REGISTRATION — EXP-0120: M4 tiler parameter-buffer (TVB) overflow mechanism

Frozen: 2026-08-28T07:37:58Z. Pinned repo revision: `87d02c34f56357734f448695cf62d37ab555fcb0`
(working tree has unrelated untracked files from sibling in-flight experiments; this
experiment gates on the **authored blob hashes** below, not on live `HEAD` — per
`CODEX.md` target-discipline and `SUBAGENT_BRIEF.md`'s "pin the revision" rule).

## 0. Question and why it matters

`docs/pipeline/README.md` currently states: *"The overflow -> partial-render trigger is
firmware-managed — no userspace knob (kernel/firmware concern)."* EXP-0108 (`RESULTS.md`
section 2.5) tested this at up to ~600,000 triangles / 4M target pixels using *distributed*,
near-full-screen geometry and found no new userspace-visible record — but explicitly could
not establish whether a partial render **actually occurred** in that matrix (command
retirement + correct readback do not, by themselves, distinguish a single-pass render from a
firmware-transparent multi-pass one). EXP-0118 built a project-authored workload
(`experiments/EXP-0118-a18-pro-partial-render-workload/`) specifically designed to force
overflow via **primitives concentrated in ~1 tile** (not distributed), with an oracle
(additive-blend accumulation into 8 R32F attachments) that is sensitive to *broken* reload
but — as the dispatching brief itself notes — still does not by itself prove a reload
happened if nothing overflowed.

This experiment's job is to supply the missing **independent, non-oracle indicator** of
whether the overflow/partial-render mechanism actually engages, to characterize **which**
mechanism (BO growth vs. multi-kick partial render vs. transparent segment-chaining vs.
something else), to determine **who supplies what** at the boundary (userspace vs.
firmware/kernel), and to bound the **finite-resource envelope** (capacity, growth
granularity, failure mode at exhaustion). This is the evidentiary basis for whether
`docs/P0-P1-CLOSURE.md` row P0.4 / `APPLE9_RE_IMPLEMENTATION_GAPS.md` `DRV-UAPI-04` must
budget for a userspace-synthesized partial-BG/partial-EOT program, or whether — as EXP-0108
already suspected — the tested surface requires none.

## 1. Hypotheses (falsifiable)

- **H1 (engagement/threshold):** as triangle count concentrated in ~1 tile increases (fixed
  128x128 target, 8 R32F attachments, additive blend — the exact EXP-0118 `accumulate`
  configuration), an **independent** (non-oracle) signal changes in a way consistent with a
  qualitatively different execution regime (partial render engaging). Two independent
  candidate signals are pre-registered:
  - **H1-timing:** wall-clock GPU-bound submission cost per triangle (slope-corrected to
    remove fixed per-process/per-encode overhead — see Method) shows a **super-linear
    knee** (a change in marginal per-triangle cost) at some triangle count, distinct from a
    single linear (constant marginal-cost) regime.
  - **H1-inventory:** the userspace-visible sel-9-registered BO set (see H2 below) changes
    (a new BO appears, or an existing BO's registered size changes) as a function of
    triangle count.
  - **Falsifier:** if per-triangle marginal timing cost is constant (single linear/power-law
    fit, no knee) across the full safely-testable range AND the BO inventory never changes,
    H1 is **not supported by this experiment's indicators** within the tested range — this
    is itself a reportable, falsifiable negative result, not proof that overflow never
    happens at any scale (see Limitations).
- **H2 (mechanism):** distinguish (a) TVB grows via a new/resized userspace-registered BO,
  (b) a genuine partial render splits one logical pass into multiple fragment-stage kicks
  with a tile reload (predicts extra userspace-visible submission-adjacent traffic — e.g. an
  IOKit completion-selector call count, or a ring-producer advance, that scales with
  triangle count rather than staying at "1 logical submit"), (c) a spill/segment-chain
  arrangement inside an already-reserved (possibly sparse) address range that needs no new
  userspace call, or (d) something else. **Falsifier for (a):** BO count/size multiset is
  byte-identical (address-independent) across the triangle-count sweep. **Falsifier for
  (b):** the post-pre-commit-dump-point selector histogram (sel=0x11 "completion/notify"
  count, total CALL count) does not vary with triangle count for a fixed submission count of
  1. **Support for (c):** BO inventory and call histogram are invariant, AND a documented,
  already-established firmware-transparent segment-chaining mechanism exists on this
  hardware for a structurally adjacent object (EXP-0043: VDM/CDM command-stream
  continuation via terminator replacement into a **pre-named** VA, no new sel-9 call).
- **H3 (who supplies what):** at and across the overflow-engagement region (however
  characterized under H1/H2), no new userspace-authored program/descriptor/resource-spec
  record appears in the sel-9-registered BO inventory, extending EXP-0108's code-window
  and BG/EOT negative result (0x10000-byte code window, no program found, tested to
  ~600,000 distributed triangles) to genuinely triangle-concentrated geometry and a wider
  range. **Falsifier:** a new BO appears at the engagement boundary whose size/content is
  consistent with executable code (in particular, growth of the 4GiB-aligned code window
  established by EXP-0042, or content resembling AGX instruction encodings per
  `tools/agx-isa`) or a new descriptor-shaped record correlated specifically with triangle
  count (as opposed to attachment count/format, which are already characterized).
- **H4 (limits):** the workload has a finite triangle-count ceiling within which output is
  numerically correct and command-buffer status is `Completed`; beyond it, failure occurs.
  **Falsifier:** no failure of any kind occurs across the full tested range up to the
  `argv` parser's own ceiling (`UINT32_MAX/3`) — this experiment does not attempt that full
  range (a hard, pre-declared stress ceiling is set below for safety) and will report
  "bounded, not universal" if no failure is reached within it.

## 2. Independent / controlled variables

- **Independent (primary):** triangle count `N`, `accumulate` mode (EXP-0118 CLI arg 3),
  target `128x128`, 1 submission per process, fixed 8xR32F MRT (hard-coded in EXP-0118; not
  independently variable without modifying it — documented limitation, not worked around).
- **Independent (secondary, orthogonal axis, per METHOD dispatch instruction):** render
  target width=height, at a fixed small `N=1` (below any plausible geometry-driven
  threshold), to separate "more geometry" from "more tile-state" pressure. EXP-0118 caps
  dimensions at 4096 (`parse_dimension`).
- **Controlled:** attachment count (8, fixed by EXP-0118), pixel format (R32Float, fixed by
  `accumulate` mode), blend mode (additive, fixed), command-queue count (1), one process per
  case (own OS process — never batched in one process, so no cross-case allocator-state
  leakage), `DYLD_INSERT_LIBRARIES`/env only — **EXP-0118's binary and sources are used
  exactly as built by the orchestrator, unmodified** (hashes pinned in section 6).
- **Held out / explicitly not varied (documented limitation):** per-vertex varying-data
  size and attachment count are hard-coded in EXP-0118 (`accumulate`/`overflow`/`indirect`
  modes always use a 16-byte dummy varying buffer and 8 fixed R32F/BGRA8 attachments); this
  experiment cannot vary them without modifying EXP-0118, which is out of scope
  ("Do NOT modify anything inside EXP-0118"). Reported as UNKNOWN/untested, not silently
  assumed equivalent.

## 3. Method

### 3.1 Timing sweep (Sweep A — H1-timing)

For each `N` in the frozen list (3.4), measure **slope-corrected marginal per-submission
wall time**: run the unmodified EXP-0118 binary twice, at submission counts `S1` and `S2`
(`argv[5]`), each a **separate OS process**; `marginal_ms(N) = (t(S2) - t(S1)) * 1000 /
(S2 - S1)`. This cancels fixed one-time process/dylib/Metal-library-load/pipeline-compile
cost (confirmed dominant at small `N`: ~1.5 ms at `N=1..1000`, vs. tens of ms to seconds at
large `N` — a pre-freeze calibration finding, not gated evidence). For `N >= 300,000` a
single `S=1` process is timed directly instead (fixed overhead is <0.1% of GPU-bound time
at this scale per the same calibration; using two `S` points here would not fit the time
budget). No interposer is attached for Sweep A (tracing overhead would confound timing).

### 3.2 Mechanism sweep (Sweep B — H1-inventory, H2, H3, triangle-count axis)

For each `N` in the frozen list (3.4), run the unmodified EXP-0118 binary **once**, one
process, under `DYLD_INSERT_LIBRARIES=iotrace.dylib` (built from the pinned,
unmodified `tools/iotrace/iotrace.c`, hash pinned in 6.2) with:
`IOTRACE_LOG=<case>.log IOTRACE_DUMP_DIR=<case>_maps IOTRACE_MAX_MAP=0x4000
G17P_DUMP_BEFORE_COMMIT=1`. `G17P_DUMP_BEFORE_COMMIT` is EXP-0118's own, pre-existing,
unmodified env-var hook (raises `SIGUSR1` once, right after encoding, before `commit`);
iotrace's `usr1_thread` responds by dumping every sel-9-tracked BO's size/GPU-VA (always
complete, uncapped) and up to `IOTRACE_MAX_MAP` bytes of content (capped, informational).
**Calibration finding (pre-freeze, non-gated):** for this workload, **zero** sel-9 calls
occur after this pre-commit dump point in a normal (non-faulting) run — confirmed by
comparing total sel=9 CALL count in a full run to the count up to the dump point. The
pre-commit dump is therefore a complete-lifetime inventory for this workload, not merely a
snapshot; if a case's trace shows sel-9 calls after the dump point, that itself is recorded
as a **deviation** from this baseline (informative, not treated as instrument error).

### 3.3 Mechanism sweep (Sweep C — dimension/tile-pressure axis)

Identical method to 3.2, varying width=height instead of `N` (held at `N=1`).

### 3.4 Frozen case lists

```
Sweep A small-N (slope method, S1=8, S2=48):
  N = 1, 10, 100, 1000, 3000, 5000, 8000, 10000, 15000, 20000, 30000,
      48217, 70000, 100000, 150000, 200000                     (16 points)
Sweep A large-N (single S=1):
  N = 300000, 500000, 800000, 1200000, 2000000, 3000000, 5000000,
      8000000, 12000000, 20000000                              (10 points)
Sweep B (mechanism, triangle axis, S=1):
  N = 1, 1000, 48217, 200000, 2000000, 20000000                 (6 points)
Sweep C (mechanism, dimension axis, N=1, S=1):
  WH = 32, 64, 128, 256, 512, 1024                               (6 points)
Sweep D (limits/failure-mode, exploratory, single-shot, NOT byte-gated):
  accumulate N=50000000 (oracle-precision-boundary case, with iotrace)
  overflow   N=15000000 (pre-freeze: succeeded once)  with iotrace
  overflow   N=20000000 (pre-freeze: GPU-recovery-discard once) with iotrace
```

All Sweep A/B/C cases run identically in **both** official captures (run01, run02) — a
**separate OS process per case, per run** (never reused, never batched). Sweep D runs
**once** (single-shot, explicitly not part of the two-run byte-exact gate — extreme-N
`overflow`-mode faults were observed to be **non-monotonic in N** during pre-freeze
calibration, i.e., not a deterministic function of `N` alone at this scale; treating a
single instance of a non-deterministic fault as a byte-exact-reproducible record would be
dishonest, so Sweep D is reported as single-shot HW-PROBE observation with that caveat
stated explicitly, per CODEX evidence-labeling discipline).

### 3.5 Pre-freeze calibration disclosure

Before writing this contract, informal (non-recorded, `work/`-only, smoke-gate-exempt per
`SUBAGENT_BRIEF.md`) calibration runs were used to: confirm the timing slope method resolves
a real signal; confirm the interposer captures sel-9 traffic for this specific binary and
that BODUMP fires only via `G17P_DUMP_BEFORE_COMMIT` (atexit only covers `dump_all_maps`,
not `dump_all_bos` — a real, documented `tools/iotrace` behavior, not modified here); locate
the float32 oracle-precision boundary (~50,000,000 triangles in `accumulate` mode) and
confirm it is width/height-**invariant** (identical failure maxima at WH=32/128/512),
supporting "oracle precision limit" over "capacity limit" for that specific boundary;
and locate the `overflow`-mode GPU-recovery-discard fault region and observe its
non-monotonicity. These informal runs are preserved under `work/pilot_*` for transparency
but are **not** part of the gated `raw/` evidence; every claim in `RESULTS.md` that relies on
them is labeled accordingly and, where feasible, re-obtained formally in Sweep A-D.

## 4. Expected observations if hypotheses are TRUE vs. FALSE

| Hypothesis | If TRUE | If FALSE (falsified) |
|---|---|---|
| H1-timing | marginal ms/triangle shows a knee (regime change) at some `N*` | single clean linear/power-law fit, no knee, across the tested range |
| H1-inventory | BO size multiset changes at/after some `N*` | BO size multiset is byte-identical (address-independent) at every tested `N` |
| H2(a) | a BO's registered size grows, or a new BO's `(size)` appears, correlated with `N` | multiset invariant |
| H2(b) | sel=0x11 (or other post-dump-point selector) CALL count scales with `N` at fixed submission-count=1 | CALL count/selector histogram after the dump point is constant across `N` |
| H3 | a new executable-code-shaped or descriptor-shaped BO appears at engagement | inventory (incl. the 0x10000-byte code window) is unchanged across the sweep |
| H4 | a clean failure boundary (status != Completed, or wrong output) is found within the tested ceiling | no failure up to the declared stress ceiling (reported bounded, not universal) |

## 5. Known confounders

- **Float32 additive-blend precision**, not TVB capacity, can make the `accumulate`-mode
  oracle (`exact=1/0`) fail at extreme `N` (per-triangle increment `1/N` shrinks below the
  running sum's ULP). Pre-freeze calibration confirms this specific failure signature
  (quantized power-of-two maxima) is **width/height-invariant**, which a true capacity limit
  would not be expected to be. `RESULTS.md` must not attribute an `accumulate`-mode oracle
  failure to TVB exhaustion without this check.
- **Fixed per-process overhead** (dylib load, Metal library/pipeline compile, ~1.5 ms)
  dominates raw single-run wall time at small `N`; the slope method exists specifically to
  remove it. A single-`S` timing at small `N` would be confounded by this and is not used
  below `N=300,000`.
- **iotrace tracing overhead** (struct hex-dump logging) could itself perturb timing; Sweep
  A therefore never attaches the interposer, and Sweep B/C never use their trace for timing
  claims.
- **GPU-recovery / driver-state carryover across processes.** Each case is its own OS
  process (no shared GPU context), but repeated large-`N` stress in the same session could
  in principle leave transient thermal/driver state that affects a subsequent case. A
  post-hoc sanity re-run (`accumulate N=1000`, expect `exact=1`, `status=Completed`) is
  captured after any Sweep D fault-inducing case, both in pre-freeze calibration and in the
  official runs, and its result is recorded.
- **Allocation-schedule-dependent GPU/CPU addresses.** GPU VAs and CPU addresses are
  **excluded from the byte-exact two-run gate**; only `(size)` multisets and call-count/
  selector histograms are gated, per the standing "no nondeterministic field in
  byte-compared records" rule. GPU VAs are still recorded (informationally) and, where they
  reproduce identically run-to-run (observed for the low-address FW-context BOs in
  pre-freeze calibration), reported as a bonus corroboration, never as a gate requirement.

## 6. Environment, tool, and source pins

### 6.1 Target
Local Apple M4 (G16G), 10 GPU cores, macOS 26.6.2 (25G82), Metal 4. This is the **only**
target used (A18 Pro is HANDS-OFF per `CLAUDE.md`; M5 out of scope).

### 6.2 Pinned source hashes (SHA-256)
```
experiments/EXP-0118-a18-pro-partial-render-workload/partial_render.m
  2d7c1238d526621e871a75f975470084ccaa7ff33a6b43d5ed178eb4bd14f8ba
experiments/EXP-0118-a18-pro-partial-render-workload/partial_render.metal
  8dd63887bc94219fa84cbed60a167e2368daa90e1d712d8932ff43673f2f6f8b
experiments/EXP-0118-a18-pro-partial-render-workload/run.sh
  593fb1ed357b80c8fc2cc8a46b545cd2512135e08d9c6f85988cb445e3123caf
experiments/EXP-0118-a18-pro-partial-render-workload/build/partial_render
  b6bf7e27e1ab7984eccc7c55274761ae8f988bf7435d13f83d586d0f543d3130
experiments/EXP-0118-a18-pro-partial-render-workload/build/g17ppartial.metallib
  ecd8d7103ca46b892b68a86a5e05d42ecd280f87500d5e2a04a0c81105a5c802
tools/iotrace/iotrace.c
  4c8e1cedb9cbacd2e26c1699989337b95602a7c6beeb8823b19a71d1b55a3441
```
Both `tools/iotrace/` and `experiments/EXP-0118-.../` are used **read-only**: iotrace is
compiled (unmodified source) into `harness/build/iotrace.dylib` inside this experiment's own
directory; EXP-0118's already-built binary/metallib are invoked as-is via `run.sh`'s output
in `experiments/EXP-0118-.../build/`.

### 6.3 Timeouts and safety
Hard per-process timeout: 150 s (Sweep A/B/C cases complete in well under 3 s based on
calibration; this generously bounds the largest Sweep A point, N=20,000,000, ~2.5 s
predicted). Sweep D cases (deliberately stress-adjacent) get the same 150 s hard timeout. A
sanity re-run (`accumulate N=1000`, expect `exact=1`) follows every Sweep D case and is
logged; if it fails, the run is halted and marked BLOCKED per `CLAUDE.md`'s recovery model
(no tool-based reboot attempted). `--selftest`/`--seqtest` gates run before any `raw/` is
trusted; a `NON-RECORDED` smoke pass (identical harness, `work/smoke/` output, discarded) is
required to complete cleanly before the first official `raw/` capture begins.

## 7. Standing-gate compliance plan

- `--selftest`: synthetic fixtures exercise the analyzer's parsing/comparison logic
  (multiset diff, selector histogram diff, address-independence normalization) without
  touching `raw/`.
- `--seqtest`: verifies the on-disk state machine `PRE_GPU -> RUN01_PRESENT -> RUN02_PRESENT`
  — this contract frozen and hashed before any capture; run01 fully present and internally
  consistent before run02 starts; run02 fully present before the two are compared.
- Non-recorded smoke gate: a full dry run of the harness against `work/smoke/` (same code
  path, disposable output) must pass before `raw/` is touched.
- No nondeterministic field in byte-compared records: the Sweep B/C gate payload is
  `(size)` multisets (per-case, sorted) + selector CALL-count histograms; GPU VA/CPU address
  fields are captured for provenance but excluded from the byte-exact comparison, matching
  EXP-0108's proven address-independent method.
- Fixtures from RECORDED REALITY: `--selftest` fixtures are drawn from actual pre-freeze
  calibration log excerpts (`work/pilot_*`), not synthesized from the desired conclusion.
- Append+fflush per record; `PROGRESS.md` updated per milestone; one case = one process;
  faults/timeouts are recorded as results, never retried-and-hidden; run ids are never
  reused; no post-capture repair of `raw/`.

## 8. Clean-room category

**DATA-TRACE** (IOKit boundary traffic of our own process, via the unmodified public
`tools/iotrace` interposer) + **HW-PROBE** (wall-clock timing of our own black-box process
invocations; observing `MTLCommandBufferStatus`/error strings via EXP-0118's own already-
public-API-only instrumentation). No Apple binary is disassembled, decompiled, or
introspected. EXP-0118 and `tools/iotrace` are used exactly as built/written, read-only.
