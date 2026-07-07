#!/usr/bin/env python3
# EXP-0037 vertex/varying splice-and-render helper (device-side).
# Copies an archive, splices bytes at an ABSOLUTE file offset, runs agxrender,
# and prints a compact per-pixel RGBA summary. CLEAN-ROOM: our own archive only.
import sys, os, subprocess, argparse, tempfile

def render(arch, src, v, f, w, h, tex=None):
    cmd = ['./agxrender','--archive',arch,'--source',src,'--vertex',v,'--fragment',f,
           '--width',str(w),'--height',str(h)]
    if tex: cmd += ['--tex-fill',tex]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=40).stdout
    px=[]; status='?'
    for line in out.splitlines():
        if line.startswith('PIXEL'):
            px.append(line.split('rgba_unorm=')[1])
        if line.startswith('STATUS'): status=line.split()[1]
    return status, px

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--archive',required=True)
    ap.add_argument('--source',required=True)
    ap.add_argument('--vertex',required=True)
    ap.add_argument('--fragment',required=True)
    ap.add_argument('--width',type=int,default=4)
    ap.add_argument('--height',type=int,default=4)
    ap.add_argument('--tex')
    # splices: repeated OFF=HEX (absolute file offset)
    ap.add_argument('--splice',action='append',default=[])
    ap.add_argument('--label',default='')
    a=ap.parse_args()
    with open(a.archive,'rb') as fh: buf=bytearray(fh.read())
    desc=[]
    for sp in a.splice:
        off,hx=sp.split('=')
        off=int(off,0); data=bytes.fromhex(hx)
        buf[off:off+len(data)]=data
        desc.append(f'@{off}={hx}')
    tf=tempfile.NamedTemporaryFile(suffix='.bin',delete=False,dir='.')
    tf.write(buf); tf.close()
    try:
        st,px=render(tf.name,a.source,a.vertex,a.fragment,a.width,a.height,a.tex)
    finally:
        os.unlink(tf.name)
    print(f'{a.label:20s} [{",".join(desc) or "baseline"}] STATUS {st}')
    # print corner pixels only for compactness: TL, TR, BL, BR + center
    if px:
        w,h=a.width,a.height
        def P(x,y): return px[y*w+x]
        print(f'   TL(0,0)={P(0,0)}  TR({w-1},0)={P(w-1,0)}')
        print(f'   BL(0,{h-1})={P(0,h-1)}  BR({w-1},{h-1})={P(w-1,h-1)}')
if __name__=='__main__': main()
