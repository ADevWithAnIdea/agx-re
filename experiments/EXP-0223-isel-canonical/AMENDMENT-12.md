# AMENDMENT-12 — preserve V2 hardware result; repair the proven-form tokenizer

Frozen after `g17p_e0223_run01` and `g17p_e0223_run02`, before changing the decoder or
dispatching a replacement formal run.

## What the two V2 captures established

Both runs dispatched 219 generated programs: 8 slot probes and 211 V2 cases.  In each run all
209 positive V2 programs matched the complete-state host oracle, and both deliberately wrong host
models mismatched.  There were no faults, hangs, copied/carrier fields, requested-versus-actual
byte disagreements, sentinel failures, or cross-run program/output differences.  The generated
programs included 100 deterministic 2..64-operation `iadd2`/`isel10` DAGs.

This is valid hardware evidence.  It must not be discarded or relabelled as a hardware failure.

## Why it is not yet the pre-registered formal promotion

The initial pre-registration also says that any whole-program decoder alias fails the case.  The
per-instruction independent decoder reported zero errors, but the older corpus tokenizer lost the
walk at an `isel10` in 118 V2 cases per run.  Once desynchronized, it reported 142,610 aliases per
run.  The exact alias sets reproduced across both orders.

The tokenizer's low-nibble-2 length rule recognizes a ten-byte register select only when the
destination byte is not `0x22` and the compare-B descriptor's high nibble is 0 or 8.  V2 directly
executed valid generated selects with destination r2 and compare sources r8..r23.  The hardware
then executed the following generated instructions and the complete program matched its oracle,
so those old restrictions are decoder overfitting, not instruction-format restrictions.

## Frozen correction hypothesis

Add a ten-byte length rule for the exact generated/proven register-descriptor grammar, after the
already-special-cased `0x27`/`0x2f` forms and before the old corpus fallback:

```text
byte+2 in {07, 0f, 17, 1f, 37, 3f}   # proven opsel 0,1,2,3,6,7
byte+1 is odd and <= 2f               # cmpA = (r0..r23 << 1) | 1
byte+3 is odd and <= 2f               # cmpB = (r0..r23 << 1) | 1
byte+4 low two bits == 2              # mapped legal compare-mode class
byte+5 is even and <= 2e              # T = r0..r23 << 1
byte+6 <= 7                            # mapped compiler condition codes
byte+9 is even and <= 2e              # F = r0..r23 << 1
```

Destination r0..r15, flags byte, and false-source control byte remain unconstrained by the length
rule because V2 or the preceding exhaustive sweeps directly executed their full relevant domains.
`0x27` and `0x2f` stay excluded: F1 found descriptor ambiguity for opsel 4/5, and the existing
tokenizer has separately evidenced length-polymorphic forms there.

## Acceptance and falsification

1. Preserve the original raw captures and original decoder hashes.
2. Apply the correction to a new decoder revision; never rewrite the decoder attributed to the
   original runs.
3. Reconstruct the V2 bodies from their actual-byte ledgers.  Every requested instruction must be
   a walk boundary with the requested mnemonic, with no leftover bytes, in both captures.
4. Run the repository tokenizer/round-trip regression suite and corpus comparison.  Reject or
   narrow the rule on any newly misframed previously clean sequence.
5. Freeze the corrected decoder and rerun the same formal V2 suite twice in different orders.
   Require byte-identical programs and results, zero independent-decode errors, zero aliases, 209
   exact positives, and two firing refuters per run.

No new Metal compilation is authorized or needed by this amendment.
