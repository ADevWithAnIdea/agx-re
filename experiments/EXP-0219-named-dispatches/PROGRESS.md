# EXP-0219 — PROGRESS

| UTC | milestone |
|---|---|
| 2026-08-30 ~21:5x | Read the five normative documents + EXP-0218 / EXP-0213 RESULTS. Device reachable at 192.168.170.254, idle: `recoveryCount` 25401, `fBusyCount` 0, `fLastSubmissionPID` 328 (login window), 11 MB in use. |
| 2026-08-30 ~22:00 | **Desk step B0** (no device): `analysis/desk_mode_instability.py` + `desk_class_maps.py` over EXP-0213's three committed quiet orders. Every unstable `tex_sample.mode` value has **bit 6 set** and **bit 3 clear**; the instability is confined to `bit6=1 & bit3=0 & bit2=0` (32 of 256 values/arm); the alternative payloads are "a channel reads 0" or "a channel's float has its LOW 16 BITS ZERO". |
| 2026-08-30 22:0x | `PRE_REGISTRATION.md` written and frozen. |
| 2026-08-30 22:0x | Authored `kernels/probes_imad.metal` (new), `kernels/carrier_const.metal` (new, 48 constants with hand-chosen distinct halves), copied `kernels/carrier_dag.metal` from EXP-0160 byte-identical. Harness pushed; **remote hashes verified separately**, 13/13 identical. |
| 2026-08-30 22:09 | **Pre-freeze calibration**: `imad` anchor `9f00560002080060d02e0a00` at `_agc.main+32` of 62, 0 leftover; region lengths dag 2412 / const 1844; block offset 52. `CAPTURE_CONTRACT.json` frozen. |
| 2026-08-30 22:09 | Pilot `g17p_e0219_A_pilot01` (80 cases) — retained, supports no verdict. Gate A 80/80. |
| 2026-08-30 22:10 | Capture `g17p_e0219_A_dag_run01` (forward, 2058 cases, 1.4 s, 0 hangs, 0 faults, recoveryCount 25401→25401). Fitted `FILE[0..31]` **reproduces EXP-0218's published table exactly**. |
| 2026-08-30 22:11 | Captures `A_dag_run02` (reverse), `A_const_run01` (forward), `A_const_run02` (reverse). All four: Gate A 100 %, 0 hangs, 0 faults, 0 victims, recoveryCount delta 0. |
| 2026-08-30 22:1x | Part-A scoring. **A1 settled (bit 3), A2 settled (index wider than 5 bits), A3 settled (WORD not pair), A4 settled (immediate branch holds over all 32 K on G17P).** Corrected model 2054/2054 and 1158/1158 in both runs. |
| 2026-08-30 22:17 | Part B: copied EXP-0204's harness + kernels **byte-identical** (`work/exp0204_copies.sha256`), authored `kernels/k_msread1.metal` (one-read carrier) and `harness/run_b.py`. Pushed; remote hashes verified separately, 12/12 identical; `gfrun4` built in this experiment's OWN tree on the neo. |
| 2026-08-30 22:17 | **§3z stop-ruler** `g17p_e0219_B_ruler01`. 3 of 9 arms are `scan`-located (`msfilt/0`, `mslodq/0`, `mslodq/1`). A `stop` halts at **+0 and +14 on all 9 arms**; the halt payload is calibrated against a `stop` at fragment-stage offset 0. Precondition MET, claim kept one-sided. |
| 2026-08-30 22:18 | `g17p_e0219_B_rep_run01` (forward, adjacent, N=16) and `..._run02` (reverse, **interleaved**, N=16), 9405 records each. Gate A 9369/9369 each. **M-B2 and M-B3 refuted**; bit6-clear control 0/33 unstable on every arm. |
| 2026-08-30 22:21 | `g17p_e0219_B_sweep_run01/02`, full 256-value sweep, 9 arms, two orders. Bit 6 live on 4 arms, inert on 5. **Every cross-order disagreement has bit 6 set and bit 3 clear** — EXP-0213's Gate E failure explained. |
| 2026-08-30 22:23 | `AMENDMENT-01` frozen (sha256 a4d45fb2…) **before** `g17p_e0219_B_rep_run03` (N=24). Prediction held out: 64/64 sequences have smallest period 4 or 8, 0 aperiodic, 0 divisibility violations. |
| 2026-08-30 22:25 | `AMENDMENT-02` frozen (sha256 d3d71ec6…) **before** `g17p_e0219_B_rep_ctl04` (one arm, one GPU context). Effect survives: 32/32 unstable, 31/32 period exactly 4. Sibling-context confound refuted. |
| 2026-08-30 22:3x | Scoring, `analysis/field_verdicts.json`, `manifest.json`, `RESULTS.md`. **Device cost for the whole experiment: recoveryCount 25401 → 25401, 0 hangs, 0 faults, 0 victims, 0 device resets, `macvdmtool` not used.** |
