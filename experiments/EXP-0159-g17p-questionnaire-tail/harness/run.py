#!/usr/bin/env python3
"""EXP-0159 runner — executes the six probe families on G17P and appends one
JSON record per case to raw/<run_id>/<family>.jsonl, flushed immediately.

Authored by the clean-room RE team.  Clean-room: PUBLIC Metal API + OWN-SHADER;
no Apple binary is inspected.  Runs ON the neo (A18 Pro / G17P).

  python3 run.py --run-id g17p-YYYYMMDD-runNN --family all|fa|fb|fc|fd|fe|ff
"""
import argparse, hashlib, json, os, struct, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
KERN = os.path.join(ROOT, "kernels")
TOOLS = os.path.expanduser("~/agxre/tools")
sys.path.insert(0, os.path.join(TOOLS, "agx-isa"))
sys.path.insert(0, os.path.join(TOOLS, "shdump"))
sys.path.insert(0, os.path.join(TOOLS, "agxtest"))

SHDUMP = os.path.join(TOOLS, "shdump", "shdump")
AGXPARSE = os.path.join(TOOLS, "shdump", "agxparse.py")
PERSIST = os.path.join(TOOLS, "agxtest", "agxrun_persist")


def sh(cmd, timeout=300, cwd=None):
    p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True,
                       text=True, timeout=timeout, cwd=cwd)
    return p.returncode, p.stdout, p.stderr



def disasm(main):
    """isadb.disassemble returns (records, leftover) and records carry no
    offset; recover offsets by walking the emitted lengths."""
    import isadb
    recs, leftover = isadb.disassemble(main)
    off = 0
    for r in recs:
        r["offset"] = off
        off += (r.get("length") or 0)
    return recs, leftover


class Sink:
    def __init__(self, rawdir):
        self.rawdir = rawdir
        self.fh = {}

    def w(self, fam, obj):
        obj.setdefault("target", "G17P")
        f = self.fh.get(fam)
        if f is None:
            f = open(os.path.join(self.rawdir, fam + ".jsonl"), "a")
            self.fh[fam] = f
        f.write(json.dumps(obj, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())

    def passthru(self, fam, line):
        if line.startswith("REC "):
            try:
                self.w(fam, json.loads(line[4:]))
                return True
            except Exception:
                pass
        return False

    def close(self):
        for f in self.fh.values():
            f.close()


def run_stream(cmd, sink, fam, timeout=900, logpath=None):
    """Run a harness, forwarding its REC lines into the sink, with a hard timeout."""
    lg = open(logpath, "a") if logpath else None
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, bufsize=1)
    t0 = time.time()
    n = 0
    try:
        for line in p.stdout:
            if lg:
                lg.write(line); lg.flush()
            if sink.passthru(fam, line.rstrip("\n")):
                n += 1
            if time.time() - t0 > timeout:
                p.kill()
                sink.w(fam, {"case": "__timeout", "outcome": "hang",
                             "note": "harness exceeded %ds" % timeout})
                break
        p.wait(timeout=30)
    finally:
        if lg:
            lg.close()
    return n, p.returncode


# ---------------------------------------------------------------- FA (P2-06)
def fam_fa(sink, args):
    exe = os.path.join(args.bin, "mslprobe")
    langs = ["", "31", "32"]
    for src in sorted(os.listdir(os.path.join(KERN, "fa"))):
        if not src.endswith(".metal"):
            continue
        name = src[:-6]
        for lv in langs:
            cmd = [exe, os.path.join(KERN, "fa", src)] + ([lv] if lv else [])
            rc, out, errtxt = sh(cmd, timeout=120)
            status, diag = "error", ""
            if "COMPILE_STATUS accept" in out:
                status = "accept"
            elif "COMPILE_STATUS reject" in out:
                status = "reject"
            if "DIAG_BEGIN" in out:
                diag = out.split("DIAG_BEGIN", 1)[1].split("DIAG_END", 1)[0].strip()
            is_ctrl = name.startswith("ctrl_")
            expect = "accept" if is_ctrl else "reject"
            sink.w("fa", {
                "family": "fa", "case": "%s@lang%s" % (name, lv or "default"),
                "source": name, "lang": lv or "default",
                "observed": status, "oracle": expect, "match": status == expect,
                "outcome": "ok" if status in ("accept", "reject") else "undecodable",
                "control": is_ctrl, "diag": diag[:1500], "rc": rc,
                "stderr": errtxt[:300]})
    sink.w("fa", {"family": "fa", "case": "__done", "outcome": "ok"})


