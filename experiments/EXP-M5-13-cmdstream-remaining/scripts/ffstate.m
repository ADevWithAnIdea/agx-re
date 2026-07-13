// ffstate.m — comprehensive parametric OWN draw for fixed-function 0x58000 pool decode.
// Clean-room: our own MSL + Metal API only; dumps our own command-stream BOs via SIGUSR1.
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdio.h>
#include <string.h>
#include <signal.h>
#include <unistd.h>
#include <stdlib.h>

static long ai(const char*s){return strtol(s,0,0);}

int main(int argc,char**argv){@autoreleasepool{
  int doDump=0;
  // depth/stencil
  int depth=0, dcmp=3, dwrite=1, sten=0;
  int sfail=0, szfail=0, spass=0, scmp=7, sref=0, srmask=0xff, swmask=0xff;
  int sfailB=-1,szfailB=-1,spassB=-1,scmpB=-1; // back-face (default: mirror front)
  int dclip=-1; // -1 default, 0 clip, 1 clamp
  int dbias=0;
  // raster
  int cull=-1, wind=-1, fill=-1;
  // blend
  int blend=0, srgb=1, drgb=0, sa=1, da=0, brgb=0, ba=0, wmask=-1, dual=0, a2c=0, a2o=0, bcol=0;
  const char*cfmt="bgra8";
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dump"))doDump=1;
    else if(!strcmp(argv[i],"--depth"))depth=1;
    else if(!strcmp(argv[i],"--dcmp")&&i+1<argc){depth=1;dcmp=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--dwrite")&&i+1<argc){depth=1;dwrite=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--sten"))sten=1;
    else if(!strcmp(argv[i],"--sfail")&&i+1<argc){sten=1;sfail=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--szfail")&&i+1<argc){sten=1;szfail=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--spass")&&i+1<argc){sten=1;spass=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--scmp")&&i+1<argc){sten=1;scmp=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--sref")&&i+1<argc){sten=1;sref=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--srmask")&&i+1<argc){sten=1;srmask=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--swmask")&&i+1<argc){sten=1;swmask=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--sfailB")&&i+1<argc){sten=1;sfailB=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--szfailB")&&i+1<argc){sten=1;szfailB=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--spassB")&&i+1<argc){sten=1;spassB=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--scmpB")&&i+1<argc){sten=1;scmpB=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--dclip")&&i+1<argc){dclip=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--dbias"))dbias=1;
    else if(!strcmp(argv[i],"--cull")&&i+1<argc)cull=ai(argv[++i]);
    else if(!strcmp(argv[i],"--wind")&&i+1<argc)wind=ai(argv[++i]);
    else if(!strcmp(argv[i],"--fill")&&i+1<argc)fill=ai(argv[++i]);
    else if(!strcmp(argv[i],"--blend"))blend=1;
    else if(!strcmp(argv[i],"--srgb")&&i+1<argc){blend=1;srgb=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--drgb")&&i+1<argc){blend=1;drgb=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--sa")&&i+1<argc){blend=1;sa=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--da")&&i+1<argc){blend=1;da=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--brgb")&&i+1<argc){blend=1;brgb=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--ba")&&i+1<argc){blend=1;ba=ai(argv[++i]);}
    else if(!strcmp(argv[i],"--wmask")&&i+1<argc)wmask=ai(argv[++i]);
    else if(!strcmp(argv[i],"--dual")){blend=1;dual=1;}
    else if(!strcmp(argv[i],"--a2c"))a2c=1;
    else if(!strcmp(argv[i],"--a2o"))a2o=1;
    else if(!strcmp(argv[i],"--bcol"))bcol=1;
    else if(!strcmp(argv[i],"--cfmt")&&i+1<argc)cfmt=argv[++i];
  }
  id<MTLDevice> dev=MTLCreateSystemDefaultDevice();
  printf("DEVICE %s\n",[[dev name]UTF8String]);
  NSString*src;
  if(dual) src=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "vertex VO v_main(uint vid[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};VO o;o.pos=float4(p[vid%3],0.5,1);o.col=float4(0.25,0.5,0.75,0.5);return o;}\n"
    "struct FO{float4 c0 [[color(0),index(0)]];float4 c1 [[color(0),index(1)]];};\n"
    "fragment FO f_main(VO in[[stage_in]]){FO o;o.c0=in.col;o.c1=float4(0.1,0.2,0.3,0.4);return o;}\n";
  else src=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "struct VO{float4 pos [[position]];float4 col;};\n"
    "vertex VO v_main(uint vid[[vertex_id]]){float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};VO o;o.pos=float4(p[vid%3],0.5,1);o.col=float4(0.25,0.5,0.75,0.5);return o;}\n"
    "fragment float4 f_main(VO in[[stage_in]]){return in.col;}\n";
  NSError*err=nil;
  id<MTLLibrary> lib=[dev newLibraryWithSource:src options:nil error:&err];
  if(!lib){printf("COMPILE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLRenderPipelineDescriptor*pd=[MTLRenderPipelineDescriptor new];
  pd.vertexFunction=[lib newFunctionWithName:@"v_main"];pd.fragmentFunction=[lib newFunctionWithName:@"f_main"];
  MTLPixelFormat cpf=MTLPixelFormatBGRA8Unorm;
  if(!strcmp(cfmt,"rgba8"))cpf=MTLPixelFormatRGBA8Unorm;
  else if(!strcmp(cfmt,"rgba16f"))cpf=MTLPixelFormatRGBA16Float;
  else if(!strcmp(cfmt,"rgba32f"))cpf=MTLPixelFormatRGBA32Float;
  pd.colorAttachments[0].pixelFormat=cpf;
  if(blend){
    pd.colorAttachments[0].blendingEnabled=YES;
    pd.colorAttachments[0].rgbBlendOperation=(MTLBlendOperation)brgb;
    pd.colorAttachments[0].alphaBlendOperation=(MTLBlendOperation)ba;
    pd.colorAttachments[0].sourceRGBBlendFactor=(MTLBlendFactor)srgb;
    pd.colorAttachments[0].destinationRGBBlendFactor=(MTLBlendFactor)drgb;
    pd.colorAttachments[0].sourceAlphaBlendFactor=(MTLBlendFactor)sa;
    pd.colorAttachments[0].destinationAlphaBlendFactor=(MTLBlendFactor)da;
  }
  if(wmask>=0) pd.colorAttachments[0].writeMask=(MTLColorWriteMask)wmask;
  if(a2c) pd.alphaToCoverageEnabled=YES;
  if(a2o) pd.alphaToOneEnabled=YES;
  int hasStencil = sten;
  if(depth) pd.depthAttachmentPixelFormat = hasStencil?MTLPixelFormatDepth32Float_Stencil8:MTLPixelFormatDepth32Float;
  if(hasStencil) pd.stencilAttachmentPixelFormat = MTLPixelFormatDepth32Float_Stencil8;
  id<MTLRenderPipelineState> pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err];
  if(!pso){printf("PIPELINE_FAIL %s\n",[[err localizedDescription]UTF8String]);return 1;}
  MTLTextureDescriptor*td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:cpf width:64 height:64 mipmapped:NO];
  td.usage=MTLTextureUsageRenderTarget;td.storageMode=MTLStorageModeShared;
  id<MTLTexture> target=[dev newTextureWithDescriptor:td];
  id<MTLTexture> dtex=nil;
  if(depth||hasStencil){
    MTLTextureDescriptor*dd=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:(hasStencil?MTLPixelFormatDepth32Float_Stencil8:MTLPixelFormatDepth32Float) width:64 height:64 mipmapped:NO];
    dd.usage=MTLTextureUsageRenderTarget;dd.storageMode=MTLStorageModePrivate;dtex=[dev newTextureWithDescriptor:dd];
  }
  id<MTLCommandQueue> q=[dev newCommandQueue];
  MTLRenderPassDescriptor*rp=[MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture=target;rp.colorAttachments[0].loadAction=MTLLoadActionClear;
  rp.colorAttachments[0].clearColor=MTLClearColorMake(0.1,0.2,0.3,0.5);rp.colorAttachments[0].storeAction=MTLStoreActionStore;
  if(depth){rp.depthAttachment.texture=dtex;rp.depthAttachment.loadAction=MTLLoadActionClear;rp.depthAttachment.clearDepth=1.0;rp.depthAttachment.storeAction=MTLStoreActionStore;}
  if(hasStencil){rp.stencilAttachment.texture=dtex;rp.stencilAttachment.loadAction=MTLLoadActionClear;rp.stencilAttachment.clearStencil=0;rp.stencilAttachment.storeAction=MTLStoreActionStore;}
  id<MTLCommandBuffer> cb=[q commandBuffer];
  id<MTLRenderCommandEncoder> enc=[cb renderCommandEncoderWithDescriptor:rp];
  [enc setRenderPipelineState:pso];
  if(depth||hasStencil){
    MTLDepthStencilDescriptor*ds=[MTLDepthStencilDescriptor new];
    if(depth){ds.depthCompareFunction=(MTLCompareFunction)dcmp;ds.depthWriteEnabled=dwrite?YES:NO;}
    if(hasStencil){
      MTLStencilDescriptor*fs=[MTLStencilDescriptor new];
      fs.stencilFailureOperation=(MTLStencilOperation)sfail;
      fs.depthFailureOperation=(MTLStencilOperation)szfail;
      fs.depthStencilPassOperation=(MTLStencilOperation)spass;
      fs.stencilCompareFunction=(MTLCompareFunction)scmp;
      fs.readMask=srmask;fs.writeMask=swmask;
      ds.frontFaceStencil=fs;
      MTLStencilDescriptor*bs=[MTLStencilDescriptor new];
      bs.stencilFailureOperation=(MTLStencilOperation)(sfailB<0?sfail:sfailB);
      bs.depthFailureOperation=(MTLStencilOperation)(szfailB<0?szfail:szfailB);
      bs.depthStencilPassOperation=(MTLStencilOperation)(spassB<0?spass:spassB);
      bs.stencilCompareFunction=(MTLCompareFunction)(scmpB<0?scmp:scmpB);
      bs.readMask=srmask;bs.writeMask=swmask;
      ds.backFaceStencil=bs;
    }
    [enc setDepthStencilState:[dev newDepthStencilStateWithDescriptor:ds]];
    if(hasStencil)[enc setStencilReferenceValue:sref];
  }
  if(cull>=0)[enc setCullMode:(MTLCullMode)cull];
  if(wind>=0)[enc setFrontFacingWinding:wind?MTLWindingCounterClockwise:MTLWindingClockwise];
  if(fill>=0)[enc setTriangleFillMode:fill?MTLTriangleFillModeLines:MTLTriangleFillModeFill];
  if(dclip>=0)[enc setDepthClipMode:dclip?MTLDepthClipModeClamp:MTLDepthClipModeClip];
  if(dbias)[enc setDepthBias:2.0 slopeScale:3.0 clamp:1.0];
  if(bcol)[enc setBlendColorRed:0.11 green:0.22 blue:0.33 alpha:0.44];
  [enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
  [enc endEncoding];[cb commit];[cb waitUntilCompleted];
  printf("STATUS=%ld\n",(long)[cb status]);
  if(doDump){fflush(stdout);kill(getpid(),SIGUSR1);usleep(400000);}
  return 0;
}}
