# EXP-0210 — AMENDMENT 02, frozen 2026-08-30 before its first dispatch

**Trigger.** `raw/e0205_q02` (EXP-0205 reverse capture `g17p_quiet02`, retained, never reused)
scored `n_foreign_runner = 1` in **1 of 18** samples. The single row is:

```
pid 26051  comm "(shdump)"   ours=False  kind=runner  new_since_start=True
```

The parenthesised comm is macOS's rendering of a process that is **exiting/zombie**. PID 26051
falls inside the contiguous block of PIDs our own capture was spawning at that instant
(25936 … 26064), it appeared after the sampler started, `fLastSubmissionPID` never left our
own runners, `fBusyCount` was 0 in every sample and `recoveryCount` was 12977 at first and
last sample.

**The cause is a race in this instrument, not a process on the machine.** `own_pids()` and
`proc_rows()` each ran their **own** `ps`. A short-lived child that exists in the second
snapshot but not in the first — or whose parent link is being torn down between them —
cannot be matched to our subtree, and is therefore scored foreign. Our captures spawn one
`shdump` per carrier, so this race is structural, not a one-off.

## What changes

1. **One snapshot.** A single `ps -Ao pid,ppid,pgid,sess,stat,%cpu,comm,args` serves both the
   ownership walk and the row scan, so a process can never be classified against a process
   table it does not appear in.
2. **Ownership by session, not only by parent.** A row is `ours` if it is in the sampler's
   `ppid` subtree **or** shares the sampler's session id. Every process this capture creates —
   `drive_one.sh`, the sampler, the capture command, `run.py`, its runners, their `shdump`
   children, and any of them in the middle of exiting — is in the sampler's session. A
   sibling experiment run from another SSH login is in a different session. This is strictly
   more accurate than a `ppid` walk and it survives reparenting and zombie reaping.
3. **Exit state is recorded.** Each row carries `stat` and `exiting` (comm parenthesised), so
   a dying process is visible in the raw rather than being silently folded into either class.

**Q1 is UNCHANGED: `n_foreign_runner == 0` in every sample.** This amendment changes only how
"ours" is determined, and it does so by removing a measurement race — not by relaxing the
criterion. Q1b, Q2, Q3, Q4 are unchanged.

## What this amendment may NOT do

It may not be applied to data already seen. `raw/e0205_q01` and `raw/e0205_q02`, and the
captures `EXP-0205/raw/g17p_quiet01` and `g17p_quiet02`, are retained **exactly as captured**,
are **not** re-scored under the amended attribution, and **do not** support a Gate E verdict.
EXP-0205's pair is re-dispatched under new run ids (`g17p_quiet03` / `g17p_quiet04`).
`EXP-0203`'s pair `g17p_q43`/`q44` already measured `n_foreign_runner = 0` under Amendment 01
and is **not** re-dispatched: this amendment can only ever move a row from foreign to ours, so
it cannot turn a measured-quiet capture into a busy one.

Frozen before the first dispatch that uses it.
