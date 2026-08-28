#!/usr/bin/env python3
"""EXP-0114 per-case worker. Invoked as its OWN process (one case per process,
per the standing gate) by run.py. Prints exactly one JSON object to stdout and
exits 0 on a normal outcome (including a CONTRACTED negative/silent-zero
outcome -- that is still "the case ran successfully and observed X"), nonzero
only on a genuine harness malfunction (compile failure, missing archive, bad
args). GPU faults/hangs surface as a non-OK "status" field with exit 0
wherever the underlying tool reports them cleanly (CMDBUF_ERROR); a true wedge
is caught by run.py's subprocess timeout, not by this script.

Three families:
  diff        -- own-shader-diff (compile-only, no GPU dispatch). Compiles a
                 kernel via shdump, extracts _agc.main, scans for the AGX
                 "read"-family two-part bundle (4-byte companion whose 3rd
                 byte is 0x0c, followed by a 10-byte op whose byte0 has a
                 zero low nibble and whose op+2 == 0x17), and records the
                 op+4 byte of every bundle found, in program order.
  splice_tex  -- HW construction: compile a 2-texture read kernel baseline,
                 splice ONE byte (op+4 of one bundle) to a frozen target
                 value, dispatch via texsplice, record the output word.
  splice_grad -- HW construction: compile a render (vertex+fragment)
                 gradient-differential-pair baseline, splice a frozen set of
                 byte offsets to frozen target values, dispatch via
                 gradsplice, record the readback pixel.

Clean-room: OWN-SHADER + PUBLIC (Mach-O container parsing via the project's
own agxparse.py). No Apple binary is disassembled or introspected -- every
byte inspected/spliced is the compiled form of our own MSL.
"""
import argparse, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent          # experiment root
REPO = HERE.parent.parent                                # agx-re repo root
AGXPARSE = REPO / "tools" / "shdump" / "agxparse.py"


def run_tool(cmd, timeout, cwd=None):
    return subprocess.run([str(x) for x in cmd], capture_output=True, text=True,
                           timeout=timeout, cwd=cwd)


def extract_hex(archive_path, stage=None):
    cmd = [sys.executable, str(AGXPARSE), str(archive_path), "--extract-hex"]
    if stage:
        cmd += ["--stage", stage]
    r = run_tool(cmd, 30)
    if r.returncode != 0:
        raise RuntimeError("agxparse --extract-hex failed: " + r.stderr[-500:])
    return r.stdout.strip()


def locate_main(archive_path, stage=None):
    cmd = [sys.executable, str(AGXPARSE), str(archive_path), "--locate", "_agc.main"]
    if stage:
        cmd = [sys.executable, str(AGXPARSE), str(archive_path), "--stage", stage, "--locate", "_agc.main"]
    r = run_tool(cmd, 30)
    if r.returncode != 0:
        raise RuntimeError("agxparse --locate failed: " + r.stderr[-500:])
    off, ln = r.stdout.strip().split()
    return int(off), int(ln)


def scan_read_bundles(hexstr):
    """Scan for the AGX texture 'read' two-part bundle: 4-byte companion
    (3rd byte == 0x0c) immediately followed by a 10-byte op whose byte0 has
    low nibble 0 and whose op+2 == 0x17 (2D integer-coordinate read mode,
    per experiments/EXP-0016-texture-isa/RESULTS.md sec 1/2). Returns the
    op+4 byte of every match found, in ascending file-position (== program)
    order. Pure structural pattern scan of our own extracted bytes -- no
    Apple tool or binary involved."""
    b = bytes.fromhex(hexstr)
    out = []
    for p in range(len(b) - 14):
        if b[p + 2] == 0x0c:
            op = b[p + 4:p + 14]
            if len(op) == 10 and (op[0] & 0x0F) == 0 and op[2] == 0x17:
                out.append(op[4])
    return out


def do_diff(a, work):
    kernel = REPO_REL(a["kernel_file"])
    archive = work / f"{a['case']}.bin"
    shdump = work / "bin" / "shdump"
    r = run_tool([shdump, "-o", archive, kernel], 60)
    if r.returncode != 0 or not archive.exists():
        return {"schema": 1, "family": "diff", "case": a["case"], "status": "compile_failed",
                "compiler_stdout_tail": r.stdout[-1000:], "compiler_stderr_tail": r.stderr[-1000:]}
    hexstr = extract_hex(archive)
    bundles = scan_read_bundles(hexstr)
    return {"schema": 1, "family": "diff", "case": a["case"], "status": "ok",
            "n_declared": a["n_declared"], "bundle_count": len(bundles),
            "op4_sequence": [int(x) for x in bundles],
            "nibble_sequence": [int(x) >> 4 for x in bundles],
            "distinct_nibbles": sorted(set(int(x) >> 4 for x in bundles)),
            "lownibble_all_zero": all((x & 0x0F) == 0 for x in bundles)}


