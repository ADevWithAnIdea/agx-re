// gvar.m — parametric OWN Metal DRAW for EXP-0024 (G-3 USC shader-entry + G-7 PPP header).
//
// Extends EXP-0019's svar.m with:
//   * --pad N        : compile N distinct DUMMY render pipelines BEFORE the real one,
//                      so the real VS/FS machine code lands at a SHIFTED gpu-VA while
//                      the real shader bytes stay byte-identical. This is the graphics
//                      analogue of EXP-0011's compute --pad shader-pointer proof: only
//                      VA-referencing words move, isolating the USC shader-entry pointer.
//   * --vsz K/--fsz K: give the VS/FS K extra live FMA blocks (fine-grained size control)
//                      so a *following* stage's code entry shifts by a measurable amount.
//   * MAGIC immediates: the real VS embeds 0x51a2b3c4, the real FS embeds 0x62c3d4e5, each
//                      forced into the code stream via a data-dependent XOR (survives DCE),
//                      so we can grep the code BO to locate each shader's exact position and
//                      measure its VA shift across --pad / --vsz.
//   * --nodepth default: G-7 present-mask work toggles state groups (--depth/--stencil/
//                      --blend) on and off and diffs the VDM header (0x18000) to find the
//                      packet present/emission-order grammar.
//
// CLEAN-ROOM: OWN-SHADER + public Metal API only. Every shader is our own MSL compiled at
// runtime; we print our own resource GPU VAs for correlation. No Apple binary is inspected.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o gvar gvar.m

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void die(const char *m){ printf("ARGERR %s\n", m); exit(2); }
static void print_va(const char *label, uint64_t va){
    printf("VA %-12s = 0x%016llx\n", label, (unsigned long long)va);
}

// ---- vertex shader: magic 0x51a2b3c4, size grows with vsz extra FMA blocks ----
static NSString *vsrc(int vsz){
    NSMutableString *body=[NSMutableString string];
    [body appendString:
      @"  float2 q = p[vid];\n"
       "  uint mb = as_type<uint>(q.x) ^ 0x51a2b3c4u;\n"    // force MAGIC 0x51a2b3c4 into code
       "  float acc = as_type<float>(mb) * 1e-30f;\n"];
    for(int j=0;j<vsz;j++){
      [body appendFormat:
        @"  { float a=q.x*%d.03f,b=q.y*%d.07f,c=a*b+acc; acc=fma(c,a,b)*1e-30f+acc; }\n", j+1, j+1];
    }
    [body appendString:
      @"  VO o; o.pos=float4(q + float2(acc,acc), 0, 1); o.col=float4(0.25,0.5,0.75,1); return o;\n"];
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]]; float4 col; };\n"
       "vertex VO v_main(uint vid [[vertex_id]], uint iid [[instance_id]],\n"
       "                 const device float2* p [[buffer(0)]]) {\n%@}\n", body];
}
// ---- fragment shader: magic 0x62c3d4e5, size grows with fsz extra FMA blocks ----
static NSString *fsrc(int fsz, int dualsrc){
    if(dualsrc){
      return @"#include <metal_stdlib>\nusing namespace metal;\n"
             "struct VO { float4 pos [[position]]; float4 col; };\n"
             "struct FO { float4 c0 [[color(0), index(0)]]; float4 c1 [[color(0), index(1)]]; };\n"
             "fragment FO f_main(VO in [[stage_in]]){ FO o; o.c0=in.col; o.c1=float4(0.5); return o; }\n";
    }
    NSMutableString *body=[NSMutableString string];
    [body appendString:
      @"  uint mb = as_type<uint>(in.col.x) ^ 0x62c3d4e5u;\n"   // force MAGIC 0x62c3d4e5 into code
       "  float acc = as_type<float>(mb) * 1e-30f;\n"];
    for(int j=0;j<fsz;j++){
      [body appendFormat:
        @"  { float a=in.col.x*%d.03f,b=in.col.y*%d.07f,c=a*b+acc; acc=fma(c,a,b)*1e-30f+acc; }\n", j+1, j+1];
    }
    [body appendString:@"  return in.col + float4(acc);\n"];
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]]; float4 col; };\n"
       "fragment float4 f_main(VO in [[stage_in]]){\n%@}\n", body];
}
// dummy distinct pipeline source (for --pad): parametrised so each is a different shader
static NSString *dummy_vsrc(int k){
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]]; float4 col; };\n"
       "vertex VO v_main(uint vid [[vertex_id]], const device float2* p [[buffer(0)]]){\n"
       "  float2 q=p[vid]; float s=q.x*%d.5f; VO o; o.pos=float4(q+float2(s*1e-30f),0,1);\n"
       "  o.col=float4(%d.0f); return o; }\n", k+1, k+1];
}
static NSString *dummy_fsrc(int k){
    return [NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO { float4 pos [[position]]; float4 col; };\n"
       "fragment float4 f_main(VO in [[stage_in]]){ return in.col*%d.5f; }\n", k+1];
}

