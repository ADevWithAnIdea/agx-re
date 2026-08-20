#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
from make_manifest import check,expected
HERE=Path(__file__).resolve().parent
check();m=json.loads((HERE/'manifest.json').read_text()); got={x['path']:x for x in m['artifacts']}; assert set(got)==expected()
for rel,x in got.items():
 p=HERE/rel;assert p.is_file() and not p.is_symlink() and p.stat().st_size==x['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256']
a=json.loads((HERE/'analysis.json').read_text());assert a['repeat_exact'] is True
print('PASS runs=2 cases=6 full_render=384 full_compute=144 exact_repeat=1')
