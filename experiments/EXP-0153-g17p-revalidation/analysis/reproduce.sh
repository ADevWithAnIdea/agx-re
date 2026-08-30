#!/bin/bash
# EXP-0153 full offline reproduction (CODEX step 10). No device needed.
#
# tools/agx-isa/db.json moved on while this experiment ran (falu2's `mod_lo`
# was split into `srcA_class` + `srcB_class`), so the case matrix is rebuilt
# against the DB the captures actually recorded -- f5db942f..., at commit
# ff99bb52326a433375008408004a8db6294a04db -- pinned into work/isa_frozen.
set -euo pipefail
cd "$(dirname "$0")/.."
FROZEN_COMMIT=ff99bb52326a433375008408004a8db6294a04db
FROZEN_SHA=f5db942f03c9ad3870a102e0e34f705217ffa7ea5883dd960d0ffec93e76e36e
mkdir -p work/isa_frozen work/isa_frozen_tools
git -C ../.. show $FROZEN_COMMIT:tools/agx-isa/db.json  > work/isa_frozen/db.json
git -C ../.. show $FROZEN_COMMIT:tools/agx-isa/isadb.py > work/isa_frozen/isadb.py
test "$(shasum -a 256 work/isa_frozen/db.json | cut -d' ' -f1)" = "$FROZEN_SHA"
rm -f work/isa_frozen_tools/agx-isa
ln -s "$PWD/work/isa_frozen" work/isa_frozen_tools/agx-isa

echo "== rebuild the case matrix and cross-check every recorded instruction"
AGX_TOOLS=$PWD/work/isa_frozen_tools python3 - <<'PY'
import sys, json
sys.path.insert(0, "harness")
import isa_helpers as H, cases as CS
b = json.load(open("raw/g17p-20260830-run01/00_build.json"))
mains = dict((k, v["main_len"]) for k, v in b.items())
anch = dict((k, (v["anchor"]["offset"], v["anchor"]["length"],
                 bytes.fromhex(v["anchor"]["bytes"])))
            for k, v in b.items() if "anchor" in v)
arms = CS.build_all(mains, anch)
n = sum(len(a["cases"]) for a in arms)
recs = [json.loads(l) for l in open("raw/g17p-20260830-run01/sweep.jsonl")]
by = dict(((r["arm"], r["i"]), r) for r in recs if r["arm"] != "_HEALTH")
bad = sum(1 for a in arms for i, c in enumerate(a["cases"])
          if (a["arm"], i) in by and by[(a["arm"], i)]["bytes"] != c["ibytes"])
print("arms %d, cases %d, instruction-byte mismatches %d" % (len(arms), n, bad))
assert n == 1958 and bad == 0
PY

echo "== score the two gated runs"
python3 analysis/verdicts.py raw/g17p-20260830-run01 raw/g17p-20260830-run03 --out analysis
echo "== emit the field verdicts"
python3 analysis/make_field_verdicts.py
echo "== arm G corpus numbers"
bash analysis/corpus_compare.sh
