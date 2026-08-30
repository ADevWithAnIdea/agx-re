#!/usr/bin/env python3
"""EXP-0142 texture/imageblock field sweep driver.

Implements the FROZEN PRE_REGISTRATION.md / CAPTURE_CONTRACT.json matrix over the
three carriers, with every FIELD-SWEEP-PROTOCOL section 7/8 control:
unique splice-archive path per request, poisoned readback, integrity sentinel on a
path independent of the instruction under test, no `fault` from one observation
(majority of 3), periodic baseline re-validation, ERRDOM capture with
InnocentVictim segregation, per-area and per-run hang caps.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. Splices only bytes the Metal runtime compiled
from OUR OWN MSL, executed through the public Metal API. No Apple binary is
introspected.

  python3 analysis/sweep.py --run RUN_ID [--gate | --full] [--arms A1,A2,B,C]
"""
import argparse, json, os, struct, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP  = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))
sys.path.insert(0, os.path.join(EXP, "harness"))
FROZEN = os.path.join(EXP, "work", "frozen")

from texrunner import TexRunner            # noqa: E402
from renderrunner import RenderRunner      # noqa: E402

CONTRACT = json.load(open(os.path.join(EXP, "CAPTURE_CONTRACT.json")))
TIMEOUT       = CONTRACT["safety"]["request_timeout_s"]
BASE_EVERY    = CONTRACT["safety"]["baseline_revalidate_every_cases"]
BASE_RETRIES  = CONTRACT["safety"]["baseline_retries"]
HANGS_AREA    = CONTRACT["safety"]["hangs_stop_area"]
HANGS_RUN     = CONTRACT["safety"]["hangs_stop_run"]
SENTINEL      = 12345.0


class Stop(Exception):
    pass


# ----------------------------------------------------------------- arms

class Arm:
    """One carrier + one runner + one observation/classification model."""
    name = "?"

    def __init__(self, outdir):
        self.outdir = outdir
        self.spldir = os.path.join(FROZEN, "spl")
        os.makedirs(self.spldir, exist_ok=True)
        self.seq = 0
        self.base_bytes = open(self.archive, "rb").read()
        self.main = self.base_bytes[self.abs_off:self.abs_off + self.length]
        self.runner = self._mk_runner()
        self.baseline = None

    def splice_path(self):
        self.seq += 1
        return os.path.join(self.spldir, "%s_%06d.bin" % (self.name, self.seq))

    def run_case(self, splices):
        """splices = [(main_offset, value)]; returns (status, obs, errdom, err)."""
        b = bytearray(self.base_bytes)
        for off, val in splices:
            b[self.abs_off + off] = val
        p = self.splice_path()
        with open(p, "wb") as f:
            f.write(bytes(b))
        try:
            return self._dispatch(p)
        finally:
            try:
                os.unlink(p)
            except OSError:
                pass

    def instr_hex(self, off, length, splices):
        b = bytearray(self.main[off:off + length])
        for o, v in splices:
            if off <= o < off + length:
                b[o - off] = v
        return bytes(b).hex()


class ArmCompute(Arm):
    def _mk_runner(self):
        return TexRunner(source=self.source, function=self.function,
                         exe=os.path.join(FROZEN, "texpersist"),
                         samp_w=16, samp_h=16, write_w=8, write_h=8)


