# EXP-0159 — progress log

Target **A18 Pro / G17P** (`192.168.10.243`), all timestamps UTC.
Six Part-II questionnaire items: `P2-06`, `TEX-01`, `TEX-19`, `TEX-21`, `TEX-22`, `MEM-19`.

| when | milestone |
|---|---|
| 2026-08-30 05:2x | Read `CLAUDE.md`/`CODEX.md`/`SUBAGENT_BRIEF.md`/`NEO-TARGET-BRIEF.md`/`FIELD-SWEEP-PROTOCOL.md`/`work/UNATTENDED-RUN.md` + the six item texts and their "areas already covered". Neo reachable, toolchain present. |
| 2026-08-30 05:3x | **Pre-freeze feasibility probe** (`raw/prefreeze/`, NOT evidence): MSL `double` rejected; `array<texture2d,1000001>` compiles; 20k distinct samplers in 0.01 s and identical descriptors dedup to one ID. These three facts made the contract specifiable. |
| 2026-08-30 05:4x | `PRE_REGISTRATION.md` written and frozen; six probe families FA..FF with hypotheses, oracles, refuters, positive controls. |
| 2026-08-30 05:4x | Harnesses authored + built on the neo: `mslprobe`, `bindtex`, `sampheap`, `texrun`, `run.py`. |
| 2026-08-30 05:4x | Smoke `smoke01` (FA): 48/48 as predicted. |
| 2026-08-30 05:4x | Smoke `smoke02` (FC): indexing exact to 999,999; found and fixed a canary-value collision and added majority-of-3 (a `...ErrorInnocentVictim` from a sibling agent appeared at index 500000). |
| 2026-08-30 05:5x | Smoke `smoke03`/`smoke04` (FD): six-class fingerprints collided -> redesigned the discriminator (out-of-range coordinate x address modes x lodMaxClamp = six distinct non-zero values); ceiling walk extended to 2,000,000 because 500,000 was never reached. Added an unwritten-output retry after one dispatch reported OK with the poison intact. |
| 2026-08-30 05:5x | Smoke `smoke05` (FB): carrier located on G17P — `iadd2` at `_agc.main+0x20`, bytes `1f015600020800501705`, byte-identical to EXP-0146's M4 carrier. Positive control fired. Strict FP64 verdict added (one binary64 op must reproduce all four rows). |
| 2026-08-30 05:5x | Smoke `smoke06` (FE): first `slot31` carrier put every load in `_agc.main.constant_program` (832 B) and left `_agc.main` at 30 B — no spliceable probe. Fixed with thread-varying indexing; the constant-program version is KEPT as a second, directly MEM-19-relevant measurement. `buffer(31)` rejected: "must be between 0 and 30". |
| 2026-08-30 05:5x | Smoke `smoke07` (FF): first carrier compiled to a bare `tex_sample` with NO `tex_addr_setup`; fixed by making coordinates and LOD thread-varying. Positive control fires (form 0x05, w 1->2 gives 1100->2000). **form 0x01 is invariant in the third operand at every tested value** — the refuter the pre-registration named. |
| 2026-08-30 05:58 | `CAPTURE_CONTRACT.json` frozen (50 authored sources); `analysis/verify.py --preflight` PASS. **Gated `g17p-20260829-run01` launched (all six families).** |
| 2026-08-30 06:0x | Gated `run01` complete (all six families). `run02` launched. |
| 2026-08-30 06:0x | `run02` complete **except family FE**, whose very first unmutated baseline dispatch was killed by a concurrent GPU error; `run.py` recorded `__probe_not_isolated` and stopped rather than sweeping against a broken baseline. Partial capture **retained unmodified**, not reused. |
| 2026-08-30 06:1x | Post-registration passes: `fe-iso01` (FE re-captured under `gpulease.sh`; 256/256, mirror 128/128 exact, all 30 slots resolved), `adv01` (**complete 256-value `tex_addr_setup.form` sweep** — 0 projective matches), `fbc01` (217 doubly-faulting FB encodings re-run 5× = 1,085 executions, 0 FP64 hits). `fbc02`, the lease-isolated repeat of `fbc01`, queued behind EXP-0156's lease. |
| 2026-08-30 06:1x | Cross-run gate: FA/FC/FD/FF **0 disagreements**; FB 20/2645 (all one class: one run wrote nothing); FE run01-vs-iso 5/281 (all contamination-class). Controls fired in every family in both runs. |
| 2026-08-30 06:2x | `analysis/verdicts.json`, `analysis/questionnaire_answers.md` (six blocks, every anchor `grep -Fxc` = 1), `RESULTS.md`, `README.md`, `manifest.json` written. `raw/prefreeze/feasibility.txt` captured for the record. |
| | **6 of 6 items closed on G17P.** P2-06 No · TEX-01 No (+ db-defect) · TEX-19 Yes · TEX-21 Yes · TEX-22 answered (4 parts) · MEM-19 answered (3 parts). |
| 2026-08-30 06:3x | `adv02`: the 256-value `tex_addr_setup.form` sweep repeated on the **2D-array** carrier — same result, **0 of 256 projective matches**, 32 operand-dependent values, all `(form & 7) == 5`. TEX-01's negative now holds on both carriers. |
| 2026-08-30 06:4x | The lease-isolated repeat of `fbc01` was attempted **three times** and timed out every time waiting for `gpulease.sh` under continuous sibling contention (EXP-0156, EXP-0158-run03). Recorded verbatim in `raw/g17p-20260829-fbc01/LEASE_ATTEMPTS.txt`; the unlocked 1,085-execution pass stands, and RESULTS says plainly that the §7A isolated confirmation was NOT obtained. |
