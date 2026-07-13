cd ~/cleanroom_work/EXP-M5-22
python3 - <<'PY'
import subprocess
arch="f_ab0.bin"
raw=bytearray(open(arch,"rb").read())
# unique preamble context around the index byte: 0f 00 03 00 a0 4c 00 <IDX> 41 00 80
import re
pat=bytes.fromhex("0f000300a04c00")
hits=[m.start() for m in re.finditer(re.escape(pat),raw)]
print("preamble-pattern hits:",hits)
idxpos=hits[0]+len(pat)   # the IDX byte
print("IDX file offset:",idxpos,"current=%02x"%raw[idxpos])
def run(idxbyte,label):
    d=bytearray(raw); d[idxpos]=idxbyte
    open(arch+".spliced","wb").write(d)
    r=subprocess.run(["/Users/user/cleanroom_work/EXP-M5-22/agxrender3","--archive",arch+".spliced",
        "--source","kernels/tex_bind.metal","--vertex","v_main","--fragment","f_ab0",
        "--argtex","255,0,0,255","--argtex","0,255,0,255","--argtex","0,0,255,255","--argtex","255,255,0,255"],
        capture_output=True,text=True,timeout=20)
    pix=[l for l in r.stdout.splitlines() if l.startswith("PIXEL") or l.startswith("STATUS")]
    print(f"{label}: "+" | ".join(pix))
run(0xa0,"IDX=0xa0 index0 expect RED   1,0,0")
run(0xa1,"IDX=0xa1 index1 expect GREEN 0,1,0")
run(0xa2,"IDX=0xa2 index2 expect BLUE  0,0,1")
run(0xa3,"IDX=0xa3 index3 expect YELLOW 1,1,0")
PY
