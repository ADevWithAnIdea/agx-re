# EXP-0139 PROGRESS (append-only; timestamped per milestone)

## M0 — 2026-08-28 — orientation
Read `CLAUDE.md`, `CODEX.md`, `experiments/SUBAGENT_BRIEF.md`,
`experiments/FIELD-SWEEP-PROTOCOL.md`, `docs/evidence-classification.md`.
Extracted the blocking-field list for the 16 integer-ALU mnemonics from
`tools/agx-isa/validation.json` vs `db.json`: **137 blocking fields confirmed**
(iadd2 12, ibfe 16, ibfe_mesh_attr 3, ibfins 12, ibitcount 1, icmp_pred 6,
icmpsel 12, imad 15, iminmax 6, isel10 10, isel10_c 10, isel8 8, isel_reg 9,
isel_reg8 7, ishift 9, iunary 1).
Read the load-bearing prior results: EXP-0128 (iadd2 register mode), EXP-0102
(`extract_bits` three-way contract), EXP-0129 (`ibitcount` srcdesc bit4),
EXP-0113 (`iminmax` nondeterminism), EXP-0112 (register aliasing, mov_imm 4-bit
dst), EXP-M4-14 (ibitcount splice sweep).

## M1 — 2026-08-28 — pilot: tooling + carriers  (DISCLOSED, NON-GATED)
`work/pilot/` (retained). Built `work/bin/{shdump,agxrun_persist,agxrun}` from
the unmodified repo tool sources.
- `p1_smoke.py`: reproduced EXP-0128's `iadd2` register-mode rule on a
  SYNTHESIZED program (N=2/7/0, dst=5/40/6 -> 30/77/42) and got a clean
  synthesized `ibitcount` popcount (85->4, 127->7, 1->1). **`db.json`'s
  `mov_imm` descriptor has since been renamed `imm8` -> `imm7`+`imm_top`
  (EXP-0128's own finding landing in the DB); EXP-0128's copy of
  `isa_helpers.mov_imm` therefore no longer assembles. Fixed in this
  experiment's own copy, documented at the call site.**
- `p2/p4/p6_recon*.py`: compiled 30 authored MSL probe kernels and tokenized
  each `_agc.main` with `tools/agx-isa`. Located live anchors for **13 of the
  16** target mnemonics. NO anchor anywhere in our own compiled corpus for
  `ibfe_mesh_attr` (fragment/mesh-stage only), `isel_reg8`, `iunary`.
- `p7_time.py`: throughput on the persistent runner measured at **~0.7 ms per
  dispatch** for these small carriers -> a full dense sweep is affordable.
- `p8_iunary.py`: **found live `iunary`-tokenizing members** by construction
  (byte0=0x27, byte+1=0x2d/0x35/0x3d, byte+2 anything but 0x54/0x56 -> the
  tighter `ibitcount` match loses). They still compute popcount and their
  operand bytes are LIVE, so `iunary.operand` is sweepable after all.

## M2 — 2026-08-28 — harness frozen
`harness/{sweeprun,anchors,casematrix,run,verify}.py`, `kernels/ialu_probes.metal`,
`kernels/carrier_dag.metal`. `verify.py --selftest` = 457 checks PASS with no
device. Case matrix: **29,685 cases**, matrix_sha256 recorded in
`CAPTURE_CONTRACT.json`. 40-case smoke run confirmed real dispatch (the `dst`
relocation model flips exactly at dst=12/13 = r6) and was then deleted as
pre-freeze pilot output.

## M3 — 2026-08-28T09:39:08Z — PRE_REGISTRATION.md + CAPTURE_CONTRACT.json FROZEN
sha256 PRE_REGISTRATION.md = be3a1b0b7ccf96407b53a12fd02e6ac7f79c95c3ce2f69f163caf2db462a1fb5
sha256 CAPTURE_CONTRACT.json = 6449e6d859f84639ed06b15050c95f1ba121302f647f388441e7a8efd3e27511
matrix_sha256 = 8bb3683479d3fa1540725406a2e321db7bbdccc9428ea696f7f3b16c0f19fdd5 (29,685 cases)
Starting gated run01.
