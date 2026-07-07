#!/usr/bin/env python3
# rt1b.py -- RT-1b red-team splice/run driver (INDEPENDENT harness).
#
# Different from RT-1a's agxtest.py (per-run fork of agxrun) and from RT-1a/FIX's
# persistrun.py (long-lived agxrun_persist). This driver:
#   * compiles OUR OWN MSL -> archive (shdump),
#   * locates instructions INSIDE _agc.main by tokenizing with the ISA DB
#     (isadb) -- not by hardcoded byte offsets, so the location method is itself
#     independent,
#   * splices bytes and runs each config through my own ONE-SHOT rt1b_run
#     (fresh MTLDevice per dispatch: no memoization surface),
#   * decodes outputs.
#
# CLEAN-ROOM: every byte inspected/spliced is the compiled form of OUR OWN MSL.
# Runs ON THE DEVICE. Needs: shdump, rt1b_run, agxparse.py, isadb.py in cwd.

import os, sys, struct, subprocess, importlib.util, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))

def _load(mod, path):
    spec = importlib.util.spec_from_file_location(mod, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

agxparse = _load("agxparse", os.path.join(HERE, "agxparse.py"))
isadb    = _load("isadb",    os.path.join(HERE, "isadb.py"))

def u32(vals):  return b"".join(struct.pack("<I", v & 0xFFFFFFFF) for v in vals)
def i32(vals):  return b"".join(struct.pack("<i", v) for v in vals)
def f32(vals):  return b"".join(struct.pack("<f", float(v)) for v in vals)
def du32(b):    return [struct.unpack_from("<I", b, i)[0] for i in range(0, len(b), 4)]
def di32(b):    return [struct.unpack_from("<i", b, i)[0] for i in range(0, len(b), 4)]
def df32(b):    return [struct.unpack_from("<f", b, i)[0] for i in range(0, len(b), 4)]

class Harness:
    def __init__(self, source, function="k", fast_math=False, workdir="."):
        self.source = source; self.function = function
        self.fast_math = fast_math; self.workdir = workdir
        os.makedirs(workdir, exist_ok=True)
        tag = hashlib.sha256(open(source, "rb").read() + function.encode()
                             + str(fast_math).encode()).hexdigest()[:10]
        self.archive = os.path.join(workdir, f"arch_{tag}.bin")
        if not os.path.exists(self.archive):
            cmd = ["./shdump", "-o", self.archive, "-f", function]
            if not fast_math: cmd.append("--no-fast-math")
            cmd.append(source)
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(self.archive):
                raise RuntimeError(f"shdump failed: {r.stderr}")
        self.base = open(self.archive, "rb").read()
        loc = agxparse.locate_region(self.base, "_agc.main")
        if loc is None: raise RuntimeError("no _agc.main")
        self.main_off, self.main_len = loc
        self.main = self.base[self.main_off:self.main_off + self.main_len]

    def tokens(self):
        """Resync-tolerant tokenization: returns list of dicts with
        off (within main), length, byte0, mnemonic (or None), hex."""
        out = []; off = 0; b = self.main
        while off < len(b):
            try:
                rec, ln = isadb.decode_one(b, off)
            except Exception:
                rec, ln = None, None
            if ln is None or ln == 0:
                # resync: emit a 2-byte unknown parcel and continue
                out.append({"off": off, "length": 2, "byte0": b[off],
                            "mnemonic": None, "hex": b[off:off+2].hex(), "unknown": True})
                off += 2; continue
            out.append({"off": off, "length": ln, "byte0": b[off],
                        "mnemonic": rec.get("mnemonic") if rec else None,
                        "op": rec.get("op_mnemonic") if rec else None,
                        "fields": rec.get("fields") if rec else {},
                        "hex": b[off:off+ln].hex(),
                        "unknown": bool(rec.get("error")) if rec else True})
            off += ln
        return out

    def find(self, byte0=None, mnemonic=None, pred=None, nth=0):
        """Find the nth instruction matching byte0 / mnemonic / predicate.
        Returns its offset within _agc.main, or None."""
        hits = []
        for t in self.tokens():
            if byte0 is not None and t["byte0"] != byte0: continue
            if mnemonic is not None and t.get("mnemonic") != mnemonic: continue
            if pred is not None and not pred(t): continue
            hits.append(t)
        return hits[nth]["off"] if nth < len(hits) else None

    def run(self, splices=None, grid=1, tg=1, ins=None, outs=None,
            tgmem=None, timeout=20.0):
        """splices: list of (off_within_main, bytes|hexstr). ins:{idx:bytes}.
        outs:{idx:nbytes}. tgmem:{idx:nbytes}. Returns dict."""
        buf = bytearray(self.base)
        applied = []
        for off, val in (splices or []):
            vb = bytes.fromhex(val) if isinstance(val, str) else bytes(val)
            ao = self.main_off + off
            old = bytes(buf[ao:ao+len(vb)])
            buf[ao:ao+len(vb)] = vb
            applied.append((off, old.hex(), vb.hex()))
        spath = os.path.join(self.workdir, "rt1b_spliced.bin")
        open(spath, "wb").write(buf)
        cmd = ["./rt1b_run", "--archive", spath, "--function", self.function,
               "--grid", str(grid), "--tg", str(tg)]
        for idx, data in (ins or {}).items():
            p = os.path.join(self.workdir, f"in_{idx}.bin")
            open(p, "wb").write(data); cmd += ["--in", f"{idx}:{p}"]
        for idx, nb in (outs or {}).items():
            cmd += ["--out", f"{idx}:{nb}"]
        for idx, nb in (tgmem or {}).items():
            cmd += ["--tgmem", f"{idx}:{nb}"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {"status": "HANG", "outs": {}, "gputime": None,
                    "splices": applied, "error": f"timeout {timeout}s (GPU wedged)"}
        resp = {"status": "UNKNOWN", "outs": {}, "gputime": None,
                "splices": applied, "error": None}
        for ln in r.stdout.splitlines():
            if ln.startswith("STATUS "): resp["status"] = ln.split(None, 1)[1]
            elif ln.startswith("GPUTIME_NS "): resp["gputime"] = int(ln.split(None, 1)[1])
            elif ln.startswith("OUT "):
                _, idx, hx = ln.split(None, 2); resp["outs"][int(idx)] = bytes.fromhex(hx)
            elif ln.startswith("ERROR "): resp["error"] = ln.split(None, 1)[1]
        if resp["status"] == "UNKNOWN" and r.stderr.strip():
            resp["error"] = r.stderr.strip()[:300]
        return resp