class ArmA(ArmCompute):
    """tex_sample / tex_coord_setup: 8 independent samples -> out[0..31], sentinel out[32]."""
    name = "A"
    archive  = os.path.join(FROZEN, "cA_sample8.bin")
    source   = os.path.join(EXP, "kernels", "tex_sample8.metal")
    function = "k_sample"
    abs_off, length = 10480, 524
    infile   = os.path.join(FROZEN, "inA.bin")

    def _dispatch(self, path):
        r = self.runner.request(archive=path, grid=1, tg=1,
                                ins={0: self.infile}, outs={1: 132}, timeout=TIMEOUT)
        if r["status"] != "OK":
            return r["status"], None, r.get("errdom"), r.get("error")
        return "OK", list(struct.unpack("<33f", r["outs"][1])), None, None

    def oracle(self):
        o = []
        for j in range(8):
            o += [101.0 * j + 1.0, 0.0, 0.0, 1.0]
        o.append(SENTINEL)
        return o

    def classify(self, obs):
        if obs is None:
            return "fault", {}
        if obs[32] != SENTINEL:
            return "invalid", {"sentinel": obs[32]}
        ch = [j for j in range(8) if obs[4 * j:4 * j + 4] != self.baseline[4 * j:4 * j + 4]]
        if not ch:
            return "ok", {}
        det = {"changed_quads": ch,
               "values": {str(j): [round(x, 4) for x in obs[4 * j:4 * j + 4]] for j in ch}}
        if all(obs[4 * j:4 * j + 4] == [0.0, 0.0, 0.0, 0.0] for j in ch):
            return "silent_zero", det
        return "wrong_value", det


