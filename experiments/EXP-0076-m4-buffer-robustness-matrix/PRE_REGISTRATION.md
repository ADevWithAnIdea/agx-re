# EXP-0076 pre-registration — M4 public-Metal owned-buffer robustness matrix

**Frozen state: PRE-GPU.** No Metal compilation or execution has occurred for
EXP-0076 at freeze time (the only host-side build so far was a throwaway
`clang` compile of the harness in a scratch dir, since deleted, to prove it
links; its only execution was with no arguments, which exits 2 at argument
validation before any Metal call). This registration precedes the build
execution and the two capture runs. Anything that could not be frozen before
the build is a STOP, not an improvisation.

**Successor statement.** EXP-0076 supersedes the never-captured scaffold
`../EXP-0068-m4-robustness-contract` (see its `SUPERSEDED.md`: pre-GPU gate
scaffold only; nothing was built or captured; it binds nothing). Its intended
scope (out-of-allocation behavior, guard/zero mappings) is folded, broadened
to the full unaligned + boundary-crossing matrix, into this experiment with a
complete fresh registration.

## Question

Part-II questionnaire items **MEM-06, MEM-07, MEM-08, MEM-09, MEM-10** of
`APPLE9_RE_IMPLEMENTATION_GAPS.md` ("P0 — Memory addressing and robustness"),
plus recorded observations adjacent to **MEM-11** and usable as direct input to
**MEM-12** (the `load_global_bounded` synthesis question). This is the
user-directed top-priority load/store/SSBO increment: for authored MSL
accessing a device buffer at controlled byte offsets, what does the hardware
actually do at unaligned offsets, past the allocation end, and across the
end-boundary — behaviorally, through the public Metal API, on the local M4?

Compiler consequence (recorded, not implemented here): these observations fix
the robust-buffer semantics a Vulkan compiler must reproduce or emulate
(`load_global_bounded`/robustness clamping) and whether unaligned
`nir_load_global` widths can be emitted natively, for the tested public-Metal
configuration.

## Hypotheses (falsifiable; refuters are per-case and recorded verbatim)

On this machine (Apple M4 / G16G, macOS 26.6.2 build 25G82, Metal 4), for MSL
authored by us, compiled at runtime with `MTLCompileOptions.fastMathEnabled =
NO` and `mathMode = MTLMathModeSafe`, accessing a 64-byte owned
`MTLBuffer` (exact length, no slack) through a `device uchar *` base plus a
runtime byte offset taken from a device `uint` uniform:

- **H1 (MEM-06).** Unaligned loads of width 8/16/32/64/128 bits at byte
  offsets 33 (misaligned by 1) and 35/39 (misaligned by width/2-1 at 64/128
  bits) return exactly the little-endian fill bytes at the access window, with
  no fault and no change to the buffer.
- **H2 (MEM-07).** Unaligned stores of the same widths at the same offsets
  write exactly the frozen store pattern into the window and leave every other
  byte of the allocation unchanged.
- **H3 (MEM-08).** Out-of-allocation reads (first fully-OOB element at offset
  64, and +1 KiB at offset 1088) return the uniform value `0x00` for every
  tested width and alignment.
- **H4 (MEM-09).** Reads that begin in-bounds and cross the end of the
  allocation by 1..W-1 bytes return the per-component mix: in-bounds fill
  bytes for the in-bounds part, `0x00` for the out-of-allocation tail.
- **H5 (MEM-10).** Out-of-allocation stores (offsets 64 and 1088) are
  discarded: the 64-byte allocation, both adjacent guard allocations, and both
  result-buffer guards are unchanged after the dispatch.
- **Stretch (optional, frozen).** A 32-bit `atomic_exchange_explicit`
  (relaxed) at offset 32 (in-bounds control) and at offset 64 (fully OOB,
  probed only in its own case) exchanges the pre-existing word out and writes
  the frozen pattern word in, with the same discard/zero expectations.

Independent variable: the frozen 106-case matrix below (operation x width x
offset class). Controlled variables: kernel source and per-class frozen MSL
access idioms, compile options, buffer geometry and byte patterns, dispatch
geometry (one compute thread), and the harness process model. Expected
observations if a hypothesis is true are computed deterministically from the
frozen fill/store rules by `analysis.py`; refuters are:

