# raw/superseded/ — stopped runs, kept because they measured something

Nothing here is deleted or edited. A run in this directory was stopped before
completion and is preserved because **its observations are the evidence for a
correction made to the harness afterwards** — which is exactly the situation in
which deleting it would destroy the justification for the change.

## `rrun01_partial_192-197_band_unknown`

Render gated run `g17p_20260830_rrun01`, stopped after **3 of 19 arms / 545
cases / 9 hangs**. Two findings came out of it, both of which changed the
pre-registration before `rrun02` was launched (see `PROGRESS.md` M19):

1. **`frag_color_pack.dst`'s hazardous band is contiguous 194..197.** The
   prefreeze smoke had measured 194 and 196 hanging; this run hung at **195 and
   197** as well, on three arms each. Because only 194/196 had been deferred to
   the end of the dispatch order, the sweep walked into 195, hung, walked into
   197, hung, hit the two-hangs-per-field budget and stopped at 197 — leaving
   `198..255` unswept for the third time across three experiments. The deferral
   band was widened to 192..197.
2. **`src_present_mask = 0xff` HANGS on G17P**, 3 of 3 arms, where EXP-M4-14
   recorded a contained command-buffer fault (device survives) on A18. A
   cross-target refutation. With 8 `frag_color_pack` arms it would also have
   spent a third of `MAX_HANGS_TOTAL` re-confirming itself before any other
   instruction family ran, so that falsifier became `once_per_carrier`.

The run name records what it did not know at the time.

## `rclean02_partial_order_unfixed`

Stopped after 21 cases. Same ordering defect as `rclean01` for `iter_at.grp`
(out-of-descriptor values dispatched before the two legal ones), superseded by
the `coverage_for(first=...)` fix.

## `rclean05_abandoned_machine_contention`

Abandoned at ~35 cases. Not a harness or hardware problem: the neo was
simultaneously hosting EXP-0169, EXP-0171 and EXP-0172, and `ps` showed 23-39
concurrent `agxrun_persist` / `gfrun` processes. Render throughput fell from
**31 cases/s** (rclean01: 2,632 cases in 85.1 s) to **~0.07 cases/s** — a ~400x
slowdown that would have made the second gated run take ~10 hours. Kept as the
measurement of that contention; `gpuwatch.jsonl` in each run records the
concurrent process table for the same reason.
