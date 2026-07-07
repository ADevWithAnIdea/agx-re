// tvar.m — parametric OWN Metal DRAW focused on TBDR pipeline config (EXP-0021).
//
// Extends the EXP-0014 dvar.m change-one-parameter draw harness with the
// TBDR-specific knobs a driver must emit and know: MSAA sample count, programmable
// sample positions, memoryless (tile-only) attachments, per-attachment load/store
// actions, multiple render targets (imageblock scaling), depth-only / partial
// render, and render-target size/format sweeps (tile-size scaling).
//
// The method is identical to EXP-0011/-0014: change exactly ONE Metal parameter,
// re-capture the registered GPU buffer objects under the iotrace interposer, and
// byte-diff the snapshots to localise each TBDR field in the tiler/tiling context
// (0x68000), the 3D attachment descriptor (0x10000110000), the FF-state pool
// (0x58000), and the tiler parameter heap (0x10000088000 / 0x10000140000).
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Every shader here is our own MSL
// compiled at runtime. We print the GPU virtual addresses of our own resources so
// captured bytes can be correlated. Nothing disassembles any Apple binary.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o tvar tvar.m
//
// Usage:
//   tvar [--w W --h H] [--vpw N --vph N] [--fmt F] [--cr..--ca C]
//        [--samples N] [--sampos] [--mrt N] [--depth] [--stencil]
//        [--mldepth] [--mlcolor] [--nocolor]
//        [--load clear|load|dontcare] [--store store|dontcare]
//        [--dload clear|load|dontcare] [--dstore store|dontcare]
//        [--iters N] [--dump] [--dumpall]
//
//   --fmt     : bgra8 (default) | rgba8 | rgba16f | rgba32f | r8 | rg11b10 | rgb10a2 | r32f
//   --samples : 1 (default) | 2 | 4  (MSAA; color becomes 2DMultisample + resolve)
//   --sampos  : set custom programmable sample positions (requires --samples >= 2)
//   --mrt     : number of color attachments 1..4 (single-sample only)
//   --mldepth : depth attachment storageMode = Memoryless (baseline Private)
//   --mlcolor : MSAA color storageMode = Memoryless (baseline Private; needs --samples>=2)
//   --nocolor : depth-only render pass (no color attachment)
//   --load/--store  : color[0] load / store action
//   --dload/--dstore: depth load / store action

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

static MTLPixelFormat parse_fmt(const char *s, int *bpp) {
    if (!strcmp(s,"rgba8"))   { *bpp=4;  return MTLPixelFormatRGBA8Unorm; }
    if (!strcmp(s,"rgba16f")) { *bpp=8;  return MTLPixelFormatRGBA16Float; }
    if (!strcmp(s,"rgba32f")) { *bpp=16; return MTLPixelFormatRGBA32Float; }
    if (!strcmp(s,"r8"))      { *bpp=1;  return MTLPixelFormatR8Unorm; }
    if (!strcmp(s,"r32f"))    { *bpp=4;  return MTLPixelFormatR32Float; }
    if (!strcmp(s,"rg11b10")) { *bpp=4;  return MTLPixelFormatRG11B10Float; }
    if (!strcmp(s,"rgb10a2")) { *bpp=4;  return MTLPixelFormatRGB10A2Unorm; }
    *bpp=4; return MTLPixelFormatBGRA8Unorm;      // "bgra8" default
}

static MTLLoadAction parse_load(const char *s) {
    if (!strcmp(s,"load"))     return MTLLoadActionLoad;
    if (!strcmp(s,"dontcare")) return MTLLoadActionDontCare;
    return MTLLoadActionClear;
}
static MTLStoreAction parse_store(const char *s) {
    if (!strcmp(s,"dontcare")) return MTLStoreActionDontCare;
    return MTLStoreActionStore;
}

// Vertex shader: reads clip-space positions from buffer(0) so we get a
// correlatable vertex-buffer VA.
static NSString *vsrc(void) {
    return
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]]; float4 col; };\n"
       "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]) {\n"
       "  VO o; o.pos = float4(p[vid], 0, 1); o.col = float4(0.25,0.5,0.75,1); return o;\n}\n";
}

