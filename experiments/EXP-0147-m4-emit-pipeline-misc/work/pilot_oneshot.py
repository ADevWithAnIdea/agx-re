import sys,shutil,subprocess,json,time
ARC='pilot_tb.bin'
o=subprocess.run(['python3','agxparse.py',ARC,'--stage','fragment','--locate','_agc.main'],capture_output=True,text=True).stdout.split()
fab=int(o[0])
fh=subprocess.run(['python3','agxparse.py',ARC,'--stage','fragment','--extract-hex'],capture_output=True,text=True).stdout.strip()
tro=fab+fh.find('670e54')//2
def oneshot(arc):
    req={'id':'x','archive':arc,'vs':'v_full','fs':'f_tb','w':2,'h':2,'nrt':1,
         'clear':[[0.25,0.5,-1.0,2.0]],'fbuf':[1.0,-2.0,3.0,0.5]}
    p=subprocess.run(['./rendersweep','--source','pilot_tb.metal'],input=json.dumps(req)+'\n',
                     capture_output=True,text=True,timeout=30)
    lines=[l for l in p.stdout.splitlines() if l.startswith('{')]
    return json.loads(lines[0]) if lines else {'status':'NO_OUT','err':p.stdout+p.stderr}
t0=time.monotonic()
print('base  ', oneshot(ARC).get('pixels',[None])[0])
for name,off,val in [('dst=0x02',3,0x02),('b2=0x00',2,0x00),('rt=0x01',5,0x01),('b7=0x00',7,0x00),('op=0x00',1,0x00)]:
    shutil.copyfile(ARC,'os.bin')
    with open('os.bin','r+b') as f: f.seek(tro+off); f.write(bytes([val]))
    rr=oneshot('os.bin')
    print(f'{name:10s}',rr['status'],rr.get('pixels',[None])[0],rr.get('error','')[:80])
print('elapsed',round(time.monotonic()-t0,2))
