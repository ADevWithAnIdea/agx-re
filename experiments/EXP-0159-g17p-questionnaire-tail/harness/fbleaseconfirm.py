#!/usr/bin/env python3
"""EXP-0159 — FIELD-SWEEP-PROTOCOL.md sec.7A confirmation pass for family FB.

Majority-of-3 under concurrent load is NOT sufficient for a `fault` verdict
(EXP-0153).  More importantly for THIS experiment: a case that faults produces no
output, so a spurious fault could in principle HIDE an FP64-capable encoding.
This pass therefore takes every FB encoding that was recorded fault/hang in BOTH
gated runs, re-runs it 5x UNDER THE GPU LEASE, and re-classifies whatever it
produces against the same host-computed oracle set.

  python3 fbleaseconfirm.py --run-a <id> --run-b <id> --out-run <id> [--reps 5]

Authored by the clean-room RE team.  Clean-room: OWN-SHADER splice + HW-PROBE.
"""
import argparse, collections, hashlib, json, os, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run as R   # reuse the frozen oracle/classifier and the shdump/parse plumbing


def faults_in_both(a, b):
    def idx(path):
        m = {}
        for ln in open(path):
            r = json.loads(ln)
            if r.get("phase") != "sweep":
                continue
            m[(r.get("field"), r.get("value"))] = r.get("outcome")
        return m
    ia = idx(os.path.join(ROOT, "raw", a, "fb.jsonl"))
    ib = idx(os.path.join(ROOT, "raw", b, "fb.jsonl"))
    out = []
    for k, va in ia.items():
        vb = ib.get(k)
        if va in ("fault", "hang") and vb in ("fault", "hang"):
            out.append(k)
    return sorted(out, key=lambda k: (k[0] or "", k[1] if k[1] is not None else -1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-a", required=True)
    ap.add_argument("--run-b", required=True)
    ap.add_argument("--out-run", required=True)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--bin", default=os.path.expanduser("~/agxre/EXP-0159/bin"))
    ap.add_argument("--work", default=os.path.expanduser("~/agxre/EXP-0159/work"))
    args = ap.parse_args()
    args.rawdir = os.path.join(ROOT, "raw", args.out_run)
    os.makedirs(args.rawdir, exist_ok=True)
    sink = R.Sink(args.rawdir)

    targets = faults_in_both(args.run_a, args.run_b)
    sink.w("fbconfirm", {"family": "fbconfirm", "case": "__scope", "value": len(targets),
                         "observed": json.dumps(targets)[:4000], "outcome": "ok",
                         "note": "encodings recorded fault/hang in BOTH gated runs; re-run %dx "
                                 "under gpulease per FIELD-SWEEP-PROTOCOL sec.7A" % args.reps})

    from persistrun import PersistRunner
    wd = os.path.join(args.work, "fbconfirm")
    os.makedirs(wd, exist_ok=True)
    src = os.path.join(ROOT, "kernels", "u64op.metal")
    arch = os.path.join(wd, "u64op.bin")
    cp = subprocess.run([R.SHDUMP, "-o", arch, "-f", "k", src], capture_output=True, text=True)
    if cp.returncode != 0:
        sink.w("fbconfirm", {"family": "fbconfirm", "case": "__compile", "outcome": "undecodable",
                             "note": (cp.stdout + cp.stderr)[:400]})
        return
    p = subprocess.run([sys.executable, R.AGXPARSE, arch, "--locate", "_agc.main"],
                       capture_output=True, text=True)
    abs_off, mlen = [int(x, 0) for x in p.stdout.split()[:2]]
    blob = open(arch, "rb").read()
    main_bytes = blob[abs_off:abs_off + mlen]
    dis, _ = R.disasm(main_bytes)
    tgt = next(d for d in dis if d.get("mnemonic") == "iadd2")
    ioff = tgt["offset"]
    sink.w("fbconfirm", {"family": "fbconfirm", "case": "__carrier",
                         "observed": main_bytes.hex(), "outcome": "ok",
                         "main_sha256": hashlib.sha256(main_bytes).hexdigest(),
                         "note": "iadd2 at _agc.main+0x%x" % ioff})

    ab = b"".join(struct.pack("<Q", r[0]) for r in R.F64_ROWS)
    bb = b"".join(struct.pack("<Q", r[1]) for r in R.F64_ROWS)
    pa, pb, pp = (os.path.join(wd, n) for n in ("a.bin", "b.bin", "poison.bin"))
    open(pa, "wb").write(ab); open(pb, "wb").write(bb)
    open(pp, "wb").write(b"\xa5" * (8 * len(R.F64_ROWS)))
    r = PersistRunner(source=src, function="k", fast_math=True, agxrun_persist=R.PERSIST)
    spliced = os.path.join(wd, "spliced.bin")

    def dispatch(mm):
        nb = bytearray(blob)
        nb[abs_off:abs_off + mlen] = mm
        open(spliced, "wb").write(bytes(nb))
        return r.request(archive=spliced, grid=len(R.F64_ROWS), tg=len(R.F64_ROWS),
                         ins={0: pp, 1: pa, 2: pb}, outs={0: 8 * len(R.F64_ROWS)}, timeout=8.0)

    base = dispatch(main_bytes)
    sink.w("fbconfirm", {"family": "fbconfirm", "case": "baseline_isolated",
                         "observed": base["outs"].get(0, b"").hex(),
                         "outcome": "ok" if base["status"] == "OK" else "fault",
                         "fault_class": base.get("error") or ""})
    fp64_any = []
    for field, val in targets:
        boff = int(field.split("+")[1])
        mm = bytearray(main_bytes)
        mm[ioff + boff] = val
        votes, seen = [], []
        for i in range(args.reps):
            resp = dispatch(bytes(mm))
            outs = resp["outs"].get(0, b"")
            vals, classes = [], []
            for j, (aa, bbv) in enumerate(R.F64_ROWS):
                w = outs[j * 8:(j + 1) * 8]
                ov = struct.unpack("<Q", w)[0] if len(w) == 8 else None
                vals.append(ov)
                classes.append(R.fb_classify(ov, aa, bbv) if ov is not None else "missing")
            fp = R.fb_fp64_hit(vals)
            st = resp["status"]
            err = resp.get("error") or ""
            outcome = ("hang" if st == "HANG" else
                       "victim" if "victim" in err.lower() else
                       "fault" if st != "OK" else "ok")
            votes.append(outcome)
            seen.append(",".join("%016x" % v if v is not None else "" for v in vals))
            if fp:
                fp64_any.append((field, val, fp))
            sink.w("fbconfirm", {"family": "fbconfirm",
                                 "case": "iadd2.b%d=0x%02x" % (boff, val),
                                 "field": field, "value": val, "rep": i,
                                 "observed": seen[-1], "oracle_class": ",".join(classes),
                                 "fp64_hit": fp, "outcome": outcome, "fault_class": err,
                                 "isolated": True})
        maj = max(set(votes), key=votes.count)
        sink.w("fbconfirm", {"family": "fbconfirm", "case": "iadd2.b%d=0x%02x" % (boff, val),
                             "field": field, "value": val, "phase": "isolated_verdict",
                             "observed": ",".join(votes), "outcome": maj, "reps": args.reps,
                             "isolated": True,
                             "note": "confirmed under gpulease per FIELD-SWEEP-PROTOCOL sec.7A"})
    sink.w("fbconfirm", {"family": "fbconfirm", "case": "__verdict",
                         "value": len(targets), "observed": json.dumps(fp64_any)[:2000],
                         "match": len(fp64_any) == 0, "outcome": "ok",
                         "note": "%d doubly-faulting encodings re-run %dx in isolation; %d produced "
                                 "a binary64 result on all four rows" % (len(targets), args.reps,
                                                                        len(fp64_any))})
    r.close()
    sink.close()


if __name__ == "__main__":
    main()