class ArmB(ArmCompute):
    """tex_write: 3 writes into an 8x8 RGBA32F target reset to (-1,-2,-3,-4)."""
    name = "B"
    archive  = os.path.join(FROZEN, "cB_write3.bin")
    source   = os.path.join(EXP, "kernels", "tex_write3.metal")
    function = "k_write"
    abs_off, length = 8608, 356
    infile   = os.path.join(FROZEN, "inB.bin")
    RESET = (-1.0, -2.0, -3.0, -4.0)

    def _dispatch(self, path):
        r = self.runner.request(archive=path, grid=1, tg=1,
                                ins={0: self.infile}, outs={1: 4}, texread=True,
                                timeout=TIMEOUT)
        if r["status"] != "OK":
            return r["status"], None, r.get("errdom"), r.get("error")
        sent = struct.unpack("<f", r["outs"][1])[0]
        tex = struct.unpack("<%df" % (8 * 8 * 4), r["tex"])
        return "OK", {"sent": sent, "tex": [tuple(tex[i * 4:i * 4 + 4]) for i in range(64)]}, None, None

    def oracle(self):
        t = [self.RESET] * 64
        t[0 * 8 + 1] = (11.0, 22.0, 33.0, 44.0)
        t[2 * 8 + 3] = (55.0, 66.0, 77.0, 88.0)
        t[4 * 8 + 5] = (99.0, 110.0, 121.0, 132.0)
        return {"sent": SENTINEL, "tex": t}

    def classify(self, obs):
        if obs is None:
            return "fault", {}
        if obs["sent"] != SENTINEL:
            return "invalid", {"sentinel": obs["sent"]}
        bt = self.baseline["tex"]
        ch = [i for i in range(64) if obs["tex"][i] != bt[i]]
        if not ch:
            return "ok", {}
        det = {"changed_texels": [[i % 8, i // 8] for i in ch],
               "values": {str(i): [round(x, 4) for x in obs["tex"][i]] for i in ch[:12]}}
        if all(obs["tex"][i] == self.RESET for i in ch):
            return "silent_zero", det          # the write stopped happening
        return "wrong_value", det


class ArmC(Arm):
    """tex_deriv: 4x4 RGBA32F render target, every pixel = (A,B,C,D+S) = (1,2,4,11)."""
    name = "C"
    archive = os.path.join(FROZEN, "cC_deriv.bin")
    source  = os.path.join(EXP, "kernels", "frag_deriv.metal")
    abs_off, length = 16048, 136
    infile  = os.path.join(FROZEN, "inC.bin")

    def _mk_runner(self):
        return RenderRunner(source=self.source, vertex="v_main", fragment="f_main",
                            exe=os.path.join(FROZEN, "renderpersist"), width=4, height=4)

    def _dispatch(self, path):
        r = self.runner.request(archive=path, ins={0: self.infile}, timeout=TIMEOUT)
        if r["status"] != "OK":
            return r["status"], None, r.get("errdom"), r.get("error")
        px = struct.unpack("<64f", r["pixels"])
        return "OK", [tuple(px[i * 4:i * 4 + 4]) for i in range(16)], None, None

    def oracle(self):
        return [(1.0, 2.0, 4.0, 11.0)] * 16

    def classify(self, obs):
        if obs is None:
            return "fault", {}
        if obs == self.baseline:
            return "ok", {}
        uniform = len(set(obs)) == 1
        det = {"px0": [round(x, 4) for x in obs[0]], "uniform": uniform}
        if not uniform:
            det["px5"] = [round(x, 4) for x in obs[5]]
            det["px15"] = [round(x, 4) for x in obs[15]]
        if obs[0] == (-9.0, -9.0, -9.0, -9.0):
            det["note"] = "clear colour: the fragment never wrote"
            return "wrong_value", det
        # the alpha channel is dfdy(v)+S: 11 both live, 8 sentinel-ALU dead,
        # 3 derivative dead, 0 nothing ran.
        changed = [k for k in range(4) if obs[0][k] != self.baseline[0][k]]
        det["changed_channels"] = changed
        if all(obs[0][k] == 0.0 for k in changed):
            return "silent_zero", det
        return "wrong_value", det


ARMS = {"A": ArmA, "B": ArmB, "C": ArmC}


# ----------------------------------------------------------------- sweep engine

class Sweep:
    def __init__(self, run_id):
        self.run_id = run_id
        self.outdir = os.path.join(EXP, "raw", run_id)
        os.makedirs(self.outdir, exist_ok=True)
        self.fp = open(os.path.join(self.outdir, "sweep.jsonl"), "a")
        self.log = open(os.path.join(self.outdir, "run.log"), "a")
        self.ncases = 0
        self.hangs_run = 0
        self.innocent = 0
        self.t0 = time.time()

    def say(self, s):
        line = "[%7.1fs] %s" % (time.time() - self.t0, s)
        print(line, flush=True)
        self.log.write(line + "\n")
        self.log.flush()

    def emit(self, rec):
        self.fp.write(json.dumps(rec) + "\n")
        self.fp.flush()
        os.fsync(self.fp.fileno())
        self.ncases += 1

    def baseline(self, arm, tag="baseline"):
        for attempt in range(BASE_RETRIES):
            st, obs, errdom, err = arm.run_case([])
            if st == "OK":
                return obs
            self.say("  %s %s attempt %d: %s %s" % (arm.name, tag, attempt, st, errdom))
            time.sleep(0.4 * (attempt + 1))
        return None

    def establish(self, arm):
        obs = self.baseline(arm, "establish")
        if obs is None:
            raise Stop("arm %s baseline unobtainable" % arm.name)
        arm.baseline = obs
        orc = arm.oracle()
        ok = (obs == orc) if not isinstance(obs, dict) else (
            obs["sent"] == orc["sent"] and obs["tex"] == orc["tex"])
        self.say("arm %s baseline == host oracle: %s" % (arm.name, ok))
        self.emit({"instr": "_baseline", "field": "-", "value": -1, "bytes": "",
                   "observed": {"matches_host_oracle": bool(ok)},
                   "oracle": {"source": "host-computed from our own MSL + known texture contents"},
                   "match": bool(ok), "outcome": "ok" if ok else "wrong_value",
                   "carrier": arm.name, "note": "baseline established for run " + self.run_id})
        if not ok:
            raise Stop("arm %s baseline does NOT match the host oracle" % arm.name)

    def revalidate(self, arm):
        obs = self.baseline(arm, "revalidate")
        if obs is None:
            raise Stop("CASCADE: arm %s baseline failed %d consecutive attempts" %
                       (arm.name, BASE_RETRIES))
        if obs != arm.baseline:
            raise Stop("CASCADE: arm %s baseline DRIFTED mid-run" % arm.name)

    def one(self, arm, instr, field, off, ilen, boff, val, note=""):
        """Run one spliced case, with the majority-of-3 fault rule."""
        splices = [(off + boff, val)]
        st, obs, errdom, err = arm.run_case(splices)
        outcome, det = (arm.classify(obs) if st == "OK" else
                        ("hang" if st == "HANG" else "fault", {}))
        confirms = None
        if outcome in ("fault", "hang"):
            # FIELD-SWEEP-PROTOCOL 7.1: never a property of the field from one observation.
            votes = [outcome]
            details = [{"status": st, "errdom": errdom}]
            for _ in range(2):
                st2, obs2, errdom2, err2 = arm.run_case(splices)
                o2, d2 = (arm.classify(obs2) if st2 == "OK" else
                          ("hang" if st2 == "HANG" else "fault", {}))
                votes.append(o2)
                details.append({"status": st2, "errdom": errdom2})
                if o2 not in ("fault", "hang"):
                    obs, det = obs2, d2
            maj = max(set(votes), key=votes.count)
            confirms = {"votes": votes, "detail": details}
            if maj not in ("fault", "hang"):
                outcome, det = arm.classify(obs) if obs is not None else (maj, {})
            else:
                outcome = maj
        if errdom and "MTLCommandBufferError" in errdom and errdom.strip().endswith(" 4"):
            self.innocent += 1
            outcome = "innocent_victim"          # segregated, not attributed to the field
        rec = {"instr": instr, "field": field, "value": val,
               "bytes": arm.instr_hex(off, ilen, splices),
               "observed": det, "oracle": {"expect": "baseline (host-computed)"},
               "match": outcome == "ok", "outcome": outcome,
               "carrier": arm.name, "note": note}
        if errdom:
            rec["errdom"] = errdom
        if confirms:
            rec["confirm"] = confirms
        rec["instance_off"] = off
        rec["byte"] = boff
        self.emit(rec)
        return outcome

    def sweep_bytes(self, arm, instr, off, ilen, plan, fieldmap, label):
        """plan = {byte_offset: [values]}"""
        area_hangs = {}
        for boff in sorted(plan):
            vals = plan[boff]
            field = fieldmap.get(boff, "?byte%d" % boff)
            area_hangs[boff] = 0
            for v in vals:
                if self.ncases % BASE_EVERY == 0 and self.ncases:
                    self.revalidate(arm)
                oc = self.one(arm, instr, field, off, ilen, boff, v, note=label)
                if oc == "hang":
                    area_hangs[boff] += 1
                    self.hangs_run += 1
                    self.say("  HANG %s %s byte+%d val=0x%02x (area %d, run %d)" %
                             (instr, label, boff, v, area_hangs[boff], self.hangs_run))
                    if self.hangs_run >= HANGS_RUN:
                        raise Stop("run hang cap %d reached" % HANGS_RUN)
                    if area_hangs[boff] >= HANGS_AREA:
                        self.say("  AREA STOPPED: %s %s byte+%d after %d hangs" %
                                 (instr, label, boff, area_hangs[boff]))
                        self.emit({"instr": instr, "field": field, "value": -1, "bytes": "",
                                   "observed": {}, "oracle": {}, "match": False,
                                   "outcome": "area_stopped", "carrier": arm.name,
                                   "note": "%s: stopped after %d genuine hangs (protocol 8)" %
                                           (label, area_hangs[boff])})
                        break
            self.say("  done %s %s byte+%d (%d values, %d cases total)" %
                     (instr, label, boff, len(vals), self.ncases))


# ----------------------------------------------------------------- field maps

FMAP_SAMPLE = {0: "kind|chain", 1: "comp_flags|b1hi", 2: "?b2_unmodelled",
               3: "result_desc", 4: "result_sel", 5: "coord", 6: "variant",
               7: "extra_coord", 8: "tex_slot", 9: "samp_slot_offset", 10: "mode",
               11: "lod_present", 12: "tex_type", 13: "samp_extra"}
FMAP_COORD  = {0: "dst_lo", 1: "b1", 2: "subop", 3: "srcA", 4: "form",
               5: "b5", 6: "b6", 7: "idx", 8: "b8", 9: "b9"}
FMAP_WRITE  = {0: "opcode", 1: "coord_pack", 2: "amode", 3: "seq_idx", 4: "layer_reg",
               5: "coord_regs[0]", 6: "coord_regs[1]", 7: "coord_regs[2]", 8: "rsv8",
               9: "coord_dim", 10: "rsv10", 11: "rsv11", 12: "wop", 13: "data_desc",
               14: "data_desc_hi", 15: "rsv15"}
FMAP_DERIV  = {0: "opcode", 1: "b1", 2: "dstsrc[0]", 3: "dstsrc[1]", 4: "dstsrc[2]",
               5: "src_comp", 6: "axis", 7: "tail[0]", 8: "tail[1]", 9: "tail[2]"}

SAMPLE_OFFS = CONTRACT["instruction_offsets"]["tex_sample"]
COORD_OFFS  = CONTRACT["instruction_offsets"]["tex_coord_setup"]
WRITE_OFFS  = CONTRACT["instruction_offsets"]["tex_write"]
DERIV_OFFS  = CONTRACT["instruction_offsets"]["tex_deriv"]

BYTE0_SAMPLE = sorted(set([(hi << 4) | 0x5 for hi in range(16)] +
                          [0x00 | lo for lo in range(16)]))
BYTE0_COORD  = [(hi << 4) | 0xb for hi in range(16)]


def plan_full(bytes_full, byte0_values=None):
    p = {b: list(range(256)) for b in bytes_full}
    if byte0_values is not None:
        p[0] = list(byte0_values)
    return p


# ----------------------------------------------------------------- run01 gate

def gate(sw):
    report = {"run": sw.run_id, "controls": {}, "probe": {}}

    # ---- arm A ----
    a = ArmA(sw.outdir)
    sw.say("arm A device = %s" % a.runner.device)
    sw.establish(a)

    # NC2 determinism
    reps = []
    for _ in range(8):
        st, obs, ed, er = a.run_case([])
        reps.append(obs if st == "OK" else None)
    det = all(r == a.baseline for r in reps)
    report["controls"]["NC2"] = {"predict": "8 unspliced re-runs identical", "pass": bool(det)}
    sw.say("NC2 determinism (8 re-runs identical): %s" % det)
    sw.emit({"instr": "tex_sample", "field": "-", "value": -1, "bytes": "",
             "observed": {"identical": bool(det)}, "oracle": {"expect": "identical"},
             "match": bool(det), "outcome": "ok" if det else "wrong_value",
             "carrier": "A", "note": "NC2 determinism control"})

    # PC1: tex_slot high nibble on bundle 7
    o7 = SAMPLE_OFFS[7]
    st, obs, ed, er = a.run_case([(o7 + 8, 0x10)])
    oc, d = (a.classify(obs) if st == "OK" else ("fault", {}))
    report["controls"]["PC1"] = {"status": st, "outcome": oc, "detail": d}
    sw.say("PC1 tex_slot 0x00->0x10 on bundle7: %s %s %s" % (st, oc, d))
    sw.emit({"instr": "tex_sample", "field": "tex_slot", "value": 0x10,
             "bytes": a.instr_hex(o7, 14, [(o7 + 8, 0x10)]), "observed": d,
             "oracle": {"expect": "q_of_bundle7 silently zeroes, others unchanged"},
             "match": oc == "silent_zero", "outcome": oc, "carrier": "A",
             "note": "PC1 positive control"})

    # PC2: variant on bundle 7
    st, obs, ed, er = a.run_case([(o7 + 6, 0x17)])
    oc2, d2 = (a.classify(obs) if st == "OK" else ("fault", {}))
    report["controls"]["PC2"] = {"status": st, "outcome": oc2, "detail": d2}
    sw.say("PC2 variant 0x09->0x17 on bundle7: %s %s %s" % (st, oc2, d2))
    sw.emit({"instr": "tex_sample", "field": "variant", "value": 0x17,
             "bytes": a.instr_hex(o7, 14, [(o7 + 6, 0x17)]), "observed": d2,
             "oracle": {"expect": "q_of_bundle7 changes, others unchanged"},
             "match": oc2 != "ok", "outcome": oc2, "carrier": "A",
             "note": "PC2 positive control"})

    # bundle -> output-quad mapping, from tex_slot silent-zeroing each bundle in turn
    b2q = {}
    for bi, off in enumerate(SAMPLE_OFFS):
        st, obs, ed, er = a.run_case([(off + 8, 0x10)])
        if st != "OK" or obs is None:
            b2q[bi] = None
            continue
        ch = [j for j in range(8) if obs[4 * j:4 * j + 4] != a.baseline[4 * j:4 * j + 4]]
        b2q[bi] = ch
    report["probe"]["bundle_to_quad"] = b2q
    sw.say("bundle->quad map (tex_slot=0x10 zeroes): %s" % b2q)

    # tex_coord_setup -> sample mapping: zero each setup's srcA and see which quad moves
    c2q = {}
    for ci, off in enumerate(COORD_OFFS):
        cur = a.main[off + 7]
        v = 0x00 if cur != 0x00 else 0xff
        st, obs, ed, er = a.run_case([(off + 7, v)])
        if st != "OK" or obs is None:
            c2q[ci] = ("STATUS", st)
            continue
        ch = [j for j in range(8) if obs[4 * j:4 * j + 4] != a.baseline[4 * j:4 * j + 4]]
        c2q[ci] = {"off": off, "idx_base": cur, "idx_new": v, "changed_quads": ch,
                   "vals": {str(j): round(obs[4 * j], 3) for j in ch}}
    report["probe"]["coordsetup_to_quad"] = c2q
    sw.say("coord_setup->quad map: %s" % json.dumps(c2q))

    # rate probe: 512 cases on bundle 7 byte+5 and byte+4
    t = time.time()
    for boff in (4, 5):
        for v in range(256):
            sw.one(a, "tex_sample", FMAP_SAMPLE[boff], o7, 14, boff, v, note="run01 rate probe")
    dt = time.time() - t
    report["probe"]["rate_ms_per_case"] = round(1000 * dt / 512.0, 2)
    sw.say("rate probe: 512 cases in %.1fs = %.2f ms/case" % (dt, 1000 * dt / 512.0))
    a.runner.close()

    # ---- arm C ----
    c = ArmC(sw.outdir)
    sw.say("arm C device = %s" % c.runner.device)
    sw.establish(c)
    d0 = DERIV_OFFS[0]
    for cid, boff, val, pred in (("PC3", 6, 0x90, "red 1.0 -> 2.0"),
                                 ("PC4", 5, 0x08, "red 1.0 -> 4.0")):
        st, obs, ed, er = c.run_case([(d0 + boff, val)])
        oc, d = (c.classify(obs) if st == "OK" else ("fault", {}))
        red = obs[0][0] if st == "OK" else None
        report["controls"][cid] = {"status": st, "outcome": oc, "red": red,
                                   "predict": pred, "px0": d.get("px0")}
        sw.say("%s byte+%d=0x%02x: %s red=%s (%s)" % (cid, boff, val, st, red, pred))
        sw.emit({"instr": "tex_deriv", "field": FMAP_DERIV[boff], "value": val,
                 "bytes": c.instr_hex(d0, 10, [(d0 + boff, val)]), "observed": d,
                 "oracle": {"expect": pred}, "match": oc != "ok", "outcome": oc,
                 "carrier": "C", "note": cid + " positive control"})
    c.runner.close()

    # ---- arm B ----
    b = ArmB(sw.outdir)
    sw.establish(b)
    w1 = WRITE_OFFS[1]
    st, obs, ed, er = b.run_case([(w1 + 12, 0x00)])
    oc, d = (b.classify(obs) if st == "OK" else ("fault", {}))
    report["controls"]["PC5"] = {"status": st, "outcome": oc, "detail": d}
    sw.say("PC5 wop 0x89->0x00 on write1: %s %s %s" % (st, oc, d))
    sw.emit({"instr": "tex_write", "field": "wop", "value": 0,
             "bytes": b.instr_hex(w1, 16, [(w1 + 12, 0)]), "observed": d,
             "oracle": {"expect": "texel(3,2) unwritten or moved; (1,0),(5,4) unchanged"},
             "match": oc != "ok", "outcome": oc, "carrier": "B", "note": "PC5 positive control"})
    nc1 = []
    for v in range(256):
        oc = sw.one(b, "tex_write", "rsv15", w1, 16, 15, v, note="NC1 inert control")
        nc1.append(oc)
    report["controls"]["NC1"] = {"predict": "inert for all 256",
                                 "pass": all(o == "ok" for o in nc1),
                                 "outcomes": {k: nc1.count(k) for k in set(nc1)}}
    sw.say("NC1 rsv15 inert for all 256: %s" % report["controls"]["NC1"])
    b.runner.close()

    with open(os.path.join(sw.outdir, "gate_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    sw.say("gate report written")
    return report


# ----------------------------------------------------------------- run02 full

def full(sw, arms, coord_pick):
    if "A1" in arms or "A2" in arms:
        a = ArmA(sw.outdir)
        sw.establish(a)
        if "A1" in arms:
            for bi in (7, 0):
                sw.say("=== A1 tex_sample bundle %d @0x%x ===" % (bi, SAMPLE_OFFS[bi]))
                sw.sweep_bytes(a, "tex_sample", SAMPLE_OFFS[bi], 14,
                               plan_full(range(1, 14), BYTE0_SAMPLE), FMAP_SAMPLE,
                               "bundle%d" % bi)
        if "A2" in arms:
            for ci in coord_pick:
                sw.say("=== A2 tex_coord_setup #%d @0x%x ===" % (ci, COORD_OFFS[ci]))
                sw.sweep_bytes(a, "tex_coord_setup", COORD_OFFS[ci], 10,
                               plan_full(range(1, 10), BYTE0_COORD), FMAP_COORD,
                               "setup%d" % ci)
        a.runner.close()
    if "B" in arms:
        b = ArmB(sw.outdir)
        sw.establish(b)
        for wi in (1, 2):
            sw.say("=== B tex_write #%d @0x%x ===" % (wi, WRITE_OFFS[wi]))
            sw.sweep_bytes(b, "tex_write", WRITE_OFFS[wi], 16,
                           plan_full(range(1, 16)), FMAP_WRITE, "write%d" % wi)
        b.runner.close()
    if "C" in arms:
        c = ArmC(sw.outdir)
        sw.establish(c)
        for di in (0, 2):
            sw.say("=== C tex_deriv #%d @0x%x ===" % (di, DERIV_OFFS[di]))
            sw.sweep_bytes(c, "tex_deriv", DERIV_OFFS[di], 10,
                           plan_full(range(1, 10)), FMAP_DERIV, "deriv%d" % di)
        c.runner.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--arms", default="A1,A2,B,C")
    ap.add_argument("--coord-pick", default="0,10")
    args = ap.parse_args()
    sw = Sweep(args.run)
    sw.say("run %s starting (gate=%s full=%s arms=%s)" %
           (args.run, args.gate, args.full, args.arms))
    try:
        if args.gate:
            gate(sw)
        if args.full:
            full(sw, set(args.arms.split(",")),
                 [int(x) for x in args.coord_pick.split(",")])
        sw.say("RUN COMPLETE: %d cases, %d hangs, %d innocent-victims" %
               (sw.ncases, sw.hangs_run, sw.innocent))
    except Stop as e:
        sw.say("RUN STOPPED: %s (after %d cases)" % (e, sw.ncases))
        sw.emit({"instr": "_stop", "field": "-", "value": -1, "bytes": "",
                 "observed": {}, "oracle": {}, "match": False, "outcome": "fault",
                 "carrier": "-", "note": str(e)})
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
