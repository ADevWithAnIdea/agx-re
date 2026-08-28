#!/usr/bin/env python3
"""EXP-0141 gates. No GPU work here.

  --selftest     structural checks on the frozen case matrix
  --preflight    authored-blob hashes match CAPTURE_CONTRACT.json
  --between-runs run01 exists, is complete, and its controls held
  --captured     both runs present, compared case-for-case
"""
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "harness"))
import sweepdefs as SD  # noqa: E402
import carriers as C  # noqa: E402

RUNS = ("m4-20260828-run01", "m4-20260828-run02")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _sites_stub():
    """Structural self-test does not touch the GPU or the compiler, so it uses
    a synthetic site table with the same shape the locator produces."""
    return {k: (m, off, ln, bytes(range(ln)))
            for k, (m, off, ln) in SD.SITES.items()}


def selftest():
    bad = []
    arms = SD.build_all(_sites_stub())
    names = [a["arm"] for a in arms]
    if len(names) != len(set(names)):
        bad.append("duplicate arm names")
    n = sum(len(a["cases"]) for a in arms)
    if n < 20000:
        bad.append("case matrix shrank to %d" % n)
    # every arm carries >= 1 case; every dense byte arm has 256 swept values
    for a in arms:
        if not a["cases"]:
            bad.append("empty arm %s" % a["arm"])
        vals = [c["value"] for c in a["cases"] if not str(c["field"]).startswith("_")]
        if a["arm"].endswith(tuple("b%d" % i for i in range(14))) and len(set(vals)) != 256:
            bad.append("%s is not a dense 256 sweep (%d distinct)" % (a["arm"], len(set(vals))))
    # falsifiers exist
    fals = [c for a in arms for c in a["cases"] if c["expect_match"] is False]
    if len(fals) < 6:
        bad.append("fewer than 6 pre-registered falsifiers (%d)" % len(fals))
    base = [c for a in arms for c in a["cases"] if c["expect_match"] is True]
    if len(base) < 6:
        bad.append("fewer than 6 pre-registered baselines (%d)" % len(base))
    # oracles are host-computed and self-consistent
    if C.CARRIERS["tgtile"]["oracle"][0][0] != 3:
        bad.append("tile oracle wrong at lane 0")
    if C.CARRIERS["attg"]["oracle"][0][0] != sum(C.ATOM_A[0:16]):
        bad.append("attg oracle wrong")
    if abs(SD.ALU_ORACLE[0][0] - (-7.0)) > 0:
        bad.append("ALU oracle drifted from -7.0")
    if abs(SD.FWD_ORACLE[0][0] - (-8.5)) > 0:
        bad.append("FWD oracle drifted from -8.5")
    for b in bad:
        print("FAIL:", b)
    print("selftest: %d arms, %d cases, %d falsifiers, %d baselines -> %s"
          % (len(arms), n, len(fals), len(base), "FAIL" if bad else "PASS"))
    return 1 if bad else 0


def preflight():
    cc = json.loads((HERE / "CAPTURE_CONTRACT.json").read_text())
    bad = []
    for rel, want in sorted(cc["authored_sha256"].items()):
        got = sha(HERE / rel)
        if got != want:
            bad.append("%s sha256 %s != frozen %s" % (rel, got[:16], want[:16]))
    for b in bad:
        print("FAIL:", b)
    print("preflight: %d authored blobs -> %s"
          % (len(cc["authored_sha256"]), "FAIL" if bad else "PASS"))
    return 1 if bad else 0


def _load(run):
    p = HERE / "raw" / run / "sweep.jsonl"
    return [json.loads(l) for l in p.open()] if p.exists() else None


def _controls_held(rows):
    bad = []
    for r in rows:
        if r["expect_match"] is not None and r["match"] != r["expect_match"]:
            bad.append("%s/%s predicted %s got %s" % (r["arm"], r["field"],
                                                      r["expect_match"], r["match"]))
    return bad


def between_runs():
    rows = _load(RUNS[0])
    if rows is None:
        print("FAIL: run01 missing")
        return 1
    bad = _controls_held(rows)
    for b in bad:
        print("FAIL:", b)
    print("between-runs: run01 has %d records, %d control violations -> %s"
          % (len(rows), len(bad), "FAIL" if bad else "PASS"))
    return 1 if bad else 0


def captured():
    a, b = _load(RUNS[0]), _load(RUNS[1])
    if a is None or b is None:
        print("FAIL: both runs required")
        return 1
    ka = {(r["arm"], r["i"]): r for r in a}
    kb = {(r["arm"], r["i"]): r for r in b}
    only = set(ka) ^ set(kb)
    diff = [k for k in set(ka) & set(kb)
            if (ka[k]["outcome"], ka[k]["match"], ka[k]["observed"]) !=
               (kb[k]["outcome"], kb[k]["match"], kb[k]["observed"])]
    print("captured: run01=%d run02=%d, %d cases only in one run, %d cases differing"
          % (len(a), len(b), len(only), len(diff)))
    for k in sorted(diff)[:20]:
        print("   DIFF %s/%d: %s %s | %s %s" % (k[0], k[1], ka[k]["outcome"],
              str(ka[k]["observed"])[:60], kb[k]["outcome"], str(kb[k]["observed"])[:60]))
    va, vb = _controls_held(a), _controls_held(b)
    for x in va + vb:
        print("FAIL control:", x)
    return 1 if (only or va or vb) else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for f in ("selftest", "preflight", "between-runs", "captured"):
        ap.add_argument("--" + f, action="store_true")
    a = ap.parse_args()
    rc = 0
    if a.selftest:
        rc |= selftest()
    if a.preflight:
        rc |= preflight()
    if getattr(a, "between_runs"):
        rc |= between_runs()
    if a.captured:
        rc |= captured()
    sys.exit(rc)
