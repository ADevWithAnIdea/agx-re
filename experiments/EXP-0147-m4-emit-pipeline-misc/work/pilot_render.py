import sys,shutil,subprocess,time,json
sys.path.insert(0,'.')
from rsdrv import RenderRunner
def locate(arc,stage):
    o=subprocess.run(['python3','agxparse.py',arc,'--stage',stage,'--locate','_agc.main'],capture_output=True,text=True).stdout.split()
    return int(o[0]),int(o[1])
def hexof(arc,stage):
    return subprocess.run(['python3','agxparse.py',arc,'--stage',stage,'--extract-hex'],capture_output=True,text=True).stdout.strip()
ARC='pilot_tb.bin'
fab,flen=locate(ARC,'fragment'); fh=hexof(ARC,'fragment')
tr=fh.find('670e54'); print('tile_read at main offset',tr//2,'abs',fab+tr//2)
r=RenderRunner('pilot_tb.metal')
print('device',r.device)
def go(rid,arc,dst,src,w=2,h=2):
    return r.request({'id':rid,'archive':arc,'vs':'v_full','fs':'f_tb','w':w,'h':h,'nrt':1,
                      'clear':[list(dst)],'fbuf':list(src)})
t0=time.monotonic()
b1=go('b1',ARC,(0.25,0.5,-1.0,2.0),(1.0,-2.0,3.0,0.5))
b2=go('b2',ARC,(0.0,0.0,0.0,0.0),(1.0,-2.0,3.0,0.5))
print('base dst=(.25,.5,-1,2):',b1.get('pixels',[None])[0], b1['status'])
print('base dst=0        :',b2.get('pixels',[None])[0])
# splice tile_read dst byte (+3) -> 0x40
tro=fab+tr//2
for name,off,val in [('dst=0x02',3,0x02),('b2=0x00',2,0x00),('rt=0x01',5,0x01),('b7=0x00',7,0x00)]:
    shutil.copyfile(ARC,'rs.bin')
    with open('rs.bin','r+b') as f: f.seek(tro+off); f.write(bytes([val]))
    rr=go('s_'+name,'rs.bin',(0.25,0.5,-1.0,2.0),(1.0,-2.0,3.0,0.5))
    print(f'{name:10s}', rr['status'], rr.get('pixels',[None])[0], rr.get('error',''))
# repeat baseline to prove no stickiness
b3=go('b3',ARC,(0.25,0.5,-1.0,2.0),(1.0,-2.0,3.0,0.5))
print('baseline repeat  :',b3.get('pixels',[None])[0])
print('elapsed',round(time.monotonic()-t0,3),'for 7 render reqs')
r.close()
