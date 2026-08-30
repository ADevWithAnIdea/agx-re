import json,sys,os
ROOT="/Users/user/asahi_re/public/agx-re"
db=json.load(open(os.path.join(ROOT,"tools/agx-isa/db.json")))
val=json.load(open(os.path.join(ROOT,"tools/agx-isa/validation.json")))
targets=sys.argv[1:]
for i in db["instructions"]:
    m=i["mnemonic"]
    if targets and m not in targets: continue
    print("="*70)
    print(json.dumps(i,indent=1))
    v=val["instructions"].get(m,{})
    print("-- validation --")
    print(json.dumps(v,indent=1))
