"""EXP-0141 PILOT: verify every carrier's HOST-COMPUTED oracle against the
UNSPLICED compiled kernel. work/ scratch, not evidence."""
import subprocess, sys
from pathlib import Path
EXP = Path(__file__).resolve().parent.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP)); sys.path.insert(0, str(REPO/'tools'/'agxtest'))
import carriers as C
from persistrun import PersistRunner
BIN = EXP/'work'/'pilot_bin'; W = EXP/'work'/'pilotin'; W.mkdir(exist_ok=True)
for name, spec in C.CARRIERS.items():
    arch = EXP/'work'/('pc_%s.bin'%name)
    subprocess.run([str(BIN/'shdump'), '-o', str(arch), '--no-fast-math',
                    str(EXP/spec['metal']), '-f', spec['func']], check=True,
                   capture_output=True)
    ins = {}
    for idx,(fn,data) in spec['inputs'].items():
        p = W/fn; p.write_bytes(data); ins[idx]=str(p)
    r = PersistRunner(source=str(EXP/spec['metal']), function=spec['func'],
                      fast_math=False, agxrun_persist=str(BIN/'agxrun_persist'))
    try:
        resp = r.request(archive=str(arch), grid=spec['grid'], tg=spec['tg'],
                         ins=ins, outs=spec['outs'], timeout=20)
        if spec['oracle'] is None:
            print('%-9s status=%s (synth carrier, no unspliced oracle) outs=%s'
                  % (name, resp['status'], {k: C.decode(name,k,v)[:4] for k,v in resp['outs'].items()}))
        else:
            obs, m = C.summarize(name, resp['outs'])
            print('%-9s status=%-4s MATCH=%s  %s' % (name, resp['status'], m, obs))
    finally:
        r.close()
