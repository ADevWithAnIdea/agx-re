# RT-ISA-FIX: batched ISA-DB fix — apply red-team corrections + decode the 0x0f exec-mask family

- **Date:** 2026-07-07
- **Clean-room category:** OWN-SHADER + HW-PROBE (only our own MSL compiled; only our own compiled bytes inspected/spliced/run)
- **Phase / question:** ROADMAP G-13 (instruction census → ~0 undecoded groups); apply RT-5 / RT-1b / RT-7 red-team findings
- **Device:** Apple A18 Pro / G17P, macOS 26.6 (25G5043d), 5 GPU cores. 0 reboots.

## Hypothesis
Three RT-5 "DB decode-bug" corrections (ballot `0x17`, shuffle byte+2 gate, reduce byte+7 dtype) and the RT-1b
"`0x0f` execution-mask family near-whole undecoded" gap can each be **independently HW-re-validated** (or
falsified) on a fresh compile, and the family can be decoded (length + descriptors) so if/else/loop/break/
continue/nested-divergence shaders tokenize cleanly. RT-7 doc corrections (uniform source, r96+, occupancy
tier, threadgroups_per_grid) and RT-5 doc corrections (texture op+4/op+6, rt_intersect sub-fields) are
prose-only.

## Method (clean-room legal)
Compile our own MSL kernels (`kernels/*.metal`) with `tools/shdump` (`--no-fast-math`), extract the compute
`_agc.main` AGX bytes (`agxparse.py --extract-hex`), and (a) decode them with the current `tools/agx-isa` DB to
reproduce each reported bug, (b) **HW-splice-and-observe** with `tools/agxtest` (`agxtest.py`, forces the
archived/ spliced machine code via `MTLPipelineOptionFailOnBinaryArchiveMiss`) to prove which bytes are
load-bearing, then (c) fix the DB and re-run the round-trip test. No Apple binary is disassembled; every byte
is from MSL we wrote.

## Procedure
- Device workspace `~/cleanroom_work/isafix/` (tool sources copied from repo, built with Command Line Tools).
- `build_extract.sh` — compile+extract every kernel → `raw/all_hex.txt`.
- `analyze.py` / `hyp.py` / `split.py` — tokenize the extracted bytes, catalog the `0x0f` sub-ops.
- `census_cf.py` — before/after byte-coverage + `0x0f`-op decode count on the CF corpus.
- `raw/hw_revalidation.log` — the consolidated HW splice/run session (ballot, shuffle, reduce, cf_for 0f splices).
- Round-trip: `python3 tools/agx-isa/roundtrip_test.py` (must stay GREEN).

## Raw results
See `raw/all_hex.txt` (every kernel's extracted `_agc.main`) and `raw/hw_revalidation.log` (HW runs + splices).
Key observations are summarized in `RESULTS.md`.

## Established facts → docs
- `0x0f` family decoded → `docs/isa/README.md` (control-flow section) + `docs/isa/encoding-tables.md` + `db.json`.
- ballot `0x17` / shuffle `0x54` / reduce byte+7 → same.
- RT-7 + RT-5 doc corrections → `docs/isa/README.md` (machine-model, SR/ABI, texture, RT sections).

## Follow-ups
- The `0x2b`/`0x3b`/`0x5b`/`0x8b` register/shift-prep family is the dominant remaining undecoded residue (not this task).
- `0f 04` `mask_op` has a single occurrence (byte+2=0x04) — role inferred; wants an isolated splice testbed.
- `rt_intersect` AS-select sub-fields need an instance/motion-AS testbed to splice-prove (RT-5 falsified the primitive-path claim).