# ---------------------------------------------------------------- FB (P2-06)
F64_ROWS = [
    (0x3FF0000000000000, 0x3E45798EE2308C3A),   # 1.0, 1e-8
    (0x4000000000000000, 0x3FF0000000000000),   # 2.0, 1.0
    (0x7FF0000000000000, 0x3FF0000000000000),   # +inf, 1.0
    (0xBFF0000000000000, 0x3FF0000000000000),   # -1.0, 1.0
]
M64 = (1 << 64) - 1


def _f64(bits):
    return struct.unpack("<d", struct.pack("<Q", bits & M64))[0]


def _b64(x):
    return struct.unpack("<Q", struct.pack("<d", x))[0]


def _f32pair(bits):
    lo, hi = bits & 0xFFFFFFFF, (bits >> 32) & 0xFFFFFFFF
    return (struct.unpack("<f", struct.pack("<I", lo))[0],
            struct.unpack("<f", struct.pack("<I", hi))[0])


def _packf32(lo, hi):
    return (struct.unpack("<I", struct.pack("<f", lo))[0] |
            (struct.unpack("<I", struct.pack("<f", hi))[0] << 32))


def fb_oracles(a, b):
    """Closed set of host-computed hypotheses for one input row.

    Ordered so the SIMPLER (integer / passthrough / lane-wise f32) explanations
    are tested first: on some rows an f64 result coincides with a passthrough,
    and attributing that to FP64 would be exactly the wrong call.  The strict
    FP64 verdict is computed separately by fb_fp64_hit(), which requires the
    SAME f64 operation to reproduce ALL four rows.
    """
    o = {}
    o["passthrough_a"] = a
    o["passthrough_b"] = b
    o["zero"] = 0
    o["poison"] = 0xA5A5A5A5A5A5A5A5
    o["i64_add"] = (a + b) & M64
    o["i64_sub"] = (a - b) & M64
    o["i64_and"] = a & b
    o["i64_or"] = a | b
    o["i64_xor"] = a ^ b
    la, ha = _f32pair(a)
    lb, hb = _f32pair(b)
    for nm, x, y in (("f32x2_add", la + lb, ha + hb), ("f32x2_sub", la - lb, ha - hb)):
        try:
            o[nm] = _packf32(x, y)
        except Exception:
            pass
    for nm, val in fb_f64_ops(a, b).items():
        o.setdefault(nm, val)
    return o


def fb_f64_ops(a, b):
    """The binary64 hypotheses, host-computed. min/max are deliberately EXCLUDED:
    on the +inf row they are indistinguishable from a passthrough, so they cannot
    discriminate and would only manufacture false positives."""
    fa_, fb_ = _f64(a), _f64(b)
    out = {}
    for nm, fn in (("f64_add", lambda: fa_ + fb_), ("f64_sub", lambda: fa_ - fb_),
                   ("f64_mul", lambda: fa_ * fb_), ("f64_div", lambda: fa_ / fb_)):
        try:
            out[nm] = _b64(fn())
        except Exception:
            pass
    return out


def fb_classify(obs, a, b):
    for nm, val in fb_oracles(a, b).items():
        if obs == val:
            return nm
    return "other"


def fb_fp64_hit(observed_rows):
    """Strict FP64 verdict for one spliced encoding: is there ONE binary64
    operation that reproduces every input row exactly?  A per-row coincidence is
    not enough -- that is what makes this a real refuter rather than noise."""
    if len(observed_rows) != len(F64_ROWS) or any(v is None for v in observed_rows):
        return None
    for op in ("f64_add", "f64_sub", "f64_mul", "f64_div"):
        if all(fb_f64_ops(a, b).get(op) == observed_rows[i]
               for i, (a, b) in enumerate(F64_ROWS)):
            return op
    return None


