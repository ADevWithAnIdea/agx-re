# EXP-0127 pre-registration: M4 graphics shader selection -- token/selector
# derivation, FS redirect generation, and code-window relocation category

## Question

P0.2 (`docs/P0-P1-CLOSURE.md`) needs the general rule for the VS creation
token EXP-0042 saw only two values of, the exact meaning of the FS selector
at `0x58000+0x08` (a HW/FW *consumer* proof, not just a structural
correlation), and whether the code-BO base maps to Linux `usc_exec_base` --
tested by determining whether the code window is heap-relative (like
EXP-0110's CDM chain) or invariant (like EXP-0110's VDM/FF-state pool)
under ordinary client-allocation pressure.

Four concrete deliverables, each with a falsifiable hypothesis below:

1. **VS token rule.** Sweep many pipeline-state creations and determine
   whether the record`+0x1c/+0x20` token is (a) a pure ordinal/fixed-stride
   handle independent of the underlying VS code's compiled size, or (b) a
   code-window-relative BYTE OFFSET whose step should then be proportional
   to the PRECEDING pipeline's own code size (mirroring the FS formula
   EXP-0042 already established: `selector = header + size + 0x40`).
2. **FS selector redirect.** Independently construct a selector value equal
   to a DIFFERENT, valid FS pipeline's own natural selector, splice it into
   the live `0x58000+0x08` field before commit (mirroring EXP-0116's
   HW-PROBE method for the CDM link), and observe whether hardware executes
   the redirected-to FS instead of the nominally bound one. Sweep the
   boundary (misalignment, zero, far out-of-range, top-bit, the field's own
   `0xffffffff` ceiling) for fault/hang/silent-alias/no-effect outcomes in
   both directions from a known-valid value.
3. **Code-window relocation category.** Allocate 64 MiB of ordinary client
   padding (EXP-0110's own `cdm_pad_big`/`vdm_pad_big` method) and create
   several additional command queues BEFORE any pipeline/library work, and
   determine whether the code BO's own registered GPU VA (`0x10000000000`)
   moves (CDM-like, heap-relative) or stays fixed (VDM/FF-state-like,
   invariant).
4. **Relocatable entry/extent.** Derived from (1)-(3): what exactly a
   driver must emit to place its own code and select it, stated as a
   concrete field-by-field recipe or an honest list of remaining unknowns.

## Falsifiable hypotheses

- **H1 (VS token, ordinal).** If the token is a pure per-pipeline-state
  ordinal counter with a fixed stride, interleaving genuinely
  different-sized VS functions in creation order (tiny/huge/tiny/huge...)
  will show a CONSTANT step between consecutive tokens regardless of which
  size preceded which. Falsifier: the step after a "huge" creation is
  measurably larger than the step after a "tiny" creation (by roughly the
  code-size difference), supporting the code-offset alternative instead.
- **H2 (VS token, capacity boundary).** A long same-size ordinal sweep will
  either (a) grow linearly without bound up to some very large N, (b) hit a
  clean pipeline-CREATION failure at some finite N (a Metal-level resource
  ceiling), or (c) hit a discontinuity where the token's own numeric regime
  changes (e.g. because the small first code container's real byte capacity
  is exhausted and a new backing region opens). Falsifier for "the token
  free-runs forever with no boundary at all": any of (b) or (c) observed
  within the tested range (up to 650 creations).
- **H3 (FS redirect, positive).** Splicing a real, valid, freshly-discovered
  alternate FS's own natural `0x58000+0x08` selector value into a bound
  pipeline's pool record before commit will make the RENDERED OUTPUT match
  the redirected-to FS (not the nominally bound one), completing without a
  fault. Falsifier: the command buffer completes but renders as the
  ORIGINALLY bound FS regardless of the spliced value (the field is
  read/cached but not the code-selecting field), OR the command buffer
  faults on an otherwise-valid alternate selector value.
- **H4 (FS selector, boundary/alias).** Values far outside any mapped
  region (the field's own `0xffffffff` ceiling; a value with the top bit
  set) will behave differently (fault, hang, or silent alias) from a
  moderate out-of-range value, mirroring EXP-0116's CDM-link finding that
  aliasing is a real, distinct, silent hazard rather than a uniform "any
  invalid value faults the same way." Falsifier: every tested
  out-of-range/boundary case behaves identically regardless of magnitude.
- **H5 (code window, invariant).** The code BO's registered GPU VA will be
  UNCHANGED under 64 MiB of ordinary client padding and under additional
  command queues created before it, matching EXP-0110's VDM/FF-state
  category rather than its CDM (heap-relative) category. Falsifier: the
  code BO's VA changes under either perturbation.

## Informal calibration that shaped this pre-registration (disclosed, not
## evidence -- see PROGRESS.md for the full trail)

Before freezing the case matrix below, throwaway calibration programs
(`work/calib_fs.m`, `work/calib_redirect2.m`, deleted large dump captures)
established three things this pre-registration's design depends on, so they
are disclosed here rather than silently assumed:

1. A fragment function that does not GENUINELY consume its `[[stage_in]]`
   varying (an earlier draft multiplied the varying by a compile-time `0.0f`
   literal, which the compiler constant-folds away) takes a different code
   path that never populates `0x58000+0x08` at all. `kernels/fsredirect.metal`
   instead scales the varying by a RUNTIME buffer value (`params[0].z = 0`),
   which cannot be constant-folded, and reliably populates the field.
2. The `0x58000+0x08` field is already correct PRE-commit (immediately
   after `endEncoding`, before `commit`) and is byte-identical pre- vs
   post-commit for an unmutated draw -- the same timing EXP-0116 already
   established for the CDM tail link, and the basis for this experiment's
   splice-before-commit method.
3. A first attempt at H3 (bind RED, splice in GREEN's own freshly-discovered
   natural selector, commit) completed WITHOUT a fault and rendered AS RED,
   not GREEN -- refuting H3 as originally stated for at least this one
   case. A follow-up calibration run confirmed the spliced value survives
   unmodified through commit (a post-commit read of the same field showed
   the spliced value, not the original), and a full-BO scan for the
   spliced value's raw bytes found no secondary copy elsewhere among the
   captured BOs. A separate calibration case (`0xffffffff`, the field's own
   representable ceiling) DID fault (`kIOGPUCommandBufferCallbackErrorPageFault`).
   This experiment's official case matrix is deliberately broadened (beyond
   what the original task brief's single "decisive redirect" framing
   implied) to characterize this apparent contradiction precisely: a
   moderate, valid-looking alternate value is silently ignored for code
   selection while an extreme value faults, which is itself a testable,
   falsifiable structure (see H3/H4 above) and not assumed correct without
   the official capture.

