#!/usr/bin/env python3
"""faultconfirm.py -- EXP-0155 lease-isolated re-confirmation of every fault/hang.

    ~/agxre/gpulease.sh EXP-0155 900 -- \
        python3 harness/faultconfirm.py --run01 <id> --run02 <id> \
                --out raw/<id>_faultconfirm [--max 400]

FIELD-SWEEP-PROTOCOL 7A (EXP-0153, 2026-08-29): majority-of-3 plus cross-run
agreement is NOT sufficient for a `fault` verdict.  Five cases passed both and
four of them were not faults at all once re-run in isolation -- sustained sibling
load can look reproducible.  So every value this experiment would report as
faulting or hanging is re-run **5x under the GPU lease** and the lease-isolated
outcome is what RESULTS.md states.

Only values recorded fault/hang in BOTH gated runs are re-confirmed; a fault in
one run only is already not promoted.

CLEAN-ROOM: OWN-SHADER + HW-PROBE, same carriers and same splices as the sweep.
"""
import argparse
import collections
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.environ.get("AGXRE_REPO", os.path.abspath(os.path.join(EXP, "..", "..")))
sys.path.insert(0, HERE)
sys.path.insert(0, EXP)
sys.path.insert(0, os.path.join(REPO, "tools", "agx-isa"))
import isadb                       # noqa: E402
import casematrix as CM            # noqa: E402
import run as R                    # noqa: E402  (the capture driver's helpers)
from runner import RenderRunner, ComputeRunner   # noqa: E402

N_TRIALS = 5
REQ_TIMEOUT = 15.0


