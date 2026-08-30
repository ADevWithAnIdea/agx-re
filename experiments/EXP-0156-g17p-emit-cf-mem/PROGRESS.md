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
