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
from oracle import selftest as O_selftest   # noqa: E402

MAX_HANGS = 2
SENTINEL0 = 0xA5C3F00D
BASELINE_EVERY = 250      # FIELD-SWEEP-PROTOCOL section 7.3
MAX_INVALID_RETRY = 3
GLOBAL_HANG_CAP = 10
MAX_CASCADED_CARRIERS = 3


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


def sentinel_state(sent, vec0_bits):
    """Three-way, NOT two-way. The smoke run showed why: a splice that changes the
    instruction's LENGTH desynchronises the downstream stream and moves the
    sentinel store's index, so the sentinel comes back non-zero but wrong. That is
    a genuine hardware result about the encoding, not the EXP-0141 "nothing
    executed" contamination, and discarding it would delete real evidence.

      "clean"      both sentinel words exactly as the host predicts -> the program
                   ran and the paths around the instruction were untouched
      "perturbed"  sentinel non-zero but not as predicted -> the program ran and
                   the splice reached BEYOND the instruction (stream desync)
      "absent"     sentinel entirely zero / missing -> nothing executed => invalid
    """
    if not sent or len(sent) < 8:
        return "absent"
    w0, w1 = struct.unpack("<II", sent[:8])
    if w0 == SENTINEL0 and w1 == ((vec0_bits ^ 0x5A5A5A5A) & 0xFFFFFFFF):
        return "clean"
    if any(sent[:8]):
        return "perturbed"
    return "absent"


def vec0_bits(carrier, vec):
    """The 32 bits the carrier's sentinel line reads as `a[t+0]`, computed on the
    HOST. c_ph2's `a` is half2*, so its a[0] is the FIRST TWO halves."""
    if carrier == "c_ph2":
        return struct.unpack("<I", struct.pack("<ee", vec[0], vec[1]))[0]
    ch = CM.FIXED[carrier][0][-1]
    return struct.unpack("<I", struct.pack("<" + ch, vec[0]))[0]