1. any in-bounds load whose observed bytes differ from the fill-derived
   expectation, or whose buffer changed;
2. any in-bounds store whose 64-byte readback differs from the model (window
   written, all other bytes unchanged);
3. any OOB read returning a nonzero value, a fault, a command-buffer error,
   or a hang/watchdog (each is recorded verbatim and answers MEM-08
   differently);
4. any straddle read whose per-byte content is not the mix model;
5. any OOB store that changes the allocation, a guard allocation, or a result
   guard, or that faults;
6. non-byte-identical repeat of an in-bounds case between the two runs;
7. any self-test, smoke-gate, or verify failure before or after capture.

Known confounders and honest limits (pre-registered, not corrected):

- **Allocation granularity.** The "allocation" under test is the API-visible
  `MTLBuffer` of length 64. The driver/firmware may sub-allocate from a larger
  backing page; accesses past the API length may land in driver-managed slack,
  in another buffer, or on an unmapped page. The experiment observes the
  userspace-visible behavior of each case and never claims which case applies
  without evidence (guard allocations are checked every case to catch
  cross-allocation corruption where the allocator happens to place them
  adjacently; failure to observe corruption does not prove isolation).
- **Compiler freedom.** The Metal compiler may lower each frozen idiom to any
  sequence (e.g. decompose a 128-bit load); this experiment observes the
  behavior of the frozen MSL idioms, not a native encoding, and makes no ISA
  claim.
- **Allocator nondeterminism.** Out-of-allocation observations may be
  nondeterministic; the two runs' per-case byte-identity for OOB/straddle/
  atomic cases is therefore an OBSERVED determinism result, not a gate (the
  frozen cross-run gate covers in-bounds cases; see the repeat policy).
- The GPU-side behavior is measured through the public API only; no
  kernel/firmware introspection occurs.

## Exact frozen method

1. **Harness** (`harness/probe.m`, public API only) runs exactly ONE case per
   process. It compiles `kernels/robustness_matrix.metal` at runtime with the
   recorded options, creates the owned buffers in the frozen guard order —
   G1 (256 B, `0x5A`), MAIN (64 B, fill `F(i) = (0xA5 + 0x1B*i) mod 256`),
   RESULT (160 B: 64 B `0x5A` guard, 32 B zeroed payload, 64 B `0xA5` guard),
   G2 (256 B, `0xC3`), PARAMS (32 B) — verifies its own upload (`pre_ok`),
   dispatches ONE compute thread, waits synchronously, checks all guard
   regions, and prints one complete JSON record. Store value bytes are frozen
   as `S(j) = (0xC7 + j) mod 256`, j = 0..15, uploaded as the params words.
2. **Kernels** (one entry point per case class; the access idiom is frozen per
   class and is the object under test): the byte offset is read at runtime
   from `params[0]`, so the compiler can never fold, align, or specialize the
   address. Idioms: `*(device uchar *)`, `*(device ushort *)`,
   `*(device uint *)`, `*(device ulong *)`, `*(device uint4 *)` loads/stores;
   the atomic stretch uses the element-index form `abuf[params[0]/4]` on a
   `device atomic_uint *` binding.
3. **Runner** (`run.py --execute --run-id <id>`) refuses to run without
   `--execute`, first requires `verify.py --selftest` to pass, then the
   preflight/between-runs gate, records git revision + dirty flags + `sw_vers`
   + `xcrun --version` + python/machine + all authored SHA-256 values, builds
   the harness once, runs the NON-RECORDED smoke invocation (one scratch case
   `load_w32_align_in` into `work/`, never promoted into `raw/`; stdout must
   parse with every field present) and only then creates the append-only raw
   tree and dispatches the 106 cases, one fresh process each, hard per-case
   timeout 120 s. A faulted, hung, or killed case is a recorded result
   (status `watchdog`/`proc_fail`/`proc_timeout`), never retried in place; the
   loop continues in a fresh process. Only 3 consecutive OS-level spawn
   failures stop the run.
4. **Two fresh runs** are required: `raw/m4-20260827-run01` and
   `raw/m4-20260827-run02`. Run 02 additionally requires identical revision
   and authored hashes to the closed run 01 record.

## Frozen case matrix (106 cases, exact)

