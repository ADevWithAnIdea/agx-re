#!/usr/bin/env python3
"""EXP-0179 arm S -- the INDEPENDENT SECOND METHOD.

The four `call` bytes are mutated inside the REAL, compiler-emitted call in our
own compiled `kernels/census/c_frame.metal` (`k_chain` -> `nl_mid` -> two leaves),
instead of inside a program we assembled. Same fields, completely different
program: different register allocation, different surrounding code, a BACKWARD
displacement, the compiler's own bracket, and a non-leaf callee.

WHY IT IS REPORTED SEPARATELY. Its call bytes come from a compiled shader, so it
can never count toward the ">= 2 carriers" bar for a GENERATED result
(PRE_REGISTRATION section 4). It is a cross-check on the RULES the generated arms
produced, and nothing more.

THE ORACLE IS HOST-COMPUTED AND HAS NOTHING TO DO WITH THE GPU:
`k_chain(a, b) = (a + b) + (a * b)`. With a = 3.0, b = 5.0 that is exactly 23.0f,
representable, so the check is exact. The output buffer is poisoned with
0xDEADBEEF first, so "wrote 23", "wrote something else" and "never ran" are three
distinguishable outcomes rather than two.

  python3 harness/splice.py --run splice_<id> [--fields b3,b5,b6,tail]

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Only our own MSL was compiled and only the
bytes produced from it are spliced. No Apple binary is disassembled.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
import platform
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H   # noqa: E402  (pins db.json/isadb.py, fail-closed)
import sweeprun as S      # noqa: E402
import isadb              # noqa: E402

SRC = EXP / "kernels" / "census" / "c_frame.metal"
FUNC = "k_chain"
A_VAL, B_VAL = 3.0, 5.0
EXPECT = (A_VAL + B_VAL) + (A_VAL * B_VAL)      # 23.0, exactly representable
REQ_TIMEOUT = 8.0
# byte index within the 14-byte call -> field name (db.json geometry)
BYTE_OF = {"b3": 3, "b5": 5, "b6": 6, "tail": 13}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class FrameSplice(object):
    def __init__(self, workdir):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.base_path = self.workdir / "base_kchain.bin"
        r = subprocess.run([str(S.SHDUMP), "-o", str(self.base_path), "-f", FUNC,
                            "--no-fast-math", str(SRC)],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        if r.returncode != 0:
            raise RuntimeError("shdump failed: %s" % r.stderr.decode()[-600:])
        self.basebuf = self.base_path.read_bytes()
        self.region_off, self.region_len = S.agxparse.locate_region(self.basebuf,
                                                                    "_agc.main")
        self.main = self.basebuf[self.region_off:self.region_off + self.region_len]
        cons = None
        for i in isadb.DB:
            if i["mnemonic"] == "call":
                cons = [(s // 8, v) for (s, w, v) in i["match"]]
        span = max(o for o, _ in cons) + 1
        self.sites = [p for p in range(len(self.main) - span + 1)
                      if all(self.main[p + o] == v for o, v in cons)]
        # DEF-0178-1: the leak-free subclass, same as every other runner here.
        self.runner = S.RUNNER(
            source=str(SRC), function=FUNC, fast_math=False,
            agxrun_persist=str(S.AGXRUN_PERSIST))
        self.device = self.runner.device
        self.spl = self.workdir / ("spl_%d.bin" % os.getpid())
        self.a = self.workdir / "a.bin"
        self.b = self.workdir / "b.bin"
        self.poison = self.workdir / "poison.bin"
        self.a.write_bytes(struct.pack("<f", A_VAL))
        self.b.write_bytes(struct.pack("<f", B_VAL))
        self.poison.write_bytes(struct.pack("<I", H.POISON))
        self.dispatches = 0

    def run(self, mutated_main, timeout=REQ_TIMEOUT):
        buf = bytearray(self.basebuf)
        buf[self.region_off:self.region_off + self.region_len] = mutated_main
        self.spl.write_bytes(bytes(buf))
        resp = self.runner.request(archive=str(self.spl), grid=1, tg=1,
                                   ins={0: str(self.a), 1: str(self.b),
                                        2: str(self.poison)},
                                   outs={2: 4}, timeout=timeout)
        self.dispatches += 1
        raw = resp["outs"].get(2, b"")
        word = struct.unpack_from("<I", raw)[0] if len(raw) >= 4 else None
        val = struct.unpack_from("<f", raw)[0] if len(raw) >= 4 else None
        return resp, word, val

    def close(self):
        try:
            self.runner.close()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--fields", default="b3,b5,b6,tail")
    ap.add_argument("--order", default="forward", choices=("forward", "reverse"))
    args = ap.parse_args()

    outdir = EXP / "raw" / args.run
    outdir.mkdir(parents=True, exist_ok=True)
    c = FrameSplice(EXP / "work" / ("splice_%s" % args.run))
    log = S.Log(outdir / "sweep.jsonl")
    (outdir / "00_env.json").write_text(json.dumps({
        "run": args.run, "arm": "S/splice", "order": args.order,
        "host": platform.node(), "platform": platform.platform(),
        "device": c.device, "source": str(SRC.relative_to(EXP)), "function": FUNC,
        "region_off": c.region_off, "region_len": c.region_len,
        "call_sites_in_main": c.sites,
        "call_bytes_at_sites": [c.main[p:p + 14].hex() for p in c.sites],
        "a": A_VAL, "b": B_VAL, "expect": EXPECT,
        "db_sha256": sha(H.ISA_DIR / "db.json"),
        "isadb_sha256": sha(H.ISA_DIR / "isadb.py"),
        "splice_sha256": sha(HERE / "splice.py"),
        "source_sha256": sha(SRC),
        "NOTE": ("INDEPENDENT SECOND METHOD. These call bytes come from a compiled "
                 "shader, so this arm NEVER counts toward the >=2-carrier bar for a "
                 "generated result."),
        "t_start": time.time()}, indent=1, sort_keys=True))
    print("call sites in _agc.main:", c.sites, "device:", c.device)

    # baseline, unmutated
    resp, word, val = c.run(c.main)
    log.write({"arm": "S", "kind": "baseline", "instr": "call", "field": None,
               "value": None, "site": None, "bytes": None,
               "observed": {"word": word, "float": val},
               "oracle": EXPECT, "match": (val == EXPECT),
               "outcome": ("ok" if val == EXPECT else "wrong_value"),
               "status": resp["status"], "os_class": S.os_class(resp.get("error")),
               "error": (resp.get("error") or "")[:300]})
    print("baseline:", resp["status"], val, "expect", EXPECT)

    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    cases = [(f, site, v) for f in fields for site in c.sites for v in range(256)]
    if args.order == "reverse":
        cases = list(reversed(cases))
    t0 = time.time()
    for (f, site, v) in cases:
        idx = BYTE_OF[f]
        mm = bytearray(c.main)
        mm[site + idx] = v
        resp, word, val = c.run(bytes(mm))
        if resp["status"] != "OK":
            outcome = "hang" if resp["status"] == "HANG" else "fault"
        elif word == H.POISON:
            outcome = "wrong_value"     # never ran / never stored
        elif val == EXPECT:
            outcome = "ok"
        elif word == 0:
            outcome = "silent_zero"
        else:
            outcome = "wrong_value"
        start, width = None, 8
        for i in isadb.DB:
            if i["mnemonic"] == "call":
                for fl in i["fields"]:
                    if fl["name"] == f:
                        start, width = fl["start"], fl["width"]
        log.write({"arm": "S", "kind": "case", "instr": "call", "field": f,
                   "value": v, "site": site, "bytes": bytes(mm[site:site + 14]).hex(),
                   "observed": {"word": word, "float": val},
                   "oracle": EXPECT, "match": (val == EXPECT), "outcome": outcome,
                   "status": resp["status"], "validity": ("valid" if not S.is_victim(
                       resp.get("error")) else "invalid_victim"),
                   "os_class": S.os_class(resp.get("error")),
                   "error": (resp.get("error") or "")[:300],
                   "start": start, "width": width, "encodable_range": 256,
                   "carrier": "S_kchain_compiled", "plan": "n/a",
                   "poisoned": (word == H.POISON),
                   "rt_ok": H.round_trips(bytes(mm[site:site + 14])),
                   "note": "REAL compiler-emitted call, mutated in place"})
    (outdir / "03_summary.json").write_text(json.dumps(
        {"n": log.n, "elapsed_s": round(time.time() - t0, 3),
         "dispatches": c.dispatches, "sites": c.sites}, indent=1))
    log.close()
    c.close()
    print("DONE", args.run, log.n, "records", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
