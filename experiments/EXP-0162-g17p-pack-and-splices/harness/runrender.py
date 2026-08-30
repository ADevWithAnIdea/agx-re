#!/usr/bin/env python3
"""EXP-0162 render capture driver (G17P) -- Arm D (`pixel_order`) and Arm E
(`vary_store`).

Both defects block emittability and neither can be adjudicated from the corpus:
`pixel_order` has ZERO corpus firings, and the 0x57 length question needs the
hardware to say which byte selects the form. This driver splices bytes into the
compiled form of OUR OWN MSL (kernels/render_probe.metal) and reads back the
rendered pixel and the raster-order texel.

  python3 harness/runrender.py --run-id g17p_YYYYMMDD_runNN --arm rog

DETECTION POWER FIRST: each arm runs its pre-registered control before any sweep,
and an arm whose control fails promotes nothing (FIELD-SWEEP-PROTOCOL section 3.2;
EXP-0129 lost an arm exactly here).

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is introspected.
"""
import argparse, collections, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = Path(os.environ.get("AGXRE_ROOT", str(EXP.parents[1])))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "shdump"))
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import agxparse                 # noqa: E402
import isadb                    # noqa: E402
import renderplan as RP         # noqa: E402
from rsdrv import RenderRunner  # noqa: E402

BIN = EXP / "work" / "bin"
KERNEL = EXP / "kernels" / "render_probe.metal"
TOL = 1e-6


