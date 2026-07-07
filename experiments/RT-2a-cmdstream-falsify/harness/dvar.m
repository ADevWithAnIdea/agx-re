// dvar.m — parametric OWN Metal DRAW for change-one-parameter cmdstream RE.
//
// Part of EXP-0014 (Phase 2 cmdstream decode, graphics side). The render analogue
// of EXP-0011's cvar.m: one small triangle draw whose every submission parameter is
// a CLI flag, so we can change exactly ONE Metal parameter, re-capture the registered
// GPU buffer objects under the iotrace interposer, and byte-diff the snapshots to
// localise each field of the tiler(TA) / fragment(3D) control lists, the draw
// parameters, viewport/scissor, the render-target descriptor, and pipeline state.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Every shader here is our own MSL,
// compiled at runtime. We print the GPU virtual addresses of our own resources so the
// captured bytes can be correlated. Nothing disassembles any Apple binary.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o dvar dvar.m
//
// Usage:
//   dvar [--w W --h H] [--vpw N --vph N] [--verts N] [--prim P] [--inst N]
//        [--fmt F] [--cr R --cg G --cb B --ca A] [--indexed] [--blend] [--depth]
//        [--vshader small|big] [--fshader small|big] [--two] [--iters N]
//        [--dump] [--dumpall] [--rtbuf 0|1]
//
//   --prim : tri (default) | strip | line | linestrip | point
//   --fmt  : bgra8 (default) | rgba8 | rgba16f | rgba32f | r8
//   --two  : encode a SECOND draw (different pipeline) in the same encoder, for an
//            intra-capture shader-pointer confirmation.
//   --rtbuf: back the render target with an MTLBuffer so its GPU VA is printable
//            (default 1). If linear RT is rejected, pass --rtbuf 0.

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

// A vertex shader that reads clip-space positions from buffer(0), so we get a
// correlatable vertex-buffer VA. "big" inflates register/instruction pressure.
static NSString *vsrc(int big) {
    NSString *body = big ?
      @"  float2 q = p[vid];\n"
       "  float v0=q.x*1.01,v1=q.y*1.02,v2=q.x*1.03,v3=q.y*1.04,v4=q.x*1.05,v5=q.y*1.06,\n"
       "        v6=q.x*1.07,v7=q.y*1.08,v8=q.x*1.09,v9=q.y*1.10,va=q.x*1.11,vb=q.y*1.12;\n"
       "  for(int j=0;j<4;j++){ v0=fma(v0,v1,vb); v1=fma(v1,v2,va); v2=fma(v2,v3,v9);\n"
       "    v3=fma(v3,v4,v8); v4=fma(v4,v5,v7); v5=fma(v5,v6,v0); v6=fma(v6,v7,v1);\n"
       "    v7=fma(v7,v8,v2); v8=fma(v8,v9,v3); v9=fma(v9,va,v4); va=fma(va,vb,v5); vb=fma(vb,v0,v6);}\n"
       "  float2 pos = q + float2(v0+v2+v4+v6+v8+va, v1+v3+v5+v7+v9+vb)*0.0f;\n"
       "  VO o; o.pos = float4(pos, 0, 1); o.col = float4(0.25,0.5,0.75,1)*(1.0+v0*0.0); return o;\n"
      :
      @"  VO o; o.pos = float4(p[vid], 0, 1); o.col = float4(0.25,0.5,0.75,1); return o;\n";
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]]; float4 col; };\n"
       "vertex VO v_main(uint vid [[vertex_id]], uint iid [[instance_id]],\n"
       "                 const device float2* p [[buffer(0)]]) {\n%@}\n", body];
}

static NSString *fsrc(int big) {
    NSString *body = big ?
      @"  float v0=in.col.x,v1=in.col.y,v2=in.col.z,v3=in.col.w,v4=0.5,v5=0.25,v6=0.75,v7=0.1;\n"
       "  for(int j=0;j<4;j++){ v0=fma(v0,v1,v7); v1=fma(v1,v2,v6); v2=fma(v2,v3,v5);\n"
       "    v3=fma(v3,v4,v0); v4=fma(v4,v5,v1); v5=fma(v5,v6,v2); v6=fma(v6,v7,v3); v7=fma(v7,v0,v4);}\n"
       "  return in.col + float4(v0+v1+v2+v3+v4+v5+v6+v7)*0.0f;\n"
      :
      @"  return in.col;\n";
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]]; float4 col; };\n"
       "fragment float4 f_main(VO in [[stage_in]]) {\n%@}\n", body];
}

static MTLPixelFormat parse_fmt(const char *s, int *bpp) {
    if (!strcmp(s,"rgba8"))   { *bpp=4;  return MTLPixelFormatRGBA8Unorm; }
    if (!strcmp(s,"rgba16f")) { *bpp=8;  return MTLPixelFormatRGBA16Float; }
    if (!strcmp(s,"rgba32f")) { *bpp=16; return MTLPixelFormatRGBA32Float; }
    if (!strcmp(s,"r8"))      { *bpp=1;  return MTLPixelFormatR8Unorm; }
    *bpp=4; return MTLPixelFormatBGRA8Unorm;      // "bgra8" default
}

