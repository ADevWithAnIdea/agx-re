import subprocess, sys

def gen_ifnest(depth):
    name = f"ifnest_{depth:03d}"
    body = []
    for j in range(1, depth + 1):
        body.append(f"if (v > {j}) {{")
    body.append("int acc = 0;")
    body.append("for (int k = 0; k < v; k++) { acc += v; }")
    body.append("o[i] = acc;")
    for j in range(depth, 0, -1):
        body.append("} else {")
        body.append(f"o[i] = -(1000 + {j});")
        body.append("return;")
        body.append("}")
    src = "\n".join(body)
    fn = (f"kernel void {name}(device int* o [[buffer(0)]], device const int* a [[buffer(1)]], "
          f"uint i [[thread_position_in_grid]]) {{ int v = a[i];\n{src}\n}}\n")
    return name, fn

def try_compile(depth):
    name, body = gen_ifnest(depth)
    src = "#include <metal_stdlib>\nusing namespace metal;\n" + body
    path = f"work/pilot/bb_{depth}.metal"
    with open(path, "w") as f:
        f.write(src)
    r = subprocess.run(["work/bin/shdump", "-o", f"work/pilot/bb_{depth}.bin", "-f", name, path],
                        capture_output=True, text=True, timeout=60)
    ok = (r.returncode == 0)
    return ok, name, (r.stdout+r.stderr)

lo, hi = 128, 256  # lo known-ok (from EXP-0104), hi known-fail
while hi - lo > 1:
    mid = (lo+hi)//2
    ok, name, log = try_compile(mid)
    print(f"depth={mid} ok={ok}")
    if ok:
        lo = mid
    else:
        hi = mid
        print(log[-300:])
print(f"MAX_COMPILABLE={lo} FIRST_FAIL={hi}")