// Fragment shader with N color outputs (MRT). N==1 => plain float4.
static NSString *fsrc(int nrt) {
    if (nrt <= 1)
        return
          @"#include <metal_stdlib>\nusing namespace metal;\n"
           "struct VO { float4 pos [[position]]; float4 col; };\n"
           "fragment float4 f_main(VO in [[stage_in]]) { return in.col; }\n";
    NSMutableString *s = [NSMutableString stringWithString:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]]; float4 col; };\n"
       "struct FO {\n"];
    for (int i=0;i<nrt;i++) [s appendFormat:@"  float4 c%d [[color(%d)]];\n", i, i];
    [s appendString:@"};\nfragment FO f_main(VO in [[stage_in]]) {\n  FO o;\n"];
    for (int i=0;i<nrt;i++) [s appendFormat:@"  o.c%d = in.col*float(%d+1)*0.25;\n", i, i];
    [s appendString:@"  return o;\n}\n"];
    return s;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        long W=64,H=64,vpw=-1,vph=-1,iters=1,samples=1,mrt=1;
        const char *fmtS="bgra8";
        const char *loadS="clear",*storeS="store",*dloadS="clear",*dstoreS="dontcare";
        int depth=0,stencil=0,mldepth=0,mlcolor=0,nocolor=0,sampos=0,doDump=0,doDumpAll=0;
        float cr=0,cg=0,cb=0,ca=1;
        for(int i=1;i<argc;i++){
            if(!strcmp(argv[i],"--w")&&i+1<argc) W=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--h")&&i+1<argc) H=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--vpw")&&i+1<argc) vpw=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--vph")&&i+1<argc) vph=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--fmt")&&i+1<argc) fmtS=argv[++i];
            else if(!strcmp(argv[i],"--samples")&&i+1<argc) samples=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--mrt")&&i+1<argc) mrt=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--load")&&i+1<argc) loadS=argv[++i];
            else if(!strcmp(argv[i],"--store")&&i+1<argc) storeS=argv[++i];
            else if(!strcmp(argv[i],"--dload")&&i+1<argc) dloadS=argv[++i];
            else if(!strcmp(argv[i],"--dstore")&&i+1<argc) dstoreS=argv[++i];
            else if(!strcmp(argv[i],"--cr")&&i+1<argc) cr=strtof(argv[++i],0);
            else if(!strcmp(argv[i],"--cg")&&i+1<argc) cg=strtof(argv[++i],0);
            else if(!strcmp(argv[i],"--cb")&&i+1<argc) cb=strtof(argv[++i],0);
            else if(!strcmp(argv[i],"--ca")&&i+1<argc) ca=strtof(argv[++i],0);
            else if(!strcmp(argv[i],"--iters")&&i+1<argc) iters=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--depth")) depth=1;
            else if(!strcmp(argv[i],"--stencil")) { depth=1; stencil=1; }
            else if(!strcmp(argv[i],"--mldepth")) mldepth=1;
            else if(!strcmp(argv[i],"--mlcolor")) mlcolor=1;
            else if(!strcmp(argv[i],"--nocolor")) nocolor=1;
            else if(!strcmp(argv[i],"--sampos")) sampos=1;
            else if(!strcmp(argv[i],"--dump")) doDump=1;
            else if(!strcmp(argv[i],"--dumpall")) doDumpAll=1;
        }
        if(vpw<0) vpw=W; if(vph<0) vph=H;
        if(mrt<1) mrt=1; if(mrt>4) mrt=4;
        int bpp=4; MTLPixelFormat fmt=parse_fmt(fmtS,&bpp);
        MTLPixelFormat dfmt = stencil ? MTLPixelFormatDepth32Float_Stencil8 : MTLPixelFormatDepth32Float;

        id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n",[[dev name] UTF8String]);
        printf("CONFIG w=%ld h=%ld vp=(%ld,%ld) fmt=%s bpp=%d samples=%ld sampos=%d mrt=%ld "
               "depth=%d stencil=%d mldepth=%d mlcolor=%d nocolor=%d load=%s store=%s dload=%s dstore=%s\n",
               W,H,vpw,vph,fmtS,bpp,samples,sampos,mrt,depth,stencil,mldepth,mlcolor,nocolor,
               loadS,storeS,dloadS,dstoreS);

        // ---- pipeline ----
        NSError *err=nil;
        id<MTLLibrary> vl=[dev newLibraryWithSource:vsrc() options:nil error:&err];
        id<MTLLibrary> fl=[dev newLibraryWithSource:fsrc((int)(nocolor?0:mrt)) options:nil error:&err];
        if(!vl||(!nocolor&&!fl)){ printf("PIPELINE_FAIL lib %s\n",[[err localizedDescription] UTF8String]); return 1; }
        MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
        pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
        pd.fragmentFunction = nocolor ? nil : [fl newFunctionWithName:@"f_main"];
        if(!nocolor) for(int i=0;i<mrt;i++) pd.colorAttachments[i].pixelFormat=fmt;
        if(depth) pd.depthAttachmentPixelFormat=dfmt;
        if(stencil) pd.stencilAttachmentPixelFormat=dfmt;
        if(samples>1) pd.rasterSampleCount=(NSUInteger)samples;
        id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if(!pso){ printf("PIPELINE_FAIL pso %s\n",[[err localizedDescription] UTF8String]); return 1; }

        // ---- color attachment(s) ----
        // Single-sample, mrt==1: buffer-backed shared so the RT VA is printable & readable.
        // MSAA: private (or memoryless) multisample color + buffer-backed shared resolve.
        NSUInteger bpr=(NSUInteger)(W*bpp); bpr=(bpr+255)&~255UL;
        id<MTLTexture> color[4]={nil,nil,nil,nil};
        id<MTLTexture> msaaColor=nil, resolveTex=nil; id<MTLBuffer> rtb=nil, resb=nil;

        if(!nocolor){
            if(samples>1){
                MTLTextureDescriptor *md=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt
                                           width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
                md.textureType=MTLTextureType2DMultisample; md.sampleCount=(NSUInteger)samples;
                md.usage=MTLTextureUsageRenderTarget;
                md.storageMode=mlcolor?MTLStorageModeMemoryless:MTLStorageModePrivate;
                msaaColor=[dev newTextureWithDescriptor:md];
                // resolve target (single-sample, buffer-backed shared, readable)
                MTLTextureDescriptor *rd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt
                                           width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
                rd.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
                rd.storageMode=MTLStorageModeShared;
                resb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
                resolveTex=[resb newTextureWithDescriptor:rd offset:0 bytesPerRow:bpr];
                if(!resolveTex) resolveTex=[dev newTextureWithDescriptor:rd];
                else print_va("resBuf",[resb gpuAddress]);
                color[0]=msaaColor;
            } else {
                for(int i=0;i<mrt;i++){
                    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt
                                               width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
                    td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
                    td.storageMode=MTLStorageModeShared;
                    if(i==0){
                        rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
                        color[0]=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
                        if(color[0]) print_va("rtBuf",[rtb gpuAddress]); else color[0]=[dev newTextureWithDescriptor:td];
                    } else {
                        color[i]=[dev newTextureWithDescriptor:td];
                    }
                }
            }
        }

        // ---- depth / stencil attachment ----
        id<MTLTexture> depthTex=nil; id<MTLDepthStencilState> dss=nil;
        if(depth){
            MTLTextureDescriptor *dd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:dfmt
                                       width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
            if(samples>1){ dd.textureType=MTLTextureType2DMultisample; dd.sampleCount=(NSUInteger)samples; }
            dd.usage=MTLTextureUsageRenderTarget;
            dd.storageMode=mldepth?MTLStorageModeMemoryless:MTLStorageModePrivate;
            depthTex=[dev newTextureWithDescriptor:dd];
            MTLDepthStencilDescriptor *dsd=[MTLDepthStencilDescriptor new];
            dsd.depthCompareFunction=MTLCompareFunctionLess; dsd.depthWriteEnabled=YES;
            if(stencil){
                MTLStencilDescriptor *sd=[MTLStencilDescriptor new];
                sd.stencilCompareFunction=MTLCompareFunctionAlways;
                sd.depthStencilPassOperation=MTLStencilOperationReplace;
                dsd.frontFaceStencil=sd; dsd.backFaceStencil=sd;
            }
            dss=[dev newDepthStencilStateWithDescriptor:dsd];
        }

        // ---- vertex buffer (full-screen triangle) ----
        id<MTLBuffer> vb=[dev newBufferWithLength:24 options:MTLResourceStorageModeShared];
        float *vp=(float*)[vb contents];
        vp[0]=-1;vp[1]=-1; vp[2]=3;vp[3]=-1; vp[4]=-1;vp[5]=3;
        print_va("vtxBuf",[vb gpuAddress]);

        id<MTLCommandQueue> q=[dev newCommandQueue];
        for(long it=0; it<iters; it++){
            printf("SUBMIT iter=%ld begin\n", it);
            MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
            if(!nocolor){
                for(int i=0;i<(samples>1?1:mrt);i++){
                    rp.colorAttachments[i].texture=color[i];
                    rp.colorAttachments[i].loadAction=parse_load(loadS);
                    rp.colorAttachments[i].clearColor=MTLClearColorMake(cr,cg,cb,ca);
                    if(samples>1){
                        rp.colorAttachments[i].resolveTexture=resolveTex;
                        rp.colorAttachments[i].storeAction=MTLStoreActionMultisampleResolve;
                    } else {
                        rp.colorAttachments[i].storeAction=parse_store(storeS);
                    }
                }
            }
            if(depth){
                rp.depthAttachment.texture=depthTex;
                rp.depthAttachment.loadAction=parse_load(dloadS);
                rp.depthAttachment.clearDepth=1.0;
                rp.depthAttachment.storeAction=parse_store(dstoreS);
                if(stencil){
                    rp.stencilAttachment.texture=depthTex;
                    rp.stencilAttachment.loadAction=parse_load(dloadS);
                    rp.stencilAttachment.clearStencil=0;
                    rp.stencilAttachment.storeAction=parse_store(dstoreS);
                }
            }
            if(sampos && samples>1){
                // custom programmable sample positions (in [0,1) tile-local units)
                MTLSamplePosition pos2[2]={{0.1,0.1},{0.9,0.9}};
                MTLSamplePosition pos4[4]={{0.1,0.1},{0.9,0.3},{0.3,0.9},{0.7,0.7}};
                if(samples==2)      [rp setSamplePositions:pos2 count:2];
                else if(samples==4) [rp setSamplePositions:pos4 count:4];
            }
            id<MTLCommandBuffer> cb=[q commandBuffer];
            id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:pso];
            MTLViewport vpp={0.0,0.0,(double)vpw,(double)vph,0.0,1.0};
            [enc setViewport:vpp];
            [enc setVertexBuffer:vb offset:0 atIndex:0];
            if(dss) [enc setDepthStencilState:dss];
            if(stencil) [enc setStencilReferenceValue:1];
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
            printf("SUBMIT iter=%ld done status=%ld err=%s\n", it,(long)[cb status],
                   [cb error]?[[[cb error] localizedDescription] UTF8String]:"none");
            if((doDumpAll)||(doDump&&it==iters-1)){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
        }

        // readback (single-sample color[0] buffer-backed, or MSAA resolve target)
        id<MTLTexture> rb = (samples>1)?resolveTex:color[0];
        if(rb && !nocolor && rb.storageMode==MTLStorageModeShared){
            unsigned char px[16]; memset(px,0,sizeof px);
            [rb getBytes:px bytesPerRow:bpr fromRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0];
            printf("PIXEL b0..3=%02x%02x%02x%02x\n",px[0],px[1],px[2],px[3]);
        }
        return 0;
    }
}
