# DRAFT for the orchestrator — proposed addition to `experiments/SUBAGENT_BRIEF.md`

**Status: DRAFT, not applied.** The orchestrator owns `SUBAGENT_BRIEF.md`; EXP-0185 did not
edit it.

**Proposed insertion point:** immediately after the existing section *"A shell hazard that
has now silently corrupted work TWICE in one session"* (which it extends and operationalises)
and before *"## Process — the parts that most often bite"*.

**Also proposed, a one-line edit to the existing "Existing tools" bullet** so the new shared
checks are discoverable from the tool list:

```diff
 - `tools/agxtest/` — hardware testbed: splice arbitrary bytes into our compiled shader, run on the
   real GPU, read back outputs (`agxrender.m`; `persistrun.py` = persistent runner, faults
   logged-and-continued). Metal runs tampered code with no integrity check (bound `MTLBinaryArchive`
   + `FailOnBinaryArchiveMiss`).
+  Also the three **shared offline checks** every capture is now expected to use —
+  `saferunner.py`, `verify_remote.py`, `closure_scan.py` — with their device-free gate
+  (`python3 tools/agxtest/selftest_tools.py`, T0..T7, ~3 s). Read that README's
+  "why each one exists": each caught a live defect, and one of them was catching it in
+  the experiment that wrote it.
```

---

## The text to insert

## The pre-capture sequence — three steps, in this order, none of them chained

Each of these exists because it caught a real defect in a real run, and each was a one-off
copy inside one experiment until EXP-0185 upstreamed it into `tools/agxtest/`. The offline
gate for all three is `python3 tools/agxtest/selftest_tools.py` — no GPU, no device, no SSH,
about three seconds. Run it before you dispatch anything.

**1. Scan your own harness before you push it.** A closure that reads a name its enclosing
scope later rebinds is resolved at *call* time, so it silently sees the new object from that
point on.

```sh
python3 tools/agxtest/closure_scan.py harness/run.py main \
    --allow 'mnem:assigned in two mutually exclusive if/else branches'
```

EXP-0178 lost `raw/g17p_20260830_run01` to exactly this: a read-back **size** rebound to a
`bytearray` two hundred lines below the closure that read it. It matters more than it sounds,
because **it presented byte-for-byte as the hang cascade the same agent had fixed twenty
minutes earlier** — four pilots failed to separate them, and what resolved it was a traceback,
not reasoning. Expect this: **having just fixed a cascade-shaped defect makes the next
cascade-shaped defect harder to see.** Allow-list mutually exclusive `if`/`else` branches
explicitly, **with a reason** — never by weakening the rule.

**2. Verify the remote blobs as a SEPARATE, UNCHAINED step, and read its exit code.**

```sh
export SSHPASS=...                                   # never written to any file
bash harness/sync.sh push
python3 tools/agxtest/verify_remote.py \
    --contract CAPTURE_CONTRACT.json --remote agxre/EXP-NNNN ; echo $?
#   0 = go     3 = MISSING/STALE, do NOT start a capture     2 = nothing was verified
```

**A frozen contract hashes what you AUTHORED. It says nothing about what the DEVICE is
running.** Re-verifying `authored_sha256` before a capture compares the local files against
the hashes of the local files — it always passes. On its first run against its own author,
this check found **11 of 18 blobs matching**: two missing on the neo, five stale, every
amendment since the first push having silently failed to arrive. A gated pair started at that
moment would have executed the pre-amendment harness under a contract asserting otherwise.
Never chain it behind the push it checks: that is the very `&&` failure mode described above,
and it would reintroduce the defect the check exists to catch. An **empty** check is not a
pass — if it matched no blobs (wrong `--prefix`), it exits 2 and says so.

**3. Use a per-child reader, and never score a malformed response as an observation.**

```python
sys.path.insert(0, ".../tools/agxtest")
from saferunner import SafePersistRunner, make_safe_runner
runner = SafePersistRunner(...)                  # or make_safe_runner(MyPinnedPersistRunner)
```

`tools/agxtest/persistrun.py` (and every `rsdrv.py` render copy) starts a **fresh reader
thread per line and abandons it on timeout**, and that thread **re-resolves `self.proc` at
execution time** — so after the first watchdog timeout it can wake on the *replacement*
child's stdout and race the foreground reader. Responses come back truncated and the shared
parser raises `ValueError: not enough values to unpack`. **A real hang is not required: a
mere WATCHDOG TIMEOUT is enough.** EXP-0178 verified by hand that its pre-registered hang
candidate runs clean on G17P (`STATUS OK`, `GPUTIME_NS 5000`, sentinel written), so **all four
"hangs" in its pilots were manufactured on a case the hardware handles fine**.

Two consequences you must carry into your analysis:

- **A malformed response is a MEASUREMENT FAILURE, not an observation.** Record it as
  `measurement_failed` with the raw lines kept, and **remove it from the agreement
  computation and from `values_dispatched`** — never as `ok`, never as `fault`, never as an
  inertness reading. Refuse a field whose measurement failures exceed 1% of its dispatched
  values (EXP-0178 `analysis/verdicts.py` is the reference).
- **A false `hang` and a real inertness are indistinguishable in a summary.** If a sweep
  cascades after its first non-OK case, treat everything past the first one as suspect until
  it is re-measured on a per-child reader — and say so in `RESULTS.md` rather than reporting
  the cascade as data.

And the general form of the same caution, already learned here twice: **a clean result from a
stub is not evidence a defect is absent.** EXP-0179's offline stub did not reproduce the
shared runner's cascade — the race needs scheduling luck — and it recorded that as an
OBSERVATION, not a gate, relying on the structural fix instead. `selftest_tools.py` T3 keeps
that distinction.

**While writing your own promotion gate, one arithmetic trap to know:** a movement rule
written `moved >= 2.0 * max(disagree, 1)` **silently cannot promote ANY width-1 field** — with
zero disagreements the clamp still demands two moving values, and a 1-bit field has at most
one value that can differ from its baseline. EXP-0178 hit this in its own gate against its own
frozen text and it was suppressing `read_en`, the exact silent-zero read-enable the experiment
was dispatched to re-verify. The correct form is `moved >= 2.0 * disagree, and > 0`. Write the
gate's refusal cases before the gate, and re-read the gate against the frozen text rather than
against your memory of it. (Full write-up: `tools/agxtest/README.md`, final section.)
