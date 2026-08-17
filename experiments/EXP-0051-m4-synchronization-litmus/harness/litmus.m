/*
 * EXP-0051 authored Metal synchronization litmus runner.
 * Public Metal API + buffers owned by this process only. No tracing or BO scan.
 */
#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum ApiKind {
    API_SAME_ENCODER_NONE,
    API_SAME_ENCODER_BARRIER,
    API_ADJACENT_ENCODERS,
    API_SAME_QUEUE_TWO_CB,
    API_SAME_QUEUE_CPU_WAIT,
    API_TWO_QUEUE_UNSYNC_CONSUMER_FIRST,
    API_TWO_QUEUE_CPU_WAIT,
    API_TWO_QUEUE_EVENT,
    API_CPU_TO_GPU,
    API_GPU_TO_CPU,
};

static uint32_t asymmetric(uint32_t epoch,uint32_t index){
    uint32_t x=0x9e3779b9u*(index+1u)+0x85ebca6bu*(epoch+3u);
    return (x^(x>>13)^0xa5c31f27u)+(index<<16);
}

static NSString *load_text(const char *path,NSError **err){
    return [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:path]
                                     encoding:NSUTF8StringEncoding error:err];
}

static id<MTLComputePipelineState> make_pso(id<MTLDevice>dev,id<MTLLibrary>lib,NSString*name){
    NSError*err=nil;id<MTLFunction>fn=[lib newFunctionWithName:name];
    if(!fn){fprintf(stderr,"MISSING_FUNCTION %s\n",[name UTF8String]);return nil;}
    id<MTLComputePipelineState>p=[dev newComputePipelineStateWithFunction:fn error:&err];
    if(!p)fprintf(stderr,"PIPELINE_FAIL %s %s\n",[name UTF8String],[[err localizedDescription] UTF8String]);
    else printf("PIPELINE name=%s thread_width=%lu max_threads=%lu\n",[name UTF8String],
                (unsigned long)[p threadExecutionWidth],(unsigned long)[p maxTotalThreadsPerThreadgroup]);
    return p;
}

static int finish(id<MTLCommandBuffer>cb,const char*label){
    [cb commit];[cb waitUntilCompleted];
    if([cb status]!=MTLCommandBufferStatusCompleted||[cb error]){
        fprintf(stderr,"COMMAND_ERROR label=%s status=%ld error=%s\n",label,(long)[cb status],
                [cb error]?[[[cb error] localizedDescription] UTF8String]:"none");return 1;
    }
    return 0;
}

static void encode_dispatch(id<MTLComputeCommandEncoder>e,id<MTLComputePipelineState>p,
                            id<MTLBuffer>b0,id<MTLBuffer>b1,const uint32_t*scalar,
                            NSUInteger grid,NSUInteger tg){
    [e setComputePipelineState:p];[e setBuffer:b0 offset:0 atIndex:0];
    if(b1)[e setBuffer:b1 offset:0 atIndex:1];
    if(scalar)[e setBytes:scalar length:4 atIndex:2];
    [e dispatchThreads:MTLSizeMake(grid,1,1) threadsPerThreadgroup:MTLSizeMake(tg,1,1)];
}

static int run_barrier_case(id<MTLDevice>dev,id<MTLCommandQueue>q,
                            id<MTLComputePipelineState>p,const char*name){
    const NSUInteger groups=1024,threads=64;
    id<MTLBuffer>out=[dev newBufferWithLength:0x1000 options:MTLResourceStorageModeShared];
    id<MTLBuffer>scratch=[dev newBufferWithLength:groups*threads*4 options:MTLResourceStorageModeShared];
    memset([out contents],0,0x1000);((uint32_t*)[out contents])[2]=0xffffffffu;
    memset([scratch contents],0x5a,groups*threads*4);
    id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];
    encode_dispatch(e,p,out,scratch,NULL,groups*threads,threads);[e endEncoding];
    int error=finish(cb,name);uint32_t*r=[out contents];
    printf("BARRIER case=%s mismatch=%u checked=%u first_key=0x%08x observed=0x%08x command_errors=%d\n",
           name,r[0],r[1],r[2],r[3],error);return error;
}