def fam_fb(sink, args):
    from persistrun import PersistRunner
    import isadb
    wd = os.path.join(args.work, "fb")
    os.makedirs(wd, exist_ok=True)
    src = os.path.join(KERN, "u64op.metal")
    arch = os.path.join(wd, "u64op.bin")
    rc, out, err = sh([SHDUMP, "-o", arch, "-f", "k", src], timeout=180)
    if rc != 0:
        sink.w("fb", {"family": "fb", "case": "__compile", "outcome": "undecodable",
                      "note": (out + err)[:500]})
        return
    rc, out, err = sh([sys.executable, AGXPARSE, arch, "--locate", "_agc.main"], timeout=120)
    abs_off, mlen = [int(x, 0) for x in out.split()[:2]]
    blob = open(arch, "rb").read()
    main = blob[abs_off:abs_off + mlen]
    dis, leftover = disasm(main)
    target = None
    for d in dis:
        if d.get("mnemonic") == "iadd2":
            target = d
            break
    sink.w("fb", {"family": "fb", "case": "__carrier",
                  "observed": main.hex(), "outcome": "ok",
                  "note": "disasm=" + " ".join(str(d.get("mnemonic")) for d in dis)
                          + " leftover=" + leftover.hex(),
                  "main_sha256": hashlib.sha256(main).hexdigest(),
                  "abs_off": abs_off, "main_len": mlen})
    if target is None:
        sink.w("fb", {"family": "fb", "case": "__no_carrier", "outcome": "undecodable",
                      "note": "no iadd2 located in our own compiled bytes"})
        return
    ioff = target["offset"]
    ilen = target.get("length") or 10
    ibytes = main[ioff:ioff + ilen]
    sink.w("fb", {"family": "fb", "case": "__instr", "value": ioff,
                  "observed": ibytes.hex(), "outcome": "ok",
                  "note": "located iadd2 at _agc.main+0x%x, %d bytes" % (ioff, ilen)})

    # inputs
    ab = b"".join(struct.pack("<Q", r[0]) for r in F64_ROWS)
    bb = b"".join(struct.pack("<Q", r[1]) for r in F64_ROWS)
    poison = b"\xa5" * (8 * len(F64_ROWS))
    pa, pb, pp = (os.path.join(wd, n) for n in ("a.bin", "b.bin", "poison.bin"))
    open(pa, "wb").write(ab); open(pb, "wb").write(bb); open(pp, "wb").write(poison)

    r = PersistRunner(source=src, function="k", fast_math=True, agxrun_persist=PERSIST)
    spliced = os.path.join(wd, "spliced.bin")

    def dispatch(mut_main, timeout=8.0):
        nb = bytearray(blob)
        nb[abs_off:abs_off + mlen] = mut_main
        open(spliced, "wb").write(bytes(nb))
        return r.request(archive=spliced, grid=len(F64_ROWS), tg=len(F64_ROWS),
                         ins={0: pp, 1: pa, 2: pb}, outs={0: 8 * len(F64_ROWS)},
                         timeout=timeout)

    def emit(case, boff, val, resp, phase="sweep"):
        outs = resp["outs"].get(0, b"")
        rows, classes, vals = [], [], []
        for i, (a, b) in enumerate(F64_ROWS):
            w = outs[i * 8:(i + 1) * 8]
            ov = struct.unpack("<Q", w)[0] if len(w) == 8 else None
            cl = fb_classify(ov, a, b) if ov is not None else "missing"
            rows.append("%016x" % ov if ov is not None else "")
            classes.append(cl)
            vals.append(ov)
        fp64 = fb_fp64_hit(vals)
        st = resp["status"]
        outcome = ("ok" if st == "OK" else
                   "hang" if st == "HANG" else
                   "victim" if (resp.get("error") or "").find("InnocentVictim") >= 0 or
                                (resp.get("error") or "").find("victim") >= 0 else "fault")
        sink.w("fb", {"family": "fb", "case": case, "instr": "iadd2",
                      "field": "byte+%d" % boff, "value": val, "phase": phase,
                      "observed": ",".join(rows), "oracle_class": ",".join(classes),
                      "fp64_hit": fp64,
                      "per_row_f64_coincidence": [c for c in classes if c.startswith("f64_")],
                      "outcome": outcome,
                      "fault_class": resp.get("error") or "", "status": st})
        return classes, outcome, fp64

    # baseline (unmutated) + positive control
    base = dispatch(main)
    emit("baseline", -1, -1, base, phase="baseline")
    ctrl = bytearray(main)
    ctrl[ioff] = ibytes[0] | 0x80          # addsub bit7 -> native 64-bit add
    cc, _, _ = emit("control.addsub_1", 0, ctrl[ioff], dispatch(bytes(ctrl)), phase="control")
    sink.w("fb", {"family": "fb", "case": "__control_verdict",
                  "observed": ",".join(cc),
                  "match": all(c == "i64_add" for c in cc),
                  "outcome": "ok" if all(c == "i64_add" for c in cc) else "wrong_value",
                  "note": "detection power: byte0 bit7 must turn the subtract into a 64-bit add"})

    hits, n = [], 0
    for boff in range(ilen):
        for val in range(256):
            if val == ibytes[boff]:
                continue
            mut = bytearray(main)
            mut[ioff + boff] = val
            resp = dispatch(bytes(mut))
            cls, outcome, fp64hit = emit("iadd2.b%d=0x%02x" % (boff, val), boff, val, resp)
            fp64_of = [fp64hit]
            if outcome != "ok":
                # majority-of-3: never conclude fault from one observation
                votes = [outcome]
                for _ in range(2):
                    rr = dispatch(bytes(mut))
                    _, o2, f2 = emit("iadd2.b%d=0x%02x" % (boff, val), boff, val, rr, phase="rerun")
                    votes.append(o2)
                maj = max(set(votes), key=votes.count)
                sink.w("fb", {"family": "fb", "case": "iadd2.b%d=0x%02x" % (boff, val),
                              "field": "byte+%d" % boff, "value": val, "phase": "majority",
                              "observed": ",".join(votes), "outcome": maj, "reruns": 3})
            if fp64_of[0] is not None:
                hits.append((boff, val, fp64_of[0], cls))
            n += 1
            if n % 128 == 0:
                bb2 = dispatch(main)
                _, bo, _ = emit("baseline@%d" % n, -1, -1, bb2, phase="baseline")
                if bo != "ok":
                    sink.w("fb", {"family": "fb", "case": "__cascade", "value": n,
                                  "outcome": "hang",
                                  "note": "baseline re-validation failed at case %d; stopping" % n})
                    r.close()
                    return
    sink.w("fb", {"family": "fb", "case": "__verdict", "value": n,
                  "observed": json.dumps(hits)[:2000],
                  "match": len(hits) == 0,
                  "outcome": "ok",
                  "note": "%d single-byte encodings swept (the complete single-byte space: "
                          "all %d bytes x 256 values); %d reproduced a binary64 operation on "
                          "all %d input rows" % (n, ilen, len(hits), len(F64_ROWS))})
    r.close()


