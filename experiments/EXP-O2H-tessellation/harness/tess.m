// tess.m — EXP-O2H OWN tessellation pipeline harness (HW-validate + iotrace target).
//
// Builds a minimal Metal tessellation pipeline exactly as Metal exposes it:
//   * a COMPUTE kernel that writes per-patch tessellation factors into an MTLBuffer
//     (unless --cpu-factors, in which case the CPU writes them and NO compute runs), then
//   * a POST-TESSELLATION VERTEX FUNCTION ([[patch(...)]]) + fragment, via drawPatches.
// Reads back the rendered target (HW validation) and prints every resource GPU VA so an
// iotrace capture can correlate the tessellation-factor buffer / control-point buffer.
//
// The --cpu-factors mode is the crux for the "compute pre-pass?" question: with NO
// user compute encoder, if a CDM (compute) launch descriptor still appears in the trace,
// drawPatches itself ran a compute tessellator; if not, tessellation is a graphics-path stage.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Never introspects any Apple binary.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o tess tess.m
// Usage: ./tess --source tess.metal [--patch tri|quad] [--level F] [--bulge F]
//               [--cpu-factors] [--partition int|pow2|fo|fe] [--iters N]
//               [--w W] [--h H] [--dump]
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <simd/simd.h>

static void print_va(const char *label, uint64_t va) {
    unsigned char b[8]; for (int i=0;i<8;i++) b[i]=(va>>(8*i))&0xff;
    printf("VA %-14s = 0x%016llx  le=", label, (unsigned long long)va);
    for (int i=0;i<8;i++) printf("%02x", b[i]);
    printf("\n");
}
static void fail(const char *st, const char *msg, NSError *e){
    printf("STATUS %s\n", st);
    if (e) printf("ERROR %s: %s\n", msg, [[e localizedDescription] UTF8String]);
    else if (msg) printf("ERROR %s\n", msg);
    fflush(stdout); exit(1);
}

enum { OPT_SOURCE=128, OPT_PATCH, OPT_LEVEL, OPT_BULGE, OPT_CPU, OPT_PART,
       OPT_ITERS, OPT_W, OPT_H, OPT_DUMP };
static const struct option L[] = {
    {"source",required_argument,0,OPT_SOURCE},{"patch",required_argument,0,OPT_PATCH},
    {"level",required_argument,0,OPT_LEVEL},{"bulge",required_argument,0,OPT_BULGE},
    {"cpu-factors",no_argument,0,OPT_CPU},{"partition",required_argument,0,OPT_PART},
    {"iters",required_argument,0,OPT_ITERS},{"w",required_argument,0,OPT_W},
    {"h",required_argument,0,OPT_H},{"dump",no_argument,0,OPT_DUMP},{0,0,0,0}
};