static int run_message_case(id<MTLDevice>dev,id<MTLCommandQueue>q,
                            id<MTLComputePipelineState>p,const char*name,
                            int cross,uint32_t iterations){
    const NSUInteger groups=cross?2:64,threads=64,mailbox_size=24;
    id<MTLBuffer>boxes=[dev newBufferWithLength:(cross?1:groups)*mailbox_size options:MTLResourceStorageModeShared];
    id<MTLBuffer>out=[dev newBufferWithLength:0x1000 options:MTLResourceStorageModeShared];
    memset([boxes contents],0,[boxes length]);memset([out contents],0,0x1000);
    id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];
    encode_dispatch(e,p,boxes,out,&iterations,groups*threads,threads);[e endEncoding];
    int error=finish(cb,name);uint32_t*r=[out contents];
    uint32_t expected=(cross?1u:64u)*iterations;
    printf("MESSAGE case=%s topology=%s iterations=%u expected=%u mismatch_words=%u producer_timeouts=%u consumer_timeouts=%u completed=%u command_errors=%d\n",
           name,cross?"cross_threadgroup":"same_threadgroup",iterations,expected,r[0],r[1],r[2],r[3],error);
    return error;
}

static void encode_producer(id<MTLCommandBuffer>cb,id<MTLComputePipelineState>p,id<MTLBuffer>src,
                            uint32_t epoch,NSUInteger n){
    id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:p];
    [e setBuffer:src offset:0 atIndex:0];[e setBytes:&epoch length:4 atIndex:1];
    [e dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[e endEncoding];
}

static void encode_consumer(id<MTLCommandBuffer>cb,id<MTLComputePipelineState>p,id<MTLBuffer>src,
                            id<MTLBuffer>dst,NSUInteger n){
    id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];[e setComputePipelineState:p];
    [e setBuffer:src offset:0 atIndex:0];[e setBuffer:dst offset:0 atIndex:1];
    [e dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[e endEncoding];
}

static const char*api_name(enum ApiKind k){
    switch(k){
      case API_SAME_ENCODER_NONE:return "same_encoder_no_explicit_barrier";
      case API_SAME_ENCODER_BARRIER:return "same_encoder_buffer_barrier";
      case API_ADJACENT_ENCODERS:return "adjacent_compute_encoders";
      case API_SAME_QUEUE_TWO_CB:return "same_queue_two_cb_no_cpu_wait";
      case API_SAME_QUEUE_CPU_WAIT:return "same_queue_two_cb_cpu_wait";
      case API_TWO_QUEUE_UNSYNC_CONSUMER_FIRST:return "two_queue_unsync_consumer_first";
      case API_TWO_QUEUE_CPU_WAIT:return "two_queue_cpu_wait";
      case API_TWO_QUEUE_EVENT:return "two_queue_shared_event";
      case API_CPU_TO_GPU:return "cpu_write_to_gpu_after_commit_wait";
      case API_GPU_TO_CPU:return "gpu_write_to_cpu_after_completion_wait";
    }return "unknown";
}

static void reset_buffers(uint32_t*s,uint32_t*d,NSUInteger n,uint32_t epoch){
    uint32_t a=0xd00d0000u^epoch,b=0xbeef0000u^(epoch*17u);
    for(NSUInteger i=0;i<n;++i){s[i]=a;d[i]=b;}
}

