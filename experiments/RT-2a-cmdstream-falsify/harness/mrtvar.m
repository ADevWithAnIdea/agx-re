// mrtvar.m — RT-2a adversarial MULTI-RENDER-TARGET harness.
//
// Drives 1..8 color attachments (MRT) so we can stress the 0x58000 fixed-function
// state pool, the PPP length word, and the attachment descriptor under a large,
// unorthodox draw the original state-packet experiments never ran.  Per-attachment
// blend + writemask are settable so we can confirm whether blend is programmable
// (shader-lowered) even with many attachments.  CLEAN-ROOM: OWN-SHADER + public
// Metal API only.
//
// Build (device): clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o mrtvar mrtvar.m
//
// Usage:
//   mrtvar [--w W --h H] [--n N(1..8)] [--blendmask HEX] [--wmask HEX]
//          [--blendfac srcalpha|one|...] [--iters N] [--dump]
//   --n         : number of color attachments
//   --blendmask : bitmask of which attachments have blending enabled (bit k => attach k)
//   --wmask     : color write mask applied to every attachment (0..15)

#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>

static void print_va(const char*l,uint64_t va){printf("VA %-12s = 0x%016llx\n",l,(unsigned long long)va);}
static MTLBlendFactor pf(const char*s){
  if(!strcmp(s,"zero"))return MTLBlendFactorZero;
  if(!strcmp(s,"one"))return MTLBlendFactorOne;
  if(!strcmp(s,"srcalpha"))return MTLBlendFactorSourceAlpha;
  if(!strcmp(s,"1-srcalpha"))return MTLBlendFactorOneMinusSourceAlpha;
  if(!strcmp(s,"dstcolor"))return MTLBlendFactorDestinationColor;
  return MTLBlendFactorSourceAlpha;
}

