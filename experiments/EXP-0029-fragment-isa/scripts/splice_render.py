#!/usr/bin/env python3
# Device-side: splice byte(s) into the fragment (or vertex) _agc.main of a render
# archive and render it, printing the pixels. Reuses agxparse --locate + agxrender.
import subprocess, sys, os, shutil

def locate(archive, stage, sym="_agc.main"):
    out = subprocess.check_output(["python3", "agxparse.py", archive, "--stage", stage,
                                   "--locate", sym]).decode().split()
    return int(out[0]), int(out[1])   # abs_off, len

def main():
    # args: archive source vfn ffn W H stage off=hex[,off=hex...]  [--tex-fill r,g,b,a]
    archive, source, vfn, ffn, W, H, stage, splices = sys.argv[1:9]
    extra = sys.argv[9:]
    abs_off, length = locate(archive, stage)
    spliced = archive + ".spliced"
    shutil.copyfile(archive, spliced)
    with open(spliced, "r+b") as f:
        data = bytearray(f.read())
        for sp in splices.split(","):
            off, hexv = sp.split("=")
            off = int(off, 0); b = bytes.fromhex(hexv)
            assert off + len(b) <= length, "splice out of _agc.main region"
            data[abs_off+off:abs_off+off+len(b)] = b
        f.seek(0); f.write(data)
    cmd = ["./agxrender", "--archive", spliced, "--source", source,
           "--vertex", vfn, "--fragment", ffn, "--width", W, "--height", H] + extra
    r = subprocess.run(cmd, capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith(("STATUS","PIPELINE_SOURCE","PIXEL","ERROR")):
            print(line)

if __name__ == "__main__":
    main()
