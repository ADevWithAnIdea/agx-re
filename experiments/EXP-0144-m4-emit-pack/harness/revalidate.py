#!/usr/bin/env python3
"""EXP-0144 REVALIDATION pass — majority-of-N per case, in the EXP-0139/EXP-0141 style.

  python3 harness/revalidate.py --run-id ID --only INSTR [--reps 3] [--max-reps 5]

Why this exists: run03/run04/run05 were captured across a window in which the host's
MTLCompilerService collapsed machine-wide. A single observation of `fault` or `hang`
in that window is evidence about the MACHINE, not about the encoding, and these
labels feed a compiler. Every case here is therefore measured N times and the verdict
is the MAJORITY over attempts that are themselves clean:

  * an attempt whose OS fault string is `...ErrorInnocentVictim` is a sibling
    experiment's fault surfacing in our command buffer -> discarded, re-run;
  * an attempt returning STATUS OK with the integrity sentinel ABSENT executed
    nothing (EXP-0141's contamination mode) -> discarded, re-run;
  * an attempt taken while the unmutated carrier baseline is failing is inside a
    cascade -> the case is marked invalid and the shard stops.

Schema fix carried here: a case that is never dispatched records `outcome: null` and
`validity: "not_run"`. The earlier runs recorded skipped cases as `outcome:"hang"`,
which makes an outcome-only cross-run comparison look 58% divergent when the
measurement-vs-measurement disagreement is 0.37%.
"""
import argparse, collections, hashlib, json, os, platform, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb                                   # noqa: E402  read-only
import probe                                   # noqa: E402
import casematrix as CM                         # noqa: E402
from oracle import selftest as O_selftest       # noqa: E402
from run import classify, sentinel_state, vec0_bits   # noqa: E402  same definitions

