# EXP-0184 — G17P one-field-away, batch B

**Question.** Four instructions in the emitter worklist are blocked by exactly one field each.
Can an emitter *choose* that field's value and get documented behaviour on the A18 Pro / G17P?

| instruction | field | span | prior state |
|---|---|---|---|
| `rt_query_traverse` | `dst` | bits 4..7 | `untested`, `range: "none"` — **never swept, on any target** |
| `if_push` | `scope` | bits 16..23 | 1 carrier, 0 moved (EXP-0140), withheld by EXP-0164 |
| `cvt_f2i` | `b9` | bits 72..79 | 1 carrier, 0 moved (EXP-0144), withheld by EXP-0164 |
| `copysign` | `operands` | bits 24..31 | 1 carrier, 0 moved (EXP-0138), withheld by EXP-0164 |

**Hypotheses, refuters, confounders, and the promotion gate:** `PRE_REGISTRATION.md`
(frozen, with `CAPTURE_CONTRACT.json`, before any build or device run).

## Method

Splice one field of one instruction inside the compiled `_agc.main` of **our own MSL**, dispatch
it on real hardware, and read back a poisoned output buffer against a host-computed oracle. For
each field the carriers are chosen to differ **in the dimension the field controls** — nesting
depth for a mask-bank selector, destination integer type for a format descriptor, operand
provenance for an operand descriptor, query phase for a traversal destination — because the reason
all three withheld fields read inert before is that exactly one carrier was ever tried.

* `kernels/` — the four authored MSL carrier files (copysign ×5, convert ×5, control flow ×5,
  intersection_query ×4).
* `harness/locate184.py` — locates each instruction by the **descriptor signature from this
  experiment's pinned `db.json`**, cross-checked against the pinned tokenizer, with a hard exit if
  the pinned snapshot is absent (EXP-0182 owns `isadb.py` and EXP-0183 owns `db.json`; neither is
  read or written here).
* `harness/saferunner184.py` — one reader thread per child, tagged by owner; a malformed response
  is a **measurement failure**, never a hang (FIELD-SWEEP-PROTOCOL 3d).
* `harness/agxrun_persist_as.m` — EXP-0157's acceleration-structure-capable persistent runner,
  used **verbatim** (sha256 `370596f1…`), so the ray geometry is the same authored two-geometry
  four-triangle set.
* `run.py` — the sweep driver. **No hang budget** (protocol 3c); every value is dispatched.
* `analysis/census.py` → `analysis/gen_arms.py` → `harness/arms184.json` → `analysis/verdicts.py`.

## Reproduction

```bash
export SSHPASS='...'                       # never written to any file
python3 analysis/contract.py freeze        # before anything else
bash harness/sync.sh push
python3 harness/verify_remote.py           # SEPARATE step; exit 0 required
bash harness/sync.sh build
bash harness/sync.sh shell 'cd ~/agxre/EXP-0184 && python3 analysis/census.py'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0184 && python3 analysis/gen_arms.py'
# ... freeze arms184.json into the contract, re-push, re-verify ...
bash harness/sync.sh shell 'cd ~/agxre/EXP-0184 && python3 run.py --run-id g17p_YYYYMMDD_run01'
bash harness/sync.sh shell 'cd ~/agxre/EXP-0184 && python3 run.py --run-id g17p_YYYYMMDD_run02'
bash harness/sync.sh pull
python3 analysis/verdicts.py raw/g17p_YYYYMMDD_run01 raw/g17p_YYYYMMDD_run02
```

## Clean-room statement

```
Clean-room provenance: HW-PROBE + OWN-SHADER
Inputs inspected:      kernels/*.metal (authored by us) and their compiled _agc.main bytes
Apple binary introspection: NONE
Reproduction:          the block above; run ids in raw/
Evidence:              raw/<run_id>/sweep.jsonl (append-only), CAPTURE_CONTRACT.json hashes
```

**Results:** `RESULTS.md`. **Progress log:** `PROGRESS.md`.