## Independent / controlled variables

- vstoken varied: `--order` (which of the 8 fixed differently-sized VS
  functions is created in which position).
- vstoken uniform: `--count` (how many near-identical VS functions are
  created and drawn, N=650, chosen to comfortably cross the capacity
  boundary calibration located near N=506).
- vstoken perturb: `--pad-mb` (0 vs 64) and `--extra-queues` (0 vs 4),
  each compared against the SAME run's own unpadded baseline.
- fsredirect: `--case` (which pipeline is bound and what value, if any, is
  spliced into the pool selector before commit).
- Controlled/fixed: dispatch shape (a single full-screen triangle), shared
  trivial FS across the VS sweeps (`fs_flat`), the fixed 3-pipeline
  discovery order (red, green, blue) at the start of every `fsredirect`
  process invocation, per-case process isolation (SUBAGENT_BRIEF.md: one
  case per process for every mutation-bearing harness invocation).

## Frozen authored-file hashes (sha256)

```
1889c111aba784588b38aa6c6b8dd0560e19380e11553633326f3f2c0bacc181  harness/vstoken.m
8e761cb00ef310acfef4e0b82ba1328d4325057813e344ecb65ba19d23402490  harness/fsredirect.m
3fcef5b180a6c8813c144a54366873dd472a1d3fcb7b9e022ce5a32edac14e39  kernels/vs_uniform.metal
a7fdb7926451d7eff9e390ed47aeff70711df9d420c446b27d3aa8b1b7ae5eed  kernels/vs_varied.metal
aedf15d002032b329ced47230584a44fe0a4250c567043048eb4e1bf0a9951b1  kernels/fsredirect.metal
cb967d80250fa7eaa056f4d1ab97e4bd77374bf4b24e09016dab06221c63981f  analysis/gen_kernels.py
ef9acd2c2da5abb4f64c77eaa963aa192e10c2e44084b6046ee2c05fa295312b  schema.py
9841075d87ee7a668d67615fe4d462b5a774baec9d694f6f1e22f51b6a8c1d7c  run.py
1f3a101c97227db5ba05519e7c681ba368c5bba8acb39cc0220e5768f544625c  verify.py
```

`kernels/vs_uniform.metal` was generated by `analysis/gen_kernels.py
--n-uniform 800` (deterministic; re-running reproduces the identical file
and hash above).

`schema.py`/`run.py`/`verify.py`'s hashes above are POST-CORRECTION (see
`CAPTURE_CONTRACT.json`'s `post_capture_corrections`, two entries):

1. The first official run attempt (`m4_20260828_run01`) crashed partway
   through on a false-positive in the address-leak deny-list (it matched
   the substring token `va` inside three legitimate derived boolean field
   names). That run's two completed records are retained as disclosed
   process evidence, not as one of the two official runs this experiment's
   closure claims depend on.
