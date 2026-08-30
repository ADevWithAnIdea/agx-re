import json,sys
d=json.load(open(sys.argv[1]))
print("cases",d["cases"],"elapsed",d["elapsed_s"])
dead=[]
for k,v in sorted(d["arms"].items()):
    live=v.get("live"); 
    print("%-24s live=%-5s steps=%-3s %s" % (k,str(live),v.get("ladder_steps"),v.get("control")))
    if not live: dead.append(k)
print("DEAD ARMS:",dead)