def do_splice_tex(a, work):
    kernel = REPO_REL(a["kernel_file"])
    archive = work / f"{a['baseline_id']}.bin"
    shdump = work / "bin" / "shdump"
    if not archive.exists():
        r = run_tool([shdump, "-o", archive, kernel], 60)
        if r.returncode != 0 or not archive.exists():
            return {"schema": 1, "family": "splice_tex", "case": a["case"], "status": "compile_failed",
                    "compiler_stderr_tail": r.stderr[-1000:]}
    off, ln = locate_main(archive)
    data = bytearray(archive.read_bytes())
    applied = []
    for sp in a["splices"]:
        abs_off = off + sp["rel_offset"]
        before = data[abs_off]
        data[abs_off] = sp["value"]
        applied.append({"rel_offset": sp["rel_offset"], "abs_offset": abs_off,
                         "before": before, "after": sp["value"]})
    spliced_path = work / f"{a['case']}_spliced.bin"
    spliced_path.write_bytes(data)

    texsplice = work / "bin" / "texsplice"
    cmd = [texsplice, "--archive", spliced_path, "--source", kernel, "--function", a["function"],
           "--tex", f"0={a['tex0_hex']}", "--tex", f"1={a['tex1_hex']}", "--out", "0=4",
           "--timeout", str(a.get("gpu_timeout_seconds", 15))]
    try:
        r = run_tool(cmd, a.get("gpu_timeout_seconds", 15) + 10)
    except subprocess.TimeoutExpired:
        return {"schema": 1, "family": "splice_tex", "case": a["case"], "status": "process_timeout",
                "applied_splices": applied}
    lines = r.stdout.splitlines()
    status_line = next((l for l in lines if l.startswith("STATUS")), "STATUS MISSING")
    status = status_line.split(None, 1)[1] if len(status_line.split(None, 1)) > 1 else "MISSING"
    out_word = None
    for l in lines:
        if l.startswith("OUT 0 "):
            out_word = l.split()[2]
    return {"schema": 1, "family": "splice_tex", "case": a["case"],
            "status": "ok" if (r.returncode == 0 and status == "OK") else "tool_" + status.lower(),
            "tool_exit": r.returncode, "tool_status": status, "out_word_hex": out_word,
            "applied_splices": applied, "stderr_tail": r.stderr[-500:] if r.returncode != 0 else ""}


def do_splice_grad(a, work):
    kernel = REPO_REL(a["kernel_file"])
    archive = work / f"{a['baseline_id']}.bin"
    shdump = work / "bin" / "shdump"
    if not archive.exists():
        r = run_tool([shdump, "-o", archive, "--render", "--vertex", a["vertex"], "--fragment", a["fragment"], kernel], 60)
        if r.returncode != 0 or not archive.exists():
            return {"schema": 1, "family": "splice_grad", "case": a["case"], "status": "compile_failed",
                    "compiler_stderr_tail": r.stderr[-1000:]}
    off, ln = locate_main(archive, stage="fragment")
    data = bytearray(archive.read_bytes())
    applied = []
    for sp in a["splices"]:
        abs_off = off + sp["rel_offset"]
        before = data[abs_off]
        data[abs_off] = sp["value"]
        applied.append({"rel_offset": sp["rel_offset"], "abs_offset": abs_off,
                         "before": before, "after": sp["value"]})
    spliced_path = work / f"{a['case']}_spliced.bin"
    spliced_path.write_bytes(data)

    gradsplice = work / "bin" / "gradsplice"
    params = ",".join(str(x) for x in a["params"])
    cmd = [gradsplice, "--archive", spliced_path, "--source", kernel, "--vertex", a["vertex"],
           "--fragment", a["fragment"], "--params", params,
           "--timeout", str(a.get("gpu_timeout_seconds", 15))]
    try:
        r = run_tool(cmd, a.get("gpu_timeout_seconds", 15) + 10)
    except subprocess.TimeoutExpired:
        return {"schema": 1, "family": "splice_grad", "case": a["case"], "status": "process_timeout",
                "applied_splices": applied}
    lines = r.stdout.splitlines()
    status_line = next((l for l in lines if l.startswith("STATUS")), "STATUS MISSING")
    status = status_line.split(None, 1)[1] if len(status_line.split(None, 1)) > 1 else "MISSING"
    pixel = None
    for l in lines:
        if l.startswith("PIXEL"):
            pixel = l
    return {"schema": 1, "family": "splice_grad", "case": a["case"],
            "status": "ok" if (r.returncode == 0 and status == "OK") else "tool_" + status.lower(),
            "tool_exit": r.returncode, "tool_status": status, "pixel": pixel,
            "applied_splices": applied, "stderr_tail": r.stderr[-500:] if r.returncode != 0 else ""}


def REPO_REL(p):
    return HERE / p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True, choices=["diff", "splice_tex", "splice_grad"])
    ap.add_argument("--case", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--args", required=True, help="JSON blob: the full contract case record")
    args = ap.parse_args()
    a = json.loads(args.args)
    work = Path(args.work)
    if args.family == "diff":
        result = do_diff(a, work)
    elif args.family == "splice_tex":
        result = do_splice_tex(a, work)
    else:
        result = do_splice_grad(a, work)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
