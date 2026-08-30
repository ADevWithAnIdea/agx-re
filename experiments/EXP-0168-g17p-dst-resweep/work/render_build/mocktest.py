#!/usr/bin/env python3
"""OFFLINE mock test of the EXP-0168 render arm. NO DEVICE, NO GPU, NO Metal.

Lives in work/ because it is build scaffolding, not evidence. It replaces
build_carrier / stage_bytes / RenderRunner with fakes that:
  * synthesize a plausible compiled program containing real, isadb-decodable
    vtx_out_pos / vary_store / pixel_order / frag_color_pack encodings;
  * synthesize read-back surfaces that satisfy each carrier's HOST oracle
    exactly when unspliced, and perturb them for chosen splices;
so the whole census -> freeze -> run pipeline, the validity rule, the ladders,
the falsifiers, the byte-mate, the hang budget and the JSONL schema all execute.
"""
import hashlib
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(EXP, "harness"))

import rendercarriers as RC
import renderarms as RA
import renderrun as RR

POISON4 = b"\xef\xbe\xad\xde"

# ---- synthesized "compiled" programs --------------------------------------
# Real encodings, taken from committed evidence in this repository:
VTX_OUT_POS = bytes.fromhex("0b002600400000" + "04")     # slot=0x04, dst=0
VARY_STORE  = bytes.fromhex("57025400e0004a54")           # byte0=0x57, bit9 set
PIX_ACQ     = bytes.fromhex("071454500600")               # EXP-0162 acquire
PIX_REL     = bytes.fromhex("070454d00600")               # EXP-0162 release
FCP         = bytes.fromhex("9745540002800050 04c2".replace(" ", ""))[:10]
NOP         = bytes.fromhex("0e00")


def _prog(parts):
    return b"".join(parts)


def fake_program(name, stage):
    fam = RC.CARRIERS[name]["family"]
    if stage == "vertex":
        if fam == "vtx":
            return _prog([VTX_OUT_POS, VARY_STORE, VTX_OUT_POS, VARY_STORE])
        return _prog([VTX_OUT_POS, VARY_STORE])
    if fam == "rog":
        return _prog([PIX_ACQ, PIX_REL])
    if fam == "fcp":
        n = 2 * RC.CARRIERS[name]["rt_count"]
        if RC.CARRIERS[name]["color_format"] == 125:
            n = 0                          # r_fcpf: no pack needed at all
        return _prog([FCP] * n) or _prog([NOP])
    return _prog([NOP])


def check_decodes():
    bad = []
    for blob, want in ((VTX_OUT_POS, "vtx_out_pos"), (VARY_STORE, "vary_store"),
                       (PIX_ACQ, "pixel_order"), (PIX_REL, "pixel_order"),
                       (FCP, "frag_color_pack")):
        try:
            d, L = RR.isadb.decode_one(blob, 0)
        except ValueError as e:
            bad.append("%s: undecodable (%s)" % (want, e))
            continue
        if d["mnemonic"] != want:
            bad.append("%s: decodes as %s" % (want, d["mnemonic"]))
        if L != len(blob):
            bad.append("%s: length %d != %d" % (want, L, len(blob)))
    return bad


