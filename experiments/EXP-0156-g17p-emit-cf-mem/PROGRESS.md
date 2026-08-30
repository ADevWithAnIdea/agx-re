# PROGRESS — EXP-0156 (A18 Pro / G17P): CF, MEM, bf16/half

Timestamped milestone log. Written after every milestone so a kill costs at most one.

- **2026-08-30 ~04:5x UTC — dispatch received.** Read `CLAUDE.md`, `CODEX.md`,
  `SUBAGENT_BRIEF.md`, `NEO-TARGET-BRIEF.md`, `FIELD-SWEEP-PROTOCOL.md`,
  `docs/evidence-classification.md`, plus EXP-0140 / EXP-0141 `RESULTS.md` and
  EXP-0152 `PRE_REGISTRATION.md` (the never-captured CF/MEM predecessor).
- **05:0x — neo reachable** at `192.168.10.243`; `~/agxre/tools` present and built.
- **05:0x — harness ported.** EXP-0152's harness + kernels reused verbatim; new carriers
  added (`tg_tile.metal` = EXP-M4-14's `k_thr.metal`; EXP-0145's four bf16/half kernels).
- **05:1x — COMPILE-ONLY PILOT on G17P (no GPU dispatch).** Every M4-derived carrier
  assertion reproduced: CF skeleton 152 B, slots `a=2 n=1 out=0`, `CF_STARTS_EXPECT`
  exact; atomic sites exact; `tg_addr_compute` at +46 = `1c 02 00 00 00 00`.
  New finding recorded: our own decoder **mis-tokenizes** the 0x11 native-bfloat group,
  `hminmax`, and the 0x?8 high-half group, so those sites are pinned by exact bytes.
- **2026-08-30 05:18:58Z — PRE-REGISTRATION AND CAPTURE CONTRACT FROZEN.**
  `PRE_REGISTRATION.md` sha256 `f1e0ec2d959c820c…`; repo revision pinned
  `7dc67d768ada3c016771923bffd5b9647dd14813` (dirty: sibling experiments in flight).
  13 991 cases, 13 979 dispatched, 12 skipped as known-hang exclusions.
- **05:2x — SMOKE (`raw/smoke-s01`, 41 cases, retained, never used for a verdict).**
  Every carrier baseline matched its host oracle; every pre-registered falsifier fired
  except `attg.opctl` (byte+11 `0x04→0x05`, EXP-0141's M4 smax control, **inert here** —
  flagged as a possible cross-target difference). Headlines already visible:
  `tg_addr_compute` byte0 **`0xfc` REPRODUCES on G17P**; bf16 add/fma/max/half2-fma all
  numerically exact; bf16 rounding is **round-to-nearest-even** (`0x3F81`, truncation
  refuted); `h_alu_hi` corruption changes **only the high half** and `half_alu`
  corruption **only the low half**; the `jump_cond` liveness gate **FIRED** (n=0 +
  poison offset ⇒ no store at all, n=0 + natural offset ⇒ correct, mixed n + poison
  offset ⇒ correct). One reproduced GPU **hang**: `mask_op` spliced over `if_push`.
- **05:20–06:07 — gated captures, batch #1.** `tgac` pair complete and clean (**100.0%
  exact cross-run agreement, 0 hangs, 0 baseline failures**): byte0 **104/256 accepted
  including BOTH `0x1c` and `0xfc`**, byte+1 96/256 (a strict superset of EXP-0141's M4
  32-value rule), bytes +2..+5 **256/256 inert** in both runs. CF chunk 1 captured
  (`cf01b` jump_cond, `cf01c` if_push_pred/ret.scoreboard/mask_op).
- **DEVIATION 1 — `cf01a` killed by a transport failure**, retained as a partial with
  `raw/g17p-20260830-cf01a/PARTIAL.md`; successor id `cf01d`.
- **DEVIATION 2 — batch #1's remaining nine captures aborted in `baseline.py`** because
  the addendum carrier was pushed to the neo with `main_len: None` mid-batch. Those nine
  run ids are retained as empty directories and never reused; batch #2 uses new ids.
