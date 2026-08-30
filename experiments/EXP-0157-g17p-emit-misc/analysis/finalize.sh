#!/bin/bash
# EXP-0157: regenerate every derived artifact from raw/ and refresh the
# generated block in RESULTS.md. Run from the experiment directory.
set -e
cd "$(dirname "$0")/.."
python3 analysis/verdicts.py raw/g17p_run01 raw/g17p_run02 raw/g17p_run03 \
        --out analysis/field_verdicts_RSH.json --report analysis/gate_report_RSH.json 2>/dev/null \
  || python3 analysis/verdicts.py raw/g17p_run01 raw/g17p_run02 \
        --out analysis/field_verdicts_RSH.json --report analysis/gate_report_RSH.json
python3 analysis/verdicts.py raw/g17p_raymove01 raw/g17p_raymove02 \
        --out analysis/field_verdicts_B2.json --report analysis/gate_report_B2.json
python3 analysis/merge.py
python3 analysis/emittability.py
python3 analysis/lenrule.py raw > analysis/length_rule_stdout.txt
python3 - <<'PY'
import subprocess, re
from pathlib import Path
out = subprocess.check_output(["python3", "analysis/summary.py"], text=True)
p = Path("RESULTS.md"); s = p.read_text()
s = re.sub(r"<!-- BEGIN GENERATED: python3 analysis/summary\.py -->.*?<!-- END GENERATED -->",
           "<!-- BEGIN GENERATED: python3 analysis/summary.py -->\n" + out + "<!-- END GENERATED -->",
           s, flags=re.S)
p.write_text(s)
print("RESULTS.md generated block refreshed")
PY