int main(int argc,char**argv){
  @autoreleasepool{
    long W=64,H=64,n=4,iters=1; unsigned blendmask=0,wmask=0xf; int doDump=0;
    const char*facS="srcalpha";
    for(int i=1;i<argc;i++){
      const char*a=argv[i];
      #define NEXT (i+1<argc?argv[++i]:(char*)"0")
      if(!strcmp(a,"--w"))W=strtol(NEXT,0,0);
      else if(!strcmp(a,"--h"))H=strtol(NEXT,0,0);
      else if(!strcmp(a,"--n"))n=strtol(NEXT,0,0);
      else if(!strcmp(a,"--blendmask"))blendmask=(unsigned)strtol(NEXT,0,0);
      else if(!strcmp(a,"--wmask"))wmask=(unsigned)strtol(NEXT,0,0);
      else if(!strcmp(a,"--blendfac"))facS=NEXT;
      else if(!strcmp(a,"--iters"))iters=strtol(NEXT,0,0);
      else if(!strcmp(a,"--dump"))doDump=1;
      else printf("UNKNOWN ARG %s\n",a);
      #undef NEXT
    }
    if(n<1)n=1; if(n>8)n=8;
    id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
    printf("DEVICE %s\n",[[dev name] UTF8String]);
    printf("CONFIG w=%ld h=%ld n=%ld blendmask=0x%x wmask=0x%x fac=%s\n",W,H,n,blendmask,wmask,facS);

    // build FS that writes N attachments
    NSMutableString*fo=[NSMutableString stringWithString:@"struct FO{\n"];
    for(long k=0;k<n;k++)[fo appendFormat:@"  float4 c%ld [[color(%ld)]];\n",k,k];
    [fo appendString:@"};\n"];
    NSMutableString*fb=[NSMutableString string];
    for(long k=0;k<n;k++)[fb appendFormat:@"  o.c%ld=in.col*float(%ld+1)*0.1;\n",k,k];
    NSString*fsrc=[NSString stringWithFormat:
      @"#include <metal_stdlib>\nusing namespace metal;\n"
       "struct VO{float4 pos [[position]];float4 col;};\n%@"
       "fragment FO f_main(VO in [[stage_in]]){FO o;\n%@ return o;}\n",fo,fb];
    NSString*vsrc=@"#include <metal_stdlib>\nusing namespace metal;\n"
      "struct VO{float4 pos [[position]];float4 col;};\n"
      "vertex VO v_main(uint vid [[vertex_id]],const device float2* p [[buffer(0)]]){\n"
      "  VO o;o.pos=float4(p[vid],0,1);o.col=float4(0.25,0.5,0.75,0.5);return o;}\n";

    NSError*err=nil;
    id<MTLLibrary> vl=[dev newLibraryWithSource:vsrc options:nil error:&err];
    id<MTLLibrary> fl=[dev newLibraryWithSource:fsrc options:nil error:&err];
    if(!vl||!fl){printf("SHADER_FAIL %s\n",[[err localizedDescription] UTF8String]);printf("%s\n",[fsrc UTF8String]);return 1;}
    MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
    pd.vertexFunction=[vl newFunctionWithName:@"v_main"];
    pd.fragmentFunction=[fl newFunctionWithName:@"f_main"];
    for(long k=0;k<n;k++){
      MTLRenderPipelineColorAttachmentDescriptor*ca=pd.colorAttachments[k];
      ca.pixelFormat=MTLPixelFormatBGRA8Unorm;
      ca.writeMask=(MTLColorWriteMask)wmask;
      if(blendmask&(1u<<k)){
        ca.blendingEnabled=YES;
        ca.rgbBlendOperation=MTLBlendOperationAdd;ca.alphaBlendOperation=MTLBlendOperationAdd;
        ca.sourceRGBBlendFactor=pf(facS);ca.destinationRGBBlendFactor=MTLBlendFactorOneMinusSourceAlpha;
        ca.sourceAlphaBlendFactor=pf(facS);ca.destinationAlphaBlendFactor=MTLBlendFactorOneMinusSourceAlpha;
      }
    }
    id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription] UTF8String]);return 1;}

    NSUInteger bpr=((W*4+255)&~255UL);
    NSMutableArray*targets=[NSMutableArray array];
    for(long k=0;k<n;k++){
      MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
                               width:(NSUInteger)W height:(NSUInteger)H mipmapped:NO];
      td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;td.storageMode=MTLStorageModeShared;
      id<MTLBuffer> rtb=[dev newBufferWithLength:bpr*H options:MTLResourceStorageModeShared];
      id<MTLTexture> t=[rtb newTextureWithDescriptor:td offset:0 bytesPerRow:bpr];
      char lbl[16];snprintf(lbl,sizeof lbl,"rt%ld",k);print_va(lbl,[rtb gpuAddress]);
      [targets addObject:t];
    }
    id<MTLBuffer> vb=[dev newBufferWithLength:64 options:MTLResourceStorageModeShared];
    float*vp=(float*)[vb contents];vp[0]=-1;vp[1]=-1;vp[2]=3;vp[3]=-1;vp[4]=-1;vp[5]=3;
    print_va("vtxBuf",[vb gpuAddress]);

    id<MTLCommandQueue> q=[dev newCommandQueue];
    for(long it=0;it<iters;it++){
      printf("SUBMIT iter=%ld begin\n",it);
      MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
      for(long k=0;k<n;k++){
        rp.colorAttachments[k].texture=targets[k];
        rp.colorAttachments[k].loadAction=MTLLoadActionClear;
        rp.colorAttachments[k].clearColor=MTLClearColorMake(0.1*k,0,0,1);
        rp.colorAttachments[k].storeAction=MTLStoreActionStore;
      }
      id<MTLCommandBuffer> cb=[q commandBuffer];
      id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
      [enc setRenderPipelineState:pso];
      MTLViewport vp2={0,0,(double)W,(double)H,0,1};[enc setViewport:vp2];
      [enc setVertexBuffer:vb offset:0 atIndex:0];
      if(blendmask)[enc setBlendColorRed:0.1 green:0.2 blue:0.3 alpha:0.4];
      [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3 instanceCount:1];
      [enc endEncoding];[cb commit];[cb waitUntilCompleted];
      printf("SUBMIT iter=%ld done status=%ld\n",it,(long)[cb status]);
      if([cb error])printf("CB_ERROR %s\n",[[[cb error] localizedDescription] UTF8String]);
      if(doDump&&it==iters-1){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
    }
    return 0;
  }
}
