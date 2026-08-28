#!/usr/bin/env python3
"""EXP-0139 fault re-validation pass (FIELD-SWEEP-PROTOCOL §7.1/§7.2).

A single `fault` observation is NOT a property of the field: with sibling GPU
experiments running, another agent's contained fault surfaces in our command
buffer. This pass takes the union of every case that produced a non-OK status
in ANY gated run and re-executes it `--repeats` times in a FRESH process,
recording the OS's own `[cb error] localizedDescription` for each attempt and
re-checking the unmutated baseline immediately before and after every case.

A field value is only reported `fault` if it faults in EVERY attempt here AND
its surrounding baselines were healthy. Anything else is recorded as
`transient` / `victim` and is EXCLUDED from the fault verdicts.

  python3 harness/revalidate.py --runs m4_..._run01,m4_..._run02 \
      --out raw/m4_..._revalidate01 --repeats 5
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import anchors as A          # noqa: E402
import casematrix as CM      # noqa: E402
import sweeprun as S         # noqa: E402
import run as R              # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--indices", default="", help="JSON file of case indices to "
                    "re-run instead of the non-OK union (used for the OK-but-"
                    "unstable cases: same 5x-in-a-fresh-process discipline, "
                    "applied to cases whose two gated launches DISAGREED)")
    ap.add_argument("--timeout", type=float, default=8.0)
    a = ap.parse_args()

    out = EXP / a.out
    if (out / "revalidate.jsonl").exists():
        sys.exit("REFUSING to reuse run id %s" % a.out)
    out.mkdir(parents=True, exist_ok=True)

    suspect = {}
    if a.indices:
        for i in json.load(open(EXP / a.indices)):
            suspect[i] = [{"run": "gated", "reason": "cross-run or in-run repeat disagreement"}]
    for rid in ([] if a.indices else a.runs.split(",")):
        for line in open(EXP / "raw" / rid / "sweep.jsonl"):
            r = json.loads(line)
            if r["status"] != "OK" or r["status2"] != "OK":
                suspect.setdefault(r["i"], []).append(
                    {"run": rid, "status": r["status"], "status2": r["status2"]})
    print("suspect cases:", len(suspect))

    work = EXP / "work" / Path(a.out).name
    nat_fns = sorted({fn for fn, _, _, _ in CM.NAT_ANCHORS.values()})
    mains = {fn: S._compile_only(EXP / "kernels" / CM.NAT_SRC, fn, work) for fn in nat_fns}
    cases = {c["i"]: c for c in CM.build_cases(mains)}

    (out / "00_env.json").write_text(json.dumps(R.env_block(), indent=1, sort_keys=True))
    log = S.Log(out / "revalidate.jsonl")
    carriers = {}
    ins_files = {}

    def carrier_for(case):
        key = ("carrier_dag.metal", "k") if case["splice_kind"] == "synth" \
            else (CM.NAT_SRC, case["fn"])
        if key not in carriers:
            carriers[key] = S.Carrier(EXP / "kernels" / key[0], key[1], work, timeout=a.timeout)
        return carriers[key]

    def ins_for(case, c):
        kind = case["ins"]
        if kind not in ins_files:
            if kind == "dag":
                ins_files[kind] = {1: c.write_input("dag_mem.bin", [0] * 16),
                                   2: c.write_input("dag_imem.bin", [0] * 16)}
            elif kind == "float":
                import struct
                pa = Path(c.workdir) / "fa.bin"
                pa.write_bytes(b"".join(struct.pack("<f", v) for v in CM.FA_IN))
                pb = Path(c.workdir) / "fb.bin"
                pb.write_bytes(b"".join(struct.pack("<f", v) for v in CM.FB_IN))
                ins_files[kind] = {0: str(pa), 1: str(pb)}
            else:
                ins_files[kind] = {0: c.write_input("a.bin", CM.A_IN),
                                   1: c.write_input("b.bin", CM.B_IN)}
        return ins_files[kind]

    baselines = {c["arm"]: c for c in cases.values() if c["field"] == "_baseline"}
    # Health criterion (FIELD-SWEEP-PROTOCOL SS7.3): the baseline is HEALTHY if
    # it reproduces the bytes it produced in the gated runs -- NOT if it matches
    # its host oracle. Two arms legitimately never match their oracle (ISEL_REG8
    # is an extrapolated construction whose baseline is pre-registered
    # `mismatch`; ICMPSEL's oracle was computed from the wrong input vector, a
    # disclosed harness defect corrected in analysis). Stability is what
    # distinguishes a cascade from a by-design mismatch.
    ref = {}
    for rid in a.runs.split(","):
        for line in open(EXP / "raw" / rid / "sweep.jsonl"):
            r = json.loads(line)
            if r["field"] == "_baseline":
                ref.setdefault(r["arm"], set()).add(r["observed"])

    def run_one(case):
        c = carrier_for(case)
        n = max(int(k) for k in case["oracle"]) + 1
        resp, iw, fw = c.run(CM.materialize(case), ins_for(case, c), case["out_slot"], n,
                             grid=case["grid"], tg=case["tg"])
        obs = {int(k): iw[int(k)] if int(k) < len(iw) else None for k in case["oracle"]}
        oc, m = S.classify(resp["status"], obs, {int(k): v for k, v in case["oracle"].items()})
        return resp, iw, oc, m

    def baseline_healthy(arm):
        b = baselines.get(arm)
        if b is None:
            return None
        for _ in range(3):
            resp, iw, oc, m = run_one(b)
            if resp["status"] == "OK" and R.words_hex(iw) in ref.get(arm, set()):
                return True
            carrier_for(b).restart()
        return False

    t0 = time.time()
    for n, (idx, evid) in enumerate(sorted(suspect.items())):
        case = cases[idx]
        b = baselines.get(case["arm"])
        pre = baseline_healthy(case["arm"])
        attempts = []
        for k in range(a.repeats):
            resp, iw, oc, m = run_one(case)
            attempts.append({"attempt": k, "status": resp["status"],
                             "err": resp.get("error"),
                             "victim": S.is_victim(resp.get("error")),
                             "observed": R.words_hex(iw), "outcome": oc, "match": m})
        post = baseline_healthy(case["arm"])
        nfault = sum(1 for x in attempts if x["status"] != "OK")
        nvictim = sum(1 for x in attempts if x["victim"])
        stable_obs = set(x["observed"] for x in attempts if x["status"] == "OK")
        if nfault == a.repeats:
            verdict = "reproducible_fault"
        elif nfault == 0:
            verdict = "transient_not_reproduced" if len(stable_obs) == 1 else "nondeterministic"
        else:
            verdict = "intermittent"
        if pre is False or post is False:
            verdict = "baseline_unhealthy"
        log.write({"i": idx, "arm": case["arm"], "instr": case["instr"],
                   "field": case["field"], "subfield": case.get("subfield"),
                   "value": case["value"], "bytes": case["instr_hex"],
                   "carrier": case["carrier"], "gated_evidence": evid,
                   "baseline_pre_ok": pre, "baseline_post_ok": post,
                   "attempts": attempts, "n_fault": nfault, "n_victim": nvictim,
                   "repeats": a.repeats, "verdict": verdict})
        if (n + 1) % 200 == 0:
            print("... %d/%d revalidated, %.1fs" % (n + 1, len(suspect), time.time() - t0))
    log.close()
    for c in carriers.values():
        c.close()
    print("DONE %d cases in %.1fs" % (len(suspect), time.time() - t0))


if __name__ == "__main__":
    main()
