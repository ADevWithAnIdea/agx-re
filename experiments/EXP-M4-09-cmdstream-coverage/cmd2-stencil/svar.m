// svar.m — parametric OWN Metal DRAW for FIXED-FUNCTION STATE-PACKET RE.
//
// Part of EXP-0019 (Phase 2 cmdstream decode: graphics fixed-function state
// packets + USC bind grammar). The state analogue of EXP-0014's dvar.m: one small
// triangle draw whose every DEPTH/STENCIL, BLEND, and RASTERIZER state parameter is
// a CLI flag, so we can change exactly ONE Metal state parameter, re-capture the
// registered GPU buffer objects under the iotrace interposer, and byte-diff the
// snapshots to localise each field of the 0x58000 fixed-function state pool, the
// 0x18000 VDM stream, and the 0x10000130000 USC binding program.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Every shader here is our own MSL,
// compiled at runtime. We print the GPU virtual addresses of our own resources so the
// captured bytes can be correlated. Nothing disassembles any Apple binary.
//
// Build (device): clang -fobjc-arc -framework Metal -framework Foundation -o svar svar.m
//
// Usage (all flags optional; one changed at a time is the method):
//   Attachments / render:  --w W --h H --vpw N --vph N --fmt F
//   Depth:                 --depth --dcmp FUNC --dwrite 0|1
//   Stencil:               --stencil --scmp F --sfail OP --szfail OP --spass OP
//                          --sread MASK --swrite MASK --sref N  --sback (distinct back face)
//   Blend:                 --blend --srgb FAC --drgb FAC --salpha FAC --dalpha FAC
//                          --brgbop OP --balphaop OP --wmask N(0..15)
//   Raster:                --cull none|front|back  --front cw|ccw  --fill fill|lines
//                          --dbias C --dslope S --dclamp K  --clip clip|clamp
//   Shader-entry probes:   --vshader small|big  --fshader small|big  --two
//   Capture:               --dump  --iters N
//
//   FUNC (compare): never less equal lequal greater nequal gequal always
//   OP  (stencil) : keep zero replace incrclamp decrclamp invert incrwrap decrwrap
//   FAC (blend)   : zero one srccolor 1-srccolor srcalpha 1-srcalpha dstcolor 1-dstcolor
//                   dstalpha 1-dstalpha srcalphasat blendcolor 1-blendcolor blendalpha
//                   1-blendalpha src1color 1-src1color src1alpha 1-src1alpha
//   OP  (blend)   : add sub revsub min max

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void die(const char *m){ printf("ARGERR %s\n", m); exit(2); }

static void print_va(const char *label, uint64_t va) {
    printf("VA %-12s = 0x%016llx\n", label, (unsigned long long)va);
}