static MTLPrimitiveType parse_prim(const char *s) {
    if (!strcmp(s,"point"))     return MTLPrimitiveTypePoint;
    if (!strcmp(s,"line"))      return MTLPrimitiveTypeLine;
    if (!strcmp(s,"linestrip")) return MTLPrimitiveTypeLineStrip;
    if (!strcmp(s,"strip"))     return MTLPrimitiveTypeTriangleStrip;
    return MTLPrimitiveTypeTriangle;
}

static id<MTLRenderPipelineState> mkpso(id<MTLDevice> dev, int vbig, int fbig,
                                        MTLPixelFormat fmt, int blend, int depth, NSError **err) {
    id<MTLLibrary> vl=[dev newLibraryWithSource:vsrc(vbig) options:nil error:err];
    id<MTLLibrary> fl=[dev newLibraryWithSource:fsrc(fbig) options:nil error:err];
    if(!vl||!fl) return nil;
    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
    pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
    pd.colorAttachments[0].pixelFormat=fmt;
    if(blend){
        pd.colorAttachments[0].blendingEnabled=YES;
        pd.colorAttachments[0].rgbBlendOperation=MTLBlendOperationAdd;
        pd.colorAttachments[0].sourceRGBBlendFactor=MTLBlendFactorSourceAlpha;
        pd.colorAttachments[0].destinationRGBBlendFactor=MTLBlendFactorOneMinusSourceAlpha;
    }
    if(depth) pd.depthAttachmentPixelFormat=MTLPixelFormatDepth32Float;
    return [dev newRenderPipelineStateWithDescriptor:pd error:err];
}

