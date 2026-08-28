# EXP-0146 — emittability of the integer-support instruction cluster, and the `I64` questionnaire section

**Target:** local **Apple M4 / G16G** (10 cores, macOS 26.6.x, Metal 4). The A18 Pro was never
touched; M5 was never touched; `macvdmtool` was never invoked.

## Question

Two deliverables, which turned out to reinforce each other:

1. **Emission, not decoding.** Move the fields of
   `carry_gen ilogic int_alu_ehi irotate mov_zext16 shift_amt_move n2_op6 n2_op8 n2_op10
   n3_mov sr_read_wide sfu_marker` from `corpus-correlation` / `tokenization-only` /
   `untested` to `hardware-run`, per `experiments/FIELD-SWEEP-PROTOCOL.md` — i.e. prove an
   emitter can choose a value and get documented behaviour, not merely that `db.json` can
   tokenize the compiler's own bytes.
2. **Answer `I64-01..06`**, the only entirely unanswered section of the 181-item Part-II
   questionnaire (`work/GAPS-COVERAGE.md`).

## Hypotheses and falsifiers

Frozen before any mutation ran: `PRE_REGISTRATION.md` (H1-H6, falsifiers F1-F4, coverage rule,
input vectors, stop rule). All four falsifiers fired; F3 fired **positive**, which is the
experiment's headline result.

## Method

`OWN-SHADER` + `HW-PROBE`. 26 MSL kernels we wrote (`kernels/`) are compiled at runtime by
`tools/shdump` (`newLibraryWithSource:`), `_agc.main` is located with
`tools/shdump/agxparse.py`, one target instruction is decoded with `tools/agx-isa/isadb.py`,
**one field or one raw byte** is changed, the instruction is re-assembled through the same
read-only DB, spliced back into a copy of the archive, and executed on the real GPU through
`tools/agxtest/agxrun_persist` + `persistrun.py` with an 8 s per-request watchdog. Each case
dispatches 8 threads carrying 8 different frozen input rows, and the result is compared against
a **host-computed** oracle written from public C/MSL/IEEE definitions.

## Commands

```sh
sh  harness/build.sh work/bin                                   # build the read-only tools
python3 work/pilot/disasm.py                                    # carrier location (no mutation)
python3 work/pilot/smoke.py                                     # all baselines vs host oracles
python3 work/pilot/splicecheck.py                               # prove splices execute
python3 harness/run_sweep.py --run-id run01                     # gated run 1
python3 harness/run_sweep.py --run-id run03                     # gated run 2
python3 harness/run_adjudicate.py --run-id run04 --list analysis/adjudicate_list.json
python3 harness/run_probes.py  --run-id run05                   # second-method probes P1-P4
python3 harness/run_srwide.py                                   # run06
python3 analysis/compare.py run01 run03                         # the promotion gate
python3 analysis/bitrule.py && python3 analysis/make_verdicts.py
```

## Clean-room provenance

```text
Clean-room provenance: OWN-SHADER + HW-PROBE (host oracles from PUBLIC C/MSL/IEEE definitions)
Inputs inspected: kernels/*.metal (authored by us) and their compiled _agc.main bytes only
Apple binary introspection: NONE
Reproduction: the command list above
Evidence: raw/pilot/, raw/run01/, raw/run02/, raw/run03/, raw/run04/, raw/run05/, raw/run06/,
          raw/trial00/  (58 764 append-only JSONL records)
```

No Apple binary was disassembled, decompiled, symbol-dumped, strings-scanned or debugged. The
only machine code inspected or spliced is the compiled form of MSL in `kernels/`, which we wrote.
`tools/agx-isa/db.json`, `tools/agx-isa/validation.json`, `docs/`, `PROVENANCE.md` and
`APPLE9_RE_IMPLEMENTATION_GAPS.md` were **not** edited, and nothing was committed.

## Outputs

| file | content |
|---|---|
| `RESULTS.md` | observations, interpretation, limitations, verdict |
| `analysis/field_verdicts.json` | 94 per-field verdicts + a 10-entry `db_defects` section |
| `analysis/I64_answers.md` | the `I64-01..06` answer block, ready to splice |
| `analysis/ilogic_lut_table.md` | all 16 boolean functions with HW-validated encodings |
| `analysis/field_maps.json`, `analysis/bit_rules.json` | the derived behaviour/bit-mask maps |
| `analysis/disagreements.json`, `analysis/adjudicate_list.json` | the gate's residue |
