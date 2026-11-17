#include "ResearchFaceAnim.h"
#include "Animation/AnimInstanceProxy.h"
#include "AnimNodes/AnimNode_CopyPoseFromMesh.h"

struct FResearchFaceProxy : FAnimInstanceProxy
{
    FAnimNode_CopyPoseFromMesh Copy;
    TArray<FResearchFaceChannel> Snapshot;
    explicit FResearchFaceProxy(UAnimInstance* Instance):FAnimInstanceProxy(Instance) {Copy.bUseAttachedParent=true;}
    virtual void Initialize(UAnimInstance* Instance) override
    {FAnimInstanceProxy::Initialize(Instance);Copy.Initialize_AnyThread(FAnimationInitializeContext(this));}
    virtual void CacheBones() override {Copy.CacheBones_AnyThread(FAnimationCacheBonesContext(this));}
    virtual void PreUpdate(UAnimInstance* Instance,float Delta) override
    {FAnimInstanceProxy::PreUpdate(Instance,Delta);Snapshot=CastChecked<UResearchFaceAnim>(Instance)->Channels;Copy.PreUpdate(Instance);}
    virtual void UpdateAnimationNode(const FAnimationUpdateContext& Context) override {Copy.Update_AnyThread(Context);}
    virtual bool Evaluate(FPoseContext& Output) override
    {
        Copy.Evaluate_AnyThread(Output);
        for(const auto& C:Snapshot) Output.Curve.Set(C.Curve,C.Value);
        return true;
    }
};
FAnimInstanceProxy* UResearchFaceAnim::CreateAnimInstanceProxy() {return new FResearchFaceProxy(this);}
void UResearchFaceAnim::DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) {delete Proxy;}