// ---- vertex/fragment shaders (own MSL) ----
static NSString *vsrc(int big) {
    NSString *body = big ?
      @"  float2 q = p[vid];\n"
       "  float v0=q.x*1.01,v1=q.y*1.02,v2=q.x*1.03,v3=q.y*1.04,v4=q.x*1.05,v5=q.y*1.06,\n"
       "        v6=q.x*1.07,v7=q.y*1.08,v8=q.x*1.09,v9=q.y*1.10,va=q.x*1.11,vb=q.y*1.12;\n"
       "  for(int j=0;j<4;j++){ v0=fma(v0,v1,vb); v1=fma(v1,v2,va); v2=fma(v2,v3,v9);\n"
       "    v3=fma(v3,v4,v8); v4=fma(v4,v5,v7); v5=fma(v5,v6,v0); v6=fma(v6,v7,v1);\n"
       "    v7=fma(v7,v8,v2); v8=fma(v8,v9,v3); v9=fma(v9,va,v4); va=fma(va,vb,v5); vb=fma(vb,v0,v6);}\n"
       "  float2 pos = q + float2(v0+v2+v4+v6+v8+va, v1+v3+v5+v7+v9+vb)*1e-9f;\n"
       "  VO o; o.pos = float4(pos, 0, 1); o.col = float4(0.25,0.5,0.75,1)*(1.0+v0*1e-9f); return o;\n"
      :
      @"  VO o; o.pos = float4(p[vid], 0, 1); o.col = float4(0.25,0.5,0.75,1); return o;\n";
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]]; float4 col; };\n"
       "vertex VO v_main(uint vid [[vertex_id]], uint iid [[instance_id]],\n"
       "                 const device float2* p [[buffer(0)]]) {\n%@}\n", body];
}
// Fragment shader: optionally emits a SECOND color (color1) for dual-source blend probes.
static NSString *fsrc(int big, int dualsrc) {
    if (dualsrc) {
      return @"#include <metal_stdlib>\nusing namespace metal;\n"
             "struct VO { float4 pos [[position]]; float4 col; };\n"
             "struct FO { float4 c0 [[color(0), index(0)]]; float4 c1 [[color(0), index(1)]]; };\n"
             "fragment FO f_main(VO in [[stage_in]]) { FO o; o.c0 = in.col; o.c1 = float4(0.5,0.5,0.5,0.5); return o; }\n";
    }
    NSString *body = big ?
      @"  float v0=in.col.x,v1=in.col.y,v2=in.col.z,v3=in.col.w,v4=0.5,v5=0.25,v6=0.75,v7=0.1;\n"
       "  for(int j=0;j<4;j++){ v0=fma(v0,v1,v7); v1=fma(v1,v2,v6); v2=fma(v2,v3,v5);\n"
       "    v3=fma(v3,v4,v0); v4=fma(v4,v5,v1); v5=fma(v5,v6,v2); v6=fma(v6,v7,v3); v7=fma(v7,v0,v4);}\n"
       "  return in.col + float4(v0+v1+v2+v3+v4+v5+v6+v7)*1e-9f;\n"
      :
      @"  return in.col;\n";
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]]; float4 col; };\n"
       "fragment float4 f_main(VO in [[stage_in]]) {\n%@}\n", body];
}

