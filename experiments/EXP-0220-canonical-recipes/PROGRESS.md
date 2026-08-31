# EXP-0220 — progress log

- **pre-freeze** — experiment created; `db.json`, `isadb.py`, `shdump.m`, `agxrun_persist.m`
  and `agxparse.py` pinned into `work/frozen/`; carrier authored; `synth220`/`prog220`/
  `cases220` written; offline gates T0..T5 green (1,584 cases, 0 donor fields, 0 Gate-A
  failures, 0 framing failures outside four declared-ambiguous cases).
- **pilot p01** — neo reachable; carrier `_agc.main` = 3228 bytes; **arm S0 established the
  slot→buffer mapping by hardware probe** (0→out, 1→mem, 2→imem; 3..7 write nothing).
- **pilot p02..p06 + diagnostics D1..D12** — seven corrections to documented rules found and
  folded into the pre-registration (`opflags` bit1 operand-class dependence; `mod_hi` bit0 and
  the in-flight-load accept bits; the store's index-register release; the stale-index rule;
  `addr_mode` bit1 as the store-side accept control; `extmode` bit0 not a don't-care; the nine
  non-tokenizing `mov_imm` immediates). The b16 arm was rebuilt on packed-half codewords after
  it was found to pass by construction.
- **pilot p07/p08** — full matrix: 1,443 of 1,444 gated cases pass; the last (a srcA/srcB
  register collision at `srcB_reg == srcA`) fixed.
- **FROZEN** — `PRE_REGISTRATION.md` + `CAPTURE_CONTRACT.json` written; remote hashes verified
  as a separate step (19 files, 0 mismatches) before any gated dispatch.
- **g17p-20260831-run01** — canonical order, 1,584 cases, 0 hangs, 20 self-inflicted faults.
- **g17p-20260831-run02** — shuffled order (seed 220), 1,584 cases, 0 hangs, same 20 faults.
- **pulled** — both run directories pulled back one at a time; 18 MB each.
- **scored** — Gate A/B/D/E pass; Gate C 1,446 of 1,453 per run (7 misses are a frozen-contract
  mislabel of known-fault `index_reg` values, left failing). Recipe dashboard 2 → 3 canonical.
