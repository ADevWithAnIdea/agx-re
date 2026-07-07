// cvar2.m — parametric OWN compute dispatch for EXP-0024 G-8 (CDM +0x00 config word +
// threadgroup-memory-size field). Extends EXP-0011's cvar.m with:
//   * static-threadgroup kernels tgs0/tgs256/tgs1k/tgs4k/tgs16k/tgs32k (a compile-time
//     `threadgroup float sh[N]`) — to see where a STATIC tg-mem size is declared.
//   * dynamic tg-mem via --tgmem BYTES on the `tgdyn` kernel (setThreadgroupMemoryLength).
//   * config-word probe kernels: add3 (tiny), heavy (reg-heavy), atom (atomics), barr
//     (barrier), simd (simd_sum) — to decode CDM record +0x00 beyond bit23.
//   * --dumpall dumps EVERY registered BO so the tg-mem size can be hunted across all BOs.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API. Our own MSL only; prints our own resource VAs.
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o cvar2 cvar2.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char *label,uint64_t va){
    printf("VA %-12s = 0x%016llx\n",label,(unsigned long long)va);
}

typedef struct { const char *name; const char *src; int nbuf; int tgmem_dyn; } Kernel;

// static threadgroup arrays sized N floats -> N*4 bytes. built with a macro string.
#define TGS(name,N) { name, \
  "#include <metal_stdlib>\nusing namespace metal;\n" \
  "kernel void k(device const float* a [[buffer(0)]], device float* o [[buffer(1)]],\n" \
  "              uint i [[thread_position_in_grid]], uint li [[thread_position_in_threadgroup]]){\n" \
  "  threadgroup float sh[" #N "]; sh[li% " #N "]=a[i];\n" \
  "  threadgroup_barrier(mem_flags::mem_threadgroup);\n" \
  "  o[i]=sh[(li+1)% " #N "]+1.0f; }\n", 2, 0 }

static const Kernel KERNELS[] = {
  { "add3",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device const float* a [[buffer(0)]], device const float* b [[buffer(1)]],\n"
    "              device float* o [[buffer(2)]], uint i [[thread_position_in_grid]]){ o[i]=a[i]+b[i]; }\n",
    3, 0 },
  // register-heavy (16 live values, EXP-0020 crosses the reg tier at ~12)
  { "heavy",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device const float* a [[buffer(0)]], device float* o [[buffer(1)]],\n"
    "              uint i [[thread_position_in_grid]]){ float x=a[i];\n"
    "  float v0=x*1.01f,v1=x*1.02f,v2=x*1.03f,v3=x*1.04f,v4=x*1.05f,v5=x*1.06f,v6=x*1.07f,v7=x*1.08f,\n"
    "        v8=x*1.09f,v9=x*1.10f,va=x*1.11f,vb=x*1.12f,vc=x*1.13f,vd=x*1.14f,ve=x*1.15f,vf=x*1.16f;\n"
    "  for(int j=0;j<3;j++){ v0=fma(v0,v1,vf); v1=fma(v1,v2,ve); v2=fma(v2,v3,vd); v3=fma(v3,v4,vc);\n"
    "    v4=fma(v4,v5,vb); v5=fma(v5,v6,va); v6=fma(v6,v7,v9); v7=fma(v7,v8,v0);\n"
    "    v8=fma(v8,v9,v1); v9=fma(v9,va,v2); va=fma(va,vb,v3); vb=fma(vb,vc,v4);\n"
    "    vc=fma(vc,vd,v5); vd=fma(vd,ve,v6); ve=fma(ve,vf,v7); vf=fma(vf,v0,v8); }\n"
    "  o[i]=v0+v1+v2+v3+v4+v5+v6+v7+v8+v9+va+vb+vc+vd+ve+vf; }\n",
    2, 0 },
  // atomics
  { "atom",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device atomic_uint* o [[buffer(0)]], uint i [[thread_position_in_grid]]){\n"
    "  atomic_fetch_add_explicit(o,1u,memory_order_relaxed); }\n",
    1, 0 },
  // barrier-only (no tg memory)
  { "barr",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device float* o [[buffer(0)]], uint i [[thread_position_in_grid]]){\n"
    "  threadgroup_barrier(mem_flags::mem_device); o[i]=o[i]+1.0f; }\n",
    1, 0 },
  // simd reduction
  { "simd",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device const float* a [[buffer(0)]], device float* o [[buffer(1)]],\n"
    "              uint i [[thread_position_in_grid]]){ o[i]=simd_sum(a[i]); }\n",
    2, 0 },
  // dynamic threadgroup memory (size set at dispatch via setThreadgroupMemoryLength)
  { "tgdyn",
    "#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void k(device const float* a [[buffer(0)]], device float* o [[buffer(1)]],\n"
    "              threadgroup float* sh [[threadgroup(0)]],\n"
    "              uint i [[thread_position_in_grid]], uint li [[thread_position_in_threadgroup]]){\n"
    "  sh[li]=a[i]; threadgroup_barrier(mem_flags::mem_threadgroup); o[i]=sh[li]+1.0f; }\n",
    2, 1 },
  TGS("tgs64",64),      // 256 B
  TGS("tgs256",256),    // 1 KB
  TGS("tgs1024",1024),  // 4 KB
  TGS("tgs4096",4096),  // 16 KB
  TGS("tgs8192",8192),  // 32 KB
};
static const int NK=sizeof(KERNELS)/sizeof(KERNELS[0]);

