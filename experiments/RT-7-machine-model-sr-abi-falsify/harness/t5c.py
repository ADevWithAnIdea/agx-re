import os,sys,subprocess,struct,importlib.util,shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE); from persistrun import PersistRunner
arch=os.path.join(HERE,"srb.bin"); buf=open(arch,"rb").read(); _,p=ap.extract_agx(buf); main=p["_agc.main"]
loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
abs1=int(loc[0])+0+1  # value get_sr at off 0
r=PersistRunner(source=os.path.join(HERE,"kernels","srb.metal"),function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
for code,nm in [(0x98,"threads_per_tg"),(0xa8,"threadgroups_per_grid"),(0x99,"tptg.y"),(0xa9,"tgpg.y"),(0x9a,"tptg.z"),(0xaa,"tgpg.z")]:
  for grid,tg in [(256,64),(128,32),(192,64)]:
    spa=os.path.join(HERE,"srb_sp.bin"); shutil.copyfile(arch,spa)
    open(spa,"r+b").close()
    with open(spa,"r+b") as f: f.seek(abs1); f.write(bytes([code]))
    resp=r.request(archive=spa,grid=grid,tg=tg,ins={},outs={0:grid*4},timeout=8)
    if resp["status"]!="OK": print("%s 0x%02x grid=%d tg=%d -> %s"%(nm,code,grid,tg,resp["status"])); continue
    v=[struct.unpack_from('<I',resp["outs"][0],4*g)[0] for g in range(min(grid,8))]
    allsame = len(set(struct.unpack_from('<I',resp["outs"][0],4*g)[0] for g in range(grid)))==1
    print("%-22s 0x%02x grid=%-4d tg=%-3d -> out[0:8]=%s allsame=%s (expect tptg=%d, tgpg=%d)"%(nm,code,grid,tg,v,allsame,tg,grid//tg))
r.close()