# ---------------------------------------------------------------- FE (MEM-19)
def const_program_census(args, n, srcpath):
    """Compile one of our own N-buffer kernels and measure the USC
    constant/uniform program it emits: its length, how many 0x67 device_loads
    it contains, and the base_slot byte of each.  Pure analysis of OUR OWN
    compiled bytes."""
    out = {}
    wd = os.path.join(args.work, "fe_cp")
    os.makedirs(wd, exist_ok=True)
    arch = os.path.join(wd, "cp%s.bin" % n)
    rc, so, se = sh([SHDUMP, "-o", arch, "-f", "k", srcpath], timeout=300)
    if rc != 0:
        out["cp_error"] = (so + se)[:300]
        return out
    blob = open(arch, "rb").read()
    for sym, key in (("_agc.main.constant_program", "cp"), ("_agc.main", "main")):
        rc, so, se = sh([sys.executable, AGXPARSE, arch, "--locate", sym], timeout=120)
        try:
            off, ln = [int(x, 0) for x in so.split()[:2]]
        except Exception:
            out[key + "_len"] = None
            continue
        body = blob[off:off + ln]
        out[key + "_len"] = ln
        out[key + "_sha256"] = hashlib.sha256(body).hexdigest()
        # 0x67 device_load leaders: 14-byte form, byte+2 in the known addr_mode set
        slots = []
        i = 0
        while i + 14 <= len(body):
            if body[i] == 0x67 and body[i + 2] in (0x44, 0x54, 0x46, 0x56):
                slots.append(body[i + 4])
                i += 14
            else:
                i += 1
        out[key + "_device_loads"] = len(slots)
        out[key + "_base_slots"] = slots
        if slots:
            out[key + "_base_slot_max"] = max(slots)
            out[key + "_base_slot_min"] = min(slots)
    return out



