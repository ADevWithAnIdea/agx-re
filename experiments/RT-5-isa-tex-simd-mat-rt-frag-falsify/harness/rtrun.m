// rtrun.m -- clean-room OWN-SHADER RT runner: builds a PRIMITIVE acceleration
// structure (one triangle at z=3), binds it + input/output buffers, runs a
// possibly-spliced compute archive from the binary archive, reads out.
// Build: clang -fobjc-arc -framework Metal -framework Foundation -o rtrun rtrun.m
// Usage: rtrun --archive A.bin --source S.metal --function k --ray "ox,oy,oz,dx,dy,dz" --out N
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <getopt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#if !__has_feature(objc_arc)
#error arc
#endif
static void emit(const char*s){printf("STATUS %s\n",s);}
static void fail(const char*s,const char*m,NSError*e){emit(s);if(e)printf("ERROR %s: %s\n",m,[[e localizedDescription]UTF8String]);else if(m)printf("ERROR %s\n",m);fflush(stdout);exit(1);}
enum{OPT_NFM=128,OPT_RAY,OPT_OUT};
static const struct option L[]={{"archive",1,0,'a'},{"source",1,0,'s'},{"function",1,0,'f'},{"no-fast-math",0,0,OPT_NFM},{"ray",1,0,OPT_RAY},{"out",1,0,OPT_OUT},{0,0,0,0}};

int main(int argc,char**argv){@autoreleasepool{
 const char*arch=0,*srcp=0,*fnn=0; BOOL fm=YES; float ray[6]={0,0,0,0,0,1}; int nout=4;
 int c; while((c=getopt_long(argc,argv,"a:s:f:",L,0))>0){switch(c){
   case 'a':arch=optarg;break;case 's':srcp=optarg;break;case 'f':fnn=optarg;break;case OPT_NFM:fm=NO;break;
   case OPT_RAY:{char*p=optarg;for(int i=0;i<6;i++){ray[i]=atof(strsep(&p,","));}break;}
   case OPT_OUT:nout=atoi(optarg);break;}}
 id<MTLDevice>dev=MTLCreateSystemDefaultDevice(); if(!dev)fail("PIPELINE_FAIL","dev",0);
 printf("DEVICE %s\n",[[dev name]UTF8String]);
 NSError*err=0;
 // --- triangle at z=3: verts (0,0,3),(1,0,3),(0,1,3) ---
 float verts[9]={0,0,3, 1,0,3, 0,1,3};
 id<MTLBuffer>vb=[dev newBufferWithBytes:verts length:sizeof(verts) options:MTLResourceStorageModeShared];
 MTLAccelerationStructureTriangleGeometryDescriptor*g=[MTLAccelerationStructureTriangleGeometryDescriptor descriptor];
 g.vertexBuffer=vb; g.vertexStride=12; g.triangleCount=1; g.vertexFormat=MTLAttributeFormatFloat3;
 MTLPrimitiveAccelerationStructureDescriptor*ad=[MTLPrimitiveAccelerationStructureDescriptor descriptor];
 ad.geometryDescriptors=@[g];
 MTLAccelerationStructureSizes sz=[dev accelerationStructureSizesWithDescriptor:ad];
 id<MTLAccelerationStructure>as=[dev newAccelerationStructureWithSize:sz.accelerationStructureSize];
 id<MTLBuffer>scratch=[dev newBufferWithLength:sz.buildScratchBufferSize options:MTLResourceStorageModePrivate];
 id<MTLCommandQueue>q=[dev newCommandQueue];
 id<MTLCommandBuffer>bcb=[q commandBuffer];
 id<MTLAccelerationStructureCommandEncoder>ae=[bcb accelerationStructureCommandEncoder];
 [ae buildAccelerationStructure:as descriptor:ad scratchBuffer:scratch scratchBufferOffset:0];
 [ae endEncoding];[bcb commit];[bcb waitUntilCompleted];
 if([bcb status]==MTLCommandBufferStatusError)fail("CMDBUF_ERROR","AS build",[bcb error]);
 // --- compile + archived pipeline ---
 NSString*src=[NSString stringWithContentsOfFile:[NSString stringWithUTF8String:srcp] encoding:NSUTF8StringEncoding error:&err];
 if(!src)fail("COMPILE_FAIL","read",err);
 MTLCompileOptions*co=[MTLCompileOptions new];[co setFastMathEnabled:fm];
 id<MTLLibrary>lib=[dev newLibraryWithSource:src options:co error:&err]; if(!lib)fail("COMPILE_FAIL","compile",err);
 id<MTLFunction>fn=[lib newFunctionWithName:[NSString stringWithUTF8String:fnn]]; if(!fn)fail("FUNCTION_MISSING","fn",0);
 MTLBinaryArchiveDescriptor*bad=[MTLBinaryArchiveDescriptor new];[bad setUrl:[NSURL fileURLWithPath:[NSString stringWithUTF8String:arch]]];
 id<MTLBinaryArchive>ar=[dev newBinaryArchiveWithDescriptor:bad error:&err]; if(!ar)fail("ARCHIVE_FAIL","ar",err);
 MTLComputePipelineDescriptor*pd=[MTLComputePipelineDescriptor new];[pd setComputeFunction:fn];[pd setBinaryArchives:@[ar]];
 id<MTLComputePipelineState>pso=[dev newComputePipelineStateWithDescriptor:pd options:MTLPipelineOptionFailOnBinaryArchiveMiss reflection:nil error:&err];
 if(!pso)fail("PIPELINE_MISS","pso",err);
 printf("PIPELINE_SOURCE archive\n");
 id<MTLBuffer>ob=[dev newBufferWithLength:nout*4 options:MTLResourceStorageModeShared];
 id<MTLBuffer>rb=[dev newBufferWithBytes:ray length:sizeof(ray) options:MTLResourceStorageModeShared];
 id<MTLCommandBuffer>cb=[q commandBuffer]; id<MTLComputeCommandEncoder>en=[cb computeCommandEncoder];
 [en setComputePipelineState:pso];
 [en setAccelerationStructure:as atBufferIndex:0];
 [en setBuffer:ob offset:0 atIndex:1];
 [en setBuffer:rb offset:0 atIndex:2];
 [en dispatchThreads:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];
 [en endEncoding];[cb commit];[cb waitUntilCompleted];
 if([cb status]==MTLCommandBufferStatusError)fail("CMDBUF_ERROR","dispatch",[cb error]);
 float*o=[ob contents]; printf("OUT");for(int i=0;i<nout;i++)printf(" %g",o[i]);printf("\n");
 emit("OK");fflush(stdout);return 0;
}}