BASELINE_EVERY = 100          # EXP-0141 cadence
MAX_DIRTY_ATTEMPTS = 4        # per rep, for InnocentVictim / sentinel-absent
MAX_HANGS_PER_AREA = 2
GLOBAL_HANG_CAP = 12


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def one_attempt(bench, case, vbits):
    """A single clean measurement, or (None, reason) if it could not be made clean."""
    for _ in range(MAX_DIRTY_ATTEMPTS):
        status, ob, sent, gt, err = bench.run(case["splices"])
        sst = sentinel_state(sent, vbits)
        rec = {"status": status, "err": err, "sentinel": sst,
               "obs": ob[:32].hex() if ob else None}
        if status == "CMDBUF_ERROR" and err and "InnocentVictim" in err:
            rec["discarded"] = "innocent_victim"
            yield rec
            continue
        if status == "OK" and sst == "absent":
            rec["discarded"] = "sentinel_absent"
            yield rec
            continue
        yield rec
        return
    return


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--only", default=None)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--max-reps", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--run-group", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out-dir", default=None, help="NON-RECORDED smoke destination")
    a = ap.parse_args()

    if O_selftest():
        sys.exit("ORACLE SELF-TEST FAILED")
    run_dir = (Path(a.out_dir) / a.run_id) if a.out_dir else (EXP / "raw" / a.run_id)
    if run_dir.exists():
        sys.exit("run id %s exists -- never reuse or overwrite a run id" % a.run_id)
    run_dir.mkdir(parents=True)
    work = EXP / "work" / ("rv_" + a.run_id)
    work.mkdir(parents=True, exist_ok=True)
    bindir, src = EXP / "work" / "bin", EXP / "kernels" / "carriers.metal"

    cases = CM.build_cases()
    targets = [t for t in CM.TARGETS if not a.only or t["key"] == a.only]
    keys = {t["mnem"] for t in targets}

    carriers, anchors = {}, {}
    for t in targets:
        c = probe.Carrier(src, t["carrier"], bindir, work)
        got = c.main[t["off"]:t["off"] + len(bytes.fromhex(t["anchor"]))].hex()
        if got != t["anchor"]:
            sys.exit("ANCHOR MISMATCH %s: got %s want %s" % (t["carrier"], got, t["anchor"]))
        carriers[t["carrier"]] = c
        anchors[t["key"]] = {"main_sha256": hashlib.sha256(c.main).hexdigest(),
                             "off": t["off"], "anchor": t["anchor"]}

    (run_dir / "00_env.json").write_text(json.dumps({
        "run_id": a.run_id, "run_group": a.run_group, "kind": "REVALIDATION",
        "reps": a.reps, "max_reps": a.max_reps, "only": a.only,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sw_vers": subprocess.run(["sw_vers"], capture_output=True, text=True).stdout,
        "git_rev": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                  capture_output=True, text=True).stdout.strip(),
        "batch": ["EXP-0138", "EXP-0140", "EXP-0144"], "n_gpu_contending": 3,
        "sha_carriers": sha(src), "sha_casematrix": sha(HERE / "casematrix.py"),
        "sha_oracle": sha(HERE / "oracle.py"), "sha_probe": sha(HERE / "probe.py"),
        "sha_revalidate": sha(HERE / "revalidate.py"), "anchors": anchors,
        "platform": platform.platform()}, indent=1, sort_keys=True))

    out = open(run_dir / "sweep.jsonl", "a")
    order = [c for c in cases if c["instr"] in keys]
    if a.limit:
        order = order[:a.limit]
    hangs, stopped, blchecks, cascades = collections.Counter(), set(), [], []
    total_hangs, stop_all = [0], [False]
    t0, n = time.time(), 0
    carrier = order[0]["carrier"]
    tgt0 = next(t for t in CM.TARGETS if t["carrier"] == carrier)
    bench = probe.Bench(carriers[carrier], bindir, 1,
                        CM.invec_bytes(carrier, CM.FIXED[carrier][1]), 0,
                        CM.NOUT_BYTES, timeout=a.timeout)

    def baseline_ok(tries=4):
        sp = ({tgt0["off"] + i: b for i, b in enumerate(bytes.fromhex(tgt0["synth"]))}
              if tgt0["mode"] == "A" else {})
        keep = bench._cur_in
        bench.set_input(CM.invec_bytes(carrier, CM.FIXED[carrier][1]))
        e0 = CM.expect(carrier, CM.FIXED[carrier][1])
        vb = vec0_bits(carrier, CM.FIXED[carrier][1])
        ok = False
        for k in range(tries):
            st, ob, sent, gt, er = bench.run(sp)
            w = list(struct.unpack("<%dI" % (len(ob) // 4), ob)) if ob else []
            ok = (st == "OK" and sentinel_state(sent, vb) == "clean"
                  and all(e0[j] is None or (j < len(w) and w[j] == e0[j]) for j in e0))
            if ok:
                break
            time.sleep(0.25 * (k + 1))
        bench.set_input(keep)
        return ok

    for c in order:
        exp = CM.expect(c["carrier"], c["vec"])
        tgt = next(t for t in CM.TARGETS if t["mnem"] == c["instr"])
        ilen = len(bytes.fromhex(tgt["synth"] if tgt["mode"] == "A" else tgt["anchor"]))
        ib = bytearray(carriers[c["carrier"]].main[tgt["off"]:tgt["off"] + ilen])
        for off, v in c["splices"].items():
            if tgt["off"] <= off < tgt["off"] + ilen:
                ib[off - tgt["off"]] = v
        try:
            decode = isadb.decode_one(bytes(ib), 0).get("mnemonic")
        except Exception:
            decode = None
        base = {"i": c["i"], "arm": c["arm"], "name": c["name"], "instr": c["instr"],
                "field": c["field"], "value": c["value"], "bytes": bytes(ib).hex(),
                "carrier": c["carrier"], "note": c["note"], "decode": decode,
                "oracle": {str(k): v for k, v in exp.items()}}
        if c.get("byte") is not None:
            base["byte"] = c["byte"]

        area = (c["instr"], c.get("byte"))
        if stop_all[0] or area in stopped:
            # SCHEMA FIX: a case that was never dispatched has NO outcome.
            base.update(outcome=None, validity="not_run", match=False, attempts=[],
                        votes={}, n_clean=0,
                        reason="area stopped after %d genuine hangs" % MAX_HANGS_PER_AREA
                               if area in stopped else "shard stopped")
            out.write(json.dumps(base, sort_keys=True) + "\n"); out.flush()
            n += 1
            continue

        bench.set_input(CM.invec_bytes(c["carrier"], c["vec"]))
        vbits = vec0_bits(c["carrier"], c["vec"])
        attempts, votes = [], collections.Counter()
        obs_by_outcome = {}
        target_reps = a.reps
        rep = 0
        while rep < target_reps:
            got_clean = False
            for rec in one_attempt(bench, c, vbits):
                attempts.append(rec)
                if rec.get("discarded"):
                    continue
                ob = bytes.fromhex(rec["obs"]) if rec["obs"] else b""
                w = list(struct.unpack("<%dI" % (len(ob) // 4), ob)) if ob else []
                oc = classify(rec["status"], rec["err"], w, exp,
                              CM.RESULT_SLOTS[c["carrier"]])
                votes[oc] += 1
                obs_by_outcome.setdefault(oc, rec["obs"])
                got_clean = True
            rep += 1
            if not got_clean:
                break
            if rep == target_reps and votes:
                top, cnt = votes.most_common(1)[0]
                # escalate only when the reps did not agree
                if cnt <= rep // 2 or len(votes) > 1:
                    if target_reps < a.max_reps:
                        target_reps = a.max_reps

        n_clean = sum(votes.values())
        if not votes:
            outcome, validity = None, "invalid_run"
        else:
            top, cnt = votes.most_common(1)[0]
            if cnt * 2 > n_clean:
                outcome, validity = top, "valid"
            else:
                outcome, validity = top, "indeterminate"

        # A fault or hang verdict is only credible if the carrier itself is healthy.
        if outcome in ("fault", "hang"):
            bl = baseline_ok()
            base["baseline_after"] = bl
            if not bl:
                validity = "invalid_run"
                cascades.append(c["i"])
                cascaded = True
                stop_all[0] = True
            if outcome == "hang" and validity == "valid":
                hangs[str(area)] += 1
                total_hangs[0] += 1
                if hangs[str(area)] >= MAX_HANGS_PER_AREA:
                    stopped.add(area)
                if total_hangs[0] >= GLOBAL_HANG_CAP:
                    stop_all[0] = True

        base.update(outcome=outcome, validity=validity,
                    match=(outcome == "ok" and validity == "valid"),
                    votes=dict(votes), n_clean=n_clean, n_attempts=len(attempts),
                    unanimous=(len(votes) == 1 and n_clean >= a.reps),
                    observed=obs_by_outcome.get(outcome), attempts=attempts)
        out.write(json.dumps(base, sort_keys=True) + "\n")
        out.flush(); os.fsync(out.fileno())
        n += 1
        if n % BASELINE_EVERY == 0:
            bl = baseline_ok()
            blchecks.append({"after_case": c["i"], "ok": bl})
            if not bl:
                print("  !! BASELINE FAILED after case %d -- CASCADE, stopping shard"
                      % c["i"], flush=True)
                cascades.append(c["i"]); stop_all[0] = True
        if n % 500 == 0:
            print("  %6d/%d  %.1f/s  hangs=%s" % (n, len(order), n / (time.time() - t0),
                                                  dict(hangs)), flush=True)
    bench.close(); out.close()
    (run_dir / "01_summary.json").write_text(json.dumps(
        {"n_cases": n, "elapsed_s": round(time.time() - t0, 2),
         "hangs": dict(hangs), "total_hangs": total_hangs[0],
         "stopped_areas": sorted(str(x) for x in stopped), "stopped_all": stop_all[0],
         "cascade_cases": cascades, "baseline_checks": blchecks,
         "baseline_checks_passed": sum(1 for b in blchecks if b["ok"]),
         "baseline_checks_total": len(blchecks)}, indent=1, sort_keys=True))
    print("DONE %s: %d cases in %.1fs, baselines %d/%d passed"
          % (a.run_id, n, time.time() - t0,
             sum(1 for b in blchecks if b["ok"]), len(blchecks)))


if __name__ == "__main__":
    main()