def fam_fe(sink, args):
    from persistrun import PersistRunner
    import isadb
    wd = os.path.join(args.work, "fe")
    os.makedirs(wd, exist_ok=True)

    # --- API ceiling + USC constant/uniform-program census.
    # For each declared buffer count: does the public path accept it, and how
    # many base slots does the emitted CONSTANT PROGRAM actually populate?
    # (On Apple9 the uniform preload is performed by 0x67 device_loads in
    # _agc.main.constant_program, not by a USC tag list -- so counting them and
    # reading their base_slot bytes IS the measurement MEM-19 asks for.)
    exe = os.path.join(args.bin, "mslprobe")
    for n in (1, 2, 4, 8, 16, 24, 28, 30, 31, 32, 40, 64):
        p = os.path.join(KERN, "slotdecl_%d.metal" % n)
        if not os.path.exists(p):
            continue
        rc, out, err = sh([exe, p], timeout=120)
        status = ("accept" if "COMPILE_STATUS accept" in out else
                  "reject" if "COMPILE_STATUS reject" in out else "error")
        diag = out.split("DIAG_BEGIN", 1)[1].split("DIAG_END", 1)[0].strip() if "DIAG_BEGIN" in out else ""
        r = {"family": "fe", "case": "declared_buffers_%d" % n, "value": n,
             "observed": status, "outcome": "ok" if status != "error" else "undecodable",
             "diag": diag[:800],
             "note": "public-path buffer-argument declaration ceiling"}
        if status == "accept":
            r.update(const_program_census(args, n, p))
        sink.w("fe", r)
    for n in (1, 2, 4, 8, 16, 24, 28, 30):
        p = os.path.join(KERN, "slotdeclu_%d.metal" % n)
        if not os.path.exists(p):
            continue
        r = {"family": "fe", "case": "uniform_read_buffers_%d" % n, "value": n,
             "outcome": "ok", "observed": "accept",
             "note": "UNIFORM (thread-invariant) reads: the accesses the compiler hoists "
                     "into the USC constant/uniform program"}
        r.update(const_program_census(args, "u%d" % n, p))
        sink.w("fe", r)

    # --- base-slot census arm
    src = os.path.join(KERN, "slot31.metal")
    arch = os.path.join(wd, "slot31.bin")
    rc, out, err = sh([SHDUMP, "-o", arch, "-f", "k", src], timeout=300)
    if rc != 0:
        sink.w("fe", {"family": "fe", "case": "__compile", "outcome": "undecodable",
                      "note": (out + err)[:600]})
        return
    rc, out, err = sh([sys.executable, AGXPARSE, arch, "--locate", "_agc.main"], timeout=120)
    abs_off, mlen = [int(x, 0) for x in out.split()[:2]]
    blob = open(arch, "rb").read()
    main = blob[abs_off:abs_off + mlen]
    dis, leftover = disasm(main)
    loads = [d for d in dis if d.get("mnemonic") == "device_load"]
    sink.w("fe", {"family": "fe", "case": "__carrier", "observed": main.hex()[:4000],
                  "outcome": "ok", "main_sha256": hashlib.sha256(main).hexdigest(),
                  "note": "%d device_load(s); leftover=%s; disasm=%s" % (
                      len(loads), leftover.hex(),
                      " ".join(str(d.get("mnemonic")) for d in dis))})

    # 31 input buffers: buffer k carries 0x51000000|k
    files = {}
    for k in range(31):
        p = os.path.join(wd, "b%d.bin" % k)
        open(p, "wb").write(struct.pack("<I", 0x51000000 | k) * 4)
        files[k] = p
    poison = os.path.join(wd, "poison.bin")
    open(poison, "wb").write(b"\xa5" * 16)
    files[0] = poison                      # buffer 0 is the output; poison it

    r = PersistRunner(source=src, function="k", fast_math=True, agxrun_persist=PERSIST)
    spliced = os.path.join(wd, "spliced.bin")

    def dispatch(mut_main, timeout=10.0):
        nb = bytearray(blob)
        nb[abs_off:abs_off + mlen] = mut_main
        open(spliced, "wb").write(bytes(nb))
        return r.request(archive=spliced, grid=1, tg=1, ins=files, outs={0: 16}, timeout=timeout)

    def decode(resp):
        o = resp["outs"].get(0, b"")
        if len(o) < 4:
            return None
        return struct.unpack("<I", o[:4])[0]

    base = dispatch(main)
    bw = decode(base)
    sink.w("fe", {"family": "fe", "case": "baseline", "observed": "%08x" % (bw or 0),
                  "outcome": "ok" if base["status"] == "OK" else "fault",
                  "fault_class": base.get("error") or "",
                  "note": "unmutated carrier; probe loads b17"})

    # locate the probe load: the device_load whose base_slot byte equals the
    # value that produced the baseline word, identified by splicing.
    if not loads:
        sink.w("fe", {"family": "fe", "case": "__no_load", "outcome": "undecodable"})
        r.close(); return
    probe = None
    for d in loads:
        off = d["offset"]
        cur = main[off + 4]
        mut = bytearray(main); mut[off + 4] = (cur + 1) & 0xFF
        rr = dispatch(bytes(mut))
        w = decode(rr)
        sink.w("fe", {"family": "fe", "case": "probe_id@0x%x" % off, "value": off,
                      "observed": "%08x" % (w or 0), "oracle": "%08x" % (bw or 0),
                      "outcome": "ok" if rr["status"] == "OK" else "fault",
                      "fault_class": rr.get("error") or "",
                      "note": "base_slot 0x%02x->0x%02x on the load at +0x%x" % (cur, (cur+1) & 0xFF, off)})
        if w is not None and bw is not None and w != bw and probe is None:
            probe = (off, cur)
    if probe is None:
        sink.w("fe", {"family": "fe", "case": "__probe_not_isolated", "outcome": "undecodable",
                      "note": "no device_load's base_slot byte changed the reported word"})
        r.close(); return
    poff, pbase = probe
    sink.w("fe", {"family": "fe", "case": "__probe", "value": poff,
                  "observed": "%02x" % pbase, "outcome": "ok",
                  "note": "probe device_load at _agc.main+0x%x, base_slot byte = 0x%02x" % (poff, pbase)})

    n = 0
    for val in range(256):
        mut = bytearray(main); mut[poff + 4] = val
        resp = dispatch(bytes(mut))
        w = decode(resp)
        st = resp["status"]
        outcome = ("hang" if st == "HANG" else
                   "victim" if "victim" in (resp.get("error") or "").lower() else
                   "fault" if st != "OK" else
                   "silent_zero" if w == 0 else
                   "unwritten" if w == 0xA5A5A5A5 else "ok")
        binding = (w - 0x51000000) if (w is not None and (w & 0xFFFFFF00) == 0x51000000) else None
        sink.w("fe", {"family": "fe", "case": "base_slot=%d" % val, "field": "base_slot",
                      "value": val, "observed": "%08x" % (w if w is not None else 0),
                      "binding": binding, "mirror_of": (val - 128) if val >= 128 else None,
                      "outcome": outcome, "fault_class": resp.get("error") or "", "status": st})
        if outcome in ("fault", "hang", "victim"):
            votes = [outcome]
            for _ in range(2):
                rr = dispatch(bytes(mut))
                st2 = rr["status"]
                o2 = ("hang" if st2 == "HANG" else
                      "victim" if "victim" in (rr.get("error") or "").lower() else
                      "fault" if st2 != "OK" else "ok")
                votes.append(o2)
            sink.w("fe", {"family": "fe", "case": "base_slot=%d" % val, "value": val,
                          "phase": "majority", "observed": ",".join(votes),
                          "outcome": max(set(votes), key=votes.count), "reruns": 3})
        n += 1
        if n % 128 == 0:
            bb2 = dispatch(main)
            if bb2["status"] != "OK":
                sink.w("fe", {"family": "fe", "case": "__cascade", "value": n, "outcome": "hang"})
                break
    sink.w("fe", {"family": "fe", "case": "__done", "value": n, "outcome": "ok"})
    r.close()


