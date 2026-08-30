#!/usr/bin/env python3
"""renderrun.py -- EXP-0168 RENDER-arm capture driver (G17P).

    # 0. calibration (writes work/, NOT evidence): what does the compiler emit?
    python3 harness/renderrun.py --mode census --run-id c01

    # 1. freeze the arm table from that census
    python3 harness/renderrun.py --mode freeze --census work/render_census_c01.json

    # 2. capture (writes raw/<run-id>/, append-only evidence)
    python3 harness/renderrun.py --mode run --run-id g17p_YYYYMMDD_runNN

THE QUESTION.  Four fields were withdrawn to `untested` by EXP-0164:
`vtx_out_pos.dst`, `vtx_out_pos.slot`, `pixel_order.kind` and
`frag_color_pack.dst`.  Three of the four were withdrawn because the CARRIER
could not express what the field controls, and the fourth because no per-value
record attributable to it exists under raw/.  This driver re-runs all four on
carriers that genuinely differ in the dimension the field controls, and records
them in the per-value schema.

WHAT MAKES A NULL MEAN ANYTHING.  Every arm proves DETECTION POWER before any
conclusion: a liveness ladder of >= 8 values of a known-live control, requiring
>= 2 distinct observed surface hashes among cases that were both status-OK and
VALID.  A faulted control does not count -- that was EXP-0163's own sec.7 defect
and it is fixed here at the point of measurement.  Ladder controls are VALUE
fields wherever one exists, because EXP-0163 measured 88 device resets in 50 s
and every one came from splicing an opcode or register-number byte.

VALIDITY, and it is not optional.  A case whose whole read-back is still
0xDEADBEEF poison, whose integrity sentinel failed, or that carries an
InnocentVictim-class OS string is NOT a valid observation and is NEVER recorded
as an inert/silent one -- it is re-run.  Two experiments have now seen a
contaminated dispatch report STATUS OK and write nothing at all with no victim
string (EXP-0160: 25 such cases); against a zero-initialised buffer those become
confident false nulls.

Derived from OUR OWN experiments/EXP-0163-.../run.py and
experiments/EXP-0162-.../harness/runrender.py.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.  Every byte spliced or inspected is the
compiled form of MSL in kernels/r_*.metal, which we wrote.  No Apple binary is
disassembled, decompiled, symbol-dumped or introspected.
"""
import argparse
import hashlib
import json
import os
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import rendercarriers as RC          # noqa: E402
import renderarms as RA              # noqa: E402
from runner3 import RenderRunner, render_cmd    # noqa: E402

WORK = os.path.join(EXP, "work")
RAW = os.path.join(EXP, "raw")
POISON4 = b"\xef\xbe\xad\xde"


# ---------------------------------------------------------------------------
# pinned tools
# ---------------------------------------------------------------------------
def find_tools():
    """The agx-isa / shdump snapshot this experiment is pinned to.

    `work/frozen/` holds the EXACT db.json / isadb.py the hardware ran against
    (sha256 in CAPTURE_CONTRACT.json).  It is preferred over the repo copy
    because the repo's db.json DRIFTS while sibling experiments extend the ISA,
    which would silently re-key these verdicts against a descriptor the hardware
    never saw (EXP-0144's portability trap).
    """
    cands = []
    if os.environ.get("AGXRE_REPO"):
        cands.append(os.path.join(os.environ["AGXRE_REPO"], "tools"))
    cands += [os.path.join(WORK, "frozen", "tools"),
              os.path.expanduser("~/agxre/EXP-0168/tools"),
              os.path.join(os.path.dirname(os.path.dirname(EXP)), "tools"),
              os.path.expanduser("~/agxre/tools")]
    for c in cands:
        if os.path.exists(os.path.join(c, "agx-isa", "isadb.py")) and \
           os.path.exists(os.path.join(c, "shdump", "agxparse.py")):
            return c
    raise RuntimeError("cannot locate a tools/ with agx-isa + shdump; tried:\n  "
                       + "\n  ".join(cands))


TOOLS = find_tools()
sys.path.insert(0, os.path.join(TOOLS, "agx-isa"))
import isadb                                   # noqa: E402  (read-only use)

AGXPARSE = os.path.join(TOOLS, "shdump", "agxparse.py")
GFRUN = os.path.join(WORK, "gfrun3")
CENSUS_PATH = os.path.join(WORK, "render_census_%s.json")
FROZEN_PATH = os.path.join(WORK, "render_frozen_arms.json")

# Every mnemonic any arm or any ladder needs located, per stage.
def _needed():
    """Which mnemonics the census must locate, per stage.

    DERIVED from renderarms.TARGETS and renderarms.LADDERS rather than
    hand-listed. It WAS hand-listed as
        {"vertex": ["vtx_out_pos", "vary_store"],
         "fragment": ["pixel_order", "frag_color_pack"]}
    and that silently defeated the `iter_at` arm: the carriers were built, the
    fragment programs DID contain `iter_at` (offset 8 in both r_i8 and r_i8s,
    confirmed by tokenizing the census's own recorded hex), and the census
    simply never looked for it -- so `--mode freeze` would have skipped every
    iter_at arm with "no occurrence in this carrier", which the code labels "a
    STRUCTURAL RESULT about when the instruction is emitted". A hand-maintained
    list turning a lookup omission into a structural claim about the hardware is
    exactly the kind of by-construction wrong answer this experiment exists to
    find. Deriving it means adding a TARGET cannot silently fail to be censused.
    """
    need = {"vertex": set(), "fragment": set()}
    for mn, spec in RA.TARGETS.items():
        need[spec["stage"]].add(mn)
        for L in RA.LADDERS.get(spec["family"], []):
            if L.get("mnemonic"):
                need[spec["stage"]].add(L["mnemonic"])
        for F in RA.FALSIFIERS.get(spec["family"], []):
            if F.get("mnemonic"):
                need[spec["stage"]].add(F["mnemonic"])
    # `vary_store` is the vertex-stage ladder for the vtx family and is also the
    # routing-sensitivity control quoted by other families' write-ups, so it is
    # always located where it can be.
    need["vertex"].add("vary_store")
    return {k: sorted(v) for k, v in need.items()}


NEEDED = _needed()


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def sh(cmd, timeout=300):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError("%s failed:\n%s\n%s" % (" ".join(cmd), r.stdout, r.stderr))
    return r.stdout


def build_carrier(name, cfg):
    arch = os.path.join(WORK, "r_%s.bin" % name)
    sh(render_cmd(GFRUN, os.path.join(EXP, cfg["src"]), cfg, build=arch,
                  vname=RC.VERTEX_FN, fname=RC.FRAGMENT_FN))
    return arch


def stage_bytes(arch, stage):
    args = [sys.executable, AGXPARSE, arch, "--stage", stage]
    loc = sh(args + ["--locate", "_agc.main"]).split()
    off, ln = int(loc[0]), int(loc[1])
    b = bytes.fromhex(sh(args + ["--extract-hex"]).strip())
    if len(b) != ln:
        raise RuntimeError("extract/locate disagree: %d vs %d" % (len(b), ln))
    return off, b