// ---- enum parsers ----
static MTLPixelFormat parse_fmt(const char *s,int *bpp){
    if(!strcmp(s,"rgba8")){*bpp=4;return MTLPixelFormatRGBA8Unorm;}
    if(!strcmp(s,"rgba16f")){*bpp=8;return MTLPixelFormatRGBA16Float;}
    *bpp=4; return MTLPixelFormatBGRA8Unorm;
}
static MTLCompareFunction parse_cmp(const char *s){
    if(!strcmp(s,"never"))return MTLCompareFunctionNever;
    if(!strcmp(s,"less"))return MTLCompareFunctionLess;
    if(!strcmp(s,"equal"))return MTLCompareFunctionEqual;
    if(!strcmp(s,"lequal"))return MTLCompareFunctionLessEqual;
    if(!strcmp(s,"greater"))return MTLCompareFunctionGreater;
    if(!strcmp(s,"nequal"))return MTLCompareFunctionNotEqual;
    if(!strcmp(s,"gequal"))return MTLCompareFunctionGreaterEqual;
    if(!strcmp(s,"always"))return MTLCompareFunctionAlways;
    die("bad cmp"); return 0;
}
static MTLStencilOperation parse_sop(const char *s){
    if(!strcmp(s,"keep"))return MTLStencilOperationKeep;
    if(!strcmp(s,"zero"))return MTLStencilOperationZero;
    if(!strcmp(s,"replace"))return MTLStencilOperationReplace;
    if(!strcmp(s,"invert"))return MTLStencilOperationInvert;
    die("bad sop"); return 0;
}
static MTLBlendFactor parse_fac(const char *s){
    if(!strcmp(s,"zero"))return MTLBlendFactorZero;
    if(!strcmp(s,"one"))return MTLBlendFactorOne;
    if(!strcmp(s,"srcalpha"))return MTLBlendFactorSourceAlpha;
    if(!strcmp(s,"1-srcalpha"))return MTLBlendFactorOneMinusSourceAlpha;
    if(!strcmp(s,"srccolor"))return MTLBlendFactorSourceColor;
    die("bad fac"); return 0;
}
static MTLCullMode parse_cull(const char *s){
    if(!strcmp(s,"none"))return MTLCullModeNone;
    if(!strcmp(s,"front"))return MTLCullModeFront;
    if(!strcmp(s,"back"))return MTLCullModeBack;
    die("bad cull"); return 0;
}