# ---------------------------------------------------------------- FF (TEX-01)
FF_FORMS = [("form05_baseline", 0x05), ("form01", 0x01), ("form07", 0x07),
            ("form00", 0x00), ("form0d", 0x0d)]
FF_UV = (0.375, 0.625)
# every value EXP-M4-14 found live on this instruction, plus boundaries
FF_HUNT_VALUES = [0x00, 0x01, 0x02, 0x04, 0x06, 0x08, 0x0c, 0x0d, 0x10, 0x18,
                  0x20, 0x40, 0x50, 0x54, 0x7f, 0x80, 0xc0, 0xc4, 0xd0, 0xf0, 0xff]


def ff_cases(path):
    ws = ["1.0", "2.0", "4.0", "0.5", "0.25", "0.0", "-0.0", "-1.0",
          "inf", "-inf", "nan", "1e-30", "1e30"]
    uvs = [("a", 0.375, 0.625), ("b", 0.75, 0.25), ("c", 0.9, 0.9), ("d", 0.125, 0.125)]
    with open(path, "w") as f:
        for un, u, v in uvs:
            for w in ws:
                f.write("%s_w%s %r %r %s\n" % (un, w, u, v, w))


def fam_ff(sink, args):
    import isadb
    wd = os.path.join(args.work, "ff")
    os.makedirs(wd, exist_ok=True)
    cf = os.path.join(wd, "cases.txt")
    ff_cases(cf)
    exe = os.path.join(args.bin, "texrun")
    for carrier, fn, extra in (("texlod", "k", []), ("texarr", "k", ["--array"])):
        src = os.path.join(KERN, carrier + ".metal")
        arch = os.path.join(wd, carrier + ".bin")
        rc, out, err = sh([SHDUMP, "-o", arch, "-f", fn, src], timeout=180)
        if rc != 0:
            sink.w("ff", {"family": "ff", "case": carrier + "/__compile",
                          "outcome": "undecodable", "note": (out + err)[:600]})
            continue
        rc, out, err = sh([sys.executable, AGXPARSE, arch, "--locate", "_agc.main"], timeout=120)
        abs_off, mlen = [int(x, 0) for x in out.split()[:2]]
        blob = open(arch, "rb").read()
        main = blob[abs_off:abs_off + mlen]
        dis, leftover = disasm(main)
        tas = [d for d in dis if d.get("mnemonic") == "tex_addr_setup"]
        sink.w("ff", {"family": "ff", "case": carrier + "/__carrier",
                      "observed": main.hex()[:4000], "outcome": "ok",
                      "main_sha256": hashlib.sha256(main).hexdigest(),
                      "note": "%d tex_addr_setup; leftover=%s; disasm=%s" % (
                          len(tas), leftover.hex(),
                          " ".join(str(d.get("mnemonic")) for d in dis))})
        if not tas:
            sink.w("ff", {"family": "ff", "case": carrier + "/__no_tex_addr_setup",
                          "outcome": "undecodable",
                          "note": "carrier does not contain the instruction under test"})
            continue
        off = tas[0]["offset"]
        orig = main[off + 1]
        sink.w("ff", {"family": "ff", "case": carrier + "/__instr", "value": off,
                      "observed": main[off:off + 12].hex(), "outcome": "ok",
                      "note": "tex_addr_setup at _agc.main+0x%x, form byte = 0x%02x" % (off, orig)})
        # Adversarial refuter hunt: with form 0x01, is there ANY operand-byte
        # value that makes the result depend on the third input?  If the form
        # really performed a projective divide, some operand encoding must
        # supply the divisor.  Sweeping every operand byte of the instruction
        # against two different w values is the strongest available test that
        # it does not.
        hunt = os.path.join(wd, "hunt_%s.txt" % carrier)
        with open(hunt, "w") as f:
            f.write("w1 %r %r 1.0\n" % FF_UV)
            f.write("w2 %r %r 2.0\n" % FF_UV)
            f.write("w4 %r %r 4.0\n" % FF_UV)
        for boff in range(2, 12):
            for bv in FF_HUNT_VALUES:
                mut = bytearray(blob)
                mm = bytearray(main)
                mm[off + 1] = 0x01
                mm[off + boff] = bv
                mut[abs_off:abs_off + mlen] = bytes(mm)
                sp = os.path.join(wd, "%s_hunt.bin" % carrier)
                open(sp, "wb").write(bytes(mut))
                run_stream([exe, sp, fn, "%s/form01_b%d_0x%02x" % (carrier, boff, bv), hunt] + extra,
                           sink, "ff", timeout=120)
        for label, fv in FF_FORMS:
            mut = bytearray(blob)
            mm = bytearray(main); mm[off + 1] = fv
            mut[abs_off:abs_off + mlen] = bytes(mm)
            sp = os.path.join(wd, "%s_%s.bin" % (carrier, label))
            open(sp, "wb").write(bytes(mut))
            run_stream([exe, sp, fn, "%s/%s" % (carrier, label), cf] + extra,
                       sink, "ff", timeout=600,
                       logpath=os.path.join(args.rawdir, "ff_%s_%s.log" % (carrier, label)))
    sink.w("ff", {"family": "ff", "case": "__done", "outcome": "ok"})