def locate(buf, mnemonic):
    """Every offset where isadb decodes `mnemonic`.

    Identical rule to EXP-0163's run.py and analysis/census.py, kept identical
    ON PURPOSE: those two once disagreed about occurrence indices (one preferred
    the tokenized prefix, the other always rescanned) and three arms were caught
    resolving to the wrong offset before anything was swept.

      1. forward-tokenize from 0; take the hits in the tokenized PREFIX -- those
         are on the real instruction grid;
      2. only if the prefix yields NO hit, fall back to an anchored decode scan
         over the whole buffer, keeping offsets whose two following instructions
         also decode.

    A scan hit is not on a proven instruction boundary, so an arm resolved that
    way is usable only through its liveness ladder (a spurious hit cannot move
    the observation).  `located_via` is recorded per arm.
    """
    recs, left, off = [], None, 0
    while off < len(buf):
        try:
            rec, L = isadb.decode_one(buf, off)
        except ValueError:
            left = off
            break
        rec["off"] = off
        recs.append(rec)
        off += L
    pre = [r["off"] for r in recs if r["mnemonic"] == mnemonic]
    if left is None:
        return pre, "tokenize"
    if pre:
        return pre, "tokenize-prefix"
    hits = []
    for o in range(len(buf) - 1):
        try:
            rec, L = isadb.decode_one(buf, o)
        except ValueError:
            continue
        if rec["mnemonic"] != mnemonic:
            continue
        ok, p = True, o + L
        for _ in range(2):
            if p >= len(buf):
                break
            try:
                _r, _l = isadb.decode_one(buf, p)
            except ValueError:
                ok = False
                break
            p += _l
        if ok:
            hits.append(o)
    return hits, "scan"


def set_field(mnemonic, raw, field, value):
    desc = isadb._BY_MNEM[mnemonic]
    v = int.from_bytes(raw, "little")
    for f in desc["fields"]:
        if f["name"] == field:
            mask = ((1 << f["width"]) - 1) << f["start"]
            v = (v & ~mask) | ((value << f["start"]) & mask)
            return v.to_bytes(desc["length"], "little")
    raise KeyError("%s.%s" % (mnemonic, field))


def set_raw_byte(raw, index, value):
    b = bytearray(raw)
    b[index] = value & 0xFF
    return bytes(b)


def field_width(mnemonic, field):
    for f in isadb._BY_MNEM[mnemonic]["fields"]:
        if f["name"] == field:
            return f["width"]
    return None


def redecodes_as(patched):
    try:
        d, _ = isadb.decode_one(patched, 0)
        return d["mnemonic"]
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# census / freeze
# ---------------------------------------------------------------------------
def select_carriers(args):
    names = [n for n in RC.CARRIERS
             if (not args.carriers or n in set(args.carriers.split(",")))
             and RC.CARRIERS[n].get("priority", 1) <= args.priority]
    return sorted(names)


def do_census(args):
    out = {"kind": "census", "run_id": args.run_id, "tools": TOOLS,
           "isadb_sha256": sha256_file(os.path.join(TOOLS, "agx-isa", "db.json")),
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "carriers": {}}
    for name in select_carriers(args):
        cfg = RC.CARRIERS[name]
        src = os.path.join(EXP, cfg["src"])
        entry = {"src": cfg["src"], "src_sha256": sha256_file(src),
                 "carrier_dim": cfg["carrier_dim"], "family": cfg["family"],
                 "why": cfg["why"], "priority": cfg.get("priority", 1),
                 "cmd": render_cmd(GFRUN, src, cfg, build="<archive>",
                                   vname=RC.VERTEX_FN, fname=RC.FRAGMENT_FN),
                 "stages": {}}
        try:
            arch = build_carrier(name, cfg)
        except Exception as e:                       # noqa: BLE001
            entry["build_error"] = str(e)[:2000]
            out["carriers"][name] = entry
            continue
        entry["archive_sha256"] = sha256_file(arch)
        for stage in ("vertex", "fragment"):
            try:
                abs_off, buf = stage_bytes(arch, stage)
            except Exception as e:                   # noqa: BLE001
                entry["stages"][stage] = {"error": str(e)[:600]}
                continue
            st = {"abs_off": abs_off, "len": len(buf), "hex": buf.hex(),
                  "occurrences": {}}
            for mn in NEEDED[stage]:
                hits, how = locate(buf, mn)
                occ = []
                for i, o in enumerate(hits):
                    d, L = isadb.decode_one(buf, o)
                    occ.append({"occ": i, "instr_off": o, "abs_off": abs_off + o,
                                "length": L, "hex": d["hex"], "fields": d["fields"]})
                st["occurrences"][mn] = {"located_via": how, "n": len(hits),
                                         "hits": occ}
            entry["stages"][stage] = st
        out["carriers"][name] = entry
    os.makedirs(WORK, exist_ok=True)
    p = CENSUS_PATH % args.run_id
    with open(p, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    # A readable summary, because the point of the census is to be READ before
    # anything is frozen.
    for name, e in sorted(out["carriers"].items()):
        if "build_error" in e:
            print("%-8s BUILD FAILED: %s" % (name, e["build_error"].splitlines()[0][:90]))
            continue
        bits = []
        for stage, st in sorted(e["stages"].items()):
            if "error" in st:
                bits.append("%s:ERR" % stage)
                continue
            for mn, oc in sorted(st["occurrences"].items()):
                if oc["n"]:
                    bits.append("%s/%s=%d(%s)" % (stage[0], mn, oc["n"], oc["located_via"]))
        print("%-8s %s" % (name, "  ".join(bits) or "(no target instructions)"))
    print("\ncensus -> %s" % p)
    return p


def do_freeze(args):
    cen = json.load(open(args.census))
    arms, skipped = [], []
    for name, e in sorted(cen["carriers"].items()):
        if "build_error" in e:
            skipped.append({"carrier": name, "why": "build failed"})
            continue
        cfg = RC.CARRIERS[name]
        dims = {cfg["family"]: cfg["carrier_dim"]}
        for mn, spec in RA.TARGETS.items():
            fam = spec["family"]
            cdim = dims.get(fam)
            if cdim is None:
                if not args.cross_family:
                    skipped.append({"carrier": name, "mnemonic": mn,
                                    "why": "carrier declares no dimension for "
                                           "the %s family; an occurrence here "
                                           "would add an arm but NOT a distinct "
                                           "carrier, and its ladders live in "
                                           "another stage. Enable with "
                                           "--cross-family." % fam})
                    continue
                cdim = "secondary:" + cfg["carrier_dim"]
            stage = spec["stage"]
            st = e["stages"].get(stage, {})
            oc = st.get("occurrences", {}).get(mn)
            if not oc or not oc["n"]:
                skipped.append({"carrier": name, "mnemonic": mn, "stage": stage,
                                "why": "no occurrence in this carrier -- a "
                                       "STRUCTURAL RESULT about when the "
                                       "instruction is emitted, not a failure"})
                continue
            for hit in oc["hits"][:args.max_occ]:
                # Ladder targets, located in the same stage of the same carrier.
                ladders = []
                for L in RA.LADDERS[fam]:
                    if L["mnemonic"] is None:
                        ladders.append({"id": L["id"], "kind": "data"})
                        continue
                    loc = st["occurrences"].get(L["mnemonic"])
                    if not loc or not loc["n"]:
                        ladders.append({"id": L["id"], "kind": "splice",
                                        "unavailable": "no %s occurrence"
                                                       % L["mnemonic"]})
                        continue
                    if L["mnemonic"] == mn:
                        cands = [hit]              # same instruction instance
                    else:
                        cands = loc["hits"][:args.ladder_max_occ]
                    ladders.append({"id": L["id"], "kind": "splice",
                                    "mnemonic": L["mnemonic"],
                                    "targets": [{"occ": c["occ"],
                                                 "abs_off": c["abs_off"],
                                                 "hex": c["hex"],
                                                 "length": c["length"]}
                                                for c in cands]})
                arms.append({
                    "arm": RA.arm_id(mn, name, stage, hit["occ"]),
                    "carrier": name, "stage": stage, "mnemonic": mn,
                    "occ": hit["occ"], "family": fam,
                    "carrier_dim": cdim,
                    "fields": sorted(spec["fields"]),
                    "expect_hex": hit["hex"], "expect_off": hit["instr_off"],
                    "abs_off": hit["abs_off"], "length": hit["length"],
                    "decoded": hit["fields"],
                    "located_via": oc["located_via"],
                    "ladders": ladders,
                })
    frozen = {"kind": "frozen_arms", "from_census": os.path.basename(args.census),
              "census_sha256": sha256_file(args.census),
              "isadb_sha256": cen["isadb_sha256"],
              "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "carrier_src_sha256": {n: e.get("src_sha256")
                                     for n, e in cen["carriers"].items()},
              "arms": arms, "skipped": skipped}
    with open(FROZEN_PATH, "w") as f:
        json.dump(frozen, f, indent=1, sort_keys=True)
    print("frozen %d arms (%d skipped) -> %s" % (len(arms), len(skipped), FROZEN_PATH))
    for a in arms:
        print("  %-34s %-9s %s" % (a["arm"], a["located_via"], a["expect_hex"]))
    for s in skipped:
        print("  SKIP %s" % json.dumps(s, sort_keys=True))
    return FROZEN_PATH