def build(vs, fs, workdir):
    out = workdir / ("r_%s.bin" % fs)
    r = subprocess.run([str(BIN / "shdump2"), "-o", str(out), "--render",
                        "--vertex", vs, "--fragment", fs, "--color-format", "125",
                        "--nrt", "1", "--samples", "1", "--no-fast-math", str(KERNEL)],
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError("build %s/%s failed: %s" % (vs, fs, r.stderr[-400:]))
    return out


class Splicer:
    def __init__(self, archive, stage, workdir, tag):
        self.arch = Path(archive).read_bytes()
        loc = agxparse.locate_region(self.arch, "_agc.main", stage=stage)
        if loc is None:
            raise RuntimeError("no _agc.main in stage %s" % stage)
        self.off, self.len = loc
        _, pieces = agxparse.extract_agx(self.arch, stage=stage)
        self.main = pieces["_agc.main"]
        self.dir = workdir / ("sp_" + tag)
        self.dir.mkdir(parents=True, exist_ok=True)
        for f in self.dir.glob("*.bin"):
            f.unlink()
        self.n = 0

    def path(self, overrides):
        buf = bytearray(self.arch)
        for o, v in overrides.items():
            buf[self.off + o] = v & 0xFF
        self.n += 1
        p = self.dir / ("%07d.bin" % self.n)
        p.write_bytes(bytes(buf))
        stale = self.dir / ("%07d.bin" % (self.n - 48))
        if stale.exists():
            try:
                stale.unlink()
            except OSError:
                pass
        return str(p)


def close(a, b, tol=TOL):
    if a is None or b is None:
        return False
    return all(abs(x - y) <= tol * max(1.0, abs(y)) for x, y in zip(a, b))


def fault_class(err):
    if not err:
        return ""
    e = err.lower()
    if "innocent" in e or "victim" in e:
        return "InnocentVictim"
    if "ignored" in e:
        return "IgnoredPriorErrors"
    if "hang" in e:
        return "Hang"
    if "address fault" in e or "page fault" in e:
        return "AddressFault"
    if "no response" in e:
        return "Watchdog"
    return err[:60]


class Arm:
    """One render arm: a splicer, a request template, and a host oracle."""

    def __init__(self, runner, spl, req, oracle_fn, clearpix):
        self.r, self.spl, self.req, self.oracle_fn = runner, spl, req, oracle_fn
        self.clearpix = clearpix
        self.hangs = 0

    def one(self, overrides, timeout=12.0):
        req = dict(self.req)
        req["archive"] = self.spl.path(overrides)
        req["id"] = "c%d" % self.spl.n
        resp = self.r.request(req, timeout=timeout)
        return resp

    def classify(self, resp):
        if resp.get("status") != "OK":
            fc = fault_class(resp.get("error"))
            if fc in ("InnocentVictim", "IgnoredPriorErrors"):
                return "victim", fc, None, None
            if fc in ("Hang", "Watchdog"):
                return "hang", fc, None, None
            return "fault", fc, None, None
        px = resp["pixels"][0]
        tx = resp.get("tex")
        return None, "", px, tx

    def measure(self, overrides, reps=3, budget=24):
        """EXP-0147's rule: after a sibling's fault, RETRY IN PLACE first. Its
        earlier recovery loop restarted the child immediately and made the fresh
        child's first request the next victim, producing 138 consecutive false
        `invalid_run`s. Only a run of consecutive victims justifies a restart."""
        votes, discarded, n, streak = {}, 0, 0, 0
        recs = []
        while n < reps and discarded < budget:
            resp = self.one(overrides)
            oc, fc, px, tx = self.classify(resp)
            if oc == "victim":
                discarded += 1
                streak += 1
                if streak >= 4:
                    self.r.restart()
                    streak = 0
                    time.sleep(0.25)
                continue
            streak = 0
            if oc is None:
                oc = self.oracle_fn(px, tx)
            key = (oc, tuple(round(v, 6) for v in (px or [])),
                   tuple(round(v, 6) for v in (tx or [])))
            votes[key] = votes.get(key, 0) + 1
            recs.append({"outcome": oc, "fault": fc})
            n += 1
            if oc in ("fault", "hang"):
                self.hangs += (oc == "hang")
                self.r.restart()
                streak = 0
        if not votes:
            return "invalid_run", None, None, "", 0, discarded
        best = max(votes.items(), key=lambda kv: kv[1])
        if best[1] == 1 and n >= 3:
            while n < 5 and discarded < budget + 8:
                resp = self.one(overrides)
                oc, fc, px, tx = self.classify(resp)
                if oc == "victim":
                    discarded += 1
                    streak += 1
                    if streak >= 4:
                        self.r.restart()
                        streak = 0
                    continue
                streak = 0
                if oc is None:
                    oc = self.oracle_fn(px, tx)
                key = (oc, tuple(round(v, 6) for v in (px or [])),
                       tuple(round(v, 6) for v in (tx or [])))
                votes[key] = votes.get(key, 0) + 1
                n += 1
            best = max(votes.items(), key=lambda kv: kv[1])
        (oc, px, tx) = best[0]
        fc = next((r["fault"] for r in recs if r["outcome"] == oc), "")
        return oc, list(px) or None, list(tx) or None, fc, best[1], discarded


# ------------------------------------------------------------------ oracles
def rog_oracle(px, tx):
    good = RP.rog_oracle()
    if close(tx, good["tex"]) and close(px, good["pixel"]):
        return "ok"
    if close(px, RP.ROG_CLEAR) and close(tx, [0, 0, 0, 0]):
        return "no_draw"
    if tx and all(abs(v) < 1e-9 for v in tx):
        return "silent_zero"
    for kept in range(1, RP.ROG_N):
        lost = RP.rog_oracle_lost(kept)
        if close(tx, lost["tex"]) and close(px, lost["pixel"]):
            return "lost_%d_of_%d" % (RP.ROG_N - kept, RP.ROG_N)
    return "wrong_value"


def kill_oracle(px, tx):
    if close(px, RP.KILL_COLOR):
        return "ok"                 # fragment survived, colour written
    if close(px, RP.KILL_CLEAR):
        return "killed"             # fragment killed -> clear colour
    return "wrong_value"


def vary_oracle(px, tx):
    if px is None:
        return "wrong_value"
    if close(px[1:], RP.VARY_ORACLE_GBA):
        return "ok"
    if close(px, RP.VARY_CLEAR):
        return "no_draw"
    return "wrong_value"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--arm", required=True, choices=["rog", "kill", "vary"])
    ap.add_argument("--out-root", default="raw")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    outdir = EXP / a.out_root / ("%s__%s" % (a.run_id, a.arm))
    if outdir.exists():
        sys.exit("run id already exists (never reuse or overwrite): %s" % outdir)
    outdir.mkdir(parents=True)
    workdir = EXP / "work" / ("rrun_%s_%s" % (a.run_id, a.arm))
    workdir.mkdir(parents=True, exist_ok=True)

    f = open(outdir / "sweep.jsonl", "w")

    def rec(d):
        d.setdefault("target", "G17P")
        d.setdefault("run_id", a.run_id)
        d.setdefault("arm", a.arm)
        f.write(json.dumps(d) + "\n")
        f.flush()
        os.fsync(f.fileno())

    if a.arm == "rog":
        vs, fs, stage = "v_rog", "f_rog", "fragment"
        req = {"vs": vs, "fs": fs, "w": 1, "h": 1, "nrt": 1, "samples": 1,
               "clear": [RP.ROG_CLEAR], "fbuf": RP.ROG_SRC, "vbuf": [0, 0, 0, 0],
               "tex": [0, 0, 0, 0], "instances": RP.ROG_N}
        oracle = rog_oracle
        anchors = {k: (v["off"], bytes.fromhex(v["bytes"]))
                   for k, v in RP.ROG_MEMBERS.items()}
    elif a.arm == "kill":
        vs, fs, stage = "v_kill", "f_kill", "fragment"
        req = {"vs": vs, "fs": fs, "w": 1, "h": 1, "nrt": 1, "samples": 1,
               "clear": [RP.KILL_CLEAR], "fbuf": [1.0, 0, 0, 0],
               "vbuf": [0, 0, 0, 0], "instances": 1}
        oracle = kill_oracle
        anchors = {"kill": (RP.KILL_OFF, bytes.fromhex(RP.KILL_BYTES))}
    else:
        vs, fs, stage = "v_vary", "f_vary", "vertex"
        req = {"vs": vs, "fs": fs, "w": 1, "h": 1, "nrt": 1, "samples": 1,
               "clear": [RP.VARY_CLEAR], "fbuf": [0, 0, 0, 0],
               "vbuf": RP.VARY_U, "instances": 1}
        oracle = vary_oracle
        anchors = {}

    arch = build(vs, fs, workdir)
    spl = Splicer(arch, stage, workdir, a.arm)

    # locate the 0x57 stores in the vertex main at run time (their offsets are a
    # property of the compile, and the contract records what was found)
    if a.arm == "vary":
        offs = [i for i in range(len(spl.main) - 7)
                if spl.main[i] == 0x57 and spl.main[i + 2] in (0x54, 0x55, 0x56)
                and spl.main[i + 5] in (0x40, 0x41)]
        # keep the ones the pilot showed, de-duplicated by stride 8
        keep, last = [], -99
        for o in offs:
            if o - last >= 8:
                keep.append(o)
                last = o
        anchors = {("vary_slot_%02x" % spl.main[o + 4]): (o, bytes(spl.main[o:o + 8]))
                   for o in keep}

    for k, (o, b) in anchors.items():
        got = bytes(spl.main[o:o + len(b)])
        if got != b:
            rec({"kind": "abort", "note": "ANCHOR MISMATCH %s want %s got %s"
                 % (k, b.hex(), got.hex())})
            sys.exit("anchor mismatch %s" % k)

    rec({"kind": "meta", "stage": stage, "vs": vs, "fs": fs,
         "main_len": len(spl.main), "main": spl.main.hex(),
         "anchors": {k: [o, b.hex()] for k, (o, b) in anchors.items()},
         "request_template": req,
         "oracle": (RP.rog_oracle() if a.arm == "rog" else
                    {"survive": RP.KILL_COLOR, "killed": RP.KILL_CLEAR}
                    if a.arm == "kill" else {"gba": RP.VARY_ORACLE_GBA})})

    runner = RenderRunner(source=str(KERNEL), exe=str(BIN / "rendersweep"))
    arm = Arm(runner, spl, req, oracle, req["clear"][0])

    def baseline(tag):
        oc, px, tx, fc, votes, disc = arm.measure({})
        rec({"kind": "baseline", "tag": tag, "field": "-", "value": -1,
             "observed": {"pixel": px, "tex": tx}, "outcome": oc,
             "match": oc == "ok", "fault_class": fc, "votes": votes,
             "discarded": disc, "note": "unmutated carrier"})
        return oc == "ok"

    if not baseline("pre"):
        rec({"kind": "abort", "note": "baseline failed before any mutation"})
        f.close(); runner.close(); sys.exit("baseline failed")

    # ------------------------------------------------ detection-power controls
    controls = []
    if a.arm == "rog":
        off = RP.ROG_MEMBERS["acquire"]["off"]
        controls = [("H4a_acq_b4_01", {off + 4: 0x01}, "acquire byte+4 -> 0x01"),
                    ("H4a_rel_b4_01", {RP.ROG_MEMBERS["release"]["off"] + 4: 0x01},
                     "release byte+4 -> 0x01"),
                    ("H4a_acq_b0_00", {off: 0x00}, "acquire opcode byte -> 0x00")]
    elif a.arm == "kill":
        controls = [("H5a_b4_01", {RP.KILL_OFF + 4: 0x01}, "kill op byte+4 -> 0x01"),
                    ("H5a_mask0", "MASK0", "unspliced, mask=0 -> fragment killed")]
    else:
        for k, (o, b) in anchors.items():
            controls.append(("VS_src_zero_%s" % k, {o + 3: 0x00},
                             "zero the source register of %s" % k))
    for cid, ov, note in controls:
        if ov == "MASK0":
            saved = dict(arm.req)
            arm.req = dict(arm.req); arm.req["fbuf"] = [0.0, 0, 0, 0]
            oc, px, tx, fc, votes, disc = arm.measure({})
            arm.req = saved
        else:
            oc, px, tx, fc, votes, disc = arm.measure(ov)
        rec({"kind": "control", "field": cid, "value": -1,
             "observed": {"pixel": px, "tex": tx}, "outcome": oc,
             "match": oc == "ok", "fault_class": fc, "votes": votes,
             "discarded": disc, "note": note})

    # ------------------------------------------------ cross-form probes (Arm D)
    if a.arm == "rog":
        for name, hexs in RP.CROSS_FORMS.items():
            bs = bytes.fromhex(hexs)
            for member, m in RP.ROG_MEMBERS.items():
                ov = {m["off"] + i: bs[i] for i in range(6)}
                oc, px, tx, fc, votes, disc = arm.measure(ov)
                rec({"kind": "crossform", "field": "%s@%s" % (name, member),
                     "value": -1, "bytes": hexs,
                     "observed": {"pixel": px, "tex": tx}, "outcome": oc,
                     "match": oc == "ok", "fault_class": fc, "votes": votes,
                     "discarded": disc, "note": "whole-encoding substitution"})
            # both members at once, using the matching acquire/release variants
            if name.endswith("_acq"):
                rel = RP.CROSS_FORMS.get(name[:-4] + "_rel")
                if rel:
                    ov = {}
                    for i, bb in enumerate(bs):
                        ov[RP.ROG_MEMBERS["acquire"]["off"] + i] = bb
                    for i, bb in enumerate(bytes.fromhex(rel)):
                        ov[RP.ROG_MEMBERS["release"]["off"] + i] = bb
                    oc, px, tx, fc, votes, disc = arm.measure(ov)
                    rec({"kind": "crossform", "field": "%s@BOTH" % name[:-4],
                         "value": -1, "bytes": hexs + "/" + rel,
                         "observed": {"pixel": px, "tex": tx}, "outcome": oc,
                         "match": oc == "ok", "fault_class": fc, "votes": votes,
                         "discarded": disc, "note": "both members substituted"})

    # ------------------------------------------------ Arm E vertex-side probes
    # Targeted, on the LAST stores in the program, where a length desync runs into
    # the `stop` rather than through six more instructions. H5d: does clearing
    # byte+1 bit1 (the corpus discriminator) or byte+5 bit6 break the VS form?
    if a.arm == "vary":
        for slot in ("vary_slot_e0", "vary_slot_c0", "vary_slot_a0"):
            if slot not in anchors:
                continue
            o, b = anchors[slot]
            for cid, ov, note in [
                ("H5d_%s_b1_clear_bit1" % slot, {o + 1: b[1] & ~0x02},
                 "byte+1 bit1 CLEARED (-> the fragment form's discriminator)"),
                ("H5d_%s_b1_set_bit3"   % slot, {o + 1: b[1] | 0x08},
                 "control: byte+1 bit3 set, bit1 left SET"),
                ("H5d_%s_b5_01"         % slot, {o + 5: 0x01},
                 "byte+5 -> 0x01 (the fragment form's tag)"),
                ("H5d_%s_b5_00"         % slot, {o + 5: 0x00},
                 "byte+5 bit6 cleared"),
                ("H5d_%s_b5_42"         % slot, {o + 5: 0x42},
                 "control: byte+5 bit6 still set"),
                ("H5d_%s_b7_ff"         % slot, {o + 7: 0xFF},
                 "byte+7: the 8th byte -- live only if the op really is 8 bytes"),
                ("H5d_%s_b6_ff"         % slot, {o + 6: 0xFF},
                 "byte+6: the 7th byte -- same question"),
            ]:
                oc, px, tx, fc, votes, disc = arm.measure(ov)
                rec({"kind": "probe", "field": cid, "value": -1,
                     "observed": {"pixel": px, "tex": tx}, "outcome": oc,
                     "match": oc == "ok", "fault_class": fc, "votes": votes,
                     "discarded": disc, "note": note})

    # ------------------------------------------------ Arm E fragment probes
    if a.arm == "kill":
        probes = [
            ("H5b_b1_16",  {RP.KILL_OFF + 1: 0x16}, "byte+1 bit1 SET (VS tag)"),
            ("H5c_b1_1c",  {RP.KILL_OFF + 1: 0x1c}, "byte+1 bit1 clear (EXP-0091 null)"),
            ("H5b_b5_41",  {RP.KILL_OFF + 5: 0x41}, "byte+5 -> 0x41 (VS tag)"),
            ("H5b_b5_40",  {RP.KILL_OFF + 5: 0x40}, "byte+5 -> 0x40 (VS tag)"),
            ("H5c_b5_03",  {RP.KILL_OFF + 5: 0x03}, "byte+5 bit6 clear"),
            ("H5_next_b0", {RP.KILL_NEXT_OFF: 0x00}, "byte at +6 (next instr leader)"),
            ("H5_next_b1", {RP.KILL_NEXT_OFF + 1: 0x00}, "byte at +7"),
        ]
        for cid, ov, note in probes:
            oc, px, tx, fc, votes, disc = arm.measure(ov)
            rec({"kind": "probe", "field": cid, "value": -1,
                 "observed": {"pixel": px, "tex": tx}, "outcome": oc,
                 "match": oc == "ok", "fault_class": fc, "votes": votes,
                 "discarded": disc, "note": note})

    # ------------------------------------------------ dense byte sweeps
    sweep_bytes = {"rog": [1, 3, 4, 5], "kill": [1, 2, 3, 4, 5], "vary": [1, 2, 5]}[a.arm]
    targets = anchors if a.arm != "rog" else \
        {k: (v["off"], bytes.fromhex(v["bytes"])) for k, v in RP.ROG_MEMBERS.items()}
    if a.arm == "vary":
        # only the two slots whose channel has a host oracle, to keep the sweep bounded
        # Only the LAST two stores. Sweeping the position stores desyncs the whole
        # vertex program and hangs the GPU (run04 measured exactly that at
        # vary_slot_00 byte+1); the late stores bound the blast radius.
        targets = {k: v for k, v in anchors.items()
                   if k in ("vary_slot_c0", "vary_slot_e0")}
    cases = []
    for tname, (toff, tb) in targets.items():
        for bi in sweep_bytes:
            for val in range(256):
                cases.append((tname, toff, tb, bi, val))
    if a.limit:
        cases = cases[:a.limit]
    t0 = time.time()
    # FIELD-SWEEP-PROTOCOL section 8 says stop an ARM after two genuine hangs "in
    # one area". Here an area is one (target, swept byte): a desync in the vertex
    # stream hangs, but that says nothing about a different byte of a different
    # store, and abandoning the whole arm throws away coverage the protocol does
    # not ask us to throw away. Two hangs in one (target,byte) stops THAT byte and
    # records a marker; the arm continues.
    per_area_hangs = collections.Counter()
    stopped_areas = set()
    for i, (tname, toff, tb, bi, val) in enumerate(cases):
        area = (tname, bi)
        if area in stopped_areas:
            continue
        if arm.hangs >= 12:
            rec({"kind": "stop_arm", "note": "12 hangs total at case %d" % i})
            break
        if i and i % 100 == 0:
            if not baseline("mid%d" % i):
                rec({"kind": "cascade", "note": "baseline failed at case %d" % i})
                break
        mut = bytearray(tb)
        mut[bi] = val
        oc, px, tx, fc, votes, disc = arm.measure({toff + bi: val})
        rec({"kind": "sweep", "instr": tname, "field": "byte%d" % bi, "byte": bi,
             "value": val, "bytes": bytes(mut).hex(),
             "observed": {"pixel": px, "tex": tx}, "outcome": oc,
             "match": oc == "ok", "fault_class": fc, "votes": votes,
             "discarded": disc, "note": ""})
        if oc == "hang":
            per_area_hangs[area] += 1
            if per_area_hangs[area] >= 2:
                stopped_areas.add(area)
                rec({"kind": "stop_area", "instr": tname, "field": "byte%d" % bi,
                     "value": val,
                     "note": "2 genuine hangs in this (target,byte); remaining values "
                             "of THIS byte skipped (FIELD-SWEEP-PROTOCOL section 8)"})
    baseline("post")
    rec({"kind": "done", "cases": len(cases), "elapsed_s": round(time.time() - t0, 1),
         "hangs": arm.hangs, "runner_restarts": runner.restarts})
    f.close()
    runner.close()
    print("DONE %s %s" % (a.run_id, a.arm))


main()
