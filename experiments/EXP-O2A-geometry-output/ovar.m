// ovar.m — parametric OWN Metal DRAW for GEOMETRY-OUTPUT-STAGE RE (EXP-O2A).
//
// The geometry-output analogue of EXP-0019's svar.m: one small draw whose
// geometry-output / raster-output Metal parameters are each a CLI flag, so we can
// change exactly ONE Metal parameter, re-capture the registered GPU buffer objects
// under the iotrace interposer, and byte-diff the snapshots to localise the field.
//
// Targets (O2-A):
//   1. Multiple viewports / scissor rects (setViewports:count:/setScissorRects:count:,
//      up to 16, with a VS [[viewport_array_index]] output).
//   2. Clip / cull distances ([[clip_distance]]).
//   3. [[point_size]] point rendering.
//   4. Primitive restart (indexed strip; index-type / restart-index field).
//   5. Alpha-to-coverage / alpha-to-one (pipeline flags).
//   6. Polygon fill mode (fill vs lines; Metal has no point fill — probed for the record).
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Every shader is our own MSL,
// compiled at runtime. We print the GPU virtual addresses of our own resources so the
// captured bytes can be correlated. Nothing disassembles any Apple binary.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o ovar ovar.m
//
// Usage (all flags optional; change ONE at a time is the method):
//   Target:      --w W --h H --fmt bgra8|rgba8 --msaa N(1/2/4)
//   Primitive:   --prim tri|point|line|linestrip|tristrip
//   Draw:        --indexed --itype u16|u32 --restart  (restart implies indexed strip)
//   Viewports:   --nvp N (0=setViewport single; >=1 uses setViewports:count:N)
//                --vpmod (perturb ONLY viewport[1] for stride isolation)
//   Scissor:     --nsc N (setScissorRects:count:N) --scmod (perturb ONLY scissor[1])
//   VS outputs:  --vpidx K (VS emits [[viewport_array_index]] = K)
//                --clipdist N (VS emits N clip distances) --pointsize F
//   Raster:      --fill fill|lines
//   Multisample: --a2c (alphaToCoverageEnabled) --a2o (alphaToOneEnabled)
//   Capture:     --dump --iters N

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void die(const char *m){ printf("ARGERR %s\n", m); exit(2); }
static void print_va(const char *label, uint64_t va){ printf("VA %-12s = 0x%016llx\n", label,(unsigned long long)va); }

// ---- generate the vertex shader (own MSL) with the requested outputs ----
static double g_calpha = 1.0;   // fragment/vertex output alpha (for alpha-to-one/coverage tests)
static NSString *make_vsrc(int hasPS, int nClip, int hasVP, int vpsel, double psize) {
    NSMutableString *s = [NSMutableString stringWithString:
        @"#include <metal_stdlib>\nusing namespace metal;\n"
         "struct VO {\n"
         "  float4 pos [[position]];\n"
         "  float4 col;\n"];
    if (hasPS)      [s appendString:@"  float psize [[point_size]];\n"];
    if (hasVP)      [s appendString:@"  uint vpidx [[viewport_array_index]];\n"];
    if (nClip == 1) [s appendString:@"  float cd [[clip_distance]];\n"];
    else if (nClip > 1) [s appendFormat:@"  float cd [[clip_distance]] [%d];\n", nClip];
    [s appendString:
        @"};\n"
         "vertex VO v_main(uint vid [[vertex_id]]) {\n"
         "  float2 p[4] = { float2(-0.9,-0.9), float2(0.9,-0.9), float2(-0.9,0.9), float2(0.9,0.9) };\n"
         "  VO o; o.pos = float4(p[vid & 3], 0, 1); o.col = float4(0.25,0.5,0.75,"];
    [s appendFormat:@"%ff);\n", g_calpha];
    if (hasPS)      [s appendFormat:@"  o.psize = %f;\n", psize];
    if (hasVP)      [s appendFormat:@"  o.vpidx = %d;\n", vpsel];
    if (nClip == 1) [s appendString:@"  o.cd = o.pos.x + 0.5;\n"];
    else if (nClip > 1) {
        for (int i = 0; i < nClip; i++)
            [s appendFormat:@"  o.cd[%d] = o.pos.x * %ff + %ff;\n", i, 1.0 + 0.1*i, 0.5 - 0.03*i];
    }
    [s appendString:@"  return o;\n}\n"];
    return s;
}
static NSString *make_fsrc(void) {
    return @"#include <metal_stdlib>\nusing namespace metal;\n"
            "struct VO { float4 pos [[position]]; float4 col; };\n"
            "fragment float4 f_main(VO in [[stage_in]]) { return in.col; }\n";
}