// ---- enum parsers ----
static MTLPixelFormat parse_fmt(const char *s, int *bpp) {
    if (!strcmp(s,"rgba8"))   { *bpp=4;  return MTLPixelFormatRGBA8Unorm; }
    if (!strcmp(s,"rgba16f")) { *bpp=8;  return MTLPixelFormatRGBA16Float; }
    if (!strcmp(s,"rgba32f")) { *bpp=16; return MTLPixelFormatRGBA32Float; }
    if (!strcmp(s,"r8"))      { *bpp=1;  return MTLPixelFormatR8Unorm; }
    *bpp=4; return MTLPixelFormatBGRA8Unorm;      // "bgra8" default
}
static MTLCompareFunction parse_cmp(const char *s) {
    if(!strcmp(s,"never"))   return MTLCompareFunctionNever;
    if(!strcmp(s,"less"))    return MTLCompareFunctionLess;
    if(!strcmp(s,"equal"))   return MTLCompareFunctionEqual;
    if(!strcmp(s,"lequal"))  return MTLCompareFunctionLessEqual;
    if(!strcmp(s,"greater")) return MTLCompareFunctionGreater;
    if(!strcmp(s,"nequal"))  return MTLCompareFunctionNotEqual;
    if(!strcmp(s,"gequal"))  return MTLCompareFunctionGreaterEqual;
    if(!strcmp(s,"always"))  return MTLCompareFunctionAlways;
    die("bad compare func"); return 0;
}
static MTLStencilOperation parse_sop(const char *s) {
    if(!strcmp(s,"keep"))      return MTLStencilOperationKeep;
    if(!strcmp(s,"zero"))      return MTLStencilOperationZero;
    if(!strcmp(s,"replace"))   return MTLStencilOperationReplace;
    if(!strcmp(s,"incrclamp")) return MTLStencilOperationIncrementClamp;
    if(!strcmp(s,"decrclamp")) return MTLStencilOperationDecrementClamp;
    if(!strcmp(s,"invert"))    return MTLStencilOperationInvert;
    if(!strcmp(s,"incrwrap"))  return MTLStencilOperationIncrementWrap;
    if(!strcmp(s,"decrwrap"))  return MTLStencilOperationDecrementWrap;
    die("bad stencil op"); return 0;
}
static MTLBlendFactor parse_fac(const char *s) {
    if(!strcmp(s,"zero"))        return MTLBlendFactorZero;
    if(!strcmp(s,"one"))         return MTLBlendFactorOne;
    if(!strcmp(s,"srccolor"))    return MTLBlendFactorSourceColor;
    if(!strcmp(s,"1-srccolor"))  return MTLBlendFactorOneMinusSourceColor;
    if(!strcmp(s,"srcalpha"))    return MTLBlendFactorSourceAlpha;
    if(!strcmp(s,"1-srcalpha"))  return MTLBlendFactorOneMinusSourceAlpha;
    if(!strcmp(s,"dstcolor"))    return MTLBlendFactorDestinationColor;
    if(!strcmp(s,"1-dstcolor"))  return MTLBlendFactorOneMinusDestinationColor;
    if(!strcmp(s,"dstalpha"))    return MTLBlendFactorDestinationAlpha;
    if(!strcmp(s,"1-dstalpha"))  return MTLBlendFactorOneMinusDestinationAlpha;
    if(!strcmp(s,"srcalphasat")) return MTLBlendFactorSourceAlphaSaturated;
    if(!strcmp(s,"blendcolor"))  return MTLBlendFactorBlendColor;
    if(!strcmp(s,"1-blendcolor"))return MTLBlendFactorOneMinusBlendColor;
    if(!strcmp(s,"blendalpha"))  return MTLBlendFactorBlendAlpha;
    if(!strcmp(s,"1-blendalpha"))return MTLBlendFactorOneMinusBlendAlpha;
    if(!strcmp(s,"src1color"))   return MTLBlendFactorSource1Color;
    if(!strcmp(s,"1-src1color")) return MTLBlendFactorOneMinusSource1Color;
    if(!strcmp(s,"src1alpha"))   return MTLBlendFactorSource1Alpha;
    if(!strcmp(s,"1-src1alpha")) return MTLBlendFactorOneMinusSource1Alpha;
    die("bad blend factor"); return 0;
}
static MTLBlendOperation parse_bop(const char *s) {
    if(!strcmp(s,"add"))    return MTLBlendOperationAdd;
    if(!strcmp(s,"sub"))    return MTLBlendOperationSubtract;
    if(!strcmp(s,"revsub")) return MTLBlendOperationReverseSubtract;
    if(!strcmp(s,"min"))    return MTLBlendOperationMin;
    if(!strcmp(s,"max"))    return MTLBlendOperationMax;
    die("bad blend op"); return 0;
}
static MTLCullMode parse_cull(const char *s){
    if(!strcmp(s,"none"))  return MTLCullModeNone;
    if(!strcmp(s,"front")) return MTLCullModeFront;
    if(!strcmp(s,"back"))  return MTLCullModeBack;
    die("bad cull"); return 0;
}