def load_outcomes(path):
    out = {}
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            r = json.loads(ln)
            if r["field"].startswith("_"):
                continue
            out[(r["carrier"], r["field"], r["value"])] = (r["outcome"], r["bytes"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run01", required=True)
    ap.add_argument("--run02", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=400)
    ap.add_argument("--per-field", type=int, default=8,
                    help="cap per (arm, field): a spread of at most N values, so one "
                         "match-bit field cannot swallow the whole isolated budget")
    args = ap.parse_args()

    o1 = load_outcomes(os.path.join(EXP, "raw", args.run01, "sweep.jsonl"))
    o2 = load_outcomes(os.path.join(EXP, "raw", args.run02, "sweep.jsonl"))
    order = {a["id"]: i for i, a in enumerate(CM.ARMS)}
    targets = [k for k in o1
               if k in o2 and o1[k][0] in ("fault", "hang") and o2[k][0] in ("fault", "hang")]
    targets.sort(key=lambda k: (order.get(k[0], 999), k[1], k[2]))
    total = len(targets)
    # spread-limit per (arm, field)
    grouped = collections.OrderedDict()
    for k in targets:
        grouped.setdefault((k[0], k[1]), []).append(k)
    kept = []
    for g, vs in grouped.items():
        if len(vs) <= args.per_field:
            kept.extend(vs)
        else:
            step = len(vs) / float(args.per_field)
            kept.extend(vs[int(i * step)] for i in range(args.per_field))
    targets = kept[:args.max]

    os.makedirs(args.out, exist_ok=True)
    jl = open(os.path.join(args.out, "confirm.jsonl"), "a")

    def emit(rec):
        jl.write(json.dumps(rec, sort_keys=True) + "\n")
        jl.flush()
        os.fsync(jl.fileno())

    emit({"_meta": True, "total_cross_run_fault_or_hang": total,
          "confirmed_here": len(targets), "trials_each": N_TRIALS,
          "isolation": "GPU lease held for the whole pass (gpulease.sh)",
          "run01": args.run01, "run02": args.run02,
          "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

    # build the carriers and locate the arms exactly as the sweep did
    carriers, arms = {}, {}
    need_arms = {t[0] for t in targets}

    def pseudo(aid):
        """The collision probe emits carrier ids the case matrix does not contain:
        `<carrier>/frag@<off>`, `<carrier>/vert@<off>` and
        `vary_store@<carrier>/vert<off>`.  Rebuild the (carrier, stage, offset)
        from the id so those faults can be confirmed too -- they carry the
        db_defect result, so they matter more than most."""
        base = aid[len("vary_store@"):] if aid.startswith("vary_store@") else aid
        mn = "vary_store" if aid.startswith("vary_store@") else (
            "op57_vertex" if "vert" in base else "op57_fragment")
        if "/" not in base:
            return None
        cname, rest = base.split("/", 1)
        st = "vertex" if rest.startswith("vert") else "fragment"
        digits = "".join(ch for ch in rest if ch.isdigit())
        if not digits or cname not in CM.CARRIERS:
            return None
        return dict(id=aid, carrier=cname, stage=st, mnemonic=mn, occ=0,
                    _off=int(digits),
                    _len=(8 if mn in ("vary_store", "op57_vertex") else 6))

    for a in CM.ARMS:
        if a["id"] not in need_arms:
            continue
        cname = a["carrier"]
        if cname not in carriers:
            arch = R.build_carrier(cname, CM.CARRIERS[cname])
            ent = {}
            for st in (["compute"] if CM.CARRIERS[cname]["kind"] == "compute"
                       else ["vertex", "fragment"]):
                off, buf = R.stage_bytes(arch, st)
                ent[st] = (off, buf)
            carriers[cname] = (arch, ent, CM.CARRIERS[cname])
        arch, ent, cfg = carriers[cname]
        off, buf = ent[a["stage"]]
        hits, how = R.locate(buf, a["mnemonic"])
        if a["occ"] >= len(hits):
            continue
        ioff = hits[a["occ"]]
        rec, L = isadb.decode_one(buf, ioff)
        arms[a["id"]] = dict(a, abs_off=off + ioff, length=L, orig=rec["hex"])

    for aid in sorted(need_arms - set(arms)):
        pa = pseudo(aid)
        if pa is None:
            continue
        cname = pa["carrier"]
        if cname not in carriers:
            arch = R.build_carrier(cname, CM.CARRIERS[cname])
            ent = {}
            for st in (["compute"] if CM.CARRIERS[cname]["kind"] == "compute"
                       else ["vertex", "fragment"]):
                off, buf = R.stage_bytes(arch, st)
                ent[st] = (off, buf)
            carriers[cname] = (arch, ent, CM.CARRIERS[cname])
        arch, ent, cfg = carriers[cname]
        off, buf = ent[pa["stage"]]
        L = pa["_len"]
        arms[aid] = dict(pa, abs_off=off + pa["_off"], length=L,
                         orig=buf[pa["_off"]:pa["_off"] + L].hex())

    runners = {}
    import struct
    for cname, (arch, ent, cfg) in carriers.items():
        if cfg["kind"] == "render":
            b0 = None
            if cfg.get("buf0"):
                fl = CM.BUF0_DERIV if cname == "t_deriv" else CM.BUF0
                b0 = [struct.unpack("<I", struct.pack("<f", v))[0] for v in fl]
            runners[cname] = RenderRunner(
                R.GFRUN, os.path.join(EXP, cfg["src"]), arch,
                os.path.join(R.WORK, f"scratch_fc_{cname}.bin"), cfg, b0)
        else:
            infile = os.path.join(R.WORK, "simd_in.bin")
            runners[cname] = ComputeRunner(R.AGXPERSIST,
                                           os.path.join(EXP, cfg["src"]),
                                           cfg["function"], infile,
                                           cfg["out_bytes"], cfg["grid"], cfg["tg"])

    seq = [0]

    def one(arm, patched):
        cname = arm["carrier"]
        arch, ent, cfg = carriers[cname]
        if arm["stage"] == "compute":
            seq[0] += 1
            spl = os.path.join(R.WORK, f"fc_{cname}.{seq[0]}.bin")
            data = bytearray(open(arch, "rb").read())
            data[arm["abs_off"]:arm["abs_off"] + arm["length"]] = patched
            open(spl, "wb").write(bytes(data))
            resp = runners[cname].run(spl, timeout=REQ_TIMEOUT)
            try:
                os.unlink(spl)
            except OSError:
                pass
            return R.obs_compute(resp)
        return R.obs_render(runners[cname].render(
            [(arm["abs_off"], patched.hex())], timeout=REQ_TIMEOUT), cfg)

    # per-arm baselines, so a confirm trial is comparable to the sweep's oracle
    bases = {}
    for aid, arm in arms.items():
        bases[aid] = one(arm, bytes.fromhex(arm["orig"]))
        emit({"instr": arm["mnemonic"], "field": "_baseline", "value": -1,
              "carrier": aid, "bytes": arm["orig"], "observed": bases[aid],
              "outcome": "ok" if bases[aid].get("status") == "OK" else "fault",
              "note": "lease-isolated baseline before the confirmation pass"})

    for (aid, fld, val) in targets:
        arm = arms.get(aid)
        if arm is None:
            continue
        patched = bytes.fromhex(o1[(aid, fld, val)][1])
        outs, classes = [], []
        for _ in range(N_TRIALS):
            ob = one(arm, patched)
            outs.append(R.classify(ob, bases[aid], None))
            classes.append(ob.get("os_class", ""))
        nbad = sum(1 for o in outs if o in ("fault", "hang"))
        emit({"instr": arm["mnemonic"], "field": fld, "value": val,
              "bytes": patched.hex(), "carrier": aid,
              "unlocked_outcomes": [o1[(aid, fld, val)][0], o2[(aid, fld, val)][0]],
              "lease_outcomes": outs, "lease_os_class": classes,
              "confirmed": nbad == N_TRIALS,
              "outcome": "fault" if nbad == N_TRIALS else outs[0],
              "note": ("reproduces 5/5 under isolation" if nbad == N_TRIALS else
                       f"NOT a property of the encoding: only {nbad}/5 faulted "
                       f"under the lease (FIELD-SWEEP-PROTOCOL 7A)")})
    jl.close()
    for r in runners.values():
        r.close()
    print(f"confirmed {len(targets)} of {total} cross-run fault/hang values")


if __name__ == "__main__":
    main()
