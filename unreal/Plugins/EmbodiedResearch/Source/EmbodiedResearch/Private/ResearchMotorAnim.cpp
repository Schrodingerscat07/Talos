#include "ResearchMotorAnim.h"
#include "Animation/AnimSingleNodeInstanceProxy.h"
#include "BoneContainer.h"

// Apply local offsets inside pose evaluation, before the avatar's existing
// post-process graph. No game-thread UObject reads occur during evaluation.
struct FResearchMotorProxy : FAnimSingleNodeInstanceProxy
{
    explicit FResearchMotorProxy(UAnimInstance* Instance) : FAnimSingleNodeInstanceProxy(Instance) {}
    TArray<FResearchMotorChannel> Snapshot;
    virtual void PreUpdate(UAnimInstance* Instance, float DeltaSeconds) override
    {
        FAnimSingleNodeInstanceProxy::PreUpdate(Instance, DeltaSeconds);
        Snapshot = CastChecked<UResearchMotorAnim>(Instance)->Channels;
    }
    virtual bool Evaluate(FPoseContext& Output) override
    {
        const bool Result = FAnimSingleNodeInstanceProxy::Evaluate(Output);
        for (const auto& Channel : Snapshot)
        {
            const auto Index = Output.Pose.GetBoneContainer().MakeCompactPoseIndex(FMeshPoseBoneIndex(Channel.MeshIndex));
            if (Index.GetInt() == INDEX_NONE) continue;
            auto& Transform = Output.Pose[Index];
            Transform.SetRotation((Transform.GetRotation() * FQuat(Channel.Axis, FMath::DegreesToRadians(Channel.Degrees))).GetNormalized());
        }
        return Result;
    }
};

FAnimInstanceProxy* UResearchMotorAnim::CreateAnimInstanceProxy() { return new FResearchMotorProxy(this); }
void UResearchMotorAnim::DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) { delete Proxy; }