int main(int argc,char**argv){
  @autoreleasepool {
    const char *kname="add3"; long gx=64,gy=1,gz=1,tgx=32,tgy=1,tgz=1,iters=1,tgmem=0;
    int doDump=0,doDumpAll=0;
    for(int i=1;i<argc;i++){
      if(!strcmp(argv[i],"--kernel")&&i+1<argc)kname=argv[++i];
      else if(!strcmp(argv[i],"--gx")&&i+1<argc)gx=strtol(argv[++i],0,0);
      else if(!strcmp(argv[i],"--tgx")&&i+1<argc)tgx=strtol(argv[++i],0,0);
      else if(!strcmp(argv[i],"--tgmem")&&i+1<argc)tgmem=strtol(argv[++i],0,0);
      else if(!strcmp(argv[i],"--iters")&&i+1<argc)iters=strtol(argv[++i],0,0);
      else if(!strcmp(argv[i],"--dump"))doDump=1;
      else if(!strcmp(argv[i],"--dumpall"))doDumpAll=1;
    }
    const Kernel *K=0; for(int i=0;i<NK;i++) if(!strcmp(KERNELS[i].name,kname)){K=&KERNELS[i];break;}
    if(!K){ printf("UNKNOWN_KERNEL %s\n",kname); return 2; }

    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name] UTF8String]);
    printf("CONFIG kernel=%s grid=(%ld,%ld,%ld) tg=(%ld,%ld,%ld) tgmem=%ld iters=%ld\n",
           kname,gx,gy,gz,tgx,tgy,tgz,tgmem,iters);

    NSError *err=nil;
    id<MTLLibrary> lib=[dev newLibraryWithSource:[NSString stringWithUTF8String:K->src] options:nil error:&err];
    if(!lib){ printf("COMPILE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLFunction> fn=[lib newFunctionWithName:@"k"];
    id<MTLComputePipelineState> pso=[dev newComputePipelineStateWithFunction:fn error:&err];
    if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    printf("PSO threadExecutionWidth=%lu maxTotalThreadsPerThreadgroup=%lu staticThreadgroupMemoryLength=%lu\n",
           (unsigned long)[pso threadExecutionWidth],(unsigned long)[pso maxTotalThreadsPerThreadgroup],
           (unsigned long)[pso staticThreadgroupMemoryLength]);

    size_t n=(size_t)(gx*gy*gz); if(n<64)n=64;
    id<MTLBuffer> bufs[8]={0};
    for(int b=0;b<K->nbuf;b++){
      bufs[b]=[dev newBufferWithLength:n*4 options:MTLResourceStorageModeShared];
      float *p=(float*)[bufs[b] contents]; for(size_t i=0;i<n;i++)p[i]=(float)(1000+b*100)+(float)i*0.5f;
      char lbl[16]; snprintf(lbl,sizeof lbl,"buf%d",b); print_va(lbl,[bufs[b] gpuAddress]);
    }

    id<MTLCommandQueue> q=[dev newCommandQueue];
    for(long it=0;it<iters;it++){
      printf("SUBMIT iter=%ld begin\n",it);
      id<MTLCommandBuffer> cb=[q commandBuffer];
      id<MTLComputeCommandEncoder> enc=[cb computeCommandEncoder];
      [enc setComputePipelineState:pso];
      for(int b=0;b<K->nbuf;b++)[enc setBuffer:bufs[b] offset:0 atIndex:b];
      if(K->tgmem_dyn){ NSUInteger tm=tgmem?tgmem:(NSUInteger)(tgx*4); [enc setThreadgroupMemoryLength:tm atIndex:0]; }
      [enc dispatchThreads:MTLSizeMake(gx,gy,gz) threadsPerThreadgroup:MTLSizeMake(tgx,tgy,tgz)];
      [enc endEncoding];
      [cb commit];
      [cb waitUntilCompleted];
      printf("SUBMIT iter=%ld done status=%ld\n",it,(long)[cb status]);
      if(doDumpAll||(doDump&&it==iters-1)){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    }
    return 0;
  }
}
