#!/usr/bin/env python3
"""Vended EXP-0221 capture driver for EXP-0234 -- runs on G17P.

Fork of our own EXP-0220 harness/run220.py (committed, read-only, NOT modified).

One generated program per case.  For every case it records, in one append-only
JSON line flushed immediately (SUBAGENT_BRIEF: "assume the host will crash
mid-run"):

  case id; target; carrier id; the requested field values of every instruction
  in the case body; the ACTUAL bytes of those instructions taken from the
  program that is dispatched; the value independently decoded from those actual
  bytes; the program sha256 and the instruction offsets; the input-state hashes;
  the complete output state (a sha256 per buffer plus every predicted and every
  unexpected byte); independent sentinels; the host prediction; the semantic
  check result; the command-buffer status; the fault classification; timeout and
  contamination flags; and the run id and dispatch position.

Usage (on the neo):
    python3 harness/run234.py --run <run_id> --order canonical|reverse|shuffle
                              --slots 0,1,2 [--seed N] [--arms A,B] [--hazard]
"""
import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import synth221 as S      # noqa: E402
import prog221 as P       # noqa: E402
import runner221 as R     # noqa: E402

# The importing experiment supplies a module with build_cases() and
# build_program_for(). This keeps the proven capture/scoring machinery while
# avoiding any dependency on EXP-0221's experiment-specific case matrix.
C = None

CARRIER = "carrier234.metal"
FUNC = "k"


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def build_bins(bindir):
    bindir.mkdir(parents=True, exist_ok=True)
    for src, exe in (("shdump.m", "shdump"), ("agxrun_persist.m", "agxrun_persist")):
        r = sh(["clang", "-fobjc-arc", "-framework", "Metal", "-framework",
                "Foundation", "-O2", "-o", str(bindir / exe),
                str(EXP / "work" / "frozen" / src)])
        if r.returncode != 0:
            raise RuntimeError("build %s failed: %s" % (exe, r.stderr[-2000:]))
    return bindir


