
---

## 10. How this method could have failed to say "no"

1. **Agreement between two runs of the same program on the same machine is nearly guaranteed,
   so a high agreement number is weak evidence that quiet mattered.** The proof is inside this
   experiment: EXP-0202's *quiet* forward capture agrees with a *busy* committed capture
   **9686/9686 = 100.00 %**, with byte-identical hard-outcome counts. What actually moved when
   the machine went quiet was never the payload agreement — it was the **hard outcomes**
   (EXP-0203's 1398-case `ok` inflation from a lost anchor; EXP-0205's single sibling-induced
   fault). **If contamination had corrupted payloads rather than faults, my method would still
   have reported 100 % and I would have had no signal at all.** Everything here therefore
   establishes *"the confirmation was taken on a quiet machine"*; it does **not** establish
   *"quiet changed the answer"* except where a hard-outcome count changed, and those cases are
   named individually.

2. **The quiet metric samples at 2 s.** A foreign GPU client that starts, submits and exits
   between two samples is invisible to Q1 and to Q3. `recoveryCount` (Q2b) would catch it only
   if it caused a reset. The machine sat at the login screen with `SecurityAgent` as the last
   submitter, and the long EXP-0202 capture carried 401 samples, so the residual risk is small
   — but it is not zero, and it is a real hole rather than a hypothetical one.

3. **Cross-run agreement compares the `observed` payload only,** with timing stripped.
   Contamination expressed in a record field outside `observed`, or inside a stripped timing
   field, is invisible to it. Hard outcomes are counted separately and compared, which covers
   the failure mode the corpus has actually seen, but not every conceivable one.

4. **The pair key is not unique in every experiment.** EXP-0202 has **6** duplicate
   `(arm, field, value, carrier, instr, sub)` keys — all `cvt_f2i` `mode = 0` *control*
   records, present twice. The comparator compares the first record per key, so a disagreement
   confined to a duplicate would be masked. It is reported as `key_unique: false` in every
   comparison JSON rather than smoothed over.

5. **Reversing case order controls ordering artefacts, not carrier blind spots.** Two runs of
   the same harness on the same machine share every systematic error the harness has. Gate E's
   further clause — *"for load-bearing inertness or a surprising semantic claim, require a
   genuinely different carrier or second method as well"* — is **NOT satisfied by this
   experiment for any row**, and specifically not for the inert rows
   (`tex_write.amode`, `tex_write.rsv11`, EXP-0206's inert rows). This experiment can move
   those rows past the *quiet* clause and no further.

6. **All three amendments moved a criterion in the direction of "quiet".** Each was frozen
   before the dispatch that used it and each superseded capture is retained unrescored, but a
   reader should weigh that they all loosened or re-attributed a failing conjunct rather than
   tightening one. The strongest defence available is that A01 and A02 are demonstrable
   attribution bugs (an XPC parent, a two-`ps` race) and A03 is a gate that provably could not
   pass any fault-heavy experiment — but a reader who thinks I rationalised should look at
   `AMENDMENT-0{1,2,3}.md` and the retained captures and judge.

7. **Only Gate E was re-run.** Gates A, B, C and D are inherited from each source experiment
   unchanged and were **not** re-audited here. If one of those is wrong, a MET verdict from
   this experiment does not rescue it.

8. **`fLastSubmissionPID` is a *last* value,** so the first samples of a capture legitimately
   name the previous capture's runner, and one signal is degenerate on this host:
   `Device Utilization %` reads a constant 100 with an idle GPU, zero submitters and
   Renderer/Tiler at 0. Q3 is therefore weaker at the start of each capture than it looks, and
   the four-signal design is really a three-signal design.

9. **I did not kill the one orphan process on the machine** (EXP-0202's leftover `gpuwatch.py`
   sampler, PID 7480, ppid 1). It issues `ps` and does no GPU work, and it is disclosed in
   every sample — but it is a foreign process that ran throughout, and "the machine was
   completely idle" is therefore not literally true.
