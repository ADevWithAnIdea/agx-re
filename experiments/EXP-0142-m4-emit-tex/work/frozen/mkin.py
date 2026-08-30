import struct, sys
# Compute carriers: 64 floats per thread (grid=1 thread).
v=[0.0]*64
# 8 sample coordinate pairs, pixel coords: sample j reads texel (j+1, j)
for j in range(8):
    v[2*j]   = j + 1.5     # x -> texel j+1
    v[2*j+1] = j + 0.5     # y -> texel j
# tex_write3 colours (in[0..11]) -- overwritten below for carrier B
v[63] = 12345.0            # integrity sentinel
open('inA.bin','wb').write(struct.pack('<64f',*v))
w=[0.0]*64
for i in range(12): w[i] = 11.0*(i+1)      # 11,22,...,132  all distinct, non-zero
w[63] = 12345.0
open('inB.bin','wb').write(struct.pack('<64f',*w))
# render carrier: A,B,C,D, W,H, _, s0, s1
r=[0.0]*16
r[0],r[1],r[2],r[3] = 1.0, 2.0, 4.0, 8.0   # dfdx(u),dfdy(u),dfdx(v),dfdy(v)
r[4],r[5] = 4.0, 4.0                        # viewport W,H
r[7],r[8] = 1.5, 2.0                        # sentinel S = 3.0
open('inC.bin','wb').write(struct.pack('<16f',*r))
print("wrote inA.bin inB.bin inC.bin")
