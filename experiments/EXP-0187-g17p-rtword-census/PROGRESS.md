# EXP-0187 — PROGRESS

## M1 — pre-registration frozen, harness verified on the device (2026-08-30)

* Pinned `db.json`, `isadb.py`, `agxparse.py`, `persistrun.py`, the **upstreamed**
  `saferunner.py`, `shdump.m`, plus EXP-0135's `shdump_mesh.m` / `mesh_extract.py`
  into `pinned/`, resolved by absolute path with a hard exit if absent.
* Authored 8 intersection_query carriers (`kernels/k_rq187.metal`) and 26 census
  constructs (cube / divergent-CF / mesh).
* **Census (target 1), on the device:** all 8 carriers compile and all 8 emit
  `n4_rt_word` — **32 parcel-aligned occurrences**, 3–5 per carrier, two distinct
  compiled `dst` baselines (`0x42` on seven carriers, `0x22` on `rq_inst`), i.e.
  both selector values `db.json` records from the corpus. Each carrier also has
  14 aligned `rt_query_traverse` occurrences for the carrier-level control.
  **3 of 32** occurrences are followed by an `if_push` (`rq_inst`), giving a
  same-program-point control; that matches `db.json`'s own provenance for this op.
* **Tokenizer walk stops at 60–62 tokens on every RT carrier**, so `walk` hits
  for `n4_rt_word` are 0 — a tokenizer limitation on intersection_query programs
  (EXP-0157 measured the same), NOT evidence of absence. Recorded, not hidden.
* **Pilot (`raw/prefreeze/pilot01`, 371 cases, 4.1 s):** harness end-to-end OK —
  8 carriers ready, sentinel present, poison tail intact, 0 hangs, 0 malformed.
  It found one defect: **my `rq_multi` host oracle was wrong** (124 vs the 121 the
  unmutated program returns in all 37 baselines). Corrected pre-freeze and
  documented; the gate compares against the arm-open baseline, never the oracle.
* Arms frozen: **211 arms / 10 272 cases** — 32 dense 256-value target arms, 64
  whole-word liveness probes, 3 same-program-point controls, 112 carrier controls.
* `CAPTURE_CONTRACT.json` frozen (27 blobs); `harness/verify_remote.py` run as a
  SEPARATE unchained step: **25/25 blobs match on the device**.

## M2 — gated runs
