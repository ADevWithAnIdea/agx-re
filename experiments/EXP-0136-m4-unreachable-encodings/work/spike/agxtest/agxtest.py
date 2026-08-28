#!/usr/bin/env python3
# agxtest.py — clean-room OWN-SHADER hardware round-trip driver (EXP-0003).
#
# The "give me bytes + inputs -> outputs" engine. It:
#   1. compiles OUR OWN MSL to a serialized Metal binary archive (via shdump),
#   2. locates the _agc.main region inside that archive file (via agxparse),
#   3. optionally SPLICES caller-supplied bytes into _agc.main in place,
#   4. writes the input buffers, forces the GPU to run the (possibly spliced)
#      archived machine code (via agxrun), and reads back the output buffers,
#   5. compares against an expected result if one was given.
#
# CLEAN-ROOM: every byte inspected/modified is the compiled form of OUR OWN MSL.
# No Apple binary is disassembled or introspected. shdump/agxparse/agxrun are our
# own tools; the splice-and-reload technique is the public MIT applegpu hwtestbed
# method, reimplemented here.
#
# Runs ON THE DEVICE (needs Metal). Example:
#   python3 agxtest.py --source add.metal --function k --grid 8 --tg 8 \
#       --buf 0=1,2,3,4,5,6,7,8 --buf 1=10,20,30,40,50,60,70,80 --out 2=8
#
# Splice example (flip float op-select 1c->1d at offset 0x22 of _agc.main):
#   ... --splice _agc.main@0x22=1d

import argparse
import os
import struct
import subprocess
import sys
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def compile_archive(shdump, source, function, fast_math, out_path):
    """Compile OUR MSL to a serialized binary archive via shdump."""
    cmd = [shdump, "-o", out_path]
    if function:
        cmd += ["-f", function]
    if not fast_math:
        cmd += ["--no-fast-math"]
    cmd += [source]
    r = sh(cmd)
    if r.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError(f"shdump failed:\n{r.stderr}")
    return r.stderr


