#!/usr/bin/env python3
"""EXP-0159 — FE (MEM-19) base-slot census, re-captured UNDER THE GPU LEASE.

Post-registration confirmation pass.  In gated run02 the FE arm's very first
(unmutated) baseline dispatch was killed by a concurrent GPU error, so the probe
could not be isolated and the 256-value sweep never ran; run.py recorded that
honestly as `__probe_not_isolated` and stopped.  That partial capture is RETAINED
under its own run id and is not reused.  This script re-captures the same arm in
isolation, with a retried baseline, under a NEW run id, per
FIELD-SWEEP-PROTOCOL.md sec.7A ("only isolation defeats sustained sibling load").

  ~/agxre/gpulease.sh EXP-0159 900 -- python3 fe_isolated.py --run-id <id>

Authored by the clean-room RE team.  Clean-room: OWN-SHADER splice + HW-PROBE.
"""
import argparse, hashlib, json, os, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import run as R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--work", default=os.path.expanduser("~/agxre/EXP-0159/work"))
    ap.add_argument("--baseline-retries", type=int, default=8)
    args = ap.parse_args()
    rawdir = os.path.join(ROOT, "raw", args.run_id)
    os.makedirs(rawdir, exist_ok=True)
    sink = R.Sink(rawdir)
    from persistrun import PersistRunner

    wd = os.path.join(args.work, "fe_iso")
    os.makedirs(wd, exist_ok=True)
    src = os.path.join(ROOT, "kernels", "slot31.metal")
    arch = os.path.join(wd, "slot31.bin")
    cp = subprocess.run([R.SHDUMP, "-o", arch, "-f", "k", src], capture_output=True, text=True)
    if cp.returncode != 0:
        sink.w("fe", {"family": "fe", "case": "__compile", "outcome": "undecodable",
                      "note": (cp.stdout + cp.stderr)[:400]})
        return
    p = subprocess.run([sys.executable, R.AGXPARSE, arch, "--locate", "_agc.main"],
                       capture_output=True, text=True)
    abs_off, mlen = [int(x, 0) for x in p.stdout.split()[:2]]
    blob = open(arch, "rb").read()
    main = blob[abs_off:abs_off + mlen]
    dis, leftover = R.disasm(main)
    loads = [d for d in dis if d.get("mnemonic") == "device_load"]
    sink.w("fe", {"family": "fe", "case": "__carrier", "observed": main.hex()[:4000],
                  "outcome": "ok", "main_sha256": hashlib.sha256(main).hexdigest(),
                  "isolated": True,
                  "note": "%d device_load(s); leftover=%s" % (len(loads), leftover.hex())})

    files = {}
    for k in range(31):
        f = os.path.join(wd, "b%d.bin" % k)
        open(f, "wb").write(struct.pack("<I", 0x51000000 | k) * 4)
        files[k] = f
    poison = os.path.join(wd, "poison.bin")
    open(poison, "wb").write(b"\xa5" * 16)
    files[0] = poison

    r = PersistRunner(source=src, function="k", fast_math=True, agxrun_persist=R.PERSIST)
    spliced = os.path.join(wd, "spliced.bin")

    def dispatch(mm, timeout=10.0):
        nb = bytearray(blob)
        nb[abs_off:abs_off + mlen] = mm
        open(spliced, "wb").write(bytes(nb))
        return r.request(archive=spliced, grid=1, tg=1, ins=files, outs={0: 16}, timeout=timeout)

    def word(resp):
        o = resp["outs"].get(0, b"")
        return struct.unpack("<I", o[:4])[0] if len(o) >= 4 else None

    # retried baseline: a lone contaminated dispatch must not abort the arm
    bw, tries = None, 0
    for tries in range(1, args.baseline_retries + 1):
        b = dispatch(main)
        sink.w("fe", {"family": "fe", "case": "baseline", "attempt": tries,
                      "observed": "%08x" % (word(b) or 0),
                      "outcome": "ok" if b["status"] == "OK" else "fault",
                      "fault_class": b.get("error") or "", "isolated": True,
                      "note": "unmutated carrier; probe loads b17"})
        if b["status"] == "OK":
            bw = word(b)
            break
    if bw is None:
        sink.w("fe", {"family": "fe", "case": "__baseline_failed", "value": tries,
                      "outcome": "fault", "isolated": True,
                      "note": "baseline never completed in %d isolated attempts" % tries})
        r.close(); return

    probe = None
    for d in loads:
        off = d["offset"]
        cur = main[off + 4]
        mm = bytearray(main); mm[off + 4] = (cur + 1) & 0xFF
        rr = dispatch(bytes(mm))
        w = word(rr)
        sink.w("fe", {"family": "fe", "case": "probe_id@0x%x" % off, "value": off,
                      "observed": "%08x" % (w or 0), "oracle": "%08x" % bw, "isolated": True,
                      "outcome": "ok" if rr["status"] == "OK" else "fault",
                      "fault_class": rr.get("error") or "",
                      "note": "base_slot 0x%02x->0x%02x on the load at +0x%x" % (cur, (cur+1) & 0xFF, off)})
        if w is not None and w != bw and probe is None:
            probe = (off, cur)
    if probe is None:
        sink.w("fe", {"family": "fe", "case": "__probe_not_isolated", "outcome": "undecodable",
                      "isolated": True})
        r.close(); return
    poff, pbase = probe
    sink.w("fe", {"family": "fe", "case": "__probe", "value": poff, "observed": "%02x" % pbase,
                  "outcome": "ok", "isolated": True,
                  "note": "probe device_load at _agc.main+0x%x, base_slot byte 0x%02x" % (poff, pbase)})

    for val in range(256):
        mm = bytearray(main); mm[poff + 4] = val
        votes, obs = [], []
        for rep in range(3):
            resp = dispatch(bytes(mm))
            w = word(resp)
            st = resp["status"]
            err = resp.get("error") or ""
            oc = ("hang" if st == "HANG" else
                  "victim" if "victim" in err.lower() else
                  "fault" if st != "OK" else
                  "silent_zero" if w == 0 else
                  "unwritten" if w == 0xA5A5A5A5 else "ok")
            votes.append(oc); obs.append("%08x" % (w if w is not None else 0))
            if oc == "ok" and rep == 0:
                break
        maj = max(set(votes), key=votes.count)
        w0 = int(obs[-1], 16)
        binding = (w0 - 0x51000000) if (w0 & 0xFFFFFF00) == 0x51000000 else None
        sink.w("fe", {"family": "fe", "case": "base_slot=%d" % val, "field": "base_slot",
                      "value": val, "observed": obs[-1], "all_observed": ",".join(obs),
                      "binding": binding, "mirror_of": (val - 128) if val >= 128 else None,
                      "outcome": maj, "votes": ",".join(votes), "isolated": True,
                      "fault_class": "" if maj == "ok" else (resp.get("error") or "")})
        if val % 64 == 63:
            bb = dispatch(main)
            sink.w("fe", {"family": "fe", "case": "baseline@%d" % val, "phase": "baseline",
                          "observed": "%08x" % (word(bb) or 0), "isolated": True,
                          "outcome": "ok" if bb["status"] == "OK" else "fault",
                          "fault_class": bb.get("error") or ""})
    sink.w("fe", {"family": "fe", "case": "__done", "outcome": "ok", "isolated": True})
    r.close(); sink.close()


if __name__ == "__main__":
    main()
