# EXP-0185 RESULTS — three proven checks are now shared, and the shared runner has a gated fix

**PURE ANALYSIS. No device, no SSH, no GPU, no dispatch.** Target: none. Date: 2026-08-30.
Nothing in this experiment is a hardware claim; every claim below is about our own host-side
code and is backed by a committed gate that re-runs offline in about three seconds.

## 1. What moved, and where it moved to

| new file | lifted from | what changed in the move |
|---|---|---|
| `tools/agxtest/saferunner.py` | `EXP-0178-.../harness/saferunner.py` + `EXP-0179-.../harness/saferunner.py` | merged: EXP-0179's `make_safe_runner(base)` factory (so an experiment's **pinned** `PersistRunner` can be wrapped) + EXP-0178's render half as `make_safe_render_runner(base)`; counters (`discarded_lines`, `restarts`, `malformed`) kept; `UPSTREAM NOTES` preserved and merged into the module docstring |
| `tools/agxtest/verify_remote.py` | `EXP-0178-.../harness/verify_remote.py` | generalised: `--contract`, `--remote`, repeatable `--prefix`/`--exclude`, pluggable transport (`SshRunner` / `LocalRunner`), batched `shasum` (150 paths per round trip), plain `ssh` when `SSHPASS` is unset, and **exit 2 when the check matched no blobs** — an empty check must not read as a pass |
| `tools/agxtest/closure_scan.py` | `EXP-0178-.../harness/closure_scan.py` | algorithm **unchanged**; CLI gains `--allow NAME:reason` / `--ignore NAME` and multiple function names; `AsyncFunctionDef` accepted as the enclosing scope |
| `tools/agxtest/fakepersist.py` | `EXP-0178-.../harness/fakerunner.py` + `EXP-0179-.../harness/fakechild.py` | merged into one stub with four modes (`good`, `truncate`, `hang_first`, `eof_first`), a shebang + exec bit (no shim script needed), tolerant argv so a runner class can spawn it exactly as it spawns the real `agxrun_persist` |
| `tools/agxtest/testdata/closure_shadow_{bad,good}.py` | new | the EXP-0178 `nb`-rebind reproduced in miniature, plus the corrected form, plus the expected `if`/`else` false positive so the allow-list itself is testable |
| `tools/agxtest/selftest_tools.py` | EXP-0178 selftest G9/G10 + EXP-0179 selftest G1/G2/G3 | one suite, T0..T7, **no GPU / no device / no SSH** |
| `tools/agxtest/README.md` | new section | five rows in the Pieces table + "why each one exists" per module + the width-1 promotion-gate pitfall |

The two experiment copies were **not** modified or deleted: they are the evidence for their
own runs and stay hash-pinned to their own contracts.

## 2. Each check still works after the move — observed

`raw/selftest_tools_run01.txt`, all eight gates (and `raw/selftest_tools_run02.txt`, the
identical re-run after `selftest_tools.py` gained an `atexit` cleanup of its scratch dir --
no gate logic changed; run01 is retained, not overwritten):

```
PASS T0 modules import, SafePersistRunner binds  -- SafePersistRunner over persistrun
PASS T1 good response parses under both runners
PASS T2 truncated OUT -> MALFORMED (safe) / raises (shared)  -- shared raised: not enough values to unpack (expected 3, got 2)
PASS T3 one timeout does not manufacture the requests after it
PASS T4 a killed child's leftovers are discarded, not handed over
PASS T5 an exited child is a wedge, not an empty-line spin
PASS T6 closure_scan flags the rebind, clears the fix, allow-list works
PASS T7 verify_remote catches MISSING and STALE and refuses an empty check
SELFTEST PASS (0 failure(s))
```

**Directly observed, not inferred:**

- **T2 reproduces DEF-0178-1 deterministically with no device.** Driven by the same stub, the
  **shared** `PersistRunner` raises `ValueError: not enough values to unpack (expected 3, got
  2)` on a truncated `OUT` line, while the upstreamed safe runner returns
  `status="MALFORMED"` with `error` and `raw` populated and **never** `HANG`. This is
  EXP-0179's gate G2, preserved.