def measure(bench, case, vbits):
    """One measurement, with the FIELD-SWEEP-PROTOCOL section 7 guards:
    InnocentVictim is machine evidence not field evidence (retried); a missing
    integrity sentinel is `invalid_run` not a result (retried); and a fault or a
    hang is NEVER concluded from a single observation (confirmed by a re-run)."""
    attempts = []
    for _k in range(MAX_INVALID_RETRY + 1):
        status, ob, sent, gt, err = bench.run(case["splices"])
        sst = sentinel_state(sent, vbits)
        attempts.append({"status": status, "err": err, "sentinel": sst,
                         "sent": sent[:8].hex() if sent else None})
        if status == "CMDBUF_ERROR" and err and "InnocentVictim" in err:
            continue                     # sibling experiment's fault, not ours
        if status == "OK" and sst == "absent":
            continue                     # nothing executed -> not a measurement
        break
    sst = sentinel_state(sent, vbits)
    validity = "invalid_run" if (status == "OK" and sst == "absent") else "valid"
    return status, ob, sent, err, attempts, validity, sst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--only", default=None, help="comma-separated instruction keys")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--out-dir", default=None,
                    help="NON-RECORDED smoke destination; omit for raw/ (the real capture)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--run-group", default=None,
                    help="logical run this shard belongs to; the analysis merges "
                         "all shards of a group. One process per instrument keeps a "
                         "host-level wedge from costing every other instrument.")
    a = ap.parse_args()

    run_dir = (Path(a.out_dir) / a.run_id) if a.out_dir else (EXP / "raw" / a.run_id)
    if run_dir.exists():
        sys.exit("run id %s already exists -- never reuse or overwrite a run id" % a.run_id)
    run_dir.mkdir(parents=True)
    work = EXP / "work" / ("run_" + a.run_id)
    work.mkdir(parents=True, exist_ok=True)
    bindir = EXP / "work" / "bin"
    src = EXP / "kernels" / "carriers.metal"

    # PRE-FLIGHT: the host oracle must be total over every case's vector BEFORE a
    # single dispatch. run01 crashed 3,137 cases in on an fp16 overflow the oracle
    # could not express; a partial capture is retained but never reused, so the
    # check is now unconditional.
    ofails = []
    for _c in CM.build_cases():
        try:
            CM.expect(_c["carrier"], _c["vec"])
            CM.invec_bytes(_c["carrier"], _c["vec"])
            vec0_bits(_c["carrier"], _c["vec"])
        except Exception as _e:
            ofails.append("%s: %s: %s" % (_c["name"], type(_e).__name__, _e))
    if ofails:
        sys.exit("ORACLE PRE-FLIGHT FAILED (%d):\n  %s" % (len(ofails), "\n  ".join(ofails[:10])))
    if O_selftest():
        sys.exit("ORACLE SELF-TEST FAILED")

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
        n_cases=len(cases), only=a.only, run_group=a.run_group, timeout_s=a.timeout,
        sha_carriers=sha(src), sha_casematrix=sha(HERE / "casematrix.py"),
        sha_oracle=sha(HERE / "oracle.py"), sha_probe=sha(HERE / "probe.py"),
        sha_run=sha(HERE / "run.py"), sha_db_json=sha(REPO / "tools" / "agx-isa" / "db.json"),
        anchors=anchors)
    (run_dir / "00_env.json").write_text(json.dumps(env, indent=1, sort_keys=True))

    def baseline_check(bench, tgt, carrier, tries=4):
        """Re-validate the UNMUTATED carrier. Retried, because this sweep's own
        deliberately-illegal encodings put the GPU into error recovery for a short
        window, and a baseline sampled inside that window fails for reasons that
        have nothing to do with a cascade. Only a baseline that fails EVERY attempt
        is a genuine cascade (protocol section 7.3), and that stops the run."""
        sp = {tgt["off"] + i: b for i, b in enumerate(bytes.fromhex(tgt["synth"]))} \
             if tgt["mode"] == "A" else {}
        keep = bench._cur_in
        bench.set_input(CM.invec_bytes(carrier, CM.FIXED[carrier][1]))
        exp0 = CM.expect(carrier, CM.FIXED[carrier][1])
        vb = vec0_bits(carrier, CM.FIXED[carrier][1])
        ok = False
        for k in range(tries):
            st, ob, sent, gt, er = bench.run(sp)
            w = list(struct.unpack("<%dI" % (len(ob) // 4), ob)) if ob else []
            ok = (st == "OK" and sentinel_state(sent, vb) == "clean"
                  and all(exp0[k2] is None or (k2 < len(w) and w[k2] == exp0[k2]) for k2 in exp0))
            if ok:
                break
            time.sleep(0.25 * (k + 1))      # let GPU error recovery settle
        bench.set_input(keep)
        return ok

    out = open(run_dir / "sweep.jsonl", "a")
    hangs, stopped, cascades, blchecks = {}, set(), [], []
    total_hangs, stop_all = [0], [False]
    cascaded_carriers = set()
    # Execution order is PRIORITY order, not alphabetical. run03 ran carriers
    # alphabetically, so when the MODE-A packed_half2_hi arm cascaded the GPU the
    # run stopped with `unpack_convert` -- the highest-priority instrument -- still
    # entirely unrun. The two pack/unpack instruments now go first and the known-
    # dangerous synthesised one goes last, so a cascade costs only what follows it.
    PRIORITY = ["c_pack", "c_unpack", "c_i2f", "c_i2f_src", "c_f2i",
                "c_f2h", "c_f2h_dst", "c_f2bf", "c_ph2"]
    order = sorted([c for c in cases if c["instr"] in keys],
                   key=lambda c: (PRIORITY.index(c["carrier"]), c["i"]))
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

        if stop_all[0] or c["carrier"] in cascaded_carriers \
                or (c["instr"], c.get("byte")) in stopped:
            rec = dict(i=c["i"], arm=c["arm"], name=c["name"], instr=c["instr"],
                       field=c["field"], value=c["value"], bytes=bytes(instr_bytes).hex(),
                       observed=None, oracle={str(k): v for k, v in exp.items()},
                       match=False, outcome="hang",
                       validity=("skipped_after_cascade" if c["carrier"] in cascaded_carriers
                                 else "skipped_after_hangs"),
                       carrier=c["carrier"], note=c["note"], decode=decode,
                       status="SKIPPED", err=None, attempts=[], confirm=None, retries=0)
            out.write(json.dumps(rec, sort_keys=True) + "\n"); out.flush()
            n += 1
            continue

        bench.set_input(CM.invec_bytes(c["carrier"], c["vec"]))
        vbits = vec0_bits(c["carrier"], c["vec"])
        status, ob, sent, err, attempts, validity, sst = measure(bench, c, vbits)
        words = list(struct.unpack("<%dI" % (len(ob) // 4), ob)) if ob else []
        outcome = classify(status, err, words, exp, CM.RESULT_SLOTS[c["carrier"]])

        # Section 7.1: never conclude fault/hang from ONE observation. Confirm the
        # carrier baseline first (section 7.3 cascade check), then re-run the case.
        confirm = None
        if outcome in ("fault", "hang") and validity == "valid":
            time.sleep(0.1)                       # do not measure inside recovery
            bl_ok = baseline_check(bench, tgt, c["carrier"])
            st2, ob2, sent2, err2, att2, val2, sst2 = measure(bench, c, vbits)
            w2 = list(struct.unpack("<%dI" % (len(ob2) // 4), ob2)) if ob2 else []
            oc2 = classify(st2, err2, w2, exp, CM.RESULT_SLOTS[c["carrier"]])
            confirm = {"baseline_ok": bl_ok, "status2": st2, "err2": err2, "outcome2": oc2,
                       "attempts2": att2, "sentinel2": sst2}
            if not bl_ok:
                validity = "invalid_run"          # cascade: not this field's property
                cascades.append({"after_case": c["i"], "carrier": c["carrier"],
                                 "where": "fault_confirm"})
            elif oc2 != outcome:
                # did not reproduce in isolation -> take the second, non-faulting read
                status, ob, err, outcome, words = st2, ob2, err2, oc2, w2
                sent, sst, validity = sent2, sst2, val2
                confirm["resolution"] = "did_not_reproduce"
            else:
                confirm["resolution"] = "reproduced"
        if outcome == "hang" and validity == "valid":
            # "area" = (instruction, swept byte). A hang while sweeping the opcode
            # LEADER says nothing about an operand byte five positions along, so
            # stopping the whole instruction on it would throw away good coverage;
            # stopping the byte stops the actually-wedging configuration. A global
            # cap still protects the host, which has no out-of-band recovery.
            area = (c["instr"], c.get("byte"))
            hangs[str(area)] = hangs.get(str(area), 0) + 1
            total_hangs[0] += 1
            if hangs[str(area)] >= MAX_HANGS:
                stopped.add(area)
            if total_hangs[0] >= GLOBAL_HANG_CAP:
                print("  !! GLOBAL HANG CAP reached -- stopping run", flush=True)
                stop_all[0] = True
        rec = dict(i=c["i"], arm=c["arm"], name=c["name"], instr=c["instr"],
                   field=c["field"], value=c["value"], bytes=bytes(instr_bytes).hex(),
                   observed=ob[:32].hex() if ob else None,
                   sentinel=sent[:8].hex() if sent else None,
                   oracle={str(k): v for k, v in exp.items()},
                   match=(outcome == "ok" and validity == "valid"), outcome=outcome,
                   validity=validity, sentinel_state=sst,
                   carrier=c["carrier"], note=c["note"], decode=decode,
                   status=status, err=err, attempts=attempts, confirm=confirm,
                   retries=len(attempts) - 1)
        if c.get("byte") is not None:
            rec["byte"] = c["byte"]
        # Section 7.3: periodic mid-run baseline re-validation.
        if n and n % BASELINE_EVERY == 0:
            bl = baseline_check(bench, tgt, c["carrier"])
            blchecks.append({"after_case": c["i"], "carrier": c["carrier"], "ok": bl})
            if not bl:
                # Protocol section 7.3: a baseline that will not come back after four
                # attempts is a real cascade. Stop; do NOT record the cascade as data.
                # Protocol section 7.3 says resume in a FRESH PROCESS. Each carrier
                # already gets its own persistent-runner child, so stopping just this
                # carrier and continuing with the next one IS that fresh process --
                # and it does not throw away the instruments that are still healthy.
                print("  !! BASELINE FAILED after case %d (%s) -- CASCADE, stopping "
                      "this carrier" % (c["i"], c["carrier"]), flush=True)
                cascades.append({"after_case": c["i"], "carrier": c["carrier"]})
                cascaded_carriers.add(c["carrier"])
                if len(cascaded_carriers) >= MAX_CASCADED_CARRIERS:
                    print("  !! %d carriers cascaded -- stopping run" % len(cascaded_carriers),
                          flush=True)
                    stop_all[0] = True
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
             stopped=sorted(str(x) for x in stopped), total_hangs=total_hangs[0],
             stopped_all=stop_all[0], cascaded_carriers=sorted(cascaded_carriers),
             cascade_cases=cascades,
             baseline_checks=blchecks), indent=1, sort_keys=True))
    print("DONE %s: %d cases in %.1fs hangs=%s" % (a.run_id, n, time.time() - t0, hangs))


if __name__ == "__main__":
    main()
