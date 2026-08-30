import json, sys
db=json.load(open('tools/agx-isa/db.json'))
for ins in db['instructions']:
    if ins['mnemonic'] in sys.argv[1:]:
        print('=== %s len=%d match=%s emit_unsafe=%s' % (ins['mnemonic'], ins['length'], ins['match'], ins.get('emit_unsafe')))
        for f in ins['fields']:
            print('    %-16s start=%-3d w=%-3d type=%-7s enum=%s' % (f['name'], f['start'], f['width'], f['type'], f.get('enum','')))