int main(int argc, char **argv){
  @autoreleasepool {
    long W=64,H=64,vpw=-1,vph=-1,iters=1,pad=0,vsz=0,fsz=0,sref=0;
    const char *fmtS="bgra8",*dcmpS="less",*scmpS="always",*spassS="keep";
    const char *srgbS="srcalpha",*drgbS="1-srcalpha";
    const char *cullS="none",*frontS="cw";
    int depth=0,dwrite=1,stencil=0,blend=0,dualsrc=0,doDump=0,two=0;
    unsigned sread=0xff,swrite=0xff;
    for(int i=1;i<argc;i++){
      const char *a=argv[i];
      #define NEXT (i+1<argc?argv[++i]:(die("missing value"),(char*)0))
      if(!strcmp(a,"--w"))W=strtol(NEXT,0,0);
      else if(!strcmp(a,"--h"))H=strtol(NEXT,0,0);
      else if(!strcmp(a,"--vpw"))vpw=strtol(NEXT,0,0);
      else if(!strcmp(a,"--vph"))vph=strtol(NEXT,0,0);
      else if(!strcmp(a,"--fmt"))fmtS=NEXT;
      else if(!strcmp(a,"--pad"))pad=strtol(NEXT,0,0);
      else if(!strcmp(a,"--vsz"))vsz=strtol(NEXT,0,0);
      else if(!strcmp(a,"--fsz"))fsz=strtol(NEXT,0,0);
      else if(!strcmp(a,"--depth"))depth=1;
      else if(!strcmp(a,"--dcmp")){depth=1;dcmpS=NEXT;}
      else if(!strcmp(a,"--dwrite")){depth=1;dwrite=(int)strtol(NEXT,0,0);}
      else if(!strcmp(a,"--stencil")){depth=1;stencil=1;}
      else if(!strcmp(a,"--scmp")){depth=1;stencil=1;scmpS=NEXT;}
      else if(!strcmp(a,"--spass")){depth=1;stencil=1;spassS=NEXT;}
      else if(!strcmp(a,"--sref")){depth=1;stencil=1;sref=strtol(NEXT,0,0);}
      else if(!strcmp(a,"--blend"))blend=1;
      else if(!strcmp(a,"--srgb")){blend=1;srgbS=NEXT;}
      else if(!strcmp(a,"--drgb")){blend=1;drgbS=NEXT;}
      else if(!strcmp(a,"--dualsrc")){blend=1;dualsrc=1;}
      else if(!strcmp(a,"--cull"))cullS=NEXT;
      else if(!strcmp(a,"--front"))frontS=NEXT;
      else if(!strcmp(a,"--two"))two=1;
      else if(!strcmp(a,"--dump"))doDump=1;
      else printf("UNKNOWN ARG %s\n",a);
      #undef NEXT
    }
    if(vpw<0)vpw=W; if(vph<0)vph=H;
    int bpp=4; MTLPixelFormat fmt=parse_fmt(fmtS,&bpp);
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name] UTF8String]);
    printf("CONFIG w=%ld h=%ld fmt=%s pad=%ld vsz=%ld fsz=%ld depth=%d dcmp=%s dwrite=%d "
           "stencil=%d scmp=%s spass=%s sref=%ld blend=%d srgb=%s drgb=%s dualsrc=%d cull=%s front=%s two=%d\n",
           W,H,fmtS,pad,vsz,fsz,depth,dcmpS,dwrite,stencil,scmpS,spassS,sref,blend,srgbS,drgbS,dualsrc,cullS,frontS,two);
    printf("MAGIC vs=0x51a2b3c4 fs=0x62c3d4e5\n");

    MTLPixelFormat dsfmt = stencil?MTLPixelFormatDepth32Float_Stencil8:MTLPixelFormatDepth32Float;
    NSError *err=nil;

    // ---- padding: compile+realize N dummy render pipelines first ----
    NSMutableArray *keep=[NSMutableArray array];
    for(long k=0;k<pad;k++){
      id<MTLLibrary> dvl=[dev newLibraryWithSource:dummy_vsrc((int)k) options:nil error:&err];
      id<MTLLibrary> dfl=[dev newLibraryWithSource:dummy_fsrc((int)k) options:nil error:&err];
      if(!dvl||!dfl) continue;
      MTLRenderPipelineDescriptor *dpd=[MTLRenderPipelineDescriptor new];
      dpd.vertexFunction=[dvl newFunctionWithName:@"v_main"];
      dpd.fragmentFunction=[dfl newFunctionWithName:@"f_main"];
      dpd.colorAttachments[0].pixelFormat=fmt;
      id<MTLRenderPipelineState> dps=[dev newRenderPipelineStateWithDescriptor:dpd error:&err];
      if(dps)[keep addObject:dps];
    }

    id<MTLLibrary> vl=[dev newLibraryWithSource:vsrc((int)vsz) options:nil error:&err];
    id<MTLLibrary> fl=[dev newLibraryWithSource:fsrc((int)fsz,dualsrc) options:nil error:&err];
    if(!vl||!fl){ printf("SHADER_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }
    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
    pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
    MTLRenderPipelineColorAttachmentDescriptor *ca0=pd.colorAttachments[0];
    ca0.pixelFormat=fmt;
    if(blend){
      ca0.blendingEnabled=YES;
      ca0.sourceRGBBlendFactor=parse_fac(srgbS);
      ca0.destinationRGBBlendFactor=parse_fac(drgbS);
      ca0.sourceAlphaBlendFactor=parse_fac(srgbS);
      ca0.destinationAlphaBlendFactor=parse_fac(drgbS);
    }
    if(depth){ pd.depthAttachmentPixelFormat=dsfmt; if(stencil) pd.stencilAttachmentPixelFormat=dsfmt; }
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){ printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]); return 1; }

    id<MTLDepthStencilState> dss=nil;
    if(depth){
      MTLDepthStencilDescriptor *dsd=[MTLDepthStencilDescriptor new];
      dsd.depthCompareFunction=parse_cmp(dcmpS);
      dsd.depthWriteEnabled=dwrite?YES:NO;
      if(stencil){
        MTLStencilDescriptor *sf=[MTLStencilDescriptor new];
        sf.stencilCompareFunction=parse_cmp(scmpS);
        sf.depthStencilPassOperation=parse_sop(spassS);
        sf.readMask=sread; sf.writeMask=swrite;
        dsd.frontFaceStencil=sf; dsd.backFaceStencil=sf;
      }
      dss=[dev newDepthStencilStateWithDescriptor:dsd];
    }

    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:fmt
                               width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
    td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead; td.storageMode=MTLStorageModeShared;
    NSUInteger bpr=((W*bpp+255)&~255UL);
    id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
    id<MTLTexture> target=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
    if(target) print_va("rtBuf",[rtb gpuAddress]); else { target=[dev newTextureWithDescriptor:td]; printf("RTBUF_REJECTED\n"); }

    id<MTLTexture> dsTex=nil;
    if(depth){
      MTLTextureDescriptor *dd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:dsfmt
                                 width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
      dd.usage=MTLTextureUsageRenderTarget; dd.storageMode=MTLStorageModePrivate;
      dsTex=[dev newTextureWithDescriptor:dd];
    }

    id<MTLBuffer> vb=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    float *vp=(float*)[vb contents]; vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
    print_va("vtxBuf",[vb gpuAddress]);

    id<MTLCommandQueue> q=[dev newCommandQueue];
    for(long it=0; it<iters; it++){
      printf("SUBMIT iter=%ld begin\n", it);
      MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor new];
      rp.colorAttachments[0].texture=target;
      rp.colorAttachments[0].loadAction=MTLLoadActionClear;
      rp.colorAttachments[0].clearColor=MTLClearColorMake(0,0,0,1);
      rp.colorAttachments[0].storeAction=MTLStoreActionStore;
      if(depth){ rp.depthAttachment.texture=dsTex; rp.depthAttachment.loadAction=MTLLoadActionClear;
                 rp.depthAttachment.clearDepth=1.0; rp.depthAttachment.storeAction=MTLStoreActionDontCare;
                 if(stencil){ rp.stencilAttachment.texture=dsTex; rp.stencilAttachment.loadAction=MTLLoadActionClear;
                              rp.stencilAttachment.clearStencil=0; rp.stencilAttachment.storeAction=MTLStoreActionDontCare; } }
      id<MTLCommandBuffer> cb=[q commandBuffer];
      id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
      [enc setRenderPipelineState:pso];
      MTLViewport vp2={0.0,0.0,(double)vpw,(double)vph,0.0,1.0};
      [enc setViewport:vp2];
      [enc setCullMode:parse_cull(cullS)];
      [enc setFrontFacingWinding:!strcmp(frontS,"ccw")?MTLWindingCounterClockwise:MTLWindingClockwise];
      [enc setVertexBuffer:vb offset:0 atIndex:0];
      if(dss){ [enc setDepthStencilState:dss]; if(stencil)[enc setStencilReferenceValue:(uint32_t)sref]; }
      if(blend)[enc setBlendColorRed:0.1 green:0.2 blue:0.3 alpha:0.4];
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
