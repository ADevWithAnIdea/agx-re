import json, collections, sys
runs=['g17p_quiet03','g17p_quiet04','g17p_20260830_run03','g17p_20260830_run04']
SUB={24:'rot_dst',32:'op_enable',40:'rot_src',48:'operands(b6)',56:'amt_tail'}
rows=collections.defaultdict(list)
for run in runs:
    for L in open('raw/%s/sweep.jsonl'%run):
        r=json.loads(L)
        if r.get('instr')!='irotate' or r.get('role')!='target': continue
        if r.get('width')!=8: continue
        r['_run']=run; rows[(r['start'],r['arm'])].append(r)
for (st,arm) in sorted(rows):
    rs=rows[(st,arm)]
    runsseen=sorted(set(r['_run'] for r in rs))
    per=collections.defaultdict(list)
    for r in rs: per[r['_run']].append(r)
    print("### %-14s start=%d arm=%s runs=%s" % (SUB.get(st,'?'), st, arm, runsseen))
    for run in runsseen:
        q=per[run]
        vals=set(r['value'] for r in q)
        dec=set(r.get('decoded_actual') for r in q)
        ab=set(r.get('actual_bytes') for r in q)
        led=sum(1 for r in q if r.get('ledger_ok'))
        ledmis=sum(1 for r in q if r.get('ledger_ok') is False)
        sc=sum(1 for r in q if r.get('sem_checked'))
        sm=sum(1 for r in q if r.get('sem_match'))
        rules=collections.Counter((r.get('oracle') or {}).get('rule') for r in q)
        cls=collections.Counter((r.get('oracle') or {}).get('class') for r in q)
        out=collections.Counter(r['outcome'] for r in q)
        print("   %-22s n=%-4d vals=%-4d decoded=%-4d actual_enc=%-4d ledger_ok=%-4d ledger_bad=%d sem_checked=%-4d sem_match=%-4d" %
              (run,len(q),len(vals),len(dec),len(ab),led,ledmis,sc,sm))
        print("        rules=%s oracle_class=%s" % (dict(rules),dict(cls)))
        print("        outcomes=%s" % dict(out))
    print()