static int run_api_case(id<MTLDevice>dev,id<MTLCommandQueue>q1,id<MTLCommandQueue>q2,
                        id<MTLComputePipelineState>prod,id<MTLComputePipelineState>cons,
                        id<MTLSharedEvent>event,enum ApiKind kind,uint32_t trials){
    const NSUInteger n=4096,bytes=n*4;
    id<MTLBuffer>src=[dev newBufferWithLength:bytes options:MTLResourceStorageModeShared];
    id<MTLBuffer>dst=[dev newBufferWithLength:bytes options:MTLResourceStorageModeShared];
    uint64_t mismatches=0,initial_source=0;uint32_t good=0,bad=0,errors=0;
    uint32_t first_epoch=0xffffffffu,first_index=0xffffffffu,first_got=0,first_want=0;
    for(uint32_t t=1;t<=trials;++t){
        uint32_t*s=[src contents],*d=[dst contents];reset_buffers(s,d,n,t);
        int e=0;
        if(kind==API_SAME_ENCODER_NONE||kind==API_SAME_ENCODER_BARRIER){
            id<MTLCommandBuffer>cb=[q1 commandBuffer];id<MTLComputeCommandEncoder>ce=[cb computeCommandEncoder];
            [ce setComputePipelineState:prod];[ce setBuffer:src offset:0 atIndex:0];[ce setBytes:&t length:4 atIndex:1];
            [ce dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];
            if(kind==API_SAME_ENCODER_BARRIER)[ce memoryBarrierWithScope:MTLBarrierScopeBuffers];
            [ce setComputePipelineState:cons];[ce setBuffer:src offset:0 atIndex:0];[ce setBuffer:dst offset:0 atIndex:1];
            [ce dispatchThreads:MTLSizeMake(n,1,1) threadsPerThreadgroup:MTLSizeMake(256,1,1)];[ce endEncoding];e+=finish(cb,api_name(kind));
        }else if(kind==API_ADJACENT_ENCODERS){
            id<MTLCommandBuffer>cb=[q1 commandBuffer];encode_producer(cb,prod,src,t,n);encode_consumer(cb,cons,src,dst,n);e+=finish(cb,api_name(kind));
        }else if(kind==API_SAME_QUEUE_TWO_CB||kind==API_SAME_QUEUE_CPU_WAIT){
            id<MTLCommandBuffer>a=[q1 commandBuffer];encode_producer(a,prod,src,t,n);[a commit];
            if(kind==API_SAME_QUEUE_CPU_WAIT)[a waitUntilCompleted];
            id<MTLCommandBuffer>b=[q1 commandBuffer];encode_consumer(b,cons,src,dst,n);[b commit];[b waitUntilCompleted];
            if(kind==API_SAME_QUEUE_TWO_CB)[a waitUntilCompleted];
            e+=([a status]!=MTLCommandBufferStatusCompleted||[a error]);e+=([b status]!=MTLCommandBufferStatusCompleted||[b error]);
        }else if(kind==API_TWO_QUEUE_UNSYNC_CONSUMER_FIRST){
            id<MTLCommandBuffer>b=[q2 commandBuffer];encode_consumer(b,cons,src,dst,n);[b commit];
            id<MTLCommandBuffer>a=[q1 commandBuffer];encode_producer(a,prod,src,t,n);[a commit];
            [b waitUntilCompleted];[a waitUntilCompleted];e+=([a status]!=MTLCommandBufferStatusCompleted||[a error]);e+=([b status]!=MTLCommandBufferStatusCompleted||[b error]);
        }else if(kind==API_TWO_QUEUE_CPU_WAIT){
            id<MTLCommandBuffer>a=[q1 commandBuffer];encode_producer(a,prod,src,t,n);e+=finish(a,api_name(kind));
            id<MTLCommandBuffer>b=[q2 commandBuffer];encode_consumer(b,cons,src,dst,n);e+=finish(b,api_name(kind));
        }else if(kind==API_TWO_QUEUE_EVENT){
            uint64_t value=(uint64_t)t;
            id<MTLCommandBuffer>b=[q2 commandBuffer];[b encodeWaitForEvent:event value:value];encode_consumer(b,cons,src,dst,n);[b commit];
            id<MTLCommandBuffer>a=[q1 commandBuffer];encode_producer(a,prod,src,t,n);[a encodeSignalEvent:event value:value];[a commit];
            [b waitUntilCompleted];[a waitUntilCompleted];e+=([a status]!=MTLCommandBufferStatusCompleted||[a error]);e+=([b status]!=MTLCommandBufferStatusCompleted||[b error]);
        }else if(kind==API_CPU_TO_GPU){
            for(NSUInteger i=0;i<n;++i)s[i]=asymmetric(t,(uint32_t)i);
            id<MTLCommandBuffer>cb=[q1 commandBuffer];encode_consumer(cb,cons,src,dst,n);e+=finish(cb,api_name(kind));
        }else if(kind==API_GPU_TO_CPU){
            id<MTLCommandBuffer>cb=[q1 commandBuffer];encode_producer(cb,prod,src,t,n);e+=finish(cb,api_name(kind));
        }
        uint64_t this_bad=0;uint32_t initial=0xd00d0000u^t;
        uint32_t*observed=(kind==API_GPU_TO_CPU)?s:d;
        for(NSUInteger i=0;i<n;++i){uint32_t want=asymmetric(t,(uint32_t)i),got=observed[i];
            if(got!=want){++this_bad;if(got==initial)++initial_source;if(first_epoch==0xffffffffu){first_epoch=t;first_index=(uint32_t)i;first_got=got;first_want=want;}}}
        mismatches+=this_bad;errors+=e;if(!this_bad&&!e)++good;else ++bad;
    }
    printf("API case=%s trials=%u words=%llu good=%u bad=%u mismatch_words=%llu initial_source_words=%llu first_epoch=%u first_index=%u first_got=0x%08x first_want=0x%08x command_errors=%u\n",
           api_name(kind),trials,(unsigned long long)trials*4096ull,good,bad,
           (unsigned long long)mismatches,(unsigned long long)initial_source,
           first_epoch,first_index,first_got,first_want,errors);
    return errors?1:0;
}

