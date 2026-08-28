# QUARANTINE (partial, precisely scoped) -- EXP-0087

**Scope: the automated `analysis.py --write` step only. The raw captured
evidence (`raw/m4-20260827-run01/`, `raw/m4-20260827-run02/`) is NOT
tainted, is complete, and is used directly in `RESULTS.md` via an
uncommitted scratch script that reads it read-only.**

## What is broken

`analysis.py::classify()` (this file is hash-frozen: it is listed in
`AUTH_CODE` and its SHA-256 is recorded in both closed raw runs'
`00_inputs.json.authored_code_sha256` and in `CAPTURE_CONTRACT.json`) has an
unhandled-shape bug: for `casematrix.py` case `move02_bit2_od0c`, the frozen
prediction is `{"out0": "corrupt_out8"}` -- a STRING value under a key the
function assumes is always numeric. `classify()` computes
`expected = {int(k[3:]): v for k, v in pred.items() if k.startswith("out")
and k[3:].isdigit()}`, which admits this string value into `expected`
unfiltered, then crashes at `abs(diff[k] - v)` with
`TypeError: unsupported operand type(s) for -: 'float' and 'str'`.

`python3 -B analysis.py --run-a m4-20260827-run01 --run-b m4-20260827-run02
--write` therefore cannot complete; `analysis.json` was never produced by
the contracted command, so `verify.py --captured`'s `require_analysis` check
also fails (in addition to the independent cross-run finding below).

## Why it is not repaired in place

`analysis.py`'s SHA-256 is already burned into both closed raw runs'
provenance records (`raw/*/00_inputs.json.authored_code_sha256["analysis.py"]`)
and into `CAPTURE_CONTRACT.json.authored_sha256["analysis.py"]`. Editing the
file now would change its hash and make `verify.py`'s `one_run()` authored-
drift check (`req(h == sha(root / p), "authored drift since capture ...")`)
fail against both already-closed runs -- i.e. "fixing" the bug would itself
break the gate on evidence that is otherwise completely valid. Per the
standing rule (never repair a quarantined/gated artifact in place), this is
left broken and recorded here instead.

## A second, independent, genuine finding (not a bug): 2/49 cases are
   nondeterministic across the two closed runs

`raw/m4-20260827-run01/04_results.jsonl` and
`raw/m4-20260827-run02/04_results.jsonl` differ on exactly two of 49 lines
(all other 47 are byte-for-byte identical, confirmed by direct diff):

| case | byte+2 | run01 | run02 |
|---|---|---|---|
| `move01_b2_26` (i=23) | `0x26` (reg_move_c2var, a documented "observed" residual) | `CMDBUF_ERROR` | `OK`, all 16 output slots read `0.0` |
| `move05_byte2_0f` (i=47) | `0x0F` (undocumented, outside every family) | `CMDBUF_ERROR` | `OK`, all 16 output slots read `0.0` |

This means `verify.py --captured`'s "byte-exact repeat" cross-run invariant
(`captured()`: `req(x["results"] == y["results"], "byte-exact repeat")`)
genuinely fails for this experiment -- not because either run is corrupt or
because a file drifted, but because these two specific illegal/boundary
encodings show real fault-vs-succeed nondeterminism on this M4 hardware.
Both raw runs are independently internally consistent and pass every
OTHER structural check (`one_run()` on each individually is clean); only
the pairwise byte-identity comparison the gate performs fails, and it fails
on exactly these two rows. This is itself a first-class result (see
`RESULTS.md` MOVE-05/MOVE-01 sections) and is NOT a reason to distrust the
other 47 cases, each of which independently reproduced byte-for-byte.

## Exact gate status

- `verify.py --selftest`, `--seqtest`: PASS (unaffected; synthetic, no raw/
  dependency).
- `verify.py --preflight`, `--between-runs`: PASSED when run (see
  `PROGRESS.md`).
- `verify.py --captured`: FAILS, on two independent grounds: (1) no
  `analysis.json` (blocked by the `analysis.py` bug above); (2) cross-run
  byte-exact-repeat, on the two rows above.

## Successor

The next sequential experiment, **EXP-0088**, should carry:
1. A corrected `analysis.py::classify()` that treats any non-numeric
   `pred[]` value (not just `"explore"`/`"unchanged"`) as a special/
   non-scored bucket instead of assuming every `"outN"` value is a float.
   It can run directly against this experiment's already-closed
   `raw/m4-20260827-run01/` and `raw/m4-20260827-run02/` -- **no GPU
   recapture is needed**; the raw evidence is sound.
2. If warranted, a small repeated-trial follow-up specifically isolating
   `byte+2=0x26` and `byte+2=0x0F` (e.g. N independent dispatches of the
   identical splice in fresh processes) to characterize the fault RATE of
   the nondeterminism observed here, rather than a single up/down sample.

## What was still delivered despite this

`RESULTS.md` in this directory reports the full classification of all 49
cases, computed by re-reading `raw/m4-20260827-run01/04_results.jsonl`
directly (the same immutable bytes `analysis.py` would have read) with a
corrected, uncommitted scratch script -- not by running the broken
`analysis.py`. Every number quoted there is traceable to that raw file.

## Exact reproduction of the `--captured` failure (for the record)

```
$ python3 -B verify.py --captured
FAIL closed root: ['QUARANTINE.md', 'analysis.json']
```

Two independent reasons in one message: `analysis.json` is missing (the
`analysis.py` bug above), and `QUARANTINE.md` itself is an "unexpected"
extra file relative to `verify.py`'s own frozen `ROOT_FILES` set --
`verify.py` is likewise hash-frozen and was not edited to whitelist this
file. Both are expected consequences of not repairing hash-frozen files
post-capture, not new defects.