# ---------------------------------------------------------------------------
# observation
# ---------------------------------------------------------------------------
def os_class(err):
    for tag in ("InnocentVictim", "IgnoredPriorErrors", "ErrorHang", "ErrorTimeout",
                "ErrorPageFault", "ErrorOutOfMemory", "ErrorInvalidResource",
                "ErrorMakeCurrent", "ErrorRestart", "ErrorRecovery"):
        if tag in err:
            return tag
    return "unclassified" if err else ""


def observe(resp, name):
    """Reduce a runner response to a compact, deterministic observation.

    EVERY surface is hashed, so a change anywhere -- any attachment, the
    writable textures, the depth buffer, the vertex-stage device buffer -- is
    DETECTED, not only at the probe points.  The probes exist to make a
    difference READABLE; the hashes are what make it detectable.
    """
    cfg = RC.CARRIERS[name]
    if resp.get("status") != "OK":
        return {"status": resp.get("status", "UNKNOWN"),
                "error": resp.get("error", "")[:220],
                "os_class": os_class(resp.get("error", "")),
                "errdom": resp.get("errdom", ""),
                "sentinel": resp.get("sentinel", ""),
                "ovr": resp.get("ovr", []),
                "foreign_retries": resp.get("foreign_retries", 0),
                "restarted": bool(resp.get("restarted"))}
    surf = resp.get("surf", {})
    o = {"status": "OK",
         "hh": {k: hashlib.sha256(v).hexdigest()[:24] for k, v in sorted(surf.items())},
         "missing": sorted(resp.get("missing", [])),
         "sentinel": resp.get("sentinel", ""),
         "ovr": resp.get("ovr", []),
         "os_class": "", "errdom": "",
         "foreign_retries": resp.get("foreign_retries", 0)}
    poisoned = [k for k, v in surf.items()
                if len(v) >= 4 and v == POISON4 * (len(v) // 4)]
    if poisoned:
        o["poison"] = sorted(poisoned)
    if not surf:
        o["status"] = "NO_SURFACE"
        return o
    if len(poisoned) == len(surf):
        o["status"] = "POISON"
        return o

    fmt, w = cfg["color_format"], cfg["width"]
    pr = {}
    for tag, buf in sorted(surf.items()):
        if tag.startswith("PIX") and "_S" not in tag:
            vv = [RC.decode_pixel(buf, fmt, x, y, w)
                  for (x, y) in RC.probe_pixels(cfg)]
            # Every carrier draws a FULL-SCREEN triangle whose varyings are equal
            # at all three vertices, so every probe pixel must hold the same
            # value.  Collapse when they agree; keep the list when they do not,
            # because disagreement is itself an observation (and `oracle_match`
            # then reports a mismatch rather than silently comparing pixel 0).
            pr[tag] = vv[0] if all(x == vv[0] for x in vv) else vv
            if len(vv) > 1 and pr[tag] is not vv[0]:
                o["probe_pixels_disagree"] = o.get("probe_pixels_disagree", []) + [tag]
        elif tag == "TEXW":
            pr[tag] = RC.decode_texw(buf)
        elif tag == "TEXWU":
            pr[tag] = RC.decode_texwu(buf)
        elif tag == "OUTBUF":
            vals = RC.decode_outbuf(buf)
            pr[tag] = vals
            o["outbuf_tail_dirty"] = _tail_dirty(name, buf)
    o["probe"] = pr
    o["rt_ok"] = _rt_ok(cfg, surf, resp.get("missing", []))
    return o


def _rt_ok(cfg, surf, missing):
    if any(m.startswith("PIX") for m in missing):
        return False
    return sum(1 for k in surf if k.startswith("PIX")) == cfg["rt_count"]


def _tail_dirty(name, buf):
    """The out-buf slots NOTHING writes must still be 0xDEADBEEF.

    If a dispatch reports OK and the tail is no longer poison, something wrote
    out of bounds -- a first-class result, not a nuisance (the parent arm's
    harness/isa_helpers.py builds the same region for the compute side).
    """
    exp = RC.oracle(name).get("OUTBUF")
    if exp is None:
        return None
    for i, e in enumerate(exp):
        if e is not None:
            continue
        if buf[i * 4:i * 4 + 4] != POISON4:
            return True
    return False


def validity(obs):
    """`valid` | `invalid_poison` | `invalid_sentinel` | `invalid_victim`.

    A fault or a hang IS a valid observation (of a fault).  What is never valid
    is an observation that cannot be attributed to our encoding at all.
    """
    if obs.get("os_class") in ("InnocentVictim", "IgnoredPriorErrors") \
            or obs.get("status") == "FOREIGN_FAULT":
        return "invalid_victim"
    sen = obs.get("sentinel", "")
    if obs.get("status") == "SENTINEL_FAIL" or (sen and not sen.startswith("OK")):
        return "invalid_sentinel"
    if obs.get("status") in ("POISON", "NO_SURFACE"):
        return "invalid_poison"
    return "valid"


def same_obs(a, b):
    return (a.get("status") == "OK" and b.get("status") == "OK"
            and a.get("hh") == b.get("hh"))


def oracle_match(name, obs, alt=False):
    """Does the observation equal the HOST-COMPUTED expectation, exactly?"""
    if obs.get("status") != "OK":
        return False
    exp = RC.oracle(name, alt)
    pr = obs.get("probe", {})
    for tag, want in exp.items():
        got = pr.get(tag)
        if got is None:
            return False
        if tag == "OUTBUF":
            for i, e in enumerate(want):
                if e is None:
                    continue
                if i >= len(got) or got[i] != e:
                    return False
            continue
        if isinstance(got, list) and got and isinstance(got[0], list):
            return False                     # probe pixels disagreed
        if not RC._eq(got, want):
            return False
    return True


def classify(name, obs, base):
    cfg = RC.CARRIERS[name]
    st = obs.get("status")
    if st == "HANG":
        return "hang"
    if st in ("POISON", "NO_SURFACE"):
        return "invalid_run"
    if st != "OK":
        return "fault"
    if cfg["family"] == "rog":
        return RC.classify_rog(name, obs.get("probe", {}))
    if same_obs(obs, base):
        return "ok"
    pr = obs.get("probe", {})
    zero = True
    for tag, v in pr.items():
        if not tag.startswith("PIX"):
            continue
        flat = v if (v and not isinstance(v[0], list)) else [x for r in v for x in r]
        if any(abs(float(x)) > 0 for x in flat):
            zero = False
    return "silent_zero" if zero else "wrong_value"


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------
class Run:
    def __init__(self, args, outdir, frozen):
        self.args = args
        self.outdir = outdir
        self.frozen = frozen
        self.jl = open(os.path.join(outdir, "sweep.jsonl"), "a")
        self.n = 0
        self.hangs_total = 0
        self.runners = {}
        self.summary = {}
        self.stop_all = False
        self.bytemate_done = 0
        self.deadline = (time.time() + args.deadline_s) if args.deadline_s > 0 else None

    # -- emission: append + flush + fsync, EVERY case, never buffered ---------
    def emit(self, rec):
        rec.setdefault("target", "G17P")
        rec.setdefault("run_id", self.args.run_id)
        rec.setdefault("ts", round(time.time(), 3))
        self.jl.write(json.dumps(rec, sort_keys=True) + "\n")
        self.jl.flush()
        os.fsync(self.jl.fileno())
        self.n += 1

    def out_of_time(self):
        return self.deadline is not None and time.time() > self.deadline

    # -- one dispatch --------------------------------------------------------
    def dispatch(self, arm, splices, bufs=None):
        r = self.runners[arm["carrier"]]
        resp = r.render(splices, timeout=RA.REQ_TIMEOUT, bufs=bufs, at=self.n)
        return observe(resp, arm["carrier"])

    def dispatch_valid(self, arm, splices, bufs=None, rec=None):
        """Re-run until the observation is attributable, emitting every attempt.

        An `invalid_*` case is NEVER the recorded observation: it is retained as
        append-only evidence with accepted=false and re-run.
        """
        obs = None
        for attempt in range(RA.MAX_INVALID_RETRIES + 1):
            obs = self.dispatch(arm, splices, bufs)
            v = validity(obs)
            if v == "valid":
                return obs, v, attempt
            if rec is not None:
                r = dict(rec)
                r.update(observed=obs, validity=v, accepted=False,
                         attempt=attempt, outcome="invalid_run", match=False,
                         rt_ok=obs.get("rt_ok"))
                self.emit(r)
            time.sleep(0.25 * (attempt + 1))
        return obs, validity(obs), RA.MAX_INVALID_RETRIES

    def dispatch_confirmed(self, arm, splices, bufs=None, rec=None):
        """Majority-of-3 before any fault/hang verdict (FIELD-SWEEP-PROTOCOL
        sec.7: never conclude `fault` from a single observation -- EXP-0139 would
        have labelled 692 legal field values `fault` without this)."""
        obs, v, att = self.dispatch_valid(arm, splices, bufs, rec)
        if obs.get("status") == "OK" or v != "valid":
            return obs, v, att, None
        trials = [obs]
        for _ in range(RA.CONFIRM_N - 1):
            t, tv, _ = self.dispatch_valid(arm, splices, bufs, rec)
            trials.append(t)
        nbad = sum(1 for t in trials if t.get("status") != "OK")
        conf = {"n": len(trials),
                "status": [t.get("status") for t in trials],
                "os_class": [t.get("os_class", "") for t in trials],
                "bad": nbad, "reproduced": nbad * 2 > len(trials)}
        if not conf["reproduced"]:
            for t in trials:
                if t.get("status") == "OK":
                    return t, validity(t), att, conf
        return trials[0], v, att, conf

    # -- arm execution -------------------------------------------------------
    def run_arm(self, arm):
        name = arm["carrier"]
        cfg = RC.CARRIERS[name]
        spec = RA.TARGETS[arm["mnemonic"]]
        orig = bytes.fromhex(arm["expect_hex"])
        base_rec = dict(instr=arm["mnemonic"], carrier=name, arm=arm["arm"],
                        carrier_dim=arm["carrier_dim"], role="baseline",
                        field="_baseline", value=-1, bytes=arm["expect_hex"],
                        byte_index=None, fstart=None, fwidth=None,
                        note=spec["controls"], confirm=None, oracle=None)
        base, v, att = self.dispatch_valid(arm, [], rec=base_rec)
        ok_oracle = oracle_match(name, base)
        r = dict(base_rec)
        r.update(observed=base, validity=v, accepted=True, attempt=att,
                 outcome="ok" if base.get("status") == "OK" else "fault",
                 match=bool(ok_oracle), rt_ok=base.get("rt_ok"),
                 oracle={k: vv for k, vv in RC.oracle(name).items()},
                 note=base_rec["note"] + " | baseline vs HOST oracle: %s"
                      % ("EXACT" if ok_oracle else "MISMATCH"))
        self.emit(r)
        S = self.summary.setdefault(arm["arm"], {
            "carrier": name, "carrier_dim": arm["carrier_dim"],
            "mnemonic": arm["mnemonic"], "located_via": arm["located_via"],
            "baseline_ok": base.get("status") == "OK",
            "baseline_oracle_exact": bool(ok_oracle),
            "ladders": {}, "ladder_pass": False, "falsifiers": {},
            "fields": {}, "hangs": 0, "stopped": None})
        if base.get("status") != "OK":
            S["stopped"] = "baseline failed"
            return
        if not ok_oracle:
            # Recorded, not fatal: the sweep's inert oracle still works against
            # this arm's own baseline, but a host-oracle mismatch bounds every
            # claim made from it and MUST be visible in the record.
            S["baseline_note"] = ("baseline does not match the host oracle; "
                                  "every verdict from this arm is bounded by that")

        self.run_ladders(arm, base, S)
        self.run_falsifiers(arm, base, S)
        if self.args.bytemate and self.bytemate_done < self.args.bytemate_arms:
            self.bytemate_done += 1
            self.run_bytemate(arm, orig, base, S)
        if S["ladder_pass"] or not self.args.skip_powerless:
            self.run_sweeps(arm, orig, base, S)
        else:
            self.emit(dict(instr=arm["mnemonic"], carrier=name, arm=arm["arm"],
                           carrier_dim=arm["carrier_dim"], role="sweep",
                           field="_not_run", value=-1, bytes="",
                           byte_index=None, fstart=None, fwidth=None,
                           observed={"status": "LADDER_FAILED"}, oracle=None,
                           validity="valid", accepted=True, attempt=0,
                           match=False, outcome="not_run", rt_ok=None,
                           confirm=None,
                           note="no ladder demonstrated detection power and "
                                "--skip-powerless is set; this arm's inertness "
                                "is NOT evidence"))
        # end-of-arm baseline re-validation
        b2, v2, _ = self.dispatch_valid(arm, [])
        holds = same_obs(b2, base)
        S["baseline_final_ok"] = bool(holds)
        self.emit(dict(instr=arm["mnemonic"], carrier=name, arm=arm["arm"],
                       carrier_dim=arm["carrier_dim"], role="baseline",
                       field="_baseline_final", value=-1, bytes=arm["expect_hex"],
                       byte_index=None, fstart=None, fwidth=None,
                       observed=b2, oracle=None, validity=v2, accepted=True,
                       attempt=0, match=bool(holds),
                       outcome="ok" if holds else "fault",
                       rt_ok=b2.get("rt_ok"), confirm=None,
                       note="end-of-arm re-validation"))

    # -- ladders -------------------------------------------------------------
    def run_ladders(self, arm, base, S):
        name = arm["carrier"]
        cfg = RC.CARRIERS[name]
        order = {"none": 0, "low": 1, "medium": 2, "high": 3}
        spec = {L["id"]: L for L in RA.LADDERS[arm["family"]]}
        for fl in sorted(arm["ladders"], key=lambda x: order.get(
                spec[x["id"]].get("hazard", "low"), 1)):
            L = spec[fl["id"]]
            if L.get("hazard") == "high" and self.args.skip_hazard:
                S["ladders"][L["id"]] = {"skipped": "--skip-hazard"}
                continue
            if fl.get("unavailable"):
                S["ladders"][L["id"]] = {"skipped": fl["unavailable"]}
                self.emit(self._lrec(arm, L, -1, "", {"status": "UNAVAILABLE"},
                                     "not_run", fl["unavailable"]))
                continue
            if fl["kind"] == "data":
                ov = RC.buf0_override_bytes(cfg)
                if ov is None:
                    S["ladders"][L["id"]] = {
                        "skipped": "carrier has no runtime-sourced input "
                                   "(colour values are literals in the MSL)"}
                    self.emit(self._lrec(arm, L, -1, "", {"status": "UNAVAILABLE"},
                                         "not_run", S["ladders"][L["id"]]["skipped"]))
                    continue
                rec = self._lrec(arm, L, 0, "", None, None, None, skeleton=True)
                obs, v, att = self.dispatch_valid(arm, [], bufs={0: ov}, rec=rec)
                moved = not same_obs(obs, base)
                alt_exact = oracle_match(name, obs, alt=True)
                applied = any(x.startswith("0 applied") for x in obs.get("ovr", []))
                S["ladders"][L["id"]] = {
                    "moved": bool(moved), "alt_oracle_exact": bool(alt_exact),
                    "override_applied": bool(applied),
                    "pass": bool(moved and applied and obs.get("status") == "OK"
                                 and v == "valid")}
                r = dict(rec)
                r.update(observed=obs, validity=v, accepted=True, attempt=att,
                         match=bool(alt_exact),
                         outcome="moved" if moved else "inert",
                         rt_ok=obs.get("rt_ok"),
                         oracle={k: vv for k, vv in RC.oracle(name, alt=True).items()},
                         note=L["cite"][:400] + " | override_applied=%s "
                              "alt_oracle_exact=%s" % (applied, alt_exact))
                self.emit(r)
                if S["ladders"][L["id"]]["pass"]:
                    S["ladder_pass"] = True
                continue
            # splice ladder: try successive occurrences until one shows power
            best = None
            for tgt in fl["targets"]:
                hashes, statuses = set(), []
                traw = bytes.fromhex(tgt["hex"])
                for val in L["values"]:
                    if self.stop_all or self.out_of_time():
                        break
                    if "raw_byte" in L:
                        patched = set_raw_byte(traw, L["raw_byte"], val)
                    else:
                        patched = set_field(fl["mnemonic"], traw, L["field"], val)
                    rec = self._lrec(arm, L, val, patched.hex(), None, None, None,
                                     skeleton=True, occ=tgt["occ"],
                                     mnem=fl["mnemonic"])
                    obs, v, att, conf = self.dispatch_confirmed(
                        arm, [(tgt["abs_off"], patched.hex())], rec=rec)
                    statuses.append(obs.get("status"))
                    # STRICT gate (EXP-0163 sec.7 defect, fixed here): a control
                    # counts as live only if it was OK, VALID, and still decodes
                    # as its own mnemonic.  A faulted control is an effect, not a
                    # demonstration that the arm can see a VALUE difference.
                    dm = redecodes_as(patched)
                    if obs.get("status") == "OK" and v == "valid" \
                            and dm == fl["mnemonic"]:
                        hashes.add(json.dumps(obs.get("hh"), sort_keys=True))
                    hung = self._count_hang(arm, S, obs, conf)
                    r = dict(rec)
                    r.update(observed=obs, validity=v, accepted=True, attempt=att,
                             confirm=conf, rt_ok=obs.get("rt_ok"),
                             match=same_obs(obs, base),
                             outcome=("hang" if hung else
                                      ("moved" if not same_obs(obs, base) else "inert")),
                             oracle=None,
                             note="%s | redecodes_as=%s" % (L["cite"][:360], dm))
                    self.emit(r)
                    if hung and S["hangs"] >= RA.MAX_HANGS_PER_ARM:
                        break
                res = {"occ": tgt["occ"], "distinct_hashes": len(hashes),
                       "statuses": statuses,
                       "pass": len(hashes) >= RA.LADDER_MIN_DISTINCT_HASHES}
                if best is None or res["distinct_hashes"] > best["distinct_hashes"]:
                    best = res
                if res["pass"]:
                    break
            S["ladders"][L["id"]] = best or {"pass": False}
            if best and best["pass"]:
                S["ladder_pass"] = True

    def _lrec(self, arm, L, value, bts, observed, outcome, note,
              skeleton=False, occ=None, mnem=None):
        r = dict(instr=mnem or arm["mnemonic"], carrier=arm["carrier"],
                 arm=arm["arm"], carrier_dim=arm["carrier_dim"], role="ladder",
                 field="%s:%s" % (L["id"], L.get("field") or
                                  ("byte%d" % L["raw_byte"] if "raw_byte" in L
                                   else "-")),
                 value=value, bytes=bts,
                 byte_index=(L["raw_byte"] if "raw_byte" in L else None),
                 fstart=None, fwidth=None, ladder_occ=occ,
                 hazard=L.get("hazard", "low"), note="", oracle=None,
                 confirm=None)
        if skeleton:
            return r
        r.update(observed=observed, outcome=outcome, note=note, oracle=None,
                 validity=validity(observed or {}), accepted=True, attempt=0,
                 match=False, rt_ok=None, confirm=None)
        return r

    # -- falsifiers ----------------------------------------------------------
    def run_falsifiers(self, arm, base, S):
        name = arm["carrier"]
        cfg = RC.CARRIERS[name]
        byocc = {}
        for fl in arm["ladders"]:
            if fl["kind"] == "splice" and not fl.get("unavailable"):
                byocc[fl["mnemonic"]] = fl["targets"][0]
        for F in RA.FALSIFIERS[arm["family"]]:
            rec = dict(instr=F["mnemonic"] or arm["mnemonic"], carrier=name,
                       arm=arm["arm"], carrier_dim=arm["carrier_dim"],
                       role="falsifier", field="%s:%s" % (F["id"], F["field"] or "-"),
                       value=(-1 if F["value"] is None else F["value"]),
                       byte_index=None, fstart=None, fwidth=None, bytes="",
                       predict=F["predict"], hazard=F.get("hazard", "low"),
                       note=F["note"][:400], oracle=None, confirm=None)
            if F["mnemonic"] is None:
                ov = RC.buf0_override_bytes(cfg)
                if ov is None:
                    rec.update(bytes="", observed={"status": "UNAVAILABLE"},
                               oracle=None, validity="valid", accepted=True,
                               attempt=0, match=False, outcome="not_run",
                               rt_ok=None, confirm=None,
                               note=F["note"] + " | UNAVAILABLE: this carrier's "
                                    "values are MSL literals, so there is no "
                                    "runtime input to change")
                    self.emit(rec)
                    S["falsifiers"][F["id"]] = {"skipped": "no runtime input"}
                    continue
                rec["bytes"] = ""
                obs, v, att = self.dispatch_valid(arm, [], bufs={0: ov}, rec=rec)
                got_alt = oracle_match(name, obs, alt=True)
                failed_baseline = not same_obs(obs, base)
                held = ("held" if (got_alt and failed_baseline)
                        else ("partial" if failed_baseline else "failed"))
                S["falsifiers"][F["id"]] = {"held": held, "alt_exact": bool(got_alt),
                                            "differs_from_baseline": bool(failed_baseline)}
                rec.update(observed=obs, validity=v, accepted=True, attempt=att,
                           match=(held == "held"), outcome="falsifier_" + held,
                           rt_ok=obs.get("rt_ok"),
                           oracle={k: vv for k, vv in RC.oracle(name, alt=True).items()},
                           confirm=None, note=F["note"])
                self.emit(rec)
                continue
            tgt = byocc.get(F["mnemonic"])
            if tgt is None:
                rec.update(bytes="", observed={"status": "UNAVAILABLE"}, oracle=None,
                           validity="valid", accepted=True, attempt=0, match=False,
                           outcome="not_run", rt_ok=None, confirm=None,
                           note=F["note"] + " | UNAVAILABLE: no %s occurrence in "
                                "this carrier" % F["mnemonic"])
                self.emit(rec)
                S["falsifiers"][F["id"]] = {"skipped": "no occurrence"}
                continue
            traw = bytes.fromhex(tgt["hex"])
            patched = set_field(F["mnemonic"], traw, F["field"], F["value"])
            rec["bytes"] = patched.hex()
            obs, v, att, conf = self.dispatch_confirmed(
                arm, [(tgt["abs_off"], patched.hex())], rec=rec)
            hung = self._count_hang(arm, S, obs, conf)
            oc = classify(name, obs, base)
            held = self._falsifier_held(F, obs, base, oc)
            S["falsifiers"][F["id"]] = {"held": held, "observed_outcome": oc}
            rec.update(observed=obs, validity=v, accepted=True, attempt=att,
                       confirm=conf, match=(held == "held"),
                       outcome=("hang" if hung else "falsifier_" + held),
                       rt_ok=obs.get("rt_ok"), oracle=None,
                       note="%s | predicted=%s observed=%s"
                            % (F["note"], F["predict"], oc))
            self.emit(rec)

    @staticmethod
    def _falsifier_held(F, obs, base, oc):
        """`held` | `partial` | `failed`.

        THREE states, not two.  A falsifier whose prediction is directionally
        right but not exact (the observation differs from the baseline, but not
        with the predicted signature) is NOT a pass; recording it as one would
        launder a wrong prediction into a passed control.
        """
        p = F["predict"]
        if p == "contained_fault":
            if obs.get("status") in ("CMDBUF_ERROR", "PIPELINE_MISS", "COMPILE_FAIL"):
                return "held"
            return "partial" if obs.get("status") == "HANG" else "failed"
        if p == "not_ok":
            return "held" if oc != "ok" else "failed"
        if p == "lost_7_of_8":
            if oc == "lost_7_of_8":
                return "held"
            return "partial" if oc not in ("ok",) else "failed"
        if p == "all_fragment_channels_zero":
            if oc == "silent_zero":
                return "held"
            return "partial" if oc not in ("ok",) else "failed"
        return "held" if not same_obs(obs, base) else "failed"

    # -- byte-mate -----------------------------------------------------------
    def run_bytemate(self, arm, orig, base, S):
        key, bm = None, None
        for fname in arm["fields"]:
            spec = RA.BYTE_MATES.get((arm["mnemonic"], fname), None)
            if (arm["mnemonic"], fname) in RA.BYTE_MATES:
                if spec is not None:
                    key, bm = fname, spec
                else:
                    self.emit(dict(instr=arm["mnemonic"], carrier=arm["carrier"],
                                   arm=arm["arm"], carrier_dim=arm["carrier_dim"],
                                   role="bytemate", field="%s:n/a" % fname,
                                   value=-1, bytes="", byte_index=None,
                                   fstart=None, fwidth=None,
                                   observed={"status": "NOT_APPLICABLE"},
                                   oracle=None, validity="valid", accepted=True,
                                   attempt=0, match=True, outcome="not_run",
                                   rt_ok=None, confirm=None,
                                   note=RA.BYTE_MATE_NA_NOTE))
        if key is None:
            return
        if bm.get("hazard") == "high" and self.args.skip_hazard:
            S["bytemate"] = {"skipped": "--skip-hazard"}
            return
        moved = 0
        local_hangs = 0
        for v in bm["values"]:
            if self.stop_all or self.out_of_time():
                break
            cur = orig[bm["raw_byte"]]
            patched = set_raw_byte(orig, bm["raw_byte"],
                                   (cur & ~bm["mate_mask"]) | (v & bm["mate_mask"]))
            if patched == orig:
                continue
            rec = dict(instr=arm["mnemonic"], carrier=arm["carrier"],
                       arm=arm["arm"], carrier_dim=arm["carrier_dim"],
                       role="bytemate", field="%s:mate" % key, value=v,
                       bytes=patched.hex(), byte_index=bm["raw_byte"],
                       fstart=None, fwidth=None, hazard=bm["hazard"],
                       note="", oracle=None, confirm=None)
            obs, va, att, conf = self.dispatch_confirmed(
                arm, [(arm["abs_off"], patched.hex())], rec=rec)
            hung = self._count_hang(arm, S, obs, conf)
            if hung:
                local_hangs += 1
            oc = classify(arm["carrier"], obs, base)
            if oc != "ok":
                moved += 1
            rec.update(observed=obs, validity=va, accepted=True, attempt=att,
                       confirm=conf, match=(oc == "ok"),
                       outcome=("hang" if hung else oc), rt_ok=obs.get("rt_ok"),
                       oracle=None,
                       note="%s | redecodes_as=%s" % (bm["note"][:400],
                                                      redecodes_as(patched)))
            self.emit(rec)
            if local_hangs >= RA.MAX_HANGS_PER_FIELD:
                self.emit(dict(instr=arm["mnemonic"], carrier=arm["carrier"],
                               arm=arm["arm"], carrier_dim=arm["carrier_dim"],
                               role="bytemate", field="%s:mate" % key, value=-1,
                               bytes="", byte_index=bm["raw_byte"], fstart=None,
                               fwidth=None, observed={"status": "FIELD_STOPPED"},
                               oracle=None, validity="valid", accepted=True,
                               attempt=0, match=False, outcome="hang",
                               rt_ok=None, confirm=None,
                               note="byte-mate STOPPED after %d hangs (budget %d)"
                                    % (local_hangs, RA.MAX_HANGS_PER_FIELD)))
                break
        S["bytemate"] = {"moved": moved, "hangs": local_hangs,
                         "n": len(bm["values"])}

    # -- dense sweeps --------------------------------------------------------
    def run_sweeps(self, arm, orig, base, S):
        name = arm["carrier"]
        spec = RA.TARGETS[arm["mnemonic"]]
        member = None
        if arm["mnemonic"] == "pixel_order":
            member = RA.pixel_order_member(arm["decoded"].get("kind", 0))
        since_base = 0
        for fname in arm["fields"]:
            if self.args.fields and fname not in set(self.args.fields.split(",")):
                continue
            meta = spec["fields"][fname]
            w = field_width(arm["mnemonic"], fname)
            if w is None:
                self.emit(self._srec(arm, fname, meta, -1, "",
                                     {"status": "NO_SUCH_FIELD"}, "not_run",
                                     "field absent from the pinned db.json"))
                continue
            if w != meta["fwidth"]:
                self.emit(self._srec(arm, fname, meta, -1, "",
                                     {"status": "WIDTH_MISMATCH"}, "not_run",
                                     "pinned db.json width %d != pre-registered "
                                     "%d -- arm refused rather than swept at a "
                                     "different field" % (w, meta["fwidth"])))
                continue
            defer = RA.KNOWN_FAULT_VALUES.get((arm["mnemonic"], fname), {}) \
                      .get("values", [])
            vals = RA.coverage_for(w, defer)
            fh = moved = nok = nfault = 0
            swept = 0
            for v in vals:
                if self.stop_all:
                    break
                if self.out_of_time():
                    self.emit(self._srec(arm, fname, meta, -1, "",
                                         {"status": "DEADLINE"}, "not_run",
                                         "wall-clock budget exhausted at %d/%d"
                                         % (swept, len(vals))))
                    break
                if since_base >= RA.BASELINE_EVERY:
                    holds = self.recheck_baseline(arm, base)
                    since_base = 0
                    if not holds:
                        self.emit(self._srec(arm, fname, meta, -1, "",
                                             {"status": "ARM_STOPPED"}, "fault",
                                             "the UNMUTATED carrier stopped "
                                             "reproducing its baseline on all %d "
                                             "attempts" % RA.BASELINE_RETRIES))
                        S["stopped"] = "baseline cascade"
                        return
                patched = set_field(arm["mnemonic"], orig, fname, v)
                rec = self._srec(arm, fname, meta, v, patched.hex(), None, None,
                                 None, skeleton=True)
                obs, va, att, conf = self.dispatch_confirmed(
                    arm, [(arm["abs_off"], patched.hex())], rec=rec)
                since_base += 1
                swept += 1
                hung = self._count_hang(arm, S, obs, conf)
                oc = classify(name, obs, base)
                if conf and not conf["reproduced"] and obs.get("status") != "OK":
                    oc = "unreproduced"
                dm = redecodes_as(patched)
                if dm != arm["mnemonic"] and oc == "ok":
                    oc = "undecodable"
                if hung:
                    oc = "hang"
                if oc == "ok":
                    nok += 1
                elif oc in ("fault", "hang"):
                    nfault += 1
                else:
                    moved += 1
                pred = None
                if member is not None and fname == "kind":
                    pred = RA.pixel_order_predict(member, v)
                rec.update(observed=obs, validity=va, accepted=True, attempt=att,
                           confirm=conf, rt_ok=obs.get("rt_ok"),
                           match=(oc == "ok"), outcome=oc, oracle=None,
                           predict=pred,
                           predict_held=(None if pred is None else pred == oc),
                           note=("" if dm == arm["mnemonic"]
                                 else "re-decodes as %s" % dm))
                self.emit(rec)
                if hung:
                    fh += 1
                    if fh >= RA.MAX_HANGS_PER_FIELD:
                        self.emit(self._srec(arm, fname, meta, -1, "",
                                             {"status": "FIELD_STOPPED"}, "hang",
                                             "FIELD STOPPED after %d genuine "
                                             "hangs at %d/%d values"
                                             % (fh, swept, len(vals))))
                        break
                    if S["hangs"] >= RA.MAX_HANGS_PER_ARM:
                        self.emit(self._srec(arm, fname, meta, -1, "",
                                             {"status": "ARM_STOPPED"}, "hang",
                                             "ARM STOPPED after %d hangs"
                                             % S["hangs"]))
                        S["stopped"] = "arm hang budget"
                        return
            S["fields"][fname] = {"n": len(vals), "swept": swept, "moved": moved,
                                  "unchanged": nok, "faults": nfault, "hangs": fh,
                                  "complete": swept == len(vals) and fh < RA.MAX_HANGS_PER_FIELD,
                                  "member": member}

    def _srec(self, arm, fname, meta, value, bts, observed, outcome, note,
              skeleton=False):
        r = dict(instr=arm["mnemonic"], carrier=arm["carrier"], arm=arm["arm"],
                 carrier_dim=arm["carrier_dim"], role="sweep", field=fname,
                 value=value, bytes=bts, byte_index=meta["byte_index"],
                 fstart=meta["fstart"], fwidth=meta["fwidth"], note="",
                 oracle=None, confirm=None)
        if skeleton:
            return r
        r.update(observed=observed, outcome=outcome, note=note, oracle=None,
                 validity="valid", accepted=True, attempt=0, match=False,
                 rt_ok=None, confirm=None)
        return r

    # -- shared --------------------------------------------------------------
    def _count_hang(self, arm, S, obs, conf):
        genuine = (conf is not None and conf.get("reproduced")
                   and (obs.get("status") == "HANG"
                        or obs.get("os_class") == "ErrorHang"))
        if not genuine:
            return False
        S["hangs"] += 1
        self.hangs_total += 1
        # A hang is a DEVICE RESET: it discards every other context's in-flight
        # command buffers. Back off before continuing.
        time.sleep(RA.HANG_SLEEP_S[min(S["hangs"], len(RA.HANG_SLEEP_S)) - 1])
        if self.hangs_total >= RA.MAX_HANGS_TOTAL:
            self.stop_all = True
        return True

    def recheck_baseline(self, arm, base):
        for k in range(RA.BASELINE_RETRIES):
            b, v, _ = self.dispatch_valid(arm, [])
            if same_obs(b, base):
                self.emit(dict(instr=arm["mnemonic"], carrier=arm["carrier"],
                               arm=arm["arm"], carrier_dim=arm["carrier_dim"],
                               role="baseline", field="_baseline_recheck",
                               value=self.n, bytes=arm["expect_hex"],
                               byte_index=None, fstart=None, fwidth=None,
                               observed=b, oracle=None, validity=v,
                               accepted=True, attempt=k, match=True,
                               outcome="ok", rt_ok=b.get("rt_ok"), confirm=None,
                               note="periodic re-validation, retries=%d" % k))
                return True
            time.sleep(0.5 * (k + 1))
        self.emit(dict(instr=arm["mnemonic"], carrier=arm["carrier"],
                       arm=arm["arm"], carrier_dim=arm["carrier_dim"],
                       role="baseline", field="_baseline_recheck", value=self.n,
                       bytes=arm["expect_hex"], byte_index=None, fstart=None,
                       fwidth=None, observed=b, oracle=None, validity=v,
                       accepted=True, attempt=RA.BASELINE_RETRIES, match=False,
                       outcome="fault", rt_ok=None, confirm=None,
                       note="periodic re-validation FAILED on all %d attempts"
                            % RA.BASELINE_RETRIES))
        return False


# ---------------------------------------------------------------------------
def do_run(args):
    if not os.path.exists(FROZEN_PATH):
        sys.exit("no frozen arm table at %s -- run --mode census then --mode "
                 "freeze first" % FROZEN_PATH)
    frozen = json.load(open(FROZEN_PATH))
    outdir = (os.path.join(WORK, "smoke_" + args.run_id) if args.smoke
              else os.path.join(RAW, args.run_id))
    if os.path.exists(outdir) and not args.smoke:
        sys.exit("run dir already exists, refusing to reuse or overwrite: %s"
                 % outdir)
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()

    want_c = set(x for x in args.carriers.split(",") if x)
    want_a = set(x for x in args.arms.split(",") if x)
    want_m = set(x for x in args.mnem.split(",") if x)
    arms = [a for a in frozen["arms"]
            if (not want_c or a["carrier"] in want_c)
            and (not want_a or a["arm"] in want_a)
            and (not want_m or a["mnemonic"] in want_m)
            and RC.CARRIERS[a["carrier"]].get("priority", 1) <= args.priority]

    inputs = {"run_id": args.run_id, "kind": "inputs", "target": "G17P",
              "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "tools": TOOLS,
              "isadb_sha256": sha256_file(os.path.join(TOOLS, "agx-isa", "db.json")),
              "frozen_arms_sha256": sha256_file(FROZEN_PATH),
              "frozen_from_census": frozen["from_census"],
              "gfrun3_sha256": sha256_file(GFRUN) if os.path.exists(GFRUN) else None,
              "harness_sha256": {f: sha256_file(os.path.join(HERE, f))
                                 for f in sorted(os.listdir(HERE))
                                 if f.endswith((".py", ".m"))},
              "kernel_sha256": {}, "carriers": {}, "arms": [], "refused": []}
    carriers = sorted({a["carrier"] for a in arms})
    for name in carriers:
        cfg = RC.CARRIERS[name]
        src = os.path.join(EXP, cfg["src"])
        inputs["kernel_sha256"][cfg["src"]] = sha256_file(src)
        arch = build_carrier(name, cfg)
        ent = {"archive_sha256": sha256_file(arch), "src_sha256": sha256_file(src),
               "carrier_dim": cfg["carrier_dim"], "why": cfg["why"], "stages": {}}
        for stage in ("vertex", "fragment"):
            try:
                off, buf = stage_bytes(arch, stage)
                ent["stages"][stage] = {"abs_off": off, "len": len(buf),
                                        "hex": buf.hex()}
            except Exception as e:                   # noqa: BLE001
                ent["stages"][stage] = {"error": str(e)[:400]}
        inputs["carriers"][name] = ent

    # FROZEN-OCCURRENCE INTEGRITY: the census bytes must still be there, at the
    # same offset.  An arm that moved is REFUSED, never swept at a new address.
    live = []
    for a in arms:
        st = inputs["carriers"][a["carrier"]]["stages"].get(a["stage"], {})
        if "hex" not in st:
            inputs["refused"].append({"arm": a["arm"], "why": st.get("error", "no stage")})
            continue
        buf = bytes.fromhex(st["hex"])
        hits, how = locate(buf, a["mnemonic"])
        if a["occ"] >= len(hits):
            inputs["refused"].append({"arm": a["arm"],
                                      "why": "occurrence %d of %d not found"
                                             % (a["occ"], len(hits))})
            continue
        ioff = hits[a["occ"]]
        d, L = isadb.decode_one(buf, ioff)
        if d["hex"] != a["expect_hex"] or ioff != a["expect_off"]:
            inputs["refused"].append({"arm": a["arm"],
                                      "why": "frozen occurrence moved: census had "
                                             "%s@%d, found %s@%d"
                                             % (a["expect_hex"], a["expect_off"],
                                                d["hex"], ioff)})
            continue
        a = dict(a)
        a["abs_off"] = st["abs_off"] + ioff
        a["decoded"] = d["fields"]
        live.append(a)
        inputs["arms"].append({"arm": a["arm"], "abs_off": a["abs_off"],
                               "hex": d["hex"], "decoded": d["fields"],
                               "located_via": how, "carrier_dim": a["carrier_dim"]})
    with open(os.path.join(outdir, "00_inputs.json"), "w") as f:
        json.dump(inputs, f, indent=1, sort_keys=True)

    run = Run(args, outdir, frozen)
    for name in carriers:
        cfg = RC.CARRIERS[name]
        run.runners[name] = RenderRunner(
            GFRUN, os.path.join(EXP, cfg["src"]),
            os.path.join(WORK, "r_%s.bin" % name),
            os.path.join(WORK, "scratch_%s_%s.bin" % (args.run_id, name)),
            cfg, RC.buf0_words(cfg), vname=RC.VERTEX_FN, fname=RC.FRAGMENT_FN)
    try:
        for a in live:
            if run.stop_all:
                break
            if run.out_of_time():
                run.emit(dict(instr=a["mnemonic"], carrier=a["carrier"],
                              arm=a["arm"], carrier_dim=a["carrier_dim"],
                              role="sweep", field="_arm_not_run", value=-1,
                              bytes="", byte_index=None, fstart=None,
                              fwidth=None, observed={"status": "DEADLINE"},
                              oracle=None, validity="valid", accepted=True,
                              attempt=0, match=False, outcome="not_run",
                              rt_ok=None, confirm=None,
                              note="wall-clock budget exhausted before this arm"))
                continue
            run.run_arm(a)
    finally:
        run.jl.close()
        for r in run.runners.values():
            r.close()

    man = {"run_id": args.run_id, "target": "G17P", "cases": run.n,
           "hangs": run.hangs_total, "stopped_early": run.stop_all,
           "elapsed_s": round(time.time() - t0, 1),
           "arms": run.summary,
           "device": {n: r.target_line for n, r in run.runners.items()},
           "restarts": {n: {"n": r.restarts, "at": r.restarts_at}
                        for n, r in run.runners.items()},
           "refused": inputs["refused"]}
    with open(os.path.join(outdir, "05_run_manifest.json"), "w") as f:
        json.dump(man, f, indent=1, sort_keys=True)
    print(json.dumps({k: man[k] for k in ("run_id", "cases", "hangs",
                                          "stopped_early", "elapsed_s",
                                          "refused")}, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("census", "freeze", "run"), default="run")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--census", default="", help="census json, for --mode freeze")
    ap.add_argument("--carriers", default="")
    ap.add_argument("--arms", default="")
    ap.add_argument("--mnem", default="")
    ap.add_argument("--fields", default="")
    ap.add_argument("--priority", type=int, default=3)
    ap.add_argument("--max-occ", type=int, default=4,
                    help="cap arms per (carrier, mnemonic)")
    ap.add_argument("--ladder-max-occ", type=int, default=4)
    ap.add_argument("--deadline-s", type=float, default=0.0)
    ap.add_argument("--smoke", action="store_true",
                    help="write to work/ instead of raw/ (calibration, not evidence)")
    ap.add_argument("--skip-hazard", action="store_true",
                    help="skip every hazard=high ladder and byte-mate control")
    ap.add_argument("--no-bytemate", dest="bytemate", action="store_false")
    ap.add_argument("--bytemate-arms", type=int, default=1,
                    help="how many arms get the byte-mate control. It is the "
                         "highest-hazard item in the plan (a decode-changing "
                         "splice into the vertex stream, which EXP-0162 measured "
                         "hanging), so it defaults to ONE arm.")
    ap.add_argument("--cross-family", action="store_true",
                    help="also sweep a target instruction on carriers that "
                         "declare no dimension for it; such arms are labelled "
                         "`secondary:` and never count toward the "
                         "distinct-carrier bar")
    ap.add_argument("--skip-powerless", action="store_true",
                    help="do not dense-sweep an arm whose ladder failed")
    ap.set_defaults(bytemate=True)
    args = ap.parse_args()
    if args.mode == "census":
        if not args.run_id:
            sys.exit("--mode census needs --run-id")
        do_census(args)
    elif args.mode == "freeze":
        if not args.census:
            sys.exit("--mode freeze needs --census work/render_census_<id>.json")
        do_freeze(args)
    else:
        if not args.run_id:
            sys.exit("--mode run needs --run-id")
        do_run(args)


if __name__ == "__main__":
    main()