2. The next pair (`m4_20260828_run02`/`run03`), both fully valid, complete
   captures, exposed a GENUINE HARDWARE finding via the cross-run gate
   itself (mirroring EXP-0116's own precedent): `result_colour` differed
   between the two runs for 2/25 `fsredirect` records
   (`misalign_plus4`/`misalign_minus1`) despite both reporting a clean
   `final_status=4` (Completed, no fault) -- i.e. racy even without a
   fault, which the schema had not anticipated. Both runs are retained as
   the primary evidence for this finding (see `RESULTS.md`); the schema
   was corrected to exclude `result_colour` for any case whose spliced
   value is not exactly one of the three discovered natural selectors, and
   a fresh pair (`run04`/`run05`) was captured under the corrected schema
   for the row that gates closure claims.

## Raw-record schema (frozen; full definitions in `schema.py`)

Two files per official run, both append-only JSONL:

- `raw/<run-id>/gated.jsonl` -- one record per sub-test/case, containing
  ONLY fields proven or assumed process-invariant (token/selector numeric
  values, booleans, status codes, colour classifications, structural
  counts). NO raw GPU virtual address (the code-window base, the pool/VDM
  base, the capacity-boundary growth region's own base, or any per-BO `cpu`
  pointer) ever appears here -- `schema.assert_no_address_leak` enforces
  this and is exercised by `verify.py --selftest`.
- `raw/<run-id>/addrs.jsonl` -- the complementary raw-address sibling
  (never compared across runs).

Every harness's own raw stdout (`raw/<run-id>/vstoken_*_stdout.txt`,
`raw/<run-id>/fsredirect_<case>_stdout.txt`) is preserved verbatim as the
human-auditable evidence trail (every draw's status, every case's full JSON
output line) independent of the derived/gated summary.

## Timeouts

- fsredirect: per-commit watchdog 10s (completion handler + timed
  semaphore, never a bare `waitUntilCompleted`); per-case process timeout
  60s (`run.py`'s `subprocess.run(..., timeout=60)`); harness's own
  `alarm(45)` as a third, innermost backstop.
- vstoken varied/perturb: per-draw watchdog 10s; process timeout 90s;
  harness `alarm(60)`.
- vstoken uniform (count=650): per-draw watchdog 10s; process timeout 340s;
  harness `alarm(300)`.
- One case per process for every mutation-bearing invocation (every
  `fsredirect --case`); the two safe, non-mutating vstoken sweeps run to
  completion in a single process each, matching EXP-0042's own precedent
  for ordinary (non-splicing) pipeline-creation sweeps.

## Confounders

- **Dead-code elimination of `[[stage_in]]` varyings** (see calibration
  item 1 above) -- mitigated by using a runtime-valued scale, not a
  compile-time literal.
- **GPU addresses vary run to run** by ordinary allocator/ASLR-like
  behaviour; only the derived, non-address facts are asserted stable
  across runs (see schema.py's module docstring for the empirical basis:
  `S_RED`/`S_GREEN`/`S_BLUE` and the VS token's own linear-fit parameters
  reproduced identically across more than a dozen independent calibration
  process launches during development).
- **Racy readback on a faulted command buffer.** EXP-0116 found that how
  much of a faulted command buffer's own earlier effect (including whether
  its `MTLLoadActionClear` even ran) is memory-visible by dump time is not
  guaranteed deterministic. `result_colour` is therefore gated ONLY when
  `final_status == Completed` (see `schema.py`
  `RACY_ON_FAULT_FSREDIRECT`), mirroring EXP-0116's
  `RACY_ON_FAULT_LINKSPLICE` precedent exactly.
- **BODUMP write-vs-read race under heavy padding.** Calibration found that
  with 64 MiB of padding allocated first, a 500ms post-SIGUSR1 sleep was
  insufficient for iotrace to finish writing ~11 x 4 MiB dump files before
  the harness read the directory, causing the SMALL, most-recently-
  registered BOs (VDM/pool/etc.) to appear spuriously absent. Fixed by a
  `--dump-sleep-ms` knob, set to 2000ms for the `pad64`/`extraq` sub-tests
  (small draw counts, so the extra wall-clock cost is negligible).
- **This is a hardware side channel, not a documented API** (direct CPU
  writes into Metal's own internal command-stream storage, exactly as
  EXP-0116 already used). A macOS/Metal update could change allocation
  timing or the exact numeric constants found here without changing the
  qualitative method. Findings are scoped to macOS 26.6.2 / this M4.

## Environment / target

Local Apple M4 (G16G), 10 GPU cores, macOS 26.6.2 (25G82), Metal 4. No SSH.
A18 Pro hands-off (not run). Pinned git revision at pre-registration time:
`633cd06b0c9890bc641128ca7b49ff66eee41cb1` (dirty tree, per repo norm --
sibling experiments commit continuously; captures are validated against the
authored-file hashes above, not against live `HEAD`).

## Run plan

`verify.py --selftest` + `--seqtest` -> smoke gate (`run.py --smoke`, a
single 2-draw non-recorded case into `work/`, never `raw/`) -> `run.py
--run-id m4_<date>_run01` -> `run.py --run-id m4_<date>_run02` -> `verify.py
--captured m4_<date>_run01 m4_<date>_run02`. Never reuse a run id; a
defective capture is retained and superseded by a new id, never repaired in
place.
