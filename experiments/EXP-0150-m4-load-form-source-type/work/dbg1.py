import sys, json, os
from pathlib import Path
EXP = Path('.').resolve(); REPO = EXP.parents[1]
sys.path.insert(0, str(EXP)); sys.path.insert(0, str(REPO/'tools'/'agxtest'))
import carriers as C, sweepdefs as SD
from persistrun import PersistRunner
sys.path.insert(0, str(EXP/'harness'))
import importlib.util
spec = importlib.util.spec_from_file_location('sr', 'harness/sweeprun.py')
sr = importlib.util.module_from_spec(spec); spec.loader.exec_module(sr)

arch, off, main = sr.compile_carrier('work/bin', 'work/dbg')
print('main_len', len(main), 'off', off)
base = Path(arch).read_bytes()
work = Path('work/dbg')
ins = {}
for idx,(fn,data) in C.CARRIER['inputs'].items():
    p = work/fn; p.write_bytes(data); ins[idx]=str(p)
print('ins', ins, 'outs', C.CARRIER['outs'])
r = PersistRunner(source=str(EXP/C.CARRIER['metal']), function=C.CARRIER['func'],
                  fast_math=False, agxrun_persist='work/bin/agxrun_persist')
print('device', r.device)
ctrl = SD.build_controls()[0]['cases']
for case in ctrl[:4]:
    b = bytearray(base); prog = bytes.fromhex(case['prog'])
    b[off:off+len(prog)] = prog
    p = work/('x_%s.bin'%case['field']); p.write_bytes(bytes(b))
    resp = r.request(archive=str(p), grid=1, tg=1, ins=ins, outs=C.CARRIER['outs'], timeout=10)
    obs, m = C.summarize(resp['outs'], case['oracle']['out0'])
    print(case['field'], resp['status'], resp.get('error'), 'oracle', case['oracle']['out0'], 'obs', obs.get('head'), 'match', m)
r.close()