def load_agxparse(agxparse_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("agxparse", agxparse_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_buf(spec, as_int):
    """'IDX=1,2,3' or 'IDX=@file' -> (index, raw_bytes)."""
    idx, _, val = spec.partition("=")
    idx = int(idx, 0)
    if val.startswith("@"):
        with open(val[1:], "rb") as f:
            return idx, f.read()
    data = bytearray()
    for tok in val.split(","):
        tok = tok.strip()
        if tok == "":
            continue
        if as_int:
            data += struct.pack("<i", int(tok, 0))
        else:
            data += struct.pack("<f", float(tok))
    return idx, bytes(data)


def parse_out(spec):
    """'IDX=N' -> (index, n_elements)."""
    idx, _, n = spec.partition("=")
    return int(idx, 0), int(n, 0)


def apply_splices(buf, splices, agxparse, symbol_default="_agc.main"):
    """splices: list of 'SYM@OFF=HEX'. Returns (new_buf, notes)."""
    b = bytearray(buf)
    notes = []
    for sp in splices:
        left, _, hexbytes = sp.partition("=")
        if "@" in left:
            sym, _, off = left.partition("@")
        else:
            sym, off = symbol_default, left
        sym = sym or symbol_default
        off = int(off, 0)
        newbytes = bytes.fromhex(hexbytes)
        loc = agxparse.locate_region(bytes(b), sym)
        if loc is None:
            raise RuntimeError(f"could not locate symbol region {sym!r}")
        base, length = loc
        if off + len(newbytes) > length:
            raise RuntimeError(
                f"splice {sym}@{off:#x} len {len(newbytes)} exceeds region length {length}")
        abs_off = base + off
        old = bytes(b[abs_off:abs_off + len(newbytes)])
        b[abs_off:abs_off + len(newbytes)] = newbytes
        notes.append(f"{sym}@{off:#04x}: {old.hex()} -> {newbytes.hex()} "
                     f"(abs file offset {abs_off})")
    return bytes(b), notes


def fmt_buffer(raw, as_int):
    vals = []
    for i in range(0, len(raw) - 3, 4):
        (u,) = struct.unpack_from("<I", raw, i)
        if as_int:
            (s,) = struct.unpack_from("<i", raw, i)
            vals.append(str(s))
        else:
            (f,) = struct.unpack_from("<f", raw, i)
            vals.append(f"{f:g}")
    return vals


def main():
    ap = argparse.ArgumentParser(description="AGX hardware round-trip driver")
    ap.add_argument("--source", required=True, help="OUR MSL source file")
    ap.add_argument("--function", default=None, help="kernel function name")
    ap.add_argument("--no-fast-math", action="store_true")
    ap.add_argument("--grid", type=int, default=1)
    ap.add_argument("--tg", type=int, default=1)
    ap.add_argument("--buf", action="append", default=[], help="IDX=csv or IDX=@file")
    ap.add_argument("--out", action="append", default=[], help="IDX=NELEMENTS")
    ap.add_argument("--expect", action="append", default=[],
                    help="IDX=csv expected result (compared to output)")
    ap.add_argument("--int", dest="as_int", action="store_true",
                    help="treat buffers as int32 (default float32)")
    ap.add_argument("--splice", action="append", default=[],
                    help="SYM@OFF=HEX splice into _agc.main region (repeatable)")
    ap.add_argument("--dump-main", action="store_true",
                    help="print _agc.main hex before and after splicing")
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--archive", default=None, help="archive path (default derived)")
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--run-timeout", type=float, default=25.0)
    ap.add_argument("--shdump", default=os.path.join(HERE, "shdump"))
    ap.add_argument("--agxrun", default=os.path.join(HERE, "agxrun"))
    ap.add_argument("--agxparse", default=os.path.join(HERE, "agxparse.py"))
    args = ap.parse_args()

    os.makedirs(args.workdir, exist_ok=True)
    agxparse = load_agxparse(args.agxparse)
    fast_math = not args.no_fast_math

    # 1. Compile OUR source -> archive (cache by source+opts hash).
    with open(args.source, "rb") as f:
        src_bytes = f.read()
    tag = hashlib.sha256(src_bytes + str(fast_math).encode() +
                         (args.function or "").encode()).hexdigest()[:12]
    base_archive = args.archive or os.path.join(args.workdir, f"arch_{tag}.bin")
    if args.rebuild or not os.path.exists(base_archive):
        meta = compile_archive(args.shdump, args.source, args.function,
                               fast_math, base_archive)
        sys.stderr.write(meta)

    with open(base_archive, "rb") as f:
        buf = f.read()

    # Report the pristine _agc.main.
    _, pieces = agxparse.extract_agx(buf)
    main_bytes = pieces.get("_agc.main") if pieces else None
    if main_bytes is None:
        print("STATUS EXTRACT_FAIL")
        print("ERROR could not extract _agc.main from archive")
        sys.exit(2)
    print(f"MAIN_LEN {len(main_bytes)}")
    if args.dump_main:
        print(f"MAIN_ORIG {main_bytes.hex()}")

    # 2/3. Splice if requested, write the run archive.
    run_archive = base_archive
    if args.splice:
        spliced, notes = apply_splices(buf, args.splice, agxparse)
        for n in notes:
            print(f"SPLICE {n}")
        run_archive = os.path.join(args.workdir, f"arch_{tag}_spliced.bin")
        with open(run_archive, "wb") as f:
            f.write(spliced)
        _, sp_pieces = agxparse.extract_agx(spliced)
        if args.dump_main and sp_pieces:
            print(f"MAIN_SPLICED {sp_pieces['_agc.main'].hex()}")

    # 4. Write input buffers to files; assemble agxrun command.
    cmd = [args.agxrun, "--archive", run_archive, "--source", args.source,
           "--function", args.function or "k",
           "--grid", str(args.grid), "--tg", str(args.tg)]
    if not fast_math:
        cmd += ["--no-fast-math"]
    for spec in args.buf:
        idx, raw = parse_buf(spec, args.as_int)
        bpath = os.path.join(args.workdir, f"in_{idx}.bin")
        with open(bpath, "wb") as f:
            f.write(raw)
        cmd += ["--buf", f"{idx}={bpath}"]
    out_specs = [parse_out(s) for s in args.out]
    for idx, nel in out_specs:
        cmd += ["--out", f"{idx}={nel * 4}"]

    # 5. Run under a hard timeout so a wedged GPU can't hang the whole session.
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=args.run_timeout)
    except subprocess.TimeoutExpired:
        print("STATUS HANG")
        print(f"ERROR agxrun exceeded {args.run_timeout}s (GPU likely wedged) -- "
              f"reboot the device and retry")
        sys.exit(3)

    # Relay agxrun output, and parse OUT lines.
    outs = {}
    status = "UNKNOWN"
    for line in r.stdout.splitlines():
        print(line)
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1]
        elif line.startswith("OUT "):
            _, idx, hexbytes = line.split(None, 2)
            outs[int(idx)] = bytes.fromhex(hexbytes)
    if r.stderr.strip():
        sys.stderr.write(r.stderr)

    if status != "OK":
        sys.exit(1)

    # Decode outputs to numbers.
    for idx, nel in out_specs:
        raw = outs.get(idx, b"")
        vals = fmt_buffer(raw, args.as_int)
        print(f"RESULT {idx} {' '.join(vals)}")

    # 6. Compare against expected, if given.
    ok = True
    for spec in args.expect:
        idx, _, val = spec.partition("=")
        idx = int(idx, 0)
        exp = [t.strip() for t in val.split(",") if t.strip() != ""]
        raw = outs.get(idx, b"")
        got = fmt_buffer(raw, args.as_int)[:len(exp)]
        # numeric compare with tolerance for floats
        match = True
        for a, b in zip(exp, got):
            if args.as_int:
                if int(a, 0) != int(b):
                    match = False
            else:
                if abs(float(a) - float(b)) > 1e-4 * max(1.0, abs(float(a))):
                    match = False
        print(f"EXPECT {idx} {' '.join(exp)}")
        print(f"COMPARE {idx} {'MATCH' if match else 'MISMATCH'}")
        ok = ok and match
    if args.expect and not ok:
        sys.exit(4)


if __name__ == "__main__":
    main()
