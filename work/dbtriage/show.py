import json, sys
db=json.load(open('tools/agx-isa/db.json'))
names=sys.argv[1:]
for ins in db['instructions']:
    if ins['mnemonic'] in names:
        print(json.dumps(ins, indent=1))
        print('---')