- **T4 proves the owner tag itself**, without relying on scheduling luck: a queued line
  belonging to a *killed* child is discarded (`discarded_lines == 1`) and the current child's
  line is the one returned.
- **T6 reproduces EXP-0178's G10 exactly.** Run against the file the defect was actually found
  in (`EXP-0178-.../harness/run.py`), the upstreamed scanner reports **the same three
  allow-listed names — `mnem`, `off`, `runner` — and nothing else**
  (`raw/closure_scan_run01.txt`). The move did not change what it sees.
- **T7 exercises `verify_remote` end to end against a local fake "remote" tree**: clean → exit
  0 and "3/3 blobs match"; a deleted file → exit 3 with `MISSING`; an amended file → exit 3
  with `STALE`; a prefix matching nothing → exit **2** with "matched NO pushed blobs".

**Interpretation, separated from the above:** T2/T4 establish that the *structural* defect is
gone in the upstreamed runner. They do **not** establish that the defect was reproducible on
demand in the shared runner's cascade form — see §5.

## 3. The `persistrun.py` patch — generated, gated, NOT applied

`analysis/persistrun-DEF-0178-1.patch` (+111 / −49 lines) implements both `saferunner`
changes in the shared class directly. It is **handed to the orchestrator, not applied**:
EXP-0184 may be running against `tools/agxtest/persistrun.py`, and changing it mid-run would
break that experiment's reproducibility (FIELD-SWEEP-PROTOCOL §7 courtesy). `git status`
shows `tools/agxtest/persistrun.py` unmodified; `git apply --check` on the patch passes.

It is produced by `analysis/make_persistrun_patch.py`, which builds the patched file from the
committed original by **exact-anchor replacement, each anchor asserted to match exactly once**
— so the diff cannot contain accidental drift in the untouched regions.

`analysis/gate_patched_persistrun.py`, **7/7 PASS** (`raw/gate_patched_persistrun_run01.txt`):

```
PASS P1 good path unchanged on every pre-existing key  -- status=OK outs[0]=a5a5a5a5a5a5a5a5
PASS P5 response is a strict superset; the four new keys only
PASS P2 truncated OUT: shared RAISES, patched -> MALFORMED  -- shared raised: not enough values to unpack (expected 3, got 2)
PASS P3 one timeout does not manufacture later results; HANG text unchanged
PASS P4 an exited child is a wedge (DEF-0153-2)  -- status=HANG
PASS P6 saferunner still works over the patched class
PASS P7 broken-pipe path unchanged  -- ('HANG', 'child pipe broken', True)
```

### Which behaviours are defaults-preserving (the review question)

**Preserved exactly, and gated:**

- every pre-existing response key has the identical value on the good path (**P1**);
- `MALFORMED` is a **new** status; every pre-existing status string is produced under exactly
  the same conditions as before (**P1/P5**);
- the `HANG` error text is byte-identical — `"no response within {timeout}s (GPU wedged)"` —
  deliberately left unchanged even though the patched reader also reports a dead child through
  it, so a caller matching on the string is unaffected (**P3**);
- the broken-pipe path returns the same `(status, error, restarted)` (**P7**);
- `_read_line(timeout)` still returns a line, or `None` for timeout **and** for EOF, so
  DEF-0153-2 stays fixed (**P4**);
- a run that never times out behaves exactly as before — the pump only changes *which thread*
  reads, never what is parsed;
- `tools/agxtest/saferunner.py` still builds and works over the patched class, so an
  experiment that pins the wrapper is not broken by the patch landing (**P6**).

**Additive (new, cannot break an existing caller that indexes known keys):**

- new status value `MALFORMED`;
- new response keys `raw`, `discarded_lines`, `restarts`, `malformed_total` — the patched
  response is a strict superset of the old one, and P5 asserts these four are the *only*
  additions;
- new instance attributes `restarts`, `malformed`, `discarded_lines`, `_q`, `_pump`;
- new method `_install_pump()`.