- **06:0x — CARRIER CONFOUND FOUND in the headline claim, and an addendum registered.**
  EXP-0141's contradicting M4 `tg_addr_compute` measurement was **not** made on
  EXP-M4-14's `k_thr.metal`: it used EXP-0141's own lane-0-fills-the-tile litmus with the
  op at **+422**. The two disagreeing records therefore differ in **both target and
  carrier**. `ADDENDUM-PREREG.md` frozen (both outcomes pre-registered) and a new arm
  added that runs **EXP-0141's own carrier byte-for-byte on the G17P**; a compile-only
  pilot confirms it reproduces EXP-0141's exact M4 offsets (+422 / +428) on G17P.
- **06:0x — `tools/agxtest/persistrun.py` re-copied to the neo** after the orchestrator's
  fix for its infinite `readline()` spin (old `fb057160…` → `cc53d8ef…`).
- **06:1x — batch #2 launched** (t141 ×2, bf ×2, mem ×2, mtg ×2, cf ×4).
- **06:2x — batch #2 complete.** `t141a/b` (addendum), `bf03/04`, `mem03/04`, `mtg03/04`,
  `cf01d`, `cf02d/e/f` all captured and pulled back.
- **06:3x — THE ADDENDUM SETTLES THE DIVERGENCE.** EXP-0141's OWN carrier, byte-for-byte on
  G17P, accepts **102/256** byte0 values including `0xfc` and the **identical 96/256**
  byte+1 set as `k_thr.metal`. Same carrier, same offsets, same oracle ⇒ **HA: the
  difference is the TARGET.** G16G accepts 1 byte0 value and 32 byte+1 values; G17P accepts
  ~100 and 96. First confirmed genuine G16G↔G17P hardware divergence in the corpus.
- **06:3x — CF SAFETY STOP FIRED.** `cf02f` hit 4 GPU hangs (`if_push_pred.level` 170/171,
  `ret.scoreboard` 0/4 — all four executed cleanly in the paired run `cf01c`, so they are
  NONDETERMINISTIC). The pre-registered budget stopped both arms and then every remaining CF
  arm. Per the dispatch's "stop after two", **all further CF work was stopped.**
  Consequence: `if_push_pred.level` and `ret.scoreboard` have one complete run and one
  truncated run, do not clear the gate, and are reported `untested` with their single-run
  observations published. `ret` therefore does NOT close; `ret_luse` does.
- **06:3x — analysis complete.** `analysis/{gate_report,field_verdicts,emittability}.json`,
  `manifest.json`, `RESULTS.md` written. **58/171 instructions and 549/1057 fields at
  emitter grade (from 50/171 and 513/1057).**
- **06:3x — two strengthening runs QUEUED on a heavily contended GPU lease**
  (`jcn1/jcn2` = `jump_cond` scope at the natural offset, `revbf1/revbf2` = the §7A
  lease-confirmed fault re-validation of the 154 bf16/half fault cases). Five agents are
  queueing for the lease. **No promoted verdict depends on either**: every promotion rests
  on an accepted-value set that both gated runs agree on case-for-case, and no promotion
  rests on a `fault` classification.
- **FINAL — analysis chain re-run end to end from `raw/` alone.**
  `analysis/verdicts.py` → `field_verdicts.py` → `emittability.py` → `make_manifest.py`.
  **59/171 instructions and 552/1057 fields at emitter grade** (from 50/171 and 513/1057).
  Nine newly emittable: `jump`, `jump_cond`, `pop_reconverge`, `ret_luse`, `atomic_mem`,
  `atomic_rmw`, `atomic_tg`, `bf_add_dst`, `hminmax` — four of them
  (`jump_cond`, `ret_luse`, `bf_add_dst`, `hminmax`) on **G17P evidence alone**.
  48 `hardware-run` field verdicts, 4 `untested`, 5 `db_defects`, 12 `insufficient`.
  Every number quoted in `RESULTS.md` was machine-checked against
  `analysis/gate_report.json`: **0 mismatches**.
  `db.json`, `validation.json`, `docs/`, `PROVENANCE.md` untouched; nothing committed.