int main(int argc, char **argv) {
  @autoreleasepool {
    long W=64,H=64,iters=1,msaa=1,nvp=0,nsc=0,clipdist=0,vpidx=-1;
    int indexed=0,restart=0,a2c=0,a2o=0,hasPS=0,vpmod=0,scmod=0,doDump=0;
    double psize=8.0;
    const char *fmtS="bgra8", *primS="tri", *itypeS="u16", *fillS="fill";
    for(int i=1;i<argc;i++){
        const char *a=argv[i];
        #define NEXT (i+1<argc ? argv[++i] : (die("missing value"),(char*)0))
        if(!strcmp(a,"--w")) W=strtol(NEXT,0,0);
        else if(!strcmp(a,"--h")) H=strtol(NEXT,0,0);
        else if(!strcmp(a,"--fmt")) fmtS=NEXT;
        else if(!strcmp(a,"--msaa")) msaa=strtol(NEXT,0,0);
        else if(!strcmp(a,"--prim")) primS=NEXT;
        else if(!strcmp(a,"--indexed")) indexed=1;
        else if(!strcmp(a,"--itype")) { indexed=1; itypeS=NEXT; }
        else if(!strcmp(a,"--restart")) { indexed=1; restart=1; }
        else if(!strcmp(a,"--nvp")) nvp=strtol(NEXT,0,0);
        else if(!strcmp(a,"--vpmod")) vpmod=1;
        else if(!strcmp(a,"--nsc")) nsc=strtol(NEXT,0,0);
        else if(!strcmp(a,"--scmod")) scmod=1;
        else if(!strcmp(a,"--vpidx")) vpidx=strtol(NEXT,0,0);
        else if(!strcmp(a,"--clipdist")) clipdist=strtol(NEXT,0,0);
        else if(!strcmp(a,"--pointsize")) { hasPS=1; psize=strtod(NEXT,0); }
        else if(!strcmp(a,"--fill")) fillS=NEXT;
        else if(!strcmp(a,"--a2c")) a2c=1;
        else if(!strcmp(a,"--a2o")) a2o=1;
        else if(!strcmp(a,"--calpha")) g_calpha=strtod(NEXT,0);
        else if(!strcmp(a,"--iters")) iters=strtol(NEXT,0,0);
        else if(!strcmp(a,"--dump")) doDump=1;
        else printf("UNKNOWN ARG %s\n", a);
        #undef NEXT
    }
    int bpp = 4;
    MTLPixelFormat fmt = !strcmp(fmtS,"rgba8") ? MTLPixelFormatRGBA8Unorm : MTLPixelFormatBGRA8Unorm;

    MTLPrimitiveType prim = MTLPrimitiveTypeTriangle;
    MTLPrimitiveTopologyClass topo = MTLPrimitiveTopologyClassTriangle;
    if(!strcmp(primS,"point"))          { prim=MTLPrimitiveTypePoint;         topo=MTLPrimitiveTopologyClassPoint; }
    else if(!strcmp(primS,"line"))      { prim=MTLPrimitiveTypeLine;          topo=MTLPrimitiveTopologyClassLine; }
    else if(!strcmp(primS,"linestrip")) { prim=MTLPrimitiveTypeLineStrip;     topo=MTLPrimitiveTopologyClassLine; }
    else if(!strcmp(primS,"tristrip"))  { prim=MTLPrimitiveTypeTriangleStrip; topo=MTLPrimitiveTopologyClassTriangle; }
    if(restart && prim==MTLPrimitiveTypeTriangle) { prim=MTLPrimitiveTypeTriangleStrip; topo=MTLPrimitiveTopologyClassTriangle; }

    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name] UTF8String]);
    printf("CONFIG w=%ld h=%ld fmt=%s msaa=%ld prim=%s indexed=%d itype=%s restart=%d nvp=%ld vpmod=%d "
           "nsc=%ld scmod=%d vpidx=%ld clipdist=%ld pointsize=%d(%g) fill=%s a2c=%d a2o=%d\n",
           W,H,fmtS,msaa,primS,indexed,itypeS,restart,nvp,vpmod,nsc,scmod,vpidx,clipdist,hasPS,psize,fillS,a2c,a2o);

    NSError *err=nil;
    NSString *vs=make_vsrc(hasPS, (int)clipdist, vpidx>=0, (int)vpidx, psize);
    id<MTLLibrary> vl=[dev newLibraryWithSource:vs options:nil error:&err];
    if(!vl){ printf("SHADER_FAIL(vs) %s\n",[[err localizedDescription] UTF8String]); return 1; }
    id<MTLLibrary> fl=[dev newLibraryWithSource:make_fsrc() options:nil error:&err];
    if(!fl){ printf("SHADER_FAIL(fs) %s\n",[[err localizedDescription] UTF8String]); return 1; }

    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
    pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=fmt;
    pd.rasterSampleCount=(NSUInteger)msaa;
    if(a2c) pd.alphaToCoverageEnabled=YES;
    if(a2o) pd.alphaToOneEnabled=YES;
    if(prim==MTLPrimitiveTypePoint) pd.inputPrimitiveTopology=topo;   // needed for point/line class in some paths
    id<MTLRenderPipelineState> pso=nil;
    @try { pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err]; }
    @catch(NSException *e){ printf("PIPELINE_EXC %s\n",[[e reason] UTF8String]); return 1; }
    if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

    // ---- render target (+ optional MSAA) ----
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt
                               width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
    td.storageMode=MTLStorageModeShared;
    id<MTLBuffer> rtb=[dev newBufferWithLength:((W*bpp+255)&~255UL)*H options:MTLResourceStorageModeShared];
    NSUInteger bpr=((W*bpp+255)&~255UL);
    id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
    if(target) print_va("rtBuf",[rtb gpuAddress]); else { target=[dev newTextureWithDescriptor:td]; printf("RTBUF_REJECTED\n"); }
    id<MTLTexture> msTex=nil;
    if(msaa>1){
        MTLTextureDescriptor *md=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt
                                   width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
        md.textureType=MTLTextureType2DMultisample; md.sampleCount=(NSUInteger)msaa;
        md.usage=MTLTextureUsageRenderTarget; md.storageMode=MTLStorageModePrivate;
        msTex=[dev newTextureWithDescriptor:md];
    }

    // ---- index buffer (indexed / restart) ----
    id<MTLBuffer> ib=nil; NSUInteger idxCount=0; int u32=!strcmp(itypeS,"u32");
    if(indexed){
        // triangle-strip indices; with --restart insert a cut value in the middle.
        // u16 restart cut = 0xffff; u32 cut = 0xffffffff (Metal implicit restart).
        uint32_t seq32[8]; int n=0;
        seq32[n++]=0; seq32[n++]=1; seq32[n++]=2; seq32[n++]=3;
        if(restart){ seq32[n++]= u32?0xffffffffu:0xffffu; seq32[n++]=0; seq32[n++]=1; seq32[n++]=2; }
        idxCount=n;
        if(u32){ ib=[dev newBufferWithLength:idxCount*4 options:MTLResourceStorageModeShared];
                 uint32_t *q=(uint32_t*)[ib contents]; for(int k=0;k<n;k++) q[k]=seq32[k]; }
        else   { ib=[dev newBufferWithLength:idxCount*2 options:MTLResourceStorageModeShared];
                 uint16_t *q=(uint16_t*)[ib contents]; for(int k=0;k<n;k++) q[k]=(uint16_t)seq32[k]; }
        print_va("idxBuf",[ib gpuAddress]);
    }

    id<MTLCommandQueue> q=[dev newCommandQueue];
    for(long it=0; it<iters; it++){
        printf("SUBMIT iter=%ld begin\n", it);
        MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
        if(msaa>1){ rp.colorAttachments[0].texture=msTex;
                    rp.colorAttachments[0].resolveTexture=target;
                    rp.colorAttachments[0].storeAction=MTLStoreActionMultisampleResolve; }
        else      { rp.colorAttachments[0].texture=target;
                    rp.colorAttachments[0].storeAction=MTLStoreActionStore; }
        rp.colorAttachments[0].loadAction=MTLLoadActionClear;
        rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
        id<MTLCommandBuffer> cb=[q commandBuffer];
        id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
        [enc setRenderPipelineState:pso];

        // ---- viewport(s) ----
        @try {
        if(nvp<=0){
            MTLViewport vp={0.0,0.0,(double)W,(double)H,0.0,1.0};
            [enc setViewport:vp];
        } else {
            MTLViewport vps[16];
            for(long i=0;i<nvp && i<16;i++){
                vps[i].originX=(double)i; vps[i].originY=(double)(2*i);
                vps[i].width=(double)(60-2*i); vps[i].height=(double)(50-i);
                vps[i].znear=0.02*i; vps[i].zfar=1.0-0.02*i;
                if(vpmod && i==1){ vps[i].height+=7.0; vps[i].znear=0.31; }
            }
            [enc setViewports:vps count:(NSUInteger)nvp];
        }
        } @catch(NSException *e){ printf("VIEWPORT_EXC n=%ld %s\n", nvp, [[e reason] UTF8String]); }

        // ---- scissor(s) ----
        @try {
        if(nsc>0){
            MTLScissorRect scs[16];
            for(long i=0;i<nsc && i<16;i++){
                scs[i].x=(NSUInteger)i; scs[i].y=(NSUInteger)(2*i);
                scs[i].width=(NSUInteger)(32-i); scs[i].height=(NSUInteger)(30-i);
                if(scmod && i==1){ scs[i].height+=5; scs[i].x=7; }
            }
            [enc setScissorRects:scs count:(NSUInteger)nsc];
        }
        } @catch(NSException *e){ printf("SCISSOR_EXC n=%ld %s\n", nsc, [[e reason] UTF8String]); }

        [enc setTriangleFillMode:!strcmp(fillS,"lines")?MTLTriangleFillModeLines:MTLTriangleFillModeFill];

        // ---- draw ----
        @try {
        if(indexed)
            [enc drawIndexedPrimitives:prim indexCount:idxCount
                             indexType:(u32?MTLIndexTypeUInt32:MTLIndexTypeUInt16)
                           indexBuffer:ib indexBufferOffset:0];
        else
            [enc drawPrimitives:prim vertexStart:0 vertexCount:4];
        } @catch(NSException *e){ printf("DRAW_EXC %s\n",[[e reason] UTF8String]); }

        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        printf("SUBMIT iter=%ld done status=%ld\n", it,(long)[cb status]);
        if([cb error]) printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);
        if(doDump&&it==iters-1){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
    }
    return 0;
  }
}
