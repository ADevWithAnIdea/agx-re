# EXP-0218 — where does `imad`'s ADDEND live?

**Kind:** desk re-analysis of already-committed artifacts. **No device was contacted**
(EXP-0213 holds the A18 Pro), no Apple binary was read, no shader was compiled, and nothing
under any `raw/` path was written or modified.

**Question.** EXP-0216 fixed `imad`'s two multiplicands on bytes +5 (`reg = v>>2`) and +6
(`reg = v>>3`), showed `imad` has no `srcA` field, scored both of its addend candidates at 0,
and closed with *"where the addend actually lives is still open."* This experiment answers it
from the 13,937 committed `imad` records (4,118 distinct 12-byte encodings, two targets).

**Answer, in one line.**

> The addend is an **8-bit immediate carried in the instruction — byte+7 bits 3..7 (low five)
> plus byte+8 bits 0..2 (high three) — but only when byte+9 bit 3 is 0. When byte+9 bit 3 is 1,
> those same bits stop being a value and become an INDEX into an external scalar file, and the
> addend value is then nowhere in the instruction.** `imad` has both addend modes, and the two
> anchors this corpus was built from sit on opposite sides of that one bit.

Both prior claims in `db.json` are correct about their own anchor and wrong as general
statements: EXP-M4-13 R6's "the immediate is in the instruction" and EXP-0160/DEF-0160-3's
"the addend is not in the instruction" describe the same instruction in its two modes.

## Files

```
PRE_REGISTRATION.md   frozen before the first addend model was fitted (sha256 in work/)
RESULTS.md            the verdict, every model's exact numerator/denominator, the undecidables
scripts/lib0218.py    read-only loaders; every byte decoded by POSITION from `bytes`
scripts/s0_product.py step 0  re-derive the product map before using it as a subtrahend
scripts/s1_census.py  step 1  co-variation census over every byte position, both carriers
scripts/s2_bytetables.py      per-byte-value addend tables
scripts/s3_models.py  steps 3-4  every pre-registered model scored, FIT vs HELD-OUT
scripts/s4_discriminators.py  the five selector-vs-literal discriminators
scripts/s5_finalize.py        the counts the verdict rests on, split by run and seed set
scripts/s6_scoreboard.py      the complete model scoreboard
scripts/s7_adversarial.py     attacks on this experiment's own conclusion
scripts/s8_width.py           the 32-bit fetch, predicted out-of-sample from the 16-bit table
analysis/*.json               machine-readable output of each step
analysis/proposed_db_edits.json  PROPOSAL ONLY — nothing in tools/agx-isa was edited
work/                 frozen db.json / validation.json copies + sha256 of all 13 raw inputs
```

## Commands

```sh
for s in s0_product s1_census s2_bytetables s3_models s4_discriminators \
         s5_finalize s6_scoreboard s7_adversarial s8_width; do
    python3 experiments/EXP-0218-imad-addend/scripts/$s.py
done
```

## Scope

`tools/agx-isa/db.json`, `tools/agx-isa/validation.json`, `docs/` and `PROVENANCE.md` were
**not** edited; **no evidence label was changed or proposed**; nothing was committed.
Every count states the target it was measured on: **C-M4 = M4 / G16G** (EXP-0139),
**C-G17P = A18 Pro / G17P** (EXP-0154, EXP-0160). No result is promoted across targets.
