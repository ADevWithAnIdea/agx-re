# `raw/g17p_20260830_run01` — DEFECTIVE, RETAINED, NEVER REUSED

**Status:** defective capture. Retained exactly as it landed (8 records). Its run id is
**burned** and is never topped up, deleted, or reused (`SUBAGENT_BRIEF.md`: *a partial capture
is retained, never reused*). The gated pair is `g17p_20260830_run03` / `run04`.

## What it contains

8 records from the `sr_compute` arm: `arm_meta`, `baseline` (**ok**), two `ladder` steps
(both **moved**), the `power_probe` (**silent_zero**, i.e. the litmus landed), then the
`sensitivity` falsifier and one `sr_sel` case, both **`measurement_failed`**.

The first six records are sound and agree with the pilots. Nothing after the falsifier is an
observation.

## Root cause — a closure-shadowing defect in this experiment's own harness

`harness/run.py` bound the compute arm's read-back **size** as

    nb = SP.CGRID * 4                      # 256

inside the compute branch, and the `raw_case` closure passed it as
`outs={0: nb, 4: nb}`. A closure resolves a free variable **at call time**, not at definition
time. Later in the same enclosing scope the falsifier block rebound the same name:

    nb = bytearray(blk0); nb[0] &= ~0x04

so from the moment the falsifier executed, every subsequent request asked the runner for a
read-back of *a bytearray* bytes, and `"%d:%d" % (idx, nbytes)` raised
`TypeError: %d format: a number is required, not bytearray` inside the request builder.

## Why it survived four pilots — and why it is a DEF-0178-1 lesson, not just a bug

The failure **presented as a hang cascade**: one clean case, then every later case unrecoverable
with `restarts=99`, including the unspliced health check. That is byte-for-byte the signature of
the shared-driver reader-thread defect I had just diagnosed and fixed, so the pilots' evidence
was read as "the fix is not taking effect" rather than "a second, independent defect produces
the same signature". The tell was there and was missed twice: the exception text changed from
`not enough values to unpack (expected 3, got 2)` (the shared parser) to
`%d format: a number is required, not bytearray` (a different call site entirely).

**What actually resolved it was the instrumentation, not the reasoning.** Adding
`traceback.format_exc()` to the runner-exception handler named `saferunner.py:188` on the first
run that hit it. Before that, four pilots produced the same three-word symptom and no location.

Two general lessons, both recorded in `RESULTS.md`:

1. **Two independent defects can share one signature.** Having just fixed a cascade-shaped
   defect makes the next cascade-shaped defect *harder* to see, not easier. The discipline that
   works is to check the exception's *identity* — text, call site, stack — not its shape.
2. **`measurement_failed` earned its keep before it measured anything.** Because a malformed
   runner response was already classified as a non-observation rather than a `hang` or a
   `fault`, this defect could never have entered a verdict as an inertness reading on
   `get_sr.sr_sel`. Under the pre-amendment classifier it would have been recorded as
   `fault` — a harness bug promoted to a hardware claim.

## The fix, and the check that generalises it

Both names are now unique and deliberately dissimilar (`out_nbytes`, `sens_block`), and
`harness/selftest.py` gate **G10** now walks `run.py`'s AST and fails if any name a nested
closure reads is assigned more than once in the enclosing scope — the defect class, checked
mechanically, offline, with no device. Running it over the fixed file found three further
candidates (`mnem`, `off`, `runner`); all three are assigned in mutually exclusive branches of
the same `if`/`else` and are safe, and G10 carries them as an explicit allow-list with that
reason rather than being weakened to ignore them.
