#!/usr/bin/env python3
"""EXP-0176: for every missing experiment, emit a VERIFIED citation path list.

Every path printed here was checked with os.path.exists at generation time, so no
drafted row can cite an artifact that does not exist.
    python3 experiments/EXP-0176-provenance-chain/analysis/cite_paths.py
"""
import json, os
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.abspath(os.path.join(HERE,'..','..','..'))
d=json.load(open(os.path.join(HERE,'missing_rows.json')))
PREF=['RESULTS.md','report.md','README.md','QUARANTINE.md','SUPERSEDED.md','STOP.md',
      'PRE_REGISTRATION.md','CAPTURE_CONTRACT.json','manifest.json','PROGRESS.md',
      'analysis.json','analysis','raw','census','captures','hex','kernels','work']
for e in d['experiments']:
    base=os.path.join(ROOT,e['dir']); have=[]
    for f in PREF:
        p=os.path.join(base,f)
        if os.path.exists(p):
            # skip empty dirs
            if os.path.isdir(p) and not any(os.scandir(p)): 
                have.append(f+'/  [EMPTY]'); continue
            have.append(f+('/' if os.path.isdir(p) else ''))
    print("%-12s %-9s %s" % (e['id'], e['first_commit'], ', '.join(have)))