int main(int argc, char **argv) {
    @autoreleasepool {
        long W=64,H=64,vpw=-1,vph=-1,verts=3,inst=1,iters=1;
        const char *primS="tri", *fmtS="bgra8", *vsh="small", *fsh="small";
        int indexed=0, blend=0, depth=0, two=0, doDump=0, doDumpAll=0, rtbuf=1;
        float cr=0,cg=0,cb=0,ca=1;
        for(int i=1;i<argc;i++){
            if(!strcmp(argv[i],"--w")&&i+1<argc) W=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--h")&&i+1<argc) H=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--vpw")&&i+1<argc) vpw=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--vph")&&i+1<argc) vph=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--verts")&&i+1<argc) verts=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--inst")&&i+1<argc) inst=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--prim")&&i+1<argc) primS=argv[++i];
            else if(!strcmp(argv[i],"--fmt")&&i+1<argc) fmtS=argv[++i];
            else if(!strcmp(argv[i],"--vshader")&&i+1<argc) vsh=argv[++i];
            else if(!strcmp(argv[i],"--fshader")&&i+1<argc) fsh=argv[++i];
            else if(!strcmp(argv[i],"--cr")&&i+1<argc) cr=strtof(argv[++i],0);
            else if(!strcmp(argv[i],"--cg")&&i+1<argc) cg=strtof(argv[++i],0);
            else if(!strcmp(argv[i],"--cb")&&i+1<argc) cb=strtof(argv[++i],0);
            else if(!strcmp(argv[i],"--ca")&&i+1<argc) ca=strtof(argv[++i],0);
            else if(!strcmp(argv[i],"--iters")&&i+1<argc) iters=strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--rtbuf")&&i+1<argc) rtbuf=(int)strtol(argv[++i],0,0);
            else if(!strcmp(argv[i],"--indexed")) indexed=1;
            else if(!strcmp(argv[i],"--blend")) blend=1;
            else if(!strcmp(argv[i],"--depth")) depth=1;
            else if(!strcmp(argv[i],"--two")) two=1;
            else if(!strcmp(argv[i],"--dump")) doDump=1;
            else if(!strcmp(argv[i],"--dumpall")) doDumpAll=1;
        }
        if(vpw<0) vpw=W; if(vph<0) vph=H;
        int bpp=4; MTLPixelFormat fmt=parse_fmt(fmtS,&bpp);
        MTLPrimitiveType prim=parse_prim(primS);

        id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n",[[dev name] UTF8String]);
        printf("CONFIG w=%ld h=%ld vp=(%ld,%ld) verts=%ld prim=%s inst=%ld fmt=%s bpp=%d "
               "indexed=%d blend=%d depth=%d vsh=%s fsh=%s two=%d iters=%ld rtbuf=%d\n",
               W,H,vpw,vph,verts,primS,inst,fmtS,bpp,indexed,blend,depth,vsh,fsh,two,iters,rtbuf);

        NSError *err=nil;
        id<MTLRenderPipelineState> pso=mkpso(dev,!strcmp(vsh,"big"),!strcmp(fsh,"big"),fmt,blend,depth,&err);
        if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

        id<MTLRenderPipelineState> pso2=nil;
        if(two){ pso2=mkpso(dev,1,1,fmt,blend,depth,&err); if(!pso2) printf("PSO2_FAIL\n"); }

        // ---- render target ----
        MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt
                                   width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
        td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
        td.storageMode=MTLStorageModeShared;
        id<MTLTexture> target=nil; id<MTLBuffer> rtb=nil;
        NSUInteger bpr=(NSUInteger)(W*bpp); bpr=(bpr+255)&~255UL;   // 256B align for linear
        if(rtbuf){
            rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
            target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
            if(target) print_va("rtBuf",[rtb gpuAddress]);
            else printf("RTBUF_REJECTED falling back to device texture\n");
        }
        if(!target) target=[dev newTextureWithDescriptor:td];

        id<MTLTexture> depthTex=nil; id<MTLDepthStencilState> dss=nil;
        if(depth){
            MTLTextureDescriptor *dd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float
                                       width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
            dd.usage=MTLTextureUsageRenderTarget; dd.storageMode=MTLStorageModePrivate;
            depthTex=[dev newTextureWithDescriptor:dd];
            MTLDepthStencilDescriptor *dsd=[MTLDepthStencilDescriptor new];
            dsd.depthCompareFunction=MTLCompareFunctionLess; dsd.depthWriteEnabled=YES;
            dss=[dev newDepthStencilStateWithDescriptor:dsd];
        }

        // ---- vertex + index buffers (so their VAs are correlatable) ----
        long nv = verts>0?verts:3;
        id<MTLBuffer> vb=[dev newBufferWithLength:(NSUInteger)(nv*8) options:MTLResourceStorageModeShared];
        float *vp=(float*)[vb contents];
        for(long i=0;i<nv;i++){ float t=(float)i/(float)(nv>1?nv-1:1);
            vp[2*i+0]=-1.0f+2.0f*t; vp[2*i+1]=(i%2)?-1.0f:1.0f; }
        // valid full-screen triangle for the first 3 verts (so a --verts 3 draw is sane)
        if(nv>=3){ vp[0]=-1;vp[1]=-1; vp[2]=3;vp[3]=-1; vp[4]=-1;vp[5]=3; }
        print_va("vtxBuf",[vb gpuAddress]);

        id<MTLBuffer> ib=nil; long nidx=nv;
        if(indexed){
            ib=[dev newBufferWithLength:(NSUInteger)(nidx*2) options:MTLResourceStorageModeShared];
            uint16_t *ip=(uint16_t*)[ib contents];
            for(long i=0;i<nidx;i++) ip[i]=(uint16_t)i;
            print_va("idxBuf",[ib gpuAddress]);
        }
        id<MTLBuffer> vb2=nil;
        if(two){ vb2=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
                 float*p=(float*)[vb2 contents]; p[0]=-1;p[1]=-1;p[2]=1;p[3]=-1;p[4]=-1;p[5]=1;
                 print_va("vtxBuf2",[vb2 gpuAddress]); }

        id<MTLCommandQueue> q=[dev newCommandQueue];
        for(long it=0; it<iters; it++){
            printf("SUBMIT iter=%ld begin\n", it);
            MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
            rp.colorAttachments[0].texture=target;
            rp.colorAttachments[0].loadAction=MTLLoadActionClear;
            rp.colorAttachments[0].clearColor=MTLClearColorMake(cr,cg,cb,ca);
            rp.colorAttachments[0].storeAction=MTLStoreActionStore;
            if(depth){ rp.depthAttachment.texture=depthTex;
                       rp.depthAttachment.loadAction=MTLLoadActionClear;
                       rp.depthAttachment.clearDepth=1.0;
                       rp.depthAttachment.storeAction=MTLStoreActionDontCare; }
            id<MTLCommandBuffer> cb=[q commandBuffer];
            id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:pso];
            MTLViewport vp={0.0,0.0,(double)vpw,(double)vph,0.0,1.0};
            [enc setViewport:vp];
            [enc setVertexBuffer:vb offset:0 atIndex:0];
            if(dss) [enc setDepthStencilState:dss];
            if(indexed)
                [enc drawIndexedPrimitives:prim indexCount:(NSUInteger)nidx
                     indexType:MTLIndexTypeUInt16 indexBuffer:ib indexBufferOffset:0
                     instanceCount:(NSUInteger)inst];
            else
                [enc drawPrimitives:prim vertexStart:0 vertexCount:(NSUInteger)nv
                     instanceCount:(NSUInteger)inst];
            if(pso2){ [enc setRenderPipelineState:pso2];
                      [enc setVertexBuffer:vb2 offset:0 atIndex:0];
                      [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3
                           instanceCount:1]; }
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
            printf("SUBMIT iter=%ld done status=%ld\n", it,(long)[cb status]);
            if((doDumpAll)||(doDump&&it==iters-1)){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
        }

        if(!depth){
            unsigned char px[16]; memset(px,0,sizeof px);
            [target getBytes:px bytesPerRow:bpr fromRegion:MTLRegionMake2D(0,0,1,1) mipmapLevel:0];
            printf("PIXEL b0..3=%02x%02x%02x%02x\n",px[0],px[1],px[2],px[3]);
        }
        return 0;
    }
}
