#!/usr/bin/env python3
"""EXP-0144 runner. Executes the FROZEN case matrix on the local M4 and appends
one JSON object per case to raw/<run_id>/sweep.jsonl, flushed immediately.

  python3 harness/run.py --run-id m4_YYYYMMDD_runNN [--only INSTR[,INSTR]]

Safety: per-request watchdog (persistrun), a hard cap of 2 genuine hangs per
instruction (that instruction's remaining cases are then recorded as skipped),
and append+fflush per case so a kill costs at most the case in flight.
"""
import argparse, hashlib, json, os, platform, struct, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb                    # noqa: E402  read-only
import probe                    # noqa: E402
import casematrix as CM         # noqa: E402

MAX_HANGS = 2
RETRY_STATUSES = ("CMDBUF_ERROR",)   # only retried when the message says InnocentVictim


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def classify(status, err, obs_words, exp, result_slots):
    if status == "HANG":
        return "hang"
    if status != "OK":
        return "fault"
    res_obs = [obs_words[i] if i < len(obs_words) else None for i in result_slots]
    res_exp = [exp.get(i) for i in result_slots]
    all_match = all(exp.get(k) is None or (k < len(obs_words) and obs_words[k] == exp[k])
                    for k in exp)
    if all_match:
        return "ok"
    if all(v == 0 for v in res_obs) and any(v not in (0, None) for v in res_exp):
        return "silent_zero"
    return "wrong_value"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--only", default=None, help="comma-separated instruction keys")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--out-dir", default=None,
                    help="NON-RECORDED smoke destination; omit for raw/ (the real capture)")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    run_dir = (Path(a.out_dir) / a.run_id) if a.out_dir else (EXP / "raw" / a.run_id)
    if run_dir.exists():
        sys.exit("run id %s already exists -- never reuse or overwrite a run id" % a.run_id)
    run_dir.mkdir(parents=True)
    work = EXP / "work" / ("run_" + a.run_id)
    work.mkdir(parents=True, exist_ok=True)
    bindir = EXP / "work" / "bin"
    src = EXP / "kernels" / "carriers.metal"

    cases = CM.build_cases()
    only = set(a.only.split(",")) if a.only else None
    targets = [t for t in CM.TARGETS if not only or t["key"] in only]
    keys = {t["mnem"] for t in targets}

    # ---- compile every carrier once, assert the frozen anchors --------------
    carriers, anchors = {}, {}
    for t in targets:
        c = probe.Carrier(src, t["carrier"], bindir, work)
        got = c.main[t["off"]:t["off"] + len(bytes.fromhex(t["anchor"]))].hex()
        if got != t["anchor"]:
            sys.exit("ANCHOR MISMATCH %s: at 0x%x got %s want %s"
                     % (t["carrier"], t["off"], got, t["anchor"]))
        carriers[t["carrier"]] = c
        anchors[t["key"]] = dict(main_sha256=hashlib.sha256(c.main).hexdigest(),
                                 main_len=len(c.main), off=t["off"], anchor=t["anchor"],
                                 region_off=c.region_off, region_len=c.region_len)

    env = dict(
        run_id=a.run_id, started_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        host_platform=platform.platform(), machine=platform.machine(),
        sw_vers=subprocess.run(["sw_vers"], capture_output=True, text=True).stdout,
        git_rev=subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                               capture_output=True, text=True).stdout.strip(),
        git_dirty=bool(subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                                      capture_output=True, text=True).stdout.strip()),
        n_cases=len(cases), only=a.only, timeout_s=a.timeout,
        sha_carriers=sha(src), sha_casematrix=sha(HERE / "casematrix.py"),
        sha_oracle=sha(HERE / "oracle.py"), sha_probe=sha(HERE / "probe.py"),
        sha_run=sha(HERE / "run.py"), sha_db_json=sha(REPO / "tools" / "agx-isa" / "db.json"),
        anchors=anchors)
    (run_dir / "00_env.json").write_text(json.dumps(env, indent=1, sort_keys=True))

    out = open(run_dir / "sweep.jsonl", "a")
    hangs, stopped = {}, set()
    order = sorted([c for c in cases if c["instr"] in keys],
                   key=lambda c: (c["carrier"], c["i"]))
    if a.limit:
        order = order[:a.limit]
    t0 = time.time()
    cur_carrier, bench = None, None
    n = 0
    for c in order:
        if cur_carrier != c["carrier"]:
            if bench:
                bench.close()
            cur_carrier = c["carrier"]
            bench = probe.Bench(carriers[cur_carrier], bindir, 1,
                                CM.invec_bytes(cur_carrier, CM.FIXED[cur_carrier][1]),
                                0, CM.NOUT_BYTES, timeout=a.timeout)
        exp = CM.expect(c["carrier"], c["vec"])
        tgt = next(t for t in CM.TARGETS if t["mnem"] == c["instr"])
        ilen = len(bytes.fromhex(tgt["synth"] if tgt["mode"] == "A" else tgt["anchor"]))
        instr_bytes = bytearray(carriers[c["carrier"]].main[tgt["off"]:tgt["off"] + ilen])
        for off, v in c["splices"].items():
            if tgt["off"] <= off < tgt["off"] + ilen:
                instr_bytes[off - tgt["off"]] = v
        try:
            dec = isadb.decode_one(bytes(instr_bytes), 0)
            decode = dec.get("mnemonic")
        except Exception:
            decode = None

        if c["instr"] in stopped:
            rec = dict(i=c["i"], arm=c["arm"], name=c["name"], instr=c["instr"],
                       field=c["field"], value=c["value"], bytes=bytes(instr_bytes).hex(),
                       observed=None, oracle={str(k): v for k, v in exp.items()},
                       match=False, outcome="skipped_after_hangs", carrier=c["carrier"],
                       note=c["note"], decode=decode, status="SKIPPED", retries=0)
            out.write(json.dumps(rec, sort_keys=True) + "\n"); out.flush()
            n += 1
            continue

        bench.set_input(CM.invec_bytes(c["carrier"], c["vec"]))
        retries = 0
        while True:
            status, ob, gt, err = bench.run(c["splices"])
            if status == "CMDBUF_ERROR" and err and "InnocentVictim" in err and retries < 3:
                retries += 1
                continue
            break
        words = list(struct.unpack("<%dI" % (len(ob) // 4), ob)) if ob else []
        outcome = classify(status, err, words, exp, CM.RESULT_SLOTS[c["carrier"]])
        if outcome == "hang":
            hangs[c["instr"]] = hangs.get(c["instr"], 0) + 1
            if hangs[c["instr"]] >= MAX_HANGS:
                stopped.add(c["instr"])
        rec = dict(i=c["i"], arm=c["arm"], name=c["name"], instr=c["instr"],
                   field=c["field"], value=c["value"], bytes=bytes(instr_bytes).hex(),
                   observed=ob[:32].hex() if ob else None,
                   oracle={str(k): v for k, v in exp.items()},
                   match=(outcome == "ok"), outcome=outcome, carrier=c["carrier"],
                   note=c["note"], decode=decode, status=status, retries=retries)
        if c.get("byte") is not None:
            rec["byte"] = c["byte"]
        out.write(json.dumps(rec, sort_keys=True) + "\n")
        out.flush()
        os.fsync(out.fileno())
        n += 1
        if n % 2000 == 0:
            el = time.time() - t0
            print("  %6d/%d  %.0f/s  hangs=%s" % (n, len(order), n / el, hangs), flush=True)
    if bench:
        bench.close()
    out.close()
    (run_dir / "01_summary.json").write_text(json.dumps(
        dict(n_run=n, elapsed_s=round(time.time() - t0, 2), hangs=hangs,
             stopped=sorted(stopped)), indent=1, sort_keys=True))
    print("DONE %s: %d cases in %.1fs hangs=%s" % (a.run_id, n, time.time() - t0, hangs))


if __name__ == "__main__":
    main()