static int compile_probe(id<MTLDevice>dev,id<MTLCommandQueue>q,NSString*path){
    NSError*err=nil;NSString*src=[NSString stringWithContentsOfFile:path encoding:NSUTF8StringEncoding error:&err];
    NSString*base=[path lastPathComponent];id<MTLLibrary>lib=src?[dev newLibraryWithSource:src options:nil error:&err]:nil;
    if(!lib){
        printf("COMPILE_PROBE name=%s accepted=0 pipeline=0 executed=0\n",[base UTF8String]);
        printf("COMPILE_ERROR_BEGIN name=%s\n%s\nCOMPILE_ERROR_END name=%s\n",[base UTF8String],
               err?[[err description] UTF8String]:"source read failed",[base UTF8String]);return 0;
    }
    id<MTLComputePipelineState>p=make_pso(dev,lib,@"probe");if(!p){printf("COMPILE_PROBE name=%s accepted=1 pipeline=0 executed=0\n",[base UTF8String]);return 1;}
    id<MTLBuffer>flag=[dev newBufferWithLength:4096 options:MTLResourceStorageModeShared];
    id<MTLBuffer>out=[dev newBufferWithLength:4096 options:MTLResourceStorageModeShared];memset([flag contents],0,4096);memset([out contents],0xcc,4096);
    id<MTLCommandBuffer>cb=[q commandBuffer];id<MTLComputeCommandEncoder>e=[cb computeCommandEncoder];
    encode_dispatch(e,p,flag,out,NULL,2,2);[e endEncoding];int error=finish(cb,[base UTF8String]);uint32_t*f=[flag contents],*o=[out contents];
    printf("COMPILE_PROBE name=%s accepted=1 pipeline=1 executed=%d flag=0x%08x out0=0x%08x out1=0x%08x\n",
           [base UTF8String],!error,f[0],o[0],o[1]);return error;
}