# --------------------------------------------------------------- FC / FD
def fam_fc(sink, args):
    run_stream([os.path.join(args.bin, "bindtex"), os.path.join(KERN, "bindtex.metal")],
               sink, "fc", timeout=900,
               logpath=os.path.join(args.rawdir, "fc_bindtex.log"))


def fam_fd(sink, args):
    exe = os.path.join(args.bin, "sampheap")
    src = os.path.join(KERN, "sampheap.metal")
    for mode, extra in (("ceiling", ["2000000"]), ("index", []), ("reuse", [])):
        run_stream([exe, src, mode] + extra, sink, "fd", timeout=1200,
                   logpath=os.path.join(args.rawdir, "fd_%s.log" % mode))
    # hang-prone arm: out-of-table resource IDs, under the GPU lease
    lease = os.path.expanduser("~/agxre/gpulease.sh")
    cmd = ([lease, "EXP-0159", "900", "--"] if os.path.exists(lease) else []) + [exe, src, "oob"]
    run_stream(cmd, sink, "fd", timeout=1200,
               logpath=os.path.join(args.rawdir, "fd_oob.log"))


FAMILIES = {"fa": fam_fa, "fb": fam_fb, "fc": fam_fc, "fd": fam_fd, "fe": fam_fe, "ff": fam_ff}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--family", default="all")
    ap.add_argument("--bin", default=os.path.join(os.path.expanduser("~/agxre/EXP-0159"), "bin"))
    ap.add_argument("--work", default=os.path.join(os.path.expanduser("~/agxre/EXP-0159"), "work"))
    args = ap.parse_args()
    args.rawdir = os.path.join(ROOT, "raw", args.run_id)
    os.makedirs(args.rawdir, exist_ok=True)
    os.makedirs(args.work, exist_ok=True)
    sink = Sink(args.rawdir)

    meta_path = os.path.join(args.rawdir, "00_meta.json")
    if not os.path.exists(meta_path):
        _, dev, _ = sh([os.path.join(args.bin, "mslprobe")], timeout=60)
        _, sw, _ = sh("sw_vers", timeout=30)
        _, cc, _ = sh("clang --version | head -1", timeout=30)
        hashes = {}
        for d in (KERN, os.path.join(KERN, "fa"), HERE):
            for f in sorted(os.listdir(d)):
                p = os.path.join(d, f)
                if os.path.isfile(p) and f.split(".")[-1] in ("metal", "m", "py"):
                    hashes[os.path.relpath(p, ROOT)] = hashlib.sha256(
                        open(p, "rb").read()).hexdigest()
        json.dump({"run_id": args.run_id, "target": "G17P",
                   "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "device": dev, "sw_vers": sw, "clang": cc.strip(),
                   "python": sys.version.split()[0],
                   "git_revision_at_freeze": "7dc67d768ada3c016771923bffd5b9647dd14813",
                   "concurrency": "run UNLOCKED and concurrent with sibling GPU experiments "
                                  "except the FD out-of-table arm, which takes gpulease.sh",
                   "source_sha256": hashes}, open(meta_path, "w"), indent=1, sort_keys=True)

    fams = list(FAMILIES) if args.family == "all" else args.family.split(",")
    for f in fams:
        t0 = time.time()
        try:
            FAMILIES[f](sink, args)
        except Exception as e:
            import traceback
            sink.w(f, {"family": f, "case": "__exception", "outcome": "undecodable",
                       "note": traceback.format_exc()[-1500:]})
        print("FAMILY %s done in %.1fs" % (f, time.time() - t0), flush=True)
    sink.close()


if __name__ == "__main__":
    main()