Operation `load` then `store`, each at widths 8/16/32/64/128 bits
(`uchar`/`ushort`/`uint`/`ulong`/`uint4`), then a 2-case atomic stretch.
Allocation = 64 bytes. `F(i) = (0xA5 + 0x1B*i) mod 256`.

| width (bits) | align_in | mis1 | mishalf | last | oob1 | far | straddle_c (c=1..W-1) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8  | 32 | — | — | 63 | 64 | 1088 | — |
| 16 | 32 | 33 | — | 62 | 64 | 1088 | 63 |
| 32 | 32 | 33 | — | 60 | 64 | 1088 | 61, 62, 63 |
| 64 | 32 | 33 | 35 | 56 | 64 | 1088 | 57..63 |
| 128 | 32 | 33 | 39 | 48 | 64 | 1088 | 49..63 |

- `align_in` — aligned in-bounds control (offset 32).
- `mis1` — misaligned by 1 byte (33).
- `mishalf` — misaligned by width/2-1 bytes, only where that differs from
  `mis1` (35 at 64-bit, 39 at 128-bit).
- `last` — last full element in-bounds (64-W).
- `oob1` — first element entirely out of the allocation (offset 64).
- `far` — +1 KiB past the end (offset 1088).
- `straddle_c` — starts in-bounds and crosses the end by c bytes
  (offset 64-W+c): 1, 3, 7, and 15 straddle cases at 16/32/64/128 bits.
- Atomic stretch: `axch_w32_align_in` (offset 32), `axch_w32_oob1`
  (offset 64). Atomics are never probed in the same case as anything else.

Counts: 52 load + 52 store + 2 atomic = **106 cases per run**. Example names:
`load_w32_align_in`, `load_w64_mishalf`, `store_w128_straddle_15`,
`store_w1_last`, `axch_w32_oob1`. The complete machine-readable matrix
(106 entries, each `{i, name, op, kernel, width, off, cls, store_hex}`) is
embedded verbatim in `CAPTURE_CONTRACT.json` (`matrix.cases`) and re-derived
from `run.py` by every verification gate; the two cannot disagree.

## Per-case record schema (frozen; single authoritative key sets)

- `04_results.jsonl`, one line per case, exactly 17 keys: `i, name, op, width,
  off, status, exit, timed_out, cb_status, err, obs, buf_after, pre_ok, g1_ok,
  g2_ok, res_g0_ok, res_g1_ok`. `obs` = result-payload bytes
  (2*max(4, width) hex chars for load/axch, empty for store); `buf_after` =
  the full 64-byte allocation after the case (128 hex chars). No timing
  fields, so the two runs are byte-comparable.
- Statuses (frozen enum): `ok` (exit 0, command-buffer status 4, full record),
  `cb_error` (full record, command-buffer status != 4), `watchdog` (in-process
  watchdog exit 97/98: compile/dispatch budget exhausted — a GPU-hang result),
  `proc_fail` (process died / unparseable record), `proc_timeout` (outer
  120 s timeout). All five are results.
- `05_receipts.jsonl`: one process receipt per case (9-key receipt + `i`,
  `name`) — process history, not byte-compared across runs.
- `03_dispatch.json`: envelope with `cases_planned`, `cases_recorded`, the
  five status counts, `results_lines`, `results_sha256`.
- Guard/integrity flags (`pre_ok`, `g1_ok`, `g2_ok`, `res_g0_ok`, `res_g1_ok`)
  are OBSERVATIONS, not gate conditions: a false `g1_ok` on an OOB store is
  exactly the MEM-10 corruption answer, and `verify.py` accepts it as valid
  evidence (proven by the self-test case `guard_corrupt_oob_store_is_valid_evidence`).

## Cross-run repeat policy (frozen before any build)

Out-of-allocation behavior is the unknown under test and may legitimately be
nondeterministic. Therefore: every **in-bounds** case (classes `align_in`,
`mis1`, `mishalf`, `last`) must be **byte-identical** between run 01 and run 02
(a violation is a hard STOP for interpretation), and every case must have
identical `status`. Per-case byte-identity of out-of-allocation, straddle, and
atomic observations is REPORTED (`analysis.json` `repeat.differing_cases`) as
the observed determinism answer for MEM-08/MEM-09/MEM-10 — nondeterminism
there is a first-class result, not a quarantine. `analysis.py` enforces the
in-bounds gate before issuing any verdict.

## Environment, timeouts, and raw schema (frozen)