# ---- fake device ----------------------------------------------------------
class FakeRunner:
    """Speaks RenderRunner's interface. Produces oracle-exact surfaces for the
    unspliced program, and a deterministic perturbation otherwise."""

    def __init__(self, name):
        self.name = name
        self.cfg = RC.CARRIERS[name]
        self.restarts = 0
        self.restarts_at = []
        self.target_line = "TARGET FakeDevice registryID=0 instances=1"
        self.calls = 0

    def close(self):
        pass

    def render(self, splices, timeout=15.0, bufs=None, instances=None, at=None):
        self.calls += 1
        alt = bool(bufs)
        exp = RC.oracle(self.name, alt=alt)
        surf = {}
        cfg = self.cfg
        fmt, w, h = cfg["color_format"], cfg["width"], cfg["height"]
        bpp = RC.BYTES_PER_PIXEL[fmt]
        # deterministic perturbation keyed on the spliced bytes
        key = hashlib.sha256(("|".join("%s=%s" % s for s in splices)).encode()).digest()
        perturb = bool(splices) and (key[0] & 1)
        for rt in range(cfg["rt_count"]):
            vals = list(exp["PIX%d" % rt])
            if perturb:
                vals = [0 for _ in vals] if (key[1] & 1) else \
                       [(v + 1) if isinstance(v, int) else RC.f32(v + 1.0) for v in vals]
            if fmt == 125:
                px = struct.pack("<4f", *[float(v) for v in vals])
            elif fmt == 115:
                px = struct.pack("<4H", *[int(v) & 0xFFFF for v in vals])
            else:
                px = bytes(int(v) & 0xFF for v in vals)
            surf["PIX%d" % rt] = px * (w * h)
        if cfg.get("tex_write"):
            tv = list(exp.get("TEXW", [0, 0, 0, 0]))
            if perturb:
                tv = [RC.f32(v + 1.0) for v in tv]
            surf["TEXW"] = struct.pack("<4f", *[float(v) for v in tv])
        if cfg.get("tex_write_uint"):
            uv = list(exp.get("TEXWU", [0, 0, 0, 0]))
            if perturb:
                uv = [(v + 1) & 0xFFFFFFFF for v in uv]
            surf["TEXWU"] = struct.pack("<4I", *uv)
        if cfg.get("out_buf"):
            ob = exp["OUTBUF"]
            raw = b""
            for v in ob:
                raw += POISON4 if v is None else struct.pack("<f", float(v))
            surf["OUTBUF"] = raw
        # one deliberate contaminated dispatch: STATUS OK, everything poison
        if self.calls == 7:
            surf = {k: POISON4 * (len(v) // 4) for k, v in surf.items()}
        # one deliberate InnocentVictim, and one deliberate hang
        if self.calls == 11:
            return {"status": "CMDBUF_ERROR", "surf": {}, "missing": [], "ovr": [],
                    "error": "kIOGPUCommandBufferCallbackErrorInnocentVictim x",
                    "errdom": "MTLCommandBufferErrorDomain 6"}
        if self.calls == 23:
            return {"status": "CMDBUF_ERROR", "surf": {}, "missing": [], "ovr": [],
                    "error": "kIOGPUCommandBufferCallbackErrorHang caused GPU Hang",
                    "errdom": "MTLCommandBufferErrorDomain 3"}
        out = {"status": "OK", "surf": surf, "missing": [], "sentinel": "OK %d" % len(splices),
               "ovr": (["0 applied 16"] if bufs else [])}
        return out


def main():
    bad = check_decodes()
    if bad:
        print("MOCK ENCODINGS UNUSABLE:\n  " + "\n  ".join(bad))
        return 2

    progs = {}

    def fake_build(name, cfg):
        return os.path.join(EXP, "work", "r_%s.bin" % name)

    def fake_stage(arch, stage):
        name = os.path.basename(arch)[2:-4]
        progs.setdefault((name, stage), fake_program(name, stage))
        return 0x1000, progs[(name, stage)]

    RR.build_carrier = fake_build
    RR.stage_bytes = fake_stage
    RR.sha256_file = lambda p: "0" * 64
    RR.RenderRunner = lambda *a, **k: FakeRunner(
        [n for n in RC.CARRIERS if os.path.basename(a[2]) == "r_%s.bin" % n][0])
    RR.time.sleep = lambda s: None

    class A:
        pass
    a = A()
    a.mode = "census"; a.run_id = "mock"; a.carriers = ""; a.priority = 3
    a.census = ""; a.arms = ""; a.mnem = ""; a.fields = ""
    a.max_occ = 4; a.ladder_max_occ = 4; a.deadline_s = 0.0
    a.smoke = True; a.skip_hazard = False; a.bytemate = True; a.skip_powerless = False
    p = RR.do_census(a)
    a.mode = "freeze"; a.census = p
    RR.do_freeze(a)
    a.mode = "run"; a.run_id = "mockrun"
    outdir = os.path.join(EXP, "work", "smoke_mockrun")
    if os.path.isdir(outdir):
        for f in os.listdir(outdir):
            os.unlink(os.path.join(outdir, f))
    RR.do_run(a)

    # ---- schema + invariant checks on what was produced --------------------
    need = {"instr", "field", "value", "bytes", "observed", "outcome", "match",
            "carrier", "note", "role", "arm", "carrier_dim", "byte_index",
            "fstart", "fwidth", "validity", "rt_ok", "target", "run_id"}
    roles = {}
    fails = []
    n = 0
    for ln in open(os.path.join(outdir, "sweep.jsonl")):
        r = json.loads(ln)
        n += 1
        miss = need - set(r)
        if miss:
            fails.append("record %d missing keys %s" % (n, sorted(miss)))
        if r["role"] not in ("sweep", "ladder", "bytemate", "falsifier", "baseline"):
            fails.append("record %d bad role %r" % (n, r["role"]))
        roles[r["role"]] = roles.get(r["role"], 0) + 1
        if r["validity"] not in ("valid", "invalid_poison", "invalid_sentinel",
                                 "invalid_victim"):
            fails.append("record %d bad validity %r" % (n, r["validity"]))
        # THE RULE: a non-valid case must never be an accepted inert observation
        if r["validity"] != "valid" and r.get("accepted") and \
                r["outcome"] in ("ok", "inert", "silent_zero"):
            fails.append("record %d: invalid case accepted as %r" % (n, r["outcome"]))
    man = json.load(open(os.path.join(outdir, "05_run_manifest.json")))
    inp = json.load(open(os.path.join(outdir, "00_inputs.json")))
    print("\n--- mock run: %d records, roles %s" % (n, roles))
    print("--- arms in manifest: %d, refused %d, hangs %d"
          % (len(man["arms"]), len(man["refused"]), man["hangs"]))
    for k, v in sorted(man["arms"].items()):
        print("    %-32s ladder_pass=%-5s fields=%s falsifiers=%s"
              % (k, v["ladder_pass"], {f: d["moved"] for f, d in v["fields"].items()},
                 {f: d.get("held") for f, d in v["falsifiers"].items()}))
    for role in ("baseline", "ladder", "falsifier", "bytemate", "sweep"):
        if role not in roles:
            fails.append("no %s records were emitted at all" % role)
    if not any(a for a in man["arms"] if a.startswith("pixel_order")):
        fails.append("no pixel_order arm was produced")
    if not any(a for a in man["arms"] if a.startswith("vtx_out_pos")):
        fails.append("no vtx_out_pos arm was produced")
    if not any(a for a in man["arms"] if a.startswith("frag_color_pack")):
        fails.append("no frag_color_pack arm was produced")
    print("\nMOCK TEST: %s" % ("PASS" if not fails else
                               "FAIL\n  " + "\n  ".join(fails[:40])))
    return 0 if not fails else 1


sys.exit(main())
