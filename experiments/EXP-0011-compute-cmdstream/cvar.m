// cvar.m — parametric OWN compute dispatch for change-one-parameter cmdstream RE.
//
// Part of EXP-0011 (Phase 2 cmdstream decode). An extension of iohello_compute:
// one small compute program whose every submission parameter is a CLI flag, so we
// can change exactly ONE Metal parameter, re-capture the registered GPU buffers
// under the iotrace interposer, and byte-diff the snapshots to localise each field
// of the launch/dispatch descriptor and the argument buffer.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Every kernel here is our own
// MSL, compiled at runtime. We print the GPU virtual addresses of our own
// resources so the captured bytes can be correlated. Nothing disassembles any
// Apple binary.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o cvar cvar.m
//
// Usage:
//   cvar --kernel NAME [--gx N --gy N --gz N] [--tgx N --tgy N --tgz N]
//        [--groups] [--tgmem BYTES] [--iters N] [--dump] [--dumpall]
//
//   --kernel : add3 (default) | mul1 | add2 | add4 | add8 | heavy | tex | tgmem
//   --groups : use dispatchThreadgroups (gx/gy/gz = threadgroup COUNT) instead of
//              dispatchThreads (gx/gy/gz = total thread count).
//   --tgmem  : bytes of threadgroup memory bound at index 0 (kernels that use it).
//   --dump   : SIGUSR1 after the last submit (snapshot BOs; interposer must be loaded).
//   --dumpall: SIGUSR1 after EVERY submit (per-iteration snapshots for ring/doorbell diff).

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *label, uint64_t va) {
    unsigned char b[8];
    for (int i = 0; i < 8; i++) b[i] = (va >> (8 * i)) & 0xff;
    printf("VA %-12s = 0x%016llx  le=", label, (unsigned long long)va);
    for (int i = 0; i < 8; i++) printf("%02x", b[i]);
    printf("\n");
}

// ---- embedded OWN kernels -------------------------------------------------
// Each entry: name, MSL source, #device buffers, uses texture, uses sampler,
// uses threadgroup memory.
typedef struct {
    const char *name;
    const char *src;
    int nbuf;       // number of device buffers to create+bind (indices 0..nbuf-1)
    int tex;        // bind a texture at texture(0)
    int smp;        // bind a sampler at sampler(0)
    int tgmem;      // bind threadgroup memory at threadgroup(0)
} Kernel;