- **§7A FAULT RE-VALIDATION PASSED.** All **154** cases both free-running bf16/half captures
  called `fault` were re-dispatched **inside the GPU lease, 5 replicates each, twice**
  (`revbf1`/`revbf2`, 0 hangs). **150/154 confirmed `fault`/`fault` at 5-of-5; 0 became
  `ok`.** The four exceptions are all `h2.h_alu_hi.b0` and still fault on their first trial
  — their `invalid_run` label is the sentinel failing *because* the fault left the buffer
  unwritten. Fault class is `kIOGPUCommandBufferCallbackErrorPageFault` (our own encoding),
  never `...ErrorInnocentVictim`. **No label, rule or count in RESULTS.md changes.**
  Contrast with EXP-0153, where 4 of 5 "reproducible" faults evaporated under isolation.
- **STILL PENDING:** `jcn1`/`jcn2` (the `jump_cond` scope sweep at the natural offset)
  remain queued behind eight `gpulease` waiters. Strengthening only; cannot weaken the
  gated poison-target verdicts. Fold-in commands are in `RESULTS.md` §13.2.
- **ADDENDUM §2 COMPLETE — `jcn1`/`jcn2` gated.** `jump_cond.cf_scope@NAT` and
  `.reserved@NAT`: **256/256 `ok` in both runs**, 0 hangs, 0 invalid runs, 3/3 baseline
  checks each, **100.0 % exact cross-run agreement**. Every case reproduced the exact
  fall-through oracle, so both fields are now inert **in a program that still computes its
  right answer**, not merely on taken-vs-not-taken. `field_verdicts.py` was fixed to pick
  the STRICTEST arm when two cover one field (it was silently keeping the weaker
  poison-offset arm because the `@NAT` gate keys were missing from its GATE table).
  `jcn1`'s first attempt exited 75 on a lease timeout — no directory, id never consumed.
- **`emittability.py` made drift-proof.** The orchestrator had already merged these
  verdicts into `validation.json` (commit `39520163`), which made the before/after delta
  collapse to zero. The baseline is now computed by **subtracting every EXP-0156-attributed
  label**, and the `db.json`/`validation.json` hashes are pinned in `emittability.json`.
  Totals also drifted under us (171→172 instructions, 1057→1060 fields) as db.json changed.
- **FINAL: delta +9 instructions, +44 fields** (52→61 of 172; 525→569 of 1060 at snapshot
  `db.json 83b83a35…`). 48 `hardware-run` verdicts, 4 `untested`, 5 `db_defects`,
  12 `insufficient`. `manifest.json --check` clean at 113 files. Nothing committed.
- **DEF-0156-1 — `RESULTS.md` DESTROYED BY A RUNAWAY WRITE, AND RECONSTRUCTED.**
  The edit that replaced §13.2 sliced `s[s.index("### 13.2 …"):s.index("## 14. …")]`, but an
  earlier edit had put §14 **ahead of** §13, so the slice was **reversed → empty string**,
  and `str.replace("", block)` inserts at every character position. Result:
  **83,178,232 bytes / 1,531,963 lines, only 116 unique lines** — the new §13.2 repeated
  ~50 000 times with the original characters interleaved singly between copies. Every other
  section, including the `# ` title, was gone.
  **Unaffected:** `raw/` (all 24 run dirs), every `analysis/*.json`, `manifest.json`,
  `PROGRESS.md`, both pre-registrations, `CAPTURE_CONTRACT.json`, `README.md`, `harness/`,
  `kernels/`. Exactly one file was hit; a repo-wide scan found no other anomaly.
  **Repair (document only, no hardware run):** restored from commit `2013bf66`
  (756 lines / 47,780 B), re-applied the post-commit edits **once each** with every
  replacement asserting a non-empty anchor occurring exactly once, lifted §13.2 verbatim
  from a surviving copy, and corrected the §13/§14 inversion that made the reversed slice
  possible. **Some post-commit prose may not be recovered verbatim** — recorded in
  `RESULTS.md` §16, not papered over. Every figure was re-checked against the untouched
  `analysis/*.json`.
- **Also recorded: three defects in this experiment's own analysis code** (`RESULTS.md`
  §15) — the missing `@NAT` GATE entries that kept the weaker arm, first-seen-beats-strictest
  de-duplication, and an emittability baseline that read our own already-merged rows back.
