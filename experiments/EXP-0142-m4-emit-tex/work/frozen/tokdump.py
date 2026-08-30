import sys, subprocess, json, os
REPO=os.path.abspath('../../../..')
sys.path.insert(0,os.path.join(REPO,'tools','agx-isa')); import isadb
AGXPARSE=os.path.join(REPO,'tools','shdump','agxparse.py')
arch=sys.argv[1]; stage=sys.argv[2] if len(sys.argv)>2 else None
cmd=['python3',AGXPARSE,arch]
if stage: cmd += ['--stage',stage]
cmd += ['--locate','_agc.main']
loc=subprocess.check_output(cmd).decode().split()
ABS,LEN=int(loc[0]),int(loc[1])
b=open(arch,'rb').read()[ABS:ABS+LEN]
print("# ABS=%d LEN=%d"%(ABS,LEN))
off=0
while off<len(b):
    try: L=isadb.instr_length(b,off)
    except Exception as e: print("%04x LENFAIL %s"%(off,e)); break
    if not L: print("%04x LEN0 %s"%(off,b[off:off+8].hex())); break
    try: d,_=isadb.decode_one(b,off)
    except Exception: d=None
    m=d['mnemonic'] if d else '?'
    print("%04x  %-20s %-36s %s"%(off,m,b[off:off+L].hex(), json.dumps(d.get('fields')) if d and d.get('fields') else ''))
    off+=L
