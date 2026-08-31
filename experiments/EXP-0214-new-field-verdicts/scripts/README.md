# EXP-0214 scripts

Pure local analysis over committed raw. No device was contacted (EXP-0213 held the neo).

| script | what it does |
|---|---|
| `span_coverage.py` | generic: given `--start/--width/--instr` and a list of `sweep.jsonl`, decodes the sub-span out of every record's **actual dispatched bytes** and reports distinct span values, distinct actual encodings, per-arm and per-run coverage, and which parent sweep arms contributed. This is the instrument that answers "did the parent sweep actually vary THESE bits". |
| `e0203_half.py` | EXP-0203: `lensel`/`mods`/`srcC` stratification of the `ext` byte+4 / byte+5 sweeps, G1..G7 re-derivation, bit-7 mirror test, `half_pack.dst` nibble census. |
| `e0202_irotate_subspans.py` | EXP-0202: per-sub-span coverage, oracle rule, sem_checked/sem_match, outcome histogram. |
| `e0202_gateA.py` | EXP-0202: Gate A re-derived the way `analysis/verdicts.py::ledger` defines it (the driver's own `ledger_ok` compares against the whole 40-bit parent and is wrong for a byte arm). |
| `e0205_op_hi.py` | EXP-0205: the period-8 inertness test on the hardware observable, with `gputime_ns` excluded. |
| `e0199_fds.py` | EXP-0199: byte+1 accepted-set rule, sub-span coverage inside the accepted set, byte+2 signature census, anomaly reproduction check. |
| `e0206_reserved_hi.py` | EXP-0206: high-byte coverage stratified by whether the sibling low byte is zero. |
