#!/usr/bin/env python3
"""Compile OWN-MSL archives and report per-stage GPU metadata without retaining archives."""
import argparse
import importlib.util
import json
import hashlib
import struct
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SHDUMP_SRC = REPO / "tools/shdump/shdump.m"
AGXPARSE = REPO / "tools/shdump/agxparse.py"

spec = importlib.util.spec_from_file_location("agxparse", AGXPARSE)
ap = importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

def fields(buf, tpos):
    vt = tpos - struct.unpack_from('<i', buf, tpos)[0]
    nf = (struct.unpack_from('<H', buf, vt)[0] - 4) // 2
    ans = {}
    for i in range(nf):
        off = struct.unpack_from('<H', buf, vt + 4 + i * 2)[0]
        if off: ans[i] = tpos + off
    return ans

def stage_metadata(blob, stage):
    outer = None
    for off, _, _ in ap.iter_gpu_images(blob):
        try:
            candidate = ap.MachO(blob, off)
        except ValueError:
            # Metal archives may include non-Mach-O wrapper/index images.
            continue
        if candidate.cputype == ap.APPLE_GPU_CPUTYPE: outer = candidate; break
    if outer is None:
        raise ValueError("archive contains no AppleGPU Mach-O image")
    section = outer.find_section("__TEXT", "__" + stage)
    base = outer.base + section["offset"]
    nested = ap.MachO(blob, base)
    meta = None
    for sec in nested.sections:
        if sec["seg"] == "__GPU_METADATA":
            meta = blob[base + sec["offset"]:base + sec["offset"] + sec["size"]]
    root = struct.unpack_from('<I', meta, 0)[0]
    rf = fields(meta, root)
    subpos = rf[0] + struct.unpack_from('<I', meta, rf[0])[0]
    sf = fields(meta, subpos)
    vals = {str(i): struct.unpack_from('<I', meta, p)[0] for i, p in sf.items() if p + 4 <= len(meta)}
    return {"gpr_field_0": vals.get("0", 0), "scratch_field_41_or_14": vals.get("41", vals.get("14", 0)),
            "all_u32_fields": vals}

def main():
    p = argparse.ArgumentParser(); p.add_argument("--source", required=True); p.add_argument("--stage", choices=("cs","vs","fs"), required=True)
    p.add_argument("--code-dir", help="save only _agc.main bytes compiled from the authored source")
    a = p.parse_args(); source = Path(a.source).resolve()
    with tempfile.TemporaryDirectory(prefix="exp0041-") as td:
        td = Path(td); shdump = td / "shdump"; archive = td / "own_shader.bin"
        subprocess.run(["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation", "-o", shdump, SHDUMP_SRC], check=True, timeout=30)
        if a.stage == "cs": cmd = [shdump, "-o", archive, "-f", "k_main", "--no-fast-math", source]
        else: cmd = [shdump, "-o", archive, "--render", "--vertex", "v_main", "--fragment", "f_main", "--no-fast-math", source]
        cp = subprocess.run(cmd, text=True, capture_output=True, timeout=60)
        if cp.returncode: raise SystemExit(cp.stderr)
        blob = archive.read_bytes(); stages = ["compute"] if a.stage == "cs" else ["vertex", "fragment"]
        code_manifest = {}
        if a.code_dir:
            code_dir = Path(a.code_dir); code_dir.mkdir(parents=True, exist_ok=False)
            _, code_stages = ap.extract_all_stages(blob)
            for s in stages:
                main = code_stages[s].get("_agc.main", b"")
                path = code_dir / f"{s}_agc_main.hex"
                path.write_text(main.hex() + "\n")
                code_manifest[s] = {"path": str(path), "bytes": len(main), "sha256": hashlib.sha256(main).hexdigest(),
                                    "provenance": "compiled _agc.main from the named authored source"}
        print(json.dumps({"source": str(source.relative_to(REPO)), "archive_retained": False,
                          "compiler_stderr": cp.stderr.splitlines(),
                          "own_main_code": code_manifest,
                          "stages": {s: stage_metadata(blob, s) for s in stages}}, sort_keys=True))
if __name__ == "__main__": main()
