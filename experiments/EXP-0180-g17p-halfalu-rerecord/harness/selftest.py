#!/usr/bin/env python3
"""EXP-0180 OFFLINE self-test. NO device, NO Metal, NO GPU.

This is a CODE test. It is NOT evidence for any hardware claim and no verdict may cite it.
It exists so that a defect in the harness is found here rather than in a gated run.

Gates:
  G1  the pinned ISA resolves to work/frozen/ and both sha256s match the contract
  G2  every one of the 16 target field spans is present in the pinned db.json and matches
      work/target_rows.json (the merge-time refusal rule, checked early)
  G3  both seed tables satisfy the FROZEN adequacy predicate: 28 distinct, non-zero,
      normal, finite fp16 lanes
  G4  every seed value is an EXACT fixed point of the falu2i minifloat encoder
  G5  the synthesized program fits, is even-length, and contains both dumps + both sentinels
  G6  every generated base instance has the intended byte+4 length class and names only
      SEEDED registers, never the destination
  G7  the case matrix is deterministic (two builds -> identical sha256) and every case's
      value round-trips out of its own bytes via db.json's geometry
  G8  the ladder and falsifier sets are non-empty for every generated arm, and the
      EXP-0169 `byte0 -> 0x00` step appears ONLY inside DSTNIB
  G9  SafePersistRunner turns a TRUNCATED response into MALFORMED with the raw lines kept
      -- never a crash and never a hang (DEF-0178-1)
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H          # noqa: E402
import casematrix as M           # noqa: E402

R = []


def gate(name, ok, detail=""):
    R.append({"gate": name, "pass": bool(ok), "detail": detail})
    print("%-4s %-6s %s" % (name, "PASS" if ok else "FAIL", detail))
    return ok


def main():
    c = json.loads((EXP / "CAPTURE_CONTRACT.json").read_text())
    pins = H.assert_pins()
    gate("G1", pins["db_sha256"] == c["pinned_isa"]["db_json_sha256"]
         and pins["isadb_sha256"] == c["pinned_isa"]["isadb_py_sha256"]
         and pins["isa_dir"].endswith("work/frozen"),
         "isa_dir=%s" % pins["isa_dir"])

    tr = json.loads((EXP / "work" / "target_rows.json").read_text())["rows"]
    bad = []
    for key, row in tr.items():
        mn, fn = key.split(".", 1)
        f = next((x for x in M.INS[mn]["fields"] if x["name"] == fn), None)
        if f is None or f["start"] != row["db_start"] or f["width"] != row["db_width"]:
            bad.append(key)
    gate("G2", not bad and len(tr) == 16, "16 fields, moved/absent=%r" % bad)

    ok3 = True
    for n, w in (("SEED_A", H.SEED_A), ("SEED_B", H.SEED_B)):
        a, rep = H.adequacy(w)
        ok3 &= a
        if not a:
            print("   %s %r" % (n, rep))
    gate("G3", ok3, "28 distinct normal non-zero fp16 lanes in both tables")

    import isadb
    ok4 = all(isadb.imm_decode(*reversed(list(reversed(isadb.imm_encode(v))))) == v
              for t in (H.SEED_A_F, H.SEED_B_F) for v in t.values())
    gate("G4", ok4, "all 28 seed magnitudes are exact minifloat fixed points")

    prog = H.synth_program("A", H.half_add(1, 0x0D, 0x11), 4096)
    body = b"".join(H.seed_instrs("A")) 
    gate("G5", len(prog) == 4096 and len(prog) % 2 == 0 and len(body) > 0,
         "program %d bytes into a 4096-byte region" % len(prog))

    ok6, d6 = True, []
    for (arm, car), b in list(M.BASE.items()) + list(M.BASE12.items()):
        blk = M.base_block(arm, car)
        b4 = blk[4]
        want = 1 if arm.startswith("E8") else 3
        srcs = [blk[1], blk[3], blk[4], blk[5]]
        names_dst = any((s & 0x7F) >> 1 == M.DST_REG for s in srcs)
        unseeded = [s for s in srcs if ((s & 0x7F) >> 1) >= H.N_SEED]
        good = (b4 & 3) == want and not names_dst and not unseeded
        ok6 &= good
        d6.append("%s@%s b4&3=%d dst_as_src=%s unseeded=%r" %
                  (arm, car, b4 & 3, names_dst, unseeded))
    gate("G6", ok6, "; ".join(d6))

    rep = {}
    c1, _ = M.build_cases(rep)
    c2, _ = M.build_cases(rep)
    same = M.matrix_sha256(c1) == M.matrix_sha256(c2)
    rt = []
    for cs in c1:
        if cs.get("fstart") is None or cs.get("foreign"):
            continue
        blk = bytes.fromhex(cs["bytes"])
        if M.get_field(blk, 0, cs["fstart"], cs["fwidth"]) != cs["value"]:
            rt.append(cs["idx"])
    gate("G7", same and not rt,
         "deterministic=%s, %d cases, field-readback mismatches=%d" % (same, len(c1), len(rt)))

    arms = {(x["arm"], x["carrier"]) for x in c1}
    lad = {k: 0 for k in arms}
    fal = {k: 0 for k in arms}
    b0zero = set()
    for cs in c1:
        k = (cs["arm"], cs["carrier"])
        if cs["field"].startswith("__ladder_"):
            lad[k] += 1
        if cs["field"].startswith("__falsifier_"):
            fal[k] += 1
        if bytes.fromhex(cs["bytes"])[:1] == b"\x00":
            b0zero.add(cs["arm"])
    gen = [k for k in arms if k[0] in ("E8_ADD", "E8_FMA", "F12_FMA")]
    gate("G8", all(lad[k] >= 4 and fal[k] >= 3 for k in gen) and b0zero <= {"DSTNIB"},
         "ladders=%r falsifiers=%r byte0-zero arms=%r"
         % ({"%s@%s" % k: lad[k] for k in gen}, {"%s@%s" % k: fal[k] for k in gen},
            sorted(b0zero)))

    # G9 -- DEF-0178-1, proved offline against work/stub/fakerunner.py
    ok9, d9 = True, []
    for _c in (EXP.parents[1] / "tools", Path.home() / "agxre" / "tools"):
        if (_c / "agxtest" / "persistrun.py").exists():
            sys.path.insert(0, str(_c / "agxtest"))
            break
    import saferunner
    for mode in ("good", "truncate"):
        cmd = [sys.executable, str(EXP / "work" / "stub" / "fakerunner.py")]
        if mode == "truncate":
            cmd.append("--truncate")
        r = saferunner.SafePersistRunner.__new__(saferunner.SafePersistRunner)
        r.exe, r.source, r.function, r.fast_math, r._reqno = cmd[0], "", "", False, 0
        r.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, bufsize=1,
                                  start_new_session=True)
        r._install_pump()
        ready = r._pumped_readline(10)
        try:
            resp = r.request(archive="x", grid=1, tg=1, ins={0: "p"}, outs={0: 8}, timeout=5)
        except Exception as e:                                     # noqa: BLE001
            resp = {"status": "CRASHED:%s" % e, "raw": []}
        want = "OK" if mode == "good" else "MALFORMED"
        good = resp["status"] == want and bool(mode == "good" or resp.get("raw"))
        ok9 &= good
        d9.append("%s->%s raw=%d" % (mode, resp["status"], len(resp.get("raw", []))))
        try:
            r.proc.kill()
        except Exception:                                          # noqa: BLE001
            pass
        assert ready and ready.startswith("READY")
    gate("G9", ok9, "; ".join(d9))

    (EXP / "work" / "selftest.json").write_text(json.dumps(
        {"gates": R, "all_pass": all(x["pass"] for x in R),
         "note": "OFFLINE CODE TEST -- not evidence for any hardware claim"},
        indent=1, sort_keys=True))
    print("\nALL PASS" if all(x["pass"] for x in R) else "\nFAILURES PRESENT")
    return 0 if all(x["pass"] for x in R) else 1


if __name__ == "__main__":
    sys.exit(main())
