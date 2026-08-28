# EXP-0077 progress log

- **2026-08-27T23:17Z — M1: tasking + mandatory reading complete.** Read
  `../CLAUDE.md` (governing law: all testing LOCAL on the M4, A18 hands-off,
  NEVER macvdmtool), `../CODEX.md` (binding 10-step process), `SUBAGENT_BRIEF.md`,
  the promoted pattern `../EXP-0074-m4-fp32-division-precision/` (README,
  PRE_REGISTRATION, run.py, verify.py, CAPTURE_CONTRACT.json, RESULTS.md), both
  quarantine records (`../EXP-0075-*/QUARANTINE.md` — gate-order contradiction,
  selftest not runnable post-run01; `../EXP-0072-*/QUARANTINE.md` — payload
  truncation from a racing worker thread), the target questionnaire section
  (APPLE9_RE_IMPLEMENTATION_GAPS.md P0 "Memory addressing and robustness",
  MEM-01..MEM-05), `docs/isa/README.md` memory family, `EXP-0012-memory/RESULTS.md`,
  `RT-1a-FIX/` (bank.metal + raw/mem_index.log: the working splice recipe this
  experiment scales up), and the read-only tool surfaces (`tools/agxtest/agxtest.py`,
  `agxrun.m`, `tools/shdump/README.md`, `tools/agx-isa/isadb.py` codec +
  device_load/device_store descriptors).
  Key frozen facts being built on: `device_load`/`device_store` are 14-byte ops;
  DB field layout has `index_reg` at bits[40:48] (byte+5), `idx_off` at bits[79:90]
  (11-bit: byte+9 bit7 = LSB, byte+10 = bits 1..8, byte+11 bits 0..1 = bits 9..10),
  `elem_size` at bits[96:104] (byte+12, bits[1:4] code). A18-side prior evidence
  (EXP-0012 on-device + RT-1a-FIX re-validation on A18): element addressing
  `(index + offset) * element_size`. M4-side HW splice evidence for these fields:
  none yet — that is this experiment's job.
  Tooling constraint honored: `tools/*` are read-only (invoked, never edited); all
  scratch under this directory's `work/`. No GPU dispatch has occurred yet.

- **2026-08-27T23:20Z — M2: kernels + harness authored.** `kernels/ld_bank.metal`
  (load probe: `out[0] = a[i0]`, i0 from idxbuf — bank.metal shape) and
  `kernels/st_bank.metal` (store probe: `tgt[i0] = 0x5A17C0DEu`, exactly one
  device_store). `harness/build.sh` builds `tools/shdump/shdump.m` and
  `tools/agxtest/agxrun.m` into this experiment's `work/bin/` (tools sources are
  read-only inputs). Filler pattern frozen: probe buffer `a[w] = 0x3CA50000 | w`
  (4096 words = 16 KiB) — any 32-bit read at a byte offset B < 16381 decodes
  uniquely to (word, byte-residue) because byte 3 of every word is the tag 0x3C
  and bytes 0..1 carry the word index.

- **2026-08-27T23:5xZ — M3: authoring complete; kernels frozen; plumbing
  validated (non-recorded, per the amended registration).** Authored
  `kernels/ld_bank.metal` (variant H: `out[0] = a[i0+i1]`, i1 bound to 0 so the
  GPR index equals idxbuf[0] bit-exactly; the a[j] load compiles to the
  canonical byte+2=0x44 indexed form at main+0x26 =
  `6700440202002000510100404600`) and `kernels/st_bank.metal` (single store
  `tgt[i0+i1] = 0x5A17C0DE` at main+0x4C = `e700540401012100110000901100`).
  Seven compile-only kernel variants were inspected to reach this shape (the
  plain `a[i0]` forms compile to a byte+2=0x46 form whose index plumbing is not
  A18-anchored; the ALU-index form is). `baseline.py` re-derives both anchors
  deterministically (two independent derives matched) and run.py STOPs on any
  drift. All 2164 frozen cases round-trip through our DB
  (assemble(decode(probe)+one-field-override)); splice deltas are asserted to
  stay inside the changed field's bytes. The DB expressed every needed value
  (no STOP required). verify.py --selftest: **19/19 PASS**; --seqtest (new
  gate-sequence state machine, the EXP-0075 fix): **14/14 PASS** (preflight
  refused with raw present, between-runs refused pre-GPU and with two runs,
  captured refused without analysis/with one run, selftest/seqtest proven
  root-independent). Authorized pre-capture plumbing (three non-recorded
  invocations into work/plumb, never into raw/): (1) unspliced ld run →
  STATUS OK, PIPELINE_SOURCE archive, out0 = 0x3CA50040 = a[64] exactly as
  hand-predicted; (2) spliced scratch case (idx_off=+1, idx=64) → out0 =
  0x3CA50041 = a[65] — the M4 splice mechanism works (tampered archive
  accepted, the changed byte is the byte that ran) and the offset moved the
  address by one ELEMENT (4 bytes), the first H-ELEM-consistent datum;
  (3) unspliced st run → tgt word 64 = 0x5A17C0DE, all other 2047 words zero.
  No GPU fault, no wedge, no reboot needed.

- **2026-08-27T24:1xZ — M4: TERMINAL. run01 crashed at the in-run smoke gate.**
  All gates passed; three authorized plumbing validations passed (see M3);
  `run.py --execute --run-id m4-20260827-run01` created
  `raw/m4-20260827-run01/` (00/01/02) and crashed inside the smoke gate with
  `KeyError: 'item'` (SMOKE_CASE lacked the `item` record key). The one smoke
  dispatch executed but its output was lost; NO matrix case ran and
  04_results.jsonl was never created. The stub raw tree exists → per CODEX the
  authored blobs cannot be repaired in place (capture-time hash binding in
  00_inputs.json); EXP-0077 is terminal process history and the successor
  **EXP-0080-m4-mem-offset-semantics** adopts the full frozen design with
  three process fixes: SMOKE_CASE full keys; the smoke gate moved BEFORE
  raw/ creation (no burned run id on a smoke defect — EXP-0075's lesson made
  structural); unexpected sweep exceptions write STOP.json. An earlier
  operator slip is also recorded for honesty: a first launch attempt with a
  stray root-level log file was killed DURING the pre-capture gates (before
  any raw path existed) and left no state.
