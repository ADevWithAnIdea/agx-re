# EXP-0166 raw/ — deliberately empty of new captures

This experiment **dispatched nothing to any GPU**. It is an offline re-derivation, so it has no raw
observations of its own; creating a token capture here would misrepresent that.

The append-only raw evidence this experiment adjudicates lives in
`experiments/EXP-0146-m4-emit-int-misc/raw/` and is pinned by SHA-256 in `../PRE_REGISTRATION.md`
§7 and in `../manifest.json`. `analysis/adjudicate.py` re-checks those hashes on every run and
prints an `INPUT DRIFT` block rather than proceeding silently if any input has changed.

The pre-registered conditional device arm (`../PRE_REGISTRATION.md` §6) was **not run** — the
coordinator placed a hold on all neo work while EXP-0167 needs a quiet machine, and
`experiments/FIELD-SWEEP-PROTOCOL.md` §7 independently records that a busy-machine re-run
manufactures faults, so a single unlocked confirmation run would not have been confirmation.