int main(int argc, char **argv){
  @autoreleasepool {
    const char *sourcePath=NULL, *patch="tri", *part="int";
    float level=8.0f, bulge=0.0f; int cpuFactors=0, doDump=0;
    long iters=1, W=64, H=64;
    int c; while((c=getopt_long(argc,argv,"",L,NULL))>0){ switch(c){
        case OPT_SOURCE: sourcePath=optarg; break;
        case OPT_PATCH: patch=optarg; break;
        case OPT_LEVEL: level=strtof(optarg,NULL); break;
        case OPT_BULGE: bulge=strtof(optarg,NULL); break;
        case OPT_CPU: cpuFactors=1; break;
        case OPT_PART: part=optarg; break;
        case OPT_ITERS: iters=strtol(optarg,NULL,0); break;
        case OPT_W: W=strtol(optarg,NULL,0); break;
        case OPT_H: H=strtol(optarg,NULL,0); break;
        case OPT_DUMP: doDump=1; break;
        default: return 1; } }
    if (!sourcePath) fail("ARGERR","need --source tess.metal", nil);
    int isQuad = !strcmp(patch,"quad");
    int nCP = isQuad ? 4 : 3;

    id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
    if(!dev) fail("NODEV","no Metal device", nil);
    printf("DEVICE %s\n", [[dev name] UTF8String]);
    printf("TESS patch=%s level=%.2f bulge=%.3f cpu_factors=%d partition=%s w=%ld h=%ld iters=%ld\n",
           patch, level, bulge, cpuFactors, part, W, H, iters);

    NSError *err=nil;
    NSString *src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:sourcePath]
                                            encoding:NSUTF8StringEncoding error:&err];
    if(!src) fail("READ","read source", err);
    id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
    if(!lib) fail("COMPILE","newLibraryWithSource", err);

    // ---- functions ----
    id<MTLFunction> vfn=[lib newFunctionWithName:isQuad?@"tess_vertex_quad":@"tess_vertex_tri"];
    id<MTLFunction> ffn=[lib newFunctionWithName:@"tess_frag"];
    id<MTLFunction> kfn=[lib newFunctionWithName:isQuad?@"tess_factors_quad":@"tess_factors_tri"];
    if(!vfn||!ffn||!kfn) fail("FUNC","function missing", nil);

    // ---- tessellation render pipeline ----
    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=vfn; pd.fragmentFunction=ffn;
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    pd.maxTessellationFactor=16;
    pd.tessellationFactorFormat=MTLTessellationFactorFormatHalf;
    pd.tessellationControlPointIndexType=MTLTessellationControlPointIndexTypeNone;
    pd.tessellationFactorStepFunction=MTLTessellationFactorStepFunctionConstant;
    pd.tessellationOutputWindingOrder=MTLWindingClockwise;
    if(!strcmp(part,"pow2")) pd.tessellationPartitionMode=MTLTessellationPartitionModePow2;
    else if(!strcmp(part,"fo")) pd.tessellationPartitionMode=MTLTessellationPartitionModeFractionalOdd;
    else if(!strcmp(part,"fe")) pd.tessellationPartitionMode=MTLTessellationPartitionModeFractionalEven;
    else pd.tessellationPartitionMode=MTLTessellationPartitionModeInteger;
    // vertex descriptor: control points come from buffer 0, per-patch-control-point.
    MTLVertexDescriptor *vd=[MTLVertexDescriptor new];
    vd.attributes[0].format=MTLVertexFormatFloat4; vd.attributes[0].offset=0; vd.attributes[0].bufferIndex=0;
    vd.layouts[0].stride=sizeof(simd_float4);
    vd.layouts[0].stepFunction=MTLVertexStepFunctionPerPatchControlPoint;
    pd.vertexDescriptor=vd;
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso) fail("PIPELINE","render pipeline (tessellation)", err);

    id<MTLComputePipelineState> cps=nil;
    if(!cpuFactors){ cps=[dev newComputePipelineStateWithFunction:kfn error:&err];
        if(!cps) fail("CPIPE","compute factor pipeline", err); }

    // ---- resources ----
    simd_float4 cpTri[3]={ {-0.8f,-0.8f,0,1}, {0.8f,-0.8f,0,1}, {0.0f,0.8f,0,1} };
    simd_float4 cpQuad[4]={ {-0.8f,-0.8f,0,1}, {0.8f,-0.8f,0,1}, {0.8f,0.8f,0,1}, {-0.8f,0.8f,0,1} };
    id<MTLBuffer> cpBuf=[dev newBufferWithBytes:(isQuad?(void*)cpQuad:(void*)cpTri)
                                          length:nCP*sizeof(simd_float4)
                                         options:MTLResourceStorageModeShared];
    // factor buffer: 1 patch. Tri half-format=8B, Quad half-format=12B.
    size_t fbytes = isQuad ? 12 : 8;
    id<MTLBuffer> facBuf=[dev newBufferWithLength:fbytes options:MTLResourceStorageModeShared];
    id<MTLBuffer> lvlBuf=[dev newBufferWithBytes:&level length:sizeof(float) options:MTLResourceStorageModeShared];
    id<MTLBuffer> bulgeBuf=[dev newBufferWithBytes:&bulge length:sizeof(float) options:MTLResourceStorageModeShared];
    if(cpuFactors){ // CPU writes half factors directly (NO compute pass)
        uint16_t *h=(uint16_t*)[facBuf contents];
        // half(level) via simple encode using __fp16
        __fp16 hv=(__fp16)level; uint16_t bits; memcpy(&bits,&hv,2);
        int n = isQuad?6:4; for(int i=0;i<n;i++) h[i]=bits;
    }

    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                                                       width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
    id<MTLTexture> target=[dev newTextureWithDescriptor:td];

    print_va("controlpoints", [cpBuf gpuAddress]);
    print_va("tessfactors",  [facBuf gpuAddress]);
    print_va("level",        [lvlBuf gpuAddress]);
    print_va("bulge",        [bulgeBuf gpuAddress]);
    printf("NCP %d FACTOR_BYTES %zu\n", nCP, fbytes);

    id<MTLCommandQueue> q=[dev newCommandQueue];
    for(long it=0; it<iters; it++){
        printf("SUBMIT iter=%ld begin\n", it);
        id<MTLCommandBuffer> cb=[q commandBuffer];
        if(!cpuFactors){
            id<MTLComputeCommandEncoder> ce=[cb computeCommandEncoder];
            [ce setComputePipelineState:cps];
            [ce setBuffer:facBuf offset:0 atIndex:0];
            [ce setBuffer:lvlBuf offset:0 atIndex:1];
            [ce dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
            [ce endEncoding];
        }
        MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
        rp.colorAttachments[0].texture=target;
        rp.colorAttachments[0].loadAction=MTLLoadActionClear;
        rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
        rp.colorAttachments[0].storeAction=MTLStoreActionStore;
        id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];
        [enc setVertexBuffer:cpBuf offset:0 atIndex:0];
        [enc setVertexBuffer:bulgeBuf offset:0 atIndex:1];
        [enc setTessellationFactorBuffer:facBuf offset:0 instanceStride:0];
        [enc drawPatches:nCP patchStart:0 patchCount:1
            patchIndexBuffer:nil patchIndexBufferOffset:0
               instanceCount:1 baseInstance:0];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        long st=(long)[cb status];
        printf("SUBMIT iter=%ld done status=%ld\n", it, st);
        if(st==MTLCommandBufferStatusError){ printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]); }
        if(doDump && it==iters-1){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    }

    // ---- readback / HW validation ----
    unsigned char *px=(unsigned char*)malloc((size_t)W*H*4);
    [target getBytes:px bytesPerRow:(NSUInteger)(W*4) fromRegion:MTLRegionMake2D(0,0,(NSUInteger)W,(NSUInteger)H) mipmapLevel:0];
    long covered=0; for(long i=0;i<W*H;i++){ unsigned char *p=px+i*4; if(p[0]||p[1]||p[2]) covered++; }
    printf("COVERED %ld of %ld\n", covered, W*H);
    for(long y=0;y<H;y+=(H>32?H/32:1)){ printf("ROW %3ld ", y);
        for(long x=0;x<W;x+=(W>48?W/48:1)){ unsigned char *p=px+(y*W+x)*4; putchar((p[0]||p[1]||p[2])?'#':'.'); }
        putchar('\n'); }
    long cx=W/2, cy=H/2; unsigned char *cp=px+(cy*W+cx)*4;
    printf("CENTER %ld %ld bgra=%02x%02x%02x%02x\n", cx, cy, cp[0],cp[1],cp[2],cp[3]);
    free(px);
    printf("STATUS OK\n"); fflush(stdout);
    return 0;
  }
}
