def scan_vs(h,label):
    b=bytes.fromhex(h); print(f"=== {label} VS 0x57 stores ===")
    i=0
    while i<len(b)-7:
        if b[i]==0x57 and b[i+2]==0x54 and (b[i+5]&0xbf)==0x40:
            src=b[i+3]; slot=b[i+4]|((b[i+5]&1)<<8); idx=slot>>5
            kind="POSITION" if idx<4 else f"varying-slot#{idx-4}"
            print(f"  @+{i:#05x}: SRC=r{src>>1:<3d} rawSLOT=0x{slot:03x} idx={idx:2d}  {kind}")
            i+=8; continue
        i+=1
def scan_fs(h,label):
    b=bytes.fromhex(h); print(f"=== {label} FS 0x2f/0xaf iter ops ===")
    i=0
    while i<len(b)-9:
        if b[i] in (0x2f,0xaf) and b[i+2]==0x54 and b[i+4]==0x03 and b[i+7]==0x02:
            dst=b[i+3]; coef=b[i+5]|((b[i+6]&1)<<8) if False else b[i+5]; mode=b[i+6]
            print(f"  @+{i:#05x}: DST=r{dst>>1:<3d} COEF=0x{coef:02x} cidx={coef>>1:2d} mode=0x{mode:02x}")
            i+=10; continue
        i+=1
import sys
VSA="0cdd10060b0026004000000400001281218226c80722a0b00201298026c81702a0b019023c81400229003c81410200083c80233e0000000c40604ccd233e12046602408057165402004048005746540420404a0057265400404042005786540660404200570654008040450057065400a040490057065508c0404c0057065406e0404b000e000000"
FSA="2f0d5400030004021000af0054040300024820012f0554000302000210002f0554080304000210002f05540203060002100009012f85000100002f05540603080002100049092f850002000097045400020020d045c219032f850003000029073f050004000097045401020410d045c28702540006008702540c0800e70654000000014e000000000702540c02000e000000"
scan_vs(VSA,"linkA"); scan_fs(FSA,"linkA")
