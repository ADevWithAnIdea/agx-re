#!/usr/bin/env python3
"""EXP-0181 -- scan committed raw/ for evidence that an instruction was DISPATCHED.

Task 1 asks, per instruction: did any experiment actually EXECUTE this instruction on
hardware (not merely tokenize it), and did a host oracle confirm its documented
behaviour?  This script answers both from the immutable raw record only.

For every `experiments/EXP-*/raw/**/*.jsonl` record carrying an `instr` (or `mnemonic`)
key it accumulates, per (mnemonic, experiment):
  * total case count and the `outcome` histogram;
  * how many records carry BOTH an `oracle` and an `observed` block (an oracle-scored
    case -- the instruction's own semantics were predicted by the host);
  * how many of those are baseline/anchor cases (`kind`/`arm`/`group` containing
    "baseline" or "anchor") that came back `ok` -- i.e. the UNMUTATED instruction
    reproduced its host oracle;
  * the distinct `target` recorded by the run (from 00_env.json / 00_inputs.json when
    present), else the experiment's own convention.

CLEAN-ROOM: pure re-analysis of this repository's own committed raw observations of our
own compiled/spliced shaders.  No device, no Apple binary.
"""
import json, os, re, sys, collections, glob

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
EXPROOT = os.path.join(ROOT, "experiments")

def main(argv):
    want = set(argv[1:]) or None
    agg = collections.defaultdict(lambda: {
        "cases": 0, "outcomes": collections.Counter(), "oracle_scored": 0,
        "baseline_ok": 0, "baseline_cases": 0, "runs": set(), "files": set()})
    for path in glob.iglob(os.path.join(EXPROOT, "EXP-*", "raw", "**", "*.jsonl"),
                           recursive=True):
        rel = os.path.relpath(path, ROOT)
        exp = rel.split(os.sep)[1]
        run = rel.split(os.sep)[3] if len(rel.split(os.sep)) > 3 else "?"
        try:
            fh = open(path, "r", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line or line[0] != "{":
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                m = r.get("instr") or r.get("mnemonic") or r.get("instruction")
                if not isinstance(m, str):
                    continue
                if want and m not in want:
                    continue
                a = agg[(m, exp)]
                a["cases"] += 1
                oc = r.get("outcome")
                if isinstance(oc, str):
                    a["outcomes"][oc] += 1
                has_oracle = isinstance(r.get("oracle"), (dict, list, int, float, str))
                if has_oracle and r.get("observed") is not None:
                    a["oracle_scored"] += 1
                tag = " ".join(str(r.get(k, "")) for k in ("kind", "arm", "group", "field"))
                if re.search(r"baseline|anchor|unmutated", tag, re.I):
                    a["baseline_cases"] += 1
                    if oc == "ok" or r.get("match") is True:
                        a["baseline_ok"] += 1
                a["runs"].add(run)
                a["files"].add(rel)
    out = {}
    for (m, exp), a in sorted(agg.items()):
        out.setdefault(m, {})[exp] = {
            "cases": a["cases"],
            "outcomes": dict(a["outcomes"]),
            "oracle_scored_cases": a["oracle_scored"],
            "baseline_or_anchor_cases": a["baseline_cases"],
            "baseline_or_anchor_ok": a["baseline_ok"],
            "runs": sorted(a["runs"]),
        }
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
