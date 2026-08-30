#!/usr/bin/env python3
"""EXP-0207 capture driver.

Seven fields across six instructions, on four carrier kinds (compute, fragment,
vertex, mesh).  One JSON object per case is appended to raw/<run_id>/sweep.jsonl
and flushed + fsync'd immediately, so a kill or a GPU wedge costs at most ONE
case.  Refuses to reuse an existing run id.

Full read-back payloads are content-addressed into raw/<run_id>/payloads.jsonl,
written once per DISTINCT payload; every case record carries the digest.  That is
lossless -- every observation can be reconstructed byte-for-byte -- while keeping
a 16 kB per-case read-back from multiplying by 8000 cases.

  python3 harness/run207.py --run-id g17p_YYYYMMDD_runNN --out-root raw
  python3 harness/run207.py --run-id pilot01 --out-root work --arms sr_c
"""
import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import pinned207                                               # noqa: E402
import plan207 as SP                                           # noqa: E402

PINNED = pinned207.verify()
ISA = pinned207.load_isadb()
AGXPARSE = pinned207.agxparse_path()
MESHEXTRACT = pinned207.mesh_extract_path()

BIN = os.path.join(EXP, "work", "bin")
SHDUMP = os.path.join(BIN, "shdump207")
SHDUMP_MESH = os.path.join(BIN, "shdump_mesh207")
RENDERSWEEP = os.path.join(BIN, "rendersweep207")
MESHSWEEP = os.path.join(BIN, "meshsweep207")
AGXPERSIST = os.path.join(BIN, "agxrun_persist")
sys.path.insert(0, BIN)