- Target: the local Apple M4 (G16G) through public Metal only; harness built
  with `xcrun clang -fobjc-arc -framework Metal -framework Foundation`.
- Recorded at capture: git revision + dirty flags, experiment-tree dirty
  entries, `sw_vers`, `xcrun --version`, python version, machine, buffer
  geometry dict, timeouts, argv/cwd/UTC timestamps of every step, and SHA-256
  of every authored blob and raw artifact.
- Hard timeouts: environment commands 10 s; host build 60 s; library+pipeline
  compile 120 s (in-process watchdog, exit 97); dispatch+readback 100 s
  (in-process watchdog, exit 98); per-case process 120 s (subprocess timeout
  as the outer belt).
- Raw schema per run: `00_inputs.json`, `01_matrix.json`, `02_build.json`,
  `03_dispatch.json`, `04_results.jsonl`, `05_receipts.jsonl`,
  `06_run_manifest.json`. Raw is append-only, regular files only, no
  symlinks. Pre-capture failures (environment, host build, smoke gate) write a
  retained `work/<run-id>/STOP.json` and never create the raw tree; a
  post-capture infrastructure failure (3 consecutive spawn failures) writes
  `raw/<run-id>/STOP.json` and ends that run. Nothing is retried
  automatically.

## Promotion rule and scope

Before any capture, in this exact order and all passing:
`python3 -B verify.py --selftest` (proves the gates satisfiable and
fail-correctly, the record builder correct, the smoke validator pure against
the EXP-0072 truncation class, and guard-violation observations admissible),
`python3 -B make_manifest.py --check`, `python3 -B verify.py --preflight`.
Between runs: `python3 -B verify.py --between-runs`. Before any verdict:
`python3 -B analysis.py --run-a ... --run-b ... --write` must exit zero
(in-bounds repeat gate green), then `python3 -B verify.py --captured` for
exactly the two contracted runs, then `python3 -B make_manifest.py --write`
and `--check`. Until then MEM-06..MEM-10 remain **Open** for this
configuration.

This experiment cannot establish native instruction encodings, ISA fields,
descriptor layouts, behavior of any other compiler version or OS, Linux/UAPI
behavior, or any A18 (G17P) claim — the A18 is hands-off for this work, and no
cross-target inference is drawn. MEM-11 (descriptor-level bounds) is an
ISA/descriptor question that behavioral public-Metal evidence cannot close;
this experiment records adjacent observations only (what robustness semantics
the hardware actually exhibits, which bounds what any bound mechanism must
reproduce), as direct input to MEM-12.

## Authored blob hashes at freeze (SHA-256)

Every value below is derived from this experiment's own final bytes and is
independently enforced by `CAPTURE_CONTRACT.json` (`authored_sha256`), which
`verify.py` re-checks at every gate.

- `kernels/robustness_matrix.metal`: `73f9f5e61af1d1297e127ec01a6368aa423a903bd124e6e16bf46c77c32fe4c8`
- `harness/probe.m`: `a397ac40498435a2b7ec9a667a40865727c39bc9489ef688248b08bd8c9515cc`
- `run.py`: `670037c16c67fb844a23923241bc6ab9762969790d06c1e3d0c90995b0fb391f`
- `analysis.py`: `f279f11f07577fca97d8ac0884d34afa3399bf6711fe550bc18f09577eafa81a`
- `make_manifest.py`: `9ec9b1d8b0fac4e5a7ad6b0edea7a67cebcb9b1f35973a7232a0640bf8600de7`
- `verify.py`: `3fd74b902524288443b52287b2164c201d52ddac02df6a448d7b9e7b5dc8e709`
- `PRE_REGISTRATION.md`: self (hash frozen in `CAPTURE_CONTRACT.json`)
- `README.md`: `5813849fdf87de381946deb95def68ee3ce1e3e434fd31ac01374976e463c57c`

Clean-room provenance: HW-PROBE / OWN-SHADER / PUBLIC API (planned only)
Inputs inspected: committed authored MSL, harness, runner, verifier, analysis
Apple binary introspection: NONE
Reproduction: `python3 -B verify.py --selftest` then `python3 -B verify.py --preflight`; capture requires explicit `run.py --execute`
Evidence: no raw observations exist at freeze; `CAPTURE_CONTRACT.json` is the frozen grammar