def load_agxparse():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "agxparse", str(EXP / "work" / "frozen" / "agxparse.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--order", default="canonical",
                    choices=("canonical", "reverse", "shuffle"))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--slots", default="",
                    help="frozen out,mem,imem slot mapping; empty = learn it from arm S0")
    ap.add_argument("--arms", default="")
    ap.add_argument("--hazard", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--hang-budget", type=int, default=12)
    ap.add_argument("--carrier", default=CARRIER,
                    help="authored Metal carrier used only for pipeline shape")
    ap.add_argument("--outroot", default="raw",
                    help="raw/ for a GATED capture; work/pilot for the disclosed "
                         "PRE-FREEZE pilot, which must never write into raw/")
    a = ap.parse_args()

    rawdir = EXP / a.outroot / a.run
    if rawdir.exists():
        print("REFUSED: %s/%s already exists -- run ids are never reused"
              % (a.outroot, a.run))
        return 3
    rawdir.mkdir(parents=True)
    work = EXP / "work" / a.run
    work.mkdir(parents=True, exist_ok=True)

    bindir = build_bins(EXP / "work" / "bin")
    agxparse = load_agxparse()

    # ---- the carrier: compile ONCE, then splice a copy per case -----------
    base_archive = work / "base.bin"
    r = sh([str(bindir / "shdump"), "-o", str(base_archive), "-f", FUNC,
            "--no-fast-math", str(EXP / "kernels" / a.carrier)])
    if r.returncode != 0 or not base_archive.exists():
        print("shdump failed:", r.stderr[-2000:])
        return 4
    base = base_archive.read_bytes()
    loc = agxparse.locate_region(base, "_agc.main")
    if loc is None:
        print("could not locate _agc.main")
        return 5
    abs_off, carrier_len = loc
    if carrier_len % 2:
        carrier_len -= 1

    # ---- input buffers -----------------------------------------------------
    poison = work / "poison.bin"
    memf = work / "mem.bin"
    imemf = work / "imem.bin"
    poison.write_bytes(P.poison_bytes())
    memf.write_bytes(P.mem_bytes())
    imemf.write_bytes(P.imem_bytes())
    IN = [(0, str(poison)), (1, str(memf)), (2, str(imemf))]
    OUTS = [(0, P.OUT_BYTES), (1, P.MEM_BYTES), (2, P.IMEM_BYTES)]
    base_state = {0: poison.read_bytes(), 1: memf.read_bytes(), 2: imemf.read_bytes()}

    meta = {
        "experiment": "EXP-0234", "run": a.run, "target": "G17P",
        "host": os.uname().nodename, "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "carrier": a.carrier, "carrier_agc_main_len": carrier_len,
        "carrier_abs_off": abs_off,
        "archive_sha256": hashlib.sha256(base).hexdigest(),
        "order": a.order, "seed": a.seed,
        "db_sha256": hashlib.sha256((EXP / "work" / "frozen" / "db.json").read_bytes()).hexdigest(),
        "isadb_sha256": hashlib.sha256((EXP / "work" / "frozen" / "isadb.py").read_bytes()).hexdigest(),
        "harness_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in sorted(HERE.glob("*.py"))},
        "input_sha256": {str(k): hashlib.sha256(v).hexdigest()
                         for k, v in base_state.items()},
        "poison_u32": "0x%08X" % S.POISON_U32,
        "out_bytes": P.OUT_BYTES,
    }
    (rawdir / "00_inputs.json").write_text(json.dumps(meta, indent=1, sort_keys=True))

    runner = R.ComputeRunner(str(bindir / "agxrun_persist"),
                             str(EXP / "kernels" / a.carrier), FUNC)
    meta["device"] = runner.device
    (rawdir / "00_inputs.json").write_text(json.dumps(meta, indent=1, sort_keys=True))
    print("READY device=%s carrier_len=%d abs_off=%d" % (runner.device, carrier_len, abs_off))

    sweep = open(rawdir / "sweep.jsonl", "a", buffering=1)
    hangs = 0
    seq = 0
    arch_prev = None

    def dispatch(case, slots):
        nonlocal seq, hangs, arch_prev
        seq += 1
        pg, prog = C.build_program_for(case, slots, carrier_len)
        rows, bad, alias = S.gate_a_ledger(prog, pg.E.parts)
        spliced = bytearray(base)
        spliced[abs_off:abs_off + carrier_len] = prog
        arch = work / ("a_%06d.bin" % seq)
        arch.write_bytes(bytes(spliced))
        # PROVE the bytes on disk are the bytes we built: re-read the region.
        back = arch.read_bytes()[abs_off:abs_off + carrier_len]
        dispatched_ok = (back == prog)

        t0 = time.time()
        res = runner.run(str(arch), IN, OUTS, timeout=a.timeout)
        dt = int((time.time() - t0) * 1000)
        if arch_prev is not None:
            try:
                os.unlink(arch_prev)
            except OSError:
                pass
        arch_prev = str(arch)

        oracle = pg.oracle()
        rec = score(case, pg, prog, rows, bad, alias, res, base_state, oracle,
                    slots, dispatched_ok)
        rec["carrier"] = a.carrier
        rec.update({"run": a.run, "seq": seq, "duration_ms": dt,
                    "restarts": runner.restarts})
        sweep.write(json.dumps(rec, sort_keys=True) + "\n")
        sweep.flush()
        if rec["outcome"] == "hang":
            hangs += 1
        return rec

    # ---- arm S0 first: it establishes the slot mapping everything else uses -
    all_cases = C.build_cases(include_hazard=a.hazard)
    s0 = [c for c in all_cases if c["arm"] == "S0"]
    rest = [c for c in all_cases if c["arm"] != "S0"]
    if a.arms:
        want = set(a.arms.split(","))
        rest = [c for c in rest if c["arm"] in want
                or c["arm"].split("-")[0] in want]
    if a.order == "reverse":
        rest = list(reversed(rest))
    elif a.order == "shuffle":
        random.Random(a.seed).shuffle(rest)
    if a.limit:
        rest = rest[:a.limit]

    probe_slots = {"out": 0, "mem": 1, "imem": 2}
    hits = {}
    for c in s0:
        rec = dispatch(c, probe_slots)
        hits[c["slot"]] = rec.get("s0_landed")
    learned = {}
    for slot, where in sorted(hits.items()):
        if where and where not in learned:
            learned[where] = slot
    (rawdir / "01_slot_probe.json").write_text(
        json.dumps({"hits": {str(k): v for k, v in hits.items()},
                    "learned": learned}, indent=1, sort_keys=True))
    print("S0 slot probe:", hits, "->", learned)

    if a.slots:
        fs = [int(x) for x in a.slots.split(",")]
        slots = {"out": fs[0], "mem": fs[1], "imem": fs[2]}
        agree = all(learned.get(k) == v for k, v in slots.items())
        if not agree:
            print("SLOT MISMATCH: frozen %r vs probed %r -- ABORTING the capture"
                  % (slots, learned))
            (rawdir / "02_abort.json").write_text(json.dumps(
                {"reason": "slot mapping did not reproduce",
                 "frozen": slots, "probed": learned}, indent=1))
            sweep.close()
            runner.close()
            return 6
    else:
        if len(learned) < 3:
            print("slot probe incomplete: %r -- cannot continue" % learned)
            sweep.close()
            runner.close()
            return 7
        slots = learned

    print("slots =", slots, " dispatching", len(rest), "cases")
    for n, c in enumerate(rest):
        rec = dispatch(c, slots)
        if n % 100 == 0:
            print("  [%4d/%4d] %-34s %-14s match=%s"
                  % (n, len(rest), c["name"], rec["outcome"], rec["match"]))
        if hangs > a.hang_budget:
            print("HANG BUDGET EXHAUSTED after %d hangs -- stopping" % hangs)
            (rawdir / "02_stopped.json").write_text(json.dumps(
                {"reason": "hang budget", "hangs": hangs, "dispatched": seq}, indent=1))
            break
    sweep.close()
    runner.close()
    (rawdir / "05_run_manifest.json").write_text(json.dumps(
        {"run": a.run, "dispatched": seq, "hangs": hangs, "slots": slots,
         "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1, sort_keys=True))
    print("done: %d cases, %d hangs" % (seq, hangs))
    return 0


# ---------------------------------------------------------------------------
MAXREPORT = 64


def score(case, pg, prog, rows, bad, alias, res, base_state, oracle, slots,
          dispatched_ok):
    status = res.get("status", "UNKNOWN")
    err = res.get("error", "")
    body = [r for r in rows
            if pg.body_start <= r["offset"] < (pg.body_end
                                               if pg.body_end is not None else 10 ** 9)]
    rec = {
        "i": case["i"], "name": case["name"], "arm": case["arm"],
        "kind": case["kind"], "target": "G17P", "carrier": CARRIER,
        "slots": slots, "expect_match": case["expect_match"],
        "hazard": case.get("hazard", False),
        "prog_sha256": hashlib.sha256(prog).hexdigest(),
        "prog_len": len(prog),
        "dispatched_bytes_verified": dispatched_ok,
        "ledger": pg.E.led.counts(),
        "donor_fields": pg.E.led.nonsynthesised(),
        "offnatural": pg.E.led.offnatural()[:MAXREPORT],
        "gate_a": {"n_instr": len(rows), "n_bad": len(bad), "bad": bad[:5],
                   "n_alias": len(alias), "alias": alias[:5]},
        "under_test": [{"offset": r["offset"], "mnemonic": r["mnemonic"],
                        "requested": r["requested"],
                        "decoded_actual": r["decoded_actual"],
                        "bytes": r["actual_bytes"]} for r in body],
        "status": status, "gputime_ns": res.get("gputime_ns"),
        "error": err[:220],
        "foreign_retries": res.get("foreign_retries", 0),
        "restarted": res.get("restarted", False),
        "hazards_declared": pg.hazards[:8],
    }
    rec["predicted_bucket"] = case.get("predicted_bucket", "exact")
    if status != "OK":
        if status == "MALFORMED":
            rec["outcome"] = "measurement_failure"
        elif status == "HANG":
            rec["outcome"] = "hang"
        elif "InnocentVictim" in err:
            rec["outcome"] = "victim"
        else:
            rec["outcome"] = "fault"
        rec["match"] = False
        rec["sem_checked"] = 0
        rec["observed_bucket"] = rec["outcome"]
        pb0 = rec["predicted_bucket"]
        rec["bucket_ok"] = (None if rec["outcome"] in ("measurement_failure", "victim")
                            or pb0 == "measure"
                            else pb0 in ("corrupt", "refute"))
        return rec

    surf = res.get("surf", {})
    idx_of = {"out": slots["out"], "mem": slots["mem"], "imem": slots["imem"]}
    rec["out_sha256"] = {str(k): hashlib.sha256(v).hexdigest()
                         for k, v in sorted(surf.items())}

    # ---- EXP-0221 additions: the raw measurement channels -----------------
    # `regs`      the 24 dumped architectural registers, read straight out of
    #             the out buffer.  EXP-0220 recorded only PREDICTED-and-wrong
    #             bytes, so a discovery arm (which predicts nothing) recorded
    #             nothing usable.  Arm T's whole answer is "which bank register
    #             came back holding the codeword", and that is this list.
    # `target16`  the 16 bytes at the case's store address, so the element
    #             SHAPE of an undocumented st_format is derived from data.
    # `tripwire`  the out word a post-`stop` store would have written.  It is
    #             the only observable `stop` has, and arm S rests on it.
    obuf = surf.get(idx_of["out"])
    if obuf is not None:
        rec["regs"] = []
        for R in P.DUMP_REGS:
            b = pg.dump_byte(R)
            rec["regs"].append(struct.unpack("<I", obuf[b:b + 4])[0]
                               if b + 4 <= len(obuf) else None)
        tb = S.store_byte_offset(0, 600)
        rec["target16"] = obuf[tb:tb + 16].hex() if tb + 16 <= len(obuf) else None
        if getattr(pg, "tripwire_off", None) is not None:
            wb = S.store_byte_offset(0, pg.tripwire_off)
            w = (struct.unpack("<I", obuf[wb:wb + 4])[0]
                 if wb + 4 <= len(obuf) else None)
            rec["tripwire_word"] = w
            rec["tripwire_written"] = (w is not None and w != S.POISON_U32)
        # arm T: the codeword channel.  `expect_codeword` is the PRE-REGISTERED
        # boolean prediction (Gate C in its boolean form, because the
        # measurement is "did the datum arrive", not a byte map), and
        # `codeword_regs` is what actually came back.  The codeword source
        # register (RB) is excluded: it holds the codeword by construction and
        # counting it would make the check unable to come out the other way.
        if case.get("cw") is not None:
            cw = P.codeword(case["cw"])
            rec["codeword"] = cw
            rec["codeword_regs"] = [R for R, v in enumerate(rec["regs"])
                                    if v == cw and R != 2]
            rec["codeword_arrived"] = bool(rec["codeword_regs"])
            ec = case.get("expect_codeword")
            rec["expect_codeword"] = ec
            if ec is not None:
                rec["codeword_prediction_ok"] = (rec["codeword_arrived"] == ec)

    # sentinel: an integrity check on a path independent of the field under test
    sb = pg.sentinel_byte()
    got_sent = None
    ob = surf.get(idx_of["out"])
    if ob is not None and sb + 4 <= len(ob):
        got_sent = struct.unpack("<I", ob[sb:sb + 4])[0]
    rec["sentinel"] = got_sent
    rec["sentinel_ok"] = (got_sent == P.SENT_IMM) if case.get("expect_sentinel", True) \
        else True

    # complete-state comparison, per buffer
    n_ok = n_wrong = n_nowrite = n_unpred = n_stray = n_trip_bytes = 0
    detail_pred, detail_stray = {}, {}
    trip_bytes = set()
    if getattr(pg, "tripwire_off", None) is not None \
            and not case.get("tripwire_before_stop"):
        _wb = S.store_byte_offset(0, pg.tripwire_off)
        trip_bytes = set(range(_wb, _wb + 4))
    for basename, want in oracle.items():
        if basename not in idx_of:
            continue
        bidx = idx_of[basename]
        got = surf.get(bidx)
        if got is None:
            continue
        pre = base_state[bidx]
        predicted_at = set(want)
        for off, val in sorted(want.items()):
            if off >= len(got):
                continue
            g = got[off]
            if val is None:
                n_unpred += 1
                if len(detail_pred) < MAXREPORT:
                    detail_pred["%s:%d" % (basename, off)] = [None, g]
                continue
            if g == val:
                n_ok += 1
            elif off + 4 <= len(pre) and got[off:off + 1] == pre[off:off + 1] \
                    and basename == "out":
                n_nowrite += 1
                if len(detail_pred) < MAXREPORT:
                    detail_pred["%s:%d" % (basename, off)] = [val, g]
            else:
                n_wrong += 1
                if len(detail_pred) < MAXREPORT:
                    detail_pred["%s:%d" % (basename, off)] = [val, g]
        # every byte that CHANGED but was not predicted is a STRAY WRITE.  The
        # XOR is done as one big-int operation and the differing runs are found
        # with a regex, so a 32 KiB complete-state comparison costs microseconds
        # rather than a 32k-iteration Python loop per case.
        n = min(len(got), len(pre))
        x = int.from_bytes(got[:n], "little") ^ int.from_bytes(pre[:n], "little")
        if x:
            xb = x.to_bytes(n, "little")
            for m in re.finditer(rb"[^\x00]+", xb):
                for off in range(m.start(), m.end()):
                    if off in predicted_at:
                        continue
                    if basename == "out" and off in trip_bytes:
                        # THE TRIPWIRE IS A MEASUREMENT, NOT A STRAY.  Arm S's
                        # post-stop store is deliberately outside the oracle so
                        # that a write there is visible; counting it as a stray
                        # as well would double-report one fact and would make
                        # every `stop` case that did not halt indistinguishable
                        # from one that corrupted an unrelated byte.
                        n_trip_bytes += 1
                        continue
                    n_stray += 1
                    if len(detail_stray) < MAXREPORT:
                        detail_stray["%s:%d" % (basename, off)] = [pre[off], got[off]]

    rec.update({"n_pred_ok": n_ok, "n_pred_wrong": n_wrong,
                "n_pred_nowrite": n_nowrite, "n_unpredicted": n_unpred,
                "n_stray_bytes": n_stray,
                "n_tripwire_bytes_changed": n_trip_bytes,
                "observed": detail_pred, "stray": detail_stray})
    rec["sem_checked"] = n_ok + n_wrong + n_nowrite
    predicts_nothing = not any(oracle[k] for k in ("out", "mem", "imem"))
    rec["match"] = bool(rec["sentinel_ok"] and n_wrong == 0 and n_nowrite == 0
                        and n_stray == 0
                        and (rec["sem_checked"] > 0 or predicts_nothing))
    if not rec["sentinel_ok"]:
        rec["outcome"] = "invalid_run"
    elif n_wrong == 0 and n_nowrite == 0 and n_stray == 0:
        rec["outcome"] = "ok"
    elif n_nowrite and not n_wrong:
        rec["outcome"] = "no_write"
    elif n_stray and not n_wrong and not n_nowrite:
        rec["outcome"] = "stray_write"
    else:
        rec["outcome"] = "wrong_value"

    # -- Gate C behaviour bucket -------------------------------------------
    if n_wrong:
        ob = "wrong"
    elif n_nowrite:
        ob = "no_write"
    elif n_stray:
        ob = "stray"
    elif n_unpred:
        ob = "unpredicted"
    elif not rec["sentinel_ok"]:
        ob = "invalid_run"
    else:
        ob = "exact"
    # arm S: `stop` halted iff the post-stop tripwire did NOT write.  The
    # tripwire byte is deliberately NOT in the oracle, so its write shows up as
    # a stray; that is correct for a `corrupt` bucket but must not be allowed to
    # silently make an `exact` case look wrong for the WRONG reason, so the two
    # facts are recorded separately and the bucket is decided on the tripwire.
    if case["kind"] == "stop" and not case.get("tripwire_before_stop") \
            and case.get("tripwire_off") is not None:
        rec["stop_halted"] = (rec.get("tripwire_written") is False)
        ob = "exact" if (rec["stop_halted"] and n_wrong == 0 and n_nowrite == 0
                         and rec["sentinel_ok"]) else ob
    rec["observed_bucket"] = ob
    pb = rec["predicted_bucket"]
    if pb == "exact":
        rec["bucket_ok"] = (ob == "exact")
    elif pb in ("corrupt", "refute"):
        # `refute` is a pre-registered FALSIFIER: it must NOT come out exact, or
        # the comparator has no detection power and the arm is undecidable.
        rec["bucket_ok"] = (ob != "exact")
    else:
        rec["bucket_ok"] = None                 # `measure`: recorded, not gating

    # arm S0 answers ONE question: which bound buffer did the probe store land in?
    if case["kind"] == "s0_slot":
        landed = None
        for basename, bidx in idx_of.items():
            got = surf.get(bidx)
            if got is None:
                continue
            pre = base_state[bidx]
            off = S.store_byte_offset(0, 10)
            if off + 4 <= len(got) and got[off:off + 4] != pre[off:off + 4]:
                if struct.unpack("<I", got[off:off + 4])[0] == P.SENT_IMM:
                    landed = basename
        rec["s0_landed"] = landed
        rec["match"] = landed is not None
        rec["outcome"] = "ok" if landed else "no_write"
    return rec


if __name__ == "__main__":
    sys.exit(main())