int main(int argc, char **argv) {
    @autoreleasepool {
        long W=64,H=64,vpw=-1,vph=-1,iters=1,sref=0,sback=0,wmask=0xf,dualsrc=0;
        unsigned sread=0xff,swrite=0xff;
        const char *fmtS="bgra8", *vsh="small", *fsh="small";
        const char *dcmpS="less", *scmpS="always";
        const char *sfailS="keep", *szfailS="keep", *spassS="keep";
        const char *srgbS="srcalpha", *drgbS="1-srcalpha", *salphaS="srcalpha", *dalphaS="1-srcalpha";
        const char *brgbopS="add", *balphaopS="add";
        const char *cullS="none", *frontS="cw", *fillS="fill", *clipS="clip";
        int depth=0, dwrite=1, stencil=0, blend=0, two=0, doDump=0, hasBias=0;
        float dbias=0, dslope=0, dclampf=0, cr=0,cg=0,cb=0,ca=1;
        for(int i=1;i<argc;i++){
            const char *a=argv[i];
            #define NEXT (i+1<argc ? argv[++i] : (die("missing value"),(char*)0))
            if(!strcmp(a,"--w")) W=strtol(NEXT,0,0);
            else if(!strcmp(a,"--h")) H=strtol(NEXT,0,0);
            else if(!strcmp(a,"--vpw")) vpw=strtol(NEXT,0,0);
            else if(!strcmp(a,"--vph")) vph=strtol(NEXT,0,0);
            else if(!strcmp(a,"--fmt")) fmtS=NEXT;
            else if(!strcmp(a,"--vshader")) vsh=NEXT;
            else if(!strcmp(a,"--fshader")) fsh=NEXT;
            else if(!strcmp(a,"--iters")) iters=strtol(NEXT,0,0);
            // depth/stencil
            else if(!strcmp(a,"--depth")) depth=1;
            else if(!strcmp(a,"--dcmp")) { depth=1; dcmpS=NEXT; }
            else if(!strcmp(a,"--dwrite")) { depth=1; dwrite=(int)strtol(NEXT,0,0); }
            else if(!strcmp(a,"--stencil")) { depth=1; stencil=1; }
            else if(!strcmp(a,"--scmp")) { depth=1; stencil=1; scmpS=NEXT; }
            else if(!strcmp(a,"--sfail")) { depth=1; stencil=1; sfailS=NEXT; }
            else if(!strcmp(a,"--szfail")) { depth=1; stencil=1; szfailS=NEXT; }
            else if(!strcmp(a,"--spass")) { depth=1; stencil=1; spassS=NEXT; }
            else if(!strcmp(a,"--sread")) { depth=1; stencil=1; sread=(unsigned)strtol(NEXT,0,0); }
            else if(!strcmp(a,"--swrite")) { depth=1; stencil=1; swrite=(unsigned)strtol(NEXT,0,0); }
            else if(!strcmp(a,"--sref")) { depth=1; stencil=1; sref=strtol(NEXT,0,0); }
            else if(!strcmp(a,"--sback")) { depth=1; stencil=1; sback=1; }
            // blend
            else if(!strcmp(a,"--blend")) blend=1;
            else if(!strcmp(a,"--srgb")) { blend=1; srgbS=NEXT; }
            else if(!strcmp(a,"--drgb")) { blend=1; drgbS=NEXT; }
            else if(!strcmp(a,"--salpha")) { blend=1; salphaS=NEXT; }
            else if(!strcmp(a,"--dalpha")) { blend=1; dalphaS=NEXT; }
            else if(!strcmp(a,"--brgbop")) { blend=1; brgbopS=NEXT; }
            else if(!strcmp(a,"--balphaop")) { blend=1; balphaopS=NEXT; }
            else if(!strcmp(a,"--wmask")) { blend=1; wmask=strtol(NEXT,0,0); }
            else if(!strcmp(a,"--dualsrc")) { blend=1; dualsrc=1; }
            // raster
            else if(!strcmp(a,"--cull")) cullS=NEXT;
            else if(!strcmp(a,"--front")) frontS=NEXT;
            else if(!strcmp(a,"--fill")) fillS=NEXT;
            else if(!strcmp(a,"--clip")) clipS=NEXT;
            else if(!strcmp(a,"--dbias")) { hasBias=1; dbias=strtof(NEXT,0); }
            else if(!strcmp(a,"--dslope")) { hasBias=1; dslope=strtof(NEXT,0); }
            else if(!strcmp(a,"--dclamp")) { hasBias=1; dclampf=strtof(NEXT,0); }
            else if(!strcmp(a,"--cr")) cr=strtof(NEXT,0);
            else if(!strcmp(a,"--two")) two=1;
            else if(!strcmp(a,"--dump")) doDump=1;
            else { printf("UNKNOWN ARG %s\n", a); }
            #undef NEXT
        }
        if(vpw<0) vpw=W; if(vph<0) vph=H;
        int bpp=4; MTLPixelFormat fmt=parse_fmt(fmtS,&bpp);

        id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
        printf("DEVICE %s\n",[[dev name] UTF8String]);
        printf("CONFIG w=%ld h=%ld fmt=%s depth=%d dcmp=%s dwrite=%d stencil=%d scmp=%s "
               "sfail=%s szfail=%s spass=%s sread=0x%x swrite=0x%x sref=%ld sback=%ld "
               "blend=%d srgb=%s drgb=%s salpha=%s dalpha=%s brgbop=%s balphaop=%s wmask=%ld dualsrc=%ld "
               "cull=%s front=%s fill=%s clip=%s dbias=%g dslope=%g dclamp=%g vsh=%s fsh=%s two=%d\n",
               W,H,fmtS,depth,dcmpS,dwrite,stencil,scmpS,sfailS,szfailS,spassS,sread,swrite,sref,sback,
               blend,srgbS,drgbS,salphaS,dalphaS,brgbopS,balphaopS,wmask,dualsrc,
               cullS,frontS,fillS,clipS,dbias,dslope,dclampf,vsh,fsh,two);

        MTLPixelFormat dsfmt = stencil ? MTLPixelFormatDepth32Float_Stencil8 : MTLPixelFormatDepth32Float;

        NSError *err=nil;
        id<MTLLibrary> vl=[dev newLibraryWithSource:vsrc(!strcmp(vsh,"big")) options:nil error:&err];
        id<MTLLibrary> fl=[dev newLibraryWithSource:fsrc(!strcmp(fsh,"big"),dualsrc) options:nil error:&err];
        if(!vl||!fl){ printf("SHADER_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
        MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
        pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
        pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
        MTLRenderPipelineColorAttachmentDescriptor *ca0=pd.colorAttachments[0];
        ca0.pixelFormat=fmt;
        ca0.writeMask=(MTLColorWriteMask)wmask;
        if(blend){
            ca0.blendingEnabled=YES;
            ca0.rgbBlendOperation=parse_bop(brgbopS);
            ca0.alphaBlendOperation=parse_bop(balphaopS);
            ca0.sourceRGBBlendFactor=parse_fac(srgbS);
            ca0.destinationRGBBlendFactor=parse_fac(drgbS);
            ca0.sourceAlphaBlendFactor=parse_fac(salphaS);
            ca0.destinationAlphaBlendFactor=parse_fac(dalphaS);
        }
        if(depth){ pd.depthAttachmentPixelFormat=dsfmt;
                   if(stencil) pd.stencilAttachmentPixelFormat=dsfmt; }
        id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
        if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

        // depth/stencil state
        id<MTLDepthStencilState> dss=nil;
        if(depth){
            MTLDepthStencilDescriptor *dsd=[MTLDepthStencilDescriptor new];
            dsd.depthCompareFunction=parse_cmp(dcmpS);
            dsd.depthWriteEnabled=dwrite?YES:NO;
            if(stencil){
                MTLStencilDescriptor *sf=[MTLStencilDescriptor new];
                sf.stencilCompareFunction=parse_cmp(scmpS);
                sf.stencilFailureOperation=parse_sop(sfailS);
                sf.depthFailureOperation=parse_sop(szfailS);
                sf.depthStencilPassOperation=parse_sop(spassS);
                sf.readMask=sread; sf.writeMask=swrite;
                dsd.frontFaceStencil=sf;
                if(sback){
                    MTLStencilDescriptor *sb=[MTLStencilDescriptor new];
                    sb.stencilCompareFunction=MTLCompareFunctionEqual;
                    sb.stencilFailureOperation=MTLStencilOperationZero;
                    sb.depthFailureOperation=MTLStencilOperationInvert;
                    sb.depthStencilPassOperation=MTLStencilOperationReplace;
                    sb.readMask=0x0f; sb.writeMask=0x3c;
                    dsd.backFaceStencil=sb;
                } else {
                    dsd.backFaceStencil=sf;
                }
            }
            dss=[dev newDepthStencilStateWithDescriptor:dsd];
        }

        // ---- render target ----
        MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt
                                   width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
        td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
        td.storageMode=MTLStorageModeShared;
        id<MTLBuffer> rtb=[dev newBufferWithLength:((W*bpp+255)&~255UL)*H options:MTLResourceStorageModeShared];
        NSUInteger bpr=((W*bpp+255)&~255UL);
        id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
        if(target) print_va("rtBuf",[rtb gpuAddress]);
        else { target=[dev newTextureWithDescriptor:td]; printf("RTBUF_REJECTED\n"); }

        id<MTLTexture> dsTex=nil;
        if(depth){
            MTLTextureDescriptor *dd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:dsfmt
                                       width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
            dd.usage=MTLTextureUsageRenderTarget; dd.storageMode=MTLStorageModePrivate;
            dsTex=[dev newTextureWithDescriptor:dd];
        }

        // ---- vertex buffer ----
        id<MTLBuffer> vb=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
        float *vp=(float*)[vb contents];
        vp[0]=-1;vp[1]=-1; vp[2]=3;vp[3]=-1; vp[4]=-1;vp[5]=3;
        print_va("vtxBuf",[vb gpuAddress]);

        id<MTLCommandQueue> q=[dev newCommandQueue];
        for(long it=0; it<iters; it++){
            printf("SUBMIT iter=%ld begin\n", it);
            MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
            rp.colorAttachments[0].texture=target;
            rp.colorAttachments[0].loadAction=MTLLoadActionClear;
            rp.colorAttachments[0].clearColor=MTLClearColorMake(cr,cg,cb,ca);
            rp.colorAttachments[0].storeAction=MTLStoreActionStore;
            if(depth){ rp.depthAttachment.texture=dsTex;
                       rp.depthAttachment.loadAction=MTLLoadActionClear;
                       rp.depthAttachment.clearDepth=1.0;
                       rp.depthAttachment.storeAction=MTLStoreActionDontCare;
                       if(stencil){ rp.stencilAttachment.texture=dsTex;
                                    rp.stencilAttachment.loadAction=MTLLoadActionClear;
                                    rp.stencilAttachment.clearStencil=0;
                                    rp.stencilAttachment.storeAction=MTLStoreActionDontCare; } }
            id<MTLCommandBuffer> cb=[q commandBuffer];
            id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
            [enc setRenderPipelineState:pso];
            MTLViewport vp2={0.0,0.0,(double)vpw,(double)vph,0.0,1.0};
            [enc setViewport:vp2];
            [enc setCullMode:parse_cull(cullS)];
            [enc setFrontFacingWinding:!strcmp(frontS,"ccw")?MTLWindingCounterClockwise:MTLWindingClockwise];
            [enc setTriangleFillMode:!strcmp(fillS,"lines")?MTLTriangleFillModeLines:MTLTriangleFillModeFill];
            [enc setDepthClipMode:!strcmp(clipS,"clamp")?MTLDepthClipModeClamp:MTLDepthClipModeClip];
            if(hasBias) [enc setDepthBias:dbias slopeScale:dslope clamp:dclampf];
            [enc setVertexBuffer:vb offset:0 atIndex:0];
            if(dss){ [enc setDepthStencilState:dss];
                     if(stencil) [enc setStencilReferenceValue:(uint32_t)sref]; }
            if(blend) [enc setBlendColorRed:0.1 green:0.2 blue:0.3 alpha:0.4];
            [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1];
            [enc endEncoding];
            [cb commit];
            [cb waitUntilCompleted];
            printf("SUBMIT iter=%ld done status=%ld\n", it,(long)[cb status]);
            if(doDump&&it==iters-1){ fflush(stdout); kill(getpid(),SIGUSR1); usleep(400000); }
        }
        return 0;
    }
}
