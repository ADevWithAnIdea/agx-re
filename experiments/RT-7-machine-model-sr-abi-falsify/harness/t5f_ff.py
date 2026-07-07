import os,sys,subprocess,importlib.util,shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
MSL=("#include <metal_stdlib>\nusing namespace metal;\n"
 "struct VO{float4 p [[position]];};\n"
 "vertex VO vmain(uint vid [[vertex_id]]){float2 q=float2(float((vid<<1)&2),float(vid&2));VO o;o.p=float4(q*2.0-1.0,0.0,1.0);return o;}\n"
 "fragment float4 fmain(bool ff [[front_facing]]){return float4(ff?0.75:0.25,0,0,1);}\n")
kp=os.path.join(HERE,"kernels","ff_cov.metal"); open(kp,"w").write(MSL)
arch=os.path.join(HERE,"ff_cov.bin")
subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"--render","--vertex","vmain","--fragment","fmain",kp],capture_output=True)
def px(a):
    o=subprocess.run([os.path.join(HERE,"agxrender"),"--archive",a,"--source",kp,"--vertex","vmain","--fragment","fmain","--width","2","--height","2"],capture_output=True,text=True).stdout
    for ln in o.splitlines():
        if ln.startswith("PIXEL 1 1"): return ln
    return "no-pixel"
print("BASELINE (front_facing):",px(arch))
# locate FS get_sr (c5) and splice byte1 -> 0x82 (lane, should read helper/lane => change pixel)
buf=open(arch,"rb").read()
hx=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","fragment","--extract-hex","--symbol","_agc.main"],capture_output=True,text=True).stdout.strip().replace(" ","").replace("\n","")
main=bytes.fromhex(hx)
# find get_sr c5
i=0;off=None
while i+4<=len(main):
    if (main[i]&0x07)==0x04 and main[i+1]==0xc5 and main[i+3]==0x06: off=i; break
    if main[i] in (0x67,0xe7): i+=14
    elif main[i]==0x0e: i+=4
    else: i+=2
print("FS get_sr c5 off:",off)
loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","fragment","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
abs1=int(loc[0])+off+1
for code,nm in [(0x82,"simd_lane"),(0xa0,"pos.x")]:
    spa=os.path.join(HERE,"ff_sp.bin"); shutil.copyfile(arch,spa)
    with open(spa,"r+b") as f: f.seek(abs1); f.write(bytes([code]))
    print("SPLICE c5->0x%02x (%s):"%(code,nm),px(spa))
