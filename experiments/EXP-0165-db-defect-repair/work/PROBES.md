# EXP-0165 probe trees — how to rebuild them

`analysis/ab_gate.py <tree>...` A/Bs any directory shaped like `tools/agx-isa`
(it needs `isadb.py`, `db.json`, `roundtrip_test.py`). The four candidate trees
this experiment measured were scratch copies and are **not committed** — five
copies of a 2700-line `isadb.py` is repo bloat, and each is one deterministic
edit away from the live tree. Rebuild any of them with:

```sh
# from the repo root; everything stays inside this experiment directory
D=experiments/EXP-0165-db-defect-repair
mkdir -p $D/work/<name>
cp tools/agx-isa/*.py tools/agx-isa/db.json tools/agx-isa/validation.json \
   $D/work/<name>/
```

then apply exactly one of the following.

## `cand` — the EXP-0161 repair (APPLIED to the live tree)
`python3 analysis/apply_defects.py work/cand/db.json`
→ clean 833 / leftover 388604 / roundtrip ALL PASS.
Firing delta vs baseline: `n3_mov` 336→259, `mov_zext16` 54→131.

## `cand2` (write 1 variant) — tighter `mov_zext16` match, REJECTED
In `work/cand2/db.json` set `mov_zext16.match = [[0,4,3],[16,3,0],[22,2,0],[24,3,1]]`
and `subform` to `start 19, width 3`.
→ clean 833 / leftover 388604, but **`frame_marker` 121 → 51**: the 12-bit match
beats `frame_marker`'s 8-bit `byte0 == 0x43` on the specificity tie-break and steals
70 of its firings. Rejected for that reason, not on the headline metric.

## `probe_r9` — the `carry_gen` length guard, MEASURED, NOT APPLIED
In `work/probe_r9/isadb.py`, immediately after the `_R9_TRIPLES` lookup in
`instr_length`, insert:
```python
    if _r9 is not None and (b0 & 0x0f) == 0x02 and 0 <= _b2 <= 0x3f:
        _r9 = None
```
→ functional re-emit 73/79 → **79/79**, but clean 833 → **832** and leftover
388604 → **389002**. REGRESSES; see `RESULTS.md` §6.

## `probe_op04` — EXP-0157's HW-measured `op04` length, MEASURED, NOT APPLIED
In `work/probe_op04/isadb.py` replace
`return 8   # op04_len8 (byte0==0x04 residue; ...)` with
`return 8 if (buf[off+1] & 0x80) else 12`.
→ clean 833 → **823**, leftover 388604 → **390568**, `op04_len8` firings 55 → 1.
REGRESSES; reported and left, per the orchestrator's instruction.

## `probe_hp` — EXP-0160's unconditional 4-byte `half_pack`, MEASURED, NOT APPLIED
In `work/probe_hp/isadb.py` replace the gate
`b0 == 0x18 and buf[off+1] == 0x05 and (buf[off+2] & 0xf8) == 0x18`
with `b0 == 0x18`.
→ clean 833 (unchanged), leftover 388604 → **388584 (-20)**, roundtrip ALL PASS.
IMPROVES, but it is an `isadb.py` length-rule change and that call is the
orchestrator's.