int main(int argc,char**argv){@autoreleasepool{
    const char*source_path=NULL,*probe_dir=NULL;uint32_t trials=128,msg_tg_iters=256,msg_cross_iters=8192;
    for(int i=1;i<argc;++i){
        if(!strcmp(argv[i],"--source")&&i+1<argc)source_path=argv[++i];
        else if(!strcmp(argv[i],"--probe-dir")&&i+1<argc)probe_dir=argv[++i];
        else if(!strcmp(argv[i],"--api-trials")&&i+1<argc)trials=(uint32_t)strtoul(argv[++i],0,0);
        else if(!strcmp(argv[i],"--message-tg-iters")&&i+1<argc)msg_tg_iters=(uint32_t)strtoul(argv[++i],0,0);
        else if(!strcmp(argv[i],"--message-cross-iters")&&i+1<argc)msg_cross_iters=(uint32_t)strtoul(argv[++i],0,0);
        else{fprintf(stderr,"unknown/missing arg %s\n",argv[i]);return 2;}
    }
    if(!source_path||!probe_dir){fprintf(stderr,"--source and --probe-dir required\n");return 2;}
    id<MTLDevice>dev=MTLCreateSystemDefaultDevice();if(!dev)return 3;
    printf("DEVICE %s\nCONFIG api_trials=%u msg_tg_iters=%u msg_cross_iters=%u\n",[[dev name]UTF8String],trials,msg_tg_iters,msg_cross_iters);
    NSError*err=nil;NSString*src=load_text(source_path,&err);id<MTLLibrary>lib=src?[dev newLibraryWithSource:src options:nil error:&err]:nil;
    if(!lib){fprintf(stderr,"MAIN_LIBRARY_FAIL %s\n",[[err description]UTF8String]);return 4;}
    id<MTLCommandQueue>q1=[dev newCommandQueue],q2=[dev newCommandQueue];id<MTLSharedEvent>event=[dev newSharedEvent];
    const char*barriers[]={"tg_mem_threadgroup","tg_mem_none","simd_mem_threadgroup","tg_device_mem_device","tg_device_mem_wrong_class","tg_device_mem_both"};
    int errors=0;
    for(size_t i=0;i<sizeof(barriers)/sizeof(barriers[0]);++i){id<MTLComputePipelineState>p=make_pso(dev,lib,[NSString stringWithUTF8String:barriers[i]]);if(!p)return 5;errors+=run_barrier_case(dev,q1,p,barriers[i]);}
    struct{const char*n;int cross;}msgs[]={{"msg_tg_relaxed",0},{"msg_tg_fence_device",0},{"msg_tg_fence_tgscope",0},{"msg_cross_relaxed",1},{"msg_cross_fence_device",1}};
    for(size_t i=0;i<sizeof(msgs)/sizeof(msgs[0]);++i){id<MTLComputePipelineState>p=make_pso(dev,lib,[NSString stringWithUTF8String:msgs[i].n]);if(!p)return 6;errors+=run_message_case(dev,q1,p,msgs[i].n,msgs[i].cross,msgs[i].cross?msg_cross_iters:msg_tg_iters);}
    id<MTLComputePipelineState>prod=make_pso(dev,lib,@"ordered_producer"),cons=make_pso(dev,lib,@"ordered_consumer");if(!prod||!cons)return 7;
    for(enum ApiKind k=API_SAME_ENCODER_NONE;k<=API_GPU_TO_CPU;k++)errors+=run_api_case(dev,q1,q2,prod,cons,event,k,trials);
    NSArray<NSString*>*files=[[NSFileManager defaultManager]contentsOfDirectoryAtPath:[NSString stringWithUTF8String:probe_dir] error:&err];
    if(!files){fprintf(stderr,"PROBE_DIR_FAIL %s\n",[[err description]UTF8String]);return 8;}
    for(NSString*name in [files sortedArrayUsingSelector:@selector(compare:)])if([name hasSuffix:@".metal"])
        errors+=compile_probe(dev,q1,[[NSString stringWithUTF8String:probe_dir]stringByAppendingPathComponent:name]);
    printf("SUITE_DONE command_or_pipeline_errors=%d\n",errors);return errors?9:0;
}}