def _sha32(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()[:32]


HARNESS_SHA = _sha32(os.path.abspath(__file__))

from saferunner207 import SafePersistRunner, SafeRenderRunner   # noqa: E402

REQ_TIMEOUT = 10.0
BUILD_TIMEOUT = 180
TOL = 1e-5
OWN_FAULT = "Caused GPU Hang Error"
COLLATERAL = ("Discarded (victim", "Ignored (for causing prior")
MAX_CONSECUTIVE_UNRECOVERED = 5


# ------------------------------------------------------------------ utils ----
def f32(x):
    return struct.unpack("<f", struct.pack("<f", float(x)))[0]


def sh(args, timeout=BUILD_TIMEOUT):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def digest(s):
    return hashlib.sha256(s.encode("ascii")).hexdigest()[:32]


def get_bits(block, start, width):
    v = int.from_bytes(block, "little")
    return (v >> start) & ((1 << width) - 1)


def set_bits(block, start, width, value):
    v = int.from_bytes(block, "little")
    m = ((1 << width) - 1) << start
    v = (v & ~m) | ((value & ((1 << width) - 1)) << start)
    return v.to_bytes(len(block), "little")


def splice(src, dst, off, block):
    with open(src, "rb") as f:
        b = bytearray(f.read())
    b[off:off + len(block)] = block
    with open(dst, "wb") as f:
        f.write(bytes(b))


def clear_reference(fmt, W, H, nrt, clear):
    """The exact bytes a target holds if the draw contributed nothing.

    Host-computed from the frozen clear colour and the pixel format, so
    "the store did not land" is decided against a known constant rather than
    against a fitted one.  None where the format's clear encoding is not
    modelled here, in which case the coverage sentinel decides instead."""
    c = clear[0]
    if fmt == 125:
        px = struct.pack("<4f", *[float(x) for x in c])
    elif fmt == 123:
        px = struct.pack("<4I", *[int(x) & 0xFFFFFFFF for x in c])
    elif fmt == 70:
        px = bytes(max(0, min(255, int(round(float(x) * 255.0)))) for x in c)
    else:
        return None
    return (px * (W * H) * nrt).hex()


def is_collateral(r):
    e = str(r.get("error", ""))
    return any(k in e for k in COLLATERAL)


def safe_request(runner, call):
    try:
        return call()
    except Exception as e:                                     # noqa: BLE001
        tb = traceback.format_exc().strip().replace("\n", " | ")[-400:]
        try:
            runner._kill(); runner._start()
        except Exception:                                      # noqa: BLE001
            pass
        return {"status": "RUNNER_EXCEPTION", "outs": {}, "gputime_ns": None,
                "error": "runner raised: %s :: %s" % (str(e)[:120], tb),
                "restarted": True, "raw": []}


# ------------------------------------------------------------------ build ----
def stage_of(arm):
    if arm["kind"] == "compute":
        return None
    if arm["kind"] == "mesh":
        return "mesh"
    return "vertex" if arm["stage"] == "vertex" else "fragment"


def build_archive(arm, workdir):
    out = os.path.join(workdir, arm["arm"] + ".bin")
    src = os.path.join(EXP, arm["kernel"])
    if arm["kind"] == "compute":
        r = sh([SHDUMP, "-o", out, "-f", arm["func"], "--no-fast-math", src])
    elif arm["kind"] == "mesh":
        r = sh([SHDUMP_MESH, "-o", out, "--object", arm["obj"], "--mesh", arm["mesh"],
                "--fragment", arm["frag"], "--color-format", "125", src])
    else:
        a = [SHDUMP, "-o", out, "--render", "--vertex", arm["vs"], "--fragment", arm["fs"],
             "--color-format", str(arm["fmt"]), "--nrt", str(arm["nrt"]),
             "--samples", str(arm["samples"]), "--blend", arm["blend"], "--no-fast-math"]
        if arm["depth"]:
            a.append("--depth")
        a.append(src)
        r = sh(a)
    if r.returncode != 0:
        raise RuntimeError("build failed for %s: %s" % (arm["arm"], r.stderr[-800:]))
    return out, r.stderr


def parse_tool(arm):
    return MESHEXTRACT if arm["kind"] == "mesh" else AGXPARSE


def locate(arm, archive):
    st = stage_of(arm)
    a = [sys.executable, parse_tool(arm), archive, "--locate", "_agc.main"]
    if st:
        a[3:3] = ["--stage", st]
    r = sh(a)
    if r.returncode != 0:
        raise RuntimeError("locate failed: %s" % r.stderr[-400:])
    return int(r.stdout.split()[0])


def extract_hex(arm, archive):
    st = stage_of(arm)
    a = [sys.executable, parse_tool(arm), archive, "--extract-hex"]
    if st:
        a[3:3] = ["--stage", st]
    r = sh(a)
    if r.returncode != 0:
        raise RuntimeError("extract failed: %s" % r.stderr[-400:])
    return r.stdout.strip()


# -------------------------------------------------------- anchor resolve -----
def tokenize(hexstr):
    try:
        recs, leftover = ISA.disassemble(bytes.fromhex(hexstr))
        return recs, leftover.hex()
    except Exception as e:                                     # noqa: BLE001
        return None, "tokenize_error: %s" % e


def occurrences(hexstr, mnem):
    """Byte offsets of every clean-tokenized occurrence of `mnem`, plus a
    fallback even-offset decode scan when the program does not tokenize
    cleanly.  The scan requires decode_one to agree on the mnemonic."""
    recs, leftover = tokenize(hexstr)
    hits = []
    if recs is not None:
        off = 0
        for r in recs:
            # A tokenization that stops early appends an <unknown> record with
            # length None; walking past it would compute nonsense offsets, so the
            # walk STOPS there and the scan path below takes over.
            if r.get("length") is None:
                break
            if r["mnemonic"] == mnem:
                hits.append(off)
            off += r["length"]
        if hits and leftover == "":
            return hits, "tokenized", leftover
    b = bytes.fromhex(hexstr)
    scan = []
    for off in range(0, len(b) - 1, 2):
        try:
            rec, _ln = ISA.decode_one(b, off)
        except Exception:                                      # noqa: BLE001
            continue
        if rec["mnemonic"] == mnem:
            scan.append(off)
    if hits:
        return hits, "tokenized_with_leftover", leftover
    return scan, "scan", leftover


def resolve_anchor(arm, hexstr):
    kind, val = arm["anchor"]
    # The occurrence we LOCATE may be a different mnemonic from the one we RULE
    # ON: `fen_syn` locates the compiler's own 4-byte `scoreboard_fence` and
    # pre-splices byte0 0x07 -> 0x80, which is the documented byte0 sibling
    # relationship and yields `dev_scoreboard_fence` at exactly the same length,
    # in a position the compiler chose for a fence.
    mnem = arm.get("anchor_instr", arm["instr"])
    if kind == "sr":
        b = bytes.fromhex(hexstr)
        hits = []
        for off in range(0, len(b) - 3, 2):
            if (b[off] & 7) == 4 and b[off + 1] == val:
                try:
                    rec, _ = ISA.decode_one(b, off)
                except Exception:                              # noqa: BLE001
                    continue
                if rec["mnemonic"] == "get_sr":
                    hits.append(off)
        hits = sorted(set(hits))
        if hits:
            return hits[0], "sr_scan:%d" % val, hits
        return None, "sr_absent:%d" % val, []
    occ, how, _lo = occurrences(hexstr, mnem)
    if kind == "occ":
        if len(occ) > val:
            return occ[val], "%s#%d" % (how, val), occ
        return None, "occ_absent(%d of %d)" % (val, len(occ)), occ
    if kind == "pat":
        if occ:
            return occ[0], "%s#0" % how, occ
        return None, "pattern_absent", occ
    if kind == "patbytes":
        b = bytes.fromhex(hexstr)
        pre = bytes.fromhex(val)
        for o in occ:
            if b[o:o + len(pre)] == pre:
                return o, "%s+prefix:%s" % (how, val), occ
        return None, "prefix_absent:%s(of %d occurrences)" % (val, len(occ)), occ
    return None, "bad_anchor", []


# ---------------------------------------------------------------- payloads ---
class PayloadStore:
    """Content-addressed, append-only.  Each DISTINCT read-back is written once;
    case records carry its digest.  Lossless, and V (distinct valid payloads) is
    then directly countable from the digests."""

    def __init__(self, path):
        self.f = open(path, "w")
        self.seen = set()

    def put(self, kind, payload):
        d = digest(kind + ":" + payload)
        if d not in self.seen:
            self.seen.add(d)
            self.f.write(json.dumps({"d": d, "kind": kind, "hex": payload}) + "\n")
            self.f.flush()
            os.fsync(self.f.fileno())
        return d

    def close(self):
        self.f.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out-root", default="raw")
    ap.add_argument("--arms", default="")
    ap.add_argument("--fields", default="")
    ap.add_argument("--max-cases", type=int, default=0)
    ap.add_argument("--census-only", action="store_true")
    ap.add_argument("--order", choices=("forward", "reverse"), default="forward",
                    help="GATE E: the confirmation run must use a REVERSED or shuffled "
                         "case order, so an order-dependent artefact cannot reproduce "
                         "itself identically in both runs")
    args = ap.parse_args()

    outdir = os.path.join(EXP, args.out_root, args.run_id)
    if os.path.exists(outdir):
        sys.exit("run id already exists: %s (never reuse a run id)" % outdir)
    os.makedirs(outdir)
    workdir = os.path.join(EXP, "work", "arch_" + args.run_id)
    os.makedirs(workdir, exist_ok=True)

    sweep = open(os.path.join(outdir, "sweep.jsonl"), "w")
    payloads = PayloadStore(os.path.join(outdir, "payloads.jsonl"))
    counter = {"n": 0}

    def emit(rec):
        rec.setdefault("t", round(time.time(), 3))
        rec.setdefault("idx", counter["n"])
        counter["n"] += 1
        sweep.write(json.dumps(rec, sort_keys=True) + "\n")
        sweep.flush()
        os.fsync(sweep.fileno())

    # input blobs the compute carriers bind
    hipress = os.path.join(workdir, "hipress.bin")
    with open(hipress, "wb") as f:
        f.write(struct.pack("<%dI" % (SP.CGRID * 16),
                            *[(i * 2654435761) & 0xFFFFFFFF for i in range(SP.CGRID * 16)]))
    zeros = os.path.join(workdir, "zeros.bin")
    with open(zeros, "wb") as f:
        f.write(b"\0" * 4096)
    poison = os.path.join(workdir, "poison.bin")
    with open(poison, "wb") as f:
        f.write(struct.pack("<%dI" % SP.CGRID, *([SP.POISON_U32] * SP.CGRID)))
    INFILES = {"hipress": hipress, "zeros": zeros}

    env = {
        "run_id": args.run_id,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pinned": {k: v[1] for k, v in PINNED.items()},
        "pinned_db_instructions": len(ISA.DB),
        "host": sh(["hostname"]).stdout.strip(),
        "uname": sh(["uname", "-a"]).stdout.strip(),
        "sw_vers": sh(["sw_vers"]).stdout.strip(),
        "python": sys.version.split()[0],
        "argv": sys.argv,
        "case_order": args.order,
        "harness_sha256_32": HARNESS_SHA,
        "concurrent_gpu_procs": [
            l for l in sh(["ps", "-Ao", "pid,comm"]).stdout.splitlines()
            if ("agxrun" in l or "rendersweep" in l or "meshsweep" in l or "shdump" in l)],
    }
    json.dump(env, open(os.path.join(outdir, "00_env.json"), "w"), indent=1, sort_keys=True)

    want = set(a for a in args.arms.split(",") if a)
    wantf = set(f for f in args.fields.split(",") if f)
    resolution = {}
    hangs_total = [0]
    hp = SP.hang_policy()

    for arm in SP.ARMS:
        if want and arm["arm"] not in want:
            continue
        t_arm = time.time()
        try:
            archive, buildlog = build_archive(arm, workdir)
        except Exception as e:                                 # noqa: BLE001
            emit({"kind": "arm_error", "arm": arm["arm"], "instr": arm["instr"],
                  "error": str(e)[:800], "outcome": "undecodable"})
            resolution[arm["arm"]] = {"status": "BUILD_FAILED", "error": str(e)[:800]}
            continue
        try:
            hx = extract_hex(arm, archive)
            base = locate(arm, archive)
        except Exception as e:                                 # noqa: BLE001
            emit({"kind": "arm_error", "arm": arm["arm"], "instr": arm["instr"],
                  "error": "extract/locate: %s" % str(e)[:600], "outcome": "undecodable"})
            resolution[arm["arm"]] = {"status": "EXTRACT_FAILED", "error": str(e)[:600]}
            continue

        off, how, hits = resolve_anchor(arm, hx)
        recs, leftover = tokenize(hx)
        if off is None:
            res = {"status": "NOT_ATTEMPTED", "why": how, "hits": hits,
                   "program_len": len(hx) // 2, "tokenize_leftover": leftover}
            resolution[arm["arm"]] = res
            emit({"kind": "arm_not_attempted", "arm": arm["arm"], "instr": arm["instr"],
                  "program_hex": hx, **res})
            continue

        desc = next(d for d in ISA.DB if d["mnemonic"] == arm["instr"])
        ilen = desc["length"]
        blk0 = bytes.fromhex(hx)[off:off + ilen]
        abs_off = base + off
        # PRE-SPLICE: some arms rule on an instruction the compiler does not
        # emit, in a POSITION the compiler chose for its sibling.  The transform
        # is applied once, becomes the arm's baseline program, and is recorded
        # in the arm_meta so it is never mistaken for an as-compiled occurrence.
        pre = arm.get("pre_splice")
        if pre:
            bb = bytearray(blk0)
            for (bi, bv) in pre:
                bb[bi] = bv
            blk0 = bytes(bb)
            prearchive = os.path.join(workdir, arm["arm"] + "_pre.bin")
            splice(archive, prearchive, abs_off, blk0)
            archive = prearchive
            try:
                rec_chk, ln_chk = ISA.decode_one(
                    bytes(bytearray(bytes.fromhex(hx))[:off] + bytearray(blk0) +
                          bytearray(bytes.fromhex(hx))[off + ilen:]), off)
                pre_decodes_as = (rec_chk["mnemonic"], ln_chk)
            except Exception as e:                             # noqa: BLE001
                pre_decodes_as = ("UNDECODABLE:%s" % str(e)[:60], None)
        fieldsdesc = {f["name"]: f for f in desc["fields"]}
        ruled = [f for f in arm["fields"] if f in fieldsdesc]
        dropped = [f for f in arm["fields"] if f not in fieldsdesc]

        resolution[arm["arm"]] = {
            "status": "RESOLVED", "instr": arm["instr"], "how": how, "hits": hits,
            "main_offset": off, "abs_off": abs_off, "instr_hex": blk0.hex(),
            "instr_len": ilen, "program_len": len(hx) // 2,
            "tokenize_leftover": leftover, "occurrences": len(hits),
            "fields_ruled": ruled, "fields_dropped_not_in_descriptor": dropped,
            "baseline_field_values": {f["name"]: get_bits(blk0, f["start"], f["width"])
                                      for f in desc["fields"]},
            "pre_splice": pre,
            "pre_splice_decodes_as": (pre_decodes_as if pre else None),
            "anchor_instr": arm.get("anchor_instr", arm["instr"]),
        }
        emit({"kind": "arm_meta", "arm": arm["arm"], "instr": arm["instr"],
              "stage": arm["stage"], "why": arm["why"],
              "carrier": {k: arm.get(k) for k in
                          ("kernel", "func", "vs", "fs", "obj", "mesh", "frag", "nrt",
                           "samples", "fmt", "blend", "depth", "W", "H", "grid", "tg",
                           "draw", "outbuf")},
              **resolution[arm["arm"]], "program_hex": hx})
        if args.census_only:
            continue

        spdir = os.path.join(workdir, arm["arm"] + "_sp")
        os.makedirs(spdir, exist_ok=True)
        spseq = [0]

        def next_splice_path():
            spseq[0] += 1
            q = os.path.join(spdir, "sp%06d.bin" % spseq[0])
            old = os.path.join(spdir, "sp%06d.bin" % (spseq[0] - 64))
            if os.path.exists(old):
                try:
                    os.unlink(old)
                except OSError:
                    pass
            return q

        # ------------------------------------------------ runner + raw case --
        if arm["kind"] == "compute":
            runner = SafePersistRunner(source=os.path.join(EXP, arm["kernel"]),
                                       function=arm["func"], fast_math=False,
                                       agxrun_persist=AGXPERSIST)
            ow = arm.get("out_words", 1)
            nwords = SP.CGRID * ow
            nbytes_out = nwords * 4
            poison_out = os.path.join(workdir, "poison_%d.bin" % nwords)
            if not os.path.exists(poison_out):
                with open(poison_out, "wb") as pf:
                    pf.write(struct.pack("<%dI" % nwords, *([SP.POISON_U32] * nwords)))
            ins = {0: poison_out, 4: poison}
            for slot, name in arm.get("ins", {}).items():
                ins[slot] = INFILES[name]
            # The host knows every codeword the dump carrier seeds, so a
            # clobbered slot is identified by NAME, not merely counted.
            codewords = None
            if ow == 17:
                seed = struct.unpack("<%dI" % (SP.CGRID * 16), open(hipress, "rb").read())
                codewords = [[(seed[t * 16 + i] ^ (0xC0DE0000 + i * 0x1111)) & 0xFFFFFFFF
                              for i in range(16)] for t in range(SP.CGRID)]

            def raw_case(arcpath):
                r = safe_request(runner, lambda: runner.request(
                    archive=arcpath, grid=arm["grid"], tg=arm["tg"], ins=ins,
                    outs={0: nbytes_out, 4: SP.CGRID * 4}, timeout=REQ_TIMEOUT))
                if r["status"] != "OK" or 0 not in r["outs"] or 4 not in r["outs"]:
                    return None, r
                sent = list(struct.unpack("<%dI" % SP.CGRID, r["outs"][4]))
                n_sent = sum(1 for x in sent[:arm["grid"]]
                             if x != SP.POISON_U32)
                if n_sent == 0:
                    r = dict(r); r["status"] = "SENTINEL_MISS"
                    r["error"] = "no integrity-sentinel lane written: dispatch did not execute"
                    return None, r
                vals = list(struct.unpack("<%dI" % nwords, r["outs"][0]))
                n_poison = sum(1 for v in vals[:arm["grid"] * ow] if v == SP.POISON_U32)
                if n_poison == arm["grid"] * ow:
                    r = dict(r); r["status"] = "OUT_NOT_WRITTEN"
                    r["error"] = ("dispatch ran (%d sentinel lanes) but every read-back "
                                  "lane is still 0xDEADBEEF poison" % n_sent)
                    return None, r
                blob = ",".join("%08x" % v for v in vals[:arm["grid"] * ow])
                o = {"d": payloads.put("words", blob), "w": vals[:8],
                     "sent": n_sent, "poison": n_poison, "words": vals}
                if ow == 17:
                    o["sr"] = [vals[t * 17 + 16] for t in range(arm["grid"])]
                    clob = sorted({i for t in range(arm["grid"]) for i in range(16)
                                   if vals[t * 17 + i] != codewords[t][i]})
                    o["clobbered_codeword_slots"] = clob
                    o["n_clobbered"] = len(clob)
                else:
                    o["sr"] = vals[:arm["grid"]]
                return o, r

            def restart():
                runner._kill(); runner._start()

        elif arm["kind"] == "mesh":
            runner = SafeRenderRunner(os.path.join(EXP, arm["kernel"]), exe=MESHSWEEP)
            clearref = clear_reference(125, arm["W"], arm["H"], 1, arm["clear"])

            def raw_case(arcpath):
                req = {"id": "c", "archive": arcpath, "object": arm["obj"],
                       "mesh": arm["mesh"], "fragment": arm["frag"],
                       "w": arm["W"], "h": arm["H"], "clear": arm["clear"],
                       "fbuf": SP.SRC, "tgobj": arm["tgobj"], "tgmesh": arm["tgmesh"],
                       "grid": arm["grid"]}
                r = safe_request(runner, lambda: runner.request(req, timeout=REQ_TIMEOUT))
                if r.get("status") != "OK" or "raw" not in r:
                    return None, r
                if r["raw"] == clearref:
                    r = dict(r); r["status"] = "SENTINEL_MISS"
                    r["error"] = "frame is byte-identical to the clear colour: nothing drawn"
                    return None, r
                return {"d": payloads.put("frame", r["raw"]), "cov": None,
                        "p": r["raw"][:64]}, r

            def restart():
                runner.restart()

        else:
            runner = SafeRenderRunner(os.path.join(EXP, arm["kernel"]), exe=RENDERSWEEP)
            clearref = clear_reference(arm["fmt"], arm["W"], arm["H"], arm["nrt"], arm["clear"])

            def raw_case(arcpath):
                req = {"id": "c", "archive": arcpath, "vs": arm["vs"], "fs": arm["fs"],
                       "w": arm["W"], "h": arm["H"], "nrt": arm["nrt"],
                       "samples": arm["samples"], "format": arm["fmt"],
                       "blend": arm["blend"], "depth": arm["depth"],
                       "outbuf": arm["outbuf"], "clear": arm["clear"],
                       "fbuf": SP.SRC, "vbuf": SP.VP}
                if arm.get("draw"):
                    req["draw"] = arm["draw"]
                    req["basevertex"] = arm["basevertex"]
                    req["baseinstance"] = arm["baseinstance"]
                    req["instances"] = arm["instances"]
                r = safe_request(runner, lambda: runner.request(req, timeout=REQ_TIMEOUT))
                if r.get("status") != "OK" or "raw" not in r:
                    return None, r
                ob = r.get("outbuf", "")
                nw = len(ob) // 8
                cov = sum(1 for i in range(nw)
                          if ob[i*8:(i+1)*8] != "efbeadde")
                if arm["outbuf"] and cov == 0:
                    r = dict(r); r["status"] = "SENTINEL_MISS"
                    r["error"] = ("the coverage sentinel is entirely poison: the "
                                  "fragment stage never ran (no draw)")
                    return None, r
                return {"d": payloads.put("frame+out", r["raw"] + "|" + ob),
                        "cov": cov, "p": r["raw"][:64],
                        "cleared": (r["raw"] == clearref) if clearref else None}, r

            def restart():
                runner.restart()

        recovery = {"restarts": 0, "retries": 0, "collateral": 0, "unrecovered": 0,
                    "consecutive_unrecovered": 0}

        def healthy():
            g, _ = raw_case(archive)
            return g is not None

        def wait_for_health():
            delay, waited, n = 0.2, 0.0, 0
            while waited < 40.0:
                restart(); recovery["restarts"] += 1; n += 1
                time.sleep(delay); waited += delay
                if healthy():
                    return n
                delay = min(delay * 2.0, 5.0)
            return -1

        def run_case(arcpath):
            """EXP-0147's measured recovery order: retry IN PLACE first (a sibling's
            reset makes the very next submission a victim), restart only if that
            fails, and NEVER record collateral as a fault."""
            for attempt in range(5):
                g, r = raw_case(arcpath)
                if g is not None:
                    return g, r, 0, attempt + 1
                recovery["retries"] += 1
                if r.get("status") == "SENTINEL_MISS":
                    g2, r2 = raw_case(arcpath)
                    if g2 is not None:
                        return g2, r2, 0, attempt + 2
                    if healthy():
                        return None, r2, 0, attempt + 2
                    r = r2
                if is_collateral(r):
                    recovery["collateral"] += 1
                time.sleep(0.05 + 0.1 * attempt)
            n = wait_for_health()
            if n < 0:
                recovery["unrecovered"] += 1
                recovery["consecutive_unrecovered"] += 1
                return None, r, 99, 6
            recovery["consecutive_unrecovered"] = 0
            g2, r2 = raw_case(arcpath)
            return g2, r2, n, 7

        # ------------------------------------------------------- baseline ----
        base_obs, base_raw, _, _ = run_case(archive)
        emit({"kind": "baseline", "arm": arm["arm"], "instr": arm["instr"],
              "bytes": blk0.hex(), "observed": base_obs,
              "status": base_raw.get("status"),
              "error": str(base_raw.get("error", ""))[:300],
              "outcome": "ok" if base_obs is not None else "fault"})
        if base_obs is None:
            emit({"kind": "arm_error", "arm": arm["arm"], "instr": arm["instr"],
                  "error": "baseline did not run: %s" % str(base_raw.get("error", ""))[:400],
                  "outcome": "fault"})
            try:
                runner.close()
            except Exception:                                  # noqa: BLE001
                pass
            continue

        # ---------------------------------------------------- calibration ----
        exec_width = 32
        for ln in buildlog.splitlines():
            if "threadExecutionWidth" in ln:
                try:
                    exec_width = int(ln.split("threadExecutionWidth =")[1].split(",")[0])
                except Exception:                              # noqa: BLE001
                    pass
        calib = {"exec_width": exec_width}
        base_sel = get_bits(blk0, fieldsdesc["sr_sel"]["start"], 8) \
            if arm["instr"] == "get_sr" else None
        centre_c = 0.5
        if arm["instr"] == "get_sr" and arm["oracle"] in ("sr_frag", "sr_frag2"):
            pix = base_raw.get("pixels") or []
            rs = [p[0] for p in pix[:arm["W"] * arm["H"]]]
            cs = [f32(rs[py * arm["W"] + px] - px)
                  for py in range(arm["H"]) for px in range(arm["W"])] if rs else []
            if arm["oracle"] == "sr_frag":
                calib["affine_model_holds"] = bool(cs) and len(set(cs)) == 1
                calib["centre_c"] = cs[0] if calib["affine_model_holds"] else None
                if calib["affine_model_holds"]:
                    centre_c = cs[0]
            else:
                calib["affine_model_holds"] = None
        if arm["instr"] == "get_sr" and arm["oracle"] in ("sr_compute", "sr_compute_dump"):
            exp = SP.sr_oracle_compute(base_sel, exec_width)
            calib["baseline_matches_documented_sr"] = (
                exp is not None and
                base_obs["sr"][:arm["grid"]] ==
                [v + SP.SR_BIAS for v in exp][:arm["grid"]])
        calib["baseline_sr_sel"] = base_sel
        calib["baseline_field_values"] = resolution[arm["arm"]]["baseline_field_values"]
        emit({"kind": "calibration", "arm": arm["arm"], "instr": arm["instr"], **calib})

        # -------------------------------------------------------- oracles ----
        def sem_oracle(field, value, cof=None):
            """Host-computed prediction for this case.  Returns
            (payload, kind) or (None, kind) where the pinned db documents no
            meaning.  NOTHING here reads the GPU."""
            ok = arm["oracle"]
            if arm["instr"] == "frag_color_store" and field == "store_mode":
                return ({"expect": "store" if value in SP.ADDR_MODE_VALUES else "no_store"},
                        "structural_partition")
            if arm["instr"] == "iter" and field == "b9":
                b = get_bits(blk0, fieldsdesc["b9"]["start"], 8)
                return ({"expect": "baseline" if value == b else "differs"},
                        "structural_partition")
            if arm["instr"] == "mesh_out_src" and field == "sel":
                b = get_bits(blk0, fieldsdesc["sel"]["start"], 8)
                return ({"expect": "baseline" if value == b else "differs"},
                        "structural_partition")
            if arm["instr"] == "vtx_coord_xform":
                return ({"expect": "baseline"}, "baseline_equality")
            if arm["instr"] == "dev_scoreboard_fence" and field == "scope_flag":
                return ({"expect": "correct" if value in (0x00, 0x04) else "unknown"},
                        "ordering")
            if arm["instr"] == "get_sr":
                if field == "form":
                    bf = get_bits(blk0, fieldsdesc["form"]["start"], 1)
                    if value == bf:
                        return ({"expect": "sr_value"}, "sr_value")
                    return ({"expect": "not_sr_value"}, "sr_value")
                if field == "dst_hi":
                    bh = get_bits(blk0, fieldsdesc["dst_hi"]["start"], 3)
                    if value == bh:
                        return ({"expect": "sr_value"}, "dst_routing")
                    return ({"expect": "not_sr_value"}, "dst_routing")
                if field == "__form_x_srsel":
                    exp = documented_sr(cof)
                    if exp is None:
                        return (None, "sr_value")
                    return ({"sr": cof, "v": exp}, "sr_value")
            return (None, "none")

        def documented_sr(sel):
            if arm["oracle"] in ("sr_compute", "sr_compute_dump", "sr_compute_hi"):
                return SP.sr_oracle_compute(sel, exec_width)
            if arm["oracle"] in ("sr_frag", "sr_frag2"):
                return SP.sr_oracle_frag(sel, arm["W"], arm["H"])
            if arm["oracle"] == "sr_vertex":
                return SP.sr_oracle_vertex(sel)
            return None

        def sr_matches(obs, raw, sel):
            """Does the observation equal the DOCUMENTED value of `sel`?"""
            exp = documented_sr(sel)
            if exp is None:
                return None
            if arm["kind"] == "compute":
                if obs.get("poison"):
                    return False
                return obs["sr"][:arm["grid"]] == \
                    [v + SP.SR_BIAS for v in exp][:arm["grid"]]
            pix = raw.get("pixels") or []
            if not pix:
                return None
            got = [p[0] for p in pix[:arm["W"] * arm["H"]]]
            if arm["oracle"] == "sr_frag":
                pred = [f32(v + centre_c) for v in exp]
            elif arm["oracle"] == "sr_vertex":
                pred = []
                for py in range(arm["H"]):
                    for px in range(arm["W"]):
                        l = SP.bary(SP.TRI_FULL, px, py, arm["W"], arm["H"])
                        pred.append(sum(l[i] * float(exp[i]) for i in range(3)))
            else:
                return None
            return all(abs(a - b) <= TOL * max(1.0, abs(b)) for a, b in zip(got, pred))

        def obs_equal(a, b):
            return a is not None and b is not None and a["d"] == b["d"]

        def classify(field, value, obs, raw, cof=None):
            """FROZEN outcome enum + an orthogonal `class`.  A malformed runner
            response is a MEASUREMENT FAILURE, never a hang and never a fault."""
            sem, okind = sem_oracle(field, value, cof)
            if raw.get("status") in ("MALFORMED", "RUNNER_EXCEPTION", "BAD_RESPONSE"):
                return "measurement_failed", sem, okind, None, False, raw.get("status")
            if raw.get("status") == "HANG":
                return "hang", sem, okind, None, False, None
            if obs is None:
                st = raw.get("status")
                if st == "SENTINEL_MISS":
                    return ("no_dispatch" if arm["kind"] == "compute" else "no_draw",
                            sem, okind, None, False, None)
                if st == "OUT_NOT_WRITTEN":
                    return "not_written", sem, okind, None, False, "POISON_INTACT"
                if is_collateral(raw):
                    return "invalid_run", sem, okind, None, False, None
                return "fault", sem, okind, None, False, None
            moved = not obs_equal(obs, base_obs)
            if arm["instr"] == "get_sr" and field in ("form", "dst_hi", "__form_x_srsel"):
                sel = cof if cof is not None else base_sel
                m = sr_matches(obs, raw, sel)
                if m is None:
                    return ("wrong_value" if moved else "ok"), sem, okind, None, None, \
                           "NO_DOCUMENTED_SR"
                if field == "__form_x_srsel":
                    return ("ok" if m else "wrong_value"), sem, okind, m, m, \
                           ("SR_MATCH" if m else ("SR_MOVED" if moved else "SR_NOMOVE"))
                want_sr = (sem or {}).get("expect") == "sr_value"
                match = (m == want_sr)
                return ("ok" if match else "wrong_value"), sem, okind, m, match, \
                       ("SR_MATCH" if m else ("SR_MOVED" if moved else "SR_NOMOVE"))
            if arm["instr"] == "dev_scoreboard_fence":
                want = fence_expected()
                m = (obs["sr"][:arm["grid"]] == want) if want else None
                if m is None:
                    return ("wrong_value" if moved else "ok"), sem, okind, None, None, "NO_ORACLE"
                return ("ok" if m else "wrong_value"), sem, okind, m, \
                       (m == ((sem or {}).get("expect") == "correct")), \
                       ("ORDER_OK" if m else "ORDER_BROKEN")
            # structural-partition / baseline-equality fields
            exp = (sem or {}).get("expect")
            if obs.get("cleared"):
                return "silent_zero", sem, okind, False, (exp in ("no_store", "differs")), \
                       "STORE_SUPPRESSED"
            if exp in ("store", "baseline"):
                return ("ok" if not moved else "wrong_value"), sem, okind, (not moved), \
                       (not moved), ("BASELINE_EQ" if not moved else "MOVED")
            if exp in ("no_store", "differs"):
                return ("ok" if moved else "wrong_value"), sem, okind, moved, moved, \
                       ("MOVED" if moved else "BASELINE_EQ")
            return ("wrong_value" if moved else "ok"), sem, okind, None, None, \
                   ("MOVED" if moved else "BASELINE_EQ")

        def fence_expected():
            if arm["arm"] in ("fen_at", "fen_syn"):
                even = sum(1 for i in range(arm["grid"]) if (i % exec_width) % 2 == 0)
                odd = arm["grid"] - even
                return [even * 1000 + odd * 2] * arm["grid"]
            if arm["arm"] == "fen_rel":
                return [sum(0x1234 + i for i in range(8)) + 1] * arm["grid"]
            return None

        def moved_of(outcome, obs):
            """None ONLY for non-observations.  Everything else is a comparison
            against a baseline that ran cleanly, so a suppressed draw, a fault, a
            hang or an unwritten read-back are all CHANGES."""
            if outcome in ("measurement_failed", "invalid_run"):
                return None
            if obs is None:
                return True
            return not obs_equal(obs, base_obs)

        def tokenize_anchor(block):
            """EXP-0169's lesson: a swept byte can change WHICH INSTRUCTION the
            bytes tokenize as, and then the 'movement' is the sweep encoding
            something else.  Recorded on EVERY case."""
            buf = bytearray(bytes.fromhex(hx))
            buf[off:off + len(block)] = block
            try:
                rec, ln = ISA.decode_one(bytes(buf), off)
                return rec["mnemonic"], ln
            except Exception as e:                             # noqa: BLE001
                return "UNDECODABLE:%s" % str(e)[:60], None

        def ledger(spath, requested_field, requested_value, requested_block):
            """GATE A (RE_EXPERIMENT_PROCESS_CORRECTIONS section 3): the bytes that were
            REQUESTED are not evidence -- the bytes that were DISPATCHED are.  Read them
            back out of the file the runner was handed, decode them independently with the
            pinned tokenizer, and assert
                requested field value == value decoded from actual dispatched bytes
            before any hardware conclusion.  A symmetric assemble/disassemble round trip
            is only a tokenizer test and is NOT this gate; this is what would have caught
            DEF-0166, where the assembler could not clear a requested bit."""
            with open(spath, "rb") as fh:
                blob = fh.read()
            actual = blob[abs_off:abs_off + ilen]
            phash = hashlib.sha256(blob).hexdigest()[:32]
            dec_val, dec_instr, dec_len = None, None, None
            try:
                ctx = bytearray(bytes.fromhex(hx))
                ctx[off:off + ilen] = actual
                rec_a, dec_len = ISA.decode_one(bytes(ctx), off)
                dec_instr = rec_a["mnemonic"]
                dec_val = rec_a["fields"].get(requested_field)
            except Exception as e:                             # noqa: BLE001
                dec_instr = "UNDECODABLE:%s" % str(e)[:60]
            okk = (actual == requested_block)
            return {"requested_value": requested_value,
                    "requested_bytes": requested_block.hex(),
                    "actual_bytes": actual.hex(),
                    "actual_decoded_instr": dec_instr,
                    "actual_decoded_len": dec_len,
                    "actual_decoded_value": dec_val,
                    "bytes_identical": okk,
                    "ledger_ok": bool(okk and (dec_val == requested_value
                                               if requested_value is not None and
                                               dec_val is not None else okk)),
                    "program_sha256_32": phash,
                    "instr_offset_in_main": off,
                    "abs_offset_in_archive": abs_off,
                    "db_sha256_32": PINNED["db.json"][1][:32],
                    "harness_sha256_32": HARNESS_SHA}

        def record(kind, field, value, block, note="", cof=None, **extra):
            tok_instr, tok_len = tokenize_anchor(block)
            sp = next_splice_path()
            splice(archive, sp, abs_off, block)
            led = ledger(sp, field if field in fieldsdesc else None, value, block)
            obs, raw, nres, attempts = run_case(sp)
            outcome, orc, okind, sem_ok, match, cls = classify(field, value, obs, raw, cof)
            rec = {"kind": kind, "arm": arm["arm"], "carrier": arm["arm"],
                   "stage": arm["stage"], "instr": arm["instr"], "field": field,
                   "value": value, "cofactor": cof, "bytes": block.hex(),
                   "observed": obs, "oracle": orc, "oracle_kind": okind,
                   "oracle_hit": sem_ok, "match": match,
                   "outcome": outcome, "class": cls,
                   "tok_instr": tok_instr, "tok_len": tok_len,
                   "tok_same_instr": (tok_instr == arm["instr"] and tok_len == ilen),
                   "sent_ok": (None if obs is None else
                               {k: obs.get(k) for k in ("sent", "poison", "cov")}),
                   "moved": moved_of(outcome, obs),
                   "victim": (str(raw.get("error", ""))[:200]
                              if outcome not in ("ok", "silent_zero", "wrong_value") else ""),
                   "own_fault": OWN_FAULT in str(raw.get("error", "")),
                   "attempts": attempts, "restarts": nres,
                   "raw_lines": (raw.get("raw") if outcome == "measurement_failed" else None),
                   "ledger": led, "ledger_ok": led["ledger_ok"],
                   "note": note}
            rec.update(extra)
            emit(rec)
            if outcome == "hang":
                hangs_total[0] += 1
            return rec

        # --------------------------------------------------- controls --------
        ctrl = SP.CONTROLS[arm["instr"]]
        for (nm, fname, alt, why) in ctrl["ladder"]:
            f = fieldsdesc.get(fname)
            if f is None:
                emit({"kind": "ladder", "arm": arm["arm"], "instr": arm["instr"],
                      "field": "__ladder_" + nm, "outcome": "undecodable",
                      "note": "field absent from the resolved descriptor"})
                continue
            cur = get_bits(blk0, f["start"], f["width"])
            v = alt if (alt is not None and alt != cur) else (cur + 1) % (1 << f["width"])
            record("ladder", "__ladder_" + nm, v,
                   set_bits(blk0, f["start"], f["width"], v), note=why)

        for (pf, pv, pwhy) in ctrl["power_probe"]:
            f = fieldsdesc.get(pf)
            if f is None:
                continue
            record("power_probe", "__power_" + pf, pv,
                   set_bits(blk0, f["start"], f["width"], pv), note=pwhy)
            break
        else:
            emit({"kind": "power_probe_absent", "arm": arm["arm"], "instr": arm["instr"],
                  "candidates": [x[0] for x in ctrl["power_probe"]],
                  "note": "no pre-registered power-probe field exists on the resolved "
                          "descriptor; the litmus was NOT run"})

        for probe in arm.get("probe_other", []):
            pocc, phow, _pl = occurrences(hx, probe["mnemonic"])
            if not pocc:
                emit({"kind": "power_probe_absent", "arm": arm["arm"],
                      "instr": arm["instr"], "candidates": [probe["mnemonic"]],
                      "note": "probe_other target %s not present in this program"
                              % probe["mnemonic"]})
                continue
            pdesc = next(d for d in ISA.DB if d["mnemonic"] == probe["mnemonic"])
            poff = pocc[0]
            pblk = bytes.fromhex(hx)[poff:poff + pdesc["length"]]
            pf = next(f for f in pdesc["fields"] if f["name"] == probe["field"])
            pnew = set_bits(pblk, pf["start"], pf["width"], probe["value"])
            psp = next_splice_path()
            splice(archive, psp, base + poff, pnew)
            pobs, praw, pn, patt = run_case(psp)
            emit({"kind": "power_probe", "arm": arm["arm"], "instr": arm["instr"],
                  "field": "__probe_%s_%s" % (probe["mnemonic"], probe["field"]),
                  "value": probe["value"], "bytes": pnew.hex(), "observed": pobs,
                  "oracle": None, "oracle_kind": "detection_power", "match": None,
                  "outcome": ("ok" if pobs is not None else "fault"),
                  "moved": (None if pobs is None and praw.get("status") in
                            ("MALFORMED", "RUNNER_EXCEPTION") else
                            (True if pobs is None else not obs_equal(pobs, base_obs))),
                  "note": probe["why"], "probe_offset": poff,
                  "probe_baseline_hex": pblk.hex()})

        sf, sv, swhy = ctrl["sensitivity"]
        sb = bytearray(blk0)
        if sf == "byte0_bit2":
            sb[0] &= ~0x04
        elif sf == "byte0":
            sb[0] = sv
        elif sf == "byte1":
            sb[1] = sv
        elif sf == "byte2":
            sb[2] = sv
        record("sensitivity", "__sens_" + sf, sv, bytes(sb), note=swhy)

        # ----------------------------------------------------- sweeps --------
        ndone = 0
        stop = False
        for fname in ruled:
            if wantf and fname not in wantf:
                continue
            f = fieldsdesc[fname]
            start, width = f["start"], f["width"]
            mode, vals = SP.field_values(arm["instr"], fname, start, width)
            if width > 8:
                nb = (width + 7) // 8
                cur = get_bits(blk0, start, width)
                plan = []
                for k in range(nb):
                    for v in range(256):
                        wv = (cur & ~(0xFF << (8 * k))) | (v << (8 * k))
                        plan.append((wv, "byte%d=%d" % (k, v)))
                plan += [(v, "structured") for v in vals]
            else:
                plan = [(v, mode) for v in vals]
            ndisp = len(plan)
            ndistinct = len({set_bits(blk0, start, width, v).hex() for (v, _t) in plan})
            if args.order == "reverse":
                plan = list(reversed(plan))
            for (v, tag) in plan:
                if args.max_cases and ndone >= args.max_cases:
                    stop = True
                    break
                record("case", fname, v, set_bits(blk0, start, width, v), note=tag,
                       start=start, width=width, encodable_range=(1 << width),
                       values_dispatched=ndisp, distinct_bytes=ndistinct)
                ndone += 1
                if recovery["consecutive_unrecovered"] >= MAX_CONSECUTIVE_UNRECOVERED:
                    emit({"kind": "arm_stopped_unrecoverable", "arm": arm["arm"],
                          "field": fname, "recovery": recovery,
                          "reason": "the UNSPLICED carrier failed to run after %d "
                                    "consecutive full recovery cycles.  Harness/device "
                                    "health stop, NOT a hang budget."
                                    % MAX_CONSECUTIVE_UNRECOVERED})
                    stop = True
                    break
                if hangs_total[0] >= hp["global_circuit_breaker"]:
                    emit({"kind": "run_stopped", "arm": arm["arm"], "field": fname,
                          "reason": "global circuit breaker %d hangs"
                                    % hp["global_circuit_breaker"]})
                    stop = True
                    break
            if stop:
                break

        # ------------------------- the joint form x sr_sel map ---------------
        if arm["instr"] == "get_sr" and not stop and not wantf:
            ff = fieldsdesc["form"]
            fs = fieldsdesc["sr_sel"]
            for fv in (0, 1):
                for sel in arm["sr_set"]:
                    blk = set_bits(blk0, ff["start"], ff["width"], fv)
                    blk = set_bits(blk, fs["start"], fs["width"], sel)
                    record("case", "__form_x_srsel", fv * 1000 + sel, blk,
                           note="form=%d sr_sel=%d" % (fv, sel), cof=sel,
                           form_value=fv, sr_sel=sel)

        emit({"kind": "arm_done", "arm": arm["arm"], "instr": arm["instr"],
              "seconds": round(time.time() - t_arm, 1), "recovery": recovery,
              "hangs_total": hangs_total[0]})
        with open(os.path.join(EXP, "PROGRESS.md"), "a") as pf2:
            pf2.write("- %s run=%s arm=%s done in %.1fs (hangs_total=%d)\n" % (
                time.strftime("%Y-%m-%dT%H:%M:%S"), args.run_id, arm["arm"],
                time.time() - t_arm, hangs_total[0]))
        try:
            runner.close()
        except Exception:                                      # noqa: BLE001
            try:
                runner._kill()
            except Exception:                                  # noqa: BLE001
                pass

    json.dump(resolution, open(os.path.join(outdir, "00_arm_resolution.json"), "w"),
              indent=1, sort_keys=True)
    json.dump({"records": counter["n"], "hangs": hangs_total[0]},
              open(os.path.join(outdir, "02_summary.json"), "w"), indent=1)
    sweep.close()
    payloads.close()
    print("run %s: %d records, %d hangs" % (args.run_id, counter["n"], hangs_total[0]))


if __name__ == "__main__":
    main()
