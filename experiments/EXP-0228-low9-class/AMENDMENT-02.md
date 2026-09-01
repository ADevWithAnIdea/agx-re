# EXP-0228 Amendment 02 — formal transport hash-list correction

Frozen before either formal hardware run. No hypothesis, generated program,
case, analysis gate, or capture command changes.

The first formal push copied the intended files but its final local reporting
command used `work/frozen/*`. Importing the pinned Python decoder during offline
self-test had created a `work/frozen/__pycache__/` directory. `shasum` reported
that directory as an error, while the following `sort` could mask its nonzero
status. Therefore that push is not accepted as a verified input transaction.

`push228_formal.sh` and `verify228_formal_remote.sh` now enumerate the five
frozen files explicitly. The corrected push must be repeated, followed by the
separate corrected remote comparison. Hardware dispatch remains forbidden
until that comparison exits zero. This is a transport-only process correction.
