import sys,shutil,subprocess,time
sys.path.insert(0,'.')
from rsdrv import RenderRunner
ARC='pilot_tb.bin'
o=subprocess.run(['python3','agxparse.py',ARC,'--stage','fragment','--locate','_agc.main'],capture_output=True,text=True).stdout.split()
fab=int(o[0])
fh=subprocess.run(['python3','agxparse.py',ARC,'--stage','fragment','--extract-hex'],capture_output=True,text=True).stdout.strip()
tro=fab+fh.find('670e54')//2
r=RenderRunner('pilot_tb.metal')
def go(rid,arc):
    return r.request({'id':rid,'archive':arc,'vs':'v_full','fs':'f_tb','w':2,'h':2,'nrt':1,
                      'clear':[[0.25,0.5,-1.0,2.0]],'fbuf':[1.0,-2.0,3.0,0.5]})
print('base', go('b',ARC).get('pixels',[None])[0])
t0=time.monotonic()
for i,(name,off,val) in enumerate([('dst=0x02',3,0x02),('b7=0x00',7,0x00),('op=0x00',1,0x00)]):
    p=f'uniq_{i}.bin'; shutil.copyfile(ARC,p)
    with open(p,'r+b') as f: f.seek(tro+off); f.write(bytes([val]))
    rr=go('u%d'%i,p)
    print(f'{name:10s}',rr['status'],rr.get('pixels',[None])[0])
print('elapsed',round(time.monotonic()-t0,3))
r.close()
