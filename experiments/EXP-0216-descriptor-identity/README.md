# EXP-0216 — descriptor identity: do the records measure the bits their row now owns?

**Type:** derived analysis of already-committed artifacts. **No device was contacted**
(EXP-0213 held the A18 Pro for quiet Gate E confirmations throughout). No Apple binary was
read or introspected. No shader was compiled. Nothing under any `raw/` tree was written.

**Question.** EXP-0215 rebuilt the citation graph and stopped at three findings it
deliberately refused to act on, because acting would have moved a verdict onto a different
operand:

1. **22 (row, citation) pairs** whose records declare a different `fstart`/`fwidth` than the
   descriptor now assigns — including `imad.srcB`/`.srcC_lo` (apparently swapped),
   `fspecial.dst`/`.src`/`.src_ext` (apparently rotated), `mov_zext16.src_reg`, and
   `half_alu_fma12.ext` (a pre-EXP-0212 span).
2. **Two experiments, 15 638 records**, keyed to a mnemonic their own committed bytes do not
   decode to: EXP-0171 (`bf_alu`) and EXP-0144 (`cvt_f2h`).
3. **Four `cvt_f2h` citations** whose bytes fail `cvt_f2h`'s own `match` on all 1 280 records.

**Method.** Everything is decided from the *actual dispatched bytes* and the *committed
observations*, never from a `field` key or a mnemonic string. Two instruments do the work,
both already in the corpus and both already positively controlled by the experiments that
produced them:

* **Gate-A geometry** — decode each record's own bits at the declared span and at the current
  span and compare to the requested value. This says which bits an observation is *about*. It
  can never rename a field.
* **Operand identity** — EXP-0154's H3 release-on-read oracle (reading a GPR as a 32-bit
  source zeroes it, and all 16 registers are dumped with distinct seeds) plus host arithmetic
  oracles that score the *rival descriptor versions* against the same records. This says what
  the bits *are*.

Predictions for each competing reading were written into `PRE_REGISTRATION.md` and frozen
before any aggregate statistic was computed; prior exposure is disclosed there.

**Hard constraints honoured.** `tools/agx-isa/db.json`, `tools/agx-isa/validation.json`,
`tools/agx-isa/isadb.py`, `docs/` and `PROVENANCE.md` were opened read-only and are unchanged.
Nothing was committed. **No evidence label was changed and none is proposed** — this is a
descriptor question, not a promotion question. Proposed descriptor edits live in
`analysis/proposed_db_edits.json` as proposals and are applied nowhere.

## Layout

```
PRE_REGISTRATION.md        competing readings + what would decide each, frozen first
RESULTS.md                 the verdicts, with the bytes
work/db_frozen.json        tools/agx-isa/db.json  sha256 02a47fc6…  (== EXP-0215's copy)
work/validation_frozen.json tools/agx-isa/validation.json sha256 6e7ff3f1…
scripts/lib0216.py         bit/match/raw-scan helpers; treats `instr` and `field` as untrusted
scripts/q1_operand_identity.py  Gate-A geometry over all 26 suspects
scripts/q1_role_classifier.py   DST-/SRC-selector classification from register dumps
scripts/q1_slotfit.py           affine seed->destination fit, destination register discovered
scripts/q1_arith_oracle.py      host models for imad / falu3 / falu3_ext / iminmax
scripts/q1_fma12_oracle.py      EXP-0203's own oracle vs the two rival half_alu_fma12 layouts
scripts/q1_subspan.py           the narrowing (sub-span sufficiency) test
scripts/q1_partition.py         half_alu_fma12.ext record partition by swept byte
scripts/q1_verdicts.py          assembles analysis/q1_verdicts.json
scripts/q2_sibling.py           match arithmetic + per-byte span overlay for bf_alu / cvt_f2h
scripts/q2_lengthrule.py        isadb length rule vs the byte-2 values the hardware accepted
analysis/*.json                 all outputs, plus proposed_db_edits.json (proposals only)
```

## Reproduce

```
cd /Users/user/asahi_re/public/agx-re
for s in q1_operand_identity q1_role_classifier q1_slotfit q1_arith_oracle \
         q1_fma12_oracle q1_subspan q1_partition q2_sibling q2_lengthrule q1_verdicts; do
    python3 experiments/EXP-0216-descriptor-identity/scripts/$s.py
done
```

Every script reads `work/db_frozen.json`, not the live `tools/agx-isa/db.json`, so a
concurrent descriptor repair cannot move the ground under the analysis mid-run. If `db.json`
has since changed, re-freeze and re-run rather than trusting these numbers.
