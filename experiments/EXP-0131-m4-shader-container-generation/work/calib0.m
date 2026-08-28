// calib0.m -- INFORMAL CALIBRATION ONLY (disclosed in PROGRESS.md), not evidence.
// Checks: does the live code BO (0x10000000000 family) contain our compiled
// render_min fragment main bytes, and is the BODUMP cpu= pointer directly
// writable from this same process (mirrors EXP-0116's calibration finding for
// CDM segment BOs, but this is a fresh check for the CODE BO specifically).
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <dirent.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>

static const char *RENDER_MIN_SRC =
"#include <metal_stdlib>\n"
"using namespace metal;\n"
"struct VOut { float4 pos [[position]]; };\n"
"vertex VOut v_main(uint vid [[vertex_id]]) {\n"
"  float2 p = float2(float((vid << 1) & 2), float(vid & 2));\n"
"  VOut o; o.pos = float4(p * 2.0 - 1.0, 0.0, 1.0); return o;\n"
"}\n"
"fragment float4 f_main() { return float4(1.0, 0.5, 0.25, 1.0); }\n";

typedef struct { char path[1024]; uint64_t gpu_va, cpu, size, read_len; uint8_t *data; } BODump;
static int hexval(char c){ if(c>='0'&&c<='9')return c-'0'; if(c>='a'&&c<='f')return c-'a'+10; if(c>='A'&&c<='F')return c-'A'+10; return -1; }
static int load_one(const char *path, BODump *out){
    FILE *f=fopen(path,"r"); if(!f) return 0;
    char line[8192];
    if(!fgets(line,sizeof(line),f)){fclose(f);return 0;}
    unsigned long long gpu_va=0,cpu=0,size=0,read_len=0; char *p;
    if((p=strstr(line,"gpu_va=0x"))) gpu_va=strtoull(p+9,NULL,16);
    if((p=strstr(line,"cpu=0x"))) cpu=strtoull(p+6,NULL,16);
    if((p=strstr(line,"size=0x"))) size=strtoull(p+7,NULL,16);
    if((p=strstr(line,"read=0x"))) read_len=strtoull(p+7,NULL,16);
    if(read_len==0){fclose(f);return 0;}
    uint8_t *buf=calloc(1,read_len);
    while(fgets(line,sizeof(line),f)){
        char *colon=strchr(line,':'); if(!colon) continue;
        unsigned long long off=strtoull(line,NULL,16);
        const char *q=colon+1; uint64_t idx=off;
        while(*q){ while(*q==' ')q++; int h1=hexval(*q); if(h1<0) break; q++; int h2=hexval(*q); if(h2<0) break; q++;
            if(idx<read_len) buf[idx]=(uint8_t)((h1<<4)|h2); idx++; }
    }
    fclose(f);
    strncpy(out->path,path,sizeof(out->path)-1);
    out->gpu_va=gpu_va; out->cpu=cpu; out->size=size; out->read_len=read_len; out->data=buf;
    return 1;
}
#define MAXD 256
static int load_all(const char *dir, BODump *out, int max){
    DIR *d=opendir(dir); if(!d) return 0;
    struct dirent *e; int n=0;
    while((e=readdir(d))!=NULL && n<max){
        if(strncmp(e->d_name,"bo_",3)!=0) continue;
        size_t l=strlen(e->d_name);
        if(l<4 || strcmp(e->d_name+l-4,".hex")!=0) continue;
        char path[1200]; snprintf(path,sizeof(path),"%s/%s",dir,e->d_name);
        if(load_one(path,&out[n])) n++;
    }
    closedir(d); return n;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *dump_dir = argc > 1 ? argv[1] : "calib_maps2";
        mkdir(dump_dir, 0755);

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        NSError *err = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:[NSString stringWithUTF8String:RENDER_MIN_SRC] options:nil error:&err];
        if (!lib) { fprintf(stderr, "compile fail: %s\n", err.localizedDescription.UTF8String); return 2; }
        id<MTLFunction> vfn = [lib newFunctionWithName:@"v_main"];
        id<MTLFunction> ffn = [lib newFunctionWithName:@"f_main"];
        MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
        pd.vertexFunction = vfn; pd.fragmentFunction = ffn;
        pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
        id<MTLRenderPipelineState> pso = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if (!pso) { fprintf(stderr, "pso fail: %s\n", err.localizedDescription.UTF8String); return 2; }

        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:4 height:4 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModeShared;
        id<MTLTexture> target = [dev newTextureWithDescriptor:td];

        id<MTLCommandQueue> q = [dev newCommandQueue];
        MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
        rp.colorAttachments[0].texture = target;
        rp.colorAttachments[0].loadAction = MTLLoadActionClear;
        rp.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,0);
        rp.colorAttachments[0].storeAction = MTLStoreActionStore;

        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc = [cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        fprintf(stderr, "baseline draw status=%ld\n", (long)cb.status);

        uint8_t px[4*4*4];
        [target getBytes:px bytesPerRow:16 fromRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0];
        fprintf(stderr, "baseline pixel bgra = %02x%02x%02x%02x\n", px[0],px[1],px[2],px[3]);

        kill(getpid(), SIGUSR1); // no-op unless iotrace interposed; harmless standalone
        // Since iotrace isn't interposed in this calibration invocation path unless
        // DYLD_INSERT_LIBRARIES is set by the caller, this program relies on the
        // caller launching it WITH iotrace interposed so g_log/dump exist.
        usleep(1200000);

        static BODump dumps[MAXD];
        int n = load_all(dump_dir, dumps, MAXD);
        fprintf(stderr, "loaded %d BO dumps from %s\n", n, dump_dir);

        const uint8_t needle[54] = {
            0x97,0x0c,0x54,0x00,0x02,0x60,0x80,0x50,0x04,0xc8,
            0x97,0x04,0x54,0x01,0x02,0x20,0xc0,0x50,0x04,0xc8,
            0x87,0x02,0x54,0x00,0x06,0x00,
            0x87,0x02,0x54,0x0c,0x08,0x00,
            0xe7,0x06,0x54,0x00,0x00,0x00,0x01,0x4e,0x00,0x00,0x00,0x00,
            0x07,0x02,0x54,0x0c,0x02,0x00,
            0x0e,0x00,0x00,0x00
        };
        int found = 0;
        uint64_t found_cpu = 0, found_gpu_va = 0; int64_t found_off = -1;
        for (int i = 0; i < n; i++) {
            if (dumps[i].gpu_va < 0x10000000000ULL || dumps[i].gpu_va >= 0x10000010000ULL) continue;
            for (uint64_t off = 0; off + 54 <= dumps[i].read_len; off++) {
                if (memcmp(dumps[i].data + off, needle, 54) == 0) {
                    found = 1; found_cpu = dumps[i].cpu; found_gpu_va = dumps[i].gpu_va; found_off = (int64_t)off;
                    fprintf(stderr, "FOUND in %s at off=0x%llx (cpu=0x%llx gpu_va=0x%llx)\n",
                            dumps[i].path, (unsigned long long)off, (unsigned long long)dumps[i].cpu, (unsigned long long)dumps[i].gpu_va);
                    break;
                }
            }
            if (found) break;
        }
        if (!found) { fprintf(stderr, "NOT FOUND\n"); return 3; }

        // header should be at found_off - 0x80
        int64_t header_off = found_off - 0x80;
        uint32_t header_word = 0;
        memcpy(&header_word, dumps[0].data, 0); // placeholder, real read below using correct dump index
        // find that dump again by cpu match to read header properly:
        for (int i = 0; i < n; i++) {
            if (dumps[i].cpu == found_cpu) {
                if (header_off >= 0 && header_off + 4 <= (int64_t)dumps[i].read_len) {
                    memcpy(&header_word, dumps[i].data + header_off, 4);
                }
                break;
            }
        }
        fprintf(stderr, "header_off=0x%llx header_word=0x%08x (expect record_size, e.g. 0xc0)\n",
                (unsigned long long)header_off, header_word);

        // Attempt a WRITE at found_cpu + found_off + 6: change 0x80 -> 0x40 (green byte, per EXP-0008).
        uint8_t *ptr = (uint8_t *)(uintptr_t)(found_cpu + (uint64_t)found_off + 6);
        fprintf(stderr, "about to write 1 byte at cpu addr %p (current value 0x%02x)\n", (void*)ptr, *ptr);
        uint8_t before = *ptr;
        *ptr = 0x40;
        uint8_t after = *ptr;
        fprintf(stderr, "wrote: before=0x%02x after=0x%02x\n", before, after);

        // Re-dump to see if the live BO capture reflects the write (independent confirmation
        // via the SAME mach_vm_read_overwrite path iotrace uses, not just our own pointer read).
        kill(getpid(), SIGUSR1);
        usleep(1200000);
        static BODump dumps2[MAXD];
        int n2 = load_all(dump_dir, dumps2, MAXD);
        for (int i = 0; i < n2; i++) {
            if (dumps2[i].cpu == found_cpu && header_off >= 0 && found_off + 6 < (int64_t)dumps2[i].read_len) {
                fprintf(stderr, "post-write redump byte at same offset = 0x%02x (expect 0x40)\n",
                        dumps2[i].data[found_off + 6]);
            }
        }

        // Second draw: fresh command buffer, SAME pipeline object, after the live
        // in-place byte write above. If the hardware fetches code from this exact
        // live BO location, the readback pixel's green channel should flip from
        // 0x80 (0.502) to 0x40 (0.251), per EXP-0008's already-HW-validated
        // archive-level mapping of this exact byte.
        id<MTLCommandBuffer> cb2 = [q commandBuffer];
        id<MTLRenderCommandEncoder> enc2 = [cb2 renderCommandEncoderWithDescriptor:rp];
        [enc2 setRenderPipelineState:pso];
        [enc2 drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
        [enc2 endEncoding];
        [cb2 commit];
        [cb2 waitUntilCompleted];
        fprintf(stderr, "post-splice draw status=%ld\n", (long)cb2.status);
        uint8_t px2[4*4*4];
        [target getBytes:px2 bytesPerRow:16 fromRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0];
        fprintf(stderr, "post-splice pixel bgra = %02x%02x%02x%02x (predict 40 vs baseline 80 in green byte)\n",
                px2[0],px2[1],px2[2],px2[3]);

        fprintf(stderr, "CALIB_DONE\n");
        return 0;
    }
}
