# EXP-M4-14 — A18 splice-and-observe: resolve the last raw encoding bits

**Goal:** close the residual `type=raw` instruction-encoding bits that compile-only
byte-diff on the M4 could not pin, by **splice-and-observe on the live A18 Pro**
(the M4 was compile-only — no reboot escape; the A18 is reboot-recoverable via
`macvdmtool`, so GPU dispatch of hand-modified encodings is safe there).

**Method (clean-room, OWN-SHADER hardware probing — the Rosenzweig technique):**
for each op with raw bits, author minimal MSL that emits it, compile with our own
`shdump`, splice systematically-varied bytes into those bit positions with our own
`agxtest`/`agxrun`/`agxrender` harness, dispatch on the A18, and read back the
output. The bit's role is inferred from the observed output delta (a register index
shifts which input is read; a mode/enum changes the operation; a no-effect bit is a
first-class **reserved/inert** negative result). Faults on G17P are **contained**
(the device survives, next dispatch works) — the whole campaign ran with **0
reboots**. No Apple binary is ever inspected; only our own compiled shaders.

Run as 4 parallel groups on isolated device workdirs (`~/cleanroom_work/splice_*`):
fragment, half/int ALU, RT/texture, address/frame. Structured findings +
per-field splice evidence (inputs, spliced bytes @offset, observed output) are in
`splice_results.json`; the own-MSL provocation kernels are in `corpus/<group>/`.

## Result

56 HW-validated field resolutions integrated into `tools/agx-isa/isadb.py`
(provenance upgraded to `HW-VALIDATED (splice, A18 EXP-M4-14)`). Own-corpus raw
bits 1.94% → 1.34%; third-party → 0.79%. Round-trip ALL PASS; tokenization
byte-identical (only raw→named bits moved). Highlights:

- `frag_color_pack` format word → per-component present-mask / gate-select / scale
  (pixel-change-proven; `0xff` present-mask faults the GPU).
- `iunary`/`ibitcount` sub-op selector corrected (byte0 bit7 + byte+1 `form`, not
  byte+4 — the prior popcount-vs-find_msb label was wrong).
- `half_alu` family: saturate bit, `hfma` op-select, source-negate modifiers.
- `tex_addr_setup` `form` (coord-proj / explicit-LOD / raw-coord), operand regs.
- `link_save_restore` `dir_offset` = SAVE (0x0000) / RESTORE (0x1fff).
- `get_sr` SR selector reconfirmed (`0xc5`=[[front_facing]]).
- Honest negatives: several bytes verified inert → typed `reserved`.

## Known floor (left raw with honest reason)

- `op04_len8` (was mis-named `frag_pos_read`): renamed — position/facing actually
  lower to `get_sr`+`iter`; this 8-byte `0x04` op appears only in third-party bytes
  our compiler never emits, so its body can't be provoked to splice-type. Its
  length rule is heterogeneous (byte+2 mixes real op-leaders) with no
  provably-regression-free shorter length — flagged for a context-aware length pass.
- `half_alu_fma12.ext`, `falu2_ext8b.exttail`: length over-consumption (the
  descriptor length absorbs a following op's bytes) — HW-corroborated; a length
  correction, not field typing.
- `rt_query_traverse.opA`, `ray_move` value-semantics: inert to the observable
  output sink, so unresolvable by observation.