**The one behavioural change a caller could notice, stated plainly:** a truncated or
unparseable `OUT` line used to raise `ValueError` out of `request()`; it now returns
`status="MALFORMED"`. A caller that *relied* on the exception to abort would now continue —
which is the point (a measurement failure is not an observation and must not be scored as
one), but it means **downstream code must handle `MALFORMED` explicitly**: score it as
`measurement_failed`, keep `resp["raw"]`, remove it from the agreement computation and from
`values_dispatched`, and refuse a field whose measurement failures exceed 1% of its dispatched
values. EXP-0178's `analysis/verdicts.py` is the reference implementation of that rule and
already does it.

## 4. Documented, not coded: the width-1 promotion-gate pitfall

`tools/agxtest/README.md` final section, and repeated in the `SUBAGENT_BRIEF` draft:

> A promotion gate written `moved >= 2.0 * max(disagree, 1)` **silently cannot promote ANY
> width-1 field.** With zero disagreements — the best possible outcome — the clamp still
> demands two moving values, and a 1-bit field has at most one value that can differ from its
> own baseline. EXP-0178 found this **in its own gate against its own frozen text**, where it
> was suppressing `read_en`, the exact silent-zero read-enable the experiment was dispatched
> to re-verify. The correct form is `moved >= 2.0 * disagree, and > 0`.

Two habits are recorded with it, because the arithmetic is only the surface: **write the
gate's refusal cases before the gate** (EXP-0178's G6 drives synthetic pairs that should pass
and each broken shape that should fail, each refusing for the reason it names), and **re-read
the gate against the frozen text, not against your memory of it** — this survived because code
and contract were both read as saying the same thing.

## 5. Limitations — what these gates do NOT prove

- **The cascade itself is not reproduced on demand in the shared runner.** T3 prints the shared
  runner's behaviour as an **OBSERVATION, never a gate**: the abandoned thread usually binds to
  the old child at `rd()` entry, so the real failure needs scheduling luck and/or several
  accumulated abandoned readers. In this run the shared runner did *not* cascade. **A clean
  result from a stub is not evidence a defect is absent** (EXP-0179 reached the same conclusion
  and relied on the structural fix, not on a passing stub). What is proven deterministically is
  the *parse* half (T2/P2) and the *tagging* half (T4).
- **No hardware was touched.** Nothing here validates the runners against a real
  `agxrun_persist`, a real GPU, or the neo. The stub speaks the documented line protocol; if the
  real runner ever emits a shape the stub does not, these gates would not see it.
- **`make_safe_render_runner` is untested here.** No render driver is shared in
  `tools/agxtest/` to bind it to (`rsdrv.py` is copied per experiment), so it is offered
  structurally, on the same pump that T4 gates, and is labelled as such.
- **`verify_remote`'s SSH transport is untested** in this run — by construction, since this was
  a no-device experiment. The gate exercises the identical command string through
  `LocalRunner`; the only untested part is the `ssh`/`sshpass` invocation itself.
- **The patch is unapplied and therefore unexercised against a real capture.** Its gates run
  against the patched *file*, not against a live sweep.

## 6. Verdict

- The three checks are shared, they kept their `UPSTREAM NOTES`, and **each still provably
  works after the move** — including reproducing, on the real file, the exact finding it
  produced inside its own experiment.
- The shared runner now has a **reviewed, gated, defaults-preserving patch** waiting for a
  quiet machine, so it can stop being the hazard rather than being subclassed around by every
  experiment that needs it.
- A future agent gets all three plus their gate from one command
  (`python3 tools/agxtest/selftest_tools.py`), and gets the *reasons* from
  `tools/agxtest/README.md` rather than having to re-derive them from a lost run.

**Evidence label:** not applicable — no hardware fact is claimed. The claims are about our own
code and are `SELF-GATED` by the committed offline suites.

## Clean-room statement

```text
Clean-room provenance: none required (host-side plumbing + static analysis of our own source)
Inputs inspected:      our own Python harness code in this repository and our own fixtures
Apple binary introspection: NONE
Device access:         NONE (no SSH, no GPU, no Metal, no dispatch)
Reproduction:          README.md "Reproduction"
Evidence:              raw/selftest_tools_run01.txt, raw/selftest_tools_run02.txt,
                       raw/gate_patched_persistrun_run01.txt, raw/closure_scan_run01.txt
```
