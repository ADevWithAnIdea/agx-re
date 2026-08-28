# `raw/m4_20260828_run01` — retained, NOT used for any field verdict

This capture is **append-only evidence that is deliberately not promoted**. It is kept
because of what it found, not for what it measured.

**What happened.** `run01` was aborted by its own D4 periodic baseline re-validation at case
4500, the first time that check ran on the control-flow carrier. The unmutated skeleton
returned `acc*2` on **every** lane instead of the `acc > 100 ? acc*2 : acc-3` mix its
host-computed oracle predicts, and it did so on all three trials, with `STATUS OK` and no OS
fault string — a reproducible semantic mismatch, not a GPU cascade. The driver restarted the
runner process, re-checked, saw the same thing, and stopped rather than recording it as data.
That is exactly the behaviour `FIELD-SWEEP-PROTOCOL.md` §7.3 asks for.

**Root cause** (isolated by `work/pilot/pilot8.py`, disclosed, non-gated): the *carrier*, not
the sentinel. `kernels/carrier_cf2.metal` — EXP-0112's `carrier_cf.metal` plus a tail of extra
arithmetic on `acc` **alone**, adding no new buffer reference, which is precisely the padding
technique EXP-0128 proposed for this purpose but never dispatched — silently moves the constant
the reused skeleton's select compares against, with the sentinel prologue on *or* off, while
every `base_slot` value stays identical. Lengthening a control-flow carrier is therefore not
semantically neutral even when the documented `base_slot` trap is avoided.

**Disposition.** The CF arm was reverted to EXP-0112's own 152-byte `carrier_cf.metal` (which
reproduces the host oracle exactly on all eight lanes), the sentinel prologue was dropped on
that carrier for lack of room, the case matrix was re-frozen, and two fresh full captures were
taken under new run ids (`m4_20260828_run02`, `m4_20260828_run03`). Those two are the gated
evidence. The case indices in `run01` do not correspond to the re-frozen matrix, so `run01` is
not comparable to them and is cited only for the finding above.
