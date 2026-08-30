# g17p_20260829_run01 — PARTIAL, RETAINED, NOT REUSED, NOT USED FOR PROMOTION

Stopped by hand at **33,185 / 52,090+ cases**, 24 of 41 arms, ~28 minutes in.

**Why.** Twice during the run the device entered a window in which nearly every
command buffer came back `kIOGPUCommandBufferCallbackErrorInnocentVictim`
("Discarded (victim of GPU error/recovery)"). Because the harness retried a
foreign fault 8 times *and* then applied the majority-of-3 confirmation on top,
one contaminated case cost about **45 seconds and 24 renders**, and throughput
collapsed from ~105 cases/s to under 1 case per 100 s. The first window followed
a *genuine, reproducible* hang of our own —
`tex_sample.tex_type = 32` on the `t_texops` gather occurrence, 3/3
`kIOGPUCommandBufferCallbackErrorHang` — and the second appeared during
`iter_at@cent1_0.grp`, whose low seven bits are the instruction's own match bits.

Both windows were transient: immediately after the stop, unmutated renders of
`c_iter` and `t_sample` returned `STATUS OK` with the correct pixels, so the
device was **not** wedged and no other agent's run needed to be warned off.

**What this capture is.** Append-only evidence, retained exactly as it was
written, of 24 arms including every `vary_slot` arm and six of the nine
`tex_sample` arms. **It is not used to promote any field.** The two gated runs
that the verdicts are computed from are captured under NEW ids
(`g17p_20260829_run02`, `g17p_20260829_run03`) with the harness fix below. This
directory is never topped up and its id is never reused.

**The harness defect it exposed, and the fix.** `run_confirmed` applied the
majority-of-3 rule to results the runner had *already* classified
`FOREIGN_FAULT` after its own 8 retries. Re-running an InnocentVictim three more
times cannot change its verdict — `classify()` maps
`os_class == "InnocentVictim"` to `foreign` unconditionally — so the extra 24
renders bought nothing and made the contaminated window last far longer than it
needed to. Corrected in the successor runs:

1. a result already classified `FOREIGN_FAULT` returns immediately, with its
   retry count recorded, and is **never** re-confirmed;
2. the foreign backoff is 0.25·(n+1) rather than 0.4·(n+1) seconds;
3. a **cascade guard**: after 8 consecutive `foreign` outcomes the driver
   settles for 3 s and re-validates the arm's unmutated baseline. If the
   baseline holds, the cascade is external and the sweep continues (recorded);
   if it does not, the arm is stopped, exactly as FIELD-SWEEP-PROTOCOL §7.3
   requires.

None of the three changes alters how any outcome is CLASSIFIED. They change only
how many redundant GPU submissions a contaminated case costs.
