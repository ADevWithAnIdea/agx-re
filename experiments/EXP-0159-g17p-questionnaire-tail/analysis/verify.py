#!/usr/bin/env python3
"""EXP-0159 gate verifier.  Authored by the clean-room RE team.

  --preflight    authored sources hash-match CAPTURE_CONTRACT.json
  --captured     both gated runs present, positive controls fired, cross-run
                 agreement on every non-victim case
"""
import argparse, collections, hashlib, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def contract():
    return json.load(open(os.path.join(ROOT, "CAPTURE_CONTRACT.json")))


def preflight():
    c = contract()
    bad = []
    for rel, want in sorted(c["source_sha256"].items()):
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            bad.append((rel, "MISSING", want)); continue
        got = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if got != want:
            bad.append((rel, got, want))
    for rel, got, want in bad:
        print("HASH-MISMATCH %s got=%s want=%s" % (rel, got[:16], want[:16]))
    print("PREFLIGHT %s (%d sources)" % ("FAIL" if bad else "PASS", len(c["source_sha256"])))
    return 1 if bad else 0


def load(run):
    d = os.path.join(ROOT, "raw", run)
    out = collections.defaultdict(list)
    for f in sorted(os.listdir(d)):
        if f.endswith(".jsonl"):
            for ln in open(os.path.join(d, f)):
                ln = ln.strip()
                if ln:
                    out[f[:-6]].append(json.loads(ln))
    return out


def key(r):
    return (r.get("family"), r.get("case"), r.get("phase") or "", r.get("value"))


CONTROLS = {
    "fa":  lambda rs: all(r["match"] for r in rs if r.get("control")),
    "fb":  lambda rs: any(r["case"] == "__control_verdict" and r.get("match") for r in rs),
    "fc":  lambda rs: any(r["case"].endswith("/uniform_0") and r.get("match") for r in rs),
    "fd":  lambda rs: len({r["observed"] for r in rs
                           if r["case"].startswith("fingerprint_g0_class")}) == 6,
    "fe":  lambda rs: any(r["case"] == "__probe" for r in rs),
    "ff":  lambda rs: _ff_control(rs),
}


def _ff_control(rs):
    b = {r["sub"]: r["observed"] for r in rs
         if r.get("form_label") == "texlod/form05_baseline" and r.get("sub", "").startswith("a_w")}
    return b.get("a_w1.0") == "1100" and b.get("a_w2.0") == "2000"


def captured(runs):
    a, b = load(runs[0]), load(runs[1])
    rc = 0
    for fam in sorted(set(a) | set(b)):
        ra, rb = a.get(fam, []), b.get(fam, [])
        ok = CONTROLS.get(fam, lambda rs: True)
        ca, cb = ok(ra), ok(rb)
        print("CONTROL %s run01=%s run02=%s" % (fam, "FIRED" if ca else "NOT-FIRED",
                                                "FIRED" if cb else "NOT-FIRED"))
        if not (ca and cb):
            rc = 1
        # cross-run comparison, victims excluded (they are machine state, not encoding state)
        def idx(rs):
            m = {}
            for r in rs:
                # victims are machine state, not encoding state (FIELD-SWEEP-PROTOCOL sec.7);
                # rerun records are per-attempt noise; for a majority record only the
                # VERDICT is comparable, not the individual vote string.
                if r.get("outcome") == "victim" or r.get("phase") == "rerun":
                    continue
                if r.get("phase") == "majority":
                    r = dict(r); r["observed"] = None
                m.setdefault(key(r), r)
            return m
        ia, ib = idx(ra), idx(rb)
        common = set(ia) & set(ib)
        diffs = [k for k in common
                 if str(ia[k].get("observed")) != str(ib[k].get("observed"))
                 or ia[k].get("outcome") != ib[k].get("outcome")]
        onlya, onlyb = set(ia) - set(ib), set(ib) - set(ia)
        print("CROSSRUN %s common=%d disagree=%d only_run01=%d only_run02=%d"
              % (fam, len(common), len(diffs), len(onlya), len(onlyb)))
        for k in sorted(diffs, key=str)[:20]:
            print("   DIFF %s run01=%r/%s run02=%r/%s" % (
                k, ia[k].get("observed"), ia[k].get("outcome"),
                ib[k].get("observed"), ib[k].get("outcome")))
        if diffs:
            rc = 1
        # every non-ok case must carry a fault classification
        miss = [r["case"] for r in ra
                if r.get("outcome") in ("fault", "hang", "victim") and not r.get("fault_class")
                and r.get("phase") != "majority"]
        if miss:
            print("   MISSING-FAULT-CLASS %d e.g. %s" % (len(miss), miss[:3]))
            rc = 1
    print("CAPTURED %s" % ("FAIL" if rc else "PASS"))
    return rc


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--captured", nargs=2, metavar=("RUN01", "RUN02"))
    a = ap.parse_args()
    if a.preflight:
        sys.exit(preflight())
    if a.captured:
        sys.exit(captured(a.captured))
    ap.print_help()