static const Kernel KERNELS[] = {
  { "add3",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device const float* a [[buffer(0)]],\n"
    "              device const float* b [[buffer(1)]],\n"
    "              device float* o       [[buffer(2)]],\n"
    "              uint i [[thread_position_in_grid]]) { o[i]=a[i]+b[i]; }\n",
    3, 0, 0, 0 },

  { "mul1",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device float* o [[buffer(0)]],\n"
    "              uint i [[thread_position_in_grid]]) { o[i]=o[i]*2.0f; }\n",
    1, 0, 0, 0 },

  { "add2",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device const float* a [[buffer(0)]],\n"
    "              device float* o       [[buffer(1)]],\n"
    "              uint i [[thread_position_in_grid]]) { o[i]=a[i]+1.0f; }\n",
    2, 0, 0, 0 },

  { "add4",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device const float* a [[buffer(0)]],\n"
    "              device const float* b [[buffer(1)]],\n"
    "              device const float* c [[buffer(2)]],\n"
    "              device float* o       [[buffer(3)]],\n"
    "              uint i [[thread_position_in_grid]]) { o[i]=a[i]+b[i]+c[i]; }\n",
    4, 0, 0, 0 },

  { "add8",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device const float* a [[buffer(0)]],\n"
    "              device const float* b [[buffer(1)]],\n"
    "              device const float* c [[buffer(2)]],\n"
    "              device const float* d [[buffer(3)]],\n"
    "              device const float* e [[buffer(4)]],\n"
    "              device const float* f [[buffer(5)]],\n"
    "              device const float* g [[buffer(6)]],\n"
    "              device float* o       [[buffer(7)]],\n"
    "              uint i [[thread_position_in_grid]]) {\n"
    "  o[i]=a[i]+b[i]+c[i]+d[i]+e[i]+f[i]+g[i]; }\n",
    8, 0, 0, 0 },

  // High register pressure: many live values across a barrier-free body.
  { "heavy",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device const float* a [[buffer(0)]],\n"
    "              device float* o       [[buffer(1)]],\n"
    "              uint i [[thread_position_in_grid]]) {\n"
    "  float x=a[i];\n"
    "  float v0=x*1.01f,v1=x*1.02f,v2=x*1.03f,v3=x*1.04f,v4=x*1.05f,v5=x*1.06f,\n"
    "        v6=x*1.07f,v7=x*1.08f,v8=x*1.09f,v9=x*1.10f,va=x*1.11f,vb=x*1.12f,\n"
    "        vc=x*1.13f,vd=x*1.14f,ve=x*1.15f,vf=x*1.16f;\n"
    "  for (int j=0;j<3;j++){\n"
    "    v0=fma(v0,v1,vf); v1=fma(v1,v2,ve); v2=fma(v2,v3,vd); v3=fma(v3,v4,vc);\n"
    "    v4=fma(v4,v5,vb); v5=fma(v5,v6,va); v6=fma(v6,v7,v9); v7=fma(v7,v8,v0);\n"
    "    v8=fma(v8,v9,v1); v9=fma(v9,va,v2); va=fma(va,vb,v3); vb=fma(vb,vc,v4);\n"
    "    vc=fma(vc,vd,v5); vd=fma(vd,ve,v6); ve=fma(ve,vf,v7); vf=fma(vf,v0,v8);\n"
    "  }\n"
    "  o[i]=v0+v1+v2+v3+v4+v5+v6+v7+v8+v9+va+vb+vc+vd+ve+vf; }\n",
    2, 0, 0, 0 },

  { "tex",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(texture2d<float> t [[texture(0)]],\n"
    "              sampler s          [[sampler(0)]],\n"
    "              device float* o    [[buffer(0)]],\n"
    "              uint i [[thread_position_in_grid]]) {\n"
    "  o[i]=t.sample(s, float2(0.5f,0.5f)).x; }\n",
    1, 1, 1, 0 },

  { "tgmem",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device const float* a [[buffer(0)]],\n"
    "              device float* o        [[buffer(1)]],\n"
    "              threadgroup float* sh  [[threadgroup(0)]],\n"
    "              uint i  [[thread_position_in_grid]],\n"
    "              uint li [[thread_position_in_threadgroup]]) {\n"
    "  sh[li]=a[i]; threadgroup_barrier(mem_flags::mem_threadgroup);\n"
    "  o[i]=sh[li]+1.0f; }\n",
    2, 0, 0, 1 },
};
static const int NKERNELS = sizeof(KERNELS)/sizeof(KERNELS[0]);

int main(int argc, char **argv) {
    @autoreleasepool {
        const char *kname = "add3";
        const char *k2name = NULL;   /* optional 2nd dispatch (different pipeline) */
        long gx=64,gy=1,gz=1, tgx=32,tgy=1,tgz=1, iters=1, tgmem=0, pad=0;
        int useGroups=0, doDump=0, doDumpAll=0;
        for (int i=1;i<argc;i++){
            if(!strcmp(argv[i],"--kernel")&&i+1<argc) kname=argv[++i];
            else if(!strcmp(argv[i],"--k2")&&i+1<argc) k2name=argv[++i];
            else if(!strcmp(argv[i],"--pad")&&i+1<argc) pad=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--gx")&&i+1<argc) gx=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--gy")&&i+1<argc) gy=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--gz")&&i+1<argc) gz=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--tgx")&&i+1<argc) tgx=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--tgy")&&i+1<argc) tgy=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--tgz")&&i+1<argc) tgz=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--iters")&&i+1<argc) iters=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--tgmem")&&i+1<argc) tgmem=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--groups")) useGroups=1;
            else if(!strcmp(argv[i],"--dump")) doDump=1;
            else if(!strcmp(argv[i],"--dumpall")) doDumpAll=1;
        }

        const Kernel *K=0;
        for(int i=0;i<NKERNELS;i++) if(!strcmp(KERNELS[i].name,kname)){K=&KERNELS[i];break;}
        if(!K){ printf("UNKNOWN_KERNEL %s\n",kname); return 2; }

        id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n", [[dev name] UTF8String]);
        printf("CONFIG kernel=%s grid=(%ld,%ld,%ld) tg=(%ld,%ld,%ld) groups=%d tgmem=%ld iters=%ld pad=%ld\n",
               kname,gx,gy,gz,tgx,tgy,tgz,useGroups,tgmem,iters,pad);

        // Padding: compile N dummy distinct pipelines first, so the real shader's
        // BO (and the control-plane allocations) land at a shifted GPU VA. This
        // lets us confirm the launch-descriptor shader pointer TRACKS the shader
        // VA (change-one-parameter: only the shader address moves).
        NSMutableArray *keep=[NSMutableArray array]; NSError *e0=nil;
        for(long p=0;p<pad;p++){
            NSString *ps=[NSString stringWithFormat:
              @"#include <metal_stdlib>\nusing namespace metal;\n"
               "kernel void k(device float* o [[buffer(0)]], uint i [[thread_position_in_grid]])"
               "{ o[i]=o[i]*%ld.0f + %ld.0f; }\n", p+2, p+1];
            id<MTLLibrary> pl=[dev newLibraryWithSource:ps options:nil error:&e0];
            id<MTLFunction> pf=[pl newFunctionWithName:@"k"];
            id<MTLComputePipelineState> pp=[dev newComputePipelineStateWithFunction:pf error:&e0];
            if(pp)[keep addObject:pp];
        }

        NSError *err=nil;
        NSString *src=[NSString stringWithUTF8String:K->src];
        id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
        if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
        id<MTLFunction> fn=[lib newFunctionWithName:@"k"];
        id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:fn error:&err];
        if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
        printf("PSO threadExecutionWidth=%lu maxTotalThreadsPerThreadgroup=%lu staticThreadgroupMemoryLength=%lu\n",
               (unsigned long)[pso threadExecutionWidth],
               (unsigned long)[pso maxTotalThreadsPerThreadgroup],
               (unsigned long)[pso staticThreadgroupMemoryLength]);

        size_t n = (size_t)(gx*gy*gz); if(n<64) n=64;
        id<MTLBuffer> bufs[8]={0};
        for(int b=0;b<K->nbuf;b++){
            bufs[b]=[dev newBufferWithLength:n*4 options:MTLResourceStorageModeShared];
            float *p=(float*)[bufs[b] contents];
            for(size_t i=0;i<n;i++) p[i]=(float)(1000+b*100)+ (float)i*0.5f;
            char lbl[16]; snprintf(lbl,sizeof lbl,"buf%d",b);
            print_va(lbl,[bufs[b] gpuAddress]);
        }

        id<MTLTexture> tex=nil; id<MTLSamplerState> smp=nil;
        if(K->tex){
            MTLTextureDescriptor *td=[MTLTextureDescriptor
                texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
                width:4 height:4 mipmapped:NO];
            td.usage=MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
            tex=[dev newTextureWithDescriptor:td];
            unsigned char px[4*4*4]; memset(px,0x80,sizeof px);
            [tex replaceRegion:MTLRegionMake2D(0,0,4,4) mipmapLevel:0 withBytes:px bytesPerRow:16];
            printf("TEX bound texture2d rgba8 4x4\n");
        }
        if(K->smp){
            MTLSamplerDescriptor *sd=[MTLSamplerDescriptor new];
            sd.minFilter=MTLSamplerMinMagFilterLinear;
            sd.magFilter=MTLSamplerMinMagFilterLinear;
            smp=[dev newSamplerStateWithDescriptor:sd];
            printf("SMP bound linear sampler\n");
        }

        // Optional second, DIFFERENT pipeline (its own shader BO) for an
        // intra-capture shader-pointer confirmation: two launch descriptors in
        // one submit, whose shader pointers must differ by (VA2-VA1)>>shift.
        id<MTLComputePipelineState> pso2=nil; id<MTLBuffer> b2=nil;
        if(k2name){
            const Kernel *K2=0;
            for(int i=0;i<NKERNELS;i++) if(!strcmp(KERNELS[i].name,k2name)){K2=&KERNELS[i];break;}
            if(K2){
                id<MTLLibrary> l2=[dev newLibraryWithSource:[NSString stringWithUTF8String:K2->src] options:nil error:&err];
                id<MTLFunction> f2=[l2 newFunctionWithName:@"k"];
                pso2=[dev newComputePipelineStateWithFunction:f2 error:&err];
                b2=[dev newBufferWithLength:n*4 options:MTLResourceStorageModeShared];
                print_va("k2buf0",[b2 gpuAddress]);
                printf("K2 kernel=%s\n", k2name);
            }
        }

        id<MTLCommandQueue> q=[dev newCommandQueue];
        for(long it=0; it<iters; it++){
            printf("SUBMIT iter=%ld begin\n", it);
            id<MTLCommandBuffer> cb=[q commandBuffer];
            id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
            [enc setComputePipelineState:pso];
            for(int b=0;b<K->nbuf;b++) [enc setBuffer:bufs[b] offset:0 atIndex:b];
            if(tex) [enc setTexture:tex atIndex:0];
            if(smp) [enc setSamplerState:smp atIndex:0];
            if(K->tgmem){ NSUInteger tm = tgmem?tgmem:(NSUInteger)(tgx*tgy*tgz*4);
                          [enc setThreadgroupMemoryLength:tm atIndex:0]; }
            if(useGroups)
                [enc dispatchThreadgroups:MTLSizeMake(gx,gy,gz)
                     threadsPerThreadgroup:MTLSizeMake(tgx,tgy,tgz)];
            else
                [enc dispatchThreads:MTLSizeMake(gx,gy,gz)
                     threadsPerThreadgroup:MTLSizeMake(tgx,tgy,tgz)];
            if(pso2){                     /* distinct dims (16 threads / tg 8) to ID it */
                [enc setComputePipelineState:pso2];
                [enc setBuffer:b2 offset:0 atIndex:0];
                [enc dispatchThreads:MTLSizeMake(16,1,1) threadsPerThreadgroup:MTLSizeMake(8,1,1)];
            }
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
            printf("SUBMIT iter=%ld done status=%ld\n", it,(long)[cb status]);
            if((doDumpAll) || (doDump && it==iters-1)){
                fflush(stdout);
                kill(getpid(), SIGUSR1);
                usleep(400000);
            }
        }
        return 0;
    }
}
